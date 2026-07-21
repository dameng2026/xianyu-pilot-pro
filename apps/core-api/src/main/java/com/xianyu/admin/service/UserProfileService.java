package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.sql.Date;
import java.security.SecureRandom;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Locale;

/**
 * 前台个人中心服务。
 * 负责个人概览、账户安全、密码/手机号/邮箱修改和安全日志。
 */
@Service
public class UserProfileService {
    private static final Logger log = LoggerFactory.getLogger(UserProfileService.class);
    private static final long CODE_TTL_MS = 5 * 60 * 1000L;
    private static final String PASSWORD_POLICY_MESSAGE = "密码需为8-32位，且包含字母和数字";

    private final JdbcTemplate jdbcTemplate;
    private final UserAuthCapabilityService capabilityService;
    private final UserSecurityAuditService securityAuditService;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
    private final SecureRandom secureRandom = new SecureRandom();
    private final Map<String, Map<String, Object>> codeStore = new ConcurrentHashMap<>();

    @Autowired
    public UserProfileService(JdbcTemplate jdbcTemplate, UserAuthCapabilityService capabilityService,
                              UserSecurityAuditService securityAuditService) {
        this.jdbcTemplate = jdbcTemplate;
        this.capabilityService = capabilityService;
        this.securityAuditService = securityAuditService;
    }

    UserProfileService(JdbcTemplate jdbcTemplate, UserAuthCapabilityService capabilityService) {
        this(jdbcTemplate, capabilityService, new UserSecurityAuditService(jdbcTemplate));
    }

    public Map<String, Object> overview() {
        Long userId = UserContext.userId();
        Map<String, Object> user = jdbcTemplate.queryForMap(
                "SELECT u.id, u.username, u.nickname, u.phone, u.email, u.avatar, u.status, u.tenant_id, " +
                        "u.last_login_time, u.created_time, u.token_balance, u.phone_verified, u.email_verified, " +
                        "u.last_security_update_time, COALESCE(t.display_name, t.tenant_name, t.name) AS tenant_name " +
                        "FROM sys_user u LEFT JOIN sys_tenant t ON t.id = u.tenant_id AND t.deleted = 0 " +
                        "WHERE u.id=? AND u.deleted=0", userId);

        Map<String, Object> activePlan = queryActivePlan(userId);
        Map<String, Object> stats = queryBusinessStats(userId, user.get("tenant_id"));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("userId", user.get("id"));
        result.put("username", user.get("username"));
        result.put("nickname", valueOr(user.get("nickname"), user.get("username")));
        result.put("phone", valueOr(user.get("phone"), ""));
        result.put("email", valueOr(user.get("email"), ""));
        result.put("avatar", valueOr(user.get("avatar"), ""));
        result.put("tenantId", user.get("tenant_id"));
        result.put("tenantName", valueOr(user.get("tenant_name"), ""));
        result.put("status", user.get("status"));
        result.put("tokenBalance", numberOrZero(user.get("token_balance")));
        result.put("phoneVerified", boolInt(user.get("phone_verified")));
        result.put("emailVerified", boolInt(user.get("email_verified")));
        result.put("lastLoginTime", user.get("last_login_time"));
        result.put("createdTime", user.get("created_time"));
        result.put("lastSecurityUpdateTime", user.get("last_security_update_time"));
        result.put("activePlan", activePlan);
        result.put("stats", stats);
        return result;
    }

    public Map<String, Object> activePlan(Long userId) {
        return new LinkedHashMap<>(queryActivePlan(userId));
    }

    public Map<String, Object> sendCode(String targetType, String target, String purpose, String ip, String userAgent) {
        capabilityService.requireProfileVerification();
        String normalizedType = normalizeType(targetType);
        String normalizedPurpose = StringUtils.hasText(purpose) ? purpose.trim() : "bind";
        String normalizedTarget = normalizeTarget(normalizedType, target);
        Long userId = UserContext.userId();

        String code = String.format("%06d", secureRandom.nextInt(1_000_000));
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("code", code);
        entry.put("expireAt", System.currentTimeMillis() + CODE_TTL_MS);
        entry.put("purpose", normalizedPurpose);
        entry.put("targetType", normalizedType);
        codeStore.put(codeKey(userId, normalizedType, normalizedTarget, normalizedPurpose), entry);

        log.info("本地开发个人中心验证码生成: userId={}, targetType={}, target={}, purpose={}",
                userId, normalizedType, mask(normalizedType, normalizedTarget), normalizedPurpose);
        securityAuditService.recordRequired(UserContext.getTenantId(), userId,
                "send_code", "发送验证码", normalizedType + ":" + mask(normalizedType, normalizedTarget), 1,
                "验证码已生成", ip, userAgent);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("expireSeconds", CODE_TTL_MS / 1000);
        result.put("targetType", normalizedType);
        result.put("target", mask(normalizedType, normalizedTarget));
        result.put("debugCode", code);
        return result;
    }

    @Transactional
    public void changePassword(String oldPassword, String newPassword, String ip, String userAgent) {
        Long userId = UserContext.userId();
        if (userId == null || userId <= 0) throw new BizException(401, "登录状态已失效，请重新登录");
        if (!StringUtils.hasText(oldPassword)) throw new BizException(400, "当前密码不能为空");
        if (oldPassword.length() > 256) throw new BizException(400, "当前密码长度不合法");
        validatePassword(newPassword);
        if (Objects.equals(oldPassword, newPassword)) throw new BizException(400, "新密码不能与当前密码相同");

        Map<String, Object> user = jdbcTemplate.queryForMap(
                "SELECT id, password_hash FROM sys_user WHERE id=? AND deleted=0", userId);
        Object storedValue = user.get("password_hash");
        String stored = storedValue instanceof String ? ((String) storedValue).trim() : null;
        if (!verifyPassword(oldPassword, stored)) {
            securityAuditService.recordRejectedRequired(UserContext.getTenantId(), userId,
                    "change_password", "修改密码", "password", "当前密码错误", ip, userAgent);
            throw new BizException(400, "当前密码错误");
        }
        int affected = jdbcTemplate.update("UPDATE sys_user SET password_hash=?, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE id=? AND deleted=0",
                encoder.encode(newPassword), userId);
        if (affected != 1) throw new BizException(409, "账号安全状态已变化，请重新登录后重试");
        securityAuditService.recordRequired(UserContext.getTenantId(), userId,
                "change_password", "修改密码", "password", 1, "密码修改成功", ip, userAgent);
    }

    @Transactional
    public void changePhone(String phone, String code, String ip, String userAgent) {
        capabilityService.requireProfileVerification();
        Long userId = UserContext.userId();
        String normalized = normalizeTarget("phone", phone);
        verifyCode(userId, "phone", normalized, "change_phone", code);
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM sys_user WHERE phone=? AND deleted=0 AND id<>?", Long.class, normalized, userId);
        if (count != null && count > 0) throw new BizException(400, "该手机号已被其他账号绑定");
        int affected = jdbcTemplate.update("UPDATE sys_user SET phone=?, phone_verified=1, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE id=? AND deleted=0",
                normalized, userId);
        if (affected != 1) throw new BizException(409, "账号安全状态已变化，请重新登录后重试");
        securityAuditService.recordRequired(UserContext.getTenantId(), userId,
                "change_phone", "修改手机号", mask("phone", normalized), 1, "手机号修改成功", ip, userAgent);
    }

    @Transactional
    public void changeEmail(String email, String code, String ip, String userAgent) {
        capabilityService.requireProfileVerification();
        Long userId = UserContext.userId();
        String normalized = normalizeTarget("email", email);
        verifyCode(userId, "email", normalized, "change_email", code);
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM sys_user WHERE email=? AND deleted=0 AND id<>?", Long.class, normalized, userId);
        if (count != null && count > 0) throw new BizException(400, "该邮箱已被其他账号绑定");
        int affected = jdbcTemplate.update("UPDATE sys_user SET email=?, email_verified=1, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE id=? AND deleted=0",
                normalized, userId);
        if (affected != 1) throw new BizException(409, "账号安全状态已变化，请重新登录后重试");
        securityAuditService.recordRequired(UserContext.getTenantId(), userId,
                "change_email", "修改邮箱", mask("email", normalized), 1, "邮箱修改成功", ip, userAgent);
    }

    public List<Map<String, Object>> recentSecurityLogs(Long userId, int limit) {
        int safeLimit = Math.max(1, Math.min(limit, 50));
        try {
            return jdbcTemplate.queryForList(
                    "SELECT id, action_type AS actionType, action_name AS actionName, target, result_status AS resultStatus, message, ip_address AS ipAddress, created_time AS createdTime " +
                            "FROM user_security_log WHERE user_id=? AND deleted=0 ORDER BY id DESC LIMIT " + safeLimit,
                    userId);
        } catch (DataAccessException e) {
            throw unavailable("安全日志", e);
        }
    }

    /**
     * 查询当前用户的 Token 消耗明细（分页）。
     * 同时返回今日消耗、七日消耗和 Token 余额统计。
     */
    public Map<String, Object> tokenLedger(int current, int size) {
        Long userId = UserContext.userId();
        int safeSize = Math.max(1, Math.min(size, 500));
        int offset = Math.max(0, (current - 1)) * safeSize;

        long total;
        try {
            Long n = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM token_balance_ledger WHERE user_id=?", Long.class, userId);
            total = n == null ? 0 : n;
        } catch (DataAccessException e) {
            throw unavailable("Token 明细", e);
        }

        List<Map<String, Object>> records;
        try {
            records = jdbcTemplate.queryForList(
                    "SELECT id, change_type AS changeType, change_amount AS changeAmount, " +
                            "before_balance AS beforeBalance, after_balance AS afterBalance, " +
                            "ref_type AS refType, ref_no AS refNo, remark, created_time AS createdTime " +
                            "FROM token_balance_ledger WHERE user_id=? " +
                            "ORDER BY id DESC LIMIT ? OFFSET ?",
                    userId, safeSize, offset);
        } catch (DataAccessException e) {
            throw unavailable("Token 明细", e);
        }
        // 统一根据 changeType 覆盖 remark 文案，避免历史数据因数据库字符集问题出现乱码
        for (Map<String, Object> row : records) {
            String changeType = row.get("changeType") == null ? "" : String.valueOf(row.get("changeType"));
            row.put("remark", remarkForChangeType(changeType, row.get("remark")));
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("records", records);
        result.put("total", total);
        result.put("current", current);
        result.put("size", safeSize);
        result.put("stats", queryTokenStats(userId));
        return result;
    }

    /**
     * 查询当前用户的 Token 充值记录（分页）。
     * 仅查询 token_recharge_record 表中当前用户的记录，按时间倒序。
     * 同时返回累计充值 Token 数、累计充值笔数统计。
     */
    public Map<String, Object> rechargeRecords(int current, int size) {
        Long userId = UserContext.userId();
        int safeSize = Math.max(1, Math.min(size, 100));
        int safeCurrent = Math.max(1, current);
        int offset = (safeCurrent - 1) * safeSize;

        long total;
        try {
            Long n = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM token_recharge_record WHERE user_id=?", Long.class, userId);
            total = n == null ? 0 : n;
        } catch (DataAccessException e) {
            throw unavailable("充值记录", e);
        }

        List<Map<String, Object>> records;
        try {
            records = jdbcTemplate.queryForList(
                    "SELECT id, payment_order_id AS paymentOrderId, order_no AS orderNo, " +
                            "token_amount AS tokenAmount, before_balance AS beforeBalance, after_balance AS afterBalance, " +
                            "source, remark, created_time AS createdTime " +
                            "FROM token_recharge_record WHERE user_id=? " +
                            "ORDER BY id DESC LIMIT ? OFFSET ?",
                    userId, safeSize, offset);
        } catch (DataAccessException e) {
            throw unavailable("充值记录", e);
        }

        long totalTokens = 0L;
        try {
            Long t = jdbcTemplate.queryForObject(
                    "SELECT COALESCE(SUM(token_amount),0) FROM token_recharge_record WHERE user_id=?", Long.class, userId);
            if (t != null) totalTokens = t;
        } catch (DataAccessException e) {
            throw unavailable("充值记录汇总", e);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("records", records);
        result.put("total", total);
        result.put("current", safeCurrent);
        result.put("size", safeSize);
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("totalRecords", total);
        stats.put("totalTokens", totalTokens);
        result.put("stats", stats);
        return result;
    }

    /**
     * 查询 Token 统计信息：今日消耗、七日消耗、Token 余额。
     * 消耗金额取 change_amount < 0 的绝对值之和（ai_charge / ai_image_charge 为负数）。
     * 今日消耗：今天 0 点至今；七日消耗：当前时刻往前滚动 7×24 小时。
     */
    private Map<String, Object> queryTokenStats(Long userId) {
        Map<String, Object> stats = new LinkedHashMap<>();

        long balance = 0L;
        try {
            Long b = jdbcTemplate.queryForObject(
                    "SELECT token_balance FROM sys_user WHERE id=? AND deleted=0", Long.class, userId);
            if (b != null) balance = b;
        } catch (DataAccessException e) {
            throw unavailable("Token 余额", e);
        }
        stats.put("tokenBalance", balance);

        long todayConsume = 0L;
        try {
            Number t = jdbcTemplate.queryForObject(
                    "SELECT COALESCE(SUM(change_amount), 0) FROM token_balance_ledger " +
                            "WHERE user_id=? AND change_amount < 0 AND created_time >= CURDATE()",
                    Number.class, userId);
            if (t != null) todayConsume = -t.longValue();
        } catch (DataAccessException e) {
            throw unavailable("今日 Token 消耗", e);
        }
        stats.put("todayConsume", todayConsume);

        long sevenDayConsume = 0L;
        try {
            Number s = jdbcTemplate.queryForObject(
                    "SELECT COALESCE(SUM(change_amount), 0) FROM token_balance_ledger " +
                            "WHERE user_id=? AND change_amount < 0 AND created_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
                    Number.class, userId);
            if (s != null) sevenDayConsume = -s.longValue();
        } catch (DataAccessException e) {
            throw unavailable("七日 Token 消耗", e);
        }
        stats.put("sevenDayConsume", sevenDayConsume);

        long monthConsume = 0L;
        try {
            Number m = jdbcTemplate.queryForObject(
                    "SELECT COALESCE(SUM(change_amount), 0) FROM token_balance_ledger " +
                            "WHERE user_id=? AND change_amount < 0 AND created_time >= DATE_FORMAT(CURDATE(), '%Y-%m-01')",
                    Number.class, userId);
            if (m != null) monthConsume = -m.longValue();
        } catch (DataAccessException e) {
            throw unavailable("本月 Token 消耗", e);
        }
        stats.put("monthConsume", monthConsume);

        return stats;
    }

    /**
     * 查询当前用户的 Token 消耗趋势（按日聚合）与本月分类构成。
     * 仅统计 change_amount < 0 的扣费记录（取绝对值）。
     * - series：最近 days 天的每日消耗序列，缺失日期补 0，按日期升序排列。
     * - categories：本月各 ref_type 的消耗汇总，按消耗降序排列。
     */
    public Map<String, Object> tokenTrend(int days) {
        Long userId = UserContext.userId();
        int safeDays = Math.max(1, Math.min(days, 90));

        Map<LocalDate, Long> consumeMap = new LinkedHashMap<>();
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT DATE(created_time) AS d, " +
                            "COALESCE(SUM(CASE WHEN change_amount < 0 THEN -change_amount ELSE 0 END), 0) AS c " +
                            "FROM token_balance_ledger WHERE user_id=? AND change_amount < 0 " +
                            "AND created_time >= DATE_SUB(CURDATE(), INTERVAL ? DAY) " +
                            "GROUP BY DATE(created_time)",
                    userId, safeDays - 1);
            for (Map<String, Object> row : rows) {
                Object d = row.get("d");
                Object c = row.get("c");
                if (d == null || c == null) continue;
                LocalDate date;
                if (d instanceof java.util.Date) {
                    if (d instanceof Date) {
                        date = ((Date) d).toLocalDate();
                    } else {
                        date = ((java.util.Date) d).toInstant().atZone(ZoneId.systemDefault()).toLocalDate();
                    }
                } else {
                    date = LocalDate.parse(String.valueOf(d));
                }
                long amount = c instanceof Number ? ((Number) c).longValue() : 0L;
                consumeMap.put(date, amount);
            }
        } catch (DataAccessException e) {
            throw unavailable("Token 趋势", e);
        }

        List<Map<String, Object>> series = new ArrayList<>();
        LocalDate today = LocalDate.now();
        for (int i = safeDays - 1; i >= 0; i--) {
            LocalDate date = today.minusDays(i);
            long consume = consumeMap.getOrDefault(date, 0L);
            Map<String, Object> point = new LinkedHashMap<>();
            point.put("date", date.toString());
            point.put("consume", consume);
            series.add(point);
        }

        List<Map<String, Object>> categories = new ArrayList<>();
        try {
            List<Map<String, Object>> catRows = jdbcTemplate.queryForList(
                    "SELECT ref_type AS refType, " +
                            "COALESCE(SUM(-change_amount), 0) AS consume " +
                            "FROM token_balance_ledger WHERE user_id=? AND change_amount < 0 " +
                            "AND created_time >= DATE_FORMAT(CURDATE(), '%Y-%m-01') " +
                            "GROUP BY ref_type ORDER BY consume DESC",
                    userId);
            for (Map<String, Object> row : catRows) {
                Object refType = row.get("refType");
                Object consume = row.get("consume");
                long amount = consume instanceof Number ? ((Number) consume).longValue() : 0L;
                if (amount <= 0) continue;
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("refType", refType == null ? "" : String.valueOf(refType));
                item.put("consume", amount);
                categories.add(item);
            }
        } catch (DataAccessException e) {
            throw unavailable("Token 分类构成", e);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("days", safeDays);
        result.put("series", series);
        result.put("categories", categories);
        return result;
    }

    private Map<String, Object> queryActivePlan(Long userId) {
        // 优先读取 sys_user.vip_level 手动覆盖字段（与后台 enrichUserLevels 保持一致）
        try {
            Integer vipLevel = jdbcTemplate.queryForObject(
                    "SELECT vip_level FROM sys_user WHERE id=? AND deleted=0",
                    Integer.class, userId);
            if (vipLevel != null && vipLevel > 0) {
                Map<String, Object> plan = new LinkedHashMap<>();
                plan.put("planCode", vipLevel >= 2 ? "svp" : "vip");
                plan.put("planName", vipLevel >= 2 ? "SVP (手动)" : "VIP (手动)");
                plan.put("startTime", null);
                plan.put("endTime", null);
                return plan;
            }
        } catch (DataAccessException e) {
            throw unavailable("会员等级", e);
        }
        // 回退到 billing_subscription 订阅读取
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT p.plan_code, p.plan_name, s.start_time, s.end_time " +
                            "FROM billing_subscription s JOIN billing_plan p ON p.id=s.plan_id AND p.deleted=0 " +
                            "WHERE s.user_id=? AND s.status=1 AND s.target_type='user_account' " +
                            "AND (s.end_time IS NULL OR s.end_time>=NOW()) ORDER BY COALESCE(s.end_time, '9999-12-31') DESC LIMIT 1",
                    userId);
            if (!rows.isEmpty()) {
                Map<String, Object> row = rows.get(0);
                Map<String, Object> plan = new LinkedHashMap<>();
                plan.put("planCode", valueOr(row.get("plan_code"), "normal"));
                plan.put("planName", valueOr(row.get("plan_name"), "普通用户"));
                plan.put("startTime", row.get("start_time"));
                plan.put("endTime", row.get("end_time"));
                return plan;
            }
        } catch (DataAccessException e) {
            throw unavailable("订阅套餐", e);
        }
        return new LinkedHashMap<>(Map.of("planCode", "normal", "planName", "普通用户"));
    }

    public String currentPlanCode(Long userId) {
        Map<String, Object> active = queryActivePlan(userId);
        Object planCode = active.get("planCode");
        if (planCode == null) return "normal";
        String code = String.valueOf(planCode).trim().toLowerCase(Locale.ROOT);
        if (code.isBlank()) return "normal";
        return "svip".equals(code) ? "svp" : code;
    }

    private Map<String, Object> queryBusinessStats(Long userId, Object tenantIdObj) {
        Long tenantId = tenantIdObj instanceof Number ? ((Number) tenantIdObj).longValue() : UserContext.getTenantId();
        if (tenantId == null || tenantId <= 0) {
            throw new BizException(403, "账号租户配置异常，请联系管理员处理");
        }
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("xianyuAccountCount", count("xianyu_account", "user_id", userId, tenantId));
        stats.put("goodsCount", countGoods(userId, tenantId));
        stats.put("sellingGoodsCount", countGoodsByStatus(userId, tenantId, 0));
        stats.put("draftGoodsCount", countGoodsByStatus(userId, tenantId, 1));
        stats.put("orderCount", countOrders(userId, tenantId));
        stats.put("messageCount", countMessages(userId, tenantId));
        stats.put("conversationCount", countByTenant("xianyu_conversation", tenantId));
        stats.put("autoReplyRuleCount", countByTenant("auto_reply_rule", tenantId));
        stats.put("deliveryRuleCount", countByTenant("delivery_rule", tenantId));
        stats.put("cardGroupCount", countByTenant("card_group", tenantId));
        return stats;
    }

    private long count(String table, String userColumn, Long userId, Long tenantId) {
        try {
            if (!tableExists(table)) throw new BizException(503, "业务统计数据结构不可用");
            if (columnExists(table, userColumn)) {
                Long n = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM " + table + " WHERE deleted=0 AND " + userColumn + "=?", Long.class, userId);
                return n == null ? 0 : n;
            }
            if (tenantId != null && columnExists(table, "tenant_id")) {
                Long n = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM " + table + " WHERE deleted=0 AND tenant_id=?", Long.class, tenantId);
                return n == null ? 0 : n;
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("业务统计", e);
        }
        throw new BizException(503, "业务统计字段配置不可用");
    }

    private long countGoods(Long userId, Long tenantId) {
        try {
            if (!tableExists("xianyu_goods")) throw new BizException(503, "商品统计数据结构不可用");
            Long n = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM xianyu_goods g LEFT JOIN xianyu_account a ON a.id=g.account_id " +
                            "WHERE g.deleted=0 AND (a.user_id=? OR (? IS NOT NULL AND g.tenant_id=?))",
                    Long.class, userId, tenantId, tenantId);
            return n == null ? 0 : n;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("商品统计", e);
        }
    }


    private long countGoodsByStatus(Long userId, Long tenantId, int status) {
        try {
            if (!tableExists("xianyu_goods")) throw new BizException(503, "商品统计数据结构不可用");
            Long n = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM xianyu_goods g LEFT JOIN xianyu_account a ON a.id=g.account_id " +
                            "WHERE g.deleted=0 AND g.status=? AND (a.user_id=? OR (? IS NOT NULL AND g.tenant_id=?))",
                    Long.class, status, userId, tenantId, tenantId);
            return n == null ? 0 : n;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("商品状态统计", e);
        }
    }

    private long countByTenant(String table, Long tenantId) {
        try {
            if (tenantId == null || !tableExists(table) || !columnExists(table, "tenant_id")) {
                throw new BizException(503, "租户统计数据结构不可用");
            }
            String deleted = columnExists(table, "deleted") ? " AND deleted=0" : "";
            Long n = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM " + table + " WHERE tenant_id=?" + deleted, Long.class, tenantId);
            return n == null ? 0 : n;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("租户统计", e);
        }
    }
    private long countOrders(Long userId, Long tenantId) {
        try {
            if (!tableExists("xianyu_trade_order")) throw new BizException(503, "订单统计数据结构不可用");
            Long n = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM xianyu_trade_order o LEFT JOIN xianyu_account a ON a.id=o.account_id " +
                            "WHERE o.deleted=0 AND (a.user_id=? OR (? IS NOT NULL AND o.tenant_id=?))",
                    Long.class, userId, tenantId, tenantId);
            return n == null ? 0 : n;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("订单统计", e);
        }
    }

    private long countMessages(Long userId, Long tenantId) {
        try {
            if (!tableExists("xianyu_message")) throw new BizException(503, "消息统计数据结构不可用");
            Long n = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM xianyu_message m LEFT JOIN xianyu_account a ON a.id=m.account_id " +
                            "WHERE m.deleted=0 AND (a.user_id=? OR (? IS NOT NULL AND m.tenant_id=?))",
                    Long.class, userId, tenantId, tenantId);
            return n == null ? 0 : n;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("消息统计", e);
        }
    }

    private void verifyCode(Long userId, String targetType, String target, String purpose, String code) {
        if (!StringUtils.hasText(code)) throw new BizException(400, "验证码不能为空");
        String key = codeKey(userId, targetType, target, purpose);
        Map<String, Object> entry = codeStore.get(key);
        if (entry == null) throw new BizException(400, "请先获取验证码");
        if (System.currentTimeMillis() > ((Number) entry.get("expireAt")).longValue()) {
            codeStore.remove(key);
            throw new BizException(400, "验证码已过期");
        }
        if (!Objects.equals(code, entry.get("code"))) throw new BizException(400, "验证码错误");
        codeStore.remove(key);
    }

    private String normalizeType(String targetType) {
        String type = StringUtils.hasText(targetType) ? targetType.trim().toLowerCase(Locale.ROOT) : "phone";
        if (!type.equals("phone") && !type.equals("email")) throw new BizException(400, "验证码类型只支持 phone/email");
        return type;
    }

    private String normalizeTarget(String type, String target) {
        if (!StringUtils.hasText(target)) throw new BizException(400, type.equals("phone") ? "手机号不能为空" : "邮箱不能为空");
        String value = target.trim();
        if (type.equals("phone") && !value.matches("^1\\d{10}$")) throw new BizException(400, "手机号格式错误");
        if (type.equals("email") && !value.matches("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")) throw new BizException(400, "邮箱格式错误");
        return value;
    }

    private String codeKey(Long userId, String type, String target, String purpose) {
        return userId + ":" + type + ":" + purpose + ":" + target;
    }

    private boolean verifyPassword(String plainPassword, String storedHash) {
        if (!StringUtils.hasText(storedHash)) return false;
        if (storedHash.startsWith("$2a$") || storedHash.startsWith("$2b$") || storedHash.startsWith("$2y$")) {
            try {
                return encoder.matches(plainPassword, storedHash);
            } catch (IllegalArgumentException exception) {
                return false;
            }
        }
        return MessageDigest.isEqual(
                plainPassword.getBytes(StandardCharsets.UTF_8),
                storedHash.getBytes(StandardCharsets.UTF_8)
        );
    }

    private void validatePassword(String password) {
        if (password == null
                || !password.matches("^(?=.*[A-Za-z])(?=.*\\d).{8,32}$")
                || password.getBytes(StandardCharsets.UTF_8).length > 72) {
            throw new BizException(400, PASSWORD_POLICY_MESSAGE);
        }
    }

    private String mask(String type, String value) {
        if (!StringUtils.hasText(value)) return "";
        if ("phone".equals(type) && value.length() >= 11) return value.substring(0, 3) + "****" + value.substring(7);
        int at = value.indexOf('@');
        if ("email".equals(type) && at > 1) return value.charAt(0) + "***" + value.substring(at);
        return value;
    }

    private Object valueOr(Object value, Object fallback) {
        if (value == null) return fallback;
        String text = String.valueOf(value);
        return text.isBlank() ? fallback : value;
    }

    private long numberOrZero(Object value) {
        if (value instanceof Number n) return n.longValue();
        if (value == null) return 0L;
        try { return Long.parseLong(String.valueOf(value)); } catch (Exception ignored) { return 0L; }
    }

    private boolean boolInt(Object value) {
        if (value instanceof Number n) return n.intValue() == 1;
        return "1".equals(String.valueOf(value)) || "true".equalsIgnoreCase(String.valueOf(value));
    }

    private boolean tableExists(String tableName) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = ?",
                    Integer.class, tableName);
            return count != null && count > 0;
        } catch (DataAccessException e) {
            throw unavailable("数据表检查", e);
        }
    }

    private boolean columnExists(String tableName, String columnName) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = ? AND column_name = ?",
                    Integer.class, tableName, columnName);
            return count != null && count > 0;
        } catch (DataAccessException e) {
            throw unavailable("数据字段检查", e);
        }
    }

    private BizException unavailable(String feature, Exception cause) {
        log.warn("{}查询失败, errorType={}", feature, cause.getClass().getSimpleName());
        return new BizException(503, feature + "暂时不可用，请稍后重试");
    }

    /**
     * 根据 changeType 返回标准 remark 文案。
     * 用于覆盖数据库中可能因字符集问题产生的乱码 remark，保证前端展示一致。
     * 仅对已知 changeType 覆盖；未知类型保留原 remark。
     */
    private String remarkForChangeType(String changeType, Object rawRemark) {
        if (changeType == null) changeType = "";
        switch (changeType) {
            case "ai_charge":
                return "AI 调用扣费";
            case "ai_image_charge":
                return "商机发掘生图扣费";
            case "recharge":
                return "Token 充值";
            case "refund":
                return "退款返还";
            case "admin_adjust":
                return "管理员调整";
            case "system":
                return "系统调整";
            default:
                return rawRemark == null ? "" : String.valueOf(rawRemark);
        }
    }
}
