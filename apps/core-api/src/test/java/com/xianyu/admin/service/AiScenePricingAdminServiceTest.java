package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AiScenePricingAdminServiceTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @SuppressWarnings("unchecked")
    @Test
    void normalizeScenePayloadShouldTrimAndDefaultFields() throws Exception {
        AiScenePricingAdminService service = new AiScenePricingAdminService(jdbcTemplate);
        Method method = AiScenePricingAdminService.class.getDeclaredMethod("normalizeScenePayload", Map.class, Map.class);
        method.setAccessible(true);

        Map<String, Object> normalized = (Map<String, Object>) method.invoke(service, new LinkedHashMap<>(Map.of(
                "sceneKey", " workflow_rewrite ",
                "sceneName", " AI改写 ",
                "sceneGroup", " rewrite ",
                "chargeMode", " fixed_per_call ",
                "sellTokensPerCall", "30"
        )), null);

        assertEquals("workflow_rewrite", normalized.get("sceneKey"));
        assertEquals("AI改写", normalized.get("sceneName"));
        assertEquals("rewrite", normalized.get("sceneGroup"));
        assertEquals("fixed_per_call", normalized.get("chargeMode"));
        assertEquals(30L, normalized.get("sellTokensPerCall"));
        assertEquals(1, normalized.get("enabled"));
    }

    @Test
    void pageBenefitsShouldNormalizePlanCodeInResults() {
        AiScenePricingAdminService service = new AiScenePricingAdminService(jdbcTemplate);
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), eq("%rewrite%"), eq("%rewrite%"))).thenReturn(1L);
        when(jdbcTemplate.query(anyString(), any(RowMapper.class), eq("%rewrite%"), eq("%rewrite%"), eq(20), eq(0)))
                .thenReturn(List.of(new LinkedHashMap<>(Map.of(
                        "id", 1L,
                        "sceneKey", "workflow_rewrite",
                        "planCode", "svip",
                        "enabled", 1
                ))));

        Map<String, Object> page = new LinkedHashMap<>();
        page.put("records", service.pageBenefits(1, 20, "rewrite", null).getRecords());

        @SuppressWarnings("unchecked")
        Map<String, Object> row = ((List<Map<String, Object>>) page.get("records")).get(0);
        assertEquals("svp", row.get("planCode"));
    }
}
