# -*- coding: utf-8 -*-
import base64

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "user_module_product_closure")
class TestUserModuleProductClosure(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        config_group = cls.env.ref("smart_construction_core.group_sc_cap_business_config_admin")
        internal_group = cls.env.ref("base.group_user")
        cls.config_admin = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "User Closure Config Admin",
                "login": "user_closure_config_admin",
                "company_id": cls.env.company.id,
                "company_ids": [(6, 0, cls.env.company.ids)],
                "groups_id": [(6, 0, (internal_group | config_group).ids)],
            }
        )
        cls.member = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "User Closure Member",
                "login": "user_closure_member",
                "company_id": cls.env.company.id,
                "company_ids": [(6, 0, cls.env.company.ids)],
                "groups_id": [(6, 0, internal_group.ids)],
            }
        )
        cls.other_user = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "User Closure Other",
                "login": "user_closure_other",
                "company_id": cls.env.company.id,
                "company_ids": [(6, 0, cls.env.company.ids)],
                "groups_id": [(6, 0, internal_group.ids)],
            }
        )
        cls.project = cls.env["project.project"].create(
            {"name": "User Closure Project", "company_id": cls.env.company.id}
        )

    def test_config_admin_creates_and_maintains_employee_profile(self):
        user = self.member.with_user(self.config_admin)

        user.action_sc_ensure_employee_profile()
        department = self.env["hr.department"].create({"name": "Closure Department"})
        job = self.env["hr.job"].create({"name": "Closure Job"})
        user.write(
            {
                "sc_personnel_department_id": department.id,
                "sc_personnel_job_id": job.id,
                "sc_personnel_active": True,
            }
        )

        self.assertEqual(user.employee_id.user_id, self.member)
        self.assertEqual(user.employee_id.department_id, department)
        self.assertEqual(user.employee_id.job_id, job)
        self.assertTrue(user.employee_id.active)

    def test_ordinary_user_cannot_create_employee_profile(self):
        with self.assertRaises(AccessError):
            self.other_user.with_user(self.member).action_sc_ensure_employee_profile()

    def test_project_assignment_uses_follower_authority_and_archives(self):
        Assignment = self.env["sc.project.member.assignment"].with_user(self.config_admin)

        assignment = Assignment.create(
            {"project_id": self.project.id, "user_id": self.member.id, "source": "manual"}
        )

        self.assertIn(self.member.partner_id, self.project.message_partner_ids)
        self.assertTrue(assignment.sc_follower_owned)
        with self.assertRaises(AccessError):
            assignment.write({"sc_follower_owned": False})

        assignment.write({"active": False})
        self.assertNotIn(self.member.partner_id, self.project.message_partner_ids)
        with self.assertRaises(UserError):
            assignment.unlink()

    def test_preexisting_follower_is_not_removed_by_assignment(self):
        self.project.message_subscribe(partner_ids=self.other_user.partner_id.ids)
        assignment = self.env["sc.project.member.assignment"].with_user(self.config_admin).create(
            {"project_id": self.project.id, "user_id": self.other_user.id}
        )

        self.assertFalse(assignment.sc_follower_owned)
        assignment.write({"active": False})
        self.assertIn(self.other_user.partner_id, self.project.message_partner_ids)

    def test_profile_document_is_company_scoped_and_owner_read_only(self):
        document = self.env["sc.user.profile.document"].with_user(self.config_admin).create(
            {
                "name": "Approved credential",
                "user_id": self.member.id,
                "company_id": self.env.company.id,
                "document_kind": "credential",
                "file_name": "credential.txt",
                "file_data": base64.b64encode(b"profile-document-contract"),
            }
        )

        own_document = document.with_user(self.member)
        self.assertEqual(own_document.name, "Approved credential")
        self.assertEqual(own_document.file_data, base64.b64encode(b"profile-document-contract"))
        with self.assertRaises(AccessError):
            document.with_user(self.member).write({"note": "forbidden"})
        with self.assertRaises(AccessError):
            document.with_user(self.other_user).read(["name", "file_data"])
        attachment = self.env["ir.attachment"].sudo().search(
            [
                ("res_model", "=", "sc.user.profile.document"),
                ("res_id", "=", document.id),
                ("res_field", "=", "file_data"),
            ],
            limit=1,
        )
        self.assertTrue(attachment)
        with self.assertRaises(AccessError):
            attachment.with_user(self.other_user).read(["datas"])
        with self.assertRaises(AccessError):
            attachment.with_user(self.member).write({"name": "forbidden.txt"})
        with self.assertRaises(UserError):
            document.unlink()

    def test_profile_document_rejects_cross_company_admin_access(self):
        other_company = self.env["res.company"].create({"name": "Closure Document Company"})
        other_company_user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Closure Document Other Company User",
                "login": "closure_document_other_company_user",
                "company_id": other_company.id,
                "company_ids": [(6, 0, other_company.ids)],
                "groups_id": [(6, 0, self.env.ref("base.group_user").ids)],
            }
        )
        document = self.env["sc.user.profile.document"].sudo().create(
            {
                "name": "Other company credential",
                "user_id": other_company_user.id,
                "company_id": other_company.id,
                "document_kind": "credential",
                "file_name": "other.txt",
                "file_data": base64.b64encode(b"other-company"),
            }
        )

        with self.assertRaises(AccessError):
            document.with_user(self.config_admin).read(["name"])
        with self.assertRaises(AccessError):
            document.with_user(self.config_admin).write({"note": "forbidden"})

    def test_ordinary_user_cannot_maintain_project_assignment(self):
        with self.assertRaises(AccessError):
            self.env["sc.project.member.assignment"].with_user(self.member).create(
                {"project_id": self.project.id, "user_id": self.member.id}
            )

    def test_membership_rejects_project_outside_user_company_scope(self):
        other_company = self.env["res.company"].create({"name": "Closure Other Company"})
        project = self.env["project.project"].create(
            {"name": "Closure Other Company Project", "company_id": other_company.id}
        )

        with self.assertRaises(ValidationError):
            self.env["sc.project.member.assignment"].create(
                {"project_id": project.id, "user_id": self.member.id}
            )
