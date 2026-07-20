#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(os.environ.get("SC_CUSTOMER_ADDONS_ROOT", "")).resolve()
    if not root.is_dir():
        print("CUSTOMER_ROOT_MISSING:SC_CUSTOMER_ADDONS_ROOT", file=sys.stderr)
        return 1
    candidates = sorted((root / "addons").glob("*/legacy_owned_models_v2.json"))
    if len(candidates) != 1:
        print("CUSTOMER_LEGACY_MODULE_AMBIGUOUS:legacy_owned_models_v2.json", file=sys.stderr)
        return 1
    module = candidates[0].parent
    owned = json.loads((module / "legacy_owned_models_v2.json").read_text(encoding="utf-8"))
    bridge = json.loads((module / "legacy_bridge_manifest_v1.json").read_text(encoding="utf-8"))
    dead = json.loads((module / "legacy_dead_models_v1.json").read_text(encoding="utf-8"))
    sets = [{row["model"] for row in doc.get("models", [])} for doc in (owned, bridge, dead)]
    if any(sets[a] & sets[b] for a in range(3) for b in range(a + 1, 3)) or len(set().union(*sets)) != 68:
        print("CUSTOMER_OWNERSHIP_INVALID:carrier_partition", file=sys.stderr)
        return 1
    result = subprocess.run([sys.executable, "scripts/verify_customer_package.py"], cwd=root)
    if result.returncode:
        return result.returncode
    print(f"[tenant_customer_module_ownership] PASS owned={len(sets[0])} bridge={len(sets[1])} dead={len(sets[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
