package com.xianyu.admin.controller;

import com.xianyu.admin.mapper.OperationLogMapper;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OperationLogControllerTenantIsolationTest {

    @AfterEach
    void clearContexts() {
        UserContext.clear();
        TenantContext.clear();
    }

    @Test
    void ordinaryUserLogQueryIsBoundToBothTenantAndUser() {
        OperationLogMapper mapper = mock(OperationLogMapper.class);
        when(mapper.listFiltered(11L, 7L, null, null, null, null, 0, 20))
                .thenReturn(List.of());
        TenantContext.setCurrentTenantId(11L);
        UserContext.set(7L, "alice", 11L);
        OperationLogController controller = new OperationLogController(mapper);

        controller.page(null, null, null, null, 1, 20);

        verify(mapper).countFiltered(11L, 7L, null, null, null, null);
        verify(mapper).listFiltered(11L, 7L, null, null, null, null, 0, 20);
    }

    @Test
    void administratorQueryRetainsPlatformWideViewWithoutUserFilter() {
        OperationLogMapper mapper = mock(OperationLogMapper.class);
        when(mapper.listFiltered(null, null, null, null, null, null, 0, 20))
                .thenReturn(List.of());
        OperationLogController controller = new OperationLogController(mapper);

        controller.page(null, null, null, null, 1, 20);

        verify(mapper).countFiltered(null, null, null, null, null, null);
        verify(mapper).listFiltered(null, null, null, null, null, null, 0, 20);
    }
}
