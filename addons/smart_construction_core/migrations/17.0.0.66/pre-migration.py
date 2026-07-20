"""Transfer the customer historical financing carrier in place."""


HANDOFF_MODULE = "external_customer_legacy_handoff"
TRANSFERRED_MODELS = ("sc.legacy.financing.loan.fact",)


def migrate(cr, installed_version):
    del installed_version
    cr.execute(
        """
        WITH target_models AS (
            SELECT id FROM ir_model WHERE model IN %s
        ), target_fields AS (
            SELECT id FROM ir_model_fields WHERE model_id IN (SELECT id FROM target_models)
        ), target_actions AS (
            SELECT id FROM ir_act_window WHERE res_model IN %s
        ), target_xmlids AS (
            SELECT data.id FROM ir_model_data data
             WHERE data.module = 'smart_construction_core' AND (
                    (data.model = 'ir.model' AND data.res_id IN (SELECT id FROM target_models))
                 OR (data.model = 'ir.model.fields' AND data.res_id IN (SELECT id FROM target_fields))
                 OR (data.model = 'ir.model.fields.selection' AND data.res_id IN (
                        SELECT id FROM ir_model_fields_selection WHERE field_id IN (SELECT id FROM target_fields)))
                 OR (data.model = 'ir.model.constraint' AND data.res_id IN (
                        SELECT id FROM ir_model_constraint WHERE model IN (SELECT id FROM target_models)))
                 OR (data.model = 'ir.model.access' AND data.res_id IN (
                        SELECT id FROM ir_model_access WHERE model_id IN (SELECT id FROM target_models)))
                 OR (data.model = 'ir.ui.view' AND data.res_id IN (
                        SELECT id FROM ir_ui_view WHERE model IN %s))
                 OR (data.model = 'ir.actions.act_window' AND data.res_id IN (SELECT id FROM target_actions))
                 OR (data.model = 'ir.ui.menu' AND data.res_id IN (
                        SELECT id FROM ir_ui_menu WHERE action IN (
                            SELECT 'ir.actions.act_window,' || id::text FROM target_actions)))
             )
        )
        UPDATE ir_model_data SET module = %s, noupdate = true
         WHERE id IN (SELECT id FROM target_xmlids)
        """,
        (TRANSFERRED_MODELS, TRANSFERRED_MODELS, TRANSFERRED_MODELS, HANDOFF_MODULE),
    )
