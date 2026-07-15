package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.config.UploadPathConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Production-grade liveness/readiness probes.
 *
 * /api/health is kept as a cheap compatibility probe. These endpoints provide
 * the richer checks needed by Docker/Kubernetes, load balancers and release gates.
 */
@RestController
public class OpsHealthController {
    private final DataSource dataSource;
    private final RedisConnectionFactory redisConnectionFactory;
    private final UploadPathConfig uploadPathConfig;
    private final String appName;

    public OpsHealthController(DataSource dataSource,
                               RedisConnectionFactory redisConnectionFactory,
                               UploadPathConfig uploadPathConfig,
                               @Value("${spring.application.name:xianyu-assistant}") String appName) {
        this.dataSource = dataSource;
        this.redisConnectionFactory = redisConnectionFactory;
        this.uploadPathConfig = uploadPathConfig;
        this.appName = appName;
    }

    @GetMapping({"/api/ops/liveness", "/admin-api/ops/liveness"})
    public Result<Map<String, Object>> liveness() {
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("status", "UP");
        res.put("app", appName);
        res.put("time", Instant.now().toString());
        return Result.ok(res);
    }

    @GetMapping({"/api/ops/readiness", "/admin-api/ops/readiness"})
    public ResponseEntity<Result<Map<String, Object>>> readiness() {
        Map<String, Object> checks = new LinkedHashMap<>();
        boolean dbOk = checkDatabase(checks);
        boolean redisOk = checkRedis(checks);
        boolean uploadStorageOk = checkUploadStorage(checks);

        Map<String, Object> res = new LinkedHashMap<>();
        boolean ready = dbOk && redisOk && uploadStorageOk;
        res.put("status", ready ? "UP" : "DOWN");
        res.put("app", appName);
        res.put("time", Instant.now().toString());
        res.put("checks", checks);
        Result<Map<String, Object>> body = ready
                ? Result.ok(res)
                : new Result<>(503, "服务尚未就绪", res);
        return ResponseEntity.status(ready ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE)
                .body(body);
    }

    private boolean checkDatabase(Map<String, Object> checks) {
        long start = System.currentTimeMillis();
        try (Connection connection = dataSource.getConnection()) {
            boolean valid = connection.isValid(2);
            checks.put("database", Map.of(
                    "status", valid ? "UP" : "DOWN",
                    "latencyMs", System.currentTimeMillis() - start
            ));
            return valid;
        } catch (Exception e) {
            checks.put("database", Map.of(
                    "status", "DOWN",
                    "latencyMs", System.currentTimeMillis() - start
            ));
            return false;
        }
    }

    private boolean checkRedis(Map<String, Object> checks) {
        long start = System.currentTimeMillis();
        try (RedisConnection connection = redisConnectionFactory.getConnection()) {
            String pong = connection.ping();
            boolean valid = "PONG".equalsIgnoreCase(pong);
            checks.put("redis", Map.of(
                    "status", valid ? "UP" : "DOWN",
                    "latencyMs", System.currentTimeMillis() - start
            ));
            return valid;
        } catch (Exception e) {
            checks.put("redis", Map.of(
                    "status", "DOWN",
                    "latencyMs", System.currentTimeMillis() - start
            ));
            return false;
        }
    }

    private boolean checkUploadStorage(Map<String, Object> checks) {
        long start = System.currentTimeMillis();
        boolean valid = uploadPathConfig.isWritable();
        checks.put("uploadStorage", Map.of(
                "status", valid ? "UP" : "DOWN",
                "latencyMs", System.currentTimeMillis() - start
        ));
        return valid;
    }
}
