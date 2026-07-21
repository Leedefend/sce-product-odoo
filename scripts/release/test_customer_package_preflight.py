#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "scripts" / "release" / "customer_package_preflight.py"
PAYLOAD_BUILDER = ROOT / "scripts" / "tenant_payload" / "build_synthetic_payload.py"
SAMPLE = ROOT / "customer_addons" / "sce_customer_sample"


class CustomerPackagePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive_root = self.root / "archive"
        self.archive_root.mkdir()
        self.archive = self.archive_root / "sample.tar.gz"
        with tarfile.open(self.archive, "w:gz") as handle:
            handle.add(SAMPLE, arcname="package/addons/sce_customer_sample")
        self.archive_sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.package_hmac_key = "test-only-package-signature-key"
        self.package_manifest = self.root / "customer-package.json"
        self.write_package_manifest()
        self.payload = self.root / "payload"
        self.hmac_key = "test-only-customer-package-key"
        subprocess.run(
            [
                sys.executable,
                str(PAYLOAD_BUILDER),
                "--output",
                str(self.payload),
                "--tenant-key",
                "sample",
                "--module-version",
                "17.0.1.3.0",
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "SC_TENANT_PAYLOAD_TEST_MODE": "1",
                "SC_TENANT_PAYLOAD_HMAC_KEY": self.hmac_key,
            },
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def write_package_manifest(
        self,
        *,
        tenant_id: str = "sample",
        modules: list[str] | None = None,
        archive_sha: str | None = None,
    ) -> None:
        payload = {
            "schema_version": "sce.tenant_customer_addon_package.v1",
            "package_kind": "tenant_customer_addon",
            "tenant_id": tenant_id,
            "modules": modules or ["sce_customer_sample"],
            "product_compatibility": {"min_inclusive": "17.0.0", "max_exclusive": "18.0.0"},
            "archive_sha256": archive_sha or self.archive_sha,
            "signature": {"algorithm": "hmac-sha256", "key_id": "test-package-key", "value": ""},
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload["signature"]["value"] = hmac.new(
            self.package_hmac_key.encode("utf-8"), canonical, hashlib.sha256
        ).hexdigest()
        self.package_manifest.write_text(json.dumps(payload), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_preflight(self, **overrides: str | None) -> subprocess.CompletedProcess[str]:
        environment = {
            **os.environ,
            "SC_CUSTOMER_ADDONS_ROOT": str(self.archive_root),
            "SC_CUSTOMER_PACKAGE_MANIFEST": str(self.package_manifest),
            "SC_CUSTOMER_ARCHIVE_SHA256": self.archive_sha,
            "SC_PAYLOAD_MANIFEST": str(self.payload / "manifest.json"),
            "SC_CUSTOMER_PACKAGE_TEST_MODE": "1",
            "SC_CUSTOMER_PACKAGE_HMAC_KEY": self.package_hmac_key,
            "SC_TENANT_PAYLOAD_TEST_MODE": "1",
            "SC_TENANT_PAYLOAD_HMAC_KEY": self.hmac_key,
        }
        for key, value in overrides.items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
        return subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT),
                "--prepare-dir",
                str(self.root / "prepared"),
                "--report",
                str(self.root / "report.json"),
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_archive_and_payload_are_admitted_without_database_writes(self) -> None:
        result = self.run_preflight()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"database_write_count":0', result.stdout)
        self.assertTrue((self.root / "prepared" / "package" / "addons" / "sce_customer_sample").is_dir())
        self.assertNotIn("sample", result.stdout)
        self.assertNotIn(self.hmac_key, result.stdout + result.stderr)
        self.assertNotIn(self.package_hmac_key, result.stdout + result.stderr)

    def test_checksum_declaration_fails_before_preparation(self) -> None:
        for key, value, marker in (
            ("SC_CUSTOMER_ARCHIVE_SHA256", "0" * 64, "CUSTOMER_PACKAGE_ARCHIVE_DECLARATION_MISMATCH"),
        ):
            with self.subTest(key=key):
                prepared = self.root / "prepared"
                if prepared.exists():
                    for child in sorted(prepared.rglob("*"), reverse=True):
                        if child.is_file():
                            child.unlink()
                        elif child.is_dir():
                            child.rmdir()
                    prepared.rmdir()
                result = self.run_preflight(**{key: value})
                self.assertNotEqual(0, result.returncode)
                self.assertIn(marker, result.stderr)
                self.assertFalse((self.root / "report.json").exists())

    def test_missing_package_manifest_fails_before_archive_or_database_work(self) -> None:
        result = self.run_preflight(SC_CUSTOMER_PACKAGE_MANIFEST=None)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("CUSTOMER_PACKAGE_MANIFEST_MISSING", result.stderr)
        self.assertFalse((self.root / "prepared").exists())
        self.assertFalse((self.root / "report.json").exists())

    def test_missing_archive_fails_before_database_work(self) -> None:
        self.archive.unlink()
        result = self.run_preflight()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("SC_CUSTOMER_ADDONS_ROOT must contain exactly one", result.stderr)
        self.assertFalse((self.root / "report.json").exists())

    def test_module_version_mismatch_fails_before_database_work(self) -> None:
        module = self.root / "version-mismatch" / "sce_customer_sample"
        shutil.copytree(SAMPLE, module)
        manifest = module / "__manifest__.py"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace("17.0.1.3.0", "17.0.9.9.9"),
            encoding="utf-8",
        )
        self.archive.unlink()
        with tarfile.open(self.archive, "w:gz") as handle:
            handle.add(module, arcname="package/addons/sce_customer_sample")
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.write_package_manifest(archive_sha=digest)
        result = self.run_preflight(SC_CUSTOMER_ARCHIVE_SHA256=digest)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("CUSTOMER_MODULE_VERSION_MISMATCH", result.stderr)
        self.assertFalse((self.root / "report.json").exists())
        self.assertNotIn(self.hmac_key, result.stdout + result.stderr)

    def test_payload_company_key_mismatch_fails_before_database_work(self) -> None:
        module = self.root / "company-mismatch" / "sce_customer_sample"
        shutil.copytree(SAMPLE, module)
        customer_manifest = module / "customer_module_manifest.json"
        payload = json.loads(customer_manifest.read_text(encoding="utf-8"))
        payload["payload_company_keys"] = ["not_the_payload_company"]
        customer_manifest.write_text(json.dumps(payload), encoding="utf-8")
        self.archive.unlink()
        with tarfile.open(self.archive, "w:gz") as handle:
            handle.add(module, arcname="package/addons/sce_customer_sample")
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.write_package_manifest(archive_sha=digest)
        result = self.run_preflight(SC_CUSTOMER_ARCHIVE_SHA256=digest)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("PAYLOAD_COMPANY_MISMATCH", result.stderr)
        self.assertFalse((self.root / "report.json").exists())

    def test_signed_manifest_allows_arbitrary_explicit_module_name_without_discovery(self) -> None:
        module_name = "external_extension_alpha"
        module = self.root / "arbitrary" / module_name
        shutil.copytree(SAMPLE, module)
        (module / "customer_module_manifest.json").unlink()
        self.archive.unlink()
        with tarfile.open(self.archive, "w:gz") as handle:
            handle.add(module, arcname=f"package/addons/{module_name}")
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.write_package_manifest(modules=[module_name], archive_sha=digest)
        result = self.run_preflight(
            SC_CUSTOMER_ARCHIVE_SHA256=digest,
            SC_PAYLOAD_MANIFEST=None,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads((self.root / "report.json").read_text(encoding="utf-8"))
        self.assertEqual([module_name], report["modules"])

    def test_unsigned_or_tampered_manifest_is_rejected_before_preparation(self) -> None:
        payload = json.loads(self.package_manifest.read_text(encoding="utf-8"))
        payload["tenant_id"] = "tampered"
        self.package_manifest.write_text(json.dumps(payload), encoding="utf-8")
        result = self.run_preflight()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("CUSTOMER_PACKAGE_SIGNATURE_INVALID", result.stderr)
        self.assertFalse((self.root / "prepared").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
