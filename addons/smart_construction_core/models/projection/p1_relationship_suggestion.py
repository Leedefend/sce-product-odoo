# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools
from odoo.exceptions import UserError


class ScP1RelationshipSuggestion(models.Model):
    _name = "sc.p1.relationship.suggestion"
    _inherit = "sc.optional.customer.projection"
    _description = "P1关系建议"
    _auto = False
    _rec_name = "display_name"
    _order = "source_family, source_model, source_res_id"

    display_name = fields.Char(string="建议说明", readonly=True)
    source_family = fields.Selection(
        [
            ("income_receivable", "收入与收款"),
            ("tax_invoice", "税务与发票"),
        ],
        string="业务域",
        readonly=True,
        index=True,
    )
    source_model = fields.Char(string="来源模型", readonly=True, index=True)
    source_res_id = fields.Integer(string="来源记录ID", readonly=True, index=True)
    source_record_name = fields.Char(string="来源单号", readonly=True, index=True)
    company_id = fields.Many2one("res.company", string="公司", readonly=True, index=True)
    currency_id = fields.Many2one("res.currency", string="币种", readonly=True)
    project_id = fields.Many2one("project.project", string="项目", readonly=True, index=True)
    target_model = fields.Char(string="目标模型", readonly=True, index=True)
    target_field = fields.Char(string="目标字段", readonly=True, index=True)
    partner_id = fields.Many2one("res.partner", string="建议往来单位", readonly=True, index=True)
    candidate_field = fields.Char(string="来源字段", readonly=True, index=True)
    candidate_value = fields.Char(string="来源值", readonly=True, index=True)
    match_basis = fields.Selection(
        [
            ("partner_name", "正式往来单位名称"),
            ("legacy_partner_map", "历史往来单位映射"),
        ],
        string="匹配依据",
        readonly=True,
        index=True,
    )
    confidence_score = fields.Float(string="置信度", readonly=True)
    recommendation = fields.Selection(
        [
            ("auto_candidate", "可自动建议"),
            ("manual_review_candidate", "需人工确认"),
        ],
        string="建议等级",
        readonly=True,
        index=True,
    )
    coverage_note = fields.Char(string="口径说明", readonly=True)

    def _raise_readonly_projection(self):
        raise UserError("P1关系建议是只读派生结果，请在正式办理单据或人工确认流程中维护关系。")

    @api.model_create_multi
    def create(self, vals_list):
        self._raise_readonly_projection()

    def write(self, vals):
        self._raise_readonly_projection()

    def unlink(self):
        self._raise_readonly_projection()

    def init(self):
        self._create_empty_projection_view()
