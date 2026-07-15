package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuMessage;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface XianyuMessageMapper {

    @Select("SELECT * FROM xianyu_message WHERE tenant_id = #{tenantId} AND conversation_id = #{conversationId} AND deleted = 0 ORDER BY created_time ASC LIMIT #{offset}, #{limit}")
    List<XianyuMessage> listByConversationId(@Param("tenantId") Long tenantId, @Param("conversationId") Long conversationId, @Param("offset") int offset, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM xianyu_message WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0")
    int count(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Select("SELECT COUNT(*) FROM xianyu_message WHERE tenant_id = #{tenantId} AND conversation_id = #{conversationId} AND deleted = 0")
    int countByConversationId(@Param("tenantId") Long tenantId, @Param("conversationId") Long conversationId);

    @Insert("INSERT INTO xianyu_message(tenant_id, account_id, conversation_id, from_user_id, to_user_id, content, message_type, direction, is_auto_reply, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{conversationId}, #{fromUserId}, #{toUserId}, #{content}, #{messageType}, #{direction}, #{isAutoReply}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuMessage message);
}
