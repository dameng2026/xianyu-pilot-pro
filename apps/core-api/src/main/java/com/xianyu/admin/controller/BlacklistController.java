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
 * 个人黑名单控制器（发货拦截）。
 * 透传到 Python automation-service 的 /api/blacklist/personal/* 路由。
 *
 * 命中黑名单的买家在对应账号（可选商品范围）下禁止自动发货。
 */
@RestController
@RequestMapping("/api/blacklist/personal")
public class BlacklistController {
    private static final Logger log = LoggerFactory.getLogger(BlacklistController.class);

    private final AutomationClient automationClient;

    public BlacklistController(AutomationClient automationClient) {
        this.automationClient = automationClient;
    }

    /**
     * 查询个人黑名单。
     */
    @GetMapping
    public Result<Object> list(
            @RequestParam(required = false) Long accountId,
            @RequestParam(required = false) String keyword) {
        try {
            Map<String, Object> query = new LinkedHashMap<>();
            if (accountId != null) query.put("accountId", accountId);
            if (keyword != null && !keyword.isBlank()) query.put("keyword", keyword.trim());
            Object data = automationClient.getInternalForData("/api/blacklist/personal/list", query);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("查询个人黑名单失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "个人黑名单暂时无法查询，请稍后重试");
        }
    }

    /**
     * 新增/更新个人黑名单。
     */
    @PostMapping
    public Result<Object> save(@RequestBody Map<String, Object> body) {
        try {
            Object data = automationClient.postInternalForData("/api/blacklist/personal/save", body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("保存个人黑名单失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "个人黑名单暂时无法保存，请稍后重试");
        }
    }

    /**
     * 删除个人黑名单记录。
     */
    @DeleteMapping("/{id}")
    public Result<Object> delete(@PathVariable("id") Long id) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("id", id);
            Object data = automationClient.postInternalForData(
                    "/api/blacklist/personal/delete?id=" + id, body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("删除个人黑名单失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "个人黑名单暂时无法删除，请稍后重试");
        }
    }

    /**
     * 启用/禁用个人黑名单记录。
     */
    @PostMapping("/{id}/toggle")
    public Result<Object> toggle(@PathVariable("id") Long id, @RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
            payload.put("id", id);
            Object data = automationClient.postInternalForData("/api/blacklist/personal/toggle", payload);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("切换个人黑名单状态失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "个人黑名单状态暂时无法切换，请稍后重试");
        }
    }
}
