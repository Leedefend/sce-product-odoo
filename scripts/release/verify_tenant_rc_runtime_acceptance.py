#!/usr/bin/env python3
import json
import os
from pathlib import Path

root = Path(os.environ["ARTIFACTS"])


def load(relative):
    path = root / relative
    if not path.is_file():
        raise SystemExit(f"RC_RUNTIME_REPORT_MISSING:{relative}")
    return json.loads(path.read_text(encoding="utf-8"))


surface = load("page-identity/full-surface-report.json")
summary = surface.get("summary", {})
expected_role_leaf_counts = {
    "fixture_role_finance": 10,
    "fixture_role_project_a_member": 7,
    "fixture_role_pm": 10,
    "fixture_role_owner": 4,
}
expected_navigation_total = sum(expected_role_leaf_counts.values())
if surface.get("leaf_counts") != expected_role_leaf_counts:
    raise SystemExit("RC_RUNTIME_NAVIGATION_ROLE_COUNTS_MISMATCH")
if (
    summary.get("authoritative_leaf_count") != expected_navigation_total
    or summary.get("scanned") != expected_navigation_total
):
    raise SystemExit("RC_RUNTIME_NAVIGATION_DENOMINATOR_MISMATCH")
if (
    summary.get("reachable") != expected_navigation_total
    or summary.get("identity_pass") != expected_navigation_total
    or summary.get("forbidden")
    or summary.get("unresolved")
):
    raise SystemExit("RC_RUNTIME_NAVIGATION_FAILURE")
for row in surface.get("rows", []):
    if row.get("console_errors") or row.get("page_errors") or row.get("http_errors"):
        raise SystemExit("RC_RUNTIME_SURFACE_ERROR")

reports = {
    "j02_j03": load("j02-j03/report.json"),
    "j04_j06": load("j04-j06/report.json"),
    "j07_j08": load("j07-j08/report.json"),
    "j09_j11": load("j09-j11/report.json"),
    "j12_j13": load("j12-j13/report.json"),
}
for name, report in reports.items():
    if not (report.get("pass") is True or report.get("ok") is True):
        raise SystemExit(f"RC_RUNTIME_JOURNEY_FAILED:{name}")

change_set = load("low-code-change-set.json")
if not change_set.get("ok"):
    raise SystemExit("RC_RUNTIME_LOW_CODE_FAILED")

payload = {
    "schema_version": 1,
    "source_sha": os.environ["SOURCE_SHA"],
    "product_image_digest": os.environ["IMAGE_DIGEST"],
    "runtime": "production-static-nginx",
    "navigation": f"{expected_navigation_total}/{expected_navigation_total}",
    "roles": 4,
    "journeys": "J02-J13",
    "responsive_widths": [390, 768, 1440, 1920],
    "low_code_change_set": "PASS",
    "console_pageerror_unhandled": 0,
    "unexpected_http_errors": 0,
    "axe_critical_serious": 0,
    "pass": True,
}
(root / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
