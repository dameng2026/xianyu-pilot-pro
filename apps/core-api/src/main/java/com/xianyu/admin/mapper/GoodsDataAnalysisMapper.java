package com.xianyu.admin.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

/**
 * 商品数据分析 Mapper
 *
 * 数据来源：
 *  - xianyu_goods 表：累计曝光/浏览/想要，30 天数据罗盘指标（鱼小铺账号）
 *  - xianyu_trade_order_item 表：按商品聚合订单数/订单金额
 *  - xianyu_trade_order 表：按时间范围筛选有效订单（排除待付款/已关闭）
 *
 * 关联方式：
 *  - xianyu_trade_order_item.goods_id → xianyu_goods.id（强关联，本地主键）
 *  - xianyu_trade_order_item.order_id → xianyu_trade_order.id
 *
 * 订单状态（兼容 Java VARCHAR 与 Python SmallInteger 两种存储）：
 *  - '0' 待付款 / '5' 已关闭 → 排除
 *  - '1' 已付款 / '2' 待发货 / '3' 已发货 / '4' 已完成 → 计入统计
 */
@Mapper
public interface GoodsDataAnalysisMapper {

    /**
     * 商品累计指标聚合（不受时间范围影响，反映商品全生命周期数据）
     * 仅统计真实商品（排除商机发掘草稿 opp: 前缀）
     */
    @Select("<script>" +
            "SELECT " +
            "  COUNT(*) AS goods_total, " +
            "  SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS on_sale, " +
            "  SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) AS off_shelf, " +
            "  SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS sold, " +
            "  COALESCE(SUM(CASE WHEN exposure_count_30d > 0 THEN exposure_count_30d ELSE exposure_count END), 0) AS exposure_sum, " +
            "  COALESCE(SUM(CASE WHEN view_count_30d > 0 THEN view_count_30d ELSE view_count END), 0) AS view_sum, " +
            "  COALESCE(SUM(want_count), 0) AS want_sum, " +
            "  COALESCE(SUM(CASE WHEN exposure_count_30d > 0 THEN exposure_count_30d ELSE 0 END), 0) AS exposure_30d_sum, " +
            "  COALESCE(SUM(CASE WHEN view_count_30d > 0 THEN view_count_30d ELSE 0 END), 0) AS view_30d_sum " +
            "FROM xianyu_goods " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "  AND external_goods_id IS NOT NULL AND external_goods_id != '' " +
            "  AND external_goods_id NOT LIKE 'opp:%' " +
            "  AND (category IS NULL OR category != '商机发掘') " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = xianyu_goods.tenant_id AND acc.id = xianyu_goods.account_id AND acc.deleted = 1)" +
            "</script>")
    Map<String, Object> goodsAggregate(@Param("tenantId") Long tenantId,
                                       @Param("accountId") Long accountId);

    /**
     * 统计零曝光/零浏览/零想要商品数量（运营预警用）
     */
    @Select("<script>" +
            "SELECT " +
            "  SUM(CASE WHEN COALESCE(NULLIF(exposure_count_30d, 0), exposure_count, 0) = 0 THEN 1 ELSE 0 END) AS zero_exposure, " +
            "  SUM(CASE WHEN COALESCE(NULLIF(view_count_30d, 0), view_count, 0) = 0 THEN 1 ELSE 0 END) AS zero_view, " +
            "  SUM(CASE WHEN COALESCE(want_count, 0) = 0 THEN 1 ELSE 0 END) AS zero_want " +
            "FROM xianyu_goods " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "  AND external_goods_id IS NOT NULL AND external_goods_id != '' " +
            "  AND external_goods_id NOT LIKE 'opp:%' " +
            "  AND (category IS NULL OR category != '商机发掘') " +
            "  AND status = 1 " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = xianyu_goods.tenant_id AND acc.id = xianyu_goods.account_id AND acc.deleted = 1)" +
            "</script>")
    Map<String, Object> zeroStats(@Param("tenantId") Long tenantId,
                                   @Param("accountId") Long accountId);

    /**
     * 统计在售但指定时间范围内无订单的商品数量
     */
    @Select("<script>" +
            "SELECT COUNT(*) AS no_order_count FROM xianyu_goods g " +
            "WHERE g.tenant_id = #{tenantId} AND g.deleted = 0 " +
            "  AND g.external_goods_id IS NOT NULL AND g.external_goods_id != '' " +
            "  AND g.external_goods_id NOT LIKE 'opp:%' " +
            "  AND (g.category IS NULL OR g.category != '商机发掘') " +
            "  AND g.status = 1 " +
            "<if test='accountId != null'>" +
            "  AND g.account_id = #{accountId} " +
            "</if>" +
            "  AND NOT EXISTS (SELECT 1 FROM xianyu_trade_order_item oi " +
            "    INNER JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id AND o.deleted = 0 " +
            "    WHERE oi.goods_id = g.id AND oi.tenant_id = g.tenant_id AND oi.deleted = 0 " +
            "      AND oi.goods_id IS NOT NULL " +
            "      AND o.order_status NOT IN ('0', '5', 0, 5) " +
            "      AND COALESCE(o.create_time, o.created_time) IS NOT NULL " +
            "      AND COALESCE(o.create_time, o.created_time) >= DATE_SUB(NOW(), INTERVAL #{days} DAY)" +
            "  ) " +
            "  AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = g.tenant_id AND acc.id = g.account_id AND acc.deleted = 1)" +
            "</script>")
    Map<String, Object> noOrderCount(@Param("tenantId") Long tenantId,
                                      @Param("accountId") Long accountId,
                                      @Param("days") int days);

    /**
     * 时间范围内的订单聚合（按商品聚合）
     * 返回 Map<goods_id, {order_count, order_amount, buyer_count, goods_count}>
     */
    @Select("<script>" +
            "SELECT " +
            "  oi.goods_id AS goods_id, " +
            "  COUNT(DISTINCT o.id) AS order_count, " +
            "  COALESCE(SUM(oi.goods_count * oi.goods_price), 0) AS order_amount, " +
            "  COUNT(DISTINCT o.buyer_id) AS buyer_count, " +
            "  COALESCE(SUM(oi.goods_count), 0) AS goods_count " +
            "FROM xianyu_trade_order_item oi " +
            "INNER JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id AND o.deleted = 0 " +
            "INNER JOIN xianyu_goods g ON g.id = oi.goods_id AND g.tenant_id = oi.tenant_id AND g.deleted = 0 " +
            "WHERE oi.tenant_id = #{tenantId} AND oi.deleted = 0 " +
            "  AND oi.goods_id IS NOT NULL " +
            "  AND o.order_status NOT IN ('0', '5', 0, 5) " +
            "  AND COALESCE(o.create_time, o.created_time) IS NOT NULL " +
            "  AND COALESCE(o.create_time, o.created_time) >= DATE_SUB(NOW(), INTERVAL #{days} DAY) " +
            "<if test='accountId != null'>" +
            "  AND g.account_id = #{accountId} " +
            "</if>" +
            "GROUP BY oi.goods_id" +
            "</script>")
    List<Map<String, Object>> orderAggregateByGoods(@Param("tenantId") Long tenantId,
                                                     @Param("accountId") Long accountId,
                                                     @Param("days") int days);

    /**
     * 时间范围内的总订单聚合（不按商品分组，用于全局概览）
     */
    @Select("<script>" +
            "SELECT " +
            "  COUNT(DISTINCT o.id) AS order_count, " +
            "  COALESCE(SUM(oi.goods_count * oi.goods_price), 0) AS order_amount, " +
            "  COUNT(DISTINCT o.buyer_id) AS buyer_count, " +
            "  COALESCE(SUM(oi.goods_count), 0) AS goods_count " +
            "FROM xianyu_trade_order_item oi " +
            "INNER JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id AND o.deleted = 0 " +
            "INNER JOIN xianyu_goods g ON g.id = oi.goods_id AND g.tenant_id = oi.tenant_id AND g.deleted = 0 " +
            "WHERE oi.tenant_id = #{tenantId} AND oi.deleted = 0 " +
            "  AND oi.goods_id IS NOT NULL " +
            "  AND o.order_status NOT IN ('0', '5', 0, 5) " +
            "  AND COALESCE(o.create_time, o.created_time) IS NOT NULL " +
            "  AND COALESCE(o.create_time, o.created_time) >= DATE_SUB(NOW(), INTERVAL #{days} DAY) " +
            "<if test='accountId != null'>" +
            "  AND g.account_id = #{accountId} " +
            "</if>" +
            "</script>")
    Map<String, Object> orderAggregateTotal(@Param("tenantId") Long tenantId,
                                             @Param("accountId") Long accountId,
                                             @Param("days") int days);

    /**
     * 上一周期订单聚合（用于计算环比）
     */
    @Select("<script>" +
            "SELECT " +
            "  COUNT(DISTINCT o.id) AS order_count, " +
            "  COALESCE(SUM(oi.goods_count * oi.goods_price), 0) AS order_amount, " +
            "  COUNT(DISTINCT o.buyer_id) AS buyer_count " +
            "FROM xianyu_trade_order_item oi " +
            "INNER JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id AND o.deleted = 0 " +
            "INNER JOIN xianyu_goods g ON g.id = oi.goods_id AND g.tenant_id = oi.tenant_id AND g.deleted = 0 " +
            "WHERE oi.tenant_id = #{tenantId} AND oi.deleted = 0 " +
            "  AND oi.goods_id IS NOT NULL " +
            "  AND o.order_status NOT IN ('0', '5', 0, 5) " +
            "  AND COALESCE(o.create_time, o.created_time) IS NOT NULL " +
            "  AND COALESCE(o.create_time, o.created_time) >= DATE_SUB(NOW(), INTERVAL #{prevDays} DAY) " +
            "  AND COALESCE(o.create_time, o.created_time) &lt; DATE_SUB(NOW(), INTERVAL #{days} DAY) " +
            "<if test='accountId != null'>" +
            "  AND g.account_id = #{accountId} " +
            "</if>" +
            "</script>")
    Map<String, Object> orderAggregatePrev(@Param("tenantId") Long tenantId,
                                            @Param("accountId") Long accountId,
                                            @Param("days") int days,
                                            @Param("prevDays") int prevDays);

    /**
     * 按日聚合的订单趋势（用于折线图）
     */
    @Select("<script>" +
            "SELECT " +
            "  DATE(COALESCE(o.create_time, o.created_time)) AS ds, " +
            "  COUNT(DISTINCT o.id) AS order_count, " +
            "  COALESCE(SUM(oi.goods_count * oi.goods_price), 0) AS order_amount, " +
            "  COUNT(DISTINCT o.buyer_id) AS buyer_count, " +
            "  COALESCE(SUM(oi.goods_count), 0) AS goods_count " +
            "FROM xianyu_trade_order_item oi " +
            "INNER JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id AND o.deleted = 0 " +
            "INNER JOIN xianyu_goods g ON g.id = oi.goods_id AND g.tenant_id = oi.tenant_id AND g.deleted = 0 " +
            "WHERE oi.tenant_id = #{tenantId} AND oi.deleted = 0 " +
            "  AND oi.goods_id IS NOT NULL " +
            "  AND o.order_status NOT IN ('0', '5', 0, 5) " +
            "  AND COALESCE(o.create_time, o.created_time) IS NOT NULL " +
            "  AND COALESCE(o.create_time, o.created_time) >= DATE_SUB(NOW(), INTERVAL #{days} DAY) " +
            "<if test='accountId != null'>" +
            "  AND g.account_id = #{accountId} " +
            "</if>" +
            "GROUP BY DATE(COALESCE(o.create_time, o.created_time)) " +
            "ORDER BY ds ASC" +
            "</script>")
    List<Map<String, Object>> dailyTrend(@Param("tenantId") Long tenantId,
                                          @Param("accountId") Long accountId,
                                          @Param("days") int days);

    /**
     * 商品列表（带订单数据），分页
     * 通过 LEFT JOIN 子查询在数据库层完成订单聚合，避免 N+1
     */
    @Select("<script>" +
            "SELECT g.id AS id, " +
            "  g.account_id AS account_id, " +
            "  g.external_goods_id AS external_goods_id, " +
            "  g.title AS title, " +
            "  g.cover_pic AS cover_pic, " +
            "  g.sold_price AS sold_price, " +
            "  g.price AS price, " +
            "  g.quantity AS quantity, " +
            "  g.stock AS stock, " +
            "  g.status AS status, " +
            "  COALESCE(NULLIF(g.exposure_count_30d, 0), g.exposure_count, 0) AS exposure_count, " +
            "  COALESCE(NULLIF(g.view_count_30d, 0), g.view_count, 0) AS view_count, " +
            "  g.want_count AS want_count, " +
            "  g.exposure_count_30d AS exposure_count_30d, " +
            "  g.view_count_30d AS view_count_30d, " +
            "  g.category AS category, " +
            "  g.gmt_create AS gmt_create, " +
            "  g.created_time AS created_time, " +
            "  g.auto_relist_enabled AS auto_relist_enabled, " +
            "  g.has_snapshot AS has_snapshot, " +
            "  g.can_edit AS can_edit, " +
            "  COALESCE(ord.order_count, 0) AS order_count, " +
            "  COALESCE(ord.order_amount, 0) AS order_amount, " +
            "  COALESCE(ord.buyer_count, 0) AS buyer_count, " +
            "  COALESCE(ord.goods_count, 0) AS sold_count " +
            "FROM xianyu_goods g " +
            "LEFT JOIN (" +
            "  SELECT oi.goods_id AS goods_id, " +
            "    COUNT(DISTINCT o.id) AS order_count, " +
            "    COALESCE(SUM(oi.goods_count * oi.goods_price), 0) AS order_amount, " +
            "    COUNT(DISTINCT o.buyer_id) AS buyer_count, " +
            "    COALESCE(SUM(oi.goods_count), 0) AS goods_count " +
            "  FROM xianyu_trade_order_item oi " +
            "  INNER JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id AND o.deleted = 0 " +
            "  WHERE oi.tenant_id = #{tenantId} AND oi.deleted = 0 " +
            "    AND oi.goods_id IS NOT NULL " +
            "    AND o.order_status NOT IN ('0', '5', 0, 5) " +
            "    AND COALESCE(o.create_time, o.created_time) IS NOT NULL " +
            "    AND COALESCE(o.create_time, o.created_time) >= DATE_SUB(NOW(), INTERVAL #{days} DAY) " +
            "  GROUP BY oi.goods_id" +
            ") ord ON ord.goods_id = g.id " +
            "WHERE g.tenant_id = #{tenantId} AND g.deleted = 0 " +
            "  AND g.external_goods_id IS NOT NULL AND g.external_goods_id != '' " +
            "  AND g.external_goods_id NOT LIKE 'opp:%' " +
            "  AND (g.category IS NULL OR g.category != '商机发掘') " +
            "<if test='accountId != null'>" +
            "  AND g.account_id = #{accountId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND g.title LIKE CONCAT('%', #{keyword}, '%') " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = g.tenant_id AND acc.id = g.account_id AND acc.deleted = 1) " +
            "ORDER BY ${orderByClause} " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<Map<String, Object>> listGoodsWithData(@Param("tenantId") Long tenantId,
                                                  @Param("accountId") Long accountId,
                                                  @Param("days") int days,
                                                  @Param("keyword") String keyword,
                                                  @Param("orderByClause") String orderByClause,
                                                  @Param("offset") int offset,
                                                  @Param("limit") int limit);

    /**
     * 商品列表总数（与 listGoodsWithData 同条件）
     */
    @Select("<script>" +
            "SELECT COUNT(*) FROM xianyu_goods g " +
            "WHERE g.tenant_id = #{tenantId} AND g.deleted = 0 " +
            "  AND g.external_goods_id IS NOT NULL AND g.external_goods_id != '' " +
            "  AND g.external_goods_id NOT LIKE 'opp:%' " +
            "  AND (g.category IS NULL OR g.category != '商机发掘') " +
            "<if test='accountId != null'>" +
            "  AND g.account_id = #{accountId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND g.title LIKE CONCAT('%', #{keyword}, '%') " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = g.tenant_id AND acc.id = g.account_id AND acc.deleted = 1)" +
            "</script>")
    int countGoodsWithData(@Param("tenantId") Long tenantId,
                            @Param("accountId") Long accountId,
                            @Param("keyword") String keyword);

    /**
     * 单商品基础信息（用于详情抽屉）
     */
    @Select("SELECT g.id AS id, g.account_id AS account_id, g.external_goods_id AS external_goods_id, " +
            "g.title AS title, g.cover_pic AS cover_pic, g.sold_price AS sold_price, g.price AS price, " +
            "g.quantity AS quantity, g.stock AS stock, g.status AS status, " +
            "COALESCE(NULLIF(g.exposure_count_30d, 0), g.exposure_count, 0) AS exposure_count, " +
            "COALESCE(NULLIF(g.view_count_30d, 0), g.view_count, 0) AS view_count, " +
            "g.want_count AS want_count, " +
            "g.exposure_count_30d AS exposure_count_30d, g.view_count_30d AS view_count_30d, " +
            "g.category AS category, g.detail_url AS detail_url, g.description AS description, " +
            "g.gmt_create AS gmt_create, g.created_time AS created_time, g.updated_time AS updated_time, " +
            "g.auto_relist_enabled AS auto_relist_enabled, g.has_snapshot AS has_snapshot, " +
            "g.original_quantity AS original_quantity, g.can_edit AS can_edit, g.edit_note AS edit_note, " +
            "acc.nickname AS account_nickname, acc.external_uid AS account_uid " +
            "FROM xianyu_goods g LEFT JOIN xianyu_account acc ON acc.id = g.account_id AND acc.tenant_id = g.tenant_id " +
            "WHERE g.tenant_id = #{tenantId} AND g.id = #{goodsId} AND g.deleted = 0")
    Map<String, Object> findGoodsById(@Param("tenantId") Long tenantId,
                                       @Param("goodsId") Long goodsId);

    /**
     * 单商品按日趋势
     */
    @Select("SELECT DATE(COALESCE(o.create_time, o.created_time)) AS ds, " +
            "  COUNT(DISTINCT o.id) AS order_count, " +
            "  COALESCE(SUM(oi.goods_count * oi.goods_price), 0) AS order_amount, " +
            "  COUNT(DISTINCT o.buyer_id) AS buyer_count, " +
            "  COALESCE(SUM(oi.goods_count), 0) AS goods_count " +
            "FROM xianyu_trade_order_item oi " +
            "INNER JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id AND o.deleted = 0 " +
            "WHERE oi.tenant_id = #{tenantId} AND oi.deleted = 0 " +
            "  AND oi.goods_id = #{goodsId} " +
            "  AND o.order_status NOT IN ('0', '5', 0, 5) " +
            "  AND COALESCE(o.create_time, o.created_time) IS NOT NULL " +
            "  AND COALESCE(o.create_time, o.created_time) >= DATE_SUB(NOW(), INTERVAL #{days} DAY) " +
            "GROUP BY DATE(COALESCE(o.create_time, o.created_time)) " +
            "ORDER BY ds ASC")
    List<Map<String, Object>> singleGoodsDailyTrend(@Param("tenantId") Long tenantId,
                                                      @Param("goodsId") Long goodsId,
                                                      @Param("days") int days);

    /**
     * 单商品时间范围内订单聚合
     */
    @Select("SELECT COUNT(DISTINCT o.id) AS order_count, " +
            "  COALESCE(SUM(oi.goods_count * oi.goods_price), 0) AS order_amount, " +
            "  COUNT(DISTINCT o.buyer_id) AS buyer_count, " +
            "  COALESCE(SUM(oi.goods_count), 0) AS sold_count " +
            "FROM xianyu_trade_order_item oi " +
            "INNER JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id AND o.deleted = 0 " +
            "WHERE oi.tenant_id = #{tenantId} AND oi.deleted = 0 " +
            "  AND oi.goods_id = #{goodsId} " +
            "  AND o.order_status NOT IN ('0', '5', 0, 5) " +
            "  AND COALESCE(o.create_time, o.created_time) IS NOT NULL " +
            "  AND COALESCE(o.create_time, o.created_time) >= DATE_SUB(NOW(), INTERVAL #{days} DAY)")
    Map<String, Object> singleGoodsOrderAggregate(@Param("tenantId") Long tenantId,
                                                    @Param("goodsId") Long goodsId,
                                                    @Param("days") int days);
}
