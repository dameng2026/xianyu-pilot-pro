CREATE TABLE IF NOT EXISTS client_error_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NULL,
    user_id BIGINT NULL,
    error_type VARCHAR(80),
    message VARCHAR(500),
    stack TEXT NULL,
    source VARCHAR(200),
    route VARCHAR(300),
    user_agent VARCHAR(600),
    ip_address VARCHAR(80),
    payload_json TEXT NULL,
    created_time DATETIME,
    INDEX idx_client_error_tenant_time(tenant_id, created_time),
    INDEX idx_client_error_user_time(user_id, created_time),
    INDEX idx_client_error_type(error_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='前端客户端错误日志';
