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
 * 发货拦截规则控制器（禁止发货规则引擎）。
 * 透传到 Python automation-service 的 /api/deliveryBlockRule/* 路由。
 */
@RestController
@RequestMapping("/api/delivery-block-rules")
public class DeliveryBlockRuleController {
    private static final Logger log = LoggerFactory.getLogger(DeliveryBlockRuleController.class);

    private final AutomationClient automationClient;

    public DeliveryBlockRuleController(AutomationClient automationClient) {
        this.automationClient = automationClient;
    }

    @GetMapping
    public Result<Object> list(@RequestParam(required = false) Long accountId) {
        try {
            Map<String, Object> query = new LinkedHashMap<>();
            if (accountId != null) query.put("accountId", accountId);
            Object data = automationClient.getInternalForData("/api/deliveryBlockRule/list", query);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("查询发货拦截规则失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "发货拦截规则暂时无法查询，请稍后重试");
        }
    }

    @PostMapping
    public Result<Object> save(@RequestBody Map<String, Object> body) {
        try {
            Object data = automationClient.postInternalForData("/api/deliveryBlockRule/save", body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("保存发货拦截规则失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "发货拦截规则暂时无法保存，请稍后重试");
        }
    }

    @PostMapping("/{id}/toggle")
    public Result<Object> toggle(@PathVariable("id") Long id, @RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
            payload.put("id", id);
            Object data = automationClient.postInternalForData("/api/deliveryBlockRule/toggle", payload);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("切换发货拦截规则失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "发货拦截规则状态暂时无法切换，请稍后重试");
        }
    }

    @DeleteMapping("/{id}")
    public Result<Object> delete(@PathVariable("id") Long id) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("id", id);
            Object data = automationClient.postInternalForData(
                    "/api/deliveryBlockRule/delete?id=" + id, body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("删除发货拦截规则失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "发货拦截规则暂时无法删除，请稍后重试");
        }
    }
}
