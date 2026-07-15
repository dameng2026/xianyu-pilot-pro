package com.xianyu.admin.common;

/**
 * 敏感信息脱敏工具类。
 * 用于在 admin 端列表/详情接口返回数据时对 phone / email 等 PII 字段做掩码处理。
 */
public final class MaskUtil {

    private MaskUtil() {}

    /**
     * 手机号脱敏：保留前 3 位和后 4 位，中间用 **** 替换。
     * 例：13812345678 -> 138****5678
     * 非手机号格式（长度不等于 11 或含非数字字符）原样返回。
     */
    public static String maskPhone(String phone) {
        if (phone == null || phone.isBlank()) return phone;
        String trimmed = phone.trim();
        if (trimmed.length() == 11 && trimmed.chars().allMatch(Character::isDigit)) {
            return trimmed.substring(0, 3) + "****" + trimmed.substring(7);
        }
        // 非标准手机号，仅保留首尾各 1 位
        if (trimmed.length() > 4) {
            return trimmed.charAt(0) + "***" + trimmed.charAt(trimmed.length() - 1);
        }
        return trimmed;
    }

    /**
     * 邮箱脱敏：保留首字符和 @ 后域名，中间用 *** 替换。
     * 例：alice@example.com -> a***@example.com
     * 无 @ 符号的字符串原样返回。
     */
    public static String maskEmail(String email) {
        if (email == null || email.isBlank()) return email;
        int atIdx = email.indexOf('@');
        if (atIdx <= 0) return email;
        String local = email.substring(0, atIdx);
        String domain = email.substring(atIdx);
        if (local.length() <= 1) {
            return local + "***" + domain;
        }
        return local.charAt(0) + "***" + domain;
    }

    /**
     * 通用字符串脱敏：保留首尾各 1 字符，中间用 *** 替换。
     * 长度 ≤ 2 的字符串返回 ***。
     */
    public static String maskGeneric(String value) {
        if (value == null || value.isBlank()) return value;
        if (value.length() <= 2) return "***";
        return value.charAt(0) + "***" + value.charAt(value.length() - 1);
    }
}
