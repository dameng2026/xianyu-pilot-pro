-- V1.29: 套餐表新增月/季/年三档价格字段
-- 一个套餐同时支持三个周期的价格，前台按周期切换展示对应价格
-- 保留 price_cent 与 period_type 字段作为向后兼容（price_cent 仍取月度价格用于排序）
ALTER TABLE billing_plan
  ADD COLUMN price_month_cent BIGINT DEFAULT 0 COMMENT '月度价格（分），0 表示未配置',
  ADD COLUMN price_quarter_cent BIGINT DEFAULT 0 COMMENT '季度价格（分），0 表示未配置',
  ADD COLUMN price_year_cent BIGINT DEFAULT 0 COMMENT '年度价格（分），0 表示未配置';

-- 回填：将现有 price_cent 按其 period_type 回填到对应周期价格字段（幂等）
UPDATE billing_plan SET price_month_cent = price_cent WHERE period_type = 'month' AND price_cent > 0 AND deleted = 0;
UPDATE billing_plan SET price_quarter_cent = price_cent WHERE period_type = 'quarter' AND price_cent > 0 AND deleted = 0;
UPDATE billing_plan SET price_year_cent = price_cent WHERE period_type = 'year' AND price_cent > 0 AND deleted = 0;
