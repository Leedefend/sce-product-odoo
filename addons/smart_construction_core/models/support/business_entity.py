# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ScBusinessEntity(models.Model):
    _name = "sc.business.entity"
    _description = "业务核算主体"
    _order = "company_id, sequence, name"
    _rec_name = "name"

    sequence = fields.Integer(default=10, index=True)
    name = fields.Char(string="名称", required=True, index=True)
    company_id = fields.Many2one(
        "res.company", string="隔离公司", required=True,
        default=lambda self: self.env.company, index=True, ondelete="restrict",
    )
    partner_id = fields.Many2one("res.partner", string="关联往来单位", index=True, ondelete="set null")
    project_name = fields.Char(string="项目名称", index=True)
    document_state_text = fields.Char(string="单据状态", index=True)
    push_result = fields.Char(string="推送结果", index=True)
    cooperation_type = fields.Char(string="合作类型", index=True)
    bank_name = fields.Char(string="开户银行", index=True)
    bank_account_no = fields.Char(string="账号", index=True)
    bank_account_holder = fields.Char(string="开户姓名", index=True)
    social_credit_code = fields.Char(string="统一社会信用代码", index=True)
    main_tax_rate = fields.Char(string="主税率")
    receipt_amount = fields.Monetary(string="收款金额", currency_field="currency_id")
    payment_amount = fields.Monetary(string="付款金额", currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", string="币种", required=True,
        default=lambda self: self.env.ref("base.CNY", raise_if_not_found=False).id
        or self.env.company.currency_id.id,
    )
    entry_user_name = fields.Char(string="录入人", index=True)
    entry_time = fields.Datetime(string="录入时间", index=True)
    entity_type = fields.Selection(
        [
            ("internal", "内部核算"), ("affiliate", "挂靠/关联主体"),
            ("trade", "商贸主体"), ("labor", "劳务主体"),
            ("platform", "平台主体"), ("project_carrier", "项目经营载体"),
            ("unknown", "待确认"),
        ],
        string="主体类型", default="unknown", required=True, index=True,
    )
    note = fields.Text(string="备注")
    active = fields.Boolean(default=True, index=True)

    @api.constrains("company_id", "partner_id")
    def _check_partner_company(self):
        for record in self:
            partner_company = record.partner_id.company_id
            if partner_company and partner_company != record.company_id:
                raise ValidationError(_("关联往来单位必须属于同一隔离公司或为共享往来单位。"))
