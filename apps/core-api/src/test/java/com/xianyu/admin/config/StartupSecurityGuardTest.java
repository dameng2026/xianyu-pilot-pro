package com.xianyu.admin.config;

import org.junit.jupiter.api.Test;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.mock.env.MockEnvironment;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class StartupSecurityGuardTest {

    @Test
    void productionRequiresApiKeyCryptoSecret() {
        MockEnvironment environment = secureProductionEnvironment();
        environment.setProperty("xianyu.api-key.crypto-secret", "");

        IllegalStateException error = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(environment).run(args()));

        assertTrue(error.getMessage().contains("API_KEY_CRYPTO_SECRET"));
    }

    @Test
    void productionRequiresOperationsMetricsToken() {
        MockEnvironment environment = secureProductionEnvironment();
        environment.setProperty("ops.metrics.token", "");

        IllegalStateException error = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(environment).run(args()));

        assertTrue(error.getMessage().contains("OPS_METRICS_TOKEN"));
    }

    @Test
    void productionRejectsInsecureCorsOrigins() {
        MockEnvironment environment = secureProductionEnvironment();
        environment.setProperty("admin.cors.user-allowed-origins", "http://app.example.com");

        IllegalStateException error = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(environment).run(args()));

        assertTrue(error.getMessage().contains("USER_CORS_ALLOWED_ORIGINS"));
    }

    @Test
    void productionRequiresRedisAuthenticationAndAnImageHostAllowlist() {
        MockEnvironment redisEnvironment = secureProductionEnvironment();
        redisEnvironment.setProperty("spring.data.redis.password", "");

        IllegalStateException redisError = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(redisEnvironment).run(args()));
        assertTrue(redisError.getMessage().contains("REDIS_PASSWORD"));

        MockEnvironment imageEnvironment = secureProductionEnvironment();
        imageEnvironment.setProperty("image.proxy.allowed-hosts", "");
        IllegalStateException imageError = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(imageEnvironment).run(args()));
        assertTrue(imageError.getMessage().contains("IMAGE_PROXY_ALLOWED_HOSTS"));
    }

    @Test
    void productionRequiresExplicitAiProviderHostRules() {
        MockEnvironment missing = secureProductionEnvironment();
        missing.setProperty("xianyu.ai.provider.allowed-hosts", "");

        IllegalStateException missingError = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(missing).run(args()));
        assertTrue(missingError.getMessage().contains("AI_PROVIDER_ALLOWED_HOSTS"));

        MockEnvironment invalid = secureProductionEnvironment();
        invalid.setProperty("xianyu.ai.provider.allowed-hosts", "*.localhost");
        IllegalStateException invalidError = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(invalid).run(args()));
        assertTrue(invalidError.getMessage().contains("AI_PROVIDER_ALLOWED_HOSTS"));
    }

    @Test
    void secureProductionConfigurationPasses() {
        assertDoesNotThrow(() -> new StartupSecurityGuard(secureProductionEnvironment()).run(args()));
    }

    @Test
    void productionRequiresSecureShortLivedMediaCookies() {
        MockEnvironment insecureCookie = secureProductionEnvironment();
        insecureCookie.setProperty("xianyu.media.cookie-secure", "false");
        IllegalStateException cookieError = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(insecureCookie).run(args()));
        assertTrue(cookieError.getMessage().contains("MEDIA_COOKIE_SECURE"));

        MockEnvironment excessiveLifetime = secureProductionEnvironment();
        excessiveLifetime.setProperty("xianyu.media.session-max-age-seconds", "1201");
        IllegalStateException lifetimeError = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(excessiveLifetime).run(args()));
        assertTrue(lifetimeError.getMessage().contains("MEDIA_SESSION_MAX_AGE_SECONDS"));
    }

    @Test
    void productionRejectsRuntimeSchemaMutations() {
        MockEnvironment environment = secureProductionEnvironment();
        environment.setProperty("xianyu.schema.runtime-mutations-enabled", "true");

        IllegalStateException error = assertThrows(IllegalStateException.class,
                () -> new StartupSecurityGuard(environment).run(args()));

        assertTrue(error.getMessage().contains("SCHEMA_RUNTIME_MUTATIONS_ENABLED"));
    }

    @Test
    void developmentDoesNotRequireProductionSecrets() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("dev");

        assertDoesNotThrow(() -> new StartupSecurityGuard(environment).run(args()));
    }

    private MockEnvironment secureProductionEnvironment() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("prod");
        environment.setProperty("xianyu.security-guard.enabled", "true");
        environment.setProperty("xianyu.automation.internal-token", strong("internal"));
        environment.setProperty("admin.jwt.secret", strong("jwt"));
        environment.setProperty("xianyu.cookie.crypto-secret", strong("cookie"));
        environment.setProperty("xianyu.api-key.crypto-secret", strong("api-key"));
        environment.setProperty("ops.metrics.token", strong("metrics"));
        environment.setProperty("spring.datasource.password", strong("mysql"));
        environment.setProperty("spring.data.redis.password", strong("redis"));
        environment.setProperty("admin.seed.enabled", "false");
        environment.setProperty("xianyu.schema.runtime-mutations-enabled", "false");
        environment.setProperty("admin.jwt.expire-seconds", "3600");
        environment.setProperty("xianyu.media.cookie-secure", "true");
        environment.setProperty("xianyu.media.session-max-age-seconds", "1200");
        environment.setProperty("admin.jwt.issuer", "xianyu-core-api");
        environment.setProperty("admin.jwt.audience", "xianyu-user-api");
        environment.setProperty("admin.cors.allowed-origins", "https://admin.example.com");
        environment.setProperty("admin.cors.allowed-origin-patterns", "");
        environment.setProperty("admin.cors.user-allowed-origins", "https://app.example.com");
        environment.setProperty("admin.cors.user-allowed-origin-patterns", "");
        environment.setProperty("image.proxy.allowed-hosts", "cdn.example.com,images.example.com");
        environment.setProperty("xianyu.ai.provider.allowed-hosts", "api.openai.com,*.trusted-ai.example.com");
        environment.setProperty("xianyu.sync.token", strong("sync"));
        environment.setProperty("xianyu.ai.provider.enabled", "false");
        return environment;
    }

    private String strong(String prefix) {
        return prefix + "-A9!" + "x7Qp".repeat(10);
    }

    private DefaultApplicationArguments args() {
        return new DefaultApplicationArguments(new String[0]);
    }
}
