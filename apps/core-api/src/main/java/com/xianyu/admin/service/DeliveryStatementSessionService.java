package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.entity.DeliveryStatementSession;
import com.xianyu.admin.entity.XianyuTradeOrder;
import com.xianyu.admin.mapper.DeliveryStatementSessionMapper;
import com.xianyu.admin.mapper.XianyuTradeOrderMapper;
import com.xianyu.admin.security.TenantContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 发货声明会话服务
 *
 * 职责：
 * 1. 提供声明会话列表查询（发货记录页"等待确认"标签使用）
 * 2. 卖家手动确认/取消会话
 * 3. 提供 executeDelivery 前置校验：声明开关开启时，必须有 confirmed 会话才能发货
 * 4. 提供 Java 调度扫描时的声明拦截：声明开关开启且未 confirmed 时跳过发货（由 Python WS 路径处理）
 */
@Service
public class DeliveryStatementSessionService {
    private static final Logger log = LoggerFactory.getLogger(DeliveryStatementSessionService.class);

    /** 状态常量 */
    public static final String STATUS_DECLARING = "declaring";
    public static final String STATUS_WAITING = "waiting";
    public static final String STATUS_CONFIRMED = "confirmed";
    public static final String STATUS_CANCELLED = "cancelled";

    /** 确认/取消来源 */
    public static final String SOURCE_BUYER = "buyer";
    public static final String SOURCE_SELLER = "seller";

    /** 买家回复"取消"后，向买家发送的提示文案 */
    private static final String BUYER_CANCEL_REPLY_TEMPLATE =
            "已为您转人工客服，请耐心等待，客服会尽快与您联系处理退款事宜。";

    private final JdbcTemplate jdbcTemplate;
    private final DeliveryStatementSessionMapper sessionMapper;
    private final XianyuTradeOrderMapper orderMapper;
    private final DeliveryExecutionService deliveryExecutionService;
    private final UserNotificationService userNotificationService;
    private final AutomationClient automationClient;
    private final DeliveryStatementCheckService checkService;

    public DeliveryStatementSessionService(JdbcTemplate jdbcTemplate,
                                           DeliveryStatementSessionMapper sessionMapper,
                                           XianyuTradeOrderMapper orderMapper,
                                           DeliveryExecutionService deliveryExecutionService,
                                           UserNotificationService userNotificationService,
                                           AutomationClient automationClient,
                                           DeliveryStatementCheckService checkService) {
        this.jdbcTemplate = jdbcTemplate;
        this.sessionMapper = sessionMapper;
        this.orderMapper = orderMapper;
        this.deliveryExecutionService = deliveryExecutionService;
        this.userNotificationService = userNotificationService;
        this.automationClient = automationClient;
        this.checkService = checkService;
    }

    // ============================================================
    // 查询
    // ============================================================

    public Map<String, Object> listSessions(Long tenantId, Long accountId, String status, int page, int size) {
        if (page < 1) page = 1;
        if (size < 1 || size > 100) size = 20;
        int offset = (page - 1) * size;
        List<DeliveryStatementSession> rows = sessionMapper.list(tenantId, accountId, status, offset, size);
        int total = sessionMapper.count(tenantId, accountId, status);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("list", rows);
        result.put("total", total);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    public DeliveryStatementSession getSession(Long tenantId, Long sessionId) {
        DeliveryStatementSession session = sessionMapper.findById(tenantId, sessionId);
        if (session == null) {
            throw new BizException(404, "声明会话不存在或已删除");
        }
        return session;
    }

    // ============================================================
    // 卖家手动操作
    // ============================================================

    /**
     * 卖家手动确认声明 → 触发该订单发货
     *
     * 流程：
     * 1. 校验 session 存在且 status=waiting
     * 2. session.status=confirmed, confirm_source=seller
     * 3. 创建 delivery_record(delivery_type='auto', delivery_timing='after_statement_confirm')
     * 4. 绑定 delivery_record_id 到 session
     * 5. 调用 executeDelivery 执行发货
     * 6. 失败时不回滚 session（保持 confirmed），由 delivery_record 的失败重试机制接管
     */
    @Transactional
    public void manualConfirm(Long tenantId, Long sessionId) {
        DeliveryStatementSession session = getSession(tenantId, sessionId);
        if (!STATUS_WAITING.equals(session.getStatus())) {
            throw new BizException(409, "当前会话状态不支持确认（仅等待买家确认状态可操作）");
        }

        // 1. 标记 confirmed
        int affected = sessionMapper.markConfirmed(tenantId, sessionId, LocalDateTime.now(), SOURCE_SELLER, null);
        if (affected == 0) {
            throw new BizException(409, "会话状态已变更，请刷新后重试");
        }

        // 2. 查订单
        XianyuTradeOrder order = findOrderByExternalOrderId(tenantId, session.getAccountId(), session.getOrderId());
        if (order == null) {
            log.warn("卖家手动确认声明：订单未找到，已标记 confirmed 但未触发发货 tenantId={} accountId={} orderId={}",
                    tenantId, session.getAccountId(), session.getOrderId());
            userNotificationService.notifyManualDeliveryReminder(
                    tenantId, session.getAccountId(), null, session.getOrderId(),
                    session.getGoodsTitle(), "订单未同步到本地，无法自动发货，请人工处理");
            return;
        }

        // 3. 创建 delivery_record（timing=after_statement_confirm，沿用 after_payment 的发货配置）
        Long recordId = createDeliveryRecordForStatementConfirm(tenantId, order);
        sessionMapper.bindDeliveryRecord(tenantId, sessionId, recordId);

        // 4. 触发发货（在新事务中执行，避免发货失败回滚 confirmed 状态）
        try {
            deliveryExecutionService.retryDelivery(recordId, tenantId);
        } catch (Exception e) {
            log.warn("卖家手动确认声明后触发发货失败 tenantId={} sessionId={} recordId={} errorType={}",
                    tenantId, sessionId, recordId, e.getClass().getSimpleName());
            // 不抛出：session 已 confirmed，delivery_record 失败由重试机制处理
        }
    }

    /**
     * 卖家手动取消声明 → 通知买家+不发货
     *
     * 流程：
     * 1. 校验 session 存在且 status=waiting
     * 2. session.status=cancelled, cancel_source=seller
     * 3. 向买家发送取消提示文案
     * 4. 发飞书/站内通知给卖家
     * 5. 不创建 delivery_record
     */
    @Transactional
    public void manualCancel(Long tenantId, Long sessionId) {
        DeliveryStatementSession session = getSession(tenantId, sessionId);
        if (!STATUS_WAITING.equals(session.getStatus())) {
            throw new BizException(409, "当前会话状态不支持取消（仅等待买家确认状态可操作）");
        }

        int affected = sessionMapper.markCancelled(tenantId, sessionId, LocalDateTime.now(), SOURCE_SELLER, null);
        if (affected == 0) {
            throw new BizException(409, "会话状态已变更，请刷新后重试");
        }

        // 向买家发送取消提示（失败不影响主流程）
        sendCancelReplyToBuyer(session);

        // 通知卖家
        userNotificationService.notifyManualDeliveryReminder(
                tenantId,
                session.getAccountId(),
                null,
                session.getOrderId(),
                session.getGoodsTitle(),
                "卖家手动取消：买家未确认发货声明，已取消该订单的自动发货");
    }

    // ============================================================
    // 前置校验（委托给 DeliveryStatementCheckService，避免循环依赖）
    // ============================================================

    /**
     * 判断指定租户的发货声明是否开启
     */
    public boolean isStatementEnabled(Long tenantId) {
        return checkService.isStatementEnabled(tenantId);
    }

    /**
     * 发货前置校验：声明开关开启时，必须存在该订单的 confirmed 会话才能发货
     */
    public boolean canDeliverAfterStatementCheck(Long tenantId, Long accountId, String externalOrderId) {
        return checkService.canDeliverAfterStatementCheck(tenantId, accountId, externalOrderId);
    }

    // ============================================================
    // 私有辅助
    // ============================================================

    private XianyuTradeOrder findOrderByExternalOrderId(Long tenantId, Long accountId, String externalOrderId) {
        if (externalOrderId == null || externalOrderId.isBlank()) {
            return null;
        }
        try {
            return orderMapper.findByExternalOrderId(tenantId, accountId, externalOrderId);
        } catch (Exception e) {
            log.warn("按 external_order_id 查询订单失败 tenantId={} accountId={} orderId={} errorType={}",
                    tenantId, accountId, externalOrderId, e.getClass().getSimpleName());
            return null;
        }
    }

    private Long createDeliveryRecordForStatementConfirm(Long tenantId, XianyuTradeOrder order) {
        jdbcTemplate.update(
                "INSERT INTO delivery_record(tenant_id, account_id, order_id, delivery_type, delivery_timing, " +
                        "status, delivery_status, retry_count, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,'auto','after_statement_confirm',0,'pending',0,NOW(),NOW(),0)",
                tenantId, order.getAccountId(), order.getId());
        return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    }

    /**
     * 向买家发送取消提示文案
     * 通过 AutomationClient 调用 Python 的 /api/websocket/sendMessage 接口
     * 字段对齐 misc.py websocket_send_message：accountId / sId / peerUserId / text
     */
    private void sendCancelReplyToBuyer(DeliveryStatementSession session) {
        try {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("accountId", session.getAccountId());
            payload.put("sId", session.getSId());
            payload.put("peerUserId", session.getBuyerId());
            payload.put("text", BUYER_CANCEL_REPLY_TEMPLATE);
            payload.put("xyGoodsId", session.getXyGoodsId());
            automationClient.postInternalForData(
                    "/api/websocket/sendMessage", payload, 30, session.getTenantId());
        } catch (Exception e) {
            log.warn("向买家发送取消提示失败 sessionId={} accountId={} errorType={}",
                    session.getId(), session.getAccountId(), e.getClass().getSimpleName());
        }
    }
}
