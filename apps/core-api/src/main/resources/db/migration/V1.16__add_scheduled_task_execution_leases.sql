-- Durable scheduled-task execution ownership for multi-replica workers.
-- A worker must atomically claim a due task, renew its lease from an
-- independent connection, and condition every terminal update on lease_token.

CREATE TABLE IF NOT EXISTS `scheduled_task` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL,
    `account_id` BIGINT NULL,
    `task_type` VARCHAR(80) NOT NULL,
    `task_name` VARCHAR(200) NULL,
    `cron_expression` VARCHAR(120) NULL,
    `config_json` TEXT NULL,
    `enabled` TINYINT NOT NULL DEFAULT 1,
    `last_run_time` DATETIME(6) NULL,
    `next_run_time` DATETIME(6) NULL,
    `last_status` VARCHAR(40) NULL,
    `last_result` TEXT NULL,
    `last_started_time` DATETIME(6) NULL,
    `last_finished_time` DATETIME(6) NULL,
    `lease_token` CHAR(32) NULL,
    `lease_owner` VARCHAR(120) NULL,
    `lease_expires_at` DATETIME(6) NULL,
    `run_attempt_count` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `consecutive_failure_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted` TINYINT NOT NULL DEFAULT 0,
    KEY `idx_task_tenant` (`tenant_id`),
    KEY `idx_task_enabled` (`enabled`),
    KEY `idx_scheduled_task_due_claim` (`enabled`, `deleted`, `next_run_time`, `lease_expires_at`),
    KEY `idx_scheduled_task_tenant_lease` (`tenant_id`, `lease_token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'last_status') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `last_status` VARCHAR(40) NULL AFTER `next_run_time`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'last_result') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `last_result` TEXT NULL AFTER `last_status`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'last_started_time') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `last_started_time` DATETIME(6) NULL AFTER `last_result`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'last_finished_time') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `last_finished_time` DATETIME(6) NULL AFTER `last_started_time`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'lease_token') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `lease_token` CHAR(32) NULL AFTER `last_finished_time`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'lease_owner') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `lease_owner` VARCHAR(120) NULL AFTER `lease_token`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'lease_expires_at') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `lease_expires_at` DATETIME(6) NULL AFTER `lease_owner`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'run_attempt_count') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `run_attempt_count` BIGINT UNSIGNED NOT NULL DEFAULT 0 AFTER `lease_expires_at`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND COLUMN_NAME = 'consecutive_failure_count') = 0,
    'ALTER TABLE `scheduled_task` ADD COLUMN `consecutive_failure_count` INT UNSIGNED NOT NULL DEFAULT 0 AFTER `run_attempt_count`',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.STATISTICS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND INDEX_NAME = 'idx_scheduled_task_due_claim') = 0,
    'CREATE INDEX `idx_scheduled_task_due_claim` ON `scheduled_task` (`enabled`, `deleted`, `next_run_time`, `lease_expires_at`)',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
    (SELECT COUNT(*) FROM information_schema.STATISTICS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'scheduled_task' AND INDEX_NAME = 'idx_scheduled_task_tenant_lease') = 0,
    'CREATE INDEX `idx_scheduled_task_tenant_lease` ON `scheduled_task` (`tenant_id`, `lease_token`)',
    'SELECT 1'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
