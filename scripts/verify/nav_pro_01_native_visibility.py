import json
import os
from pathlib import Path

from odoo.addons.smart_construction_core.core_extension_policy_maps import ROLE_SURFACE_OVERRIDES
from odoo.addons.smart_core.delivery.menu_fact_service import MenuFactService
from odoo.addons.smart_core.delivery.menu_service import MenuService

CONTEXT_XMLIDS = {
    "finance": "smart_construction_core.menu_sc_settlement_adjustment",
    "project_member": "smart_construction_core.menu_sc_quality_issue",
    "pm": "smart_construction_core.menu_sc_expense_contract_material",
    "owner": "smart_construction_core.menu_sc_project_income_contract",
}
context_routes = {}


for role in ("finance", "project_member", "pm", "owner"):
    user = env["res.users"].sudo().search([("login", "=", f"nav_pro_{role}")], limit=1)
    if not user:
        raise RuntimeError(f"missing NAV-PRO runtime user: {role}")
    user_env = env(user=user.id)
    facts = MenuFactService(user_env).export_visible_menu_facts()
    visible_ids = {row["menu_id"] for row in facts.flat}
    policy = ROLE_SURFACE_OVERRIDES[role]
    expected = set(policy.get("primary_menu_xmlids") or []) | set(policy.get("role_home_menu_xmlids") or [])
    missing = []
    for xmlid in sorted(expected):
        menu = env.ref(xmlid, raise_if_not_found=False)
        if not menu or menu._name != "ir.ui.menu" or menu.id not in visible_ids:
            missing.append(xmlid)
    print(f"{role.upper()}_DECLARED={len(expected)}")
    print(f"{role.upper()}_NATIVE_VISIBLE={len(expected) - len(missing)}")
    if missing:
        raise RuntimeError(f"{role}: declared primary menu is not native-visible: {missing}")
    surface = {**policy, "exposure_policy_declared": True}
    native = MenuService._menu_fact_tree_as_native(facts.tree)
    projected = MenuService._filter_primary_native_nodes(native, surface)
    projected_xmlids = set()
    stack = list(projected)
    while stack:
        node = stack.pop()
        projected_xmlids.add(MenuService._node_menu_xmlid(node))
        stack.extend(node.get("children") or [])
    projection_missing = sorted(expected - projected_xmlids)
    if projection_missing:
        raise RuntimeError(f"{role}: native ancestor-chain projection rejected: {projection_missing}")
    contextual = set(policy.get("contextual_menu_xmlids") or [])
    contextual_missing = []
    for xmlid in sorted(contextual):
        menu = env.ref(xmlid, raise_if_not_found=False)
        if not menu or menu._name != "ir.ui.menu" or menu.id not in visible_ids or not menu.action:
            contextual_missing.append(xmlid)
    if contextual_missing:
        raise RuntimeError(f"{role}: contextual route is not native-visible/actionable: {contextual_missing}")
    context_menu = env.ref(CONTEXT_XMLIDS[role], raise_if_not_found=False)
    if not context_menu or context_menu._name != "ir.ui.menu" or context_menu.id not in visible_ids:
        raise RuntimeError(f"{role}: contextual menu is not native-visible: {CONTEXT_XMLIDS[role]}")
    if not context_menu.action:
        raise RuntimeError(f"{role}: contextual menu has no action: {CONTEXT_XMLIDS[role]}")
    context_routes[role] = f"/a/{context_menu.action.id}?menu_id={context_menu.id}"

output = Path(os.getenv("NAV_PRO_CONTEXT_ROUTES_OUT") or "/tmp/nav-pro-01/context-routes.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(context_routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("NAV_PRO_01_NATIVE_VISIBILITY=PASS")
