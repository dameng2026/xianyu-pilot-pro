package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.net.InetAddress;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class SafeRemoteImageFetcherTest {
    private static final byte[] PNG = new byte[]{
            (byte) 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x01
    };

    @Test
    void validatesEveryRedirectBeforeOpeningTheNextConnection() throws Exception {
        List<URI> requested = new ArrayList<>();
        SafeRemoteImageFetcher fetcher = new SafeRemoteImageFetcher(policy(), uri -> {
            requested.add(uri);
            return response(302, Map.of("location", List.of("https://169.254.169.254/latest/meta-data")), new byte[0]);
        }, 1_024, 3);

        assertThrows(IllegalArgumentException.class,
                () -> fetcher.fetch("https://cdn.example/image.png"));
        assertEquals(List.of(URI.create("https://cdn.example/image.png")), requested);
    }

    @Test
    void rejectsOversizedOrNonImageResponses() throws Exception {
        byte[] oversized = new byte[33];
        System.arraycopy(PNG, 0, oversized, 0, PNG.length);
        SafeRemoteImageFetcher oversizedFetcher = new SafeRemoteImageFetcher(policy(),
                ignored -> response(200, Map.of("content-type", List.of("image/png")), oversized), 32, 1);
        SafeRemoteImageFetcher htmlFetcher = new SafeRemoteImageFetcher(policy(),
                ignored -> response(200, Map.of("content-type", List.of("text/html")), PNG), 32, 1);

        assertThrows(IllegalArgumentException.class,
                () -> oversizedFetcher.fetch("https://cdn.example/image.png"));
        assertThrows(IllegalArgumentException.class,
                () -> htmlFetcher.fetch("https://cdn.example/image.png"));
    }

    @Test
    void returnsOnlyVerifiedImageBytes() throws Exception {
        SafeRemoteImageFetcher fetcher = new SafeRemoteImageFetcher(policy(),
                ignored -> response(200, Map.of(
                        "content-type", List.of("image/png; charset=binary"),
                        "content-length", List.of(String.valueOf(PNG.length))), PNG), 1_024, 1);

        SafeRemoteImageFetcher.FetchedImage fetched = fetcher.fetch("https://cdn.example/image.png");

        assertEquals("image/png", fetched.contentType());
        assertArrayEquals(PNG, fetched.bytes());
    }

    private OutboundImageUrlPolicy policy() throws Exception {
        return new OutboundImageUrlPolicy(Set.of(), host -> {
            if (host.equals("169.254.169.254")) {
                return new InetAddress[]{InetAddress.getByName("169.254.169.254")};
            }
            return new InetAddress[]{InetAddress.getByName("93.184.216.34")};
        });
    }

    private SafeRemoteImageFetcher.TransportResponse response(int status,
                                                               Map<String, List<String>> headers,
                                                               byte[] body) {
        return new SafeRemoteImageFetcher.TransportResponse(
                status, headers, new ByteArrayInputStream(body));
    }
}
