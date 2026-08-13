-- 个人黑名单表（发货拦截）
-- 对齐同类项目 personal_blacklist 能力：
--   命中黑名单的买家在对应账号（可选商品范围）下禁止自动发货
CREATE TABLE IF NOT EXISTS `personal_blacklist` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `account_id` BIGINT NOT NULL COMMENT '闲鱼账号ID',
  `buyer_user_id` VARCHAR(128) NOT NULL COMMENT '买家用户ID（不含@goofish后缀）',
  `buyer_nickname` VARCHAR(128) DEFAULT '' COMMENT '买家昵称（展示用）',
  `goods_id` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '绑定的闲鱼商品ID，空串表示该账号全部商品',
  `reason` VARCHAR(500) DEFAULT '' COMMENT '拉黑原因',
  `enabled` TINYINT DEFAULT 1 COMMENT '1启用 0禁用',
  `deleted` TINYINT DEFAULT 0 COMMENT '0未删除 1已删除',
  `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_pb_tenant_account_buyer_goods` (`tenant_id`, `account_id`, `buyer_user_id`, `goods_id`),
  KEY `idx_pb_tenant_account_enabled` (`tenant_id`, `account_id`, `deleted`, `enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='个人黑名单表';
