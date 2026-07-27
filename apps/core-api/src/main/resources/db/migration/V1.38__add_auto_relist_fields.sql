-- 售整自动上架功能：在 xianyu_goods 表新增 6 个字段（4 个核心 + 2 个冗余用于跨库查询优化）
-- 注：core-api 不使用 Flyway 框架，本文件为文档性质；实际表结构变更由 SchemaCompatibilityRunner 在启动时幂等添加。
-- SchemaCompatibilityRunner.addColumnIfMissing 保证幂等，旧库升级时自动补齐字段。

ALTER TABLE xianyu_goods ADD COLUMN auto_relist_enabled TINYINT NOT NULL DEFAULT 0
  COMMENT '售整自动上架开关：0关 1开';
ALTER TABLE xianyu_goods ADD COLUMN next_relist_goods_id BIGINT NULL
  COMMENT '重发后的新商品记录ID（指向新 xianyu_goods.id）';
ALTER TABLE xianyu_goods ADD COLUMN relist_source_goods_id BIGINT NULL
  COMMENT '本商品是从哪个原商品重发来的（反向追溯）';
ALTER TABLE xianyu_goods ADD COLUMN last_relist_at DATETIME NULL
  COMMENT '上次重发时间，用于审计';
ALTER TABLE xianyu_goods ADD COLUMN has_snapshot TINYINT NOT NULL DEFAULT 0
  COMMENT '是否有完整数据快照：0无 1有（由 Python 端写入快照时同步更新）';
ALTER TABLE xianyu_goods ADD COLUMN original_quantity INT NULL
  COMMENT '商品原始库存（从快照同步），用于判断 autoRelist 触发条件';
ALTER TABLE xianyu_goods ADD INDEX idx_auto_relist_enabled (auto_relist_enabled, status, next_relist_goods_id);
