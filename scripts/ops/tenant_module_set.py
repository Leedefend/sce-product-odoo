#!/usr/bin/env python3
"""Read the authoritative tenant module-set matrix without shell evaluation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/tenant/module_sets.v1.json"
KEYS = {
    "product": "product_modules",
    "demo": "demo_modules",
    "acceptance": "acceptance_modules",
    "customer": "customer_extension_modules",
}


def load_config() -> dict:
    with CONFIG.open(encoding="utf-8") as handle:
        return json.load(handle)


def modules_for(name: str, resolve_customer: bool) -> list[str]:
    config = load_config()
    modules = list(config[KEYS[name]])
    if name != "customer":
        return modules
    customer_module = os.environ.get(config["customer_module_env"], "").strip()
    if resolve_customer:
        if not customer_module:
            raise SystemExit("SC_CUSTOMER_MODULE is required for the customer module set")
        modules = [customer_module if item == "${SC_CUSTOMER_MODULE}" else item for item in modules]
    return list(config["product_modules"]) + modules


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("set_name", choices=sorted(KEYS))
    parser.add_argument("--resolve-customer", action="store_true")
    args = parser.parse_args()
    print(",".join(modules_for(args.set_name, args.resolve_customer)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
