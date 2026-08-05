# 前台更新日志维护规则

> **强制规则**：任何 AI 模型在执行"上线"动作前，必须先完整阅读本文件，并按本文件流程对比代码差异、维护更新日志。
> 未经对比代码差异并更新 `apps/user-web/src/data/releaseNotes.js` 与 `apps/user-web/package.json` 的 version，不得执行上线。

## 一、功能概述

前台「系统设置 → 关于 → 更新日志」板块用于向用户展示版本迭代与功能演进记录。

- **展示页面**：`apps/user-web/src/pages/settings/AboutSettings.vue`
- **数据源**：`apps/user-web/src/data/releaseNotes.js`（唯一数据源，最新版本在前）
- **版本号注入**：`apps/user-web/package.json` 的 `version` 字段 → vite 注入 `__APP_VERSION__` → `apps/user-web/src/utils/appMeta.js` 的 `APP_VERSION`
- **后端接口**：`apps/core-api/src/main/resources/release-notes.json` 是发布时从 `releaseNotes.js` 生成的同步产物；
  core-api 通过 `GET /api/content/release-notes` 对外提供，AI 客服「小梦」与前台「关于」页共用该接口。
  每次修改 `releaseNotes.js` 后必须重新生成该 JSON（见步骤 4），否则 AI 客服查询到的是旧版本日志。

## 二、版本号递增规则（语义化版本 SemVer）

版本号格式 `MAJOR.MINOR.PATCH`（如 `1.0.0`），按本次上线的前台功能变动规模递增：

| 变动类型 | type 字段 | 触发条件 | 版本号递增 | 示例 | 展示色调 |
|---------|-----------|---------|-----------|------|---------|
| 问题修复 | `patch` | bug 修复、文案微调、样式小修补 | 修订号 +1 | `1.0.0 → 1.0.1` | 绿色 |
| 功能更新 | `minor` | 新增功能、功能优化升级、交互重构 | 次版本号 +1 | `1.0.0 → 1.1.0` | 蓝色 |
| 大版本 | `major` | 大量功能改变、架构调整、不兼容更新 | 主版本号 +1 | `1.0.0 → 2.0.0` | 橙色 |

**判定优先级**：major > minor > patch。一次上线同时含多种变动时，按最高等级递增。例如同时有 bug 修复和新增功能，按 minor 递增。

**纯后台变动不递增**：若本次上线仅修改 `apps/core-api`、`apps/automation-service`、`apps/crawler-service`、`apps/admin-web` 等非前台代码，且前台 `apps/user-web` 无任何功能变动，则不新增日志条目、不递增版本号（仅在日志无变化时跳过整个流程）。

## 三、更新日志数据结构

`apps/user-web/src/data/releaseNotes.js` 中每条记录结构：

```javascript
{
  version: '1.0.1',          // 不带 v 前缀，与 package.json version 一致
  date: '2026-07-20',        // 发布日期 YYYY-MM-DD
  type: 'patch',             // 'major' | 'minor' | 'patch'
  title: '标题',             // 简短版本标题
  summary: '一句话概述',      // 该版本变更概述
  changes: [                 // 分类变更列表，按需使用「新增/优化/修复/移除」等标签
    { label: '新增', items: ['xxx 功能'] },
    { label: '优化', items: ['xxx 体验'] },
    { label: '修复', items: ['xxx 问题'] }
  ],
  remark: '可选备注'          // 可选，重要提示
}
```

**字段约束**：
1. `version` 必须与 `apps/user-web/package.json` 的 `version` 字段保持一致
2. 新条目必须放在 `releaseNotes` 数组最前面（最新在上）
3. `changes.items` 每条应面向用户可感知的功能变动，避免出现纯技术实现细节（如"重构了某 hook"），应转为用户视角（如"优化了表格加载性能"）
4. 不得删除历史条目，只追加

## 四、上线前代码对比流程（强制）

### 4.1 对比方案：私人 git 仓库

项目本地已在 git 管理下，但默认无远程仓库。采用**私人 git 仓库作为「已上线代码」权威快照**的方案：

- 私人仓库（GitHub / Gitee 私有仓库）保存每次上线后的代码快照
- 每次上线 = 一次 commit + push 到私人仓库
- 下次开发完成后、上线前，对比私人仓库的最新状态与本地工作区，即可找出"本次将上线的前台变动"

### 4.2 首次配置（仅需一次）

若 `git remote -v` 输出为空，说明尚未配置私人仓库，需先完成配置：

```bash
# 1. 在 GitHub / Gitee 创建一个私有仓库（空仓库，不要初始化 README）
# 2. 添加为 remote（推荐命名为 mirror，避免与可能的正式仓库冲突）
git remote add mirror <私有仓库地址>
# 3. 首次推送当前已上线代码作为基线
git push -u mirror master
```

若已存在 remote，跳过本步。

### 4.3 每次上线前的对比与日志更新流程

AI 在执行上线动作前，必须按以下步骤操作：

```bash
# 步骤 1：拉取私人仓库最新状态（已上线代码快照）
git fetch mirror

# 步骤 2：对比前台代码差异（仅关注 apps/user-web）
git diff mirror/master -- apps/user-web
```

**步骤 3：分析 diff，判定变动类型**

AI 需阅读 diff 输出，识别前台功能变动：
- 仅修复 bug / 文案 / 样式小修补 → `patch`
- 新增功能 / 功能优化升级 / 交互重构 → `minor`
- 大量功能改变 / 架构调整 → `major`
- 无前台功能变动（仅后台/构建配置变动）→ 跳过日志更新，直接上线

**步骤 4：递增版本号并追加日志条目**

按判定结果：
1. 在 `apps/user-web/src/data/releaseNotes.js` 的 `releaseNotes` 数组最前面追加新条目
2. 同步更新 `apps/user-web/src/data/releaseNotes.js` 的 `CURRENT_VERSION` 常量
3. 同步更新 `apps/user-web/package.json` 的 `version` 字段为新版本号
4. 重新生成 core-api 更新日志资源（从 `releaseNotes.js` 同步）：

   ```powershell
   @'
   import { pathToFileURL } from 'node:url';
   import path from 'node:path';
   const m = await import(pathToFileURL(path.resolve('apps/user-web/src/data/releaseNotes.js')).href);
   const payload = { currentVersion: m.CURRENT_VERSION, updatedAt: new Date().toISOString().slice(0, 10), releaseNotes: m.releaseNotes };
   const fs = await import('node:fs');
   fs.writeFileSync(path.resolve('apps/core-api/src/main/resources/release-notes.json'), JSON.stringify(payload, null, 2), 'utf8');
   '@ | node --input-type=module -
   ```

**步骤 5：提交并推送私人仓库**

```bash
git add apps/user-web/src/data/releaseNotes.js apps/user-web/package.json apps/core-api/src/main/resources/release-notes.json
git commit -m "chore(release): bump user-web to <新版本号>"
git push mirror master
```

**步骤 6：执行正式上线**

确认日志已更新且私人仓库已推送后，方可执行正式上线流程。

### 4.4 无 remote 时的降级处理（本地 git tag 方案）

若 `git remote -v` 为空且用户尚未配置私人仓库，AI 必须改用**本地 git tag** 标记每次上线点，纯本地完成对比，不依赖任何远程仓库：

**原理**：每次上线后打一个 `released/<版本号>` 的标签指向当时已上线的 commit；下次上线前对比「最新 released 标签」与「当前工作区」即可找出本次将上线的前台变动。

**首次基线（仅当仓库中尚无任何 `released/*` 标签时执行一次）**：

```bash
# 确认无 released 标签
git tag --list 'released/*'
# 以当前已上线代码作为 v1.0.0 基线打标签
git tag released/1.0.0
```

**每次上线前的对比与日志更新流程（替代 4.3）**：

```bash
# 步骤 1：找到最新已上线标签
LATEST_TAG=$(git tag --list 'released/*' --sort=-v:refname | head -1)
# 若为空，说明尚未建立基线，先按「首次基线」步骤打 released/1.0.0

# 步骤 2：对比前台代码差异（仅关注 apps/user-web）
git diff $LATEST_TAG -- apps/user-web
```

步骤 3、4 与 4.3 相同（分析 diff 判定变动类型、递增版本号并追加日志条目）。

**步骤 5：提交并打新标签（替代推送远程）**：

```bash
git add apps/user-web/src/data/releaseNotes.js apps/user-web/package.json
git commit -m "chore(release): bump user-web to <新版本号>"
git tag released/<新版本号>
```

步骤 6：执行正式上线。

**配置私人仓库后的迁移**：若后续用户配置了私人仓库（按 4.2），可一次性推送所有本地标签 `git push mirror --tags`，之后切换为 4.3 的远程对比流程，本地标签作为补充保留。

### 4.5 方案选择优先级

1. 若 `git remote -v` 含 `mirror` 或其他已配置的远程 → 使用 4.3 远程对比流程
2. 否则若本地存在 `released/*` 标签 → 使用 4.4 本地 tag 降级流程
3. 否则（既无 remote 也无标签）→ AI 必须先执行 4.4 的「首次基线」打 `released/1.0.0`，再继续上线流程，不得跳过对比直接上线
