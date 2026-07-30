-- V1.64: 修复 V1.11 索引在 MySQL 8.0 静默失败 + 补充图片记录表复合索引
-- V1.11 使用了 MySQL 8.0 不支持的 ADD INDEX IF NOT EXISTS 语法，导致5个关键索引未创建
-- 本脚本使用 INFORMATION_SCHEMA + PREPARE/EXECUTE 动态 SQL 兼容 MySQL 8.0

-- 1. xianyu_trade_order: idx_xyo_tenant_deleted_created
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order' AND INDEX_NAME = 'idx_xyo_tenant_deleted_created');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_xyo_tenant_deleted_created ON xianyu_trade_order(tenant_id, deleted, created_time, id)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. xianyu_trade_order: idx_xyo_tenant_deleted_account_created
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order' AND INDEX_NAME = 'idx_xyo_tenant_deleted_account_created');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_xyo_tenant_deleted_account_created ON xianyu_trade_order(tenant_id, deleted, account_id, created_time, id)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. xianyu_trade_order: idx_xyo_tenant_deleted_status_created
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order' AND INDEX_NAME = 'idx_xyo_tenant_deleted_status_created');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_xyo_tenant_deleted_status_created ON xianyu_trade_order(tenant_id, deleted, order_status, created_time, id)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4. xianyu_trade_order_item: idx_xyoi_tenant_order_deleted_id
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order_item' AND INDEX_NAME = 'idx_xyoi_tenant_order_deleted_id');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_xyoi_tenant_order_deleted_id ON xianyu_trade_order_item(tenant_id, order_id, deleted, id)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 5. xianyu_goods: idx_xyg_tenant_external_deleted
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_goods' AND INDEX_NAME = 'idx_xyg_tenant_external_deleted');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_xyg_tenant_external_deleted ON xianyu_goods(tenant_id, external_goods_id, deleted)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 6. opportunity_image_history: idx_oih_tenant_deleted_source_created（补充 V1.25 索引缺失 deleted 列）
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'opportunity_image_history' AND INDEX_NAME = 'idx_oih_tenant_deleted_source_created');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_oih_tenant_deleted_source_created ON opportunity_image_history(tenant_id, deleted, source, created_time)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 7. xianyu_goods: idx_xyg_tenant_deleted_account（商品数据分析 NOT EXISTS 子查询优化）
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_goods' AND INDEX_NAME = 'idx_xyg_tenant_deleted_account');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_xyg_tenant_deleted_account ON xianyu_goods(tenant_id, deleted, account_id)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 8. xianyu_account: idx_xya_tenant_id_deleted（NOT EXISTS 子查询覆盖索引）
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_account' AND INDEX_NAME = 'idx_xya_tenant_id_deleted');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_xya_tenant_id_deleted ON xianyu_account(tenant_id, id, deleted)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
