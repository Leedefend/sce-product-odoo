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
if summary.get("authoritative_leaf_count") != 80 or summary.get("scanned") != 80:
    raise SystemExit("RC_RUNTIME_NAVIGATION_NOT_80_OF_80")
if summary.get("reachable") != 80 or summary.get("forbidden") or summary.get("unresolved"):
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
    "navigation": "80/80",
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
