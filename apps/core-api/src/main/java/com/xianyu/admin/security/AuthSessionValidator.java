package com.xianyu.admin.security;

import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Validates a signed JWT against the current account security state.
 *
 * <p>JWT signature validation alone cannot revoke an already issued token when
 * an account is disabled, its password changes, or an administrator's roles
 * are reduced.  This validator intentionally checks the authoritative row on
 * every protected request so those changes take effect immediately.</p>
 */
@Component
public class AuthSessionValidator {
    private final JdbcTemplate jdbcTemplate;

    public AuthSessionValidator(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void validateUser(long userId, long tenantId, String username, long securityVersion) {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT username, tenant_id, status, deleted, security_version FROM sys_user WHERE id=? LIMIT 1",
                    userId);
            if (rows.size() != 1) throw new InvalidAuthSessionException();
            Map<String, Object> row = rows.get(0);
            if (number(row.get("tenant_id")) != tenantId
                    || number(row.get("status")) != 1
                    || number(row.get("deleted")) != 0
                    || number(row.get("security_version")) != securityVersion
                    || !safe(row.get("username")).equals(username)) {
                throw new InvalidAuthSessionException();
            }
        } catch (InvalidAuthSessionException e) {
            throw e;
        } catch (DataAccessException e) {
            throw new AuthStateUnavailableException(e);
        }
    }

    public void validateAdmin(long userId, String username, String roles, long securityVersion) {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT username, roles, status, deleted, security_version FROM sys_admin_user WHERE id=? LIMIT 1",
                    userId);
            if (rows.size() != 1) throw new InvalidAuthSessionException();
            Map<String, Object> row = rows.get(0);
            if (number(row.get("status")) != 1
                    || number(row.get("deleted")) != 0
                    || number(row.get("security_version")) != securityVersion
                    || !safe(row.get("username")).equals(username)
                    || !roleSet(row.get("roles")).equals(roleSet(roles))) {
                throw new InvalidAuthSessionException();
            }
        } catch (InvalidAuthSessionException e) {
            throw e;
        } catch (DataAccessException e) {
            throw new AuthStateUnavailableException(e);
        }
    }

    private Set<String> roleSet(Object value) {
        return Arrays.stream(safe(value).split(","))
                .map(String::trim)
                .filter(role -> !role.isEmpty())
                .collect(Collectors.toUnmodifiableSet());
    }

    private long number(Object value) {
        if (value instanceof Number number) return number.longValue();
        try {
            return Long.parseLong(safe(value));
        } catch (NumberFormatException e) {
            return Long.MIN_VALUE;
        }
    }

    private String safe(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    public static final class InvalidAuthSessionException extends RuntimeException {
        public InvalidAuthSessionException() {
            super("authentication state is no longer valid");
        }
    }

    public static final class AuthStateUnavailableException extends RuntimeException {
        public AuthStateUnavailableException(Throwable cause) {
            super("authentication state is unavailable", cause);
        }
    }
}
