-- =============================================================================
-- V1.66__add_delivery_text_source_segments.sql
-- =============================================================================
-- 功能：为 delivery_text_source 表新增 segments JSON 列，支持"多条正文逐条发送"
--       与"图片发货"功能。
--
-- 背景：
--   原先货源库的"正文"是单条 TEXT 字段（content 列），仅支持发送一条纯文本
--   或卡密模板。业务需要支持分步发送多条话术（如：商品说明 + 引导好评），
--   且每条可以是纯文本或单张图片二选一。
--
-- segments 结构（JSON 数组）：
--   [
--     {"type": "text",  "content": "您好，商品已发货..."},
--     {"type": "image", "imageUrl": "/uploads/images/xxx.jpg", "assetId": 123},
--     {"type": "text",  "content": "请确认收货后给个好评~"}
--   ]
--   - type=text  : 纯文本消息（content 必填，imageUrl 必须为空）
--   - type=image : 图片消息（imageUrl 必填，assetId 可选，content 必须为空）
--   - 每条 segment 只能是 text 或 image 二选一（互斥，由前后端双重校验）
--
-- 兼容性：
--   - MySQL 8.0 不支持 "ADD COLUMN IF NOT EXISTS"，使用 INFORMATION_SCHEMA 动态 SQL
--   - 字段可为空，旧货源（仅 content 字段）不受影响，执行端会回退到单条发送
--   - 保留 content 列不动，向后兼容
-- =============================================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_text_source' AND COLUMN_NAME = 'segments');

SET @sql = IF(@col_exists = 0,
  'ALTER TABLE delivery_text_source ADD COLUMN segments JSON NULL COMMENT ''多条正文配置（JSON 数组，每条 type=text/image 二选一，空则回退 content 单条发送）''',
  'SELECT 1');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
