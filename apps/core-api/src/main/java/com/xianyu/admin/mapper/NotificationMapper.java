package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.Notification;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface NotificationMapper {

    @Select("SELECT * FROM notification WHERE tenant_id = #{tenantId} AND deleted = 0 ORDER BY created_time DESC LIMIT #{limit}")
    List<Notification> listRecent(@Param("tenantId") Long tenantId, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM notification WHERE tenant_id = #{tenantId} AND deleted = 0")
    int count(@Param("tenantId") Long tenantId);

    @Insert("INSERT INTO notification(tenant_id, title, content, type, status, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{title}, #{content}, #{type}, #{status}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(Notification notification);

    @Update("UPDATE notification SET status = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int markRead(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Update("UPDATE notification SET status = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND deleted = 0")
    int markAllRead(@Param("tenantId") Long tenantId);
}
