-- ============================================================
-- 为 xianyu_chat_message 表添加复合索引
-- 
-- 优化 get_online_conversations（会话列表）和 get_context_messages（消息上下文）查询性能
-- 
-- 查询模式：
--   WHERE tenant_id = ? AND account_id = ? AND deleted = 0 AND content_type NOT IN (32)
--   PARTITION BY s_id
--   ORDER BY message_time DESC
--
-- 索引 idx_chat_msg_lookup 覆盖 WHERE 条件（等值查询）和窗口函数（排序），
-- content_type NOT IN (32) 作为过滤条件在索引扫描后应用。
-- ============================================================

ALTER TABLE `xianyu_chat_message`
    ADD INDEX `idx_chat_msg_lookup` (`tenant_id`, `account_id`, `deleted`, `s_id`, `message_time`);