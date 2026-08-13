-- V1.34 退款关单（退款订单注销）配置
-- ============================================================================
-- 对齐同类项目 refund_cancel 能力：
--   1. xianyu_account 增加退款关单开关 / 外部注销URL / 超时时间
--   2. xianyu_trade_order 增加是否已注销与错误原因
-- 使用 INFORMATION_SCHEMA + 存储过程实现幂等。
-- ============================================================================

DROP PROCEDURE IF EXISTS `pr_v1_34_account_refund_cancel_enabled`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_34_account_refund_cancel_enabled`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_account'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_account' AND COLUMN_NAME = 'refund_cancel_enabled'
    ) THEN
        ALTER TABLE `xianyu_account`
            ADD COLUMN `refund_cancel_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '退款关单开关：1开启 0关闭' AFTER `remark`;
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_34_account_refund_cancel_enabled`();
DROP PROCEDURE IF EXISTS `pr_v1_34_account_refund_cancel_enabled`;

DROP PROCEDURE IF EXISTS `pr_v1_34_account_refund_cancel_url`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_34_account_refund_cancel_url`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_account'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_account' AND COLUMN_NAME = 'refund_cancel_url'
    ) THEN
        ALTER TABLE `xianyu_account`
            ADD COLUMN `refund_cancel_url` VARCHAR(500) DEFAULT NULL COMMENT '退款关单外部注销接口URL' AFTER `refund_cancel_enabled`;
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_34_account_refund_cancel_url`();
DROP PROCEDURE IF EXISTS `pr_v1_34_account_refund_cancel_url`;

DROP PROCEDURE IF EXISTS `pr_v1_34_account_refund_cancel_timeout`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_34_account_refund_cancel_timeout`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_account'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_account' AND COLUMN_NAME = 'refund_cancel_timeout'
    ) THEN
        ALTER TABLE `xianyu_account`
            ADD COLUMN `refund_cancel_timeout` INT DEFAULT 60 COMMENT '退款关单接口超时秒数' AFTER `refund_cancel_url`;
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_34_account_refund_cancel_timeout`();
DROP PROCEDURE IF EXISTS `pr_v1_34_account_refund_cancel_timeout`;

DROP PROCEDURE IF EXISTS `pr_v1_34_order_is_unregistered`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_34_order_is_unregistered`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order' AND COLUMN_NAME = 'is_unregistered'
    ) THEN
        ALTER TABLE `xianyu_trade_order`
            ADD COLUMN `is_unregistered` TINYINT NOT NULL DEFAULT 0 COMMENT '退款关单是否已注销：0否 1是' AFTER `is_red_flower`;
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_34_order_is_unregistered`();
DROP PROCEDURE IF EXISTS `pr_v1_34_order_is_unregistered`;

DROP PROCEDURE IF EXISTS `pr_v1_34_order_unregister_error_reason`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_34_order_unregister_error_reason`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order' AND COLUMN_NAME = 'unregister_error_reason'
    ) THEN
        ALTER TABLE `xianyu_trade_order`
            ADD COLUMN `unregister_error_reason` VARCHAR(500) DEFAULT NULL COMMENT '退款关单失败原因' AFTER `is_unregistered`;
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_34_order_unregister_error_reason`();
DROP PROCEDURE IF EXISTS `pr_v1_34_order_unregister_error_reason`;
