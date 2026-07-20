# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class ScOperatingMetricsProject(models.Model):
    """
    经营指标（项目维度）SQL 视图：
    - 只读聚合视图，不在查询时创建数据；
    - 指标口径依赖结算单（store=True）聚合，风险数在视图内近似统计。
    """

    _name = "sc.operating.metrics.project"
    _inherit = "sc.optional.customer.projection"
    _description = "经营指标（项目）"
    _rec_name = "project_id"
    _order = "project_id desc"
    _auto = False

    project_id = fields.Many2one("project.project", string="项目", required=True, index=True, readonly=True)
    company_id = fields.Many2one("res.company", string="公司", readonly=True, index=True)
    currency_id = fields.Many2one("res.currency", string="币种", readonly=True)

    receipt_amount = fields.Monetary(string="本期收款", currency_field="currency_id", readonly=True)
    output_invoice_amount = fields.Monetary(string="销项开票金额", currency_field="currency_id", readonly=True)
    output_tax_amount = fields.Monetary(string="销项税额", currency_field="currency_id", readonly=True)
    input_invoice_amount = fields.Monetary(string="进项发票金额", currency_field="currency_id", readonly=True)
    input_tax_amount = fields.Monetary(string="进项税额", currency_field="currency_id", readonly=True)
    prepaid_tax_amount = fields.Monetary(string="预缴税额", currency_field="currency_id", readonly=True)
    deduction_amount = fields.Monetary(string="抵扣金额", currency_field="currency_id", readonly=True)
    deduction_tax_amount = fields.Monetary(string="抵扣税额", currency_field="currency_id", readonly=True)
    deduction_surcharge_amount = fields.Monetary(string="抵扣附加税", currency_field="currency_id", readonly=True)
    company_finance_income_amount = fields.Monetary(string="公司财务收入", currency_field="currency_id", readonly=True)
    company_finance_expense_amount = fields.Monetary(string="公司财务支出", currency_field="currency_id", readonly=True)
    deduction_paid_amount = fields.Monetary(string="扣款实缴", currency_field="currency_id", readonly=True)
    deduction_refund_amount = fields.Monetary(string="扣款退回", currency_field="currency_id", readonly=True)
    expense_amount = fields.Monetary(string="费用/保证金支出", currency_field="currency_id", readonly=True)
    net_cash_amount = fields.Monetary(string="经营现金净额", currency_field="currency_id", readonly=True)
    tax_balance_amount = fields.Monetary(string="税额净额", currency_field="currency_id", readonly=True)
    settlement_amount_total = fields.Monetary(string="结算总额", currency_field="currency_id", readonly=True)
    settlement_amount_paid = fields.Monetary(string="已付金额", currency_field="currency_id", readonly=True)
    settlement_amount_payable = fields.Monetary(string="可付余额", currency_field="currency_id", readonly=True)

    receipt_count = fields.Integer(string="收款单数", readonly=True)
    invoice_count = fields.Integer(string="发票数", readonly=True)
    tax_deduction_count = fields.Integer(string="抵扣登记数", readonly=True)
    source_line_count = fields.Integer(string="来源明细数", readonly=True)
    overpay_risk_count = fields.Integer(string="超付风险单数", readonly=True)
    three_way_missing_count = fields.Integer(string="三单缺失项", readonly=True)
    coverage_note = fields.Char(string="承载说明", readonly=True)

    def init(self):
        self._create_empty_projection_view()
