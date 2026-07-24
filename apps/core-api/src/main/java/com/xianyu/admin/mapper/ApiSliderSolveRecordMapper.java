package com.xianyu.admin.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Mapper
public interface ApiSliderSolveRecordMapper {

    /**
     * KPI 聚合：总次数、成功次数、失败次数、超时、预检验拒绝、服务不可用、今日 Token 消耗、今日求解次数
     * 统计口径：排除 timeout/precheck_rejected/service_unavailable/stale_terminated 不计入失败与成功率
     */
    @Select("<script>" +
            "SELECT " +
            "COALESCE(SUM(CASE WHEN NOT (status IN ('timeout','precheck_rejected') OR COALESCE(failure_reason,'') IN ('service_unavailable','precheck_rejected','timeout','stale_terminated')) THEN 1 ELSE 0 END), 0) AS total, " +
            "COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) AS success_count, " +
            "COALESCE(SUM(CASE WHEN status = 'fail' AND COALESCE(failure_reason,'') NOT IN ('service_unavailable','precheck_rejected','timeout','stale_terminated') THEN 1 ELSE 0 END), 0) AS fail_count, " +
            "COALESCE(SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END), 0) AS timeout_count, " +
            "COALESCE(SUM(CASE WHEN status = 'precheck_rejected' THEN 1 ELSE 0 END), 0) AS precheck_rejected_count, " +
            "COALESCE(SUM(CASE WHEN COALESCE(failure_reason,'') = 'service_unavailable' THEN 1 ELSE 0 END), 0) AS service_unavailable_count, " +
            "COALESCE(SUM(CASE WHEN status = 'success' THEN token_charged ELSE 0 END), 0) AS charged_tokens " +
            "FROM xianyu_api_captcha_solve_record " +
            "WHERE COALESCE(deleted,0) = 0 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='endTime != null'> AND created_at &lt; #{endTime} </if>" +
            "<if test='tenantId != null'> AND tenant_id = #{tenantId} </if>" +
            "</script>")
    Map<String, Object> selectKpi(@Param("startTime") LocalDateTime startTime,
                                  @Param("endTime") LocalDateTime endTime,
                                  @Param("tenantId") Long tenantId);

    /**
     * 按日趋势
     */
    @Select("<script>" +
            "SELECT DATE(created_at) AS date, " +
            "COUNT(*) AS total, " +
            "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, " +
            "SUM(CASE WHEN status='fail' AND COALESCE(failure_reason,'') NOT IN ('service_unavailable','precheck_rejected','timeout','stale_terminated') THEN 1 ELSE 0 END) AS fail, " +
            "SUM(CASE WHEN status='success' THEN token_charged ELSE 0 END) AS charged_tokens " +
            "FROM xianyu_api_captcha_solve_record " +
            "WHERE COALESCE(deleted,0) = 0 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='endTime != null'> AND created_at &lt; #{endTime} </if>" +
            "<if test='tenantId != null'> AND tenant_id = #{tenantId} </if>" +
            "GROUP BY DATE(created_at) ORDER BY date ASC" +
            "</script>")
    List<Map<String, Object>> selectTrend(@Param("startTime") LocalDateTime startTime,
                                          @Param("endTime") LocalDateTime endTime,
                                          @Param("tenantId") Long tenantId);

    /**
     * 按租户分组（后台用）
     */
    @Select("<script>" +
            "SELECT tenant_id, MAX(api_key_prefix) AS api_key_prefix, " +
            "COUNT(*) AS total, " +
            "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, " +
            "SUM(CASE WHEN status='fail' AND COALESCE(failure_reason,'') NOT IN ('service_unavailable','precheck_rejected','timeout','stale_terminated') THEN 1 ELSE 0 END) AS fail, " +
            "SUM(CASE WHEN status='success' THEN token_charged ELSE 0 END) AS charged_tokens, " +
            "MAX(created_at) AS last_solve_time " +
            "FROM xianyu_api_captcha_solve_record " +
            "WHERE COALESCE(deleted,0) = 0 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='endTime != null'> AND created_at &lt; #{endTime} </if>" +
            "GROUP BY tenant_id ORDER BY total DESC" +
            "</script>")
    List<Map<String, Object>> selectTenantGroups(@Param("startTime") LocalDateTime startTime,
                                                  @Param("endTime") LocalDateTime endTime);

    /**
     * 明细分页查询
     */
    @Select("<script>" +
            "SELECT id, tenant_id, api_key_prefix, client_ip, request_id, event_desc, trigger_scene, " +
            "result, status, engine, retry_count, error_message, failure_reason, " +
            "queued_at, started_at, finished_at, token_charged, token_charge_failed, duration_ms, created_at " +
            "FROM xianyu_api_captcha_solve_record " +
            "WHERE COALESCE(deleted,0) = 0 " +
            "<if test='tenantId != null'> AND tenant_id = #{tenantId} </if>" +
            "<if test='status != null and status != \"\"'> AND status = #{status} </if>" +
            "<if test='apiKeyPrefix != null and apiKeyPrefix != \"\"'> AND api_key_prefix = #{apiKeyPrefix} </if>" +
            "<if test='keyword != null and keyword != \"\"'> AND (request_id LIKE CONCAT('%',#{keyword},'%') OR error_message LIKE CONCAT('%',#{keyword},'%')) </if>" +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='endTime != null'> AND created_at &lt; #{endTime} </if>" +
            "ORDER BY created_at DESC LIMIT #{offset}, #{size}" +
            "</script>")
    List<Map<String, Object>> selectRecords(@Param("tenantId") Long tenantId,
                                            @Param("status") String status,
                                            @Param("apiKeyPrefix") String apiKeyPrefix,
                                            @Param("keyword") String keyword,
                                            @Param("startTime") LocalDateTime startTime,
                                            @Param("endTime") LocalDateTime endTime,
                                            @Param("offset") int offset,
                                            @Param("size") int size);

    @Select("<script>" +
            "SELECT COUNT(*) FROM xianyu_api_captcha_solve_record " +
            "WHERE COALESCE(deleted,0) = 0 " +
            "<if test='tenantId != null'> AND tenant_id = #{tenantId} </if>" +
            "<if test='status != null and status != \"\"'> AND status = #{status} </if>" +
            "<if test='apiKeyPrefix != null and apiKeyPrefix != \"\"'> AND api_key_prefix = #{apiKeyPrefix} </if>" +
            "<if test='keyword != null and keyword != \"\"'> AND (request_id LIKE CONCAT('%',#{keyword},'%') OR error_message LIKE CONCAT('%',#{keyword},'%')) </if>" +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='endTime != null'> AND created_at &lt; #{endTime} </if>" +
            "</script>")
    long countRecords(@Param("tenantId") Long tenantId,
                      @Param("status") String status,
                      @Param("apiKeyPrefix") String apiKeyPrefix,
                      @Param("keyword") String keyword,
                      @Param("startTime") LocalDateTime startTime,
                      @Param("endTime") LocalDateTime endTime);

    /**
     * 扫描僵尸记录（对账定时任务用）
     */
    @Select("SELECT id, tenant_id, request_id FROM xianyu_api_captcha_solve_record " +
            "WHERE status IN ('queued','retrying') AND queued_at IS NOT NULL " +
            "AND queued_at &lt; DATE_SUB(NOW(), INTERVAL 10 MINUTE) AND COALESCE(deleted,0) = 0")
    List<Map<String, Object>> selectStaleRecords();
}
