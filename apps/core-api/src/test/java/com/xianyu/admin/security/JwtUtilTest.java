package com.xianyu.admin.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtUtilTest {
    private static final String SECRET = "enterprise-test-secret-that-is-longer-than-32-characters";
    private static final String ISSUER = "xianyu-core-api";
    private static final String AUDIENCE = "xianyu-user-api";
    private static final ObjectMapper JSON = new ObjectMapper();

    @Test
    void createsPurposeBoundAdminAndUserTokens() {
        JwtUtil jwt = new JwtUtil(SECRET, 900, ISSUER, AUDIENCE);

        Map<String, Object> admin = jwt.verify(jwt.createAdminToken(1L, "admin", "R_SUPER"));
        Map<String, Object> user = jwt.verify(jwt.createUserToken(7L, "buyer", 42L));

        assertEquals("admin", admin.get("tokenType"));
        assertEquals("user", user.get("tokenType"));
        assertEquals("42", user.get("tenantId"));
        assertEquals(1L, ((Number) user.get("authVersion")).longValue());
        assertEquals(ISSUER, user.get("iss"));
        assertNotNull(user.get("jti"));
    }

    @Test
    void rejectsAnAlgorithmHeaderEvenWhenItHasAValidHmacSignature() throws Exception {
        JwtUtil jwt = new JwtUtil(SECRET, 900, ISSUER, AUDIENCE);
        String valid = jwt.createAdminToken(1L, "admin", "R_SUPER");
        String[] parts = valid.split("\\.");
        String forgedHeader = b64(JSON.writeValueAsBytes(Map.of("alg", "none", "typ", "JWT")));
        String signedData = forgedHeader + "." + parts[1];
        String forged = signedData + "." + sign(signedData);

        assertThrows(IllegalArgumentException.class, () -> jwt.verify(forged));
    }

    @Test
    void rejectsAValidlySignedTokenFromAnotherIssuer() throws Exception {
        JwtUtil jwt = new JwtUtil(SECRET, 900, ISSUER, AUDIENCE);
        String valid = jwt.createAdminToken(1L, "admin", "R_SUPER");
        String[] parts = valid.split("\\.");
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = JSON.readValue(Base64.getUrlDecoder().decode(parts[1]), Map.class);
        Map<String, Object> forgedPayload = new LinkedHashMap<>(payload);
        forgedPayload.put("iss", "another-service");
        String encodedPayload = b64(JSON.writeValueAsBytes(forgedPayload));
        String signedData = parts[0] + "." + encodedPayload;
        String forged = signedData + "." + sign(signedData);

        assertThrows(IllegalArgumentException.class, () -> jwt.verify(forged));
    }

    private static String sign(String value) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        return b64(mac.doFinal(value.getBytes(StandardCharsets.UTF_8)));
    }

    private static String b64(byte[] value) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(value);
    }
}
