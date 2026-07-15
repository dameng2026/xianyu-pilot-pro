package com.xianyu.admin.security;

/**
 * 租户上下文，基于 ThreadLocal 存储当前请求的租户信息。
 * 由 TenantInterceptor 设置，请求结束后自动清除。
 */
public class TenantContext {
    private static final ThreadLocal<Long> TENANT_ID = new ThreadLocal<>();
    private static final ThreadLocal<Long> USER_ID = new ThreadLocal<>();

    public static void setCurrentTenantId(Long tenantId) {
        TENANT_ID.set(tenantId);
    }

    public static Long getCurrentTenantId() {
        return TENANT_ID.get();
    }

    public static void setCurrentUserId(Long userId) {
        USER_ID.set(userId);
    }

    public static Long getCurrentUserId() {
        return USER_ID.get();
    }

    public static void clear() {
        TENANT_ID.remove();
        USER_ID.remove();
    }
}