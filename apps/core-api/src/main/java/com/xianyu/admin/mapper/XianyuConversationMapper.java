package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuConversation;
import org.apache.ibatis.annotations.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@Mapper
public interface XianyuConversationMapper {

    @Select("<script>" +
            "SELECT * FROM xianyu_conversation " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (buyer_name LIKE CONCAT('%', #{keyword}, '%') OR goods_title LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "ORDER BY last_message_time DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<XianyuConversation> list(@Param("tenantId") Long tenantId,
                                  @Param("accountId") Long accountId,
                                  @Param("keyword") String keyword,
                                  @Param("offset") int offset,
                                  @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM xianyu_conversation " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='accountId != null'>" +
            "  AND account_id = #{accountId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (buyer_name LIKE CONCAT('%', #{keyword}, '%') OR goods_title LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "</script>")
    int count(@Param("tenantId") Long tenantId,
              @Param("accountId") Long accountId,
              @Param("keyword") String keyword);

    @Select("SELECT * FROM xianyu_conversation WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    XianyuConversation findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Insert("INSERT INTO xianyu_conversation(tenant_id, account_id, external_buyer_id, buyer_name, buyer_avatar, goods_title, goods_id, status, last_message_time, last_message_content, unread_count, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{externalBuyerId}, #{buyerName}, #{buyerAvatar}, #{goodsTitle}, #{goodsId}, #{status}, #{lastMessageTime}, #{lastMessageContent}, #{unreadCount}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuConversation conversation);

    @Update("UPDATE xianyu_conversation SET buyer_name = #{buyerName}, buyer_avatar = #{buyerAvatar}, " +
            "goods_title = #{goodsTitle}, goods_id = #{goodsId}, status = #{status}, " +
            "last_message_time = #{lastMessageTime}, last_message_content = #{lastMessageContent}, " +
            "unread_count = #{unreadCount}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int update(XianyuConversation conversation);

    @Select("SELECT * FROM xianyu_conversation WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND external_buyer_id = #{externalBuyerId} AND deleted = 0 LIMIT 1")
    XianyuConversation findByExternalBuyerId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("externalBuyerId") String externalBuyerId);


    @Update("UPDATE xianyu_conversation SET status = #{status}, unread_count = CASE WHEN #{clearUnread} = 1 THEN 0 ELSE unread_count END, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int updateStatus(@Param("tenantId") Long tenantId,
                     @Param("id") Long id,
                     @Param("status") Integer status,
                     @Param("clearUnread") Integer clearUnread);

    @Update("UPDATE xianyu_conversation SET unread_count = 0, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int markRead(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Select("SELECT COUNT(*) FROM xianyu_conversation WHERE tenant_id = #{tenantId} AND deleted = 0")
    int countAll(@Param("tenantId") Long tenantId);

    @Select("SELECT DATE(last_message_time) AS stat_date, COUNT(*) AS count FROM xianyu_conversation WHERE tenant_id = #{tenantId} AND deleted = 0 AND last_message_time >= #{startDate} GROUP BY DATE(last_message_time) ORDER BY stat_date ASC")
    List<Map<String, Object>> countDaily(@Param("tenantId") Long tenantId, @Param("startDate") LocalDate startDate);

    @Select("<script>" +
            "SELECT DATE(last_message_time) AS stat_date, COUNT(*) AS count " +
            "FROM xianyu_conversation " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 AND last_message_time >= #{startDate} " +
            "<if test='accountId != null'>AND account_id = #{accountId}</if>" +
            "GROUP BY DATE(last_message_time) ORDER BY stat_date ASC" +
            "</script>")
    List<Map<String, Object>> countDailyByAccount(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("startDate") LocalDate startDate);
}
