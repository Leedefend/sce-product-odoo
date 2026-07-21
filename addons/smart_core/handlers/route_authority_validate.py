# -*- coding: utf-8 -*-
from __future__ import annotations

from ..core.base_handler import BaseIntentHandler
from ..core.intent_execution_result import IntentExecutionResult
from ..delivery.menu_service import MenuService
from ..identity.identity_resolver import IdentityResolver


def _positive_int(value) -> int:
    try:
        parsed = int(value or 0)
    except Exception:
        return 0
    return parsed if parsed > 0 else 0


class RouteAuthorityValidateHandler(BaseIntentHandler):
    INTENT_TYPE = "route.authority.validate"
    DESCRIPTION = "Validate a delivered route authority against current session and record scope"
    VERSION = "1.0.0"
    SOURCE_KIND = "route_authority_runtime_validation"
    SOURCE_AUTHORITIES = ("route_authority_v1", "ir.model.access", "ir.rule", "allowed_company_ids")
    REQUIRED_GROUPS = []

    def _params(self, payload) -> dict:
        params = {}
        if isinstance(payload, dict):
            inner = payload.get("params")
            params.update(inner if isinstance(inner, dict) else payload)
        if isinstance(getattr(self, "params", None), dict):
            params.update(self.params)
        return params

    def _deny(self, reason: str) -> IntentExecutionResult:
        return IntentExecutionResult(
            ok=False,
            error={"code": 403, "message": "route authority denied", "reason_code": reason},
            meta={"intent": self.INTENT_TYPE, "version": self.VERSION},
            code=403,
        )

    def handle(self, payload=None, ctx=None):
        params = self._params(payload)
        action_id = _positive_int(params.get("action_id"))
        if not action_id:
            return self._deny("ROUTE_ACTION_REQUIRED")

        resolver = IdentityResolver(self.env)
        surface = resolver.build_role_surface(
            resolver.user_group_xmlids(self.env.user),
            [],
            {"workspace.home"},
        )
        authority = MenuService(self.env).build_route_authority(surface)
        entries = [
            row
            for bucket in ("primary_actions", "role_home_actions", "contextual_actions", "admin_actions")
            for row in authority.get(bucket) or []
            if isinstance(row, dict) and _positive_int(row.get("action_id")) == action_id
        ]
        if len(entries) != 1:
            return self._deny("ROUTE_ACTION_NOT_AUTHORIZED")
        entry = entries[0]
        requirements = entry.get("context_requirements") if isinstance(entry.get("context_requirements"), dict) else {}
        for key in requirements.get("required_query") or []:
            if not _positive_int(params.get(str(key))):
                return self._deny("ROUTE_CONTEXT_REQUIRED")

        company_key = str(requirements.get("company_query") or "").strip()
        project_key = str(requirements.get("project_query") or "").strip()
        record_key = str(requirements.get("record_query") or "").strip()
        company_id = _positive_int(params.get(company_key)) if company_key else 0
        project_id = _positive_int(params.get(project_key)) if project_key else 0
        record_id = _positive_int(params.get(record_key)) if record_key else 0
        if company_id and company_id not in self.env.companies.ids:
            return self._deny("ROUTE_COMPANY_SCOPE_DENIED")

        record_model = str(requirements.get("record_model") or "").strip()
        if record_model and record_id:
            if record_model not in self.env:
                return self._deny("ROUTE_CONTEXT_MODEL_MISSING")
            record = self.env[record_model].browse(record_id).exists()
            if not record:
                return self._deny("ROUTE_CONTEXT_RECORD_DENIED")
            try:
                record.check_access_rule("read")
            except Exception:
                return self._deny("ROUTE_CONTEXT_RECORD_DENIED")
            project_field = str(requirements.get("record_project_field") or "").strip()
            company_field = str(requirements.get("record_company_field") or "").strip()
            if project_field and project_id and _positive_int(getattr(record, project_field, None).id) != project_id:
                return self._deny("ROUTE_PROJECT_SCOPE_DENIED")
            if company_field and company_id and _positive_int(getattr(record, company_field, None).id) != company_id:
                return self._deny("ROUTE_COMPANY_SCOPE_DENIED")

        return IntentExecutionResult(
            ok=True,
            status="success",
            data={
                "allowed": True,
                "action_xmlid": str(entry.get("action_xmlid") or ""),
                "route_kind": str(entry.get("route_kind") or ""),
            },
            meta={"intent": self.INTENT_TYPE, "version": self.VERSION, "source_kind": self.SOURCE_KIND},
        )
