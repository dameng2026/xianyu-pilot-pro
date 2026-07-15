package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PublishAddressControllerTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    private PublishAddressController controller;

    @BeforeEach
    void setUp() {
        controller = new PublishAddressController(jdbcTemplate);
        TenantContext.setCurrentTenantId(1L);
        TenantContext.setCurrentUserId(2L);
        UserContext.set(2L, "tester", 1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
        UserContext.clear();
    }

    @Test
    void historyKeepsLegacyAddressesAndMarksWhetherTheyAreComplete() {
        when(jdbcTemplate.queryForList(anyString(), eq(1L), eq(2L))).thenReturn(List.of(
                row(1L, "中原区", "郑州市", "中原区", "", "", "", ""),
                row(11L, "中原工学院中原校区", "郑州市", "中原区", "河南省", "410102", "113.615291,34.749122", "B0173072GH")
        ));

        Result<List<Map<String, Object>>> result = controller.history();

        assertEquals(200, result.getCode());
        assertNotNull(result.getData());
        assertEquals(2, result.getData().size());
        assertEquals(1L, result.getData().get(0).get("id"));
        assertEquals(false, result.getData().get(0).get("complete"));
        assertEquals(11L, result.getData().get(1).get("id"));
        assertEquals("410102", result.getData().get(1).get("divisionId"));
        assertEquals(true, result.getData().get(1).get("complete"));
    }

    @Test
    void saveRejectsAddressWhenRequiredFieldsAreMissing() {
        BizException error = assertThrows(BizException.class, () -> controller.save(new LinkedHashMap<>(Map.of(
                "poiName", "中原工学院中原校区",
                "prov", "河南省",
                "city", "郑州市",
                "area", "中原区",
                "gps", "113.615291,34.749122",
                "poiId", "B0173072GH"
        ))));

        assertEquals(400, error.getCode());
        assertTrue(error.getMessage().contains("divisionId"));
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void historyReportsDatabaseFailureAsSafeServiceUnavailable() {
        when(jdbcTemplate.queryForList(anyString(), eq(1L), eq(2L)))
                .thenThrow(new RuntimeException("jdbc:secret-host"));

        BizException error = assertThrows(BizException.class, controller::history);

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("secret-host"));
    }

    @Test
    void saveReportsDatabaseFailureWithoutLeakingDriverDetails() {
        when(jdbcTemplate.update(
                anyString(),
                eq(1L), eq(2L), eq("中原工学院中原校区"), eq("郑州市"), eq("中原区"),
                eq("河南省"), eq("410102"), eq("113.615291,34.749122"), eq("B0173072GH"), eq("")
        )).thenThrow(new RuntimeException("password=top-secret"));

        BizException error = assertThrows(BizException.class, () -> controller.save(validAddress()));

        assertEquals(503, error.getCode());
        assertFalse(error.getMessage().contains("top-secret"));
    }

    @Test
    void missingUserContextIsAnAuthenticationFailure() {
        UserContext.clear();

        BizException error = assertThrows(BizException.class, controller::history);

        assertEquals(401, error.getCode());
        verifyNoInteractions(jdbcTemplate);
    }

    private static Map<String, Object> validAddress() {
        return new LinkedHashMap<>(Map.of(
                "poiName", "中原工学院中原校区",
                "prov", "河南省",
                "city", "郑州市",
                "area", "中原区",
                "divisionId", "410102",
                "gps", "113.615291,34.749122",
                "poiId", "B0173072GH"
        ));
    }

    private static Map<String, Object> row(Long id, String poiName, String city, String area,
                                           String prov, String divisionId, String gps, String poiId) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", id);
        row.put("poiName", poiName);
        row.put("city", city);
        row.put("area", area);
        row.put("prov", prov);
        row.put("divisionId", divisionId);
        row.put("gps", gps);
        row.put("poiId", poiId);
        row.put("detail", poiName);
        row.put("useCount", 1);
        return row;
    }
}
