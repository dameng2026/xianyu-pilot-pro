package com.xianyu.admin.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.Result;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ReadListener;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletInputStream;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongSupplier;

/** Bounds anonymous client-error ingestion before JSON deserialization. */
@Component
@Order(2)
public class ClientErrorIngressFilter extends OncePerRequestFilter {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final int MAX_TRACKED_CLIENTS = 10_000;

    private final int maxRequests;
    private final long windowMillis;
    private final int maxBodyBytes;
    private final LongSupplier clock;
    private final ConcurrentHashMap<String, Window> windows = new ConcurrentHashMap<>();

    @Autowired
    public ClientErrorIngressFilter(
            @Value("${client-errors.ingress.max-requests-per-window:60}") int maxRequests,
            @Value("${client-errors.ingress.window-millis:60000}") long windowMillis,
            @Value("${client-errors.ingress.max-body-bytes:65536}") int maxBodyBytes) {
        this(maxRequests, windowMillis, maxBodyBytes, System::currentTimeMillis);
    }

    ClientErrorIngressFilter(int maxRequests, long windowMillis, int maxBodyBytes, LongSupplier clock) {
        this.maxRequests = Math.max(1, maxRequests);
        this.windowMillis = Math.max(1, windowMillis);
        this.maxBodyBytes = Math.max(1, Math.min(maxBodyBytes, 1024 * 1024));
        this.clock = clock;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !"POST".equalsIgnoreCase(request.getMethod())
                || !"/api/client-errors".equals(request.getRequestURI());
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        if (!allow(remoteKey(request))) {
            response.setHeader("Retry-After", String.valueOf(Math.max(1, windowMillis / 1_000)));
            deny(response, 429, "too many client error reports");
            return;
        }
        long declaredLength = request.getContentLengthLong();
        if (declaredLength > maxBodyBytes) {
            deny(response, HttpServletResponse.SC_REQUEST_ENTITY_TOO_LARGE, "client error report is too large");
            return;
        }

        byte[] body = request.getInputStream().readNBytes(maxBodyBytes + 1);
        if (body.length > maxBodyBytes) {
            deny(response, HttpServletResponse.SC_REQUEST_ENTITY_TOO_LARGE, "client error report is too large");
            return;
        }
        filterChain.doFilter(new CachedBodyRequest(request, body), response);
    }

    private boolean allow(String key) {
        long now = clock.getAsLong();
        if (windows.size() >= MAX_TRACKED_CLIENTS && !windows.containsKey(key)) {
            evictExpired(now);
            if (windows.size() >= MAX_TRACKED_CLIENTS) return false;
        }
        boolean[] allowed = {false};
        windows.compute(key, (ignored, current) -> {
            if (current == null || now - current.startedAt >= windowMillis) {
                allowed[0] = true;
                return new Window(now, 1);
            }
            if (current.requests >= maxRequests) return current;
            allowed[0] = true;
            return new Window(current.startedAt, current.requests + 1);
        });
        return allowed[0];
    }

    private void evictExpired(long now) {
        Iterator<Map.Entry<String, Window>> iterator = windows.entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<String, Window> entry = iterator.next();
            if (now - entry.getValue().startedAt >= windowMillis) {
                windows.remove(entry.getKey(), entry.getValue());
            }
        }
    }

    private String remoteKey(HttpServletRequest request) {
        return ClientIpResolver.resolve(request);
    }

    private static void deny(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(JSON.writeValueAsString(new Result<>(status, message, null)));
    }

    private record Window(long startedAt, int requests) {}

    private static final class CachedBodyRequest extends HttpServletRequestWrapper {
        private final byte[] body;

        private CachedBodyRequest(HttpServletRequest request, byte[] body) {
            super(request);
            this.body = body;
        }

        @Override
        public int getContentLength() {
            return body.length;
        }

        @Override
        public long getContentLengthLong() {
            return body.length;
        }

        @Override
        public ServletInputStream getInputStream() {
            ByteArrayInputStream input = new ByteArrayInputStream(body);
            return new ServletInputStream() {
                @Override
                public int read() {
                    return input.read();
                }

                @Override
                public int read(byte[] bytes, int off, int len) {
                    return input.read(bytes, off, len);
                }

                @Override
                public boolean isFinished() {
                    return input.available() == 0;
                }

                @Override
                public boolean isReady() {
                    return true;
                }

                @Override
                public void setReadListener(ReadListener readListener) {
                    if (readListener == null) return;
                    try {
                        if (isFinished()) readListener.onAllDataRead();
                        else readListener.onDataAvailable();
                    } catch (IOException e) {
                        readListener.onError(e);
                    }
                }
            };
        }

        @Override
        public BufferedReader getReader() {
            return new BufferedReader(new InputStreamReader(getInputStream(), StandardCharsets.UTF_8));
        }
    }
}
