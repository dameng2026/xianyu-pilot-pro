package com.xianyu.admin.security;

import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockHttpServletRequest;

import jakarta.servlet.http.Cookie;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.*;

class MediaSessionCookieServiceTest {
    private static final String SECRET = "media-session-test-secret-at-least-32-bytes";

    @Test
    void userCookieIsHttpOnlyStrictSecureAndNeverOutlivesJwt() {
        JwtUtil jwt = jwt(120);
        MediaSessionCookieService service = service(jwt, new AuthSessionValidator(validJdbc()), true, 1_200);
        String token = jwt.createUserToken(11, "alice", 7L, 1L);
        MockHttpServletRequest request = bearer(token);

        MediaSessionCookieService.IssuedCookie issued = service.issueUser(request);

        assertTrue(issued.maxAgeSeconds() > 0);
        assertTrue(issued.maxAgeSeconds() <= 120);
        assertEquals(issued.maxAgeSeconds(), maxAge(issued.setCookieHeader()));
        assertTrue(issued.setCookieHeader().startsWith(
                MediaSessionCookieService.USER_COOKIE_NAME + "=" + token));
        assertTrue(issued.setCookieHeader().contains("Path=/uploads"));
        assertTrue(issued.setCookieHeader().contains("Secure"));
        assertTrue(issued.setCookieHeader().contains("HttpOnly"));
        assertTrue(issued.setCookieHeader().contains("SameSite=Strict"));
    }

    @Test
    void secureAttributeCanBeDisabledOnlyByExplicitConfiguration() {
        JwtUtil jwt = jwt(600);
        MediaSessionCookieService service = service(jwt, new AuthSessionValidator(validJdbc()), false, 300);

        String header = service.issueUser(
                bearer(jwt.createUserToken(11, "alice", 7L, 1L))).setCookieHeader();

        assertFalse(header.contains("; Secure"));
        assertTrue(header.contains("HttpOnly"));
        assertTrue(header.contains("SameSite=Strict"));
    }

    @Test
    void issuedUserCookieAuthenticatesTenantAndRevalidatesAuthoritativeAccount() {
        JwtUtil jwt = jwt(600);
        MediaSessionCookieService service = service(jwt, new AuthSessionValidator(validJdbc()), true, 300);
        String token = jwt.createUserToken(11, "alice", 7L, 1L);
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/uploads/images/tenant-7/a.png");
        request.setCookies(new Cookie(MediaSessionCookieService.USER_COOKIE_NAME, token));

        MediaSessionCookieService.UserMediaPrincipal principal =
                service.authenticateUser(request).orElseThrow();

        assertEquals(11, principal.userId());
        assertEquals(7, principal.tenantId());
    }

    @Test
    void issuedAdminCookieAuthenticatesAdminButCannotBeUsedAsUserCookie() {
        JwtUtil jwt = jwt(600);
        MediaSessionCookieService service = service(jwt, new AuthSessionValidator(validJdbc()), true, 300);
        String adminToken = jwt.createAdminToken(99, "root", "R_SUPER", 1L);
        MockHttpServletRequest adminRequest = new MockHttpServletRequest();
        adminRequest.setCookies(new Cookie(MediaSessionCookieService.ADMIN_COOKIE_NAME, adminToken));

        MediaSessionCookieService.AdminMediaPrincipal principal =
                service.authenticateAdmin(adminRequest).orElseThrow();

        assertEquals(99, principal.userId());
        assertEquals("R_SUPER", principal.roles());

        MockHttpServletRequest userRequest = new MockHttpServletRequest();
        userRequest.setCookies(new Cookie(MediaSessionCookieService.USER_COOKIE_NAME, adminToken));
        assertTrue(service.authenticateUser(userRequest).isEmpty());
    }

    @Test
    void issueRejectsMissingBearerWrongTokenTypeAndRevokedAccount() {
        JwtUtil jwt = jwt(600);
        MediaSessionCookieService service = service(jwt, new AuthSessionValidator(validJdbc()), true, 300);

        assertThrows(MediaSessionCookieService.InvalidMediaSessionException.class,
                () -> service.issueUser(new MockHttpServletRequest()));
        assertThrows(MediaSessionCookieService.InvalidMediaSessionException.class,
                () -> service.issueAdmin(bearer(jwt.createUserToken(11, "alice", 7L, 1L))));

        JdbcTemplate revoked = new StubJdbc(
                List.of(Map.of(
                        "username", "alice", "tenant_id", 7L, "status", 0,
                        "deleted", 0, "security_version", 1L)),
                List.of());
        MediaSessionCookieService revokedService = service(
                jwt, new AuthSessionValidator(revoked), true, 300);
        assertThrows(MediaSessionCookieService.InvalidMediaSessionException.class,
                () -> revokedService.issueUser(
                        bearer(jwt.createUserToken(11, "alice", 7L, 1L))));
    }

    @Test
    void authenticationFailsClosedAndDistinguishesAuthDatabaseOutage() {
        JwtUtil jwt = jwt(600);
        MediaSessionCookieService service = service(jwt, new AuthSessionValidator(validJdbc()), true, 300);
        MockHttpServletRequest malformed = new MockHttpServletRequest();
        malformed.setCookies(new Cookie(MediaSessionCookieService.USER_COOKIE_NAME, "not-a-jwt"));
        assertTrue(service.authenticateUser(malformed).isEmpty());

        MediaSessionCookieService unavailable = service(
                jwt, new AuthSessionValidator(new FailingJdbc()), true, 300);
        MockHttpServletRequest validCookie = new MockHttpServletRequest();
        validCookie.setCookies(new Cookie(
                MediaSessionCookieService.USER_COOKIE_NAME,
                jwt.createUserToken(11, "alice", 7L, 1L)));
        assertThrows(MediaSessionCookieService.MediaSessionUnavailableException.class,
                () -> unavailable.authenticateUser(validCookie));
    }

    @Test
    void clearCookiesUseMatchingScopeAndImmediateExpiry() {
        MediaSessionCookieService service = service(
                jwt(600), new AuthSessionValidator(validJdbc()), true, 300);

        String user = service.clearUserCookie();
        String admin = service.clearAdminCookie();

        assertTrue(user.startsWith(MediaSessionCookieService.USER_COOKIE_NAME + "="));
        assertTrue(admin.startsWith(MediaSessionCookieService.ADMIN_COOKIE_NAME + "="));
        assertTrue(user.contains("Path=/uploads"));
        assertTrue(user.contains("Max-Age=0"));
        assertTrue(user.contains("HttpOnly"));
        assertTrue(user.contains("SameSite=Strict"));
    }

    @Test
    void invalidCookieLifetimeConfigurationIsRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> service(jwt(600), new AuthSessionValidator(validJdbc()), true, 59));
        assertThrows(IllegalArgumentException.class,
                () -> service(jwt(600), new AuthSessionValidator(validJdbc()), true, 1_201));
    }

    private MediaSessionCookieService service(
            JwtUtil jwt, AuthSessionValidator validator, boolean secure, long maxAge) {
        return new MediaSessionCookieService(jwt, validator, secure, maxAge);
    }

    private JwtUtil jwt(long expirySeconds) {
        return new JwtUtil(SECRET, expirySeconds, "issuer", "audience");
    }

    private MockHttpServletRequest bearer(String token) {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("Authorization", "Bearer " + token);
        return request;
    }

    private JdbcTemplate validJdbc() {
        return new StubJdbc(
                List.of(Map.of(
                        "username", "alice", "tenant_id", 7L, "status", 1,
                        "deleted", 0, "security_version", 1L)),
                List.of(Map.of(
                        "username", "root", "roles", "R_SUPER", "status", 1,
                        "deleted", 0, "security_version", 1L)));
    }

    private long maxAge(String header) {
        Matcher matcher = Pattern.compile("(?:^|; )Max-Age=([0-9]+)").matcher(header);
        assertTrue(matcher.find(), header);
        return Long.parseLong(matcher.group(1));
    }

    private static class StubJdbc extends JdbcTemplate {
        private final List<Map<String, Object>> users;
        private final List<Map<String, Object>> admins;

        StubJdbc(List<Map<String, Object>> users, List<Map<String, Object>> admins) {
            this.users = users;
            this.admins = admins;
        }

        @Override
        public List<Map<String, Object>> queryForList(String sql, Object... args) {
            return sql.contains("sys_admin_user") ? admins : users;
        }
    }

    private static final class FailingJdbc extends JdbcTemplate {
        @Override
        public List<Map<String, Object>> queryForList(String sql, Object... args) {
            throw new DataAccessResourceFailureException("database unavailable");
        }
    }
}
