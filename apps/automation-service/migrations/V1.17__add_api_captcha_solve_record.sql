-- V1.17: API 对接滑块求解记录表
-- 背景：对外开放滑块求解 API，需独立记录第三方调用，与内部账号保活的求解记录物理隔离
-- 字段与 xianyu_captcha_solve_record 对齐，新增 API 对接专属字段（tenant_id/api_key_prefix/client_ip/request_id/token_charged）
-- 非破坏性：仅 CREATE TABLE IF NOT EXISTS，幂等可重入

CREATE TABLE IF NOT EXISTS xianyu_api_captcha_solve_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT NOT NULL COMMENT '调用方租户',
    api_key_prefix VARCHAR(8) NOT NULL COMMENT '调用方密钥前 8 位',
    client_ip VARCHAR(45) NULL COMMENT '调用方 IP（IPv4/IPv6）',
    request_id VARCHAR(32) NOT NULL UNIQUE COMMENT '请求唯一 ID（幂等用，req_ 开头）',
    event_desc VARCHAR(255) NULL COMMENT '事件描述',
    trigger_scene VARCHAR(64) NOT NULL DEFAULT 'api' COMMENT '触发场景，固定 api',
    result VARCHAR(32) NULL COMMENT '处理结果：slider_success/slider_fail',
    status VARCHAR(32) NOT NULL DEFAULT 'queued' COMMENT 'queued/retrying/success/fail/timeout/precheck_rejected/stale_terminated',
    engine VARCHAR(64) NOT NULL DEFAULT 'Playwright',
    retry_count INT NOT NULL DEFAULT 0,
    error_message TEXT NULL COMMENT '错误详情（cookie 已脱敏）',
    priority INT NOT NULL DEFAULT 0,
    failure_reason VARCHAR(64) NOT NULL DEFAULT '' COMMENT '失败原因分类',
    queued_at DATETIME NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    open_reason VARCHAR(255) NULL,
    solve_reason VARCHAR(255) NULL,
    token_charged INT NOT NULL DEFAULT 0 COMMENT '实际扣费 Token 数（0=未扣）',
    token_charge_failed TINYINT NOT NULL DEFAULT 0 COMMENT '1=成功但扣费失败（极端竞态），需后台对账',
    duration_ms INT NULL COMMENT '求解耗时毫秒',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted TINYINT NOT NULL DEFAULT 0,
    INDEX idx_acsr_tenant_status (tenant_id, status, deleted),
    INDEX idx_acsr_tenant_created (tenant_id, created_at),
    INDEX idx_acsr_request_id (request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='API 对接滑块求解记录';
