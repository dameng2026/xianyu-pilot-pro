package com.xianyu.admin.security;

/**
 * API 滑块求解对接的鉴权上下文。
 * 由 ApikeyAuthFilter 在校验 X-Api-Key 通过后设置，请求结束 clear()。
 */
public class ApiSliderContext {
    private static final ThreadLocal<Long> TENANT_ID = new ThreadLocal<>();
    private static final ThreadLocal<String> API_KEY_PREFIX = new ThreadLocal<>();

    public static void set(Long tenantId, String apiKeyPrefix) {
        TENANT_ID.set(tenantId);
        API_KEY_PREFIX.set(apiKeyPrefix);
    }

    public static Long tenantId() {
        return TENANT_ID.get();
    }

    public static String apiKeyPrefix() {
        return API_KEY_PREFIX.get();
    }

    public static void clear() {
        TENANT_ID.remove();
        API_KEY_PREFIX.remove();
    }
}
