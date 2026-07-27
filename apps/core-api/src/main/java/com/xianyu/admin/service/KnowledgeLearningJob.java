package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.Statement;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

@Service
public class KnowledgeLearningJob {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeLearningJob.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final AtomicBoolean RUNNING = new AtomicBoolean(false);

    private final JdbcTemplate jdbc;
    private RestClient restClient;

    @Value("${xianyu.ai-cs.kb-learning.enabled:true}")
    private boolean enabled;

    @Value("${xianyu.ai-cs.kb-learning.cron:0 0 2 * * ?}")
    private String cron;

    @Value("${xianyu.ai-cs.kb-learning.lookback-hours:24}")
    private int lookbackHours;

    @Value("${xianyu.ai-cs.kb-learning.ai-ratio-threshold:0.6}")
    private double aiRatioThreshold;

    @Value("${xianyu.ai-cs.kb-learning.min-conversation-messages:5}")
    private int minConversationMessages;

    @Value("${xianyu.ai-cs.kb-learning.max-conversations-per-run:500}")
    private int maxConversationsPerRun;

    @Value("${xianyu.ai-cs.kb-learning.llm-batch-size:5}")
    private int llmBatchSize;

    @Value("${xianyu.ai-cs.kb-learning.llm-concurrency:3}")
    private int llmConcurrency;

    @Value("${xianyu.ai-cs.kb-learning.auto-approve:true}")
    private boolean autoApprove;

    @Value("${xianyu.ai-cs.kb-learning.max-cost-yuan-per-run:50}")
    private double maxCostYuanPerRun;

    @Value("${xianyu.ai-cs.kb-learning.automation-base-url:http://localhost:12401}")
    private String automationBaseUrl;

    @Value("${xianyu.automation.internal-token:}")
    private String internalToken;

    public KnowledgeLearningJob(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * 有界线程池：手动触发学习任务时使用，避免裸 new Thread。
     * 单线程 + 有界队列，保证手动触发与定时任务不会并发执行（runLearning 内部还有 RUNNING CAS 兜底）。
     */
    private static final java.util.concurrent.ExecutorService LEARNING_ASYNC_POOL =
            java.util.concurrent.Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "kb-learning-async");
                t.setDaemon(true);
                t.setUncaughtExceptionHandler((thread, ex) ->
                        org.slf4j.LoggerFactory.getLogger(KnowledgeLearningJob.class)
                                .error("kb-learning async task failed", ex));
                return t;
            });

    /**
     * 异步触发学习任务（供 AdminLearnedKbController 手动触发使用）。
     * 与定时任务 {@link #runLearning()} 共享 RUNNING 标志，保证幂等不并发。
     */
    public void runLearningAsync() {
        LEARNING_ASYNC_POOL.submit(this::runLearning);
    }

    @PostConstruct
    void init() {
        // 强制 HTTP/1.1：automation-service 的 uvicorn（httptools 实现）不支持 h2c 升级，
        // 默认 JDK HttpClient 会尝试 HTTP/2 升级导致 uvicorn 报
        // "Unsupported upgrade request" + "Invalid HTTP request received" → 400 Bad Request
        HttpClient jdkClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(10))
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(jdkClient);
        requestFactory.setReadTimeout(Duration.ofSeconds(300));  // 学习任务可能较长
        this.restClient = RestClient.builder()
                .baseUrl(automationBaseUrl)
                .requestFactory(requestFactory)
                .build();
    }

    @Scheduled(cron = "${xianyu.ai-cs.kb-learning.cron:0 0 2 * * ?}")
    public void runLearning() {
        if (!enabled) {
            log.info("kb-learning job disabled, skip");
            return;
        }
        // 防重入：避免定时任务与手动 trigger 并发执行，或前次未结束后再次启动
        if (!RUNNING.compareAndSet(false, true)) {
            log.warn("kb-learning job already running, skip this trigger");
            return;
        }
        try {
            doRunLearning();
        } finally {
            RUNNING.set(false);
        }
    }

    private void doRunLearning() {
        // Java 端预生成 batchId 仅用于写 running 日志；自动审核时改用 Python 返回的 batch_id
        String localBatchId = "kb-learn-" + System.currentTimeMillis();
        LocalDateTime startedAt = LocalDateTime.now();

        Long logId = insertLog(localBatchId, startedAt);

        try {
            Map<String, Object> config = new HashMap<>();
            config.put("lookback_hours", lookbackHours);
            config.put("ai_ratio_threshold", aiRatioThreshold);
            config.put("min_conversation_messages", minConversationMessages);
            config.put("max_conversations_per_run", maxConversationsPerRun);
            config.put("llm_batch_size", llmBatchSize);
            config.put("llm_concurrency", llmConcurrency);
            config.put("max_cost_yuan_per_run", maxCostYuanPerRun);

            String path = "/api/kb-learning/run";
            log.info("kb-learning localBatchId={} calling {}{}", localBatchId, automationBaseUrl, path);

            var spec = restClient.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON);
            if (internalToken != null && !internalToken.isBlank()) {
                spec.header("X-Internal-Token", internalToken);
                // 学习作业是系统级跨租户任务，Python deps.py 要求内部调用必须带 X-Internal-Tenant-Id，
                // 传 1（默认主租户）只为通过鉴权；Python 端 run_learning_job 不按 tenant_id 过滤会话
                spec.header("X-Internal-Tenant-Id", "1");
            }
            Map<String, Object> body = spec.body(config).retrieve().body(Map.class);
            @SuppressWarnings("unchecked")
            Map<String, Object> data = body != null ? (Map<String, Object>) body.get("data") : null;

            if (data == null) {
                throw new RuntimeException("empty response from automation-service");
            }

            // 用 Python 返回的真实 batch_id 做自动审核（Python 写入 ai_cs_learned_kb.learn_batch_id 的是这个值）
            String pyBatchId = (String) data.get("batch_id");
            if (pyBatchId == null || pyBatchId.isBlank()) {
                pyBatchId = localBatchId;  // 兜底
                log.warn("kb-learning Python returned empty batch_id, fallback to localBatchId={}", localBatchId);
            }

            // 同步更新日志表中的 batch_id 为 Python 真实值，便于后续按 batch_id 查询
            if (logId != null && !pyBatchId.equals(localBatchId)) {
                jdbc.update("UPDATE ai_cs_kb_learning_log SET batch_id=? WHERE id=?", pyBatchId, logId);
            }

            if (autoApprove) {
                int approved = jdbc.update(
                    "UPDATE ai_cs_learned_kb SET review_status='approved', reviewed_time=NOW() " +
                    "WHERE review_status='pending' AND learn_batch_id=? AND deleted=0",
                    pyBatchId
                );
                log.info("kb-learning pyBatchId={} auto-approved {} items", pyBatchId, approved);
            }

            updateLogSuccess(logId, data);
            log.info("kb-learning pyBatchId={} finished: {}", pyBatchId, data);

        } catch (Exception e) {
            log.error("kb-learning localBatchId={} failed errorType={}", localBatchId, e.getClass().getSimpleName(), e);
            updateLogFailed(logId, e);
        }
    }

    private Long insertLog(String batchId, LocalDateTime startedAt) {
        Map<String, Object> snapshot = new HashMap<>();
        snapshot.put("lookback_hours", lookbackHours);
        snapshot.put("ai_ratio_threshold", aiRatioThreshold);
        snapshot.put("max_conversations_per_run", maxConversationsPerRun);

        try {
            // 序列化提前到 lambda 外执行：lambda 不允许抛出受检异常 JsonProcessingException
            String snapshotJson = MAPPER.writeValueAsString(snapshot);
            var keyHolder = new GeneratedKeyHolder();
            jdbc.update((Connection con) -> {
                PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO ai_cs_kb_learning_log " +
                    "(batch_id, started_at, status, config_snapshot, deleted, created_time) " +
                    "VALUES (?, ?, 'running', ?, 0, NOW())",
                    Statement.RETURN_GENERATED_KEYS
                );
                ps.setString(1, batchId);
                ps.setObject(2, startedAt);
                ps.setString(3, snapshotJson);
                return ps;
            }, keyHolder);
            return keyHolder.getKey() == null ? null : keyHolder.getKey().longValue();
        } catch (Exception e) {
            log.error("insert learning log failed", e);
            return null;
        }
    }

    private void updateLogSuccess(Long logId, Map<String, Object> data) {
        if (logId == null) return;
        try {
            jdbc.update(
                "UPDATE ai_cs_kb_learning_log SET " +
                "finished_at=NOW(), status=?, total_conversations=?, kept_conversations=?, " +
                "rejected_by_ai_ratio=?, extracted_items=?, deduplicated_items=?, " +
                "llm_tokens_used=?, llm_cost_yuan=? WHERE id=?",
                (String) data.getOrDefault("status", "success"),
                toInt(data.get("total_conversations"), 0),
                toInt(data.get("kept_conversations"), 0),
                toInt(data.get("rejected_by_ai_ratio"), 0),
                toInt(data.get("extracted_items"), 0),
                toInt(data.get("deduplicated_items"), 0),
                toInt(data.get("llm_tokens_used"), 0),
                toDouble(data.get("llm_cost_yuan"), 0.0),
                logId
            );
        } catch (Exception e) {
            log.error("update learning log success failed", e);
        }
    }

    /** 安全转换：兼容 Number / String 两种类型，避免 Python 返回 String 时 ClassCastException */
    private static int toInt(Object v, int def) {
        if (v == null) return def;
        if (v instanceof Number) return ((Number) v).intValue();
        try { return Integer.parseInt(String.valueOf(v).trim()); }
        catch (NumberFormatException e) { return def; }
    }

    private static double toDouble(Object v, double def) {
        if (v == null) return def;
        if (v instanceof Number) return ((Number) v).doubleValue();
        try { return Double.parseDouble(String.valueOf(v).trim()); }
        catch (NumberFormatException e) { return def; }
    }

    private void updateLogFailed(Long logId, Exception e) {
        if (logId == null) return;
        try {
            jdbc.update(
                "UPDATE ai_cs_kb_learning_log SET " +
                "finished_at=NOW(), status='failed', error_message=? WHERE id=?",
                e.getClass().getSimpleName() + ": " + e.getMessage(),
                logId
            );
        } catch (Exception ex) {
            log.error("update learning log failed failed", ex);
        }
    }
}
