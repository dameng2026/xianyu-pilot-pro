package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.JwtUtil;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;

/**
 * 前台用户（sys_user 表）认证服务。
 * 处理登录、登出、用户信息查询、注册、邮箱验证码登录、密码重置。
 *
 * 验证码方式已统一切换为邮箱验证码（原手机号短信验证码已移除）。
 */
@Service
public class UserAuthService {
    private static final Logger log = LoggerFactory.getLogger(UserAuthService.class);

    private final JdbcTemplate jdbcTemplate;
    private final JwtUtil jwtUtil;
    private final Environment environment;
    private final StringRedisTemplate redisTemplate;
    private final UserProfileService userProfileService;
    private final UserAuthCapabilityService capabilityService;
    private final EmailSenderService emailSenderService;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
    private final String dummyPasswordHash = encoder.encode(UUID.randomUUID().toString());
    private final SecureRandom secureRandom = new SecureRandom();
    private final boolean seedEnabled;

    private static final Duration EMAIL_CODE_TTL = Duration.ofMinutes(5);
    private static final Duration EMAIL_RESEND_INTERVAL = Duration.ofSeconds(60);
    private static final Duration EMAIL_HOURLY_WINDOW = Duration.ofHours(1);
    private static final int MAX_TARGET_SENDS_PER_HOUR = 10;
    private static final int MAX_IP_SENDS_PER_HOUR = 60;
    private static final int MAX_VERIFY_FAILS = 5;
    private static final Duration PASSWORD_LOGIN_WINDOW = Duration.ofMinutes(15);
    private static final int MAX_PASSWORD_FAILS_PER_ACCOUNT = 5;
    private static final int MAX_PASSWORD_FAILS_PER_IP = 30;
    private static final String PASSWORD_POLICY_MESSAGE = "密码需为8-32位，且包含字母和数字";
    private static final String EMAIL_REGEX = "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$";

    public UserAuthService(JdbcTemplate jdbcTemplate, JwtUtil jwtUtil, Environment environment,
                           StringRedisTemplate redisTemplate,
                           UserProfileService userProfileService,
                           UserAuthCapabilityService capabilityService,
                           EmailSenderService emailSenderService,
                           @Value("${admin.seed.enabled:false}") boolean seedEnabled) {
        this.jdbcTemplate = jdbcTemplate;
        this.jwtUtil = jwtUtil;
        this.environment = environment;
        this.redisTemplate = redisTemplate;
        this.userProfileService = userProfileService;
        this.capabilityService = capabilityService;
        this.emailSenderService = emailSenderService;
        this.seedEnabled = seedEnabled;
    }

    /**
     * 前台用户登录。按 username 在 sys_user 中查找。
     * 密码校验：优先 BCrypt，兼容明文密码并自动升级为 BCrypt。
     * 返回 JWT token 及用户基本信息。
     */
    public Map<String, Object> login(String username, String password) {
        return login(username, password, "unknown");
    }

    public Map<String, Object> login(String username, String password, String ipAddress) {
        if (username == null || username.isBlank() || password == null || password.isBlank()) {
            throw new BizException(400, "用户名和密码不能为空");
        }
        username = username.trim();
        if (username.length() > 128 || password.length() > 256) {
            throw new BizException(400, "登录凭据长度不合法");
        }
        enforcePasswordLoginRateLimit(username, ipAddress);

        try {
            List<Map<String, Object>> users = jdbcTemplate.queryForList(
                    "SELECT * FROM sys_user WHERE username=? AND deleted=0", username);

            if (users.isEmpty()) {
                consumePasswordVerification(password);
                log.warn("用户登录失败：用户名不存在 username={}", maskTarget(username));
                throw new BizException(401, "用户名或密码错误");
            }

            Map<String, Object> matchedUser = null;
            boolean needsUpgrade = false;
            boolean passwordVerificationAttempted = false;

            for (Map<String, Object> user : users) {
                Object statusObj = user.get("status");
                if (statusObj != null && !"1".equals(String.valueOf(statusObj))) {
                    continue;
                }
                Object storedValue = user.get("password_hash");
                String hash = storedValue instanceof String ? ((String) storedValue).trim() : null;
                if (hash == null || hash.isEmpty()) {
                    continue;
                }
                passwordVerificationAttempted = true;
                if (verifyPassword(password, hash)) {
                    matchedUser = user;
                    if (!isBCryptHash(hash)) {
                        needsUpgrade = true;
                    }
                    break;
                }
            }

            if (matchedUser == null) {
                if (!passwordVerificationAttempted) consumePasswordVerification(password);
                log.warn("用户登录失败：密码错误 username={}", maskTarget(username));
                throw new BizException(401, "用户名或密码错误");
            }

            Long id = ((Number) matchedUser.get("id")).longValue();
            Long tenantId = matchedUser.get("tenant_id") != null
                    ? ((Number) matchedUser.get("tenant_id")).longValue() : null;
            requireTenantForLogin(tenantId);
            String token = jwtUtil.createUserToken(
                    id, username, tenantId, securityVersion(matchedUser.get("security_version")));

            jdbcTemplate.update("UPDATE sys_user SET last_login_time=NOW() WHERE id=?", id);

            if (needsUpgrade) {
                jdbcTemplate.update("UPDATE sys_user SET password_hash=? WHERE id=?",
                        encoder.encode(password), id);
                log.info("已将用户 {} 的密码自动升级为 BCrypt 哈希", maskTarget(username));
            }

            clearPasswordLoginFailures(username, ipAddress);

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("token", token);
            result.put("username", username);
            result.put("userId", id);
            result.put("tenantId", tenantId);
            result.put("nickname", matchedUser.getOrDefault("nickname", username));
            return result;
        } catch (BizException e) {
            if (e.getCode() == 401) {
                recordPasswordLoginFailure(username, ipAddress);
            }
            throw e;
        }
    }

    private boolean verifyPassword(String plainPassword, String storedHash) {
        if (storedHash == null || storedHash.isEmpty()) return false;
        if (isBCryptHash(storedHash)) {
            try {
                return encoder.matches(plainPassword, storedHash);
            } catch (IllegalArgumentException exception) {
                return false;
            }
        }
        boolean matches = MessageDigest.isEqual(
                storedHash.getBytes(StandardCharsets.UTF_8),
                plainPassword.getBytes(StandardCharsets.UTF_8)
        );
        consumePasswordVerification(plainPassword);
        return matches;
    }

    private void consumePasswordVerification(String password) {
        try {
            encoder.matches(password == null ? "" : password, dummyPasswordHash);
        } catch (IllegalArgumentException ignored) {
            // The fixed dummy hash is generated locally and should always be valid.
        }
    }

    private boolean isBCryptHash(String hash) {
        return hash != null && (hash.startsWith("$2a$") || hash.startsWith("$2b$") || hash.startsWith("$2y$"));
    }

    /**
     * 管理员代登：为指定前台用户生成一个登录 token，用于辅助调试。
     *
     * <p>仅校验用户存在、未删除、状态正常（status=1）、且关联了合法的 tenant_id。
     * 不会校验密码，也不会消费密码失败计数；调用方必须经过 AdminRbacFilter 校验为 R_SUPER 角色。
     * 调用此方法会更新 last_login_time，但不会变更 security_version（避免吊销用户已有会话）。</p>
     *
     * @param userId 前台用户 id（sys_user.id）
     * @return 与正常登录一致的结构：{token, username, userId, tenantId, nickname}
     */
    public Map<String, Object> generateLoginTokenForUser(Long userId) {
        if (userId == null || userId <= 0) {
            throw new BizException(400, "用户标识无效");
        }
        Map<String, Object> user;
        try {
            user = jdbcTemplate.queryForMap(
                    "SELECT id, username, nickname, tenant_id, status, security_version, deleted " +
                            "FROM sys_user WHERE id=? AND deleted=0", userId);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            throw new BizException(404, "用户不存在或已删除");
        }
        Object statusObj = user.get("status");
        if (statusObj == null || !"1".equals(String.valueOf(statusObj))) {
            throw new BizException(403, "目标账号已被禁用，无法代登");
        }
        Long tenantId = user.get("tenant_id") != null
                ? ((Number) user.get("tenant_id")).longValue() : null;
        requireTenantForLogin(tenantId);

        long id = ((Number) user.get("id")).longValue();
        String username = String.valueOf(user.get("username"));
        String token = jwtUtil.createUserToken(
                id, username, tenantId, securityVersion(user.get("security_version")));

        // 代登也记录最后登录时间，便于审计追溯；不动 security_version 以免吊销用户已有会话
        jdbcTemplate.update("UPDATE sys_user SET last_login_time=NOW() WHERE id=?", id);
        log.warn("管理员代登已签发前台用户 token: userId={}, username={}, tenantId={}",
                id, maskTarget(username), tenantId);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("token", token);
        result.put("username", username);
        result.put("userId", id);
        result.put("tenantId", tenantId);
        result.put("nickname", user.getOrDefault("nickname", username));
        return result;
    }

    /**
     * 获取当前登录用户信息（包含租户信息）。
     */
    public Map<String, Object> currentUser() {
        Long userId = UserContext.userId();
        Map<String, Object> u = jdbcTemplate.queryForMap(
                "SELECT u.id, u.username, u.nickname, u.phone, u.email, u.avatar, u.status, u.tenant_id, " +
                "u.last_login_time, u.token_balance, u.phone_verified, u.email_verified, u.last_security_update_time, " +
                "COALESCE(t.display_name, t.tenant_name, t.name) AS tenant_name " +
                "FROM sys_user u LEFT JOIN sys_tenant t ON t.id = u.tenant_id AND t.deleted = 0 " +
                "WHERE u.id=? AND u.deleted=0", userId);
        Map<String, Object> activePlan = userProfileService.activePlan(userId);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("userId", u.get("id"));
        result.put("username", u.get("username"));
        result.put("nickname", u.getOrDefault("nickname", u.get("username")));
        result.put("phone", u.getOrDefault("phone", ""));
        result.put("email", u.getOrDefault("email", ""));
        result.put("avatar", u.getOrDefault("avatar", ""));
        result.put("status", u.get("status"));
        result.put("tenantId", u.get("tenant_id"));
        result.put("tenantName", u.getOrDefault("tenant_name", ""));
        result.put("lastLoginTime", u.get("last_login_time"));
        result.put("tokenBalance", u.getOrDefault("token_balance", 0));
        result.put("activePlan", activePlan);
        result.put("planCode", activePlan.getOrDefault("planCode", "normal"));
        result.put("planName", activePlan.getOrDefault("planName", "普通用户"));
        result.put("phoneVerified", "1".equals(String.valueOf(u.get("phone_verified"))) || "true".equalsIgnoreCase(String.valueOf(u.get("phone_verified"))));
        result.put("emailVerified", "1".equals(String.valueOf(u.get("email_verified"))) || "true".equalsIgnoreCase(String.valueOf(u.get("email_verified"))));
        result.put("lastSecurityUpdateTime", u.get("last_security_update_time"));
        return result;
    }

    public void logout() {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null || tenantId == null || tenantId <= 0
                || !Objects.equals(userId, TenantContext.getCurrentUserId())
                || !Objects.equals(tenantId, TenantContext.getCurrentTenantId())) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
        int affected = jdbcTemplate.update(
                "UPDATE sys_user SET security_version=security_version+1, "
                        + "last_security_update_time=NOW(), updated_time=NOW() "
                        + "WHERE id=? AND tenant_id=? AND status=1 AND deleted=0",
                userId,
                tenantId
        );
        if (affected != 1) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
    }


    /**
     * 初始化 sys_user 种子数据。仅在 sys_user 表为空时执行。
     */
    public void seedUser() {
        if (!seedEnabled || isProdProfile()) {
            log.info("已禁用前台演示用户初始化");
            return;
        }
        Long count = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user", Long.class);
        if (count != null && count > 0) return;

        String pwd = encoder.encode("123456");
        Long tenantId = findOrCreateDefaultTenant();
        jdbcTemplate.update(
                "INSERT INTO sys_user(username, password_hash, nickname, email, email_verified, tenant_id, status, created_time, updated_time, deleted) VALUES(?,?,?,?,1,?,1,NOW(),NOW(),0)",
                "demo", pwd, "演示用户", "demo@xianyu.local", tenantId);
        log.warn("仅开发环境已初始化 sys_user 演示账户：demo / 123456，请勿用于生产");
    }

    /**
     * 邮箱验证码登录。
     * 验证码校验通过后按 email 查找用户，找不到则按 username 查找。
     * 若自助注册开放且用户不存在，可自动创建账号。
     */
    public Map<String, Object> loginByEmail(String email, String emailCode) {
        capabilityService.requireEmailVerification();
        if (email == null || emailCode == null) {
            throw new BizException(400, "邮箱和验证码不能为空");
        }
        email = email.trim();
        if (!email.matches(EMAIL_REGEX)) {
            throw new BizException(400, "邮箱格式不正确");
        }
        verifyCode(email, emailCode.trim());

        List<Map<String, Object>> users = jdbcTemplate.queryForList(
                "SELECT * FROM sys_user WHERE email=? AND deleted=0 LIMIT 1", email);
        if (users.isEmpty()) {
            users = jdbcTemplate.queryForList(
                    "SELECT * FROM sys_user WHERE username=? AND deleted=0 LIMIT 1", email);
        }

        Map<String, Object> user;
        if (users.isEmpty()) {
            // Email login and self-registration are separate published capabilities.
            // Never let a direct email-login call create an account when registration is closed.
            capabilityService.requireSelfRegistration();
            user = autoCreateUser(email);
        } else {
            user = users.get(0);
        }

        return buildLoginResult(user);
    }

    /**
     * 发送邮箱验证码。
     * 本地开发模式：生成验证码存 Redis 并在响应中返回 devCode。
     * 生产模式：生成验证码存 Redis 并通过 SMTP 真实发送，不返回 devCode。
     */
    public Map<String, Object> sendEmailCode(String email, String ipAddress) {
        capabilityService.requireEmailVerification();
        String target = normalizeEmailTarget(email);
        enforceEmailRateLimit(target, ipAddress);

        String code = String.format("%06d", secureRandom.nextInt(1_000_000));
        redisTemplate.opsForValue().set(emailCodeKey(target), code, EMAIL_CODE_TTL);
        redisTemplate.delete(emailFailKey(target));
        redisTemplate.opsForValue().set(emailCooldownKey(target), "1", EMAIL_RESEND_INTERVAL);
        incrementWithWindow(emailHourlyTargetKey(target), EMAIL_HOURLY_WINDOW);
        incrementWithWindow(emailHourlyIpKey(ipAddress), EMAIL_HOURLY_WINDOW);

        Map<String, Object> result = new LinkedHashMap<>();
        boolean devOnly = capabilityService.current().emailVerification().devOnly();
        if (devOnly) {
            log.info("本地开发验证码已生成: target={}, ip={}", maskTarget(target), maskTarget(ipAddress));
            result.put("message", "本地开发验证码已生成");
            result.put("devCode", code);
        } else {
            emailSenderService.sendVerificationCode(target, code);
            log.info("邮箱验证码已发送: target={}, ip={}", maskTarget(target), maskTarget(ipAddress));
            result.put("message", "验证码已发送至您的邮箱");
        }
        return result;
    }

    /**
     * 用户注册（邮箱验证码注册）。
     * email 同时写入 username 和 email 字段，设置 email_verified=1。
     */
    public Map<String, Object> register(String email, String password, String emailCode, String inviteCode) {
        capabilityService.requireSelfRegistration();
        capabilityService.requireEmailVerification();
        if (email == null || email.isBlank()) {
            throw new BizException(400, "邮箱不能为空");
        }
        email = email.trim();
        if (!email.matches(EMAIL_REGEX)) {
            throw new BizException(400, "邮箱格式不正确");
        }
        validatePassword(password);
        if (emailCode == null || emailCode.isBlank()) {
            throw new BizException(400, "验证码不能为空");
        }
        verifyCode(email, emailCode.trim());

        List<Map<String, Object>> exists = jdbcTemplate.queryForList(
                "SELECT * FROM sys_user WHERE (email=? OR username=?) AND deleted=0 LIMIT 1", email, email);
        if (!exists.isEmpty()) {
            throw new BizException(400, "该邮箱已注册");
        }

        // 每个自然注册用户默认创建独立租户，避免跨用户共享默认租户导致数据串租户。
        Long tenantId = createTenantForUser(email);

        String pwd = encoder.encode(password);
        jdbcTemplate.update(
                "INSERT INTO sys_user(username, password_hash, nickname, email, email_verified, tenant_id, status, created_time, updated_time, deleted) VALUES(?,?,?,?,1,?,1,NOW(),NOW(),0)",
                email, pwd, email, email, tenantId);

        List<Map<String, Object>> created = jdbcTemplate.queryForList(
                "SELECT * FROM sys_user WHERE email=? AND deleted=0 LIMIT 1", email);
        if (created.isEmpty()) {
            throw new BizException(500, "注册失败，请重试");
        }
        log.info("新用户注册成功: email={}, tenantId={}", maskTarget(email), tenantId);
        return buildLoginResult(created.get(0));
    }

    /**
     * 重置密码（邮箱验证码重置）。
     * 前置 verifyResetCode 已校验验证码（不消费），此处二次校验并消费。
     */
    public void resetPassword(String email, String emailCode, String newPassword) {
        capabilityService.requirePasswordReset();
        capabilityService.requireEmailVerification();
        if (email == null || email.isEmpty()) throw new BizException(400, "邮箱不能为空");
        if (emailCode == null || emailCode.isEmpty()) throw new BizException(400, "验证码不能为空");
        validatePassword(newPassword);

        verifyCode(email, emailCode);

        List<Map<String, Object>> users = jdbcTemplate.queryForList(
                "SELECT * FROM sys_user WHERE email=? AND deleted=0 LIMIT 1", email);
        if (users.isEmpty()) {
            users = jdbcTemplate.queryForList(
                    "SELECT * FROM sys_user WHERE username=? AND deleted=0 LIMIT 1", email);
        }
        if (users.isEmpty()) throw new BizException(404, "未找到该账号");

        Long userId = ((Number) users.get(0).get("id")).longValue();
        jdbcTemplate.update("UPDATE sys_user SET password_hash=?, security_version=security_version+1, last_security_update_time=NOW(), updated_time=NOW() WHERE id=?",
                encoder.encode(newPassword), userId);
        log.info("密码重置成功: userId={}", userId);
    }

    /**
     * 找回密码前置验证码校验（不消费验证码，供后续 resetPassword 二次校验）。
     */
    public void verifyResetCode(String email, String emailCode) {
        capabilityService.requirePasswordReset();
        capabilityService.requireEmailVerification();
        if (email == null || email.isBlank()) throw new BizException(400, "邮箱不能为空");
        if (!email.trim().matches(EMAIL_REGEX)) throw new BizException(400, "邮箱格式不正确");
        if (emailCode == null || emailCode.isBlank()) throw new BizException(400, "验证码不能为空");
        verifyCode(email.trim(), emailCode.trim(), false);
    }

    private void verifyCode(String target, String code) {
        verifyCode(target, code, true);
    }

    private void verifyCode(String target, String code, boolean consumeOnSuccess) {
        String normalizedTarget = target == null ? "" : target.trim();
        if (normalizedTarget.isEmpty()) throw new BizException(400, "邮箱不能为空");
        String failKey = emailFailKey(normalizedTarget);
        String failCount = redisTemplate.opsForValue().get(failKey);
        if (parseInt(failCount) >= MAX_VERIFY_FAILS) {
            throw new BizException(400, "验证码错误次数过多，请重新获取");
        }
        String stored = redisTemplate.opsForValue().get(emailCodeKey(normalizedTarget));
        if (stored == null) throw new BizException(400, "请先获取验证码或验证码已过期");
        if (!stored.equals(code)) {
            incrementWithWindow(failKey, EMAIL_CODE_TTL);
            throw new BizException(400, "验证码错误");
        }
        if (consumeOnSuccess) {
            redisTemplate.delete(emailCodeKey(normalizedTarget));
            redisTemplate.delete(failKey);
            redisTemplate.delete(emailCooldownKey(normalizedTarget));
        }
    }

    private String normalizeEmailTarget(String email) {
        String target = email == null ? "" : email.trim();
        if (target.isEmpty()) {
            throw new BizException(400, "邮箱不能为空");
        }
        if (!target.matches(EMAIL_REGEX)) {
            throw new BizException(400, "邮箱格式不正确");
        }
        return target;
    }

    private void enforceEmailRateLimit(String target, String ipAddress) {
        if (Boolean.TRUE.equals(redisTemplate.hasKey(emailCooldownKey(target)))) {
            throw new BizException(429, "验证码发送过于频繁，请稍后再试");
        }
        int targetHourly = parseInt(redisTemplate.opsForValue().get(emailHourlyTargetKey(target)));
        if (targetHourly >= MAX_TARGET_SENDS_PER_HOUR) {
            throw new BizException(429, "该邮箱验证码发送次数过多，请稍后再试");
        }
        int ipHourly = parseInt(redisTemplate.opsForValue().get(emailHourlyIpKey(ipAddress)));
        if (ipHourly >= MAX_IP_SENDS_PER_HOUR) {
            throw new BizException(429, "当前网络验证码发送次数过多，请稍后再试");
        }
    }

    private long incrementWithWindow(String key, Duration window) {
        Long value = redisTemplate.opsForValue().increment(key);
        if (value == null) {
            throw new BizException(503, "认证安全状态暂时无法更新，请稍后重试");
        }
        if (value == 1L && !Boolean.TRUE.equals(redisTemplate.expire(key, window))) {
            throw new BizException(503, "认证安全状态暂时无法更新，请稍后重试");
        }
        return value;
    }

    private void validatePassword(String password) {
        if (password == null
                || !password.matches("^(?=.*[A-Za-z])(?=.*\\d).{8,32}$")
                || password.getBytes(StandardCharsets.UTF_8).length > 72) {
            throw new BizException(400, PASSWORD_POLICY_MESSAGE);
        }
    }

    private void enforcePasswordLoginRateLimit(String username, String ipAddress) {
        int accountFails = parseInt(redisTemplate.opsForValue().get(passwordFailAccountKey(username)));
        if (accountFails >= MAX_PASSWORD_FAILS_PER_ACCOUNT) {
            throw new BizException(429, "密码错误次数过多，请15分钟后再试");
        }
        int ipFails = parseInt(redisTemplate.opsForValue().get(passwordFailIpKey(ipAddress)));
        if (ipFails >= MAX_PASSWORD_FAILS_PER_IP) {
            throw new BizException(429, "当前网络登录尝试过于频繁，请稍后再试");
        }
    }

    private void recordPasswordLoginFailure(String username, String ipAddress) {
        incrementWithWindow(passwordFailAccountKey(username), PASSWORD_LOGIN_WINDOW);
        incrementWithWindow(passwordFailIpKey(ipAddress), PASSWORD_LOGIN_WINDOW);
    }

    private void clearPasswordLoginFailures(String username, String ipAddress) {
        redisTemplate.delete(passwordFailAccountKey(username));
        // Keep the IP-wide counter for the window. A single valid credential
        // must not reset the attack budget for probing other accounts.
    }

    private String emailCodeKey(String target) { return "xya:email:code:" + maskKey(target); }
    private String emailCooldownKey(String target) { return "xya:email:cooldown:" + maskKey(target); }
    private String emailFailKey(String target) { return "xya:email:fail:" + maskKey(target); }
    private String emailHourlyTargetKey(String target) { return "xya:email:hourly:target:" + maskKey(target); }
    private String emailHourlyIpKey(String ipAddress) { return "xya:email:hourly:ip:" + maskKey(ipAddress); }
    private String passwordFailAccountKey(String username) { return "xya:login:fail:account:" + maskKey(username); }
    private String passwordFailIpKey(String ipAddress) { return "xya:login:fail:ip:" + maskKey(ipAddress); }

    private String maskKey(String value) {
        String normalized = value == null || value.isBlank()
                ? "unknown"
                : value.trim().toLowerCase(Locale.ROOT);
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(normalized.getBytes(StandardCharsets.UTF_8));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
        } catch (Exception e) {
            throw new IllegalStateException("SHA-256 is unavailable", e);
        }
    }

    private int parseInt(String value) {
        if (value == null || value.isBlank()) return 0;
        try { return Integer.parseInt(value); } catch (NumberFormatException e) { return Integer.MAX_VALUE; }
    }

    private Long createTenantForUser(String identifier) {
        String suffix = identifier == null ? UUID.randomUUID().toString().replace("-", "").substring(0, 8) : identifier.replaceAll("[^a-zA-Z0-9]", "");
        if (suffix.length() > 32) suffix = suffix.substring(0, 32);
        String tenantCode = "tenant_" + suffix + "_" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        String displayName = (identifier == null || identifier.isBlank()) ? "用户租户" : identifier + "的团队";
        jdbcTemplate.update(
                "INSERT INTO sys_tenant(tenant_name, name, display_name, status, created_time, updated_time, deleted) VALUES(?,?,?,1,NOW(),NOW(),0)",
                displayName, tenantCode, displayName);
        Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        log.info("已为用户创建独立租户: tenantId={}, identifier={}", id, maskTarget(identifier));
        return id;
    }

    private boolean isProdProfile() {
        return Arrays.asList(environment.getActiveProfiles()).contains("prod");
    }

    private String maskTarget(String target) {
        if (target == null || target.length() < 7) return "***";
        return target.substring(0, 3) + "****" + target.substring(target.length() - 4);
    }

    private Long findOrCreateDefaultTenant() {
        List<Map<String, Object>> tenants = jdbcTemplate.queryForList(
                "SELECT id FROM sys_tenant WHERE deleted=0 LIMIT 1");
        if (!tenants.isEmpty()) {
            return ((Number) tenants.get(0).get("id")).longValue();
        }
        jdbcTemplate.update(
                "INSERT INTO sys_tenant(name, display_name, status, created_time, updated_time, deleted) VALUES(?,?,1,NOW(),NOW(),0)",
                "default", "默认租户");
        Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        log.info("已创建默认租户: id={}", id);
        return id;
    }

    private Map<String, Object> autoCreateUser(String email) {
        String pwd = encoder.encode(UUID.randomUUID().toString().substring(0, 12));
        Long tenantId = createTenantForUser(email);

        jdbcTemplate.update(
                "INSERT INTO sys_user(username, password_hash, nickname, email, email_verified, tenant_id, status, created_time, updated_time, deleted) VALUES(?,?,?,?,1,?,1,NOW(),NOW(),0)",
                email, pwd, email, email, tenantId);

        List<Map<String, Object>> created = jdbcTemplate.queryForList(
                "SELECT * FROM sys_user WHERE email=? AND deleted=0 LIMIT 1", email);
        if (created.isEmpty()) throw new BizException(500, "自动创建用户失败");
        log.info("邮箱验证码登录自动创建用户: {}, tenantId={}", maskTarget(email), tenantId);
        return created.get(0);
    }

    private Map<String, Object> buildLoginResult(Map<String, Object> user) {
        Long id = ((Number) user.get("id")).longValue();
        String username = String.valueOf(user.get("username"));
        Long tenantId = user.get("tenant_id") != null
                ? ((Number) user.get("tenant_id")).longValue() : null;
        requireTenantForLogin(tenantId);
        String token = jwtUtil.createUserToken(
                id, username, tenantId, securityVersion(user.get("security_version")));
        jdbcTemplate.update("UPDATE sys_user SET last_login_time=NOW() WHERE id=?", id);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("token", token);
        result.put("username", username);
        result.put("userId", id);
        result.put("tenantId", tenantId);
        result.put("nickname", user.getOrDefault("nickname", username));
        return result;
    }

    private void requireTenantForLogin(Long tenantId) {
        if (tenantId == null || tenantId <= 0) {
            throw new BizException(403, "账号租户配置异常，请联系管理员处理");
        }
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
}
