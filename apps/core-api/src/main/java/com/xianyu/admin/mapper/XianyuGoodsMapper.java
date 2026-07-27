package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuGoods;
import org.apache.ibatis.annotations.*;

import java.util.List;
import java.util.Map;

@Mapper
public interface XianyuGoodsMapper {

    @Select("<script>" +
            "SELECT * FROM xianyu_goods " +
            "WHERE tenant_id = #{tenantId} " +
            "<if test='deleted != null'>" +
            "  AND deleted = #{deleted} " +
            "</if>" +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND title LIKE CONCAT('%', #{keyword}, '%') " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND status = #{status} " +
            "</if>" +
            "<if test='excludeStatus != null'>" +
            "  AND status != #{excludeStatus} " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = xianyu_goods.tenant_id AND acc.id = xianyu_goods.account_id AND acc.deleted = 1) " +
            "ORDER BY updated_time DESC, id DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<XianyuGoods> list(@Param("tenantId") Long tenantId,
                           @Param("accountId") Long accountId,
                           @Param("keyword") String keyword,
                           @Param("status") Integer status,
                           @Param("excludeStatus") Integer excludeStatus,
                           @Param("deleted") Integer deleted,
                           @Param("offset") int offset,
                           @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM xianyu_goods " +
            "WHERE tenant_id = #{tenantId} " +
            "<if test='deleted != null'>" +
            "  AND deleted = #{deleted} " +
            "</if>" +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND title LIKE CONCAT('%', #{keyword}, '%') " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND status = #{status} " +
            "</if>" +
            "<if test='excludeStatus != null'>" +
            "  AND status != #{excludeStatus} " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = xianyu_goods.tenant_id AND acc.id = xianyu_goods.account_id AND acc.deleted = 1) " +
            "</script>")
    int count(@Param("tenantId") Long tenantId,
              @Param("accountId") Long accountId,
              @Param("keyword") String keyword,
              @Param("status") Integer status,
              @Param("excludeStatus") Integer excludeStatus,
              @Param("deleted") Integer deleted);

    @Select("SELECT * FROM xianyu_goods WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    XianyuGoods findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Insert("INSERT INTO xianyu_goods(tenant_id, account_id, external_goods_id, title, price, sold_price, cover_pic, image_url, stock, quantity, exposure_count, view_count, want_count, exposure_count_30d, view_count_30d, detail_url, detail_info, description, category, sort_order, status, deleted, created_time, gmt_create, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{externalGoodsId}, #{title}, #{price}, #{soldPrice}, #{coverPic}, #{imageUrl}, #{stock}, #{quantity}, #{exposureCount}, #{viewCount}, #{wantCount}, #{exposureCount30d}, #{viewCount30d}, #{detailUrl}, #{detailInfo}, #{description}, #{category}, #{sortOrder}, #{status}, 0, NOW(), #{gmtCreate}, NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuGoods goods);

    @Update("UPDATE xianyu_goods SET account_id = #{accountId}, external_goods_id = #{externalGoodsId}, title = #{title}, price = #{price}, sold_price = #{soldPrice}, cover_pic = #{coverPic}, " +
            "image_url = #{imageUrl}, stock = #{stock}, quantity = #{quantity}, exposure_count = #{exposureCount}, view_count = #{viewCount}, want_count = #{wantCount}, " +
            "exposure_count_30d = #{exposureCount30d}, view_count_30d = #{viewCount30d}, " +
            "detail_url = #{detailUrl}, detail_info = #{detailInfo}, description = #{description}, category = #{category}, sort_order = #{sortOrder}, status = #{status}, " +
            "gmt_create = #{gmtCreate}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int update(XianyuGoods goods);

    @Update("UPDATE xianyu_goods SET deleted = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int softDelete(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Delete("DELETE FROM xianyu_goods WHERE tenant_id = #{tenantId} AND id = #{id}")
    int hardDelete(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Select("SELECT * FROM xianyu_goods WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND external_goods_id = #{externalGoodsId} AND deleted = 0")
    XianyuGoods findByExternalGoodsId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("externalGoodsId") String externalGoodsId);

    /**
     * 更新售整自动上架开关。仅修改 auto_relist_enabled，不触碰其他字段。
     */
    @Update("UPDATE xianyu_goods SET auto_relist_enabled = #{enabled}, updated_time = NOW() " +
            "WHERE id = #{id} AND tenant_id = #{tenantId} AND deleted = 0")
    int updateAutoRelistEnabled(@Param("id") Long id,
                                @Param("enabled") Integer enabled,
                                @Param("tenantId") Long tenantId);

    @Select("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id = #{tenantId} AND deleted = 0")
    int countAll(@Param("tenantId") Long tenantId);

    @Select("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id = #{tenantId} AND status = 1 AND deleted = 0")
    int countSelling(@Param("tenantId") Long tenantId);

    @Select("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id = #{tenantId} AND status = 2 AND deleted = 0")
    int countSold(@Param("tenantId") Long tenantId);

    @Select("SELECT category, COUNT(*) AS goods_count FROM xianyu_goods WHERE tenant_id = #{tenantId} AND deleted = 0 GROUP BY category ORDER BY goods_count DESC")
    List<Map<String, Object>> countByCategory(@Param("tenantId") Long tenantId);

    @Select("<script>" +
            "SELECT goods_id, " +
            "  JSON_UNQUOTE(JSON_EXTRACT(config_json, '$.payDelivery.mode')) AS delivery_type, " +
            "  IF(JSON_UNQUOTE(JSON_EXTRACT(config_json, '$.payDelivery.enabled')) IN ('1', 'true'), 1, 0) AS status " +
            "FROM delivery_goods_config " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 AND goods_id IS NOT NULL " +
            "AND goods_id IN " +
            "<foreach collection='goodsIds' item='gid' open='(' separator=',' close=')'>" +
            "  #{gid}" +
            "</foreach>" +
            " ORDER BY goods_id, id DESC" +
            "</script>")
    List<Map<String, Object>> findDeliveryRulesForGoods(@Param("tenantId") Long tenantId, @Param("goodsIds") List<Long> goodsIds);

    @Select("<script>" +
            "SELECT DISTINCT account_id FROM auto_reply_rule " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 AND status = 1 " +
            "AND account_id IN " +
            "<foreach collection='accountIds' item='aid' open='(' separator=',' close=')'>" +
            "  #{aid}" +
            "</foreach>" +
            "</script>")
    List<Long> findAccountsWithAutoReply(@Param("tenantId") Long tenantId, @Param("accountIds") List<Long> accountIds);

    /**
     * 统计商品状态分布（全部数据，非当页）
     * 返回 Map 的 key 使用驼峰命名（与 map-underscore-to-camel-case 配置保持一致）：
     * - total: 全部未删除商品
     * - onSale: 在售商品（status=1 且非本地草稿）
     * - offShelfOrDraft: 下架/草稿（status=0 或 本地草稿）
     */
    @Select("<script>" +
            "SELECT " +
            "  COUNT(*) AS total, " +
            "  SUM(CASE WHEN status = 1 " +
            "    AND (category IS NULL OR category != '商机发掘') " +
            "    AND external_goods_id IS NOT NULL AND external_goods_id != '' " +
            "    AND external_goods_id NOT LIKE 'opp:%' " +
            "    THEN 1 ELSE 0 END) AS onSale, " +
            "  SUM(CASE WHEN status = 0 " +
            "    OR category = '商机发掘' " +
            "    OR external_goods_id IS NULL " +
            "    OR external_goods_id = '' " +
            "    OR external_goods_id LIKE 'opp:%' " +
            "    THEN 1 ELSE 0 END) AS offShelfOrDraft " +
            "FROM xianyu_goods " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = xianyu_goods.tenant_id AND acc.id = xianyu_goods.account_id AND acc.deleted = 1) " +
            "</script>")
    Map<String, Object> countStatusStats(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    /**
     * 统计已开启自动发货的商品数（delivery_goods_config.payDelivery.enabled=1）
     * 与实际发货逻辑同源（ws_delivery_handler._load_goods_delivery_rule）。
     */
    @Select("<script>" +
            "SELECT COUNT(DISTINCT g.id) " +
            "FROM xianyu_goods g " +
            "INNER JOIN delivery_goods_config dgc ON dgc.goods_id = g.id AND dgc.tenant_id = g.tenant_id AND dgc.deleted = 0 " +
            "WHERE g.tenant_id = #{tenantId} AND g.deleted = 0 " +
            "AND JSON_UNQUOTE(JSON_EXTRACT(dgc.config_json, '$.payDelivery.enabled')) IN ('1', 'true') " +
            "<if test='accountId != null'>" +
            "  AND g.account_id = #{accountId} " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = g.tenant_id AND acc.id = g.account_id AND acc.deleted = 1) " +
            "</script>")
    int countAutoDeliveryOn(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    /**
     * 统计已开启自动回复的账号数（auto_reply_rule status=1）
     */
    @Select("<script>" +
            "SELECT COUNT(DISTINCT account_id) " +
            "FROM auto_reply_rule " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 AND status = 1 " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "AND EXISTS (SELECT 1 FROM xianyu_account_auth auth WHERE auth.tenant_id = auto_reply_rule.tenant_id AND auth.account_id = auto_reply_rule.account_id AND auth.deleted = 0 AND auth.cookie_status = 1) " +
            "</script>")
    int countAutoReplyAccounts(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    /**
     * 统计存在商品级自动回复开启（xianyu_goods.auto_reply_enabled=1）的账号数，
     * 与「自动回复」页面（automation-service auto-reply-scope）同源。
     */
    @Select("<script>" +
            "SELECT COUNT(DISTINCT account_id) " +
            "FROM xianyu_goods " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 AND auto_reply_enabled = 1 AND account_id IS NOT NULL " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "AND NOT EXISTS (SELECT 1 FROM xianyu_account acc WHERE acc.tenant_id = xianyu_goods.tenant_id AND acc.id = xianyu_goods.account_id AND acc.deleted = 1) " +
            "</script>")
    int countAutoReplyEnabledAccounts(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);
}
