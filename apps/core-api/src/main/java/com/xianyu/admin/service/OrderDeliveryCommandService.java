package com.xianyu.admin.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.OrderManualDeliveryRequest;
import com.xianyu.admin.dto.OrderSyncRequest;
import com.xianyu.admin.dto.ScheduleRedeliveryRequest;
import com.xianyu.admin.entity.XianyuTradeOrder;
import com.xianyu.admin.mapper.XianyuTradeOrderMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class OrderDeliveryCommandService {
    private static final Logger log = LoggerFactory.getLogger(OrderDeliveryCommandService.class);

    private final XianyuTradeOrderMapper orderMapper;
    private final JdbcTemplate jdbcTemplate;
    private final AutomationClient automationClient;
    private final DeliveryExecutionService deliveryExecutionService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public OrderDeliveryCommandService(XianyuTradeOrderMapper orderMapper,
                                       JdbcTemplate jdbcTemplate,
                                       AutomationClient automationClient,
                                       DeliveryExecutionService deliveryExecutionService) {
        this.orderMapper = orderMapper;
        this.jdbcTemplate = jdbcTemplate;
        this.automationClient = automationClient;
        this.deliveryExecutionService = deliveryExecutionService;
    }

    @Transactional
    public void manualDelivery(Long tenantId, Long orderId, OrderManualDeliveryRequest request) {
        XianyuTradeOrder order = requireOrder(tenantId, orderId);
        int requestedQuantity = request.getQuantityRequested() == null || request.getQuantityRequested() < 1
                ? 1
                : request.getQuantityRequested();

        jdbcTemplate.update(
                "INSERT INTO delivery_record(tenant_id, account_id, order_id, delivery_timing, delivery_mode, delivery_method, " +
                        "delivery_content, content, quantity_requested, quantity_sent, status, delivery_status, retry_count, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,NOW(),NOW(),0)",
                tenantId,
                order.getAccountId(),
                orderId,
                request.getDeliveryTiming(),
                request.getDeliveryMode(),
                "manual_" + request.getDeliveryMode(),
                request.getDeliveryContent(),
                request.getDeliveryContent(),
                requestedQuantity,
                0,
                0,
                "pending"
        );

        Long recordId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        if (recordId == null) {
            throw new BizException(500, "manual delivery record was not created");
        }
        deliveryExecutionService.retryDelivery(recordId, tenantId);
    }

    public Map<String, Object> syncOrder(Long tenantId, Long orderId) {
        XianyuTradeOrder order = requireOrder(tenantId, orderId);
        try {
            Map<String, Object> result = automationClient.postInternalForData(
                    "/api/internal/orders/sync-sold",
                    Map.of(
                            "tenantId", tenantId,
                            "accountId", order.getAccountId(),
                            "externalOrderId", order.getExternalOrderId()
                    ),
                    tenantId
            );
            return normalizeSyncResult(result, "同步结果为空");
        } catch (Exception e) {
            log.warn("同步单个订单失败 tenantId={} orderId={} accountId={}, errorType={}", tenantId, orderId, order.getAccountId(), e.getClass().getSimpleName());
            return failedSyncResult(extractSyncFailureMessage(e, "订单同步失败"));
        }
    }

    public Map<String, Object> syncOrders(Long tenantId, OrderSyncRequest request) {
        LinkedHashMap<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenantId", tenantId);
        payload.put("accountId", request.getAccountId());
        payload.put("externalOrderId", request.getExternalOrderId());

        Map<String, Object> result;
        try {
            result = normalizeSyncResult(
                    automationClient.postInternalForData("/api/internal/orders/sync-sold", payload, tenantId),
                    "同步结果为空"
            );
        } catch (Exception e) {
            log.warn("同步账号订单失败 tenantId={} accountId={}, errorType={}", tenantId, request.getAccountId(), e.getClass().getSimpleName());
            return failedSyncResult(extractSyncFailureMessage(e, "账号订单同步失败"));
        }

        if (Boolean.TRUE.equals(request.getSyncDeliveryStatus())) {
            try {
                automationClient.postInternalForData("/api/internal/orders/sync-delivery-status", payload, tenantId);
            } catch (Exception e) {
                log.warn("同步发货状态失败 tenantId={} accountId={}, errorType={}", tenantId, request.getAccountId(), e.getClass().getSimpleName());
            }
        }
        return result;
    }

    public void scheduleRedelivery(Long tenantId, Long recordId, ScheduleRedeliveryRequest request) {
        Map<String, Object> record = jdbcTemplate.queryForMap(
                "SELECT id, order_id, account_id, delivery_timing FROM delivery_record WHERE id=? AND tenant_id=? AND deleted=0",
                recordId,
                tenantId
        );

        LinkedHashMap<String, Object> config = new LinkedHashMap<>();
        config.put("recordId", recordId);
        config.put("orderId", record.get("order_id"));
        config.put("deliveryTiming", record.get("delivery_timing"));

        jdbcTemplate.update(
                "INSERT INTO scheduled_task(tenant_id, account_id, task_type, task_name, cron_expression, config_json, enabled, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,NOW(),NOW(),0)",
                tenantId,
                toLong(record.get("account_id")),
                "redelivery",
                "Redelivery #" + recordId,
                request.getCronExpression(),
                toJson(config),
                1
        );
    }

    private XianyuTradeOrder requireOrder(Long tenantId, Long orderId) {
        XianyuTradeOrder order = orderMapper.findById(tenantId, orderId);
        if (order == null) {
            throw new BizException(404, "order not found");
        }
        return order;
    }

    private String toJson(Map<String, Object> payload) {
        try {
            return objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException e) {
            throw new BizException(500, "cannot serialize scheduled task config");
        }
    }

    private Long toLong(Object value) {
        if (value instanceof Number number) {
            return number.longValue();
        }
        if (value == null) {
            return null;
        }
        return Long.parseLong(String.valueOf(value));
    }

    private Map<String, Object> normalizeSyncResult(Map<String, Object> result, String emptyMessage) {
        if (result == null || result.isEmpty()) {
            return failedSyncResult(emptyMessage);
        }

        if (result.containsKey("ok")) {
            return result;
        }

        Object success = result.get("success");
        if (success != null) {
            if (Boolean.TRUE.equals(success)) {
                return result;
            }
            return failedSyncResult(firstNonBlank(
                    result.get("error"),
                    result.get("message"),
                    emptyMessage
            ));
        }

        Object code = result.get("code");
        if (code != null && !String.valueOf(code).matches("200|0")) {
            return failedSyncResult(firstNonBlank(
                    result.get("msg"),
                    result.get("message"),
                    emptyMessage
            ));
        }

        return result;
    }

    private Map<String, Object> failedSyncResult(String message) {
        return Map.of(
                "ok", false,
                "message", firstNonBlank(message, "同步失败")
        );
    }

    private String extractSyncFailureMessage(Exception e, String fallback) {
        if (e instanceof com.xianyu.admin.common.BizException bizException
                && bizException.getMessage() != null
                && !bizException.getMessage().isBlank()) {
            return bizException.getMessage();
        }
        return fallback;
    }

    private String firstNonBlank(Object... values) {
        if (values == null) {
            return "";
        }
        for (Object value : values) {
            if (value == null) {
                continue;
            }
            String text = String.valueOf(value).trim();
            if (!text.isEmpty() && !"null".equalsIgnoreCase(text)) {
                return text;
            }
        }
        return "";
    }
}
