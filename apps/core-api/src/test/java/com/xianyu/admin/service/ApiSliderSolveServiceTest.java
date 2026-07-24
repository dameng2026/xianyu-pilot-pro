package com.xianyu.admin.service;

import com.xianyu.admin.mapper.ApiSliderSolveRecordMapper;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ApiSliderSolveServiceTest {

    @Test
    void resolvesTenantMainUserInsteadOfTreatingTenantIdAsUserId() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), eq(11L))).thenReturn(List.of(Map.of("id", 77L)));
        ApiSliderSolveService service = new ApiSliderSolveService(
                jdbc,
                mock(ApiSliderSolveRecordMapper.class),
                mock(StringRedisTemplate.class),
                mock(PlatformTransactionManager.class)
        );

        assertEquals(77L, service.resolveTenantUserId(11L));
    }
}
