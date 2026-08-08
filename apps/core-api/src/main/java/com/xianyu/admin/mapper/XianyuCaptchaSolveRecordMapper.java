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
 *
 * 统计口径说明（2026-07-24 调整）：
 * 以下记录不计入成功率与失败次数统计：
 * - 超时：status='timeout' 或 failure_reason='stale_terminated'（retrying 超 15 分钟被清理）
 * - 预检验拒绝：status='precheck_rejected' 或 failure_reason IN ('precheck_rejected','cookie_invalid','account_inactive','account_disabled')
 *   （Cookie 过期 / 账号不活跃 / 账号禁用 均属预检验阶段拒绝，非求解本身失败）
 * - 服务不可用/浏览器崩溃：failure_reason='service_unavailable' 或 'browser_crashed'
 *   （hasLogin 不可用 / Chrome 启动失败 / 浏览器崩溃，均为环境性故障，非求解本身失败）
 * 因此：
 * - total（求解总次数）= 排除上述记录后的有效记录数（用于成功率分母）
 * - fail（失败次数）= status='fail' 且 failure_reason 不属于上述排除类的记录数
 * - timeout_count / precheck_rejected_count / service_unavailable_count 仍单独统计供徽标展示
 */
    @Select("<script>" +
            "SELECT " +
            "SUM(CASE WHEN NOT (status IN ('timeout', 'precheck_rejected') OR COALESCE(failure_reason, '') IN ('service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', 'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled')) THEN 1 ELSE 0 END) AS total, " +
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count, " +
            "SUM(CASE WHEN status = 'fail' AND COALESCE(failure_reason, '') NOT IN ('service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', 'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled') THEN 1 ELSE 0 END) AS fail_count, " +
            "SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) AS timeout_count, " +
            "SUM(CASE WHEN status = 'precheck_rejected' THEN 1 ELSE 0 END) AS precheck_rejected_count, " +
            "SUM(CASE WHEN COALESCE(failure_reason, '') = 'service_unavailable' THEN 1 ELSE 0 END) AS service_unavailable_count " +
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
     * 统计口径与 selectKpi 一致：排除超时/预检验拒绝/服务不可用记录。
     */
    @Select("<script>" +
            "SELECT DATE(created_at) AS date, " +
            "SUM(CASE WHEN NOT (status IN ('timeout', 'precheck_rejected') OR COALESCE(failure_reason, '') IN ('service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', 'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled')) THEN 1 ELSE 0 END) AS total, " +
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count, " +
            "SUM(CASE WHEN status = 'fail' AND COALESCE(failure_reason, '') NOT IN ('service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', 'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled') THEN 1 ELSE 0 END) AS fail_count, " +
            "SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) AS timeout_count, " +
            "SUM(CASE WHEN status = 'precheck_rejected' THEN 1 ELSE 0 END) AS precheck_rejected_count, " +
            "SUM(CASE WHEN COALESCE(failure_reason, '') = 'service_unavailable' THEN 1 ELSE 0 END) AS service_unavailable_count " +
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
     * 统计口径与 selectKpi 一致：排除超时/预检验拒绝/服务不可用记录。
     */
    @Select("<script>" +
            "SELECT account_id, " +
            "MAX(account_name) AS account_name, " +
            "SUM(CASE WHEN NOT (status IN ('timeout', 'precheck_rejected') OR COALESCE(failure_reason, '') IN ('service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', 'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled')) THEN 1 ELSE 0 END) AS total, " +
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count, " +
            "SUM(CASE WHEN status = 'fail' AND COALESCE(failure_reason, '') NOT IN ('service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', 'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled') THEN 1 ELSE 0 END) AS fail_count, " +
            "SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) AS timeout_count, " +
            "SUM(CASE WHEN status = 'precheck_rejected' THEN 1 ELSE 0 END) AS precheck_rejected_count, " +
            "SUM(CASE WHEN COALESCE(failure_reason, '') = 'service_unavailable' THEN 1 ELSE 0 END) AS service_unavailable_count, " +
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
            "priority, failure_reason, proxy_source, queued_at, started_at, finished_at, " +
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
     * 按状态统计记录数（用于队列实时状态徽标）。
     * status 传 'queued' 或 'retrying'，返回当前处于该瞬态的记录数。
     */
    @Select("SELECT COUNT(*) FROM xianyu_captcha_solve_record " +
            "WHERE status = #{status} AND COALESCE(deleted, 0) = 0")
    int countByStatus(@Param("status") String status);

    /**
     * 按代理来源（proxy_source）分组聚合成功率（2026-08-03 新增）。
     * 统计口径与 selectKpi 一致：排除超时/预检验拒绝/服务不可用记录。
     * 空值 proxy_source 归为 'unknown'。
     */
    @Select("<script>" +
            "SELECT COALESCE(NULLIF(proxy_source, ''), 'unknown') AS proxy_source, " +
            "SUM(CASE WHEN NOT (status IN ('timeout', 'precheck_rejected') OR COALESCE(failure_reason, '') IN ('service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', 'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled')) THEN 1 ELSE 0 END) AS total, " +
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count, " +
            "SUM(CASE WHEN status = 'fail' AND COALESCE(failure_reason, '') NOT IN ('service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', 'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled') THEN 1 ELSE 0 END) AS fail_count " +
            "FROM xianyu_captcha_solve_record " +
            "WHERE COALESCE(deleted, 0) = 0 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "GROUP BY COALESCE(NULLIF(proxy_source, ''), 'unknown') " +
            "ORDER BY total DESC" +
            "</script>")
    List<Map<String, Object>> selectProxySourceGroups(@Param("startTime") LocalDateTime startTime,
                                                       @Param("userId") Long userId,
                                                       @Param("accountId") Long accountId);

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
}
