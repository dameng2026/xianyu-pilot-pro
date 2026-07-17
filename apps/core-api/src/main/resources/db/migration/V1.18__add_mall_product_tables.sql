-- 货源商城商品表
-- 支持文本商品（直接发货内容）与卡密商品（库存池发卡）两种类型
-- price_cent 以分为单位存储，避免浮点数精度问题
CREATE TABLE IF NOT EXISTS mall_product (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '租户ID(0=全局共享)',
  product_type VARCHAR(10) NOT NULL DEFAULT 'text' COMMENT '商品类型: text=文本商品, card=卡密商品',
  title VARCHAR(200) NOT NULL COMMENT '商品标题',
  subtitle VARCHAR(200) NOT NULL DEFAULT '' COMMENT '副标题(卡密商品)',
  content TEXT COMMENT '商品正文/描述',
  price_cent BIGINT NOT NULL DEFAULT 0 COMMENT '价格(分)',
  delivery_content TEXT COMMENT '发货内容(文本商品)',
  cover_url VARCHAR(500) NOT NULL DEFAULT '' COMMENT '封面图URL',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=下架, 1=上架',
  category VARCHAR(50) NOT NULL DEFAULT '' COMMENT 'AI自动分类',
  ai_category_confidence DECIMAL(5,2) NOT NULL DEFAULT 0 COMMENT 'AI分类置信度',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
  bought_count INT NOT NULL DEFAULT 0 COMMENT '已购买人数',
  created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted TINYINT NOT NULL DEFAULT 0 COMMENT '软删除',
  PRIMARY KEY (id),
  INDEX idx_mall_product_type (product_type, status, deleted),
  INDEX idx_mall_product_category (category, status, deleted),
  INDEX idx_mall_product_tenant (tenant_id, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='货源商城商品';

-- 卡密库存表
-- 卡密商品独立维护可用库存，售出时绑定订单号并标记为 sold
CREATE TABLE IF NOT EXISTS mall_card_key (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  product_id BIGINT NOT NULL COMMENT '商品ID',
  card_content TEXT NOT NULL COMMENT '卡密内容',
  status VARCHAR(15) NOT NULL DEFAULT 'available' COMMENT '状态: available=可用, sold=已售, disabled=已禁用',
  order_no VARCHAR(64) NOT NULL DEFAULT '' COMMENT '售出订单号',
  created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  sold_time DATETIME NULL COMMENT '售出时间',
  PRIMARY KEY (id),
  INDEX idx_card_key_product (product_id, status),
  INDEX idx_card_key_order (order_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='卡密库存';

-- 常见问题表
-- 商城前台展示的 FAQ，按 sort_order 排序
CREATE TABLE IF NOT EXISTS mall_faq (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '租户ID',
  question VARCHAR(500) NOT NULL COMMENT '问题',
  answer TEXT NOT NULL COMMENT '答案',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=禁用, 1=启用',
  created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted TINYINT NOT NULL DEFAULT 0 COMMENT '软删除',
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='货源商城常见问题';
