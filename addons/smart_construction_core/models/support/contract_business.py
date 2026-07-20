# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ConstructionContractBusiness(models.Model):
    _inherit = "construction.contract"

    amount_untaxed = fields.Monetary(string="平台合同金额")
    visible_contract_amount = fields.Monetary(
        string="合同金额",
        currency_field="currency_id",
        compute="_compute_visible_contract_amount",
        store=True,
        help="标准产品合同金额口径。",
    )
    document_status = fields.Char(string="单据状态", compute="_compute_document_status")
    engineering_category_text = fields.Char(string="工程类别")
    affiliated_person = fields.Char(string="挂靠人")
    engineering_content = fields.Text(string="合同内容")
    contract_duration_text = fields.Text(string="合同工期")
    contract_payment_method_text = fields.Text(string="合同约定付款方式")
    entry_user_text = fields.Char(string="录入人")
    entry_time = fields.Datetime(string="录入时间")
    approval_info = fields.Text(string="审批信息")
    attachment_text = fields.Text(string="附件")
    visible_invoice_amount = fields.Monetary(string="累计开票", currency_field="currency_id")
    visible_received_amount = fields.Monetary(string="累计收款", currency_field="currency_id")
    visible_invoice_unreceived_amount = fields.Monetary(
        string="开票未收款",
        currency_field="currency_id",
        compute="_compute_visible_invoice_unreceived_amount",
        store=True,
    )
    visible_unreceived_amount = fields.Monetary(
        string="未收款",
        currency_field="currency_id",
        compute="_compute_visible_unreceived_amounts",
        store=True,
    )
    visible_unreceived_rate = fields.Char(
        string="未收款比例",
        compute="_compute_visible_unreceived_amounts",
        store=True,
    )
    expense_execution_status_display = fields.Char(
        string="单据状态", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_document_no = fields.Char(
        string="单据编号", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_project_name = fields.Char(
        string="项目名称", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_contract_date = fields.Char(
        string="签订日期", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_title = fields.Char(
        string="标题", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_counterparty = fields.Char(
        string="往来单位", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_engineering_content = fields.Text(
        string="合同内容", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_category = fields.Char(
        string="合同类别", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_amount_display = fields.Char(
        string="合同金额", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_invoice_amount = fields.Char(
        string="已开票金额", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_paid_amount = fields.Char(
        string="已付款金额", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_unpaid_amount = fields.Char(
        string="未付款金额", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_uninvoiced_amount = fields.Char(
        string="未开票金额", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_contract_no = fields.Char(
        string="合同编号", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_attachment_text = fields.Text(
        string="附件", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_source_created_by = fields.Char(
        string="录入人", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    expense_execution_source_created_at = fields.Char(
        string="录入时间", compute="_compute_expense_execution_formal_visible_fields", store=True, readonly=True
    )
    contract_unreceived_amount = fields.Monetary(
        string="平台未收款",
        currency_field="currency_id",
        compute="_compute_contract_receivable_amounts",
        compute_sudo=True,
    )
    contract_unreceived_rate = fields.Char(
        string="平台未收款比例",
        compute="_compute_contract_receivable_amounts",
        compute_sudo=True,
    )


    @api.depends("amount_untaxed")
    def _compute_visible_contract_amount(self):
        for rec in self:
            rec.visible_contract_amount = rec.amount_untaxed or 0.0

    @api.depends("visible_invoice_amount", "visible_received_amount")
    def _compute_visible_invoice_unreceived_amount(self):
        for rec in self:
            rec.visible_invoice_unreceived_amount = max(
                (rec.visible_invoice_amount or 0.0) - (rec.visible_received_amount or 0.0), 0.0
            )

    @api.depends(
        "visible_contract_amount",
        "visible_received_amount",
    )
    def _compute_visible_unreceived_amounts(self):
        for rec in self:
            unreceived = max((rec.visible_contract_amount or 0.0) - (rec.visible_received_amount or 0.0), 0.0)
            rec.visible_unreceived_amount = unreceived
            total = rec.visible_contract_amount or 0.0
            rec.visible_unreceived_rate = f"{unreceived / total * 100:.2f}%" if total else ""

    @staticmethod
    def _formal_amount_text(value):
        if value in (False, None, ""):
            return ""
        amount = float(value)
        return str(int(amount)) if amount.is_integer() else str(amount)

    @staticmethod
    def _formal_date_text(value):
        return fields.Date.to_string(value) if value else ""

    @api.depends(
        "document_status",
        "project_id.display_name",
        "date_contract",
        "subject",
        "partner_id.display_name",
        "engineering_content",
        "expense_contract_category_id.name",
        "expense_contract_category_auto_id.name",
        "visible_contract_amount",
        "visible_invoice_amount",
        "visible_received_amount",
        "visible_unreceived_amount",
        "visible_invoice_unreceived_amount",
        "attachment_text",
        "entry_user_text",
        "entry_time",
        "source_created_by",
        "source_created_at",
    )
    def _compute_expense_execution_formal_visible_fields(self):
        for rec in self:
            rec.expense_execution_status_display = rec.document_status or ""
            rec.expense_execution_document_no = rec.name or ""
            rec.expense_execution_project_name = rec.project_id.display_name if rec.project_id else ""
            rec.expense_execution_contract_date = rec._formal_date_text(rec.date_contract)
            rec.expense_execution_title = rec.subject or ""
            rec.expense_execution_counterparty = rec.partner_id.display_name if rec.partner_id else ""
            rec.expense_execution_engineering_content = rec.engineering_content or ""
            rec.expense_execution_category = (
                (rec.expense_contract_category_id.display_name if rec.expense_contract_category_id else "")
                or (rec.expense_contract_category_auto_id.display_name if rec.expense_contract_category_auto_id else "")
                or ""
            )
            rec.expense_execution_amount_display = rec._formal_amount_text(rec.visible_contract_amount)
            rec.expense_execution_invoice_amount = rec._formal_amount_text(rec.visible_invoice_amount)
            rec.expense_execution_paid_amount = rec._formal_amount_text(rec.visible_received_amount)
            rec.expense_execution_unpaid_amount = rec._formal_amount_text(rec.visible_unreceived_amount)
            rec.expense_execution_uninvoiced_amount = rec._formal_amount_text(rec.visible_invoice_unreceived_amount)
            rec.expense_execution_contract_no = rec.name or ""
            rec.expense_execution_attachment_text = rec.attachment_text or ""
            rec.expense_execution_source_created_by = rec.entry_user_text or rec.source_created_by or ""
            source_created_at = rec.entry_time or rec.source_created_at
            rec.expense_execution_source_created_at = (
                fields.Datetime.to_string(source_created_at) if source_created_at else ""
            )


    @api.depends("state")
    def _compute_document_status(self):
        state_map = {
            "draft": "未提交",
            "confirmed": "审核通过",
            "running": "审核通过",
            "closed": "审核通过",
            "cancel": "已作废",
        }
        for rec in self:
            rec.document_status = state_map.get(rec.state) or rec.state or ""

    @api.depends("visible_contract_amount", "received_amount")
    def _compute_contract_receivable_amounts(self):
        for rec in self:
            total = rec.visible_contract_amount or 0.0
            unreceived = total - (rec.received_amount or 0.0)
            rec.contract_unreceived_amount = unreceived
            if not total:
                rec.contract_unreceived_rate = ""
                continue
            rec.contract_unreceived_rate = f"{unreceived / total * 100:.2f}%"
