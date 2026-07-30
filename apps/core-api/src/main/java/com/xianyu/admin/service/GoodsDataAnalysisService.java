package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.mapper.GoodsDataAnalysisMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 商品数据分析 Service
 *
 * 设计要点：
 *  1. 数据来源混合：
 *     - 商品累计指标（曝光/浏览/想要）来自 xianyu_goods 表（不受时间范围影响）
 *     - 订单指标（订单数/订单金额/买家数）来自 xianyu_trade_order_item 关联 xianyu_trade_order，按时间范围筛选
 *  2. 时间范围支持 1/3/7/30 天（与鱼小铺数据罗盘 1/7/30 对齐，额外支持 3 天）
 *  3. 排序字段白名单：防止 SQL 注入（orderByClause 通过 ${} 拼接）
 *  4. 环比计算：当期 vs 上一周期（同样长度的时间窗口）
 *  5. 转化率 = 订单数 / 曝光数（按商品累计曝光计算，仅鱼小铺有30天曝光数据时才准确）
 */
@Service
public class GoodsDataAnalysisService {
    private static final Logger log = LoggerFactory.getLogger(GoodsDataAnalysisService.class);

    private static final Set<Integer> ALLOWED_DAYS = new HashSet<>(Arrays.asList(1, 3, 7, 30));

    /**
     * 排序字段白名单（防止 SQL 注入）
     * key = 前端传入的 sortBy 值，value = SQL ORDER BY 子句
     */
    private static final String EXPOSURE_EXPR = "COALESCE(NULLIF(g.exposure_count_30d, 0), g.exposure_count, 0)";
    private static final String VIEW_EXPR = "COALESCE(NULLIF(g.view_count_30d, 0), g.view_count, 0)";

    private static final Map<String, String> SORT_CLAUSES = new HashMap<>();
    static {
        SORT_CLAUSES.put("exposure", EXPOSURE_EXPR + " DESC, " + VIEW_EXPR + " DESC, g.id DESC");
        SORT_CLAUSES.put("view", VIEW_EXPR + " DESC, " + EXPOSURE_EXPR + " DESC, g.id DESC");
        SORT_CLAUSES.put("want", "g.want_count DESC, " + VIEW_EXPR + " DESC, g.id DESC");
        SORT_CLAUSES.put("order", "ord.order_count DESC, ord.order_amount DESC, g.id DESC");
        SORT_CLAUSES.put("orderAmount", "ord.order_amount DESC, ord.order_count DESC, g.id DESC");
        SORT_CLAUSES.put("sold", "ord.goods_count DESC, ord.order_count DESC, g.id DESC");
        SORT_CLAUSES.put("conversion", "ord.order_count DESC, " + EXPOSURE_EXPR + " ASC, g.id DESC");
        SORT_CLAUSES.put("newest", "g.gmt_create DESC, g.id DESC");
        SORT_CLAUSES.put("price", "g.sold_price DESC, g.id DESC");
        SORT_CLAUSES.put("worst_exposure", EXPOSURE_EXPR + " ASC, " + VIEW_EXPR + " ASC, g.id DESC");
        SORT_CLAUSES.put("worst_view", VIEW_EXPR + " ASC, " + EXPOSURE_EXPR + " ASC, g.id DESC");
        SORT_CLAUSES.put("worst_want", "g.want_count ASC, " + EXPOSURE_EXPR + " ASC, g.id DESC");
        SORT_CLAUSES.put("worst_conversion", "ord.order_count ASC, " + EXPOSURE_EXPR + " DESC, g.id DESC");
        SORT_CLAUSES.put("worst_order", "ord.order_count ASC, " + EXPOSURE_EXPR + " DESC, g.id DESC");
    }

    private final GoodsDataAnalysisMapper mapper;

    /**
     * summary() 并行查询线程池。
     * 设计要点：
     *  1. 查询为 I/O 密集型（MySQL 索引扫描），CPU 占用低，线程数可略大于 CPU 核数
     *  2. summary() 单次请求最多并行 5 个查询，poolSize=8 足够
     *  3. 使用命名线程池便于排查，避免使用 ForkJoinPool.commonPool 影响其他业务
     */
    private static final ExecutorService SUMMARY_QUERY_EXECUTOR =
            Executors.newFixedThreadPool(8, r -> {
                Thread t = new Thread(r, "goods-data-summary-query");
                t.setDaemon(true);
                return t;
            });

    public GoodsDataAnalysisService(GoodsDataAnalysisMapper mapper) {
        this.mapper = mapper;
    }

    /**
     * 全局概览
     *
     * 性能优化：8 个无依赖查询并行执行，整体耗时由"串行总和"降为"最慢查询"。
     * 依赖关系分析：
     *  - goodsAgg / zeroStats：无依赖，可并行（商品累计聚合 / 零指标统计）
     *  - curOrders / prevOrders：无依赖，可并行（当期 / 上一周期订单聚合）
     *  - dailyTrend：无依赖，独立查询
     *  - noOrder：无依赖，独立查询（与 zeroStats 不同：noOrder 是按时间范围筛选"无订单"商品数）
     *  - topByOrders / topByExposure：无依赖，可并行（两次 listGoodsWithData 仅排序与 LIMIT 不同）
     */
    public Map<String, Object> summary(Long tenantId, Long accountId, int days) {
        if (!ALLOWED_DAYS.contains(days)) {
            throw new BizException(400, "时间范围仅支持 1/3/7/30 天");
        }

        int prevDays = days * 2;

        // ===== 并行执行无依赖查询 =====
        // 分组1：商品累计指标 + 零指标统计（同表 xianyu_goods 聚合，并行）
        CompletableFuture<Map<String, Object>> goodsAggFuture = CompletableFuture.supplyAsync(
                () -> mapper.goodsAggregate(tenantId, accountId), SUMMARY_QUERY_EXECUTOR);

        CompletableFuture<Map<String, Object>> zeroStatsFuture = CompletableFuture.supplyAsync(
                () -> mapper.zeroStats(tenantId, accountId), SUMMARY_QUERY_EXECUTOR);

        // 分组2：当期 + 上一周期订单聚合（同表 xianyu_trade_order_item，并行）
        CompletableFuture<Map<String, Object>> curOrdersFuture = CompletableFuture.supplyAsync(
                () -> mapper.orderAggregateTotal(tenantId, accountId, days), SUMMARY_QUERY_EXECUTOR);

        CompletableFuture<Map<String, Object>> prevOrdersFuture = CompletableFuture.supplyAsync(
                () -> mapper.orderAggregatePrev(tenantId, accountId, days, prevDays), SUMMARY_QUERY_EXECUTOR);

        // 分组3：按日趋势（独立查询）
        CompletableFuture<List<Map<String, Object>>> dailyTrendFuture = CompletableFuture.supplyAsync(
                () -> mapper.dailyTrend(tenantId, accountId, days), SUMMARY_QUERY_EXECUTOR);

        // 分组4：无订单商品数（独立查询，依赖 days 参数）
        CompletableFuture<Map<String, Object>> noOrderFuture = CompletableFuture.supplyAsync(
                () -> mapper.noOrderCount(tenantId, accountId, days), SUMMARY_QUERY_EXECUTOR);

        // 分组5：TOP 排行（两次 listGoodsWithData 仅排序不同，并行）
        CompletableFuture<List<Map<String, Object>>> topByOrdersFuture = CompletableFuture.supplyAsync(
                () -> buildTopGoods(tenantId, accountId, days, "order", 5), SUMMARY_QUERY_EXECUTOR);

        CompletableFuture<List<Map<String, Object>>> topByExposureFuture = CompletableFuture.supplyAsync(
                () -> buildTopGoods(tenantId, accountId, days, "exposure", 5), SUMMARY_QUERY_EXECUTOR);

        // 等待所有并行任务完成
        CompletableFuture.allOf(
                goodsAggFuture, zeroStatsFuture, curOrdersFuture, prevOrdersFuture,
                dailyTrendFuture, noOrderFuture, topByOrdersFuture, topByExposureFuture
        ).join();

        // 获取结果（join 不会抛 InterruptedException，异常会被包装为 CompletionException）
        Map<String, Object> goodsAgg = goodsAggFuture.join();
        Map<String, Object> zeroStats = zeroStatsFuture.join();
        Map<String, Object> curOrders = curOrdersFuture.join();
        Map<String, Object> prevOrders = prevOrdersFuture.join();
        List<Map<String, Object>> dailyTrend = dailyTrendFuture.join();
        Map<String, Object> noOrder = noOrderFuture.join();
        List<Map<String, Object>> topByOrders = topByOrdersFuture.join();
        List<Map<String, Object>> topByExposure = topByExposureFuture.join();

        // 补全无数据日期（CPU 操作，无需并行）
        dailyTrend = fillMissingDates(dailyTrend, days);

        // 运营预警指标
        long zeroExposure = toLong(zeroStats.get("zero_exposure"));
        long zeroView = toLong(zeroStats.get("zero_view"));
        long zeroWant = toLong(zeroStats.get("zero_want"));
        long noOrderGoods = toLong(noOrder.get("no_order_count"));

        // 6. 计算汇总数据
        long goodsTotal = toLong(goodsAgg.get("goods_total"));
        long onSale = toLong(goodsAgg.get("on_sale"));
        long offShelf = toLong(goodsAgg.get("off_shelf"));
        long sold = toLong(goodsAgg.get("sold"));
        long exposureSum = toLong(goodsAgg.get("exposure_sum"));
        long viewSum = toLong(goodsAgg.get("view_sum"));
        long wantSum = toLong(goodsAgg.get("want_sum"));
        long exposure30dSum = toLong(goodsAgg.get("exposure_30d_sum"));
        long view30dSum = toLong(goodsAgg.get("view_30d_sum"));

        long orderCount = toLong(curOrders.get("order_count"));
        BigDecimal orderAmount = toBigDecimal(curOrders.get("order_amount"));
        long buyerCount = toLong(curOrders.get("buyer_count"));
        long soldCount = toLong(curOrders.get("goods_count"));

        long prevOrderCount = toLong(prevOrders.get("order_count"));
        BigDecimal prevOrderAmount = toBigDecimal(prevOrders.get("order_amount"));
        long prevBuyerCount = toLong(prevOrders.get("buyer_count"));

        // 7. 计算派生指标
        BigDecimal avgOrderAmount = orderCount > 0
                ? orderAmount.divide(BigDecimal.valueOf(orderCount), 2, RoundingMode.HALF_UP)
                : BigDecimal.ZERO;
        // 转化率：订单数 / 曝光数（用 30 天曝光更准确，没有则用累计）
        long exposureBase = exposure30dSum > 0 ? exposure30dSum : exposureSum;
        double conversionRate = exposureBase > 0
                ? (double) orderCount / exposureBase * 100
                : 0.0;

        // 8. 环比
        double orderCountRatio = ratioPercent(orderCount, prevOrderCount);
        double orderAmountRatio = ratioPercent(orderAmount.doubleValue(), prevOrderAmount.doubleValue());
        double buyerRatio = ratioPercent(buyerCount, prevBuyerCount);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("days", days);
        result.put("realDateRange", buildDateRange(days));
        result.put("scope", accountId == null ? "all" : "single");

        Map<String, Object> goods = new LinkedHashMap<>();
        goods.put("total", goodsTotal);
        goods.put("onSale", onSale);
        goods.put("offShelf", offShelf);
        goods.put("sold", sold);
        goods.put("exposureSum", exposureSum);
        goods.put("viewSum", viewSum);
        goods.put("wantSum", wantSum);
        goods.put("exposure30dSum", exposure30dSum);
        goods.put("view30dSum", view30dSum);
        result.put("goods", goods);

        Map<String, Object> orders = new LinkedHashMap<>();
        orders.put("orderCount", orderCount);
        orders.put("orderAmount", orderAmount);
        orders.put("buyerCount", buyerCount);
        orders.put("soldCount", soldCount);
        orders.put("avgOrderAmount", avgOrderAmount);
        orders.put("conversionRate", conversionRate);
        orders.put("orderCountRatio", orderCountRatio);
        orders.put("orderAmountRatio", orderAmountRatio);
        orders.put("buyerRatio", buyerRatio);
        result.put("orders", orders);

        result.put("dailyTrend", dailyTrend);
        result.put("topByOrders", topByOrders);
        result.put("topByExposure", topByExposure);

        // 运营预警
        Map<String, Object> alerts = new LinkedHashMap<>();
        alerts.put("zeroExposure", zeroExposure);
        alerts.put("zeroView", zeroView);
        alerts.put("zeroWant", zeroWant);
        alerts.put("noOrder", noOrderGoods);
        alerts.put("onSale", onSale);
        result.put("alerts", alerts);

        return result;
    }

    /**
     * 商品列表（带数据）
     */
    public PageResult<Map<String, Object>> products(Long tenantId, Long accountId, int days,
                                                      String keyword, String sortBy, int current, int size) {
        if (!ALLOWED_DAYS.contains(days)) {
            throw new BizException(400, "时间范围仅支持 1/3/7/30 天");
        }
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        String orderByClause = SORT_CLAUSES.getOrDefault(sortBy, SORT_CLAUSES.get("order"));
        if (orderByClause == null) orderByClause = SORT_CLAUSES.get("order");

        int total = mapper.countGoodsWithData(tenantId, accountId, keyword);
        List<Map<String, Object>> records = mapper.listGoodsWithData(tenantId, accountId, days, keyword, orderByClause, offset, limit);

        // 计算每个商品的转化率
        for (Map<String, Object> row : records) {
            long orderCount = toLong(row.get("order_count"));
            long exposure = toLong(row.get("exposure_count"));
            long exposure30d = toLong(row.get("exposure_count_30d"));
            long exposureBase = exposure30d > 0 ? exposure30d : exposure;
            double conversion = exposureBase > 0 ? (double) orderCount / exposureBase * 100 : 0.0;
            row.put("conversion_rate", conversion);
            row.put("order_amount", toBigDecimal(row.get("order_amount")));
            row.put("sold_price", toBigDecimalStr(row.get("sold_price")));
            row.put("price", toBigDecimalStr(row.get("price")));
            // 状态映射：DB status -> FE status（与 XianyuGoodsService.dbToFeStatus 保持一致）
            row.put("status", dbToFeStatus(toInt(row.get("status"))));
        }

        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 单商品概览
     */
    public Map<String, Object> productSummary(Long tenantId, Long goodsId, int days) {
        if (!ALLOWED_DAYS.contains(days)) {
            throw new BizException(400, "时间范围仅支持 1/3/7/30 天");
        }
        Map<String, Object> goods = mapper.findGoodsById(tenantId, goodsId);
        if (goods == null) {
            throw new BizException(404, "商品不存在");
        }

        // 转换字段
        goods.put("sold_price", toBigDecimalStr(goods.get("sold_price")));
        goods.put("price", toBigDecimalStr(goods.get("price")));
        goods.put("status", dbToFeStatus(toInt(goods.get("status"))));

        // 时间范围内的订单聚合
        Map<String, Object> curOrders = mapper.singleGoodsOrderAggregate(tenantId, goodsId, days);
        long orderCount = toLong(curOrders.get("order_count"));
        BigDecimal orderAmount = toBigDecimal(curOrders.get("order_amount"));
        long buyerCount = toLong(curOrders.get("buyer_count"));
        long soldCount = toLong(curOrders.get("sold_count"));

        // 上一周期
        int prevDays = days * 2;
        // 复用 singleGoodsOrderAggregate，但需要筛选上一周期。为简化，直接重新查询：使用一个临时方法
        // 这里用更简单的实现：通过 dailyTrend 截取
        // 实际为性能考虑，我们直接查整个 prevDays 范围，然后从结果中减去当前周期
        Map<String, Object> prevAllOrders = mapper.singleGoodsOrderAggregate(tenantId, goodsId, prevDays);
        long prevAllOrderCount = toLong(prevAllOrders.get("order_count"));
        BigDecimal prevAllOrderAmount = toBigDecimal(prevAllOrders.get("order_amount"));
        long prevAllBuyerCount = toLong(prevAllOrders.get("buyer_count"));

        long prevOrderCount = Math.max(0, prevAllOrderCount - orderCount);
        BigDecimal prevOrderAmount = prevAllOrderAmount.subtract(orderAmount).max(BigDecimal.ZERO);
        long prevBuyerCount = Math.max(0, prevAllBuyerCount - buyerCount);

        // 转化率
        long exposure = toLong(goods.get("exposure_count"));
        long exposure30d = toLong(goods.get("exposure_count_30d"));
        long exposureBase = exposure30d > 0 ? exposure30d : exposure;
        double conversionRate = exposureBase > 0 ? (double) orderCount / exposureBase * 100 : 0.0;

        Map<String, Object> orders = new LinkedHashMap<>();
        orders.put("orderCount", orderCount);
        orders.put("orderAmount", orderAmount);
        orders.put("buyerCount", buyerCount);
        orders.put("soldCount", soldCount);
        orders.put("orderCountRatio", ratioPercent(orderCount, prevOrderCount));
        orders.put("orderAmountRatio", ratioPercent(orderAmount.doubleValue(), prevOrderAmount.doubleValue()));
        orders.put("buyerRatio", ratioPercent(buyerCount, prevBuyerCount));
        orders.put("conversionRate", conversionRate);

        goods.put("orders", orders);
        goods.put("days", days);
        goods.put("realDateRange", buildDateRange(days));
        return goods;
    }

    /**
     * 单商品按日趋势
     */
    public List<Map<String, Object>> productTrend(Long tenantId, Long goodsId, int days) {
        if (!ALLOWED_DAYS.contains(days)) {
            throw new BizException(400, "时间范围仅支持 1/3/7/30 天");
        }
        // 校验商品存在
        Map<String, Object> goods = mapper.findGoodsById(tenantId, goodsId);
        if (goods == null) {
            throw new BizException(404, "商品不存在");
        }
        List<Map<String, Object>> trend = mapper.singleGoodsDailyTrend(tenantId, goodsId, days);
        return fillMissingDates(trend, days);
    }

    /**
     * 最差商品筛选
     *
     * @param metric 筛选维度：exposure（曝光低）/ view（浏览低）/ conversion（转化低）/ order（订单少）
     * @param limit  返回数量上限（最大 200）
     */
    public List<Map<String, Object>> worstProducts(Long tenantId, Long accountId, int days,
                                                     String metric, int limit) {
        if (!ALLOWED_DAYS.contains(days)) {
            throw new BizException(400, "时间范围仅支持 1/3/7/30 天");
        }
        String sortBy;
        switch (metric == null ? "" : metric) {
            case "view":
                sortBy = "worst_view";
                break;
            case "want":
                sortBy = "worst_want";
                break;
            case "conversion":
                sortBy = "worst_conversion";
                break;
            case "order":
                sortBy = "worst_order";
                break;
            case "exposure":
            default:
                sortBy = "worst_exposure";
                break;
        }
        int safeLimit = Math.max(1, Math.min(limit <= 0 ? 20 : limit, 200));
        String orderByClause = SORT_CLAUSES.get(sortBy);
        List<Map<String, Object>> records = mapper.listGoodsWithData(tenantId, accountId, days, null, orderByClause, 0, safeLimit);
        for (Map<String, Object> row : records) {
            long orderCount = toLong(row.get("order_count"));
            long exposure = toLong(row.get("exposure_count"));
            long exposure30d = toLong(row.get("exposure_count_30d"));
            long exposureBase = exposure30d > 0 ? exposure30d : exposure;
            double conversion = exposureBase > 0 ? (double) orderCount / exposureBase * 100 : 0.0;
            row.put("conversion_rate", conversion);
            row.put("order_amount", toBigDecimal(row.get("order_amount")));
            row.put("sold_price", toBigDecimalStr(row.get("sold_price")));
            row.put("price", toBigDecimalStr(row.get("price")));
            row.put("status", dbToFeStatus(toInt(row.get("status"))));
        }
        return records;
    }

    // ===== 内部工具方法 =====

    private List<Map<String, Object>> buildTopGoods(Long tenantId, Long accountId, int days, String sortBy, int limit) {
        String orderByClause = SORT_CLAUSES.get(sortBy);
        List<Map<String, Object>> records = mapper.listGoodsWithData(tenantId, accountId, days, null, orderByClause, 0, limit);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> row : records) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("id"));
            item.put("title", row.get("title"));
            item.put("coverPic", row.get("cover_pic"));
            item.put("soldPrice", toBigDecimalStr(row.get("sold_price")));
            item.put("exposureCount", toLong(row.get("exposure_count")));
            item.put("viewCount", toLong(row.get("view_count")));
            item.put("wantCount", toLong(row.get("want_count")));
            item.put("orderCount", toLong(row.get("order_count")));
            item.put("orderAmount", toBigDecimal(row.get("order_amount")));
            item.put("soldCount", toLong(row.get("sold_count")));
            item.put("accountId", row.get("account_id"));
            result.add(item);
        }
        return result;
    }

    /**
     * 补全缺失的日期（趋势数据按日连续）
     */
    private List<Map<String, Object>> fillMissingDates(List<Map<String, Object>> trend, int days) {
        if (trend == null) trend = new ArrayList<>();
        Map<String, Map<String, Object>> dateMap = new LinkedHashMap<>();
        for (Map<String, Object> row : trend) {
            Object dsObj = row.get("ds");
            if (dsObj == null) continue;
            String ds = dsObj instanceof java.sql.Date
                    ? ((java.sql.Date) dsObj).toLocalDate().toString()
                    : String.valueOf(dsObj);
            dateMap.put(ds, row);
        }

        List<Map<String, Object>> result = new ArrayList<>();
        LocalDate today = LocalDate.now();
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd");
        for (int i = days - 1; i >= 0; i--) {
            LocalDate date = today.minusDays(i);
            String ds = date.format(fmt);
            Map<String, Object> row = dateMap.get(ds);
            if (row == null) {
                row = new LinkedHashMap<>();
                row.put("ds", ds);
                row.put("order_count", 0L);
                row.put("order_amount", BigDecimal.ZERO);
                row.put("buyer_count", 0L);
                row.put("goods_count", 0L);
            } else {
                // 标准化 ds 为字符串
                row.put("ds", ds);
                row.put("order_count", toLong(row.get("order_count")));
                row.put("order_amount", toBigDecimal(row.get("order_amount")));
                row.put("buyer_count", toLong(row.get("buyer_count")));
                row.put("goods_count", toLong(row.get("goods_count")));
            }
            result.add(row);
        }
        return result;
    }

    private String[] buildDateRange(int days) {
        LocalDate today = LocalDate.now();
        LocalDate start = today.minusDays(days - 1L);
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd");
        return new String[]{start.format(fmt), today.format(fmt)};
    }

    private static long toLong(Object value) {
        if (value == null) return 0L;
        if (value instanceof Number) return ((Number) value).longValue();
        try { return Long.parseLong(String.valueOf(value)); } catch (NumberFormatException e) { return 0L; }
    }

    private static int toInt(Object value) {
        if (value == null) return 0;
        if (value instanceof Number) return ((Number) value).intValue();
        try { return Integer.parseInt(String.valueOf(value)); } catch (NumberFormatException e) { return 0; }
    }

    private static BigDecimal toBigDecimal(Object value) {
        if (value == null) return BigDecimal.ZERO;
        if (value instanceof BigDecimal) return (BigDecimal) value;
        if (value instanceof Number) return BigDecimal.valueOf(((Number) value).doubleValue());
        try { return new BigDecimal(String.valueOf(value)); } catch (NumberFormatException e) { return BigDecimal.ZERO; }
    }

    private static String toBigDecimalStr(Object value) {
        if (value == null) return null;
        if (value instanceof BigDecimal) return ((BigDecimal) value).toPlainString();
        if (value instanceof Number) return String.valueOf(value);
        return String.valueOf(value);
    }

    private static double ratioPercent(double current, double previous) {
        if (previous == 0) {
            return current > 0 ? 100.0 : 0.0;
        }
        return (current - previous) / previous * 100.0;
    }

    private static int dbToFeStatus(Integer dbStatus) {
        if (dbStatus == null) return 1;
        switch (dbStatus) {
            case 1: return 0;  // 在售
            case 0: return 1;  // 下架
            default: return dbStatus;
        }
    }
}
