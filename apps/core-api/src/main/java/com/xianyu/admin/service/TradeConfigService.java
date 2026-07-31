package com.xianyu.admin.service;

import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 交易配置服务（基于 sys_config 表）。
 *
 * 缓存策略：
 * - get(key) 与每个 getXxx() 单值方法各自 @Cacheable，按方法名作 key 隔离
 * - getAll() 整体结果 @Cacheable(key='all')，第二次起直接命中聚合缓存
 * - 注意：getAll() 内部调用 getXxx() 是 self-invocation 不走代理，
 *   但 getAll() 自身结果被缓存，第二次外部调用命中后不会再触发内部 getXxx()
 * - set() 通过 @CacheEvict(allEntries=true) 清空整个 cache
 */
@Service
public class TradeConfigService {

    private final JdbcTemplate jdbcTemplate;

    public TradeConfigService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 读取配置值。
     */
    @Cacheable(value = "tradeConfig", key = "#key", unless = "#result == null")
    public String get(String key, String defaultValue) {
        try {
            List<String> values = jdbcTemplate.queryForList(
                "SELECT config_value FROM sys_config WHERE config_key = ? AND deleted = 0 LIMIT 1",
                String.class, key);
            return values.isEmpty() ? defaultValue : values.get(0);
        } catch (Exception e) {
            return defaultValue;
        }
    }

    /**
     * 写入配置值（upsert）。
     * 任意 key 的写入都可能影响 getAll() 的聚合结果，因此清空整个 cache。
     */
    @CacheEvict(value = "tradeConfig", allEntries = true)
    public void set(String key, String value) {
        int updated = jdbcTemplate.update(
            "UPDATE sys_config SET config_value = ?, updated_time = NOW() WHERE config_key = ? AND deleted = 0",
            value, key);
        if (updated == 0) {
            jdbcTemplate.update(
                "INSERT INTO sys_config(config_key, config_value, created_time, updated_time, deleted) VALUES(?, ?, NOW(), NOW(), 0)",
                key, value);
        }
    }

    /**
     * 获取抽佣率（默认 0.0500）
     */
    @Cacheable(value = "tradeConfig", key = "'commission_rate'")
    public BigDecimal getCommissionRate() {
        return new BigDecimal(get("trade.commission_rate", "0.0500"));
    }

    /**
     * 获取冷冻天数（默认 7）
     */
    @Cacheable(value = "tradeConfig", key = "'freeze_days'")
    public int getFreezeDays() {
        return Integer.parseInt(get("trade.freeze_days", "7"));
    }

    /**
     * 获取自动完结小时数（默认 72）
     */
    @Cacheable(value = "tradeConfig", key = "'auto_complete_hours'")
    public int getAutoCompleteHours() {
        return Integer.parseInt(get("trade.auto_complete_hours", "72"));
    }

    /**
     * 获取最低提现金额（分，默认 5000）
     */
    @Cacheable(value = "tradeConfig", key = "'min_withdrawal_amount_cent'")
    public long getMinWithdrawalAmountCent() {
        return Long.parseLong(get("trade.min_withdrawal_amount_cent", "5000"));
    }

    /**
     * 获取退款窗口天数（默认 7，等于冷冻期）
     */
    @Cacheable(value = "tradeConfig", key = "'refund_window_days'")
    public int getRefundWindowDays() {
        return Integer.parseInt(get("trade.refund_window_days", "7"));
    }

    /**
     * 获取单个供货商最多上架商品数（默认 100）
     */
    @Cacheable(value = "tradeConfig", key = "'max_products_per_seller'")
    public int getMaxProductsPerSeller() {
        return Integer.parseInt(get("trade.max_products_per_seller", "100"));
    }

    /**
     * 获取客服微信（默认 JiShu0724）
     */
    @Cacheable(value = "tradeConfig", key = "'customer_service_wechat'")
    public String getCustomerServiceWechat() {
        return get("trade.customer_service_wechat", "JiShu0724");
    }

    /**
     * 获取全部交易配置。
     * 整体结果缓存到 key='all'，第二次外部调用直接命中。
     */
    @Cacheable(value = "tradeConfig", key = "'all'")
    public Map<String, Object> getAll() {
        Map<String, Object> config = new HashMap<>();
        config.put("commission_rate", getCommissionRate());
        config.put("freeze_days", getFreezeDays());
        config.put("auto_complete_hours", getAutoCompleteHours());
        config.put("min_withdrawal_amount_cent", getMinWithdrawalAmountCent());
        config.put("refund_window_days", getRefundWindowDays());
        config.put("max_products_per_seller", getMaxProductsPerSeller());
        config.put("customer_service_wechat", getCustomerServiceWechat());
        return config;
    }
}
