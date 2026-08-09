package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.TenantContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 系统用户管理服务（sys_user 表）。
 * 提供用户 CRUD、分页查询、状态管理等功能。
 */
@Service
public class SysUserService {
    private static final Logger log = LoggerFactory.getLogger(SysUserService.class);

    private final JdbcTemplate jdbcTemplate;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
    private final OperationAuditService auditService;

    public SysUserService(JdbcTemplate jdbcTemplate, OperationAuditService auditService) {
        this.jdbcTemplate = jdbcTemplate;
        this.auditService = auditService;
    }

    /**
     * 记录操作审计日志（失败不影响主流程）。
     * @param targetId 目标用户 ID
     * @param operationType 操作类型
     * @param operationDesc 操作描述
     */
    private void auditLogRequired(Long targetId, String operationType, String operationDesc) {
        Long operatorId = AdminContext.userId();
        Long tenantId = TenantContext.getCurrentTenantId();
        auditService.recordRequired(tenantId, operatorId, operationType, operationDesc,
                "sys_user", targetId, null);
    }

    /**
     * 密码强度校验：至少 8 位，且必须同时包含字母和数字。
     * 在创建用户、重置密码、修改密码三个入口统一调用，避免策略散落。
     * @param password 明文密码
     * @param fieldName 错误提示中的字段名（如"密码"/"新密码"）
     */
    private void validatePasswordStrength(String password, String fieldName) {
        if (password == null || password.isEmpty()) {
            throw new BizException(400, fieldName + "不能为空");
        }
        if (password.length() < 8) {
            throw new BizException(400, fieldName + "至少 8 位");
        }
        if (!password.matches(".*[A-Za-z].*") || !password.matches(".*\\d.*")) {
            throw new BizException(400, fieldName + "必须同时包含字母和数字");
        }
    }

    public PageResult<Map<String, Object>> page(int current, int size,
                                                 String username, String nickname,
                                                 String phone, String email,
                                                 String status) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        String where = buildWhere(username, nickname, phone, email, status, args);

        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM sys_user u" + where, Long.class, args.toArray());

        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);

        List<Map<String, Object>> records = jdbcTemplate.query(
                "SELECT u.id, u.username, u.nickname, u.phone, u.email, " +
                "u.avatar, u.tenant_id, COALESCE(t.display_name, t.tenant_name, t.name) AS tenant_name, " +
                "u.status, u.last_login_time, u.last_login_ip, " +
                "u.created_time, u.updated_time, " +
                "COALESCE(u.token_balance, 0) AS token_balance " +
                "FROM sys_user u " +
                "LEFT JOIN sys_tenant t ON t.id = u.tenant_id AND t.deleted = 0" +
                where +
                " ORDER BY u.id DESC LIMIT ? OFFSET ?",
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("username", rs.getString("username"));
                    row.put("nickname", rs.getString("nickname"));
                    row.put("phone", rs.getString("phone"));
                    row.put("email", rs.getString("email"));
                    row.put("avatar", rs.getString("avatar"));
                    row.put("tenantId", rs.getObject("tenant_id"));
                    row.put("tenantName", rs.getString("tenant_name"));
                    row.put("status", rs.getObject("status"));
                    row.put("lastLoginTime", rs.getTimestamp("last_login_time"));
                    row.put("lastLoginIp", rs.getString("last_login_ip"));
                    row.put("createdTime", rs.getTimestamp("created_time"));
                    row.put("updatedTime", rs.getTimestamp("updated_time"));
                    row.put("tokenBalance", rs.getObject("token_balance"));
                    return row;
                },
                pageArgs.toArray()
        );

        enrichUserLevels(records);
        return new PageResult<>(records, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public Map<String, Object> detail(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.query(
                "SELECT u.id, u.username, u.nickname, u.phone, u.email, " +
                "u.avatar, u.tenant_id, COALESCE(t.display_name, t.tenant_name, t.name) AS tenant_name, " +
                "u.status, u.last_login_time, u.last_login_ip, " +
                "u.created_time, u.updated_time, " +
                "COALESCE(u.token_balance, 0) AS token_balance " +
                "FROM sys_user u " +
                "LEFT JOIN sys_tenant t ON t.id = u.tenant_id AND t.deleted = 0 " +
                "WHERE u.id=? AND u.deleted=0",
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("username", rs.getString("username"));
                    row.put("nickname", rs.getString("nickname"));
                    row.put("phone", rs.getString("phone"));
                    row.put("email", rs.getString("email"));
                    row.put("avatar", rs.getString("avatar"));
                    row.put("tenantId", rs.getObject("tenant_id"));
                    row.put("tenantName", rs.getString("tenant_name"));
                    row.put("status", rs.getObject("status"));
                    row.put("lastLoginTime", rs.getTimestamp("last_login_time"));
                    row.put("lastLoginIp", rs.getString("last_login_ip"));
                    row.put("createdTime", rs.getTimestamp("created_time"));
                    row.put("updatedTime", rs.getTimestamp("updated_time"));
                    row.put("tokenBalance", rs.getObject("token_balance"));
                    return row;
                },
                id
        );
        if (rows.isEmpty()) {
            throw new BizException(404, "用户不存在");
        }
        enrichUserLevels(rows);
        return rows.get(0);
    }

    @Transactional
    public Map<String, Object> create(Map<String, Object> data) {
        String username = String.valueOf(data.get("username")).trim();
        String password = String.valueOf(data.getOrDefault("password", "123456"));
        String confirmPassword = String.valueOf(data.getOrDefault("confirmPassword", ""));
        String nickname = String.valueOf(data.getOrDefault("nickname", ""));
        String phone = String.valueOf(data.getOrDefault("phone", ""));
        String email = String.valueOf(data.getOrDefault("email", ""));
        String avatar = String.valueOf(data.getOrDefault("avatar", ""));
        int status = parseInt(data.getOrDefault("status", "1"));
        Long tenantId = parseLong(data.get("tenantId"));

        // 如果没有指定租户，使用默认租户
        if (tenantId == null) {
            tenantId = findOrCreateDefaultTenantId();
        }

        if (username.isEmpty()) {
            throw new BizException(400, "登录账号不能为空");
        }
        // 创建用户强制密码强度校验（至少 8 位，含字母+数字）
        validatePasswordStrength(password, "密码");
        if (!confirmPassword.isEmpty() && !password.equals(confirmPassword)) {
            throw new BizException(400, "两次输入的密码不一致");
        }
        if (!phone.isEmpty() && !phone.matches("^1\\d{10}$")) {
            throw new BizException(400, "手机号格式不正确");
        }
        if (!email.isEmpty() && !email.matches("^[\\w.+-]+@[\\w-]+\\.[\\w.]+$")) {
            throw new BizException(400, "邮箱格式不正确");
        }

        Long existCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM sys_user WHERE username=? AND deleted=0",
                Long.class, username);
        if (existCount != null && existCount > 0) {
            throw new BizException(400, "该登录账号已存在");
        }

        if (!phone.isEmpty()) {
            Long phoneCount = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM sys_user WHERE phone=? AND deleted=0",
                    Long.class, phone);
            if (phoneCount != null && phoneCount > 0) {
                throw new BizException(400, "该手机号已被使用");
            }
        }

        if (!email.isEmpty()) {
            Long emailCount = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM sys_user WHERE email=? AND deleted=0",
                    Long.class, email);
            if (emailCount != null && emailCount > 0) {
                throw new BizException(400, "该邮箱已被使用");
            }
        }

        String passwordHash = encoder.encode(password);
        jdbcTemplate.update(
                "INSERT INTO sys_user(username, password_hash, nickname, phone, email, avatar, tenant_id, status, created_time, updated_time, deleted) " +
                "VALUES(?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                username, passwordHash,
                nickname.isEmpty() ? null : nickname,
                phone.isEmpty() ? null : phone,
                email.isEmpty() ? null : email,
                avatar.isEmpty() ? null : avatar,
                tenantId,
                status
        );

        Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        log.info("创建用户成功: id={}", newId);
        auditLogRequired(newId, "USER_CREATE", "创建用户: " + username);
        return detail(newId);
    }

    @Transactional
    public void resetPassword(long id, String newPassword) {
        // 重置密码强制强度校验（至少 8 位，含字母+数字）
        validatePasswordStrength(newPassword, "新密码");
        Long existCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM sys_user WHERE id=? AND deleted=0",
                Long.class, id);
        if (existCount == null || existCount == 0) {
            throw new BizException(404, "用户不存在");
        }
        String passwordHash = encoder.encode(newPassword);
        jdbcTemplate.update(
                "UPDATE sys_user SET password_hash=?, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE id=? AND deleted=0",
                passwordHash, id);
        log.info("管理员重置用户密码: userId={}", id);
        auditLogRequired(id, "USER_RESET_PASSWORD", "管理员重置用户密码");
    }

    @Transactional
    public Map<String, Object> update(long id, Map<String, Object> data) {
        Map<String, Object> existing = detail(id);
        Integer oldVipLevel = currentVipLevel(id);

        String username = String.valueOf(data.getOrDefault("username", existing.get("username"))).trim();
        String nickname = String.valueOf(data.getOrDefault("nickname", existing.getOrDefault("nickname", "")));
        String avatar = String.valueOf(data.getOrDefault("avatar", existing.getOrDefault("avatar", "")));
        int status = parseInt(data.getOrDefault("status", existing.get("status")));
        Long tenantId = data.containsKey("tenantId") ? parseLong(data.get("tenantId")) : null;

        // PII 字段处理：前端编辑时不传 phone/email 表示不修改（避免脱敏值写回）
        // - data 不含 key：保持原值
        // - data 含 key 但值为空字符串：清空为 null
        // - data 含 key 且有值：校验格式后更新
        String phone = null;
        if (data.containsKey("phone")) {
            phone = String.valueOf(data.get("phone")).trim();
        } else {
            Object existingPhone = existing.get("phone");
            phone = existingPhone == null ? "" : String.valueOf(existingPhone);
        }
        String email = null;
        if (data.containsKey("email")) {
            email = String.valueOf(data.get("email")).trim();
        } else {
            Object existingEmail = existing.get("email");
            email = existingEmail == null ? "" : String.valueOf(existingEmail);
        }

        // 仅当前端显式传值时校验格式（空字符串表示清空，不校验）
        if (data.containsKey("phone") && !phone.isEmpty() && !phone.matches("^1\\d{10}$")) {
            throw new BizException(400, "手机号格式不正确");
        }
        if (data.containsKey("email") && !email.isEmpty() && !email.matches("^[\\w.+-]+@[\\w-]+\\.[\\w.]+$")) {
            throw new BizException(400, "邮箱格式不正确");
        }

        // 手机号唯一性校验（仅当显式修改时）
        if (data.containsKey("phone") && !phone.isEmpty()) {
            Long phoneCount = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM sys_user WHERE phone=? AND deleted=0 AND id<>?",
                    Long.class, phone, id);
            if (phoneCount != null && phoneCount > 0) {
                throw new BizException(400, "该手机号已被使用");
            }
        }
        // 邮箱唯一性校验（仅当显式修改时）
        if (data.containsKey("email") && !email.isEmpty()) {
            Long emailCount = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM sys_user WHERE email=? AND deleted=0 AND id<>?",
                    Long.class, email, id);
            if (emailCount != null && emailCount > 0) {
                throw new BizException(400, "该邮箱已被使用");
            }
        }

        Long existCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM sys_user WHERE username=? AND deleted=0 AND id<>?",
                Long.class, username, id);
        if (existCount != null && existCount > 0) {
            throw new BizException(400, "用户名已存在");
        }

        List<Object> args = new ArrayList<>();
        StringBuilder sql = new StringBuilder("UPDATE sys_user SET username=?, nickname=?, phone=?, email=?, avatar=?, status=?, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW()");
        args.add(username);
        args.add(nickname.isEmpty() ? null : nickname);
        // 仅当前端显式传值时更新 phone/email，否则保持原值
        if (data.containsKey("phone")) {
            args.add(phone.isEmpty() ? null : phone);
        } else {
            args.add(existing.get("phone"));
        }
        if (data.containsKey("email")) {
            args.add(email.isEmpty() ? null : email);
        } else {
            args.add(existing.get("email"));
        }
        args.add(avatar.isEmpty() ? null : avatar);
        args.add(status);

        if (tenantId != null) {
            sql.append(", tenant_id=?");
            args.add(tenantId);
        }

        if (data.containsKey("password")) {
            String newPwd = String.valueOf(data.get("password"));
            if (StringUtils.hasText(newPwd)) {
                // 修改密码强制强度校验（至少 8 位，含字母+数字）
                validatePasswordStrength(newPwd, "新密码");
                sql.append(", password_hash=?");
                args.add(encoder.encode(newPwd));
            }
        }

        // VIP 等级：单事务内一并更新（字段由 DataInitializer 统一初始化）
        Integer newVipLevel = null;
        Integer vipDurationDays = null;
        if (data.containsKey("vipLevel")) {
            newVipLevel = parseInt(data.get("vipLevel"));
            sql.append(", vip_level=?");
            args.add(newVipLevel);
        }
        // 手动开通天数：与 VIP 等级一起下发，用于生成真实订阅到期时间
        if (data.containsKey("vipDurationDays")) {
            Long days = parseLong(data.get("vipDurationDays"));
            vipDurationDays = days == null ? null : days.intValue();
        }

        // Token 余额：单事务内一并更新
        if (data.containsKey("tokenBalance")) {
            Long tb = parseLong(data.get("tokenBalance"));
            sql.append(", token_balance=?");
            args.add(tb == null ? 0L : tb);
        }

        sql.append(" WHERE id=? AND deleted=0");
        args.add(id);

        int rows = jdbcTemplate.update(sql.toString(), args.toArray());
        if (rows == 0) {
            throw new BizException(404, "用户不存在");
        }

        // 手动会员等级变更（或显式下发开通天数）时同步订阅记录，提供真实的开通/到期时间数据
        if (newVipLevel != null && (data.containsKey("vipDurationDays") || !Objects.equals(oldVipLevel, newVipLevel))) {
            syncManualVipSubscription(id, newVipLevel, vipDurationDays);
        }

        log.info("更新用户成功: id={}", id);
        auditLogRequired(id, "USER_UPDATE", "更新用户信息: " + username);
        return detail(id);
    }

    @Transactional
    public void delete(long id) {
        int rows = jdbcTemplate.update(
                "UPDATE sys_user SET deleted=1, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE id=? AND deleted=0", id);
        if (rows == 0) {
            throw new BizException(404, "用户不存在");
        }
        log.info("删除用户: id={}", id);
        auditLogRequired(id, "USER_DELETE", "删除用户");
    }

    @Transactional
    public int batchDelete(List<Long> ids) {
        if (ids == null || ids.isEmpty()) return 0;
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>(ids);
        int n = jdbcTemplate.update(
                "UPDATE sys_user SET deleted=1, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE deleted=0 AND id IN (" + placeholders + ")",
                args.toArray());
        log.info("批量删除用户: ids={}, count={}", ids, n);
        for (Long id : ids) {
            auditLogRequired(id, "USER_BATCH_DELETE", "批量删除用户");
        }
        return n;
    }

    @Transactional
    public void updateStatus(long id, int status) {
        int rows = jdbcTemplate.update(
                "UPDATE sys_user SET status=?, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE id=? AND deleted=0", status, id);
        if (rows == 0) {
            throw new BizException(404, "用户不存在");
        }
        log.info("更新用户状态: id={}, status={}", id, status);
        auditLogRequired(id, "USER_UPDATE_STATUS", "更新用户状态: " + (status == 1 ? "启用" : "禁用"));
    }

    @Transactional
    public int batchUpdateStatus(List<Long> ids, int status) {
        if (ids == null || ids.isEmpty()) return 0;
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>();
        args.add(status);
        args.addAll(ids);
        int n = jdbcTemplate.update(
                "UPDATE sys_user SET status=?, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE deleted=0 AND id IN (" + placeholders + ")",
                args.toArray());
        log.info("批量更新用户状态: ids={}, status={}, count={}", ids, status, n);
        for (Long id : ids) {
            auditLogRequired(id, "USER_BATCH_UPDATE_STATUS", "批量更新用户状态: " + (status == 1 ? "启用" : "禁用"));
        }
        return n;
    }

    @Transactional
    public void updateTokenBalance(long id, long tokenBalance) {
        int rows = jdbcTemplate.update(
                "UPDATE sys_user SET token_balance=?, updated_time=NOW() WHERE id=? AND deleted=0",
                tokenBalance, id);
        if (rows == 0) {
            throw new BizException(404, "用户不存在");
        }
        log.info("更新用户 Token 余额: id={}, tokenBalance={}", id, tokenBalance);
        auditLogRequired(id, "USER_UPDATE_TOKEN_BALANCE", "更新用户 Token 余额: " + tokenBalance);
    }

    @Transactional
    public void updateVipLevel(long id, int vipLevel, Integer vipDurationDays) {
        int rows = jdbcTemplate.update(
                "UPDATE sys_user SET vip_level=?, updated_time=NOW() WHERE id=? AND deleted=0",
                vipLevel, id);
        if (rows == 0) {
            throw new BizException(404, "用户不存在");
        }
        log.info("更新用户 VIP 等级: id={}, vipLevel={}, vipDurationDays={}", id, vipLevel, vipDurationDays);
        auditLogRequired(id, "USER_UPDATE_VIP_LEVEL", "更新用户 VIP 等级: " + vipLevel);
        syncManualVipSubscription(id, vipLevel, vipDurationDays);
    }

    private Integer currentVipLevel(long userId) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT vip_level FROM sys_user WHERE id=? AND deleted=0", Integer.class, userId);
        } catch (DataAccessException e) {
            // vip_level 字段缺失等兼容场景
            return null;
        }
    }

    /**
     * 手动开通/变更会员等级时同步订阅记录，为前台提供真实的开通/到期时间数据。
     * vipLevel>0 时创建订阅（vipDurationDays 为开通天数，null/0 视为永久有效）；
     * vipLevel<=0 时停用该用户的手动订阅，回退为普通用户。
     */
    private void syncManualVipSubscription(long userId, int vipLevel, Integer vipDurationDays) {
        // 先停用该用户已有的手动订阅
        jdbcTemplate.update(
                "UPDATE billing_subscription SET status=0, updated_time=NOW() " +
                        "WHERE user_id=? AND target_type='user_account' AND source='admin_manual' AND status=1",
                userId);
        if (vipLevel <= 0) return;
        String planCode = vipLevel == 3 ? "vip-single" : (vipLevel >= 2 ? "svp" : "vip");
        List<Map<String, Object>> plans = jdbcTemplate.queryForList(
                "SELECT id FROM billing_plan WHERE plan_code=? AND deleted=0 ORDER BY id ASC LIMIT 1", planCode);
        if (plans.isEmpty()) {
            log.warn("同步手动会员订阅失败：未找到套餐 plan_code={}, userId={}", planCode, userId);
            return;
        }
        Long planId = ((Number) plans.get(0).get("id")).longValue();
        Long tenantId = currentTenantId(userId);
        if (tenantId == null) {
            log.warn("同步手动会员订阅失败：用户缺少 tenant_id, userId={}", userId);
            return;
        }
        int days = vipDurationDays == null ? 0 : Math.max(0, vipDurationDays);
        if (days > 0) {
            jdbcTemplate.update(
                    "INSERT INTO billing_subscription(tenant_id, user_id, plan_id, target_type, target_id, start_time, end_time, status, source, created_time, updated_time) " +
                            "VALUES(?,?,?,'user_account',NULL,NOW(),DATE_ADD(NOW(), INTERVAL ? DAY),1,'admin_manual',NOW(),NOW())",
                    tenantId, userId, planId, days);
        } else {
            jdbcTemplate.update(
                    "INSERT INTO billing_subscription(tenant_id, user_id, plan_id, target_type, target_id, start_time, end_time, status, source, created_time, updated_time) " +
                            "VALUES(?,?,?,'user_account',NULL,NOW(),NULL,1,'admin_manual',NOW(),NOW())",
                    tenantId, userId, planId);
        }
        log.info("同步手动会员订阅: userId={}, vipLevel={}, vipDurationDays={}, planId={}", userId, vipLevel, days, planId);
    }

    private Long currentTenantId(long userId) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT tenant_id FROM sys_user WHERE id=? AND deleted=0", Long.class, userId);
        } catch (DataAccessException e) {
            return null;
        }
    }

    public void enrichUserLevels(List<Map<String, Object>> records) {
        if (records == null || records.isEmpty()) return;
        for (Map<String, Object> row : records) {
            row.put("userLevel", "normal");
            row.put("userLevelName", "普通用户");
            row.put("planName", "普通用户");
        }
        List<Long> ids = records.stream()
                .map(r -> ((Number) r.get("id")).longValue())
                .collect(Collectors.toList());
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        try {
            // 读取 vip_level 覆盖字段（字段由 DataInitializer 统一初始化）
            Map<Long, Integer> vipOverrides = new HashMap<>();
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
            } catch (Exception ignored) {}

            List<Map<String, Object>> plans = jdbcTemplate.query(
                    "SELECT s.user_id, p.plan_code, p.plan_name, s.start_time, s.end_time " +
                            "FROM billing_subscription s " +
                            "JOIN billing_plan p ON p.id = s.plan_id AND p.deleted = 0 " +
                            "WHERE s.user_id IN (" + placeholders + ") AND s.status = 1 " +
                            "AND (s.end_time IS NULL OR s.end_time >= NOW()) " +
                            "ORDER BY s.user_id, s.end_time DESC, s.id DESC",
                    (rs, rn) -> {
                        Map<String, Object> m = new LinkedHashMap<>();
                        m.put("userId", rs.getLong("user_id"));
                        m.put("planCode", normalizeUserLevel(rs.getString("plan_code")));
                        m.put("planName", rs.getString("plan_name"));
                        m.put("planStartTime", rs.getTimestamp("start_time"));
                        m.put("planEndTime", rs.getTimestamp("end_time"));
                        return m;
                    },
                    ids.toArray()
            );
            Map<Long, Map<String, Object>> first = new LinkedHashMap<>();
            for (Map<String, Object> plan : plans) {
                Long userId = ((Number) plan.get("userId")).longValue();
                first.putIfAbsent(userId, plan);
            }
            for (Map<String, Object> row : records) {
                Long uid = ((Number) row.get("id")).longValue();
                // vip_level 覆盖优先于订阅
                Integer overrideLevel = vipOverrides.get(uid);
                if (overrideLevel != null) {
                    String code = overrideLevel == 3 ? "vip-single" : (overrideLevel >= 2 ? "svp" : "vip");
                    row.put("userLevel", code);
                    row.put("userLevelName", userLevelName(code));
                    row.put("planName", overrideLevel == 3 ? "VIP（单店版） (手动)" : (overrideLevel >= 2 ? "SVP (手动)" : "VIP (手动)"));
                    // 手动等级覆盖优先，但充值/到期时间仍展示真实订阅时间
                    Map<String, Object> sub = first.get(uid);
                    row.put("planStartTime", sub == null ? null : sub.get("planStartTime"));
                    row.put("planEndTime", sub == null ? null : sub.get("planEndTime"));
                } else {
                    Map<String, Object> plan = first.get(uid);
                    if (plan != null) {
                        String code = String.valueOf(plan.get("planCode"));
                        row.put("userLevel", code);
                        row.put("userLevelName", userLevelName(code));
                        row.put("planName", plan.get("planName"));
                        row.put("planStartTime", plan.get("planStartTime"));
                        row.put("planEndTime", plan.get("planEndTime"));
                    }
                }
            }
        } catch (Exception ignored) {
            // 兼容未执行套餐迁移的旧库
        }
    }

    private String normalizeUserLevel(String planCode) {
        if (planCode == null) return "normal";
        String c = planCode.trim().toLowerCase(Locale.ROOT);
        if ("svip".equals(c)) return "svp";
        if (c.startsWith("vip-single") || c.startsWith("vip_single") || "vip1".equals(c)) return "vip-single";
        if ("svp".equals(c) || "vip".equals(c)) return c;
        return "normal";
    }

    private String userLevelName(String userLevel) {
        if ("vip-single".equals(userLevel)) return "VIP（单店版）";
        if ("svp".equals(userLevel)) return "SVP";
        if ("vip".equals(userLevel)) return "VIP";
        return "普通用户";
    }

    // ==================== 私有辅助方法 ====================

    private Long findOrCreateDefaultTenantId() {
        List<Map<String, Object>> tenants = jdbcTemplate.queryForList(
                "SELECT id FROM sys_tenant WHERE deleted=0 LIMIT 1");
        if (!tenants.isEmpty()) {
            return ((Number) tenants.get(0).get("id")).longValue();
        }
        jdbcTemplate.update(
                "INSERT INTO sys_tenant(tenant_name, name, display_name, status, created_time, updated_time, deleted) VALUES(?,?,?,1,NOW(),NOW(),0)",
                "默认租户", "default", "默认租户");
        Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        log.info("已自动创建默认租户: id={}", id);
        return id;
    }

    private String buildWhere(String username, String nickname, String phone, String email,
                               String status, List<Object> args) {
        StringBuilder where = new StringBuilder(" WHERE u.deleted=0");

        if (StringUtils.hasText(username)) {
            where.append(" AND u.username LIKE ?");
            args.add("%" + username + "%");
        }
        if (StringUtils.hasText(nickname)) {
            where.append(" AND u.nickname LIKE ?");
            args.add("%" + nickname + "%");
        }
        if (StringUtils.hasText(phone)) {
            where.append(" AND u.phone LIKE ?");
            args.add("%" + phone + "%");
        }
        if (StringUtils.hasText(email)) {
            where.append(" AND u.email LIKE ?");
            args.add("%" + email + "%");
        }
        if (StringUtils.hasText(status)) {
            Integer statusCode = parseStatusCode(status);
            if (statusCode != null) {
                where.append(" AND u.status=?");
                args.add(statusCode);
            }
        }

        return where.toString();
    }

    private Integer parseStatusCode(String status) {
        if (!StringUtils.hasText(status)) return null;
        String s = status.trim();
        if ("正常".equals(s) || "启用".equals(s) || "1".equals(s) || "true".equalsIgnoreCase(s)) return 1;
        if ("禁用".equals(s) || "异常".equals(s) || "0".equals(s) || "false".equalsIgnoreCase(s)) return 0;
        try { return Integer.parseInt(s); } catch (NumberFormatException e) { return null; }
    }

    private int parseInt(Object value) {
        if (value == null) return 1;
        if (value instanceof Number) return ((Number) value).intValue();
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException e) {
            return 1;
        }
    }

    private Long parseLong(Object value) {
        if (value == null) return null;
        if (value instanceof Number) return ((Number) value).longValue();
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
