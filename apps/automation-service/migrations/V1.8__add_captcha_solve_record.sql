-- 滑块求解记录表
-- 记录每次滑块自动求解的触发场景、处理结果和验证状态
CREATE TABLE IF NOT EXISTS `xianyu_captcha_solve_record` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `account_id` BIGINT NOT NULL COMMENT '账号ID',
  `account_name` VARCHAR(128) DEFAULT '' COMMENT '账号名称',
  `event_desc` VARCHAR(255) NOT NULL COMMENT '事件描述',
  `trigger_scene` VARCHAR(64) DEFAULT '' COMMENT '触发场景: ws_connect/cookie_keepalive/token_refresh/manual',
  `result` VARCHAR(32) DEFAULT '' COMMENT '处理结果: slider_success/slider_fail',
  `status` VARCHAR(32) NOT NULL DEFAULT 'retrying' COMMENT '处理状态: retrying/success/fail',
  `engine` VARCHAR(64) DEFAULT 'Playwright' COMMENT '验证引擎',
  `retry_count` INT DEFAULT 0 COMMENT '重试次数',
  `error_message` TEXT COMMENT '错误详情',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` TINYINT DEFAULT 0 COMMENT '0未删除 1已删除',
  PRIMARY KEY (`id`),
  INDEX `idx_csr_account_id` (`account_id`),
  INDEX `idx_csr_created_at` (`created_at`),
  INDEX `idx_csr_tenant_status` (`tenant_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='滑块求解记录表';
