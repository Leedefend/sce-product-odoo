# -*- coding: utf-8 -*-
from odoo import fields, models, tools
from odoo.osv import expression


class ScMaterialStockSummary(models.Model):
    _name = "sc.material.stock.summary"
    _inherit = "sc.optional.customer.projection"
    _description = "库存统计表（新）"
    _auto = False
    _rec_name = "display_name"
    _order = "material_name, project_name, material_spec"
    _sc_readonly_navigation_button_methods = {
        "action_open_stock_in_lines",
        "action_open_stock_out_lines",
        "action_open_all_stock_lines",
    }

    display_name = fields.Char(string="汇总项", readonly=True)
    company_id = fields.Many2one("res.company", string="公司", readonly=True, index=True)
    project_id = fields.Many2one("project.project", string="项目", readonly=True, index=True)
    project_name = fields.Char(string="项目名称", readonly=True, index=True)
    material_code = fields.Char(string="材料编码", readonly=True, index=True)
    material_name = fields.Char(string="材料名称", readonly=True, index=True)
    material_spec = fields.Char(string="规格型号", readonly=True, index=True)
    material_uom = fields.Char(string="单位", readonly=True)
    partner_name = fields.Char(string="往来单位", readonly=True, index=True)
    contract_no = fields.Char(string="合同编号", readonly=True, index=True)
    warehouse_name = fields.Char(string="部门/仓库", readonly=True, index=True)
    currency_id = fields.Many2one("res.currency", string="币种", readonly=True)
    in_qty = fields.Float(string="入库数量", readonly=True)
    in_amount = fields.Monetary(string="入库金额", currency_field="currency_id", readonly=True)
    in_avg_price = fields.Float(string="入库均价", readonly=True)
    out_qty = fields.Float(string="出库数量", readonly=True)
    out_amount = fields.Monetary(string="出库金额", currency_field="currency_id", readonly=True)
    out_avg_price = fields.Float(string="出库均价", readonly=True)
    profit_qty = fields.Float(string="利润数量", readonly=True)
    price_diff = fields.Float(string="价差", readonly=True)
    profit_amount = fields.Monetary(string="利润金额", currency_field="currency_id", readonly=True)
    stock_qty = fields.Float(string="库存数量", readonly=True)
    stock_amount = fields.Monetary(string="库存金额", currency_field="currency_id", readonly=True)
    stock_avg_price = fields.Float(string="库存均价", readonly=True)
    stock_in_line_count = fields.Integer(string="入库明细数", readonly=True)
    stock_out_line_count = fields.Integer(string="出库明细数", readonly=True)
    first_date = fields.Date(string="最早日期", readonly=True)
    last_date = fields.Date(string="最晚日期", readonly=True)
    coverage_note = fields.Char(string="承载说明", readonly=True)

    def _empty_aware_domain(self, field_name, value):
        value = value or False
        if value:
            return [(field_name, "=", value)]
        return expression.OR([[(field_name, "=", False)], [(field_name, "=", "")]])

    def _source_domain(self, fact_types):
        self.ensure_one()
        domain = [
            ("active", "=", True),
            ("state", "!=", "cancel"),
            ("fact_type", "in", fact_types),
        ]
        if self.project_id:
            domain = expression.AND([domain, expression.OR([[("project_id", "=", self.project_id.id)], [("project_id", "=", False)]])])
        else:
            domain.append(("project_id", "=", False))
        for field_name, value in (
            ("material_code", self.material_code),
            ("material_name", self.material_name),
            ("material_spec", self.material_spec),
            ("material_uom", self.material_uom),
        ):
            domain = expression.AND([domain, self._empty_aware_domain(field_name, value)])
        return domain

    def _source_context(self):
        self.ensure_one()
        return {
            "search_default_active_only": 1,
            "search_default_group_fact_type": 1,
            "default_project_id": self.project_id.id if self.project_id else False,
        }

    def _open_source_action(self, name, fact_types):
        self.ensure_one()
        action = self.env.ref("smart_construction_core.action_sc_customer_projection_unavailable", raise_if_not_found=False)
        result = action.sudo().read()[0] if action else {"type": "ir.actions.act_window", "view_mode": "tree,form"}
        result.pop("groups_id", None)
        result.update(
            {
                "name": "%s / %s" % (self.display_name or "材料库存", name),
                "domain": self._source_domain(fact_types),
                "context": self._source_context(),
                "target": "current",
            }
        )
        return result

    def action_open_stock_in_lines(self):
        return self._open_source_action("入库来源", ["stock_in", "stock_in_line", "legacy_source_stock_in"])

    def action_open_stock_out_lines(self):
        return self._open_source_action("出库来源", ["stock_out", "stock_out_line"])

    def action_open_all_stock_lines(self):
        return self._open_source_action("库存来源", ["stock_in", "stock_in_line", "legacy_source_stock_in", "stock_out", "stock_out_line"])

    def init(self):
        self._create_empty_projection_view()
