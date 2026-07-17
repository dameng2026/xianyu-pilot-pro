package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.CsvCellEncoder;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.AdminXianyuAccountVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class AdminModuleService {
    private static final Logger log = LoggerFactory.getLogger(AdminModuleService.class);
    /**
     * Catalog entries that describe operational capabilities, but have no read/write backend wired here.
     * Falling through to admin_module_record would turn arbitrary JSON into fake backup/log/file/etc. state.
     */
    private static final Set<String> MODULES_WITHOUT_REAL_BACKEND = Set.of(
            "licenses", "notify-channels", "notify-logs", "risk-events", "runtime",
            "backups", "versions", "rag", "alerts", "files"
    );

    private final JdbcTemplate jdbcTemplate;
    private final ModuleCatalog catalog;
    private final SysUserService sysUserService;
    private final AdminXianyuAccountService adminXianyuAccountService;
    private final BillingPlanService billingPlanService;
    private final AdminRealDataModuleService realDataModuleService;
    private final AiBillingService aiBillingService;
    private final AiProviderEndpointPolicy aiProviderEndpointPolicy;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Autowired
    public AdminModuleService(JdbcTemplate jdbcTemplate, ModuleCatalog catalog, SysUserService sysUserService,
                              AdminXianyuAccountService adminXianyuAccountService,
                              BillingPlanService billingPlanService,
                              AdminRealDataModuleService realDataModuleService,
                              AiBillingService aiBillingService,
                              AiProviderEndpointPolicy aiProviderEndpointPolicy) {
        this.jdbcTemplate = jdbcTemplate;
        this.catalog = catalog;
        this.sysUserService = sysUserService;
        this.adminXianyuAccountService = adminXianyuAccountService;
        this.billingPlanService = billingPlanService;
        this.realDataModuleService = realDataModuleService;
        this.aiBillingService = aiBillingService;
        this.aiProviderEndpointPolicy = aiProviderEndpointPolicy;
    }

    AdminModuleService(JdbcTemplate jdbcTemplate, ModuleCatalog catalog, SysUserService sysUserService,
                       AdminXianyuAccountService adminXianyuAccountService,
                       BillingPlanService billingPlanService,
                       AdminRealDataModuleService realDataModuleService,
                       AiBillingService aiBillingService) {
        this(jdbcTemplate, catalog, sysUserService, adminXianyuAccountService, billingPlanService,
                realDataModuleService, aiBillingService, new AiProviderEndpointPolicy(""));
    }

    public ModuleCatalog.ModuleMeta meta(String moduleKey) {
        requireAvailableModule(moduleKey);
        return catalog.get(moduleKey);
    }

    public PageResult<Map<String, Object>> page(String moduleKey, int current, int size, String keyword, String status) {
        requireAvailableModule(moduleKey);
        if ("xianyu-accounts".equals(moduleKey)) {
            return pageXianyuAccounts(keyword, status, current, size);
        }
        if ("users".equals(moduleKey)) {
            return pageUsers(keyword, status, current, size);
        }
        if ("plans".equals(moduleKey)) {
            return billingPlanService.page(current, size, keyword, status);
        }
        if (realDataModuleService.supports(moduleKey)) {
            return realDataModuleService.page(moduleKey, current, size, keyword, status);
        }
        if ("ai-usage".equals(moduleKey)) {
            return aiBillingService.pageUsageLogs(current, size, keyword, null, status);
        }
        if ("ai-token".equals(moduleKey)) {
            return aiBillingService.pageLedger(current, size, keyword, "ai_charge");
        }
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        String where = buildWhere(moduleKey, keyword, status, args);
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM admin_module_record" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.query(
                "SELECT id,module_key,status,json_text,created_time,updated_time FROM admin_module_record" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
                (rs, rowNum) -> {
                    Map<String, Object> data = normalizeRecord(
                            rs.getLong("id"),
                            rs.getString("module_key"),
                            rs.getString("status"),
                            rs.getString("json_text"),
                            String.valueOf(rs.getTimestamp("created_time")),
                            String.valueOf(rs.getTimestamp("updated_time"))
                    );
                    return maskIfNeeded(moduleKey, data);
                },
                pageArgs.toArray()
        );
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    private PageResult<Map<String, Object>> pageUsers(String keyword, String status, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE u.deleted=0");
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (u.username LIKE ? OR u.nickname LIKE ? OR u.phone LIKE ? OR u.email LIKE ?)");
            String kw = "%" + keyword + "%";
            args.add(kw); args.add(kw); args.add(kw); args.add(kw);
        }
        if (status != null && !status.isBlank()) {
            if (status.contains("正常") || status.contains("启用") || status.equals("1")) {
                where.append(" AND u.status=1");
            } else if (status.contains("禁用") || status.contains("异常") || status.equals("0")) {
                where.append(" AND u.status=0");
            }
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user u" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.query(
                "SELECT u.id, u.username, u.nickname, u.phone, u.email, " +
                "u.avatar, u.tenant_id, COALESCE(t.display_name, t.tenant_name, t.name) AS tenant_name, " +
                "u.status AS user_status, " +
                "u.last_login_time, u.last_login_ip, u.created_time, u.updated_time, " +
                "COALESCE(u.token_balance, 0) AS token_balance " +
                "FROM sys_user u " +
                "LEFT JOIN sys_tenant t ON t.id = u.tenant_id AND t.deleted = 0" +
                where + " ORDER BY u.id DESC LIMIT ? OFFSET ?",
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("userId", rs.getLong("id"));
                    row.put("username", rs.getString("username"));
                    row.put("account", rs.getString("username"));
                    row.put("nickname", rs.getString("nickname"));
                    row.put("phone", rs.getString("phone"));
                    row.put("email", rs.getString("email"));
                    row.put("avatar", rs.getString("avatar"));
                    row.put("tenantId", rs.getObject("tenant_id"));
                    row.put("tenantName", rs.getString("tenant_name"));
                    int userStatus = rs.getInt("user_status");
                    row.put("status", userStatus == 1 ? "正常" : "禁用");
                    row.put("lastLoginTime", rs.getTimestamp("last_login_time"));
                    row.put("lastLoginIp", rs.getString("last_login_ip"));
                    row.put("createdTime", rs.getTimestamp("created_time"));
                    row.put("updatedTime", rs.getTimestamp("updated_time"));
                    row.put("tokenBalance", rs.getLong("token_balance"));
                    return row;
                },
                pageArgs.toArray()
        );

        // 统计闲鱼账号数量
        if (!rows.isEmpty()) {
            List<Long> userIds = rows.stream()
                    .map(r -> ((Number) r.get("id")).longValue())
                    .collect(Collectors.toList());
            String idPlaceholders = userIds.stream().map(i -> "?").collect(Collectors.joining(","));

            Map<Long, Integer> xianyuCountMap = new LinkedHashMap<>();
            try {
                List<Object> countArgs = new ArrayList<>(userIds);
                List<Map<String, Object>> counts = jdbcTemplate.query(
                        "SELECT COALESCE(user_id, created_by_user_id) AS owner_user_id, COUNT(*) AS cnt FROM xianyu_account " +
                        "WHERE COALESCE(user_id, created_by_user_id) IN (" + idPlaceholders + ") AND deleted = 0 GROUP BY COALESCE(user_id, created_by_user_id)",
                        (rs, rn) -> Map.of("userId", rs.getLong("owner_user_id"), "cnt", rs.getInt("cnt")),
                        countArgs.toArray()
                );
                for (Map<String, Object> c : counts) {
                    xianyuCountMap.put(((Number) c.get("userId")).longValue(), ((Number) c.get("cnt")).intValue());
                }
            } catch (Exception e) {
                throw dependencyUnavailable("用户闲鱼账号统计", e);
            }

            for (Map<String, Object> row : rows) {
                Long uid = ((Number) row.get("id")).longValue();
                row.put("xianyuAccountCount", xianyuCountMap.getOrDefault(uid, 0));
            }
        }

        enrichUserLevelRows(rows);
        // 列表视图对 phone/email 做 PII 脱敏，避免批量泄露
        for (Map<String, Object> row : rows) {
            Object phone = row.get("phone");
            if (phone != null) row.put("phone", com.xianyu.admin.common.MaskUtil.maskPhone(String.valueOf(phone)));
            Object email = row.get("email");
            if (email != null) row.put("email", com.xianyu.admin.common.MaskUtil.maskEmail(String.valueOf(email)));
        }
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    private PageResult<Map<String, Object>> pageXianyuAccounts(String keyword, String status, int current, int size) {
        Integer statusCode = null;
        if (status != null && !status.isBlank()) {
            if (status.contains("正常") || status.contains("启用") || status.equals("1")) {
                statusCode = 1;
            } else if (status.contains("禁用") || status.contains("异常") || status.equals("0")) {
                statusCode = 0;
            }
        }
        com.xianyu.admin.common.PageResult<AdminXianyuAccountVO> result = adminXianyuAccountService.page(
                keyword, statusCode, null, null, null, null, null, null, null, null, current, size);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (AdminXianyuAccountVO vo : result.getRecords()) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", vo.getId());
            row.put("externalUid", vo.getExternalUid());
            row.put("xianyuNickname", vo.getXianyuNickname());
            row.put("avatarUrl", vo.getAvatarUrl());
            row.put("username", vo.getUsername());
            row.put("status", vo.getStatus() != null && vo.getStatus() == 1 ? "正常" : "禁用");
            row.put("cookieStatus", cookieStatusLabel(vo.getCookieStatus()));
            row.put("wsStatus", vo.getWsStatus() != null && vo.getWsStatus() == 1 ? "在线" : "离线");
            row.put("onlineStatus", vo.getOnlineStatus() != null && vo.getOnlineStatus() == 1 ? "在线" : "离线");
            row.put("membershipLevel", vo.getMembershipLevel());
            row.put("lastLoginTime", vo.getLastLoginTime());
            row.put("lastSyncTime", vo.getLastSyncTime());
            row.put("createdTime", vo.getCreatedTime());
            rows.add(row);
        }
        return new PageResult<>(rows, PageUtils.normalizeCurrent(current), PageUtils.normalizeSize(size), (int) result.getTotal());
    }

    private String cookieStatusLabel(Integer cookieStatus) {
        if (cookieStatus == null) return "未知";
        return switch (cookieStatus) {
            case 1 -> "正常";
            case 2 -> "过期";
            default -> "失效";
        };
    }

    private long countSysUsers() {
        Long c = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE deleted=0", Long.class);
        return c == null ? 0 : c;
    }

    private long countSysUsersToday() {
        Long c = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND DATE(created_time)=CURRENT_DATE()", Long.class);
        return c == null ? 0 : c;
    }

    private Map<String, Object> detailUser(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.query(
                "SELECT id, username, nickname, phone, email, avatar, status, " +
                "last_login_time, last_login_ip, created_time, updated_time, " +
                "COALESCE(token_balance, 0) AS token_balance " +
                "FROM sys_user WHERE id=? AND deleted=0",
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("userId", rs.getLong("id"));
                    row.put("username", rs.getString("username"));
                    row.put("account", rs.getString("username"));
                    row.put("nickname", rs.getString("nickname"));
                    row.put("phone", rs.getString("phone"));
                    row.put("email", rs.getString("email"));
                    row.put("avatar", rs.getString("avatar"));
                    int userStatus = rs.getInt("status");
                    row.put("status", userStatus == 1 ? "正常" : "禁用");
                    row.put("lastLoginTime", rs.getTimestamp("last_login_time"));
                    row.put("lastLoginIp", rs.getString("last_login_ip"));
                    row.put("createdTime", rs.getTimestamp("created_time"));
                    row.put("updatedTime", rs.getTimestamp("updated_time"));
                    row.put("tokenBalance", rs.getLong("token_balance"));
                    return row;
                },
                id
        );
        if (rows.isEmpty()) {
            throw new BizException(404, "用户不存在");
        }
        enrichUserLevelRows(rows);
        return rows.get(0);
    }

    private void enrichUserLevelRows(List<Map<String, Object>> rows) {
        if (rows == null || rows.isEmpty()) return;
        for (Map<String, Object> row : rows) {
            row.put("userLevel", "normal");
            row.put("userLevelName", "普通用户");
            row.put("planName", "普通用户");
        }
        List<Long> ids = rows.stream().map(r -> ((Number) r.get("id")).longValue()).collect(Collectors.toList());
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        try {
            // 读取 vip_level 手动覆盖字段（字段由 DataInitializer 统一初始化）
            Map<Long, Integer> vipOverrides = new LinkedHashMap<>();
            try {
                List<Map<String, Object>> overrides = jdbcTemplate.queryForList(
                        "SELECT id, vip_level FROM sys_user WHERE id IN (" + placeholders + ")",
                        ids.toArray());
                for (Map<String, Object> o : overrides) {
                    Number v = (Number) o.get("vip_level");
                    if (v != null && v.intValue() > 0) {
                        vipOverrides.put(((Number) o.get("id")).longValue(), v.intValue());
                    }
                }
            } catch (Exception e) {
                throw dependencyUnavailable("用户等级覆盖数据", e);
            }

            List<Map<String, Object>> plans = jdbcTemplate.query(
                    "SELECT s.user_id, p.plan_code, p.plan_name FROM billing_subscription s " +
                            "JOIN billing_plan p ON p.id=s.plan_id AND p.deleted=0 " +
                            "WHERE s.user_id IN (" + placeholders + ") AND s.status=1 " +
                            "AND (s.end_time IS NULL OR s.end_time >= NOW()) " +
                            "ORDER BY s.user_id, s.end_time DESC, s.id DESC",
                    (rs, rn) -> Map.of("userId", rs.getLong("user_id"), "planCode", normalizeUserLevel(rs.getString("plan_code")), "planName", rs.getString("plan_name")),
                    ids.toArray()
            );
            Map<Long, Map<String, Object>> byUser = new LinkedHashMap<>();
            for (Map<String, Object> p : plans) byUser.putIfAbsent(((Number) p.get("userId")).longValue(), p);
            for (Map<String, Object> row : rows) {
                Long uid = ((Number) row.get("id")).longValue();
                // vip_level 覆盖优先于订阅
                Integer overrideLevel = vipOverrides.get(uid);
                if (overrideLevel != null) {
                    String code = overrideLevel >= 2 ? "svp" : "vip";
                    row.put("userLevel", code);
                    row.put("userLevelName", overrideLevel >= 2 ? "SVP" : "VIP");
                    row.put("planName", overrideLevel >= 2 ? "SVP (手动)" : "VIP (手动)");
                } else {
                    Map<String, Object> p = byUser.get(uid);
                    if (p != null) {
                        String level = String.valueOf(p.get("planCode"));
                        row.put("userLevel", level);
                        row.put("userLevelName", "svp".equals(level) ? "SVP" : "vip".equals(level) ? "VIP" : "普通用户");
                        row.put("planName", p.get("planName"));
                    }
                }
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw dependencyUnavailable("用户订阅等级数据", e);
        }
    }

    private String normalizeUserLevel(String planCode) {
        if (planCode == null) return "normal";
        String c = planCode.trim().toLowerCase(Locale.ROOT);
        if ("svip".equals(c)) return "svp";
        if ("svp".equals(c) || "vip".equals(c)) return c;
        return "normal";
    }


    public Map<String, Object> unmaskedRecord(String moduleKey, long id) {
        requireAvailableModule(moduleKey);
        requirePositiveId(id);
        List<Map<String, Object>> rows = jdbcTemplate.query(
                "SELECT id,module_key,status,json_text,created_time,updated_time FROM admin_module_record WHERE id=? AND module_key=? AND deleted=0",
                (rs, rowNum) -> normalizeRecord(
                        rs.getLong("id"),
                        rs.getString("module_key"),
                        rs.getString("status"),
                        rs.getString("json_text"),
                        String.valueOf(rs.getTimestamp("created_time")),
                        String.valueOf(rs.getTimestamp("updated_time"))
                ),
                id,
                moduleKey
        );
        if (rows.isEmpty()) {
            throw new BizException(404, "记录不存在");
        }
        return rows.get(0);
    }

    public Map<String, Object> detail(String moduleKey, long id) {
        requireAvailableModule(moduleKey);
        requirePositiveId(id);
        if ("xianyu-accounts".equals(moduleKey)) {
            return detailXianyuAccount(id);
        }
        if ("users".equals(moduleKey)) {
            return detailUser(id);
        }
        if ("plans".equals(moduleKey)) {
            return billingPlanService.detail(id);
        }
        if (realDataModuleService.supports(moduleKey)) {
            return realDataModuleService.detail(moduleKey, id);
        }
        List<Map<String, Object>> rows = jdbcTemplate.query(
                "SELECT id,module_key,status,json_text,created_time,updated_time FROM admin_module_record WHERE id=? AND module_key=? AND deleted=0",
                (rs, rowNum) -> normalizeRecord(
                        rs.getLong("id"),
                        rs.getString("module_key"),
                        rs.getString("status"),
                        rs.getString("json_text"),
                        String.valueOf(rs.getTimestamp("created_time")),
                        String.valueOf(rs.getTimestamp("updated_time"))
                ),
                id,
                moduleKey
        );
        if (rows.isEmpty()) {
            throw new BizException(404, "记录不存在");
        }
        return maskIfNeeded(moduleKey, rows.get(0));
    }

    private Map<String, Object> detailXianyuAccount(long id) {
        AdminXianyuAccountVO vo = adminXianyuAccountService.detail(id);
        if (vo == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", vo.getId());
        row.put("externalUid", vo.getExternalUid());
        row.put("xianyuNickname", vo.getXianyuNickname());
        row.put("avatarUrl", vo.getAvatarUrl());
        row.put("province", vo.getProvince());
        row.put("city", vo.getCity());
        row.put("accountLevel", vo.getAccountLevel());
        row.put("remark", vo.getRemark());
        row.put("username", vo.getUsername());
        row.put("userNickname", vo.getUserNickname());
        row.put("userPhone", vo.getUserPhone());
        row.put("userEmail", vo.getUserEmail());
        row.put("status", vo.getStatus() != null && vo.getStatus() == 1 ? "正常" : "禁用");
        row.put("cookieStatus", cookieStatusLabel(vo.getCookieStatus()));
        row.put("wsStatus", vo.getWsStatus() != null && vo.getWsStatus() == 1 ? "在线" : "离线");
        row.put("onlineStatus", vo.getOnlineStatus() != null && vo.getOnlineStatus() == 1 ? "在线" : "离线");
        row.put("membershipLevel", vo.getMembershipLevel());
        row.put("membershipStatus", vo.getMembershipStatus() != null && vo.getMembershipStatus() == 1 ? "正常" : "过期");
        row.put("membershipExpiredTime", vo.getMembershipExpiredTime());
        row.put("lastLoginTime", vo.getLastLoginTime());
        row.put("lastSyncTime", vo.getLastSyncTime());
        row.put("lastOnlineTime", vo.getLastOnlineTime());
        row.put("lastHeartbeatTime", vo.getLastHeartbeatTime());
        row.put("wsLatencyMs", vo.getWsLatencyMs());
        row.put("apiSuccessRate", vo.getApiSuccessRate());
        row.put("avgResponseMs", vo.getAvgResponseMs());
        row.put("healthScore", vo.getHealthScore());
        row.put("createdTime", vo.getCreatedTime());
        row.put("updatedTime", vo.getUpdatedTime());
        return row;
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> save(String moduleKey, Map<String, Object> data) {
        requireAvailableModule(moduleKey);
        if (data == null) {
            throw new BizException(400, "请求数据不能为空");
        }
        if ("users".equals(moduleKey)) {
            Long id = optionalPositiveId(data.get("id"));
            if (id == null) {
                data.remove("id");
                return sysUserService.create(data);
            } else {
                return sysUserService.update(id, data);
            }
        }
        if ("plans".equals(moduleKey)) {
            return billingPlanService.save(data);
        }
        if (realDataModuleService.supports(moduleKey)) {
            return realDataModuleService.save(moduleKey, data);
        }
        try {
            prepareModelConfigData(moduleKey, data);
            Long id = optionalPositiveId(data.get("id"));
            preserveMaskedSecrets(moduleKey, id, data);
            validateModelProviderEndpoints(moduleKey, data);
            aiBillingService.normalizeAndSyncModelConfig(moduleKey, data);
            String status = String.valueOf(data.getOrDefault("status", "正常"));
            data.put("updatedTime", now());
            if (id == null) {
                data.remove("id");
                data.putIfAbsent("createdTime", now());
                int affected = jdbcTemplate.update(
                        "INSERT INTO admin_module_record(module_key,status,json_text,created_time,updated_time,deleted) VALUES(?,?,?,?,?,0)",
                        moduleKey,
                        status,
                        objectMapper.writeValueAsString(data),
                        new Date(),
                        new Date()
                );
                if (affected != 1) {
                    throw new BizException(503, "模块数据保存暂时不可用，请稍后重试");
                }
                Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
                if (newId == null || newId <= 0) {
                    throw new BizException(503, "模块数据保存暂时不可用，请稍后重试");
                }
                data.put("id", newId);
            } else {
                int affected = jdbcTemplate.update(
                        "UPDATE admin_module_record SET status=?, json_text=?, updated_time=? WHERE id=? AND module_key=? AND deleted=0",
                        status,
                        objectMapper.writeValueAsString(data),
                        new Date(),
                        id,
                        moduleKey
                );
                if (affected == 0) {
                    throw new BizException(404, "记录不存在");
                }
            }
            return maskIfNeeded(moduleKey, data);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw dependencyUnavailable("模块数据保存", e);
        }
    }

    public void updateStatus(String moduleKey, long id, String status) {
        requireAvailableModule(moduleKey);
        requirePositiveId(id);
        requireStatus(status);
        if ("xianyu-accounts".equals(moduleKey)) {
            updateXianyuAccountStatus(id, status);
            return;
        }
        if ("users".equals(moduleKey)) {
            int statusInt = ("正常".equals(status) || "1".equals(status) || "启用".equals(status)) ? 1 : 0;
            sysUserService.updateStatus(id, statusInt);
            return;
        }
        if ("plans".equals(moduleKey)) {
            billingPlanService.detail(id);
            billingPlanService.updateStatus(id, status);
            return;
        }
        if (realDataModuleService.supports(moduleKey)) {
            realDataModuleService.updateStatus(moduleKey, id, status);
            return;
        }
        int affected = jdbcTemplate.update(
                "UPDATE admin_module_record SET status=?, updated_time=? WHERE id=? AND module_key=? AND deleted=0",
                status,
                new Date(),
                id,
                moduleKey
        );
        if (affected == 0) {
            throw new BizException(404, "记录不存在");
        }
    }

    public int batchUpdateStatus(String moduleKey, List<Long> ids, String status) {
        requireAvailableModule(moduleKey);
        requireIds(ids);
        requireStatus(status);
        if ("users".equals(moduleKey)) {
            int statusInt = ("正常".equals(status) || "1".equals(status) || "启用".equals(status)) ? 1 : 0;
            return requireAffected(sysUserService.batchUpdateStatus(ids, statusInt), "未找到可更新的用户");
        }
        if ("plans".equals(moduleKey)) {
            return requireAffected(billingPlanService.batchUpdateStatus(ids, status), "未找到可更新的套餐");
        }
        if (realDataModuleService.supports(moduleKey)) {
            return requireAffected(realDataModuleService.batchUpdateStatus(moduleKey, ids, status), "未找到可更新的业务记录");
        }
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>();
        args.add(status);
        args.add(new Date());
        args.add(moduleKey);
        args.addAll(ids);
        int n = jdbcTemplate.update(
                "UPDATE admin_module_record SET status=?, updated_time=? WHERE module_key=? AND deleted=0 AND id IN (" + placeholders + ")",
                args.toArray()
        );
        if (n == 0) {
            throw new BizException(404, "未找到可更新的记录");
        }
        return n;
    }

    public void delete(String moduleKey, long id) {
        requireAvailableModule(moduleKey);
        requirePositiveId(id);
        if ("xianyu-accounts".equals(moduleKey)) {
            adminXianyuAccountService.disable(id);
            return;
        }
        if ("users".equals(moduleKey)) {
            sysUserService.delete(id);
            return;
        }
        if ("plans".equals(moduleKey)) {
            billingPlanService.detail(id);
            billingPlanService.delete(id);
            return;
        }
        if (realDataModuleService.supports(moduleKey)) {
            realDataModuleService.delete(moduleKey, id);
            return;
        }
        int affected = jdbcTemplate.update(
                "UPDATE admin_module_record SET deleted=1, updated_time=? WHERE id=? AND module_key=? AND deleted=0",
                new Date(), id, moduleKey);
        if (affected == 0) {
            throw new BizException(404, "记录不存在");
        }
    }

    public int batchDelete(String moduleKey, List<Long> ids) {
        requireAvailableModule(moduleKey);
        requireIds(ids);
        if ("users".equals(moduleKey)) {
            return requireAffected(sysUserService.batchDelete(ids), "未找到可删除的用户");
        }
        if ("plans".equals(moduleKey)) {
            return requireAffected(billingPlanService.batchDelete(ids), "未找到可删除的套餐");
        }
        if (realDataModuleService.supports(moduleKey)) {
            return requireAffected(realDataModuleService.batchDelete(moduleKey, ids), "未找到可删除的业务记录");
        }
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>();
        args.add(new Date());
        args.add(moduleKey);
        args.addAll(ids);
        int n = jdbcTemplate.update(
                "UPDATE admin_module_record SET deleted=1, updated_time=? WHERE module_key=? AND deleted=0 AND id IN (" + placeholders + ")",
                args.toArray()
        );
        if (n == 0) {
            throw new BizException(404, "未找到可删除的记录");
        }
        return n;
    }

    public Map<String, Object> stats(String moduleKey) {
        requireAvailableModule(moduleKey);
        if ("xianyu-accounts".equals(moduleKey)) {
            return statsXianyuAccounts();
        }
        if ("users".equals(moduleKey)) {
            return statsUsers();
        }
        if ("plans".equals(moduleKey)) {
            return billingPlanService.stats();
        }
        if (realDataModuleService.supports(moduleKey)) {
            return realDataModuleService.stats(moduleKey);
        }
        if ("ai-usage".equals(moduleKey)) {
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("total", jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0", Long.class));
            res.put("normal", jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=1", Long.class));
            res.put("danger", jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND status=0", Long.class));
            res.put("today", jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_usage_log WHERE deleted=0 AND DATE(created_time)=CURRENT_DATE()", Long.class));
            return res;
        }
        if ("ai-token".equals(moduleKey)) {
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("total", jdbcTemplate.queryForObject("SELECT COUNT(*) FROM token_balance_ledger", Long.class));
            res.put("normal", jdbcTemplate.queryForObject("SELECT COUNT(*) FROM token_balance_ledger WHERE change_amount > 0", Long.class));
            res.put("danger", jdbcTemplate.queryForObject("SELECT COUNT(*) FROM token_balance_ledger WHERE change_amount < 0", Long.class));
            res.put("today", jdbcTemplate.queryForObject("SELECT COUNT(*) FROM token_balance_ledger WHERE DATE(created_time)=CURRENT_DATE()", Long.class));
            return res;
        }
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("total", count(moduleKey));
        res.put("normal", countByStatusLike(moduleKey, List.of("正常", "启用", "成功", "已支付", "在线")));
        res.put("warning", countByStatusLike(moduleKey, List.of("待处理", "过期", "告警", "离线", "待支付")));
        res.put("danger", countByStatusLike(moduleKey, List.of("异常", "失败", "禁用", "高")));
        res.put("today", countToday(moduleKey));
        return res;
    }

    private Map<String, Object> statsUsers() {
        Map<String, Object> res = new LinkedHashMap<>();
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE deleted=0", Long.class);
        Long normal = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND status=1", Long.class);
        Long danger = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND status=0", Long.class);
        Long today = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND DATE(created_time)=CURRENT_DATE()", Long.class);
        res.put("total", total == null ? 0 : total);
        res.put("normal", normal == null ? 0 : normal);
        res.put("warning", 0);
        res.put("danger", danger == null ? 0 : danger);
        res.put("today", today == null ? 0 : today);
        return res;
    }

    private Map<String, Object> statsXianyuAccounts() {
        Map<String, Object> res = new LinkedHashMap<>();
        try {
            Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM xianyu_account WHERE deleted=0", Long.class);
            Long normal = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM xianyu_account WHERE deleted=0 AND status=1", Long.class);
            Long danger = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM xianyu_account WHERE deleted=0 AND status=0", Long.class);
            Long today = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM xianyu_account WHERE deleted=0 AND DATE(created_time)=CURRENT_DATE()", Long.class);
            res.put("total", total == null ? 0 : total);
            res.put("normal", normal == null ? 0 : normal);
            res.put("warning", 0);
            res.put("danger", danger == null ? 0 : danger);
            res.put("today", today == null ? 0 : today);
        } catch (Exception e) {
            throw dependencyUnavailable("闲鱼账号统计", e);
        }
        return res;
    }

    private void updateXianyuAccountStatus(long id, String status) {
        if ("正常".equals(status) || "1".equals(status) || "启用".equals(status)) {
            adminXianyuAccountService.enable(id);
        } else {
            adminXianyuAccountService.disable(id);
        }
    }

    public String exportCsv(String moduleKey, String keyword, String status) {
        requireAvailableModule(moduleKey);
        if (realDataModuleService.supports(moduleKey)) {
            return realDataModuleService.exportCsv(moduleKey, keyword, status);
        }
        // users 模块：从 sys_user 表导出，复用 pageUsers（已含 PII 脱敏和 VIP 等级）
        if ("users".equals(moduleKey)) {
            PageResult<Map<String, Object>> result = pageUsers(keyword, status, 1, 5000);
            List<Map<String, Object>> rows = result.getRecords();
            StringBuilder sb = new StringBuilder("\uFEFF");
            sb.append("用户名,昵称,手机号,邮箱,VIP等级,Token余额,状态,注册时间\n");
            for (Map<String, Object> row : rows) {
                sb.append(String.join(",",
                        csv(str(row.get("username"))),
                        csv(str(row.get("nickname"))),
                        csv(str(row.get("phone"))),
                        csv(str(row.get("email"))),
                        csv(str(row.get("userLevelName"))),
                        csv(str(row.get("tokenBalance"))),
                        csv(str(row.get("status"))),
                        csv(str(row.get("createdTime")))
                )).append("\n");
            }
            return sb.toString();
        }
        ModuleCatalog.ModuleMeta meta = meta(moduleKey);
        List<Map<String, Object>> rows;
        if ("ai-usage".equals(moduleKey)) {
            rows = aiBillingService.pageUsageLogs(1, 5000, keyword, null, status).getRecords();
        } else if ("ai-token".equals(moduleKey)) {
            rows = aiBillingService.pageLedger(1, 5000, keyword, "ai_charge").getRecords();
        } else {
            List<Object> args = new ArrayList<>();
            String where = buildWhere(moduleKey, keyword, status, args);
            rows = jdbcTemplate.query(
                    "SELECT id,module_key,status,json_text,created_time,updated_time FROM admin_module_record" + where + " ORDER BY id DESC LIMIT 5000",
                    (rs, rowNum) -> normalizeRecord(
                            rs.getLong("id"),
                            rs.getString("module_key"),
                            rs.getString("status"),
                            rs.getString("json_text"),
                            String.valueOf(rs.getTimestamp("created_time")),
                            String.valueOf(rs.getTimestamp("updated_time"))
                    ),
                    args.toArray()
            );
        }
        StringBuilder sb = new StringBuilder("\uFEFF");
        List<Map<String, Object>> columns = meta.columns();
        sb.append(columns.stream().map(c -> csv(String.valueOf(c.get("label")))).collect(Collectors.joining(","))).append("\n");
        for (Map<String, Object> row : rows) {
            sb.append(columns.stream().map(c -> csv(String.valueOf(row.getOrDefault(String.valueOf(c.get("prop")), "")))).collect(Collectors.joining(","))).append("\n");
        }
        return sb.toString();
    }

    public List<Map<String, Object>> recentEvents() {
        // 后台仪表盘「最近后台操作」时间线：聚合 operation_log 表中最近 10 条记录。
        // 兼容 operation_log 表不存在的情况（启动早期或未迁移时），避免 500。
        try {
            Integer exists = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'operation_log'",
                    Integer.class);
            if (exists == null || exists == 0) {
                throw new BizException(503, "后台操作日志能力暂时不可用");
            }
            return jdbcTemplate.queryForList(
                    "SELECT id, " +
                            "COALESCE(NULLIF(operation_type, ''), 'SYSTEM') AS module, " +
                            "COALESCE(NULLIF(operation_desc, ''), operation_type) AS action, " +
                            "target_id AS targetId, " +
                            "DATE_FORMAT(created_time, '%Y-%m-%d %H:%i:%s') AS time, " +
                            "CASE WHEN result = 1 OR result IS NULL THEN '成功' ELSE '失败' END AS result " +
                            "FROM operation_log WHERE deleted = 0 ORDER BY created_time DESC LIMIT 10");
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw dependencyUnavailable("后台操作日志", e);
        }
    }

    public List<Map<String, Object>> menus() {
        throw new BizException(503, "动态菜单后端尚未启用，请使用前端路由模式");
    }

    private String buildWhere(String moduleKey, String keyword, String status, List<Object> args) {
        String where = " WHERE module_key = ? AND deleted = 0 ";
        args.add(moduleKey);
        if (StringUtils.hasText(keyword)) {
            where += " AND json_text LIKE ? ";
            args.add("%" + keyword + "%");
        }
        if (StringUtils.hasText(status)) {
            where += " AND (status = ? OR json_text LIKE ?) ";
            args.add(status);
            args.add("%" + status + "%");
        }
        return where;
    }

    private Map<String, Object> normalizeRecord(long id, String moduleKey, String status, String json, String createdTime, String updatedTime) {
        Map<String, Object> data = parseJson(json);
        data.put("id", id);
        data.putIfAbsent("moduleKey", moduleKey);
        data.putIfAbsent("status", status);
        data.putIfAbsent("createdTime", createdTime);
        data.putIfAbsent("updatedTime", updatedTime);
        return data;
    }

    private Map<String, Object> parseJson(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<LinkedHashMap<String, Object>>() {});
        } catch (Exception e) {
            throw dependencyUnavailable("模块数据解析", e);
        }
    }

    private Map<String, Object> maskIfNeeded(String moduleKey, Map<String, Object> row) {
        if (!"system-settings".equals(moduleKey)
                && !"model-config-general".equals(moduleKey)
                && !"model-config-chat".equals(moduleKey)
                && !"model-config-image".equals(moduleKey)
                && !"model-config-image-2".equals(moduleKey)
                && !"model-config-image-3".equals(moduleKey)
                && !"model-config-image-prompts".equals(moduleKey)
                && !"xianyu-accounts".equals(moduleKey)
                && !"notification-config".equals(moduleKey)
                && !"smtp-config".equals(moduleKey)) {
            return row;
        }
        Map<String, Object> copy = new LinkedHashMap<>(row);
        // 统一敏感字段掩码：包含 API Key、Cookie、密码、各类 Secret、SMTP 密码等
        for (String key : List.of(
                "settingValue", "apiKey", "cookie", "cookieText", "cookieStr", "websocketToken",
                "password", "proxyPassword",
                // 通知渠道 / OAuth Secret
                "secret", "appSecret", "clientSecret",
                // SMTP 邮件密码
                "smtpPass", "smtpPassword"
        )) {
            Object v = copy.get(key);
            if (v != null && !String.valueOf(v).isBlank()) {
                copy.put(key, "******");
            }
        }
        return copy;
    }


    @SuppressWarnings("unchecked")
    private void preserveMaskedSecrets(String moduleKey, Object id, Map<String, Object> data) {
        if (!isModelConfigModule(moduleKey) || id == null || String.valueOf(id).isBlank()) return;
        Object apiKey = data.get("apiKey");
        if (apiKey == null || !"******".equals(String.valueOf(apiKey))) return;
        try {
            String oldJson = jdbcTemplate.queryForObject(
                    "SELECT json_text FROM admin_module_record WHERE id=? AND module_key=? AND deleted=0",
                    String.class,
                    Long.parseLong(String.valueOf(id)),
                    moduleKey
            );
            if (oldJson != null && !oldJson.isBlank()) {
                Map<String, Object> old = objectMapper.readValue(oldJson, Map.class);
                Object oldKey = old.get("apiKey");
                if (oldKey != null && !String.valueOf(oldKey).isBlank() && !"******".equals(String.valueOf(oldKey))) {
                    data.put("apiKey", oldKey);
                }
            }
        } catch (Exception e) {
            throw dependencyUnavailable("已保存的模型密钥", e);
        }
    }

    private void requireAvailableModule(String moduleKey) {
        if (moduleKey == null || moduleKey.isBlank()) {
            throw new BizException(400, "模块标识不能为空");
        }
        try {
            catalog.get(moduleKey);
        } catch (IllegalArgumentException e) {
            throw new BizException(400, "未知的管理模块");
        }
        if (MODULES_WITHOUT_REAL_BACKEND.contains(moduleKey)) {
            throw new BizException(503, "该管理模块尚未接入真实后端能力，当前不可用");
        }
    }

    private BizException dependencyUnavailable(String operation, Exception cause) {
        if (cause instanceof BizException bizException) {
            return bizException;
        }
        log.error("{} unavailable (type={})", operation, cause.getClass().getName());
        return new BizException(503, operation + "暂时不可用，请稍后重试");
    }

    private int requireAffected(int affected, String message) {
        if (affected == 0) {
            throw new BizException(404, message);
        }
        return affected;
    }

    private Long optionalPositiveId(Object rawId) {
        if (rawId == null || String.valueOf(rawId).isBlank()) {
            return null;
        }
        try {
            long id = Long.parseLong(String.valueOf(rawId));
            requirePositiveId(id);
            return id;
        } catch (NumberFormatException e) {
            throw new BizException(400, "记录标识格式不正确");
        }
    }

    private void requirePositiveId(long id) {
        if (id <= 0) {
            throw new BizException(400, "记录标识必须大于 0");
        }
    }

    private void requireIds(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            throw new BizException(400, "请选择至少一条记录");
        }
        if (ids.stream().anyMatch(id -> id == null || id <= 0)) {
            throw new BizException(400, "记录标识必须大于 0");
        }
    }

    private void requireStatus(String status) {
        if (status == null || status.isBlank()) {
            throw new BizException(400, "status 不能为空");
        }
    }
    private void prepareModelConfigData(String moduleKey, Map<String, Object> data) {
        if (!isModelConfigModule(moduleKey)) {
            return;
        }
        syncBooleanStatus(data, "enabled");
        syncBooleanStatus(data, "safeReview");
        syncBooleanStatus(data, "streamOutput");
        syncBooleanStatus(data, "preprocess");
    }

    private boolean isModelConfigModule(String moduleKey) {
        return List.of("model-config-general", "model-config-chat", "model-config-image",
                "model-config-image-2", "model-config-image-3", "model-config-image-prompts").contains(moduleKey);
    }

    private void validateModelProviderEndpoints(String moduleKey, Map<String, Object> data) {
        if (!isModelConfigModule(moduleKey) || "model-config-image-prompts".equals(moduleKey)) {
            return;
        }
        for (String key : List.of("baseUrl", "proxyBaseUrl")) {
            Object value = data.get(key);
            if (value != null && !String.valueOf(value).isBlank()) {
                data.put(key, aiProviderEndpointPolicy.validateBaseUrl(String.valueOf(value)));
            }
        }
    }

    private void syncBooleanStatus(Map<String, Object> data, String key) {
        if (!data.containsKey(key)) {
            return;
        }
        Object value = data.get(key);
        if (value instanceof Boolean) {
            return;
        }
        String text = String.valueOf(value);
        data.put(key, "1".equals(text) || "true".equalsIgnoreCase(text) || "正常".equals(text) || "启用".equals(text));
    }

    private String str(Object o) {
        return o == null ? "" : String.valueOf(o);
    }

    private String csv(String s) {
        return CsvCellEncoder.encode(s);
    }

    private String now() {
        return LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
    }

    private long count(String moduleKey) {
        Long c = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM admin_module_record WHERE module_key=? AND deleted=0", Long.class, moduleKey);
        return c == null ? 0 : c;
    }

    private long countToday(String moduleKey) {
        Long c = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM admin_module_record WHERE module_key=? AND deleted=0 AND DATE(created_time)=CURRENT_DATE()", Long.class, moduleKey);
        return c == null ? 0 : c;
    }

    private long countByStatusLike(String moduleKey, List<String> words) {
        if (words == null || words.isEmpty()) {
            return 0;
        }
        String cond = words.stream().map(w -> "(status LIKE ? OR json_text LIKE ?)").collect(Collectors.joining(" OR "));
        List<Object> args = new ArrayList<>();
        args.add(moduleKey);
        for (String w : words) {
            args.add("%" + w + "%");
            args.add("%" + w + "%");
        }
        Long c = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM admin_module_record WHERE module_key=? AND deleted=0 AND (" + cond + ")",
                Long.class,
                args.toArray()
        );
        return c == null ? 0 : c;
    }

}
