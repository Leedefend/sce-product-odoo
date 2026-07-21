# NAV-POLICY-01 产品导航裁决

审计基线为 `53aa5521ca20` 诊断镜像对应的全新 `sc_frontend_acceptance` 隔离库。`TENANT-RC-01` 保持暂停；本轮未构建镜像、未运行 Trivy 或完整 CI，也未修改 ACL、record rule、前端 fallback、生产数据或附件。

## 口径

`NATIVE_LEAF_COUNT=324` 是四个正式角色的“角色 × 原生叶节点”出现次数，角色原始分布为 finance 104、project_member 79、pm 94、owner 47；去重后是 177 个 menu XML-ID、169 个 action XML-ID。矩阵逐行保留角色，因此 324 行可以直接审计每个角色的 ACL、record rule、发布策略和最终裁决。

产品规则的事实优先级为：

1. `sc.product.policy` 中状态为 released 的产品菜单和 capability；
2. `ROLE_SURFACE_OVERRIDES` 的角色根目录、menu/action/model blocklist；
3. 当前角色实际的 model ACL 和适用 record rule；
4. 浏览器对精确 menu/action 的实际 HTTP 结果。

`project_member` 策略中的 `smart_construction_core.menu_sc_construction_center` 在安装库中不存在。其唯一同义、真实的“施工管理”父节点是 `smart_construction_core.menu_sc_construction_management_center`，本矩阵按该真实 XML-ID解释既有产品策略；这是一项待后续最小修复的策略标识漂移，不是扩大角色权限。

## 派生结果

```text
NATIVE_LEAF_COUNT=324
NATIVE_UNIQUE_MENU_COUNT=177
PRODUCT_ROLE_NAV_COUNT=138
PRODUCT_ADMIN_NAV_COUNT=0
PLATFORM_TECHNICAL_COUNT=0
CUSTOMER_PRIVATE_COUNT=0
DENIED_COUNT=182
DEAD_OR_BROKEN_COUNT=4
UNRESOLVED_COUNT=0

FINANCE_COUNT=64
PROJECT_MEMBER_COUNT=20
PM_COUNT=34
OWNER_COUNT=20
```

324 项中，176 项位于当前角色正式根目录之外，6 项在允许根目录内但 model read ACL 不成立，合计 182 项为 `DENIED_BY_CAPABILITY`。4 项 `DEAD_OR_BROKEN` 是两个失效 action 分别出现在 PM 和 owner 导航中。管理员、低代码治理、平台技术和客户私有入口均未进入这 324 项的正式业务角色分母。

138 是按现有产品策略自然计算出的候选分母，不是新的硬编码门槛。后续修复应以本 CSV 的逐项裁决为输入，不能反向调整算法去追求 138。

## 旧 70、声称 80 与当前 324

旧 70 中有 57 项仍属于合法 `PRODUCT_ROLE_NAV`，13 项不再成立：3 项已不在当前 324 清单，另 10 项超出当前正式角色根目录。当前 138 项合法角色入口中有 81 项未被旧 70 覆盖，因此旧验收确实遗漏了合法产品入口。

仓库与本轮外部证据中找不到“80 项”的逐项清单、menu/action 集合或可复算报告。唯一证据是 `scripts/release/verify_tenant_rc_runtime_acceptance.py` 中硬编码的 `80/80` 字符串和失败消息，无法识别所谓比 70 多出的 10 项。

```text
OLD_70_VALID_COUNT=57
OLD_70_REMOVED_COUNT=13
OLD_80_DELTA_IDENTIFIED=false
```

因此正式废弃 80 口径；旧 70 仅保留为历史回归参照。

## 两个修复提交

### `596643c17cb24d250b843484dbc2de4fcc8d3b0c` — DROP

该提交把角色 allowlist 应用在已经按产品策略重新分组的合成导航树末端。此时真实 Odoo 父链已经丢失，合成父节点也不携带角色根 XML-ID，导致合法叶节点被整体删除，实际结果降为 4/4。

实现没有硬编码 70/80，但测试直接规定 finance 可见“付款申请”、不可见“项目列表”，没有从权威矩阵生成期望。非空 allowlist 下，无 XML-ID 的孤立叶节点 fail-closed；空 allowlist 则表示“不限制”，而不是“无权限”。这两个语义都没有形成明确产品合同。

### `3336add78916a59886af824143a98ea2e0ec86bd` — REWRITE

该提交把 allowlist 提前到真实 native tree 上执行，再用过滤后的 native index 约束产品策略行，投影边界方向正确。非管理员的策略行必须命中过滤后的 menu ID/XML-ID/scene/route，因此合成分组本身不会重新引入已排除叶节点；action/model blocklist 仍在最终层独立执行。

但它仍不能直接保留：

- 测试仍把 finance 的具体业务菜单假设写死，没有从矩阵生成；
- `project_member` 的施工管理根 XML-ID 已失效，会误删整条合法父链；
- `final_surface["menu_xmlids"] = []` 借用了“空 allowlist = 不限制”的隐式语义；
- 非空 allowlist 时缺失 XML-ID 的叶节点 fail-closed，空 allowlist 时却完全关闭该检查，语义需要显式拆分；
- 导航投影只验证 native 授权，不验证 action domain 使用的字段仍存在，因此两个失效 action 仍会进入导航。

后续最小修复应保留“在真实父链上先求交”的结构，重写策略输入和测试，使预期来自权威 CSV，并显式定义 empty/missing XML-ID 语义。

```text
COMMIT_596643C=DROP
COMMIT_3336ADD=REWRITE
```

## HTTP 500 分类

浏览器精确探针证明，两个 action 的 `ui.contract.v2` 都返回 200；500 出现在随后的 `api.data list`：

- menu `smart_construction_core.menu_sc_project_income_contract_acceptance_construction` / action `smart_construction_core.action_construction_contract_income_construction`：domain 使用已不存在的 `construction.contract.income.legacy_contract_id`；
- menu `smart_construction_core.menu_sc_income_contract_execution` / action `smart_construction_core.action_construction_contract_income_execution`：domain 使用已不存在的 `construction.contract.income.legacy_visible_title`。

两者均不是模块未安装、ACL 拒绝或 record rule 缺失：PM/owner 对模型有 read ACL，且存在适用 record rule。根因是产品/客户拆分后，产品 action/search domain 仍引用已移出的 legacy 字段。每个 action 对 PM、owner 各出现一次，因此是 2 个唯一缺陷、4 条矩阵记录。

NAV-PRO-01 收口已完成最小修复：重复的“施工合同”菜单被停用，其 action 改用 canonical `business_category_id.code`；“收入合同执行”改用 canonical `subject`。两条 action 的 `ui.contract.v2` 与 `api.data list` 均由隔离 HTTP smoke 验证为 200，未扩大 ACL 或 record rule。

此前定向测试日志中的 `GET /web/login 500` 属于测试基础设施探针，而非业务导航：仓库唯一的周期调用者是 Compose healthcheck；`scripts/test/test.sh` 的一次性测试容器采用 `--no-http --stop-after-init`，与服务型 `/web/login` healthcheck 生命周期不兼容。本轮稳定隔离服务中该探针持续返回 200，两个业务 action 的 traceback 也与 `/web/login` 无关。该项分类为 `TEST_HARNESS_HEALTHCHECK_LIFECYCLE_MISMATCH`；后续应在一次性测试容器禁用服务 healthcheck，不把其瞬态结果计入 RC 页面错误。

```text
HTTP_500_UNRESOLVED=0
```

## 交付物与边界

- `authoritative_navigation_matrix.csv`：324 行逐角色权威矩阵；
- 仓库外证据：运行时菜单/ACL/policy 导出、两个 action 的请求响应和服务端 traceback；
- 历史两个导航提交没有直接复用；当前实现按权威矩阵重写为显式 exposure policy、原生菜单求交和独立 contextual authority。现有旧镜像仍保持诊断制品身份。

本裁决及其派生矩阵已成为 NAV-PRO-01 的可复算输入。确定性矩阵生成、Odoo 定向测试、四角色原生可见性、HTTP 数据探针和浏览器主导航/上下文路由 smoke 均已通过；最终 RC 镜像仍须在本提交进入正式构建流程后单独生成和验收。
