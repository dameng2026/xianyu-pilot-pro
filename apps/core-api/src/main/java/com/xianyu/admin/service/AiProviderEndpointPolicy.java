package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
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

/**
 * Fail-closed network boundary for administrator-configured AI endpoints.
 *
 * <p>Model configuration is persisted in the database, so validating only an
 * environment variable at startup is insufficient. Every outbound request is
 * revalidated to account for configuration and DNS changes. Provider clients
 * must also keep redirects disabled so a validated public endpoint cannot
 * redirect credentials to an internal address.</p>
 */
@Component
public class AiProviderEndpointPolicy {
    private static final int MAX_URL_LENGTH = 2_048;

    private final Set<String> allowedHostRules;
    private final HostResolver resolver;

    @Autowired
    public AiProviderEndpointPolicy(
            @Value("${xianyu.ai.provider.allowed-hosts:${AI_PROVIDER_ALLOWED_HOSTS:}}") String allowedHosts) {
        this(parseAllowedHosts(allowedHosts), InetAddress::getAllByName);
    }

    AiProviderEndpointPolicy(Set<String> allowedHosts, HostResolver resolver) {
        this.allowedHostRules = allowedHosts == null ? Set.of() : allowedHosts.stream()
                .map(AiProviderEndpointPolicy::normalizeHostRule)
                .filter(rule -> !rule.isBlank())
                .collect(Collectors.toUnmodifiableSet());
        this.resolver = resolver;
    }

    /** Returns the validated base URL without trailing slashes. */
    public String validateBaseUrl(String rawUrl) {
        return validateAndResolveBaseUrl(rawUrl).baseUrl();
    }

    /**
     * Validates and resolves a provider endpoint as one security decision.
     *
     * <p>The returned DNS snapshot must be pinned by the outbound transport for
     * the corresponding connection. Keeping the original host separately lets
     * TLS continue to use that host for SNI and certificate verification.</p>
     */
    public ValidatedEndpoint validateAndResolveBaseUrl(String rawUrl) {
        if (rawUrl == null || rawUrl.isBlank() || rawUrl.length() > MAX_URL_LENGTH
                || rawUrl.chars().anyMatch(Character::isISOControl)) {
            throw invalid();
        }
        final URI uri;
        try {
            uri = URI.create(rawUrl.trim());
        } catch (RuntimeException e) {
            throw invalid();
        }
        if (!uri.isAbsolute() || !"https".equalsIgnoreCase(uri.getScheme())
                || uri.getRawUserInfo() != null || uri.getRawQuery() != null
                || uri.getRawFragment() != null) {
            throw invalid();
        }
        int port = uri.getPort();
        if (port != -1 && port != 443) {
            throw invalid();
        }
        String host = normalizeHost(uri.getHost());
        if (host.isBlank() || isLocalHostname(host) || isIpLiteral(host)) {
            throw invalid();
        }
        if (!allowedHostRules.isEmpty() && allowedHostRules.stream().noneMatch(rule ->
                matchesHostRule(host, rule))) {
            throw new BizException(400, "AI Provider 域名不在生产允许列表中");
        }

        final InetAddress[] addresses;
        try {
            addresses = resolver.resolve(host);
        } catch (Exception e) {
            throw new BizException(503, "AI Provider 域名暂时无法安全解析");
        }
        if (addresses == null || addresses.length == 0
                || Arrays.stream(addresses).anyMatch(address -> !isPublicAddress(address))) {
            throw new BizException(400, "AI Provider 地址不能指向本机、内网或保留网络");
        }

        String normalized = uri.toASCIIString();
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return new ValidatedEndpoint(normalized, host, addresses);
    }

    public static final class ValidatedEndpoint {
        private final String baseUrl;
        private final String tlsHost;
        private final InetAddress[] verifiedAddresses;

        private ValidatedEndpoint(String baseUrl, String tlsHost, InetAddress[] verifiedAddresses) {
            this.baseUrl = baseUrl;
            this.tlsHost = tlsHost;
            this.verifiedAddresses = verifiedAddresses.clone();
        }

        public String baseUrl() {
            return baseUrl;
        }

        public String tlsHost() {
            return tlsHost;
        }

        public InetAddress[] verifiedAddresses() {
            return verifiedAddresses.clone();
        }
    }

    private BizException invalid() {
        return new BizException(400, "AI Provider 地址必须是公网 HTTPS 标准地址");
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
        if (first == 0xfc || first == 0xfd) return false;
        return !(bytes.length >= 4
                && (bytes[0] & 0xff) == 0x20
                && (bytes[1] & 0xff) == 0x01
                && (bytes[2] & 0xff) == 0x0d
                && (bytes[3] & 0xff) == 0xb8);
    }

    private static boolean isLocalHostname(String host) {
        return host.equals("localhost") || host.endsWith(".localhost")
                || host.endsWith(".local") || host.endsWith(".internal")
                || host.endsWith(".home") || host.endsWith(".lan");
    }

    private static boolean isIpLiteral(String host) {
        return host.indexOf(':') >= 0 || host.matches("[0-9.]+");
    }

    private static Set<String> parseAllowedHosts(String value) {
        if (value == null || value.isBlank()) return Set.of();
        return Arrays.stream(value.split(","))
                .map(String::trim)
                .filter(item -> !item.isBlank())
                .collect(Collectors.toUnmodifiableSet());
    }

    private static boolean matchesHostRule(String host, String rule) {
        if (rule.startsWith("*.")) {
            String suffix = rule.substring(2);
            return !host.equals(suffix) && host.endsWith("." + suffix);
        }
        return host.equals(rule);
    }

    private static String normalizeHostRule(String rule) {
        if (rule == null) return "";
        String value = rule.trim();
        boolean wildcard = value.startsWith("*.");
        String host = normalizeHost(wildcard ? value.substring(2) : value);
        return host.isBlank() ? "" : (wildcard ? "*." : "") + host;
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
