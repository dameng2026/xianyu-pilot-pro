package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class XianyuApiUtilsTest {

    @Test
    void pageHeadPayloadShouldMatchObservedWebRequestShape() throws Exception {
        Method method = XianyuApiUtils.class.getDeclaredMethod("buildPageHeadDataJson", String.class);
        method.setAccessible(true);

        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) method.invoke(null, "2220042556983");

        assertEquals(Boolean.FALSE, payload.get("self"));
        assertEquals("2220042556983", payload.get("userId"));
    }
}
