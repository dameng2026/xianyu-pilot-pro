package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.service.AiProviderService;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.BusinessSettingsService;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.mock.web.MockMultipartFile;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

class BusinessSettingsControllerKnowledgeUploadTest {

    @ParameterizedTest
    @ValueSource(strings = {"rules.xls", "rules.ppt", "rules.docx", "rules.exe"})
    void rejectsFormatsThatThePinnedKnowledgeParsersCannotProcess(String filename) {
        AutomationClient automationClient = mock(AutomationClient.class);
        BusinessSettingsController controller = new BusinessSettingsController(
                mock(BusinessSettingsService.class),
                mock(AiProviderService.class),
                automationClient
        );
        MockMultipartFile file = new MockMultipartFile(
                "file", filename, "application/octet-stream", new byte[]{1, 2, 3});

        BizException error = assertThrows(BizException.class, () -> controller.uploadKnowledge(file));

        assertEquals(400, error.getCode());
        verifyNoInteractions(automationClient);
    }
}
