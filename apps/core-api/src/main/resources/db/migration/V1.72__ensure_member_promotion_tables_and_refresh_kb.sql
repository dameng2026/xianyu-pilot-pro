-- V1.72：确保会员充值活动三张表存在 + 刷新促销活动知识条目
--
-- 背景：V1.44 的 DDL 在部分环境（无 Flyway 历史）未执行，导致
-- MemberPromotionScheduler 每分钟报「表不存在」，且 AI 客服知识库仍引用旧表名
-- member_quota_log（实际表名为 member_promotion_quota_log）。
-- 本迁移幂等：CREATE TABLE IF NOT EXISTS + UPDATE + INSERT ... WHERE NOT EXISTS。

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

-- 2.1 补列：member_promotion_plan.rule_version（V1.44 建表缺失，但 Java 服务查询引用该列）
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'member_promotion_plan' AND COLUMN_NAME = 'rule_version');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE member_promotion_plan ADD COLUMN rule_version INT NOT NULL DEFAULT 1 COMMENT ''活动套餐规则版本''',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. 名额变更审计日志表（旧知识条目误写为 member_quota_log）
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

-- 4. 刷新「会员促销活动」知识条目（旧表名 + 内部实现细节 → 用户视角 + 实时工具）
UPDATE ai_cs_knowledge
SET content = '平台会员充值活动（限时促销）：\n'
  '- 活动入口：会员中心展示进行中/长期活动（折扣价、名额、倒计时、活动标签）。\n'
  '- 活动规则：活动套餐按 月度/季度/年度 提供活动价；名额有限，先到先得；部分活动限制每人购买次数。\n'
  '- 购买流程：选择活动套餐 → 微信/支付宝支付 → 支付成功即时到账并占用名额；超时未支付自动释放。\n'
  '- 活动状态：未开始/进行中/已结束/已关闭/名额已满。\n'
  '- 小梦回答「有什么促销活动」「活动价多少钱」时必须调用 get_promotions 实时查询，禁止凭知识条目猜测活动与价格。',
    keywords = 'membership,promotion,activity,plan,quota,促销,活动,套餐,限时,活动价,get_promotions',
    updated_time = NOW()
WHERE tenant_id IS NULL AND title = '会员促销活动';

-- 5. 新增「促销活动实时查询」规则
INSERT INTO ai_cs_knowledge(
    tenant_id, category, title, content, keywords,
    priority, enabled, sort_order, created_time, updated_time
)
SELECT NULL, 'membership', '促销活动实时查询',
  '促销活动（限时折扣/返现/名额限制/倒计时）随时可能由后台创建、开启或关闭，'
  '必须调用 get_promotions 实时查询，禁止使用知识库中的历史活动内容。\n'
  '查询返回：活动名称、状态、活动标签、活动套餐（月/季/年活动价）、名额余量、前台通知；'
  '无进行中活动时如实告知用户当前没有促销活动。',
  '促销,活动,限时,折扣,返现,活动价,名额,get_promotions,实时',
  100, 1, 33, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_cs_knowledge
    WHERE tenant_id IS NULL AND title = '促销活动实时查询'
);
