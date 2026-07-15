package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.HotGoodsStat;
import org.apache.ibatis.annotations.*;

import java.time.LocalDate;
import java.util.List;

@Mapper
public interface HotGoodsStatMapper {

    @Select("<script>" +
            "SELECT * FROM hot_goods_stat " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='statDate != null'>" +
            "  AND stat_date = #{statDate} " +
            "</if>" +
            "ORDER BY daily_sales DESC, created_time DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<HotGoodsStat> list(@Param("tenantId") Long tenantId,
                            @Param("statDate") LocalDate statDate,
                            @Param("offset") int offset,
                            @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM hot_goods_stat " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='statDate != null'>" +
            "  AND stat_date = #{statDate} " +
            "</if>" +
            "</script>")
    int count(@Param("tenantId") Long tenantId,
              @Param("statDate") LocalDate statDate);

    @Select("SELECT * FROM hot_goods_stat WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    HotGoodsStat findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Insert("INSERT INTO hot_goods_stat(tenant_id, goods_id, account_id, title, price, cover_pic, daily_sales, stat_date, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{goodsId}, #{accountId}, #{title}, #{price}, #{coverPic}, #{dailySales}, #{statDate}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(HotGoodsStat stat);

    @Update("UPDATE hot_goods_stat SET title = #{title}, price = #{price}, cover_pic = #{coverPic}, " +
            "daily_sales = #{dailySales}, stat_date = #{statDate}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id}")
    int update(HotGoodsStat stat);

    @Update("UPDATE hot_goods_stat SET deleted = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id}")
    int softDelete(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Select("SELECT COUNT(*) FROM hot_goods_stat WHERE tenant_id = #{tenantId} AND stat_date = #{statDate} AND deleted = 0")
    int countByDate(@Param("tenantId") Long tenantId, @Param("statDate") LocalDate statDate);

    @Select("SELECT * FROM hot_goods_stat WHERE tenant_id = #{tenantId} AND goods_id = #{goodsId} AND stat_date = #{statDate} AND deleted = 0")
    HotGoodsStat findByGoodsIdAndDate(@Param("tenantId") Long tenantId,
                                       @Param("goodsId") Long goodsId,
                                       @Param("statDate") LocalDate statDate);

    @Select("SELECT * FROM hot_goods_stat WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "AND stat_date = #{statDate} " +
            "ORDER BY daily_sales DESC")
    List<HotGoodsStat> listByDate(@Param("tenantId") Long tenantId, @Param("statDate") LocalDate statDate);

    @Select("SELECT DISTINCT stat_date FROM hot_goods_stat WHERE tenant_id = #{tenantId} AND deleted = 0 ORDER BY stat_date DESC")
    List<LocalDate> listDistinctDates(@Param("tenantId") Long tenantId);

    /**
     * 查询所有租户下所有商品中 quantity > 5 的商品（用于ETL统计）
     */
    @Select("SELECT g.id AS goods_id, g.tenant_id, g.account_id, g.title, g.price, g.cover_pic, " +
            "COALESCE(g.quantity, 0) AS daily_sales " +
            "FROM xianyu_goods g " +
            "WHERE g.deleted = 0 AND g.status = 0 " +
            "AND COALESCE(g.quantity, 0) > #{minSales}")
    List<java.util.Map<String, Object>> findGoodsWithHighSales(@Param("minSales") int minSales);

    @Delete("DELETE FROM hot_goods_stat WHERE stat_date = #{statDate}")
    int deleteByDate(@Param("statDate") LocalDate statDate);
}