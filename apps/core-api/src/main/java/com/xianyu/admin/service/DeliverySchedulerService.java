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
 * 5. 兜底补发货 300s → autoReplenishStuckDeliveries 复活卡死/死信记录（见下）
 *
 * 付款后发货：三条路径殊途同归到 /internal/orders/deliver，经过四重锁检查后取卡发货
 *
 * 兜底补发货（autoReplenishStuckDeliveries）覆盖的两类异常：
 *   a) 处理中卡死：status=1 超 5 分钟未更新（服务崩溃/JVM 异常），无人重置
 *   b) 死信复活：status=3 AND retry_count>=5，但订单仍待发货、未取消，距上次失败 >1 小时
 * 两种场景都需通过"订单未取消 + 配置仍启用 + 货源仍可用 + 声明已确认"四重校验才会补发，
 * 由 processPendingDeliveries 接力执行实际发货。
 */
@Service
public class DeliverySchedulerService {
    private static final Logger log = LoggerFactory.getLogger(DeliverySchedulerService.class);

    private final DeliveryExecutionService executionService;
    private final JdbcTemplate jdbcTemplate;
    private final AutomationClient automationClient;
    private final DeliveryStatementCheckService statementCheckService;

    public DeliverySchedulerService(DeliveryExecutionService executionService, JdbcTemplate jdbcTemplate,
                                    AutomationClient automationClient,
                                    DeliveryStatementCheckService statementCheckService) {
        this.executionService = executionService;
        this.jdbcTemplate = jdbcTemplate;
        this.automationClient = automationClient;
        this.statementCheckService = statementCheckService;
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
     *
     * 重复发货防护（事故级修复）：
     * - 排除已有 delivery_content 的记录：这些记录已经发送过卡密/文本内容，
     *   重置后会被 executeDelivery 的补发逻辑处理（重发首次内容而非新卡密）。
     *   但为避免重复发送，这些记录只在 autoReplenishStuckDeliveries 中按更长的退避时间处理。
     * - 排除该订单已有 status=2 成功记录的情况：避免对已成功发货的订单重复发货。
     * 重置后由 processPendingDeliveries（30s 间隔）自动拾取并重试执行。
     */
    @Scheduled(fixedRate = 60000)
    public void retryFailedDeliveries() {
        try {
            // 只重置没有 delivery_content 的失败记录（未发送过内容的记录可以安全重试）
            // 已有 delivery_content 的记录由 autoReplenishStuckDeliveries 按 1 小时退避处理
            int reset = jdbcTemplate.update(
                    "UPDATE delivery_record SET status=0, delivery_status='pending', updated_time=NOW() " +
                            "WHERE deleted=0 AND status=3 AND retry_count < 5 " +
                            "AND updated_time < DATE_SUB(NOW(), INTERVAL 60 SECOND) " +
                            "AND (delivery_content IS NULL OR delivery_content='') " +
                            "AND fail_reason NOT LIKE '%未配置自动发货规则%' " +
                            "AND fail_reason NOT LIKE '%未配置发货规则%' " +
                            "AND fail_reason NOT LIKE '%等待买家确认发货声明%' " +
                            "AND order_id NOT IN (" +
                            "  SELECT order_id FROM (" +
                            "    SELECT order_id FROM delivery_record " +
                            "    WHERE deleted=0 AND status=2 AND order_id IS NOT NULL" +
                            "  ) AS successful_orders" +
                            ")");
            if (reset > 0) {
                log.info("自动重发: 重置 {} 个失败发货记录为待处理（将在下个周期重试）", reset);
            }
        } catch (Exception e) {
            log.error("自动重发扫描异常, errorType={}", e.getClass().getSimpleName());
        }
    }

    /**
     * 兜底补发货：每 5 分钟扫描一次卡死/死信的发货记录，复活后由 processPendingDeliveries 接力执行。
     *
     * 覆盖两类现有机制无法处理的异常：
     * 1) 处理中卡死（status=1 超 5 分钟未更新）：retryFailedDeliveries 只扫 status=3，
     *    若 JVM 崩溃/网络中断导致记录卡在 status=1，会永久滞留。此处兜底重置。
     * 2) 死信复活（status=3 AND retry_count>=5）：retryFailedDeliveries 因 retry_count<5 限制会跳过，
     *    若订单仍待发货且未取消，每小时给一次"重新出发"的机会。
     *
     * 四重前置校验（任一不通过则跳过，不补发）：
     *   - 订单未取消：order_status IN (1,2)（≠5 已关闭/退款）
     *   - 配置仍启用：商品 delivery_goods_config 仍存在且 payDelivery.enabled=1
     *   - 货源仍可用：text 模式 source 存在；card 模式 group 有 status=0 库存
     *   - 声明已确认：声明开启时必须有 confirmed 会话
     *
     * 重复发货防护（事故级修复）：
     *   - 排除已有 status=2 成功记录的订单：避免对已成功发货的订单重复补发
     *   - 已有 delivery_content 的记录：由 executeDelivery 补发逻辑重发首次内容（不认领新卡密）
     *
     * 退避：
     *   - 处理中卡死：保留 retry_count（避免无限重试），仅重置 status=0
     *   - 死信复活：重置 retry_count=0（给一次新机会），要求 updated_time < NOW() - 1 小时
     *   - 卡死记录若持锁卡密（card_item_id 非空且卡密状态=1），先释放卡密再重置
     */
    @Scheduled(fixedRate = 300000, initialDelay = 120000)
    public void autoReplenishStuckDeliveries() {
        // 一次查询捞取两类候选记录，避免多次扫表
        // 排除已有 status=2 成功记录的订单（重复发货防护）
        String sql =
                "SELECT dr.id AS record_id, dr.tenant_id, dr.account_id, dr.order_id, dr.status, " +
                "dr.retry_count, dr.fail_reason, dr.delivery_mode, dr.card_item_id, dr.delivery_timing, " +
                "dr.delivery_content, " +
                "dr.updated_time AS record_updated, " +
                "o.order_status, o.external_order_id, o.account_id AS order_account_id, " +
                "oi.goods_id AS item_goods_id, oi.external_goods_id AS item_external_goods_id " +
                "FROM delivery_record dr " +
                "JOIN xianyu_trade_order o ON o.id = dr.order_id AND o.deleted = 0 " +
                "LEFT JOIN xianyu_trade_order_item oi ON oi.order_id = dr.order_id AND oi.deleted = 0 " +
                "WHERE dr.deleted = 0 AND dr.tenant_id IS NOT NULL " +
                // 重复发货防护：排除已有 status=2 成功记录的订单
                "AND NOT EXISTS (" +
                "  SELECT 1 FROM delivery_record dr2 " +
                "  WHERE dr2.tenant_id=dr.tenant_id AND dr2.order_id=dr.order_id " +
                "  AND dr2.deleted=0 AND dr2.status=2 AND dr2.id<>dr.id" +
                ") " +
                "AND ( " +
                // 1) 处理中卡死：status=1 超 5 分钟未更新
                "  (dr.status = 1 AND dr.updated_time < DATE_SUB(NOW(), INTERVAL 5 MINUTE)) " +
                "  OR " +
                // 2) 死信复活：status=3 AND retry_count>=5，距上次失败 >1 小时
                "  (dr.status = 3 AND dr.retry_count >= 5 " +
                "   AND dr.updated_time < DATE_SUB(NOW(), INTERVAL 1 HOUR) " +
                "   AND dr.fail_reason NOT LIKE '%未配置自动发货规则%' " +
                "   AND dr.fail_reason NOT LIKE '%未配置发货规则%' " +
                "   AND dr.fail_reason NOT LIKE '%等待买家确认发货声明%' " +
                "   AND dr.fail_reason NOT LIKE '%商品未配置%' " +
                "   AND dr.fail_reason NOT LIKE '%卡密库存不足%') " +
                ") " +
                "ORDER BY dr.updated_time ASC LIMIT 50";

        List<Map<String, Object>> candidates;
        try {
            candidates = jdbcTemplate.queryForList(sql);
        } catch (Exception e) {
            log.warn("兜底补发货扫描查询失败, errorType={}", e.getClass().getSimpleName());
            return;
        }
        if (candidates == null || candidates.isEmpty()) {
            return;
        }

        int stuckReset = 0;
        int deadRevived = 0;
        int skipped = 0;
        for (Map<String, Object> row : candidates) {
            try {
                int status = ((Number) row.get("status")).intValue();
                Long recordId = ((Number) row.get("record_id")).longValue();
                Long tenantId = ((Number) row.get("tenant_id")).longValue();
                Long orderId = toLongOrNull(row.get("order_id"));
                Long accountId = row.get("order_account_id") == null
                        ? toLongOrNull(row.get("account_id"))
                        : toLongOrNull(row.get("order_account_id"));

                // 1) 订单未取消校验：order_status 必须仍是待发货（1=已付款 / 2=待发货）
                //    order_status=5（已关闭/退款）即"用户取消"信号，跳过补发
                Object orderStatusObj = row.get("order_status");
                if (orderStatusObj == null) {
                    skipped++;
                    continue;
                }
                int orderStatus = ((Number) orderStatusObj).intValue();
                if (orderStatus != 1 && orderStatus != 2) {
                    skipped++;
                    continue;
                }

                // 2) 商品配置仍启用 + 货源仍可用校验
                Long itemGoodsId = toLongOrNull(row.get("item_goods_id"));
                String itemExternalGoodsId = row.get("item_external_goods_id") == null ? null
                        : String.valueOf(row.get("item_external_goods_id"));
                ReplenishReadiness readiness = checkReplenishReadiness(
                        tenantId, itemGoodsId, itemExternalGoodsId);
                if (!readiness.ready) {
                    skipped++;
                    continue;
                }

                // 3) 发货声明校验（声明开启时必须有 confirmed 会话）
                String externalOrderId = row.get("external_order_id") == null ? null
                        : String.valueOf(row.get("external_order_id"));
                if (!"after_statement_confirm".equals(String.valueOf(row.get("delivery_timing")))
                        && externalOrderId != null && !externalOrderId.isBlank()
                        && !statementCheckService.canDeliverAfterStatementCheck(
                                tenantId, accountId, externalOrderId)) {
                    log.info("兜底补发货跳过：声明未确认 tenantId={} orderId={} extOrderId={}",
                            tenantId, orderId, externalOrderId);
                    skipped++;
                    continue;
                }

                // 4) 处理中卡死场景：若持锁卡密，先释放避免卡密永久占用
                Long cardItemId = toLongOrNull(row.get("card_item_id"));
                if (cardItemId != null) {
                    releaseStuckClaimedCard(tenantId, cardItemId);
                }

                // 5) 重置状态，由 processPendingDeliveries 接力执行
                if (status == 1) {
                    // 处理中卡死：保留 retry_count，仅重置 status
                    jdbcTemplate.update(
                            "UPDATE delivery_record SET status=0, delivery_status='pending', " +
                                    "error_message=NULL, fail_reason=NULL, updated_time=NOW() " +
                                    "WHERE id=? AND tenant_id=? AND deleted=0",
                            recordId, tenantId);
                    stuckReset++;
                    log.info("兜底补发货：重置卡死记录 recordId={} tenantId={} orderId={}",
                            recordId, tenantId, orderId);
                } else {
                    // 死信复活：重置 retry_count 给一次新机会
                    jdbcTemplate.update(
                            "UPDATE delivery_record SET status=0, delivery_status='pending', " +
                                    "retry_count=0, error_message=NULL, fail_reason=NULL, updated_time=NOW() " +
                                    "WHERE id=? AND tenant_id=? AND deleted=0",
                            recordId, tenantId);
                    deadRevived++;
                    log.info("兜底补发货：复活死信记录 recordId={} tenantId={} orderId={} (retry_count 已重置)",
                            recordId, tenantId, orderId);
                }
            } catch (Exception e) {
                log.warn("兜底补发货行处理异常 recordId={} errorType={} msg={}",
                        row.get("record_id"), e.getClass().getSimpleName(), e.getMessage());
                skipped++;
            }
        }
        if (stuckReset > 0 || deadRevived > 0) {
            log.info("兜底补发货扫描完成: 卡死重置 {} 个, 死信复活 {} 个, 跳过 {} 个",
                    stuckReset, deadRevived, skipped);
        }
    }

    /**
     * 释放卡死记录持有的卡密（仅当卡密仍处于已认领状态 status=1 时）
     */
    private void releaseStuckClaimedCard(Long tenantId, Long cardItemId) {
        try {
            int released = jdbcTemplate.update(
                    "UPDATE card_item SET status=0, is_used=0, used_order_id=NULL, used_by_order_id=NULL, " +
                            "used_time=NULL, updated_time=NOW() " +
                            "WHERE id=? AND tenant_id=? AND deleted=0 AND status=1",
                    cardItemId, tenantId);
            if (released > 0) {
                log.info("兜底补发货：释放卡死持锁卡密 cardItemId={} tenantId={}", cardItemId, tenantId);
            }
        } catch (Exception e) {
            log.warn("释放卡死卡密失败 cardItemId={} tenantId={} errorType={}",
                    cardItemId, tenantId, e.getClass().getSimpleName());
        }
    }

    /**
     * 兜底补发货行前校验：商品配置仍启用 + 货源仍可用
     * 返回 readiness.ready=true 才允许补发，否则跳过
     */
    private ReplenishReadiness checkReplenishReadiness(Long tenantId, Long itemGoodsId, String itemExternalGoodsId) {
        // 1) 解析内部 goodsId（兼容 oi.goods_id 存储闲鱼 external_goods_id 的情况）
        Long internalGoodsId = resolveInternalGoodsIdForReplenish(tenantId, itemGoodsId, itemExternalGoodsId);
        if (internalGoodsId == null) {
            return ReplenishReadiness.notReady("商品未匹配到内部 goodsId");
        }

        // 2) 读取商品 payDelivery 配置
        Map<String, Object> config;
        try {
            config = jdbcTemplate.queryForMap(
                    "SELECT config_json FROM delivery_goods_config " +
                            "WHERE tenant_id=? AND goods_id=? AND deleted=0 LIMIT 1",
                    tenantId, internalGoodsId);
        } catch (Exception e) {
            return ReplenishReadiness.notReady("商品发货配置已删除");
        }
        String configJson = config.get("config_json") == null ? null : String.valueOf(config.get("config_json"));
        if (configJson == null || configJson.isBlank()) {
            return ReplenishReadiness.notReady("商品发货配置为空");
        }

        // 3) 解析 JSON 中 payDelivery.enabled 和货源字段
        //    使用轻量字符串匹配，避免引入 Jackson 依赖
        if (!configJson.contains("\"payDelivery\"")) {
            return ReplenishReadiness.notReady("缺少 payDelivery 配置");
        }
        if (!configJson.contains("\"enabled\":1") && !configJson.contains("\"enabled\": 1")) {
            return ReplenishReadiness.notReady("payDelivery 已禁用");
        }

        // 4) 货源可用性校验
        if (configJson.contains("\"mode\":\"card\"") || configJson.contains("\"mode\": \"card\"")) {
            // 卡密模式：解析 cardGroupId，校验分组仍有未使用卡密
            Long cardGroupId = extractLongAfter(configJson, "\"cardGroupId\":");
            if (cardGroupId == null) {
                return ReplenishReadiness.notReady("卡密模式未绑定分组");
            }
            Integer available;
            try {
                available = jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM card_item " +
                                "WHERE tenant_id=? AND group_id=? AND deleted=0 AND status=0",
                        Integer.class, tenantId, cardGroupId);
            } catch (Exception e) {
                return ReplenishReadiness.notReady("卡密库存查询失败");
            }
            if (available == null || available <= 0) {
                return ReplenishReadiness.notReady("卡密库存为 0");
            }
        } else if (configJson.contains("\"mode\":\"text\"") || configJson.contains("\"mode\": \"text\"")) {
            // 文本模式：解析 sourceId，校验文本货源仍存在
            Long sourceId = extractLongAfter(configJson, "\"sourceId\":");
            if (sourceId != null) {
                Integer exists;
                try {
                    exists = jdbcTemplate.queryForObject(
                            "SELECT COUNT(*) FROM delivery_text_source " +
                                    "WHERE tenant_id=? AND id=? AND deleted=0",
                            Integer.class, tenantId, sourceId);
                } catch (Exception e) {
                    return ReplenishReadiness.notReady("文本货源查询失败");
                }
                if (exists == null || exists <= 0) {
                    return ReplenishReadiness.notReady("文本货源已删除");
                }
            }
            // sourceId 为空时，content 可能为内联模板，视为可用
        }
        return ReplenishReadiness.ready();
    }

    /**
     * 解析内部 goodsId：兼容 oi.goods_id 存储闲鱼 external_goods_id 的历史行为
     */
    private Long resolveInternalGoodsIdForReplenish(Long tenantId, Long itemGoodsId, String itemExternalGoodsId) {
        if (itemGoodsId == null && (itemExternalGoodsId == null || itemExternalGoodsId.isBlank())) {
            return null;
        }
        // 1) 先按主键查 xianyu_goods.id
        if (itemGoodsId != null) {
            try {
                Long direct = jdbcTemplate.queryForObject(
                        "SELECT id FROM xianyu_goods WHERE tenant_id=? AND id=? AND deleted=0 LIMIT 1",
                        Long.class, tenantId, itemGoodsId);
                if (direct != null) {
                    return direct;
                }
            } catch (Exception ignored) {
                // fall through to external_goods_id lookup
            }
        }
        // 2) 用 oi.goods_id 当作 external_goods_id 查
        if (itemGoodsId != null) {
            try {
                Long byExternal = jdbcTemplate.queryForObject(
                        "SELECT id FROM xianyu_goods WHERE tenant_id=? AND external_goods_id=? AND deleted=0 LIMIT 1",
                        Long.class, tenantId, String.valueOf(itemGoodsId));
                if (byExternal != null) {
                    return byExternal;
                }
            } catch (Exception ignored) {
                // fall through
            }
        }
        // 3) 用 oi.external_goods_id 字段查
        if (itemExternalGoodsId != null && !itemExternalGoodsId.isBlank()) {
            try {
                return jdbcTemplate.queryForObject(
                        "SELECT id FROM xianyu_goods WHERE tenant_id=? AND external_goods_id=? AND deleted=0 LIMIT 1",
                        Long.class, tenantId, itemExternalGoodsId);
            } catch (Exception ignored) {
                return null;
            }
        }
        return null;
    }

    /**
     * 从 JSON 字符串中提取 "key":value 后的 long 值（轻量解析，避免引入 Jackson）
     */
    private Long extractLongAfter(String json, String key) {
        if (json == null || key == null) return null;
        int idx = json.indexOf(key);
        if (idx < 0) return null;
        int start = idx + key.length();
        // 跳过空白
        while (start < json.length() && Character.isWhitespace(json.charAt(start))) start++;
        if (start >= json.length()) return null;
        int end = start;
        // 数字（含负号）
        if (json.charAt(start) == '-') end++;
        while (end < json.length() && Character.isDigit(json.charAt(end))) end++;
        if (end == start || (json.charAt(start) == '-' && end == start + 1)) return null;
        try {
            return Long.parseLong(json.substring(start, end));
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * 补发货行前校验结果
     */
    private static final class ReplenishReadiness {
        final boolean ready;
        final String reason;
        private ReplenishReadiness(boolean ready, String reason) {
            this.ready = ready;
            this.reason = reason;
        }
        static ReplenishReadiness ready() { return new ReplenishReadiness(true, null); }
        static ReplenishReadiness notReady(String reason) { return new ReplenishReadiness(false, reason); }
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
        boolean statementEnabled = statementCheckService.isStatementEnabled(tenantId);
        for (Map<String, Object> order : orders) {
            Object orderId = order.get("order_id");
            Long orderIdLong = orderId instanceof Number ? ((Number) orderId).longValue() : Long.parseLong(orderId.toString());
            // 发货声明开启时，Java 定时任务不直接创建发货记录：
            // 由 Python WS 路径收到付款消息后发送声明、等待买家确认，确认后才触发发货。
            // 这里跳过未确认声明的订单，避免 Java 路径绕过声明流程直接发货。
            if (statementEnabled) {
                Long accountId = order.get("account_id") instanceof Number
                        ? ((Number) order.get("account_id")).longValue() : null;
                String externalOrderId = queryExternalOrderId(tenantId, orderIdLong);
                if (externalOrderId != null
                        && !statementCheckService.canDeliverAfterStatementCheck(
                                tenantId, accountId, externalOrderId)) {
                    log.info("声明开启且未确认，Java 扫描跳过创建发货记录 tenantId={} accountId={} orderId={}",
                            tenantId, accountId, externalOrderId);
                    continue;
                }
            }
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

    /**
     * 查询订单的 external_order_id（闲鱼订单号），用于声明会话匹配
     */
    private String queryExternalOrderId(Long tenantId, Long orderId) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT external_order_id FROM xianyu_trade_order WHERE id=? AND tenant_id=? AND deleted=0 LIMIT 1",
                    String.class, orderId, tenantId);
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * 安全转换为 Long，兼容 Number、String（VARCHAR 列）与 null。
     * 用于 V1.35 后 delivery_record.order_id 等 VARCHAR 列的类型兼容。
     */
    private static Long toLongOrNull(Object v) {
        if (v == null) return null;
        if (v instanceof Number) return ((Number) v).longValue();
        try {
            return Long.parseLong(String.valueOf(v).trim());
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
