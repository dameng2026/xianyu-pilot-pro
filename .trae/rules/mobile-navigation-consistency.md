# 移动端顶部/底部导航栏一致性规则

> **强制规则**：任何 AI 模型在修改"移动端项目（`apps/user-web` 下所有移动端相关代码，宽度 ≤ 768px 生效范围）"前，必须先完整阅读本文件。
> 顶部导航栏与底部导航栏为**全局组件**，必须保持跨页面一致性，不得因单张设计图的局部差异而擅自更改。
> 本规则与 `release-notes-workflow.md`、`database-migration-on-release.md`、`data-sync-bridge-token.md` 并行生效。

## 一、背景与功能概述

本项目移动端由多位设计人员分别出图，每张设计图所绘制的**顶部导航栏**和**底部导航栏**可能存在不一致的情况（如图标样式、按钮排布、标题位置、配色、高度等差异）。

用户发送给 AI 模型的提示词均是基于**单张设计图**撰写的，因此提示词中描述的顶部/底部导航栏细节可能仅反映该张设计图的局部样式，并不代表项目全局规范。若 AI 模型直接按单张设计图的描述修改全局导航栏组件，将破坏其他移动端页面的视觉一致性，造成事故级 UI Bug。

本规则用于固化"全局导航栏组件不得因单页设计图差异而擅自更改"的纪律。

### 1.1 移动端生效范围

- 触发条件：`apps/user-web/src/App.vue` 中的 `shouldUseMobileLite` 计算属性为 `true` 时（默认屏幕宽度 ≤ 768px 且未强制桌面模式）
- 作用对象：所有移动端页面与组件，包括但不限于：
  - `apps/user-web/src/components/MobileLite.vue`（全局布局）
  - `apps/user-web/src/mobile/` 目录下所有页面组件
  - 任何被移动端引用的公共组件、样式、图标

### 1.2 全局导航栏组件位置

| 组件 | 文件 | 标识 | 作用 |
|------|------|------|------|
| 全局布局容器 | `apps/user-web/src/components/MobileLite.vue` | - | 承载顶部导航、底部导航、左侧抽屉、页面插槽 |
| 顶部导航栏 | `apps/user-web/src/components/MobileLite.vue` | `<header class="m-topbar">` | 固定顶部，含左侧菜单按钮、页面标题、右侧用户区/通知 |
| 左侧抽屉 | `apps/user-web/src/components/MobileLite.vue` | `<aside class="m-drawer">` | 由顶部菜单按钮触发，全局导航入口 |
| 底部导航栏 | `apps/user-web/src/components/MobileLite.vue` | `<nav class="m-tabbar">` | 固定底部，5 个入口：首页、数据面板、快速开始、订单管理、我的 |
| 底部导航高亮逻辑 | `apps/user-web/src/components/MobileLite.vue` | `onNavigate` / `onSubNavigate` | 控制当前激活的底部 tab |
| 导航数据源 | `apps/user-web/src/data/nav.js` | `navGroups` / `settingsTabs` / `settingsKeys` | 抽屉与底部 tab 的结构化数据 |
| 移动端图标库 | `apps/user-web/src/mobile/MobileIcons.js` | - | 顶部/底部/抽屉所用的 SVG 图标 |

## 二、核心约束（违反即为事故级 Bug）

1. **顶部导航栏为全局组件，不得因单页设计图差异而更改**：`<header class="m-topbar">` 的结构、高度、配色、左侧菜单按钮、右侧用户区/通知按钮、标题展示规则在所有移动端页面必须保持一致。即使用户提示词描述的某张设计图顶部导航栏样式与此不同，也不得据此修改全局组件。
2. **底部导航栏为全局组件，不得因单页设计图差异而更改**：`<nav class="m-tabbar">` 的 5 个入口（首页、数据面板、快速开始、订单管理、我的）、图标、文案、排序、高亮规则在所有移动端页面必须保持一致。即使用户提示词描述的某张设计图底部导航栏与此不同，也不得据此修改全局组件。
3. **左侧抽屉为全局组件，不得因单页设计图差异而更改**：`<aside class="m-drawer">` 的宽度、分组结构、入口列表、用户信息区、底部按钮必须保持一致。
4. **个别不在底部导航栏的页面可例外**：若某页面本身不属于底部导航栏 5 个入口之一（如详情页、子页面、设置子页等），且设计图明确要求该页面**不显示底部导航栏**或**使用不同的底部区域**，则可以：
   - 在该页面隐藏底部导航栏（通过 `MobileLite.vue` 提供的 props 或插槽机制控制）
   - 但不得修改 `<nav class="m-tabbar">` 组件本身的样式与结构
5. **确需更改全局导航栏时的强制流程**：若用户**明确要求**修改全局顶部/底部导航栏（而非按某张设计图适配单页），必须：
   - 向用户确认："此修改将影响所有移动端页面的顶部/底部导航栏，确认是全局调整吗？"
   - 同步更新所有移动端页面所依赖的 `MobileLite.vue`、`nav.js`、`MobileIcons.js`
   - 在所有已实现的移动端页面（`apps/user-web/src/mobile/` 下全部文件）回归验证视觉一致性
   - 在更新日志中记录此次全局导航栏变更
6. **提示词中的导航栏描述视为单页样式，不视为全局规范**：用户基于设计图撰写的提示词中，若提到顶部/底部导航栏的图标、文案、颜色、布局细节，默认仅适用于该张设计图所对应的页面，AI 不得将其推广到全局组件。
7. **不得在页面组件内重复实现顶部/底部导航栏**：移动端页面组件（如 `MobileHome.vue`、`MobileData.vue` 等）不得自行实现 `<header>` 顶部栏或 `<nav>` 底部栏，必须复用 `MobileLite.vue` 的全局导航。页面组件只负责填充 `MobileLite.vue` 提供的内容插槽。

## 三、修改前检查流程（强制）

### 3.1 判断本次修改是否涉及导航栏

在开始任何移动端修改前，必须先回答以下问题：

1. 本次修改的页面是否属于底部导航栏 5 个入口之一（首页、数据面板、快速开始、订单管理、我的）？
2. 用户提示词是否描述了顶部导航栏或底部导航栏的样式、图标、文案、布局？
3. 本次修改是否需要触碰 `MobileLite.vue`、`nav.js`、`MobileIcons.js` 中的导航相关代码？

### 3.2 根据判断结果分流

| 情况 | 处理 |
|------|------|
| 修改的页面属于底部导航栏入口，且提示词未要求改导航栏 | ✅ 仅修改页面内容插槽，**不触碰** `MobileLite.vue` 的 `.m-topbar` / `.m-tabbar` / `.m-drawer` |
| 修改的页面属于底部导航栏入口，但提示词描述了不同的导航栏样式 | ❌ **不得修改全局导航栏**。按当前全局导航栏规范实现页面内容，并在交付说明中告知用户：提示词中的导航栏样式与全局规范不一致，已保留全局规范，如需全局调整请单独提出 |
| 修改的页面不属于底部导航栏入口（详情页/子页等），设计图要求隐藏底部导航 | ✅ 可通过 `MobileLite.vue` 提供的机制隐藏底部导航，但**不修改** `.m-tabbar` 组件本身 |
| 用户明确要求全局调整顶部/底部导航栏 | ⚠️ 按"二、核心约束第 5 条"的强制流程执行，先向用户确认全局影响范围 |
| 修改涉及 `MobileLite.vue` 的非导航部分（如插槽、布局容器） | ✅ 可修改，但不得影响 `.m-topbar` / `.m-tabbar` / `.m-drawer` 的渲染逻辑与样式 |

### 3.3 验证一致性

修改完成后，必须确认：

```bash
# 确认全局导航栏组件未被意外修改（对比 git diff）
git diff -- apps/user-web/src/components/MobileLite.vue
git diff -- apps/user-web/src/data/nav.js
git diff -- apps/user-web/src/mobile/MobileIcons.js
```

若本次修改本不应触碰全局导航栏，但上述 diff 出现 `.m-topbar` / `.m-tabbar` / `.m-drawer` / `navGroups` / 底部 tab 相关变更，**立即回滚**并重新审视修改方案。

## 四、设计图差异处理建议

当某张设计图的顶部/底部导航栏与项目当前全局规范不一致时，AI 模型应：

1. **优先保留全局规范**：按项目当前 `MobileLite.vue` 的导航栏实现为准，不按设计图修改导航栏。
2. **在交付说明中明确告知差异**：例如"设计图顶部导航栏右侧显示 XX 图标，但全局规范为 YY，已按全局规范实现，如需全局调整请单独提出"。
3. **仅实现页面内容部分**：设计图中的页面主体内容（卡片、图表、列表等）按设计图还原，导航栏部分保持全局一致。
4. **如用户坚持按设计图修改**：按"二、核心约束第 5 条"的强制流程执行，先确认全局影响，再统一修改。

## 五、相关文件清单

| 文件 | 作用 |
|------|------|
| `apps/user-web/src/components/MobileLite.vue` | 全局移动端布局，承载顶部导航 `.m-topbar`、底部导航 `.m-tabbar`、左侧抽屉 `.m-drawer` |
| `apps/user-web/src/data/nav.js` | 导航数据源：`navGroups`（抽屉分组）、`settingsTabs`、`settingsKeys`、底部 tab 配置 |
| `apps/user-web/src/mobile/MobileIcons.js` | 移动端 SVG 图标库，顶部/底部/抽屉图标来源 |
| `apps/user-web/src/App.vue` | `shouldUseMobileLite` 计算属性，决定是否进入移动端布局 |
| `apps/user-web/src/mobile/MobileHome.vue` | 移动端首页（填充 MobileLite 内容插槽） |
| `apps/user-web/src/mobile/MobileData.vue` | 移动端数据面板主页 |
| `apps/user-web/src/mobile/MobileDataDetail.vue` | 移动端数据面板详情页（非底部 tab 入口，可隐藏底部导航） |
| `apps/user-web/src/mobile/MobileProfile.vue` | 移动端"我的"页面 |
| `apps/user-web/src/mobile/MobileMessages.vue` | 移动端消息页 |
| `apps/user-web/src/mobile/MobileAutomation.vue` | 移动端自动化页 |
| `apps/user-web/src/mobile/MobileProducts.vue` | 移动端商品页 |
| `apps/user-web/src/mobile/MobileAccounts.vue` | 移动端账号页 |
