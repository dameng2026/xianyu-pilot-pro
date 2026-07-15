package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.XianyuAccountFeatureService;
import com.xianyu.admin.service.XianyuAccountService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuAccountControllerTest {

    @Mock
    private XianyuAccountService accountService;

    @Mock
    private XianyuAccountFeatureService featureService;

    private XianyuAccountController controller;

    @BeforeEach
    void setUp() {
        controller = new XianyuAccountController(accountService, featureService);
        TenantContext.setCurrentTenantId(1L);
        TenantContext.setCurrentUserId(9L);
        UserContext.set(9L, "tester", 1L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
        UserContext.clear();
    }

    @Test
    void faceVerificationsShouldDelegateWithTenantAndUserContext() {
        PageResult<Map<String, Object>> page = new PageResult<>(
                List.of(Map.of("id", 5L, "accountId", 18L, "title", "人机验证提醒")),
                1,
                10,
                1
        );
        when(featureService.pageFaceVerifications(1L, 9L, 18L, 1, 10)).thenReturn(page);

        Result<PageResult<Map<String, Object>>> result = controller.faceVerifications(18L, 1, 10);

        verify(featureService, times(1)).pageFaceVerifications(1L, 9L, 18L, 1, 10);
        assertNotNull(result.getData());
        assertEquals(1L, result.getData().getTotal());
    }

    @Test
    void saveAutoRateShouldDelegateWithTenantAndUserContext() {
        when(featureService.saveAutoRateConfig(1L, 9L, 18L, Map.of("enabled", true)))
                .thenReturn(Map.of("accountId", 18L, "enabled", true, "rateType", "text"));

        Result<Map<String, Object>> result = controller.saveAutoRate(18L, Map.of("enabled", true));

        verify(featureService, times(1)).saveAutoRateConfig(1L, 9L, 18L, Map.of("enabled", true));
        assertNotNull(result.getData());
        assertEquals(Boolean.TRUE, result.getData().get("enabled"));
    }

    @Test
    void strategyConfigShouldDelegateWithTenantContext() {
        when(featureService.getStrategyConfig(1L, 18L))
                .thenReturn(Map.of("accountId", 18L, "messageExpireTime", 3600, "scheduledRedelivery", false));

        Result<Map<String, Object>> result = controller.strategyConfig(18L);

        verify(featureService, times(1)).getStrategyConfig(1L, 18L);
        assertNotNull(result.getData());
        assertEquals(3600, result.getData().get("messageExpireTime"));
    }

    @Test
    void saveStrategyConfigShouldDelegateWithTenantContext() {
        when(featureService.saveStrategyConfig(1L, 18L, Map.of("messageExpireTime", 7200, "scheduledRedelivery", true)))
                .thenReturn(Map.of("accountId", 18L, "messageExpireTime", 7200, "scheduledRedelivery", true));

        Result<Map<String, Object>> result = controller.saveStrategyConfig(18L, Map.of("messageExpireTime", 7200, "scheduledRedelivery", true));

        verify(featureService, times(1)).saveStrategyConfig(1L, 18L, Map.of("messageExpireTime", 7200, "scheduledRedelivery", true));
        assertNotNull(result.getData());
        assertEquals(Boolean.TRUE, result.getData().get("scheduledRedelivery"));
    }
}
