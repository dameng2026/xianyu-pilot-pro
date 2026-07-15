package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OpenSourceContentTruthfulnessTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Test
    void missingOptionalConfigurationUsesDocumentedDefaults() {
        when(jdbcTemplate.queryForObject(anyString(), eq(String.class), any(), any()))
                .thenThrow(new EmptyResultDataAccessException(1));

        Map<String, Object> result = new OpenSourceContentService(jdbcTemplate).getAboutContent();

        assertFalse(result.isEmpty());
        assertFalse(result.toString().contains("@xianyu.local"));
        assertFalse(result.toString().contains("https://github.com/"));
        assertTrue(result.toString().contains("尚未配置") || result.toString().contains("待配置"));
    }

    @Test
    void databaseFailureDoesNotMasqueradeAsDefaultContent() {
        when(jdbcTemplate.queryForObject(anyString(), eq(String.class), any(), any()))
                .thenThrow(new DataAccessResourceFailureException("database unavailable"));

        BizException error = assertThrows(BizException.class,
                () -> new OpenSourceContentService(jdbcTemplate).getAboutContent());

        assertEquals(503, error.getCode());
    }

    @Test
    void unsafeLegacyAboutConfigurationIsNeutralizedAndReported() {
        when(jdbcTemplate.queryForObject(anyString(), eq(String.class), any(), any()))
                .thenReturn("""
                        {
                          "heroTitle":"<img src=x onerror=alert(1)>",
                          "supports":[{
                            "label":"legacy",
                            "actionType":"external",
                            "actionValue":"javascript:alert(1)",
                            "imageUrl":"data:image/svg+xml,<svg onload=alert(1)>"
                          }],
                          "legalDocs":{
                            "termsUrl":"http://insecure.example/terms",
                            "privacyUrl":"",
                            "supportEmail":"support@xianyu.local"
                          }
                        }
                        """);

        Map<String, Object> result = new OpenSourceContentService(jdbcTemplate).getAboutContent();

        assertFalse(String.valueOf(result.get("heroTitle")).contains("<"));
        @SuppressWarnings("unchecked")
        Map<String, Object> support = (Map<String, Object>) ((List<?>) result.get("supports")).get(0);
        assertEquals("toast", support.get("actionType"));
        assertEquals("", support.get("imageUrl"));
        @SuppressWarnings("unchecked")
        Map<String, Object> legal = (Map<String, Object>) result.get("legalDocs");
        assertEquals("", legal.get("termsUrl"));
        assertEquals("", legal.get("supportEmail"));
        assertTrue(String.valueOf(result.get("configurationWarning")).contains("安全校验"));
    }
}
