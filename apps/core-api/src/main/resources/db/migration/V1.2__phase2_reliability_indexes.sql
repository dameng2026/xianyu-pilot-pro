-- Phase 2：可靠性与并发安全索引
-- 说明：用于卡密原子认领、自动发货幂等、验证码迁移不涉及数据库结构。
-- 如果索引已存在，请忽略重复索引错误；DataInitializer 也会在启动时尝试创建这些索引。

CREATE INDEX idx_card_item_claim ON card_item(tenant_id, group_id, status, deleted, id);
CREATE INDEX idx_card_item_order ON card_item(tenant_id, group_id, used_order_id);
CREATE INDEX idx_delivery_order_idempotent ON delivery_record(tenant_id, order_id, status, deleted);
CREATE INDEX idx_auto_reply_log_idempotent ON auto_reply_log(tenant_id, account_id, conversation_id, rule_id, action, created_time);
