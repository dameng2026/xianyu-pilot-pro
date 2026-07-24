package com.xianyu.admin.security;

public interface ApikeyVerifier {
    VerifiedCredential verify(String apiKey);

    record VerifiedCredential(Long tenantId, String apiKeyPrefix) {}
}
