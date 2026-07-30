package com.xianyu.admin.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 滑块求解尝试明细 Mapper（仅后台管理端只读查询）。
 *
 * 表 xianyu_captcha_solve_attempt 由 automation-service 的 V1.24 迁移脚本创建，
 * core-api 与 automation-service 共享同一 MySQL 实例，因此可直接读取。
 *
 * 关键字段说明：
 * - solve_scheme: python_script / playwright（求解方案）
 * - drag_method: in_container / out_container / none（拖动方法）
 * - speed_strategy: standard / medium / fast / slow_pause / random / none（速度策略）
 * - attempt_no: 1-5（尝试轮次，由 crawler-service sliderSolver 内部 attempt 计数）
 * - success: 0=失败 / 1=成功
 * - duration_ms: 本次尝试耗时（毫秒）
 */
@Mapper
public interface XianyuCaptchaSolveAttemptMapper {

    /**
     * 按指定维度聚合统计成功率。
     *
     * @param field     聚合字段名（solve_scheme / drag_method / speed_strategy / attempt_no）
     *                  调用方必须使用白名单值，避免 SQL 注入
     * @param startTime 统计起始时间（null=全量）
     * @param userId    用户 ID 过滤（与 accountId 互斥，accountId 优先）
     * @param accountId 账号 ID 过滤
     * @return 每行包含 {dim, total, success, success_rate, avg_duration_ms}
     */
    @Select("<script>" +
            "SELECT ${field} AS dim, " +
            "COUNT(*) AS total, " +
            "COALESCE(SUM(success), 0) AS success, " +
            "ROUND(COALESCE(SUM(success), 0) * 100.0 / GREATEST(COUNT(*), 1), 2) AS success_rate, " +
            "COALESCE(ROUND(AVG(duration_ms)), 0) AS avg_duration_ms " +
            "FROM xianyu_captcha_solve_attempt " +
            "WHERE 1=1 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "GROUP BY ${field} " +
            "ORDER BY total DESC" +
            "</script>")
    List<Map<String, Object>> selectDimensionStats(@Param("field") String field,
                                                    @Param("startTime") LocalDateTime startTime,
                                                    @Param("userId") Long userId,
                                                    @Param("accountId") Long accountId);

    /**
     * 总尝试次数和成功次数。
     */
    @Select("<script>" +
            "SELECT COUNT(*) AS total, COALESCE(SUM(success), 0) AS success " +
            "FROM xianyu_captcha_solve_attempt " +
            "WHERE 1=1 " +
            "<if test='startTime != null'> AND created_at &gt;= #{startTime} </if>" +
            "<if test='accountId != null'> AND account_id = #{accountId} </if>" +
            "<if test='userId != null and accountId == null'>" +
            "  AND account_id IN (SELECT id FROM xianyu_account WHERE COALESCE(user_id, created_by_user_id) = #{userId}) " +
            "</if>" +
            "</script>")
    Map<String, Object> selectTotals(@Param("startTime") LocalDateTime startTime,
                                     @Param("userId") Long userId,
                                     @Param("accountId") Long accountId);

    /**
     * 查询单条求解记录的尝试明细列表（用于前端查看详情）。
     */
    @Select("SELECT attempt_no, solve_scheme, drag_method, speed_strategy, " +
            "success, duration_ms, error_message, created_at " +
            "FROM xianyu_captcha_solve_attempt " +
            "WHERE record_id = #{recordId} " +
            "ORDER BY attempt_no ASC, id ASC")
    List<Map<String, Object>> selectByRecordId(@Param("recordId") Long recordId);
}
