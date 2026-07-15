package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeliveryGoodsConfigServiceTest {
    @Mock
    private JdbcTemplate jdbcTemplate;

    private DeliveryGoodsConfigService service;

    @BeforeEach
    void setUp() {
        service = new DeliveryGoodsConfigService(jdbcTemplate, new ObjectMapper());
    }

    @Test
    void rejectsUnavailableApiModeBeforeReadingOrWritingTheDatabase() {
        BizException error = assertThrows(BizException.class, () -> service.apply(
                1L,
                List.of(11L),
                Map.of("timing", "payDelivery", "enabled", 1, "mode", "api")
        ));

        assertEquals(422, error.getCode());
        assertEquals("API 发货模式暂不可用，请改用文本或卡密发货", error.getMessage());
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void rejectsTheWholeBatchWhenAnyGoodsIsOutsideTheTenant() {
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(List.of(
                Map.of("id", 11L, "account_id", 7L)
        ));

        BizException error = assertThrows(BizException.class, () -> service.apply(
                1L,
                List.of(11L, 12L),
                Map.of("timing", "payDelivery", "enabled", 0, "mode", "text")
        ));

        assertEquals(404, error.getCode());
        assertEquals("部分商品不存在或不属于当前租户，未执行配置变更", error.getMessage());
        verify(jdbcTemplate, never()).update(anyString(), any(Object[].class));
    }

    @Test
    void corruptExistingJsonIsNotSilentlyOverwritten() {
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenAnswer(invocation -> {
            String sql = invocation.getArgument(0);
            if (sql.contains("FROM xianyu_goods")) {
                return List.of(Map.of("id", 11L, "account_id", 7L));
            }
            return List.of(Map.of("id", 99L, "config_json", "{broken-json"));
        });

        BizException error = assertThrows(BizException.class, () -> service.apply(
                1L,
                List.of(11L),
                Map.of("timing", "payDelivery", "enabled", 0, "mode", "text")
        ));

        assertEquals(409, error.getCode());
        assertEquals("现有商品发货配置已损坏，已阻止覆盖，请联系管理员修复", error.getMessage());
        verify(jdbcTemplate, never()).update(anyString(), any(Object[].class));
    }

    @Test
    void savesAValidatedTextConfigurationWithTheActualGoodsAccount() throws Exception {
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenAnswer(invocation -> {
            String sql = invocation.getArgument(0);
            if (sql.contains("FROM xianyu_goods")) {
                return List.of(Map.of("id", 11L, "account_id", 7L));
            }
            return List.of();
        });
        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);

        int changed = service.apply(
                1L,
                List.of(11L),
                Map.of(
                        "timing", "payDelivery",
                        "enabled", 1,
                        "mode", "text",
                        "content", "感谢购买，这是发货正文"
                )
        );

        assertEquals(1, changed);
        ArgumentCaptor<Object[]> args = ArgumentCaptor.forClass(Object[].class);
        verify(jdbcTemplate).update(anyString(), args.capture());
        Object[] inserted = args.getValue();
        assertEquals(1L, inserted[0]);
        assertEquals(11L, inserted[1]);
        @SuppressWarnings("unchecked")
        Map<String, Object> json = new ObjectMapper().readValue(String.valueOf(inserted[2]), LinkedHashMap.class);
        assertEquals(7, ((Number) json.get("accountId")).intValue());
        @SuppressWarnings("unchecked")
        Map<String, Object> payDelivery = (Map<String, Object>) json.get("payDelivery");
        assertEquals("text", payDelivery.get("mode"));
        assertEquals(1, ((Number) payDelivery.get("enabled")).intValue());
        assertEquals("感谢购买，这是发货正文", payDelivery.get("content"));
    }

    @Test
    void databaseFailureReturnsAStableMessageWithoutInternalDetails() {
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class)))
                .thenThrow(new RuntimeException("jdbc://secret-host/schema"));

        BizException error = assertThrows(BizException.class, () -> service.read(1L, 11L));

        assertEquals(503, error.getCode());
        assertEquals("商品状态暂时无法校验，未执行配置变更", error.getMessage());
        assertFalse(error.getMessage().contains("secret-host"));
    }

    @Test
    void everyMutatingInterfaceMethodIsTransactional() throws Exception {
        for (Method method : List.of(
                DeliveryGoodsConfigService.class.getMethod("apply", Long.class, java.util.Collection.class, Map.class),
                DeliveryGoodsConfigService.class.getMethod("applyAll", Long.class, Map.class),
                DeliveryGoodsConfigService.class.getMethod("delete", Long.class, java.util.Collection.class),
                DeliveryGoodsConfigService.class.getMethod("setEnabled", Long.class, Long.class, String.class, Object.class)
        )) {
            assertNotNull(method.getAnnotation(Transactional.class), method.getName() + " must be atomic");
        }
    }
}
