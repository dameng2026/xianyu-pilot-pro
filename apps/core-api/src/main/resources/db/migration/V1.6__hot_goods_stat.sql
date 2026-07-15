-- ============================================================
-- 热销商品统计表迁移脚本
-- 说明：存储当日销量大于5件的商品数据，用于模型训练和爆款文案分析
-- ============================================================

-- 创建热销商品统计表
CREATE TABLE IF NOT EXISTS `hot_goods_stat` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `tenant_id` BIGINT NOT NULL DEFAULT 0 COMMENT '租户ID',
    `goods_id` BIGINT NOT NULL DEFAULT 0 COMMENT '关联商品ID(xianyu_goods.id)',
    `account_id` BIGINT NOT NULL DEFAULT 0 COMMENT '闲鱼账号ID',
    `title` VARCHAR(500) NULL COMMENT '商品文案标题',
    `price` VARCHAR(50) NULL COMMENT '商品价格',
    `cover_pic` TEXT NULL COMMENT '商品封面图URL',
    `daily_sales` INT NOT NULL DEFAULT 0 COMMENT '当日销量',
    `stat_date` DATE NOT NULL COMMENT '统计日期',
    `deleted` INT NOT NULL DEFAULT 0 COMMENT '逻辑删除(0-未删 1-已删)',
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_tenant_stat_date` (`tenant_id`, `stat_date`),
    INDEX `idx_stat_date` (`stat_date`),
    INDEX `idx_goods_id` (`goods_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='热销商品统计表 - 存储当日销量>5的商品数据，用于模型训练和爆款文案分析';