package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * 支付回调审计使用独立事务，确保验签失败和业务回滚也留下可追溯记录。
 */
@Service
public class PaymentCallbackAuditService {
    private final JdbcTemplate jdbcTemplate;

    public PaymentCallbackAuditService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void record(String orderNo, String channel, String provider, String rawBody,
                       String signature, boolean verified, boolean processed, String message) {
        try {
            int affected = jdbcTemplate.update(
                    "INSERT INTO payment_callback_log(order_no, channel_type, provider_type, request_body, signature, verify_status, process_status, message, created_time) VALUES(?,?,?,?,?,?,?,?,NOW())",
                    bounded(orderNo, 80), bounded(channel, 30), bounded(provider, 30), bounded(rawBody, 64_000),
                    bounded(signature, 500), verified ? 1 : 0, processed ? 1 : 0, bounded(message, 500));
            if (affected != 1) throw new BizException(503, "支付回调审计写入未被数据库确认");
        } catch (BizException e) {
            throw e;
        } catch (DataAccessException e) {
            throw new BizException(503, "支付回调审计暂时无法写入，请稍后重试");
        }
    }

    private String bounded(String value, int maxLength) {
        if (value == null) return "";
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }
}
