#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "addons" / "smart_construction_core"


def main() -> int:
    manifest = ast.literal_eval((MODULE / "__manifest__.py").read_text(encoding="utf-8"))
    errors = []
    ids = set()
    refs = []
    for rel in manifest.get("data", []):
        if not rel.endswith(".xml"):
            continue
        path = MODULE / rel
        tree = ET.parse(path)
        for node in tree.iter():
            xmlid = node.attrib.get("id")
            if xmlid:
                ids.add(xmlid)
            model = node.attrib.get("model", "")
            if model.startswith("sc.legacy."):
                errors.append(f"LEGACY_VIEW_MODEL:{rel}:{model}")
            for key in ("ref", "action", "parent"):
                value = node.attrib.get(key)
                if value and value.startswith("smart_construction_core."):
                    refs.append((rel, value.split(".", 1)[1]))
            if node.tag == "field" and node.attrib.get("name") in {"res_model", "model"}:
                value = (node.text or "").strip()
                if value.startswith("sc.legacy."):
                    errors.append(f"LEGACY_ACTION_MODEL:{rel}:{value}")
    for rel, ref in refs:
        if ref.startswith(("action_sc_legacy_", "menu_sc_legacy_", "view_sc_legacy_")) and ref not in ids:
            errors.append(f"OLD_MODULE_XMLID_RUNTIME_REFERENCE:{rel}:{ref}")
    if errors:
        for item in sorted(set(errors)):
            print(item, file=sys.stderr)
        return 1
    print("[tenant_legacy_xmlid_boundary] PASS dangling_customer_xmlids=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
