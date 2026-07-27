package com.xianyu.admin.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.OrderManualDeliveryRequest;
import com.xianyu.admin.dto.OrderSyncRequest;
import com.xianyu.admin.dto.ScheduleRedeliveryRequest;
import com.xianyu.admin.entity.CardItem;
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
    private final CardService cardService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public OrderDeliveryCommandService(XianyuTradeOrderMapper orderMapper,
                                       JdbcTemplate jdbcTemplate,
                                       AutomationClient automationClient,
                                       DeliveryExecutionService deliveryExecutionService,
                                       CardService cardService) {
        this.orderMapper = orderMapper;
        this.jdbcTemplate = jdbcTemplate;
        this.automationClient = automationClient;
        this.deliveryExecutionService = deliveryExecutionService;
        this.cardService = cardService;
    }

    @Transactional
    public void manualDelivery(Long tenantId, Long orderId, OrderManualDeliveryRequest request) {
        XianyuTradeOrder order = requireOrder(tenantId, orderId);
        int requestedQuantity = request.getQuantityRequested() == null || request.getQuantityRequested() < 1
                ? 1
                : request.getQuantityRequested();

        Long sourceId = request.getSourceId();
        String deliveryMode = request.getDeliveryMode();
        String deliveryContent = request.getDeliveryContent();
        Long claimedCardItemId = null;
        Long claimedCardGroupId = null;

        if (sourceId != null) {
            // === 从货源库发货 ===
            Map<String, Object> source = fetchDeliverySource(tenantId, sourceId);
            String sourceMode = String.valueOf(source.getOrDefault("delivery_mode", "text"));
            if (sourceMode.isBlank()) {
                sourceMode = "text";
            }
            deliveryMode = sourceMode;

            if ("card".equals(sourceMode)) {
                // 卡密发货：从货源绑定的卡密组认领一张未使用卡密
                Long cardGroupId = toLong(source.get("card_group_id"));
                if (cardGroupId == null) {
                    throw new BizException(400, "该货源未绑定卡密组，无法进行卡密发货");
                }
                claimedCardGroupId = cardGroupId;
                CardItem claimed = cardService.claimUnusedCard(tenantId, cardGroupId, orderId);
                claimedCardItemId = claimed.getId();
                deliveryContent = resolveCardContent(source, claimed);
                if (deliveryContent == null || deliveryContent.isBlank()) {
                    // 卡密内容为空，释放认领并报错
                    cardService.releaseClaimedCard(tenantId, claimedCardGroupId, claimedCardItemId);
                    throw new BizException(409, "认领的卡密内容为空，请检查卡密仓库数据完整性");
                }
            } else {
                // 文本发货：用货源 content 直接作为发货内容
                deliveryContent = String.valueOf(source.getOrDefault("content", ""));
                if (deliveryContent.isBlank()) {
                    throw new BizException(400, "货源内容为空，无法发货");
                }
            }
        } else {
            // === 自定义发货内容（原逻辑） ===
            if (deliveryMode == null || deliveryMode.isBlank()) {
                throw new BizException(400, "发货方式不能为空");
            }
            if (deliveryContent == null || deliveryContent.isBlank()) {
                throw new BizException(400, "发货内容不能为空");
            }
        }

        jdbcTemplate.update(
                "INSERT INTO delivery_record(tenant_id, account_id, order_id, delivery_timing, delivery_mode, delivery_method, " +
                        "delivery_content, content, quantity_requested, quantity_sent, status, delivery_status, retry_count, card_item_id, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,?,NOW(),NOW(),0)",
                tenantId,
                order.getAccountId(),
                orderId,
                request.getDeliveryTiming(),
                deliveryMode,
                "manual_" + deliveryMode,
                deliveryContent,
                deliveryContent,
                requestedQuantity,
                0,
                0,
                "pending",
                claimedCardItemId
        );

        Long recordId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        if (recordId == null) {
            throw new BizException(500, "manual delivery record was not created");
        }

        // 执行发货（executeDelivery 走「补发识别」路径直接重发 delivery_content，不重复认领卡密）
        deliveryExecutionService.retryDelivery(recordId, tenantId);

        // 发货后处理卡密状态
        if (claimedCardItemId != null && claimedCardGroupId != null) {
            Integer status = null;
            try {
                status = jdbcTemplate.queryForObject(
                        "SELECT status FROM delivery_record WHERE id=? AND tenant_id=?",
                        Integer.class, recordId, tenantId);
            } catch (Exception e) {
                log.warn("查询发货记录状态失败 recordId={}, errorType={}", recordId, e.getClass().getSimpleName());
            }
            if (status != null && status == 2) {
                // 发货成功：标记卡密为已使用
                cardService.markCardUsed(tenantId, claimedCardGroupId, claimedCardItemId, orderId);
            } else {
                // 发货未成功（如声明拦截、被防线拦截标记为成功但未实际发送的并发边缘场景除外）：
                // 释放认领的卡密，避免卡密被锁死
                // 注意：status=2 但被防线拦截的并发场景极少，此时卡密会被标记为已使用（防重复发卡密），
                // 用户可在卡密仓库手动重置。
                cardService.releaseClaimedCard(tenantId, claimedCardGroupId, claimedCardItemId);
            }
        }
    }

    /**
     * 查询货源库货源，校验租户归属和未删除。
     */
    private Map<String, Object> fetchDeliverySource(Long tenantId, Long sourceId) {
        Map<String, Object> source;
        try {
            source = jdbcTemplate.queryForMap(
                    "SELECT id, tenant_id, delivery_mode, card_group_id, title, content, remark " +
                            "FROM delivery_text_source WHERE id=? AND tenant_id=? AND deleted=0",
                    sourceId, tenantId);
        } catch (Exception e) {
            throw new BizException(404, "货源不存在或已删除");
        }
        return source;
    }

    /**
     * 卡密发货时，用货源 content 作为模板，替换卡密占位符生成发货内容。
     * 模板变量：{卡号} {密码} {链接} {提取码} {卡密}
     * 若货源 content 为空，直接用卡密原始内容。
     */
    private String resolveCardContent(Map<String, Object> source, CardItem claimed) {
        String template = String.valueOf(source.getOrDefault("content", ""));
        String rawCard = claimed.getCardContent();
        if (rawCard == null || rawCard.isBlank()) {
            return null;
        }
        if (template == null || template.isBlank() || "null".equals(template)) {
            return rawCard;
        }
        String[] parts = rawCard.split("----", 2);
        String cardNumber = parts[0].trim();
        String cardPassword = parts.length > 1 ? parts[1].trim() : "";
        String cardLink = (cardNumber.startsWith("http://") || cardNumber.startsWith("https://")) ? cardNumber : "";
        String cardCode = rawCard;
        try {
            return template
                    .replace("{卡号}", cardNumber)
                    .replace("{密码}", cardPassword)
                    .replace("{链接}", cardLink)
                    .replace("{提取码}", cardPassword)
                    .replace("{卡密}", cardCode);
        } catch (Exception e) {
            log.warn("卡密模板替换失败，回退到原始卡密内容 sourceId={}, errorType={}",
                    source.get("id"), e.getClass().getSimpleName());
            return rawCard;
        }
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
