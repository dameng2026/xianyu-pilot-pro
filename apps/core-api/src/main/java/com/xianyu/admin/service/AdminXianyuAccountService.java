package com.xianyu.admin.service;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.AdminXianyuAccountVO;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 后台管理员专用闲鱼账号服务。
 * 核心特点：
 * 1. 支持超级管理员跨租户查询；传入 tenantId 时必须按租户过滤。
 * 2. 仅用于 admin-web，不对外暴露普通用户接口。
 * 3. 必须由 JwtAuthFilter 校验管理员身份后才能访问。
 * 4. 不返回 encrypted_cookie、encrypted_token、完整 Cookie、_m_h5_tk、password_hash、salt。
 */
@Service
public class AdminXianyuAccountService {
    private static final Logger log = LoggerFactory.getLogger(AdminXianyuAccountService.class);

    private final XianyuAccountMapper accountMapper;

    public AdminXianyuAccountService(XianyuAccountMapper accountMapper) {
        this.accountMapper = accountMapper;
    }

    /**
     * 后台管理员分页查询闲鱼账号列表（支持租户筛选）。
     */
    public PageResult<AdminXianyuAccountVO> page(String keyword, Integer status,
                                                  Integer cookieStatus, Integer wsStatus,
                                                  Integer onlineStatus, String membershipLevel,
                                                  Long tenantId, Long userId,
                                                  LocalDateTime createdStart, LocalDateTime createdEnd,
                                                  int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = accountMapper.adminCount(keyword, status, cookieStatus, wsStatus,
                onlineStatus, membershipLevel, tenantId, userId, createdStart, createdEnd);
        List<Map<String, Object>> rows = accountMapper.adminList(keyword, status, cookieStatus, wsStatus,
                onlineStatus, membershipLevel, tenantId, userId, createdStart, createdEnd, offset, limit);

        List<AdminXianyuAccountVO> records = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            records.add(mapRowToAdminVO(row));
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 管理员查看某账号详情。
     */
    public AdminXianyuAccountVO detail(Long id) {
        Map<String, Object> row = accountMapper.adminFindById(id, null);
        if (row == null || row.isEmpty()) {
            return null;
        }
        return mapRowToAdminVO(row);
    }

    /**
     * 启用账号。
     */
    public void enable(Long id) {
        accountMapper.updateStatus(id, 1);
        log.info("管理员启用闲鱼账号: id={}", id);
    }

    /**
     * 禁用账号。
     */
    public void disable(Long id) {
        accountMapper.updateStatus(id, 0);
        log.info("管理员禁用闲鱼账号: id={}", id);
    }

    // ==================== 私有辅助方法 ====================

    private AdminXianyuAccountVO mapRowToAdminVO(Map<String, Object> row) {
        AdminXianyuAccountVO vo = new AdminXianyuAccountVO();

        // 账号基本信息
        vo.setId(getLong(row, "id"));
        vo.setPlatform(getString(row, "platform"));
        vo.setExternalUid(getString(row, "external_uid"));
        vo.setXianyuNickname(getString(row, "xianyu_nickname"));
        vo.setAvatarUrl(XianyuAccountService.normalizeAvatarUrl(getString(row, "avatar_url")));
        vo.setProvince(getString(row, "province"));
        vo.setCity(getString(row, "city"));
        vo.setAccountLevel(getInteger(row, "account_level"));
        vo.setRemark(getString(row, "remark"));
        vo.setStatus(getInteger(row, "status"));
        vo.setCreatedTime(getLocalDateTime(row, "created_time"));
        vo.setUpdatedTime(getLocalDateTime(row, "updated_time"));

        // 所属用户信息（phone/email 做脱敏处理，避免 PII 泄露）
        vo.setUserId(getLong(row, "created_by_user_id"));
        vo.setUsername(getString(row, "username"));
        vo.setUserNickname(getString(row, "user_nickname"));
        String userPhone = getString(row, "user_phone");
        vo.setUserPhone(userPhone != null && !userPhone.isBlank() ? com.xianyu.admin.common.MaskUtil.maskPhone(userPhone) : null);
        String userEmail = getString(row, "user_email");
        vo.setUserEmail(userEmail != null && !userEmail.isBlank() ? com.xianyu.admin.common.MaskUtil.maskEmail(userEmail) : null);

        // 所属租户信息
        vo.setTenantId(getLong(row, "tenant_id"));
        vo.setTenantName(getString(row, "tenant_name"));

        // 认证信息
        vo.setAuthType(getString(row, "auth_type"));
        vo.setCookieStatus(getInteger(row, "cookie_status"));
        vo.setLastRefreshTime(getLocalDateTime(row, "last_refresh_time"));

        // 运行时信息
        vo.setOnlineStatus(getInteger(row, "online_status"));
        vo.setWsStatus(getInteger(row, "ws_status"));
        vo.setLastLoginTime(getLocalDateTime(row, "last_login_time"));
        vo.setLastHeartbeatTime(getLocalDateTime(row, "last_heartbeat_time"));
        vo.setLastOnlineTime(getLocalDateTime(row, "last_online_time"));
        vo.setLastSyncTime(getLocalDateTime(row, "last_sync_time"));
        vo.setWsLatencyMs(getInteger(row, "ws_latency_ms"));

        // 会员信息
        vo.setMembershipLevel(getString(row, "membership_level"));
        vo.setMembershipStatus(getInteger(row, "membership_status"));
        vo.setMembershipExpiredTime(getLocalDateTime(row, "membership_expired_time"));

        // 健康信息
        vo.setHealthScore(getInteger(row, "health_score"));
        vo.setApiSuccessRate(getDouble(row, "api_success_rate"));
        vo.setAvgResponseMs(getInteger(row, "avg_response_ms"));

        return vo;
    }

    private Long getLong(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Long) return (Long) val;
        if (val instanceof Number) return ((Number) val).longValue();
        try { return Long.parseLong(String.valueOf(val)); } catch (Exception e) { return null; }
    }

    private String getString(Map<String, Object> map, String key) {
        Object val = map.get(key);
        return val != null ? String.valueOf(val) : null;
    }

    private Integer getInteger(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Integer) return (Integer) val;
        if (val instanceof Number) return ((Number) val).intValue();
        try { return Integer.parseInt(String.valueOf(val)); } catch (Exception e) { return null; }
    }

    private Double getDouble(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Double) return (Double) val;
        if (val instanceof Number) return ((Number) val).doubleValue();
        try { return Double.parseDouble(String.valueOf(val)); } catch (Exception e) { return null; }
    }

    private LocalDateTime getLocalDateTime(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val instanceof LocalDateTime) return (LocalDateTime) val;
        return null;
    }
}