package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.lang.reflect.Method;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class UserSecurityAuditServiceTest {

    @Test
    void rejectedSecurityAttemptUsesIndependentTransactionAndRequiresOneAuditRow() throws Exception {
        Method method = UserSecurityAuditService.class.getMethod(
                "recordRejectedRequired", Long.class, Long.class, String.class, String.class,
                String.class, String.class, String.class, String.class);
        Transactional transactional = method.getAnnotation(Transactional.class);
        assertEquals(Propagation.REQUIRES_NEW, transactional.propagation());

        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);
        UserSecurityAuditService service = new UserSecurityAuditService(jdbc);

        service.recordRejectedRequired(
                11L, 7L, "change_password", "修改密码", "password", "当前密码错误",
                "203.0.113.8", "test");

        verify(jdbc).update(anyString(), any(Object[].class));
    }
}
