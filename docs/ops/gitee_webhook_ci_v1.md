# Gitee WebHook 自建 CI v1

English: [gitee_webhook_ci_v1.en.md](gitee_webhook_ci_v1.en.md)

## 边界

- Gitee 是主代码与 PR 入口；GitHub 暂时作为镜像。
- 华为节点 `1.95.2.123` 执行轻量公开守卫，后续才允许接专业门禁。
- 本方案不使用 Gitee Go，不消耗 Gitee 构建分钟，不触发 RC、附件或生产部署。
- WebHook CI 只接受 `leegege/sce-product-odoo`、发送者 `leegege`、同仓库 Push/PR 和完整 40 位 SHA。

## 安全链

1. 只接受 `POST /hooks/gitee` 和 JSON 请求，最大 1 MiB。
2. 按 Gitee 官方算法校验 `X-Gitee-Timestamp` 与 `X-Gitee-Token`，允许时钟偏差 300 秒。
3. 已使用过的签名时间戳不可重放。
4. 校验仓库、发送者、事件；fork PR、删除分支、关闭/合并后的 PR 直接拒绝。
5. 只把规范化的 SHA、事件和 PR 编号写入 SQLite；不保存原始请求或明文密钥。
6. 相同 SHA 只执行一次；服务重启后恢复未完成队列。
7. Worker 不继承 WebHook secret 或回写 token。
8. 构建器只使用固定 Gitee URL，并在 detached HEAD 上复核实际 SHA。
9. 每次构建使用独立临时目录；日志和扫描报告保存在服务器独立目录。

## 服务器状态

服务：`gitee-webhook-ci.service`

```text
USER=gitee-ci
BIND=127.0.0.1:9080
HEALTH=http://127.0.0.1:9080/healthz
DB=/var/lib/gitee-ci/jobs.sqlite3
LOG=/var/log/gitee-ci
ARTIFACT=/var/lib/gitee-ci/artifacts
DEPLOY_KEY=/etc/gitee-ci/id_ed25519
SECRET=/etc/gitee-ci/sce-product-odoo.env
PUBLIC_HEALTH=https://1.95.2.123/healthz
WEBHOOK=https://1.95.2.123/hooks/gitee
```

密钥和私钥均为服务器本地 `0400/0440` 文件，不进入 Git、不打印到日志。
Nginx 只把精确的 WebHook 路径反向代理到 loopback 服务；公网证书由 Certbot
使用 Let's Encrypt 短期 IP 证书签发并由 systemd timer 自动续期。

## 平台配置状态

已完成公网可信 HTTPS。以下 Gitee 仓库配置仍必须在启用真实事件前完成：

1. 使用具备 `keys`、`hook`、`pull_requests` 和仓库管理权限的临时管理令牌运行
   `make gitee.ci.repository.configure GITEE_TOKEN_FILE=<0600文件>`。
2. 该命令登记服务器公钥、创建签名 WebHook、保护 `main`、创建治理 PR 并发送测试事件。
3. 配置成功后撤销临时管理令牌；不得把它复制到 CI 服务器。
4. 为最小权限机器人令牌建立服务器本地 secret 文件，用于结果评论/状态回写；构建进程不得获得写仓库权限。

配置命令在任何写操作前统一探测所需权限；权限不足时列出全部缺项并保持仓库不变。

## 验证

```bash
make verify.gitee.webhook.ci
make gitee.ci.server.status
make gitee.ci.https.status
```

负向矩阵包括无效签名、过期请求、重放、错误仓库、错误发送者、fork PR、分支/命令注入、删除/关闭事件和 secret 环境隔离。
