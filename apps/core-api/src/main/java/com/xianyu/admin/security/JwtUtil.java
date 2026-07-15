package com.xianyu.admin.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Component
public class JwtUtil {
    private final String secret;
    private final long expireSeconds;
    private final String issuer;
    private final String audience;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private static final int MAX_TOKEN_LENGTH = 8_192;
    private static final long CLOCK_SKEW_SECONDS = 60;
    private static final Set<String> TOKEN_TYPES = Set.of("admin", "user");

    public JwtUtil(@Value("${admin.jwt.secret}") String secret,
                   @Value("${admin.jwt.expire-seconds:3600}") long expireSeconds,
                   @Value("${admin.jwt.issuer:xianyu-core-api}") String issuer,
                   @Value("${admin.jwt.audience:xianyu-user-api}") String audience) {
        if (secret == null || secret.isBlank()) throw new IllegalArgumentException("JWT secret is required");
        if (expireSeconds < 60 || expireSeconds > 86_400) {
            throw new IllegalArgumentException("JWT expiration must be between 60 and 86400 seconds");
        }
        if (issuer == null || issuer.isBlank()) throw new IllegalArgumentException("JWT issuer is required");
        if (audience == null || audience.isBlank()) throw new IllegalArgumentException("JWT audience is required");
        this.secret = secret;
        this.expireSeconds = expireSeconds;
        this.issuer = issuer;
        this.audience = audience;
    }

    public String createAdminToken(long userId, String username, String roles) {
        return createAdminToken(userId, username, roles, 1L);
    }

    public String createAdminToken(long userId, String username, String roles, long securityVersion) {
        if (roles == null || roles.isBlank()) {
            throw new IllegalArgumentException("admin roles are required");
        }
        return createToken(userId, username, roles, null, "admin", securityVersion);
    }

    public String createUserToken(long userId, String username, Long tenantId) {
        return createUserToken(userId, username, tenantId, 1L);
    }

    public String createUserToken(long userId, String username, Long tenantId, long securityVersion) {
        if (tenantId == null || tenantId <= 0) {
            throw new IllegalArgumentException("user tenantId is required");
        }
        return createToken(userId, username, null, tenantId, "user", securityVersion);
    }

    private String createToken(long userId, String username, String roles, Long tenantId,
                               String tokenType, long securityVersion) {
        if (userId <= 0 || username == null || username.isBlank()) {
            throw new IllegalArgumentException("valid token subject is required");
        }
        if (securityVersion <= 0) {
            throw new IllegalArgumentException("valid security version is required");
        }
        try {
            Map<String, Object> header = new LinkedHashMap<>();
            header.put("alg", "HS256"); header.put("typ", "JWT");
            Map<String, Object> payload = new LinkedHashMap<>();
            long now = Instant.now().getEpochSecond();
            payload.put("iss", issuer);
            payload.put("aud", audience);
            payload.put("sub", String.valueOf(userId));
            payload.put("userName", username);
            payload.put("tokenType", tokenType);
            payload.put("jti", UUID.randomUUID().toString());
            payload.put("authVersion", securityVersion);
            if (roles != null) payload.put("roles", roles);
            if (tenantId != null) payload.put("tenantId", String.valueOf(tenantId));
            payload.put("iat", now);
            payload.put("exp", now + expireSeconds);
            String h = b64(objectMapper.writeValueAsBytes(header));
            String p = b64(objectMapper.writeValueAsBytes(payload));
            String sign = sign(h + "." + p);
            return h + "." + p + "." + sign;
        } catch (Exception e) {
            throw new IllegalStateException("create token failed", e);
        }
    }

    public Map<String, Object> verify(String token) {
        try {
            if (token == null || token.isBlank() || token.length() > MAX_TOKEN_LENGTH) {
                throw new IllegalArgumentException("token format invalid");
            }
            String[] arr = token.split("\\.", -1);
            if (arr.length != 3 || arr[0].isBlank() || arr[1].isBlank() || arr[2].isBlank()) {
                throw new IllegalArgumentException("token format invalid");
            }
            String expected = sign(arr[0] + "." + arr[1]);
            if (!MessageDigestSafe.equals(expected, arr[2])) throw new IllegalArgumentException("token signature invalid");

            @SuppressWarnings("unchecked")
            Map<String, Object> header = objectMapper.readValue(
                    Base64.getUrlDecoder().decode(arr[0]), Map.class);
            if (!"HS256".equals(header.get("alg")) || !"JWT".equals(header.get("typ"))) {
                throw new IllegalArgumentException("token header invalid");
            }

            byte[] payload = Base64.getUrlDecoder().decode(arr[1]);
            @SuppressWarnings("unchecked")
            Map<String, Object> map = objectMapper.readValue(payload, Map.class);
            String tokenIssuer = requiredString(map, "iss");
            String tokenAudience = requiredString(map, "aud");
            String subject = requiredString(map, "sub");
            String username = requiredString(map, "userName");
            String tokenType = requiredString(map, "tokenType");
            requiredString(map, "jti");
            long authVersion = requiredNumber(map, "authVersion");
            long issuedAt = requiredNumber(map, "iat");
            long expiresAt = requiredNumber(map, "exp");
            long now = Instant.now().getEpochSecond();

            if (!issuer.equals(tokenIssuer)) throw new IllegalArgumentException("token issuer invalid");
            if (!audience.equals(tokenAudience)) throw new IllegalArgumentException("token audience invalid");
            if (!TOKEN_TYPES.contains(tokenType)) throw new IllegalArgumentException("token type invalid");
            if (authVersion <= 0) throw new IllegalArgumentException("token auth version invalid");
            if (subject.isBlank() || username.isBlank()) throw new IllegalArgumentException("token subject invalid");
            if (issuedAt > now + CLOCK_SKEW_SECONDS) throw new IllegalArgumentException("token issued in future");
            if (expiresAt <= now) throw new IllegalArgumentException("token expired");
            if (expiresAt <= issuedAt || expiresAt - issuedAt > expireSeconds + CLOCK_SKEW_SECONDS) {
                throw new IllegalArgumentException("token lifetime invalid");
            }
            if ("admin".equals(tokenType) && requiredString(map, "roles").isBlank()) {
                throw new IllegalArgumentException("admin roles missing");
            }
            if ("user".equals(tokenType)) {
                long tenantId = Long.parseLong(requiredString(map, "tenantId"));
                if (tenantId <= 0) throw new IllegalArgumentException("user tenant invalid");
            }
            return map;
        } catch (Exception e) {
            throw new IllegalArgumentException("token invalid");
        }
    }

    private String requiredString(Map<String, Object> payload, String name) {
        Object value = payload.get(name);
        if (value == null || String.valueOf(value).isBlank()) {
            throw new IllegalArgumentException("token claim missing");
        }
        return String.valueOf(value);
    }

    private long requiredNumber(Map<String, Object> payload, String name) {
        Object value = payload.get(name);
        if (!(value instanceof Number number)) {
            throw new IllegalArgumentException("token numeric claim missing");
        }
        return number.longValue();
    }

    private String sign(String data) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        return b64(mac.doFinal(data.getBytes(StandardCharsets.UTF_8)));
    }

    private String b64(byte[] bytes) { return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes); }

    static class MessageDigestSafe {
        static boolean equals(String a, String b) {
            if (a == null || b == null) return false;
            byte[] aa = a.getBytes(StandardCharsets.UTF_8), bb = b.getBytes(StandardCharsets.UTF_8);
            if (aa.length != bb.length) return false;
            int r = 0; for (int i = 0; i < aa.length; i++) r |= aa[i] ^ bb[i];
            return r == 0;
        }
    }
}
