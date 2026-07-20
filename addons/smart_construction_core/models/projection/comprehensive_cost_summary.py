# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class ScComprehensiveCostSummary(models.Model):
    _name = "sc.comprehensive.cost.summary"
    _inherit = "sc.optional.customer.projection"
    _description = "成本统计表（综合）"
    _auto = False
    _rec_name = "display_name"
    _order = "project_id"
    _sc_readonly_navigation_button_methods = {
        "action_open_income_contracts",
        "action_open_receipts",
        "action_open_output_invoices",
        "action_open_payable_contracts",
        "action_open_supplier_contracts",
        "action_open_material_costs",
        "action_open_labor_costs",
        "action_open_lease_costs",
        "action_open_expenses",
        "action_open_salary",
        "action_open_input_invoices",
        "action_open_payments",
    }

    display_name = fields.Char(string="汇总项", readonly=True)
    company_id = fields.Many2one("res.company", string="公司", readonly=True, index=True)
    project_id = fields.Many2one("project.project", string="项目", readonly=True, index=True)
    project_name = fields.Char(string="项目名称", readonly=True, index=True)
    currency_id = fields.Many2one("res.currency", string="币种", readonly=True)

    income_contract_amount = fields.Monetary(string="收入合同金额", currency_field="currency_id", readonly=True)
    receipt_amount = fields.Monetary(string="已收款", currency_field="currency_id", readonly=True)
    output_invoice_amount = fields.Monetary(string="已开票", currency_field="currency_id", readonly=True)
    receivable_unpaid_amount = fields.Monetary(string="未收款", currency_field="currency_id", readonly=True)

    payable_contract_amount = fields.Monetary(string="应付合同金额", currency_field="currency_id", readonly=True)
    supplier_contract_amount = fields.Monetary(string="供应商合同金额", currency_field="currency_id", readonly=True)
    material_cost_amount = fields.Monetary(string="材料成本", currency_field="currency_id", readonly=True)
    labor_cost_amount = fields.Monetary(string="劳务/分包成本", currency_field="currency_id", readonly=True)
    lease_cost_amount = fields.Monetary(string="租赁/机械成本", currency_field="currency_id", readonly=True)
    expense_cost_amount = fields.Monetary(string="费用成本", currency_field="currency_id", readonly=True)
    salary_cost_amount = fields.Monetary(string="工资成本", currency_field="currency_id", readonly=True)
    input_invoice_amount = fields.Monetary(string="成本发票金额", currency_field="currency_id", readonly=True)
    paid_amount = fields.Monetary(string="已付款", currency_field="currency_id", readonly=True)
    payable_unpaid_amount = fields.Monetary(string="未付款", currency_field="currency_id", readonly=True)

    total_cost_amount = fields.Monetary(string="成本合计（已承载）", currency_field="currency_id", readonly=True)
    profit_amount = fields.Monetary(string="利润额（已承载）", currency_field="currency_id", readonly=True)
    profit_rate = fields.Float(string="利润率(%)", readonly=True)

    source_line_count = fields.Integer(string="来源明细数", readonly=True)
    material_line_count = fields.Integer(string="材料明细数", readonly=True)
    expense_line_count = fields.Integer(string="费用单数", readonly=True)
    salary_line_count = fields.Integer(string="工资单数", readonly=True)
    coverage_note = fields.Char(string="承载说明", readonly=True)

    def _raise_readonly_projection(self):
        raise UserError("成本统计表（综合）是历史事实汇总结果，请从来源业务单据维护数据。")

    @api.model_create_multi
    def create(self, vals_list):
        self._raise_readonly_projection()

    def write(self, vals):
        self._raise_readonly_projection()

    def unlink(self):
        self._raise_readonly_projection()

    def _project_domain(self):
        self.ensure_one()
        if self.project_id:
            return [("project_id", "=", self.project_id.id)]
        return [("project_id", "=", False)]

    def _project_context(self):
        self.ensure_one()
        return {
            "default_project_id": self.project_id.id if self.project_id else False,
            "current_project_id": self.project_id.id if self.project_id else False,
            "search_default_group_project": 1,
        }

    def _open_action(self, action_xmlid, name, domain, context=None):
        self.ensure_one()
        action = self.env.ref(action_xmlid, raise_if_not_found=False)
        result = action.sudo().read()[0] if action else {"type": "ir.actions.act_window", "view_mode": "tree,form"}
        result.update(
            {
                "name": "%s / %s" % (self.project_name or "项目", name),
                "domain": domain,
                "context": context or self._project_context(),
                "target": "current",
            }
        )
        return result

    def action_open_income_contracts(self):
        return self._open_action(
            "smart_construction_core.action_construction_contract_income",
            "收入合同",
            self._project_domain() + [("type", "=", "out"), ("archived", "=", False), ("state", "!=", "cancel")],
        )

    def action_open_receipts(self):
        return self._open_action(
            "smart_construction_core.action_sc_receipt_income",
            "收款登记",
            self._project_domain() + [("active", "=", True), ("state", "!=", "cancel")],
        )

    def action_open_output_invoices(self):
        return self._open_action(
            "smart_construction_core.action_sc_invoice_registration",
            "销项发票",
            self._project_domain() + [("active", "=", True), ("state", "!=", "cancel"), ("direction", "=", "output")],
            dict(self._project_context(), default_direction="output"),
        )

    def action_open_payable_contracts(self):
        return self._open_action(
            "smart_construction_core.action_construction_contract_expense",
            "应付合同",
            self._project_domain() + [("type", "=", "in"), ("archived", "=", False), ("state", "!=", "cancel")],
        )

    def action_open_supplier_contracts(self):
        return self._open_action(
            "smart_construction_core.action_sc_customer_projection_unavailable",
            "供应商合同",
            self._project_domain() + [("active", "=", True), ("deleted_flag", "in", ["0", False, ""])],
        )

    def action_open_material_costs(self):
        return self._open_action(
            "smart_construction_core.action_sc_customer_projection_unavailable",
            "材料成本",
            self._project_domain()
            + [
                ("active", "=", True),
                ("state", "!=", "cancel"),
                ("fact_type", "in", ["stock_in", "stock_in_line", "legacy_source_stock_in", "material_lease_settlement"]),
            ],
        )

    def action_open_labor_costs(self):
        return self._open_action(
            "smart_construction_core.action_sc_customer_projection_unavailable",
            "劳务/分包成本",
            self._project_domain()
            + [
                ("active", "=", True),
                ("state", "!=", "cancel"),
                ("fact_type", "in", ["labor_settlement", "subcontract_settlement", "labor_contract", "subcontract_contract"]),
            ],
        )

    def action_open_lease_costs(self):
        return self._open_action(
            "smart_construction_core.action_sc_customer_projection_unavailable",
            "租赁/机械成本",
            self._project_domain()
            + [
                ("active", "=", True),
                ("state", "!=", "cancel"),
                ("fact_type", "in", ["lease_settlement", "lease_summary", "equipment_shift", "lease_contract_line", "lease_contract"]),
            ],
        )

    def action_open_expenses(self):
        return self._open_action(
            "smart_construction_core.action_sc_expense_claim",
            "费用报销",
            self._project_domain() + [("active", "=", True), ("state", "!=", "cancel"), ("claim_type", "=", "expense")],
            dict(self._project_context(), default_claim_type="expense"),
        )

    def action_open_salary(self):
        return self._open_action(
            "smart_construction_core.action_sc_salary_registration",
            "工资登记",
            self._project_domain() + [("state", "!=", "cancel"), ("fact_type", "=", "salary_registration")],
            dict(self._project_context(), default_fact_type="salary_registration"),
        )

    def action_open_input_invoices(self):
        return self._open_action(
            "smart_construction_core.action_sc_invoice_registration",
            "进项发票",
            self._project_domain() + [("active", "=", True), ("state", "!=", "cancel"), ("direction", "=", "input")],
            dict(self._project_context(), default_direction="input"),
        )

    def action_open_payments(self):
        return self._open_action(
            "smart_construction_core.action_sc_payment_execution",
            "付款执行",
            self._project_domain() + [("active", "=", True), ("state", "!=", "cancel")],
        )

    def init(self):
        self._create_empty_projection_view()
