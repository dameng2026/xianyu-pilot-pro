-- ============================================================
-- V1.7__auto_delivery_tables.sql
-- 自动发货模块新表：商品配置、声明、模板、全店配置
-- ============================================================

-- 1. 商品发货配置表（JSON存储各时机的配置）
CREATE TABLE IF NOT EXISTS `delivery_goods_config` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `goods_id` BIGINT NOT NULL COMMENT '商品ID',
    `config_json` TEXT COMMENT '发货配置JSON：{payDelivery:{...}, confirmDelivery:{...}, reviewDelivery:{...}}',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0,
    INDEX `idx_dgc_tenant_goods` (`tenant_id`, `goods_id`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品粒度自动发货配置';

-- 2. 发货声明表
CREATE TABLE IF NOT EXISTS `delivery_statement` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `enabled` TINYINT DEFAULT 0 COMMENT '是否启用',
    `content` TEXT COMMENT '声明文案',
    `scope` VARCHAR(32) DEFAULT 'all' COMMENT '生效范围：all=全店, specific=指定商品',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0,
    INDEX `idx_ds_tenant` (`tenant_id`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='发货声明配置';

-- 3. 发货模板表
CREATE TABLE IF NOT EXISTS `delivery_template` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `name` VARCHAR(200) NOT NULL COMMENT '模板名称',
    `type` TINYINT DEFAULT 6 COMMENT '类型：1付款后发货 2收货后赠送 3好评后赠送 4声明 5卡密 6普通文本',
    `status` TINYINT DEFAULT 1 COMMENT '状态：1启用 0禁用',
    `content` TEXT COMMENT '模板内容',
    `random_enabled` TINYINT DEFAULT 0 COMMENT '是否加入随机模板列表',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0,
    INDEX `idx_dt_tenant` (`tenant_id`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='发货模板';

-- 4. 全店默认发货配置表
CREATE TABLE IF NOT EXISTS `delivery_global_config` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `config_json` TEXT COMMENT '全局配置JSON',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0,
    INDEX `idx_dgc_tenant` (`tenant_id`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全店默认发货配置';

-- 5. 扩展 delivery_record 表字段（如有必要）
-- 检查是否需要添加 delivery_timing 和 delivery_mode 字段
SET @exist_timing := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_record' AND COLUMN_NAME = 'delivery_timing');
SET @sql_timing := IF(@exist_timing = 0, 'ALTER TABLE delivery_record ADD COLUMN delivery_timing VARCHAR(32) DEFAULT NULL COMMENT "发货时机：after_payment/after_receipt/after_review"', 'SELECT 1');
PREPARE stmt_timing FROM @sql_timing;
EXECUTE stmt_timing;
DEALLOCATE PREPARE stmt_timing;

SET @exist_mode := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_record' AND COLUMN_NAME = 'delivery_mode');
SET @sql_mode := IF(@exist_mode = 0, 'ALTER TABLE delivery_record ADD COLUMN delivery_mode VARCHAR(16) DEFAULT NULL COMMENT "发货模式：text/card"', 'SELECT 1');
PREPARE stmt_mode FROM @sql_mode;
EXECUTE stmt_mode;
DEALLOCATE PREPARE stmt_mode;

SET @exist_delivery_content := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_record' AND COLUMN_NAME = 'delivery_content');
SET @sql_dc := IF(@exist_delivery_content = 0, 'ALTER TABLE delivery_record ADD COLUMN delivery_content TEXT DEFAULT NULL COMMENT "实际发送内容"', 'SELECT 1');
PREPARE stmt_dc FROM @sql_dc;
EXECUTE stmt_dc;
DEALLOCATE PREPARE stmt_dc;

SET @exist_completed_time := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_record' AND COLUMN_NAME = 'completed_time');
SET @sql_ct := IF(@exist_completed_time = 0, 'ALTER TABLE delivery_record ADD COLUMN completed_time DATETIME DEFAULT NULL COMMENT "完成时间"', 'SELECT 1');
PREPARE stmt_ct FROM @sql_ct;
EXECUTE stmt_ct;
DEALLOCATE PREPARE stmt_ct;

-- 6. 扩展 xianyu_trade_order 表发货状态字段
SET @exist_delivery_status := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xianyu_trade_order' AND COLUMN_NAME = 'delivery_status');
SET @sql_ds := IF(@exist_delivery_status = 0, 'ALTER TABLE xianyu_trade_order ADD COLUMN delivery_status VARCHAR(16) DEFAULT NULL COMMENT "发货状态：pending/shipped"', 'SELECT 1');
PREPARE stmt_ds FROM @sql_ds;
EXECUTE stmt_ds;
DEALLOCATE PREPARE stmt_ds;