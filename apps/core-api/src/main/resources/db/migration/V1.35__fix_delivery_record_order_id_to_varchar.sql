-- ============================================================
-- V1.35__fix_delivery_record_order_id_to_varchar.sql
-- 将 delivery_record.order_id 字段从 bigint 改为 varchar(64)
--
-- 背景：
-- 闲鱼推送的付款消息 reminderUrl 中的 orderId 是超长字符串
-- （例如 "12345678901234567890"，已超过 bigint 有符号上限 9223372036854775807），
-- _insert_delivery_record 传入字符串给 bigint 列时 MySQL 静默写入 NULL，
-- 导致：
--   1. delivery_record.order_id 全部为 NULL
--   2. _has_existing_realtime_delivery 的 Check 1（order_id 精确匹配）永远走不到
--   3. 退到 Check 2（sid+buyer+goods+10分钟窗口），同一会话同商品的多单被误判为重复发货
--   4. 自动发货在第一条付款消息处理后，后续多单全部被跳过，规则匹配步骤根本走不到
--
-- 修复方式：将 order_id 列类型从 bigint 改为 varchar(64)，让闲鱼 orderId 字符串完整写入。
-- 风险评估：非破坏性扩展，bigint 历史数值会安全转换为字符串形式（如 123 → "123"），
--   不丢失数据；相关查询/索引按字符串比较仍可命中历史记录。
-- 幂等：通过 information_schema 检查当前类型，仅当为 bigint 时执行 MODIFY。
-- ============================================================

-- 1. 将 order_id 从 bigint 改为 varchar(64)（仅当当前类型为 bigint 时执行）
SET @col_type := (SELECT DATA_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_record' AND COLUMN_NAME = 'order_id');
SET @sql_modify := IF(@col_type = 'bigint',
    'ALTER TABLE delivery_record MODIFY COLUMN order_id VARCHAR(64) DEFAULT NULL COMMENT ''订单ID（闲鱼orderId为长字符串，bigint溢出会写入NULL，改varchar避免溢出）''',
    'SELECT 1');
PREPARE stmt_modify FROM @sql_modify;
EXECUTE stmt_modify;
DEALLOCATE PREPARE stmt_modify;
