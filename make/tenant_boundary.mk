.PHONY: verify.product.release.version verify.tenant.product_legacy_boundary verify.tenant.customer_module_ownership verify.tenant.legacy_xmlid_boundary verify.tenant.product_fresh_install verify.tenant.boundary_q11_profile

verify.product.release.version: guard.prod.forbid
	python3 scripts/release/test_product_release.py
	python3 scripts/verify/product_release_version_guard.py
	python3 scripts/release/test_customer_package_preflight.py

verify.tenant.product_legacy_boundary: guard.prod.forbid
	python3 scripts/verify/tenant_product_legacy_boundary.py

verify.tenant.customer_module_ownership: guard.prod.forbid
	python3 scripts/verify/tenant_customer_module_ownership.py

verify.tenant.legacy_xmlid_boundary: guard.prod.forbid
	python3 scripts/verify/tenant_legacy_xmlid_boundary.py

verify.tenant.product_fresh_install: guard.prod.forbid verify.tenant.product_legacy_boundary verify.tenant.legacy_xmlid_boundary
	python3 scripts/verify/tenant_product_fresh_install.py

verify.tenant.boundary_q11_profile: guard.prod.forbid check-compose-env
	@test -n "$(CANDIDATE_IMAGE)" || { echo "CANDIDATE_IMAGE is required" >&2; exit 2; }
	@test -n "$(BOUNDARY_Q11_PROFILE)" || { echo "BOUNDARY_Q11_PROFILE is required" >&2; exit 2; }
	@test -n "$(BOUNDARY_Q11_ARTIFACTS)" || { echo "BOUNDARY_Q11_ARTIFACTS is required" >&2; exit 2; }
	@CANDIDATE_IMAGE="$(CANDIDATE_IMAGE)" BOUNDARY_Q11_PROFILE="$(BOUNDARY_Q11_PROFILE)" \
		BOUNDARY_Q11_ARTIFACTS="$(BOUNDARY_Q11_ARTIFACTS)" DB_USER="$(DB_USER)" \
		DB_PASSWORD="$(DB_PASSWORD)" ADMIN_PASSWD="$(ADMIN_PASSWD)" JWT_SECRET="$(JWT_SECRET)" \
		bash scripts/release/tenant_boundary_q11_profiles.sh
