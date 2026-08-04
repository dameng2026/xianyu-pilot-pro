-- 会员体系升级：普通用户 / VIP（单店版）/ VIP / SVIP 四档
-- 1. 新增 VIP（单店版）套餐（plan_code=vip-single），价格 9.99 / 25.99 / 88.88 元，店铺限制 1 个
-- 2. 普通用户保持免费，店铺限制 1 个
-- 3. VIP 升级为店铺不限制（max_xianyu_accounts=0，0 表示无限制），价格 19.99 / 39.99 / 138.88 元
-- 4. SVP/SVIP 店铺不限制，价格调整为 39.99 / 99.99 / 299.99 元
-- 5. 功能管理配置新增首行「店铺数量」（key=store-limit，0 表示无限制）

-- 新增 VIP（单店版）套餐（幂等）
INSERT INTO billing_plan(
    plan_name, plan_code, price_cent, duration_days,
    max_xianyu_accounts, max_goods_count, max_ai_reply_per_day, max_workflow_per_day, max_storage_mb,
    enable_auto_delivery, enable_kami, enable_ai_reply, enable_workflow,
    features_text, period_type,
    price_month_cent, price_quarter_cent, price_year_cent,
    status, created_time, updated_time, deleted
)
SELECT
    'VIP（单店版）', 'vip-single', 999, 30,
    1, 200, 3000, 100, 1024,
    1, 1, 1, 1,
    '闲鱼店铺数量：1 个', 'month',
    999, 2599, 8888,
    1, NOW(), NOW(), 0
WHERE NOT EXISTS (
    SELECT 1 FROM billing_plan WHERE plan_code IN ('vip-single','vip_single') AND deleted=0
);

-- 普通用户：免费，店铺限制 1 个
UPDATE billing_plan
SET max_xianyu_accounts = 1,
    features_text = CASE
        WHEN features_text IS NULL OR features_text = '' THEN '闲鱼店铺数量：1 个'
        WHEN features_text LIKE '%店铺%' THEN features_text
        ELSE CONCAT(features_text, '\n闲鱼店铺数量：1 个')
    END,
    updated_time = NOW()
WHERE deleted = 0 AND plan_code = 'normal';

-- VIP：店铺数量不限制，价格 19.99 / 39.99 / 138.88 元
UPDATE billing_plan
SET max_xianyu_accounts = 0,
    price_cent = 1999,
    price_month_cent = 1999,
    price_quarter_cent = 3999,
    price_year_cent = 13888,
    features_text = CASE
        WHEN features_text IS NULL OR features_text = '' THEN '闲鱼店铺数量：不限制'
        WHEN features_text LIKE '%店铺%' THEN features_text
        ELSE CONCAT(features_text, '\n闲鱼店铺数量：不限制')
    END,
    updated_time = NOW()
WHERE deleted = 0 AND plan_code = 'vip';

-- SVP/SVIP：店铺数量不限制，价格调整为 39.99 / 99.99 / 299.99 元
UPDATE billing_plan
SET max_xianyu_accounts = 0,
    price_cent = 3999,
    price_month_cent = 3999,
    price_quarter_cent = 9999,
    price_year_cent = 29999,
    features_text = CASE
        WHEN features_text IS NULL OR features_text = '' THEN '闲鱼店铺数量：不限制'
        WHEN features_text LIKE '%店铺%' THEN features_text
        ELSE CONCAT(features_text, '\n闲鱼店铺数量：不限制')
    END,
    updated_time = NOW()
WHERE deleted = 0 AND plan_code IN ('svp', 'svip');

-- 功能管理配置：新增首行「店铺数量」（0=无限制）
UPDATE admin_module_record
SET json_text = JSON_SET(
        json_text,
        '$.features."store-limit"',
        JSON_OBJECT(
            'title', '店铺数量',
            'group', 'overview',
            'normal', 1,
            'vipSingle', 1,
            'vip', 0,
            'svp', 0,
            'maintenance', false,
            'limitMode', 'none'
        )
    ),
    updated_time = NOW()
WHERE module_key = 'user_feature_switch'
  AND status = 'config'
  AND deleted = 0
  AND json_text IS NOT NULL
  AND JSON_VALID(json_text) = 1
  AND NOT JSON_CONTAINS_PATH(json_text, 'one', '$.features."store-limit"');
