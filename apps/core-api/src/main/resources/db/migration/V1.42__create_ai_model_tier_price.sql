-- 注：core-api 不使用 Flyway 框架，本文件为文档性质；
-- 实际表结构变更由 SchemaCompatibilityRunner 在启动时幂等创建。
-- 与 automation-service 不共享此表（automation-service 不直接读取 ai_model_tier_price）。

-- 通用模型按用户等级定价：支持 normal/vip/svp 三档不同的每次扣费 Token 数
-- 取代 ai_model_price_config.tokens_per_call（单一价格）和 perCallPrice × tokenExchangeRate（公式价格）
-- 通用模型（module_key='model-config-general'）的扣费以本表为准，由 AiBillingService.resolveTierTokensPerCall() 读取

CREATE TABLE IF NOT EXISTS `ai_model_tier_price` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `module_key` VARCHAR(80) NOT NULL COMMENT '模块 key，如 model-config-general',
    `vip_level` INT NOT NULL DEFAULT 0 COMMENT '用户 VIP 等级：0=普通, 1=VIP, 2=SVP',
    `tokens_per_call` BIGINT NOT NULL DEFAULT 3 COMMENT '每次调用扣费 Token 数',
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_tier_module_level` (`module_key`, `vip_level`),
    KEY `idx_tier_module` (`module_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通用模型按用户等级定价配置';
