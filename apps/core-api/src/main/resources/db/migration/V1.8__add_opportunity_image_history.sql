-- ============================================================
-- V1.8__add_opportunity_image_history.sql
-- 商机发掘生图历史记录表（用于异常恢复与图片重试）
-- ============================================================

CREATE TABLE IF NOT EXISTS `opportunity_image_history` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `user_id` BIGINT NOT NULL COMMENT '用户ID',
    `request_id` VARCHAR(64) NOT NULL COMMENT '生图请求唯一标识',
    `model` VARCHAR(128) DEFAULT '' COMMENT '模型名称',
    `prompt` TEXT COMMENT '生图提示词',
    `image_size` VARCHAR(20) DEFAULT '1024x1024' COMMENT '图片尺寸',
    `image_count` INT DEFAULT 0 COMMENT '图片数量',
    `result_images` TEXT COMMENT '结果图片JSON（url列表）',
    `method_used` VARCHAR(32) DEFAULT '' COMMENT '使用的方法：proxy-async-poll/async-poll/direct-sync',
    `status` VARCHAR(16) DEFAULT 'success' COMMENT '状态：success/failed',
    `error_message` TEXT COMMENT '错误信息',
    `raw_response` TEXT COMMENT '原始响应JSON',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0,
    INDEX `idx_oih_tenant_user` (`tenant_id`, `user_id`, `deleted`),
    INDEX `idx_oih_request_id` (`request_id`),
    INDEX `idx_oih_created_time` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商机发掘生图历史记录';