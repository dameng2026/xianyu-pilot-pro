package com.xianyu.admin.security;

public class AdminContext {
    private static final ThreadLocal<Long> USER_ID = new ThreadLocal<>();
    private static final ThreadLocal<String> USERNAME = new ThreadLocal<>();
    private static final ThreadLocal<String> ROLES = new ThreadLocal<>();

    public static void set(Long userId, String username) { set(userId, username, null); }

    public static void set(Long userId, String username, String roles) {
        USER_ID.set(userId);
        USERNAME.set(username);
        ROLES.set(roles);
    }

    public static Long userId() { return USER_ID.get(); }
    public static String username() { return USERNAME.get(); }
    public static String roles() { return ROLES.get(); }

    public static boolean hasRole(String role) {
        String roles = ROLES.get();
        if (roles == null || role == null) return false;
        for (String item : roles.split(",")) {
            if (role.equals(item.trim())) return true;
        }
        return false;
    }

    public static void clear() { USER_ID.remove(); USERNAME.remove(); ROLES.remove(); }
}
