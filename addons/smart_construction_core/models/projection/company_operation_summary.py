# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, tools
from odoo.exceptions import UserError


class ScCompanyOperationSummary(models.Model):
    _name = "sc.company.operation.summary"
    _inherit = "sc.optional.customer.projection"
    _description = "公司经营情况表"
    _auto = False
    _rec_name = "period_label"
    _order = "period_year desc, period_month desc"
    _sc_readonly_navigation_button_methods = {
        "action_open_deduction_paid",
        "action_open_company_income",
        "action_open_reimbursements",
        "action_open_payroll_documents",
        "action_open_deduction_refunds",
        "action_open_company_expenses",
    }

    period_label = fields.Char(string="年-月份", readonly=True)
    period_year = fields.Integer(string="年度", readonly=True, index=True)
    period_month = fields.Integer(string="月份", readonly=True, index=True)
    company_id = fields.Many2one("res.company", string="公司", readonly=True, index=True)
    currency_id = fields.Many2one("res.currency", string="币种", readonly=True)

    revenue_amount = fields.Monetary(string="营收", currency_field="currency_id", readonly=True)

    deduction_management_fee_amount = fields.Monetary(string="扣款实缴登记/管理费", currency_field="currency_id", readonly=True)
    deduction_enterprise_income_tax_amount = fields.Monetary(string="扣款实缴登记/企业所得税", currency_field="currency_id", readonly=True)
    deduction_vat_surcharge_amount = fields.Monetary(string="扣款实缴登记/增值税附加", currency_field="currency_id", readonly=True)
    deduction_vat_surcharge_nonrefundable_amount = fields.Monetary(
        string="扣款实缴登记/增值税附加(不可退)",
        currency_field="currency_id",
        readonly=True,
    )
    company_interest_income_amount = fields.Monetary(string="财务收入/利息公司", currency_field="currency_id", readonly=True)
    bid_document_fee_income_amount = fields.Monetary(string="财务收入/标书制作费", currency_field="currency_id", readonly=True)
    appearance_fee_income_amount = fields.Monetary(string="财务收入/出场费", currency_field="currency_id", readonly=True)
    certificate_fee_income_amount = fields.Monetary(string="财务收入/证书费", currency_field="currency_id", readonly=True)
    company_operation_income_amount = fields.Monetary(string="财务收入/公司经营收入", currency_field="currency_id", readonly=True)
    union_fee_income_amount = fields.Monetary(string="财务收入/工会经费", currency_field="currency_id", readonly=True)
    branch_annual_fee_income_amount = fields.Monetary(string="财务收入/分公司年费", currency_field="currency_id", readonly=True)
    disability_fund_income_amount = fields.Monetary(string="财务收入/残保金", currency_field="currency_id", readonly=True)
    personal_income_tax_income_amount = fields.Monetary(string="财务收入/个人所得税", currency_field="currency_id", readonly=True)
    income_amount = fields.Monetary(string="收入合计", currency_field="currency_id", readonly=True)

    expense_amount = fields.Monetary(string="支出合计", currency_field="currency_id", readonly=True)
    reimbursement_amount = fields.Monetary(string="报销申请/报销", currency_field="currency_id", readonly=True)
    salary_amount = fields.Monetary(string="工资登记/工资", currency_field="currency_id", readonly=True)
    employee_social_security_amount = fields.Monetary(string="社保登记/员工社保", currency_field="currency_id", readonly=True)
    certificate_social_security_amount = fields.Monetary(string="社保登记/证书社保", currency_field="currency_id", readonly=True)
    deduction_refund_surcharge_amount = fields.Monetary(string="扣款实缴退回/增值税附加退项目", currency_field="currency_id", readonly=True)
    company_enterprise_income_tax_expense_amount = fields.Monetary(string="公司财务支出/企业所得税", currency_field="currency_id", readonly=True)
    company_personal_income_tax_expense_amount = fields.Monetary(string="公司财务支出/个人所得税", currency_field="currency_id", readonly=True)
    company_vat_surcharge_tax_bureau_amount = fields.Monetary(string="公司财务支出/增值税附加交税务局", currency_field="currency_id", readonly=True)
    tender_fee_expense_amount = fields.Monetary(string="公司财务支出/投标费", currency_field="currency_id", readonly=True)
    appearance_fee_expense_amount = fields.Monetary(string="公司财务支出/出场费", currency_field="currency_id", readonly=True)
    company_operation_expense_amount = fields.Monetary(string="公司财务支出/公司经营支出", currency_field="currency_id", readonly=True)
    company_interest_expense_amount = fields.Monetary(string="公司财务支出/利息公司", currency_field="currency_id", readonly=True)
    disability_fund_expense_amount = fields.Monetary(string="公司财务支出/残保金", currency_field="currency_id", readonly=True)
    union_fee_expense_amount = fields.Monetary(string="公司财务支出/工会经费", currency_field="currency_id", readonly=True)
    service_fee_expense_amount = fields.Monetary(string="公司财务支出/手续费", currency_field="currency_id", readonly=True)

    source_line_count = fields.Integer(string="来源明细数", readonly=True)
    coverage_note = fields.Char(string="承载说明", readonly=True)

    def _raise_readonly_projection(self):
        raise UserError("公司经营情况表是月度经营事实汇总结果，请从来源业务单据维护数据。")

    @api.model_create_multi
    def create(self, vals_list):
        self._raise_readonly_projection()

    def write(self, vals):
        self._raise_readonly_projection()

    def unlink(self):
        self._raise_readonly_projection()

    def _month_start(self):
        self.ensure_one()
        return date(self.period_year, self.period_month, 1)

    def _next_month_start(self):
        month_start = self._month_start()
        if month_start.month == 12:
            return date(month_start.year + 1, 1, 1)
        return date(month_start.year, month_start.month + 1, 1)

    def _date_month_domain(self, field_name):
        self.ensure_one()
        return [(field_name, ">=", self._month_start()), (field_name, "<", self._next_month_start())]

    def _char_date_month_domain(self, field_name):
        self.ensure_one()
        return [
            (field_name, ">=", self._month_start().isoformat()),
            (field_name, "<", self._next_month_start().isoformat()),
        ]

    def _open_action(self, action_xmlid, name, domain, context=None):
        self.ensure_one()
        action = self.env.ref(action_xmlid, raise_if_not_found=False)
        result = action.sudo().read()[0] if action else {"type": "ir.actions.act_window", "view_mode": "tree,form"}
        result.update(
            {
                "name": "%s / %s" % (self.period_label or "公司经营情况表", name),
                "domain": domain,
                "context": context or {"create": False},
                "target": "current",
            }
        )
        return result

    def action_open_deduction_paid(self):
        return self._open_action(
            "smart_construction_core.action_sc_customer_projection_unavailable",
            "扣款实缴明细",
            [("active", "=", True)] + self._date_month_domain("document_date"),
            {"create": False, "search_default_group_item": 1},
        )

    def action_open_company_income(self):
        return self._open_action(
            "smart_construction_core.action_sc_receipt_income",
            "公司财务收入",
            [
                ("active", "=", True),
                ("business_category_id.code", "=", "finance.receipt.company"),
            ]
            + self._date_month_domain("date_receipt"),
            {"create": False, "search_default_group_income_category": 1},
        )

    def action_open_reimbursements(self):
        return self._open_action(
            "smart_construction_core.action_sc_customer_projection_unavailable",
            "历史费用报销明细",
            [("active", "=", True)] + self._char_date_month_domain("document_date"),
            {"create": False, "search_default_group_finance_type": 1},
        )

    def action_open_payroll_documents(self):
        return self._open_action(
            "smart_construction_core.action_sc_salary_registration",
            "工资社保来源",
            [
                ("active", "=", True),
                ("period_year", "=", self.period_year),
                ("period_month", "=", self.period_month),
            ],
            {"create": False, "search_default_group_fact_type": 1},
        )

    def action_open_deduction_refunds(self):
        return self._open_action(
            "smart_construction_core.action_sc_customer_projection_unavailable",
            "扣款退回来源",
            [
                ("active", "=", True),
                ("id", "=", False),
            ]
            + self._date_month_domain("transaction_date"),
            {"create": False, "search_default_group_source_table": 1},
        )

    def action_open_company_expenses(self):
        return self._open_action(
            "smart_construction_core.action_sc_customer_projection_unavailable",
            "公司财务支出",
            [
                ("active", "=", True),
                ("id", "=", False),
            ]
            + self._date_month_domain("transaction_date"),
            {"create": False, "search_default_group_source_table": 1},
        )

    def init(self):
        self._create_empty_projection_view()
