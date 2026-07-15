package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.AutoReplyLog;
import org.apache.ibatis.annotations.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@Mapper
public interface AutoReplyLogMapper {

    @Select("<script>SELECT * FROM auto_reply_log WHERE tenant_id = #{tenantId} AND deleted=0 <if test='accountId != null'>AND account_id = #{accountId}</if> ORDER BY created_time DESC LIMIT #{offset}, #{limit}</script>")
    List<AutoReplyLog> list(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("offset") int offset, @Param("limit") int limit);

    @Select("<script>SELECT COUNT(*) FROM auto_reply_log WHERE tenant_id = #{tenantId} AND deleted=0 <if test='accountId != null'>AND account_id = #{accountId}</if></script>")
    int count(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Insert("INSERT INTO auto_reply_log(tenant_id, account_id, conversation_id, rule_id, trigger_message, reply_content, hit_type, status, fail_reason, action, safety_reasons, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{conversationId}, #{ruleId}, #{triggerMessage}, #{replyContent}, #{hitType}, #{status}, #{failReason}, #{action}, #{safetyReasons}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(AutoReplyLog log);

    @Select("SELECT COUNT(*) FROM auto_reply_log WHERE tenant_id = #{tenantId} AND deleted=0 AND DATE(created_time) = CURDATE()")
    int countTodayHits(@Param("tenantId") Long tenantId);

    @Select("SELECT COUNT(*) FROM auto_reply_log WHERE tenant_id = #{tenantId} AND deleted=0 AND rule_id=#{ruleId} AND DATE(created_time)=CURDATE()")
    int countTodayByRule(@Param("tenantId") Long tenantId, @Param("ruleId") Long ruleId);

    @Select("SELECT DATE(created_time) AS stat_date, COUNT(*) AS count FROM auto_reply_log WHERE tenant_id = #{tenantId} AND deleted=0 AND created_time >= #{startDate} GROUP BY DATE(created_time) ORDER BY stat_date ASC")
    List<Map<String, Object>> countDaily(@Param("tenantId") Long tenantId, @Param("startDate") LocalDate startDate);

    @Select("SELECT action, COUNT(*) AS count FROM auto_reply_log WHERE tenant_id=#{tenantId} AND deleted=0 AND created_time >= #{startDate} GROUP BY action")
    List<Map<String, Object>> countByAction(@Param("tenantId") Long tenantId, @Param("startDate") LocalDate startDate);
}