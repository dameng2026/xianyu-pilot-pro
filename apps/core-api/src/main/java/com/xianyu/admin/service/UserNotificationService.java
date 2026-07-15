package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class UserNotificationService {
    private static final String MANUAL_DELIVERY_EVENT = "代发货提醒";

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public UserNotificationService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void notifyManualDeliveryReminder(Long tenantId,
                                             Long accountId,
                                             Long orderId,
                                             String orderNo,
                                             String goodsTitle,
                                             String reason) {
        if (tenantId == null || orderId == null) {
            return;
        }

        List<Long> userIds = jdbcTemplate.query(
                "SELECT DISTINCT user_id FROM user_notification_setting WHERE tenant_id=? AND deleted=0",
                (rs, rowNum) -> rs.getLong(1),
                tenantId
        );
        boolean hasSettings = userIds != null && !userIds.isEmpty();
        if (!hasSettings) {
            Long currentUserId = TenantContext.getCurrentUserId();
            if (currentUserId != null) {
                userIds = List.of(currentUserId);
            } else if (UserContext.userId() != null) {
                userIds = List.of(UserContext.userId());
            } else {
                userIds = List.of();
            }
        }

        String title = "代发货提醒";
        String content = buildManualDeliveryContent(orderNo, goodsTitle, reason);
        for (Long userId : userIds) {
            if (userId == null) {
                continue;
            }
            if (hasSettings && !isEventEnabled(tenantId, userId, MANUAL_DELIVERY_EVENT)) {
                continue;
            }
            insertInAppNotification(tenantId, userId, accountId, MANUAL_DELIVERY_EVENT, title, content, "warn", 2);
        }
    }

    public void insertInAppNotification(Long tenantId,
                                        Long userId,
                                        Long accountId,
                                        String eventType,
                                        String title,
                                        String content,
                                        String level,
                                        int priority) {
        jdbcTemplate.update(
                "INSERT INTO notification(tenant_id, user_id, account_id, notice_type, notification_type, title, content, level, priority, is_read, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,0,NOW(),NOW(),0)",
                tenantId, userId, accountId, eventType, eventType, title, content, level, priority
        );
    }

    public boolean isEventEnabled(Long tenantId, Long userId, String eventType) {
        try {
            String json = jdbcTemplate.queryForObject(
                    "SELECT config_json FROM user_notification_setting WHERE tenant_id=? AND user_id=? AND deleted=0 LIMIT 1",
                    String.class, tenantId, userId
            );
            if (json == null || json.isBlank()) {
                return true;
            }
            Map<String, Object> config = objectMapper.readValue(json, new TypeReference<LinkedHashMap<String, Object>>() {});
            Object eventsObj = config.get("events");
            if (!(eventsObj instanceof List<?> events)) {
                return true;
            }
            for (Object eventObj : events) {
                if (!(eventObj instanceof Map<?, ?> eventMap)) {
                    continue;
                }
                Object name = eventMap.get("event");
                if (name != null && eventType.equals(String.valueOf(name))) {
                    Object enabled = eventMap.get("enabled");
                    return enabled == null || Boolean.TRUE.equals(enabled) || "true".equalsIgnoreCase(String.valueOf(enabled)) || "1".equals(String.valueOf(enabled));
                }
            }
        } catch (Exception ignored) {
            return true;
        }
        return true;
    }

    private String buildManualDeliveryContent(String orderNo, String goodsTitle, String reason) {
        List<String> lines = new ArrayList<>();
        lines.add("检测到新订单自动发货未成功，需要人工代发货。");
        if (orderNo != null && !orderNo.isBlank()) {
            lines.add("订单号：" + orderNo);
        }
        if (goodsTitle != null && !goodsTitle.isBlank()) {
            lines.add("商品：" + goodsTitle);
        }
        if (reason != null && !reason.isBlank()) {
            lines.add("失败原因：" + reason);
        }
        lines.add("提醒时间：" + LocalDateTime.now());
        return String.join("\n", lines);
    }
}
