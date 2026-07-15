package com.xianyu.admin.security;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;

/**
 * Issues and verifies narrowly-scoped browser cookies for same-origin media reads.
 *
 * <p>The cookie contains the already issued access JWT. It is never accepted by
 * the normal API authentication filters; only media controllers read it. This
 * preserves immediate revocation through {@link AuthSessionValidator} while
 * allowing ordinary {@code <img>} elements to authenticate without exposing a
 * bearer token in a URL.</p>
 */
@Service
public class MediaSessionCookieService {
    public static final String USER_COOKIE_NAME = "xianyu_media_user";
    public static final String ADMIN_COOKIE_NAME = "xianyu_media_admin";
    public static final String COOKIE_PATH = "/uploads";

    private final JwtUtil jwtUtil;
    private final AuthSessionValidator authSessionValidator;
    private final boolean secure;
    private final long configuredMaxAgeSeconds;

    public MediaSessionCookieService(
            JwtUtil jwtUtil,
            AuthSessionValidator authSessionValidator,
            @Value("${xianyu.media.cookie-secure:true}") boolean secure,
            @Value("${xianyu.media.session-max-age-seconds:1200}") long configuredMaxAgeSeconds) {
        if (configuredMaxAgeSeconds < 60 || configuredMaxAgeSeconds > 1_200) {
            throw new IllegalArgumentException("media session max age must be between 60 and 1200 seconds");
        }
        this.jwtUtil = jwtUtil;
        this.authSessionValidator = authSessionValidator;
        this.secure = secure;
        this.configuredMaxAgeSeconds = configuredMaxAgeSeconds;
    }

    public IssuedCookie issueUser(HttpServletRequest request) {
        ParsedToken token = parseAuthorization(request, "user");
        validateUser(token);
        return issuedCookie(USER_COOKIE_NAME, token);
    }

    public IssuedCookie issueAdmin(HttpServletRequest request) {
        ParsedToken token = parseAuthorization(request, "admin");
        validateAdmin(token);
        return issuedCookie(ADMIN_COOKIE_NAME, token);
    }

    public String clearUserCookie() {
        return clearCookie(USER_COOKIE_NAME);
    }

    public String clearAdminCookie() {
        return clearCookie(ADMIN_COOKIE_NAME);
    }

    public Optional<UserMediaPrincipal> authenticateUser(HttpServletRequest request) {
        Optional<String> rawToken = cookieValue(request, USER_COOKIE_NAME);
        if (rawToken.isEmpty()) return Optional.empty();
        try {
            ParsedToken token = parseToken(rawToken.get(), "user");
            validateUser(token);
            return Optional.of(new UserMediaPrincipal(token.userId(), token.tenantId()));
        } catch (MediaSessionUnavailableException exception) {
            throw exception;
        } catch (RuntimeException exception) {
            return Optional.empty();
        }
    }

    public Optional<AdminMediaPrincipal> authenticateAdmin(HttpServletRequest request) {
        Optional<String> rawToken = cookieValue(request, ADMIN_COOKIE_NAME);
        if (rawToken.isEmpty()) return Optional.empty();
        try {
            ParsedToken token = parseToken(rawToken.get(), "admin");
            validateAdmin(token);
            return Optional.of(new AdminMediaPrincipal(token.userId(), token.roles()));
        } catch (MediaSessionUnavailableException exception) {
            throw exception;
        } catch (RuntimeException exception) {
            return Optional.empty();
        }
    }

    private ParsedToken parseAuthorization(HttpServletRequest request, String expectedType) {
        String authorization = request == null ? null : request.getHeader("Authorization");
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            throw new InvalidMediaSessionException();
        }
        String token = authorization.substring(7).trim();
        if (token.isEmpty()) throw new InvalidMediaSessionException();
        return parseToken(token, expectedType);
    }

    private ParsedToken parseToken(String rawToken, String expectedType) {
        try {
            Map<String, Object> claims = jwtUtil.verify(rawToken);
            String tokenType = stringValue(claims.get("tokenType"));
            if (!expectedType.equals(tokenType)) throw new InvalidMediaSessionException();
            long userId = positiveLong(claims.get("sub"));
            long authVersion = positiveLong(claims.get("authVersion"));
            long expiresAt = positiveLong(claims.get("exp"));
            String username = stringValue(claims.get("userName"));
            if (username.isBlank()) throw new InvalidMediaSessionException();
            Long tenantId = null;
            String roles = "";
            if ("user".equals(tokenType)) {
                tenantId = positiveLong(claims.get("tenantId"));
            } else {
                roles = stringValue(claims.get("roles"));
                if (roles.isBlank()) throw new InvalidMediaSessionException();
            }
            return new ParsedToken(
                    rawToken, tokenType, userId, username, tenantId, roles, authVersion, expiresAt);
        } catch (InvalidMediaSessionException exception) {
            throw exception;
        } catch (RuntimeException exception) {
            throw new InvalidMediaSessionException();
        }
    }

    private void validateUser(ParsedToken token) {
        try {
            if (token.tenantId() == null) throw new InvalidMediaSessionException();
            authSessionValidator.validateUser(
                    token.userId(), token.tenantId(), token.username(), token.authVersion());
        } catch (AuthSessionValidator.AuthStateUnavailableException exception) {
            throw new MediaSessionUnavailableException(exception);
        } catch (AuthSessionValidator.InvalidAuthSessionException exception) {
            throw new InvalidMediaSessionException();
        }
    }

    private void validateAdmin(ParsedToken token) {
        try {
            authSessionValidator.validateAdmin(
                    token.userId(), token.username(), token.roles(), token.authVersion());
        } catch (AuthSessionValidator.AuthStateUnavailableException exception) {
            throw new MediaSessionUnavailableException(exception);
        } catch (AuthSessionValidator.InvalidAuthSessionException exception) {
            throw new InvalidMediaSessionException();
        }
    }

    private IssuedCookie issuedCookie(String name, ParsedToken token) {
        long remainingJwtSeconds = token.expiresAt() - Instant.now().getEpochSecond();
        if (remainingJwtSeconds <= 0) throw new InvalidMediaSessionException();
        long maxAgeSeconds = Math.min(configuredMaxAgeSeconds, remainingJwtSeconds);
        ResponseCookie cookie = baseCookie(name, token.rawToken())
                .maxAge(Duration.ofSeconds(maxAgeSeconds))
                .build();
        return new IssuedCookie(cookie.toString(), maxAgeSeconds);
    }

    private String clearCookie(String name) {
        return baseCookie(name, "")
                .maxAge(Duration.ZERO)
                .build()
                .toString();
    }

    private ResponseCookie.ResponseCookieBuilder baseCookie(String name, String value) {
        return ResponseCookie.from(name, value)
                .httpOnly(true)
                .secure(secure)
                .sameSite("Strict")
                .path(COOKIE_PATH);
    }

    private Optional<String> cookieValue(HttpServletRequest request, String expectedName) {
        if (request == null || request.getCookies() == null) return Optional.empty();
        for (Cookie cookie : request.getCookies()) {
            if (expectedName.equals(cookie.getName()) && cookie.getValue() != null
                    && !cookie.getValue().isBlank()) {
                return Optional.of(cookie.getValue());
            }
        }
        return Optional.empty();
    }

    private long positiveLong(Object value) {
        try {
            long parsed = Long.parseLong(String.valueOf(value));
            if (parsed <= 0) throw new NumberFormatException();
            return parsed;
        } catch (RuntimeException exception) {
            throw new InvalidMediaSessionException();
        }
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private record ParsedToken(
            String rawToken,
            String tokenType,
            long userId,
            String username,
            Long tenantId,
            String roles,
            long authVersion,
            long expiresAt) {}

    public record IssuedCookie(String setCookieHeader, long maxAgeSeconds) {}
    public record UserMediaPrincipal(long userId, long tenantId) {}
    public record AdminMediaPrincipal(long userId, String roles) {}

    public static final class InvalidMediaSessionException extends RuntimeException {}

    public static final class MediaSessionUnavailableException extends RuntimeException {
        public MediaSessionUnavailableException(Throwable cause) {
            super("media authentication state is unavailable", cause);
        }
    }
}
