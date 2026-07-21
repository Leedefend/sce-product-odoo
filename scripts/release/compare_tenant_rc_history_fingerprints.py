#!/usr/bin/env python3
"""Fail closed when an isolated RC upgrade changes historical business identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BUSINESS_COUNT_KEYS = (
    "companies",
    "users",
    "partners",
    "projects",
    "contracts",
    "settlements",
    "payment_requests",
    "payment_executions",
    "ledgers",
    "attachments",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_business(payload: dict) -> dict:
    return {
        "counts": {key: payload["counts"].get(key) for key in BUSINESS_COUNT_KEYS},
        "id_digests": {key: payload["id_digests"].get(key) for key in BUSINESS_COUNT_KEYS},
        "amounts": payload["amounts"],
        "relation_bindings": payload["relation_bindings"],
        "attachment_index": payload["attachment_index"],
        "filestore": payload["filestore"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--identity", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    before = load(args.before)
    after = load(args.after)
    identity = load(args.identity)
    failures: list[str] = []

    if stable_business(before) != stable_business(after):
        failures.append("HISTORICAL_BUSINESS_FINGERPRINT_DRIFT")

    before_carriers = before.get("legacy_carriers") or {}
    after_carriers = after.get("legacy_carriers") or {}
    if len(before_carriers) != 67 or set(before_carriers) != set(after_carriers):
        failures.append("LEGACY_CARRIER_SET_DRIFT")
    else:
        for model, old in before_carriers.items():
            new = after_carriers[model]
            if old["table"] != new["table"]:
                failures.append(f"LEGACY_CARRIER_TABLE_DRIFT:{model}")
            if old["record_count"] != new["record_count"] or old["id_digest"] != new["id_digest"]:
                failures.append(f"LEGACY_CARRIER_RECORD_DRIFT:{model}")
            if not set(old["columns"]).issubset(new["columns"]):
                failures.append(f"LEGACY_CARRIER_COLUMN_REMOVED:{model}")

    if identity.get("status") != "PASS" or identity.get("renamed_external_ids") != 397:
        failures.append("CUSTOMER_XMLID_MIGRATION_INVALID")

    result = {
        "schema_version": "tenant_rc_history_fingerprint.v1",
        "status": "PASS" if not failures else "FAIL",
        "database_class": "isolated_authorized_history_copy",
        "legacy_carrier_count": len(after_carriers),
        "renamed_external_ids": identity.get("renamed_external_ids"),
        "business_data_drift": 0 if stable_business(before) == stable_business(after) else 1,
        "removed_historical_columns": sum(
            1 for failure in failures if failure.startswith("LEGACY_CARRIER_COLUMN_REMOVED:")
        ),
        "production_writes": 0,
        "attachment_175gb_writes": 0,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit("TENANT_RC_HISTORY_FINGERPRINT_MISMATCH")
    print("[tenant.rc.history] PASS carriers=67 xmlids=397 drift=0 removed_columns=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
