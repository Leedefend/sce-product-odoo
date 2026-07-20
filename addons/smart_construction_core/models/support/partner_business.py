# -*- coding: utf-8 -*-


from odoo import api, fields, models
from odoo.exceptions import UserError


SUPPLIER_TYPE_SELECTION = [
    ("material", "材料供应商"),
    ("labor", "劳务供应商"),
    ("subcontract", "分包单位"),
    ("service", "服务供应商"),
    ("equipment", "设备供应商"),
    ("other", "其他"),
]


class ScSupplierType(models.Model):
    _name = "sc.supplier.type"
    _description = "供应商类型"
    _inherit = ["sc.delete.guard.mixin"]
    _order = "sequence, id"

    name = fields.Char(string="类型名称", required=True, translate=True)
    code = fields.Char(string="类型编码", required=True, index=True)
    sequence = fields.Integer(string="排序", default=10)
    active = fields.Boolean(string="启用", default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "供应商类型编码必须唯一。"),
    ]

    def unlink(self):
        active_types = self.filtered("active")
        if active_types:
            raise UserError("请先停用供应商类型后再删除。")
        self._sc_raise_delete_blockers(action_label="删除供应商类型")
        return super().unlink()


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "sc.delete.guard.mixin"]
    _sc_delete_guard_blocker_models = (
        "construction.contract",
        "payment.request",
        "project.project",
        "sc.contract.event",
        "sc.expense.claim",
        "sc.financing.loan",
        "sc.invoice.registration",
        "sc.material.acceptance",
        "sc.material.inbound",
        "sc.material.outbound",
        "sc.material.price",
        "sc.material.purchase.request",
        "sc.material.rfq",
        "sc.material.rental.order",
        "sc.material.rental.plan",
        "sc.payment.execution",
        "sc.plan",
        "sc.quality.issue",
        "sc.receipt.income",
        "sc.safety.issue",
        "sc.settlement.adjustment",
        "sc.settlement.order",
        "sc.subcontract.plan",
        "sc.subcontract.register",
        "sc.subcontract.request",
        "sc.subcontract.settlement",
        "sc.tax.deduction.registration",
        "tender.bid",
    )

    sc_supplier_type = fields.Selection(
        SUPPLIER_TYPE_SELECTION,
        string="主供应商类型",
        index=True,
    )
    sc_supplier_type_ids = fields.Many2many(
        "sc.supplier.type",
        "sc_res_partner_supplier_type_rel",
        "partner_id",
        "supplier_type_id",
        string="供应商类型",
    )
    sc_supplier_type_label = fields.Char(
        string="供应商类型汇总",
        compute="_compute_sc_supplier_type_label",
        store=True,
        readonly=True,
    )
    sc_account_name = fields.Char(string="账户名称")
    sc_bank_name = fields.Char(string="开户银行")
    sc_bank_account = fields.Char(string="账号")
    sc_region = fields.Char(string="所属地区", index=True)
    sc_registered_capital = fields.Char(string="注册资本")
    sc_establishment_date = fields.Date(string="成立日期")
    sc_business_term = fields.Char(string="营业期限")
    sc_legal_representative = fields.Char(string="法定代表人")
    sc_contact_name = fields.Char(string="联系人")
    sc_business_scope = fields.Text(string="经营范围")
    sc_default_tax_rate = fields.Float(string="默认税率%", digits=(16, 4))
    sc_default_tax_rate_text = fields.Char(string="税率文本")
    sc_supplier_note = fields.Text(string="供应商备注")
    sc_attachment_ids = fields.Many2many(
        "ir.attachment",
        "sc_res_partner_supplier_attachment_rel",
        "partner_id",
        "attachment_id",
        string="供应商附件",
    )

    # Historical identity carrier fields for idempotent migration replay.

    @api.depends("sc_supplier_type_ids.name", "sc_supplier_type_ids.sequence", "sc_supplier_type")
    def _compute_sc_supplier_type_label(self):
        selection_labels = dict(SUPPLIER_TYPE_SELECTION)
        for partner in self:
            types = partner.sc_supplier_type_ids.sorted(lambda item: (item.sequence, item.id))
            if types:
                partner.sc_supplier_type_label = "、".join(types.mapped("name"))
            else:
                partner.sc_supplier_type_label = selection_labels.get(partner.sc_supplier_type or "", "")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("sc_skip_supplier_type_sync"):
            for record, vals in zip(records, vals_list):
                record._sc_sync_supplier_type_fields(vals)
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals and not self.env.context.get("sc_skip_supplier_type_sync"):
            self._sc_sync_supplier_type_fields(vals)
        return result

    @api.model
    def _sc_backfill_supplier_type_ids(self):
        partners = self.sudo().with_context(active_test=False).search([("supplier_rank", ">", 0)])
        if not partners:
            return True

        type_by_code = {
            supplier_type.code: supplier_type
            for supplier_type in self.env["sc.supplier.type"].sudo().search([])
            if supplier_type.code
        }
        fallback_type = type_by_code.get("other")
        for partner in partners:
            supplier_type = type_by_code.get(partner.sc_supplier_type or "") or fallback_type
            if supplier_type and supplier_type not in partner.sc_supplier_type_ids:
                partner.with_context(sc_skip_supplier_type_sync=True).write(
                    {"sc_supplier_type_ids": [(4, supplier_type.id)]}
                )
        return True

    def _sc_sync_supplier_type_fields(self, vals):
        if not vals or self.env.context.get("sc_skip_supplier_type_sync"):
            return
        Type = self.env["sc.supplier.type"].sudo()
        for partner in self:
            if "sc_supplier_type_ids" in vals:
                first_type = partner.sc_supplier_type_ids.sorted(lambda item: (item.sequence, item.id))[:1]
                partner.with_context(sc_skip_supplier_type_sync=True).write(
                    {"sc_supplier_type": first_type.code if first_type else False}
                )
                continue
            if "sc_supplier_type" in vals and partner.sc_supplier_type:
                type_rec = Type.search([("code", "=", partner.sc_supplier_type)], limit=1)
                if type_rec and type_rec not in partner.sc_supplier_type_ids:
                    partner.with_context(sc_skip_supplier_type_sync=True).write(
                        {"sc_supplier_type_ids": [(4, type_rec.id)]}
                    )







    def unlink(self):
        self._sc_raise_delete_blockers(action_label="删除往来单位")
        return super().unlink()




class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    sc_account_holder_name = fields.Char(string="账户名称")
    sc_bank_name = fields.Char(string="开户银行", index=True)


