import json

from odoo.addons.smart_construction_acceptance_fixture.tools.frontend_productization_fixture import (
    ensure_fixture,
)

summary = ensure_fixture(env)
env.cr.commit()
print(json.dumps(summary, ensure_ascii=False, indent=2))
