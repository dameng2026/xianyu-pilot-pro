package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AiCsService;
import com.xianyu.admin.service.AutomationClient;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * AI 客服"小梦"后台管理 API。
 *
 * 提供统计、会话审计、消息审计、工具调用审计、计费配置、知识库 CRUD。
 * 所有接口走 /admin-api/ai-cs/* 前缀，由 AdminJwtAuthFilter 鉴权。
 */
@RestController
@RequestMapping("/admin-api/ai-cs")
public class AdminAiCsController {
    private final AiCsService aiCsService;
    private final AutomationClient automationClient;

    public AdminAiCsController(AiCsService aiCsService, AutomationClient automationClient) {
        this.aiCsService = aiCsService;
        this.automationClient = automationClient;
    }

    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        return Result.ok(aiCsService.adminStats());
    }

    @GetMapping("/sessions/page")
    public Result<PageResult<Map<String, Object>>> pageSessions(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) String status) {
        return Result.ok(aiCsService.adminPageSessions(current, size, userId, status));
    }

    @GetMapping("/messages/page")
    public Result<PageResult<Map<String, Object>>> pageMessages(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) Long sessionId,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) String role) {
        return Result.ok(aiCsService.adminPageMessages(current, size, sessionId, userId, role));
    }

    /**
     * 获取指定会话的全部消息（按时间正序，返回完整内容）。
     * 供后台会话审计"对话气泡视图"使用：一次性加载该会话的所有消息，
     * 不分页，便于以聊天气泡形式直观展示完整对话流。
     */
    @GetMapping("/messages/session/{sessionId}")
    public Result<java.util.List<Map<String, Object>>> listSessionMessages(
            @PathVariable Long sessionId) {
        return Result.ok(aiCsService.adminListSessionMessages(sessionId));
    }

    @GetMapping("/tool-calls/page")
    public Result<PageResult<Map<String, Object>>> pageToolCalls(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) Long sessionId,
            @RequestParam(required = false) String status) {
        return Result.ok(aiCsService.adminPageToolCalls(current, size, sessionId, status));
    }

    @GetMapping("/billing-config")
    public Result<Map<String, Object>> getBillingConfig() {
        return Result.ok(aiCsService.getBillingConfig());
    }

    @PutMapping("/billing-config")
    public Result<Map<String, Object>> saveBillingConfig(@RequestBody Map<String, Object> data) {
        return Result.ok(aiCsService.saveBillingConfig(data));
    }

    @GetMapping("/knowledge/categories")
    public Result<Object> knowledgeCategories() {
        return Result.ok(aiCsService.knowledgeCategories());
    }

    @GetMapping("/knowledge/page")
    public Result<PageResult<Map<String, Object>>> pageKnowledge(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String enabled) {
        return Result.ok(aiCsService.pageKnowledge(current, size, category, keyword, enabled));
    }

    @PostMapping("/knowledge")
    public Result<Map<String, Object>> saveKnowledge(@RequestBody Map<String, Object> data) {
        return Result.ok(aiCsService.saveKnowledge(data));
    }

    @GetMapping("/knowledge/{id}")
    public Result<Map<String, Object>> knowledgeDetail(@PathVariable long id) {
        return Result.ok(aiCsService.knowledgeDetail(id));
    }

    @DeleteMapping("/knowledge/{id}")
    public Result<Void> deleteKnowledge(@PathVariable long id) {
        aiCsService.deleteKnowledge(id);
        return Result.ok(null);
    }

    /**
     * 重建知识库向量索引。
     */
    @PostMapping("/knowledge/rebuild")
    public Result<Map<String, Object>> rebuildIndex() {
        try {
            Map<String, Object> result = automationClient.postInternalForData("/api/ai-cs/knowledge/rebuild", Map.of());
            return Result.ok(result);
        } catch (Exception e) {
            return Result.ok(Map.of("success", false, "message", e.getMessage()));
        }
    }
}
