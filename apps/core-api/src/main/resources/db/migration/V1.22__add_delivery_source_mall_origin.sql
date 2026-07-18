-- ============================================================
-- V1.22__add_delivery_source_mall_origin.sql
-- 货源库支持「商城购买货源」来源标记：
--   from_mall         TINYINT(1)  0=自有货源(默认) / 1=商城购买货源
--   mall_product_id   BIGINT      商城货源关联的 mall_product.id（from_mall=1 时使用）
-- 商城购买货源的标题与正文不存副本，读取时 JOIN mall_product 表实时获取最新内容，
-- 以保证后台货源商城更新后，用户货源库内容同步变更。
-- 非破坏性变更：仅追加列，已有数据默认 from_mall=0、mall_product_id=NULL
-- ============================================================

ALTER TABLE `delivery_text_source`
    ADD COLUMN `from_mall` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否来自商城购买: 0=自有货源, 1=商城购买货源';

ALTER TABLE `delivery_text_source`
    ADD COLUMN `mall_product_id` BIGINT DEFAULT NULL COMMENT '商城货源关联的商品ID (mall_product.id)，from_mall=1 时使用';

-- 商城货源按 (tenant_id, from_mall, mall_product_id) 检索重复购买与列表过滤
CREATE INDEX `idx_dts_mall_product` ON `delivery_text_source`(`tenant_id`, `from_mall`, `mall_product_id`);
