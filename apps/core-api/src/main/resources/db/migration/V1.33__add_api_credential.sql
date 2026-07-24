-- V1.33: API 滑块求解对接凭证表 + 默认价格配置
-- 背景：商业版滑块求解能力以 SaaS API 形式对外开放，需要独立存储对接凭证与默认价格
-- 非破坏性：仅 CREATE TABLE IF NOT EXISTS + INSERT ... ON DUPLICATE KEY UPDATE，幂等可重入

CREATE TABLE IF NOT EXISTS xianyu_api_credential (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL UNIQUE COMMENT '租户ID（一租户一密钥）',
    api_key_hash VARCHAR(64) NOT NULL UNIQUE COMMENT 'sha256(apiKey)，不存明文',
    api_key_prefix VARCHAR(8) NOT NULL COMMENT 'apiKey 前 8 位明文，用于展示识别',
    enabled TINYINT NOT NULL DEFAULT 1 COMMENT '1启用 0禁用',
    last_used_at DATETIME NULL COMMENT '最近调用时间',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_api_credential_hash (api_key_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='API 对接凭证';

-- 默认价格配置：module_key='api-slider-solve'，per_call_price=0.05 元，token_exchange_rate=100 → 5 Token/次
-- 先清理可能存在的旧记录确保幂等
DELETE FROM ai_model_price_config WHERE module_key = 'api-slider-solve' AND tenant_id IS NULL;
INSERT INTO ai_model_price_config
    (tenant_id, module_key, provider_name, model_name, model_type, billing_mode,
     input_price_per_1k, output_price_per_1k, cached_input_price_per_1k,
     per_call_price, token_exchange_rate, min_charge_token, billing_unit,
     enabled, created_time, updated_time, deleted)
VALUES
    (NULL, 'api-slider-solve', 'default', 'default', 'chat', 'per_call',
     0, 0, 0,
     0.05, 100, 1, '1K',
     1, NOW(), NOW(), 0);
