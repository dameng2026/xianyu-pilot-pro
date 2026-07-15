package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuAccountRuntime;
import org.apache.ibatis.annotations.*;

import java.time.LocalDateTime;

@Mapper
public interface XianyuAccountRuntimeMapper {

    @Select("SELECT * FROM xianyu_account_runtime WHERE (tenant_id = #{tenantId} OR tenant_id IS NULL) AND account_id = #{accountId} AND deleted = 0 ORDER BY updated_time DESC, id DESC LIMIT 1")
    XianyuAccountRuntime findByAccountId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Select("SELECT * FROM xianyu_account_runtime WHERE (tenant_id = #{tenantId} OR tenant_id IS NULL) AND account_id = #{accountId} ORDER BY deleted ASC, updated_time DESC, id DESC LIMIT 1")
    XianyuAccountRuntime findLatestByAccountIdIncludingDeleted(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Insert("INSERT INTO xianyu_account_runtime(tenant_id, account_id, online_status, ws_status, ws_latency_ms, cookie_status, last_login_time, last_heartbeat_time, last_online_time, last_sync_time, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{onlineStatus}, #{wsStatus}, #{wsLatencyMs}, #{cookieStatus}, #{lastLoginTime}, #{lastHeartbeatTime}, #{lastOnlineTime}, #{lastSyncTime}, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuAccountRuntime runtime);

    @Update("UPDATE xianyu_account_runtime SET online_status = #{onlineStatus}, ws_status = #{wsStatus}, " +
            "ws_latency_ms = #{wsLatencyMs}, last_login_time = #{lastLoginTime}, last_heartbeat_time = #{lastHeartbeatTime}, " +
            "last_online_time = #{lastOnlineTime}, last_sync_time = #{lastSyncTime}, cookie_status = #{cookieStatus}, " +
            "last_login_status_code = #{lastLoginStatusCode}, last_login_status_message = #{lastLoginStatusMessage}, " +
            "last_login_check_time = #{lastLoginCheckTime}, updated_time = NOW() " +
            "WHERE (tenant_id = #{tenantId} OR tenant_id IS NULL) AND (id = #{id} OR (#{id} IS NULL AND account_id = #{accountId}))")
    int update(XianyuAccountRuntime runtime);

    @Update("UPDATE xianyu_account_runtime SET online_status = #{onlineStatus}, ws_status = #{wsStatus}, " +
            "ws_latency_ms = #{wsLatencyMs}, last_heartbeat_time = #{heartbeatTime}, updated_time = NOW() " +
            "WHERE (tenant_id = #{tenantId} OR tenant_id IS NULL) AND account_id = #{accountId}")
    int updateHeartbeat(@Param("tenantId") Long tenantId,
                        @Param("accountId") Long accountId,
                        @Param("onlineStatus") Integer onlineStatus,
                        @Param("wsStatus") Integer wsStatus,
                        @Param("wsLatencyMs") Integer wsLatencyMs,
                        @Param("heartbeatTime") LocalDateTime heartbeatTime);

    @Update("UPDATE xianyu_account_runtime SET deleted = 1, online_status = 0, ws_status = 0, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0")
    int softDeleteByAccountId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Update("UPDATE xianyu_account_runtime SET deleted = 0, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 1")
    int restoreByAccountId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Update("UPDATE xianyu_account_runtime SET cookie_status = #{cookieStatus}, last_login_status_code = #{code}, last_login_status_message = #{message}, " +
            "last_login_check_time = #{checkedAt}, updated_time = NOW() " +
            "WHERE (tenant_id = #{tenantId} OR tenant_id IS NULL) AND account_id = #{accountId}")
    int updateLoginStatus(@Param("tenantId") Long tenantId,
                          @Param("accountId") Long accountId,
                          @Param("cookieStatus") Integer cookieStatus,
                          @Param("code") String code,
                          @Param("message") String message,
                          @Param("checkedAt") LocalDateTime checkedAt);

    @Select("SELECT COUNT(*) FROM xianyu_account_runtime WHERE tenant_id = #{tenantId} AND ws_status = #{wsStatus}")
    int countByWsStatus(@Param("tenantId") Long tenantId, @Param("wsStatus") Integer wsStatus);
}
