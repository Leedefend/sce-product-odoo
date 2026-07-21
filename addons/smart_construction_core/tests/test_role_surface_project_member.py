from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.smart_construction_core.core_extension_actor_roles import resolve_release_actor_role_codes
from odoo.addons.smart_construction_core.core_extension_policy_maps import (
    ROLE_GROUPS_CAPABILITY_FALLBACK,
    ROLE_GROUPS_EXPLICIT,
    ROLE_PRECEDENCE,
    ROLE_SURFACE_OVERRIDES,
)
from odoo.addons.smart_core.delivery.menu_service import MenuService
from odoo.addons.smart_core.identity.identity_resolver import IdentityResolver
from odoo.addons.smart_core.handlers.route_authority_validate import RouteAuthorityValidateHandler


@tagged("post_install", "-at_install", "user_data_boundary")
class TestProjectMemberRoleSurface(TransactionCase):
    def _resolver(self):
        resolver = IdentityResolver()
        resolver._role_groups_explicit = ROLE_GROUPS_EXPLICIT
        resolver._role_groups_capability_fallback = ROLE_GROUPS_CAPABILITY_FALLBACK
        resolver._role_precedence = ROLE_PRECEDENCE
        resolver._role_surface_map = {**resolver._role_surface_map, **ROLE_SURFACE_OVERRIDES}
        return resolver

    def test_role_matrix_uses_authoritative_groups(self):
        resolver = self._resolver()
        matrix = {
            "project_member": {"smart_construction_core.group_sc_cap_project_read"},
            "finance": {"smart_construction_core.group_sc_role_finance_manager"},
            "pm": {"smart_construction_core.group_sc_role_project_manager", "smart_construction_core.group_sc_cap_project_read"},
            "owner": {"smart_construction_core.group_sc_role_owner", "smart_construction_core.group_sc_cap_project_read"},
        }
        for expected, groups in matrix.items():
            with self.subTest(expected=expected):
                self.assertEqual(resolver.resolve_role_code(groups), expected)

        self.assertEqual(
            resolver.resolve_role_code({"smart_core.group_smart_core_admin"}),
            "system_admin",
        )

    def test_formal_role_surface_uses_authoritative_product_label_and_home(self):
        resolver = self._resolver()
        matrix = {
            "finance": ({"smart_construction_core.group_sc_role_finance_manager"}, "财务主管"),
            "project_member": ({"smart_construction_core.group_sc_cap_project_read"}, "项目成员"),
            "pm": ({"smart_construction_core.group_sc_role_project_manager"}, "项目经理"),
            "owner": ({"smart_construction_core.group_sc_role_owner"}, "企业负责人"),
        }
        for role, (groups, label) in matrix.items():
            with self.subTest(role=role):
                surface = resolver.build_role_surface(
                    groups,
                    [],
                    {"projects.list", "projects.ledger"},
                    ROLE_SURFACE_OVERRIDES,
                )
                self.assertEqual(surface["role_code"], role)
                self.assertEqual(surface["role_label"], label)
                self.assertEqual(surface["landing_scene_key"], "workspace.home")
                self.assertEqual(surface["landing_path"], "/s/workspace.home")
                self.assertTrue(surface["exposure_policy_declared"])
                self.assertTrue(surface["primary_menu_xmlids"] or surface["role_home_menu_xmlids"])

    def test_primary_navigation_policy_is_explicit_and_identifier_only(self):
        for role in ("finance", "project_member", "pm", "owner", "business_config_admin"):
            with self.subTest(role=role):
                policy = ROLE_SURFACE_OVERRIDES[role]
                exposed = set(policy.get("primary_menu_xmlids") or []) | set(policy.get("role_home_menu_xmlids") or [])
                exposed |= set(policy.get("admin_menu_xmlids") or [])
                denied = set(policy.get("denied_menu_xmlids") or [])
                self.assertFalse(exposed & denied)
                self.assertTrue(all(xmlid.startswith("smart_construction_core.menu_") for xmlid in exposed | denied))

    def test_primary_native_projection_rebuilds_ancestors_and_fails_closed(self):
        nodes = [{
            "xmlid": "x.root",
            "children": [
                {"xmlid": "x.primary", "meta": {"model": "x.record", "action_id": 1}},
                {"xmlid": "x.context", "meta": {"model": "x.record", "action_id": 2}},
                {"meta": {"model": "x.record", "action_id": 3}},
            ],
        }]
        surface = {
            "exposure_policy_declared": True,
            "primary_menu_xmlids": ["x.primary"],
            "role_home_menu_xmlids": [],
            "admin_menu_xmlids": [],
            "denied_menu_xmlids": [],
        }

        projected = MenuService._filter_primary_native_nodes(nodes, surface)

        self.assertEqual(projected[0]["xmlid"], "x.root")
        self.assertEqual([child["xmlid"] for child in projected[0]["children"]], ["x.primary"])
        self.assertEqual(MenuService._filter_primary_native_nodes(nodes, {}), [])
        self.assertEqual(
            MenuService._filter_primary_native_nodes(nodes, {"exposure_policy_declared": True}),
            [],
        )

    def test_contextual_route_authority_carries_stable_action_meta_without_primary_projection(self):
        surface = {
            **ROLE_SURFACE_OVERRIDES["finance"],
            "exposure_policy_declared": True,
        }

        routes = MenuService(self.env).build_contextual_routes(surface)
        target = next(
            row
            for row in routes
            if row["menu_xmlid"] == "smart_construction_core.menu_sc_settlement_adjustment"
        )

        self.assertGreater(target["menu_id"], 0)
        self.assertGreater(target["action_id"], 0)
        self.assertEqual(target["model"], "sc.settlement.adjustment")
        self.assertTrue(target["name"])
        self.assertTrue(target["view_modes"])
        self.assertEqual(
            target["route"],
            "/a/%s?menu_id=%s" % (target["action_id"], target["menu_id"]),
        )

    def test_route_authority_contract_separates_admin_and_contextual_action_only_entries(self):
        Users = self.env["res.users"].with_context(no_reset_password=True)
        base_group = self.env.ref("base.group_user")
        pm_group = self.env.ref("smart_construction_core.group_sc_role_project_manager")
        config_group = self.env.ref("smart_construction_core.group_sc_cap_business_config_admin")
        pm_user = Users.create({
            "name": "Route Authority PM",
            "login": "route.authority.pm",
            "groups_id": [(6, 0, [base_group.id, pm_group.id])],
        })
        config_user = Users.create({
            "name": "Route Authority Config Admin",
            "login": "route.authority.config",
            "groups_id": [(6, 0, [base_group.id, config_group.id])],
        })
        resolver = self._resolver()
        pm_surface = resolver.build_role_surface(
            {"smart_construction_core.group_sc_role_project_manager"},
            [],
            {"workspace.home"},
            ROLE_SURFACE_OVERRIDES,
        )
        config_surface = resolver.build_role_surface(
            {"smart_construction_core.group_sc_cap_business_config_admin"},
            [],
            {"workspace.home"},
            ROLE_SURFACE_OVERRIDES,
        )

        pm_contract = MenuService(self.env(user=pm_user)).build_route_authority(pm_surface)
        config_contract = MenuService(self.env(user=config_user)).build_route_authority(config_surface)

        self.assertEqual(pm_contract["contract_version"], "route_authority.v1")
        execution = next(
            row for row in pm_contract["contextual_actions"]
            if row["action_xmlid"] == "smart_construction_core.action_construction_contract_income_execution"
        )
        self.assertEqual(execution["route_kind"], "CONTEXTUAL_ROUTE")
        self.assertEqual(
            execution["context_requirements"]["required_query"],
            ["company_id", "project_id", "contract_id"],
        )
        self.assertFalse(pm_contract["admin_actions"])

        user_management = next(
            row for row in config_contract["admin_actions"]
            if row["action_xmlid"] == "smart_construction_core.action_sc_runtime_user_management"
        )
        self.assertEqual(user_management["route_kind"], "ADMIN_ROUTE")
        self.assertFalse(config_contract["primary_actions"])
        self.assertFalse(config_contract["role_home_actions"])

        admin_result = RouteAuthorityValidateHandler(self.env(user=config_user)).handle({
            "params": {"action_id": user_management["action_id"]},
        })
        denied_result = RouteAuthorityValidateHandler(self.env(user=pm_user)).handle({
            "params": {"action_id": user_management["action_id"]},
        })
        missing_context_result = RouteAuthorityValidateHandler(self.env(user=pm_user)).handle({
            "params": {"action_id": execution["action_id"]},
        })
        self.assertTrue(admin_result.ok)
        self.assertFalse(denied_result.ok)
        self.assertEqual(denied_result.code, 403)
        self.assertFalse(missing_context_result.ok)
        self.assertEqual(missing_context_result.code, 403)

    def test_shell_only_role_keeps_scoped_empty_route_authority(self):
        Users = self.env["res.users"].with_context(no_reset_password=True)
        base_group = self.env.ref("base.group_user")
        executive_group = self.env.ref("smart_construction_core.group_sc_role_executive")
        executive_user = Users.create({
            "name": "Route Authority Executive",
            "login": "route.authority.executive",
            "groups_id": [(6, 0, [base_group.id, executive_group.id])],
        })
        surface = self._resolver().build_role_surface(
            {"smart_construction_core.group_sc_role_executive"},
            [],
            {"workspace.home"},
            ROLE_SURFACE_OVERRIDES,
        )

        self.assertEqual(surface["role_code"], "executive")
        self.assertFalse(surface["exposure_policy_declared"])
        contract = MenuService(self.env(user=executive_user)).build_route_authority(surface)
        self.assertEqual(contract["principal_scope"], {
            "user_id": executive_user.id,
            "company_id": executive_user.company_id.id,
            "role_code": "executive",
        })
        for bucket in (
            "primary_actions",
            "role_home_actions",
            "contextual_actions",
            "admin_actions",
            "denied_actions",
            "menu_containers",
        ):
            self.assertFalse(contract[bucket], bucket)

    def test_delivery_projection_keeps_synthetic_ancestors_without_granting_them(self):
        nodes = [{
            "key": "group:synthetic",
            "children": [
                {"meta": {"menu_xmlid": "x.primary", "action_id": 1}},
                {"meta": {"menu_xmlid": "x.context", "action_id": 2}},
                {"meta": {"action_id": 3}},
            ],
        }]
        surface = {
            "exposure_policy_declared": True,
            "primary_menu_xmlids": ["x.primary"],
            "role_home_menu_xmlids": [],
            "admin_menu_xmlids": [],
            "denied_menu_xmlids": [],
        }

        projected = MenuService._filter_primary_delivery_nodes(nodes, surface)

        self.assertEqual(len(projected), 1)
        self.assertEqual(len(projected[0]["children"]), 1)
        self.assertEqual(projected[0]["children"][0]["meta"]["menu_xmlid"], "x.primary")

    def test_declared_primary_native_leaf_survives_unrelated_release_menu_surface(self):
        service = MenuService()
        surface = {
            "role_code": "finance",
            "exposure_policy_declared": True,
            "primary_menu_xmlids": ["x.primary"],
            "role_home_menu_xmlids": [],
            "admin_menu_xmlids": [],
            "denied_menu_xmlids": [],
        }
        native = [{
            "xmlid": "x.root",
            "label": "业务中心",
            "menu_id": 10,
            "children": [{
                "xmlid": "x.primary",
                "label": "正式办理",
                "menu_id": 11,
                "action_id": 21,
                "model": "x.record",
                "meta": {"menu_xmlid": "x.primary", "action_id": 21, "model": "x.record"},
            }],
        }]
        policy = {"menu_groups": [{
            "group_key": "unrelated",
            "group_label": "其他发布面",
            "menus": [{
                "menu_key": "unrelated",
                "label": "其他入口",
                "menu_id": 99,
                "action_id": 99,
                "menu_xmlid": "x.unrelated",
                "release_state": "released",
            }],
        }]}

        nav = service.build_nav(policy=policy, role_surface=surface, native_nav=native)

        self.assertEqual(
            [
                child.get("meta", {}).get("menu_xmlid")
                for group in nav[0].get("children") or []
                for child in group.get("children") or []
            ],
            ["x.primary"],
        )

    def test_release_actor_role_does_not_promote_project_reader_to_pm(self):
        class User:
            groups_id = type("Groups", (), {"get_external_id": lambda self: {1: "base.group_user"}})()

            def has_group(self, xmlid):
                return xmlid == "smart_construction_core.group_sc_cap_project_read"

        self.assertEqual(resolve_release_actor_role_codes(User()), ["project_member"])

    def test_release_and_delivery_navigation_use_identifier_policy(self):
        resolver = self._resolver()
        surface = resolver.build_role_surface(
            {"smart_construction_core.group_sc_cap_project_read"},
            [],
            {"projects.list"},
            ROLE_SURFACE_OVERRIDES,
        )
        nodes = [{
            "xmlid": "smart_construction_core.menu_sc_project_center",
            "children": [
                {"xmlid": "smart_construction_core.menu_sc_project_project", "meta": {"model": "project.project", "action_id": 1}},
                {"xmlid": "x.payment", "meta": {"model": "payment.request", "action_id": 2}},
                {"xmlid": "x.settlement", "meta": {"model": "sc.settlement.order", "action_id": 3}},
            ],
        }]
        release_nav = resolver.filter_nav_for_role_surface(nodes, surface)
        delivery_nav = MenuService._filter_role_surface_nodes(nodes, surface)
        for nav in (release_nav, delivery_nav):
            models = [child.get("meta", {}).get("model") for child in nav[0]["children"]]
            self.assertEqual(models, ["project.project"])

    def test_finance_navigation_is_not_affected_by_project_member_policy(self):
        nodes = [{"meta": {"model": "payment.request", "action_id": 2}, "children": []}]
        self.assertEqual(MenuService._filter_role_surface_nodes(nodes, {"role_code": "finance"}), nodes)

    def test_restricted_role_has_no_release_or_delivery_navigation(self):
        resolver = self._resolver()
        surface = resolver.build_role_surface(set(), [], {"workspace.home"}, ROLE_SURFACE_OVERRIDES)
        nodes = [{"xmlid": "x.sensitive", "meta": {"model": "payment.request"}, "children": []}]

        self.assertEqual(surface["role_code"], "restricted")
        self.assertTrue(surface["deny_all_navigation"])
        self.assertEqual(resolver.filter_nav_for_role_surface(nodes, surface), [])
        self.assertEqual(MenuService._filter_role_surface_nodes(nodes, surface), [])

    def test_known_unreachable_actions_are_removed_by_stable_identifiers(self):
        resolver = self._resolver()
        nodes = [{
            "xmlid": "smart_construction_core.menu_sc_project_center",
            "children": [
                {
                    "xmlid": "smart_construction_core.menu_sc_plan",
                    "meta": {"action_xmlid": "smart_construction_core.action_sc_plan", "model": "sc.plan", "action_id": 1},
                },
                {
                    "xmlid": "smart_construction_core.menu_sc_plan_report",
                    "meta": {"action_xmlid": "smart_construction_core.action_sc_plan_report", "model": "sc.plan.report", "action_id": 2},
                },
                {
                    "xmlid": "smart_construction_core.menu_sc_tender_registration",
                    "meta": {"action_xmlid": "smart_construction_core.action_sc_tender_registration", "model": "tender.bid", "action_id": 3},
                },
                {
                    "xmlid": "smart_construction_core.menu_payment_request",
                    "meta": {"action_xmlid": "smart_construction_core.action_payment_request", "model": "payment.request", "action_id": 4},
                },
            ],
        }]
        forbidden_actions = {
            "finance": {
                "smart_construction_core.action_sc_plan",
                "smart_construction_core.action_sc_plan_report",
            },
            "project_member": {"smart_construction_core.action_sc_tender_registration"},
            "owner": {"smart_construction_core.action_sc_tender_registration"},
            "pm": set(),
        }
        role_groups = {
            "finance": {"smart_construction_core.group_sc_role_finance_manager"},
            "project_member": {"smart_construction_core.group_sc_cap_project_read"},
            "owner": {"smart_construction_core.group_sc_role_owner"},
            "pm": {"smart_construction_core.group_sc_role_project_manager"},
        }
        for role, groups in role_groups.items():
            with self.subTest(role=role):
                surface = resolver.build_role_surface(groups, [], {"projects.list"}, ROLE_SURFACE_OVERRIDES)
                for nav in (
                    resolver.filter_nav_for_role_surface(nodes, surface),
                    MenuService._filter_role_surface_nodes(nodes, surface),
                ):
                    actual = {child["meta"]["action_xmlid"] for child in nav[0]["children"]}
                    self.assertFalse(actual & forbidden_actions[role])
                    if role == "finance":
                        self.assertIn("smart_construction_core.action_payment_request", actual)
                    if role == "pm":
                        self.assertIn("smart_construction_core.action_sc_plan", actual)
                        self.assertIn("smart_construction_core.action_sc_plan_report", actual)
                        self.assertIn("smart_construction_core.action_sc_tender_registration", actual)
