-- 通知去重记录表
-- 用于确保账号状态类通知（Cookie 到期 / 账号掉线 / 人机验证）
-- 在账号状态恢复前每条只发送一次，避免断线重连循环或周期性保活任务
-- 每隔几分钟触发重复通知刷屏。
--
-- 去重逻辑：
--   1. 发送通知前：查询是否存在 (tenant_id, account_id, event_type) 记录
--   2. 已存在 → 跳过发送
--   3. 不存在 → 发送通知，发送后写入本表
--   4. 账号恢复（cookie_status=1 / WS 重连 / 手动更新 Cookie / 扫码登录）→ 删除该账号所有去重记录
CREATE TABLE IF NOT EXISTS notification_dedup (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NOT NULL,
  account_id BIGINT NOT NULL,
  event_type VARCHAR(80) NOT NULL,
  last_sent_time DATETIME NOT NULL,
  created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_nd_tenant_account_event(tenant_id, account_id, event_type),
  INDEX idx_nd_account(tenant_id, account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通知去重记录';
