#!/usr/bin/env python3
"""Host-side read-only SQL and filestore fingerprint for pre/post upgrade."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


TABLES = {
    "companies": "res_company",
    "users": "res_users",
    "partners": "res_partner",
    "projects": "project_project",
    "contracts": "construction_contract",
    "settlements": "sc_settlement_order",
    "payment_requests": "payment_request",
    "payment_executions": "sc_payment_execution",
    "ledgers": "payment_ledger",
    "attachments": "ir_attachment",
    "config_contracts": "ui_business_config_contract",
    "config_versions": "ui_business_config_contract_version",
    "low_code_change_sets": "ui_business_config_change_set",
}
AMOUNTS = {
    "construction_contract": ("amount_total", "amount", "contract_amount"),
    "sc_settlement_order": ("amount_total", "settlement_amount", "amount"),
    "payment_request": ("amount", "amount_total"),
    "sc_payment_execution": ("amount", "actual_amount", "paid_amount"),
    "payment_ledger": ("amount", "amount_total"),
}
RELATIONS = {
    "construction_contract": ("project_id",),
    "sc_settlement_order": ("contract_id", "project_id"),
    "payment_request": ("settlement_id", "contract_id", "project_id", "partner_id"),
    "sc_payment_execution": ("payment_request_id",),
    "payment_ledger": ("payment_request_id",),
}

project = os.environ["FINGERPRINT_PROJECT"]
compose_files = [
    value
    for value in os.environ.get(
        "FINGERPRINT_COMPOSE_FILES", os.environ.get("FINGERPRINT_COMPOSE_FILE", "")
    ).split(os.pathsep)
    if value
]
if not compose_files:
    raise SystemExit("FINGERPRINT_COMPOSE_FILES_REQUIRED")
database = os.environ["FINGERPRINT_DB"]
db_user = os.environ["DB_USER"]
filestore_mode = os.environ.get("FINGERPRINT_FILESTORE_MODE", "exec")
out_path = Path(os.environ["FINGERPRINT_OUTPUT"])
compose = ["docker", "compose", "-p", project]
for compose_file in compose_files:
    compose.extend(("-f", compose_file))


def run(args: list[str]) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()


def sql(statement: str) -> str:
    return run([*compose, "exec", "-T", "db", "psql", "-U", db_user, "-d", database, "-Atc", statement])


def table_exists(table: str) -> bool:
    return sql(f"SELECT to_regclass('public.{table}') IS NOT NULL").lower() == "t"


def column_exists(table: str, column: str) -> bool:
    return sql(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        f"WHERE table_schema='public' AND table_name='{table}' AND column_name='{column}')"
    ).lower() == "t"


counts = {}
id_digests = {}
for label, table in TABLES.items():
    if not table_exists(table):
        counts[label] = None
        id_digests[label] = None
        continue
    counts[label] = int(sql(f"SELECT count(*) FROM {table}"))
    id_digests[label] = sql(f"SELECT md5(COALESCE(string_agg(id::text, ',' ORDER BY id), '')) FROM {table}")

amounts = {}
for table, candidates in AMOUNTS.items():
    if not table_exists(table):
        amounts[table] = None
        continue
    field = next((name for name in candidates if column_exists(table, name)), None)
    value = sql(f"SELECT COALESCE(round(sum({field})::numeric, 2), 0) FROM {table}") if field else "0"
    row_digest = (
        sql(
            "SELECT md5(COALESCE(string_agg(id::text || ':' || "
            f"COALESCE(round({field}::numeric, 2)::text, ''), ',' ORDER BY id), '')) FROM {table}"
        )
        if field
        else None
    )
    amounts[table] = {"field": field, "sum": value, "row_digest": row_digest}

missing_relations = {}
relation_bindings = {}
warnings = []
for table, fields in RELATIONS.items():
    if not table_exists(table):
        missing_relations[table] = None
        continue
    missing_relations[table] = {}
    relation_bindings[table] = {}
    for field in fields:
        if not column_exists(table, field):
            continue
        missing = int(sql(f"SELECT count(*) FROM {table} WHERE {field} IS NULL"))
        missing_relations[table][field] = missing
        relation_bindings[table][field] = {
            "non_null_count": int(sql(f"SELECT count(*) FROM {table} WHERE {field} IS NOT NULL")),
            "binding_digest": sql(
                "SELECT md5(COALESCE(string_agg(id::text || ':' || "
                f"COALESCE({field}::text, ''), ',' ORDER BY id), '')) FROM {table}"
            ),
        }
        if missing:
            warnings.append({"code": "missing_relation", "reference": f"{table}.{field}", "count": missing})

for table in AMOUNTS:
    if not table_exists(table):
        continue
    currency_field = next((field for field in ("currency_id", "company_currency_id") if column_exists(table, field)), None)
    if currency_field:
        missing = int(sql(f"SELECT count(*) FROM {table} WHERE {currency_field} IS NULL"))
        if missing:
            warnings.append({"code": "missing_currency", "reference": f"{table}.{currency_field}", "count": missing})

modules = []
if table_exists("ir_module_module"):
    version_column = "installed_version" if column_exists("ir_module_module", "installed_version") else "latest_version"
    raw = sql(
        "SELECT COALESCE(json_agg(row_to_json(x))::text, '[]') FROM "
        f"(SELECT name,state,COALESCE({version_column},'') AS installed_version "
        "FROM ir_module_module WHERE name LIKE 'smart_%' ORDER BY name) x"
    )
    modules = json.loads(raw)

attachment_index = None
if table_exists("ir_attachment"):
    index_fields = [
        field
        for field in ("res_model", "res_id", "company_id", "store_fname", "checksum", "file_size")
        if column_exists("ir_attachment", field)
    ]
    expressions = ["id::text", *(f"COALESCE({field}::text, '')" for field in index_fields)]
    attachment_index = {
        "fields": index_fields,
        "row_count": int(sql("SELECT count(*) FROM ir_attachment")),
        "binding_digest": sql(
            "SELECT md5(COALESCE(string_agg(concat_ws(':', "
            + ", ".join(expressions)
            + "), ',' ORDER BY id), '')) FROM ir_attachment"
        ),
    }

carrier_inventory = os.environ.get("FINGERPRINT_CARRIER_INVENTORY", "").strip()
legacy_carriers = None
if carrier_inventory:
    inventory_path = Path(carrier_inventory)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    models = [item["model"] for item in inventory.get("models", [])]
    if len(models) != 67 or len(set(models)) != 67:
        raise SystemExit("FINGERPRINT_CARRIER_INVENTORY_INVALID")
    legacy_carriers = {}
    for model in sorted(models):
        table = model.replace(".", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]+", table):
            raise SystemExit("FINGERPRINT_CARRIER_TABLE_INVALID")
        if not table_exists(table):
            raise SystemExit(f"FINGERPRINT_CARRIER_TABLE_ABSENT:{table}")
        columns_raw = sql(
            "SELECT COALESCE(json_agg(column_name ORDER BY ordinal_position)::text, '[]') "
            "FROM information_schema.columns WHERE table_schema='public' "
            f"AND table_name='{table}'"
        )
        legacy_carriers[model] = {
            "table": table,
            "record_count": int(sql(f"SELECT count(*) FROM {table}")),
            "id_digest": sql(
                f"SELECT md5(COALESCE(string_agg(id::text, ',' ORDER BY id), '')) FROM {table}"
            ),
            "columns": json.loads(columns_raw),
        }

filestore_command = (
    f"root='/var/lib/odoo/filestore/{database}'; "
    "count=$(find \"$root\" -type f 2>/dev/null | wc -l); "
    "bytes=$(find \"$root\" -type f -printf '%s\\n' 2>/dev/null | awk '{s+=$1} END {print s+0}'); "
    "digest=$(find \"$root\" -type f -printf '%P\\n' 2>/dev/null | sort | while read p; do "
    "printf '%s\\0' \"$p\"; sha256sum \"$root/$p\" | awk '{print $1}'; done | sha256sum | awk '{print $1}'); "
    "printf '%s|%s|%s\\n' \"$count\" \"$bytes\" \"$digest\""
)
if filestore_mode == "exec":
    filestore_raw = run([*compose, "exec", "-T", "odoo", "sh", "-c", filestore_command])
else:
    filestore_raw = run([*compose, "run", "--rm", "--no-deps", "-T", "--entrypoint", "sh", "odoo", "-c", filestore_command])
file_count, file_bytes, file_digest = filestore_raw.split("|")[-3:]

payload = {
    "schema_version": 1,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "database": database,
    "mode": "sql_and_filestore_read_only_redacted",
    "database_bytes": int(sql(f"SELECT pg_database_size('{database}')")),
    "counts": counts,
    "id_digests": id_digests,
    "amounts": amounts,
    "missing_relations": missing_relations,
    "relation_bindings": relation_bindings,
    "attachment_index": attachment_index,
    "legacy_carriers": legacy_carriers,
    "known_historical_warnings": warnings,
    "known_historical_warning_count": len(warnings),
    "filestore": {"file_count": int(file_count), "bytes": int(file_bytes), "sha256": file_digest},
    "modules": modules,
    "pending_modules": [row["name"] for row in modules if row["state"] in {"to install", "to upgrade", "to remove"}],
    "demo_module_state": next((row["state"] for row in modules if row["name"] == "smart_construction_demo"), "uninstalled"),
    "sensitive_values_included": False,
    "database_write_count": 0,
}
canonical = dict(payload)
canonical.pop("generated_at")
canonical.pop("database")
canonical.pop("modules")
canonical.pop("pending_modules")
canonical.pop("database_bytes")
payload["business_fingerprint_sha256"] = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
print(f"[candidate.sql_fingerprint] PASS db={database} fingerprint={payload['business_fingerprint_sha256']} warnings={len(warnings)}")
