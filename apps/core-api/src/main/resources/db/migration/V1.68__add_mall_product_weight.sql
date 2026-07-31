-- mall_product 加 weight 字段（兼容 MySQL 8.0 的动态 SQL）
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mall_product' AND COLUMN_NAME = 'weight');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE mall_product ADD COLUMN weight INT NOT NULL DEFAULT 0 COMMENT ''展示权重(越大越靠前)''',
    'SELECT ''column weight already exists'' AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 为现有 mall_product 补充默认 weight=0（不影响现有排序）
UPDATE mall_product SET weight = 0 WHERE weight IS NULL;
