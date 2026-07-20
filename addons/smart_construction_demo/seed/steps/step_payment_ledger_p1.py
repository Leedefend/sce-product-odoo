# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError

from ..registry import SeedStep, register


def _complete_settlement(settlement):
    if settlement.state == "draft":
        settlement.action_submit()
    if settlement.state == "submit":
        reviewer = settlement.env.ref("smart_construction_demo.user_sc_settlement_manager_cap")
        for _index in range(max(1, len(settlement.review_ids))):
            settlement.with_user(reviewer).validate_tier()
            settlement.invalidate_recordset()
            if settlement.validation_status == "validated":
                break
        if settlement.validation_status == "validated" and settlement.state == "submit":
            settlement.action_on_tier_approved()
    if settlement.state == "approve":
        settlement.action_done()
    if settlement.state != "done":
        raise UserError("Demo 结算单未能按正式状态机完成。")


def _find_demo_project(env):
    try:
        return env.ref("smart_construction_demo.sc_demo_project_001")
    except ValueError:
        return env["project.project"].sudo().search([], limit=1)


def _find_demo_partner(env):
    partner = env.ref("smart_construction_demo.seed_partner_contract", raise_if_not_found=False)
    if not partner:
        raise UserError("缺少基础主数据：seed_partner_contract。")
    return partner


def _ensure_demo_contract_in(env, project, partner):
    Contract = env["construction.contract"].sudo()
    subject = "Demo 合同-支出"
    contract = Contract.search(
        [("subject", "=", subject), ("project_id", "=", project.id)],
        limit=1,
    )
    if contract:
        return contract
    tax = env.ref("smart_construction_seed.tax_purchase_13", raise_if_not_found=False)
    if not tax:
        raise UserError("缺少基础主数据：tax_purchase_13。")
    return Contract.create(
        {
            "subject": subject,
            "type": "in",
            "project_id": project.id,
            "partner_id": partner.id,
            "tax_id": tax.id,
            "date_contract": "2025-02-01",
        }
    )


def _ensure_demo_settlement(env, project, contract, partner):
    Settlement = env["sc.settlement.order"].sudo()
    Line = env["sc.settlement.order.line"].sudo()
    name_prefix = "DEMO-SO-P1-"
    existing = Settlement.search([("name", "=like", f"{name_prefix}%")], limit=1)
    if existing:
        if not existing.line_ids:
            Line.create(
                {
                    "settlement_id": existing.id,
                    "name": "Demo-结算行(P1)",
                    "qty": 1.0,
                    "price_unit": 100.0,
                }
            )
        _complete_settlement(existing)
        return existing
    record = Settlement.create(
        {
            "name": f"{name_prefix}001",
            "project_id": project.id,
            "contract_id": contract.id,
            "partner_id": partner.id,
            "settlement_type": "out",
            "note": "seed:payment_ledger_p1",
        }
    )
    Line.create(
        {
            "settlement_id": record.id,
            "name": "Demo-结算行(P1)",
            "qty": 1.0,
            "price_unit": 100.0,
        }
    )
    _complete_settlement(record)
    return record


def run(env):
    Payment = env["payment.request"].sudo()
    Ledger = env["payment.ledger"].sudo()
    ICP = env["ir.config_parameter"].sudo()
    name_prefix = "DEMO-PR-LEDGER-P1-"
    ledger_prefix = "RR-LEDGER-P1"

    existing_ledger = Ledger.search([("ref", "=like", f"{ledger_prefix}%")], limit=1)
    if existing_ledger:
        ICP.set_param("sc.seed.payment_ledger_p1", str(existing_ledger.id))
        return {"ok": True, "ledger_id": existing_ledger.id}

    project = _find_demo_project(env)
    if not project:
        raise UserError("缺少 demo 项目，无法创建付款台账样本。")

    partner = _find_demo_partner(env)
    contract = _ensure_demo_contract_in(env, project, partner)
    settlement = _ensure_demo_settlement(env, project, contract, partner)

    payment = Payment.search([("name", "=like", f"{name_prefix}%")], limit=1)
    if not payment:
        payment = Payment.create(
            {
                "name": f"{name_prefix}001",
                "type": "pay",
                "project_id": project.id,
                "contract_id": contract.id,
                "settlement_id": settlement.id,
                "partner_id": partner.id,
                "amount": 100.0,
                "note": "seed:payment_ledger_p1",
            }
        )
    if payment.state != "approved":
        env.cr.execute(
            "UPDATE payment_request SET state=%s, validation_status=%s WHERE id=%s",
            ("approved", "validated", payment.id),
        )
        env.invalidate_all()

    ledger = payment._ensure_payment_ledger(
        paid_at=fields.Datetime.now(),
        ref=f"{ledger_prefix}-001",
        note="seed:payment_ledger_p1",
    )
    ICP.set_param("sc.seed.payment_ledger_p1", str(ledger.id))
    return {"ok": True, "payment_request_id": payment.id, "ledger_id": ledger.id}


register(
    SeedStep(
        name="payment_ledger_p1",
        description="Create approved payment request and ledger sample for P1 audit.",
        run=run,
    )
)
