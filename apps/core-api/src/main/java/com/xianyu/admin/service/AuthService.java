package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.JwtUtil;
import com.xianyu.admin.security.TenantContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

@Service
public class AuthService {
    private static final Logger log = LoggerFactory.getLogger(AuthService.class);

    private static final String DEFAULT_ADMIN_USERNAME = "admin";
    private static final String DEFAULT_ADMIN_PASSWORD = "123456";
    private static final String LEGACY_ADMIN_PASSWORD = "admin123456";
    private static final String DEFAULT_ADMIN_NICKNAME = "超级管理员";
    private static final String DEFAULT_ADMIN_EMAIL = "admin@xianyu.local";
    private static final String DEFAULT_ADMIN_ROLES = "R_SUPER,R_ADMIN";

    private static final String DEMO_OPERATOR_USERNAME = "User";
    private static final String DEMO_OPERATOR_NICKNAME = "演示运营账号";
    private static final String DEMO_OPERATOR_EMAIL = "user-demo@xianyu.local";

    private final JdbcTemplate jdbcTemplate;
    private final JwtUtil jwtUtil;
    private final OperationAuditService auditService;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
    private final String dummyPasswordHash = encoder.encode(java.util.UUID.randomUUID().toString());
    private final Environment environment;
    private final boolean seedEnabled;

    public AuthService(
            JdbcTemplate jdbcTemplate,
            JwtUtil jwtUtil,
            OperationAuditService auditService,
            Environment environment,
            @Value("${admin.seed.enabled:false}") boolean seedEnabled
    ) {
        this.jdbcTemplate = jdbcTemplate;
        this.jwtUtil = jwtUtil;
        this.auditService = auditService;
        this.environment = environment;
        this.seedEnabled = seedEnabled;
    }

    public Map<String, Object> login(String username, String password) {
        if (username == null || username.isBlank() || password == null || password.isBlank()) {
            throw new BizException(400, "用户名和密码不能为空");
        }
        username = username.trim();
        if (username.length() > 128 || password.length() > 256) {
            throw new BizException(400, "登录凭据长度不合法");
        }
        List<Map<String, Object>> list = jdbcTemplate.queryForList(
                "SELECT * FROM sys_admin_user WHERE username=? AND deleted=0 LIMIT 1",
                username
        );
        if (list.isEmpty()) {
            consumePasswordVerification(password);
            throw new BizException(401, "用户名或密码错误");
        }

        Map<String, Object> user = list.get(0);
        if (!"1".equals(String.valueOf(user.get("status")))) {
            consumePasswordVerification(password);
            throw new BizException(401, "用户名或密码错误");
        }

        Object storedValue = user.get("password_hash");
        String storedHash = storedValue instanceof String ? ((String) storedValue).trim() : null;
        if (storedHash == null || storedHash.isBlank()) {
            consumePasswordVerification(password);
            throw new BizException(401, "用户名或密码错误");
        }
        if (!verifyPassword(password, storedHash)) {
            throw new BizException(401, "用户名或密码错误");
        }

        Long id = ((Number) user.get("id")).longValue();
        String roles = String.valueOf(user.getOrDefault("roles", "R_SUPER"));
        long securityVersion = securityVersion(user.get("security_version"));
        String token = jwtUtil.createAdminToken(id, username, roles, securityVersion);

        jdbcTemplate.update("UPDATE sys_admin_user SET last_login_time=NOW() WHERE id=?", id);

        if (!isBCryptHash(storedHash)) {
            jdbcTemplate.update(
                    "UPDATE sys_admin_user SET password_hash=?, updated_time=NOW() WHERE id=?",
                    encoder.encode(password),
                    id
            );
        }

        // 当前仅签发访问令牌；不要把同一令牌伪装成 refresh token。
        // 令牌过期后客户端应重新登录，直到独立的可撤销刷新令牌流程落地。
        return Map.of("token", token);
    }

    public Map<String, Object> userInfo(Long userId) {
        Map<String, Object> user = jdbcTemplate.queryForMap("SELECT * FROM sys_admin_user WHERE id=?", userId);
        String roles = String.valueOf(user.getOrDefault("roles", "R_SUPER"));
        Object avatar = user.get("avatar");
        List<String> roleList = Arrays.stream(roles.split(","))
                .map(String::trim)
                .filter(role -> !role.isEmpty())
                .toList();
        boolean superAdministrator = roleList.contains("R_SUPER");
        List<String> buttons = superAdministrator
                ? List.of("add", "edit", "delete", "view", "export")
                : List.of("view", "export");

        return Map.of(
                "buttons", buttons,
                "roles", roleList,
                "userId", user.get("id"),
                "userName", user.get("username"),
                "email", user.getOrDefault("email", DEFAULT_ADMIN_EMAIL),
                "avatar", avatar == null ? "" : avatar
        );
    }

    public void logout(Long userId) {
        if (userId == null || userId <= 0) {
            throw new BizException(401, "管理员登录状态已失效，请重新登录");
        }
        int affected = jdbcTemplate.update(
                "UPDATE sys_admin_user SET security_version=security_version+1, updated_time=NOW() "
                        + "WHERE id=? AND status=1 AND deleted=0",
                userId
        );
        if (affected != 1) {
            throw new BizException(401, "管理员登录状态已失效，请重新登录");
        }
    }

    /**
     * 管理员修改自己的登录密码。
     * 校验旧密码 → 校验新密码强度 → BCrypt 加密入库 → security_version+1 使既有令牌失效。
     * 修改成功后当前会话令牌也会失效，前端需引导用户重新登录。
     */
    @Transactional
    public void changePassword(Long userId, String oldPassword, String newPassword) {
        if (userId == null || userId <= 0) {
            throw new BizException(401, "管理员登录状态已失效，请重新登录");
        }
        if (oldPassword == null || oldPassword.isBlank()) {
            throw new BizException(400, "原密码不能为空");
        }
        validatePasswordStrength(newPassword, "新密码");
        if (oldPassword.equals(newPassword)) {
            throw new BizException(400, "新密码不能与原密码相同");
        }

        List<Map<String, Object>> list = jdbcTemplate.queryForList(
                "SELECT id, username, password_hash, status, deleted FROM sys_admin_user WHERE id=? LIMIT 1",
                userId
        );
        if (list.isEmpty()) {
            throw new BizException(401, "管理员账号不存在，请重新登录");
        }
        Map<String, Object> user = list.get(0);
        if (!"1".equals(String.valueOf(user.get("status"))) || "1".equals(String.valueOf(user.get("deleted")))) {
            throw new BizException(401, "管理员账号已停用，请联系超级管理员");
        }

        String storedHash = String.valueOf(user.get("password_hash"));
        if (!verifyPassword(oldPassword, storedHash)) {
            throw new BizException(400, "原密码错误");
        }

        String newHash = encoder.encode(newPassword);
        int affected = jdbcTemplate.update(
                "UPDATE sys_admin_user SET password_hash=?, security_version=security_version+1, updated_time=NOW() "
                        + "WHERE id=? AND status=1 AND deleted=0",
                newHash, userId
        );
        if (affected != 1) {
            throw new BizException(500, "密码更新失败，请稍后重试");
        }

        String username = String.valueOf(user.get("username"));
        log.info("管理员修改自身密码: userId={}, username={}", userId, username);
        auditService.recordRequired(
                TenantContext.getCurrentTenantId(),
                AdminContext.userId(),
                "ADMIN_CHANGE_PASSWORD",
                "管理员修改自身登录密码: " + username,
                "sys_admin_user",
                userId,
                null
        );
    }

    /**
     * 密码强度校验：至少 8 位，且必须同时包含字母和数字。
     * 与 SysUserService.validatePasswordStrength 保持一致策略。
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

    public void seedAdmin() {
        if (!seedEnabled || isProdProfile()) {
            return;
        }

        ensureDefaultAdminAccount();
        ensureDemoOperatorAccount();
    }

    private void ensureDefaultAdminAccount() {
        List<Map<String, Object>> admins = jdbcTemplate.queryForList(
                "SELECT id, username, password_hash, deleted FROM sys_admin_user WHERE username=? LIMIT 1",
                DEFAULT_ADMIN_USERNAME
        );

        if (admins.isEmpty()) {
            jdbcTemplate.update(
                    "INSERT INTO sys_admin_user(username,password_hash,nickname,email,roles,status,created_time,updated_time,deleted) " +
                            "VALUES(?,?,?,?,?,1,NOW(),NOW(),0)",
                    DEFAULT_ADMIN_USERNAME,
                    encoder.encode(DEFAULT_ADMIN_PASSWORD),
                    DEFAULT_ADMIN_NICKNAME,
                    DEFAULT_ADMIN_EMAIL,
                    DEFAULT_ADMIN_ROLES
            );
            log.info("Initialized admin account with requested default credentials");
            return;
        }

        Map<String, Object> admin = admins.get(0);
        Long id = ((Number) admin.get("id")).longValue();
        String storedHash = String.valueOf(admin.get("password_hash"));
        boolean passwordAlreadyMatches = DEFAULT_ADMIN_PASSWORD.equals(storedHash)
                || matchesPassword(DEFAULT_ADMIN_PASSWORD, storedHash);

        if (passwordAlreadyMatches) {
            jdbcTemplate.update(
                    "UPDATE sys_admin_user SET nickname=COALESCE(NULLIF(nickname,''), ?), " +
                            "email=COALESCE(NULLIF(email,''), ?), roles=COALESCE(NULLIF(roles,''), ?), " +
                            "status=1, deleted=0, updated_time=NOW() WHERE id=?",
                    DEFAULT_ADMIN_NICKNAME,
                    DEFAULT_ADMIN_EMAIL,
                    DEFAULT_ADMIN_ROLES,
                    id
            );
            return;
        }

        if (shouldMigrateAdminPassword(storedHash, admin)) {
            jdbcTemplate.update(
                    "UPDATE sys_admin_user SET username=?, password_hash=?, nickname=?, email=?, roles=?, status=1, deleted=0, security_version=security_version+1, updated_time=NOW() WHERE id=?",
                    DEFAULT_ADMIN_USERNAME,
                    encoder.encode(DEFAULT_ADMIN_PASSWORD),
                    DEFAULT_ADMIN_NICKNAME,
                    DEFAULT_ADMIN_EMAIL,
                    DEFAULT_ADMIN_ROLES,
                    id
            );
            log.info("Migrated admin account password to requested default password");
        }
    }

    private boolean shouldMigrateAdminPassword(String storedHash, Map<String, Object> admin) {
        return "1".equals(String.valueOf(admin.getOrDefault("deleted", 0)))
                || LEGACY_ADMIN_PASSWORD.equals(storedHash)
                || matchesPassword(LEGACY_ADMIN_PASSWORD, storedHash)
                || !isBCryptHash(storedHash);
    }

    private void ensureDemoOperatorAccount() {
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM sys_admin_user WHERE username=? AND deleted=0",
                Long.class,
                DEMO_OPERATOR_USERNAME
        );
        if (count != null && count > 0) {
            return;
        }

        jdbcTemplate.update(
                "INSERT INTO sys_admin_user(username,password_hash,nickname,email,roles,status,created_time,updated_time,deleted) " +
                        "VALUES(?,?,?,?,?,1,NOW(),NOW(),0)",
                DEMO_OPERATOR_USERNAME,
                encoder.encode(DEFAULT_ADMIN_PASSWORD),
                DEMO_OPERATOR_NICKNAME,
                DEMO_OPERATOR_EMAIL,
                "R_ADMIN"
        );
    }

    private boolean verifyPassword(String plainPassword, String storedHash) {
        if (storedHash == null || storedHash.isBlank()) {
            return false;
        }
        if (isBCryptHash(storedHash)) {
            return matchesPassword(plainPassword, storedHash);
        }
        return storedHash.equals(plainPassword);
    }

    private boolean matchesPassword(String plainPassword, String storedHash) {
        try {
            return encoder.matches(plainPassword, storedHash);
        } catch (IllegalArgumentException ex) {
            return false;
        }
    }

    private void consumePasswordVerification(String password) {
        // Keep missing/disabled account paths close to the BCrypt timing of a normal login so
        // the public endpoint does not become an account-enumeration oracle.
        matchesPassword(password, dummyPasswordHash);
    }

    private boolean isBCryptHash(String hash) {
        return hash != null && (hash.startsWith("$2a$") || hash.startsWith("$2b$") || hash.startsWith("$2y$"));
    }

    private long securityVersion(Object value) {
        if (value instanceof Number number && number.longValue() > 0) {
            return number.longValue();
        }
        if (value != null) {
            try {
                long parsed = Long.parseLong(String.valueOf(value));
                if (parsed > 0) return parsed;
            } catch (NumberFormatException ignored) {
                // Compatibility rows receive the database default below.
            }
        }
        return 1L;
    }

    private boolean isProdProfile() {
        return Arrays.asList(environment.getActiveProfiles()).contains("prod");
    }
}
