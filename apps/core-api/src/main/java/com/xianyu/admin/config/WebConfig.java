package com.xianyu.admin.config;

import com.xianyu.admin.security.FeatureGuardFilter;
import com.xianyu.admin.security.JwtAuthFilter;
import com.xianyu.admin.security.UserJwtAuthFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.web.filter.CorsFilter;
import org.springframework.web.servlet.config.annotation.AsyncSupportConfigurer;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;
import java.util.function.Consumer;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Bean
    public FilterRegistrationBean<TraceIdFilter> traceIdFilter() {
        FilterRegistrationBean<TraceIdFilter> bean = new FilterRegistrationBean<>(new TraceIdFilter());
        bean.addUrlPatterns("/*");
        bean.setOrder(1);
        return bean;
    }

    @Bean
    public FilterRegistrationBean<JwtAuthFilter> jwtFilter(JwtAuthFilter filter) {
        FilterRegistrationBean<JwtAuthFilter> bean = new FilterRegistrationBean<>(filter);
        bean.addUrlPatterns("/admin-api/*");
        bean.setOrder(2);
        return bean;
    }

    @Bean
    public FilterRegistrationBean<UserJwtAuthFilter> userJwtFilter(UserJwtAuthFilter filter) {
        FilterRegistrationBean<UserJwtAuthFilter> bean = new FilterRegistrationBean<>(filter);
        bean.addUrlPatterns("/api/*");
        bean.setOrder(3);
        return bean;
    }

    /**
     * 功能开关强制校验（后端兜底，防绕过前端拦截）。
     * 必须在用户鉴权（order=3）之后执行，确保 TenantContext 已填充 userId。
     */
    @Bean
    public FilterRegistrationBean<FeatureGuardFilter> featureGuardFilter(FeatureGuardFilter filter) {
        FilterRegistrationBean<FeatureGuardFilter> bean = new FilterRegistrationBean<>(filter);
        bean.addUrlPatterns("/api/*");
        bean.setOrder(4);
        return bean;
    }

    @Bean
    public CorsFilter corsFilter(
            @Value("${admin.cors.allowed-origins:}") String adminOrigins,
            @Value("${admin.cors.allowed-origin-patterns:}") String adminOriginPatterns,
            @Value("${admin.cors.user-allowed-origins:}") String userOrigins,
            @Value("${admin.cors.user-allowed-origin-patterns:}") String userOriginPatterns) {
        CorsConfiguration adminConfig = createCorsConfiguration(adminOrigins, adminOriginPatterns);
        CorsConfiguration apiConfig = createCorsConfiguration(
                mergeCsv(adminOrigins, userOrigins),
                mergeCsv(adminOriginPatterns, userOriginPatterns)
        );

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/admin-api/**", adminConfig);
        source.registerCorsConfiguration("/api/**", apiConfig);
        return new CorsFilter(source);
    }

    @Bean
    public FilterRegistrationBean<CorsFilter> corsFilterRegistration(CorsFilter corsFilter) {
        FilterRegistrationBean<CorsFilter> bean = new FilterRegistrationBean<>(corsFilter);
        bean.addUrlPatterns("/*");
        // CORS must wrap authentication so 401/403 responses remain readable
        // by the configured browser origins instead of surfacing as a generic
        // client-side network error.
        bean.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return bean;
    }

    private static CorsConfiguration createCorsConfiguration(String origins, String originPatterns) {
        CorsConfiguration config = new CorsConfiguration();
        addCsvValues(origins, config::addAllowedOrigin);
        addCsvValues(originPatterns, config::addAllowedOriginPattern);
        config.addAllowedHeader("*");
        config.addAllowedMethod("*");
        config.setAllowCredentials(false);
        return config;
    }

    private static void addCsvValues(String rawValue, Consumer<String> consumer) {
        if (rawValue == null || rawValue.isBlank()) {
            return;
        }
        Arrays.stream(rawValue.split(","))
                .map(String::trim)
                .filter(s -> !s.isBlank())
                .forEach(consumer);
    }

    private static String mergeCsv(String left, String right) {
        if (left == null || left.isBlank()) {
            return right == null ? "" : right;
        }
        if (right == null || right.isBlank()) {
            return left;
        }
        return left + "," + right;
    }

    @Override
    public void configureAsyncSupport(AsyncSupportConfigurer configurer) {
        // SSE 连接需要长期保持，默认异步超时会被 Spring 提前回收并导致前端收到 503。
        configurer.setDefaultTimeout(0);
    }

}
