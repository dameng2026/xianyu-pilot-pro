-- V1.75 小梦主动消息相关表
-- 1. user_feature_visit_log：用户功能首次访问记录表，用于检测"第一次进入/使用"
-- 2. ai_cs_proactive_message：小梦主动消息表，存储待推送的主动沟通内容
-- 本文件由 SchemaCompatibilityRunner.ensureProactiveMessageTables() 幂等创建。

-- 用户功能首次访问记录表
CREATE TABLE IF NOT EXISTS user_feature_visit_log (
    id                BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id           BIGINT NOT NULL COMMENT '用户 ID',
    tenant_id         BIGINT NOT NULL COMMENT '租户 ID',
    feature_key       VARCHAR(64) NOT NULL COMMENT '功能标识(如 workflow_first_visit)',
    visit_count       INT NOT NULL DEFAULT 1 COMMENT '访问次数',
    first_visit_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次访问时间',
    last_visit_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最近访问时间',
    created_time      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_feature (user_id, tenant_id, feature_key),
    INDEX idx_feature_visit (tenant_id, feature_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户功能首次访问记录表';

-- 小梦主动消息表
CREATE TABLE IF NOT EXISTS ai_cs_proactive_message (
    id             BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id        BIGINT NOT NULL COMMENT '用户 ID',
    tenant_id      BIGINT NOT NULL COMMENT '租户 ID',
    feature_key    VARCHAR(64) NOT NULL COMMENT '触发功能标识(如 workflow_first_visit)',
    session_id     BIGINT NULL COMMENT '关联的 AI 客服会话 ID',
    message_id     BIGINT NULL COMMENT '关联的 ai_cs_message 消息 ID',
    title          VARCHAR(128) NOT NULL COMMENT '通知标题',
    content        MEDIUMTEXT NOT NULL COMMENT '通知内容(用于弹窗展示)',
    action_text    VARCHAR(64) NOT NULL DEFAULT '查看' COMMENT '操作按钮文案',
    status         VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/shown/read/dismissed',
    created_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shown_time     DATETIME NULL COMMENT '前端展示时间',
    read_time      DATETIME NULL COMMENT '用户点击查看时间',
    UNIQUE KEY uk_proactive_user_feature (user_id, tenant_id, feature_key),
    INDEX idx_proactive_status (tenant_id, user_id, status),
    INDEX idx_proactive_created (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='小梦主动消息表';
