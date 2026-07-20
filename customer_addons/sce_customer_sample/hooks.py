from odoo.exceptions import UserError


def post_init_hook(env):
    params = env["ir.config_parameter"].sudo()
    existing = str(params.get_param("sc.tenant.bound_tenant_key", "") or "").strip()
    if existing and existing != "sample":
        raise UserError("TPV1_DATABASE_TENANT_ALREADY_BOUND")
    params.set_param("sc.tenant.bound_tenant_key", "sample")


def uninstall_hook(env):
    if not env.context.get("allow_audited_tenant_destroy"):
        raise UserError(
            "Customer delivery modules cannot be uninstalled. "
            "Use the audited tenant-destroy workflow."
        )
