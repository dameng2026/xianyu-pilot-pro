-- ============================================================
-- V1.19__delivery_statement_session.sql
-- 发货声明会话表：跟踪"收到付款→发送声明→买家确认/取消→触发发货"全流程
-- 按订单粒度跟踪，与 delivery_record（发货结果记录）解耦
-- ============================================================

CREATE TABLE IF NOT EXISTS `delivery_statement_session` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `account_id` BIGINT NOT NULL COMMENT '闲鱼账号ID',
    `order_id` VARCHAR(64) NOT NULL COMMENT '订单号（从 reminderUrl 提取）',
    `buyer_id` VARCHAR(64) DEFAULT NULL COMMENT '买家ID',
    `buyer_nick` VARCHAR(128) DEFAULT NULL COMMENT '买家昵称（文案变量）',
    `xy_goods_id` VARCHAR(64) DEFAULT NULL COMMENT '商品ID',
    `goods_title` VARCHAR(255) DEFAULT NULL COMMENT '商品标题（文案变量）',
    `s_id` VARCHAR(64) DEFAULT NULL COMMENT '会话ID',
    `pnm_id` VARCHAR(64) DEFAULT NULL COMMENT 'pnmId（可选）',
    `statement_content` TEXT COMMENT '实际发送的声明文案（变量已替换）',
    `statement_msg_id` VARCHAR(128) DEFAULT NULL COMMENT '声明消息ID（幂等用）',
    `status` VARCHAR(16) NOT NULL DEFAULT 'declaring' COMMENT '状态：declaring/waiting/confirmed/cancelled',
    `sent_at` DATETIME DEFAULT NULL COMMENT '声明发送时间',
    `confirmed_at` DATETIME DEFAULT NULL COMMENT '买家确认时间',
    `cancelled_at` DATETIME DEFAULT NULL COMMENT '买家取消时间',
    `confirm_source` VARCHAR(16) DEFAULT NULL COMMENT '确认来源：buyer=买家回复/seller=卖家手动',
    `cancel_source` VARCHAR(16) DEFAULT NULL COMMENT '取消来源：buyer=买家回复/seller=卖家手动',
    `reply_msg_id` VARCHAR(128) DEFAULT NULL COMMENT '买家确认/取消消息ID',
    `delivery_record_id` BIGINT DEFAULT NULL COMMENT '确认后创建的发货记录ID（关联 delivery_record.id）',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0,
    INDEX `idx_dss_tenant` (`tenant_id`, `deleted`),
    INDEX `idx_dss_lookup` (`account_id`, `s_id`, `status`),
    INDEX `idx_dss_order` (`account_id`, `order_id`),
    INDEX `idx_dss_buyer` (`account_id`, `buyer_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='发货声明会话（按订单粒度跟踪声明→确认/取消→发货）';
