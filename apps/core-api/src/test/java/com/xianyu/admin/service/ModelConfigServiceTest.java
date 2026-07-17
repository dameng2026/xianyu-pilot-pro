package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.dao.DataAccessResourceFailureException;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ModelConfigServiceTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private SensitiveWordService sensitiveWordService;

    @Test
    void matchImagePromptCategoryShouldPreferKeywordHit() {
        ModelConfigService service = new ModelConfigService(jdbcTemplate, sensitiveWordService);

        Map<String, Object> matched = service.matchImagePromptCategory(
                "优酷 svip 会员 7天 周卡 自动发货",
                "支持手机 平板 电视 电脑",
                List.of(
                        promptRecord("会员卡", "会员卡,svip,周卡,自动发货", "prompt-a"),
                        promptRecord("源码", "源码,程序,小程序", "prompt-b")
                )
        );

        assertEquals("会员卡", matched.get("categoryKey"));
        assertEquals("prompt-a", matched.get("promptTemplate"));
    }

    @Test
    void resolveImagePromptShouldUseCategoryTemplateInDefaultMode() {
        ModelConfigService service = new ModelConfigService(jdbcTemplate, sensitiveWordService);

        String prompt = service.resolveImagePrompt(
                "default",
                "",
                "base-default",
                "Steam 激活码 DLC 自动发货",
                "全区可用 秒发",
                List.of(promptRecord("游戏", "Steam,激活码,DLC", "TITLE={{TITLE}}\nCONTENT={{CONTENT}}"))
        );

        assertTrue(prompt.contains("TITLE=Steam 激活码 DLC 自动发货"));
        assertTrue(prompt.contains("CONTENT=全区可用 秒发"));
    }

    @Test
    void resolveImagePromptShouldPreferCustomPromptInCustomMode() {
        ModelConfigService service = new ModelConfigService(jdbcTemplate, sensitiveWordService);

        String prompt = service.resolveImagePrompt(
                "custom",
                "CUSTOM={{TITLE}}",
                "base-default",
                "程序代做",
                "Java Python C++",
                List.of(promptRecord("代做", "代做,程序", "SHOULD_NOT_USE"))
        );

        assertEquals("CUSTOM=程序代做", prompt);
    }

    @Test
    void getImagePromptConfigsShouldSortBySortOrderThenId() {
        ModelConfigService service = new ModelConfigService(jdbcTemplate, sensitiveWordService);

        when(jdbcTemplate.queryForList(anyString(), eq(ModelConfigService.PROMPT))).thenReturn(List.of(
                promptDbRow(8L, "generic_virtual", 999),
                promptDbRow(3L, "video_template", 65),
                promptDbRow(2L, "membership_vip", 10),
                promptDbRow(1L, "game_cdk", 10)
        ));

        List<Map<String, Object>> configs = service.getImagePromptConfigs();

        assertEquals(List.of("game_cdk", "membership_vip", "video_template", "generic_virtual"),
                configs.stream().map(row -> String.valueOf(row.get("categoryKey"))).toList());
    }

    @Test
    void databaseFailureIsUnavailableInsteadOfLookingLikeMissingConfiguration() {
        ModelConfigService service = new ModelConfigService(jdbcTemplate, sensitiveWordService);
        when(jdbcTemplate.queryForList(anyString(), eq(ModelConfigService.GENERAL)))
                .thenThrow(new DataAccessResourceFailureException("database unavailable"));

        BizException error = assertThrows(BizException.class, service::getGeneralConfig);

        assertEquals(503, error.getCode());
    }

    private Map<String, Object> promptRecord(String categoryKey, String matchKeywords, String promptTemplate) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("categoryKey", categoryKey);
        row.put("matchKeywords", matchKeywords);
        row.put("promptTemplate", promptTemplate);
        row.put("enabled", true);
        row.put("status", "正常");
        return row;
    }

    private Map<String, Object> promptDbRow(long id, String categoryKey, int sortOrder) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", id);
        row.put("status", "正常");
        row.put("json_text", "{\"categoryKey\":\"" + categoryKey + "\",\"matchKeywords\":\"" + categoryKey + "\",\"promptTemplate\":\"" + categoryKey + "\",\"enabled\":true,\"sortOrder\":" + sortOrder + "}");
        row.put("updated_time", "2026-07-03 00:00:00");
        return row;
    }
}
