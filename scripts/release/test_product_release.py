#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "release" / "product_release.py"
SPEC = importlib.util.spec_from_file_location("sce_product_release_test", MODULE_PATH)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ProductReleaseTests(unittest.TestCase):
    def test_release_manifest_is_bound_to_sbom_and_hashes_itself(self) -> None:
        version = release.read_version()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_manifest = root / "image-manifest.json"
            sbom = root / "sbom.cyclonedx.json"
            output = root / "product-release-manifest.json"
            image_manifest.write_text(json.dumps({
                "product_version": version,
                "source_sha": "a" * 40,
                "source_tree_sha": "b" * 40,
                "image_digest": "sha256:" + "c" * 64,
                "frontend_build_sha256": "d" * 64,
                "module_version_matrix": {"smart_core": "17.0.1.0.0"},
                "build_time": "2026-01-01T00:00:00Z",
            }), encoding="utf-8")
            sbom.write_text('{"bomFormat":"CycloneDX"}\n', encoding="utf-8")
            subprocess.run([
                sys.executable,
                str(ROOT / "scripts" / "release" / "product_release_manifest.py"),
                "--image-manifest", str(image_manifest),
                "--sbom", str(sbom),
                "--output", str(output),
            ], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["product_version"], version)
            self.assertEqual(payload["sbom_sha256"], hashlib.sha256(sbom.read_bytes()).hexdigest())
            manifest_sha = hashlib.sha256(output.read_bytes()).hexdigest()
            self.assertTrue((root / "product-release-manifest.sha256").read_text().startswith(manifest_sha))

    def test_version_and_release_contract_have_one_source(self) -> None:
        payload = release.load_release_config()
        self.assertEqual(payload["product_version"], release.read_version())
        self.assertEqual(payload["version_source"], "VERSION")
        self.assertEqual(
            set(payload["contracts"].values()),
            {"tenant_payload_v1", "route_authority.v1"},
        )

    def test_release_candidate_semver_precedes_final_release(self) -> None:
        current = release.read_version()
        self.assertLess(release.compare_versions(current, "1.0.0"), 0)
        self.assertGreater(release.compare_versions(current, "1.0.0-rc.0"), 0)

    def test_customer_compatibility_accepts_current_contracts(self) -> None:
        payload = release.load_release_config()
        release.verify_customer_compatibility(
            release.read_version(),
            "2.0.0",
            list(payload["contracts"].values()),
        )

    def test_customer_compatibility_rejects_version_and_contract_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "PRODUCT_VERSION_INCOMPATIBLE"):
            release.verify_customer_compatibility("2.0.0", "3.0.0", ["tenant_payload_v1"])
        with self.assertRaisesRegex(ValueError, "REQUIRED_CONTRACT_UNSUPPORTED"):
            release.verify_customer_compatibility(release.read_version(), "2.0.0", ["unknown.v9"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
