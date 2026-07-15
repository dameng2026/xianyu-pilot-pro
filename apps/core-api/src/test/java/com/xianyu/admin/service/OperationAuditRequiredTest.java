package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.mapper.OperationLogMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.lang.reflect.Method;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OperationAuditRequiredTest {

    @Test
    void requiredAuditFailsClosedWhenPersistenceFails() {
        OperationLogMapper mapper = mock(OperationLogMapper.class);
        when(mapper.insert(any())).thenThrow(new IllegalStateException("audit database unavailable"));
        OperationAuditService service = new OperationAuditService(mapper);

        BizException error = assertThrows(BizException.class, () -> service.recordRequired(
                3L, 9L, "USER_DELETE", "delete user", "sys_user", 17L, null));

        assertEquals(503, error.getCode());
    }

    @Test
    void statusMutationPropagatesRequiredAuditFailure() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        OperationAuditService audit = mock(OperationAuditService.class);
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);
        when(audit.recordRequired(any(), any(), anyString(), anyString(), anyString(), anyLong(), any()))
                .thenThrow(new BizException(503, "audit unavailable"));
        SysUserService service = new SysUserService(jdbc, audit);

        BizException error = assertThrows(BizException.class, () -> service.updateStatus(17L, 0));

        assertEquals(503, error.getCode());
        verify(audit).recordRequired(any(), any(), anyString(), anyString(), anyString(), anyLong(), any());
    }

    @Test
    void everyHighRiskMutationHasATransactionBoundary() throws Exception {
        for (Method method : List.of(
                SysUserService.class.getMethod("resetPassword", long.class, String.class),
                SysUserService.class.getMethod("update", long.class, java.util.Map.class),
                SysUserService.class.getMethod("delete", long.class),
                SysUserService.class.getMethod("batchDelete", List.class),
                SysUserService.class.getMethod("updateStatus", long.class, int.class),
                SysUserService.class.getMethod("batchUpdateStatus", List.class, int.class),
                SysUserService.class.getMethod("updateTokenBalance", long.class, long.class),
                SysUserService.class.getMethod("updateVipLevel", long.class, int.class))) {
            assertNotNull(method.getAnnotation(Transactional.class), method.getName());
        }
    }
}
