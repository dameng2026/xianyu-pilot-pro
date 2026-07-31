-- V1.26: 补建消息服务关键索引
-- 目的：解决会话列表加载慢（10s）和消息上下文加载慢（5s+）的数据库性能瓶颈。
-- 这些索引覆盖 get_online_conversations / get_context_messages / _apply_ai_reply_preview
-- 等热点查询的 JOIN 和 WHERE 条件，避免全表扫描。
--
-- 约束：
-- - MySQL 8.0 不支持 CREATE INDEX IF NOT EXISTS，使用 INFORMATION_SCHEMA + PREPARE/EXECUTE 保证幂等
-- - 仅追加索引，不修改/删除已有索引，不改变表结构（符合 database-migration-on-release.md 规则）
-- - 多次执行安全，已存在的索引会被跳过

-- ============================================================
-- xianyu_conversation 表：补建 account_id 维度的复合索引
-- 现有 uk_conv_peer 使用 seller_external_uid，但热点 SQL JOIN 条件用 account_id
-- ============================================================

-- 1. (tenant_id, account_id, peer_key) — get_online_conversations LEFT JOIN 条件
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    AND table_name = 'xianyu_conversation'
    AND index_name = 'idx_conv_tenant_account_peerkey'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_conv_tenant_account_peerkey ON xianyu_conversation (tenant_id, account_id, peer_key)',
    'SELECT ''V1.26: idx_conv_tenant_account_peerkey already exists, skipped''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. (tenant_id, account_id, external_buyer_id) — get_online_conversations LEFT JOIN OR 条件
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    AND table_name = 'xianyu_conversation'
    AND index_name = 'idx_conv_tenant_account_extbuyer'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_conv_tenant_account_extbuyer ON xianyu_conversation (tenant_id, account_id, external_buyer_id)',
    'SELECT ''V1.26: idx_conv_tenant_account_extbuyer already exists, skipped''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. (tenant_id, account_id, peer_external_uid) — _resolve_conversation_ids_for_context 查询
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    AND table_name = 'xianyu_conversation'
    AND index_name = 'idx_conv_tenant_account_peeruid'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_conv_tenant_account_peeruid ON xianyu_conversation (tenant_id, account_id, peer_external_uid)',
    'SELECT ''V1.26: idx_conv_tenant_account_peeruid already exists, skipped''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================
-- xianyu_chat_message 表：补建 peer_user_id 维度的查询索引
-- get_context_messages 分支 2 按 sender_user_id / receiver_user_id / peer_external_uid 查消息
-- ============================================================

-- 4. (tenant_id, account_id, sender_user_id, message_time) — 按 peer_user_id 查消息
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    AND table_name = 'xianyu_chat_message'
    AND index_name = 'idx_chatmsg_tenant_account_sender_time'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_chatmsg_tenant_account_sender_time ON xianyu_chat_message (tenant_id, account_id, sender_user_id, message_time)',
    'SELECT ''V1.26: idx_chatmsg_tenant_account_sender_time already exists, skipped''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5. (tenant_id, account_id, receiver_user_id, message_time) — 按 peer_user_id 查消息
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    AND table_name = 'xianyu_chat_message'
    AND index_name = 'idx_chatmsg_tenant_account_receiver_time'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_chatmsg_tenant_account_receiver_time ON xianyu_chat_message (tenant_id, account_id, receiver_user_id, message_time)',
    'SELECT ''V1.26: idx_chatmsg_tenant_account_receiver_time already exists, skipped''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 6. (tenant_id, account_id, peer_external_uid, message_time) — 按 peer_external_uid 查消息
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    AND table_name = 'xianyu_chat_message'
    AND index_name = 'idx_chatmsg_tenant_account_peeruid_time'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_chatmsg_tenant_account_peeruid_time ON xianyu_chat_message (tenant_id, account_id, peer_external_uid, message_time)',
    'SELECT ''V1.26: idx_chatmsg_tenant_account_peeruid_time already exists, skipped''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================
-- xianyu_message 表：补建 AI 回复预览查询索引
-- _apply_ai_reply_preview 查 to_user_id IN (...) + is_auto_reply = 1
-- ============================================================

-- 7. (tenant_id, account_id, to_user_id, is_auto_reply, msg_time) — AI 回复预览
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    AND table_name = 'xianyu_message'
    AND index_name = 'idx_msg_tenant_account_touser_auto_time'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_msg_tenant_account_touser_auto_time ON xianyu_message (tenant_id, account_id, to_user_id, is_auto_reply, msg_time)',
    'SELECT ''V1.26: idx_msg_tenant_account_touser_auto_time already exists, skipped''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
