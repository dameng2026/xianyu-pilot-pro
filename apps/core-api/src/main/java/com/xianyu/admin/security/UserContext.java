package com.xianyu.admin.security;

/**
 * 前台用户请求级上下文，基于 ThreadLocal 存储当前用户信息。
 * 由 UserJwtAuthFilter 设置，请求结束后自动清除。
 */
public class UserContext {
    private static final ThreadLocal<Long> USER_ID = new ThreadLocal<>();
    private static final ThreadLocal<String> USERNAME = new ThreadLocal<>();
    private static final ThreadLocal<Long> TENANT_ID = new ThreadLocal<>();

    public static void set(Long userId, String username, Long tenantId) {
        USER_ID.set(userId);
        USERNAME.set(username);
        TENANT_ID.set(tenantId);
    }

    public static Long userId() { return USER_ID.get(); }
    public static String username() { return USERNAME.get(); }
    public static Long getTenantId() { return TENANT_ID.get(); }

    public static void clear() {
        USER_ID.remove();
        USERNAME.remove();
        TENANT_ID.remove();
    }
}