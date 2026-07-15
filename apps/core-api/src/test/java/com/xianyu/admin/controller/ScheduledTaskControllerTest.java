package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AutomationClient;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ScheduledTaskControllerTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private AutomationClient automationClient;

    private ScheduledTaskController controller;

    @BeforeEach
    void setUp() {
        controller = new ScheduledTaskController(jdbcTemplate, automationClient);
        TenantContext.setCurrentTenantId(1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void createShouldRejectUnsupportedTaskType() {
        Result<Void> result = controller.create(Map.of(
                "taskName", "bad-task",
                "taskType", "not_supported",
                "cronExpression", "0 0/15 * * * ?",
                "configJson", "{\"recordId\":900}",
                "enabled", 1
        ));

        assertEquals(422, result.getCode());
        assertEquals("暂不支持该定时任务类型", result.getMsg());
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void failedManualRunMustNotRecordAFakeLastRunTimeOrExposeDetails() {
        when(jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM scheduled_task WHERE id=? AND tenant_id=? AND deleted=0",
                Integer.class,
                77L,
                1L
        )).thenReturn(1);
        when(automationClient.postInternalForData(anyString(), any()))
                .thenThrow(new RuntimeException("internal automation host details"));

        BizException error = assertThrows(BizException.class, () -> controller.run(77L));

        assertEquals(503, error.getCode());
        assertEquals("自动化服务暂时不可用，任务未确认执行，请稍后重试", error.getMessage());
        verify(jdbcTemplate).queryForObject(
                "SELECT COUNT(*) FROM scheduled_task WHERE id=? AND tenant_id=? AND deleted=0",
                Integer.class,
                77L,
                1L
        );
    }

    @Test
    void createRejectsAnAccountOwnedByAnotherTenant() {
        when(jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM xianyu_account WHERE id=? AND tenant_id=? AND deleted=0",
                Integer.class,
                99L,
                1L
        )).thenReturn(0);

        BizException error = assertThrows(BizException.class, () -> controller.create(Map.of(
                "taskName", "sync",
                "taskType", "sync_goods",
                "accountId", 99,
                "configJson", "{}"
        )));

        assertEquals(404, error.getCode());
        verify(jdbcTemplate, never()).update(anyString(), any(Object[].class));
        verifyNoInteractions(automationClient);
    }

    @Test
    void createRejectsNonObjectOrOversizedTaskConfiguration() {
        BizException nonObject = assertThrows(BizException.class, () -> controller.create(Map.of(
                "taskType", "workflow",
                "configJson", "[]"
        )));
        assertEquals(400, nonObject.getCode());

        String oversized = "{\"value\":\"" + "x".repeat(33 * 1024) + "\"}";
        BizException tooLarge = assertThrows(BizException.class, () -> controller.create(Map.of(
                "taskType", "workflow",
                "configJson", oversized
        )));
        assertEquals(413, tooLarge.getCode());
        verifyNoInteractions(jdbcTemplate, automationClient);
    }

    @Test
    void updateReportsMissingTaskInsteadOfFakeSuccess() {
        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(0);

        BizException error = assertThrows(BizException.class, () -> controller.update(77L, Map.of(
                "taskType", "workflow",
                "configJson", "{}",
                "enabled", true
        )));

        assertEquals(404, error.getCode());
    }
}
