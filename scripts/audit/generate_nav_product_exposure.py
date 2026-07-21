#!/usr/bin/env python3
"""Derive NAV-PRO-01 exposure decisions from the accepted authorization audit."""

from __future__ import annotations

import argparse
import ast
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "addons/smart_construction_core/core_extension_policy_maps.py"

TASK_EVIDENCE = {
    "finance": {
        "smart_construction_core.menu_sc_receipt_income": ("finance.receipt", "J05,E2E-07", "财务办理"),
        "smart_construction_core.menu_sc_settlement_order": ("finance.settlement", "J04,J05,E2E-08", "财务办理"),
        "smart_construction_core.menu_sc_user_payment_apply_acceptance": ("finance.payment_request", "J05,J06,J08,E2E-06", "财务办理"),
        "smart_construction_core.menu_sc_payment_execution": ("finance.payment_execution", "J05,J08,E2E-07", "财务办理"),
        "smart_construction_core.menu_sc_invoice_registration": ("finance.invoice_ledger", "J05,E2E-07", "财务查询"),
        "smart_construction_core.menu_sc_finance_project_capital_position": ("finance.project_funds", "J05,E2E-09", "财务分析"),
        "smart_construction_core.menu_sc_finance_counterparty_position_summary": ("finance.counterparty_funds", "J05,E2E-09", "财务分析"),
        "smart_construction_core.menu_sc_funding_plan_summary": ("finance.funding_plan", "J05,E2E-09", "财务分析"),
        "smart_construction_core.menu_sc_treasury_reconciliation": ("finance.reconciliation", "J05,E2E-07", "财务办理"),
        "smart_construction_core.menu_sc_fund_daily_user_report": ("finance.daily_report", "J05,E2E-09", "财务分析"),
    },
    "project_member": {
        "smart_construction_core.menu_sc_project_project": ("member.my_projects", "J03,E2E-01,E2E-10", "项目工作"),
        "smart_construction_core.menu_sc_project_management_scene": ("member.project_workspace", "J03,E2E-01", "项目工作"),
        "smart_construction_core.menu_sc_project_documents": ("member.project_documents", "J04,E2E-05", "项目工作"),
        "smart_construction_core.menu_sc_contract_center": ("member.contract_read", "J04,E2E-04", "项目工作"),
        "smart_construction_core.menu_sc_plan": ("member.plan", "J04,E2E-03", "现场工作"),
        "smart_construction_core.menu_sc_plan_report": ("member.plan_report", "J04,E2E-03", "现场工作"),
        "smart_construction_core.menu_sc_construction_diary": ("member.site_diary", "J04,E2E-05", "现场工作"),
    },
    "pm": {
        "smart_construction_core.menu_sc_project_initiation": ("pm.project_intake", "J04,E2E-01", "项目工作台"),
        "smart_construction_core.menu_sc_project_quick_create": ("pm.quick_create", "ROLE_HOME,E2E-01", "角色首页"),
        "smart_construction_core.menu_sc_project_project": ("pm.project_ledger", "J04,E2E-01", "项目工作台"),
        "smart_construction_core.menu_sc_project_management_scene": ("pm.project_workspace", "J04,E2E-01", "项目工作台"),
        "smart_construction_core.menu_sc_project_documents": ("pm.project_documents", "J04,E2E-05", "项目工作台"),
        "smart_construction_core.menu_sc_project_work_breakdown": ("pm.work_breakdown", "J04,E2E-02,E2E-03", "项目工作台"),
        "smart_construction_core.menu_sc_contract_center": ("pm.contract_center", "J04,E2E-04", "合同与结算"),
        "smart_construction_core.menu_sc_expense_contract_settlement": ("pm.expense_settlement", "J04,E2E-08", "合同与结算"),
        "smart_construction_core.menu_sc_income_contract_settlement": ("pm.income_settlement", "J04,E2E-08", "合同与结算"),
        "smart_construction_core.menu_sc_contract_event": ("pm.contract_event", "J04,E2E-05", "合同与结算"),
    },
    "owner": {
        "smart_construction_core.menu_sc_project_project": ("owner.project_overview", "J03,E2E-09", "经营总览"),
        "smart_construction_core.menu_sc_project_kanban": ("owner.project_portfolio", "J03,E2E-09", "经营总览"),
        "smart_construction_core.menu_sc_project_management_scene": ("owner.enterprise_dashboard", "J03,E2E-09", "经营总览"),
        "smart_construction_core.menu_sc_contract_center": ("owner.contract_overview", "J03,J04,E2E-09", "经营总览"),
    },
}


def load_role_policy() -> dict:
    tree = ast.parse(POLICY_PATH.read_text(encoding="utf-8"), filename=str(POLICY_PATH))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "ROLE_SURFACE_OVERRIDES" for target in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("ROLE_SURFACE_OVERRIDES not found")


def context_parent(row: dict) -> str:
    chain = [item.strip() for item in str(row.get("parent_menu_xmlid_chain") or "").split(" > ") if item.strip()]
    return chain[-1] if chain else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = load_role_policy()

    with args.input.open(encoding="utf-8", newline="") as handle:
        authorized = [row for row in csv.DictReader(handle) if row.get("final_decision") == "PRODUCT_ROLE_NAV"]
    if len(authorized) != 138:
        raise SystemExit(f"expected 138 authorized assignments, got {len(authorized)}")

    fields = list(authorized[0]) + [
        "exposure_mode",
        "primary_group",
        "task_key",
        "journey_refs",
        "entry_reason",
        "context_parent",
    ]
    counts: dict[str, int] = {}
    for row in authorized:
        role = row["role"]
        xmlid = row["menu_xmlid"]
        role_policy = policy[role]
        primary = set(role_policy.get("primary_menu_xmlids") or [])
        home = set(role_policy.get("role_home_menu_xmlids") or [])
        denied = set(role_policy.get("denied_menu_xmlids") or [])
        if xmlid in denied:
            mode = "DENIED"
            evidence = ("", "", "")
            reason = "技术可读但无正式角色任务或旅程依据"
        elif xmlid in home:
            mode = "ROLE_HOME_ACTION"
            evidence = TASK_EVIDENCE.get(role, {}).get(xmlid, ("", "", ""))
            reason = "角色首页的正式快捷操作"
        elif xmlid in primary:
            mode = "PRIMARY_NAV"
            evidence = TASK_EVIDENCE.get(role, {}).get(xmlid, ("", "", ""))
            reason = "独立高频任务或正式旅程入口"
        else:
            mode = "CONTEXTUAL_ROUTE"
            evidence = ("", "", "")
            reason = "保留授权直达能力，由项目、合同、资金关系链或搜索进入"
        if mode in {"PRIMARY_NAV", "ROLE_HOME_ACTION"} and not all(evidence):
            raise SystemExit(f"missing task evidence: {role} {xmlid}")
        row.update(
            exposure_mode=mode,
            primary_group=evidence[2],
            task_key=evidence[0],
            journey_refs=evidence[1],
            entry_reason=reason,
            context_parent=context_parent(row) if mode == "CONTEXTUAL_ROUTE" else "",
        )
        counts[mode] = counts.get(mode, 0) + 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(authorized)
    print(" ".join(f"{key}={counts.get(key, 0)}" for key in ("PRIMARY_NAV", "CONTEXTUAL_ROUTE", "ROLE_HOME_ACTION", "ADMIN_ONLY", "DENIED")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
