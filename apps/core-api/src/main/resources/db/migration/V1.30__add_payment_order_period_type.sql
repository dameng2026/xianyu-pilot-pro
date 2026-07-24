-- V1.30: payment_order 表新增 period_type 字段，保存 VIP 订单的计费周期
-- 用户在前台 VIP 会员中心选择月/季/年套餐下单时，订单需记录所选周期，
-- 以便支付成功后按周期推导会员有效期（月=30天，季=90天，年=365天），
-- 并确保扣费金额与前台展示价格一致（取 price_month_cent / price_quarter_cent / price_year_cent）。
-- 仅追加字段，不影响历史订单（period_type 为 NULL 时按月度处理）。
ALTER TABLE payment_order
  ADD COLUMN period_type VARCHAR(10) DEFAULT NULL COMMENT 'VIP订单计费周期：month/quarter/year；NULL 视为 month（兼容历史订单）';
