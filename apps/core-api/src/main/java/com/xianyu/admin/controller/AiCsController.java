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
import java.security.MessageDigest;
import java.util.LinkedHashMap;
import java.util.List;
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

    /**
     * 列出当前用户的历史会话（最多 30 条未归档会话，按最后活跃时间倒序）。
     * 每条会话附带首条用户消息作为预览，便于用户识别会话主题。
     */
    @GetMapping("/api/ai-cs/sessions")
    public Result<List<Map<String, Object>>> listUserSessions(
            @RequestParam(value = "limit", defaultValue = "30") int limit) {
        return Result.ok(aiCsService.listUserSessions(limit));
    }

    /**
     * 恢复已关闭的会话为活跃状态，用于"继续对话"。
     * 关闭当前活跃会话（如果有），将目标会话 status=1。
     * 不允许恢复已归档的会话。
     */
    @PostMapping("/api/ai-cs/session/resume")
    public Result<Map<String, Object>> resumeSession(@RequestBody Map<String, Object> body) {
        Long sessionId = parseLong(body.get("sessionId"));
        return Result.ok(aiCsService.resumeSession(sessionId));
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
        // AI 客服对话对用户完全免费（项目规则：用户无每日免费自动回复额度限制，
        // 仅系统 AI 客服"小梦"保留额度）。因此跳过余额校验与配额提示，
        // 让所有用户都能无障碍使用 AI 客服对话功能。
        // 注意：工具调用中涉及通用模型计费的（如 polish_product_title）仍遵循按次计费规则，
        // 由 AiProviderService 在调用时单独扣费，与对话主流程解耦。
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

        return outputStream -> {
            try {
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
     *
     * 本接口在 UserJwtAuthFilter 白名单中（无 JWT），通过 X-Internal-Token 鉴权，
     * userId/tenantId 从请求体获取（Python 端 call_java_complete 传入）。
     */
    @PostMapping("/api/ai-cs/complete")
    public Result<Map<String, Object>> complete(@RequestBody Map<String, Object> body,
                                                 @RequestHeader(value = "X-Internal-Token", required = false) String internalToken) {
        // 验证内部令牌
        if (internalToken == null || internalToken.isBlank()) {
            return new Result<>(401, "缺少内部调用令牌", null);
        }
        String expectedToken = aiCsService.getInternalApiToken();
        if (expectedToken == null || expectedToken.isBlank() || !MessageDigest.isEqual(expectedToken.getBytes(StandardCharsets.UTF_8), internalToken.getBytes(StandardCharsets.UTF_8))) {
            return new Result<>(401, "内部调用令牌无效", null);
        }
        // 从请求体获取 userId/tenantId（Python 端传入）
        Long userId = parseLong(body.get("userId"));
        Long tenantId = parseLong(body.get("tenantId"));
        if (userId <= 0 || tenantId <= 0) {
            return new Result<>(400, "userId/tenantId 不能为空", null);
        }
        Long sessionId = parseLong(body.get("sessionId"));
        String content = text(body.get("content"));
        String toolCalls = text(body.get("toolCalls"));
        // content 为空但携带 toolCalls 时（二次推理生成的写操作工具），仍需落库工具调用并返回真实 toolCallId
        if ((content == null || content.isBlank()) && (toolCalls == null || toolCalls.isBlank())) {
            return Result.ok(Map.of("messageId", 0, "tokensCharged", 0, "deducted", false));
        }
        aiCsService.validateSessionOwnership(sessionId, userId, tenantId);
        Map<String, Object> res = aiCsService.appendAssistantMessageAndCharge(sessionId, content, toolCalls, userId, tenantId);
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
     *
     * 必须从 ai_cs_tool_call 表查询 tool_name 和 arguments 透传给 Python，
     * 否则 Python 无法执行工具（execute_confirmed_tool 在 tool_name 为空时直接返回失败）。
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
        // 查询 ai_cs_tool_call 记录，校验归属后透传 tool/arguments 给 Python
        Map<String, Object> toolCall = aiCsService.getToolCall(toolCallId);
        String toolName = "";
        Object argumentsObj = null;
        if (!toolCall.isEmpty()) {
            // 归属校验：tool_call 的 tenant/user 必须与当前用户一致
            Long tcTenantId = toolCall.get("tenant_id") == null ? null : ((Number) toolCall.get("tenant_id")).longValue();
            Long tcUserId = toolCall.get("user_id") == null ? null : ((Number) toolCall.get("user_id")).longValue();
            if (tcTenantId == null || !tcTenantId.equals(tenantId)
                    || tcUserId == null || !tcUserId.equals(userId)) {
                throw new BizException(403, "无权操作此工具调用");
            }
            toolName = toolCall.get("tool_name") == null ? "" : String.valueOf(toolCall.get("tool_name"));
            argumentsObj = toolCall.get("arguments");
        }
        // 调用 Python 执行工具
        Map<String, Object> req = new LinkedHashMap<>();
        req.put("sessionId", sessionId);
        req.put("userId", userId);
        req.put("tenantId", tenantId);
        req.put("toolCallId", toolCallId);
        req.put("accept", accept);
        req.put("tool", toolName);
        // arguments 在 DB 中是 JSON 字符串；Python 端会兼容字符串和 dict
        req.put("arguments", argumentsObj == null ? "{}" : argumentsObj);
        Map<String, Object> result = automationClient.postInternalForData("/api/ai-cs/tool/execute", req, tenantId);
        return Result.ok(result);
    }

    /**
     * 工具调用执行结果回调（Python 端执行后回传结果）。
     * 本接口在 UserJwtAuthFilter 白名单中（无 JWT），通过 X-Internal-Token 鉴权。
     */
    @PostMapping("/api/ai-cs/tool/result")
    public Result<Void> toolResult(@RequestBody Map<String, Object> body,
                                    @RequestHeader(value = "X-Internal-Token", required = false) String internalToken) {
        if (internalToken == null || internalToken.isBlank()) {
            return new Result<>(401, "缺少内部调用令牌", null);
        }
        String expectedToken = aiCsService.getInternalApiToken();
        if (expectedToken == null || expectedToken.isBlank() || !MessageDigest.isEqual(expectedToken.getBytes(StandardCharsets.UTF_8), internalToken.getBytes(StandardCharsets.UTF_8))) {
            return new Result<>(401, "内部调用令牌无效", null);
        }
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
