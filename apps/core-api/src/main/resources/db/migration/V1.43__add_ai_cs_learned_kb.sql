-- V1.43__add_ai_cs_learned_kb.sql
-- AI 客服自主学习知识库相关表（5 张）
-- 功能：每日定时从买家-卖家对话中提取高价值 Q&A，脱敏后入库，供自动回复 AI 通过 RAG 检索使用

-- 1. 动态分类表（AI 自动生成分类，如"电子销售"、"视频剪辑"等）
CREATE TABLE IF NOT EXISTS ai_cs_kb_category (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(64) NOT NULL COMMENT '分类名称（AI 自动生成）',
    name_hash       CHAR(32) NOT NULL COMMENT '分类名 MD5，用于去重',
    parent_id       BIGINT NULL COMMENT '父分类 ID，支持二级分类（NULL 为一级）',
    sort_order      INT NOT NULL DEFAULT 0,
    entry_count     INT NOT NULL DEFAULT 0 COMMENT '该分类下条目数（冗余计数）',
    source          VARCHAR(16) NOT NULL DEFAULT 'ai' COMMENT 'ai=AI 自动生成 / manual=后台手动',
    deleted         TINYINT NOT NULL DEFAULT 0,
    created_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_kb_cat_name_hash (name_hash, deleted),
    INDEX idx_kb_cat_parent (parent_id, sort_order)
) COMMENT='AI 客服学习 KB 动态分类表';

-- 2. 平台共享学习 KB 主表（跨租户共享，从会话中提取的 Q&A）
CREATE TABLE IF NOT EXISTS ai_cs_learned_kb (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    category_id     BIGINT NULL COMMENT '关联 ai_cs_kb_category.id',
    question        VARCHAR(1000) NOT NULL COMMENT '买家问题（已脱敏）',
    answer          MEDIUMTEXT NOT NULL COMMENT '卖家回复（已脱敏）',
    tags            VARCHAR(512) NULL COMMENT 'AI 标签，逗号分隔',
    source_summary  VARCHAR(500) NULL COMMENT '一句话摘要',
    content_hash    CHAR(32) NOT NULL COMMENT 'question+answer 的 MD5',
    score           INT NOT NULL DEFAULT 50 COMMENT '价值评分 0-100',
    review_status   VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected',
    reviewed_by     BIGINT NULL,
    reviewed_time   DATETIME NULL,
    reject_reason   VARCHAR(255) NULL,
    enabled         TINYINT NOT NULL DEFAULT 1,
    vector_indexed  TINYINT NOT NULL DEFAULT 0 COMMENT '是否已写入 RAG 向量库',
    vector_error    VARCHAR(255) NULL,
    source_count    INT NOT NULL DEFAULT 1 COMMENT '该 Q&A 被多少会话提取出来',
    source_conv_ids TEXT NULL COMMENT '来源会话 ID 列表（JSON 数组，最多 20 个）',
    learn_batch_id  VARCHAR(64) NOT NULL COMMENT '学习批次 ID',
    sensitive_filtered TINYINT NOT NULL DEFAULT 1 COMMENT '是否已完成敏感信息过滤',
    deleted         TINYINT NOT NULL DEFAULT 0,
    created_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_learned_kb_hash (content_hash, deleted),
    INDEX idx_learned_kb_cat (category_id, enabled, score),
    INDEX idx_learned_kb_status (review_status, enabled, vector_indexed),
    INDEX idx_learned_kb_batch (learn_batch_id)
) COMMENT='AI 客服学习知识库主表（跨租户共享）';

-- 3. 用户私有 KB 表（仅本人可见，用户手动添加）
CREATE TABLE IF NOT EXISTS ai_cs_user_kb (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id       BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    title           VARCHAR(255) NOT NULL,
    content         MEDIUMTEXT NOT NULL,
    category        VARCHAR(64) NULL,
    tags            VARCHAR(512) NULL,
    vector_indexed  TINYINT NOT NULL DEFAULT 0,
    vector_error    VARCHAR(255) NULL,
    enabled         TINYINT NOT NULL DEFAULT 1,
    deleted         TINYINT NOT NULL DEFAULT 0,
    created_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_kb_user (tenant_id, user_id, enabled, deleted),
    INDEX idx_user_kb_vector (vector_indexed, deleted)
) COMMENT='用户私有知识库表（仅本人可见）';

-- 4. 用户启用关系表（用户选择启用哪些 KB：平台学习 KB 或自己的私有 KB）
CREATE TABLE IF NOT EXISTS ai_cs_user_kb_binding (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id       BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    kb_type         VARCHAR(16) NOT NULL COMMENT 'learned=平台学习 KB / user=用户私有 KB',
    kb_id           BIGINT NOT NULL,
    enabled         TINYINT NOT NULL DEFAULT 1,
    bound_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted         TINYINT NOT NULL DEFAULT 0,
    UNIQUE KEY uk_user_kb_binding (tenant_id, user_id, kb_type, kb_id, deleted),
    INDEX idx_binding_user (tenant_id, user_id, enabled, deleted)
) COMMENT='用户启用的知识库绑定关系';

-- 5. 学习作业审计日志表（每次学习作业的统计与状态）
CREATE TABLE IF NOT EXISTS ai_cs_kb_learning_log (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    batch_id            VARCHAR(64) NOT NULL,
    started_at          DATETIME NOT NULL,
    finished_at         DATETIME NULL,
    status              VARCHAR(16) NOT NULL COMMENT 'running/success/failed/partial',
    total_conversations INT NOT NULL DEFAULT 0,
    kept_conversations  INT NOT NULL DEFAULT 0,
    rejected_by_ai_ratio INT NOT NULL DEFAULT 0,
    extracted_items     INT NOT NULL DEFAULT 0,
    deduplicated_items  INT NOT NULL DEFAULT 0,
    llm_tokens_used     INT NOT NULL DEFAULT 0,
    llm_cost_yuan       DECIMAL(10,4) NOT NULL DEFAULT 0,
    error_message       TEXT NULL,
    config_snapshot     JSON NULL,
    deleted             TINYINT NOT NULL DEFAULT 0,
    created_time        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_learning_log_batch (batch_id),
    INDEX idx_learning_log_status (status, started_at)
) COMMENT='AI 客服 KB 学习作业审计日志';
