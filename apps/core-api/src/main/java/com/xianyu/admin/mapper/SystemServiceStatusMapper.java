package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.SystemServiceStatus;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface SystemServiceStatusMapper {

    @Select("SELECT * FROM system_service_status WHERE deleted = 0 ORDER BY id ASC")
    List<SystemServiceStatus> listAll();

    @Select("SELECT * FROM system_service_status WHERE id = #{id} AND deleted = 0")
    SystemServiceStatus findById(@Param("id") Long id);

    @Insert("INSERT INTO system_service_status(tenant_id, node_name, node_ip, app_version, status, cpu_usage, memory_usage, disk_usage, last_heartbeat_time, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{nodeName}, #{nodeIp}, #{appVersion}, #{status}, #{cpuUsage}, #{memoryUsage}, #{diskUsage}, #{lastHeartbeatTime}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(SystemServiceStatus node);

    @Update("UPDATE system_service_status SET node_name = #{nodeName}, node_ip = #{nodeIp}, " +
            "app_version = #{appVersion}, status = #{status}, cpu_usage = #{cpuUsage}, memory_usage = #{memoryUsage}, " +
            "disk_usage = #{diskUsage}, last_heartbeat_time = #{lastHeartbeatTime}, updated_time = NOW() " +
            "WHERE id = #{id} AND deleted = 0")
    int update(SystemServiceStatus node);
}
