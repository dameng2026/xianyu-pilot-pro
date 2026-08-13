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
 * 默认回复控制器。
 * 透传到 Python automation-service 的 /api/defaultReply/* 路由。
 *
 * 账号级兜底回复：未命中关键词规则且 AI 客服关闭时生效；
 * 支持 text（文本/图片）与 api（外部接口）两种类型，reply_once 可限制同一买家仅回复一次。
 */
@RestController
@RequestMapping("/api/default-reply")
public class DefaultReplyController {
    private static final Logger log = LoggerFactory.getLogger(DefaultReplyController.class);

    private final AutomationClient automationClient;

    public DefaultReplyController(AutomationClient automationClient) {
        this.automationClient = automationClient;
    }

    /**
     * 查询当前租户所有账号的默认回复配置。
     */
    @GetMapping
    public Result<Object> list() {
        try {
            Object data = automationClient.getInternalForData("/api/defaultReply/list", new LinkedHashMap<>());
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("查询默认回复配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "默认回复配置暂时无法查询，请稍后重试");
        }
    }

    /**
     * 查询指定账号的默认回复配置。
     */
    @GetMapping("/{accountId}")
    public Result<Object> get(@PathVariable("accountId") Long accountId) {
        try {
            Object data = automationClient.getInternalForData(
                    "/api/defaultReply/" + accountId, new LinkedHashMap<>());
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("查询默认回复配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "默认回复配置暂时无法查询，请稍后重试");
        }
    }

    /**
     * 保存指定账号的默认回复配置。
     */
    @PostMapping("/{accountId}")
    public Result<Object> save(@PathVariable("accountId") Long accountId,
                               @RequestBody Map<String, Object> body) {
        try {
            Object data = automationClient.postInternalForData("/api/defaultReply/" + accountId, body);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("保存默认回复配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "默认回复配置暂时无法保存，请稍后重试");
        }
    }

    /**
     * 删除指定账号的默认回复配置。
     */
    @DeleteMapping("/{accountId}")
    public Result<Object> delete(@PathVariable("accountId") Long accountId) {
        try {
            Object data = automationClient.deleteInternalForData("/api/defaultReply/" + accountId);
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("删除默认回复配置失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "默认回复配置暂时无法删除，请稍后重试");
        }
    }

    /**
     * 清空指定账号的默认回复记录（reply_once 计数）。
     */
    @PostMapping("/{accountId}/clear-records")
    public Result<Object> clearRecords(@PathVariable("accountId") Long accountId) {
        try {
            Object data = automationClient.postInternalForData(
                    "/api/defaultReply/" + accountId + "/clearRecords", new LinkedHashMap<>());
            return Result.ok(data);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            log.error("清空默认回复记录失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "默认回复记录暂时无法清空，请稍后重试");
        }
    }
}
