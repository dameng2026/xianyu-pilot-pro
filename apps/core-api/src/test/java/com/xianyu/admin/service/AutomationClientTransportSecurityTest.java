package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AutomationClientTransportSecurityTest {

    @Test
    void preservesLegitimatePublicContentUploadNames() {
        assertEquals("open-content.webp",
                AutomationClient.sanitizeMultipartFileName("open-content.webp"));
        assertEquals("carousel.png",
                AutomationClient.sanitizeMultipartFileName("carousel.png"));
    }

    @Test
    void stripsPathsAndHeaderControlCharactersFromMultipartFileName() {
        String sanitized = AutomationClient.sanitizeMultipartFileName(
                "../../evil\r\nX-Injected: yes.png");

        assertFalse(sanitized.contains("/"));
        assertFalse(sanitized.contains("\\"));
        assertFalse(sanitized.contains("\r"));
        assertFalse(sanitized.contains("\n"));
        assertTrue(sanitized.endsWith(".png"));
    }

    @Test
    void rejectsUploadStreamsThatExceedTheHardLimit() {
        BizException error = assertThrows(BizException.class, () ->
                AutomationClient.readBounded(
                        new ByteArrayInputStream(new byte[1_025]),
                        1_024,
                        "too large"
                ));

        assertEquals(413, error.getCode());
    }

    @Test
    void rejectsOversizedDependencyResponsesBeforeJsonParsing() {
        BizException error = assertThrows(BizException.class, () ->
                AutomationClient.readResponseText(
                        new ByteArrayInputStream(new byte[9]),
                        8
                ));

        assertEquals(502, error.getCode());
    }
}
