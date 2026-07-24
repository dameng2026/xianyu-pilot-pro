package com.xianyu.admin.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;

@Service
public class ApiKeyCryptoService {
    private static final String PREFIX = "enc:v1:";
    private static final String CONFIGURATION_NAME = "xianyu.api-key.crypto-secret";
    private static final int IV_LENGTH = 12;
    private static final int TAG_BITS = 128;

    private final SecureRandom secureRandom = new SecureRandom();
    private final SecretKeySpec secretKey;

    public ApiKeyCryptoService(@Value("${xianyu.api-key.crypto-secret}") String secret) {
        this.secretKey = new SecretKeySpec(deriveKey(secret), "AES");
    }

    public String encrypt(String plainText) {
        if (plainText == null || plainText.isBlank()) return plainText;
        try {
            byte[] iv = new byte[IV_LENGTH];
            secureRandom.nextBytes(iv);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, secretKey, new GCMParameterSpec(TAG_BITS, iv));
            byte[] encrypted = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));
            return PREFIX + encode(iv) + ":" + encode(encrypted);
        } catch (Exception e) {
            throw new IllegalStateException("API 密钥加密失败", e);
        }
    }

    public String decrypt(String encryptedText) {
        if (encryptedText == null || encryptedText.isBlank()) return null;
        if (!encryptedText.startsWith(PREFIX)) throw new IllegalStateException("API 密钥密文格式无效");
        try {
            String[] parts = encryptedText.split(":", 4);
            if (parts.length != 4) throw new IllegalArgumentException("API 密钥密文格式无效");
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, secretKey,
                    new GCMParameterSpec(TAG_BITS, Base64.getUrlDecoder().decode(parts[2])));
            return new String(cipher.doFinal(Base64.getUrlDecoder().decode(parts[3])), StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new IllegalStateException("API 密钥解密失败，请检查配置 " + CONFIGURATION_NAME + " 是否一致", e);
        }
    }

    private static byte[] deriveKey(String secret) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return Arrays.copyOf(digest.digest(String.valueOf(secret).getBytes(StandardCharsets.UTF_8)), 32);
        } catch (Exception e) {
            throw new IllegalStateException("API 密钥加密密钥初始化失败", e);
        }
    }

    private static String encode(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
