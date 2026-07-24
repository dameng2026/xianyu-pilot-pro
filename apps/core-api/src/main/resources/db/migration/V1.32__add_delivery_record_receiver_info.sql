-- ============================================================
-- V1.32__add_delivery_record_receiver_info.sql
-- 给 delivery_record 表补齐 receiver_info JSON 列
--
-- 背景：
-- ws_delivery_handler.py 的 _has_existing_realtime_delivery (1230 行 SELECT)
-- 与 _insert_delivery_record (1938 行 INSERT) 都使用 receiver_info 字段
-- 存储 {sid, pnmId, buyerUserId, xyGoodsId, buyerUserName} JSON，
-- 用于同一会话同一商品的并发去重（持锁后二次检查），消除 TOCTOU 竞态导致的重复发货。
-- 但线上数据库从未添加过该列，导致实时自动发货一直抛 OperationalError，
-- 用户配置了卡密发货后下单仍不发货。
--
-- 修复方式：纯加列，非破坏性，幂等可重入。
-- ============================================================

-- 1. 添加 receiver_info JSON 列
SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_record' AND COLUMN_NAME = 'receiver_info');
SET @sql_add_col := IF(@col_exists = 0,
    'ALTER TABLE delivery_record ADD COLUMN receiver_info JSON DEFAULT NULL COMMENT ''收件人信息JSON：{sid,pnmId,buyerUserId,xyGoodsId,buyerUserName}（实时发货并发去重用）''',
    'SELECT 1');
PREPARE stmt_add_col FROM @sql_add_col;
EXECUTE stmt_add_col;
DEALLOCATE PREPARE stmt_add_col;

-- 2. 添加 (tenant_id, account_id, delivery_timing) 复合索引，加速 _has_existing_realtime_delivery 查询
--    原查询条件：tenant_id + account_id + delivery_timing + JSON_EXTRACT(receiver_info, ...) + status IN (1,2)
--    前三个等值字段建复合索引可显著减少扫描行数
SET @idx_exists := (SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_record'
    AND INDEX_NAME = 'idx_delivery_record_tenant_account_timing');
SET @sql_add_idx := IF(@idx_exists = 0,
    'ALTER TABLE delivery_record ADD INDEX idx_delivery_record_tenant_account_timing (tenant_id, account_id, delivery_timing)',
    'SELECT 1');
PREPARE stmt_add_idx FROM @sql_add_idx;
EXECUTE stmt_add_idx;
DEALLOCATE PREPARE stmt_add_idx;
