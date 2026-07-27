-- 鱼小铺商品曝光/浏览数据指标字段
-- 注：automation-service 使用 SQLAlchemy create_all + main.py.runtime_compatibility_columns() 自动建表/补字段，
-- 本文件为文档性质，实际表结构变更由 ORM 模型 (entities.py) 与 runtime_compatibility_columns() 保证幂等。
-- 旧库升级时，main.py 会通过 ALTER TABLE ADD COLUMN 补齐缺失字段。

ALTER TABLE xianyu_goods ADD COLUMN gmt_create DATETIME NULL
  COMMENT '闲鱼商品创建时间（鱼小铺商品管理接口 gmtCreate 字段）';
ALTER TABLE xianyu_goods ADD COLUMN exposure_count_30d INT NOT NULL DEFAULT 0
  COMMENT '最近30天曝光次数（鱼小铺数据罗盘 showPv）';
ALTER TABLE xianyu_goods ADD COLUMN view_count_30d INT NOT NULL DEFAULT 0
  COMMENT '最近30天浏览次数（鱼小铺数据罗盘 ipv）';
