#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "config/tenant/p0_state_known_debt.v1.json"
TEST_FILE = ROOT / "addons/smart_construction_core/tests/test_p0_state_closure.py"


def main() -> int:
    errors = []
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    failures = payload.get("failures") or []
    if payload.get("baseline_sha") != "6b7ec6a667f297cca4d3788f0fd3b0633097b94e":
        errors.append("baseline_sha_changed")
    if payload.get("failure_count") != 16 or len(failures) != 16:
        errors.append("known_debt_count_mismatch")
    test_ids = [item.get("test_id") for item in failures]
    if len(test_ids) != len(set(test_ids)):
        errors.append("duplicate_test_id")
    source = TEST_FILE.read_text(encoding="utf-8")
    for test_id in test_ids:
        if f"def {test_id}(" not in source:
            errors.append(f"missing_test:{test_id}")
    if any(item.get("error_type") not in {"UserError", "ValidationError", "AccessError"} for item in failures):
        errors.append("error_type_not_frozen")
    if errors:
        print("[tenant_p04_p0_debt_guard] FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("[tenant_p04_p0_debt_guard] PASS frozen=16 baseline=6b7ec6a")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
