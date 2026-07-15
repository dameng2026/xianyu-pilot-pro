package com.xianyu.admin.service;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.security.TenantContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.lang.reflect.Field;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class WorkflowServiceTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private AutomationClient automationClient;

    @Mock
    private WorkflowAccountValidationService workflowAccountValidationService;

    @Mock
    private WorkflowAddressValidationService workflowAddressValidationService;

    private WorkflowService service;

    @BeforeEach
    void setUp() throws Exception {
        TenantContext.setCurrentTenantId(1L);
        TenantContext.setCurrentUserId(2L);
        service = new WorkflowService(
                jdbcTemplate,
                automationClient,
                workflowAccountValidationService,
                workflowAddressValidationService
        );

        Field avgAtField = WorkflowService.class.getDeclaredField("cachedAvgItemTimingAtMs");
        avgAtField.setAccessible(true);
        avgAtField.setLong(service, System.currentTimeMillis());
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void listExecutionsShouldAliasInnerWorkflowExecutionSubquery() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class), any(Object[].class))).thenReturn(1L);

        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 101L);
        row.put("execution_no", "WF202607091010000001");
        row.put("workflow_id", 7L);
        row.put("workflow_name", "测试工作流");
        row.put("trigger_mode", "manual");
        row.put("status", "success");
        row.put("progress", 100);
        row.put("node_total", 1);
        row.put("node_success", 1);
        row.put("error_message", "");
        row.put("created_time", "2026-07-09 10:10:00");
        row.put("started_time", "2026-07-09 10:10:00");
        row.put("finished_time", "2026-07-09 10:10:05");
        row.put("duration_ms", 5000);

        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(List.of(row));

        PageResult<Map<String, Object>> result = service.listExecutions(null, "", null, 1, 20);

        ArgumentCaptor<String> sqlCaptor = ArgumentCaptor.forClass(String.class);
        verify(jdbcTemplate).queryForList(sqlCaptor.capture(), any(Object[].class));

        String sql = sqlCaptor.getValue();
        assertTrue(
                sql.contains("SELECT id FROM workflow_execution e"),
                "inner execution paging subquery must alias workflow_execution as e so the shared WHERE clause stays valid"
        );
        assertEquals(1, result.getRecords().size());
        assertEquals("测试工作流", result.getRecords().get(0).get("workflowName"));
    }

    @Test
    void continueExecutionMustNotExposeAutomationExceptionDetails() {
        Map<String, Object> execution = new LinkedHashMap<>();
        execution.put("id", 88L);
        execution.put("workflow_id", 7L);
        execution.put("status", "failed");
        execution.put("input_json", """
                {
                  "addressPayload": {
                    "poiName": "测试地点",
                    "prov": "浙江省",
                    "city": "杭州市",
                    "area": "余杭区",
                    "divisionId": "330110",
                    "gps": "120.1,30.2",
                    "poiId": "poi-1"
                  }
                }
                """);

        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(List.of(execution));
        when(workflowAddressValidationService.validateExecutionAddress(any())).thenReturn(Map.of("ok", true));
        when(workflowAccountValidationService.validateExecutionAccounts(eq(1L), any(), any())).thenReturn(List.of());
        when(automationClient.postInternalForData(anyString(), anyMap(), anyLong()))
                .thenThrow(new RuntimeException("internal host and credential details"));

        Map<String, Object> result = service.continueExecution(88L);

        assertEquals(false, result.get("ok"));
        assertEquals("自动化服务暂时不可用，未能确认继续执行，请稍后重试", result.get("message"));
        assertFalse(String.valueOf(result.get("message")).contains("credential"));
        verify(automationClient).postInternalForData(anyString(), anyMap(), anyLong());
    }
}
