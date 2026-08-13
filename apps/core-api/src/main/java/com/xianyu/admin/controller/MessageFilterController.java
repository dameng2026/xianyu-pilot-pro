package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AutomationClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 消息过滤规则控制器。
 * 透传到 Python automation-service 的 /api/messageFilters/* 路由。
 *
 * 过滤类型：
 * - skip_reply  命中关键词后跳过自动回复
 * - skip_notify 命中关键词后跳过消息通知（SSE 广播）
 */
@RestController
@RequestMapping("/api/message-filters")
public class MessageFilterController {
    private static final Logger log = LoggerFactory.getLogger(MessageFilterController.class);

    private final AutomationClient automationClient;

    public MessageFilterController(AutomationClient automationClient) {
        this.automationClient = automationClient;
    }

    /**
     * 查询消息过滤规则，支持按账号/过滤类型/关键词筛选。
     */
    @GetMapping
    public Result<Object> list(
            @RequestParam(required = false) Long accountId,
            @RequestParam(required = false) String filterType,
            @RequestParam(required = false) String keyword) {
        try {
            Map<String, Object> query = new LinkedHashMap<>();
            if (accountId != null) query.put("accountId", accountId);
            if (filterType != null && !filterType.isBlank()) query.put("filterType", filterType.trim());
            if (keyword != null && !keyword.isBlank()) query.put("keyword", keyword.trim());
            Object data = automationClient.getInternalForData("/api/messageFilters/list", query);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("查询消息过滤规则失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "消息过滤规则暂时无法查询，请稍后重试");
        }
    }

    /**
     * 新增/更新消息过滤规则。
     */
    @PostMapping
    public Result<Object> save(@RequestBody Map<String, Object> body) {
        try {
            Object data = automationClient.postInternalForData("/api/messageFilters/save", body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("保存消息过滤规则失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "消息过滤规则暂时无法保存，请稍后重试");
        }
    }

    /**
     * 删除单条消息过滤规则。
     */
    @DeleteMapping("/{id}")
    public Result<Object> delete(@PathVariable("id") Long id) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("id", id);
            Object data = automationClient.postInternalForData(
                    "/api/messageFilters/delete?id=" + id, body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("删除消息过滤规则失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "消息过滤规则暂时无法删除，请稍后重试");
        }
    }

    /**
     * 批量删除消息过滤规则。
     */
    @PostMapping("/batch-delete")
    public Result<Object> batchDelete(@RequestBody Map<String, Object> body) {
        try {
            Object data = automationClient.postInternalForData("/api/messageFilters/batchDelete", body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("批量删除消息过滤规则失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "消息过滤规则暂时无法批量删除，请稍后重试");
        }
    }

    /**
     * 启用/禁用消息过滤规则。
     */
    @PostMapping("/{id}/toggle")
    public Result<Object> toggle(@PathVariable("id") Long id, @RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
            payload.put("id", id);
            Object data = automationClient.postInternalForData("/api/messageFilters/toggle", payload);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("切换消息过滤规则状态失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "消息过滤规则状态暂时无法切换，请稍后重试");
        }
    }
}
