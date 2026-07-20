#!/usr/bin/env python3
"""Verify that release module sets do not contain demo, fixture, or unresolved data."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/tenant/module_sets.v1.json"
INVENTORY = ROOT / "docs/ops/audit/tenant_pro_03_data_responsibility_inventory.csv"


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    product = set(config["product_modules"])
    errors = []
    with INVENTORY.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["module"] not in product:
            continue
        installed_trigger = row["install_trigger"] in {
            "module_manifest",
            "module_install_hook",
            "module_upgrade_migration",
            "module_manifest_data",
        }
        if installed_trigger and row["classification"] in {
            "DEMO_ONLY",
            "TEST_FIXTURE_ONLY",
            "CUSTOMER_ONLY",
        }:
            errors.append("%s classified %s in Product" % (row["path"], row["classification"]))
        if row["classification"] == "LEGACY_UNRESOLVED" and row["allowed_environment"] in {
            "production",
            "all",
        }:
            errors.append("%s unresolved but release-eligible" % row["path"])
    if errors:
        for message in errors:
            print("[tenant.data_responsibility_boundary] FAIL %s" % message)
        raise SystemExit(2)
    print("[tenant.data_responsibility_boundary] PASS rows=%d" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
