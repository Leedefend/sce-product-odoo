#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
from pathlib import Path

from python_http_smoke_utils import extract_login_token, http_post_json


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = str(os.getenv("E2E_BASE_URL") or "http://127.0.0.1:28069").rstrip("/")
DB_NAME = str(os.getenv("DB_NAME") or "sc_nav_pro_01")
PASSWORD = str(os.getenv("NAV_PRO_PASSWORD") or "")
ROLE_KEYS = ("finance", "project_member", "pm", "owner")
CONTEXT_ACTIONS = {
    "finance": ("结算调整", "sc.settlement.adjustment"),
    "project_member": ("质量问题闭环", "sc.quality.issue"),
    "pm": ("材料合同", "construction.contract.expense"),
    "owner": ("收入合同", "construction.contract.income"),
}
CONTEXT_XMLIDS = {
    "finance": "smart_construction_core.menu_sc_settlement_adjustment",
    "project_member": "smart_construction_core.menu_sc_quality_issue",
    "pm": "smart_construction_core.menu_sc_expense_contract_material",
    "owner": "smart_construction_core.menu_sc_project_income_contract",
}
BROKEN_ACTIONS = {
    "施工合同": "construction.contract.income",
    "收入合同执行": "construction.contract.income",
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


def flatten_xmlids(nodes) -> set[str]:
    found = set()
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        children = node.get("children") if isinstance(node.get("children"), list) else []
        if children:
            found.update(flatten_xmlids(children))
            continue
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        xmlid = str(node.get("menu_xmlid") or node.get("xmlid") or meta.get("menu_xmlid") or "").strip()
        if xmlid:
            found.add(xmlid)
    return found


def all_xmlids(nodes) -> set[str]:
    found = set()
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        xmlid = str(node.get("menu_xmlid") or node.get("xmlid") or meta.get("menu_xmlid") or "").strip()
        if xmlid:
            found.add(xmlid)
        found.update(all_xmlids(node.get("children") if isinstance(node.get("children"), list) else []))
    return found


def node_count(nodes) -> int:
    return sum(
        1 + node_count(node.get("children") if isinstance(node.get("children"), list) else [])
        for node in nodes or []
        if isinstance(node, dict)
    )


def require_ok(status: int, payload: dict, label: str) -> dict:
    if status >= 400 or payload.get("ok") is not True:
        raise RuntimeError(f"{label} failed: status={status} error={payload.get('error')!r}")
    return payload.get("data") if isinstance(payload.get("data"), dict) else {}


def find_action(token: str, name: str, model: str) -> dict:
    status, payload = intent(
        "api.data",
        {
            "op": "list",
            "model": "ir.actions.act_window",
            "fields": ["id", "name", "res_model", "domain"],
            "domain": [["name", "=", name], ["res_model", "=", model]],
            "limit": 2,
        },
        token,
    )
    data = require_ok(status, payload, f"action_lookup.{name}")
    rows = [row for row in data.get("records") or [] if isinstance(row, dict)]
    if len(rows) != 1:
        raise RuntimeError(f"action lookup is not unique: {name}/{model} count={len(rows)}")
    return rows[0]


def role_policy() -> dict:
    tree = ast.parse(
        (ROOT / "addons/smart_construction_core/core_extension_policy_maps.py").read_text(encoding="utf-8")
    )
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "ROLE_SURFACE_OVERRIDES" for target in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("ROLE_SURFACE_OVERRIDES not found")


def main() -> int:
    if not PASSWORD:
        raise RuntimeError("NAV_PRO_PASSWORD is required")
    report = {"database": DB_NAME, "roles": {}, "direct_actions": {}}
    policies = role_policy()
    all_release = set()
    all_delivery = set()
    for role in ROLE_KEYS:
        status, payload = intent("login", {"db": DB_NAME, "login": f"nav_pro_{role}", "password": PASSWORD})
        require_ok(status, payload, f"{role}.login")
        token = extract_login_token(payload)
        status, payload = intent("system.init", {"contract_mode": "user", "with_preload": False}, token)
        data = require_ok(status, payload, f"{role}.system.init")
        release = flatten_xmlids(((data.get("release_navigation_v1") or {}).get("nav") or []))
        delivery_role = data.get("delivery_engine_v1") if isinstance(data.get("delivery_engine_v1"), dict) else {}
        delivery = flatten_xmlids((delivery_role.get("nav") or []))
        if release != delivery:
            raise RuntimeError(f"{role}: release/delivery leaf mismatch: {sorted(release ^ delivery)}")
        expected = set(policies[role].get("primary_menu_xmlids") or []) | set(policies[role].get("role_home_menu_xmlids") or [])
        if delivery != expected:
            role_surface = data.get("role_surface") if isinstance(data.get("role_surface"), dict) else {}
            role_nav_xmlids = all_xmlids(data.get("nav_role_surface") or [])
            raise RuntimeError(
                f"{role}: delivery/policy leaf mismatch: {sorted(delivery ^ expected)}; "
                f"role_surface_keys={sorted(role_surface)}; "
                f"declared={role_surface.get('exposure_policy_declared')!r}; "
                f"surface_primary_count={len(role_surface.get('primary_menu_xmlids') or [])}; "
                f"delivery_role={delivery_role.get('role_code')!r}; "
                f"role_nav_xmlid_count={len(role_nav_xmlids)}; "
                f"expected_in_role_nav={len(expected & role_nav_xmlids)}; "
                f"role_nav_node_count={node_count(data.get('nav_role_surface') or [])}; "
                f"nav_source={(data.get('nav_meta') or {}).get('nav_source')!r}"
            )
        if CONTEXT_XMLIDS[role] in delivery:
            raise RuntimeError(f"{role}: contextual route leaked into primary navigation")
        expected_context = set(policies[role].get("contextual_menu_xmlids") or [])
        delivered_context = {
            str(row.get("menu_xmlid") or "").strip()
            for row in delivery_role.get("contextual_routes") or []
            if isinstance(row, dict) and str(row.get("menu_xmlid") or "").strip()
        }
        if delivered_context != expected_context:
            raise RuntimeError(f"{role}: contextual route authority differs from policy: {sorted(delivered_context ^ expected_context)}")
        if delivery & delivered_context:
            raise RuntimeError(f"{role}: primary/contextual route authority overlap")
        all_release.update(release)
        all_delivery.update(delivery)
        context_name, context_model = CONTEXT_ACTIONS[role]
        context = find_action(token, context_name, context_model)
        status, payload = intent(
            "ui.contract.v2",
            {"op": "action_open", "action_id": context["id"], "client_type": "web_pc", "delivery_profile": "full"},
            token,
        )
        require_ok(status, payload, f"{role}.context.ui_contract")
        report["roles"][role] = {"release_leaf_count": len(release), "delivery_leaf_count": len(delivery), "contextual_route_count": len(delivered_context), "context_route": "PASS"}
        print(f"{role.upper()}_PRIMARY_RUNTIME={len(delivery)}")

    status, login_payload = intent("login", {"db": DB_NAME, "login": "nav_pro_pm", "password": PASSWORD})
    token = extract_login_token(login_payload)
    for action_name, model in BROKEN_ACTIONS.items():
        action = find_action(token, action_name, model)
        domain = ast.literal_eval(action.get("domain") or "[]")
        status, payload = intent(
            "ui.contract.v2",
            {"op": "action_open", "action_id": action["id"], "client_type": "web_pc", "delivery_profile": "full"},
            token,
        )
        require_ok(status, payload, f"{action_name}.ui_contract")
        status, payload = intent(
            "api.data",
            {"op": "list", "model": model, "fields": ["id", "name", "subject"], "domain": domain, "limit": 1},
            token,
        )
        require_ok(status, payload, f"{action_name}.api_data")
        report["direct_actions"][action_name] = "PASS"

    report["release_delivery_leaf_diff"] = len(all_release ^ all_delivery)
    print("NAV_PRO_01_HTTP_SMOKE=PASS")
    print(f"RELEASE_DELIVERY_LEAF_DIFF={report['release_delivery_leaf_diff']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
