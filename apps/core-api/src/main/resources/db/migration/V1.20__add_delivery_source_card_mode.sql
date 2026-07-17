-- ============================================================
-- V1.20__add_delivery_source_card_mode.sql
-- 货源库支持卡密发货模式：
--   delivery_mode  VARCHAR(20)  'text'=文本发货(默认) / 'card'=卡密发货
--   card_group_id  BIGINT       卡密发货时关联的 card_group.id
-- 非破坏性变更：仅追加列，已有数据默认 delivery_mode='text'，card_group_id=NULL
-- ============================================================

ALTER TABLE `delivery_text_source`
    ADD COLUMN `delivery_mode` VARCHAR(20) NOT NULL DEFAULT 'text' COMMENT '发货类型：text=文本发货 / card=卡密发货';

ALTER TABLE `delivery_text_source`
    ADD COLUMN `card_group_id` BIGINT DEFAULT NULL COMMENT '卡密发货时关联的卡密分组ID（card_group.id）';

-- 卡密发货场景按 card_group_id 关联查询卡密库存，加索引优化联表
CREATE INDEX `idx_dts_card_group` ON `delivery_text_source`(`tenant_id`, `delivery_mode`, `card_group_id`);
