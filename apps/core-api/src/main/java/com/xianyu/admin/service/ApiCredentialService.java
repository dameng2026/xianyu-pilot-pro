package com.xianyu.admin.service;

import com.xianyu.admin.mapper.ApiCredentialMapper;
import com.xianyu.admin.security.ApikeyVerifier;
import org.springframework.stereotype.Service;

import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class ApiCredentialService implements ApikeyVerifier {

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final String ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    private static final int KEY_LENGTH = 32;
    private static final int PREFIX_LENGTH = 8;

    private final ApiCredentialMapper mapper;

    public ApiCredentialService(ApiCredentialMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public VerifiedCredential verify(String apiKey) {
        if (apiKey == null || apiKey.isBlank()) return null;
        String hash = sha256(apiKey);
        Map<String, Object> row = mapper.findByHash(hash);
        if (row == null) return null;
        Long tenantId = getLong(row, "tenant_id");
        String prefix = (String) row.get("api_key_prefix");
        if (tenantId == null) return null;
        mapper.touchLastUsed(tenantId);
        return new VerifiedCredential(tenantId, prefix);
    }

    /**
     * 获取租户的凭证信息（脱敏，不返回完整 apiKey）。
     * 若租户尚无凭证，自动创建一个。
     */
    public Map<String, Object> getOrCreateCredential(Long tenantId) {
        Map<String, Object> row = mapper.findByTenantId(tenantId);
        if (row == null) {
            String plainKey = generateApiKey();
            String hash = sha256(plainKey);
            String prefix = plainKey.substring(0, PREFIX_LENGTH);
            mapper.upsertCredential(tenantId, hash, prefix);
            row = mapper.findByTenantId(tenantId);
            if (row == null) {
                throw new IllegalStateException("failed to create api credential");
            }
            // 首次创建时返回明文（仅一次）
            row = new LinkedHashMap<>(row);
            row.put("api_key_plain", plainKey);
        }
        return row;
    }

    /**
     * 重置密钥，返回新明文（仅此一次可见）。
     */
    public String resetCredential(Long tenantId) {
        String plainKey = generateApiKey();
        String hash = sha256(plainKey);
        String prefix = plainKey.substring(0, PREFIX_LENGTH);
        int affected = mapper.updateCredential(tenantId, hash, prefix);
        if (affected == 0) {
            // 尚未存在则创建
            mapper.upsertCredential(tenantId, hash, prefix);
        }
        return plainKey;
    }

    private String generateApiKey() {
        StringBuilder sb = new StringBuilder(KEY_LENGTH);
        for (int i = 0; i < KEY_LENGTH; i++) {
            sb.append(ALPHABET.charAt(RANDOM.nextInt(ALPHABET.length())));
        }
        return sb.toString();
    }

    private static String sha256(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] bytes = md.digest(input.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(bytes);
        } catch (Exception e) {
            throw new IllegalStateException("sha256 failed", e);
        }
    }

    private static Long getLong(Map<String, Object> row, String key) {
        Object v = row.get(key);
        if (v == null) return null;
        if (v instanceof Number n) return n.longValue();
        try { return Long.parseLong(v.toString()); } catch (Exception e) { return null; }
    }
}
