package com.xianyu.admin.controller;

import org.springframework.http.MediaType;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Lightweight Prometheus text exposition for production smoke monitoring.
 *
 * This intentionally avoids adding a Micrometer/Actuator dependency to keep the
 * current build small. It exposes coarse business and dependency metrics that
 * Grafana/Prometheus can scrape through the Docker internal network.
 */
@RestController
public class OpsPrometheusController {
    private final JdbcTemplate jdbcTemplate;
    private final DataSource dataSource;
    private final RedisConnectionFactory redisConnectionFactory;

    public OpsPrometheusController(JdbcTemplate jdbcTemplate,
                                   DataSource dataSource,
                                   RedisConnectionFactory redisConnectionFactory) {
        this.jdbcTemplate = jdbcTemplate;
        this.dataSource = dataSource;
        this.redisConnectionFactory = redisConnectionFactory;
    }

    @GetMapping(value = {"/api/ops/prometheus", "/admin-api/ops/prometheus"}, produces = MediaType.TEXT_PLAIN_VALUE)
    public String prometheus() {
        StringBuilder out = new StringBuilder(4096);
        gauge(out, "xianyu_core_up", "Core API JVM process is reachable", 1);
        gauge(out, "xianyu_core_scrape_timestamp_seconds", "Unix timestamp of this scrape", Instant.now().getEpochSecond());
        gauge(out, "xianyu_core_database_up", "Database connectivity status", checkDatabase() ? 1 : 0);
        gauge(out, "xianyu_core_redis_up", "Redis connectivity status", checkRedis() ? 1 : 0);
        appendTableCount(out, "xianyu_payment_orders_total", "Payment orders by status", "payment_order", "status", "deleted=0");
        appendTableCount(out, "xianyu_client_errors_total", "Client-side error logs by type", "client_error_log", "error_type", "1=1");
        appendNotificationDelivery(out);
        return out.toString();
    }

    private boolean checkDatabase() {
        try (Connection connection = dataSource.getConnection()) {
            return connection.isValid(2);
        } catch (Exception e) {
            return false;
        }
    }

    private boolean checkRedis() {
        try (RedisConnection connection = redisConnectionFactory.getConnection()) {
            return "PONG".equalsIgnoreCase(connection.ping());
        } catch (Exception e) {
            return false;
        }
    }

    private void appendNotificationDelivery(StringBuilder out) {
        if (!tableExists("notification_delivery_log")) return;
        help(out, "xianyu_notification_delivery_total", "Notification deliveries grouped by success flag");
        type(out, "xianyu_notification_delivery_total", "counter");
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT success, COUNT(*) AS cnt FROM notification_delivery_log GROUP BY success");
            for (Map<String, Object> row : rows) {
                String success = String.valueOf(row.getOrDefault("success", "0"));
                Number cnt = number(row.get("cnt"));
                out.append("xianyu_notification_delivery_total{success=\"").append(escapeLabel(success)).append("\"} ").append(cnt.longValue()).append('\n');
            }
        } catch (Exception ignored) {
            gauge(out, "xianyu_notification_delivery_scrape_error", "Notification delivery metric scrape error", 1);
        }
    }

    private void appendTableCount(StringBuilder out, String metric, String description, String table, String groupColumn, String where) {
        if (!tableExists(table)) return;
        help(out, metric, description);
        type(out, metric, "counter");
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT " + groupColumn + " AS label_value, COUNT(*) AS cnt FROM " + table + " WHERE " + where + " GROUP BY " + groupColumn);
            for (Map<String, Object> row : rows) {
                String label = String.valueOf(row.getOrDefault("label_value", "unknown"));
                Number cnt = number(row.get("cnt"));
                out.append(metric).append("{value=\"").append(escapeLabel(label)).append("\"} ").append(cnt.longValue()).append('\n');
            }
        } catch (Exception e) {
            gauge(out, metric + "_scrape_error", description + " scrape error", 1);
        }
    }

    private boolean tableExists(String tableName) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = ?",
                    Integer.class, tableName);
            return count != null && count > 0;
        } catch (Exception e) {
            return false;
        }
    }

    private Number number(Object value) {
        if (value instanceof Number n) return n;
        if (value == null) return 0;
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception ignored) {
            return 0;
        }
    }

    private void gauge(StringBuilder out, String name, String description, Number value) {
        help(out, name, description);
        type(out, name, "gauge");
        out.append(name).append(' ').append(String.format(Locale.ROOT, "%s", value)).append('\n');
    }

    private void help(StringBuilder out, String name, String description) {
        out.append("# HELP ").append(name).append(' ').append(description.replace('\n', ' ')).append('\n');
    }

    private void type(StringBuilder out, String name, String type) {
        out.append("# TYPE ").append(name).append(' ').append(type).append('\n');
    }

    private String escapeLabel(String value) {
        return value == null ? "" : value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ");
    }
}
