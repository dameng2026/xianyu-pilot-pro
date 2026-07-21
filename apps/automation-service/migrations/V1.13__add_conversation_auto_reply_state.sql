-- ============================================================
-- V1.13: 会话级自动回复运行时状态 + 消息 AI 标记
--
-- 背景：
--   1. 需要区分 AI 自动回复消息与人工发送消息，便于前端展示与人工干预检测
--   2. 需要支持"人工干预自动暂停 AI 回复"：
--      - 检测到人工发送消息后，自动暂停当前会话的 AI 自动回复
--      - 买家发送"开启自动回复"指令 或 距上次人工回复 > 1 分钟时自动恢复
--      - 用户在网站手动点击按钮关闭时，禁止自动恢复，仅允许手动开启
--
-- 变更：
--   xianyu_conversation 新增 4 字段：
--     - auto_reply_paused          会话级自动回复是否暂停（0否 1是）
--     - auto_reply_manual_disabled 是否被用户手动关闭（0否 1是，1时不允许自动恢复）
--     - last_manual_reply_at       最后一次人工回复时间戳（毫秒）
--     - last_auto_reply_at         最后一次 AI 自动回复时间戳（毫秒）
--   xianyu_chat_message 新增 1 字段：
--     - is_auto_reply              是否 AI 自动回复（0否 1是）
--
-- 兼容性：所有新字段均有默认值，老数据无须回填；纯追加 ALTER，不修改/删除既有字段
-- ============================================================

ALTER TABLE `xianyu_conversation`
    ADD COLUMN `auto_reply_paused` SMALLINT NOT NULL DEFAULT 0
        COMMENT '会话级自动回复是否暂停 0否 1是（人工干预或手动关闭触发）'
        AFTER `status`,
    ADD COLUMN `auto_reply_manual_disabled` SMALLINT NOT NULL DEFAULT 0
        COMMENT '是否被用户手动关闭 0否 1是（1时不允许自动恢复，仅手动开启）'
        AFTER `auto_reply_paused`,
    ADD COLUMN `last_manual_reply_at` BIGINT NULL
        COMMENT '最后一次人工回复时间戳（毫秒），用于1分钟自动恢复判断'
        AFTER `auto_reply_manual_disabled`,
    ADD COLUMN `last_auto_reply_at` BIGINT NULL
        COMMENT '最后一次 AI 自动回复时间戳（毫秒）'
        AFTER `last_manual_reply_at`;

ALTER TABLE `xianyu_chat_message`
    ADD COLUMN `is_auto_reply` SMALLINT NOT NULL DEFAULT 0
        COMMENT '是否 AI 自动回复 0否 1是'
        AFTER `direction`;

-- 便于按会话+暂停状态快速查询
CREATE INDEX `idx_conv_paused_tenant_account`
    ON `xianyu_conversation` (`tenant_id`, `account_id`, `auto_reply_paused`);
