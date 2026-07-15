-- ============================================================
-- 重建 xianyu_conversation 表数据
--
-- 基于清洗后的 xianyu_chat_message 重新生成会话记录。
-- 先备份原表，然后 TRUNCATE 并用清洗后的消息数据重建。
--
-- 注意：执行此脚本前必须先执行 V1.3 和 V1.4 的字段迁移。
-- ============================================================

-- Step 1: 备份现有会话表
CREATE TABLE IF NOT EXISTS `xianyu_conversation_bak_202506` AS
SELECT * FROM `xianyu_conversation`;

-- Step 2: 清空会话表（准备重建）
TRUNCATE TABLE `xianyu_conversation`;

-- Step 3: 从清洗后的消息数据重建会话
INSERT INTO `xianyu_conversation` (
    `tenant_id`,
    `account_id`,
    `seller_external_uid`,
    `peer_external_uid`,
    `peer_key`,
    `buyer_name`,
    `goods_id`,
    `goods_title`,
    `last_message_time`,
    `last_message_content`,
    `unread_count`,
    `deleted`,
    `created_time`,
    `updated_time`
)
SELECT
    m.tenant_id,
    MAX(m.account_id) AS account_id,
    MAX(m.seller_external_uid) AS seller_external_uid,
    MAX(m.peer_external_uid) AS peer_external_uid,
    COALESCE(MAX(m.peer_external_uid), CONCAT('sid:', m.s_id)) AS peer_key,
    COALESCE(
        MAX(NULLIF(m.sender_user_name, '')),
        MAX(m.peer_external_uid),
        CONCAT('sid:', m.s_id)
    ) AS buyer_name,
    MAX(NULLIF(m.xy_goods_id, '')) AS goods_id,
    COALESCE(
        MAX(NULLIF(m.reminder_content, '')),
        MAX(NULLIF(m.xy_goods_id, '')),
        '未知商品'
    ) AS goods_title,
    FROM_UNIXTIME(MAX(m.message_time) / 1000) AS last_message_time,
    SUBSTRING_INDEX(
        GROUP_CONCAT(COALESCE(NULLIF(m.msg_content, ''), '[非文本消息]') ORDER BY m.message_time DESC SEPARATOR '|||'),
        '|||',
        1
    ) AS last_message_content,
    SUM(CASE WHEN m.direction = 'IN' AND (m.read_status = 0 OR m.read_status IS NULL) THEN 1 ELSE 0 END) AS unread_count,
    0 AS deleted,
    NOW() AS created_time,
    NOW() AS updated_time
FROM `xianyu_chat_message` m
WHERE m.deleted = 0
  AND m.parse_status IN ('ok', 'partial')
  AND m.seller_external_uid IS NOT NULL
  AND m.s_id IS NOT NULL
  AND m.s_id != ''
  AND (m.s_id NOT REGEXP '[一-龥]' OR m.parse_status = 'ok')
GROUP BY
    m.tenant_id,
    m.seller_external_uid,
    COALESCE(m.peer_external_uid, CONCAT('sid:', m.s_id));

-- Step 4: 更新 xianyu_message 表的会话关联
-- 将现有 xianyu_message 关联到新的 conversation id
UPDATE xianyu_message xm
JOIN xianyu_conversation xc
    ON xc.tenant_id = xm.tenant_id
    AND xc.account_id = xm.account_id
    AND (
        xc.peer_key = COALESCE(xm.from_user_id, CONCAT('sid:', xm.session_id))
        OR xc.peer_key = CONCAT('sid:', xm.session_id)
    )
SET xm.conversation_id = xc.id
WHERE xm.conversation_id IS NULL OR xm.conversation_id = 0;