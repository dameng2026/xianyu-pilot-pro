package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.DeliveryRecord;
import org.apache.ibatis.annotations.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@Mapper
public interface DeliveryRecordMapper {

    @Select("SELECT * FROM delivery_record WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0 ORDER BY created_time DESC LIMIT #{offset}, #{limit}")
    List<DeliveryRecord> list(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("offset") int offset, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM delivery_record WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0")
    int count(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Select("SELECT COUNT(*) FROM delivery_record WHERE tenant_id = #{tenantId} AND status = #{status} AND deleted = 0")
    int countByStatus(@Param("tenantId") Long tenantId, @Param("status") Integer status);

    @Insert("INSERT INTO delivery_record(tenant_id, account_id, order_id, rule_id, delivery_type, content, status, retry_count, fail_reason, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{orderId}, #{ruleId}, #{deliveryType}, #{content}, #{status}, #{retryCount}, #{failReason}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(DeliveryRecord record);

    @Select("SELECT COUNT(*) FROM delivery_record WHERE tenant_id = #{tenantId} AND deleted = 0 AND DATE(created_time) = CURDATE()")
    int countToday(@Param("tenantId") Long tenantId);

    @Select("SELECT COUNT(*) FROM delivery_record WHERE tenant_id = #{tenantId} AND deleted = 0 AND status = 0")
    int countPending(@Param("tenantId") Long tenantId);

    @Select("SELECT DATE(created_time) AS stat_date, COUNT(*) AS count FROM delivery_record WHERE tenant_id = #{tenantId} AND deleted = 0 AND created_time >= #{startDate} GROUP BY DATE(created_time) ORDER BY stat_date ASC")
    List<Map<String, Object>> countDaily(@Param("tenantId") Long tenantId, @Param("startDate") LocalDate startDate);

    @Select("SELECT DATE(created_time) AS stat_date, COUNT(*) AS count FROM delivery_record WHERE tenant_id = #{tenantId} AND deleted = 0 AND status = #{status} AND created_time >= #{startDate} GROUP BY DATE(created_time) ORDER BY stat_date ASC")
    List<Map<String, Object>> countDailyByStatus(@Param("tenantId") Long tenantId, @Param("status") Integer status, @Param("startDate") LocalDate startDate);
}
