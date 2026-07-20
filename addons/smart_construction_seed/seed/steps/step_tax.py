# -*- coding: utf-8 -*-
from ..registry import SeedStep, register


def _run(env):
    """Delegate to the product-owned, create-only reference initializer."""
    env["construction.contract"].sudo()._sc_ensure_contract_tax_seeds()


register(
    SeedStep(
        name="tax_defaults",
        description="Create missing product-owned contract tax references.",
        run=_run,
    )
)
