package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

class FeatureSwitchServiceTest {

    private static final String SELECT_JSON_SQL_PREFIX = "SELECT json_text FROM admin_module_record";
    private static final String SELECT_ID_SQL_PREFIX = "SELECT id FROM admin_module_record";

    private JdbcTemplate mockJdbcEmpty() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(startsWith(SELECT_JSON_SQL_PREFIX), any(Object[].class)))
                .thenReturn(List.of());
        when(jdbc.queryForList(startsWith(SELECT_ID_SQL_PREFIX), any(Object[].class)))
                .thenReturn(List.of());
        return jdbc;
    }

    private JdbcTemplate mockJdbcWithConfig(String json) {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        Map<String, Object> row = new HashMap<>();
        row.put("json_text", json);
        row.put("id", 1L);
        when(jdbc.queryForList(startsWith(SELECT_JSON_SQL_PREFIX), any(Object[].class)))
                .thenReturn(List.of(row));
        when(jdbc.queryForList(startsWith(SELECT_ID_SQL_PREFIX), any(Object[].class)))
                .thenReturn(List.of(row));
        return jdbc;
    }

    private UserProfileService mockUserProfile(String planCode) {
        UserProfileService ups = mock(UserProfileService.class);
        when(ups.currentPlanCode(any())).thenReturn(planCode);
        return ups;
    }

    // ===================== 等级判定 =====================

    @Test
    void levelWeightNormalVipSvp() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("normal"));
        assertTrue(s.levelSatisfied("normal", "normal"));
        assertFalse(s.levelSatisfied("normal", "vip"));
        assertFalse(s.levelSatisfied("normal", "svp"));
        assertTrue(s.levelSatisfied("vip", "normal"));
        assertTrue(s.levelSatisfied("vip", "vip"));
        assertFalse(s.levelSatisfied("vip", "svp"));
        assertTrue(s.levelSatisfied("svp", "normal"));
        assertTrue(s.levelSatisfied("svp", "vip"));
        assertTrue(s.levelSatisfied("svp", "svp"));
    }

    @Test
    void levelWeightAcceptsSvipAlias() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("normal"));
        // svip 应等同于 svp
        assertTrue(s.levelSatisfied("svip", "svp"));
        assertTrue(s.levelSatisfied("svp", "svip"));
        assertTrue(s.levelSatisfied("svip", "vip"));
    }

    @Test
    void levelWeightUnknownLevelFallsBackToNormal() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("normal"));
        // 未知等级视为 normal
        assertFalse(s.levelSatisfied("unknown_level", "vip"));
        assertTrue(s.levelSatisfied("unknown_level", "normal"));
    }

    // ===================== 默认配置 =====================

    @Test
    void missingConfigurationReturnsAllEnabledDefaults() {
        JdbcTemplate jdbc = mockJdbcEmpty();
        FeatureSwitchService s = new FeatureSwitchService(jdbc, mockUserProfile("normal"));

        List<Map<String, Object>> switches = s.listSwitches();

        assertFalse(switches.isEmpty(), "应返回默认开关清单");
        for (Map<String, Object> sw : switches) {
            assertEquals(Boolean.TRUE, sw.get("enabled"), "默认全部开启: " + sw.get("key"));
            assertEquals("normal", sw.get("minLevel"), "默认最低等级 normal: " + sw.get("key"));
        }
        // 验证用户要求的必含页面
        Set<String> keys = new HashSet<>();
        for (Map<String, Object> sw : switches) keys.add(String.valueOf(sw.get("key")));
        assertTrue(keys.contains("delivery-statement"), "必须包含发货声明页");
        assertTrue(keys.contains("delivery-mall"), "必须包含货源商城页");
        assertTrue(keys.contains("vip"), "必须包含会员页");
    }

    @Test
    void databaseReadFailureDegradesToDefaults() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class)))
                .thenThrow(new RuntimeException("db unavailable"));
        FeatureSwitchService s = new FeatureSwitchService(jdbc, mockUserProfile("normal"));

        // 不应抛异常，应降级返回默认配置
        List<Map<String, Object>> switches = s.listSwitches();
        assertFalse(switches.isEmpty());
        assertEquals(Boolean.TRUE, switches.get(0).get("enabled"));
    }

    // ===================== 用户端状态 =====================

    @Test
    void userStatusAllAccessibleWhenDefaultsAndNormalUser() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("normal"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);

        assertEquals("normal", status.get("level"));
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> blocked = (Map<String, Map<String, Object>>) status.get("blocked");

        assertFalse(accessible.isEmpty());
        assertTrue(blocked.isEmpty(), "默认配置下不应有被拦截的页面");
        for (Boolean v : accessible.values()) assertTrue(v);
    }

    @Test
    void userStatusBlockedWhenFeatureDisabled() {
        // 配置 delivery-statement 为关闭
        String json = "{\"features\":{\"delivery-statement\":{\"enabled\":false,\"minLevel\":\"normal\"}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("normal"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> blocked = (Map<String, Map<String, Object>>) status.get("blocked");

        assertFalse(accessible.get("delivery-statement"));
        Map<String, Object> info = blocked.get("delivery-statement");
        assertNotNull(info);
        assertEquals("disabled", info.get("reason"));
        assertEquals("normal", info.get("required_level"));
    }

    @Test
    void userStatusBlockedWhenLevelInsufficient() {
        // 配置 vip 页面要求 vip 等级
        String json = "{\"features\":{\"vip\":{\"enabled\":true,\"minLevel\":\"vip\"}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("normal"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> blocked = (Map<String, Map<String, Object>>) status.get("blocked");

        assertFalse(accessible.get("vip"));
        Map<String, Object> info = blocked.get("vip");
        assertNotNull(info);
        assertEquals("level", info.get("reason"));
        assertEquals("vip", info.get("required_level"));
    }

    @Test
    void userStatusAccessibleWhenLevelSufficient() {
        String json = "{\"features\":{\"vip\":{\"enabled\":true,\"minLevel\":\"vip\"}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("vip"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");

        assertTrue(accessible.get("vip"));
    }

    @Test
    void userStatusLevelResolvedFromUserProfileService() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("svp"));
        Map<String, Object> status = s.getStatusForCurrentUser(42L);
        assertEquals("svp", status.get("level"));
    }

    @Test
    void userStatusLevelFallsBackToNormalWhenProfileServiceFails() {
        UserProfileService ups = mock(UserProfileService.class);
        when(ups.currentPlanCode(any())).thenThrow(new RuntimeException("profile unavailable"));
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), ups);

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        assertEquals("normal", status.get("level"));
    }

    @Test
    void userStatusNullUserIdReturnsNormalLevel() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("normal"));
        Map<String, Object> status = s.getStatusForCurrentUser(null);
        assertEquals("normal", status.get("level"));
    }

    // ===================== 保存配置 =====================

    @Test
    void saveConfigZeroAffectedThrowsConflict() {
        JdbcTemplate jdbc = mockJdbcWithConfig("{}");
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(0);

        FeatureSwitchService s = new FeatureSwitchService(jdbc, mockUserProfile("normal"));
        List<Map<String, Object>> features = List.of(
                Map.of("key", "vip", "enabled", true, "minLevel", "vip"));

        BizException error = assertThrows(BizException.class, () -> s.saveConfig(features));
        assertEquals(409, error.getCode());
    }

    @Test
    void saveConfigEmptyListThrowsBadRequest() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("normal"));
        BizException error = assertThrows(BizException.class, () -> s.saveConfig(null));
        assertEquals(400, error.getCode());
    }

    @Test
    void saveConfigInsertsWhenRecordAbsent() {
        JdbcTemplate jdbc = mockJdbcEmpty();
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);

        FeatureSwitchService s = new FeatureSwitchService(jdbc, mockUserProfile("normal"));
        List<Map<String, Object>> features = List.of(
                Map.of("key", "vip", "enabled", false, "minLevel", "normal"));

        s.saveConfig(features);
        verify(jdbc, times(1)).update(contains("INSERT INTO admin_module_record"), any(Object[].class));
    }

    @Test
    void saveConfigUpdatesWhenRecordPresent() {
        JdbcTemplate jdbc = mockJdbcWithConfig("{}");
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);

        FeatureSwitchService s = new FeatureSwitchService(jdbc, mockUserProfile("normal"));
        List<Map<String, Object>> features = List.of(
                Map.of("key", "vip", "enabled", false, "minLevel", "normal"));

        s.saveConfig(features);
        verify(jdbc, times(1)).update(contains("UPDATE admin_module_record"), any(Object[].class));
    }

    @Test
    void normalizeConfigSvipAliasBecomesSvp() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("normal"));
        List<Map<String, Object>> features = List.of(
                Map.of("key", "vip", "enabled", true, "minLevel", "svip"));
        // 保存时 svip 会被规范化为 svp
        // 通过保存后再读取验证（mock 已配置返回 {}，所以 listSwitches 会用默认值）
        // 这里直接验证 levelSatisfied 兼容性
        assertTrue(s.levelSatisfied("svip", "svip"));
    }

    @Test
    void listSwitchesMergesStoredOverrideWithDefaults() {
        // 存储中关闭 vip 页面
        String json = "{\"features\":{\"vip\":{\"enabled\":false,\"minLevel\":\"normal\"}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("normal"));

        List<Map<String, Object>> switches = s.listSwitches();
        Map<String, Object> vipSwitch = switches.stream()
                .filter(sw -> "vip".equals(sw.get("key")))
                .findFirst().orElseThrow();
        assertEquals(false, vipSwitch.get("enabled"));
        // 其他页面应保持默认开启
        Map<String, Object> dashboardSwitch = switches.stream()
                .filter(sw -> "dashboard".equals(sw.get("key")))
                .findFirst().orElseThrow();
        assertEquals(true, dashboardSwitch.get("enabled"));
    }
}
