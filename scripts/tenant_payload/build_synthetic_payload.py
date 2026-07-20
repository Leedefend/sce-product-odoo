#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "addons/smart_core/utils/tenant_payload_v1.py"
SPEC = importlib.util.spec_from_file_location("tenant_payload_v1_builder", LIBRARY)
payload_v1 = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
import sys

sys.modules[SPEC.name] = payload_v1
SPEC.loader.exec_module(payload_v1)


def _record(external_key: str, values: dict, relationships: dict, file_meta: dict | None = None) -> dict:
    content_checksum = hashlib.sha256(
        json.dumps(
            {"values": values, "relationships": relationships, "file": file_meta},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    result = {
        "external_key": external_key,
        "values": values,
        "relationships": relationships,
        "content_checksum": content_checksum,
    }
    if file_meta:
        result["file"] = file_meta
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--tenant-key", default="sample")
    parser.add_argument("--module-version", default="17.0.1.3.0")
    parser.add_argument("--snapshot-id", default="synthetic:tenant-p04:001")
    parser.add_argument("--variant", default="001")
    parser.add_argument("--stable-external-keys", action="store_true")
    parser.add_argument("--company-key", default="main")
    args = parser.parse_args()
    if os.environ.get("SC_TENANT_PAYLOAD_TEST_MODE") != "1":
        raise SystemExit("TPV1_SYNTHETIC_TEST_MODE_REQUIRED")
    secret = os.environ.get("SC_TENANT_PAYLOAD_HMAC_KEY", "").encode("utf-8")
    if not secret:
        raise SystemExit("TPV1_SIGNATURE_KEY_REQUIRED")
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit("TPV1_SYNTHETIC_OUTPUT_NOT_EMPTY")
    output.mkdir(parents=True, exist_ok=True)
    records_dir = output / "records"
    filestore_dir = output / "filestore"
    records_dir.mkdir()
    filestore_dir.mkdir()

    variant = str(args.variant).strip().lower()
    if not variant or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in variant):
        raise SystemExit("TPV1_SYNTHETIC_VARIANT_INVALID")
    company_key = str(args.company_key).strip().lower()
    if not company_key or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in company_key):
        raise SystemExit("TPV1_SYNTHETIC_COMPANY_KEY_INVALID")
    key_variant = "stable" if args.stable_external_keys else variant
    attachment = f"synthetic tenant payload attachment {variant}\n".encode("utf-8")
    attachment_digest = hashlib.sha256(attachment).hexdigest()
    attachment_path = f"filestore/{attachment_digest[:2]}/{attachment_digest}"
    physical = output / attachment_path
    physical.parent.mkdir()
    physical.write_bytes(attachment)
    file_meta = {"path": attachment_path, "sha256": attachment_digest, "bytes": len(attachment)}
    resources = {
        "companies": [
            _record(
                company_key,
                {} if company_key == "main" else {"display_name": f"Synthetic Isolated Company {variant}"},
                {},
            )
        ],
        "partners": [
            _record(
                f"synthetic.organization.{key_variant}",
                {"display_name": f"Synthetic Tenant Organization {variant}", "entity_type": "organization"},
                {"company": f"companies::{company_key}"},
            )
        ],
        "projects": [
            _record(
                f"synthetic.project.{key_variant}",
                {"display_name": f"Synthetic Isolated Project {variant}", "active": True},
                {
                    "company": f"companies::{company_key}",
                    "owner": f"partners::synthetic.organization.{key_variant}",
                },
            )
        ],
        "attachments": [
            _record(
                f"synthetic.attachment.{key_variant}",
                {
                    "filename": f"synthetic-evidence-{variant}.txt",
                    "mimetype": "text/plain",
                    "resource_model": "res.partner",
                },
                {"company": f"companies::{company_key}", "target": f"partners::synthetic.organization.{key_variant}"},
                file_meta,
            ),
            _record(
                f"synthetic.attachment.shared.{key_variant}",
                {
                    "filename": f"synthetic-evidence-shared-{variant}.txt",
                    "mimetype": "text/plain",
                    "resource_model": "res.partner",
                },
                {"company": f"companies::{company_key}", "target": f"partners::synthetic.organization.{key_variant}"},
                file_meta,
            ),
        ],
    }
    file_entries = []
    checksums: list[tuple[str, str]] = []
    for resource, rows in resources.items():
        relative = f"records/{resource}.jsonl"
        content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode("utf-8")
        (output / relative).write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        checksums.append((relative, digest))
        file_entries.append({"path": relative, "bytes": len(content), "rows": len(rows), "sha256": digest})
    checksums.append((attachment_path, attachment_digest))
    file_entries.append({"path": attachment_path, "bytes": len(attachment), "rows": 0, "sha256": attachment_digest})
    checksums.sort()
    checksum_bytes = "".join(f"{digest}  {relative}\n" for relative, digest in checksums).encode("ascii")
    (output / "checksums.sha256").write_bytes(checksum_bytes)
    manifest = {
        "schema_version": "tenant_payload_v1",
        "payload_id": args.snapshot_id.replace(":", "-"),
        "tenant_key": args.tenant_key,
        "customer_module": f"sce_customer_{args.tenant_key}",
        "customer_module_version": args.module_version,
        "product_interface_version": "1",
        "source_snapshot_id": args.snapshot_id,
        "source_version": "synthetic-v1",
        "source_database_fingerprint": "sha256:synthetic-no-source-database",
        "created_at_utc": "2026-07-19T00:00:00Z",
        "record_counts": {resource: len(rows) for resource, rows in resources.items()},
        "amount_summaries": {},
        "relationship_summaries": {
            "attachments.company": 2,
            "attachments.target": 2,
            "partners.company": 1,
            "projects.company": 1,
            "projects.owner": 1,
        },
        "filestore_file_count": 1,
        "filestore_bytes": len(attachment),
        "payload_checksum": hashlib.sha256(checksum_bytes).hexdigest(),
        "encryption": {
            "algorithm": "age-x25519",
            "key_id": "synthetic-test-recipient",
            "at_rest_encrypted": True,
            "envelope_format": "tar.zst.age",
        },
        "signature_algorithm": "hmac-sha256",
        "signature_key_id": "synthetic-test-signing-key",
        "files": sorted(file_entries, key=lambda item: item["path"]),
        "import_order": [f"records/{resource}.jsonl" for resource in resources],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    signature = hmac.new(secret, payload_v1.canonical_manifest_bytes(manifest), hashlib.sha256).hexdigest()
    (output / "signature").write_text(signature + "\n", encoding="ascii")
    print(json.dumps({"schema_version": "tenant_payload_v1", "status": "PASS", "synthetic": True, "payload_checksum": manifest["payload_checksum"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
