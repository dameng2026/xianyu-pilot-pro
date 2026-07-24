-- V1.16: 滑块求解不活跃账号排除表
-- 存储3天未登录前台用户的闲鱼账号，使其无法进入滑块求解队列
-- 用户登录前台时自动从排除表中移除其所有闲鱼账号
-- 避免3天不活跃用户的账号占用求解排队序列并产生脏数据
CREATE TABLE IF NOT EXISTS xianyu_account_solve_exclusion (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_id BIGINT NOT NULL COMMENT '闲鱼账号 ID (xianyu_account.id)',
    tenant_id BIGINT NOT NULL COMMENT '租户 ID（即用户 ID sys_user.tenant_id）',
    user_id BIGINT NOT NULL COMMENT '所属用户 ID (xianyu_account.user_id)',
    reason VARCHAR(64) NOT NULL DEFAULT 'user_inactive' COMMENT '排除原因: user_inactive=用户3天未登录',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_account_id (account_id),
    INDEX idx_tenant_user (tenant_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='滑块求解不活跃账号排除表';
