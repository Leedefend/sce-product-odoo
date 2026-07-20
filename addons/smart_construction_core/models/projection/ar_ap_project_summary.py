# -*- coding: utf-8 -*-
import ast

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class ScArApProjectSummary(models.Model):
    _name = "sc.ar.ap.project.summary"
    _inherit = "sc.optional.customer.projection"
    _description = "应收应付报表（项目）"
    _auto = False
    _rec_name = "display_name"
    _order = "project_id, partner_name"
    _sc_readonly_navigation_button_methods = {
        "action_open_income_contracts",
        "action_open_expense_contracts",
        "action_open_receipts",
        "action_open_invoices",
        "action_open_payments",
        "action_open_finance_facts",
    }

    display_name = fields.Char(string="汇总项", readonly=True)
    project_id = fields.Many2one("project.project", string="项目", readonly=True, index=True)
    project_name = fields.Char(string="项目名称", readonly=True)
    partner_id = fields.Many2one("res.partner", string="往来单位记录", readonly=True, index=True)
    partner_key = fields.Char(string="往来单位键", readonly=True, index=True)
    partner_name = fields.Char(string="往来单位", readonly=True, index=True)
    income_contract_amount = fields.Float(string="收入合同金额", readonly=True)
    output_invoice_amount = fields.Float(string="已开票", readonly=True)
    receipt_amount = fields.Float(string="已收款", readonly=True)
    receivable_unpaid_amount = fields.Float(string="未收款", readonly=True)
    invoiced_unreceived_amount = fields.Float(string="已开票未收款", readonly=True)
    received_uninvoiced_amount = fields.Float(string="已收款未开票", readonly=True)
    payable_contract_amount = fields.Float(string="应付合同金额", readonly=True)
    payable_pricing_method_text = fields.Char(string="历史计价方式", readonly=True)
    input_invoice_amount = fields.Float(string="已收供应商发票", readonly=True)
    paid_amount = fields.Float(string="已付款", readonly=True)
    payable_unpaid_amount = fields.Float(string="未付款", readonly=True)
    paid_uninvoiced_amount = fields.Float(string="付款超票", readonly=True)
    output_tax_amount = fields.Float(string="销项税额", readonly=True)
    input_tax_amount = fields.Float(string="进项税额", readonly=True)
    deduction_tax_amount = fields.Float(string="抵扣税额", readonly=True)
    tax_deduction_rate = fields.Float(
        string="抵扣比例",
        readonly=True,
        help="项目级指标：按项目抵扣税额合计 / 项目销项税额合计计算。"
        "同一项目下多往来单位行会重复展示该比例，导出或透视时不应按行求和。",
    )
    output_surcharge_amount = fields.Float(string="销项附加税", readonly=True)
    input_surcharge_amount = fields.Float(string="进项附加税", readonly=True)
    deduction_surcharge_amount = fields.Float(string="抵扣附加税", readonly=True)
    self_funding_income_amount = fields.Float(string="自筹收入金额", readonly=True)
    self_funding_refund_amount = fields.Float(string="自筹退回金额", readonly=True)
    self_funding_unreturned_amount = fields.Float(string="自筹未退金额", readonly=True)
    actual_available_balance = fields.Float(
        string="实际可用余额",
        readonly=True,
        help="项目级指标：来自旧库项目资金余额。"
        "同一项目下多往来单位行会重复展示该余额，导出或透视时不应按行求和。",
    )

    def _raise_readonly_projection(self):
        raise UserError("应收应付报表（项目）是历史事实汇总结果，请从来源业务单据维护数据。")

    @api.model_create_multi
    def create(self, vals_list):
        self._raise_readonly_projection()

    def write(self, vals):
        self._raise_readonly_projection()

    def unlink(self):
        self._raise_readonly_projection()

    def _action_domain(self, action_result):
        raw_domain = action_result.get("domain") or []
        if isinstance(raw_domain, str):
            try:
                parsed = ast.literal_eval(raw_domain)
            except (SyntaxError, ValueError):
                parsed = []
            return list(parsed) if isinstance(parsed, list) else []
        return list(raw_domain) if isinstance(raw_domain, list) else []

    def _action_context(self, action_result):
        raw_context = action_result.get("context") or {}
        if isinstance(raw_context, str):
            try:
                parsed = ast.literal_eval(raw_context)
            except (SyntaxError, ValueError):
                parsed = {}
            context = dict(parsed) if isinstance(parsed, dict) else {}
        else:
            context = dict(raw_context) if isinstance(raw_context, dict) else {}
        if self.project_id:
            context.update(
                {
                    "default_project_id": self.project_id.id,
                    "current_project_id": self.project_id.id,
                }
            )
        if self.partner_id:
            context.update(
                {
                    "default_partner_id": self.partner_id.id,
                    "current_partner_id": self.partner_id.id,
                }
            )
        if self.partner_name:
            context.setdefault("default_partner_name", self.partner_name)
        return context

    def _project_partner_domain(self, model_name):
        self.ensure_one()
        project_domain = []
        if self.project_id:
            project_domain.append(("project_id", "=", self.project_id.id))
        else:
            project_domain.append(("project_id", "=", False))
        identity_domain = []
        if self.partner_id:
            identity_domain.append(("partner_id", "=", self.partner_id.id))
        if self.partner_name and model_name in {
            "sc.invoice.registration",
            "sc.finance.business.fact",
            "sc.treasury.ledger",
        }:
            partner_name_fields = self.env[model_name]._fields
            if "partner_name" in partner_name_fields:
                name_domain = [("partner_name", "=", self.partner_name)]
            elif "legacy_partner_name" in partner_name_fields:
                name_domain = [("legacy_partner_name", "=", self.partner_name)]
            else:
                name_domain = []
            if identity_domain and name_domain:
                identity_domain = expression.OR([identity_domain, name_domain])
            elif name_domain:
                identity_domain = name_domain
        if identity_domain:
            return expression.AND([project_domain, identity_domain])
        return project_domain

    def _open_action(self, action_xmlid, name, extra_domain=None, use_action_domain=True):
        self.ensure_one()
        action = self.env.ref(action_xmlid, raise_if_not_found=False)
        if not action:
            raise UserError("来源入口不存在，请检查业务菜单配置。")
        result = action.sudo().read()[0]
        domain = self._action_domain(result) if use_action_domain else []
        domain.extend(self._project_partner_domain(result.get("res_model")))
        if extra_domain:
            domain.extend(extra_domain)
        result.update(
            {
                "name": "%s / %s" % (self.display_name or "应收应付", name),
                "domain": domain,
                "context": self._action_context(result),
                "target": "current",
            }
        )
        return result

    def action_open_income_contracts(self):
        return self._open_action(
            "smart_construction_core.action_construction_contract_income_execution",
            "收入合同",
            [("type", "=", "out")],
            use_action_domain=False,
        )

    def action_open_expense_contracts(self):
        return self._open_action(
            "smart_construction_core.action_construction_contract_expense_execution",
            "支出合同",
            [("type", "=", "in")],
            use_action_domain=False,
        )

    def action_open_receipts(self):
        return self._open_action(
            "smart_construction_core.action_sc_receipt_income",
            "收款登记",
            [("active", "=", True)],
        )

    def action_open_invoices(self):
        return self._open_action(
            "smart_construction_core.action_sc_invoice_registration",
            "发票登记",
            [("active", "=", True)],
        )

    def action_open_payments(self):
        return self._open_action(
            "smart_construction_core.action_sc_treasury_ledger_payment",
            "付款台账",
            [("direction", "=", "out"), ("state", "=", "posted")],
        )

    def action_open_finance_facts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "%s / 收付款事实" % (self.display_name or "应收应付"),
            "res_model": "sc.finance.business.fact",
            "view_mode": "tree,pivot,form",
            "domain": self._project_partner_domain("sc.finance.business.fact"),
            "context": {
                "search_default_group_business_domain": 1,
            },
            "target": "current",
        }

    def init(self):
        self._create_empty_projection_view()
