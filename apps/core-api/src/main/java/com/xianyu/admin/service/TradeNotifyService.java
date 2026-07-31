package com.xianyu.admin.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

/**
 * 供货中心通知服务
 * 封装交易场景通知，调用 notification 表写入站内信
 */
@Service
public class TradeNotifyService {

    private final JdbcTemplate jdbcTemplate;

    public TradeNotifyService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 通知供货商：审核通过
     */
    public void notifyAuditApproved(Long userId, Long businessId, String moduleKey) {
        Map<String, Object> extra = new HashMap<>();
        extra.put("productId", businessId);
        extra.put("moduleKey", moduleKey);
        insertNotification(userId, "货源审核通过",
            "您的货源（ID: " + businessId + "）已通过审核，可前往供货中心上架。", "supply_audit_approved", extra);
    }

    /**
     * 通知供货商：审核驳回
     */
    public void notifyAuditRejected(Long userId, Long businessId, String moduleKey, String reason) {
        Map<String, Object> extra = new HashMap<>();
        extra.put("productId", businessId);
        extra.put("moduleKey", moduleKey);
        extra.put("reason", reason);
        insertNotification(userId, "货源审核驳回",
            "您的货源（ID: " + businessId + "）审核未通过，原因：" + reason + "。请修改后重新提交。", "supply_audit_rejected", extra);
    }

    /**
     * 写入站内信到 notification 表
     * 参考 UserNotificationService.insertInAppNotification
     */
    private void insertNotification(Long userId, String title, String content, String noticeType, Map<String, Object> extra) {
        try {
            jdbcTemplate.update(
                "INSERT INTO notification(tenant_id, user_id, notice_type, notification_type, title, content, " +
                "level, priority, is_read, created_time) " +
                "SELECT tenant_id, ?, ?, ?, ?, ?, 'normal', 0, 0, NOW() FROM sys_user WHERE id = ?",
                userId, noticeType, noticeType, title, content, userId);
        } catch (Exception e) {
            // 通知发送失败不影响主流程
        }
    }
}
