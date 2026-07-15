package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

class AutomationClientBusinessStatusTest {

    @Test
    void dataExtractionRejectsDownstreamBusinessFailure() throws Exception {
        AutomationClient client = new AutomationClient();
        Method method = AutomationClient.class.getDeclaredMethod("dataOrSelf", Map.class);
        method.setAccessible(true);
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("code", 503);
        response.put("msg", "功能当前不可用");
        response.put("data", Map.of("message", "不得被当作成功数据"));

        InvocationTargetException thrown = assertThrows(
                InvocationTargetException.class,
                () -> method.invoke(client, response)
        );

        BizException cause = (BizException) thrown.getCause();
        assertEquals(503, cause.getCode());
        assertEquals("依赖服务暂时不可用，请稍后重试", cause.getMessage());
    }

    @Test
    void dataExtractionStillUnwrapsSuccessfulResponse() throws Exception {
        AutomationClient client = new AutomationClient();
        Method method = AutomationClient.class.getDeclaredMethod("dataOrSelf", Map.class);
        method.setAccessible(true);
        Map<String, Object> data = Map.of("count", 2);
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("code", 200);
        response.put("data", data);

        Object result = method.invoke(client, response);

        assertSame(data, result);
    }

    @Test
    void httpFailurePreservesSafeStatusWithoutLeakingResponseBody() throws Exception {
        AutomationClient client = new AutomationClient();
        Method method = AutomationClient.class.getDeclaredMethod("ensureSuccessStatus", int.class, String.class);
        method.setAccessible(true);

        InvocationTargetException thrown = assertThrows(
                InvocationTargetException.class,
                () -> method.invoke(client, 404, "{\"detail\":\"sql password=secret\"}")
        );

        BizException cause = (BizException) thrown.getCause();
        assertEquals(404, cause.getCode());
        assertEquals("请求的下游资源不存在", cause.getMessage());
    }
}
