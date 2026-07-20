# OCA server-ux vendor subset

This directory contains only the product runtime dependencies copied from
`OCA/server-ux` branch `17.0` at commit
`2b908a8e68ddde906ea45be7b5fb24676f29f8cc`:

- `base_tier_validation`
- `base_tier_validation_server_action`

The subset is committed directly so product builds and professional CI are
self-contained after the product repository is checked out from Gitee. Do not
replace it with an unpinned submodule or add unrelated OCA modules.
