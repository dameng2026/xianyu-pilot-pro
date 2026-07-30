-- =============================================================================
-- V1.63__add_card_group_sku_property_key.sql
-- =============================================================================
-- 功能：为 card_group 表新增 sku_property_key 字段，支持 SKU 专属卡密池。
--
-- 背景：
--   多规格商品自动发货功能需要支持"按 SKU 隔离卡密池"。
--   card_group.sku_property_key 为空 → 通用卡密池（现有行为，服务所有 SKU）
--   card_group.sku_property_key 非空 → SKU 专属卡密池（值为 xianyu_goods_sku.property_key）
--
-- 兼容性：
--   - MySQL 8.0 不支持 "ADD COLUMN IF NOT EXISTS"，使用 INFORMATION_SCHEMA 动态 SQL
--   - 字段可为空，现有卡密组不受影响（向后兼容）
-- =============================================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'card_group' AND COLUMN_NAME = 'sku_property_key');

SET @sql = IF(@col_exists = 0,
  'ALTER TABLE card_group ADD COLUMN sku_property_key VARCHAR(512) NULL COMMENT ''SKU专属卡密池的规格键（对应 xianyu_goods_sku.property_key，为空=通用卡密池）''',
  'SELECT 1');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 为按 sku_property_key 查询添加索引（可选，提升匹配效率）
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'card_group' AND INDEX_NAME = 'idx_card_group_sku_property_key');

SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_card_group_sku_property_key ON card_group(tenant_id, sku_property_key)',
  'SELECT 1');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
