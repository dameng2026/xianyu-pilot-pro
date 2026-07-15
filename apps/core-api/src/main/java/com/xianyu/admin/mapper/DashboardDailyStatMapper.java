package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.DashboardDailyStat;
import org.apache.ibatis.annotations.*;

import java.time.LocalDate;
import java.util.List;

@Mapper
public interface DashboardDailyStatMapper {

    @Select("SELECT * FROM dashboard_daily_stat WHERE tenant_id = #{tenantId} AND deleted = 0 AND stat_date >= #{startDate} AND stat_date <= #{endDate} ORDER BY stat_date ASC")
    List<DashboardDailyStat> findByDateRange(@Param("tenantId") Long tenantId, @Param("startDate") LocalDate startDate, @Param("endDate") LocalDate endDate);

    @Select("SELECT * FROM dashboard_daily_stat WHERE tenant_id = #{tenantId} AND stat_date = #{statDate} AND deleted = 0 LIMIT 1")
    DashboardDailyStat findByDate(@Param("tenantId") Long tenantId, @Param("statDate") LocalDate statDate);

    @Insert("INSERT INTO dashboard_daily_stat(tenant_id, stat_date, account_count, goods_count, selling_goods_count, order_count, order_amount, message_count, auto_reply_count, delivery_success_count, delivery_fail_count, ws_online_rate, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{statDate}, #{accountCount}, #{goodsCount}, #{sellingGoodsCount}, #{orderCount}, #{orderAmount}, #{messageCount}, #{autoReplyCount}, #{deliverySuccessCount}, #{deliveryFailCount}, #{wsOnlineRate}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(DashboardDailyStat stat);

    @Insert("INSERT INTO dashboard_daily_stat(tenant_id, stat_date, account_count, goods_count, selling_goods_count, order_count, order_amount, message_count, auto_reply_count, delivery_success_count, delivery_fail_count, ws_online_rate, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{statDate}, #{accountCount}, #{goodsCount}, #{sellingGoodsCount}, #{orderCount}, #{orderAmount}, #{messageCount}, #{autoReplyCount}, #{deliverySuccessCount}, #{deliveryFailCount}, #{wsOnlineRate}, 0, NOW(), NOW()) " +
            "ON DUPLICATE KEY UPDATE " +
            "account_count = VALUES(account_count), goods_count = VALUES(goods_count), selling_goods_count = VALUES(selling_goods_count), " +
            "order_count = VALUES(order_count), order_amount = VALUES(order_amount), message_count = VALUES(message_count), " +
            "auto_reply_count = VALUES(auto_reply_count), delivery_success_count = VALUES(delivery_success_count), " +
            "delivery_fail_count = VALUES(delivery_fail_count), ws_online_rate = VALUES(ws_online_rate), updated_time = NOW()")
    int upsert(DashboardDailyStat stat);
}
