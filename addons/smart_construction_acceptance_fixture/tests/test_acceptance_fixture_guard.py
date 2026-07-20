# -*- coding: utf-8 -*-
import os
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from ..tools.frontend_productization_fixture import _guard_acceptance_scope


class _Cursor:
    def __init__(self, dbname):
        self.dbname = dbname


class _NoOrmEnvironment:
    """Expose only the database name and fail if a guard reaches the ORM."""

    def __init__(self, dbname):
        self.cr = _Cursor(dbname)

    def __getitem__(self, model_name):
        raise AssertionError("guard accessed ORM model %s before rejecting" % model_name)


@tagged("post_install", "-at_install", "sc_gate", "acceptance_fixture_gate")
class TestAcceptanceFixtureGuard(TransactionCase):
    def _assert_denied(self, dbname, environment, allow_demo_data, password, message):
        values = {
            "SC_ENVIRONMENT": environment,
            "SC_ALLOW_DEMO_DATA": allow_demo_data,
            "SC_ACCEPTANCE_FIXTURE_PASSWORD": password,
        }
        with patch.dict(os.environ, values, clear=False):
            with self.assertRaisesRegex(RuntimeError, message):
                _guard_acceptance_scope(_NoOrmEnvironment(dbname))

    def test_rejects_wrong_database_before_orm_access(self):
        self._assert_denied("production", "acceptance", "1", "secret", "requires database")

    def test_rejects_wrong_environment_before_orm_access(self):
        self._assert_denied(
            "sc_frontend_acceptance", "production", "1", "secret", "SC_ENVIRONMENT"
        )

    def test_rejects_missing_allow_flag_before_orm_access(self):
        self._assert_denied(
            "sc_frontend_acceptance", "acceptance", "0", "secret", "SC_ALLOW_DEMO_DATA"
        )

    def test_rejects_missing_secret_before_orm_access(self):
        self._assert_denied(
            "sc_frontend_acceptance", "acceptance", "1", "", "SC_ACCEPTANCE_FIXTURE_PASSWORD"
        )
