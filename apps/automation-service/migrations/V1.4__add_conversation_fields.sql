-- ============================================================
-- 为 xianyu_conversation 表添加稳定身份字段
--
-- 背景：原有 external_buyer_id 在未解析出 buyer 时会被填入 sid:xxx
-- 导致会话维度混乱。需要补充稳定的卖家 UID 和买家 UID。
-- ============================================================

ALTER TABLE `xianyu_conversation`
    ADD COLUMN `seller_external_uid` VARCHAR(64) NULL COMMENT '闲鱼卖家真实UID/unb' AFTER `account_id`,
    ADD COLUMN `peer_external_uid` VARCHAR(64) NULL COMMENT '买家UID（稳定）' AFTER `external_buyer_id`,
    ADD COLUMN `peer_key` VARCHAR(128) NULL COMMENT '对端唯一标识（用于去重合会话）' AFTER `peer_external_uid`;

CREATE UNIQUE INDEX `uk_conv_peer`
    ON `xianyu_conversation` (`tenant_id`, `seller_external_uid`, `peer_key`);