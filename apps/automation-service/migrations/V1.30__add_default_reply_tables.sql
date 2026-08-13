-- 默认回复配置表（账号级）
-- 未命中关键词规则且 AI 客服关闭时，按账号兜底回复
CREATE TABLE IF NOT EXISTS `default_reply` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `account_id` BIGINT NOT NULL COMMENT '闲鱼账号ID',
  `enabled` TINYINT DEFAULT 1 COMMENT '1启用 0禁用',
  `reply_type` VARCHAR(16) DEFAULT 'text' COMMENT 'text文本 / api外部接口',
  `reply_content` TEXT COMMENT '文本回复内容',
  `reply_image` VARCHAR(500) DEFAULT '' COMMENT '回复图片URL（本地/uploads或闲鱼CDN）',
  `api_url` VARCHAR(500) DEFAULT '' COMMENT '外部API地址（仅https公网）',
  `api_timeout` INT DEFAULT 30 COMMENT 'API超时秒数',
  `reply_once` TINYINT DEFAULT 0 COMMENT '1仅对同一买家回复一次',
  `deleted` TINYINT DEFAULT 0 COMMENT '0未删除 1已删除',
  `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dr_tenant_account` (`tenant_id`, `account_id`),
  KEY `idx_dr_tenant_enabled` (`tenant_id`, `deleted`, `enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='默认回复配置表';

-- 默认回复记录表（reply_once 用）
CREATE TABLE IF NOT EXISTS `default_reply_record` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `account_id` BIGINT NOT NULL COMMENT '闲鱼账号ID',
  `buyer_user_id` VARCHAR(128) NOT NULL COMMENT '买家用户ID',
  `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_drr_tenant_account_buyer` (`tenant_id`, `account_id`, `buyer_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='默认回复记录表';
