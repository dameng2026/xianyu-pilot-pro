package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.OrderManualDeliveryRequest;
import com.xianyu.admin.dto.OrderSyncRequest;
import com.xianyu.admin.dto.XianyuTradeOrderDTO;
import com.xianyu.admin.dto.XianyuTradeOrderVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.OrderDeliveryCommandService;
import com.xianyu.admin.service.XianyuTradeOrderService;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/orders")
@Validated
public class XianyuTradeOrderController {
    private final XianyuTradeOrderService orderService;
    private final OrderDeliveryCommandService orderDeliveryCommandService;
    private final AutomationClient automationClient;
    private final JdbcTemplate jdbcTemplate;

    public XianyuTradeOrderController(XianyuTradeOrderService orderService,
                                      OrderDeliveryCommandService orderDeliveryCommandService,
                                      AutomationClient automationClient,
                                      JdbcTemplate jdbcTemplate) {
        this.orderService = orderService;
        this.orderDeliveryCommandService = orderDeliveryCommandService;
        this.automationClient = automationClient;
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 分页查询订单列表
     * 支持排序：sortField（createdAt/orderStatus/buyerName/totalAmount）+ sortOrder（asc/desc）
     * sortField 不传或不在白名单内时使用默认排序：created_time DESC
     */
    @GetMapping
    public Result<PageResult<XianyuTradeOrderVO>> page(
            @RequestParam(required = false) Long accountId,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer status,
            @RequestParam(required = false) String buyerId,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "false") boolean sync,
            @RequestParam(required = false) String sortField,
            @RequestParam(required = false) String sortOrder) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (sync) {
            throw new BizException(410, "GET 订单列表不再执行同步；请先调用 POST /api/orders/sync，再刷新列表");
        }
        PageResult<XianyuTradeOrderVO> result = orderService.page(tenantId, accountId, keyword, status, buyerId,
                current, size, sortField, sortOrder);
        return Result.ok(result);
    }

    /**
     * 查询订单详情（含订单项）
     */
    @GetMapping("/{id}")
    public Result<XianyuTradeOrderVO> detail(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        XianyuTradeOrderVO result = orderService.detail(tenantId, id);
        return Result.ok(result);
    }

    /**
     * 向买家发送“求小红花”消息并标记订单。
     */
    @PostMapping("/{id}/request-red-flower")
    public Result<Void> requestRedFlower(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }

        Map<String, Object> order;
        try {
            order = jdbcTemplate.queryForMap(
                    "SELECT account_id, buyer_id, external_order_id, is_red_flower " +
                            "FROM xianyu_trade_order WHERE id=? AND tenant_id=? AND deleted=0",
                    id, tenantId);
        } catch (EmptyResultDataAccessException e) {
            throw new BizException(404, "订单不存在");
        }

        Object redFlower = order.get("is_red_flower");
        if (redFlower != null && "1".equals(String.valueOf(redFlower))) {
            throw new BizException(400, "该订单已求过小红花");
        }

        Long accountId = ((Number) order.get("account_id")).longValue();
        String buyerId = String.valueOf(order.get("buyer_id") == null ? "" : order.get("buyer_id"));
        String orderNo = String.valueOf(order.get("external_order_id") == null ? "" : order.get("external_order_id"));
        if (buyerId.isBlank()) {
            throw new BizException(400, "订单缺少买家ID，无法发送求小红花消息");
        }

        String sid;
        try {
            sid = jdbcTemplate.queryForObject(
                    "SELECT m.s_id FROM xianyu_message m " +
                            "WHERE m.tenant_id=? AND m.account_id=? AND m.deleted=0 " +
                            "AND m.s_id IS NOT NULL AND m.s_id <> '' " +
                            "AND m.conversation_id = (" +
                            "  SELECT c.id FROM xianyu_conversation c " +
                            "  WHERE c.tenant_id=? AND c.account_id=? AND c.deleted=0 " +
                            "    AND REPLACE(c.external_buyer_id, '@goofish', '') = REPLACE(?, '@goofish', '') " +
                            "  ORDER BY COALESCE(c.last_message_time, c.updated_time, c.created_time) DESC, c.id DESC LIMIT 1" +
                            ") ORDER BY COALESCE(m.message_time, 0) DESC, m.id DESC LIMIT 1",
                    String.class, tenantId, accountId, tenantId, accountId, buyerId);
        } catch (EmptyResultDataAccessException e) {
            sid = null;
        }
        if (sid == null || sid.isBlank()) {
            throw new BizException(400, "未找到与买家的会话，无法发送求小红花消息");
        }

        String peerId = buyerId.contains("@goofish") ? buyerId : buyerId + "@goofish";
        Map<String, Object> payload = new HashMap<>();
        payload.put("accountId", accountId);
        payload.put("cid", sid);
        payload.put("toId", peerId);
        payload.put("message", "亲，方便的话确认收货后帮忙点亮小红花哦，非常感谢您的支持！");

        // Python 端会校验账号归属、会话有效性并真实发送；业务失败直接抛错
        automationClient.postInternalForDataOrThrow("/api/websocket/sendMessage", payload);

        jdbcTemplate.update(
                "UPDATE xianyu_trade_order SET is_red_flower=1, updated_time=NOW() WHERE id=? AND tenant_id=?",
                id, tenantId);
        return Result.ok(null);
    }

    /**
     * 查询今日订单金额（仅统计 order_status IN (1,2,3,4) 且 deleted=0 的订单 total_amount 之和）。
     * accountId 为空时统计当前租户全部账号。
     */
    @GetMapping("/today-amount")
    public Result<Map<String, Object>> todayAmount(@RequestParam(required = false) Long accountId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        BigDecimal amount = orderService.todayAmount(tenantId, accountId);
        Map<String, Object> result = new HashMap<>();
        result.put("todayAmount", amount == null ? BigDecimal.ZERO : amount);
        return Result.ok(result);
    }

    /**
     * 更新订单
     */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody XianyuTradeOrderDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        orderService.update(tenantId, id, dto);
        return Result.ok(null);
    }

    @PostMapping("/{id}/manual-delivery")
    public Result<Void> manualDelivery(@PathVariable Long id, @Valid @RequestBody OrderManualDeliveryRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        orderDeliveryCommandService.manualDelivery(tenantId, id, request);
        return Result.ok(null);
    }

    @PostMapping("/{id}/sync")
    public Result<Map<String, Object>> syncOne(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> result = orderDeliveryCommandService.syncOrder(tenantId, id);
        return Result.ok(result);
    }

    @PostMapping("/sync")
    public Result<Map<String, Object>> syncList(@RequestBody OrderSyncRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> result = orderDeliveryCommandService.syncOrders(tenantId, request);
        return Result.ok(result);
    }
}
