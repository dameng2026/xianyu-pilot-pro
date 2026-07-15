package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuAccountAvailabilityProbeServiceTest {

    @Mock
    private XianyuApiProbeClient probeClient;

    @Test
    void probeReturnsFailureWhenPageHeadFails() {
        when(probeClient.callPageHead("cookie", "uid-88")).thenReturn(null);

        XianyuAccountAvailabilityProbeService service = new XianyuAccountAvailabilityProbeService(probeClient);

        AccountAuthProbeResult result = service.probe("cookie", "uid-88");

        assertFalse(result.isAlive());
        assertEquals("PAGE_HEAD_FAILED", result.getCode());
        assertEquals("登录已失效，请重新登录闲鱼账号", result.getMessage());
    }

    @Test
    void probeReturnsOkWhenPageHeadSucceeds() {
        // page.head 成功即足以证明账号登录态正常，不再额外调用 probeWebSocketToken
        when(probeClient.callPageHead("cookie", "uid-88"))
                .thenReturn(Map.of("nick", "demo"));

        XianyuAccountAvailabilityProbeService service = new XianyuAccountAvailabilityProbeService(probeClient);

        AccountAuthProbeResult result = service.probe("cookie", "uid-88");

        assertTrue(result.isAlive());
    }
}
