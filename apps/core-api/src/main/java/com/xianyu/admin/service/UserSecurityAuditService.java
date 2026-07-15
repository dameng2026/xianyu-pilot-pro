package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/** Durable audit boundary for user account security operations. */
@Service
public class UserSecurityAuditService {
    private static final Logger log = LoggerFactory.getLogger(UserSecurityAuditService.class);
    private final JdbcTemplate jdbcTemplate;

    public UserSecurityAuditService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /** Joins a successful security mutation so the audit and mutation commit together. */
    @Transactional
    public void recordRequired(Long tenantId, Long userId, String actionType, String actionName,
                               String target, int status, String message, String ip, String userAgent) {
        insert(tenantId, userId, actionType, actionName, target, status, message, ip, userAgent);
    }

    /** Persists a rejected attempt even when the caller's transaction rolls back. */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordRejectedRequired(Long tenantId, Long userId, String actionType, String actionName,
                                       String target, String message, String ip, String userAgent) {
        insert(tenantId, userId, actionType, actionName, target, 0, message, ip, userAgent);
    }

    private void insert(Long tenantId, Long userId, String actionType, String actionName,
                        String target, int status, String message, String ip, String userAgent) {
        try {
            if (tenantId == null || tenantId <= 0 || userId == null || userId <= 0) {
                throw new IllegalArgumentException("authenticated tenant and user are required");
            }
            int affected = jdbcTemplate.update(
                    "INSERT INTO user_security_log(tenant_id, user_id, action_type, action_name, target, ip_address, user_agent, result_status, message, created_time, deleted) " +
                            "VALUES(?,?,?,?,?,?,?,?,?,NOW(),0)",
                    tenantId, userId, bounded(actionType, 80), bounded(actionName, 120), bounded(target, 255),
                    bounded(ip, 80), bounded(userAgent, 500), status == 1 ? 1 : 0, bounded(message, 500));
            if (affected != 1) throw new IllegalStateException("audit insert was not confirmed");
        } catch (Exception e) {
            log.error("写入用户安全审计失败 userId={} actionType={} errorType={}",
                    userId, actionType, e.getClass().getSimpleName());
            throw new BizException(503, "安全审计日志暂时不可用，操作未完成");
        }
    }

    private String bounded(String value, int maximum) {
        if (value == null) return "";
        String normalized = value.replaceAll("[\\r\\n\\t]+", " ").trim();
        return normalized.length() <= maximum ? normalized : normalized.substring(0, maximum);
    }
}
