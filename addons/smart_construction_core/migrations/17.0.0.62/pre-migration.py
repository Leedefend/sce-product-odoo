"""Detach retired history seed identities without deleting their records."""


HANDOFF_MODULE = "external_customer_legacy_handoff"
TRANSFERRED_MODELS = (
    "sc.project.member.staging",
    "sc.legacy.task.evidence",
    "sc.legacy.construction.diary.line",
    "sc.legacy.attendance.checkin",
    "sc.legacy.personnel.movement",
    "sc.legacy.salary.line",
    "sc.legacy.scbs.fact.staging",
    "sc.legacy.scbs.material.map",
)


def migrate(cr, installed_version):
    del installed_version
    cr.execute(
        """
        WITH target_models AS (
            SELECT id FROM ir_model WHERE model IN %s
        ), target_fields AS (
            SELECT id FROM ir_model_fields WHERE model_id IN (SELECT id FROM target_models)
        ), target_xmlids AS (
            SELECT data.id
              FROM ir_model_data data
             WHERE data.module = 'smart_construction_core'
               AND (
                    (data.model = 'ir.model' AND data.res_id IN (SELECT id FROM target_models))
                 OR (data.model = 'ir.model.fields' AND data.res_id IN (SELECT id FROM target_fields))
                 OR (data.model = 'ir.model.fields.selection' AND data.res_id IN (
                        SELECT id FROM ir_model_fields_selection WHERE field_id IN (SELECT id FROM target_fields)
                    ))
                 OR (data.model = 'ir.model.constraint' AND data.res_id IN (
                        SELECT id FROM ir_model_constraint WHERE model IN (SELECT id FROM target_models)
                    ))
                 OR (data.model = 'ir.model.access' AND data.res_id IN (
                        SELECT id FROM ir_model_access WHERE model_id IN (SELECT id FROM target_models)
                    ))
               )
        )
        UPDATE ir_model_data
           SET module = %s,
               noupdate = true
         WHERE id IN (SELECT id FROM target_xmlids)
        """,
        (TRANSFERRED_MODELS, HANDOFF_MODULE),
    )
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = %s,
               noupdate = true
         WHERE module = 'smart_construction_core'
           AND model = 'sc.legacy.report.inventory'
           AND name LIKE 'legacy_report_inventory_%%'
        """,
        (HANDOFF_MODULE,),
    )
