-- ============================================================
-- 为 xianyu_chat_message 表添加稳定身份字段和校验支持
--
-- 背景：诊断发现 sender_user_id 大量为空、s_id 被消息内容污染、
-- pnm_id 基本为空。需要补充稳定字段来修复数据质量和去重。
-- ============================================================

-- Step 1: 添加新字段
ALTER TABLE `xianyu_chat_message`
    ADD COLUMN `seller_external_uid` VARCHAR(64) NULL COMMENT '闲鱼卖家真实UID/unb' AFTER `account_id`,
    ADD COLUMN `peer_external_uid` VARCHAR(64) NULL COMMENT '买家UID' AFTER `sender_user_name`,
    ADD COLUMN `receiver_user_id` VARCHAR(64) NULL COMMENT '接收者用户ID' AFTER `sender_user_id`,
    ADD COLUMN `message_uid` VARCHAR(128) NULL COMMENT '稳定消息唯一ID（用于去重）' AFTER `pnm_id`,
    ADD COLUMN `parse_status` VARCHAR(16) DEFAULT 'ok' COMMENT '解析状态: ok/partial/failed' AFTER `direction`,
    ADD COLUMN `raw_payload` LONGTEXT NULL COMMENT '原始消息payload（用于调试和重新解析）' AFTER `complete_msg`;

-- Step 2: 建立新索引
CREATE INDEX `idx_chat_seller_time`
    ON `xianyu_chat_message` (`tenant_id`, `seller_external_uid`, `deleted`, `message_time`);

CREATE INDEX `idx_chat_peer_time`
    ON `xianyu_chat_message` (`tenant_id`, `seller_external_uid`, `peer_external_uid`, `message_time`);

CREATE UNIQUE INDEX `uk_chat_msg_uid`
    ON `xianyu_chat_message` (`tenant_id`, `seller_external_uid`, `message_uid`);