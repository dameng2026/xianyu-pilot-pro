-- ============================================================
-- 统一 xianyu_chat_message / xianyu_conversation / xianyu_account
-- 相关 varchar 字段的字符集和排序规则为 utf8mb4 / utf8mb4_unicode_ci
--
-- 背景：MySQL 报错 1267 Illegal mix of collations
--   utf8mb4_0900_ai_ci(IMPLICIT) and utf8mb4_unicode_ci(IMPLICIT)
-- 当 JOIN 或比较时两侧字段 collation 不一致会触发该错误。
--
-- 修复策略：将所有参与互相比对的字符串字段统一为 utf8mb4_unicode_ci，
-- 避免隐式类型转换时的排序规则冲突。
-- ============================================================

-- ============================================================
-- Step 1: 修复 xianyu_chat_message 表
-- ============================================================
ALTER TABLE xianyu_chat_message
  MODIFY s_id VARCHAR(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  MODIFY sender_user_id VARCHAR(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  MODIFY receiver_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  MODIFY peer_external_uid VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  MODIFY seller_external_uid VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- Step 2: 修复 xianyu_conversation 表
-- ============================================================
ALTER TABLE xianyu_conversation
  MODIFY external_buyer_id VARCHAR(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  MODIFY peer_external_uid VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  MODIFY peer_key VARCHAR(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  MODIFY seller_external_uid VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- Step 3: 修复 xianyu_account 表
-- ============================================================
ALTER TABLE xianyu_account
  MODIFY external_uid VARCHAR(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;