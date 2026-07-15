package com.xianyu.admin.common;

/**
 * 分页参数归一化工具。
 * 统一限制最大 page size，避免恶意大分页拖垮数据库和 JVM。
 */
public final class PageUtils {
    public static final int DEFAULT_MAX_SIZE = 100;

    private PageUtils() {}

    public static int normalizeCurrent(int current) {
        return Math.max(current, 1);
    }

    public static int normalizeSize(int size) {
        return normalizeSize(size, DEFAULT_MAX_SIZE);
    }

    public static int normalizeSize(int size, int maxSize) {
        int safeMax = Math.max(maxSize, 1);
        return Math.min(Math.max(size, 1), safeMax);
    }

    public static int offset(int current, int size) {
        int safeCurrent = normalizeCurrent(current);
        int safeSize = normalizeSize(size);
        return (safeCurrent - 1) * safeSize;
    }
}
