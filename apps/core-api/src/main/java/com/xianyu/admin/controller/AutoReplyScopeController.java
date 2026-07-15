package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.service.AutomationClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 自动回复作用域管理控制器。
 * 透传到 Python automation-service 的 /api/auto-reply-scope/* 路由。
 *
 * 三档作用域：商品级 > 账号级 > 全局（NULL 不继承全局，默认关闭）。
 */
@RestController
@RequestMapping("/api/auto-reply-scope")
public class AutoReplyScopeController {
    private static final Logger log = LoggerFactory.getLogger(AutoReplyScopeController.class);

    private final AutomationClient automationClient;

    public AutoReplyScopeController(AutomationClient automationClient) {
        this.automationClient = automationClient;
    }

    /**
     * 查询商品列表及 effective auto_reply 状态。
     */
    @GetMapping("/products")
    public Result<Object> listProducts(
            @RequestParam(required = false) Long accountId) {
        try {
            Map<String, Object> query = new LinkedHashMap<>();
            if (accountId != null) query.put("accountId", accountId);
            Object data = automationClient.getInternalForData("/api/auto-reply-scope/products", query);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("查询商品作用域列表失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "自动回复商品范围暂时无法查询，请稍后重试");
        }
    }

    /**
     * 更新单个商品的 auto_reply_enabled。
     */
    @PostMapping("/product")
    public Result<Object> updateProductScope(@RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> data = automationClient.postInternalForData("/api/auto-reply-scope/product", body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("更新商品作用域失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "自动回复商品范围暂时无法更新，请稍后重试");
        }
    }

    /**
     * 更新账号级 auto_reply 启用状态。
     */
    @PostMapping("/account")
    public Result<Object> updateAccountScope(@RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> data = automationClient.postInternalForData("/api/auto-reply-scope/account", body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("更新账号作用域失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "自动回复账号范围暂时无法更新，请稍后重试");
        }
    }

    /**
     * 批量更新商品或账号的 auto_reply 状态。
     */
    @PostMapping("/batch")
    public Result<Object> batchUpdateScope(@RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> data = automationClient.postInternalForData("/api/auto-reply-scope/batch", body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("批量更新作用域失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "自动回复范围暂时无法批量更新，请稍后重试");
        }
    }

    /**
     * 查询全局开关和账号级作用域配置。
     */
    @GetMapping("/status")
    public Result<Object> getStatus(@RequestParam(required = false) Long accountId) {
        try {
            Map<String, Object> query = new LinkedHashMap<>();
            if (accountId != null) query.put("accountId", accountId);
            Object data = automationClient.getInternalForData("/api/auto-reply-scope/status", query);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("查询作用域状态失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "自动回复范围状态暂时无法查询，请稍后重试");
        }
    }
}
