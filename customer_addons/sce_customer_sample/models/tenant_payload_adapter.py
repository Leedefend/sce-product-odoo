from odoo import api, models


class SampleTenantPayloadAdapter(models.AbstractModel):
    _inherit = "sc.tenant.payload.adapter"

    @api.model
    def get_adapter(self, tenant_key):
        if tenant_key != "sample":
            return super().get_adapter(tenant_key)
        self.assert_import_operator()
        return {
            "tenant_key": "sample",
            "database_tenant_key": "sample",
            "customer_module": "sce_customer_sample",
            "customer_module_version": "17.0.1.3.0",
            "payload_schema_version": "tenant_payload_v1",
            "product_interface_version": "1",
            "supported_source_versions": ["synthetic-v1"],
            "model_import_order": ["companies", "partners", "projects", "attachments"],
            "external_key_mapping": "sc.tenant.payload.external.identity",
            "resources": {
                "companies": {
                    "model": "res.company",
                    "value_fields": {"display_name": "name"},
                    "relationship_fields": {},
                    "bootstrap_xmlids": {"main": "base.main_company"},
                    "company_identity": True,
                },
                "partners": {
                    "model": "res.partner",
                    "value_fields": {
                        "display_name": "name",
                        "entity_type": "company_type",
                    },
                    "value_mappings": {
                        "entity_type": {"organization": "company", "person": "person"},
                    },
                    "relationship_fields": {
                        "company": {"field": "company_id", "resource": "companies", "many": False},
                    },
                    "company_relationship": "company",
                },
                "projects": {
                    "model": "project.project",
                    "value_fields": {"display_name": "name", "active": "active"},
                    "relationship_fields": {
                        "company": {"field": "company_id", "resource": "companies", "many": False},
                        "owner": {"field": "owner_id", "resource": "partners", "many": False},
                    },
                    "company_relationship": "company",
                },
                "attachments": {
                    "model": "ir.attachment",
                    "kind": "attachment",
                    "value_fields": {
                        "filename": "name",
                        "mimetype": "mimetype",
                        "resource_model": "res_model",
                    },
                    "relationship_fields": {
                        "company": {"field": "company_id", "resource": "companies", "many": False},
                        "target": {
                            "field": "res_id",
                            "resource": "*",
                            "many": False,
                            "polymorphic": True,
                            "model_field": "res_model",
                        },
                    },
                    "company_relationship": "company",
                },
            },
        }
