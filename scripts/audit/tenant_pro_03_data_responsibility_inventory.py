#!/usr/bin/env python3
"""Generate the TENANT-PRO-03 data responsibility inventory.

The inventory is deliberately path- and carrier-oriented.  It never prints or
copies record values, so it can be regenerated after a personal-data scan
without turning audit output into another payload carrier.
"""

from __future__ import annotations

import csv
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/ops/audit/tenant_pro_03_data_responsibility_inventory.csv"

RESOURCE_SUFFIXES = {
    ".csv",
    ".gif",
    ".jpeg",
    ".jpg",
    ".json",
    ".png",
    ".svg",
    ".webp",
    ".xml",
    ".yaml",
    ".yml",
}
RELEASE_PREFIXES = (
    ".github/workflows/",
    "make/",
    "scripts/release/",
)
REFERENCE_SEED_MARKERS = (
    "baseline",
    "dictionary",
    "icp_defaults",
    "project_stage",
    "reference",
    "tax",
)
DEMO_MARKERS = (
    "/demo/",
    "_demo",
    "demo_",
    "showcase",
    "showroom",
    "/scenario/",
)
FIXTURE_MARKERS = (
    "/fixture/",
    "/fixtures/",
    "/test/",
    "/tests/",
    "scripts/verify/",
    "smart_construction_acceptance_fixture",
)
LEGACY_SEED_PATHS = set()


@dataclass(frozen=True)
class Decision:
    classification: str
    allowed_environment: str
    install_trigger: str
    idempotent: str
    uninstall_policy: str
    customer_specific: str
    contains_personal_data: str
    decision: str


def tracked_paths() -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    return sorted(
        line for line in output.splitlines() if line and (ROOT / line).is_file()
    )


def module_for(path: str) -> str:
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] in {"addons", "customer_addons"}:
        return parts[1]
    return ""


def is_inventory_scope(path: str) -> bool:
    lowered = path.lower()
    name = Path(path).name
    suffix = Path(path).suffix.lower()
    if path.startswith(("addons/smart_construction_demo/", "addons/smart_construction_seed/")):
        return True
    if path.startswith(("scripts/demo/", "scripts/verify/")):
        return True
    if path.startswith(RELEASE_PREFIXES):
        return True
    if name == "Makefile" or name.startswith("Dockerfile") or name.startswith("docker-compose"):
        return True
    if suffix in RESOURCE_SUFFIXES:
        return True
    if "/migrations/" in lowered:
        return True
    if name == "__manifest__.py":
        return True
    if name in {"hooks.py", "hook.py"}:
        return True
    return False


def install_trigger(path: str) -> str:
    name = Path(path).name
    if name == "__manifest__.py":
        return "module_manifest"
    if name in {"hooks.py", "hook.py"}:
        return "module_install_hook"
    if "/migrations/" in path:
        return "module_upgrade_migration"
    if path.startswith("scripts/verify/") or any(marker in path.lower() for marker in FIXTURE_MARKERS):
        return "explicit_acceptance_or_test_runner"
    if path.startswith("scripts/demo/") or "smart_construction_demo" in path:
        return "explicit_demo_module_or_runner"
    if path.startswith(RELEASE_PREFIXES) or Path(path).name.startswith(("Dockerfile", "docker-compose")):
        return "build_release_or_ci_configuration"
    if "/data/" in path or "/demo/" in path:
        return "module_manifest_data"
    return "explicit_tool_or_module_execution"


def classify(path: str) -> Decision:
    lowered = path.lower()
    module = module_for(path)
    trigger = install_trigger(path)

    if "sce_customer_" in lowered or path.startswith("customer_addons/"):
        return Decision(
            "CUSTOMER_ONLY",
            "customer_extension_validation",
            trigger,
            "required",
            "external_customer_module_owned_only",
            "false" if "sce_customer_sample" in lowered else "true",
            "false",
            "KEEP_ONLY_AS_EXTERNAL_CUSTOMER_EXTENSION_TEMPLATE",
        )

    if path in LEGACY_SEED_PATHS:
        return Decision(
            "LEGACY_UNRESOLVED",
            "none_until_resolved",
            trigger,
            "unproven",
            "no_automatic_uninstall_action",
            "false",
            "false",
            "EXCLUDE_FROM_RELEASE_DEFAULT_AND_RESOLVE",
        )

    if module == "smart_construction_demo" or path.startswith("scripts/demo/"):
        return Decision(
            "DEMO_ONLY",
            "demo",
            trigger,
            "required",
            "remove_module_owned_demo_records_only",
            "false",
            "false",
            "KEEP_DEMO_EXPLICIT_AND_NON_PRODUCTION",
        )

    if module == "smart_construction_seed":
        if any(marker in lowered for marker in DEMO_MARKERS):
            return Decision(
                "DEMO_ONLY",
                "demo",
                trigger,
                "required",
                "remove_module_owned_demo_records_only",
                "false",
                "false",
                "MOVE_OUT_OF_SEED_INTO_DEMO_CARRIER",
            )
        return Decision(
            "PRODUCT_REFERENCE_SEED",
            "production,demo,acceptance,customer",
            trigger,
            "required",
            "preserve_user_modified_reference_values",
            "false",
            "false",
            "KEEP_ONLY_IF_PRODUCT_REFERENCE_BASIS_IS_DOCUMENTED",
        )

    if path.startswith("scripts/verify/") or any(marker in lowered for marker in FIXTURE_MARKERS):
        return Decision(
            "TEST_FIXTURE_ONLY",
            "acceptance,test",
            trigger,
            "required",
            "destroy_dedicated_acceptance_database",
            "false",
            "false",
            "KEEP_OUT_OF_PRODUCTION_INSTALL_SET",
        )

    if any(marker in lowered for marker in DEMO_MARKERS):
        return Decision(
            "DEMO_ONLY",
            "demo",
            trigger,
            "required",
            "remove_module_owned_demo_records_only",
            "false",
            "false",
            "KEEP_DEMO_EXPLICIT_AND_NON_PRODUCTION",
        )

    if "/data/" in lowered and any(marker in lowered for marker in REFERENCE_SEED_MARKERS):
        return Decision(
            "PRODUCT_REFERENCE_SEED",
            "production,demo,acceptance,customer",
            trigger,
            "required",
            "preserve_user_modified_reference_values",
            "false",
            "false",
            "KEEP_AS_DOCUMENTED_PRODUCT_REFERENCE_BASELINE",
        )

    return Decision(
        "PRODUCT_REQUIRED",
        "production,demo,acceptance,customer",
        trigger,
        "required",
        "module_owned_records_only",
        "false",
        "false",
        "KEEP_AS_PRODUCT_OR_DELIVERY_CONFIGURATION",
    )


def record_or_resource(path: str) -> str:
    name = Path(path).name
    if name == "__manifest__.py":
        return "module_manifest"
    if name in {"hooks.py", "hook.py"}:
        return "module_install_hook"
    if "/migrations/" in path:
        return "module_upgrade_migration"
    return Path(path).stem


def generate() -> dict[str, int]:
    rows = []
    counts: dict[str, int] = {}
    for path in tracked_paths():
        if not is_inventory_scope(path):
            continue
        item = classify(path)
        counts[item.classification] = counts.get(item.classification, 0) + 1
        rows.append(
            {
                "path": path,
                "module": module_for(path),
                "record_or_resource": record_or_resource(path),
                "classification": item.classification,
                "allowed_environment": item.allowed_environment,
                "install_trigger": item.install_trigger,
                "idempotent": item.idempotent,
                "uninstall_policy": item.uninstall_policy,
                "customer_specific": item.customer_specific,
                "contains_personal_data": item.contains_personal_data,
                "decision": item.decision,
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "module",
        "record_or_resource",
        "classification",
        "allowed_environment",
        "install_trigger",
        "idempotent",
        "uninstall_policy",
        "customer_specific",
        "contains_personal_data",
        "decision",
    ]
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return counts


def main() -> int:
    counts = generate()
    rendered = " ".join(f"{key}={counts.get(key, 0)}" for key in (
        "PRODUCT_REQUIRED",
        "PRODUCT_REFERENCE_SEED",
        "DEMO_ONLY",
        "TEST_FIXTURE_ONLY",
        "CUSTOMER_ONLY",
        "LEGACY_UNRESOLVED",
    ))
    print(f"[tenant_pro_03_inventory] PASS rows={sum(counts.values())} {rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
