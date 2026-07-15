CREATE TABLE IF NOT EXISTS notification_delivery_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT,
  user_id BIGINT,
  channel_key VARCHAR(80),
  channel_name VARCHAR(120),
  event_type VARCHAR(80),
  success TINYINT DEFAULT 0,
  status_code INT DEFAULT 0,
  cost_ms BIGINT DEFAULT 0,
  message VARCHAR(500),
  created_time DATETIME,
  INDEX idx_ndl_user_time(tenant_id, user_id, created_time),
  INDEX idx_ndl_success(success, created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通知发送记录';
