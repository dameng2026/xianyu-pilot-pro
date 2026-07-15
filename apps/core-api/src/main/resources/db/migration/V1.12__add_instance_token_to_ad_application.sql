-- ============================================================
-- V1.12__add_instance_token_to_ad_application.sql
-- 为 open_source_ad_application 表添加 instance_token 列
-- 该列存储开源版实例的唯一标识 Token，用于将广告申请记录归属到
-- 具体的开源版部署实例，支持按实例查询历史申请记录。
-- ============================================================

-- MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，使用存储过程实现幂等
DROP PROCEDURE IF EXISTS proc_add_instance_token_column;
DELIMITER //
CREATE PROCEDURE proc_add_instance_token_column()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'open_source_ad_application'
          AND column_name = 'instance_token'
    ) THEN
        ALTER TABLE `open_source_ad_application`
            ADD COLUMN `instance_token` VARCHAR(120) DEFAULT NULL
            COMMENT '开源版实例标识Token（osi_前缀），用于关联具体开源版部署'
            AFTER `site_name`;
        ALTER TABLE `open_source_ad_application`
            ADD INDEX `idx_osaa_instance_token` (`instance_token`);
    END IF;
END //
DELIMITER ;
CALL proc_add_instance_token_column();
DROP PROCEDURE IF EXISTS proc_add_instance_token_column;
