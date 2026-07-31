-- V1.27 修复 V1.25 在 MySQL 8.0/8.4 上静默失败的 schema 对象
-- ============================================================================
-- 背景：V1.25 使用了 MySQL 不支持的 `ADD COLUMN IF NOT EXISTS` 和 `CREATE INDEX IF NOT EXISTS`
-- （这是 MariaDB 专有语法），在 MySQL 8.0/8.4 上会静默失败，导致：
--   1. xianyu_account_auto_rate_config 缺少 schedule_hour 列
--   2. xianyu_account_auto_rate_config 缺少 idx_xyaarc_enabled_hour 索引
-- 引发后端服务启动失败（project_memory.md 已记录该事故）。
--
-- 本脚本使用 INFORMATION_SCHEMA + PREPARE/EXECUTE 动态 SQL 实现幂等创建，
-- 参考 V1.64、V1.49 的写法，确保在 MySQL 8.0/8.4 上可重入、可重复执行。
-- ============================================================================

-- 1. 修复 xianyu_account_auto_rate_config.schedule_hour 列
-- 使用 INFORMATION_SCHEMA.COLUMNS 检查列是否存在，不存在则动态执行 ADD COLUMN
DROP PROCEDURE IF EXISTS `pr_v1_27_add_schedule_hour`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_27_add_schedule_hour`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'xianyu_account_auto_rate_config'
          AND COLUMN_NAME = 'schedule_hour'
    ) THEN
        ALTER TABLE `xianyu_account_auto_rate_config`
            ADD COLUMN `schedule_hour` INT NOT NULL DEFAULT 9 COMMENT '每天执行时间（小时，0-23），默认 9 点';
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_27_add_schedule_hour`();
DROP PROCEDURE IF EXISTS `pr_v1_27_add_schedule_hour`;

-- 2. 修复 idx_xyaarc_enabled_hour 索引
-- 使用 INFORMATION_SCHEMA.STATISTICS 检查索引是否存在，不存在则动态创建
DROP PROCEDURE IF EXISTS `pr_v1_27_add_index_enabled_hour`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_27_add_index_enabled_hour`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'xianyu_account_auto_rate_config'
          AND INDEX_NAME = 'idx_xyaarc_enabled_hour'
    ) THEN
        ALTER TABLE `xianyu_account_auto_rate_config`
            ADD INDEX `idx_xyaarc_enabled_hour` (`enabled`, `schedule_hour`, `deleted`);
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_27_add_index_enabled_hour`();
DROP PROCEDURE IF EXISTS `pr_v1_27_add_index_enabled_hour`;

-- 3. 修复 card_group.sku_property_key 列（project_memory.md 记录的另一个静默失败项）
-- 若该表/列已存在则跳过，不存在则添加
DROP PROCEDURE IF EXISTS `pr_v1_27_add_sku_property_key`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_27_add_sku_property_key`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'card_group'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'card_group'
          AND COLUMN_NAME = 'sku_property_key'
    ) THEN
        ALTER TABLE `card_group`
            ADD COLUMN `sku_property_key` VARCHAR(100) NULL COMMENT '卡密 SKU 属性 Key（用于匹配闲鱼商品 SKU）';
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_27_add_sku_property_key`();
DROP PROCEDURE IF EXISTS `pr_v1_27_add_sku_property_key`;

-- 4. 确保 xianyu_auto_rate_log 表存在（V1.25 第 15 行的 CREATE TABLE IF NOT EXISTS 是合法 MySQL 语法，
--    通常会成功，但为完整性这里做一次幂等校验）
CREATE TABLE IF NOT EXISTS `xianyu_auto_rate_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `account_id` BIGINT NOT NULL COMMENT '闲鱼账号ID',
    `run_time` DATETIME(6) NOT NULL COMMENT '本次执行时间',
    `schedule_hour` INT NULL COMMENT '配置的执行时间（0-23），手动触发时为 NULL',
    `trigger_type` VARCHAR(20) NOT NULL DEFAULT 'scheduled' COMMENT '触发方式：scheduled=定时, manual=手动',
    `status` VARCHAR(20) NOT NULL DEFAULT 'success' COMMENT '执行结果：success=成功, skip=跳过, failed=失败, partial=部分成功',
    `total_pending` INT NOT NULL DEFAULT 0 COMMENT '本次发现的待评价订单数',
    `total_success` INT NOT NULL DEFAULT 0 COMMENT '成功评价数',
    `total_failed` INT NOT NULL DEFAULT 0 COMMENT '失败评价数',
    `total_skipped` INT NOT NULL DEFAULT 0 COMMENT '跳过订单数（已评价或不可评价）',
    `error_message` VARCHAR(500) NULL COMMENT '错误信息（脱敏）',
    `details_json` TEXT NULL COMMENT '明细 JSON（每条订单的处理结果，便于排查）',
    `duration_seconds` FLOAT NOT NULL DEFAULT 0 COMMENT '本次执行耗时（秒）',
    `deleted` TINYINT NOT NULL DEFAULT 0,
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_arl_tenant_account_time` (`tenant_id`, `account_id`, `run_time`),
    KEY `idx_arl_tenant_time` (`tenant_id`, `run_time`),
    KEY `idx_arl_status` (`tenant_id`, `status`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动补评价执行日志';
