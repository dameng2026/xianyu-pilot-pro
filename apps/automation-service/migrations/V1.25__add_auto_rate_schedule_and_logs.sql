-- 自动补评价功能：账号级执行时间配置 + 执行日志
-- 1) 为 xianyu_account_auto_rate_config 增加 schedule_hour 字段（每天几点执行，0-23，默认 9 点）
-- 2) 新增 xianyu_auto_rate_log 表，记录每次自动评价的执行结果（成功/跳过/失败 + 详情）
-- 全部为非破坏性 DDL，可幂等执行。

-- 1. 为自动评价配置表增加执行时间字段
ALTER TABLE `xianyu_account_auto_rate_config`
    ADD COLUMN IF NOT EXISTS `schedule_hour` INT NOT NULL DEFAULT 9 COMMENT '每天执行时间（小时，0-23），默认 9 点';

-- 索引：便于调度器按 (enabled, schedule_hour) 检索需要执行的账号
CREATE INDEX IF NOT EXISTS `idx_xyaarc_enabled_hour`
    ON `xianyu_account_auto_rate_config` (`enabled`, `schedule_hour`, `deleted`);

-- 2. 自动评价执行日志表
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
