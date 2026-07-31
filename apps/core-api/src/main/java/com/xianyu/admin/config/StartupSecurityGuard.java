package com.xianyu.admin.config;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

/** Production/staging startup gate for security-critical runtime configuration. */
@Component
public class StartupSecurityGuard implements ApplicationRunner {
    private static final Set<String> PROD_LIKE = Set.of("prod", "production", "staging", "stage");
    private static final Set<String> WEAK_VALUES = Set.of(
            "123456", "root", "password", "changeme", "change-me",
            "please-change-this-admin-jwt-secret-at-least-32-chars",
            "change-this-admin-jwt-secret-in-production-please",
            "dev-only-cookie-crypto-secret-change-me-32-chars",
            "dev-only-internal-api-token-change-me-32-chars",
            "dev-only-redis-password-change-me"
    );

    private final Environment environment;

    public StartupSecurityGuard(Environment environment) {
        this.environment = environment;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!isProductionLike()) return;
        // 生产环境默认启用安全检查（fail-closed），避免遗漏配置导致弱 token/种子初始化等事故。
        // 如需显式关闭，设置 XIANYU_SECURITY_GUARD_ENABLED=false（不推荐）。
        boolean defaultEnabled = true;
        if (!Boolean.parseBoolean(property("xianyu.security-guard.enabled", String.valueOf(defaultEnabled)))) {
            return;
        }

        requireStrong("INTERNAL_API_TOKEN", property("xianyu.automation.internal-token"), 32);
        requireStrong("ADMIN_JWT_SECRET", property("admin.jwt.secret"), 32);
        requireStrong("COOKIE_CRYPTO_SECRET", property("xianyu.cookie.crypto-secret"), 32);
        requireStrong("API_KEY_CRYPTO_SECRET", property("xianyu.api-key.crypto-secret"), 32);
        requireStrong("OPS_METRICS_TOKEN", property("ops.metrics.token"), 32);
        requireStrong("SPRING_DATASOURCE_PASSWORD", property("spring.datasource.password"), 32);
        requireStrong("REDIS_PASSWORD", property("spring.data.redis.password"), 32);
        requireStrong("DATA_SYNC_API_TOKEN", property("xianyu.sync.token"), 32);

        if (Boolean.parseBoolean(property("admin.seed.enabled", "false"))) {
            throw new IllegalStateException("ADMIN_SEED_ENABLED must be false in prod/staging");
        }
        if (Boolean.parseBoolean(property("payment.sandbox.enabled", "false"))) {
            throw new IllegalStateException("PAYMENT_SANDBOX_ENABLED must be false in prod/staging");
        }
        if (Boolean.parseBoolean(property("xianyu.schema.runtime-mutations-enabled", "true"))) {
            throw new IllegalStateException(
                    "SCHEMA_RUNTIME_MUTATIONS_ENABLED must be false in prod/staging; apply versioned migrations before startup"
            );
        }

        int expiration = parsePositiveInt("JWT_EXPIRE_SECONDS",
                property("admin.jwt.expire-seconds", "86400"));
        if (expiration < 300 || expiration > 604_800) {
            throw new IllegalStateException("JWT_EXPIRE_SECONDS must be between 300 and 604800 in prod/staging");
        }
        if (!Boolean.parseBoolean(property("xianyu.media.cookie-secure", "false"))) {
            throw new IllegalStateException("MEDIA_COOKIE_SECURE must be true in prod/staging");
        }
        int mediaSessionMaxAge = parsePositiveInt(
                "MEDIA_SESSION_MAX_AGE_SECONDS",
                property("xianyu.media.session-max-age-seconds", "1200")
        );
        if (mediaSessionMaxAge < 60 || mediaSessionMaxAge > 1_200 || mediaSessionMaxAge > expiration) {
            throw new IllegalStateException(
                    "MEDIA_SESSION_MAX_AGE_SECONDS must be between 60 and 1200 and not exceed JWT_EXPIRE_SECONDS"
            );
        }
        requireSimpleIdentifier("JWT_ISSUER", property("admin.jwt.issuer"));
        requireSimpleIdentifier("JWT_AUDIENCE", property("admin.jwt.audience"));

        requireHttpsOrigins("ADMIN_CORS_ALLOWED_ORIGINS", property("admin.cors.allowed-origins"));
        requireHttpsOrigins("USER_CORS_ALLOWED_ORIGINS", property("admin.cors.user-allowed-origins"));
        requireEmpty("ADMIN_CORS_ALLOWED_ORIGIN_PATTERNS",
                property("admin.cors.allowed-origin-patterns"));
        requireEmpty("USER_CORS_ALLOWED_ORIGIN_PATTERNS",
                property("admin.cors.user-allowed-origin-patterns"));
        requireImageHostAllowlist(property("image.proxy.allowed-hosts"));
        requireAiProviderHostAllowlist(property("xianyu.ai.provider.allowed-hosts"));

        if (Boolean.parseBoolean(property("xianyu.ai.provider.enabled", "false"))) {
            requireHttpsUrl("AI_PROVIDER_BASE_URL", property("xianyu.ai.provider.base-url"));
            requireStrong("AI_PROVIDER_API_KEY", property("xianyu.ai.provider.api-key"), 20);
        }
    }

    private boolean isProductionLike() {
        return Arrays.stream(environment.getActiveProfiles())
                .map(value -> value.toLowerCase(Locale.ROOT))
                .anyMatch(PROD_LIKE::contains);
    }

    private String property(String name) {
        return property(name, "");
    }

    private String property(String name, String fallback) {
        return environment.getProperty(name, fallback);
    }

    private void requireStrong(String displayName, String value, int minLength) {
        String normalized = value == null ? "" : value.trim();
        String lower = normalized.toLowerCase(Locale.ROOT);
        long uniqueCharacters = normalized.chars().distinct().count();
        if (normalized.length() < minLength || uniqueCharacters < 4 || WEAK_VALUES.contains(lower)
                || lower.contains("replace-with") || lower.contains("placeholder")
                || lower.contains("dev-only") || lower.contains("change-me")) {
            throw new IllegalStateException(displayName + " is unsafe in prod/staging");
        }
    }

    private void requireHttpsOrigins(String displayName, String raw) {
        if (raw == null || raw.isBlank()) {
            throw new IllegalStateException(displayName + " must contain at least one explicit HTTPS origin");
        }
        for (String item : raw.split(",")) {
            String value = item.trim();
            try {
                URI uri = URI.create(value);
                boolean valid = "https".equalsIgnoreCase(uri.getScheme())
                        && uri.getHost() != null && !uri.getHost().isBlank()
                        && uri.getRawUserInfo() == null
                        && (uri.getRawPath() == null || uri.getRawPath().isEmpty())
                        && uri.getRawQuery() == null && uri.getRawFragment() == null
                        && !value.contains("*")
                        && !isLocalHost(uri.getHost());
                if (!valid) throw new IllegalArgumentException("invalid origin");
            } catch (RuntimeException e) {
                throw new IllegalStateException(displayName + " contains an unsafe origin");
            }
        }
    }

    private void requireEmpty(String displayName, String value) {
        if (value != null && !value.isBlank()) {
            throw new IllegalStateException(displayName + " must be empty in prod/staging; use explicit origins");
        }
    }

    private void requireImageHostAllowlist(String raw) {
        if (raw == null || raw.isBlank()) {
            throw new IllegalStateException("IMAGE_PROXY_ALLOWED_HOSTS must contain explicit public hosts");
        }
        Set<String> normalized = new HashSet<>();
        for (String item : raw.split(",")) {
            String host = item.trim().toLowerCase(Locale.ROOT);
            if (host.startsWith("*.")) host = host.substring(2);
            boolean valid = host.length() <= 253 && host.contains(".")
                    && host.matches("[a-z0-9.-]+")
                    && !host.startsWith(".") && !host.endsWith(".")
                    && !host.contains("..") && !isLocalHost(host);
            if (!valid || !normalized.add(host)) {
                throw new IllegalStateException("IMAGE_PROXY_ALLOWED_HOSTS contains an invalid or duplicate host");
            }
        }
    }

    private void requireAiProviderHostAllowlist(String raw) {
        if (raw == null || raw.isBlank()) {
            throw new IllegalStateException(
                    "AI_PROVIDER_ALLOWED_HOSTS must contain explicit provider hosts in prod/staging");
        }
        Set<String> normalized = new HashSet<>();
        for (String item : raw.split(",")) {
            String rule = item.trim().toLowerCase(Locale.ROOT);
            boolean wildcard = rule.startsWith("*.");
            String host = wildcard ? rule.substring(2) : rule;
            boolean valid = host.length() <= 253 && host.contains(".")
                    && host.matches("[a-z0-9.-]+")
                    && !host.startsWith(".") && !host.endsWith(".")
                    && !host.contains("..") && !isLocalHost(host)
                    && !host.matches("[0-9.]+");
            String canonicalRule = (wildcard ? "*." : "") + host;
            if (!valid || !normalized.add(canonicalRule)) {
                throw new IllegalStateException(
                        "AI_PROVIDER_ALLOWED_HOSTS contains an invalid or duplicate host rule");
            }
        }
    }

    private void requireHttpsUrl(String displayName, String value) {
        try {
            URI uri = URI.create(value == null ? "" : value.trim());
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                    || uri.getRawUserInfo() != null || isLocalHost(uri.getHost())) {
                throw new IllegalArgumentException("invalid URL");
            }
        } catch (RuntimeException e) {
            throw new IllegalStateException(displayName + " must be a public HTTPS URL");
        }
    }

    private void requireSimpleIdentifier(String displayName, String value) {
        if (value == null || !value.matches("[A-Za-z0-9._:-]{3,80}")) {
            throw new IllegalStateException(displayName + " is invalid");
        }
    }

    private int parsePositiveInt(String displayName, String raw) {
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException e) {
            throw new IllegalStateException(displayName + " must be an integer");
        }
    }

    private boolean isLocalHost(String host) {
        String value = host == null ? "" : host.toLowerCase(Locale.ROOT);
        return value.equals("localhost") || value.equals("127.0.0.1") || value.equals("::1")
                || value.endsWith(".local") || value.endsWith(".internal")
                || value.endsWith(".localhost");
    }
}
