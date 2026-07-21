# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "runtime_user_management")
class TestRuntimeUserManagement(TransactionCase):
    def _create_runtime_user(self, login, name, managed=False):
        return self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "login": login,
                "name": name,
                "email": "%s@example.test" % login,
                "sc_runtime_user_managed": managed,
            }
        )

    def test_managed_internal_login_counts_as_runtime_company_user(self):
        user = self._create_runtime_user("runtime_user_scope", "正式用户", managed=True)

        users = self.env["res.users"].search([("sc_runtime_company_real_user", "=", True)])

        self.assertIn(user, users)

    def test_unmanaged_login_is_excluded_from_runtime_company_user(self):
        user = self._create_runtime_user("runtime_unmanaged_scope", "非受管用户")

        users = self.env["res.users"].search([("sc_runtime_company_real_user", "=", True)])

        self.assertNotIn(user, users)

    def test_runtime_source_login_uses_canonical_login(self):
        user = self._create_runtime_user("runtime_display_scope", "正式用户", managed=True)

        self.assertEqual(user.sc_runtime_source_login, "runtime_display_scope")

    def test_runtime_source_login_is_searchable(self):
        user = self._create_runtime_user("runtime_search_original", "正式用户", managed=True)

        users = self.env["res.users"].search([("sc_runtime_source_login", "ilike", "search_original")])

        self.assertIn(user, users)

    def test_runtime_user_creation_requires_explicit_initial_password(self):
        Users = self.env["res.users"].with_context(sc_runtime_user_management=True)

        with self.assertRaises(ValidationError):
            Users._sc_runtime_user_safe_vals({"login": "boundary_user", "name": "Boundary User"})

    def test_runtime_user_creation_accepts_context_secret_without_default(self):
        Users = self.env["res.users"].with_context(
            sc_runtime_user_management=True,
            sc_default_initial_password="runtime-only-secret",
        )

        vals = Users._sc_runtime_user_safe_vals({"login": "boundary_user", "name": "Boundary User"})

        self.assertEqual(vals["password"], "runtime-only-secret")

    def test_runtime_user_company_must_be_in_multi_company_scope(self):
        Users = self.env["res.users"].with_context(
            sc_runtime_user_management=True,
            sc_default_initial_password="runtime-only-secret",
        )

        with self.assertRaises(ValidationError):
            Users._sc_runtime_user_safe_vals(
                {
                    "login": "invalid_company_scope",
                    "name": "Invalid Company Scope",
                    "company_id": self.env.company.id,
                    "company_ids": [(6, 0, [])],
                }
            )

    def test_runtime_user_incremental_company_commands_preserve_main_company(self):
        other_company = self.env["res.company"].create({"name": "Runtime Scope Other Company"})
        self.env.user.write({"company_ids": [(4, other_company.id)]})
        user = self._create_runtime_user("runtime_company_commands", "Runtime Company Commands")
        Users = self.env["res.users"].with_context(sc_runtime_user_management=True)

        with self.assertRaises(ValidationError):
            Users._sc_runtime_user_safe_vals(
                {"company_ids": [(3, self.env.company.id), (4, other_company.id)]},
                existing_user=user,
            )

    def test_security_changes_increment_token_epoch(self):
        user = self._create_runtime_user("token_epoch_boundary", "Token Epoch Boundary")
        before = user.token_version

        user.write({"active": False})

        self.assertEqual(user.token_version, before + 1)

    def test_profile_changes_do_not_increment_token_epoch(self):
        user = self._create_runtime_user("profile_epoch_boundary", "Profile Epoch Boundary")
        before = user.token_version

        user.write({"name": "Profile Epoch Boundary Updated"})

        self.assertEqual(user.token_version, before)
