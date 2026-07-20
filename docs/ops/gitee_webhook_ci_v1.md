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
```

密钥和私钥均为服务器本地 `0400/0440` 文件，不进入 Git、不打印到日志。

## 尚需平台配置

在启用真实事件之前必须同时完成：

1. 为 `1.95.2.123` 建立公网可信 HTTPS 反向代理到 `127.0.0.1:9080`。
2. 把服务器生成的公钥登记为仓库只读 Deploy Key。
3. 使用 Gitee 签名密钥模式创建 WebHook，只启用 Push 和 Pull Request。
4. 配置 `main` 保护：禁止直接 Push、禁止 force push/删除、必须 PR。
5. 为最小权限机器人令牌建立服务器本地 secret 文件，用于结果评论/状态回写；构建进程不得获得写仓库权限。

没有 HTTPS 和 Gitee 管理授权时，服务保持 loopback-only，不得临时改成公网 HTTP。

## 验证

```bash
make verify.gitee.webhook.ci
make gitee.ci.server.status
```

负向矩阵包括无效签名、过期请求、重放、错误仓库、错误发送者、fork PR、分支/命令注入、删除/关闭事件和 secret 环境隔离。
