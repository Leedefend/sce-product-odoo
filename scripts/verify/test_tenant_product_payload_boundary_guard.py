#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = ROOT / "scripts/verify/tenant_product_payload_boundary_guard.py"
LIFECYCLE = ROOT / "scripts/release/product_lifecycle.sh"


def load_guard():
    spec = importlib.util.spec_from_file_location("tenant_product_payload_boundary_guard", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TenantProductPayloadBoundaryGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guard = load_guard()

    def rules(self, relative: str, content: str) -> set[str]:
        return {rule for rule, _path in self.guard.classify_file(relative, content)}

    def test_specific_customer_module_name_is_rejected(self) -> None:
        rules = self.rules("scripts/release/example.py", "module = 'sce_customer_baosheng_private'")
        self.assertIn("customer_identity_or_brand_reference", rules)
        self.assertIn("runtime_tenant_specific_module_reference", rules)

    def test_fixed_tenant_id_is_rejected(self) -> None:
        rules = self.rules("config/example.json", json.dumps({"tenant_id": "scbs55"}))
        self.assertIn("customer_identity_or_brand_reference", rules)

    def test_fixed_customer_archive_name_is_rejected(self) -> None:
        rules = self.rules("artifacts/baosheng-history.tar.gz", "")
        self.assertIn("tracked_payload_or_archive", rules)
        self.assertIn("customer_identity_or_brand_reference", rules)

    def test_signed_generic_manifest_with_arbitrary_module_is_not_customer_identity(self) -> None:
        manifest = {
            "schema_version": "sce.tenant_customer_addon_package.v1",
            "package_kind": "tenant_customer_addon",
            "tenant_id": "tenant_example",
            "modules": ["external_extension_alpha"],
            "minimum_product_version": "1.0.0-rc.0",
            "maximum_product_version_exclusive": "2.0.0",
            "required_contracts": ["tenant_payload_v1", "route_authority.v1"],
            "archive_sha256": "0" * 64,
            "signature": {"algorithm": "ed25519", "key_id": "external-key", "value": "external-signature"},
        }
        self.assertEqual(set(), self.rules("tmp/generic-package-manifest.json", json.dumps(manifest)))

    def test_exact_generic_prefix_placeholder_is_narrowly_permitted(self) -> None:
        content = "GENERIC_MODULE_PATTERN = 'sce_customer_<tenant_key>'"
        self.assertEqual(set(), self.rules("config/generic_protocol.txt", content))
        specific = "GENERIC_MODULE_PATTERN = 'sce_customer_baosheng_private'"
        self.assertIn(
            "customer_identity_or_brand_reference",
            self.rules("config/generic_protocol.txt", specific),
        )

    def test_external_mode_missing_manifest_fails_before_docker_or_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "docker-called"
            docker = root / "docker"
            docker.write_text(f"#!/usr/bin/env bash\ntouch '{marker}'\nexit 99\n", encoding="utf-8")
            docker.chmod(0o755)
            environment = {
                **os.environ,
                "PATH": f"{root}:{os.environ.get('PATH', '')}",
                "DB_NAME": "sc_rc_boundary_test",
                "CANDIDATE_IMAGE": "unused",
                "PRODUCT_LIFECYCLE_MODE": "product-with-external-customer-package",
            }
            result = subprocess.run(
                ["bash", str(LIFECYCLE), "verify"],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("SC_CUSTOMER_PACKAGE_MANIFEST is required", result.stderr)
            self.assertFalse(marker.exists())

    def test_export_runtime_contains_no_fixed_identity_and_logs_fingerprint_only(self) -> None:
        content = (ROOT / "scripts/release/export_authorized_tenant_payload.sh").read_text(encoding="utf-8")
        self.assertNotIn("baosheng", content.lower())
        self.assertIn("tenant_fingerprint", content)
        self.assertNotIn("PASS source=%s", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
