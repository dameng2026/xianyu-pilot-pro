package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuAccount;
import org.apache.ibatis.annotations.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Mapper
public interface XianyuAccountMapper {

    @Select("<script>" +
            "SELECT a.*, m.level AS membership_level, m.expired_time AS membership_expired_time, " +
            "m.status AS membership_status, auth.cookie_status, auth.last_login_status_code, " +
            "auth.last_login_status_message, auth.last_login_check_time, r.online_status, r.ws_status, r.ws_latency_ms, " +
            "r.last_heartbeat_time, r.last_online_time, " +
            "h.health_score, h.api_success_rate, h.avg_response_ms " +
            "FROM xianyu_account a " +
            "LEFT JOIN xianyu_account_membership m ON a.id = m.account_id " +
            "LEFT JOIN xianyu_account_auth auth ON a.id = auth.account_id AND auth.deleted = 0 " +
            "LEFT JOIN xianyu_account_runtime r ON a.id = r.account_id " +
            "LEFT JOIN xianyu_account_health_snapshot h ON h.id = (SELECT hs.id FROM xianyu_account_health_snapshot hs WHERE hs.account_id = a.id AND hs.tenant_id = #{tenantId} AND hs.deleted = 0 ORDER BY hs.collected_time DESC LIMIT 1) " +
            "WHERE a.deleted = 0 AND a.tenant_id = #{tenantId} " +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (a.nickname LIKE CONCAT('%', #{keyword}, '%') OR a.remark LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND a.status = #{status} " +
            "</if>" +
            "ORDER BY a.created_time DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<Map<String, Object>> list(@Param("tenantId") Long tenantId,
                                   @Param("keyword") String keyword,
                                   @Param("status") Integer status,
                                   @Param("offset") int offset,
                                   @Param("limit") int limit);

    @Select("<script>" +
            "SELECT a.id, a.external_uid, a.nickname, a.display_name, a.avatar_url, a.province, a.city, " +
            "a.account_level, a.remark, a.status, a.message_expire_time, a.scheduled_redelivery, a.auto_polish, " +
            "auth.cookie_status, auth.last_login_status_code, auth.last_login_status_message, auth.last_login_check_time, " +
            "r.online_status, r.ws_status, r.ws_latency_ms, r.last_heartbeat_time, r.last_online_time, " +
            "h.health_score, h.api_success_rate, h.avg_response_ms " +
            "FROM xianyu_account a " +
            "LEFT JOIN xianyu_account_auth auth ON a.id = auth.account_id AND auth.deleted = 0 " +
            "LEFT JOIN xianyu_account_runtime r ON a.id = r.account_id " +
            "LEFT JOIN xianyu_account_health_snapshot h ON h.id = (SELECT hs.id FROM xianyu_account_health_snapshot hs WHERE hs.account_id = a.id AND hs.tenant_id = #{tenantId} AND hs.deleted = 0 ORDER BY hs.collected_time DESC LIMIT 1) " +
            "WHERE a.deleted = 0 AND a.tenant_id = #{tenantId} " +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (a.nickname LIKE CONCAT('%', #{keyword}, '%') OR a.remark LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND a.status = #{status} " +
            "</if>" +
            "ORDER BY a.created_time DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<Map<String, Object>> listLite(@Param("tenantId") Long tenantId,
                                       @Param("keyword") String keyword,
                                       @Param("status") Integer status,
                                       @Param("offset") int offset,
                                       @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) " +
            "FROM xianyu_account " +
            "WHERE deleted = 0 AND tenant_id = #{tenantId} " +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (nickname LIKE CONCAT('%', #{keyword}, '%') OR remark LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND status = #{status} " +
            "</if>" +
            "</script>")
    int count(@Param("tenantId") Long tenantId,
              @Param("keyword") String keyword,
              @Param("status") Integer status);

    @Select("SELECT * FROM xianyu_account WHERE id = #{id} AND deleted = 0 AND tenant_id = #{tenantId}")
    XianyuAccount findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Insert("INSERT INTO xianyu_account(tenant_id, user_id, created_by_user_id, platform, external_uid, nickname, avatar_url, province, city, account_level, remark, status, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{userId}, #{userId}, 'xianyu', #{externalUid}, #{nickname}, #{avatarUrl}, #{province}, #{city}, #{accountLevel}, #{remark}, #{status}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuAccount account);

    @Update("UPDATE xianyu_account SET nickname = #{nickname}, avatar_url = #{avatarUrl}, province = #{province}, " +
            "city = #{city}, account_level = #{accountLevel}, remark = #{remark}, status = #{status}, " +
            "display_name = #{displayName}, ip_location = #{ipLocation}, introduction = #{introduction}, " +
            "followers = #{followers}, following = #{following}, seller_level = #{sellerLevel}, " +
            "fish_shop_score = #{fishShopScore}, fish_shop_user = #{fishShopUser}, praise_ratio = #{praiseRatio}, " +
            "review_num = #{reviewNum}, sold_count = #{soldCount}, updated_time = NOW() " +
            "WHERE id = #{id} AND deleted = 0 AND tenant_id = #{tenantId}")
    int update(XianyuAccount account);

    @Update("UPDATE xianyu_account SET deleted = 1, updated_time = NOW() WHERE id = #{id} AND deleted = 0 AND tenant_id = #{tenantId}")
    int softDelete(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Select("SELECT * FROM xianyu_account WHERE external_uid = #{externalUid} AND deleted = 0 AND tenant_id = #{tenantId}")
    XianyuAccount findByExternalUid(@Param("tenantId") Long tenantId, @Param("externalUid") String externalUid);

    @Select("SELECT " +
            "COUNT(*) AS total, " +
            "SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS active_count, " +
            "SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) AS inactive_count " +
            "FROM xianyu_account " +
            "WHERE deleted = 0 AND tenant_id = #{tenantId}")
    Map<String, Object> selectSummary(@Param("tenantId") Long tenantId);

    @Select("SELECT " +
            "SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS verify_count " +
            "FROM xianyu_account " +
            "WHERE deleted = 0 AND tenant_id = #{tenantId}")
    Map<String, Object> selectByStatus(@Param("tenantId") Long tenantId);

    @Select("SELECT COUNT(*) FROM xianyu_account WHERE deleted = 0 AND tenant_id = #{tenantId}")
    int countAll(@Param("tenantId") Long tenantId);

    // ========== 后台管理员方法（tenantId 为空时仅超级管理员全局查询；传入 tenantId 时必须过滤） ==========

    @Select("<script>" +
            "SELECT " +
            "a.id, COALESCE(a.user_id, a.created_by_user_id) AS created_by_user_id, a.tenant_id, " +
            "u.username, u.nickname AS user_nickname, u.phone AS user_phone, u.email AS user_email, " +
            "COALESCE(ut.display_name, ut.tenant_name, ut.name) AS tenant_name, " +
            "a.platform, a.external_uid, a.nickname AS xianyu_nickname, a.avatar_url, " +
            "a.province, a.city, a.account_level, a.remark, a.status, " +
            "a.created_time, a.updated_time, " +
            "auth.auth_type, auth.cookie_status, auth.updated_time AS last_refresh_time, " +
            "r.online_status, r.ws_status, r.last_login_time, r.last_heartbeat_time, " +
            "r.last_online_time, r.last_sync_time, r.ws_latency_ms, " +
            "m.level AS membership_level, m.status AS membership_status, m.expired_time AS membership_expired_time, " +
            "h.health_score, h.api_success_rate, h.avg_response_ms " +
            "FROM xianyu_account a " +
            "LEFT JOIN sys_user u ON u.id = COALESCE(a.user_id, a.created_by_user_id) AND u.deleted = 0 " +
            "LEFT JOIN sys_tenant ut ON ut.id = a.tenant_id AND ut.deleted = 0 " +
            "LEFT JOIN xianyu_account_auth auth ON auth.account_id = a.id AND auth.deleted = 0 " +
            "LEFT JOIN xianyu_account_runtime r ON r.account_id = a.id " +
            "LEFT JOIN xianyu_account_membership m ON m.account_id = a.id " +
            "LEFT JOIN xianyu_account_health_snapshot h ON h.id = (SELECT hs.id FROM xianyu_account_health_snapshot hs WHERE hs.account_id = a.id ORDER BY hs.collected_time DESC LIMIT 1) " +
            "WHERE a.deleted = 0 " +
            "<if test='tenantId != null'>" +
            "  AND a.tenant_id = #{tenantId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (a.external_uid LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR a.nickname LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR a.remark LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR u.username LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR u.nickname LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR u.phone LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR u.email LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND a.status = #{status} " +
            "</if>" +
            "<if test='cookieStatus != null'>" +
            "  AND (auth.cookie_status = #{cookieStatus} OR (auth.cookie_status IS NULL AND 0 = #{cookieStatus})) " +
            "</if>" +
            "<if test='wsStatus != null'>" +
            "  AND r.ws_status = #{wsStatus} " +
            "</if>" +
            "<if test='onlineStatus != null'>" +
            "  AND r.online_status = #{onlineStatus} " +
            "</if>" +
            "<if test='membershipLevel != null and membershipLevel != \"\"'>" +
            "  AND m.level = #{membershipLevel} " +
            "</if>" +
            "<if test='userId != null'>" +
            "  AND COALESCE(a.user_id, a.created_by_user_id) = #{userId} " +
            "</if>" +
            "<if test='createdStart != null'>" +
            "  AND a.created_time >= #{createdStart} " +
            "</if>" +
            "<if test='createdEnd != null'>" +
            "  AND a.created_time &lt;= #{createdEnd} " +
            "</if>" +
            "ORDER BY a.created_time DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<Map<String, Object>> adminList(@Param("keyword") String keyword,
                                        @Param("status") Integer status,
                                        @Param("cookieStatus") Integer cookieStatus,
                                        @Param("wsStatus") Integer wsStatus,
                                        @Param("onlineStatus") Integer onlineStatus,
                                        @Param("membershipLevel") String membershipLevel,
                                        @Param("tenantId") Long tenantId,
                                        @Param("userId") Long userId,
                                        @Param("createdStart") LocalDateTime createdStart,
                                        @Param("createdEnd") LocalDateTime createdEnd,
                                        @Param("offset") int offset,
                                        @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM xianyu_account a " +
            "LEFT JOIN sys_user u ON u.id = COALESCE(a.user_id, a.created_by_user_id) AND u.deleted = 0 " +
            "LEFT JOIN xianyu_account_auth auth ON auth.account_id = a.id AND auth.deleted = 0 " +
            "LEFT JOIN xianyu_account_runtime r ON r.account_id = a.id " +
            "LEFT JOIN xianyu_account_membership m ON m.account_id = a.id " +
            "WHERE a.deleted = 0 " +
            "<if test='tenantId != null'>" +
            "  AND a.tenant_id = #{tenantId} " +
            "</if>" +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (a.external_uid LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR a.nickname LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR a.remark LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR u.username LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR u.nickname LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR u.phone LIKE CONCAT('%', #{keyword}, '%') " +
            "    OR u.email LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "<if test='status != null'>" +
            "  AND a.status = #{status} " +
            "</if>" +
            "<if test='cookieStatus != null'>" +
            "  AND (auth.cookie_status = #{cookieStatus} OR (auth.cookie_status IS NULL AND 0 = #{cookieStatus})) " +
            "</if>" +
            "<if test='wsStatus != null'>" +
            "  AND r.ws_status = #{wsStatus} " +
            "</if>" +
            "<if test='onlineStatus != null'>" +
            "  AND r.online_status = #{onlineStatus} " +
            "</if>" +
            "<if test='membershipLevel != null and membershipLevel != \"\"'>" +
            "  AND m.level = #{membershipLevel} " +
            "</if>" +
            "<if test='userId != null'>" +
            "  AND COALESCE(a.user_id, a.created_by_user_id) = #{userId} " +
            "</if>" +
            "<if test='createdStart != null'>" +
            "  AND a.created_time >= #{createdStart} " +
            "</if>" +
            "<if test='createdEnd != null'>" +
            "  AND a.created_time &lt;= #{createdEnd} " +
            "</if>" +
            "</script>")
    int adminCount(@Param("keyword") String keyword,
                   @Param("status") Integer status,
                   @Param("cookieStatus") Integer cookieStatus,
                   @Param("wsStatus") Integer wsStatus,
                   @Param("onlineStatus") Integer onlineStatus,
                   @Param("membershipLevel") String membershipLevel,
                   @Param("tenantId") Long tenantId,
                   @Param("userId") Long userId,
                   @Param("createdStart") LocalDateTime createdStart,
                   @Param("createdEnd") LocalDateTime createdEnd);

    @Update("UPDATE xianyu_account SET status = #{status}, updated_time = NOW() WHERE id = #{id} AND deleted = 0")
    int updateStatus(@Param("id") Long id, @Param("status") Integer status);

    @Select("<script>" +
            "SELECT " +
            "a.id, COALESCE(a.user_id, a.created_by_user_id) AS created_by_user_id, a.tenant_id, " +
            "u.username, u.nickname AS user_nickname, u.phone AS user_phone, u.email AS user_email, " +
            "COALESCE(ut.display_name, ut.tenant_name, ut.name) AS tenant_name, " +
            "a.platform, a.external_uid, a.nickname AS xianyu_nickname, a.avatar_url, " +
            "a.province, a.city, a.account_level, a.remark, a.status, " +
            "a.created_time, a.updated_time, " +
            "auth.auth_type, auth.cookie_status, auth.updated_time AS last_refresh_time, " +
            "r.online_status, r.ws_status, r.last_login_time, r.last_heartbeat_time, " +
            "r.last_online_time, r.last_sync_time, r.ws_latency_ms, " +
            "m.level AS membership_level, m.status AS membership_status, m.expired_time AS membership_expired_time, " +
            "h.health_score, h.api_success_rate, h.avg_response_ms " +
            "FROM xianyu_account a " +
            "LEFT JOIN sys_user u ON u.id = COALESCE(a.user_id, a.created_by_user_id) AND u.deleted = 0 " +
            "LEFT JOIN sys_tenant ut ON ut.id = a.tenant_id AND ut.deleted = 0 " +
            "LEFT JOIN xianyu_account_auth auth ON auth.account_id = a.id AND auth.deleted = 0 " +
            "LEFT JOIN xianyu_account_runtime r ON r.account_id = a.id " +
            "LEFT JOIN xianyu_account_membership m ON m.account_id = a.id " +
            "LEFT JOIN xianyu_account_health_snapshot h ON h.id = (SELECT hs.id FROM xianyu_account_health_snapshot hs WHERE hs.account_id = a.id ORDER BY hs.collected_time DESC LIMIT 1) " +
            "WHERE a.id = #{id} AND a.deleted = 0 " +
            "<if test='tenantId != null'>" +
            "  AND a.tenant_id = #{tenantId} " +
            "</if>" +
            "</script>")
    Map<String, Object> adminFindById(@Param("id") Long id, @Param("tenantId") Long tenantId);
}
