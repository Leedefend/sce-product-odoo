#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "addons/smart_core/utils/tenant_payload_v1.py"
SPEC = importlib.util.spec_from_file_location("tenant_payload_v1_test", MODULE_PATH)
payload_v1 = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
import sys

sys.modules[SPEC.name] = payload_v1
SPEC.loader.exec_module(payload_v1)


def _record(external_key: str = "company:main", values: dict | None = None, relationships: dict | None = None) -> dict:
    values = values or {"display_code": "SYNTHETIC-001"}
    relationships = relationships or {}
    checksum = hashlib.sha256(
        json.dumps(
            {"values": values, "relationships": relationships, "file": None},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return {
        "external_key": external_key,
        "values": values,
        "relationships": relationships,
        "content_checksum": checksum,
    }


def _build_payload(root: Path, *, tenant_key: str = "sample", record: dict | None = None) -> dict:
    records = root / "records"
    records.mkdir()
    content = (json.dumps(record or _record(), ensure_ascii=False, sort_keys=True) + "\n").encode()
    record_path = records / "companies.jsonl"
    record_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    checksums = f"{digest}  records/companies.jsonl\n".encode()
    (root / "checksums.sha256").write_bytes(checksums)
    manifest = {
        "schema_version": "tenant_payload_v1",
        "payload_id": "synthetic-snapshot-001",
        "tenant_key": tenant_key,
        "customer_module": f"sce_customer_{tenant_key}",
        "customer_module_version": "17.0.1.0.0",
        "product_interface_version": "1",
        "source_snapshot_id": "synthetic:20260719:001",
        "source_version": "synthetic-v1",
        "source_database_fingerprint": "sha256:redacted-synthetic-fingerprint",
        "created_at_utc": "2026-07-19T00:00:00Z",
        "record_counts": {"companies": 1},
        "amount_summaries": {},
        "relationship_summaries": {},
        "filestore_file_count": 0,
        "filestore_bytes": 0,
        "payload_checksum": hashlib.sha256(checksums).hexdigest(),
        "encryption": {
            "algorithm": "age-x25519",
            "key_id": "synthetic-recipient",
            "at_rest_encrypted": True,
            "envelope_format": "tar.zst.age",
        },
        "signature_algorithm": "hmac-sha256",
        "signature_key_id": "synthetic-test-key",
        "files": [
            {
                "path": "records/companies.jsonl",
                "bytes": len(content),
                "rows": 1,
                "sha256": digest,
            }
        ],
        "import_order": ["records/companies.jsonl"],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    signature = hmac.new(b"synthetic-secret", payload_v1.canonical_manifest_bytes(manifest), hashlib.sha256).hexdigest()
    (root / "signature").write_text(signature + "\n", encoding="ascii")
    return manifest


class TenantPayloadV1Tests(unittest.TestCase):
    def _validate(self, root: Path, tenant_key: str = "sample"):
        with patch.dict(os.environ, {"SC_TENANT_PAYLOAD_TEST_MODE": "1"}):
            return payload_v1.validate_payload_directory(
                root,
                expected_tenant_key=tenant_key,
                hmac_key=b"synthetic-secret",
            )

    def test_valid_synthetic_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_payload(root)
            summary = self._validate(root)
            self.assertEqual(summary.record_count, 1)
            self.assertEqual(summary.filestore_file_count, 0)

    def test_rejects_cross_tenant_before_database_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_payload(root)
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "TENANT_MISMATCH"):
                self._validate(root, "another")

    def test_rejects_secret_field_without_echoing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "must-never-appear-in-error"
            _build_payload(root, record=_record(values={"password": secret}))
            with self.assertRaises(payload_v1.TenantPayloadError) as caught:
                self._validate(root)
            self.assertIn("SECRET_FIELD_FORBIDDEN", str(caught.exception))
            self.assertNotIn(secret, str(caught.exception))

    def test_rejects_checksum_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_payload(root)
            with (root / "records/companies.jsonl").open("ab") as handle:
                handle.write(b"tamper\n")
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "INTEGRITY_MISMATCH"):
                self._validate(root)

    def test_rejects_signature_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_payload(root)
            (root / "signature").write_text("0" * 64 + "\n", encoding="ascii")
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "SIGNATURE_INVALID"):
                self._validate(root)

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_payload(root)
            (root / "filestore").mkdir()
            (root / "filestore/escape").symlink_to(root / "manifest.json")
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "SYMLINK_FORBIDDEN"):
                self._validate(root)

    def test_rejects_undeclared_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_payload(root)
            (root / "records/extra.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "UNDECLARED_FILE"):
                self._validate(root)

    def test_hmac_is_synthetic_test_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_payload(root)
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(payload_v1.TenantPayloadError, "HMAC_TEST_MODE_REQUIRED"):
                    payload_v1.validate_payload_directory(root, hmac_key=b"synthetic-secret")

    def test_rejects_incompatible_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _build_payload(Path(tmp))
            manifest["schema_version"] = "tenant_payload_v2"
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "SCHEMA_INCOMPATIBLE"):
                payload_v1.validate_manifest(manifest)

    def test_rejects_incompatible_customer_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _build_payload(Path(tmp))
            manifest["customer_module"] = "sce_customer_another"
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "CUSTOMER_MODULE_MISMATCH"):
                payload_v1.validate_manifest(manifest)

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _build_payload(Path(tmp))
            manifest["files"][0]["path"] = "records/../../outside.jsonl"
            manifest["import_order"] = ["records/../../outside.jsonl"]
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "PATH_UNSAFE"):
                payload_v1.validate_manifest(manifest)

    def test_rejects_missing_declared_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_payload(root)
            (root / "records/companies.jsonl").unlink()
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "FILE_TYPE_INVALID"):
                self._validate(root)

    def test_rejects_amount_summary_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _record(values={"amount": "10.25"})
            manifest = _build_payload(root, record=record)
            manifest["amount_summaries"] = {"companies.amount": "10.26"}
            (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
            signature = hmac.new(
                b"synthetic-secret", payload_v1.canonical_manifest_bytes(manifest), hashlib.sha256
            ).hexdigest()
            (root / "signature").write_text(signature + "\n", encoding="ascii")
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "AMOUNT_SUMMARY_MISMATCH"):
                self._validate(root)

    def test_rejects_relationship_summary_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _record(relationships={"company": "companies::main"})
            manifest = _build_payload(root, record=record)
            manifest["relationship_summaries"] = {"companies.company": 2}
            (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
            signature = hmac.new(
                b"synthetic-secret", payload_v1.canonical_manifest_bytes(manifest), hashlib.sha256
            ).hexdigest()
            (root / "signature").write_text(signature + "\n", encoding="ascii")
            with self.assertRaisesRegex(payload_v1.TenantPayloadError, "RELATIONSHIP_SUMMARY_MISMATCH"):
                self._validate(root)


if __name__ == "__main__":
    unittest.main()
