# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ResUsers(models.Model):
    _inherit = "res.users"

    sc_personnel_department_id = fields.Many2one(
        "hr.department",
        string="部门",
        compute="_compute_sc_personnel_profile",
        inverse="_inverse_sc_personnel_department_id",
    )
    sc_personnel_job_id = fields.Many2one(
        "hr.job",
        string="岗位",
        compute="_compute_sc_personnel_profile",
        inverse="_inverse_sc_personnel_job_id",
    )
    sc_personnel_active = fields.Boolean(
        string="在职",
        compute="_compute_sc_personnel_profile",
        inverse="_inverse_sc_personnel_active",
    )
    sc_project_member_assignment_ids = fields.One2many(
        "sc.project.member.assignment",
        "user_id",
        string="项目成员授权",
    )
    sc_profile_document_ids = fields.One2many(
        "sc.user.profile.document",
        "user_id",
        string="人员档案附件",
    )

    @api.depends("employee_id", "employee_id.department_id", "employee_id.job_id", "employee_id.active")
    def _compute_sc_personnel_profile(self):
        for user in self:
            employee = user.employee_id
            user.sc_personnel_department_id = employee.department_id
            user.sc_personnel_job_id = employee.job_id
            user.sc_personnel_active = bool(employee and employee.active)

    def _sc_check_personnel_maintainer(self):
        if not self.env.user.has_group("smart_construction_core.group_sc_cap_business_config_admin"):
            raise AccessError(_("仅业务配置管理员可以维护人员档案。"))
        allowed_companies = self.env.user.company_ids
        if any(user.company_id not in allowed_companies for user in self):
            raise AccessError(_("不能维护当前管理员公司范围之外的人员档案。"))

    def _sc_ensure_employee_profile(self):
        self.ensure_one()
        self._sc_check_personnel_maintainer()
        employee = self.env["hr.employee"].sudo().with_context(active_test=False).search(
            [("user_id", "=", self.id), ("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if employee:
            return employee.with_env(self.env)
        employee = self.env["hr.employee"].sudo().create(
            {
                "name": self.name,
                "user_id": self.id,
                "work_email": self.email,
                "work_phone": self.phone,
                "company_id": self.company_id.id,
            }
        )
        return employee.with_env(self.env)

    def action_sc_ensure_employee_profile(self):
        for user in self:
            user._sc_ensure_employee_profile()
        return True

    def _inverse_sc_personnel_department_id(self):
        for user in self:
            employee = user._sc_ensure_employee_profile()
            employee.sudo().write({"department_id": user.sc_personnel_department_id.id})

    def _inverse_sc_personnel_job_id(self):
        for user in self:
            employee = user._sc_ensure_employee_profile()
            employee.sudo().write({"job_id": user.sc_personnel_job_id.id})

    def _inverse_sc_personnel_active(self):
        for user in self:
            employee = user.employee_id
            if employee or user.sc_personnel_active:
                user._sc_ensure_employee_profile().sudo().write({"active": user.sc_personnel_active})


class ScProjectMemberAssignment(models.Model):
    _name = "sc.project.member.assignment"
    _description = "Project Member Authority Assignment"
    _order = "active desc, project_id, user_id"

    project_id = fields.Many2one(
        "project.project",
        string="项目",
        required=True,
        index=True,
        ondelete="restrict",
    )
    user_id = fields.Many2one(
        "res.users",
        string="用户",
        required=True,
        index=True,
        ondelete="restrict",
        domain=[("share", "=", False)],
    )
    company_id = fields.Many2one(
        "res.company",
        related="project_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)
    source = fields.Selection(
        [("manual", "正式维护"), ("approved_migration", "获批迁移")],
        required=True,
        default="manual",
    )
    note = fields.Char(string="审计说明")
    sc_follower_owned = fields.Boolean(
        string="契约创建的关注关系",
        default=False,
        readonly=True,
        copy=False,
    )

    _sql_constraints = [
        ("sc_project_member_assignment_unique", "unique(project_id, user_id)", "同一用户在同一项目只能有一条成员授权。"),
    ]

    @api.constrains("project_id", "user_id")
    def _check_company_scope(self):
        for assignment in self:
            if assignment.project_id.company_id not in assignment.user_id.company_ids:
                raise ValidationError(_("项目公司必须位于用户的多公司访问范围内。"))

    def _sc_is_follower(self):
        self.ensure_one()
        return self.user_id.partner_id in self.project_id.message_partner_ids

    def _sc_activate_follower(self):
        self.ensure_one()
        if not self.active or self._sc_is_follower():
            return False
        self.project_id.message_subscribe(partner_ids=self.user_id.partner_id.ids)
        return True

    def _sc_release_owned_follower(self, project, user, owned):
        if owned and project and user:
            project.message_unsubscribe(partner_ids=user.partner_id.ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.pop("sc_follower_owned", None)
        assignments = super().create(vals_list)
        for assignment in assignments:
            if assignment._sc_activate_follower():
                super(ScProjectMemberAssignment, assignment).write({"sc_follower_owned": True})
        return assignments

    def write(self, vals):
        if "sc_follower_owned" in vals:
            raise AccessError(_("项目成员 follower 所有权只能由正式成员契约维护。"))
        authority_change = bool({"project_id", "user_id", "active"} & set(vals))
        before = {
            assignment.id: (
                assignment.project_id,
                assignment.user_id,
                assignment.sc_follower_owned,
            )
            for assignment in self
        }
        result = super().write(vals)
        if not authority_change:
            return result
        for assignment in self:
            old_project, old_user, old_owned = before[assignment.id]
            identity_changed = old_project != assignment.project_id or old_user != assignment.user_id
            if old_owned and (identity_changed or not assignment.active):
                assignment._sc_release_owned_follower(old_project, old_user, True)
                super(ScProjectMemberAssignment, assignment).write({"sc_follower_owned": False})
            if assignment.active and (identity_changed or not assignment._sc_is_follower()):
                if assignment._sc_activate_follower():
                    super(ScProjectMemberAssignment, assignment).write({"sc_follower_owned": True})
        return result

    def unlink(self):
        raise UserError(_("项目成员授权必须停用，不能物理删除，以保留审计记录。"))


class ScUserProfileDocument(models.Model):
    _name = "sc.user.profile.document"
    _description = "Formal User Profile Document"
    _order = "user_id, document_kind, id"

    name = fields.Char(string="文档名称", required=True)
    user_id = fields.Many2one(
        "res.users",
        string="用户",
        required=True,
        index=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company",
        string="公司",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    document_kind = fields.Selection(
        [
            ("signature", "签章"),
            ("credential", "证件/资质"),
            ("personnel_archive", "人员档案"),
        ],
        string="文档类型",
        required=True,
    )
    file_name = fields.Char(string="文件名", required=True)
    file_data = fields.Binary(string="文件", required=True, attachment=True)
    active = fields.Boolean(default=True)
    note = fields.Char(string="说明")

    @api.constrains("user_id", "company_id")
    def _check_user_company_scope(self):
        for document in self:
            if document.company_id not in document.user_id.company_ids:
                raise ValidationError(_("档案公司必须位于用户的多公司访问范围内。"))

    def unlink(self):
        raise UserError(_("正式用户档案必须停用，不能物理删除。"))
