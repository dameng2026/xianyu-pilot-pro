-- 供货商品表
CREATE TABLE IF NOT EXISTS supply_product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    seller_id BIGINT NOT NULL COMMENT '供货商用户ID',
    product_type VARCHAR(10) NOT NULL DEFAULT 'text' COMMENT 'text=文本货源, card=卡密货源',
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(200) DEFAULT '',
    content TEXT COMMENT '商品描述/正文',
    delivery_content TEXT COMMENT '文本货源的发货内容',
    cover_url VARCHAR(500) DEFAULT '',
    images_json JSON COMMENT '商品图片数组',
    category VARCHAR(50) DEFAULT '' COMMENT 'AI分类',
    price_cent BIGINT NOT NULL DEFAULT 0 COMMENT '售价(分)',
    stock INT NOT NULL DEFAULT -1 COMMENT '库存(-1=无限,文本货源默认-1)',
    card_group_id BIGINT NULL COMMENT '卡密货源关联的 card_group.id',
    audit_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/rejected/approved',
    audit_reason VARCHAR(500) DEFAULT '' COMMENT '驳回原因',
    audit_at DATETIME NULL,
    auditor_id BIGINT NULL,
    status TINYINT NOT NULL DEFAULT 0 COMMENT '0=下架,1=上架(仅 audit_status=approved 时可上架)',
    weight INT NOT NULL DEFAULT 0 COMMENT '展示权重(越大越靠前,后台可调)',
    bought_count INT NOT NULL DEFAULT 0 COMMENT '销量',
    rating_avg DECIMAL(3,2) DEFAULT 5.00 COMMENT '平均评分',
    rating_count INT DEFAULT 0,
    sort_order INT DEFAULT 0,
    commission_rate DECIMAL(5,4) DEFAULT 0.0500 COMMENT '单品抽佣率(默认5%),0=用全局配置',
    created_time DATETIME,
    updated_time DATETIME,
    deleted TINYINT NOT NULL DEFAULT 0,
    INDEX idx_supply_seller(seller_id, deleted, audit_status),
    INDEX idx_supply_status(audit_status, status, deleted),
    INDEX idx_supply_category(category, status, deleted),
    INDEX idx_supply_card_group(card_group_id),
    INDEX idx_supply_weight(weight, status, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供货商品表';

-- 通用审核记录表
CREATE TABLE IF NOT EXISTS audit_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    module_key VARCHAR(40) NOT NULL COMMENT 'supply_product/other_module',
    business_id BIGINT NOT NULL COMMENT '业务记录ID(如 supply_product.id)',
    submitter_id BIGINT NOT NULL,
    auditor_id BIGINT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected',
    reason VARCHAR(500) DEFAULT '' COMMENT '驳回原因或通过备注',
    snapshot_json JSON COMMENT '提交时数据快照',
    submitted_at DATETIME,
    audited_at DATETIME,
    INDEX idx_audit_module(module_key, status),
    INDEX idx_audit_submitter(submitter_id, status),
    INDEX idx_audit_auditor(auditor_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通用审核记录';

-- card_group 加关联供货商品字段（兼容 MySQL 8.0 的动态 SQL）
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'card_group' AND COLUMN_NAME = 'linked_supply_product_id');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE card_group ADD COLUMN linked_supply_product_id BIGINT NULL COMMENT ''关联的供货商品ID''',
    'SELECT ''column linked_supply_product_id already exists'' AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
