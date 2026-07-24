package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.mapper.ApiSliderSolveRecordMapper;
import com.xianyu.admin.security.ApiSliderContext;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Service
public class ApiSliderSolveService {

    private static final Logger log = LoggerFactory.getLogger(ApiSliderSolveService.class);
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final String PENDING_KEY_PREFIX = "api_slider:pending:";
    private static final String MODULE_KEY = "api-slider-solve";
    private static final BigDecimal DEFAULT_PER_CALL_PRICE = new BigDecimal("0.05");
    private static final BigDecimal DEFAULT_EXCHANGE_RATE = new BigDecimal("100");

    private final JdbcTemplate jdbcTemplate;
    private final ApiSliderSolveRecordMapper recordMapper;
    private final StringRedisTemplate redisTemplate;

    @Value("${xianyu.api-slider.automation-base-url:http://localhost:12401}")
    private String automationBaseUrl;

    @Value("${xianyu.api-slider.internal-token:dev-only-internal-api-token-change-me-32-chars}")
    private String internalToken;

    @Value("${xianyu.api-slider.solve-timeout-ms:120000}")
    private long solveTimeoutMs;

    private RestClient httpClient;

    @Autowired
    public ApiSliderSolveService(JdbcTemplate jdbcTemplate,
                                 ApiSliderSolveRecordMapper recordMapper,
                                 StringRedisTemplate redisTemplate) {
        this.jdbcTemplate = jdbcTemplate;
        this.recordMapper = recordMapper;
        this.redisTemplate = redisTemplate;
    }

    @PostConstruct
    void init() {
        this.httpClient = RestClient.builder()
                .baseUrl(automationBaseUrl)
                .build();
    }

    /**
     * 获取价格配置（module_key='api-slider-solve'）。
     * 返回 {perCallPrice, tokenExchangeRate, perCallTokens}
     * 若未配置或禁用，perCallPrice<=0 视为禁用，返回 null。
     */
    public Map<String, Object> loadPriceConfig(Long tenantId) {
        // 优先查租户级配置，回退全局配置
        Map<String, Object> row = jdbcTemplate.queryForList(
                "SELECT * FROM ai_model_price_config WHERE deleted=0 AND enabled=1 AND module_key=? " +
                        "AND (tenant_id IS NULL OR tenant_id=?) ORDER BY CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END, id DESC LIMIT 1",
                MODULE_KEY, tenantId).stream().findFirst().orElse(null);
        if (row == null) return null;
        BigDecimal perCall = toBigDecimal(row.get("per_call_price"));
        BigDecimal rate = toBigDecimal(row.get("token_exchange_rate"));
        if (perCall == null || perCall.compareTo(BigDecimal.ZERO) <= 0) return null;
        if (rate == null || rate.compareTo(BigDecimal.ZERO) <= 0) return null;
        int perCallTokens = perCall.multiply(rate).setScale(0, RoundingMode.HALF_UP).intValue();
        if (perCallTokens < 1) perCallTokens = 1;
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("perCallPrice", perCall);
        res.put("tokenExchangeRate", rate);
        res.put("perCallTokens", perCallTokens);
        return res;
    }

    /**
     * 对外求解主入口。
     * 1. 加载价格（null=未配置，返回 503）
     * 2. 准入检查：(pending+1) × perCallTokens ≤ 余额
     * 3. pending_count += 1（Redis INCR）
     * 4. 调 Python automation-service
     * 5. 成功 → 扣费；失败 → 不扣费
     * 6. finally: pending_count -= 1
     */
    public Map<String, Object> solve(Map<String, Object> body, String clientIp) {
        Long tenantId = ApiSliderContext.tenantId();
        String apiKeyPrefix = ApiSliderContext.apiKeyPrefix();
        if (tenantId == null) throw new BizException(401, "api key context missing");

        // 1. 加载价格
        Map<String, Object> price = loadPriceConfig(tenantId);
        if (price == null) throw new BizException(503, "服务未配置价格");
        int perCallTokens = (int) price.get("perCallTokens");

        // 2. 准入检查
        String pendingKey = PENDING_KEY_PREFIX + tenantId;
        long pendingCount = getCurrentPending(pendingKey);
        long tokenBalance = queryTokenBalance(tenantId);
        long required = (pendingCount + 1) * perCallTokens;
        if (tokenBalance < required) {
            Map<String, Object> err = new LinkedHashMap<>();
            err.put("ok", false);
            err.put("status", "insufficient_balance");
            err.put("error", "余额不足。当前排队/处理中 " + pendingCount + " 个请求，本次共需 " + required + " Token，您的余额为 " + tokenBalance + "。请充值或等待队列消化。");
            err.put("pendingCount", pendingCount);
            err.put("requiredTokens", required);
            err.put("balanceTokens", tokenBalance);
            return err;
        }

        // 3. 接受请求：pending_count += 1
        redisTemplate.opsForValue().increment(pendingKey);
        String requestId = "req_" + UUID.randomUUID().toString().replace("-", "").substring(0, 24);
        String cookie = (String) body.get("cookie");
        String targetUrl = (String) body.getOrDefault("targetUrl", "https://www.goofish.com");
        long timeoutMs = toLong(body.get("timeoutMs"), 90000L);
        if (timeoutMs < 5000) timeoutMs = 5000;
        if (timeoutMs > 120000) timeoutMs = 120000;

        try {
            // 4. 调 Python
            Map<String, Object> payload = new HashMap<>();
            payload.put("requestId", requestId);
            payload.put("tenantId", tenantId);
            payload.put("apiKeyPrefix", apiKeyPrefix);
            payload.put("clientIp", clientIp);
            payload.put("cookie", cookie);
            payload.put("targetUrl", targetUrl);
            payload.put("timeoutMs", timeoutMs);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("X-Internal-Token", internalToken);
            headers.set("X-Internal-Tenant-Id", String.valueOf(tenantId));

            ResponseEntity<Map> resp = httpClient.post()
                    .uri("/api/slider/solve")
                    .headers(h -> h.addAll(headers))
                    .body(payload)
                    .retrieve()
                    .toEntity(Map.class);

            Map<String, Object> result = resp.getBody() != null ? resp.getBody() : new HashMap<>();
            String status = (String) result.getOrDefault("status", "fail");
            boolean success = "success".equals(status);

            // 5. 扣费（仅成功）
            int tokenCharged = 0;
            boolean chargeFailed = false;
            if (success) {
                int affected = jdbcTemplate.update(
                        "UPDATE sys_user SET token_balance = token_balance - ?, updated_time = NOW() " +
                                "WHERE id = ? AND tenant_id = ? AND status = 1 AND deleted = 0 AND token_balance >= ?",
                        perCallTokens, tenantId, tenantId, perCallTokens);
                if (affected == 1) {
                    tokenCharged = perCallTokens;
                    writeTokenLedger(tenantId, -perCallTokens, requestId);
                } else {
                    // 极端竞态：余额被其他操作耗尽
                    chargeFailed = true;
                    log.warn("token charge failed for tenant {} req {} (balance race)", tenantId, requestId);
                }
            }
            result.put("ok", success);
            result.put("recordId", requestId);
            result.put("tokenCharged", tokenCharged);
            if (chargeFailed) {
                result.put("tokenChargeFailed", true);
            }
            return result;
        } catch (Exception e) {
            log.error("api slider solve failed req={} tenant={}", requestId, tenantId, e);
            Map<String, Object> err = new LinkedHashMap<>();
            err.put("ok", false);
            err.put("status", "service_unavailable");
            err.put("error", "服务暂不可用：" + sanitizeError(e.getMessage()));
            err.put("recordId", requestId);
            err.put("tokenCharged", 0);
            return err;
        } finally {
            // 6. pending_count -= 1（保底不低于 0）
            Long remaining = redisTemplate.opsForValue().decrement(pendingKey);
            if (remaining != null && remaining < 0) {
                redisTemplate.opsForValue().set(pendingKey, "0");
            }
        }
    }

    private long getCurrentPending(String key) {
        String v = redisTemplate.opsForValue().get(key);
        if (v == null) return 0;
        try { return Math.max(0, Long.parseLong(v)); } catch (Exception e) { return 0; }
    }

    private long queryTokenBalance(Long tenantId) {
        try {
            Map<String, Object> row = jdbcTemplate.queryForMap(
                    "SELECT token_balance FROM sys_user WHERE id = ? AND tenant_id = ? AND status = 1 AND deleted = 0",
                    tenantId, tenantId);
            return ((Number) row.get("token_balance")).longValue();
        } catch (Exception e) {
            log.warn("query token balance failed tenant={}", tenantId, e);
            return 0;
        }
    }

    /**
     * 查询用户余额行（前台 overview 用，Task 2.8 Step 3 追加）。
     */
    public Map<String, Object> queryUserBalanceRow(Long tenantId) {
        return jdbcTemplate.queryForMap(
                "SELECT id, token_balance FROM sys_user WHERE id = ? AND tenant_id = ? AND status = 1 AND deleted = 0",
                tenantId, tenantId);
    }

    private void writeTokenLedger(Long tenantId, long change, String refNo) {
        try {
            jdbcTemplate.update(
                    "INSERT INTO token_balance_ledger (user_id, tenant_id, change_amount, change_type, ref_type, ref_no, remark, created_time, updated_time) " +
                            "VALUES (?, ?, ?, 'consume', 'api_slider', ?, 'API滑块求解扣费', NOW(), NOW())",
                    tenantId, tenantId, change, refNo);
        } catch (Exception e) {
            log.warn("write token ledger failed tenant={} ref={}", tenantId, refNo, e);
        }
    }

    private static String sanitizeError(String msg) {
        if (msg == null) return "unknown";
        // 脱敏 cookie 片段
        return msg.replaceAll("(?i)(cookie=)[^;\\s]+", "$1***")
                  .replaceAll("(?i)(_m_h5_tk=)[^;\\s]+", "$1***");
    }

    private static long toLong(Object v, long def) {
        if (v == null) return def;
        if (v instanceof Number n) return n.longValue();
        try { return Long.parseLong(v.toString()); } catch (Exception e) { return def; }
    }

    private static BigDecimal toBigDecimal(Object v) {
        if (v == null) return null;
        if (v instanceof BigDecimal b) return b;
        if (v instanceof Number n) return BigDecimal.valueOf(n.doubleValue());
        try { return new BigDecimal(v.toString()); } catch (Exception e) { return null; }
    }

    /**
     * 对账定时任务调用：扫描僵尸记录，回滚 pending_count
     */
    public void reconcileStaleRecords() {
        var staleRecords = recordMapper.selectStaleRecords();
        if (staleRecords.isEmpty()) return;
        Map<Long, Integer> tenantCount = new HashMap<>();
        for (Map<String, Object> row : staleRecords) {
            Long tenantId = ((Number) row.get("tenant_id")).longValue();
            tenantCount.merge(tenantId, 1, Integer::sum);
            jdbcTemplate.update(
                    "UPDATE xianyu_api_captcha_solve_record SET status='stale_terminated', result='stale_terminated', " +
                            "failure_reason='stale_terminated', token_charged=0, finished_at=NOW(), updated_at=NOW() WHERE id = ?",
                    row.get("id"));
        }
        tenantCount.forEach((tenantId, cnt) -> {
            String key = PENDING_KEY_PREFIX + tenantId;
            redisTemplate.opsForValue().decrement(key, cnt);
            Long remaining = redisTemplate.opsForValue().decrement(key);
            if (remaining != null && remaining < 0) {
                redisTemplate.opsForValue().set(key, "0");
            }
        });
        log.info("reconciled {} stale api slider records across {} tenants", staleRecords.size(), tenantCount.size());
    }
}
