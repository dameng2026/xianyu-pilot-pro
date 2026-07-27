-- V1.44__add_member_promotion_activity.sql
-- 会员充值限时活动功能
-- 新增 3 张表：活动主表、活动套餐配置、名额变更日志
-- 扩展 payment_order 表：追加活动订单快照字段与名额预占标记

-- 1. 活动主表
CREATE TABLE IF NOT EXISTS member_promotion_activity (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    activity_name       VARCHAR(100) NOT NULL COMMENT '活动名称',
    activity_code       VARCHAR(50) NOT NULL COMMENT '活动编码（唯一）',
    description         VARCHAR(500) NULL COMMENT '后台备注',
    status              VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT 'draft/pending/ongoing/ended/closed/quota_full',
    start_time          DATETIME NOT NULL COMMENT '开始时间（服务端时间）',
    end_time            DATETIME NOT NULL COMMENT '结束时间（服务端时间）',
    is_long_term        TINYINT NOT NULL DEFAULT 0 COMMENT '是否长期活动（1=endTime 视为无限）',
    auto_close_on_end   TINYINT NOT NULL DEFAULT 1 COMMENT '到期自动关闭',
    notice_title        VARCHAR(50) NULL COMMENT '前台通知标题',
    notice_content      VARCHAR(500) NULL COMMENT '前台通知正文（纯文本）',
    notice_visible      TINYINT NOT NULL DEFAULT 1 COMMENT '前台是否展示通知',
    notice_position     VARCHAR(20) NOT NULL DEFAULT 'top' COMMENT 'top/banner/card',
    notice_icon         VARCHAR(30) NOT NULL DEFAULT 'hot' COMMENT 'hot/gift/flash/star',
    total_quota         INT NOT NULL DEFAULT 0 COMMENT '活动总名额（0=不限量，汇总各套餐 quota）',
    sold_count          INT NOT NULL DEFAULT 0 COMMENT '已售份数（支付成功）',
    preoccupied_count   INT NOT NULL DEFAULT 0 COMMENT '预占份数（待支付订单）',
    created_by          BIGINT NULL COMMENT '创建人 admin user id',
    created_by_name     VARCHAR(50) NULL COMMENT '创建人名称',
    rule_version        INT NOT NULL DEFAULT 1 COMMENT '活动规则版本（每次关键变更 +1）',
    deleted             TINYINT NOT NULL DEFAULT 0,
    created_time        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_promo_activity_code (activity_code, deleted),
    INDEX idx_promo_activity_status (status, start_time, end_time, deleted),
    INDEX idx_promo_activity_time (start_time, end_time, deleted)
) COMMENT='会员充值活动主表';

-- 2. 活动套餐配置表
CREATE TABLE IF NOT EXISTS member_promotion_plan (
    id                      BIGINT PRIMARY KEY AUTO_INCREMENT,
    activity_id             BIGINT NOT NULL COMMENT '关联 member_promotion_activity.id',
    plan_id                 BIGINT NOT NULL COMMENT '关联 billing_plan.id',
    period_type             VARCHAR(10) NOT NULL COMMENT 'month/quarter/year',
    activity_price_cent     BIGINT NOT NULL COMMENT '活动价（分）',
    quota                   INT NOT NULL DEFAULT 0 COMMENT '套餐名额（0=不限量）',
    sold_count              INT NOT NULL DEFAULT 0 COMMENT '已售份数',
    preoccupied_count       INT NOT NULL DEFAULT 0 COMMENT '预占份数',
    sort_order              INT NOT NULL DEFAULT 0 COMMENT '前台排序',
    activity_tag            VARCHAR(20) NULL COMMENT '活动标签',
    show_sold_count         TINYINT NOT NULL DEFAULT 1 COMMENT '是否展示已售份数',
    show_quota              TINYINT NOT NULL DEFAULT 1 COMMENT '是否展示总名额',
    show_remain             TINYINT NOT NULL DEFAULT 1 COMMENT '是否展示剩余名额',
    allow_repurchase        TINYINT NOT NULL DEFAULT 1 COMMENT '是否允许同一用户重复购买',
    max_purchase_per_user   INT NOT NULL DEFAULT 0 COMMENT '单用户最多购买次数（0=不限）',
    deleted                 TINYINT NOT NULL DEFAULT 0,
    created_time            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_promo_plan_activity (activity_id, plan_id, period_type, deleted),
    INDEX idx_promo_plan_plan (plan_id, deleted),
    INDEX idx_promo_plan_activity (activity_id, deleted)
) COMMENT='活动套餐配置';

-- 3. 名额变更审计日志表
CREATE TABLE IF NOT EXISTS member_promotion_quota_log (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    activity_id         BIGINT NOT NULL COMMENT '活动ID',
    activity_plan_id    BIGINT NOT NULL COMMENT '活动套餐配置ID',
    order_no            VARCHAR(80) NULL COMMENT '关联订单号（preoccupy/confirm/release 时）',
    change_type         VARCHAR(20) NOT NULL COMMENT 'preoccupy/confirm/release/admin_adjust',
    delta               INT NOT NULL COMMENT '变更数量（+1 / -1）',
    before_value        INT NOT NULL COMMENT '变更前 preoccupied 或 sold 数量',
    after_value         INT NOT NULL COMMENT '变更后数量',
    operator_id         BIGINT NULL COMMENT '操作人（admin_adjust 时）',
    operator_name       VARCHAR(50) NULL,
    remark              VARCHAR(200) NULL,
    created_time        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_promo_quota_log_activity (activity_id, activity_plan_id),
    INDEX idx_promo_quota_log_order (order_no),
    INDEX idx_promo_quota_log_type (change_type, created_time)
) COMMENT='名额变更审计日志';

-- 4. 扩展 payment_order 表：追加活动订单快照字段
-- 注：amount_cent 仍存实际支付价（活动价），original_price_cent 仅用于前端展示划线原价
ALTER TABLE payment_order
    ADD COLUMN activity_id            BIGINT NULL COMMENT '活动ID（活动订单）',
    ADD COLUMN activity_plan_id       BIGINT NULL COMMENT '活动套餐配置ID',
    ADD COLUMN activity_name          VARCHAR(100) NULL COMMENT '活动名称快照',
    ADD COLUMN original_price_cent    BIGINT NULL COMMENT '套餐原价快照（分）',
    ADD COLUMN activity_price_cent    BIGINT NULL COMMENT '活动价快照（分）',
    ADD COLUMN discount_cent          BIGINT NOT NULL DEFAULT 0 COMMENT '优惠金额（分）',
    ADD COLUMN is_activity_order      TINYINT NOT NULL DEFAULT 0 COMMENT '是否活动订单',
    ADD COLUMN quota_preoccupied      TINYINT NOT NULL DEFAULT 0 COMMENT '是否已预占名额',
    ADD COLUMN activity_rule_version  INT NULL COMMENT '活动规则版本快照';

-- 活动订单查询索引
ALTER TABLE payment_order
    ADD INDEX idx_payment_order_activity (activity_id, is_activity_order, deleted);
