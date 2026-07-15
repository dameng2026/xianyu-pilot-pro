package com.xianyu.admin.controller;

import com.xianyu.admin.service.ImageProxyService;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class ImageProxyController {

    private final ImageProxyService imageProxyService;

    public ImageProxyController(ImageProxyService imageProxyService) {
        this.imageProxyService = imageProxyService;
    }

    @GetMapping("/proxy-image/{token}")
    public ResponseEntity<byte[]> proxyImage(@PathVariable String token) {
        ImageProxyService.ProxyResult result = imageProxyService.proxy(token);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(result.contentType()))
                .header("X-Content-Type-Options", "nosniff")
                .header("Content-Security-Policy", "default-src 'none'; sandbox")
                .header("Referrer-Policy", "no-referrer")
                // The opaque capability expires after 30 minutes in ImageProxyService.
                // Shared/browser caches must not extend access beyond that boundary.
                .cacheControl(CacheControl.noStore().cachePrivate().mustRevalidate())
                .body(result.bytes());
    }
}
