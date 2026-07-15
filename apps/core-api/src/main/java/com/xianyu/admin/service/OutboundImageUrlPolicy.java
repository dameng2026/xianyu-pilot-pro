package com.xianyu.admin.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.IDN;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.URI;
import java.util.Arrays;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

/** Validates every remote image hop before an outbound connection is made. */
@Component
public class OutboundImageUrlPolicy {
    private static final int MAX_URL_LENGTH = 2_048;

    private final Set<String> allowedHosts;
    private final HostResolver resolver;

    @Autowired
    public OutboundImageUrlPolicy(@Value("${image.proxy.allowed-hosts:}") String allowedHosts) {
        this(parseAllowedHosts(allowedHosts), InetAddress::getAllByName);
    }

    OutboundImageUrlPolicy(Set<String> allowedHosts, HostResolver resolver) {
        this.allowedHosts = allowedHosts == null ? Set.of() : allowedHosts.stream()
                .map(OutboundImageUrlPolicy::normalizeHost)
                .filter(host -> !host.isBlank())
                .collect(Collectors.toUnmodifiableSet());
        this.resolver = resolver;
    }

    public URI validate(String rawUrl) {
        if (rawUrl == null || rawUrl.isBlank() || rawUrl.length() > MAX_URL_LENGTH) {
            throw new IllegalArgumentException("invalid remote image URL");
        }
        if (rawUrl.chars().anyMatch(ch -> Character.isISOControl(ch))) {
            throw new IllegalArgumentException("invalid remote image URL");
        }
        final URI uri;
        try {
            uri = URI.create(rawUrl.trim());
        } catch (RuntimeException e) {
            throw new IllegalArgumentException("invalid remote image URL", e);
        }
        return validate(uri);
    }

    public URI validate(URI uri) {
        if (uri == null || !uri.isAbsolute()) {
            throw new IllegalArgumentException("remote image URL must be absolute");
        }
        String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
        if (!"https".equals(scheme)) {
            throw new IllegalArgumentException("remote image URL must use HTTPS");
        }
        if (uri.getRawUserInfo() != null || uri.getRawFragment() != null) {
            throw new IllegalArgumentException("remote image URL contains forbidden components");
        }
        String host = normalizeHost(uri.getHost());
        if (host.isBlank() || isLocalHostname(host)) {
            throw new IllegalArgumentException("remote image host is not allowed");
        }
        int port = uri.getPort();
        if (port != -1 && port != 443) {
            throw new IllegalArgumentException("remote image URL uses a forbidden port");
        }
        if (!allowedHosts.isEmpty() && allowedHosts.stream().noneMatch(allowed ->
                host.equals(allowed) || host.endsWith("." + allowed))) {
            throw new IllegalArgumentException("remote image host is not allowlisted");
        }

        InetAddress[] addresses;
        try {
            addresses = resolver.resolve(host);
        } catch (Exception e) {
            throw new IllegalArgumentException("remote image host cannot be resolved", e);
        }
        if (addresses == null || addresses.length == 0
                || Arrays.stream(addresses).anyMatch(address -> !isPublicAddress(address))) {
            throw new IllegalArgumentException("remote image host resolves to a non-public address");
        }
        return uri;
    }

    private static boolean isPublicAddress(InetAddress address) {
        if (address == null || address.isAnyLocalAddress() || address.isLoopbackAddress()
                || address.isLinkLocalAddress() || address.isSiteLocalAddress()
                || address.isMulticastAddress()) {
            return false;
        }
        byte[] bytes = address.getAddress();
        if (address instanceof Inet4Address || bytes.length == 4) {
            int a = bytes[0] & 0xff;
            int b = bytes[1] & 0xff;
            int c = bytes[2] & 0xff;
            if (a == 0 || a == 10 || a == 127 || a >= 224) return false;
            if (a == 100 && b >= 64 && b <= 127) return false;
            if (a == 169 && b == 254) return false;
            if (a == 172 && b >= 16 && b <= 31) return false;
            if (a == 192 && b == 168) return false;
            if (a == 192 && b == 0 && (c == 0 || c == 2)) return false;
            if (a == 198 && (b == 18 || b == 19 || (b == 51 && c == 100))) return false;
            return !(a == 203 && b == 0 && c == 113);
        }
        int first = bytes[0] & 0xff;
        if (first == 0xfc || first == 0xfd) return false; // IPv6 unique-local fc00::/7
        return !(bytes.length >= 4
                && (bytes[0] & 0xff) == 0x20
                && (bytes[1] & 0xff) == 0x01
                && (bytes[2] & 0xff) == 0x0d
                && (bytes[3] & 0xff) == 0xb8); // documentation range
    }

    private static boolean isLocalHostname(String host) {
        return host.equals("localhost") || host.endsWith(".localhost")
                || host.endsWith(".local") || host.endsWith(".internal")
                || host.endsWith(".home") || host.endsWith(".lan");
    }

    private static Set<String> parseAllowedHosts(String value) {
        if (value == null || value.isBlank()) return Set.of();
        return Arrays.stream(value.split(","))
                .map(String::trim)
                .filter(item -> !item.isBlank())
                .map(item -> item.startsWith("*.") ? item.substring(2) : item)
                .collect(Collectors.toUnmodifiableSet());
    }

    private static String normalizeHost(String host) {
        if (host == null) return "";
        String normalized = host.trim();
        if (normalized.startsWith("[") && normalized.endsWith("]")) {
            normalized = normalized.substring(1, normalized.length() - 1);
        }
        while (normalized.endsWith(".")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        if (normalized.indexOf(':') >= 0) {
            return normalized.toLowerCase(Locale.ROOT);
        }
        try {
            return IDN.toASCII(normalized).toLowerCase(Locale.ROOT);
        } catch (IllegalArgumentException e) {
            return "";
        }
    }

    @FunctionalInterface
    interface HostResolver {
        InetAddress[] resolve(String host) throws Exception;
    }
}
