package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class ImageProxyService {
    private static final Logger log = LoggerFactory.getLogger(ImageProxyService.class);
    private static final long ENTRY_TTL_MS = 30 * 60 * 1000L;
    private static final int MAX_REGISTERED_URLS = 5_000;
    private static final long MAX_MEMORY_CACHE_BYTES = 100L * 1024 * 1024;

    private final ConcurrentHashMap<String, CacheEntry> entries = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, byte[]> imageCache = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, String> typeCache = new ConcurrentHashMap<>();
    private final AtomicLong cachedBytes = new AtomicLong();
    private final OutboundImageUrlPolicy urlPolicy;
    private final SafeRemoteImageFetcher imageFetcher;
    private final ScheduledExecutorService cleaner = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread thread = new Thread(r, "img-proxy-cleaner");
        thread.setDaemon(true);
        return thread;
    });

    public ImageProxyService(OutboundImageUrlPolicy urlPolicy, SafeRemoteImageFetcher imageFetcher) {
        this.urlPolicy = urlPolicy;
        this.imageFetcher = imageFetcher;
        cleaner.scheduleAtFixedRate(this::evictExpired, 5, 5, TimeUnit.MINUTES);
    }

    /** Registers only a validated public HTTP(S) image destination. */
    public String register(String originalUrl) {
        URI safeUri = urlPolicy.validate(originalUrl);
        if (entries.size() >= MAX_REGISTERED_URLS) {
            evictExpired();
            if (entries.size() >= MAX_REGISTERED_URLS) {
                throw new BizException(429, "图片代理请求过多，请稍后重试");
            }
        }
        String token = UUID.randomUUID().toString().replace("-", "");
        entries.put(token, new CacheEntry(safeUri.toString(), System.currentTimeMillis()));
        return token;
    }

    /** Resolves an opaque token through the bounded SSRF-safe image fetcher. */
    public ProxyResult proxy(String token) {
        CacheEntry entry = entries.get(token);
        if (entry == null || isExpired(entry)) {
            remove(token);
            throw new BizException(404, "图片不存在或代理令牌已过期");
        }

        byte[] cached = imageCache.get(token);
        String cachedType = typeCache.get(token);
        if (cached != null && cachedType != null) {
            return new ProxyResult(cached, cachedType);
        }

        try {
            SafeRemoteImageFetcher.FetchedImage fetched = imageFetcher.fetch(entry.originalUrl());
            byte[] bytes = fetched.bytes();
            if (reserveCache(bytes.length)) {
                byte[] previous = imageCache.putIfAbsent(token, bytes.clone());
                if (previous == null) {
                    typeCache.put(token, fetched.contentType());
                } else {
                    cachedBytes.addAndGet(-bytes.length);
                }
            }
            return new ProxyResult(bytes, fetched.contentType());
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.warn("proxy image failed, errorType={}", e.getClass().getSimpleName());
            throw new BizException(502, "远程图片加载失败");
        }
    }

    private boolean reserveCache(int bytes) {
        while (true) {
            long current = cachedBytes.get();
            if (bytes < 0 || current + bytes > MAX_MEMORY_CACHE_BYTES) return false;
            if (cachedBytes.compareAndSet(current, current + bytes)) return true;
        }
    }

    private boolean isExpired(CacheEntry entry) {
        return System.currentTimeMillis() - entry.createdAt() > ENTRY_TTL_MS;
    }

    private void evictExpired() {
        long now = System.currentTimeMillis();
        entries.forEach((token, entry) -> {
            if (now - entry.createdAt() > ENTRY_TTL_MS) remove(token);
        });
    }

    private void remove(String token) {
        if (token == null) return;
        entries.remove(token);
        byte[] removed = imageCache.remove(token);
        typeCache.remove(token);
        if (removed != null) cachedBytes.addAndGet(-removed.length);
    }

    @PreDestroy
    void shutdown() {
        cleaner.shutdownNow();
        entries.clear();
        imageCache.clear();
        typeCache.clear();
        cachedBytes.set(0);
    }

    private record CacheEntry(String originalUrl, long createdAt) {}

    public record ProxyResult(byte[] bytes, String contentType) {
        public ProxyResult {
            bytes = bytes.clone();
        }

        @Override
        public byte[] bytes() {
            return bytes.clone();
        }
    }
}
