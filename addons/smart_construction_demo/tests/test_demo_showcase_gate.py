# -*- coding: utf-8 -*-
import os
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from ..hooks import guard_demo_scope


class _GuardCursor:
    def __init__(self, dbname):
        self.dbname = dbname


class _NoOrmEnvironment:
    def __init__(self, dbname):
        self.cr = _GuardCursor(dbname)

    def __getitem__(self, model_name):
        raise AssertionError("demo guard accessed ORM before rejecting: %s" % model_name)


@tagged("post_install", "-at_install", "sc_gate", "demo_gate")
class TestDemoShowcaseGate(TransactionCase):
    """Prevent demo filters from leaking into core business entries."""

    def test_no_demo_showcase_filters_in_core(self):
        demo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        addons_root = os.path.abspath(os.path.join(demo_root, os.pardir))
        module_root = os.path.join(addons_root, "smart_construction_core")
        allow_paths = {
            os.path.join("models", "core", "project_core.py"),
            os.path.join("migrations", "17.0.0.60", "post-migration.py"),
        }
        legacy_tokens = ("sc_demo_showcase", "sc_demo_showcase_ready")

        hits = []
        for root, _, files in os.walk(module_root):
            if "__pycache__" in root:
                continue
            for name in files:
                if not (name.endswith(".py") or name.endswith(".xml")):
                    continue
                path = os.path.join(root, name)
                with open(path, "r", encoding="utf-8") as handle:
                    content = handle.read()
                if not any(token in content for token in legacy_tokens):
                    continue
                rel_path = os.path.relpath(path, module_root)
                if rel_path.startswith("tests" + os.sep):
                    continue
                for idx, line in enumerate(content.splitlines(), start=1):
                    if not any(token in line for token in legacy_tokens):
                        continue
                    if rel_path in allow_paths:
                        continue
                    hits.append(f"{rel_path}:{idx}")

        self.assertFalse(
            hits,
            "禁止 core 模块硬编码 demo 过滤（sc_demo_showcase*），命中：%s"
            % ", ".join(hits),
        )

    def _assert_scope_denied(self, dbname, environment, allow, password, message):
        with patch.dict(
            os.environ,
            {
                "SC_ENVIRONMENT": environment,
                "SC_ALLOW_DEMO_DATA": allow,
                "SC_DEMO_USER_PASSWORD": password,
            },
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, message):
                guard_demo_scope(_NoOrmEnvironment(dbname))

    def test_demo_scope_rejects_production_database_before_orm(self):
        self._assert_scope_denied("production", "demo", "1", "secret", "sc_demo database")

    def test_demo_scope_rejects_history_database_before_orm(self):
        self._assert_scope_denied(
            "history_rehearsal", "demo", "1", "secret", "sc_demo database"
        )

    def test_demo_scope_rejects_empty_database_before_orm(self):
        self._assert_scope_denied("", "demo", "1", "secret", "sc_demo database")

    def test_demo_scope_rejects_unauthorized_environment_before_orm(self):
        self._assert_scope_denied("sc_demo", "production", "1", "secret", "SC_ENVIRONMENT")

    def test_demo_scope_rejects_missing_secret_before_orm(self):
        self._assert_scope_denied("sc_demo", "demo", "1", "", "SC_DEMO_USER_PASSWORD")
