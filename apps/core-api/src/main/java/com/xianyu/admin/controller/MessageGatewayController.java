package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AutomationClient;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/msg")
public class MessageGatewayController {
    private final AutomationClient automationClient;

    public MessageGatewayController(AutomationClient automationClient) {
        this.automationClient = automationClient;
    }

    @PostMapping("/context")
    public Object context(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = withTenant(body);
        return automationClient.postInternal("/api/msg/context", payload);
    }

    @GetMapping("/online/conversations")
    public Object onlineConversations(
            @RequestParam(required = false) Long xianyuAccountId,
            @RequestParam(required = false) Long accountId,
            @RequestParam(required = false) Long cursor,
            @RequestParam(required = false) Integer pageSize,
            @RequestParam(required = false) Integer limit) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        Long finalAccountId = xianyuAccountId != null ? xianyuAccountId : accountId;
        if (finalAccountId == null) {
            return Map.of("code", 200, "msg", "操作成功", "data", java.util.Map.of("conversations", java.util.List.of(), "hasMore", false, "nextCursor", null));
        }
        java.util.Map<String, Object> params = new java.util.LinkedHashMap<>();
        params.put("xianyuAccountId", finalAccountId);
        params.put("tenantId", tenantId);
        // 新分页参数：cursor + pageSize
        if (cursor != null) {
            params.put("cursor", cursor);
        }
        int effectivePageSize = pageSize != null ? pageSize : 20;
        params.put("pageSize", Math.max(1, Math.min(effectivePageSize, 100)));
        // 兼容旧参数 limit：仅在未传 cursor 时透传
        if (cursor == null && limit != null) {
            params.put("limit", Math.max(1, Math.min(limit, 200)));
        }
        return automationClient.getInternal("/api/msg/online/conversations", params);
    }

    @PostMapping("/avatars")
    public Object avatars(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = withTenant(body);
        return automationClient.postInternal("/api/msg/avatars", payload);
    }

    @PostMapping("/list")
    public Object list(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> payload = withTenant(body);
        return automationClient.postInternal("/api/msg/list", payload);
    }

    private Map<String, Object> withTenant(Map<String, Object> body) {
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : new LinkedHashMap<>(body);
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        // 租户 ID 只信任服务端上下文，必须覆盖请求体，禁止客户端伪造 tenantId。
        payload.put("tenantId", tenantId);
        payload.put("tenant_id", tenantId);
        return payload;
    }
}
