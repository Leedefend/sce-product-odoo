# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProjectBusiness(models.Model):
    _inherit = "project.project"

    partner_id = fields.Many2one("res.partner", string="关联单位")
    sc_partner_display_name = fields.Char(string="关联单位显示名称", compute="_compute_sc_partner_display_name")
    short_name = fields.Char(string="项目简称")
    project_environment = fields.Char(string="项目环境")
    specialty_type_name = fields.Char(string="专业类型")
    business_nature = fields.Char(string="经营性质")
    detail_address = fields.Text(string="项目详细地址")
    project_profile = fields.Text(string="项目简介")
    project_area = fields.Char(string="项目面积")
    project_overview = fields.Text(string="项目概况")

    @api.depends("partner_id", "partner_id.display_name")
    def _compute_sc_partner_display_name(self):
        for project in self:
            project.sc_partner_display_name = project.partner_id.display_name or ""
