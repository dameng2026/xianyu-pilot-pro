package com.xianyu.admin.security;

import jakarta.servlet.http.HttpServletRequest;

import java.net.InetAddress;
import java.util.ArrayList;
import java.util.List;

/** Resolves client IP without trusting forwarding headers from public peers. */
public final class ClientIpResolver {
    private static final int MAX_FORWARDED_HEADER_LENGTH = 2_048;
    private static final int MAX_FORWARDING_HOPS = 20;

    private ClientIpResolver() {}

    public static String resolve(HttpServletRequest request) {
        String remote = normalizeLiteral(request == null ? null : request.getRemoteAddr());
        if (request == null || remote == null || !isTrustedProxy(remote)) {
            return remote == null ? "unknown" : remote;
        }

        List<String> forwarded = parseForwarded(request.getHeader("X-Forwarded-For"));
        for (int i = forwarded.size() - 1; i >= 0; i--) {
            String candidate = forwarded.get(i);
            if (!isTrustedProxy(candidate)) return candidate;
        }
        if (!forwarded.isEmpty()) return forwarded.get(0);

        String realIp = normalizeLiteral(request.getHeader("X-Real-IP"));
        return realIp == null ? remote : realIp;
    }

    private static List<String> parseForwarded(String value) {
        if (value == null || value.isBlank() || value.length() > MAX_FORWARDED_HEADER_LENGTH) {
            return List.of();
        }
        String[] parts = value.split(",");
        if (parts.length > MAX_FORWARDING_HOPS) return List.of();
        List<String> result = new ArrayList<>();
        for (String part : parts) {
            String normalized = normalizeLiteral(part);
            if (normalized != null) result.add(normalized);
        }
        return result;
    }

    private static boolean isTrustedProxy(String value) {
        try {
            InetAddress address = InetAddress.getByName(value);
            if (address.isAnyLocalAddress() || address.isLoopbackAddress()
                    || address.isLinkLocalAddress() || address.isSiteLocalAddress()) {
                return true;
            }
            byte[] bytes = address.getAddress();
            return bytes.length == 16 && (((bytes[0] & 0xff) == 0xfc) || ((bytes[0] & 0xff) == 0xfd));
        } catch (Exception e) {
            return false;
        }
    }

    private static String normalizeLiteral(String value) {
        if (value == null) return null;
        String candidate = value.trim();
        if (candidate.isEmpty()) return null;
        boolean ipv4 = candidate.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}");
        boolean ipv6 = candidate.contains(":") && candidate.matches("[0-9A-Fa-f:.]+");
        if (!(ipv4 || ipv6)) return null;
        try {
            InetAddress address = InetAddress.getByName(candidate);
            if (ipv4) {
                String[] octets = candidate.split("\\.");
                for (String octet : octets) {
                    if (Integer.parseInt(octet) > 255) return null;
                }
            }
            return address.getHostAddress();
        } catch (Exception e) {
            return null;
        }
    }
}
