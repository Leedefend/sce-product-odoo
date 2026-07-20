#!/usr/bin/env python3
"""Generate the TENANT-BOUNDARY-06 legacy carrier ownership inventory.

The report records technical names and aggregate counts only. It never reads
record values, attachment content, or customer payloads. Optional history
counts must be supplied as a model-to-count JSON produced in an isolated DB.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "addons/smart_construction_core"
DEFAULT_OUTPUT = ROOT / "docs/ops/audit/tenant_boundary_06_legacy_carrier_inventory.csv"
FIELDS = (
    "path",
    "symbol_or_xmlid",
    "model",
    "table",
    "classification",
    "record_count_in_history_db",
    "referenced_by_product_runtime",
    "referenced_by_customer_adapter",
    "has_user_navigation",
    "has_acl",
    "move_target",
    "migration_required",
    "decision",
)
FINAL_FIELDS = (
    "model",
    "table",
    "python_path",
    "views",
    "actions",
    "menus",
    "ACL",
    "record_rules",
    "cron",
    "seed",
    "record_count",
    "runtime_references",
    "report_dependencies",
    "frontend_contract_dependencies",
    "customer_adapter_dependencies",
    "classification",
    "final_owner",
    "decision_evidence",
)
FINAL_CLASSIFICATIONS = {"CUSTOMER_LEGACY_CARRIER", "DEAD_CONFIRMED"}
DIRECT_CARRIER_MODELS = {"sc.history.todo", "sc.project.member.staging"}
TRANSITIONAL_MODELS = {
    "sc.legacy.legacy_source.fact.staging",
    "sc.legacy.legacy_source.material.map",
    "sc.project.member.staging",
}
MIXED_FILES = {"partner_legacy.py", "project_legacy.py", "contract_legacy.py"}
LEGACY_TOKEN = re.compile(r"(?:\blegacy\b|legacy_|_legacy|sc\.history\.todo|sc\.project\.member\.staging)", re.I)
REFERENCE_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
TEXT_SUFFIXES = {".csv", ".json", ".md", ".mk", ".py", ".sh", ".ts", ".vue", ".xml", ".yaml", ".yml"}


def _sanitize_private_reference(value: str) -> str:
    """Keep structural evidence while removing the private module identity."""
    return re.sub(
        r"customer:addons/[^/]+/",
        "external_customer_legacy_module/",
        value,
    )


def render_final_carrier_inventory(source: Path, output: Path) -> int:
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or tuple(rows[0].keys()) != FINAL_FIELDS:
        raise SystemExit("TENANT_BOUNDARY_FINAL_INVENTORY_SCHEMA_INVALID")
    models = [row["model"] for row in rows]
    classifications = Counter(row["classification"] for row in rows)
    if (
        len(rows) != 68
        or len(set(models)) != 68
        or set(classifications) - FINAL_CLASSIFICATIONS
        or classifications["CUSTOMER_LEGACY_CARRIER"] != 67
        or classifications["DEAD_CONFIRMED"] != 1
    ):
        raise SystemExit("TENANT_BOUNDARY_FINAL_INVENTORY_PARTITION_INVALID")
    rendered = [
        {key: _sanitize_private_reference(row.get(key, "")) for key in FINAL_FIELDS}
        for row in rows
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FINAL_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rendered)
    record_total = sum(
        int(row["record_count"])
        for row in rendered
        if str(row["record_count"]).isdigit()
    )
    print(
        "[tenant_boundary_06_inventory] PASS carriers=68 "
        "customer=67 dead=1 unresolved=0 records=%d" % record_total
    )
    return 0


def tracked_paths() -> list[str]:
    output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return sorted(path for path in output.splitlines() if path)


def literal_assignment(node: ast.ClassDef, name: str):
    for item in node.body:
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        try:
            return ast.literal_eval(item.value)
        except (ValueError, TypeError):
            return None
    return None


def is_direct_carrier(model: str) -> bool:
    return model.startswith("sc.legacy.") or model in DIRECT_CARRIER_MODELS


def classification_for(model: str, path: Path, text: str, symbol: str) -> str:
    if model in TRANSITIONAL_MODELS or "/migrations/" in path.as_posix():
        return "TRANSITIONAL_STAGING"
    if is_direct_carrier(model):
        return "CUSTOMER_LEGACY_CARRIER"
    if path.name in MIXED_FILES:
        return "MIXED_REQUIRES_SPLIT"
    if "sc.tenant.payload.external.identity" in text or "tenant_payload" in path.as_posix():
        return "PRODUCT_GENERIC_MIGRATION_FRAMEWORK"
    if LEGACY_TOKEN.search(symbol) or LEGACY_TOKEN.search(path.as_posix()):
        return "CUSTOMER_LEGACY_CARRIER"
    if LEGACY_TOKEN.search(text):
        return "MIXED_REQUIRES_SPLIT"
    return "PRODUCT_CANONICAL"


def move_target(classification: str) -> str:
    if classification == "CUSTOMER_LEGACY_CARRIER":
        return "external_customer_legacy_module"
    if classification == "TRANSITIONAL_STAGING":
        return "external_customer_legacy_module_or_retire_after_migration"
    if classification == "MIXED_REQUIRES_SPLIT":
        return "split_product_canonical_and_external_customer_legacy_module"
    if classification == "PRODUCT_GENERIC_MIGRATION_FRAMEWORK":
        return "smart_core_generic_protocol"
    if classification == "DEAD_OR_UNUSED":
        return "remove_after_reference_and_history_proof"
    return "smart_construction_core"


def decision(classification: str) -> str:
    return {
        "CUSTOMER_LEGACY_CARRIER": "MOVE_WITH_TECHNICAL_NAME_AND_TABLE_PRESERVED",
        "TRANSITIONAL_STAGING": "REVIEW_ONLINE_WRITES_THEN_MOVE_OR_RETIRE",
        "MIXED_REQUIRES_SPLIT": "SPLIT_BEFORE_OWNERSHIP_TRANSFER",
        "PRODUCT_GENERIC_MIGRATION_FRAMEWORK": "KEEP_ONLY_GENERIC_PROTOCOL",
        "DEAD_OR_UNUSED": "REMOVE_ONLY_AFTER_DB_AND_RUNTIME_PROOF",
        "PRODUCT_CANONICAL": "KEEP_AS_STANDARD_PRODUCT",
    }[classification]


def row(path: Path, symbol: str, model: str, table: str, classification: str, counts: dict[str, int], product_refs: int, customer_refs: int, nav: bool = False, acl: bool = False) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "symbol_or_xmlid": symbol,
        "model": model,
        "table": table,
        "classification": classification,
        "record_count_in_history_db": counts.get(model, "NOT_MEASURED") if model else "NOT_APPLICABLE",
        "referenced_by_product_runtime": product_refs,
        "referenced_by_customer_adapter": customer_refs,
        "has_user_navigation": str(nav).lower(),
        "has_acl": str(acl).lower(),
        "move_target": move_target(classification),
        "migration_required": str(classification in {"CUSTOMER_LEGACY_CARRIER", "TRANSITIONAL_STAGING", "MIXED_REQUIRES_SPLIT"}).lower(),
        "decision": decision(classification),
    }


def reference_count(needle: str, references: Counter[str]) -> int:
    if not needle:
        return 0
    return references[needle]


def reference_counts(files: list[Path]) -> Counter[str]:
    result: Counter[str] = Counter()
    for path in files:
        result.update(REFERENCE_TOKEN.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return result


def python_rows(path: Path, counts: dict[str, int], product_references: Counter[str], customer_references: Counter[str]) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    result = []
    for node in (item for item in ast.walk(tree) if isinstance(item, ast.ClassDef)):
        model = literal_assignment(node, "_name") or literal_assignment(node, "_inherit") or ""
        if isinstance(model, (tuple, list)):
            model = ",".join(model)
        if not isinstance(model, str):
            model = ""
        table = literal_assignment(node, "_table") or (model.replace(".", "_") if model else "")
        class_text = ast.get_source_segment(text, node) or ""
        class_kind = classification_for(model, path, class_text, node.name)
        if is_direct_carrier(model) or LEGACY_TOKEN.search(class_text) or path.name in MIXED_FILES:
            result.append(row(path, node.name, model, str(table), class_kind, counts, reference_count(model, product_references), reference_count(model, customer_references)))
        for item in node.body:
            if not isinstance(item, (ast.Assign, ast.AnnAssign)):
                continue
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            names = [target.id for target in targets if isinstance(target, ast.Name)]
            for name in names:
                source = ast.get_source_segment(text, item) or ""
                if not (LEGACY_TOKEN.search(name) or (is_direct_carrier(model) and "fields." in source)):
                    continue
                field_kind = classification_for(model, path, source, name)
                result.append(row(path, f"{node.name}.{name}", model, str(table), field_kind, counts, reference_count(name, product_references), reference_count(name, customer_references)))
    return result


def xml_rows(path: Path, counts: dict[str, int], product_references: Counter[str], customer_references: Counter[str]) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not LEGACY_TOKEN.search(text) and "legacy" not in path.name.lower():
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return [row(path, path.stem, "", "", classification_for("", path, text, path.stem), counts, 0, 0)]
    result = []
    for node in root.iter():
        if node.tag not in {"record", "menuitem"}:
            continue
        xmlid = node.attrib.get("id", "")
        record_model = node.attrib.get("model", "ir.ui.menu" if node.tag == "menuitem" else "")
        serialized = ET.tostring(node, encoding="unicode")
        if not (LEGACY_TOKEN.search(xmlid) or LEGACY_TOKEN.search(record_model) or LEGACY_TOKEN.search(serialized) or "legacy" in path.name.lower()):
            continue
        kind = classification_for(record_model, path, serialized, xmlid)
        result.append(row(path, xmlid, record_model, record_model.replace(".", "_"), kind, counts, reference_count(xmlid, product_references), reference_count(xmlid, customer_references), nav=node.tag == "menuitem" or record_model in {"ir.ui.menu", "ir.actions.act_window"}))
    return result


def csv_rows(path: Path, counts: dict[str, int], product_references: Counter[str], customer_references: Counter[str]) -> list[dict[str, object]]:
    result = []
    with path.open(encoding="utf-8", newline="") as handle:
        for item in csv.DictReader(handle):
            serialized = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if not LEGACY_TOKEN.search(serialized):
                continue
            xmlid = item.get("id") or item.get("name") or "acl"
            model_ref = item.get("model_id:id", "")
            model = model_ref.removeprefix("model_").replace("_", ".")
            kind = classification_for(model, path, serialized, xmlid)
            result.append(row(path, xmlid, model, model.replace(".", "_"), kind, counts, reference_count(xmlid, product_references), reference_count(xmlid, customer_references), acl=True))
    return result


def file_level_rows(paths: list[str], counts: dict[str, int], product_references: Counter[str], customer_references: Counter[str]) -> list[dict[str, object]]:
    result = []
    for relative in paths:
        path = ROOT / relative
        if not path.is_file() or path.suffix not in {".py", ".xml", ".csv", ".json", ".ts", ".vue"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not LEGACY_TOKEN.search(text) and "legacy" not in path.name.lower():
            continue
        if relative.startswith("addons/smart_construction_core/models/") and path.suffix == ".py":
            result.extend(python_rows(path, counts, product_references, customer_references))
        elif relative.startswith("addons/smart_construction_core/") and path.suffix == ".xml":
            result.extend(xml_rows(path, counts, product_references, customer_references))
        elif relative.endswith("ir.model.access.csv"):
            result.extend(csv_rows(path, counts, product_references, customer_references))
        else:
            kind = classification_for("", path, text, path.stem)
            result.append(row(path, path.stem, "", "", kind, counts, 0, 0, nav="menu" in path.name.lower(), acl="security" in relative))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--history-counts", type=Path)
    parser.add_argument("--customer-root", type=Path)
    args = parser.parse_args()
    if args.customer_root:
        final_source = (
            args.customer_root
            / "docs"
            / "audit"
            / "tenant_boundary_06_carrier_final_inventory.csv"
        )
        if not final_source.is_file():
            raise SystemExit("TENANT_BOUNDARY_FINAL_INVENTORY_MISSING")
        return render_final_carrier_inventory(final_source, args.output)
    counts_payload = json.loads(args.history_counts.read_text()) if args.history_counts else {}
    counts = counts_payload.get("models", counts_payload)
    paths = tracked_paths()
    product_files = [
        ROOT / path
        for path in paths
        if (ROOT / path).is_file()
        and (ROOT / path).suffix.lower() in TEXT_SUFFIXES
        and path.startswith(("addons/", "frontend/apps/web/src/", "scripts/", "make/"))
    ]
    customer_files = []
    if args.customer_root and args.customer_root.is_dir():
        customer_files = [path for path in args.customer_root.rglob("*") if path.is_file() and ".git" not in path.parts and path.suffix.lower() in TEXT_SUFFIXES]
    rows = file_level_rows(
        paths,
        counts,
        reference_counts(product_files),
        reference_counts(customer_files),
    )
    unique = {(item["path"], item["symbol_or_xmlid"], item["model"]): item for item in rows}
    rendered = sorted(unique.values(), key=lambda item: (str(item["path"]), str(item["symbol_or_xmlid"]), str(item["model"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rendered)
    summary = Counter(str(item["classification"]) for item in rendered)
    print("[tenant_boundary_06_inventory] PASS rows=%d %s" % (len(rendered), " ".join(f"{key}={summary[key]}" for key in sorted(summary))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
