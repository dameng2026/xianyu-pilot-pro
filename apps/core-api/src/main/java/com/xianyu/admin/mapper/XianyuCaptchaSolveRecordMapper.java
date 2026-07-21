package com.xianyu.admin.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 滑块求解记录查询 Mapper（仅后台管理端只读查询）。
 * 表 xianyu_captcha_solve_record 由 automation-service 的 V1.8/V1.9 迁移脚本创建，
 * core-api 与 automation-service 共享同一 MySQL 实例，因此可直接读取。
 *
 * 关键字段说明：
 * - status: retrying/success/fail
 * - result: slider_success/slider_fail
 * - trigger_scene: ws_connect/cookie_keepalive/token_refresh/manual/manual_retry
 * - error_message: 文本前缀可能含元数据 [durationMs=xxx, screenshot=/path] 后接错误描述
 */
@Mapper
public interface XianyuCaptchaSolveRecordMapper {

    /**
     * KPI 聚合：总次数、成功次数、失败次数。
     * startTime 为空时统计全量。
     * userId 不为空时按子查询过滤该用户名下账号。
     * accountId 不为空时直接按账号过滤（与 userId 互斥，accountId 优先）。
     */
    @Select("<script>" +
            "SELECT COUNT(*) AS total, " +
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count, " +
            "SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS fail_count " +
            "FROM xianyu_captcha_solve_record " +
            "WHERE COALESCE(deleted, 0) = 0 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "</script>")
    Map<String, Object> selectKpi(@Param("startTime") LocalDateTime startTime,
                                  @Param("userId") Long userId,
                                  @Param("accountId") Long accountId);

    /**
     * 按日聚合趋势：返回每天的总数、成功、失败。
     */
    @Select("<script>" +
            "SELECT DATE(created_at) AS date, " +
            "COUNT(*) AS total, " +
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count, " +
            "SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS fail_count " +
            "FROM xianyu_captcha_solve_record " +
            "WHERE COALESCE(deleted, 0) = 0 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "GROUP BY DATE(created_at) " +
            "ORDER BY date ASC" +
            "</script>")
    List<Map<String, Object>> selectTrend(@Param("startTime") LocalDateTime startTime,
                                          @Param("userId") Long userId,
                                          @Param("accountId") Long accountId);

    /**
     * 按账号分组聚合：返回每个账号的总数、成功、失败、最近求解时间。
     * 仅返回最近 N 天内有记录的账号，按总数倒序。
     */
    @Select("<script>" +
            "SELECT account_id, " +
            "MAX(account_name) AS account_name, " +
            "COUNT(*) AS total, " +
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count, " +
            "SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS fail_count, " +
            "MAX(created_at) AS last_solve_time " +
            "FROM xianyu_captcha_solve_record " +
            "WHERE COALESCE(deleted, 0) = 0 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "GROUP BY account_id " +
            "ORDER BY total DESC" +
            "</script>")
    List<Map<String, Object>> selectAccountGroups(@Param("startTime") LocalDateTime startTime,
                                                   @Param("userId") Long userId,
                                                   @Param("accountId") Long accountId);

    /**
     * 分页查询明细列表。
     */
    @Select("<script>" +
            "SELECT id, tenant_id, account_id, account_name, event_desc, open_reason, solve_reason, " +
            "trigger_scene, result, status, engine, retry_count, error_message, " +
            "priority, failure_reason, queued_at, started_at, finished_at, " +
            "created_at, updated_at " +
            "FROM xianyu_captcha_solve_record " +
            "WHERE COALESCE(deleted, 0) = 0 " +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "<if test='status != null and status != \"\"'> AND status = #{status} </if>" +
            "<if test='triggerScene != null and triggerScene != \"\"'> AND trigger_scene = #{triggerScene} </if>" +
            "<if test='accountName != null and accountName != \"\"'> AND account_name LIKE CONCAT('%', #{accountName}, '%') </if>" +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='endTime != null'> AND created_at &lt;= #{endTime} </if>" +
            "ORDER BY created_at DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<Map<String, Object>> selectList(@Param("accountId") Long accountId,
                                         @Param("userId") Long userId,
                                         @Param("status") String status,
                                         @Param("triggerScene") String triggerScene,
                                         @Param("accountName") String accountName,
                                         @Param("startTime") LocalDateTime startTime,
                                         @Param("endTime") LocalDateTime endTime,
                                         @Param("offset") int offset,
                                         @Param("limit") int limit);

    /**
     * 明细总数。
     */
    @Select("<script>" +
            "SELECT COUNT(*) FROM xianyu_captcha_solve_record " +
            "WHERE COALESCE(deleted, 0) = 0 " +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "<if test='status != null and status != \"\"'> AND status = #{status} </if>" +
            "<if test='triggerScene != null and triggerScene != \"\"'> AND trigger_scene = #{triggerScene} </if>" +
            "<if test='accountName != null and accountName != \"\"'> AND account_name LIKE CONCAT('%', #{accountName}, '%') </if>" +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='endTime != null'> AND created_at &lt;= #{endTime} </if>" +
            "</script>")
    int selectCount(@Param("accountId") Long accountId,
                    @Param("userId") Long userId,
                    @Param("status") String status,
                    @Param("triggerScene") String triggerScene,
                    @Param("accountName") String accountName,
                    @Param("startTime") LocalDateTime startTime,
                    @Param("endTime") LocalDateTime endTime);

    /**
     * 静默自动求解摘要：仅统计自动触发场景（ws_connect / cookie_keepalive / token_refresh），
     * 排除手动触发（manual / manual_retry）。
     *
     * 用于前台进入页面时展示"您不在场时滑块求解已自动为您解决 N 次"的惊喜提示。
     *
     * @param startTime 起始时间（必填，来自前端 since 参数）
     * @param endTime   截止时间（必填，通常为当前时间）
     * @param userId    用户 ID 过滤（与 accountId 互斥）
     * @param accountId 账号 ID 过滤（优先于 userId）
     */
    @Select("<script>" +
            "SELECT COUNT(*) AS total, " +
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count, " +
            "SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS fail_count, " +
            "COUNT(DISTINCT account_id) AS account_count, " +
            "MAX(created_at) AS last_solve_time " +
            "FROM xianyu_captcha_solve_record " +
            "WHERE COALESCE(deleted, 0) = 0 " +
            "AND trigger_scene IN ('ws_connect', 'cookie_keepalive', 'token_refresh') " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='endTime != null'> AND created_at &lt;= #{endTime} </if>" +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "</script>")
    Map<String, Object> selectSilentSummary(@Param("startTime") LocalDateTime startTime,
                                             @Param("endTime") LocalDateTime endTime,
                                             @Param("userId") Long userId,
                                             @Param("accountId") Long accountId);
}
