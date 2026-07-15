package com.xianyu.admin.security;

import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.Base64;
import java.util.Locale;

/** Distributed brute-force protection for the administrator login endpoint. */
@Component
public class AdminLoginAttemptGuard {
    private static final Logger log = LoggerFactory.getLogger(AdminLoginAttemptGuard.class);
    private static final Duration WINDOW = Duration.ofMinutes(15);
    private static final int MAX_ACCOUNT_FAILURES = 5;
    private static final int MAX_IP_FAILURES = 30;

    private final StringRedisTemplate redisTemplate;

    public AdminLoginAttemptGuard(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public void checkAllowed(String username, String clientIp) {
        try {
            if (readCount(accountKey(username)) >= MAX_ACCOUNT_FAILURES) {
                throw new BizException(429, "登录尝试过于频繁，请 15 分钟后再试");
            }
            if (readCount(ipKey(clientIp)) >= MAX_IP_FAILURES) {
                throw new BizException(429, "当前网络登录尝试过于频繁，请 15 分钟后再试");
            }
        } catch (BizException e) {
            throw e;
        } catch (RuntimeException e) {
            log.error("Admin login rate-limit storage unavailable, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "登录安全服务暂时不可用，请稍后重试");
        }
    }

    public void recordFailure(String username, String clientIp) {
        try {
            increment(accountKey(username));
            increment(ipKey(clientIp));
        } catch (RuntimeException e) {
            log.error("Failed to persist admin login failure counters, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "登录安全服务暂时不可用，请稍后重试");
        }
    }

    public void recordSuccess(String username) {
        try {
            // Keep the IP-wide counter for the remainder of the window: one valid credential
            // must not let an attacker reset a distributed account-enumeration budget.
            redisTemplate.delete(accountKey(username));
        } catch (RuntimeException e) {
            log.error("Failed to clear admin login account counter, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "登录安全服务暂时不可用，请稍后重试");
        }
    }

    private int readCount(String key) {
        String value = redisTemplate.opsForValue().get(key);
        if (value == null || value.isBlank()) return 0;
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            // Corrupt security state is not treated as an unlimited budget.
            return Integer.MAX_VALUE;
        }
    }

    private void increment(String key) {
        Long count = redisTemplate.opsForValue().increment(key);
        if (count == null) {
            throw new IllegalStateException("Redis increment returned null");
        }
        if (count == 1L) {
            Boolean expirySet = redisTemplate.expire(key, WINDOW);
            if (Boolean.FALSE.equals(expirySet)) {
                throw new IllegalStateException("Redis expiry was not set");
            }
        }
    }

    private String accountKey(String username) {
        return "xya:admin-login:account:" + hash(normalize(username));
    }

    private String ipKey(String clientIp) {
        return "xya:admin-login:ip:" + hash(normalize(clientIp));
    }

    private String normalize(String value) {
        return value == null || value.isBlank()
                ? "unknown"
                : value.trim().toLowerCase(Locale.ROOT);
    }

    private String hash(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is unavailable", e);
        }
    }
}
