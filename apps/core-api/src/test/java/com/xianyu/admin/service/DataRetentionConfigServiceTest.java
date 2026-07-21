package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 验证 DataRetentionConfigService：
 *   1. 缺省配置返回文档化默认值（enabled=true, retentionDays=14, 所有类别开启）
 *   2. 数据库故障抛 503 而非返回伪造默认值
 *   3. 零行更新抛 409（并发保护）
 *   4. retentionDays 越界拒绝保存
 *   5. getRetentionInfoForPublic 仅返回公开字段（retentionDays + chatMessageCleanupEnabled）
 */
class DataRetentionConfigServiceTest {

    @Test
    void missingConfigurationReturnsDocumentedDefaults() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());

        Map<String, Object> config = new DataRetentionConfigService(jdbc).getConfig();

        assertEquals(true, config.get("enabled"));
        assertEquals(14, ((Number) config.get("retentionDays")).intValue());
        assertEquals("0 0 4 * * ?", config.get("cleanupCron"));
        @SuppressWarnings("unchecked")
        Map<String, Object> categories = (Map<String, Object>) config.get("categories");
        assertEquals(true, categories.get("operationLog"));
        assertEquals(true, categories.get("chatMessage"));
        assertEquals(true, categories.get("autoReplyLog"));
        verify(jdbc, never()).update(anyString(), any(Object[].class));
    }

    @Test
    void databaseFailureIsUnavailableInsteadOfFakeDefaultConfiguration() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class)))
                .thenThrow(new RuntimeException("database unavailable password=secret"));

        BizException error = assertThrows(BizException.class,
                () -> new DataRetentionConfigService(jdbc).getConfig());

        assertEquals(503, error.getCode());
    }

    @Test
    void zeroAffectedUpdateCannotBecomeSuccessfulConfigurationSave() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class)))
                .thenReturn(List.of(Map.of("id", 9L)));
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(0);

        BizException error = assertThrows(BizException.class,
                () -> new DataRetentionConfigService(jdbc).saveConfig(Map.of("enabled", true, "retentionDays", 14)));

        assertEquals(409, error.getCode());
    }

    @Test
    void retentionDaysOutOfRangeIsRejected() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);

        BizException tooSmall = assertThrows(BizException.class,
                () -> new DataRetentionConfigService(jdbc).saveConfig(Map.of("enabled", true, "retentionDays", 0)));
        assertEquals(400, tooSmall.getCode());

        BizException tooLarge = assertThrows(BizException.class,
                () -> new DataRetentionConfigService(jdbc).saveConfig(Map.of("enabled", true, "retentionDays", 366)));
        assertEquals(400, tooLarge.getCode());

        verify(jdbc, never()).queryForList(anyString(), any(Object[].class));
        verify(jdbc, never()).update(anyString(), any(Object[].class));
    }

    @Test
    void publicInfoOnlyExposesRetentionDaysAndChatFlag() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());

        Map<String, Object> info = new DataRetentionConfigService(jdbc).getRetentionInfoForPublic();

        assertEquals(2, info.size());
        assertEquals(14, ((Number) info.get("retentionDays")).intValue());
        assertEquals(true, info.get("chatMessageCleanupEnabled"));
        assertFalse(info.containsKey("enabled"), "不应暴露全局 enabled 开关给前台");
        assertFalse(info.containsKey("cleanupCron"), "不应暴露 cron 表达式给前台");
        assertFalse(info.containsKey("categories"), "不应暴露类别开关详情给前台");
    }

    @Test
    void recordCleanupResultWritesLastCleanupStatistics() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class)))
                .thenReturn(List.of(Map.of("id", 9L)));
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);

        new DataRetentionConfigService(jdbc).recordCleanupResult(1234, Map.of("operationLog", 100, "chatMessage", 800));

        verify(jdbc).update(anyString(), any(Object[].class));
    }
}
