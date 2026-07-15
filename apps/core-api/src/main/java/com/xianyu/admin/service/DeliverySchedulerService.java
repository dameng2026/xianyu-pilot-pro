package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 自动发货调度任务
 * 定时扫描并处理待发货记录，以及扫描新订单创建设货记录
 */
@Service
public class DeliverySchedulerService {
    private static final Logger log = LoggerFactory.getLogger(DeliverySchedulerService.class);

    private final DeliveryExecutionService executionService;
    private final JdbcTemplate jdbcTemplate;

    public DeliverySchedulerService(DeliveryExecutionService executionService, JdbcTemplate jdbcTemplate) {
        this.executionService = executionService;
        this.jdbcTemplate = jdbcTemplate;
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
}
