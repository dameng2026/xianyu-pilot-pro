-- V1.21: 为 mall_product 表新增 copy 字段（商品文案，供 AI 改写板块使用）
-- 该字段为 AI 改写源数据，与 title 配合生成新的商品文案和标题，再由生图板块生成封面图
-- 仅追加列，不修改已有列，不影响现有数据
ALTER TABLE mall_product ADD COLUMN copy TEXT NULL COMMENT '商品文案(供AI改写使用，非面向用户展示)' AFTER content;
