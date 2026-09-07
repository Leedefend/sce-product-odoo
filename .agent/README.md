# .agent 工程上下文（产品净根仓库）

## 仓库定位

SCE 产品净根（clean root）：承载 P0-P4 产品分层与架构守卫的规范源。本仓库的治理文档是其他仓库的依据，
不是运行实例。

## 与其他仓库的关系（跨仓库分层）

- 产品机制实现层 → 独立后端机制仓库；本净根提供机制规范，不承载运行实例。
- 客户私有交付层 → 独立客户交付仓库；客户资产与产品净根隔离，不回流入产品层。

## AI 工作原则

以根目录 `AGENTS.md` 为最高执行策略：分支白名单、preflight、架构守卫、产品分层判定
（Formal Product Layer / Layer Target / Why Here / Blast Radius）缺一不可。

## 本目录约定

- `context.yaml`：仓库身份与权威路径索引
- `goals/`、`workflows/`、`runs/`：涉及本仓库的工程任务按需创建（格式见工作空间级 `.agent/README.md`）
