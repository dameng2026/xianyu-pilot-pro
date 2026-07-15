package com.xianyu.admin.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.security.JwtUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * 前端错误上报服务。
 *
 * 该接口必须尽量“低影响”：无论用户是否登录、数据库表是否已迁移完成，
 * 都不能因为错误上报失败影响用户主流程。已登录用户会尽量从 JWT 中解析 user/tenant。
 */
@Service
public class ClientErrorService {
    private static final Logger log = LoggerFactory.getLogger(ClientErrorService.class);
    private static final int MAX_EVENTS_PER_REQUEST = 20;
    private static final int MAX_TEXT = 4000;
    private static final int MAX_SANITIZE_DEPTH = 6;
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Pattern SENSITIVE_KEY = Pattern.compile(
            "(?i).*(authorization|cookie|password|passwd|secret|token|api[-_]?key|credential|session).*"
    );
    private static final Pattern BEARER_VALUE = Pattern.compile(
            "(?i)(Bearer\\s+)[A-Za-z0-9._~+\\-/]+=*"
    );
    private static final Pattern NAMED_SECRET_VALUE = Pattern.compile(
            "(?i)((?:authorization|cookie|password|passwd|secret|token|api[-_]?key|credential|session)\\s*[=:]\\s*)[^\\s,;}&]+"
    );

    private final JdbcTemplate jdbcTemplate;
    private final JwtUtil jwtUtil;

    public ClientErrorService(JdbcTemplate jdbcTemplate, JwtUtil jwtUtil) {
        this.jdbcTemplate = jdbcTemplate;
        this.jwtUtil = jwtUtil;
    }

    public Map<String, Object> report(Map<String, Object> payload, String authorization, String ip, String userAgent) {
        List<?> events = normalizeEvents(payload == null ? null : payload.get("events"));
        Map<String, Object> identity = parseIdentity(authorization);
        long accepted = 0;
        long dropped = 0;
        long pending = 0;

        for (int i = 0; i < events.size() && i < MAX_EVENTS_PER_REQUEST; i++) {
            Object raw = events.get(i);
            if (!(raw instanceof Map<?, ?> rawMap)) {
                dropped++;
                continue;
            }
            Map<String, Object> event = new LinkedHashMap<>();
            rawMap.forEach((k, v) -> event.put(String.valueOf(k), v));
            try {
                insertEvent(event, identity, ip, userAgent);
                accepted++;
            } catch (Exception e) {
                pending++;
                log.warn("Failed to persist client error report, errorType={}", e.getClass().getSimpleName());
            }
        }
        if (events.size() > MAX_EVENTS_PER_REQUEST) {
            dropped += events.size() - MAX_EVENTS_PER_REQUEST;
        }
        return Map.of("accepted", accepted, "dropped", dropped, "pending", pending);
    }


    public PageResult<Map<String, Object>> page(int current, int size, String keyword, String type) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        java.util.List<Object> args = new java.util.ArrayList<>();
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (message LIKE ? OR route LIKE ? OR source LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw);
        }
        if (StringUtils.hasText(type)) {
            where.append(" AND error_type=?");
            args.add(type.trim());
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM client_error_log" + where, Long.class, args.toArray());
        java.util.List<Object> pageArgs = new java.util.ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        java.util.List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, user_id AS userId, error_type AS errorType, message, source, route, user_agent AS userAgent, ip_address AS ipAddress, created_time AS createdTime " +
                        "FROM client_error_log" + where + " ORDER BY created_time DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        return new PageResult<>(records, safeCurrent, safeSize, total == null ? 0 : total);
    }

    private List<?> normalizeEvents(Object events) {
        if (events instanceof List<?> list) return list;
        if (events instanceof Map<?, ?> map) return List.of(map);
        return List.of();
    }

    private void insertEvent(Map<String, Object> event, Map<String, Object> identity, String ip, String userAgent) {
        Map<String, Object> sanitized = sanitizeMap(event, 0);
        jdbcTemplate.update("INSERT INTO client_error_log(tenant_id, user_id, error_type, message, stack, source, route, user_agent, ip_address, payload_json, created_time) VALUES(?,?,?,?,?,?,?,?,?,?,NOW())",
                identity.get("tenantId"), identity.get("userId"),
                text(sanitized.get("type"), 80), text(sanitized.get("message"), 500), text(sanitized.get("stack"), MAX_TEXT),
                text(sanitized.get("source"), 200), text(sanitized.get("route"), 300),
                text(first(sanitized.get("userAgent"), sanitizeText(userAgent)), 600),
                text(ip, 80), toJson(sanitized));
    }

    private Map<String, Object> parseIdentity(String authorization) {
        if (!StringUtils.hasText(authorization)) return Map.of();
        String token = authorization.trim();
        if (token.startsWith("Bearer ")) token = token.substring(7).trim();
        if (!StringUtils.hasText(token)) return Map.of();
        try {
            Map<String, Object> payload = jwtUtil.verify(token);
            Map<String, Object> res = new LinkedHashMap<>();
            Object sub = payload.get("sub");
            Object tenantId = payload.get("tenantId");
            if (sub != null) res.put("userId", Long.valueOf(String.valueOf(sub)));
            if (tenantId != null) res.put("tenantId", Long.valueOf(String.valueOf(tenantId)));
            return res;
        } catch (Exception ignored) {
            return Map.of();
        }
    }

    private Object first(Object primary, Object fallback) {
        return primary == null || String.valueOf(primary).isBlank() ? fallback : primary;
    }

    private String text(Object value, int maxLen) {
        if (value == null) return null;
        String s = sanitizeText(String.valueOf(value)).trim();
        if (s.length() > maxLen) return s.substring(0, maxLen);
        return s;
    }

    private Map<String, Object> sanitizeMap(Map<?, ?> input, int depth) {
        Map<String, Object> output = new LinkedHashMap<>();
        if (input == null || depth > MAX_SANITIZE_DEPTH) return output;
        input.forEach((rawKey, value) -> {
            String key = String.valueOf(rawKey);
            if (key.length() > 120) key = key.substring(0, 120);
            output.put(key, SENSITIVE_KEY.matcher(key).matches()
                    ? "[REDACTED]" : sanitizeValue(value, depth + 1));
        });
        return output;
    }

    private Object sanitizeValue(Object value, int depth) {
        if (value == null) return null;
        if (depth > MAX_SANITIZE_DEPTH) return "[TRUNCATED]";
        if (value instanceof Map<?, ?> map) return sanitizeMap(map, depth);
        if (value instanceof List<?> list) {
            return list.stream().limit(100).map(item -> sanitizeValue(item, depth + 1)).toList();
        }
        if (value instanceof Number || value instanceof Boolean) return value;
        return sanitizeText(String.valueOf(value));
    }

    private String sanitizeText(String value) {
        if (value == null) return null;
        String sanitized = BEARER_VALUE.matcher(value).replaceAll("$1[REDACTED]");
        return NAMED_SECRET_VALUE.matcher(sanitized).replaceAll("$1[REDACTED]");
    }

    private String toJson(Map<String, Object> event) {
        try {
            String json = JSON.writeValueAsString(event);
            if (json.length() <= MAX_TEXT) return json;
            String preview = json.substring(0, Math.min(3500, json.length()));
            return JSON.writeValueAsString(Map.of("truncated", true, "preview", preview));
        } catch (JsonProcessingException e) {
            return "{\"serializationError\":true}";
        }
    }
}
