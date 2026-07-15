package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryExecutionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 自动发货统计、触发、扫描控制器
 * 对应前端 AutoDeliveryPage 的统计和扫描操作
 */
@RestController
@RequestMapping("/api/auto-delivery")
public class DeliveryOpsController {
    private static final Logger log = LoggerFactory.getLogger(DeliveryOpsController.class);
    private static final Set<String> ALLOWED_TIMINGS = Set.of("after_payment", "after_receipt", "after_review");

    private final JdbcTemplate jdbcTemplate;
    private final DeliveryExecutionService deliveryExecutionService;

    public DeliveryOpsController(JdbcTemplate jdbcTemplate, DeliveryExecutionService deliveryExecutionService) {
        this.jdbcTemplate = jdbcTemplate;
        this.deliveryExecutionService = deliveryExecutionService;
    }

    /**
     * 获取自动发货统计
     * GET /api/auto-delivery/stats
     */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        Long tenantId = requireTenant();
        LocalDate today = LocalDate.now();

        try {
            Integer todaySuccess = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM delivery_record WHERE tenant_id=? AND deleted=0 AND DATE(created_time)=? AND status=2",
                    Integer.class, tenantId, today);
            Integer todayFail = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM delivery_record WHERE tenant_id=? AND deleted=0 AND DATE(created_time)=? AND status=3",
                    Integer.class, tenantId, today);
            Integer pendingOrders = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM delivery_record WHERE tenant_id=? AND deleted=0 AND status=0",
                    Integer.class, tenantId);
            Integer lowStockGoods = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM delivery_goods_config WHERE tenant_id=? AND deleted=0 AND config_json LIKE '%\"stockLow\":true%'",
                    Integer.class, tenantId);
            Integer enabledGoods = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM delivery_goods_config WHERE tenant_id=? AND deleted=0 AND config_json LIKE '%\"enabled\":1%'",
                    Integer.class, tenantId);

            return Result.ok(Map.of(
                    "todaySuccess", countOrZero(todaySuccess),
                    "todayFail", countOrZero(todayFail),
                    "pendingOrders", countOrZero(pendingOrders),
                    "lowStockGoods", countOrZero(lowStockGoods),
                    "enabledGoods", countOrZero(enabledGoods)
            ));
        } catch (Exception e) {
            log.error("查询自动发货统计失败, tenantId={}, errorType={}", tenantId, e.getClass().getSimpleName());
            throw new BizException(503, "自动发货统计暂时无法加载，请稍后重试");
        }
    }

    /**
     * 手动触发单个订单发货
     * POST /api/auto-delivery/trigger
     * body: { orderId: 123, timing: "after_payment" }
     * 创建发货记录后立即执行发货
     */
    @PostMapping("/trigger")
    public Result<Void> trigger(@RequestBody Map<String, Object> body) {
        Long tenantId = requireTenant();
        if (body == null) {
            throw new BizException(400, "请求内容不能为空");
        }
        Object orderId = body.get("orderId");
        if (orderId == null || String.valueOf(orderId).isBlank()) {
            throw new BizException(400, "请提供订单ID");
        }

        String timing = stringValue(body.getOrDefault("timing", "after_payment"), "timing").trim();
        if (!ALLOWED_TIMINGS.contains(timing)) {
            throw new BizException(400, "timing 仅支持 after_payment、after_receipt 或 after_review");
        }

        Long orderIdLong = positiveId(orderId, "orderId");

        // 创建一条待执行的发货记录
        try {
            int inserted = jdbcTemplate.update(
                    "INSERT INTO delivery_record(tenant_id, account_id, order_id, delivery_type, delivery_timing, status, retry_count, created_time, updated_time, deleted) " +
                            "SELECT ?, o.account_id, ?, 'manual', ?, 0, 0, NOW(), NOW(), 0 FROM xianyu_trade_order o WHERE o.tenant_id=? AND o.id=? AND o.deleted=0",
                    tenantId, orderIdLong, timing, tenantId, orderIdLong);
            if (inserted == 0) {
                throw new BizException(404, "订单不存在或已删除");
            }
            if (inserted != 1) {
                throw new BizException(503, "发货任务暂时无法创建，请稍后重试");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("创建手动发货记录失败, tenantId={}, orderId={}, errorType={}", tenantId, orderIdLong, e.getClass().getSimpleName());
            throw new BizException(503, "发货任务暂时无法创建，请稍后重试");
        }

        // 获取刚创建的记录并立即执行
        Long recordId;
        Map<String, Object> record;
        try {
            recordId = jdbcTemplate.queryForObject(
                    "SELECT id FROM delivery_record WHERE tenant_id=? AND order_id=? AND delivery_type='manual' AND status=0 ORDER BY id DESC LIMIT 1",
                    Long.class, tenantId, orderIdLong);
            if (recordId == null) {
                throw new IllegalStateException("created delivery record id is null");
            }
            record = jdbcTemplate.queryForMap(
                    "SELECT dr.*, o.account_id AS order_account_id, o.buyer_name, o.buyer_id, o.external_order_id " +
                            "FROM delivery_record dr " +
                            "JOIN xianyu_trade_order o ON o.id = dr.order_id AND o.deleted = 0 " +
                            "WHERE dr.id=? AND dr.tenant_id=? AND dr.deleted=0",
                    recordId, tenantId);
        } catch (Exception e) {
            log.error("读取手动发货记录失败, tenantId={}, orderId={}, errorType={}", tenantId, orderIdLong, e.getClass().getSimpleName());
            throw new BizException(503, "发货任务暂时无法读取，请稍后重试");
        }

        try {
            deliveryExecutionService.executeDelivery(record);
            return Result.ok(null);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("执行手动发货失败, tenantId={}, orderId={}, recordId={}, errorType={}", tenantId, orderIdLong, recordId, e.getClass().getSimpleName());
            throw new BizException(503, "发货暂时无法执行，请检查账号状态与发货配置后重试");
        }
    }

    /**
     * 扫描待发货订单
     * POST /api/auto-delivery/scan
     */
    @PostMapping("/scan")
    public Result<Map<String, Object>> scan() {
        Long tenantId = requireTenant();

        // 查询待发货的订单（状态为已付款待发货，且有商品配置）
        String sql = "SELECT o.id AS order_id, MAX(oi.goods_id) AS goods_id, MAX(g.account_id) AS account_id " +
                "FROM xianyu_trade_order o " +
                "JOIN xianyu_trade_order_item oi ON oi.order_id=o.id AND oi.deleted=0 " +
                "JOIN xianyu_goods g ON g.id=oi.goods_id AND g.deleted=0 " +
                "JOIN delivery_goods_config dgc ON dgc.goods_id=g.id AND dgc.tenant_id=? AND dgc.deleted=0 " +
                "WHERE o.tenant_id=? AND o.deleted=0 AND o.order_status IN (1,2) " +
                "AND dgc.config_json LIKE '%\"payDelivery\"%' " +
                "AND dgc.config_json LIKE '%\"enabled\":1%' " +
                "AND o.id NOT IN (SELECT order_id FROM delivery_record WHERE tenant_id=? AND deleted=0 AND delivery_timing='after_payment' AND status IN (0,1,2,3,5,6,7)) " +
                "GROUP BY o.id " +
                "LIMIT 50";

        List<Map<String, Object>> orders;
        try {
            orders = jdbcTemplate.queryForList(sql, tenantId, tenantId, tenantId);
        } catch (Exception e) {
            log.error("扫描待发货订单失败, tenantId={}, errorType={}", tenantId, e.getClass().getSimpleName());
            throw new BizException(503, "待发货订单暂时无法扫描，请稍后重试");
        }

        int created = 0;
        int executed = 0;
        int failed = 0;
        for (Map<String, Object> order : orders) {
            Long orderIdLong;
            Long recordId;
            Map<String, Object> record;
            try {
                orderIdLong = positiveId(order.get("order_id"), "order_id");

                Integer existCount = jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM delivery_record WHERE tenant_id=? AND order_id=? AND delivery_timing='after_payment' AND deleted=0 AND status IN (0,1,2,3,5,6,7)",
                        Integer.class, tenantId, orderIdLong);
                if (existCount != null && existCount > 0) continue;

                int inserted = jdbcTemplate.update(
                        "INSERT INTO delivery_record(tenant_id, account_id, order_id, delivery_type, delivery_timing, status, retry_count, created_time, updated_time, deleted) " +
                                "VALUES(?,?,?,'auto','after_payment',0,0,NOW(),NOW(),0)",
                        tenantId, order.get("account_id"), orderIdLong);
                if (inserted != 1) {
                    throw new IllegalStateException("delivery record insert affected " + inserted + " rows");
                }
                created++;

                recordId = jdbcTemplate.queryForObject(
                        "SELECT id FROM delivery_record WHERE tenant_id=? AND order_id=? AND delivery_type='auto' AND status=0 ORDER BY id DESC LIMIT 1",
                        Long.class, tenantId, orderIdLong);
                if (recordId == null) {
                    throw new IllegalStateException("created delivery record id is null");
                }
                record = jdbcTemplate.queryForMap(
                        "SELECT dr.*, o.account_id AS order_account_id, o.buyer_name, o.buyer_id, o.external_order_id " +
                                "FROM delivery_record dr " +
                                "JOIN xianyu_trade_order o ON o.id = dr.order_id AND o.deleted = 0 " +
                                "WHERE dr.id=? AND dr.tenant_id=? AND dr.deleted=0",
                        recordId, tenantId);
            } catch (Exception e) {
                log.error("创建或读取扫描发货记录失败, tenantId={}, orderId={}, errorType={}",
                        tenantId, order.get("order_id"), e.getClass().getSimpleName());
                throw new BizException(503, "扫描发货任务暂时无法创建，请稍后重试");
            }

            try {
                deliveryExecutionService.executeDelivery(record);
                executed++;
            } catch (BizException e) {
                if (e.getCode() >= 500) {
                    throw e;
                }
                failed++;
                log.warn("扫描发货被业务规则拒绝, tenantId={}, orderId={}, recordId={}, code={}",
                        tenantId, orderIdLong, recordId, e.getCode());
            } catch (DataAccessException e) {
                log.error("扫描发货依赖数据库失败, tenantId={}, orderId={}, recordId={}, errorType={}",
                        tenantId,
                        orderIdLong,
                        recordId,
                        e.getClass().getSimpleName());
                throw new BizException(503, "扫描发货服务暂时不可用，请稍后重试");
            } catch (Exception e) {
                failed++;
                log.warn("扫描发货执行失败, tenantId={}, orderId={}, recordId={}, errorType={}", tenantId, orderIdLong, recordId, e.getClass().getSimpleName());
            }
        }

        return Result.ok(Map.of("scanned", created, "executed", executed, "failed", failed,
                "message", "扫描完成，创建 " + created + " 个待发货任务，成功发货 " + executed + " 个，失败 " + failed + " 个"));
    }

    private Long requireTenant() {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        return tenantId;
    }

    private int countOrZero(Integer value) {
        return value == null ? 0 : value;
    }

    private Long positiveId(Object value, String field) {
        try {
            long parsed = value instanceof Number number
                    ? new BigDecimal(String.valueOf(number)).longValueExact()
                    : Long.parseLong(String.valueOf(value));
            if (parsed <= 0) throw new NumberFormatException("non-positive");
            return parsed;
        } catch (Exception e) {
            throw new BizException(400, field + " 必须为正整数");
        }
    }

    private String stringValue(Object value, String field) {
        if (value instanceof String text) return text;
        throw new BizException(400, field + " 必须为字符串");
    }
}
