from __future__ import annotations

import json
import os

from odoo import api
from odoo.exceptions import UserError


group = env.ref("smart_core.group_smart_core_tenant_payload_importer")
operator_login = str(os.environ.get("SC_TENANT_PAYLOAD_OPERATOR_LOGIN", "") or "").strip()
operator = env["res.users"].with_context(active_test=False).search([("login", "=", operator_login), ("active", "=", True)], limit=1)
if not operator or group not in operator.groups_id:
    raise UserError("TPV1_PERMISSION_PROBE_OPERATOR_INVALID")
if operator.has_group("base.group_system") or operator.has_group("smart_core.group_smart_core_admin"):
    raise UserError("TPV1_PERMISSION_PROBE_OPERATOR_OVERPRIVILEGED")
ordinary = env["res.users"].with_context(active_test=False).search(
    [("id", "not in", [1, operator.id]), ("active", "=", True), ("share", "=", False), ("groups_id", "not in", group.id)],
    limit=1,
)
created_ordinary = False
if not ordinary:
    if os.environ.get("SC_TENANT_PAYLOAD_TEST_MODE") != "1":
        raise UserError("TPV1_PERMISSION_PROBE_ORDINARY_USER_MISSING")
    company = env.ref("base.main_company")
    ordinary = env["res.users"].with_context(no_reset_password=True).create(
        {
            "name": "Synthetic Ordinary Permission Probe",
            "login": "synthetic_ordinary_permission_probe",
            "company_id": company.id,
            "company_ids": [(6, 0, [company.id])],
            "active": True,
            "share": False,
        }
    )
    created_ordinary = True
ordinary_env = api.Environment(env.cr, ordinary.id, {"allowed_company_ids": ordinary.company_ids.ids})
try:
    ordinary_env["sc.tenant.payload.adapter"].assert_import_operator()
except UserError as exc:
    if str(exc) != "TPV1_IMPORT_OPERATOR_REQUIRED":
        raise
else:
    raise UserError("TPV1_PERMISSION_PROBE_ORDINARY_USER_ALLOWED")
operator_id = operator.id
ordinary_id = ordinary.id
if created_ordinary:
    env.cr.rollback()
print(
    json.dumps(
        {
            "schema_version": "tenant_payload_v1",
            "status": "PASS",
            "operator_id": operator_id,
            "ordinary_user_id": ordinary_id,
            "ordinary_user_persisted": False if created_ordinary else True,
            "operator_system_admin": False,
            "ordinary_user_import_denied": True,
        },
        sort_keys=True,
    )
)
