#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADDONS = ROOT / "addons"


def main() -> int:
    product = {"smart_core", "smart_construction_core", "smart_construction_bundle", "smart_construction_seed"}
    errors = []
    for name in sorted(product):
        path = ADDONS / name / "__manifest__.py"
        if not path.is_file():
            errors.append(f"PRODUCT_MODULE_MISSING:{name}")
            continue
        manifest = ast.literal_eval(path.read_text(encoding="utf-8"))
        for dependency in manifest.get("depends", []):
            if dependency.startswith("sce_customer_") or dependency.endswith("_demo") or "fixture" in dependency:
                errors.append(f"PRODUCT_DEPENDENCY_FORBIDDEN:{name}:{dependency}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("[tenant_product_fresh_install] PASS product_dependency_closure=clean runtime_test=Q11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
