# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools
from odoo.exceptions import UserError


class ScFundDailySummary(models.Model):
    _name = "sc.fund.daily.summary"
    _inherit = "sc.optional.customer.projection"
    _description = "企业资金日报汇总"
    _auto = False
    _rec_name = "display_name"
    _order = "document_date desc, business_entity_id"
    _sc_readonly_navigation_button_methods = {"action_open_snapshot_facts"}

    display_name = fields.Char(string="汇总项", readonly=True)
    document_date = fields.Date(string="日期", readonly=True, index=True)
    company_id = fields.Many2one("res.company", string="隔离公司", readonly=True, index=True)
    business_entity_id = fields.Many2one("sc.business.entity", string="业务核算主体", readonly=True, index=True)
    business_entity_name = fields.Char(string="业务核算主体名称", readonly=True)
    project_id = fields.Many2one("project.project", string="来源项目", readonly=True, index=True)
    project_name = fields.Char(string="来源项目名称", readonly=True)
    account_name = fields.Char(string="账户名称", readonly=True, index=True)
    bank_account_no = fields.Char(string="银行账号", readonly=True)
    line_count = fields.Integer(string="明细数", readonly=True)
    daily_income = fields.Float(string="当日收入", readonly=True)
    daily_expense = fields.Float(string="当日支出", readonly=True)
    net_amount = fields.Float(string="收支净额", readonly=True)
    account_balance = fields.Float(string="账面余额", readonly=True)
    current_account_balance = fields.Float(string="当前账面余额", readonly=True)
    current_bank_balance = fields.Float(string="当前银行余额", readonly=True)
    bank_system_difference = fields.Float(string="账实差异", readonly=True)

    def _raise_readonly_projection(self):
        raise UserError("企业资金日报汇总是历史事实汇总结果，请从来源企业资金日报维护数据。")

    @api.model_create_multi
    def create(self, vals_list):
        self._raise_readonly_projection()

    def write(self, vals):
        self._raise_readonly_projection()

    def unlink(self):
        self._raise_readonly_projection()

    def _snapshot_fact_domain(self):
        self.ensure_one()
        return [
            ("document_scope", "=", "enterprise"),
            ("business_entity_id", "=", self.business_entity_id.id if self.business_entity_id else False),
            ("snapshot_date", "=", self.document_date),
            ("company_id", "=", self.company_id.id if self.company_id else False),
            ("project_id", "=", self.project_id.id if self.project_id else False),
        ]

    def action_open_snapshot_facts(self):
        self.ensure_one()
        action = self.env.ref("smart_construction_core.action_sc_fund_daily", raise_if_not_found=False)
        result = action.sudo().read()[0] if action else {"type": "ir.actions.act_window", "view_mode": "tree,form"}
        result.update(
            {
                "name": "%s / 企业资金日报" % (self.display_name or "企业资金日报汇总"),
                "domain": self._snapshot_fact_domain(),
                "context": {"create": False, "search_default_scope_enterprise": 1},
                "target": "current",
            }
        )
        return result

    def init(self):
        self._create_empty_projection_view()
