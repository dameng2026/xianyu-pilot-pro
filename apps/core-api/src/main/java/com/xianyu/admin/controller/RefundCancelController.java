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
 * 退款关单（退款订单注销）配置控制器。
 * 透传到 Python automation-service 的 /api/refundCancel/* 路由。
 */
@RestController
@RequestMapping("/api/refund-cancel")
public class RefundCancelController {
    private static final Logger log = LoggerFactory.getLogger(RefundCancelController.class);

    private final AutomationClient automationClient;

    public RefundCancelController(AutomationClient automationClient) {
        this.automationClient = automationClient;
    }

    @GetMapping("/{accountId}")
    public Result<Object> get(@PathVariable("accountId") Long accountId) {
        try {
            Object data = automationClient.getInternalForData(
                    "/api/refundCancel/" + accountId, new LinkedHashMap<>());
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("查询退款关单配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "退款关单配置暂时无法查询，请稍后重试");
        }
    }

    @PutMapping("/{accountId}")
    public Result<Object> save(@PathVariable("accountId") Long accountId,
                               @RequestBody Map<String, Object> body) {
        try {
            Object data = automationClient.postInternalForData("/api/refundCancel/" + accountId, body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("保存退款关单配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "退款关单配置暂时无法保存，请稍后重试");
        }
    }
}
