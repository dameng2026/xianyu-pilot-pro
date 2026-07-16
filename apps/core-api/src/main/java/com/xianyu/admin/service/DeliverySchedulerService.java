package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 自动发货调度任务
 * 定时扫描并处理待发货记录，以及扫描新订单创建设货记录
 *
 * 新订单监测机制：
 * 1. WebSocket 实时推送 → ws_delivery_handler 立即触发（毫秒级）
 * 2. 定时拉取 60s → autoScanPendingOrders 扫描本地库创建发货记录
 * 3. 定时拉取 600s → autoSyncOrdersFromXianyu 从闲鱼 MTOP 拉取最新订单入库
 * 4. 超时检测 60s → 由 autoScanPendingOrders 顺带覆盖（订单状态已落库）
 *
 * 付款后发货：三条路径殊途同归到 /internal/orders/deliver，经过四重锁检查后取卡发货
 */
@Service
public class DeliverySchedulerService {
    private static final Logger log = LoggerFactory.getLogger(DeliverySchedulerService.class);

    private final DeliveryExecutionService executionService;
    private final JdbcTemplate jdbcTemplate;
    private final AutomationClient automationClient;

    public DeliverySchedulerService(DeliveryExecutionService executionService, JdbcTemplate jdbcTemplate,
                                    AutomationClient automationClient) {
        this.executionService = executionService;
        this.jdbcTemplate = jdbcTemplate;
        this.automationClient = automationClient;
    }

    /**
     * 每 30 秒扫描一次待发货记录并执行发货
     */
    @Scheduled(fixedRate = 30000)
    public void processPendingDeliveries() {
        try {
            int processed = executionService.processPendingDeliveries();
            if (processed > 0) {
                log.info("定时发货扫描: 处理了 {} 个待发货订单", processed);
            }
        } catch (Exception e) {
            log.error("定时发货扫描异常, errorType={}", e.getClass().getSimpleName());
        }
    }

    /**
     * 每 60 秒扫描失败的发货记录，重置为待处理以触发自动重发。
     * 限制：retry_count < 5，且距上次更新 > 60 秒（退避，避免立即重试导致雪崩）。
     * 排除永久性错误（未配置发货规则等），避免无效重试堵塞队列。
     * 重置后由 processPendingDeliveries（30s 间隔）自动拾取并重试执行。
     */
    @Scheduled(fixedRate = 60000)
    public void retryFailedDeliveries() {
        try {
            int reset = jdbcTemplate.update(
                    "UPDATE delivery_record SET status=0, delivery_status='pending', updated_time=NOW() " +
                            "WHERE deleted=0 AND status=3 AND retry_count < 5 " +
                            "AND updated_time < DATE_SUB(NOW(), INTERVAL 60 SECOND) " +
                            "AND fail_reason NOT LIKE '%未配置自动发货规则%' " +
                            "AND fail_reason NOT LIKE '%未配置发货规则%'");
            if (reset > 0) {
                log.info("自动重发: 重置 {} 个失败发货记录为待处理（将在下个周期重试）", reset);
            }
        } catch (Exception e) {
            log.error("自动重发扫描异常, errorType={}", e.getClass().getSimpleName());
        }
    }

    /**
     * 每 60 秒扫描一次待发货订单，自动创建发货记录
     * 覆盖所有有自动发货配置的租户
     */
    @Scheduled(fixedRate = 60000)
    public void autoScanPendingOrders() {
        try {
            // 获取所有有自动发货配置的租户
            List<Long> tenantIds = jdbcTemplate.queryForList(
                    "SELECT DISTINCT tenant_id FROM delivery_goods_config WHERE deleted=0 AND config_json IS NOT NULL AND config_json!=''",
                    Long.class);

            for (Long tenantId : tenantIds) {
                try {
                    scanAndCreateRecords(tenantId);
                } catch (Exception e) {
                    log.warn("租户 {} 自动扫描发货时异常, errorType={}", tenantId, e.getClass().getSimpleName());
                }
            }
        } catch (Exception e) {
            log.error("自动扫描待发货订单异常, errorType={}", e.getClass().getSimpleName());
        }
    }

    /**
     * 为指定租户扫描待发货订单，创建 delivery_record
     */
    private void scanAndCreateRecords(Long tenantId) {
        // 注意：oi.goods_id 可能存储闲鱼 external_goods_id（Python sync_sold_orders 历史行为），
        // 因此 JOIN 条件需同时匹配 g.id=oi.goods_id 或 g.external_goods_id=oi.goods_id
        String sql = "SELECT o.id AS order_id, MAX(oi.goods_id) AS goods_id, MAX(g.account_id) AS account_id " +
                "FROM xianyu_trade_order o " +
                "JOIN xianyu_trade_order_item oi ON oi.order_id=o.id AND oi.deleted=0 " +
                "JOIN xianyu_goods g ON g.deleted=0 AND (g.id=oi.goods_id OR g.external_goods_id=CAST(oi.goods_id AS CHAR)) " +
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
            return; // 表可能还不存在
        }

        int created = 0;
        // 主 SQL 已通过 NOT IN 排除已存在 delivery_record 的订单，此处无需重复 COUNT 校验
        List<Object[]> batchArgs = new ArrayList<>();
        for (Map<String, Object> order : orders) {
            Object orderId = order.get("order_id");
            Long orderIdLong = orderId instanceof Number ? ((Number) orderId).longValue() : Long.parseLong(orderId.toString());
            batchArgs.add(new Object[]{tenantId, order.get("account_id"), orderIdLong});
        }
        if (!batchArgs.isEmpty()) {
            try {
                int[] counts = jdbcTemplate.batchUpdate(
                        "INSERT INTO delivery_record(tenant_id, account_id, order_id, delivery_type, delivery_timing, status, retry_count, created_time, updated_time, deleted) " +
                                "VALUES(?,?,?,'auto','after_payment',0,0,NOW(),NOW(),0)",
                        batchArgs);
                for (int c : counts) if (c > 0) created++;
            } catch (Exception e) {
                log.warn("批量创建待发货记录失败 (tenantId={}), errorType={}", tenantId, e.getClass().getSimpleName());
            }
        }

        if (created > 0) {
            log.info("自动扫描创建 {} 个待发货记录 (tenantId={})", created, tenantId);
        }
    }

    /**
     * 每 600 秒（10 分钟）从闲鱼 MTOP 拉取最新订单入库
     * 参考垃圾箱项目 fetch_orders_task（ALL, 600s）实现。
     *
     * 覆盖所有有自动发货配置的租户，对每个有效账号调用 Python 端
     * /api/internal/orders/sync-sold 从闲鱼 MTOP 主动拉取已售订单。
     * 解决"订单管理页面无法同步最新数据"问题：用户无需手动点击同步按钮。
     */
    @Scheduled(fixedRate = 600000, initialDelay = 60000)
    public void autoSyncOrdersFromXianyu() {
        List<Long> tenantIds;
        try {
            tenantIds = jdbcTemplate.queryForList(
                    "SELECT DISTINCT tenant_id FROM delivery_goods_config WHERE deleted=0 AND config_json IS NOT NULL AND config_json!=''",
                    Long.class);
        } catch (Exception e) {
            log.debug("查询自动发货配置租户列表失败, errorType={}", e.getClass().getSimpleName());
            return;
        }
        if (tenantIds == null || tenantIds.isEmpty()) {
            return;
        }

        int totalSynced = 0;
        for (Long tenantId : tenantIds) {
            try {
                totalSynced += syncOrdersForTenant(tenantId);
            } catch (Exception e) {
                log.warn("租户 {} 自动同步订单异常, errorType={}", tenantId, e.getClass().getSimpleName());
            }
        }
        if (totalSynced > 0) {
            log.info("定时同步闲鱼订单完成: 共同步 {} 个账号的订单", totalSynced);
        }
    }

    /**
     * 同步指定租户下所有有效账号的订单
     * 只同步 cookie_status=1（已登录）且 status=1（正常）的账号，避免无效 API 调用
     */
    private int syncOrdersForTenant(Long tenantId) {
        List<Map<String, Object>> accounts;
        try {
            accounts = jdbcTemplate.queryForList(
                    "SELECT id FROM xianyu_account WHERE tenant_id=? AND deleted=0 AND status=1 AND cookie_status=1",
                    tenantId);
        } catch (Exception e) {
            log.debug("查询租户 {} 有效账号失败, errorType={}", tenantId, e.getClass().getSimpleName());
            return 0;
        }
        if (accounts == null || accounts.isEmpty()) {
            return 0;
        }

        int synced = 0;
        for (Map<String, Object> account : accounts) {
            Object accountIdObj = account.get("id");
            Long accountId = accountIdObj instanceof Number ? ((Number) accountIdObj).longValue() : null;
            if (accountId == null) {
                continue;
            }
            try {
                LinkedHashMap<String, Object> payload = new LinkedHashMap<>();
                payload.put("tenantId", tenantId);
                payload.put("accountId", accountId);
                payload.put("externalOrderId", null);
                automationClient.postInternalForData("/api/internal/orders/sync-sold", payload, tenantId);
                synced++;
            } catch (Exception e) {
                log.debug("同步账号 {} 订单失败 (tenantId={}), errorType={}",
                        accountId, tenantId, e.getClass().getSimpleName());
            }
        }
        return synced;
    }
}
