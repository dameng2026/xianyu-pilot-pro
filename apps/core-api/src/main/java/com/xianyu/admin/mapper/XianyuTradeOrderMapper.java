package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuTradeOrder;
import org.apache.ibatis.annotations.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@Mapper
public interface XianyuTradeOrderMapper {

    @Select("<script>" +
            "SELECT * FROM xianyu_trade_order " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (buyer_name LIKE CONCAT('%', #{keyword}, '%') OR external_order_id LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND order_status = #{status} " +
            "</if>" +
            "<if test='buyerId != null and buyerId != \"\"'>" +
            "  AND (buyer_id = #{buyerId} OR buyer_id = CONCAT(#{buyerId}, '@goofish')) " +
            "</if>" +
            "ORDER BY created_time DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<XianyuTradeOrder> list(@Param("tenantId") Long tenantId,
                                @Param("accountId") Long accountId,
                                @Param("keyword") String keyword,
                                @Param("status") Integer status,
                                @Param("buyerId") String buyerId,
                                @Param("offset") int offset,
                                @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM xianyu_trade_order " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (buyer_name LIKE CONCAT('%', #{keyword}, '%') OR external_order_id LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND order_status = #{status} " +
            "</if>" +
            "<if test='buyerId != null and buyerId != \"\"'>" +
            "  AND (buyer_id = #{buyerId} OR buyer_id = CONCAT(#{buyerId}, '@goofish')) " +
            "</if>" +
            "</script>")
    int count(@Param("tenantId") Long tenantId,
              @Param("accountId") Long accountId,
              @Param("keyword") String keyword,
              @Param("status") Integer status,
              @Param("buyerId") String buyerId);

    @Select("SELECT * FROM xianyu_trade_order WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    XianyuTradeOrder findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Insert("INSERT INTO xianyu_trade_order(tenant_id, account_id, external_order_id, order_status, total_amount, buyer_name, buyer_id, create_time, pay_time, ship_time, confirm_time, buyer_message, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{externalOrderId}, #{orderStatus}, #{totalAmount}, #{buyerName}, #{buyerId}, #{createTime}, #{payTime}, #{shipTime}, #{confirmTime}, #{buyerMessage}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuTradeOrder order);

    @Update("UPDATE xianyu_trade_order SET order_status = #{orderStatus}, total_amount = #{totalAmount}, " +
            "buyer_name = #{buyerName}, buyer_id = #{buyerId}, pay_time = #{payTime}, ship_time = #{shipTime}, " +
            "confirm_time = #{confirmTime}, buyer_message = #{buyerMessage}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int update(XianyuTradeOrder order);

    @Update("UPDATE xianyu_trade_order SET deleted = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int softDelete(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Select("SELECT * FROM xianyu_trade_order WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND external_order_id = #{externalOrderId} AND deleted = 0")
    XianyuTradeOrder findByExternalOrderId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("externalOrderId") String externalOrderId);

    @Select("SELECT COUNT(*) FROM xianyu_trade_order WHERE tenant_id = #{tenantId} AND deleted = 0 AND DATE(COALESCE(create_time, created_time)) = CURDATE()")
    int countToday(@Param("tenantId") Long tenantId);

    @Select("SELECT COALESCE(SUM(total_amount), 0) FROM xianyu_trade_order WHERE tenant_id = #{tenantId} AND deleted = 0 AND order_status IN (1, 2, 3, 4) AND DATE(COALESCE(pay_time, create_time, created_time)) = CURDATE()")
    BigDecimal sumTodayAmount(@Param("tenantId") Long tenantId);

    @Select("SELECT DATE(COALESCE(create_time, created_time)) AS stat_date, COUNT(*) AS count FROM xianyu_trade_order WHERE tenant_id = #{tenantId} AND deleted = 0 AND COALESCE(create_time, created_time) >= #{startDate} GROUP BY DATE(COALESCE(create_time, created_time)) ORDER BY stat_date ASC")
    List<Map<String, Object>> countDaily(@Param("tenantId") Long tenantId, @Param("startDate") java.time.LocalDate startDate);

    @Update("UPDATE xianyu_trade_order SET delivery_status = #{deliveryStatus}, delivery_time = NOW(), ship_time = NOW(), order_status = #{orderStatus}, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int updateDeliveryStatus(@Param("tenantId") Long tenantId, @Param("id") Long id, @Param("deliveryStatus") Integer deliveryStatus, @Param("orderStatus") Integer orderStatus);
}
