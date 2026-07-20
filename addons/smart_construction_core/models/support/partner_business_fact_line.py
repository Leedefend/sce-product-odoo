# -*- coding: utf-8 -*-
from odoo import fields, models, tools
from odoo.exceptions import UserError


class ScPartnerBusinessFactLine(models.Model):
    _name = "sc.partner.business.fact.line"
    _inherit = "sc.optional.customer.projection"
    _description = "客户供应商关联业务明细"
    _auto = False
    _rec_name = "display_name"
    _order = "document_date desc, id desc"

    display_name = fields.Char(string="业务摘要", readonly=True)
    partner_id = fields.Many2one("res.partner", string="往来单位", readonly=True, index=True)
    business_role = fields.Selection(
        [("customer", "客户"), ("supplier", "供应商")],
        string="业务方向",
        readonly=True,
        index=True,
    )
    source_label = fields.Char(string="业务类型", readonly=True, index=True)
    project_id = fields.Many2one("project.project", string="项目", readonly=True, index=True)
    project_name = fields.Char(string="项目名称", readonly=True, index=True)
    document_no = fields.Char(string="单据编号", readonly=True, index=True)
    document_date = fields.Date(string="单据日期", readonly=True, index=True)
    amount = fields.Monetary(string="金额", currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one("res.currency", string="币种", readonly=True)
    document_state = fields.Char(string="单据状态", readonly=True, index=True)
    creator_name = fields.Char(string="录入人", readonly=True, index=True)
    created_time = fields.Datetime(string="录入时间", readonly=True, index=True)
    source_model = fields.Char(string="来源模型", readonly=True, index=True)
    source_res_id = fields.Integer(string="来源记录", readonly=True, index=True)
    source_note = fields.Text(string="说明", readonly=True)

    def init(self):
        self._create_empty_projection_view()

    def action_open_source_record(self):
        self.ensure_one()
        if not self.source_model or not self.source_res_id or self.source_model not in self.env:
            raise UserError("没有可打开的来源业务单据。")
        source = self.env[self.source_model].browse(self.source_res_id).exists()
        if not source:
            raise UserError("来源业务单据不存在或已被归档清理。")
        return {
            "type": "ir.actions.act_window",
            "name": self.source_label or source.display_name,
            "res_model": self.source_model,
            "res_id": source.id,
            "view_mode": "form",
            "target": "current",
        }
