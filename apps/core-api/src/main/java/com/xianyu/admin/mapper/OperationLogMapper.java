package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.OperationLog;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface OperationLogMapper {

    @Select("<script>SELECT * FROM operation_log WHERE deleted = 0 <if test='tenantId != null'> AND tenant_id = #{tenantId} </if> ORDER BY created_time DESC LIMIT #{offset}, #{limit}</script>")
    List<OperationLog> list(@Param("tenantId") Long tenantId, @Param("offset") int offset, @Param("limit") int limit);

    @Select("<script>SELECT COUNT(*) FROM operation_log WHERE deleted = 0 <if test='tenantId != null'> AND tenant_id = #{tenantId} </if></script>")
    int count(@Param("tenantId") Long tenantId);

    @Insert("INSERT INTO operation_log(tenant_id, user_id, operation_type, operation_desc, target_type, target_id, ip_address, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{userId}, #{operationType}, #{operationDesc}, #{targetType}, #{targetId}, #{ipAddress}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(OperationLog log);

    @Select("<script>" +
            "SELECT * FROM operation_log WHERE deleted = 0 <if test='tenantId != null'> AND tenant_id = #{tenantId} </if> " +
            "<if test='userId != null'> AND user_id = #{userId} </if>" +
            "<if test='operationType != null and operationType != \"\"'> AND operation_type = #{operationType} </if>" +
            "<if test='targetType != null and targetType != \"\"'> AND target_type = #{targetType} </if>" +
            "<if test='targetId != null'> AND target_id = #{targetId} </if>" +
            "<if test='keyword != null and keyword != \"\"'> AND (operation_desc LIKE CONCAT('%', #{keyword}, '%') OR operation_type LIKE CONCAT('%', #{keyword}, '%')) </if>" +
            "ORDER BY created_time DESC, id DESC LIMIT #{offset}, #{limit}" +
            "</script>")
    List<OperationLog> listFiltered(@Param("tenantId") Long tenantId,
                                    @Param("userId") Long userId,
                                    @Param("operationType") String operationType,
                                    @Param("targetType") String targetType,
                                    @Param("targetId") Long targetId,
                                    @Param("keyword") String keyword,
                                    @Param("offset") int offset,
                                    @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM operation_log WHERE deleted = 0 <if test='tenantId != null'> AND tenant_id = #{tenantId} </if> " +
            "<if test='userId != null'> AND user_id = #{userId} </if>" +
            "<if test='operationType != null and operationType != \"\"'> AND operation_type = #{operationType} </if>" +
            "<if test='targetType != null and targetType != \"\"'> AND target_type = #{targetType} </if>" +
            "<if test='targetId != null'> AND target_id = #{targetId} </if>" +
            "<if test='keyword != null and keyword != \"\"'> AND (operation_desc LIKE CONCAT('%', #{keyword}, '%') OR operation_type LIKE CONCAT('%', #{keyword}, '%')) </if>" +
            "</script>")
    int countFiltered(@Param("tenantId") Long tenantId,
                      @Param("userId") Long userId,
                      @Param("operationType") String operationType,
                      @Param("targetType") String targetType,
                      @Param("targetId") Long targetId,
                      @Param("keyword") String keyword);
}
