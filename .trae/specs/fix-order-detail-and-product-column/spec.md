# 订单详情报错修复与商品信息列优化 Spec

## Why

点击订单列表中的"查看详情"按钮时，前端收到"系统繁忙，请稍后重试，错误编号：web-mr5y99da-bge6gtcx"错误，导致订单详情面板无法展示。同时，订单列表的商品信息列格式需要优化为"封面图 + 商品名称（商品ID）"的紧凑展示。

## What Changes

- 修复 `delivery_record` 表缺失 4 个列（`delivery_method`、`quantity_requested`、`quantity_sent`、`platform_sync_time`）导致的 SQL 异常。`DataInitializer` 启动时自动执行 `ALTER TABLE ADD COLUMN` 迁移。
- 优化订单列表商品信息列：将"商品标题"和"商品ID:xxx"两行展示改为"封面图 + 商品名称（商品ID）"单行内联格式。

## Impact

- Affected code:
  - `apps/core-api/src/main/java/com/xianyu/admin/config/DataInitializer.java` — 数据库迁移
  - `apps/user-web/src/pages/OrdersPage.vue` — 商品信息列模板与样式

## ADDED Requirements

### Requirement: delivery_record 表结构完整性

系统 SHALL 在启动时自动检测并补齐 `delivery_record` 表中 `delivery_method`、`quantity_requested`、`quantity_sent`、`platform_sync_time` 四个列，确保 `XianyuTradeOrderService.enrichDeliverySnapshot()` 的 SQL 查询不会因列不存在而抛出异常。

#### Scenario: 首次启动迁移
- **WHEN** 应用启动且 `delivery_record` 表缺少上述任一列
- **THEN** `DataInitializer` 通过 `addColumnIfMissing` 自动添加该列
- **AND** 启动日志无 SQL 异常

#### Scenario: 详情接口正常返回
- **WHEN** 用户点击"查看详情"
- **THEN** `GET /api/orders/{id}` 返回 `code=200`
- **AND** 响应体包含 `deliveryMethod`、`deliveryStatus`、`quantityRequested`、`quantitySent`、`platformSyncTime` 字段

## MODIFIED Requirements

### Requirement: 订单列表商品信息列展示

订单列表的商品信息列 SHALL 以"封面图 + 商品名称（商品ID）"格式展示每个商品项。

#### Scenario: 有商品ID的商品
- **WHEN** 订单商品项有 `externalGoodsId` 且有 `goodsTitle`
- **THEN** 显示封面缩略图（40x40）
- **AND** 商品名称后紧跟括号包裹的商品ID，如"iPhone 15 Pro Max（12345678）"

#### Scenario: 无商品ID的商品
- **WHEN** 订单商品项缺少 `externalGoodsId`
- **THEN** 仅显示封面缩略图和商品名称，不显示括号

#### Scenario: 无封面图
- **WHEN** 商品项缺少 `goodsImage`
- **THEN** 不渲染 `<img>` 标签，仅显示文字部分
