from __future__ import annotations

import hashlib
import json
import os

from odoo.exceptions import UserError


def _required(name):
    value = str(os.environ.get(name, "") or "").strip()
    if not value:
        raise UserError(f"TPV1_ENV_REQUIRED:{name}")
    return value


login = _required("SC_TENANT_PAYLOAD_OPERATOR_LOGIN")
approved_by = _required("SC_TENANT_PAYLOAD_APPROVED_BY")
allowlist = {item.strip() for item in _required("SC_TENANT_PAYLOAD_DB_ALLOWLIST").split(",") if item.strip()}
if env.cr.dbname not in allowlist:
    raise UserError("TPV1_DATABASE_NOT_ALLOWLISTED")
operator = env["res.users"].with_context(active_test=False).search([("login", "=", login), ("active", "=", True)], limit=1)
if not operator:
    if os.environ.get("SC_TENANT_PAYLOAD_CREATE_OPERATOR") != "1" or os.environ.get("SC_TENANT_PAYLOAD_TEST_MODE") != "1":
        raise UserError("TPV1_IMPORT_OPERATOR_NOT_FOUND")
    company = env.ref("base.main_company")
    operator = env["res.users"].with_context(no_reset_password=True).create(
        {
            "name": "Synthetic Tenant Payload Import Service",
            "login": login,
            "company_id": company.id,
            "company_ids": [(6, 0, [company.id])],
            "active": True,
            "share": False,
        }
    )
group = env.ref("smart_core.group_smart_core_tenant_payload_importer")
if group not in operator.groups_id:
    operator.write({"groups_id": [(4, group.id)]})
env.cr.commit()
print(
    json.dumps(
        {
            "schema_version": "tenant_payload_v1",
            "status": "PASS",
            "database": env.cr.dbname,
            "operator_id": operator.id,
            "created_for_synthetic_test": os.environ.get("SC_TENANT_PAYLOAD_CREATE_OPERATOR") == "1",
            "approval_fingerprint": hashlib.sha256(approved_by.encode("utf-8")).hexdigest()[:12],
        },
        sort_keys=True,
    )
)
