-- ============================================================
-- V1.31__delivery_goods_config_unique_constraint.sql
-- 规范 delivery_goods_config 表结构：唯一约束 + JSON 列类型 + 辅助索引
--
-- 背景：V1.7 建表时只有普通索引 idx_dgc_tenant_goods(tenant_id, goods_id, deleted)，
-- 未定义唯一约束。线上环境手动添加了 uk_dgc_tenant_goods(tenant_id, goods_id) 唯一约束，
-- 但该约束不含 deleted 字段，导致软删除记录(deleted=1)阻止新记录 INSERT，
-- 触发 DuplicateKeyException（商品发货配置保存失败）。
--
-- 代码层面已用 INSERT ... ON DUPLICATE KEY UPDATE 兼容（DeliveryGoodsConfigService.persist），
-- 此迁移确保所有环境表结构一致。
-- ============================================================

-- 1. 将 config_json 列类型统一为 JSON NOT NULL（V1.7 定义为 TEXT）
SET @col_type := (SELECT DATA_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_goods_config' AND COLUMN_NAME = 'config_json');
SET @sql_json := IF(@col_type != 'json',
    'ALTER TABLE delivery_goods_config MODIFY COLUMN config_json JSON NOT NULL COMMENT ''发货配置JSON：{payDelivery:{...}, confirmDelivery:{...}, reviewDelivery:{...}}''',
    'SELECT 1');
PREPARE stmt_json FROM @sql_json;
EXECUTE stmt_json;
DEALLOCATE PREPARE stmt_json;

-- 2. 清理重复的软删除记录，为添加唯一约束做准备
-- 2a. 物理删除所有 deleted=1 的记录（配置表的软删除记录无审计价值）
DELETE FROM delivery_goods_config WHERE deleted = 1;

-- 2b. 同一 (tenant_id, goods_id) 有多条 deleted=0 的记录时，保留 id 最大的，其余物理删除
DELETE dgc1 FROM delivery_goods_config dgc1
INNER JOIN (
    SELECT tenant_id, goods_id, MAX(id) AS max_id
    FROM delivery_goods_config
    WHERE deleted = 0
    GROUP BY tenant_id, goods_id
    HAVING COUNT(*) > 1
) dup ON dgc1.tenant_id = dup.tenant_id
    AND dgc1.goods_id = dup.goods_id
    AND dgc1.id < dup.max_id
WHERE dgc1.deleted = 0;

-- 3. 添加唯一约束 uk_dgc_tenant_goods (tenant_id, goods_id)
SET @uk_exists := (SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_goods_config'
    AND INDEX_NAME = 'uk_dgc_tenant_goods');
SET @sql_uk := IF(@uk_exists = 0,
    'ALTER TABLE delivery_goods_config ADD UNIQUE INDEX uk_dgc_tenant_goods (tenant_id, goods_id)',
    'SELECT 1');
PREPARE stmt_uk FROM @sql_uk;
EXECUTE stmt_uk;
DEALLOCATE PREPARE stmt_uk;

-- 4. 添加 idx_dgc_deleted 辅助索引（按 deleted 字段过滤加速）
SET @idx_deleted_exists := (SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_goods_config'
    AND INDEX_NAME = 'idx_dgc_deleted');
SET @sql_idx := IF(@idx_deleted_exists = 0,
    'ALTER TABLE delivery_goods_config ADD INDEX idx_dgc_deleted (deleted)',
    'SELECT 1');
PREPARE stmt_idx FROM @sql_idx;
EXECUTE stmt_idx;
DEALLOCATE PREPARE stmt_idx;
