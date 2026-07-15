-- ============================================================
-- V1.10__open_source_bridge_tables.sql
-- 开源版 bridge 对接相关表结构
-- 1. 用户反馈表 user_feedback（含 site_source / site_name 数据隔离字段）
-- 2. 用户反馈回复表 user_feedback_reply
-- 3. 开源版广告申请表 open_source_ad_application
-- 注：admin_module_record 表已在 SchemaCompatibilityRunner / V1.x 中创建，此处不再重复
-- 运行时代码（OpenSourceBridgeController.ensureFeedbackTables / OpenSourceAdService.ensureApplicationTable）
-- 仍保留 IF NOT EXISTS 兜底逻辑，与本脚本共存不冲突。
-- 实际表结构由 SchemaCompatibilityRunner.ensureOpenSourceBridgeTables() 在启动时创建。
-- ============================================================

-- 1. 用户反馈表（如不存在则创建，已存在则跳过）
CREATE TABLE IF NOT EXISTS `user_feedback` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `user_id` BIGINT NOT NULL COMMENT '用户ID',
    `username` VARCHAR(120) DEFAULT NULL COMMENT '用户名',
    `category` VARCHAR(40) NOT NULL COMMENT '反馈分类',
    `title` VARCHAR(200) NOT NULL COMMENT '反馈标题',
    `content` TEXT NOT NULL COMMENT '反馈内容',
    `contact` VARCHAR(200) DEFAULT NULL COMMENT '联系方式',
    `site_source` VARCHAR(40) DEFAULT 'commercial' COMMENT '来源站点编码 commercial/open-source',
    `site_name` VARCHAR(120) DEFAULT NULL COMMENT '来源站点名称',
    `status` VARCHAR(40) DEFAULT 'open' COMMENT '状态 open/in_progress/replied/closed',
    `priority` VARCHAR(20) DEFAULT 'normal' COMMENT '优先级 normal/high/urgent',
    `replier_user_id` BIGINT DEFAULT NULL COMMENT '回复人用户ID',
    `replier_username` VARCHAR(120) DEFAULT NULL COMMENT '回复人用户名',
    `replied_time` DATETIME DEFAULT NULL COMMENT '回复时间',
    `created_time` DATETIME DEFAULT NULL COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT NULL COMMENT '更新时间',
    `deleted` TINYINT DEFAULT 0 COMMENT '是否删除 0未删除 1已删除',
    INDEX `idx_uf_tenant_time` (`tenant_id`, `created_time`),
    INDEX `idx_uf_status` (`status`),
    INDEX `idx_uf_user` (`user_id`),
    INDEX `idx_uf_site_source` (`site_source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户反馈';

-- 存量数据回填：未设置来源的反馈默认标记为商业版
-- 如需执行请手动运行（MySQL 不支持 ADD COLUMN IF NOT EXISTS，由 SchemaCompatibilityRunner 处理）
-- UPDATE user_feedback SET site_source = 'commercial', site_name = '商业版'
-- WHERE site_source IS NULL OR site_source = '';

-- 2. 用户反馈回复表
CREATE TABLE IF NOT EXISTS `user_feedback_reply` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `feedback_id` BIGINT NOT NULL COMMENT '反馈ID',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `replier_user_id` BIGINT NOT NULL COMMENT '回复人用户ID',
    `replier_username` VARCHAR(120) DEFAULT NULL COMMENT '回复人用户名',
    `replier_role` VARCHAR(20) DEFAULT NULL COMMENT '回复角色 user/admin',
    `content` TEXT NOT NULL COMMENT '回复内容',
    `created_time` DATETIME DEFAULT NULL COMMENT '创建时间',
    INDEX `idx_fr_feedback` (`feedback_id`, `created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户反馈回复';

-- 3. 开源版广告申请表
CREATE TABLE IF NOT EXISTS `open_source_ad_application` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `site_code` VARCHAR(40) NOT NULL DEFAULT 'open-source' COMMENT '来源站点编码',
    `site_name` VARCHAR(120) DEFAULT NULL COMMENT '来源站点名称',
    `application_no` VARCHAR(40) DEFAULT NULL COMMENT '申请单号',
    `position_type` VARCHAR(40) NOT NULL COMMENT '广告位类型 home_carousel/sidebar_text',
    `position_label` VARCHAR(120) DEFAULT NULL COMMENT '广告位标签',
    `plan_code` VARCHAR(80) DEFAULT NULL COMMENT '套餐编码',
    `plan_title` VARCHAR(160) DEFAULT NULL COMMENT '套餐标题',
    `company_name` VARCHAR(200) NOT NULL COMMENT '公司名称',
    `contact_name` VARCHAR(80) NOT NULL COMMENT '联系人姓名',
    `contact_phone` VARCHAR(80) DEFAULT NULL COMMENT '联系电话',
    `contact_wechat` VARCHAR(80) DEFAULT NULL COMMENT '联系微信',
    `title` VARCHAR(200) NOT NULL COMMENT '广告标题',
    `landing_url` VARCHAR(500) DEFAULT NULL COMMENT '落地页地址',
    `budget` VARCHAR(80) DEFAULT NULL COMMENT '预算',
    `start_date` VARCHAR(40) DEFAULT NULL COMMENT '开始日期',
    `duration_days` VARCHAR(40) DEFAULT NULL COMMENT '投放天数',
    `remark` TEXT DEFAULT NULL COMMENT '备注',
    `status` VARCHAR(40) NOT NULL DEFAULT 'pending' COMMENT '状态 pending/approved/rejected/online/offline',
    `status_message` VARCHAR(255) DEFAULT NULL COMMENT '状态说明',
    `reviewer_user_id` BIGINT DEFAULT NULL COMMENT '审核人用户ID',
    `reviewer_username` VARCHAR(120) DEFAULT NULL COMMENT '审核人用户名',
    `reviewed_time` DATETIME DEFAULT NULL COMMENT '审核时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_osaa_tenant_site` (`tenant_id`, `site_code`, `status`),
    INDEX `idx_osaa_status` (`status`),
    INDEX `idx_osaa_application_no` (`application_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='开源版广告申请';
