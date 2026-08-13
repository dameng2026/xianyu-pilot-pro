-- 发货拦截规则表（禁止发货规则引擎）
-- 对齐同类项目 xy_delivery_block_rules 的核心能力：
--   buyer_has_order      买家在当前账号已有其他订单 → 禁止发货
--   buyer_unconfirmed    买家存在未确认收货订单 → 禁止发货
-- account_id=0 表示全租户生效，否则仅指定账号生效
CREATE TABLE IF NOT EXISTS `delivery_block_rule` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `account_id` BIGINT NOT NULL DEFAULT 0 COMMENT '闲鱼账号ID，0表示全部账号',
  `rule_code` VARCHAR(50) NOT NULL COMMENT '规则编码: buyer_has_order / buyer_unconfirmed',
  `rule_name` VARCHAR(100) DEFAULT '' COMMENT '规则名称',
  `config_json` TEXT COMMENT '规则配置（预留）',
  `enabled` TINYINT DEFAULT 0 COMMENT '1启用 0禁用',
  `priority` INT DEFAULT 0 COMMENT '优先级，越小越先执行',
  `deleted` TINYINT DEFAULT 0 COMMENT '0未删除 1已删除',
  `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dbr_tenant_account_code` (`tenant_id`, `account_id`, `rule_code`),
  KEY `idx_dbr_tenant_enabled` (`tenant_id`, `deleted`, `enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='发货拦截规则表';
