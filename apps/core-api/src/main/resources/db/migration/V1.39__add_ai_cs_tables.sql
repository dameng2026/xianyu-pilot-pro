-- AI 客服"小梦"功能：会话/消息/计费配置/知识库/每日统计/工具调用日志
-- 注：core-api 不使用 Flyway 框架，本文件为文档性质；实际表结构变更由 SchemaCompatibilityRunner 在启动时幂等创建。

CREATE TABLE IF NOT EXISTS ai_cs_session (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_token VARCHAR(64) NOT NULL UNIQUE COMMENT '会话标识（前端持有）',
    user_id BIGINT NOT NULL COMMENT '所属用户',
    tenant_id BIGINT NOT NULL COMMENT '租户隔离',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1=活跃 0=已关闭',
    message_count INT NOT NULL DEFAULT 0 COMMENT '当前会话消息计数（含 user 与 assistant）',
    casual_count INT NOT NULL DEFAULT 0 COMMENT '连续闲聊计数',
    casual_reminded TINYINT NOT NULL DEFAULT 0 COMMENT '本会话是否已提醒过闲聊（0/1）',
    compressed_summary TEXT NULL COMMENT '历史压缩摘要（压缩后写入下一会话）',
    last_active_time DATETIME NULL,
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cs_session_user(user_id, status, last_active_time),
    INDEX idx_cs_session_tenant(tenant_id, created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服会话';

CREATE TABLE IF NOT EXISTS ai_cs_message (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    role VARCHAR(16) NOT NULL COMMENT 'user / assistant / system',
    content MEDIUMTEXT NOT NULL,
    tokens_charged INT NOT NULL DEFAULT 0 COMMENT '本条消息扣费 Token（assistant 才扣费，0 表示未扣费）',
    is_casual TINYINT NOT NULL DEFAULT 0 COMMENT '是否被判定为闲聊（0/1）',
    tool_calls TEXT NULL COMMENT 'AI 触发的工具调用 JSON',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_cs_msg_session(session_id, id),
    INDEX idx_cs_msg_user(user_id, created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服消息';

CREATE TABLE IF NOT EXISTS ai_cs_billing_config (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NULL COMMENT '租户隔离；NULL 表示全局默认',
    per_message_tokens INT NOT NULL DEFAULT 3 COMMENT '每条成功回复扣费 Token 数',
    max_context_messages INT NOT NULL DEFAULT 50 COMMENT '单会话上下文上限',
    casual_threshold INT NOT NULL DEFAULT 5 COMMENT '连续闲聊提醒阈值',
    casual_reminder_text TEXT NULL COMMENT '闲聊提醒文案',
    enabled TINYINT NOT NULL DEFAULT 1 COMMENT '客服总开关',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_cs_billing_tenant(tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服计费/行为配置';

CREATE TABLE IF NOT EXISTS ai_cs_knowledge (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NULL COMMENT '租户隔离；NULL 表示全局共享',
    category VARCHAR(64) NOT NULL COMMENT '分类 key（如 system_usage / xianyu_account / auto_reply）',
    title VARCHAR(255) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    keywords VARCHAR(512) NULL COMMENT '检索关键词，逗号分隔',
    priority INT NOT NULL DEFAULT 50 COMMENT '优先级，数字越大越优先',
    enabled TINYINT NOT NULL DEFAULT 1,
    sort_order INT NOT NULL DEFAULT 0,
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cs_kb_category(category, enabled, sort_order),
    INDEX idx_cs_kb_tenant(tenant_id, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服知识库';

CREATE TABLE IF NOT EXISTS ai_cs_daily_stat (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    stat_date DATE NOT NULL,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    session_count INT NOT NULL DEFAULT 0,
    user_message_count INT NOT NULL DEFAULT 0,
    assistant_message_count INT NOT NULL DEFAULT 0,
    tokens_charged INT NOT NULL DEFAULT 0,
    casual_count INT NOT NULL DEFAULT 0,
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_cs_daily(stat_date, user_id),
    INDEX idx_cs_daily_tenant(tenant_id, stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服每日统计';

CREATE TABLE IF NOT EXISTS ai_cs_tool_call (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    tool_name VARCHAR(64) NOT NULL,
    arguments TEXT NULL COMMENT '调用参数 JSON',
    status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending / confirmed / executed / rejected / failed',
    result TEXT NULL COMMENT '执行结果 JSON',
    requires_confirm TINYINT NOT NULL DEFAULT 1 COMMENT '是否需要用户确认',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cs_tool_session(session_id, status),
    INDEX idx_cs_tool_user(user_id, created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服工具调用日志';
