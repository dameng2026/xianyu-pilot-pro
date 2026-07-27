-- 鱼小铺多规格商品 SKU/规格/规格值/编辑快照表
-- 注：automation-service 使用 SQLAlchemy create_all 自动建表，本文件为文档性质；
-- 实际表结构由 ORM 模型 (entities.py) 中的 XianyuGoodsProperty / XianyuGoodsPropertyValue / XianyuGoodsSku / XianyuGoodsEditSnapshot 定义。

-- 规格类型表（颜色、尺码等，一个商品最多 2 个规格类型）
CREATE TABLE IF NOT EXISTS xianyu_goods_property (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NOT NULL COMMENT '租户ID',
  account_id BIGINT NOT NULL COMMENT '闲鱼账号ID',
  external_goods_id VARCHAR(128) NOT NULL COMMENT '闲鱼商品itemId',
  property_name VARCHAR(128) NOT NULL COMMENT '规格名称',
  support_image TINYINT NOT NULL DEFAULT 0 COMMENT '是否支持规格图片：1是 0否',
  sort_order INT NOT NULL DEFAULT 0,
  deleted TINYINT NOT NULL DEFAULT 0,
  created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_goods_property_lookup (tenant_id, external_goods_id, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鱼小铺商品规格类型';

-- 规格值表（红色、蓝色、S、M、L 等）
CREATE TABLE IF NOT EXISTS xianyu_goods_property_value (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NOT NULL,
  property_id BIGINT NOT NULL COMMENT '关联规格类型ID',
  external_goods_id VARCHAR(128) NOT NULL,
  property_value VARCHAR(255) NOT NULL COMMENT '规格值',
  property_value_img VARCHAR(512) NULL COMMENT '规格图片URL（仅 support_image=1 时有值）',
  sort_order INT NOT NULL DEFAULT 0,
  deleted TINYINT NOT NULL DEFAULT 0,
  created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_property_value_lookup (property_id, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鱼小铺商品规格值';

-- SKU 表（每个规格组合一行；property_key 用于响应乱序匹配）
CREATE TABLE IF NOT EXISTS xianyu_goods_sku (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NOT NULL,
  account_id BIGINT NOT NULL,
  external_goods_id VARCHAR(128) NOT NULL COMMENT '闲鱼商品itemId',
  sku_id VARCHAR(128) NULL COMMENT '闲鱼返回的skuId',
  inventory_id VARCHAR(128) NULL COMMENT '闲鱼返回的inventoryId',
  property_list_json JSON NOT NULL COMMENT '规格组合：[{propertyText,valueText}, ...]',
  property_key VARCHAR(512) NOT NULL COMMENT '规格组合规范化键',
  price_in_cent BIGINT NOT NULL DEFAULT 0 COMMENT 'SKU价格（单位：分）',
  quantity INT NOT NULL DEFAULT 0 COMMENT 'SKU库存',
  deleted TINYINT NOT NULL DEFAULT 0,
  created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_sku_goods_lookup (tenant_id, external_goods_id, deleted),
  UNIQUE KEY uk_sku_property_key (external_goods_id, property_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鱼小铺商品 SKU';

-- 编辑快照表（保存发布/编辑成功后的完整商品数据，用于回显兜底与售整自动上架）
CREATE TABLE IF NOT EXISTS xianyu_goods_edit_snapshot (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NOT NULL,
  account_id BIGINT NOT NULL,
  external_goods_id VARCHAR(128) NOT NULL,
  snapshot_json JSON NOT NULL COMMENT '完整商品数据快照',
  source VARCHAR(32) NOT NULL DEFAULT 'publish' COMMENT '快照来源：publish/edit/detail_api/relist',
  account_type VARCHAR(16) NOT NULL DEFAULT 'fish_shop' COMMENT '账号类型：fish_shop / normal',
  deleted TINYINT NOT NULL DEFAULT 0,
  created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_snapshot_lookup (account_id, external_goods_id, account_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品编辑/发布快照（鱼小铺+普通账号）';
