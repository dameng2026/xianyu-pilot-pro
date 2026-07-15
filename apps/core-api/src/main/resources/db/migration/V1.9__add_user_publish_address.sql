-- 创建用户常用发布地址表
-- 记录用户每次发布商品时设置的位置信息，用于工作流自动填充常用地址
CREATE TABLE IF NOT EXISTS user_publish_address (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    user_id BIGINT DEFAULT NULL COMMENT '用户ID',
    address_poi_name VARCHAR(500) DEFAULT '' COMMENT '地址POI名称',
    address_city VARCHAR(100) DEFAULT '' COMMENT '城市',
    address_area VARCHAR(100) DEFAULT '' COMMENT '区域',
    address_detail VARCHAR(500) DEFAULT '' COMMENT '详细地址',
    use_count INT DEFAULT 1 COMMENT '使用次数',
    deleted TINYINT DEFAULT 0 COMMENT '是否删除 0未删除 1已删除',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_tenant_user (tenant_id, user_id, deleted),
    INDEX idx_tenant_use_count (tenant_id, deleted, use_count DESC),
    UNIQUE KEY uk_tenant_user_address (tenant_id, user_id, address_poi_name(200))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户常用发布地址';