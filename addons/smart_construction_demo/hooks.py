# -*- coding: utf-8 -*-
import os


def guard_demo_scope(env):
    db_name = str(env.cr.dbname or "").strip()
    if not (db_name == "sc_demo" or db_name.startswith("sc_demo_")):
        raise RuntimeError("smart_construction_demo requires a sc_demo database")
    if os.environ.get("SC_ENVIRONMENT") != "demo":
        raise RuntimeError("smart_construction_demo requires SC_ENVIRONMENT=demo")
    if os.environ.get("SC_ALLOW_DEMO_DATA") != "1":
        raise RuntimeError("smart_construction_demo requires SC_ALLOW_DEMO_DATA=1")
    if not str(os.environ.get("SC_DEMO_USER_PASSWORD") or "").strip():
        raise RuntimeError("smart_construction_demo requires SC_DEMO_USER_PASSWORD")


def apply_demo_user_passwords(env):
    guard_demo_scope(env)
    password = os.environ["SC_DEMO_USER_PASSWORD"].strip()
    rows = env["ir.model.data"].sudo().search(
        [("module", "=", "smart_construction_demo"), ("model", "=", "res.users")]
    )
    user_ids = [row.res_id for row in rows.exists()]
    users = env["res.users"].sudo().with_context(active_test=False).browse(user_ids).exists()
    if users:
        users.write({"password": password})


def pre_init_hook(env):
    guard_demo_scope(env)


def post_init_hook(env):
    apply_demo_user_passwords(env)
