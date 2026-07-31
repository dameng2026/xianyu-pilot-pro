-- ============================================================
-- V1.49: 学习知识库三级分类改造（一级大类 + 二级子类）
-- 背景：V1.48 的 13 个平级分类存在以下问题：
--   1. 商品品类（手机数码/虚拟货源/网站搭建等）与通用买卖问题（库存/发货/退款等）混在同一层级，前台选择困难
--   2. 缺少层级结构，无法"一键启用整个大类"或"精确启用某个子类"
--   3. 分类粒度过粗，无法精准匹配闲鱼不同品类下的差异化刁钻问题
-- 本次改造：
--   1. 扩展 ai_cs_kb_category 表：新增 icon/color/description 字段（UI美化用）
--   2. 软删现有所有平级分类（V1.48 的 13 个）
--   3. 重建为三级结构：13 个一级大类 + 68 个二级子类
--   4. 重置 entry_count=0（V1.48 已清空学习知识，无条目）
-- 注意：
--   - parent_id 字段在 V1.43 已存在，本次启用其语义
--   - 一级 parent_id IS NULL，二级 parent_id = 对应一级id
--   - ai_cs_learned_kb.category_id 指向二级分类（不变）
--   - 仅追加/软删，不物理删除，保证可回滚
-- ============================================================

-- 1. 扩展 ai_cs_kb_category 表（幂等，MySQL 8.0 兼容写法）
--    MySQL 8.0 不支持 "ADD COLUMN IF NOT EXISTS"，使用 INFORMATION_SCHEMA 动态 SQL
-- 1.1 icon 字段
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_kb_category' AND COLUMN_NAME = 'icon');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE ai_cs_kb_category ADD COLUMN icon VARCHAR(64) NULL COMMENT ''一级分类图标（emoji 或图标名）''',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 1.2 color 字段
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_kb_category' AND COLUMN_NAME = 'color');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE ai_cs_kb_category ADD COLUMN color VARCHAR(16) NULL COMMENT ''一级分类主题色（HEX，用于UI徽章）''',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 1.3 description 字段
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_kb_category' AND COLUMN_NAME = 'description');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE ai_cs_kb_category ADD COLUMN description VARCHAR(255) NULL COMMENT ''分类描述''',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. 扩展 ai_cs_learned_kb 表（标记种子数据来源）
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_cs_learned_kb' AND COLUMN_NAME = 'source_type');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE ai_cs_learned_kb ADD COLUMN source_type VARCHAR(16) NOT NULL DEFAULT ''ai'' COMMENT ''ai=AI自动学习 / seed=人工种子Q&A''',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. 清理已软删记录的 name_hash，避免与即将软删的记录在 (name_hash, deleted) 唯一键上冲突
--    根因：V1.47 创建的 9 条分类已被 V1.48 软删（deleted=1），但后续又有人重新创建了相同 name 的分类（deleted=0）
--    直接 UPDATE deleted=0 -> deleted=1 会因 name_hash 相同而违反唯一键 uk_kb_cat_name_hash
--    方案：把已软删记录的 name_hash 改为 MD5(name + id)，保证唯一，不物理删除任何数据
UPDATE ai_cs_kb_category 
SET name_hash = MD5(CONCAT(name, '_del_', id)), updated_time = NOW() 
WHERE deleted = 1;

-- 4. 软删现有所有平级分类（V1.48 的 13 个，包括已软删的也无害）
UPDATE ai_cs_kb_category SET deleted = 1, updated_time = NOW() WHERE deleted = 0;

-- 5. 插入 13 个一级分类（parent_id IS NULL，is_system=1）
-- 命名规范：code 使用 lower_snake_case，name 使用中文
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, icon, color, description, source, deleted, created_time, updated_time)
VALUES
  ('交易通用问题', MD5('交易通用问题'), 'general_trade',
   '["库存","发货","退款","价格","咨询","登录"]', 1, NULL, 1,
   '💬', '#4A6CF7', '适用于所有商品的通用买卖问题（库存/发货/退款/价格/商品咨询/账号登录）',
   'manual', 0, NOW(), NOW()),
  ('服饰鞋包', MD5('服饰鞋包'), 'fashion_bag',
   '["服装","鞋","包","配饰"]', 1, NULL, 2,
   '👗', '#E89BAB', '男装/女装/鞋类/箱包/配饰等服饰鞋包类商品',
   'manual', 0, NOW(), NOW()),
  ('数码家电', MD5('数码家电'), 'digital_appliance',
   '["手机","电脑","相机","家电"]', 1, NULL, 3,
   '📱', '#4A90E2', '手机/电脑平板/相机摄影/音频设备/家用电器/智能设备',
   'manual', 0, NOW(), NOW()),
  ('美妆个护', MD5('美妆个护'), 'beauty_care',
   '["护肤","化妆","香水","个护"]', 1, NULL, 4,
   '💄', '#E91E63', '护肤品/化妆品/香水/个人护理/美容工具',
   'manual', 0, NOW(), NOW()),
  ('家居生活', MD5('家居生活'), 'home_life',
   '["家具","家纺","厨具","装饰"]', 1, NULL, 5,
   '🏠', '#795548', '家具/家纺/厨房用品/装饰摆件/收纳整理',
   'manual', 0, NOW(), NOW()),
  ('母婴用品', MD5('母婴用品'), 'baby_mom',
   '["奶粉","纸尿裤","玩具","孕妇"]', 1, NULL, 6,
   '👶', '#FF9800', '奶粉辅食/纸尿裤/玩具书籍/孕妇用品/婴幼服装',
   'manual', 0, NOW(), NOW()),
  ('运动户外', MD5('运动户外'), 'sports_outdoor',
   '["运动","户外","骑行","垂钓"]', 1, NULL, 7,
   '⚽', '#4CAF50', '运动器材/户外装备/运动服饰/骑行装备/垂钓用品',
   'manual', 0, NOW(), NOW()),
  ('图书教材', MD5('图书教材'), 'books',
   '["教材","教辅","小说","杂志"]', 1, NULL, 8,
   '📚', '#9C27B0', '教材教辅/小说文学/杂志期刊/专业书籍/儿童读物',
   'manual', 0, NOW(), NOW()),
  ('艺术品收藏', MD5('艺术品收藏'), 'art_collection',
   '["字画","邮票","古董","潮玩"]', 1, NULL, 9,
   '🎨', '#673AB7', '字画书法/邮票钱币/古董收藏/潮玩手办/纪念品',
   'manual', 0, NOW(), NOW()),
  ('宠物用品', MD5('宠物用品'), 'pet_supplies',
   '["宠物","猫","狗","水族"]', 1, NULL, 10,
   '🐱', '#8D6E63', '宠物食品/宠物玩具/宠物服饰/宠物用具/水族用品',
   'manual', 0, NOW(), NOW()),
  ('汽车用品', MD5('汽车用品'), 'auto_items',
   '["汽车","摩托车","自行车"]', 1, NULL, 11,
   '🚗', '#607D8B', '汽车装饰/汽车配件/汽车电子/摩托车/自行车',
   'manual', 0, NOW(), NOW()),
  ('手工DIY', MD5('手工DIY'), 'handcraft',
   '["手工","编织","陶艺","木工"]', 1, NULL, 12,
   '✂️', '#FF5722', '手工材料/手工成品/编织工艺/陶艺作品/木工作品',
   'manual', 0, NOW(), NOW()),
  ('虚拟货源', MD5('虚拟货源'), 'virtual_goods',
   '["卡密","激活码","软件","设计"]', 1, NULL, 13,
   '💾', '#00BCD4', '软件安装包/程序部署服务/网页设计/激活码/电子书/设计模板',
   'manual', 0, NOW(), NOW());

-- 6. 插入 68 个二级分类（parent_id = 对应一级id，is_system=1）
-- 使用子查询获取父分类id，避免硬编码
-- 6.1 交易通用问题（parent=general_trade）下 6 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '库存查询' AS name, 'general_stock_query' AS code, '["库存","有货","现货","还有吗","没货","缺货","断货","在不在"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '发货跟踪', 'general_shipping_track', '["发货","物流","快递","什么时候发","单号","运单","发出","揽收"]', 2
  UNION ALL SELECT '退款售后', 'general_refund_aftersale', '["退款","退货","换货","质量","坏了","破损","不想要","退钱"]', 3
  UNION ALL SELECT '商品咨询', 'general_product_consult', '["规格","材质","尺寸","功能","详情","什么样","多大","多重"]', 4
  UNION ALL SELECT '价格优惠', 'general_price_discount', '["便宜点","优惠","满减","折扣","券","降价","打折","少点"]', 5
  UNION ALL SELECT '账号登录', 'general_account_login', '["登录","cookie","失效","掉线","登不上","扫码","二维码"]', 6
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'general_trade' AND deleted = 0 LIMIT 1) AS p;

-- 6.2 服饰鞋包（parent=fashion_bag）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '男装' AS name, 'fashion_men' AS code, '["男装","衬衫","T恤","外套","裤子","夹克"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '女装', 'fashion_women', '["女装","连衣裙","半身裙","衬衫","外套","针织"]', 2
  UNION ALL SELECT '鞋类', 'fashion_shoes', '["鞋","运动鞋","板鞋","皮鞋","拖鞋","靴子"]', 3
  UNION ALL SELECT '箱包', 'fashion_bags', '["包","背包","手提包","钱包","行李箱","托特包"]', 4
  UNION ALL SELECT '配饰', 'fashion_accessories', '["配饰","帽子","围巾","皮带","手表","首饰"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'fashion_bag' AND deleted = 0 LIMIT 1) AS p;

-- 6.3 数码家电（parent=digital_appliance）下 6 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '手机' AS name, 'digital_phone' AS code, '["手机","iPhone","华为","小米","三星","OPPO","vivo"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '电脑平板', 'digital_computer', '["电脑","笔记本","台式机","平板","MacBook","联想","戴尔"]', 2
  UNION ALL SELECT '相机摄影', 'digital_camera', '["相机","单反","微单","镜头","摄影","三脚架","GoPro"]', 3
  UNION ALL SELECT '音频设备', 'digital_audio', '["耳机","音响","音箱","麦克风","AirPods","蓝牙音箱"]', 4
  UNION ALL SELECT '家用电器', 'digital_appliance_home', '["冰箱","洗衣机","空调","电视","微波炉","电饭煲"]', 5
  UNION ALL SELECT '智能设备', 'digital_smart', '["智能手表","智能手环","智能音箱","智能家居","平衡车"]', 6
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'digital_appliance' AND deleted = 0 LIMIT 1) AS p;

-- 6.4 美妆个护（parent=beauty_care）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '护肤品' AS name, 'beauty_skincare' AS code, '["护肤","面霜","精华","面膜","洗面奶","爽肤水","乳液"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '化妆品', 'beauty_makeup', '["化妆","口红","粉底","眼影","睫毛膏","腮红","BB霜"]', 2
  UNION ALL SELECT '香水', 'beauty_perfume', '["香水","香氛","淡香水","浓香水","香精","留香"]', 3
  UNION ALL SELECT '个人护理', 'beauty_personal_care', '["护理","洗发水","沐浴露","牙膏","卫生巾","剃须刀"]', 4
  UNION ALL SELECT '美容工具', 'beauty_tools', '["美容工具","化妆刷","美容仪","卷发棒","理发器","指甲刀"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'beauty_care' AND deleted = 0 LIMIT 1) AS p;

-- 6.5 家居生活（parent=home_life）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '家具' AS name, 'home_furniture' AS code, '["沙发","床","衣柜","餐桌","椅子","书桌","茶几"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '家纺', 'home_textile', '["床品","四件套","被子","枕头","毛巾","窗帘","地毯"]', 2
  UNION ALL SELECT '厨房用品', 'home_kitchen', '["厨具","锅","碗","刀","砧板","餐具","水壶"]', 3
  UNION ALL SELECT '装饰摆件', 'home_decor', '["装饰","摆件","挂画","花瓶","相框","香薰"]', 4
  UNION ALL SELECT '收纳整理', 'home_storage', '["收纳","整理","收纳箱","衣架","挂钩","置物架"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'home_life' AND deleted = 0 LIMIT 1) AS p;

-- 6.6 母婴用品（parent=baby_mom）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '奶粉辅食' AS name, 'baby_formula' AS code, '["奶粉","辅食","米粉","果泥","奶粉段","配方奶"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '纸尿裤', 'baby_diaper', '["纸尿裤","尿不湿","拉拉裤","NB","S","M","L","XL"]', 2
  UNION ALL SELECT '玩具书籍', 'baby_toys', '["玩具","积木","绘本","故事书","早教","拼图"]', 3
  UNION ALL SELECT '孕妇用品', 'baby_pregnant', '["孕妇","孕妇装","胎心仪","月子","待产","防辐射"]', 4
  UNION ALL SELECT '婴幼服装', 'baby_clothes', '["婴儿","宝宝","童装","婴儿服","连体衣","肚兜"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'baby_mom' AND deleted = 0 LIMIT 1) AS p;

-- 6.7 运动户外（parent=sports_outdoor）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '运动器材' AS name, 'sports_equipment' AS code, '["哑铃","跑步机","瑜伽","健身","杠铃","拉力器"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '户外装备', 'sports_outdoor_gear', '["帐篷","睡袋","登山","背包","炉具","登山杖"]', 2
  UNION ALL SELECT '运动服饰', 'sports_apparel', '["运动服","速干衣","运动裤","运动文胸","瑜伽服"]', 3
  UNION ALL SELECT '骑行装备', 'sports_cycling', '["自行车","电动车","头盔","骑行服","车灯","车锁"]', 4
  UNION ALL SELECT '垂钓用品', 'sports_fishing', '["鱼竿","鱼线","鱼饵","鱼钩","渔轮","钓箱"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'sports_outdoor' AND deleted = 0 LIMIT 1) AS p;

-- 6.8 图书教材（parent=books）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '教材教辅' AS name, 'books_textbook' AS code, '["教材","教辅","课本","练习册","试卷","参考书"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '小说文学', 'books_novel', '["小说","文学","名著","散文","诗集","网络小说"]', 2
  UNION ALL SELECT '杂志期刊', 'books_magazine', '["杂志","期刊","读者","意林","时尚","国家地理"]', 3
  UNION ALL SELECT '专业书籍', 'books_professional', '["专业","技术","编程","医学","法律","经管"]', 4
  UNION ALL SELECT '儿童读物', 'books_children', '["绘本","童话","儿童","启蒙","拼音","故事"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'books' AND deleted = 0 LIMIT 1) AS p;

-- 6.9 艺术品收藏（parent=art_collection）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '字画书法' AS name, 'art_calligraphy' AS code, '["字画","书法","国画","油画","水墨","篆刻"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '邮票钱币', 'art_stamp_coin', '["邮票","钱币","纪念币","古币","银元","纸币"]', 2
  UNION ALL SELECT '古董收藏', 'art_antique', '["古董","古玩","瓷器","玉器","青铜","鼻烟壶"]', 3
  UNION ALL SELECT '潮玩手办', 'art_trendy', '["手办","盲盒","高达","乐高","模型","扭蛋"]', 4
  UNION ALL SELECT '纪念品', 'art_memorabilia', '["纪念","徽章","门票","球星卡","明信片","绝版"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'art_collection' AND deleted = 0 LIMIT 1) AS p;

-- 6.10 宠物用品（parent=pet_supplies）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '宠物食品' AS name, 'pet_food' AS code, '["猫粮","狗粮","零食","罐头","主粮","幼猫","成猫"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '宠物玩具', 'pet_toys', '["逗猫棒","球","飞盘","咬胶","猫爬架","玩具"]', 2
  UNION ALL SELECT '宠物服饰', 'pet_clothes', '["宠物衣服","牵引绳","项圈","雨衣","鞋子"]', 3
  UNION ALL SELECT '宠物用具', 'pet_supplies_misc', '["猫砂盆","食盆","笼子","航空箱","牵引"]', 4
  UNION ALL SELECT '水族用品', 'pet_aquarium', '["鱼缸","鱼食","过滤器","加热棒","造景","热带鱼"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'pet_supplies' AND deleted = 0 LIMIT 1) AS p;

-- 6.11 汽车用品（parent=auto_items）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '汽车装饰' AS name, 'auto_decor' AS code, '["脚垫","座套","香水","挂件","方向盘套","贴纸"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '汽车配件', 'auto_parts', '["雨刷","灯泡","轮胎","机油","滤芯","火花塞"]', 2
  UNION ALL SELECT '汽车电子', 'auto_electronics', '["行车记录仪","导航","倒车雷达","充电器","车载冰箱"]', 3
  UNION ALL SELECT '摩托车', 'auto_motorcycle', '["摩托车","头盔","骑行服","机车","踏板"]', 4
  UNION ALL SELECT '自行车', 'auto_bicycle', '["自行车","山地车","公路车","电动车","车锁"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'auto_items' AND deleted = 0 LIMIT 1) AS p;

-- 6.12 手工DIY（parent=handcraft）下 5 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '手工材料' AS name, 'handcraft_materials' AS code, '["毛线","布料","串珠","粘土","颜料","画笔"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '手工成品', 'handcraft_products', '["手作","DIY","定制","手工","礼物","创意"]', 2
  UNION ALL SELECT '编织工艺', 'handcraft_knitting', '["编织","钩针","毛衣","围巾","玩偶","抱枕"]', 3
  UNION ALL SELECT '陶艺作品', 'handcraft_ceramic', '["陶艺","陶瓷","手工","花瓶","杯子","摆件"]', 4
  UNION ALL SELECT '木工作品', 'handcraft_wood', '["木工","木质","手工","家具","摆件","模型"]', 5
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'handcraft' AND deleted = 0 LIMIT 1) AS p;

-- 6.13 虚拟货源（parent=virtual_goods）下 6 个二级
INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, parent_id, sort_order, source, deleted, created_time, updated_time)
SELECT name, MD5(name), code, keywords, 1, p.id, sort_order, 'manual', 0, NOW(), NOW()
FROM (
  SELECT '软件安装包' AS name, 'virtual_software' AS code, '["安装包","破解","激活","软件","Windows","Office"]' AS keywords, 1 AS sort_order
  UNION ALL SELECT '程序部署服务', 'virtual_deployment', '["部署","代搭","环境","服务器","Docker","Linux","安装"]', 2
  UNION ALL SELECT '网页设计', 'virtual_webdesign', '["网页","设计","网站","H5","前端","模板","建站"]', 3
  UNION ALL SELECT '激活码', 'virtual_activation', '["激活码","序列号","授权","License","注册码","兑换码"]', 4
  UNION ALL SELECT '电子书', 'virtual_ebook', '["电子书","PDF","epub","资料","教程","文档"]', 5
  UNION ALL SELECT '设计模板', 'virtual_template', '["模板","素材","PSD","PPT","设计","资源","素材库"]', 6
) AS sub
CROSS JOIN (SELECT id FROM ai_cs_kb_category WHERE code = 'virtual_goods' AND deleted = 0 LIMIT 1) AS p;

-- 7. 验证：检查一级分类数（应为 13）与二级分类数（应为 68）
-- SELECT
--   SUM(CASE WHEN parent_id IS NULL AND deleted = 0 THEN 1 ELSE 0 END) AS level1_count,
--   SUM(CASE WHEN parent_id IS NOT NULL AND deleted = 0 THEN 1 ELSE 0 END) AS level2_count
-- FROM ai_cs_kb_category;
