package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ImageGenerationHistorySecurityTest {

    @Test
    void historyDetailQueryIsTenantScoped() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForMap(anyString(), eq(42L), eq("request-1")))
                .thenReturn(Map.of("request_id", "request-1", "result_images", "[]"));
        ImageGenerationService service = service(jdbc, mock(ImageProxyService.class), mock(CookieCryptoService.class));

        service.getHistory(42L, "request-1");

        verify(jdbc).queryForMap(
                org.mockito.ArgumentMatchers.contains("tenant_id=? AND request_id=?"),
                eq(42L), eq("request-1"));
    }

    @Test
    void recoveredImagesNeverExposeEncryptedOrPlaintextSourceUrls() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        ImageProxyService proxy = mock(ImageProxyService.class);
        CookieCryptoService crypto = mock(CookieCryptoService.class);
        when(jdbc.queryForMap(anyString(), eq(42L), eq(9L))).thenReturn(Map.of(
                "result_images", "[{\"index\":0,\"encryptedOriginalUrl\":\"enc:v1:cipher\"}]",
                "image_count", 1
        ));
        when(crypto.decryptIfNeeded("enc:v1:cipher")).thenReturn("https://cdn.example/image.png");
        when(proxy.register("https://cdn.example/image.png")).thenReturn("opaque-token");
        ImageGenerationService service = service(jdbc, proxy, crypto);

        Map<String, Object> recovered = service.recoverImages(42L, 9L).get(0);

        assertEquals("/api/proxy-image/opaque-token", recovered.get("url"));
        assertFalse(recovered.containsKey("originalUrl"));
        assertFalse(recovered.containsKey("encryptedOriginalUrl"));
    }

    private ImageGenerationService service(JdbcTemplate jdbc,
                                           ImageProxyService proxy,
                                           CookieCryptoService crypto) {
        return new ImageGenerationService(
                mock(ModelConfigService.class),
                jdbc,
                mock(AiProviderService.class),
                proxy,
                mock(ImageCacheService.class),
                crypto
        );
    }
}
