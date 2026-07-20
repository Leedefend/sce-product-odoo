# Gitee 权威仓库到 GitHub 只读镜像

## 固定边界

- Gitee `leegege/sce-product-odoo` 是唯一开发、PR 和合并入口。
- GitHub `Leedefend/sce-product-odoo` 只接收 Gitee `main` 的同一提交 SHA。
- 普通身份不能直接写 GitHub `main`；GitHub Ruleset 仅允许 Deploy Key 绕过。
- 仓库只能存在一个 write Deploy Key，名称为 `sce-gitee-to-github-mirror`。
- 禁止 force push、force-with-lease、删除 `main`、反向覆盖 Gitee 或按 WebHook 分支文本推送。

## 凭据隔离

```text
Gitee WebHook receiver（仅签名 secret）
        ↓
Gitee CI worker（仅 Gitee 只读 Deploy Key）
        ↓ 门禁通过且 SHA == Gitee main
/var/lib/gitee-mirror/source.git（无远端凭据 handoff）
        ↓
gitee-mirror service（仅 GitHub write Deploy Key）
        ↓ 精确 SHA + fast-forward
GitHub main
```

`gitee-ci` 无权读取 `/etc/gitee-mirror/github_ed25519`。`gitee-mirror`
通过 systemd `ReadOnlyPaths` 只读 handoff 对象库，不能修改候选 ref。

## 安装与验证

所有写操作必须通过 Make 入口：

```bash
GITEE_MIRROR_SERVER_CONFIRM=1 make gitee.github.mirror.install
GITHUB_MIRROR_RULESET_CONFIRM=1 make github.mirror.ruleset.configure
GITEE_MIRROR_SEED_CONFIRM=1 \
GITEE_MIRROR_SEED_SHA=<exact-gitee-main-sha> \
make gitee.github.mirror.seed
GITEE_MIRROR_RUN_CONFIRM=1 make gitee.github.mirror.run
make github.mirror.non_mirror_push.test
```

`github.mirror.ruleset.configure` 先创建并回读 active Ruleset，再删除旧 Branch
Protection，避免规则叠加。它发现第二个 write Deploy Key 时必须停止。

GitHub fresh clone 应使用公开 HTTPS URL；历史守卫故意拒绝 GitHub SSH
origin，防止普通开发工作区获得镜像写入路径。Gitee 工作区使用只读或最小权限
SSH 身份，并通过 `make pr.push` 只写 Gitee 权威远端。
