#!/usr/bin/env python3
"""Collect model counts from an isolated candidate DB without reading values."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path


SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--db-user", required=True)
    parser.add_argument("--customer-module")
    parser.add_argument("--customer-legacy-module")
    args = parser.parse_args()

    with args.inventory.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    model_tables = {
        row["model"]: row["table"]
        for row in rows
        if row["model"]
        and (
            row["model"].startswith("sc.legacy.")
            or row["model"] in {"sc.history.todo", "sc.project.member.staging"}
        )
        and row["table"]
    }
    if not model_tables or any(not SAFE_IDENTIFIER.fullmatch(table) for table in model_tables.values()):
        raise SystemExit("TENANT_BOUNDARY_HISTORY_TABLE_SET_INVALID")
    compose = [
        "docker", "compose", "-p", args.project,
        "-f", "docker-compose.production-candidate.yml",
        "exec", "-T", "db", "psql", "-U", args.db_user,
        "-d", args.database, "-At", "-F", "|", "-v", "ON_ERROR_STOP=1",
    ]
    table_output = subprocess.check_output(
        compose + ["-c", "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')"],
        text=True,
    )
    existing_tables = set(table_output.splitlines())
    selects = [
        "SELECT %s, count(*)::bigint FROM %s" % (
            "'" + model.replace("'", "''") + "'",
            '"%s"' % table,
        )
        for model, table in sorted(model_tables.items())
        if table in existing_tables
    ]
    sql = " UNION ALL ".join(selects) + " ORDER BY 1"
    output = subprocess.check_output(compose + ["-c", sql], text=True) if selects else ""
    counts: dict[str, int | str] = {
        model: "TABLE_ABSENT"
        for model, table in model_tables.items()
        if table not in existing_tables
    }
    counts.update({line.split("|", 1)[0]: int(line.split("|", 1)[1]) for line in output.splitlines() if line})
    module_names = ["smart_construction_core"] + [
        name for name in (args.customer_module, args.customer_legacy_module) if name
    ]
    quoted_modules = ",".join("'" + name.replace("'", "''") + "'" for name in module_names)
    module_sql = (
        "SELECT name || '|' || state FROM ir_module_module "
        f"WHERE name IN ({quoted_modules}) ORDER BY name"
    )
    module_output = subprocess.check_output(compose + ["-c", module_sql], text=True)
    modules = dict(line.split("|", 1) for line in module_output.splitlines() if line)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "schema_version": "tenant_boundary_06_history_counts.v1",
                "database_class": "isolated_frozen_history_copy",
                "models": counts,
                "module_states": modules,
                "values_read": False,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    record_total = sum(value for value in counts.values() if isinstance(value, int))
    absent = sum(value == "TABLE_ABSENT" for value in counts.values())
    print(f"[tenant_boundary_06_history_counts] PASS models={len(counts)} records={record_total} tables_absent={absent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
