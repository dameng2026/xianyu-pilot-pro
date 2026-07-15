package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.service.AiProviderService;
import org.junit.jupiter.api.Test;
import org.springframework.web.bind.annotation.PostMapping;

import java.lang.reflect.Method;
import java.util.Collections;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiProviderControllerSecurityTest {

    @Test
    void arbitraryProviderTestIsNotExposedToOrdinaryUsers() throws Exception {
        Method method = AiProviderController.class.getDeclaredMethod("test", Map.class);

        assertArrayEquals(
                new String[]{"/admin-api/ai-provider/test"},
                method.getAnnotation(PostMapping.class).value()
        );
    }

    @Test
    void categorySuggestionUsesTheBillablePath() {
        AiProviderService service = mock(AiProviderService.class);
        when(service.isConfigured()).thenReturn(true);
        when(service.generateText(
                eq("category_suggest"), anyString(), anyString(), eq(0.1D), eq(true)
        )).thenReturn(Map.of("ok", true, "content", "{\"index\":1}"));
        AiProviderController controller = new AiProviderController(service);

        controller.suggestCategory(Map.of(
                "title", "phone",
                "description", "used phone",
                "categories", List.of(Map.of(
                        "id", 1,
                        "name", "phone",
                        "path", "electronics/phone",
                        "pathIds", List.of(1)
                ))
        ));

        verify(service).generateText(
                eq("category_suggest"), anyString(), anyString(), eq(0.1D), eq(true)
        );
    }

    @Test
    void categorySuggestionDoesNotHideInsufficientBalanceAsDegradedSuccess() {
        AiProviderService service = mock(AiProviderService.class);
        when(service.isConfigured()).thenReturn(true);
        when(service.generateText(
                eq("category_suggest"), anyString(), anyString(), eq(0.1D), eq(true)
        )).thenThrow(new BizException(402, "insufficient balance"));
        AiProviderController controller = new AiProviderController(service);

        BizException error = assertThrows(BizException.class, () ->
                controller.suggestCategory(Map.of(
                        "title", "phone",
                        "categories", List.of(Map.of(
                                "id", 1,
                                "name", "phone",
                                "path", "electronics/phone"
                        ))
                )));

        assertEquals(402, error.getCode());
    }

    @Test
    void categorySuggestionRejectsUnboundedCandidateCollections() {
        AiProviderService service = mock(AiProviderService.class);
        when(service.isConfigured()).thenReturn(true);
        AiProviderController controller = new AiProviderController(service);
        List<Map<String, Object>> categories = Collections.nCopies(
                10_001,
                Map.of("id", 1, "name", "phone", "path", "phone")
        );

        BizException error = assertThrows(BizException.class, () ->
                controller.suggestCategory(Map.of("categories", categories)));

        assertEquals(413, error.getCode());
        verify(service, never()).generateText(anyString(), anyString(), anyString(), eq(0.1D), eq(true));
    }

    @Test
    void categorySuggestionRejectsNullPathIdentifiersAsBadInput() {
        AiProviderService service = mock(AiProviderService.class);
        when(service.isConfigured()).thenReturn(true);
        AiProviderController controller = new AiProviderController(service);
        List<Object> pathIds = new ArrayList<>();
        pathIds.add(1);
        pathIds.add(null);

        BizException error = assertThrows(BizException.class, () ->
                controller.suggestCategory(Map.of(
                        "categories", List.of(Map.of(
                                "id", 1,
                                "name", "phone",
                                "path", "electronics/phone",
                                "pathIds", pathIds
                        ))
                )));

        assertEquals(400, error.getCode());
        verify(service, never()).generateText(anyString(), anyString(), anyString(), eq(0.1D), eq(true));
    }
}
