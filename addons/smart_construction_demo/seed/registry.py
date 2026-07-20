# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass(frozen=True)
class SeedStep:
    name: str
    description: str
    run: Callable


_REGISTRY: Dict[str, SeedStep] = {}
_PROFILES: Dict[str, List[str]] = {
    "demo_full": [
        "dictionary",
        "company_currency_cny",
        "demo_10_users",
        "demo_user_prefs",
        "demo_20_projects",
        "demo_30_tenders",
        "demo_40_contracts",
        "demo_50_boq_wbs",
        "demo_60_attachments",
        "z_demo_full_my_work",
        "demo_90_verify",
    ],
}


def register(step: SeedStep) -> None:
    if step.name in _REGISTRY:
        raise ValueError("demo step already registered: %s" % step.name)
    _REGISTRY[step.name] = step


def list_steps() -> List[str]:
    return sorted(_REGISTRY)


def _guard_demo_scope(env) -> None:
    db_name = str(getattr(getattr(env, "cr", None), "dbname", "") or "").strip()
    if not (db_name == "sc_demo" or db_name.startswith("sc_demo_")):
        raise RuntimeError("demo data requires a sc_demo database (got %s)" % (db_name or "<empty>"))
    if os.environ.get("SC_ENVIRONMENT") != "demo":
        raise RuntimeError("demo data requires SC_ENVIRONMENT=demo")
    if os.environ.get("SC_ALLOW_DEMO_DATA") != "1":
        raise RuntimeError("demo data requires SC_ALLOW_DEMO_DATA=1")
    if not str(os.environ.get("SC_DEMO_USER_PASSWORD") or "").strip():
        raise RuntimeError("demo data requires SC_DEMO_USER_PASSWORD")


def _resolve(selected: str) -> List[SeedStep]:
    value = (selected or "").strip()
    if value.startswith("profile:"):
        value = value.split(":", 1)[1].strip()
    if value in _PROFILES:
        names = _PROFILES[value]
    elif not value or value.lower() == "all":
        names = list_steps()
    else:
        names = [item.strip() for item in value.split(",") if item.strip()]
    missing = [name for name in names if name not in _REGISTRY]
    if missing:
        raise ValueError("unknown demo steps: %s; available=%s" % (missing, list_steps()))
    return [_REGISTRY[name] for name in names]


def run_steps(env, selected: str) -> List[str]:
    _guard_demo_scope(env)
    executed = []
    for step in _resolve(selected):
        step.run(env)
        executed.append(step.name)
    return executed
