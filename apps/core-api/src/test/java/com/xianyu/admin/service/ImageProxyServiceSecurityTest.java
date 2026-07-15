package com.xianyu.admin.service;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.net.InetAddress;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ImageProxyServiceSecurityTest {
    private ImageProxyService service;

    @AfterEach
    void shutdown() {
        if (service != null) service.shutdown();
    }

    @Test
    void rejectsUnsafeDestinationBeforeIssuingAProxyToken() throws Exception {
        OutboundImageUrlPolicy policy = new OutboundImageUrlPolicy(Set.of(),
                host -> new InetAddress[]{InetAddress.getByName(host)});
        service = new ImageProxyService(policy, mock(SafeRemoteImageFetcher.class));

        assertThrows(IllegalArgumentException.class,
                () -> service.register("https://127.0.0.1/internal.png"));
    }

    @Test
    void delegatesTokenFetchToTheBoundedImageFetcher() throws Exception {
        OutboundImageUrlPolicy policy = new OutboundImageUrlPolicy(Set.of(),
                ignored -> new InetAddress[]{InetAddress.getByName("93.184.216.34")});
        SafeRemoteImageFetcher fetcher = mock(SafeRemoteImageFetcher.class);
        byte[] png = new byte[]{(byte) 0x89, 0x50, 0x4e, 0x47};
        when(fetcher.fetch("https://cdn.example/a.png"))
                .thenReturn(new SafeRemoteImageFetcher.FetchedImage(png, "image/png"));
        service = new ImageProxyService(policy, fetcher);

        String token = service.register("https://cdn.example/a.png");
        ImageProxyService.ProxyResult result = service.proxy(token);

        assertArrayEquals(png, result.bytes());
    }
}
