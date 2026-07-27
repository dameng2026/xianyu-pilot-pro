package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.AiBillingService;
import com.xianyu.admin.service.AiCsService;
import com.xianyu.admin.service.AutomationClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * AI 客服"小梦"前台 API。
 *
 * 三层鉴权：所有需要 sessionId 的接口都会校验 session 归属（session_id + user_id + tenant_id），
 * 确保 AI 不会操作到其他用户的数据。
 *
 * SSE 流式聊天由本 Controller 代理到 Python 端 /api/ai-cs/chat；
 * Python 端负责调用通用模型、闲聊检测、工具调用、上下文压缩等实际 AI 推理。
 */
@RestController
public class AiCsController {
    private static final Logger log = LoggerFactory.getLogger(AiCsController.class);

    private final AiCsService aiCsService;
    private final AiBillingService aiBillingService;
    private final AutomationClient automationClient;

    public AiCsController(AiCsService aiCsService,
                          AiBillingService aiBillingService,
                          AutomationClient automationClient) {
        this.aiCsService = aiCsService;
        this.aiBillingService = aiBillingService;
        this.automationClient = automationClient;
    }

    @PostMapping("/api/ai-cs/session/create")
    public Result<Map<String, Object>> createSession() {
        return Result.ok(aiCsService.createSession());
    }

    @GetMapping("/api/ai-cs/session/current")
    public Result<Map<String, Object>> currentSession() {
        return Result.ok(aiCsService.currentSession());
    }

    @PostMapping("/api/ai-cs/session/close")
    public Result<Void> closeSession(@RequestBody Map<String, Object> body) {
        Long sessionId = parseLong(body.get("sessionId"));
        aiCsService.closeSession(sessionId);
        return Result.ok(null);
    }

    @GetMapping("/api/ai-cs/messages")
    public Result<Object> listMessages(@RequestParam("sessionId") Long sessionId,
                                       @RequestParam(value = "limit", defaultValue = "100") int limit) {
        return Result.ok(aiCsService.listMessages(sessionId, limit));
    }

    @GetMapping("/api/ai-cs/config")
    public Result<Map<String, Object>> getConfig() {
        Map<String, Object> config = aiCsService.getBillingConfig();
        // 附带余额信息，便于前端展示
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        try {
            Map<String, Object> balance = aiBillingService.balance(userId);
            config.put("balance", balance.get("tokenBalance"));
            config.put("perCallTokens", balance.get("perCallTokens"));
        } catch (Exception e) {
            config.put("balance", 0);
        }
        return Result.ok(config);
    }

    /**
     * 保存当前租户的 AI 客服计费配置（用户每日免费额度、每条扣费 Token 数等）。
     * 仅租户管理员可调用；saveBillingConfig 内部以 UserContext.getTenantId() 隔离。
     */
    @PutMapping("/api/ai-cs/billing-config")
    public Result<Map<String, Object>> saveBillingConfig(@RequestBody Map<String, Object> body) {
        return Result.ok(aiCsService.saveBillingConfig(body));
    }


    /**
     * SSE 流式聊天。
     *
     * 流程：
     * 1. 校验会话归属（三层鉴权）
     * 2. 校验 Token 余额（不足时返回 SSE error 事件，前端弹出充值按钮）
     * 3. 持久化用户消息
     * 4. 闲聊检测：若为闲聊，自增 casual_count，达到阈值时通过 SSE casual_remind 事件提醒（仅一次）
     * 5. 通过 AutomationClient 代理到 Python /api/ai-cs/chat，SSE 流式回传
     * 6. Python 端完成后通过回调写入 assistant 消息并扣费（见 /api/ai-cs/complete）
     */
    @PostMapping(value = "/api/ai-cs/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public StreamingResponseBody chat(@RequestBody Map<String, Object> body) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        Long sessionId = parseLong(body.get("sessionId"));
        String message = text(body.get("message"));
        if (message == null || message.isBlank()) {
            return out -> writeSseError(out, "error", "消息不能为空");
        }
        // 校验会话归属
        try {
            aiCsService.validateSessionOwnership(sessionId, userId, tenantId);
        } catch (BizException e) {
            return out -> writeSseError(out, "error", e.getMessage());
        }
        // 每日免费额度判断：今日已发送 user 消息数（不含本条）
        int dailyFreeQuota = aiCsService.getDailyFreeQuota(tenantId);
        int todayUserCountBefore = aiCsService.getTodayUserMessageCount(userId, tenantId);
        boolean freeQuotaAvailable = dailyFreeQuota > 0 && todayUserCountBefore < dailyFreeQuota;
        // 余额校验：仅当本条不在免费额度内时才校验
        int perMessageTokens = aiCsService.getPerMessageTokens(tenantId);
        long balance;
        try {
            Map<String, Object> bal = aiBillingService.balance(userId);
            balance = ((Number) bal.get("tokenBalance")).longValue();
        } catch (Exception e) {
            return out -> writeSseError(out, "error", "余额查询失败，请稍后重试");
        }
        if (!freeQuotaAvailable && balance < perMessageTokens) {
            return out -> {
                String ev = "event: insufficient_balance\n" +
                        "data: {\"type\":\"insufficient_balance\",\"message\":\"今日免费额度已用完且 Token 余额不足，请充值后继续\",\"freeQuota\":" + dailyFreeQuota + ",\"usedQuota\":" + todayUserCountBefore + ",\"buttons\":[{\"type\":\"recharge\",\"label\":\"立即充值\"}]}\n\n";
                out.write(ev.getBytes(StandardCharsets.UTF_8));
                out.flush();
            };
        }
        // 持久化用户消息
        boolean isCasual = aiCsService.isCasualMessage(message);
        aiCsService.appendUserMessage(sessionId, message, isCasual);
        // 闲聊计数
        boolean shouldRemind = false;
        if (isCasual) {
            shouldRemind = aiCsService.bumpCasualAndShouldRemind(sessionId);
        }
        final boolean finalShouldRemind = shouldRemind;
        // 消息计数 + 判断是否超限
        Map<String, Object> countInfo = aiCsService.bumpMessageCount(sessionId);
        int currentCount = ((Number) countInfo.get("currentCount")).intValue();
        int maxCount = ((Number) countInfo.get("maxCount")).intValue();
        boolean exceeded = Boolean.TRUE.equals(countInfo.get("exceeded"));
        // 免费额度状态：本条发送后，今日已用条数
        final int todayUsedAfter = todayUserCountBefore + 1;
        final boolean quotaExceededNow = !freeQuotaAvailable;
        final int finalDailyFreeQuota = dailyFreeQuota;
        final int finalPerMessageTokens = perMessageTokens;
        final long finalBalance = balance;

        return outputStream -> {
            try {
                // 若免费额度已用完，发送 quota_exceeded 事件（不阻断，告知用户本条将扣费）
                if (quotaExceededNow) {
                    String ev = "event: quota_exceeded\n" +
                            "data: {\"type\":\"quota_exceeded\",\"message\":\"今日免费额度已用完，后续每条消息将扣费 " + finalPerMessageTokens + " Token\",\"dailyFreeQuota\":" + finalDailyFreeQuota + ",\"usedQuota\":" + todayUsedAfter + ",\"perMessageTokens\":" + finalPerMessageTokens + ",\"balance\":" + finalBalance + "}\n\n";
                    outputStream.write(ev.getBytes(StandardCharsets.UTF_8));
                    outputStream.flush();
                } else if (todayUsedAfter >= finalDailyFreeQuota) {
                    // 本条是免费额度最后一条，提醒用户下一条开始扣费
                    String ev = "event: quota_warning\n" +
                            "data: {\"type\":\"quota_warning\",\"message\":\"今日免费额度还剩 0 条，下一条消息将开始扣费 " + finalPerMessageTokens + " Token/条\",\"dailyFreeQuota\":" + finalDailyFreeQuota + ",\"usedQuota\":" + todayUsedAfter + ",\"perMessageTokens\":" + finalPerMessageTokens + "}\n\n";
                    outputStream.write(ev.getBytes(StandardCharsets.UTF_8));
                    outputStream.flush();
                }
                // 若超限，先发送 context_exceeded 事件（不阻断，让用户在前端选择新会话或压缩）
                if (exceeded) {
                    String ev = "event: context_exceeded\n" +
                            "data: {\"message\":\"当前会话已超出上下文上限\",\"currentCount\":" + currentCount + ",\"maxCount\":" + maxCount + ",\"buttons\":[{\"type\":\"new_session\",\"label\":\"开启新会话\"},{\"type\":\"compress\",\"label\":\"压缩上下文\"}]}\n\n";
                    outputStream.write(ev.getBytes(StandardCharsets.UTF_8));
                    outputStream.flush();
                }
                // 若需闲聊提醒，先发送 casual_remind 事件
                if (finalShouldRemind) {
                    String reminder = aiCsService.getBillingConfig(tenantId).getOrDefault("casualReminderText", AiCsService.DEFAULT_CASUAL_REMINDER).toString();
                    String ev = "event: casual_remind\ndata: {\"message\":\"" + escapeJson(reminder) + "\"}\n\n";
                    outputStream.write(ev.getBytes(StandardCharsets.UTF_8));
                    outputStream.flush();
                }
                // 代理到 Python SSE
                Map<String, Object> query = new LinkedHashMap<>();
                query.put("sessionId", sessionId);
                query.put("userId", userId);
                query.put("tenantId", tenantId);
                query.put("message", message);
                automationClient.streamSse("/api/ai-cs/chat", query, outputStream, tenantId);
            } catch (Exception e) {
                log.error("AI 客服 SSE 代理失败 sessionId={}, userId={}", sessionId, userId, e);
                writeSseError(outputStream, "error", "AI 客服暂时不可用，请稍后重试");
            }
        };
    }

    /**
     * Python 端 SSE 完成后的回调：写入 assistant 消息并扣费。
     * 由 Python 端在 SSE 流结束前调用，确保消息持久化与扣费。
     */
    @PostMapping("/api/ai-cs/complete")
    public Result<Map<String, Object>> complete(@RequestBody Map<String, Object> body) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        Long sessionId = parseLong(body.get("sessionId"));
        String content = text(body.get("content"));
        String toolCalls = text(body.get("toolCalls"));
        if (content == null || content.isBlank()) {
            return Result.ok(Map.of("messageId", 0, "tokensCharged", 0, "deducted", false));
        }
        aiCsService.validateSessionOwnership(sessionId, userId, tenantId);
        Map<String, Object> res = aiCsService.appendAssistantMessageAndCharge(sessionId, content, toolCalls);
        return Result.ok(res);
    }

    /**
     * 上下文压缩（不扣费）。
     * Java 端调用 Python 生成摘要，然后将摘要写入新会话。
     */
    @PostMapping("/api/ai-cs/compress")
    public Result<Map<String, Object>> compress(@RequestBody Map<String, Object> body) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        Long sessionId = parseLong(body.get("sessionId"));
        aiCsService.validateSessionOwnership(sessionId, userId, tenantId);
        // 调用 Python 生成摘要
        Map<String, Object> req = new LinkedHashMap<>();
        req.put("sessionId", sessionId);
        req.put("userId", userId);
        req.put("tenantId", tenantId);
        Map<String, Object> pyResp;
        try {
            pyResp = automationClient.postInternalForData("/api/ai-cs/compress", req, tenantId);
        } catch (Exception e) {
            log.error("调用 Python 上下文压缩失败 sessionId={}", sessionId, e);
            throw new BizException(503, "上下文压缩服务暂时不可用");
        }
        String summary = text(pyResp.get("summary"));
        if (summary == null || summary.isBlank()) {
            throw new BizException(503, "上下文压缩未返回有效摘要");
        }
        return Result.ok(aiCsService.compressContext(sessionId, summary));
    }

    /**
     * 工具调用确认/拒绝。
     */
    @PostMapping("/api/ai-cs/tool/confirm")
    public Result<Map<String, Object>> confirmTool(@RequestBody Map<String, Object> body) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        Long sessionId = parseLong(body.get("sessionId"));
        Long toolCallId = parseLong(body.get("toolCallId"));
        boolean accept = Boolean.TRUE.equals(body.get("accept"));
        aiCsService.validateSessionOwnership(sessionId, userId, tenantId);
        aiCsService.updateToolCallStatus(toolCallId, accept ? "confirmed" : "rejected", null);
        // 调用 Python 执行工具
        Map<String, Object> req = new LinkedHashMap<>();
        req.put("sessionId", sessionId);
        req.put("userId", userId);
        req.put("tenantId", tenantId);
        req.put("toolCallId", toolCallId);
        req.put("accept", accept);
        Map<String, Object> result = automationClient.postInternalForData("/api/ai-cs/tool/execute", req, tenantId);
        return Result.ok(result);
    }

    /**
     * 工具调用执行结果回调（Python 端执行后回传结果）。
     */
    @PostMapping("/api/ai-cs/tool/result")
    public Result<Void> toolResult(@RequestBody Map<String, Object> body) {
        Long toolCallId = parseLong(body.get("toolCallId"));
        String status = text(body.get("status"));
        String resultJson = text(body.get("result"));
        aiCsService.updateToolCallStatus(toolCallId, status, resultJson);
        return Result.ok(null);
    }

    // ==================== 工具方法 ====================

    private static long parseLong(Object o) {
        if (o == null) return 0L;
        try { return Long.parseLong(String.valueOf(o)); } catch (Exception e) { return 0L; }
    }

    private static String text(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    private static void writeSseError(java.io.OutputStream out, String type, String message) {
        try {
            String ev = "event: " + type + "\ndata: {\"type\":\"" + type + "\",\"message\":\"" + escapeJson(message) + "\"}\n\n";
            out.write(ev.getBytes(StandardCharsets.UTF_8));
            out.flush();
        } catch (Exception ignored) {}
    }

    private static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
    }
}
