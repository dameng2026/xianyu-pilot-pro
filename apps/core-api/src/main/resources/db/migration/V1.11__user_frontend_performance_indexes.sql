-- User frontend first-load performance indexes.
-- Focus areas:
-- 1. orders page list/count queries
-- 2. order item summary batch lookups
-- 3. goods cover lookups by external_goods_id

ALTER TABLE xianyu_trade_order
    ADD INDEX IF NOT EXISTS idx_xyo_tenant_deleted_created (tenant_id, deleted, created_time, id);

ALTER TABLE xianyu_trade_order
    ADD INDEX IF NOT EXISTS idx_xyo_tenant_deleted_account_created (tenant_id, deleted, account_id, created_time, id);

ALTER TABLE xianyu_trade_order
    ADD INDEX IF NOT EXISTS idx_xyo_tenant_deleted_status_created (tenant_id, deleted, order_status, created_time, id);

ALTER TABLE xianyu_trade_order_item
    ADD INDEX IF NOT EXISTS idx_xyoi_tenant_order_deleted_id (tenant_id, order_id, deleted, id);

ALTER TABLE xianyu_goods
    ADD INDEX IF NOT EXISTS idx_xyg_tenant_external_deleted (tenant_id, external_goods_id, deleted);
