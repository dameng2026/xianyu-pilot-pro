package com.xianyu.admin.service;

import com.xianyu.admin.config.UploadPathConfig;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ImageCacheServiceSecurityTest {
    private ImageCacheService service;

    @AfterEach
    void shutdown() {
        if (service != null) service.shutdown();
        TenantContext.clear();
        UserContext.clear();
    }

    @Test
    void cacheUsesTheSameSafeOutboundFetcherAsThePublicProxy() {
        SafeRemoteImageFetcher fetcher = mock(SafeRemoteImageFetcher.class);
        when(fetcher.fetch("http://127.0.0.1/internal.png"))
                .thenThrow(new IllegalArgumentException("private destination"));
        TenantContext.setCurrentTenantId(7L);
        UserContext.set(9L, "user", 7L);
        service = new ImageCacheService(
                fetcher,
                new UploadPathConfig("uploads"),
                mock(UploadStorageGovernanceService.class));

        assertNull(service.cache("http://127.0.0.1/internal.png"));
        verify(fetcher).fetch("http://127.0.0.1/internal.png");
    }
}
