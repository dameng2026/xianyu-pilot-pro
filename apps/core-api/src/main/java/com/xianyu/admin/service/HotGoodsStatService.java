package com.xianyu.admin.service;

import com.xianyu.admin.entity.HotGoodsStat;
import com.xianyu.admin.mapper.HotGoodsStatMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * 热销商品统计服务
 * 负责每日统计数据的ETL（抽取、转换、加载）和查询
 */
@Service
public class HotGoodsStatService {
    private static final Logger log = LoggerFactory.getLogger(HotGoodsStatService.class);

    private final HotGoodsStatMapper statMapper;

    public HotGoodsStatService(HotGoodsStatMapper statMapper) {
        this.statMapper = statMapper;
    }

    /**
     * 执行每日热销商品统计
     * 扫描所有在售商品，筛选出销量大于5的商品并存入统计表
     * 阈值默认5件，可配置
     */
    @Transactional
    public int refreshDailyStats(Long tenantId) {
        return refreshDailyStats(tenantId, 5);
    }

    /**
     * 执行每日热销商品统计（可指定销量阈值）
     */
    @Transactional
    public int refreshDailyStats(Long tenantId, int minSales) {
        LocalDate today = LocalDate.now();
        log.info("开始刷新热销商品统计数据: tenantId={}, date={}, minSales={}", tenantId, today, minSales);

        // 1. 清除当日的旧数据
        statMapper.deleteByDate(today);

        // 2. 查询销量大于阈值的商品
        List<Map<String, Object>> highSalesGoods = statMapper.findGoodsWithHighSales(minSales);
        log.info("查询到 {} 个符合条件的商品", highSalesGoods.size());

        // 3. 插入统计记录
        int inserted = 0;
        for (Map<String, Object> goods : highSalesGoods) {
            HotGoodsStat stat = new HotGoodsStat();
            stat.setTenantId(toLong(goods.get("tenant_id")));
            stat.setGoodsId(toLong(goods.get("goods_id")));
            stat.setAccountId(toLong(goods.get("account_id")));
            stat.setTitle(toString(goods.get("title")));
            stat.setPrice(toString(goods.get("price")));
            stat.setCoverPic(toString(goods.get("cover_pic")));
            stat.setDailySales(toInt(goods.get("daily_sales")));
            stat.setStatDate(today);
            statMapper.insert(stat);
            inserted++;
        }

        log.info("热销商品统计刷新完成: tenantId={}, date={}, inserted={}", tenantId, today, inserted);
        return inserted;
    }

    /**
     * 分页查询热销商品统计
     */
    public List<HotGoodsStat> page(Long tenantId, LocalDate statDate, int offset, int limit) {
        return statMapper.list(tenantId, statDate, offset, limit);
    }

    /**
     * 查询总数
     */
    public int count(Long tenantId, LocalDate statDate) {
        return statMapper.count(tenantId, statDate);
    }

    /**
     * 查询指定日期的所有热销商品
     */
    public List<HotGoodsStat> listByDate(Long tenantId, LocalDate statDate) {
        return statMapper.listByDate(tenantId, statDate);
    }

    /**
     * 获取所有有统计数据的日期
     */
    public List<LocalDate> listDistinctDates(Long tenantId) {
        return statMapper.listDistinctDates(tenantId);
    }

    // ==================== 辅助方法 ====================

    private Long toLong(Object val) {
        if (val == null) return 0L;
        if (val instanceof Number) return ((Number) val).longValue();
        try { return Long.parseLong(String.valueOf(val)); } catch (NumberFormatException e) { return 0L; }
    }

    private Integer toInt(Object val) {
        if (val == null) return 0;
        if (val instanceof Number) return ((Number) val).intValue();
        try { return Integer.parseInt(String.valueOf(val)); } catch (NumberFormatException e) { return 0; }
    }

    private String toString(Object val) {
        return val != null ? String.valueOf(val) : null;
    }
}