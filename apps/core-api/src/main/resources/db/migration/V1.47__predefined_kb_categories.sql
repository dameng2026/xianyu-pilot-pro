-- ============================================================
-- V1.47: 客服知识库分类化改造
-- 1. ai_cs_kb_category 扩展：code/keywords/is_system 字段
-- 2. 预定义 15 个业务场景分类（is_system=1，不可删）
-- 3. ai_cs_learned_kb 扩展：conversation_turn_count 字段
-- 4. 历史数据迁移：现有 LLM 自动分类归到最接近的预定义分类
-- 注意：仅追加/扩展，不删除任何已有字段或数据
-- ============================================================

-- 1. ai_cs_kb_category 扩展字段（幂等）
ALTER TABLE ai_cs_kb_category
  ADD COLUMN IF NOT EXISTS code VARCHAR(32) NULL COMMENT '分类业务代码（预定义分类的唯一标识）',
  ADD COLUMN IF NOT EXISTS keywords JSON NULL COMMENT '关键词规则数组，用于检索时分类预过滤',
  ADD COLUMN IF NOT EXISTS is_system TINYINT NOT NULL DEFAULT 0 COMMENT '1=预定义不可删，0=可删';

-- 2. ai_cs_learned_kb 扩展字段（幂等）
ALTER TABLE ai_cs_learned_kb
  ADD COLUMN IF NOT EXISTS conversation_turn_count INT NOT NULL DEFAULT 0 COMMENT '原始对话轮数';

-- 3. 预定义 15 个业务场景分类（幂等插入，已存在则跳过）
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, sort_order, source, deleted, created_time, updated_time) VALUES
  ('库存查询', MD5('库存查询'), 'stock_query',
   '["库存","有货","现货","还有吗","没货","缺货","断货","在不在"]', 1, 1, 'manual', 0, NOW(), NOW()),
  ('发货跟踪', MD5('发货跟踪'), 'shipping_track',
   '["发货","物流","快递","什么时候发","单号","运单","发出","揽收"]', 1, 2, 'manual', 0, NOW(), NOW()),
  ('退款售后', MD5('退款售后'), 'refund_aftersale',
   '["退款","退货","换货","质量","坏了","破损","不想要","退钱"]', 1, 3, 'manual', 0, NOW(), NOW()),
  ('商品咨询', MD5('商品咨询'), 'product_consult',
   '["规格","材质","尺寸","功能","详情","什么样","什么样","多大","多重"]', 1, 4, 'manual', 0, NOW(), NOW()),
  ('价格优惠', MD5('价格优惠'), 'price_discount',
   '["便宜点","优惠","满减","折扣","券","降价","打折","少点"]', 1, 5, 'manual', 0, NOW(), NOW()),
  ('账号登录', MD5('账号登录'), 'account_login',
   '["登录","cookie","失效","掉线","登不上","扫码","二维码"]', 1, 6, 'manual', 0, NOW(), NOW()),
  ('卡密发货', MD5('卡密发货'), 'card_key_delivery',
   '["卡密","激活码","自动发货","虚拟商品","兑换码"]', 1, 7, 'manual', 0, NOW(), NOW()),
  ('工作流配置', MD5('工作流配置'), 'workflow_config',
   '["工作流","节点","流程","触发","条件"]', 1, 8, 'manual', 0, NOW(), NOW()),
  ('定时任务', MD5('定时任务'), 'scheduled_task',
   '["定时","上架","定时回复","计划任务","每天"]', 1, 9, 'manual', 0, NOW(), NOW()),
  ('自动回复', MD5('自动回复'), 'auto_reply',
   '["自动回复","模板","AI回复","智能回复","话术"]', 1, 10, 'manual', 0, NOW(), NOW()),
  ('自动发货', MD5('自动发货'), 'auto_delivery',
   '["自动发货","发货规则","自动发货设置"]', 1, 11, 'manual', 0, NOW(), NOW()),
  ('会员充值', MD5('会员充值'), 'membership_recharge',
   '["Token","充值","VIP","会员","SVP","余额"]', 1, 12, 'manual', 0, NOW(), NOW()),
  ('系统使用', MD5('系统使用'), 'system_usage',
   '["怎么用","功能","操作","使用","教程","怎么操作"]', 1, 13, 'manual', 0, NOW(), NOW()),
  ('故障排查', MD5('故障排查'), 'troubleshoot',
   '["报错","错误","不能用","失败","异常","bug","崩溃"]', 1, 14, 'manual', 0, NOW(), NOW()),
  ('其他', MD5('其他'), 'other',
   '["其他","其它","杂项"]', 1, 99, 'manual', 0, NOW(), NOW());

-- 4. 历史数据迁移：将现有 LLM 自动生成的分类归到最接近的预定义分类
-- 策略：按名称关键词匹配，匹配不到的归到 'other'
-- 仅迁移非预定义分类下的 KB（is_system=0 的分类）
UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'stock_query' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%库存%' OR c.name LIKE '%有货%' OR c.name LIKE '%现货%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'shipping_track' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%发货%' OR c.name LIKE '%物流%' OR c.name LIKE '%快递%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'refund_aftersale' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%退款%' OR c.name LIKE '%退货%' OR c.name LIKE '%售后%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'product_consult' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%商品%' OR c.name LIKE '%咨询%' OR c.name LIKE '%规格%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'price_discount' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%价格%' OR c.name LIKE '%优惠%' OR c.name LIKE '%折扣%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'account_login' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%账号%' OR c.name LIKE '%登录%' OR c.name LIKE '%cookie%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'card_key_delivery' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%卡密%' OR c.name LIKE '%激活%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'workflow_config' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND c.name LIKE '%工作流%';

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'scheduled_task' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%定时%' OR c.name LIKE '%计划%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'auto_reply' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND c.name LIKE '%自动回复%';

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'auto_delivery' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND c.name LIKE '%自动发货%';

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'membership_recharge' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%会员%' OR c.name LIKE '%充值%' OR c.name LIKE '%Token%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'system_usage' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%系统%' OR c.name LIKE '%使用%' OR c.name LIKE '%功能%');

UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'troubleshoot' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0
  AND (c.name LIKE '%故障%' OR c.name LIKE '%报错%' OR c.name LIKE '%错误%');

-- 未匹配的历史分类归到 'other'
UPDATE ai_cs_learned_kb k
JOIN ai_cs_kb_category c ON k.category_id = c.id
SET k.category_id = (SELECT id FROM ai_cs_kb_category WHERE code = 'other' AND deleted = 0 LIMIT 1)
WHERE c.is_system = 0;

-- 5. 软删旧的 LLM 自动生成分类（is_system=0 且无 KB 引用的）
UPDATE ai_cs_kb_category
SET deleted = 1, updated_time = NOW()
WHERE is_system = 0
  AND id NOT IN (SELECT DISTINCT category_id FROM ai_cs_learned_kb WHERE category_id IS NOT NULL);

-- 6. 更新 entry_count 冗余计数
UPDATE ai_cs_kb_category c
SET entry_count = (
  SELECT COUNT(*) FROM ai_cs_learned_kb k
  WHERE k.category_id = c.id AND k.deleted = 0
)
WHERE c.deleted = 0;
