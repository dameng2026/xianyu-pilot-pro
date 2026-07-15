package com.xianyu.admin.controller;

import com.xianyu.admin.service.ImageProxyService;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ImageProxyControllerSecurityTest {

    @Test
    void capabilityResponseCannotOutliveItsTokenInSharedCaches() {
        ImageProxyService service = mock(ImageProxyService.class);
        byte[] bytes = "image".getBytes(StandardCharsets.UTF_8);
        when(service.proxy("opaque-token"))
                .thenReturn(new ImageProxyService.ProxyResult(bytes, "image/png"));

        ResponseEntity<byte[]> response = new ImageProxyController(service).proxyImage("opaque-token");

        String cacheControl = response.getHeaders().getCacheControl();
        assertNotNull(cacheControl);
        assertTrue(cacheControl.contains("no-store"));
        assertTrue(cacheControl.contains("private"));
        assertTrue(cacheControl.contains("must-revalidate"));
        assertEquals("no-referrer", response.getHeaders().getFirst("Referrer-Policy"));
        assertArrayEquals(bytes, response.getBody());
    }
}
