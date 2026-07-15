package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.XianyuConversationVO;
import com.xianyu.admin.dto.XianyuMessageVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.XianyuMessageService;
import jakarta.servlet.http.HttpServletRequest;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/conversations")
@Validated
public class XianyuMessageController {

    private final XianyuMessageService messageService;

    public XianyuMessageController(XianyuMessageService messageService) {
        this.messageService = messageService;
    }

    /**
     * 分页查询会话列表
     */
    @GetMapping
    public Result<PageResult<XianyuConversationVO>> conversations(
            @RequestParam(required = false) Long accountId,
            @RequestParam(required = false) Long xianyuAccountId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (accountId == null) accountId = xianyuAccountId;
        PageResult<XianyuConversationVO> result = messageService.conversations(tenantId, accountId, keyword, current, size);
        return Result.ok(result);
    }

    /**
     * 分页查询会话消息列表
     */
    @GetMapping("/{id}/messages")
    public Result<PageResult<XianyuMessageVO>> messages(
            @PathVariable Long id,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<XianyuMessageVO> result = messageService.messages(tenantId, id, current, size);
        return Result.ok(result);
    }


    /**
     * 更新会话状态：end/completed、transfer/transferred、close、reopen。
     */
    @PatchMapping("/{id}/status")
    public Result<XianyuConversationVO> updateStatus(@PathVariable Long id,
                                                      @RequestBody(required = false) Map<String, Object> body,
                                                      HttpServletRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        Map<String, Object> payload = body == null ? new LinkedHashMap<>() : body;
        String action = String.valueOf(payload.getOrDefault("action", payload.getOrDefault("status", "")));
        String note = String.valueOf(payload.getOrDefault("note", ""));
        XianyuConversationVO result = messageService.updateConversationStatus(tenantId, userId, id, action, note, getClientIp(request));
        return Result.ok(result);
    }

    /**
     * 标记会话已读，清零 unread_count。
     */
    @PatchMapping("/{id}/read")
    public Result<XianyuConversationVO> markRead(@PathVariable Long id, HttpServletRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        XianyuConversationVO result = messageService.markRead(tenantId, userId, id, getClientIp(request));
        return Result.ok(result);
    }

    private String getClientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }

}
