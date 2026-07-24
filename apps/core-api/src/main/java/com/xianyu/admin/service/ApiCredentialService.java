package com.xianyu.admin.service;

import com.xianyu.admin.mapper.ApiCredentialMapper;
import com.xianyu.admin.security.ApikeyVerifier;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class ApiCredentialService implements ApikeyVerifier, ApplicationRunner {

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final String ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    private static final int KEY_LENGTH = 32;
    private static final int PREFIX_LENGTH = 8;

    private final ApiCredentialMapper mapper;
    private final ApiKeyCryptoService cryptoService;

    public ApiCredentialService(ApiCredentialMapper mapper, ApiKeyCryptoService cryptoService) {
        this.mapper = mapper;
        this.cryptoService = cryptoService;
    }

    @Override
    public void run(ApplicationArguments args) {
        var operationKeys = args.getOptionValues("api-credential-full-reset");
        if (operationKeys != null && !operationKeys.isEmpty()) {
            resetAllCredentialsOnce(operationKeys.get(0));
        }
    }

    @Transactional
    public int resetAllCredentialsOnce(String operationKey) {
        if (operationKey == null || operationKey.isBlank()) {
            throw new IllegalArgumentException("api-credential-full-reset must be provided explicitly");
        }
        mapper.ensureFullResetOperation(operationKey);
        Map<String, Object> operation = mapper.findFullResetOperationForUpdate(operationKey);
        if (operation == null || !"pending".equals(operation.get("status"))) return 0;
        int resetCount = 0;
        for (Long tenantId : mapper.findAllTenantsWithCredentials()) {
            saveCredential(tenantId, generateApiKey());
            resetCount++;
        }
        if (mapper.markFullResetCompleted(operationKey) != 1) {
            throw new IllegalStateException("API credential full reset completion failed");
        }
        return resetCount;
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

    public Map<String, Object> getOrCreateCredential(Long tenantId) {
        Map<String, Object> row = mapper.findByTenantId(tenantId);
        if (row == null) {
            String plainKey = generateApiKey();
            saveCredential(tenantId, plainKey);
            row = mapper.findByTenantId(tenantId);
        } else if (row.get("api_key_encrypted") == null) {
            String plainKey = generateApiKey();
            saveCredential(tenantId, plainKey);
            row = mapper.findByTenantId(tenantId);
        }
        if (row == null) throw new IllegalStateException("failed to create api credential");
        Map<String, Object> result = new LinkedHashMap<>(row);
        result.put("api_key_plain", cryptoService.decrypt((String) row.get("api_key_encrypted")));
        result.remove("api_key_hash");
        result.remove("api_key_encrypted");
        return result;
    }

    public String resetCredential(Long tenantId) {
        String plainKey = generateApiKey();
        saveCredential(tenantId, plainKey);
        return plainKey;
    }

    private void saveCredential(Long tenantId, String plainKey) {
        String hash = sha256(plainKey);
        String prefix = plainKey.substring(0, PREFIX_LENGTH);
        String encrypted = cryptoService.encrypt(plainKey);
        int affected = mapper.updateCredential(tenantId, hash, prefix, encrypted);
        if (affected == 0) mapper.upsertCredential(tenantId, hash, prefix, encrypted);
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
