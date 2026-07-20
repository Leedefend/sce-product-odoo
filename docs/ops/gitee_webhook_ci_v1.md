# Gitee WebHook 自建 CI v1

English: [gitee_webhook_ci_v1.en.md](gitee_webhook_ci_v1.en.md)

## 边界

- Gitee 是主代码与 PR 入口；GitHub 暂时作为镜像。
- 华为节点 `1.95.2.123` 对同仓库事件执行轻量公开守卫；PR 事件在其通过后继续执行
  `pnpm install` 和完整 `make ci` 专业门禁。
- 本方案不使用 Gitee Go，不消耗 Gitee 构建分钟，不触发 RC、附件或生产部署。
- WebHook CI 只接受 `leegege/sce-product-odoo`、发送者 `leegege`、同仓库 Push/PR 和完整 40 位 SHA。

## 安全链

1. 只接受 `POST /hooks/gitee` 和 JSON 请求，最大 1 MiB。
2. 按 Gitee 官方算法校验签名与时间戳，兼容文档请求头和 API 创建钩子的
   `sign`/`timestamp` 查询参数；存在完整查询签名时以它为权威，否则使用请求头。
   专用解析器保留 Gitee 未转义的 Base64 `+`，允许时钟偏差 300 秒，查询签名不写入访问日志。
3. 已使用过的签名时间戳不可重放。
4. 校验仓库、发送者、事件；fork PR、删除分支、关闭/合并后的 PR 直接拒绝。
5. 只把规范化的 SHA、事件和 PR 编号写入 SQLite；不保存原始请求或明文密钥。
6. 相同 SHA 的重复事件只执行一次；若 PR 事件晚于 Push 到达，任务从公开守卫升级为专业门禁，
   即使公开守卫正在运行也会在其结束后继续专业门禁。服务重启后恢复未完成队列。
7. Worker 不继承 WebHook secret 或回写 token。
8. 构建器只使用固定 Gitee URL，并在 detached HEAD 上复核实际 SHA。
9. 每次构建使用独立临时目录；日志和扫描报告保存在服务器独立目录。
10. Push 只执行公开守卫；同仓库、同所有者 PR 才执行专业门禁，fork 在入队前拒绝。
11. receiver 保持 `MemoryDenyWriteExecute=true` 且不启动构建进程；worker 不持有 WebHook
    密钥，并单独承担 Node/V8/Wasm 专业构建。两者只通过 SQLite 规范化队列通信。

## 服务器状态

服务：`gitee-webhook-ci.service`（签名接收器）和 `gitee-ci-worker.service`（构建器）。

```text
USER=gitee-ci
BIND=127.0.0.1:9080
HEALTH=http://127.0.0.1:9080/healthz
DB=/var/lib/gitee-ci/jobs.sqlite3
LOG=/var/log/gitee-ci
ARTIFACT=/var/lib/gitee-ci/artifacts
DEPLOY_KEY=/etc/gitee-ci/id_ed25519
RECEIVER_ENV=/etc/gitee-ci/sce-product-odoo-receiver.env
WORKER_ENV=/etc/gitee-ci/sce-product-odoo-worker.env
PUBLIC_HEALTH=https://1.95.2.123/healthz
WEBHOOK=https://1.95.2.123/hooks/gitee
```

WebHook 密钥只进入 receiver 环境，Deploy Key 只进入 worker 环境；两个服务不共享密钥文件。
密钥和私钥均为服务器本地 `0400/0440` 文件，不进入 Git、不打印到日志。
Nginx 只把精确的 WebHook 路径反向代理到 loopback 服务；公网证书由 Certbot
使用 Let's Encrypt 短期 IP 证书签发并由 systemd timer 自动续期。

## 平台配置状态

已完成公网可信 HTTPS、只读 Deploy Key、签名 WebHook、`main` 保护和治理 PR。
配置程序可幂等复核这些状态。Gitee 自带“测试 WebHook”使用非目标仓库的模拟
payload，因此会被仓库白名单拒绝；验收必须使用同仓库真实 Push/PR 的精确 SHA。

1. 配置复核使用具备 `keys`、`hook`、`pull_requests` 和仓库管理权限的临时管理令牌运行
   `make gitee.ci.repository.configure GITEE_TOKEN_FILE=<0600文件>`。
2. 配置成功后撤销临时管理令牌；不得把它复制到 CI 服务器。
3. 结果评论/状态回写仍需单独的最小权限机器人令牌；构建进程不得获得写仓库权限。

配置命令在任何写操作前统一探测所需权限；权限不足时列出全部缺项并保持仓库不变。

## 首次端到端证据

治理 PR `#1` 的真实同仓库事件已按精确 SHA
`736a310ab4f5a0844797d8178a34e3b92cc3320a` 完成：只读 Deploy Key 检出成功，
历史/secret/个人数据/客户边界与 12/12 发布扫描通过，任务退出码为 0，临时工作区已清理，
CI 日志未命中凭据标记。

## 验证

```bash
make verify.gitee.webhook.ci
make gitee.ci.server.status
make gitee.ci.https.status
```

15 项矩阵包括请求头/查询签名正向用例、原始 Base64 `+`、API 双通道优先级、Push→PR 队列升级、receiver/worker 密钥隔离，以及无效签名、意外或重复查询参数、过期请求、重放、错误仓库、错误发送者、fork PR、分支/命令注入、删除/关闭事件和 secret 环境隔离。
