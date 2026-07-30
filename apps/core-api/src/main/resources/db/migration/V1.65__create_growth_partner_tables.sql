-- ============================================================
-- V1.65 增长合伙人系统表结构（文档性质，实际由 SchemaCompatibilityRunner 幂等创建）
-- 依据 .trae/rules/database-migration-on-release.md 规则，仅追加、非破坏性 DDL
-- 涉及表：
--   growth_global_config        全局配置（token奖励/最低提现等）
--   growth_agent_tier_config    代理等级配置（名称/门槛/分成比例/图标/颜色）
--   growth_invite_code          邀请码与推广链接
--   growth_referral_relation    推荐关系（一级/二级）
--   growth_reward_record        奖励记录（Token奖励/现金分成）
--   growth_user_balance         用户收益余额（总收益/可提现/冻结/已提现）
--   growth_withdrawal_request   提现申请（微信/支付宝/银行卡）
-- 同时为 sys_user 增加 balance（现金余额，分）与 referrer_id（直接推荐人）两列
-- ============================================================

-- 注意：以下 DDL 仅为文档参考。实际建表由 SchemaCompatibilityRunner.ensureGrowthTables()
-- 在应用启动时以 CREATE TABLE IF NOT EXISTS 幂等执行，ADD COLUMN IF NOT EXISTS 通过
-- INFORMATION_SCHEMA 动态判断后执行，兼容 MySQL 8.0。

-- growth_global_config：单行配置表（id=1）
-- token_reward_per_referral  二级用户首单消费后一级用户获得的 Token 数量（默认 100）
-- min_withdrawal_amount      最低提现金额，单位分（默认 5000 = 50 元）
-- first_month_only            是否仅首月消费分成（1=是，0=长期分成，默认 1）
CREATE TABLE IF NOT EXISTS growth_global_config (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    token_reward_per_referral BIGINT NOT NULL DEFAULT 100 COMMENT '二级用户首单消费奖励一级用户的 Token 数',
    min_withdrawal_amount BIGINT NOT NULL DEFAULT 5000 COMMENT '最低提现金额（分），默认 5000=50元',
    first_month_only TINYINT NOT NULL DEFAULT 1 COMMENT '分成仅首月：1是 0否',
    withdraw_enabled TINYINT NOT NULL DEFAULT 1 COMMENT '提现开关：1开 0关',
    updated_by VARCHAR(100),
    created_time DATETIME,
    updated_time DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- growth_agent_tier_config：代理等级配置（可后台自定义名称与分成）
CREATE TABLE IF NOT EXISTS growth_agent_tier_config (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tier_code VARCHAR(40) NOT NULL COMMENT '等级编码：normal/bronze/gold/diamond 或自定义',
    tier_name VARCHAR(80) NOT NULL COMMENT '等级名称（如 普通代理/青铜代理）',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序（升序展示）',
    min_referrals INT NOT NULL DEFAULT 0 COMMENT '升级所需有效邀请人数',
    commission_rate DECIMAL(5,2) NOT NULL DEFAULT 0.00 COMMENT '首月分成比例（0-100，如 20 表示 20%）',
    token_reward BIGINT NOT NULL DEFAULT 100 COMMENT '该等级一级用户获得的 Token 奖励（可覆盖全局配置）',
    icon VARCHAR(120) COMMENT '图标标识（前端映射）',
    color VARCHAR(20) COMMENT '主题色（如 #2378f3）',
    badge_url VARCHAR(500) COMMENT '徽章图片地址',
    description VARCHAR(500) COMMENT '等级说明',
    enabled TINYINT NOT NULL DEFAULT 1,
    created_time DATETIME,
    updated_time DATETIME,
    UNIQUE KEY uk_growth_tier_code (tier_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- growth_invite_code：邀请码与推广链接
CREATE TABLE IF NOT EXISTS growth_invite_code (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL COMMENT '邀请码/推广码（唯一）',
    owner_user_id BIGINT NOT NULL COMMENT '邀请码归属用户',
    tenant_id BIGINT NOT NULL,
    code_type VARCHAR(20) NOT NULL DEFAULT 'code' COMMENT 'code=邀请码 link=推广链接',
    channel VARCHAR(60) COMMENT '来源渠道标记',
    usage_count INT NOT NULL DEFAULT 0 COMMENT '被使用次数',
    expires_at DATETIME COMMENT '过期时间（NULL=永久）',
    remark VARCHAR(200),
    created_time DATETIME,
    updated_time DATETIME,
    UNIQUE KEY uk_growth_invite_code (code),
    INDEX idx_growth_invite_owner (owner_user_id),
    INDEX idx_growth_invite_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- growth_referral_relation：推荐关系
CREATE TABLE IF NOT EXISTS growth_referral_relation (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    inviter_id BIGINT NOT NULL COMMENT '邀请人（一级用户）',
    invitee_id BIGINT NOT NULL COMMENT '被邀请人（二级用户）',
    invitee_tenant_id BIGINT COMMENT '被邀请人租户',
    level TINYINT NOT NULL DEFAULT 1 COMMENT '关系层级：1=直接 2=间接（预留）',
    invite_code VARCHAR(64) COMMENT '使用的邀请码',
    channel VARCHAR(60) COMMENT '来源渠道',
    first_consumed_at DATETIME COMMENT '被邀请人首次消费时间',
    first_month_end_at DATETIME COMMENT '首月分成结束时间',
    created_time DATETIME,
    UNIQUE KEY uk_growth_referral (inviter_id, invitee_id),
    INDEX idx_growth_referral_inviter (inviter_id),
    INDEX idx_growth_referral_invitee (invitee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- growth_reward_record：奖励记录
CREATE TABLE IF NOT EXISTS growth_reward_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    inviter_id BIGINT NOT NULL COMMENT '获益的一级用户',
    invitee_id BIGINT NOT NULL COMMENT '消费的被邀请人',
    invitee_tenant_id BIGINT,
    reward_type VARCHAR(20) NOT NULL COMMENT 'token=Token奖励 cash=现金分成',
    level TINYINT NOT NULL DEFAULT 1 COMMENT '关系层级',
    source_amount BIGINT NOT NULL DEFAULT 0 COMMENT '触发消费金额（分）',
    source_order_no VARCHAR(80) COMMENT '触发订单号',
    source_product VARCHAR(120) COMMENT '消费产品名',
    commission_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '分成比例',
    token_amount BIGINT DEFAULT 0 COMMENT '奖励 Token 数',
    cash_amount BIGINT DEFAULT 0 COMMENT '奖励现金（分）',
    status VARCHAR(20) NOT NULL DEFAULT 'settled' COMMENT 'settled=已结算 reverted=已回滚',
    settled_at DATETIME,
    created_time DATETIME,
    INDEX idx_growth_reward_inviter (inviter_id, created_time),
    INDEX idx_growth_reward_invitee (invitee_id),
    INDEX idx_growth_reward_order (source_order_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- growth_user_balance：用户收益余额（聚合表，单位均为分）
CREATE TABLE IF NOT EXISTS growth_user_balance (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    total_earnings BIGINT NOT NULL DEFAULT 0 COMMENT '累计收益（分）',
    available_balance BIGINT NOT NULL DEFAULT 0 COMMENT '可提现余额（分）',
    frozen_balance BIGINT NOT NULL DEFAULT 0 COMMENT '冻结余额（提现申请中）',
    withdrawn_amount BIGINT NOT NULL DEFAULT 0 COMMENT '已提现金额（分）',
    total_token_reward BIGINT NOT NULL DEFAULT 0 COMMENT '累计 Token 奖励',
    total_referrals INT NOT NULL DEFAULT 0 COMMENT '累计邀请人数',
    valid_referrals INT NOT NULL DEFAULT 0 COMMENT '有效邀请人数',
    tier_code VARCHAR(40) NOT NULL DEFAULT 'normal' COMMENT '当前代理等级',
    tier_updated_at DATETIME,
    created_time DATETIME,
    updated_time DATETIME,
    UNIQUE KEY uk_growth_balance_user (user_id),
    INDEX idx_growth_balance_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- growth_withdrawal_request：提现申请
CREATE TABLE IF NOT EXISTS growth_withdrawal_request (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    amount BIGINT NOT NULL COMMENT '提现金额（分）',
    payment_method VARCHAR(20) NOT NULL COMMENT 'wechat_qr=微信收款码 alipay_qr=支付宝收款码 alipay_account=支付宝账号 bank_card=银行卡',
    payment_account VARCHAR(500) NOT NULL COMMENT '收款信息（JSON：含二维码URL或账号）',
    payment_name VARCHAR(100) COMMENT '收款人姓名',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending=待审批 approved=已通过 rejected=已驳回 paid=已打款 failed=打款失败',
    reject_reason VARCHAR(500),
    reviewed_by VARCHAR(100),
    reviewed_at DATETIME,
    paid_at DATETIME,
    created_time DATETIME,
    updated_time DATETIME,
    INDEX idx_growth_wd_user (user_id, status, created_time),
    INDEX idx_growth_wd_status (status, created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
