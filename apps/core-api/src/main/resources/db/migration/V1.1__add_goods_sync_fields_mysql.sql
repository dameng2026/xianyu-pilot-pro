-- ============================================================
-- 商品表字段补全迁移脚本 (MySQL 5.7+ 兼容版)
-- 说明：为 xianyu_goods 表添加商品同步所需的新字段
-- 执行前请备份数据库
-- ============================================================

-- 注意：以下语句如果字段已存在会报错，可在执行前用 SHOW COLUMNS 确认
-- 或使用存储过程实现幂等（见下方注释）

-- 1. 修改 price 字段类型为 VARCHAR（如果之前是 DECIMAL）
ALTER TABLE xianyu_goods MODIFY COLUMN price VARCHAR(50) NULL COMMENT '价格';

-- 2. 新增售价字段
ALTER TABLE xianyu_goods ADD COLUMN sold_price VARCHAR(50) NULL COMMENT '售价' AFTER price;

-- 3. 新增封面图字段
ALTER TABLE xianyu_goods ADD COLUMN cover_pic TEXT NULL COMMENT '封面图URL' AFTER sold_price;

-- 4. 新增库存数量字段（整数）
ALTER TABLE xianyu_goods ADD COLUMN quantity INT DEFAULT 0 COMMENT '库存数量' AFTER stock;

-- 5. 新增曝光次数
ALTER TABLE xianyu_goods ADD COLUMN exposure_count INT DEFAULT 0 COMMENT '曝光次数' AFTER quantity;

-- 6. 新增浏览次数
ALTER TABLE xianyu_goods ADD COLUMN view_count INT DEFAULT 0 COMMENT '浏览次数' AFTER exposure_count;

-- 7. 新增想要人数
ALTER TABLE xianyu_goods ADD COLUMN want_count INT DEFAULT 0 COMMENT '想要人数' AFTER view_count;

-- 8. 新增详情页URL
ALTER TABLE xianyu_goods ADD COLUMN detail_url TEXT NULL COMMENT '详情页URL' AFTER want_count;

-- 9. 新增详情描述文字
ALTER TABLE xianyu_goods ADD COLUMN detail_info TEXT NULL COMMENT '详情描述文字' AFTER detail_url;

-- 10. 新增排序序号
ALTER TABLE xianyu_goods ADD COLUMN sort_order INT DEFAULT 0 COMMENT '排序序号' AFTER status;

-- 11. 添加索引
ALTER TABLE xianyu_goods ADD INDEX idx_account_external_goods (account_id, external_goods_id);
ALTER TABLE xianyu_goods ADD INDEX idx_tenant_status (tenant_id, status, deleted);