package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;

class BusinessSettingsServiceTest {

    @SuppressWarnings("unchecked")
    @Test
    void legacyAiCustomerServiceDefaultsShouldUpgradeToNewCopy() throws Exception {
        BusinessSettingsService service = new BusinessSettingsService(mock(JdbcTemplate.class));

        Method defaultConfig = BusinessSettingsService.class.getDeclaredMethod("defaultConfig", String.class);
        defaultConfig.setAccessible(true);
        Map<String, Object> defaults = (Map<String, Object>) defaultConfig.invoke(service, "ai-customer-service");

        Map<String, Object> saved = new LinkedHashMap<>();
        saved.put("systemPrompt",
                "你是闲鱼店铺的专业客服助手，请用友好、专业、简洁的语气回答买家问题。\n" +
                "【身份定位】你是本店的AI客服，熟悉店铺所有商品的详情、价格、规格与售后政策。");
        saved.put("welcomeMessage", "您好~欢迎光临本店！我是AI客服小鱼，有什么可以帮您？商品拍下后48小时内发货，有任何问题随时问我哦~");

        Method mergeWithDefaults = BusinessSettingsService.class.getDeclaredMethod("mergeWithDefaults", String.class, Map.class, Map.class);
        mergeWithDefaults.setAccessible(true);
        Map<String, Object> merged = (Map<String, Object>) mergeWithDefaults.invoke(service, "ai-customer-service", saved, defaults);

        String systemPrompt = String.valueOf(merged.get("systemPrompt"));
        String welcomeMessage = String.valueOf(merged.get("welcomeMessage"));

        assertTrue(systemPrompt.contains("禁止编造"));
        assertTrue(systemPrompt.contains("信息优先级"));
        assertTrue(welcomeMessage.contains("欢迎咨询"));
        assertTrue(welcomeMessage.contains("转人工客服核实"));
        assertEquals(defaults.get("systemPrompt"), systemPrompt);
        assertEquals(defaults.get("welcomeMessage"), welcomeMessage);
    }
}
