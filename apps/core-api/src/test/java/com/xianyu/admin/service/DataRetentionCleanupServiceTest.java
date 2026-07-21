package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 验证 DataRetentionCleanupService：
 *   1. enabled=false 时跳过所有清理
 *   2. 对每个开启的类别按 created_time < DATE_SUB(NOW(), INTERVAL N DAY) 删除
 *   3. chatMessage 使用 message_time（毫秒时间戳），条件为 message_time < UNIX_TIMESTAMP(NOW() - INTERVAL N DAY) * 1000
 *   4. 分批删除（每批 500 条），直到某批返回 0 行停止
 *   5. 单类别异常不阻断其他类别
 *   6. 清理完成后回写 lastCleanup 统计
 */
class DataRetentionCleanupServiceTest {

    private DataRetentionConfigService configServiceReturning(Map<String, Object> config) {
        DataRetentionConfigService configService = mock(DataRetentionConfigService.class);
        when(configService.getConfig()).thenReturn(config);
        return configService;
    }

    private Map<String, Object> enabledConfigWithAllCategories(int retentionDays) {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("enabled", true);
        config.put("retentionDays", retentionDays);
        config.put("cleanupCron", "0 0 4 * * ?");
        Map<String, Object> cats = new LinkedHashMap<>();
        for (String cat : DataRetentionConfigService.CLEANUP_CATEGORIES) {
            cats.put(cat, true);
        }
        config.put("categories", cats);
        return config;
    }

    @Test
    void disabledConfigSkipsAllCleanup() {
        DataRetentionConfigService configService = mock(DataRetentionConfigService.class);
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("enabled", false);
        config.put("retentionDays", 14);
        when(configService.getConfig()).thenReturn(config);
        JdbcTemplate jdbc = mock(JdbcTemplate.class);

        DataRetentionCleanupService service = new DataRetentionCleanupService(jdbc, configService);

        DataRetentionCleanupService.CleanupResult result = service.executeCleanup();

        assertEquals(0, result.totalDeleted);
        verify(jdbc, never()).update(anyString(), any(Object[].class));
        verify(configService, never()).recordCleanupResult(anyInt(), any());
    }

    @Test
    void deletesByCreatedTimeForRegularCategories() {
        Map<String, Object> config = enabledConfigWithAllCategories(14);
        // 仅 operationLog 开启，其他关闭，避免测试干扰
        @SuppressWarnings("unchecked")
        Map<String, Object> cats = (Map<String, Object>) config.get("categories");
        for (String cat : DataRetentionConfigService.CLEANUP_CATEGORIES) {
            cats.put(cat, false);
        }
        cats.put("operationLog", true);

        DataRetentionConfigService configService = configServiceReturning(config);
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        // 第一批删 500 条，第二批删 0 条停止
        when(jdbc.update(anyString(), any(Object[].class)))
                .thenReturn(500)
                .thenReturn(0);

        DataRetentionCleanupService service = new DataRetentionCleanupService(jdbc, configService);

        DataRetentionCleanupService.CleanupResult result = service.executeCleanup();

        assertEquals(500, result.totalDeleted);
        assertEquals(500, result.byCategory.get("operationLog"));
        // 验证 SQL 使用 created_time 字段
        verify(jdbc, atLeastOnce()).update(
                org.mockito.ArgumentMatchers.contains("created_time"),
                any(Object[].class));
        // 验证不使用 message_time 字段（非 chatMessage 类别）
        verify(jdbc, never()).update(
                org.mockito.ArgumentMatchers.contains("message_time"),
                any(Object[].class));
        verify(configService, times(1)).recordCleanupResult(eq(500), any());
    }

    @Test
    void chatMessageUsesMessageTimeInMillisTimestamp() {
        Map<String, Object> config = enabledConfigWithAllCategories(7);
        @SuppressWarnings("unchecked")
        Map<String, Object> cats = (Map<String, Object>) config.get("categories");
        for (String cat : DataRetentionConfigService.CLEANUP_CATEGORIES) {
            cats.put(cat, false);
        }
        cats.put("chatMessage", true);

        DataRetentionConfigService configService = configServiceReturning(config);
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.update(anyString(), any(Object[].class)))
                .thenReturn(300)
                .thenReturn(0);

        DataRetentionCleanupService service = new DataRetentionCleanupService(jdbc, configService);

        DataRetentionCleanupService.CleanupResult result = service.executeCleanup();

        assertEquals(300, result.totalDeleted);
        verify(jdbc, atLeastOnce()).update(
                org.mockito.ArgumentMatchers.contains("message_time"),
                any(Object[].class));
        // 验证使用 UNIX_TIMESTAMP * 1000 表达式（毫秒时间戳）
        verify(jdbc, atLeastOnce()).update(
                org.mockito.ArgumentMatchers.contains("UNIX_TIMESTAMP"),
                any(Object[].class));
    }

    @Test
    void singleCategoryFailureDoesNotAbortOthers() {
        Map<String, Object> config = enabledConfigWithAllCategories(14);
        @SuppressWarnings("unchecked")
        Map<String, Object> cats = (Map<String, Object>) config.get("categories");
        for (String cat : DataRetentionConfigService.CLEANUP_CATEGORIES) {
            cats.put(cat, false);
        }
        cats.put("operationLog", true);
        cats.put("clientErrorLog", true);

        DataRetentionConfigService configService = configServiceReturning(config);
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        // operationLog 抛异常，clientErrorLog 正常
        when(jdbc.update(anyString(), any(Object[].class)))
                .thenThrow(new RuntimeException("simulated failure"))
                .thenReturn(200)
                .thenReturn(0);

        DataRetentionCleanupService service = new DataRetentionCleanupService(jdbc, configService);

        DataRetentionCleanupService.CleanupResult result = service.executeCleanup();

        // operationLog 失败记 0，clientErrorLog 删 200
        assertEquals(200, result.totalDeleted);
        assertEquals(200, result.byCategory.get("clientErrorLog"));
        verify(configService, times(1)).recordCleanupResult(eq(200), any());
    }

    @Test
    void batchDeletionStopsWhenZeroRowsAffected() {
        Map<String, Object> config = enabledConfigWithAllCategories(14);
        @SuppressWarnings("unchecked")
        Map<String, Object> cats = (Map<String, Object>) config.get("categories");
        for (String cat : DataRetentionConfigService.CLEANUP_CATEGORIES) {
            cats.put(cat, false);
        }
        cats.put("autoReplyLog", true);

        DataRetentionConfigService configService = configServiceReturning(config);
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        // 第一批 500，第二批 500，第三批 0 停止
        when(jdbc.update(anyString(), any(Object[].class)))
                .thenReturn(500)
                .thenReturn(500)
                .thenReturn(0);

        DataRetentionCleanupService service = new DataRetentionCleanupService(jdbc, configService);

        DataRetentionCleanupService.CleanupResult result = service.executeCleanup();

        assertEquals(1000, result.totalDeleted);
        assertEquals(1000, result.byCategory.get("autoReplyLog"));
    }
}
