package com.xianyu.admin.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.DashboardSummaryVO;
import com.xianyu.admin.dto.SalesTrendVO;
import com.xianyu.admin.service.AdminModuleService;
import com.xianyu.admin.service.AiProviderEndpointPolicy;
import com.xianyu.admin.service.DashboardService;
import com.xianyu.admin.service.ModuleCatalog;
import com.xianyu.admin.service.ImageGenerationService;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.TenantContext;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

@RestController
@RequestMapping("/admin-api/admin")
public class AdminModuleController {
    private static final Logger log = LoggerFactory.getLogger(AdminModuleController.class);
    private static final String TODAY_ORDER_COUNT_SQL =
            "SELECT COUNT(*) FROM xianyu_trade_order " +
            "WHERE deleted=0 " +
            "AND COALESCE(create_time, created_time) >= CURDATE() " +
            "AND COALESCE(create_time, created_time) < CURDATE() + INTERVAL 1 DAY";
    private static final String TODAY_SALES_AMOUNT_SQL =
            "SELECT COALESCE(SUM(total_amount),0) FROM xianyu_trade_order " +
            "WHERE deleted=0 AND order_status IN (1,2,3,4) " +
            "AND COALESCE(pay_time, create_time, created_time) >= CURDATE() " +
            "AND COALESCE(pay_time, create_time, created_time) < CURDATE() + INTERVAL 1 DAY";
    private static final String DAILY_ORDER_TREND_SQL =
            "SELECT DATE(COALESCE(create_time, created_time)) d, COUNT(*) c " +
            "FROM xianyu_trade_order " +
            "WHERE deleted=0 " +
            "AND COALESCE(create_time, created_time) >= ? " +
            "AND COALESCE(create_time, created_time) < ? " +
            "GROUP BY DATE(COALESCE(create_time, created_time))";
    private final AdminModuleService service;
    private final DashboardService dashboardService;
    private final ImageGenerationService imageGenerationService;
    private final JdbcTemplate jdbcTemplate;
    private final AiProviderEndpointPolicy aiProviderEndpointPolicy;
    @Value("${xianyu.automation.base-url:http://localhost:12401}")
    private String automationBaseUrl;
    @Value("${xianyu.automation.crawler-base-url:http://localhost:3001}")
    private String crawlerBaseUrl;
    public AdminModuleController(AdminModuleService service, DashboardService dashboardService,
                                  ImageGenerationService imageGenerationService, JdbcTemplate jdbcTemplate,
                                  AiProviderEndpointPolicy aiProviderEndpointPolicy) {
        this.service = service;
        this.dashboardService = dashboardService;
        this.imageGenerationService = imageGenerationService;
        this.jdbcTemplate = jdbcTemplate;
        this.aiProviderEndpointPolicy = aiProviderEndpointPolicy;
    }

    @GetMapping("/dashboard/summary")
    public Result<Map<String, Object>> summary() {
        Map<String, Object> result = new LinkedHashMap<>();
        List<Map<String, Object>> cards = new ArrayList<>();
        Long tenantId = TenantContext.getCurrentTenantId();
        try {
            if (tenantId != null) {
                DashboardSummaryVO vo = dashboardService.summary(tenantId);
                cards.add(buildCard("accountCount", "账号数", String.valueOf(vo.getAccountCount()), "user", null, null));
                cards.add(buildCard("goodsCount", "商品总数", String.valueOf(vo.getGoodsCount()), "goods", null, null));
                cards.add(buildCard("sellingGoodsCount", "在售商品", String.valueOf(vo.getSellingGoodsCount()), "shop", null, null));
                cards.add(buildCard("todayOrderCount", "今日订单", String.valueOf(vo.getTodayOrderCount()), "order", null, null));
                cards.add(buildCard("todaySalesAmount", "今日销售额", vo.getTodaySalesAmount().toString(), "money", null, null));
                cards.add(buildCard("autoReplyCount", "AI回复", String.valueOf(vo.getAutoReplyCount()), "chat", null, null));
                cards.add(buildCard("deliverySuccessCount", "发货成功", String.valueOf(vo.getDeliverySuccessCount()), "success", null, null));
                cards.add(buildCard("deliveryFailCount", "发货失败", String.valueOf(vo.getDeliveryFailCount()), "fail", null, null));
                cards.add(buildCard("pendingDeliveryCount", "待发货", String.valueOf(vo.getPendingDeliveryCount()), "pending", null, null));
            } else {
                // admin 平台管理员：tenantId 为 null 时使用全表统计
                cards.add(buildCard("accountCount", "账号数", queryCount("SELECT COUNT(*) FROM xianyu_account WHERE deleted=0"), "user", null, null));
                cards.add(buildCard("goodsCount", "商品总数", queryCount("SELECT COUNT(*) FROM xianyu_goods WHERE deleted=0"), "goods", null, null));
                cards.add(buildCard("sellingGoodsCount", "在售商品", queryCount("SELECT COUNT(*) FROM xianyu_goods WHERE deleted=0 AND status=1"), "shop", null, null));
                cards.add(buildCard("todayOrderCount", "今日订单", queryCount(TODAY_ORDER_COUNT_SQL), "order", null, null));
                cards.add(buildCard("todaySalesAmount", "今日销售额", querySum(TODAY_SALES_AMOUNT_SQL), "money", null, null));
                cards.add(buildCard("autoReplyCount", "AI回复", queryCount("SELECT COUNT(*) FROM auto_reply_log WHERE created_time >= CURDATE() AND created_time < CURDATE() + INTERVAL 1 DAY"), "chat", null, null));
                cards.add(buildCard("deliverySuccessCount", "发货成功", queryCount("SELECT COUNT(*) FROM delivery_record WHERE deleted=0 AND status=2"), "success", null, null));
                cards.add(buildCard("deliveryFailCount", "发货失败", queryCount("SELECT COUNT(*) FROM delivery_record WHERE deleted=0 AND status=3"), "fail", null, null));
                cards.add(buildCard("pendingDeliveryCount", "待发货", queryCount("SELECT COUNT(*) FROM xianyu_trade_order WHERE deleted=0 AND order_status='1'"), "pending", null, null));
            }
        } catch (Exception e) {
            throw unavailable("仪表盘摘要", e);
        }
        result.put("cards", cards);
        return Result.ok(result);
    }

    private String queryCount(String sql) {
        try {
            Long c = jdbcTemplate.queryForObject(sql, Long.class);
            if (c == null) {
                throw new BizException(503, "统计数据暂时不可用，请稍后重试");
            }
            return String.valueOf(c);
        } catch (Exception e) {
            throw unavailable("统计数据", e);
        }
    }

    private String querySum(String sql) {
        try {
            Object v = jdbcTemplate.queryForObject(sql, Object.class);
            if (v == null) {
                throw new BizException(503, "汇总数据暂时不可用，请稍后重试");
            }
            return String.valueOf(v);
        } catch (Exception e) {
            throw unavailable("汇总数据", e);
        }
    }

    @GetMapping("/menus")
    public Result<List<Map<String, Object>>> menus() {
        return Result.ok(callDependency("动态菜单", service::menus));
    }

    /**
     * 仪表盘首屏聚合端点：一次返回 summary + trend + recent-events，减少前端多次 HTTP 请求。
     * 每个子项独立 try-catch，单个数据源失败不影响整体返回。
     */
    @GetMapping("/dashboard/init")
    public Result<Map<String, Object>> dashboardInit() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("summary", safeCall("仪表盘概览", () -> summary().getData()));
        result.put("trend", safeCall("趋势统计", () -> trend(7).getData()));
        result.put("recentEvents", safeCall("最近事件", () -> service.recentEvents()));
        result.put("pendingTasks", safeCall("待办任务", () -> pendingTasks().getData()));
        result.put("realtimeStats", safeCall("实时统计", () -> realtimeStats().getData()));
        result.put("topHotGoods", safeCall("热销商品", () -> topHotGoods().getData()));
        result.put("riskDistribution", safeCall("风控分布", () -> riskDistribution().getData()));
        result.put("systemHealth", safeCall("系统健康", () -> systemHealth().getData()));
        return Result.ok(result);
    }

    /**
     * 安全调用包装：子数据源失败时返回 null 而非中断整个聚合接口
     */
    private <T> T safeCall(String name, java.util.function.Supplier<T> action) {
        try {
            return action.get();
        } catch (Exception e) {
            log.warn("dashboard/init 子项 [{}] 查询失败: {}", name, e.getMessage());
            return null;
        }
    }

    /**
     * 实时监控卡片：在线账号数 / 今日发布数 / 今日成交额 / AI 调用次数
     */
    @GetMapping("/dashboard/realtime-stats")
    public Result<Map<String, Object>> realtimeStats() {
        Map<String, Object> result = new LinkedHashMap<>();
        // 在线账号数（online_status=1）
        result.put("onlineAccounts", queryCount(
                "SELECT COUNT(*) FROM xianyu_account_runtime WHERE online_status=1"));
        // 今日发布商品数（workflow_published_goods 今日新增）
        result.put("todayPublished", queryCount(
                "SELECT COUNT(*) FROM workflow_published_goods WHERE DATE(created_time)=CURRENT_DATE()"));
        // 今日成交额
        result.put("todaySalesAmount", querySum(
                TODAY_SALES_AMOUNT_SQL));
        // 今日 AI 调用次数
        result.put("todayAiCalls", queryCount(
                "SELECT COUNT(*) FROM ai_usage_log WHERE DATE(created_time)=CURRENT_DATE()"));
        // 今日 AI 失败次数
        result.put("todayAiFailures", queryCount(
                "SELECT COUNT(*) FROM ai_usage_log WHERE DATE(created_time)=CURRENT_DATE() AND status!=1"));
        // 工作流执行中
        result.put("runningWorkflows", queryCount(
                "SELECT COUNT(*) FROM workflow_execution WHERE deleted=0 AND status IN ('queued','running')"));
        return Result.ok(result);
    }

    /**
     * Top 5 热销商品（基于 hot_goods_stat 表，按 daily_sales DESC）
     */
    @GetMapping("/dashboard/top-hot-goods")
    public Result<List<Map<String, Object>>> topHotGoods() {
        try {
            // 检查 hot_goods_stat 表是否存在
            Integer exists = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'hot_goods_stat'",
                    Integer.class);
            if (exists == null || exists == 0) {
                return Result.ok(List.of());
            }
            return Result.ok(jdbcTemplate.queryForList(
                    "SELECT h.id, h.title, h.price, h.cover_pic AS imageUrl, h.daily_sales AS sales, h.stat_date, " +
                            "COALESCE(a.account_name, a.nickname, '') AS accountName " +
                            "FROM hot_goods_stat h " +
                            "LEFT JOIN xianyu_account a ON h.account_id = a.id " +
                            "WHERE h.daily_sales >= 5 AND h.deleted = 0 " +
                            "ORDER BY h.daily_sales DESC, h.stat_date DESC LIMIT 5"));
        } catch (Exception e) {
            throw unavailable("热销商品统计", e);
        }
    }

    /**
     * 风控分布：按 risk_level 分组账号数
     */
    @GetMapping("/dashboard/risk-distribution")
    public Result<List<Map<String, Object>>> riskDistribution() {
        try {
            return Result.ok(jdbcTemplate.queryForList(
                    "SELECT risk_level, COUNT(*) AS count FROM xianyu_account WHERE deleted=0 GROUP BY risk_level ORDER BY risk_level"));
        } catch (Exception e) {
            throw unavailable("风控分布统计", e);
        }
    }

    /**
     * 系统健康状态：聚合 core-api / automation-service / crawler-service 三个服务的存活状态
     */
    @GetMapping("/dashboard/system-health")
    public Result<Map<String, Object>> systemHealth() {
        Map<String, Object> result = new LinkedHashMap<>();
        // core-api（自身，默认存活）
        Map<String, Object> coreApi = new LinkedHashMap<>();
        coreApi.put("name", "core-api");
        coreApi.put("port", 18080);
        coreApi.put("status", "up");
        coreApi.put("latencyMs", 0);
        result.put("coreApi", coreApi);
        // automation-service
        result.put("automationService", checkServiceHealth(
                "automation-service",
                healthUrl(automationBaseUrl, "/ready")
        ));
        // crawler-service
        result.put("crawlerService", checkServiceHealth(
                "crawler-service",
                healthUrl(crawlerBaseUrl, "/api/ready")
        ));
        return Result.ok(result);
    }

    private String healthUrl(String baseUrl, String path) {
        String normalized = baseUrl == null ? "" : baseUrl.trim();
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return normalized + path;
    }

    private Map<String, Object> checkServiceHealth(String name, String url) {
        Map<String, Object> svc = new LinkedHashMap<>();
        svc.put("name", name);
        long start = System.currentTimeMillis();
        try {
            java.net.http.HttpRequest req = java.net.http.HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(2))
                    .GET().build();
            java.net.http.HttpResponse<InputStream> resp = httpClient.send(
                    req, java.net.http.HttpResponse.BodyHandlers.ofInputStream());
            long latency = System.currentTimeMillis() - start;
            boolean identityMatches = false;
            if (resp.statusCode() == 200) {
                try {
                    JsonNode body = new ObjectMapper().readTree(readLimitedBody(resp));
                    identityMatches = name.equals(body.path("service").asText());
                } catch (Exception parseError) {
                    svc.put("error", "健康检查返回无法解析的服务身份");
                }
            } else {
                closeBody(resp);
            }
            svc.put("status", resp.statusCode() == 200 && identityMatches ? "up" : "degraded");
            svc.put("latencyMs", latency);
            svc.put("statusCode", resp.statusCode());
            if (resp.statusCode() == 200 && !identityMatches && !svc.containsKey("error")) {
                svc.put("error", "服务身份不匹配");
            }
        } catch (Exception e) {
            svc.put("status", "down");
            svc.put("latencyMs", System.currentTimeMillis() - start);
            svc.put("error", "健康检查请求失败");
        }
        return svc;
    }

    @GetMapping("/dashboard/trend")
    public Result<Map<String, Object>> trend(@RequestParam(defaultValue = "7") int range) {
        if (range != 7 && range != 30 && range != 90) {
            throw new BizException(400, "range 仅支持 7、30 或 90");
        }
        try {
            Long tenantId = TenantContext.getCurrentTenantId();
            if (tenantId != null) {
                SalesTrendVO vo = dashboardService.salesTrend(tenantId, range);
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("dates", vo.getDates());
                result.put("orders", vo.getOrderCount());
                result.put("delivery", vo.getDeliveryCount());
                result.put("ai", vo.getAiReplyCount());
                return Result.ok(result);
            } else {
                // admin 平台管理员：3 次 GROUP BY 查询替代 N×3 次循环，配合 idx_xto_created/idx_auto_reply_log_created 索引
                java.time.LocalDate today = java.time.LocalDate.now();
                java.time.LocalDate start = today.minusDays(range - 1L);
                java.sql.Date sqlStart = java.sql.Date.valueOf(start);
                java.sql.Date sqlEndExclusive = java.sql.Date.valueOf(today.plusDays(1));
                List<String> dates = new ArrayList<>();
                for (int i = range - 1; i >= 0; i--) dates.add(start.plusDays(range - 1 - i).toString());
                List<Long> orders = queryDailyCounts(
                        DAILY_ORDER_TREND_SQL,
                        sqlStart, sqlEndExclusive, dates);
                List<Long> delivery = queryDailyCounts(
                        "SELECT DATE(created_time) d, COUNT(*) c FROM delivery_record WHERE deleted=0 AND created_time >= ? AND created_time < ? GROUP BY DATE(created_time)",
                        sqlStart, sqlEndExclusive, dates);
                List<Long> ai = queryDailyCounts(
                        "SELECT DATE(created_time) d, COUNT(*) c FROM auto_reply_log WHERE created_time >= ? AND created_time < ? GROUP BY DATE(created_time)",
                        sqlStart, sqlEndExclusive, dates);
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("dates", dates);
                result.put("orders", orders);
                result.put("delivery", delivery);
                result.put("ai", ai);
                return Result.ok(result);
            }
        } catch (Exception e) {
            throw unavailable("仪表盘趋势", e);
        }
    }

    /**
     * 收入与 AI 成本财务统计：
     * - 收入来自 payment_order 表（status=1 已支付）的真实二维码收款流水
     * - AI 成本来自 ai_usage_log 表（status=1 成功）的 cost_cent 累计
     * - 利润 = 收入 - AI 成本（已换算为元，未扣商品成本/佣金/支付手续费）
     * - 按 range 7/30/90 天统计，前端 4 张卡片随时间范围联动
     */
    @GetMapping("/dashboard/finance")
    public Result<Map<String, Object>> finance(@RequestParam(defaultValue = "7") int range) {
        if (range != 7 && range != 30 && range != 90) {
            throw new BizException(400, "range 仅支持 7、30 或 90");
        }
        try {
            java.time.LocalDate today = java.time.LocalDate.now();
            java.time.LocalDate start = today.minusDays(range - 1L);
            java.sql.Date sqlStart = java.sql.Date.valueOf(start);
            java.sql.Date sqlEndExclusive = java.sql.Date.valueOf(today.plusDays(1));
            // 范围内总收入（payment_order.status=1 表示已支付）
            Long totalIncomeCent = queryLongOrNull(
                    "SELECT COALESCE(SUM(amount_cent),0) FROM payment_order " +
                            "WHERE deleted=0 AND status=1 " +
                            "AND COALESCE(paid_time, created_time) >= ? " +
                            "AND COALESCE(paid_time, created_time) < ?",
                    sqlStart, sqlEndExclusive);
            // 范围内 AI 成本（ai_usage_log.status=1 表示成功计费）
            Long totalAiCostCent = queryLongOrNull(
                    "SELECT COALESCE(SUM(cost_cent),0) FROM ai_usage_log " +
                            "WHERE deleted=0 AND status=1 " +
                            "AND created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            // 范围内 Token 消耗
            Long totalChargeTokens = queryLongOrNull(
                    "SELECT COALESCE(SUM(charge_tokens),0) FROM ai_usage_log " +
                            "WHERE deleted=0 AND status=1 " +
                            "AND created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            // 今日收入（供 KPI 卡片使用，与范围无关）
            Long todayIncomeCent = queryLongOrNull(
                    "SELECT COALESCE(SUM(amount_cent),0) FROM payment_order " +
                            "WHERE deleted=0 AND status=1 " +
                            "AND COALESCE(paid_time, created_time) >= CURDATE() " +
                            "AND COALESCE(paid_time, created_time) < CURDATE() + INTERVAL 1 DAY");
            // 今日 AI 成本（供 KPI 卡片使用，与范围无关）
            Long todayAiCostCent = queryLongOrNull(
                    "SELECT COALESCE(SUM(cost_cent),0) FROM ai_usage_log " +
                            "WHERE deleted=0 AND status=1 " +
                            "AND created_time >= CURDATE() " +
                            "AND created_time < CURDATE() + INTERVAL 1 DAY");
            // 范围内每日收入趋势
            List<String> dates = new ArrayList<>();
            for (int i = range - 1; i >= 0; i--) dates.add(start.plusDays(range - 1 - i).toString());
            Map<String, Long> incomeMap = new LinkedHashMap<>();
            try {
                jdbcTemplate.query(
                        "SELECT DATE(COALESCE(paid_time, created_time)) d, COALESCE(SUM(amount_cent),0) c " +
                                "FROM payment_order WHERE deleted=0 AND status=1 " +
                                "AND COALESCE(paid_time, created_time) >= ? " +
                                "AND COALESCE(paid_time, created_time) < ? " +
                                "GROUP BY DATE(COALESCE(paid_time, created_time))",
                        rs -> {
                            String d = String.valueOf(rs.getDate(1).toLocalDate());
                            incomeMap.put(d, rs.getLong(2));
                        },
                        sqlStart, sqlEndExclusive);
            } catch (Exception ignore) {
                // 收入趋势查询失败不影响整体返回
            }
            List<Long> dailyIncome = new ArrayList<>(dates.size());
            for (String d : dates) dailyIncome.add(incomeMap.getOrDefault(d, 0L));

            long incomeCent = totalIncomeCent == null ? 0 : totalIncomeCent;
            long costCent = totalAiCostCent == null ? 0 : totalAiCostCent;
            long profitCent = incomeCent - costCent;
            Integer marginPercent = incomeCent > 0
                    ? (int) Math.round(((double) profitCent / incomeCent) * 100)
                    : null;
            long todayIncome = todayIncomeCent == null ? 0 : todayIncomeCent;
            long todayCost = todayAiCostCent == null ? 0 : todayAiCostCent;
            long todayProfit = todayIncome - todayCost;

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("range", range);
            result.put("dates", dates);
            result.put("totalIncomeCent", incomeCent);
            result.put("totalAiCostCent", costCent);
            result.put("totalProfitCent", profitCent);
            result.put("totalChargeTokens", totalChargeTokens == null ? 0 : totalChargeTokens);
            result.put("marginPercent", marginPercent);
            result.put("dailyIncome", dailyIncome);
            result.put("todayIncomeCent", todayIncome);
            result.put("todayAiCostCent", todayCost);
            result.put("todayProfitCent", todayProfit);
            return Result.ok(result);
        } catch (Exception e) {
            throw unavailable("仪表盘财务统计", e);
        }
    }

    /**
     * 通知投递统计：替换原"数据暂不可用"占位面板，从 notification_delivery_log 真实聚合
     */
    @GetMapping("/dashboard/notify-stats")
    public Result<Map<String, Object>> notifyStats(@RequestParam(defaultValue = "7") int range) {
        if (range != 7 && range != 30 && range != 90) {
            throw new BizException(400, "range 仅支持 7、30 或 90");
        }
        try {
            java.time.LocalDate today = java.time.LocalDate.now();
            java.time.LocalDate start = today.minusDays(range - 1L);
            java.sql.Date sqlStart = java.sql.Date.valueOf(start);
            java.sql.Date sqlEndExclusive = java.sql.Date.valueOf(today.plusDays(1));
            Long totalCount = queryLongOrNull(
                    "SELECT COUNT(*) FROM notification_delivery_log WHERE created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            Long successCount = queryLongOrNull(
                    "SELECT COUNT(*) FROM notification_delivery_log WHERE success=1 AND created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            Long failedCount = queryLongOrNull(
                    "SELECT COUNT(*) FROM notification_delivery_log WHERE success=0 AND created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            Long todayCount = queryLongOrNull(
                    "SELECT COUNT(*) FROM notification_delivery_log WHERE created_time >= CURDATE() AND created_time < CURDATE() + INTERVAL 1 DAY");
            Long avgCostMs = queryLongOrNull(
                    "SELECT COALESCE(AVG(cost_ms),0) FROM notification_delivery_log WHERE created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            List<Map<String, Object>> byChannel = jdbcTemplate.queryForList(
                    "SELECT COALESCE(channel_name, channel_key, '未知渠道') AS channel, COUNT(*) AS total, " +
                            "SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS success " +
                            "FROM notification_delivery_log WHERE created_time >= ? AND created_time < ? " +
                            "GROUP BY COALESCE(channel_name, channel_key, '未知渠道') ORDER BY total DESC LIMIT 10",
                    sqlStart, sqlEndExclusive);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("range", range);
            result.put("totalCount", totalCount == null ? 0 : totalCount);
            result.put("successCount", successCount == null ? 0 : successCount);
            result.put("failedCount", failedCount == null ? 0 : failedCount);
            result.put("todayCount", todayCount == null ? 0 : todayCount);
            result.put("avgCostMs", avgCostMs == null ? 0 : avgCostMs);
            result.put("byChannel", byChannel);
            return Result.ok(result);
        } catch (Exception e) {
            throw unavailable("通知投递统计", e);
        }
    }

    /**
     * 客户端错误监控：替换原"数据暂不可用"占位面板，从 client_error_log 真实聚合
     */
    @GetMapping("/dashboard/client-error-stats")
    public Result<Map<String, Object>> clientErrorStats(@RequestParam(defaultValue = "7") int range) {
        if (range != 7 && range != 30 && range != 90) {
            throw new BizException(400, "range 仅支持 7、30 或 90");
        }
        try {
            java.time.LocalDate today = java.time.LocalDate.now();
            java.time.LocalDate start = today.minusDays(range - 1L);
            java.sql.Date sqlStart = java.sql.Date.valueOf(start);
            java.sql.Date sqlEndExclusive = java.sql.Date.valueOf(today.plusDays(1));
            Long totalCount = queryLongOrNull(
                    "SELECT COUNT(*) FROM client_error_log WHERE created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            Long todayCount = queryLongOrNull(
                    "SELECT COUNT(*) FROM client_error_log WHERE created_time >= CURDATE() AND created_time < CURDATE() + INTERVAL 1 DAY");
            List<Map<String, Object>> topErrorTypes = jdbcTemplate.queryForList(
                    "SELECT COALESCE(error_type, 'unknown') AS errorType, COUNT(*) AS count " +
                            "FROM client_error_log WHERE created_time >= ? AND created_time < ? " +
                            "GROUP BY COALESCE(error_type, 'unknown') ORDER BY count DESC LIMIT 10",
                    sqlStart, sqlEndExclusive);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("range", range);
            result.put("totalCount", totalCount == null ? 0 : totalCount);
            result.put("todayCount", todayCount == null ? 0 : todayCount);
            result.put("topErrorTypes", topErrorTypes);
            return Result.ok(result);
        } catch (Exception e) {
            throw unavailable("客户端错误统计", e);
        }
    }

    /**
     * 卡密库存统计：替换原"数据暂不可用"占位面板，从 card_group/card_item 真实聚合
     */
    @GetMapping("/dashboard/stock-stats")
    public Result<Map<String, Object>> stockStats() {
        try {
            Long totalGroups = queryLongOrNull(
                    "SELECT COUNT(*) FROM card_group WHERE deleted=0");
            Long totalStock = queryLongOrNull(
                    "SELECT COALESCE(SUM(total_count),0) FROM card_group WHERE deleted=0");
            Long usedStock = queryLongOrNull(
                    "SELECT COALESCE(SUM(used_count),0) FROM card_group WHERE deleted=0");
            Long remainStock = queryLongOrNull(
                    "SELECT COALESCE(SUM(remain_count),0) FROM card_group WHERE deleted=0");
            Long lowStockGroups = queryLongOrNull(
                    "SELECT COUNT(*) FROM card_group WHERE deleted=0 AND status=1 AND remain_count <= alert_threshold");
            Long todayConsumed = queryLongOrNull(
                    "SELECT COUNT(*) FROM card_item WHERE deleted=0 AND is_used=1 " +
                            "AND used_time >= CURDATE() AND used_time < CURDATE() + INTERVAL 1 DAY");
            List<Map<String, Object>> lowStockList = jdbcTemplate.queryForList(
                    "SELECT id, group_name, remain_count, alert_threshold " +
                            "FROM card_group WHERE deleted=0 AND status=1 AND remain_count <= alert_threshold " +
                            "ORDER BY remain_count ASC LIMIT 10");
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("totalGroups", totalGroups == null ? 0 : totalGroups);
            result.put("totalStock", totalStock == null ? 0 : totalStock);
            result.put("usedStock", usedStock == null ? 0 : usedStock);
            result.put("remainStock", remainStock == null ? 0 : remainStock);
            result.put("lowStockGroups", lowStockGroups == null ? 0 : lowStockGroups);
            result.put("todayConsumed", todayConsumed == null ? 0 : todayConsumed);
            result.put("lowStockList", lowStockList);
            return Result.ok(result);
        } catch (Exception e) {
            throw unavailable("卡密库存统计", e);
        }
    }

    /**
     * 商机与商品同步统计：替换原"数据暂不可用"占位面板
     * - 商品同步来自 xianyu_goods_sync_task
     * - 商机生图来自 opportunity_image_history
     */
    @GetMapping("/dashboard/sync-stats")
    public Result<Map<String, Object>> syncStats(@RequestParam(defaultValue = "7") int range) {
        if (range != 7 && range != 30 && range != 90) {
            throw new BizException(400, "range 仅支持 7、30 或 90");
        }
        try {
            java.time.LocalDate today = java.time.LocalDate.now();
            java.time.LocalDate start = today.minusDays(range - 1L);
            java.sql.Date sqlStart = java.sql.Date.valueOf(start);
            java.sql.Date sqlEndExclusive = java.sql.Date.valueOf(today.plusDays(1));
            Long syncTotal = queryLongOrNull(
                    "SELECT COUNT(*) FROM xianyu_goods_sync_task WHERE deleted=0 AND created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            Long syncSuccess = queryLongOrNull(
                    "SELECT COUNT(*) FROM xianyu_goods_sync_task WHERE deleted=0 AND status='completed' AND created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            Long syncFailed = queryLongOrNull(
                    "SELECT COUNT(*) FROM xianyu_goods_sync_task WHERE deleted=0 AND status IN ('failed','terminated') AND created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            Long todaySyncCount = queryLongOrNull(
                    "SELECT COUNT(*) FROM xianyu_goods_sync_task WHERE deleted=0 AND created_time >= CURDATE() AND created_time < CURDATE() + INTERVAL 1 DAY");
            Long imageGenerated = queryLongOrNull(
                    "SELECT COUNT(*) FROM opportunity_image_history WHERE created_time >= ? AND created_time < ?",
                    sqlStart, sqlEndExclusive);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("range", range);
            result.put("syncTotal", syncTotal == null ? 0 : syncTotal);
            result.put("syncSuccess", syncSuccess == null ? 0 : syncSuccess);
            result.put("syncFailed", syncFailed == null ? 0 : syncFailed);
            result.put("todaySyncCount", todaySyncCount == null ? 0 : todaySyncCount);
            result.put("imageGenerated", imageGenerated == null ? 0 : imageGenerated);
            return Result.ok(result);
        } catch (Exception e) {
            throw unavailable("商机与商品同步统计", e);
        }
    }

    private Long queryLongOrNull(String sql, Object... args) {
        try {
            Long v = jdbcTemplate.queryForObject(sql, Long.class, args);
            return v == null ? 0L : v;
        } catch (Exception e) {
            log.warn("dashboard 聚合查询失败, sql={}, errorType={}", sql.substring(0, Math.min(60, sql.length())), e.getClass().getSimpleName());
            return 0L;
        }
    }

    /**
     * 按天聚合统计：执行一次 GROUP BY DATE(created_time) 查询，按 dates 顺序对齐填充，
     * 缺失的日期补 0。替代 N 次循环 COUNT。
     */
    private List<Long> queryDailyCounts(String sql, java.sql.Date startExclusive, java.sql.Date endExclusive, List<String> dates) {
        Map<String, Long> map = new LinkedHashMap<>();
        try {
            jdbcTemplate.query(sql,
                    rs -> {
                        String d = String.valueOf(rs.getDate(1).toLocalDate());
                        map.put(d, rs.getLong(2));
                    },
                    startExclusive, endExclusive);
        } catch (Exception e) {
            throw unavailable("每日趋势统计", e);
        }
        List<Long> result = new ArrayList<>(dates.size());
        for (String d : dates) result.add(map.getOrDefault(d, 0L));
        return result;
    }

    private Map<String, Object> buildCard(String key, String label, String value, String icon, String badge, String extra) {
        Map<String, Object> card = new LinkedHashMap<>();
        card.put("key", key);
        card.put("label", label);
        card.put("value", value);
        card.put("icon", icon);
        if (badge != null) card.put("badge", badge);
        if (extra != null) card.put("extra", extra);
        return card;
    }

    @GetMapping("/dashboard/recent-events")
    public Result<List<Map<String, Object>>> recentEvents() {
        return Result.ok(callDependency("后台操作日志", service::recentEvents));
    }

    /**
     * 待办列表数据源：聚合 失败的工作流执行 / 触发风控账号 / 通知发送失败 / 卡密低库存
     * 排序：按 created_time DESC，统一映射为 {title, time, type, source, sourceId}
     */
    @GetMapping("/dashboard/pending-tasks")
    public Result<List<Map<String, Object>>> pendingTasks() {
        List<Map<String, Object>> tasks = new ArrayList<>();
        // 1. 失败的工作流执行（需用户介入重试）
        try {
            tasks.addAll(jdbcTemplate.queryForList(
                    "SELECT id, execution_no, workflow_id, error_message, " +
                            "DATE_FORMAT(created_time, '%Y-%m-%d %H:%i:%s') AS time " +
                            "FROM workflow_execution WHERE deleted=0 AND status='failed' " +
                            "ORDER BY created_time DESC LIMIT 20"));
        } catch (Exception e) {
            throw unavailable("待办工作流数据", e);
        }
        // 2. 触发风控但未解除的闲鱼账号（risk_level > 0）
        try {
            tasks.addAll(jdbcTemplate.queryForList(
                    "SELECT id, external_uid, nickname, risk_level, " +
                            "DATE_FORMAT(updated_time, '%Y-%m-%d %H:%i:%s') AS time, " +
                            "'risk' AS task_type " +
                            "FROM xianyu_account WHERE deleted=0 AND risk_level > 0 " +
                            "ORDER BY updated_time DESC LIMIT 20"));
        } catch (Exception e) {
            throw unavailable("待办风控数据", e);
        }
        // 3. 通知发送失败且 retry_count < 3 的记录
        try {
            tasks.addAll(jdbcTemplate.queryForList(
                    "SELECT id, channel_name, event_type, message, retry_count, " +
                            "DATE_FORMAT(created_time, '%Y-%m-%d %H:%i:%s') AS time, " +
                            "'notify_fail' AS task_type " +
                            "FROM notification_delivery_log WHERE success=0 AND retry_count < 3 " +
                            "ORDER BY created_time DESC LIMIT 20"));
        } catch (Exception e) {
            throw unavailable("待办通知数据", e);
        }
        // 4. 卡密低库存（remain_count <= alert_threshold）
        try {
            tasks.addAll(jdbcTemplate.queryForList(
                    "SELECT id, group_name, remain_count, alert_threshold, " +
                            "DATE_FORMAT(updated_time, '%Y-%m-%d %H:%i:%s') AS time, " +
                            "'kami_low' AS task_type " +
                            "FROM card_group WHERE deleted=0 AND status=1 AND remain_count <= alert_threshold " +
                            "ORDER BY updated_time DESC LIMIT 20"));
        } catch (Exception e) {
            throw unavailable("待办卡密库存数据", e);
        }
        // 统一格式化为 {title, time, type, source, sourceId}
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> row : tasks) {
            Map<String, Object> item = new LinkedHashMap<>();
            String taskType = String.valueOf(row.getOrDefault("task_type", "workflow_fail"));
            String title;
            String type;
            switch (taskType) {
                case "risk":
                    title = "闲鱼账号 [" + row.getOrDefault("nickname", row.get("external_uid")) + "] 触发风控（等级 " + row.get("risk_level") + "）";
                    type = "risk";
                    break;
                case "notify_fail":
                    title = "通知发送失败 [" + row.getOrDefault("channel_name", "未知渠道") + "] " + row.getOrDefault("event_type", "") + "（已重试 " + row.getOrDefault("retry_count", 0) + " 次）";
                    type = "notify";
                    break;
                case "kami_low":
                    title = "卡密库存预警 [" + row.getOrDefault("group_name", "未命名") + "] 剩余 " + row.getOrDefault("remain_count", 0) + "（阈值 " + row.getOrDefault("alert_threshold", 10) + "）";
                    type = "kami";
                    break;
                default:
                    title = "工作流执行失败 [" + row.getOrDefault("execution_no", "") + "]";
                    if (row.get("error_message") != null) {
                        String err = String.valueOf(row.get("error_message"));
                        if (err.length() > 60) err = err.substring(0, 60) + "...";
                        title += "：" + err;
                    }
                    type = "workflow";
                    break;
            }
            item.put("title", title);
            item.put("time", row.getOrDefault("time", ""));
            item.put("type", type);
            item.put("source", taskType);
            item.put("sourceId", row.get("id"));
            result.add(item);
        }
        // 按 time 倒序
        result.sort((a, b) -> String.valueOf(b.get("time")).compareTo(String.valueOf(a.get("time"))));
        return Result.ok(result);
    }

    /**
     * 通知已读状态：标记一批事件为已读
     * 请求体：{ "eventIds": [1, 2, 3], "eventSource": "recent_event" }
     */
    @PostMapping("/notifications/read-status")
    public Result<Map<String, Object>> markNotificationsRead(@RequestBody Map<String, Object> body) {
        Long adminUserId = AdminContext.userId();
        if (adminUserId == null) {
            throw new BizException(401, "请先登录");
        }
        List<Long> ids = parseEventIds(body);
        String eventSource = String.valueOf(body.getOrDefault("eventSource", "recent_event"));
        if (eventSource.isBlank()) {
            throw new BizException(400, "eventSource 不能为空");
        }
        int inserted = 0;
        try {
            for (Long id : ids) {
                    int rows = jdbcTemplate.update(
                            "INSERT IGNORE INTO sys_notification_read (admin_user_id, event_source, event_id, read_at) VALUES (?, ?, ?, NOW())",
                            adminUserId, eventSource, id);
                    inserted += rows;
            }
        } catch (Exception e) {
            throw unavailable("通知已读状态保存", e);
        }
        Map<String, Object> ret = new LinkedHashMap<>();
        ret.put("marked", inserted);
        return Result.ok(ret);
    }

    /**
     * 通知已读状态：查询当前管理员已读事件 ID 列表
     * 参数 eventSource（默认 recent_event）
     */
    @GetMapping("/notifications/read-status")
    public Result<List<Long>> getReadStatus(@RequestParam(defaultValue = "recent_event") String eventSource) {
        Long adminUserId = AdminContext.userId();
        if (adminUserId == null) {
            throw new BizException(401, "请先登录");
        }
        try {
            return Result.ok(jdbcTemplate.queryForList(
                    "SELECT event_id FROM sys_notification_read WHERE admin_user_id = ? AND event_source = ?",
                    Long.class, adminUserId, eventSource));
        } catch (Exception e) {
            throw unavailable("通知已读状态", e);
        }
    }

    /**
     * 通知已读状态：一键标记当前管理员所有未读事件为已读
     * 请求体：{ "eventIds": [1,2,3] } —— 全部标记为已读
     */
    @PostMapping("/notifications/mark-all-read")
    public Result<Map<String, Object>> markAllRead(@RequestBody(required = false) Map<String, Object> body) {
        Long adminUserId = AdminContext.userId();
        if (adminUserId == null) {
            throw new BizException(401, "请先登录");
        }
        List<Long> ids = parseEventIds(body);
        String eventSource = body == null ? "recent_event" : String.valueOf(body.getOrDefault("eventSource", "recent_event"));
        if (eventSource.isBlank()) {
            throw new BizException(400, "eventSource 不能为空");
        }
        int inserted = 0;
        try {
            for (Long id : ids) {
                int rows = jdbcTemplate.update(
                        "INSERT IGNORE INTO sys_notification_read (admin_user_id, event_source, event_id, read_at) VALUES (?, ?, ?, NOW())",
                        adminUserId, eventSource, id);
                inserted += rows;
            }
        } catch (Exception e) {
            throw unavailable("通知已读状态保存", e);
        }
        Map<String, Object> ret = new LinkedHashMap<>();
        ret.put("marked", inserted);
        return Result.ok(ret);
    }

    private List<Long> parseEventIds(Map<String, Object> body) {
        if (body == null || !(body.get("eventIds") instanceof List<?> rawIds) || rawIds.isEmpty()) {
            throw new BizException(400, "eventIds 至少需要一条记录");
        }
        List<Long> ids = new ArrayList<>(rawIds.size());
        for (Object rawId : rawIds) {
            try {
                long id = Long.parseLong(String.valueOf(rawId));
                if (id <= 0) {
                    throw new NumberFormatException("non-positive id");
                }
                ids.add(id);
            } catch (NumberFormatException e) {
                throw new BizException(400, "eventIds 包含非法记录标识");
            }
        }
        return ids;
    }

    @GetMapping("/modules/{moduleKey}/meta")
    public Result<ModuleCatalog.ModuleMeta> meta(@PathVariable String moduleKey) {
        return Result.ok(callDependency("模块元数据", () -> service.meta(moduleKey)));
    }

    @GetMapping("/modules/{moduleKey}/stats")
    public Result<Map<String, Object>> stats(@PathVariable String moduleKey) {
        return Result.ok(callDependency("模块统计", () -> service.stats(moduleKey)));
    }

    @GetMapping("/modules/{moduleKey}/page")
    public Result<PageResult<Map<String, Object>>> page(@PathVariable String moduleKey,
                                                        @RequestParam(defaultValue = "1") int current,
                                                        @RequestParam(defaultValue = "10") int size,
                                                        @RequestParam(required = false) String keyword,
                                                        @RequestParam(required = false) String status,
                                                        @RequestParam(required = false) String sortField,
                                                        @RequestParam(required = false) String sortOrder) {
        return Result.ok(callDependency("模块列表",
                () -> service.page(moduleKey, current, size, keyword, status, sortField, sortOrder)));
    }

    /**
     * 直接查询 sys_user 用户列表（不受 admin_module_record 影响）。
     * 支持 keyword、status、page、pageSize 参数。
     */
    @GetMapping("/users")
    public Result<Map<String, Object>> listUsers(@RequestParam(defaultValue = "1") int current,
                                                 @RequestParam(defaultValue = "20") int size,
                                                 @RequestParam(required = false) String keyword,
                                                 @RequestParam(required = false) String status) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            PageResult<Map<String, Object>> page = callDependency("后台用户列表",
                    () -> service.page("users", current, size, keyword, status));
            result.put("records", page.getRecords());
            result.put("total", page.getTotal());
            result.put("current", page.getCurrent());
            result.put("size", page.getSize());
        } catch (Exception e) {
            throw unavailable("后台用户列表", e);
        }
        return Result.ok(result);
    }

    /**
     * 获取租户列表（用于用户编辑弹窗的下拉选择器）。
     * 返回所有未删除的租户，前端按 id 选择。
     */
    @GetMapping("/tenants")
    public Result<List<Map<String, Object>>> listTenants(@RequestParam(required = false) String keyword) {
        try {
            StringBuilder sql = new StringBuilder(
                    "SELECT id, COALESCE(display_name, tenant_name, name, CONCAT('tenant-', id)) AS name " +
                    "FROM sys_tenant WHERE deleted=0");
            List<Object> args = new ArrayList<>();
            if (keyword != null && !keyword.isBlank()) {
                sql.append(" AND (display_name LIKE ? OR tenant_name LIKE ? OR name LIKE ?)");
                String kw = "%" + keyword + "%";
                args.add(kw); args.add(kw); args.add(kw);
            }
            sql.append(" ORDER BY id ASC LIMIT 200");
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql.toString(), args.toArray());
            return Result.ok(rows);
        } catch (Exception e) {
            throw unavailable("租户列表", e);
        }
    }

    @GetMapping("/modules/{moduleKey}/{id}")
    public Result<Map<String, Object>> detail(@PathVariable String moduleKey, @PathVariable long id) {
        requirePositiveId(id);
        return Result.ok(callDependency("模块详情", () -> service.detail(moduleKey, id)));
    }

    @PostMapping("/modules/{moduleKey}")
    public Result<Map<String, Object>> save(@PathVariable String moduleKey, @RequestBody Map<String, Object> data) {
        return Result.ok(callDependency("模块数据保存", () -> service.save(moduleKey, data)));
    }

    @PutMapping("/modules/{moduleKey}/{id}")
    public Result<Map<String, Object>> update(@PathVariable String moduleKey, @PathVariable long id, @RequestBody Map<String, Object> data) {
        requirePositiveId(id);
        if (data == null) {
            throw new BizException(400, "请求数据不能为空");
        }
        data.put("id", id);
        return Result.ok(callDependency("模块数据更新", () -> service.save(moduleKey, data)));
    }

    @PutMapping("/modules/{moduleKey}/{id}/status")
    public Result<Void> updateStatus(@PathVariable String moduleKey, @PathVariable long id, @RequestBody Map<String, Object> data) {
        requirePositiveId(id);
        if (data == null || data.get("status") == null || String.valueOf(data.get("status")).isBlank()) {
            throw new BizException(400, "status 不能为空");
        }
        runDependency("模块状态更新", () -> service.updateStatus(moduleKey, id, String.valueOf(data.get("status"))));
        return Result.ok(null);
    }

    private static final List<String> MODEL_CONFIG_MODULES =
            List.of("model-config-general", "model-config-chat", "model-config-image",
                    "model-config-image-2", "model-config-image-3");

    private static final ObjectMapper objectMapper = new ObjectMapper();

    private static final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)  // 许多 AI 供应商/代理不支持 HTTP/2
            .connectTimeout(Duration.ofSeconds(15))
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();
    private static final int MAX_UPSTREAM_RESPONSE_BYTES = 1024 * 1024;
    private static final int MAX_PROVIDER_MODELS = 1_000;

    /**
     * 测试 AI 模型连接
     * 向 OpenAI 兼容的 Chat Completions API 发送最简请求验证连接
     */
    @PostMapping("/modules/{moduleKey}/test-connection")
    public Result<Map<String, Object>> testConnection(@PathVariable String moduleKey, @RequestBody Map<String, Object> data) {
        if (!MODEL_CONFIG_MODULES.contains(moduleKey)) {
            throw new BizException(400, "当前模块不支持连接测试");
        }
        if (data == null) {
            throw new BizException(400, "连接配置不能为空");
        }
        preserveMaskedSecretForTest(moduleKey, data);

        String baseUrl = str(data, "baseUrl");
        String apiKey = str(data, "apiKey");
        String model = resolveModel(data);

        if (baseUrl.isBlank() || apiKey.isBlank() || "******".equals(apiKey) || model.isBlank()) {
            throw new BizException(400, "缺少必要配置：baseUrl、apiKey、model");
        }

        if ("model-config-image".equals(moduleKey) || "model-config-image-2".equals(moduleKey) || "model-config-image-3".equals(moduleKey)) {
            try {
                Map<String, Object> imageResult = imageGenerationService.testConnection(data);
                if (imageResult == null || !Boolean.TRUE.equals(imageResult.get("ok"))) {
                    throw new BizException(503, "生图模型服务连接失败，请检查提供商状态后重试");
                }
                return Result.ok(imageResult);
            } catch (BizException e) {
                throw e;
            } catch (Exception e) {
                throw unavailable("生图模型连接测试", e);
            }
        }

        long start = System.currentTimeMillis();
        try {
            String safeBaseUrl = aiProviderEndpointPolicy.validateBaseUrl(baseUrl);
            URI endpointUri = URI.create(safeBaseUrl + "/chat/completions");

            Map<String, Object> requestBody = new LinkedHashMap<>();
            requestBody.put("model", model);
            requestBody.put("temperature", 0.2);
            requestBody.put("max_tokens", 32);
            requestBody.put("messages", List.of(Map.of("role", "user", "content", "请回复 ok")));

            String jsonBody = objectMapper.writeValueAsString(requestBody);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(endpointUri)
                    .header("Authorization", "Bearer " + apiKey)
                    .header("Content-Type", "application/json")
                    .timeout(Duration.ofSeconds(30))
                    .POST(HttpRequest.BodyPublishers.ofString(jsonBody, StandardCharsets.UTF_8))
                    .build();

            HttpResponse<InputStream> response = httpClient.send(
                    request, HttpResponse.BodyHandlers.ofInputStream());

            if (response.statusCode() != 200) {
                closeBody(response);
                throw new BizException(503, "模型服务连接失败（HTTP " + response.statusCode() + "），请稍后重试");
            }

            JsonNode choices = objectMapper.readTree(readLimitedBody(response)).path("choices");
            if (!choices.isArray() || choices.isEmpty()) {
                throw new BizException(503, "模型服务返回了无效响应，请稍后重试");
            }
            String content = choices.path(0).path("message").path("content").asText("").trim();
            if (content.isBlank()) {
                throw new BizException(503, "模型服务返回了无效响应，请稍后重试");
            }

            long durationMs = System.currentTimeMillis() - start;
            return Result.ok(Map.of(
                    "ok", true,
                    "durationMs", durationMs,
                    "responseSummary", content.length() <= 500 ? content : content.substring(0, 500),
                    "message", "连接成功"
            ));
        } catch (BizException e) {
            throw e;
        } catch (IllegalArgumentException e) {
            throw new BizException(400, "连接配置格式不正确");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw unavailable("模型连接测试", e);
        } catch (Exception e) {
            throw unavailable("模型连接测试", e);
        }
    }


    private void preserveMaskedSecretForTest(String moduleKey, Map<String, Object> data) {
        if (data == null) return;
        Object id = data.get("id");
        Object apiKey = data.get("apiKey");
        if (id == null || apiKey == null || !"******".equals(String.valueOf(apiKey))) return;
        try {
            Map<String, Object> raw = service.unmaskedRecord(moduleKey, Long.parseLong(String.valueOf(id)));
            Object oldKey = raw.get("apiKey");
            if (oldKey != null && !String.valueOf(oldKey).isBlank() && !"******".equals(String.valueOf(oldKey))) {
                data.put("apiKey", oldKey);
            }
        } catch (BizException e) {
            if (e.getCode() == 404) {
                throw new BizException(400, "已保存的模型配置不存在");
            }
            throw e;
        } catch (Exception e) {
            throw unavailable("已保存的模型密钥", e);
        }
    }

    /**
     * 获取 AI 模型列表
     * 向 {baseUrl}/models 发送请求，解析 data[].id 返回模型列表
     */
    @PostMapping("/modules/{moduleKey}/fetch-models")
    public Result<Map<String, Object>> fetchModels(@PathVariable String moduleKey, @RequestBody Map<String, Object> data) {
        if (!MODEL_CONFIG_MODULES.contains(moduleKey)) {
            throw new BizException(400, "当前模块不支持获取模型列表");
        }
        if (data == null) {
            throw new BizException(400, "模型配置不能为空");
        }
        preserveMaskedSecretForTest(moduleKey, data);
        String baseUrl = str(data, "baseUrl");
        String apiKey = str(data, "apiKey");

        if (baseUrl.isBlank() || apiKey.isBlank() || "******".equals(apiKey)) {
            throw new BizException(400, "缺少 baseUrl 或 apiKey");
        }

        try {
            String safeBaseUrl = aiProviderEndpointPolicy.validateBaseUrl(baseUrl);
            URI endpointUri = URI.create(safeBaseUrl + "/models");

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(endpointUri)
                    .header("Authorization", "Bearer " + apiKey)
                    .timeout(Duration.ofSeconds(30))
                    .GET()
                    .build();

            HttpResponse<InputStream> response = httpClient.send(
                    request, HttpResponse.BodyHandlers.ofInputStream());

            if (response.statusCode() != 200) {
                closeBody(response);
                throw new BizException(503, "模型列表服务请求失败（HTTP " + response.statusCode() + "），请稍后重试");
            }

            JsonNode dataList = objectMapper.readTree(readLimitedBody(response)).path("data");
            if (!dataList.isArray() || dataList.isEmpty()) {
                throw new BizException(503, "模型列表服务返回了无效响应，请稍后重试");
            }
            if (dataList.size() > MAX_PROVIDER_MODELS) {
                throw new BizException(503, "模型列表服务返回的数据过多，请缩小提供商模型范围后重试");
            }

            List<String> collectedModels = new ArrayList<>();
            dataList.forEach(modelNode -> {
                String id = modelNode.path("id").asText("").trim();
                if (!id.isBlank()) {
                    collectedModels.add(id);
                }
            });
            List<String> models = collectedModels.stream()
                    .filter(s -> !s.isBlank())
                    .distinct()
                    .toList();
            if (models.isEmpty()) {
                throw new BizException(503, "模型列表服务返回了无效响应，请稍后重试");
            }

            return Result.ok(Map.of("ok", true, "models", models, "message", "获取成功"));
        } catch (BizException e) {
            throw e;
        } catch (IllegalArgumentException e) {
            throw new BizException(400, "连接配置格式不正确");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw unavailable("模型列表获取", e);
        } catch (Exception e) {
            throw unavailable("模型列表获取", e);
        }
    }

    /** 从 data 中解析 model 名称 */
    private static String resolveModel(Map<String, Object> data) {
        for (String key : List.of("defaultModel", "modelName", "model")) {
            String v = str(data, key);
            if (!v.isBlank()) return v;
        }
        return "";
    }

    /** 安全获取字符串值 */
    private static String str(Map<String, Object> data, String key) {
        Object v = data.get(key);
        return v == null ? "" : v.toString().trim();
    }

    private static String readLimitedBody(HttpResponse<InputStream> response) throws IOException {
        try (InputStream input = response.body()) {
            byte[] content = input.readNBytes(MAX_UPSTREAM_RESPONSE_BYTES + 1);
            if (content.length > MAX_UPSTREAM_RESPONSE_BYTES) {
                throw new IOException("upstream response exceeds configured limit");
            }
            return new String(content, StandardCharsets.UTF_8);
        }
    }

    private static void closeBody(HttpResponse<InputStream> response) {
        try (InputStream ignored = response.body()) {
            // Closing without buffering prevents error bodies from exhausting heap.
        } catch (IOException ignored) {
            // The public result is already a sanitized dependency failure.
        }
    }

    private BizException unavailable(String operation, Exception cause) {
        if (cause instanceof BizException bizException) {
            return bizException;
        }
        log.error("{} unavailable (type={})", operation, cause.getClass().getName());
        return new BizException(503, operation + "暂时不可用，请稍后重试");
    }

    private <T> T callDependency(String operation, Supplier<T> action) {
        try {
            T result = action.get();
            if (result == null) {
                throw new BizException(503, operation + "暂时不可用，请稍后重试");
            }
            return result;
        } catch (Exception e) {
            throw unavailable(operation, e);
        }
    }

    private void runDependency(String operation, Runnable action) {
        try {
            action.run();
        } catch (Exception e) {
            throw unavailable(operation, e);
        }
    }

    private void requirePositiveId(long id) {
        if (id <= 0) {
            throw new BizException(400, "记录标识必须大于 0");
        }
    }

    public record BatchStatusReq(List<Long> ids, String status) {}

    @PostMapping("/modules/{moduleKey}/batch-status")
    public Result<Map<String, Object>> batchStatus(@PathVariable String moduleKey, @RequestBody BatchStatusReq req) {
        if (req == null || req.status() == null || req.status().isBlank()) {
            throw new BizException(400, "status 不能为空");
        }
        int count = callDependency("模块批量状态更新",
                () -> service.batchUpdateStatus(moduleKey, req.ids(), req.status()));
        return Result.ok(Map.of("count", count));
    }

    public record BatchIdsReq(List<Long> ids) {}

    @PostMapping("/modules/{moduleKey}/batch-delete")
    public Result<Map<String, Object>> batchDelete(@PathVariable String moduleKey, @RequestBody BatchIdsReq req) {
        if (req == null) {
            throw new BizException(400, "请求数据不能为空");
        }
        int count = callDependency("模块批量删除", () -> service.batchDelete(moduleKey, req.ids()));
        return Result.ok(Map.of("count", count));
    }

    @DeleteMapping("/modules/{moduleKey}/{id}")
    public Result<Void> delete(@PathVariable String moduleKey, @PathVariable long id) {
        requirePositiveId(id);
        runDependency("模块删除", () -> service.delete(moduleKey, id));
        return Result.ok(null);
    }

    @GetMapping("/modules/{moduleKey}/export")
    public ResponseEntity<byte[]> export(@PathVariable String moduleKey,
                                         @RequestParam(required = false) String keyword,
                                         @RequestParam(required = false) String status) {
        String csv = callDependency("模块数据导出", () -> service.exportCsv(moduleKey, keyword, status));
        String filename = moduleKey + ".csv";
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(new MediaType("text", "csv", StandardCharsets.UTF_8))
                .body(csv.getBytes(StandardCharsets.UTF_8));
    }
}
