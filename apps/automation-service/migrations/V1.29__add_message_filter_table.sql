-- 消息过滤规则表
-- 用于按账号+关键词屏蔽自动回复与消息通知（skip_reply / skip_notify）
-- 参考同类项目 xy_message_filters 能力，适配我方租户模型与软删除约定
CREATE TABLE IF NOT EXISTS `message_filter` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `account_id` BIGINT NOT NULL COMMENT '闲鱼账号ID',
  `keyword` VARCHAR(200) NOT NULL COMMENT '过滤关键词（命中即生效）',
  `filter_type` VARCHAR(32) NOT NULL COMMENT '过滤类型: skip_reply(跳过自动回复) / skip_notify(跳过消息通知)',
  `enabled` TINYINT DEFAULT 1 COMMENT '1启用 0禁用',
  `deleted` TINYINT DEFAULT 0 COMMENT '0未删除 1已删除',
  `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_mf_tenant_account_keyword_type` (`tenant_id`, `account_id`, `keyword`, `filter_type`),
  KEY `idx_mf_tenant_account` (`tenant_id`, `account_id`, `deleted`, `enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息过滤规则表';
