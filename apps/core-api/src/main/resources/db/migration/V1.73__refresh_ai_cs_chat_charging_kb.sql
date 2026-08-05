-- V1.73：刷新 AI 客服计费描述（小梦对话免费）与上下文压缩条目（移除内部字段）

UPDATE ai_cs_knowledge
SET content = 'AI 客服小梦对接后台通用模型。'
  '系统 AI 客服「小梦」对话由系统额度承担，不扣除用户 Token；'
  '工具触发的 AI 调用（如商品标题润色）按通用模型按次计费规则扣费。'
  '上下文默认 50 条，超出可新建会话或压缩上下文（压缩不扣费）。'
  '连续闲聊 5 条后礼貌提醒一次。',
    keywords = 'ai客服,小梦,通用模型,token,上下文,闲聊,免费,扣费',
    updated_time = NOW()
WHERE tenant_id IS NULL AND category = 'ai_customer_service' AND title = 'AI 客服配置';

UPDATE ai_cs_knowledge
SET content = '上下文压缩机制：\n'
  '- 单会话消息过多时自动压缩（约 50 条触发）。\n'
  '- 调用通用模型生成简短摘要，压缩不扣费。\n'
  '- 新会话会自动带上压缩摘要作为上下文，保证记忆连续。\n\n'
  '历史保留：\n'
  '- 客服面板关闭再打开后历史消息保留。\n'
  '- 每个会话独立隔离，互不影响。\n\n'
  '会话管理：每个会话有独立标识，关闭后自动清理活跃状态。',
    keywords = 'ai客服,上下文,压缩,历史,会话,记忆,summary',
    updated_time = NOW()
WHERE tenant_id IS NULL AND category = 'ai_customer_service' AND title = '上下文压缩与历史保留';
