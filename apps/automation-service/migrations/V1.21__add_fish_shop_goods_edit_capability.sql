-- 鱼小铺商品编辑能力字段
-- 用于商品列表"编辑"按钮的前置判断：只有 can_edit=1 的鱼小铺商品才允许进入编辑页
-- 注：automation-service 使用 SQLAlchemy create_all + main.py.runtime_compatibility_columns() 自动建表/补字段，
-- 本文件为文档性质，实际表结构变更由 ORM 模型 (entities.py) 与 runtime_compatibility_columns() 保证幂等。
-- 旧库升级时，main.py 会通过 ALTER TABLE ADD COLUMN 补齐缺失字段。

ALTER TABLE xianyu_goods ADD COLUMN can_edit TINYINT NOT NULL DEFAULT 1
  COMMENT '鱼小铺商品是否支持编辑（来自 itemExtendList.itemEdit/itemOperationInfo）。1=可编辑，0=不可编辑';
ALTER TABLE xianyu_goods ADD COLUMN edit_note VARCHAR(500) NOT NULL DEFAULT ''
  COMMENT '鱼小铺商品不可编辑时的提示文案（来自 itemExtendList.itemEdit.note）';
