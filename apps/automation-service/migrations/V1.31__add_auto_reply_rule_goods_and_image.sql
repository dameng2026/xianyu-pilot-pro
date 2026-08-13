-- V1.31 自动回复规则新增商品绑定与图片回复能力
-- ============================================================================
-- 对齐同类项目关键词能力：
--   1. xy_goods_id：规则可绑定闲鱼商品，NULL 表示通用规则（所有商品生效）
--   2. reply_image：关键词命中后发送图片消息（图片关键词）
-- 使用 INFORMATION_SCHEMA + 存储过程实现幂等，兼容 MySQL 8.0/8.4 可重入执行。
-- ============================================================================

DROP PROCEDURE IF EXISTS `pr_v1_31_add_xy_goods_id`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_31_add_xy_goods_id`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auto_reply_rule'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'auto_reply_rule'
          AND COLUMN_NAME = 'xy_goods_id'
    ) THEN
        ALTER TABLE `auto_reply_rule`
            ADD COLUMN `xy_goods_id` VARCHAR(64) NULL COMMENT '绑定的闲鱼商品ID，NULL表示通用规则' AFTER `account_id`;
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_31_add_xy_goods_id`();
DROP PROCEDURE IF EXISTS `pr_v1_31_add_xy_goods_id`;

DROP PROCEDURE IF EXISTS `pr_v1_31_add_reply_image`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_31_add_reply_image`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auto_reply_rule'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'auto_reply_rule'
          AND COLUMN_NAME = 'reply_image'
    ) THEN
        ALTER TABLE `auto_reply_rule`
            ADD COLUMN `reply_image` VARCHAR(500) NOT NULL DEFAULT '' COMMENT '关键词命中后发送的图片URL（图片关键词）' AFTER `reply_content`;
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_31_add_reply_image`();
DROP PROCEDURE IF EXISTS `pr_v1_31_add_reply_image`;

DROP PROCEDURE IF EXISTS `pr_v1_31_add_goods_index`;
DELIMITER $$
CREATE PROCEDURE `pr_v1_31_add_goods_index`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auto_reply_rule'
    ) AND NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'auto_reply_rule'
          AND INDEX_NAME = 'idx_arr_tenant_account_goods'
    ) THEN
        ALTER TABLE `auto_reply_rule`
            ADD INDEX `idx_arr_tenant_account_goods` (`tenant_id`, `account_id`, `xy_goods_id`, `deleted`);
    END IF;
END$$
DELIMITER ;
CALL `pr_v1_31_add_goods_index`();
DROP PROCEDURE IF EXISTS `pr_v1_31_add_goods_index`;
