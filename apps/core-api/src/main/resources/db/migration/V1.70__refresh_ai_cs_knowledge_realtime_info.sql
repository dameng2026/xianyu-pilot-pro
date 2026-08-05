-- AI 客服小梦知识库刷新：
-- 1. 清理 2026-08 会员四档升级后仍残留的旧文案（三档会员/每日免费额度/账号上限等）
-- 2. 移除知识条目中的内部 API 路径与实现细节（只保留用户视角）
-- 3. 新增「实时信息查询规则」：会员价格/店铺限制/功能对比/更新日志/公告一律走接口

-- 会员等级与权益差异（旧三档 → 新四档）
UPDATE ai_cs_knowledge
SET content = '会员分四档（当前最新）：\n'
  '1. 普通用户（免费）：可绑定 1 个闲鱼店铺，可使用账号管理、商品发布、订单查看等基础功能。\n'
  '2. VIP（单店版）：功能权限与 VIP 一致，限绑定 1 个闲鱼店铺，月付 9.99 元起。\n'
  '3. VIP：不限店铺数量，月付 19.99 元起。\n'
  '4. SVP/SVIP：最高等级，不限店铺数量，享最高优先级与专属服务，月付 39.99 元起。\n'
  '具体套餐价格、店铺数量限制与功能对比以实时接口为准（会员价格 get_vip_price / 店铺限制 get_store_limit / 功能对比 get_feature_comparison），\n'
  '禁止回答旧版「三档会员/每日免费额度/账号上限」等信息。\n'
  '升级路径：个人中心或会员中心 → 选择套餐 → 微信/支付宝支付；升级后立即生效，到期后自动降级为普通用户。\n'
  'Token 与会员相互独立：Token 用于 AI 功能计费，充值 Token 不影响会员等级。',
    keywords = '会员,等级,vip,svp,svip,普通,vip单店版,权益,升级,店铺,套餐,价格',
    updated_time = NOW()
WHERE tenant_id IS NULL AND title = '会员等级与权益差异';

-- 会员等级与 Token 扣费规则（旧三档 + 内部 API 路径 → 用户视角四档）
UPDATE ai_cs_knowledge
SET content = '会员等级（vip_level）：普通用户=0，VIP=1，SVP=2，VIP（单店版）=3。\n'
  'VIP（单店版）功能权限与 VIP 一致，仅店铺数量限制不同（单店版 1 个店铺，VIP 不限）。\n'
  'Token 扣费规则：\n'
  '- 通用模型按次计费，扣费数量按用户等级由后台配置（默认 3 Token/次，管理员可调整）。\n'
  '- VIP（单店版）与 VIP 按同一档扣费。\n'
  '- 扣费优先级：等级定价 > 通用定价 > 默认值。\n'
  '- 余额查询：个人中心 / 客服面板顶部，或直接问小梦（get_token_balance）。\n'
  '- 余额不足时 AI 功能不可用，前端会引导充值；小梦可在用户询问时自然提醒。\n'
  '会员价格、店铺限制、功能对比均为实时数据，必须通过接口查询，不依赖本知识条目。',
    keywords = '会员,等级,vip_level,token,扣费,余额,充值,单店版,svp,vip',
    updated_time = NOW()
WHERE tenant_id IS NULL AND title = '会员等级与 Token 扣费规则';

-- Token 与计费 FAQ（清理过期免费额度与内部细节）
UPDATE ai_cs_knowledge
SET content = 'Q: Token 余额在哪里查看？\n'
  'A: 右上角头像下拉 / 个人中心 / 客服面板顶部，也可以直接问小梦查询。\n'
  'Q: Token 怎么充值？\n'
  'A: 个人中心/会员中心 → 充值弹窗 → 选择套餐 → 微信/支付宝支付。\n'
  'Q: 每次 AI 调用扣多少 Token？\n'
  'A: 通用模型按次计费，扣费按用户等级由后台配置（默认 3 Token/次，管理员可调整）。\n'
  'Q: 小梦客服对话扣费吗？\n'
  'A: 系统 AI 客服「小梦」对话由系统额度承担，不扣除用户 Token（具体以实际计费为准）。\n'
  'Q: 余额不足会怎样？\n'
  'A: 相关 AI 功能不可用，会提示充值；可先问小梦查询余额。\n'
  'Q: 充值的 Token 会过期吗？\n'
  'A: 以充值页面与后台配置为准，一般长期有效；具体请以系统实际展示为准。\n'
  'Q: 工具调用扣费吗？\n'
  'A: 工具调用本身不额外扣费，但工具触发的 AI 调用（如标题润色）按规则扣费。\n'
  'Q: 闲聊扣费吗？\n'
  'A: 不扣费；连续闲聊过多会礼貌提醒一次。',
    keywords = 'faq,token,balance,计费,余额,充值,扣费,闲聊,免费',
    updated_time = NOW()
WHERE tenant_id IS NULL AND title = 'Token 与计费 FAQ';

-- Token 余额与计费总览（清理过期扣费描述）
UPDATE ai_cs_knowledge
SET content = 'Token 是平台 AI 功能的统一计费单位：\n'
  '- 余额查询：个人中心 / 客服面板顶部，或直接问小梦（get_token_balance）。\n'
  '- 充值入口：个人中心/会员中心 → 充值弹窗 → 选择套餐 → 微信/支付宝支付。\n'
  '- 扣费场景：通用模型按次计费（按用户等级配置，默认 3 Token/次）；生图等模型按后台配置计费。\n'
  '- 余额不足：相关 AI 功能不可用，前端引导充值。\n'
  '- 会员价格/店铺限制/功能对比：实时接口查询，不依赖知识库。',
    keywords = 'system_usage,token,balance,billing,计费,余额,充值,扣费,通用模型',
    updated_time = NOW()
WHERE tenant_id IS NULL AND title = 'Token 余额与计费总览';

-- 充值流程与套餐升级（移除内部 API 路径，改为用户视角 + 实时接口规则）
UPDATE ai_cs_knowledge
SET content = '充值流程（用户视角）：\n'
  '1. 个人中心或会员中心 → 点击充值/升级。\n'
  '2. 选择 Token 套餐或会员套餐（月度/季度/年度）。\n'
  '3. 微信/支付宝支付，支付成功后即时到账。\n'
  '4. 会员升级立即生效，到期后自动降级为普通用户。\n'
  '会员四档：普通用户（免费）/ VIP（单店版）/ VIP / SVP。\n'
  '- 套餐价格：以 get_vip_price 实时报价为准（后台可调）。\n'
  '- 店铺数量限制：以 get_store_limit 实时配置为准（功能管理首行，0=不限）。\n'
  '- 功能对比：以 get_feature_comparison 实时配置为准（后台「系统运维 → 功能管理」）。\n'
  '- 促销活动：会员中心展示后台配置的活动（折扣/返现/名额限制/倒计时）。\n'
  '注意：小梦回答会员相关问题时必须调用实时工具，禁止使用本条目中的历史价格或档位信息。',
    keywords = '充值,套餐,升级,会员,支付,vip,svp,店铺,功能对比,促销',
    updated_time = NOW()
WHERE tenant_id IS NULL AND title = '充值流程与套餐升级';

-- 新增：实时信息查询规则
INSERT INTO ai_cs_knowledge(
    tenant_id, category, title, content, keywords,
    priority, enabled, sort_order, created_time, updated_time
)
SELECT NULL, 'system_usage', '实时信息查询规则',
  '以下信息随时可能更新，禁止依赖知识库旧文案，必须调用实时工具：\n'
  '- 会员套餐价格 → get_vip_price\n'
  '- 店铺数量限制 → get_store_limit\n'
  '- 各等级功能对比 → get_feature_comparison\n'
  '- 更新日志 → get_release_notes\n'
  '- 平台公告 → get_announcements\n'
  '- Token 余额 → get_token_balance\n'
  '工具返回失败时如实告知「暂时不可用」，不得编造或使用旧数据。',
  '实时,接口,会员价格,店铺限制,功能对比,更新日志,公告,token,禁止旧数据',
  100, 1, 30, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_cs_knowledge
    WHERE tenant_id IS NULL AND title = '实时信息查询规则'
);

-- 新增：更新日志与公告
INSERT INTO ai_cs_knowledge(
    tenant_id, category, title, content, keywords,
    priority, enabled, sort_order, created_time, updated_time
)
SELECT NULL, 'system_usage', '更新日志与公告',
  '更新日志：系统每次发布新版本都会记录版本号、发布日期与更新内容；'
  '用户可在「系统设置 → 关于 → 更新日志」查看，也可直接问小梦「最近更新了什么」（get_release_notes 实时查询）。\n'
  '平台公告：管理员发布的公告展示在首页公告栏，也可直接问小梦「有什么公告」（get_announcements 实时查询）。',
  '更新日志,公告,版本,发布,release,notice,announcement,最近更新',
  95, 1, 31, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_cs_knowledge
    WHERE tenant_id IS NULL AND title = '更新日志与公告'
);

-- 新增：充值引导与销管尺度
INSERT INTO ai_cs_knowledge(
    tenant_id, category, title, content, keywords,
    priority, enabled, sort_order, created_time, updated_time
)
SELECT NULL, 'membership', '充值引导与销管尺度',
  '小梦承担轻度销售角色，但必须把握尺度：\n'
  '1. 用户询问会员/套餐/价格/店铺上限/功能权益/Token 时：调用实时工具如实回答，并结合用户当前等级给一条自然建议。\n'
  '2. 升级建议映射：普通用户 → VIP（单店版）或 VIP；VIP（单店版）→ VIP；VIP → SVP；SVP 无需再推销。\n'
  '3. 余额不足时自然提醒充值入口（个人中心/会员中心），不夸大不催促。\n'
  '4. 禁止虚假承诺、夸大权益、诱导冲动消费；一次对话最多主动引导一次，用户拒绝后不得反复推销。',
  '销管,充值,升级,引导,会员,套餐,建议,尺度,推荐',
  100, 1, 32, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_cs_knowledge
    WHERE tenant_id IS NULL AND title = '充值引导与销管尺度'
);
