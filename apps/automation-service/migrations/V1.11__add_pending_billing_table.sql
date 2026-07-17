-- AI 计费待补扣记录表
-- 当 Python 自动回复/工作流调用通用模型时，若 Java 计费服务暂不可用（AiBillingUnavailable），
-- 将计费请求暂存到本表，由定时任务在 Java 恢复后补扣，避免"已调用 AI 但无计费记录"的漏计费问题。
-- Java charge 接口已支持 request_id 幂等，重复补扣安全。

CREATE TABLE IF NOT EXISTS `pending_ai_billing` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `user_id` BIGINT NOT NULL COMMENT '用户ID',
  `account_id` BIGINT NOT NULL DEFAULT 0 COMMENT '账号ID（自动回复场景用，0表示用户级）',
  `scene` VARCHAR(80) NOT NULL COMMENT '计费场景，如 auto_reply / product_polish',
  `request_id` VARCHAR(120) NOT NULL COMMENT '幂等键，与 Java ai_usage_log.request_id 对应',
  `payload_json` MEDIUMTEXT NOT NULL COMMENT '原始计费 payload（含 provider/model/usage 等）',
  `attempt_count` INT NOT NULL DEFAULT 0 COMMENT '已重试次数',
  `max_attempts` INT NOT NULL DEFAULT 12 COMMENT '最大重试次数（默认12次）',
  `next_retry_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '下次重试时间',
  `last_error` VARCHAR(512) DEFAULT '' COMMENT '最近失败摘要',
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending / success / failed / dead',
  `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_pending_billing_request` (`request_id`),
  KEY `idx_pending_billing_due` (`status`, `next_retry_at`),
  KEY `idx_pending_billing_user` (`tenant_id`, `user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 计费待补扣记录';
