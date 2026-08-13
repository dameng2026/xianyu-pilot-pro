package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.AutoReplyRule;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface AutoReplyRuleMapper {

    @Select("<script>SELECT * FROM auto_reply_rule WHERE tenant_id = #{tenantId} AND deleted = 0 <if test='accountId != null'> AND account_id = #{accountId} </if> ORDER BY priority ASC LIMIT #{offset}, #{limit}</script>")
    List<AutoReplyRule> list(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("offset") int offset, @Param("limit") int limit);

    @Select("<script>SELECT COUNT(*) FROM auto_reply_rule WHERE tenant_id = #{tenantId} AND deleted = 0 <if test='accountId != null'> AND account_id = #{accountId} </if></script>")
    int count(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Select("SELECT * FROM auto_reply_rule WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    AutoReplyRule findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Insert("INSERT INTO auto_reply_rule(tenant_id, account_id, xy_goods_id, rule_name, match_type, match_keywords, reply_content, reply_image, reply_mode, status, priority, safe_mode, handoff_keywords, price_floor, max_daily_replies, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{xyGoodsId}, #{ruleName}, #{matchType}, #{matchKeywords}, #{replyContent}, #{replyImage}, #{replyMode}, #{status}, #{priority}, #{safeMode}, #{handoffKeywords}, #{priceFloor}, #{maxDailyReplies}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(AutoReplyRule rule);

    @Update("UPDATE auto_reply_rule SET account_id = #{accountId}, xy_goods_id = #{xyGoodsId}, rule_name = #{ruleName}, match_type = #{matchType}, " +
            "match_keywords = #{matchKeywords}, reply_content = #{replyContent}, reply_image = #{replyImage}, reply_mode = #{replyMode}, " +
            "status = #{status}, priority = #{priority}, safe_mode = #{safeMode}, handoff_keywords = #{handoffKeywords}, " +
            "price_floor = #{priceFloor}, max_daily_replies = #{maxDailyReplies}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int update(AutoReplyRule rule);

    @Update("UPDATE auto_reply_rule SET deleted = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int softDelete(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Select("<script>SELECT * FROM auto_reply_rule WHERE tenant_id = #{tenantId} AND status = #{status} AND deleted = 0 <if test='accountId != null'> AND account_id = #{accountId} </if> ORDER BY priority ASC</script>")
    List<AutoReplyRule> findByAccountIdAndStatus(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("status") Integer status);
}
