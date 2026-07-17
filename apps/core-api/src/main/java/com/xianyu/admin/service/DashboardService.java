package com.xianyu.admin.service;

import com.xianyu.admin.dto.*;
import com.xianyu.admin.entity.*;
import com.xianyu.admin.mapper.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class DashboardService {
    private static final Logger log = LoggerFactory.getLogger(DashboardService.class);
    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final XianyuAccountMapper accountMapper;
    private final XianyuGoodsMapper goodsMapper;
    private final XianyuTradeOrderMapper orderMapper;
    private final XianyuConversationMapper conversationMapper;
    private final AutoReplyLogMapper autoReplyLogMapper;
    private final XianyuAccountRuntimeMapper runtimeMapper;
    private final DeliveryRecordMapper deliveryRecordMapper;
    private final DashboardDailyStatMapper dailyStatMapper;
    private final OperationLogMapper operationLogMapper;
    private final XianyuAccountHealthSnapshotMapper healthSnapshotMapper;

    public DashboardService(XianyuAccountMapper accountMapper,
                            XianyuGoodsMapper goodsMapper,
                            XianyuTradeOrderMapper orderMapper,
                            XianyuConversationMapper conversationMapper,
                            AutoReplyLogMapper autoReplyLogMapper,
                            XianyuAccountRuntimeMapper runtimeMapper,
                            DeliveryRecordMapper deliveryRecordMapper,
                            DashboardDailyStatMapper dailyStatMapper,
                            OperationLogMapper operationLogMapper,
                            XianyuAccountHealthSnapshotMapper healthSnapshotMapper) {
        this.accountMapper = accountMapper;
        this.goodsMapper = goodsMapper;
        this.orderMapper = orderMapper;
        this.conversationMapper = conversationMapper;
        this.autoReplyLogMapper = autoReplyLogMapper;
        this.runtimeMapper = runtimeMapper;
        this.deliveryRecordMapper = deliveryRecordMapper;
        this.dailyStatMapper = dailyStatMapper;
        this.operationLogMapper = operationLogMapper;
        this.healthSnapshotMapper = healthSnapshotMapper;
    }

    /**
     * 仪表盘汇总统计
     */
    public DashboardSummaryVO summary(Long tenantId) {
        return summary(tenantId, null);
    }

    /**
     * 仪表盘汇总统计（支持按账号过滤）
     */
    public DashboardSummaryVO summary(Long tenantId, Long accountId) {
        DashboardSummaryVO vo = new DashboardSummaryVO();

        if (accountId == null) {
            // 账号数
            Map<String, Object> accountSummary = accountMapper.selectSummary(tenantId);
            vo.setAccountCount(getInt(accountSummary, "total"));

            // 商品总数/在售/已售
            vo.setGoodsCount(goodsMapper.countAll(tenantId));
            vo.setSellingGoodsCount(goodsMapper.countSelling(tenantId));
            vo.setTotalSoldCount(goodsMapper.countSold(tenantId));

            // 今日订单/销售额
            vo.setTodayOrderCount(orderMapper.countToday(tenantId));
            vo.setTodaySalesAmount(orderMapper.sumTodayAmount(tenantId));

            // 消息数（会话数）
            vo.setMessageCount(conversationMapper.countAll(tenantId));

            // 今日自动回复命中
            vo.setAutoReplyCount(autoReplyLogMapper.countTodayHits(tenantId));

            // WebSocket在线率
            int totalAccounts = vo.getAccountCount();
            if (totalAccounts > 0) {
                int wsOnline = runtimeMapper.countByWsStatus(tenantId, 1);
                vo.setWsOnlineRate((double) wsOnline / totalAccounts * 100);
            } else {
                vo.setWsOnlineRate(0.0);
            }

            // 发货统计
            vo.setDeliverySuccessCount(deliveryRecordMapper.countByStatus(tenantId, 1));
            vo.setDeliveryFailCount(deliveryRecordMapper.countByStatus(tenantId, 0));
            vo.setPendingDeliveryCount(deliveryRecordMapper.countPending(tenantId));
        } else {
            // 单账号视图
            vo.setAccountCount(1);

            // 商品总数/在售/已售
            vo.setGoodsCount(goodsMapper.count(tenantId, accountId, null, null, null, 0));
            vo.setSellingGoodsCount(goodsMapper.count(tenantId, accountId, null, 1, null, 0));
            vo.setTotalSoldCount(goodsMapper.count(tenantId, accountId, null, 2, null, 0));

            // 今日订单/销售额
            vo.setTodayOrderCount(orderMapper.countTodayByAccount(tenantId, accountId));
            vo.setTodaySalesAmount(orderMapper.sumTodayAmountByAccount(tenantId, accountId));

            // 消息数（会话数，按账号过滤）
            vo.setMessageCount(conversationMapper.count(tenantId, accountId, null));

            // 今日自动回复命中
            vo.setAutoReplyCount(autoReplyLogMapper.countTodayHitsByAccount(tenantId, accountId));

            // WebSocket在线率（单账号直接看 ws_status）
            XianyuAccountRuntime runtime = runtimeMapper.findByAccountId(tenantId, accountId);
            vo.setWsOnlineRate(runtime != null && runtime.getWsStatus() != null && runtime.getWsStatus() == 1 ? 100.0 : 0.0);

            // 发货统计
            vo.setDeliverySuccessCount(deliveryRecordMapper.countByStatusAndAccount(tenantId, accountId, 1));
            vo.setDeliveryFailCount(deliveryRecordMapper.countByStatusAndAccount(tenantId, accountId, 0));
            vo.setPendingDeliveryCount(deliveryRecordMapper.countPendingByAccount(tenantId, accountId));
        }

        return vo;
    }

    /**
     * 销售趋势（优先查daily_stat，无数据时实时聚合）
     */
    public SalesTrendVO salesTrend(Long tenantId, int days) {
        return salesTrend(tenantId, null, days);
    }

    /**
     * 销售趋势（支持按账号过滤，accountId 非空时实时聚合）
     */
    public SalesTrendVO salesTrend(Long tenantId, Long accountId, int days) {
        LocalDate endDate = LocalDate.now();
        LocalDate startDate = endDate.minusDays(days - 1);

        // 单账号视图或 daily_stat 无数据时实时聚合
        if (accountId == null) {
            List<DashboardDailyStat> stats = dailyStatMapper.findByDateRange(tenantId, startDate, endDate);
            if (stats != null && !stats.isEmpty()) {
                return buildTrendFromDailyStat(stats, startDate, endDate, days);
            }
        }

        return buildTrendFromRawData(tenantId, accountId, startDate, endDate, days);
    }

    /**
     * 订单消息趋势
     */
    public SalesTrendVO orderMessageTrend(Long tenantId, int days) {
        return orderMessageTrend(tenantId, null, days);
    }

    /**
     * 订单消息趋势（支持按账号过滤）
     */
    public SalesTrendVO orderMessageTrend(Long tenantId, Long accountId, int days) {
        LocalDate endDate = LocalDate.now();
        LocalDate startDate = endDate.minusDays(days - 1);

        SalesTrendVO vo = new SalesTrendVO();

        // 订单趋势
        List<Map<String, Object>> orderDaily = orderMapper.countDailyByAccount(tenantId, accountId, startDate);
        Map<String, Integer> orderMap = toDailyMap(orderDaily);

        // 消息趋势
        List<Map<String, Object>> messageDaily = conversationMapper.countDailyByAccount(tenantId, accountId, startDate);
        Map<String, Integer> messageMap = toDailyMap(messageDaily);

        // 填充所有日期
        for (int i = 0; i < days; i++) {
            String dateStr = startDate.plusDays(i).format(DATE_FMT);
            vo.getDates().add(dateStr);
            vo.getOrderCount().add(orderMap.getOrDefault(dateStr, 0));
            vo.getMessageCount().add(messageMap.getOrDefault(dateStr, 0));
            vo.getDeliveryCount().add(0);
            vo.getAiReplyCount().add(0);
        }

        return vo;
    }

    /**
     * 类目销售统计
     */
    public List<CategorySalesVO> categorySales(Long tenantId) {
        List<Map<String, Object>> rows = goodsMapper.countByCategory(tenantId);
        List<CategorySalesVO> result = new ArrayList<>();

        for (Map<String, Object> row : rows) {
            CategorySalesVO vo = new CategorySalesVO();
            Object categoryObj = row.get("category");
            String category = categoryObj != null ? String.valueOf(categoryObj) : null;
            vo.setCategoryName(category);
            vo.setGoodsCount(getInt(row, "goods_count"));

            // sales count: count orders where goods category matches
            // Simplified: use goods_count as sales indicator since we don't have direct join
            vo.setSalesCount(getInt(row, "goods_count"));

            result.add(vo);
        }

        return result;
    }

    /**
     * 账号健康
     */
    public List<AccountHealthVO> accountHealth(Long tenantId) {
        List<XianyuAccount> accounts = listAccounts(tenantId);
        List<AccountHealthVO> result = new ArrayList<>();

        for (XianyuAccount account : accounts) {
            AccountHealthVO vo = new AccountHealthVO();
            vo.setAccountId(account.getId());
            vo.setNickname(account.getNickname());
            vo.setStatus(account.getStatus());

            XianyuAccountHealthSnapshot snapshot = healthSnapshotMapper.findLatestByAccountId(tenantId, account.getId());
            if (snapshot != null) {
                vo.setHealthScore(snapshot.getHealthScore());
            } else {
                vo.setHealthScore(100); // 默认健康分
            }

            result.add(vo);
        }

        return result;
    }

    /**
     * 最近操作日志
     */
    public List<RecentLogVO> recentLogs(Long tenantId, int limit) {
        List<OperationLog> logs = operationLogMapper.list(tenantId, 0, limit);
        List<RecentLogVO> result = new ArrayList<>();

        for (OperationLog log : logs) {
            RecentLogVO vo = new RecentLogVO();
            vo.setId(log.getId());
            vo.setOperationType(log.getOperationType());
            vo.setOperationDesc(log.getOperationDesc());
            vo.setTargetType(log.getTargetType());
            vo.setCreatedTime(log.getCreatedTime());
            result.add(vo);
        }

        return result;
    }

    // ==================== 私有辅助方法 ====================

    private SalesTrendVO buildTrendFromDailyStat(List<DashboardDailyStat> stats, LocalDate startDate, LocalDate endDate, int days) {
        SalesTrendVO vo = new SalesTrendVO();

        Map<LocalDate, DashboardDailyStat> statMap = stats.stream()
                .collect(Collectors.toMap(DashboardDailyStat::getStatDate, s -> s));

        for (int i = 0; i < days; i++) {
            LocalDate date = startDate.plusDays(i);
            vo.getDates().add(date.format(DATE_FMT));

            DashboardDailyStat stat = statMap.get(date);
            if (stat != null) {
                vo.getOrderCount().add(stat.getOrderCount() != null ? stat.getOrderCount() : 0);
                vo.getMessageCount().add(stat.getMessageCount() != null ? stat.getMessageCount() : 0);
                vo.getDeliveryCount().add((stat.getDeliverySuccessCount() != null ? stat.getDeliverySuccessCount() : 0) +
                        (stat.getDeliveryFailCount() != null ? stat.getDeliveryFailCount() : 0));
                vo.getDeliverySuccess().add(stat.getDeliverySuccessCount() != null ? stat.getDeliverySuccessCount() : 0);
                vo.getDeliveryFail().add(stat.getDeliveryFailCount() != null ? stat.getDeliveryFailCount() : 0);
                vo.getAiReplyCount().add(stat.getAutoReplyCount() != null ? stat.getAutoReplyCount() : 0);
            } else {
                vo.getOrderCount().add(0);
                vo.getMessageCount().add(0);
                vo.getDeliveryCount().add(0);
                vo.getDeliverySuccess().add(0);
                vo.getDeliveryFail().add(0);
                vo.getAiReplyCount().add(0);
            }
        }

        return vo;
    }

    private SalesTrendVO buildTrendFromRawData(Long tenantId, Long accountId, LocalDate startDate, LocalDate endDate, int days) {
        SalesTrendVO vo = new SalesTrendVO();

        // 订单
        List<Map<String, Object>> orderDaily = orderMapper.countDailyByAccount(tenantId, accountId, startDate);
        Map<String, Integer> orderMap = toDailyMap(orderDaily);

        // 消息
        List<Map<String, Object>> messageDaily = conversationMapper.countDailyByAccount(tenantId, accountId, startDate);
        Map<String, Integer> messageMap = toDailyMap(messageDaily);

        // 发货
        List<Map<String, Object>> deliveryDaily = deliveryRecordMapper.countDailyByAccount(tenantId, accountId, startDate);
        Map<String, Integer> deliveryMap = toDailyMap(deliveryDaily);

        // 发货成功/失败分拆
        List<Map<String, Object>> deliverySuccessDaily = deliveryRecordMapper.countDailyByStatusAndAccount(tenantId, accountId, 1, startDate);
        Map<String, Integer> deliverySuccessMap = toDailyMap(deliverySuccessDaily);
        List<Map<String, Object>> deliveryFailDaily = deliveryRecordMapper.countDailyByStatusAndAccount(tenantId, accountId, 0, startDate);
        Map<String, Integer> deliveryFailMap = toDailyMap(deliveryFailDaily);

        // AI回复
        List<Map<String, Object>> replyDaily = autoReplyLogMapper.countDailyByAccount(tenantId, accountId, startDate);
        Map<String, Integer> replyMap = toDailyMap(replyDaily);

        for (int i = 0; i < days; i++) {
            String dateStr = startDate.plusDays(i).format(DATE_FMT);
            vo.getDates().add(dateStr);
            vo.getOrderCount().add(orderMap.getOrDefault(dateStr, 0));
            vo.getMessageCount().add(messageMap.getOrDefault(dateStr, 0));
            vo.getDeliveryCount().add(deliveryMap.getOrDefault(dateStr, 0));
            vo.getDeliverySuccess().add(deliverySuccessMap.getOrDefault(dateStr, 0));
            vo.getDeliveryFail().add(deliveryFailMap.getOrDefault(dateStr, 0));
            vo.getAiReplyCount().add(replyMap.getOrDefault(dateStr, 0));
        }

        return vo;
    }

    private Map<String, Integer> toDailyMap(List<Map<String, Object>> rows) {
        Map<String, Integer> map = new HashMap<>();
        if (rows == null) return map;
        for (Map<String, Object> row : rows) {
            Object dateObj = row.get("stat_date");
            String dateStr = dateObj != null ? String.valueOf(dateObj) : null;
            if (dateStr != null) {
                Integer count = getInt(row, "count");
                map.put(dateStr, count);
            }
        }
        return map;
    }

    private int getInt(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return 0;
        if (val instanceof Number) return ((Number) val).intValue();
        try {
            return Integer.parseInt(String.valueOf(val));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private List<XianyuAccount> listAccounts(Long tenantId) {
        // Mapper doesn't have a simple listAll, use list with large limit
        List<Map<String, Object>> rows = accountMapper.list(tenantId, null, null, 0, 10000);
        List<XianyuAccount> accounts = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            XianyuAccount account = new XianyuAccount();
            account.setId(getLongVal(row, "id"));
            account.setNickname(getString(row, "nickname"));
            account.setStatus(getInt(row, "status"));
            accounts.add(account);
        }
        return accounts;
    }

    private Long getLongVal(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Long) return (Long) val;
        if (val instanceof Number) return ((Number) val).longValue();
        return Long.parseLong(String.valueOf(val));
    }

    private String getString(Map<String, Object> map, String key) {
        Object val = map.get(key);
        return val != null ? String.valueOf(val) : null;
    }
}
