from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ExternalCustomerAddonsRuntimeBoundaryTests(unittest.TestCase):
    def test_compose_override_is_opt_in(self):
        text = (ROOT / "scripts/common/compose.sh").read_text(encoding="utf-8")
        condition = 'if [[ -n "${SC_CUSTOMER_ADDONS_ROOT:-}" ]]; then'
        override = 'docker-compose.customer-addons.yml'
        self.assertIn(condition, text)
        self.assertIn(override, text)
        self.assertLess(text.index(condition), text.index(override))

    def test_module_operations_do_not_require_customer_mount_for_product(self):
        base_path = "/usr/lib/python3/dist-packages/odoo/addons,/mnt/source-addons,/mnt/extra-addons,$ADDONS_EXTERNAL_MOUNT"
        for relative in ("scripts/mod/install.sh", "scripts/mod/upgrade.sh"):
            with self.subTest(script=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(f'ODOO_ADDONS_PATH="{base_path}"', text)
                self.assertIn('if [[ -n "${SC_CUSTOMER_ADDONS_ROOT:-}" ]]; then', text)
                self.assertIn('ODOO_ADDONS_PATH="${ODOO_ADDONS_PATH},/mnt/customer-addons"', text)
                self.assertIn('--addons-path="$ODOO_ADDONS_PATH"', text)

    def test_customer_rename_confirmation_can_reach_odoo_shell(self):
        text = (ROOT / "scripts/ops/odoo_shell_exec.sh").read_text(encoding="utf-8")
        self.assertIn("SC_CONFIRM_*", text)


if __name__ == "__main__":
    unittest.main()
