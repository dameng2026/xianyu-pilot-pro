package com.xianyu.admin.service;

import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * One source of truth for the deliberately anonymous Java media namespace.
 *
 * <p>Public media must be both writable and servable under exactly the same
 * policy. Keeping this seam small prevents a producer from creating public
 * database rows that the authorization controller cannot safely expose.</p>
 */
public final class PublicMediaPolicy {
    private static final Pattern SYSTEM_LOGO_URL = Pattern.compile(
            "^/uploads/public/(logos/[0-9]{8}/[a-f0-9]{32}\\.(png|jpg))$");

    private PublicMediaPolicy() {}

    public static Optional<SystemLogoLocation> systemLogoLocation(String publicUrl) {
        if (publicUrl == null) return Optional.empty();
        Matcher matcher = SYSTEM_LOGO_URL.matcher(publicUrl);
        if (!matcher.matches()) return Optional.empty();
        String relativePath = matcher.group(1);
        return Optional.of(new SystemLogoLocation(
                relativePath,
                "public/" + relativePath,
                "png".equals(matcher.group(2)) ? "image/png" : "image/jpeg"));
    }

    public static boolean allowsSystemLogoWrite(
            long scopeTenantId,
            Long userId,
            String storageKey,
            String publicUrl,
            String mediaType,
            String sourceType,
            String purpose) {
        Optional<SystemLogoLocation> location = systemLogoLocation(publicUrl);
        return scopeTenantId == 0L
                && userId == null
                && location.isPresent()
                && location.get().storageKey().equals(storageKey)
                && location.get().mediaType().equals(mediaType)
                && "system-logo".equals(sourceType)
                && "system-logo".equals(purpose);
    }

    public record SystemLogoLocation(String relativePath, String storageKey, String mediaType) {}
}
