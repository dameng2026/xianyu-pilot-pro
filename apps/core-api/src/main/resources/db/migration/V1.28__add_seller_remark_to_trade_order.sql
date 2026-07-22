-- ============================================================
-- V1.28__add_seller_remark_to_trade_order.sql
-- 给 xianyu_trade_order 表添加卖家备注字段（seller_remark）
-- 采用存在性检查模式，保证幂等可重入
-- ============================================================

SET @exist_col := (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order' AND COLUMN_NAME = 'seller_remark');
SET @sql := IF(@exist_col = 0,
    'ALTER TABLE xianyu_trade_order ADD COLUMN seller_remark TEXT DEFAULT NULL COMMENT "卖家备注"',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
