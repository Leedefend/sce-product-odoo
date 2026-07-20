#!/usr/bin/env python3
"""Fail closed when tenant module sets overlap or import another data layer."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADDONS = ROOT / "addons"
CONFIG = ROOT / "config/tenant/module_sets.v1.json"


def fail(messages: list[str]) -> None:
    for message in messages:
        print("[tenant.module_set_matrix] FAIL %s" % message)
    raise SystemExit(2)


def manifest_dependencies(module: str) -> set[str]:
    manifest = ADDONS / module / "__manifest__.py"
    if not manifest.is_file():
        return set()
    values = ast.literal_eval(manifest.read_text(encoding="utf-8"))
    return set(values.get("depends", []))


def dependency_closure(modules: set[str]) -> set[str]:
    closure = set(modules)
    pending = list(modules)
    while pending:
        module = pending.pop()
        for dependency in manifest_dependencies(module):
            if dependency in closure:
                continue
            closure.add(dependency)
            if (ADDONS / dependency / "__manifest__.py").is_file():
                pending.append(dependency)
    return closure


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    product = set(config["product_modules"])
    demo = set(config["demo_modules"])
    acceptance = set(config["acceptance_modules"])
    customer_token = set(config["customer_extension_modules"])
    errors = []

    if demo != product | {"smart_construction_demo"}:
        errors.append("DEMO_MODULE_SET must equal Product + smart_construction_demo")
    if acceptance != product | {"smart_construction_acceptance_fixture"}:
        errors.append(
            "ACCEPTANCE_MODULE_SET must equal Product + smart_construction_acceptance_fixture"
        )
    if customer_token != {"${SC_CUSTOMER_MODULE}"}:
        errors.append("CUSTOMER_EXTENSION_MODULE_SET must contain only SC_CUSTOMER_MODULE")

    forbidden_by_set = {
        "Product": {"smart_construction_demo", "smart_construction_acceptance_fixture"},
        "Demo": {"smart_construction_acceptance_fixture"},
        "Acceptance": {"smart_construction_demo"},
    }
    for label, modules in (("Product", product), ("Demo", demo), ("Acceptance", acceptance)):
        closure = dependency_closure(modules)
        hits = sorted(closure & forbidden_by_set[label])
        if hits:
            errors.append("%s dependency closure imports forbidden modules: %s" % (label, hits))
        customer_hits = sorted(item for item in closure if item.startswith("sce_customer_"))
        if customer_hits:
            errors.append("%s dependency closure imports customer modules: %s" % (label, customer_hits))

    if errors:
        fail(errors)
    print(
        "[tenant.module_set_matrix] PASS product=%d demo=%d acceptance=%d customer_extension=1"
        % (len(product), len(demo), len(acceptance))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
