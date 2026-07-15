package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.CardService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

class CardControllerSecurityTest {
    private CardService cardService;
    private CardController controller;

    @BeforeEach
    void setUp() {
        cardService = mock(CardService.class);
        controller = new CardController(cardService);
        TenantContext.setCurrentTenantId(7L);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void batchImportSupportsSeparateCardAndPasswordFields() {
        Result<Map<String, Object>> result = controller.batchCreateItems(
                9L,
                new CardController.BatchImportReq(List.of(
                        new CardController.BatchItemReq(null, "CARD-001", "secret")
                ))
        );

        assertEquals(1, result.getData().get("successCount"));
        verify(cardService).createItem(7L, 9L, "CARD-001----secret");
    }

    @Test
    void batchImportRejectsResourceExhaustionBeforeDatabaseWork() {
        List<CardController.BatchItemReq> items = Collections.nCopies(
                1_001,
                new CardController.BatchItemReq("value", null, null)
        );

        BizException error = assertThrows(BizException.class, () ->
                controller.batchCreateItems(9L, new CardController.BatchImportReq(items)));

        assertEquals(413, error.getCode());
        verifyNoInteractions(cardService);
    }
}
