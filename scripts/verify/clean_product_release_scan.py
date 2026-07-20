#!/usr/bin/env python3
"""Run and consolidate the file-tree, security, and product-boundary scans."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOUNDARY_CHECKS = (
    "scripts/verify/tenant_product_legacy_boundary.py",
    "scripts/verify/tenant_legacy_xmlid_boundary.py",
    "scripts/verify/customer_module_extraction_guard.py",
    "scripts/verify/product_to_customer_dependency_guard.py",
    "scripts/verify/tenant_product_payload_boundary_guard.py",
    "scripts/verify/tenant_module_set_matrix.py",
    "scripts/verify/tenant_product_fresh_install.py",
    "scripts/verify/tenant_data_responsibility_boundary.py",
    "scripts/verify/branch_governance_consistency_guard.py",
)


def run(command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": command,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "returncode": result.returncode,
        "output": result.stdout.strip().splitlines()[-20:],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    evidence = args.report.resolve().parent
    evidence.mkdir(parents=True, exist_ok=True)
    tree_report = evidence / "clean-product-tree-report.json"
    secret_report = evidence / "clean-product-secret-scan-report.json"
    personal_report = evidence / "clean-product-personal-data-scan-report.json"

    checks = {
        "tree": run([sys.executable, "scripts/verify/clean_product_tree_guard.py", "--report", str(tree_report)]),
        "secret": run(
            [
                sys.executable,
                "scripts/ci/secret_scan.py",
                "--scope",
                "worktree",
                "--report",
                str(secret_report),
            ]
        ),
        "personal_data": run(
            [
                sys.executable,
                "scripts/ci/personal_data_scan.py",
                "--scope",
                "worktree",
                "--report",
                str(personal_report),
            ]
        ),
    }
    boundary = {path: run([sys.executable, path]) for path in BOUNDARY_CHECKS}
    component_reports = {
        "tree": json.loads(tree_report.read_text(encoding="utf-8")),
        "secret": json.loads(secret_report.read_text(encoding="utf-8")),
        "personal_data": json.loads(personal_report.read_text(encoding="utf-8")),
    }
    all_checks = [*checks.values(), *boundary.values()]
    report = {
        "schema_version": "sce.clean_product_release_scan.v1",
        "source_head": "009f26e6351ba1aadc97efda2ebc972a60c03f37",
        "source_history_included": False,
        "root": str(ROOT),
        "status": "PASS" if all(item["returncode"] == 0 for item in all_checks) else "FAIL",
        "checks": checks,
        "boundary_checks": boundary,
        "component_reports": component_reports,
        "sensitive_values_recorded": False,
    }
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[clean_product_release_scan] {report['status']} checks={len(all_checks)}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
