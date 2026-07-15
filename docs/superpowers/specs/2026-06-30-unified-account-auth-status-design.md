# 统一账号 Cookie / 登录状态判定设计文档

- **日期**：2026-06-30
- **状态**：待实现
- **范围**：`apps/core-api`、`apps/user-web`、`apps/automation-service`
- **目标**：让账号管理、连接管理、工作流，以及项目内所有依赖账号 Cookie / 登录态的功能使用同一套判定能力、同一份状态数据、同一种错误语义

---

## 一、背景与问题

当前项目中“账号 Cookie 是否正常”“账号是否可继续执行需要登录态的动作”至少存在三套口径：

1. **账号管理页**
   - 主要根据数据库中的 `cookie_status` 和账号 `status` 展示“正常 / 失效 / 过期 / 需验证”
   - 不会在页面加载时做统一的实时登录探测
   - 结果可能是历史状态，不一定等于当前真实可用状态

2. **连接管理页**
   - 主要根据 WebSocket 运行态接口返回值和本地兜底文案展示 Cookie 状态
   - 一部分状态来自 `websocketStatus`，一部分状态来自账号列表字段，一部分状态来自 SSE 事件
   - Cookie 状态和登录态语义混杂，容易出现“WS 在线但登录已不可用”或“Cookie 文案看似正常但工作流无法启动”

3. **工作流运行前校验**
   - 在后端单独解密 Cookie、检查 `_m_h5_tk`、检查 `externalUid`，再调用 `user.page.head` 做真实探测
   - 判断更严格，但只在工作流运行前触发
   - 失败后虽然拦截执行，但不会统一刷新所有页面上的账号状态

这导致用户会看到以下冲突场景：

- 账号管理页显示三个账号 Cookie 正常、WS 在线
- 工作流运行前弹窗提示三个账号“登录已失效，请重新登录”
- 连接管理页、消息页、商品页等其他位置继续沿用旧状态

目标不是只修复工作流弹窗，而是建立**全项目唯一的账号认证状态判定能力**，并保证任何地方只要“使用了”或“判断了”账号登录态，就会触发统一判定并把结果同步给全站相关页面。

---

## 二、设计目标

### 2.1 业务目标

1. 账号管理、连接管理、工作流、检查登录、刷新资料、Cookie 更新后状态、WebSocket 风控回写，全部使用同一套判定结果。
2. 项目中所有依赖账号登录态的功能，在真正执行前都能获得统一的“是否可用 + 为什么不可用”结果。
3. 当任一入口触发新的登录态判定后，相关页面应尽快看到统一更新后的状态，而不是保留旧文案。

### 2.2 技术目标

1. 建立一个统一的后端服务，作为账号 Cookie / 登录态的唯一真相源。
2. 将当前散落在账号页、连接页、工作流、自动化链路中的判定逻辑收口。
3. 返回结构化状态，而不是只有 `true/false` 或“登录已失效”这一种模糊文案。
4. 将最新判定结果持久化，供列表页、筛选、统计、其他页面直接复用。
5. 状态变化后统一广播事件，推动前端相关页面刷新。

### 2.3 非目标

1. 本轮不重写全部 WebSocket 状态机。
2. 本轮不将“账号健康分”接口一起实现。
3. 本轮不要求账号列表页每次打开都对所有账号实时探测一次，以避免页面过慢和额外外部压力。

---

## 三、统一口径定义

### 3.1 两类状态必须分开

后续所有页面必须明确区分下面两种状态：

1. **认证状态 / 登录状态**
   - 回答的问题是：这个账号当前还能不能继续执行需要闲鱼登录态的动作？
   - 例如：工作流发布、刷新资料、检查登录、同步商品、发消息前校验、自动化任务启动

2. **连接状态 / WebSocket 状态**
   - 回答的问题是：这个账号当前有没有和消息链路建立实时连接？
   - 它影响消息接收和自动回复，但不等同于登录态

结论：**Cookie / 登录状态不能再通过 WebSocket 在线与否推断**；WebSocket 在线也不能替代真实登录探测。

### 3.2 统一判定链路

统一判定能力采用固定链路，任何入口都必须复用：

1. 账号是否存在且启用
2. 认证记录是否存在
3. Cookie 是否可解密
4. 解密后 Cookie 是否为空
5. Cookie 是否包含 `_m_h5_tk`
6. 是否能确定 `externalUid`
7. 使用 `user.page.head` 做真实探测

只有全部通过，账号才被视为“当前登录态可用”。

### 3.3 统一状态结果模型

统一判定服务不再只返回 `boolean`，而是返回结构化结果：

```json
{
  "accountId": 12,
  "nickname": "小龙云设计",
  "usable": false,
  "cookieStatus": 0,
  "loginStatusCode": "PAGE_HEAD_FAILED",
  "loginStatusMessage": "登录已失效，请重新登录闲鱼账号",
  "checkedAt": "2026-06-30T14:05:12",
  "source": "workflow_precheck"
}
```

字段定义：

- `usable`
  - `true`：允许执行需要登录态的动作
  - `false`：不允许

- `cookieStatus`
  - 为兼容现有链路，继续使用数值语义：
  - `1`：正常
  - `0`：失效 / 需验证 / 不可用
  - `2`：过期

- `loginStatusCode`
  - 机器可读错误码，供前后端和后续自动化逻辑统一判断

- `loginStatusMessage`
  - 用户可见文案，所有页面和弹窗复用，不再各自拼接

- `checkedAt`
  - 最近一次统一判定时间

- `source`
  - 触发本次判定的入口，如 `workflow_precheck`、`account_refresh_profile`、`check_login`、`connection_status_refresh`

### 3.4 建议错误码

首版统一错误码如下：

| 错误码 | `cookieStatus` | `usable` | 用户文案 |
|---|---:|---:|---|
| `OK` | 1 | true | 登录状态正常 |
| `ACCOUNT_DISABLED` | 0 | false | 账号已停用，请先启用后再操作 |
| `AUTH_MISSING` | 0 | false | 未找到登录信息，请重新登录闲鱼账号 |
| `COOKIE_DECRYPT_FAILED` | 0 | false | Cookie 解密失败，请重新登录闲鱼账号 |
| `COOKIE_EMPTY` | 0 | false | 登录信息为空，请重新登录闲鱼账号 |
| `COOKIE_TOKEN_MISSING` | 0 | false | Cookie 中缺少 `_m_h5_tk`，请重新登录闲鱼账号 |
| `EXTERNAL_UID_MISSING` | 0 | false | 账号缺少 `externalUid`，请重新登录闲鱼账号 |
| `COOKIE_EXPIRED` | 2 | false | 登录已过期，请重新登录闲鱼账号 |
| `PAGE_HEAD_FAILED` | 0 | false | 登录已失效，请重新登录闲鱼账号 |
| `CAPTCHA_REQUIRED` | 0 | false | 当前账号需要完成验证后才能继续操作 |
| `UNKNOWN_ERROR` | 0 | false | 账号登录状态检查失败，请稍后重试 |

说明：

1. `COOKIE_EXPIRED` 用于能明确识别为“过期”的场景。
2. `PAGE_HEAD_FAILED` 仍然保留，但只作为真实探测失败的专用结果，不再泛化为所有错误。
3. WebSocket 风控或滑块如果能明确识别为需要验证，应优先映射到 `CAPTCHA_REQUIRED`。

---

## 四、后端架构设计

### 4.1 新增统一服务

在 `apps/core-api` 新增统一服务，例如：

- `XianyuAccountAuthStatusService`

职责：

1. 对单个账号执行统一判定链路
2. 返回结构化结果
3. 将结果回写到数据库
4. 当状态变化时发出统一事件
5. 支持批量判定多个账号

建议提供的方法：

```java
AccountAuthStatusResult checkAndSync(Long tenantId, Long accountId, String source);

List<AccountAuthStatusResult> checkAndSyncBatch(Long tenantId, Collection<Long> accountIds, String source);

AccountAuthStatusResult fromStoredState(Long tenantId, Long accountId);
```

### 4.2 统一探测实现

统一服务内部复用现有能力，但不再直接暴露为 `boolean`：

- Cookie 解密仍复用 `CookieCryptoService`
- 真实探测仍复用 `XianyuApiUtils.callPageHead`
- 原 `XianyuAccountAvailabilityProbeService` 需要升级为返回结构化探测结果，不能只给 `true/false`

建议新增结果类型：

```java
public class AccountAuthProbeResult {
    private boolean usable;
    private int cookieStatus;
    private String loginStatusCode;
    private String loginStatusMessage;
}
```

### 4.3 数据持久化

目前仅有 `cookie_status` 不足以承载统一语义，需要补充字段。

建议在 `xianyu_account_auth` 增加：

- `last_login_status_code` `VARCHAR(64)`
- `last_login_status_message` `VARCHAR(255)`
- `last_login_check_time` `DATETIME`

建议在 `xianyu_account_runtime` 镜像增加同名字段，便于连接管理和运行态页面直接读取：

- `last_login_status_code`
- `last_login_status_message`
- `last_login_check_time`

说明：

1. `xianyu_account_auth` 是账号认证状态的主存储。
2. `xianyu_account_runtime` 保留镜像，兼容现有连接页和自动化链路的读取模式。
3. `cookie_status` 仍保留并同步更新，避免一次性破坏现有逻辑。

### 4.4 状态变化广播

统一服务在状态回写后需要统一广播事件，例如：

```json
{
  "type": "account_auth_status_changed",
  "accountId": 12,
  "cookieStatus": 0,
  "usable": false,
  "loginStatusCode": "PAGE_HEAD_FAILED",
  "loginStatusMessage": "登录已失效，请重新登录闲鱼账号",
  "checkedAt": "2026-06-30T14:05:12",
  "source": "workflow_precheck"
}
```

现有的 `cookie_status_changed` 事件暂时保留兼容，但所有新页面逻辑应优先消费 `account_auth_status_changed`。

---

## 五、接口契约调整

### 5.1 账号列表接口

受影响接口：

- `GET/POST` 账号列表相关接口
- `getAccounts()` 依赖的 `core-api` 账号查询返回
- 连接管理页当前依赖的账号列表

需要让账号对象统一带上这些字段：

```json
{
  "cookieStatus": 0,
  "loginUsable": false,
  "loginStatusCode": "PAGE_HEAD_FAILED",
  "loginStatusMessage": "登录已失效，请重新登录闲鱼账号",
  "loginCheckedAt": "2026-06-30T14:05:12"
}
```

要求：

1. 账号管理页显示直接取这组字段
2. 连接管理页的 Cookie 文案也直接取这组字段
3. 自动回复、商品发布、消息、机会页等所有 `getAccounts()` 消费方都拿到同一套字段

### 5.2 工作流运行前校验

`WorkflowAccountValidationService` 不再自己逐项拼装错误原因，而是改为调用统一服务：

- 获取触发器 / 发布节点涉及的账号
- 对这些账号执行 `checkAndSyncBatch(..., "workflow_precheck")`
- 将 `usable=false` 的结果整理成原有 `invalidAccounts` 响应

这样工作流的错误弹窗文案自动与账号页、连接页一致。

### 5.3 刷新资料

`refreshProfile(accountId)` 在执行前必须先走统一服务：

1. 先判定并回写状态，`source = account_refresh_profile`
2. 若不可用，则直接返回统一错误文案
3. 若可用，再调用 `page.head` / `page.nav` 刷新资料
4. 刷新成功后再次以 `OK` 状态回写最近判定时间

### 5.4 检查登录

连接管理页中的“检查登录”不应再只返回自由文本，而应直接触发统一服务，并返回统一结果结构。

### 5.5 手动更新 Cookie / 扫码登录成功

这些动作完成后不应仅把 `cookie_status` 粗暴置为 `1`，而应：

1. 先保存 Cookie
2. 立即执行一次统一判定
3. 根据真实结果写回状态
4. 广播统一事件

这样可以避免“刚更新完 Cookie 页面立刻显示正常，但真实其实仍不可用”的假阳性。

---

## 六、前端页面与消费方改造

### 6.1 账号管理页

文件：

- `apps/user-web/src/pages/AccountsPage.vue`

改造要求：

1. 账号表格中的 Cookie 状态统一展示 `loginStatusMessage` 对应的标签文案，而不是只看 `cookie_status`
2. 右侧“连接诊断”中的 Cookie 状态、账号验证提示，统一使用后端返回的结构化结果
3. 增加“最近检测时间”展示
4. 收到 `account_auth_status_changed` 事件时，局部刷新当前账号状态
5. `refreshProfile`、`更新 Cookie`、扫码成功、手动添加成功后，统一刷新列表

### 6.2 连接管理页

文件：

- `apps/user-web/src/pages/ConnectionsPage.vue`

改造要求：

1. Cookie 状态不能再用 `s.cookieStatus || (a.status===1?'有效':'异常/需验证')` 这种兜底逻辑
2. `selected.cookie`、统计卡片、筛选条件都改为基于统一认证状态字段
3. WebSocket 状态与登录状态并列展示，不再互相覆盖
4. “检查登录”按钮调用统一登录检查接口
5. 收到 `account_auth_status_changed` 时更新对应行和右侧详情

### 6.3 工作流页

文件：

- `apps/user-web/src/pages/WorkflowPage.vue`

改造要求：

1. 运行前账号校验失败弹窗直接展示统一服务返回的 `loginStatusMessage`
2. 若账号状态变化，工作流页选账号卡片中的状态提示也应同步更新
3. `loadAccounts()` 拉到的账号数据中应带统一认证状态字段，供账号选择器展示

### 6.4 其他 `getAccounts()` 消费方

需要确认并统一受益的页面包括但不限于：

- `AutoReplyPage.vue`
- `AutoDeliveryPage.vue`
- `MessagesPage.vue`
- `OpportunityPage.vue`
- `ProductPublishPage.vue`
- `ProductsPage.vue`
- `OrdersPage.vue`
- 移动端账号与消息相关页面

这批页面本轮不一定都做复杂 UI 改造，但至少要保证：

1. 读取账号数据时能拿到统一认证状态
2. 需要判断账号可用性时，不再自己猜状态
3. 如果页面有明显的账号状态展示，也应改用统一字段

---

## 七、自动化与旁路状态统一

### 7.1 WebSocket 风控回写

当前 `automation-service` 中 `ws_client.py` 会在滑块或失效场景下直接更新 `cookie_status` 并广播 `cookie_status_changed`。

本轮要求：

1. 保留现有风控检测能力
2. 但更新出口统一为“认证状态同步”语义
3. 至少补齐：
   - `loginStatusCode`
   - `loginStatusMessage`
   - `last_login_check_time`
4. 同时广播 `account_auth_status_changed`

### 7.2 运行中发现登录过期

自动化运行过程中，像同步商品、发布、搜索、消息相关链路，只要识别到“登录已过期 / token 失效 / 需要验证”，都应尽量落到同一个状态回写出口。

原则：

1. 识别到明确认证问题时，必须同步统一状态
2. 不要只抛异常，不更新账号状态
3. 不要在不同模块里各自定义不同中文文案

---

## 八、数据库与兼容策略

### 8.1 数据库迁移

`DataInitializer` 需要负责补齐字段，确保已部署库平滑升级。

需要新增字段：

#### `xianyu_account_auth`

- `last_login_status_code VARCHAR(64) NULL`
- `last_login_status_message VARCHAR(255) NULL`
- `last_login_check_time DATETIME NULL`

#### `xianyu_account_runtime`

- `last_login_status_code VARCHAR(64) NULL`
- `last_login_status_message VARCHAR(255) NULL`
- `last_login_check_time DATETIME NULL`

### 8.2 兼容旧逻辑

为避免一次性破坏现网逻辑：

1. 保留 `cookie_status` 字段
2. 保留旧 `cookie_status_changed` 事件，但内部可由统一服务顺带发出
3. 老前端若只认 `cookie_status` 仍可工作
4. 新前端逐步迁移到结构化字段

---

## 九、错误处理与边界场景

### 9.1 列表页不做全量实时探测

账号管理和连接管理页在普通加载时只读取最近一次统一判定结果，不主动对每个账号实时触发 `page.head`。

原因：

1. 避免页面打开过慢
2. 避免对闲鱼接口施加过多实时探测请求
3. 避免用户只是浏览列表就触发大量外部调用

### 9.2 哪些动作必须触发最新判定

以下动作必须触发统一判定并更新页面：

1. 工作流运行前校验
2. 检查登录
3. 刷新资料
4. 手动更新 Cookie
5. 扫码登录成功
6. 连接管理中明确执行 Cookie 相关刷新动作
7. 自动化运行过程中检测到登录失效、滑块、过期

### 9.3 外部接口异常

如果 `page.head` 因网络异常、超时、返回结构缺失等失败：

1. 当前统一映射为不可用状态
2. 默认错误码使用 `PAGE_HEAD_FAILED` 或 `UNKNOWN_ERROR`
3. 页面展示统一用户文案
4. 服务端日志保留原始异常信息，便于后续排查是否真是账号失效还是链路故障

后续如果要进一步区分“账号失效”和“探测链路故障”，可在统一服务中继续细化错误码，但本轮先统一能力。

---

## 十、测试方案

### 10.1 后端单元测试

重点覆盖：

1. 账号停用时返回 `ACCOUNT_DISABLED`
2. 无认证记录时返回 `AUTH_MISSING`
3. Cookie 解密失败时返回 `COOKIE_DECRYPT_FAILED`
4. Cookie 缺 `_m_h5_tk` 时返回 `COOKIE_TOKEN_MISSING`
5. 缺 `externalUid` 时返回 `EXTERNAL_UID_MISSING`
6. `page.head` 探测失败时返回 `PAGE_HEAD_FAILED`
7. 成功时返回 `OK`
8. 统一服务会同步写回 `cookie_status` 与最近判定字段
9. 工作流运行前校验复用统一服务，不再自己生成分叉逻辑

### 10.2 前端页面测试

重点覆盖：

1. 账号管理页根据统一字段展示 Cookie / 登录状态
2. 连接管理页根据统一字段展示 Cookie 状态
3. 收到 `account_auth_status_changed` 后，两页都能同步更新
4. 工作流运行前校验失败时弹窗显示统一文案

### 10.3 集成验证

建议手工验证以下路径：

1. 正常账号：
   - 账号页显示正常
   - 连接页显示正常
   - 工作流可启动

2. 无效 Cookie 账号：
   - 检查登录后状态变为不可用
   - 账号页、连接页同步更新
   - 工作流被拦截，文案一致

3. 更新 Cookie 后恢复：
   - 保存 Cookie
   - 统一判定重新变为正常
   - 账号页、连接页、工作流账号选择列表同步恢复

4. WebSocket 风控触发：
   - 自动化侧回写统一状态
   - 页面收到统一事件并更新

---

## 十一、实施顺序建议

建议按以下顺序实现：

1. `core-api` 新增统一认证状态服务与结果模型
2. 数据库字段补齐与状态回写
3. 工作流运行前校验切到统一服务
4. 账号列表接口补充统一状态字段
5. 账号管理页改造
6. 连接管理页改造
7. `checkLogin` / `refreshProfile` / 更新 Cookie 接口切换
8. `automation-service` 的风控 / 失效回写出口统一
9. 其他 `getAccounts()` 消费方逐步迁移

---

## 十二、最终设计结论

本轮的核心不是“让工作流别报错”，而是建立**全项目唯一的账号 Cookie / 登录状态判定能力**：

1. 判定逻辑统一在后端服务中
2. 状态结果结构化，兼顾机器判断与用户文案
3. 所有会使用或判断登录态的入口都复用同一服务
4. 新判定结果会统一回写并广播，驱动账号管理、连接管理、工作流和其他相关页面同步更新

这样才能真正解决“账号页正常、工作流异常、连接页又是另一套口径”的问题。
