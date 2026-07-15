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

/**
 * Cookie 加解密服务。
 *
 * 存储格式：enc:v1:{base64url(iv)}:{base64url(cipherText+tag)}
 * 说明：为兼容历史数据，decryptIfNeeded 会对非 enc:v1 前缀的内容按明文返回。
 */
@Service
public class CookieCryptoService {
    private static final String PREFIX = "enc:v1:";
    private static final int IV_LENGTH = 12;
    private static final int GCM_TAG_BITS = 128;
    private final SecureRandom secureRandom = new SecureRandom();
    private final SecretKeySpec secretKey;

    public CookieCryptoService(@Value("${xianyu.cookie.crypto-secret:dev-only-cookie-crypto-secret-change-me-32-chars}") String secret) {
        this.secretKey = new SecretKeySpec(deriveKey(secret), "AES");
    }

    public String encrypt(String plainText) {
        if (plainText == null || plainText.isBlank()) return plainText;
        if (plainText.startsWith(PREFIX)) return plainText;
        try {
            byte[] iv = new byte[IV_LENGTH];
            secureRandom.nextBytes(iv);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, secretKey, new GCMParameterSpec(GCM_TAG_BITS, iv));
            byte[] cipherText = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));
            return PREFIX + b64(iv) + ":" + b64(cipherText);
        } catch (Exception e) {
            throw new IllegalStateException("Cookie 加密失败", e);
        }
    }

    public String decryptIfNeeded(String storedText) {
        if (storedText == null || storedText.isBlank()) return storedText;
        if (!storedText.startsWith(PREFIX)) return storedText;
        try {
            String[] parts = storedText.split(":", 4);
            if (parts.length != 4) throw new IllegalArgumentException("encrypted cookie format invalid");
            byte[] iv = Base64.getUrlDecoder().decode(parts[2]);
            byte[] cipherText = Base64.getUrlDecoder().decode(parts[3]);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, secretKey, new GCMParameterSpec(GCM_TAG_BITS, iv));
            return new String(cipher.doFinal(cipherText), StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new IllegalStateException("Cookie 解密失败，请检查 xianyu.cookie.crypto-secret 是否一致", e);
        }
    }

    private static byte[] deriveKey(String secret) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return Arrays.copyOf(digest.digest(String.valueOf(secret).getBytes(StandardCharsets.UTF_8)), 32);
        } catch (Exception e) {
            throw new IllegalStateException("Cookie 加密密钥初始化失败", e);
        }
    }

    private static String b64(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
