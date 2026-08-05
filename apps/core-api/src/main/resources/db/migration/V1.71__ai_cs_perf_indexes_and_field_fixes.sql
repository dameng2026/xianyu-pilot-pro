-- V1.71: AI 客服性能索引与字段优化
--
-- 1. 为知识库三张表添加 FULLTEXT 全文索引，提升 RAG 关键词检索性能
-- 2. 将 ai_cs_learned_kb.question 字段从 VARCHAR(1000) 改为 TEXT，防止超长问题被截断
-- 3. 为 ai_cs_learned_kb 和 ai_cs_kb_learning_log 添加 created_time 排序索引
-- 4. 添加 ai_cs_daily_stat 的查询索引
-- 5. 添加 ai_cs_kb_category 的 code 索引

-- ============================================================
-- 1. FULLTEXT 全文索引
-- ============================================================

-- ai_cs_knowledge: 按 content/keywords 全文搜索
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_knowledge' AND INDEX_NAME = 'ft_kb_content');
SET @sql = IF(@idx_exists = 0,
  'ALTER TABLE ai_cs_knowledge ADD FULLTEXT INDEX ft_kb_content (content, keywords)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ai_cs_learned_kb: 按 question/tags 全文搜索
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_learned_kb' AND INDEX_NAME = 'ft_learned_kb_question');
SET @sql = IF(@idx_exists = 0,
  'ALTER TABLE ai_cs_learned_kb ADD FULLTEXT INDEX ft_learned_kb_question (question, tags)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ai_cs_user_kb: 按 title/tags 全文搜索
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_user_kb' AND INDEX_NAME = 'ft_user_kb_title');
SET @sql = IF(@idx_exists = 0,
  'ALTER TABLE ai_cs_user_kb ADD FULLTEXT INDEX ft_user_kb_title (title, tags)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- 2. 字段类型修改
-- ============================================================

-- ai_cs_learned_kb.question: VARCHAR(1000) → TEXT（超长问题不被截断）
-- 使用 INFORMATION_SCHEMA 检查字段类型，避免重复执行
SET @col_type = (SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_learned_kb' AND COLUMN_NAME = 'question');
SET @sql = IF(@col_type IS NULL OR @col_type != 'text',
  'ALTER TABLE ai_cs_learned_kb MODIFY COLUMN question TEXT NOT NULL COMMENT ''用户问题''',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- 3. 排序索引
-- ============================================================

-- ai_cs_learned_kb: 按 created_time 倒序查询
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_learned_kb' AND INDEX_NAME = 'idx_learned_kb_created');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_learned_kb_created ON ai_cs_learned_kb(created_time)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ai_cs_kb_learning_log: 按 created_time 倒序查询
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_kb_learning_log' AND INDEX_NAME = 'idx_learning_log_created');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_learning_log_created ON ai_cs_kb_learning_log(created_time)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- 4. 日常统计查询索引
-- ============================================================

-- ai_cs_daily_stat: 按 stat_date 聚合查询
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_daily_stat' AND INDEX_NAME = 'idx_daily_stat_date');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_daily_stat_date ON ai_cs_daily_stat(stat_date)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- 5. ai_cs_kb_category code 索引
-- ============================================================

SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_kb_category' AND INDEX_NAME = 'idx_kb_category_code');
SET @sql = IF(@idx_exists = 0,
  'CREATE INDEX idx_kb_category_code ON ai_cs_kb_category(code)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;