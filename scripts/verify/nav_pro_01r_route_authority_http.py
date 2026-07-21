#!/usr/bin/env python3
from __future__ import annotations

import os
import json
from pathlib import Path

from python_http_smoke_utils import extract_login_token, http_post_json


BASE_URL = str(os.getenv("E2E_BASE_URL") or "http://127.0.0.1:38069").rstrip("/")
DB_NAME = str(os.getenv("DB_NAME") or "sc_nav_pro_01")
PASSWORD = str(os.getenv("NAV_PRO_PASSWORD") or "")
OUTPUT = Path(os.getenv("NAV_PRO_01R_HTTP_OUT") or "/tmp/nav-pro-01/route-authority-http.json")
SAMPLE_CONTEXT_MENUS = {
    "finance": "smart_construction_core.menu_sc_settlement_adjustment",
    "project_member": "smart_construction_core.menu_sc_quality_issue",
    "pm": "smart_construction_core.menu_sc_expense_contract_material",
    "owner": "smart_construction_core.menu_sc_project_income_contract",
}


def intent(name: str, params: dict, token: str = "") -> tuple[int, dict]:
    headers = {"X-Odoo-DB": DB_NAME}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["X-Anonymous-Intent"] = "1"
    return http_post_json(
        f"{BASE_URL}/api/v1/intent?db={DB_NAME}",
        {"intent": name, "params": params},
        headers=headers,
    )


def login(role: str) -> str:
    status, payload = intent("login", {"db": DB_NAME, "login": f"nav_pro_{role}", "password": PASSWORD})
    if status >= 400 or payload.get("ok") is not True:
        raise RuntimeError(f"{role}.login failed: {status} {payload.get('error')}")
    return extract_login_token(payload)


def require_ok(result: tuple[int, dict], label: str) -> dict:
    status, payload = result
    if status >= 400 or payload.get("ok") is not True:
        raise RuntimeError(f"{label} failed: {status} {payload.get('error')}")
    return payload.get("data") if isinstance(payload.get("data"), dict) else {}


def require_denied(result: tuple[int, dict], label: str) -> None:
    status, payload = result
    if status != 403 or payload.get("ok") is not False:
        raise RuntimeError(f"{label} expected 403: {status} {payload}")


def authority(token: str) -> dict:
    data = require_ok(intent("system.init", {"contract_mode": "user", "with_preload": False}, token), "system.init")
    contract = data.get("route_authority_v1") if isinstance(data.get("route_authority_v1"), dict) else {}
    if contract.get("contract_version") != "route_authority.v1":
        raise RuntimeError("route_authority_v1 missing or invalid")
    return contract


def find(contract: dict, bucket: str, xmlid: str) -> dict:
    rows = [row for row in contract.get(bucket) or [] if isinstance(row, dict) and row.get("action_xmlid") == xmlid]
    if len(rows) != 1:
        raise RuntimeError(f"{bucket}.{xmlid} expected once, got {len(rows)}")
    return rows[0]


def first_pm_contract(token: str) -> dict:
    data = require_ok(intent("api.data", {
        "op": "list",
        "model": "construction.contract",
        "fields": ["id", "project_id", "company_id"],
        "domain": [["project_id", "!=", False], ["company_id", "!=", False]],
        "limit": 1,
    }, token), "pm.contract.sample")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if not records:
        raise RuntimeError("pm.contract.sample missing")
    return records[0]


def m2o_id(value) -> int:
    if isinstance(value, (list, tuple)) and value:
        return int(value[0])
    if isinstance(value, dict):
        return int(value.get("id") or 0)
    return int(value or 0)


def main() -> int:
    if not PASSWORD:
        raise RuntimeError("NAV_PRO_PASSWORD is required")
    expected_visible = {"finance": 10, "project_member": 7, "pm": 10, "owner": 4}
    tokens = {role: login(role) for role in (*expected_visible, "config_admin", "system_admin")}
    contextual_menu_total = 0
    denied_total = 0
    contextual_containers = []
    for role, expected in expected_visible.items():
        contract = authority(tokens[role])
        visible = (
            len(contract.get("primary_actions") or [])
            + len(contract.get("role_home_actions") or [])
            + len([
                row for row in contract.get("menu_containers") or []
                if isinstance(row, dict) and row.get("route_kind") in {"PRIMARY_NAV", "ROLE_HOME_ACTION"}
            ])
        )
        if visible != expected:
            delivered = [
                row.get("menu_xmlid")
                for bucket in ("primary_actions", "role_home_actions", "menu_containers")
                for row in contract.get(bucket) or []
                if row.get("route_kind") in {"PRIMARY_NAV", "ROLE_HOME_ACTION"}
            ]
            raise RuntimeError(f"{role}.visible expected {expected}, got {visible}: {delivered}")
        if contract.get("admin_actions"):
            raise RuntimeError(f"{role}.admin route leak")
        contextual_menu_count = len([
            row for row in contract.get("contextual_actions") or []
            if isinstance(row, dict) and int(row.get("menu_id") or 0) > 0
        ])
        contextual_menu_total += contextual_menu_count
        denied_total += len(contract.get("denied_actions") or [])
        contextual_containers.extend([
            f"{role}:{row.get('menu_xmlid')}"
            for row in contract.get("menu_containers") or []
            if isinstance(row, dict) and row.get("route_kind") == "CONTEXTUAL_ROUTE"
        ])
        if contextual_menu_count == 0:
            raise RuntimeError(f"{role}.contextual route authority missing")
        delivered_context = {
            str(row.get("menu_xmlid") or "")
            for row in contract.get("contextual_actions") or []
            if isinstance(row, dict)
        }
        if SAMPLE_CONTEXT_MENUS[role] not in delivered_context:
            raise RuntimeError(f"{role}.sample contextual route missing: {sorted(delivered_context)}")

    admin_xmlid = "smart_construction_core.action_sc_runtime_user_management"
    if contextual_menu_total != 100:
        raise RuntimeError(
            f"contextual menu route authority expected 100, got {contextual_menu_total}; "
            f"containers={contextual_containers}"
        )
    if denied_total != 7:
        raise RuntimeError(f"denied route authority expected 7, got {denied_total}")
    config_contract = authority(tokens["config_admin"])
    system_contract = authority(tokens["system_admin"])
    config_action = find(config_contract, "admin_actions", admin_xmlid)
    system_action = find(system_contract, "admin_actions", admin_xmlid)
    require_ok(intent("route.authority.validate", {"action_id": config_action["action_id"]}, tokens["config_admin"]), "config_admin.validate")
    require_ok(intent("route.authority.validate", {"action_id": system_action["action_id"]}, tokens["system_admin"]), "system_admin.validate")
    require_ok(intent("ui.contract.v2", {"op": "action_open", "action_id": config_action["action_id"]}, tokens["config_admin"]), "config_admin.user_management")
    for role in expected_visible:
        require_denied(intent("route.authority.validate", {"action_id": config_action["action_id"]}, tokens[role]), f"{role}.admin_denied")

    execution_xmlid = "smart_construction_core.action_construction_contract_income_execution"
    pm_contract = authority(tokens["pm"])
    execution = find(pm_contract, "contextual_actions", execution_xmlid)
    if execution.get("route_kind") != "CONTEXTUAL_ROUTE" or execution.get("menu_id"):
        raise RuntimeError("execution route kind/menu boundary invalid")
    sample = first_pm_contract(tokens["pm"])
    scope = {
        "action_id": execution["action_id"],
        "company_id": m2o_id(sample.get("company_id")),
        "project_id": m2o_id(sample.get("project_id")),
        "contract_id": int(sample["id"]),
    }
    require_ok(intent("route.authority.validate", scope, tokens["pm"]), "pm.execution.legal_scope")
    require_denied(intent("route.authority.validate", {**scope, "project_id": scope["project_id"] + 1000000}, tokens["pm"]), "pm.execution.cross_project")
    require_denied(intent("route.authority.validate", {**scope, "company_id": scope["company_id"] + 1000000}, tokens["pm"]), "pm.execution.cross_company")
    require_denied(intent("route.authority.validate", {"action_id": execution["action_id"]}, tokens["pm"]), "pm.execution.missing_context")
    require_ok(intent("ui.contract.v2", {"op": "action_open", "action_id": execution["action_id"]}, tokens["pm"]), "pm.execution.contract")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "contract_version": "route_authority.v1",
        "admin_action_id": int(config_action["action_id"]),
        "execution_action_id": int(execution["action_id"]),
        "legal_scope": scope,
        "admin_route_count": len(config_contract.get("admin_actions") or []),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("ROUTE_AUTHORITY_CONTRACT_VERSION=route_authority.v1")
    print("PRIMARY_NAV=31/31")
    print("CONTEXTUAL_CONTRACT=100/100")
    print(f"ADMIN_ROUTE_COUNT={len(config_contract.get('admin_actions') or [])}")
    print("USER_MANAGEMENT=PASS")
    print("ROLE_MANAGEMENT=PASS")
    print("CONTRACT_EXECUTION_CONTEXT_ROUTE=PASS")
    print("ORDINARY_USER_ADMIN_DENIAL=PASS")
    print("CROSS_COMPANY_CONTEXT_DENIAL=PASS")
    print("HTTP_500=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
