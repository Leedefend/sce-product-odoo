import os


password = str(os.getenv("NAV_PRO_PASSWORD") or "").strip()
if not password:
    raise RuntimeError("NAV_PRO_PASSWORD is required")

roles = {
    "finance": ["smart_construction_core.group_sc_role_finance_manager"],
    "project_member": [
        "smart_construction_core.group_sc_cap_project_read",
        "smart_construction_core.group_sc_cap_business_initiator",
    ],
    "pm": ["smart_construction_core.group_sc_role_project_manager"],
    "owner": ["smart_construction_core.group_sc_role_owner"],
    "config_admin": ["smart_construction_core.group_sc_cap_business_config_admin"],
    "system_admin": ["smart_core.group_smart_core_admin"],
}
users = env["res.users"].sudo().with_context(no_reset_password=True)
internal = env.ref("base.group_user")
users_by_role = {}
for role, group_xmlids in roles.items():
    login = f"nav_pro_{role}"
    groups = [env.ref(group_xmlid) for group_xmlid in group_xmlids]
    user = users.search([("login", "=", login)], limit=1)
    values = {
        "name": f"NAV-PRO-01 {role}",
        "login": login,
        "password": password,
        "company_id": env.company.id,
        "company_ids": [(6, 0, [env.company.id])],
        "groups_id": [(6, 0, [internal.id, *[group.id for group in groups]])],
        "active": True,
        "sc_runtime_user_managed": role in {"finance", "project_member", "pm", "owner"},
    }
    if user:
        user.write(values)
    else:
        user = users.create(values)
    users_by_role[role] = user

project = env["project.project"].sudo().search([("name", "=", "NAV-PRO-01R Context Project")], limit=1)
if not project:
    project = env["project.project"].sudo().create({
        "name": "NAV-PRO-01R Context Project",
        "company_id": env.company.id,
        "user_id": users_by_role["pm"].id,
    })
partner = env["res.partner"].sudo().search([("name", "=", "NAV-PRO-01R Context Partner")], limit=1)
if not partner:
    partner = env["res.partner"].sudo().create({"name": "NAV-PRO-01R Context Partner"})
contract = env["construction.contract"].sudo().search([
    ("subject", "=", "NAV-PRO-01R Context Contract"),
    ("project_id", "=", project.id),
], limit=1)
if not contract:
    env["construction.contract"].sudo().create({
        "subject": "NAV-PRO-01R Context Contract",
        "type": "out",
        "project_id": project.id,
        "partner_id": partner.id,
    })

action_xmlids = (
    "smart_construction_core.action_construction_contract_income_construction",
    "smart_construction_core.action_construction_contract_income_execution",
)
for xmlid in action_xmlids:
    action = env.ref(xmlid)
    fields = set(env[action.res_model]._fields)
    if "legacy_contract_id" in fields or "legacy_visible_title" in fields:
        raise RuntimeError(f"legacy field unexpectedly present on {action.res_model}")
retired_menu = env.ref("smart_construction_core.menu_sc_project_income_contract_acceptance_construction")
if retired_menu.active:
    raise RuntimeError("retired legacy construction-contract menu remains active")
env.cr.commit()
print("NAV_PRO_01_RUNTIME_PREPARE=PASS")
