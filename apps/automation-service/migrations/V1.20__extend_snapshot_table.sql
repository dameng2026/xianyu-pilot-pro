-- 扩展 xianyu_goods_edit_snapshot 表支持普通账号快照
-- 注：automation-service 使用 SQLAlchemy create_all + main.py.runtime_compatibility_columns() 自动建表/补字段，
-- 本文件为文档性质；实际表结构变更由 ORM 模型 (entities.py) 与 runtime_compatibility_columns() 保证幂等。
-- 旧库升级时，main.py 会通过 ALTER TABLE ADD COLUMN 补齐 account_type 字段。

-- 新增 account_type 字段，区分鱼小铺与普通账号快照
ALTER TABLE xianyu_goods_edit_snapshot ADD COLUMN account_type VARCHAR(16) NOT NULL DEFAULT 'fish_shop'
  COMMENT '账号类型：fish_shop / normal';

-- 添加查询索引：按账号 + 商品ID + 账号类型查找快照
ALTER TABLE xianyu_goods_edit_snapshot ADD INDEX idx_snapshot_lookup (account_id, external_goods_id, account_type);
