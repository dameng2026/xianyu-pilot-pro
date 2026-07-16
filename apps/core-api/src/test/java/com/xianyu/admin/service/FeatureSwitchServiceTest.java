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

    // ===================== 默认配置 =====================

    @Test
    void missingConfigurationReturnsAllLevelsEnabled() {
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcEmpty(), mockUserProfile("normal"));

        List<Map<String, Object>> switches = s.listSwitches();

        assertFalse(switches.isEmpty(), "应返回默认开关清单");
        for (Map<String, Object> sw : switches) {
            assertEquals(Boolean.TRUE, sw.get("normal"), "默认 normal 开启: " + sw.get("key"));
            assertEquals(Boolean.TRUE, sw.get("vip"), "默认 vip 开启: " + sw.get("key"));
            assertEquals(Boolean.TRUE, sw.get("svp"), "默认 svp 开启: " + sw.get("key"));
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

        List<Map<String, Object>> switches = s.listSwitches();
        assertFalse(switches.isEmpty());
        assertEquals(Boolean.TRUE, switches.get(0).get("normal"));
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
    void userStatusBlockedWhenUserLevelSwitchOffAndHigherLevelOn() {
        // workflow 对 normal 关闭，对 vip/svp 开放
        String json = "{\"features\":{\"workflow\":{\"normal\":false,\"vip\":true,\"svp\":true}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("normal"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> blocked = (Map<String, Map<String, Object>>) status.get("blocked");

        assertFalse(accessible.get("workflow"));
        Map<String, Object> info = blocked.get("workflow");
        assertNotNull(info);
        assertEquals("level", info.get("reason"));
        assertEquals("vip", info.get("required_level"));
    }

    @Test
    void userStatusAccessibleWhenUserLevelSwitchOn() {
        // workflow 对 normal 关闭，对 vip/svp 开放
        String json = "{\"features\":{\"workflow\":{\"normal\":false,\"vip\":true,\"svp\":true}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("vip"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");

        assertTrue(accessible.get("workflow"));
    }

    @Test
    void userStatusBlockedDisabledWhenAllLevelsOff() {
        // 所有级别都关闭
        String json = "{\"features\":{\"workflow\":{\"normal\":false,\"vip\":false,\"svp\":false}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("normal"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> blocked = (Map<String, Map<String, Object>>) status.get("blocked");

        assertFalse(accessible.get("workflow"));
        Map<String, Object> info = blocked.get("workflow");
        assertNotNull(info);
        assertEquals("disabled", info.get("reason"));
    }

    @Test
    void userStatusBlockedDisabledForAllUserLevelsWhenAllOff() {
        // 所有级别都关闭，vip 用户也应被 disabled
        String json = "{\"features\":{\"workflow\":{\"normal\":false,\"vip\":false,\"svp\":false}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("vip"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> blocked = (Map<String, Map<String, Object>>) status.get("blocked");

        assertFalse(accessible.get("workflow"));
        assertEquals("disabled", blocked.get("workflow").get("reason"));
    }

    @Test
    void userStatusVipUserBlockedWhenVipOffButSvpOn() {
        // vip 关闭，svp 开启 → vip 用户被拦截，提示升级到 svp
        String json = "{\"features\":{\"workflow\":{\"normal\":false,\"vip\":false,\"svp\":true}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("vip"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> blocked = (Map<String, Map<String, Object>>) status.get("blocked");

        assertFalse(accessible.get("workflow"));
        Map<String, Object> info = blocked.get("workflow");
        assertEquals("level", info.get("reason"));
        assertEquals("svp", info.get("required_level"));
    }

    @Test
    void userStatusSvpUserAlwaysAccessibleWhenAnyLevelOn() {
        // svp 用户：只要 svp 开关为 true 就可访问
        String json = "{\"features\":{\"workflow\":{\"normal\":false,\"vip\":false,\"svp\":true}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("svp"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");

        assertTrue(accessible.get("workflow"));
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

    @Test
    void userStatusAcceptsSvipAliasAsSvp() {
        // svip 应等同于 svp
        String json = "{\"features\":{\"workflow\":{\"normal\":false,\"vip\":false,\"svp\":true}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("svip"));

        Map<String, Object> status = s.getStatusForCurrentUser(1L);
        @SuppressWarnings("unchecked")
        Map<String, Boolean> accessible = (Map<String, Boolean>) status.get("accessible");

        assertTrue(accessible.get("workflow"), "svip 用户应等同于 svp，可访问 svp 开启的功能");
    }

    // ===================== 保存配置 =====================

    @Test
    void saveConfigZeroAffectedThrowsConflict() {
        JdbcTemplate jdbc = mockJdbcWithConfig("{}");
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(0);

        FeatureSwitchService s = new FeatureSwitchService(jdbc, mockUserProfile("normal"));
        List<Map<String, Object>> features = List.of(
                Map.of("key", "workflow", "normal", false, "vip", true, "svp", true));

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
                Map.of("key", "workflow", "normal", false, "vip", true, "svp", true));

        s.saveConfig(features);
        verify(jdbc, times(1)).update(contains("INSERT INTO admin_module_record"), any(Object[].class));
    }

    @Test
    void saveConfigUpdatesWhenRecordPresent() {
        JdbcTemplate jdbc = mockJdbcWithConfig("{}");
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);

        FeatureSwitchService s = new FeatureSwitchService(jdbc, mockUserProfile("normal"));
        List<Map<String, Object>> features = List.of(
                Map.of("key", "workflow", "normal", false, "vip", true, "svp", true));

        s.saveConfig(features);
        verify(jdbc, times(1)).update(contains("UPDATE admin_module_record"), any(Object[].class));
    }

    @Test
    void listSwitchesMergesStoredOverrideWithDefaults() {
        // 存储中关闭 workflow 的 normal 开关
        String json = "{\"features\":{\"workflow\":{\"normal\":false,\"vip\":true,\"svp\":true}}}";
        FeatureSwitchService s = new FeatureSwitchService(mockJdbcWithConfig(json), mockUserProfile("normal"));

        List<Map<String, Object>> switches = s.listSwitches();
        Map<String, Object> workflowSwitch = switches.stream()
                .filter(sw -> "workflow".equals(sw.get("key")))
                .findFirst().orElseThrow();
        assertEquals(false, workflowSwitch.get("normal"));
        assertEquals(true, workflowSwitch.get("vip"));
        assertEquals(true, workflowSwitch.get("svp"));
        // 其他功能应保持默认全开
        Map<String, Object> dashboardSwitch = switches.stream()
                .filter(sw -> "dashboard".equals(sw.get("key")))
                .findFirst().orElseThrow();
        assertEquals(true, dashboardSwitch.get("normal"));
        assertEquals(true, dashboardSwitch.get("vip"));
        assertEquals(true, dashboardSwitch.get("svp"));
    }

    // ===================== 等级判定（向后兼容） =====================

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
        assertTrue(s.levelSatisfied("svip", "svp"));
        assertTrue(s.levelSatisfied("svp", "svip"));
    }
}
