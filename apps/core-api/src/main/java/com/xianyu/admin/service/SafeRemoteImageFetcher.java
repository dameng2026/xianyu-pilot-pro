package com.xianyu.admin.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Downloads a bounded, verified image while validating every redirect hop. */
@Service
public class SafeRemoteImageFetcher {
    private static final Set<String> ALLOWED_CONTENT_TYPES = Set.of(
            "image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"
    );

    private final OutboundImageUrlPolicy urlPolicy;
    private final Transport transport;
    private final int maxBytes;
    private final int maxRedirects;

    @Autowired
    public SafeRemoteImageFetcher(
            OutboundImageUrlPolicy urlPolicy,
            @Value("${image.proxy.max-bytes:10485760}") int maxBytes,
            @Value("${image.proxy.max-redirects:3}") int maxRedirects) {
        this(urlPolicy, new HttpClientTransport(), maxBytes, maxRedirects);
    }

    SafeRemoteImageFetcher(OutboundImageUrlPolicy urlPolicy, Transport transport,
                           int maxBytes, int maxRedirects) {
        this.urlPolicy = urlPolicy;
        this.transport = transport;
        this.maxBytes = Math.max(1, Math.min(maxBytes, 50 * 1024 * 1024));
        this.maxRedirects = Math.max(0, Math.min(maxRedirects, 5));
    }

    public FetchedImage fetch(String rawUrl) {
        URI current = urlPolicy.validate(rawUrl);
        for (int hop = 0; hop <= maxRedirects; hop++) {
            TransportResponse response = send(current);
            try (InputStream body = response.body()) {
                if (isRedirect(response.statusCode())) {
                    if (hop == maxRedirects) {
                        throw new IllegalArgumentException("remote image has too many redirects");
                    }
                    String location = firstHeader(response.headers(), "location");
                    if (location == null || location.isBlank()) {
                        throw new IllegalArgumentException("remote image redirect is missing Location");
                    }
                    current = urlPolicy.validate(current.resolve(location));
                    continue;
                }
                if (response.statusCode() < 200 || response.statusCode() >= 300) {
                    throw new IllegalArgumentException("remote image returned HTTP " + response.statusCode());
                }

                String contentType = normalizeContentType(firstHeader(response.headers(), "content-type"));
                if (!ALLOWED_CONTENT_TYPES.contains(contentType)) {
                    throw new IllegalArgumentException("remote response is not a supported image");
                }
                assertDeclaredLength(response.headers());
                byte[] bytes = readBounded(body);
                if (!matchesContentType(bytes, contentType)) {
                    throw new IllegalArgumentException("remote image content does not match its media type");
                }
                return new FetchedImage(bytes, contentType);
            } catch (IOException e) {
                throw new IllegalStateException("remote image download failed", e);
            }
        }
        throw new IllegalArgumentException("remote image has too many redirects");
    }

    private TransportResponse send(URI uri) {
        // Re-resolve immediately before every request. This also catches DNS
        // changes between registration and the first fetch.
        urlPolicy.validate(uri);
        try {
            return transport.get(uri);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("remote image download interrupted", e);
        } catch (Exception e) {
            throw new IllegalStateException("remote image download failed", e);
        }
    }

    private void assertDeclaredLength(Map<String, List<String>> headers) {
        String rawLength = firstHeader(headers, "content-length");
        if (rawLength == null || rawLength.isBlank()) return;
        try {
            long length = Long.parseLong(rawLength.trim());
            if (length < 0 || length > maxBytes) {
                throw new IllegalArgumentException("remote image exceeds the size limit");
            }
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("remote image has an invalid Content-Length", e);
        }
    }

    private byte[] readBounded(InputStream input) throws IOException {
        byte[] bytes = input.readNBytes(maxBytes + 1);
        if (bytes.length > maxBytes) {
            throw new IllegalArgumentException("remote image exceeds the size limit");
        }
        if (bytes.length == 0) {
            throw new IllegalArgumentException("remote image is empty");
        }
        return bytes;
    }

    private boolean matchesContentType(byte[] bytes, String contentType) {
        return switch (contentType) {
            case "image/png" -> startsWith(bytes, new int[]{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a});
            case "image/jpeg" -> startsWith(bytes, new int[]{0xff, 0xd8, 0xff});
            case "image/gif" -> asciiAt(bytes, 0, "GIF87a") || asciiAt(bytes, 0, "GIF89a");
            case "image/webp" -> asciiAt(bytes, 0, "RIFF") && asciiAt(bytes, 8, "WEBP");
            case "image/avif" -> asciiAt(bytes, 4, "ftyp")
                    && (asciiAt(bytes, 8, "avif") || asciiAt(bytes, 8, "avis")
                    || asciiAt(bytes, 8, "mif1") || asciiAt(bytes, 8, "msf1"));
            default -> false;
        };
    }

    private boolean startsWith(byte[] bytes, int[] signature) {
        if (bytes.length < signature.length) return false;
        for (int i = 0; i < signature.length; i++) {
            if ((bytes[i] & 0xff) != signature[i]) return false;
        }
        return true;
    }

    private boolean asciiAt(byte[] bytes, int offset, String value) {
        if (offset < 0 || bytes.length < offset + value.length()) return false;
        for (int i = 0; i < value.length(); i++) {
            if ((bytes[offset + i] & 0xff) != value.charAt(i)) return false;
        }
        return true;
    }

    private boolean isRedirect(int status) {
        return status == 301 || status == 302 || status == 303 || status == 307 || status == 308;
    }

    private String normalizeContentType(String value) {
        if (value == null) return "";
        int semicolon = value.indexOf(';');
        String normalized = semicolon >= 0 ? value.substring(0, semicolon) : value;
        return normalized.trim().toLowerCase(Locale.ROOT);
    }

    private String firstHeader(Map<String, List<String>> headers, String name) {
        if (headers == null) return null;
        for (Map.Entry<String, List<String>> entry : headers.entrySet()) {
            if (entry.getKey() != null && entry.getKey().equalsIgnoreCase(name)
                    && entry.getValue() != null && !entry.getValue().isEmpty()) {
                return entry.getValue().get(0);
            }
        }
        return null;
    }

    public record FetchedImage(byte[] bytes, String contentType) {
        public FetchedImage {
            bytes = bytes.clone();
        }

        @Override
        public byte[] bytes() {
            return bytes.clone();
        }
    }

    @FunctionalInterface
    interface Transport {
        TransportResponse get(URI uri) throws Exception;
    }

    record TransportResponse(int statusCode, Map<String, List<String>> headers, InputStream body) {}

    private static final class HttpClientTransport implements Transport {
        private final HttpClient client = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(10))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();

        @Override
        public TransportResponse get(URI uri) throws IOException, InterruptedException {
            HttpRequest request = HttpRequest.newBuilder(uri)
                    .timeout(Duration.ofSeconds(30))
                    .header("User-Agent", "XianyuAssistant-ImageProxy/1.0")
                    .header("Accept", "image/png,image/jpeg,image/webp,image/gif,image/avif")
                    .GET()
                    .build();
            HttpResponse<InputStream> response = client.send(request, HttpResponse.BodyHandlers.ofInputStream());
            return new TransportResponse(response.statusCode(), response.headers().map(), response.body());
        }
    }
}
