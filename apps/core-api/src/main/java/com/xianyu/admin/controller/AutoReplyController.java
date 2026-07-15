package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.AutoReplyRuleDTO;
import com.xianyu.admin.dto.AutoReplyRuleVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AutoReplyService;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auto-reply/rules")
@Validated
public class AutoReplyController {

    private final AutoReplyService autoReplyService;

    public AutoReplyController(AutoReplyService autoReplyService) {
        this.autoReplyService = autoReplyService;
    }

    /**
     * 分页查询自动回复规则列表
     */
    @GetMapping
    public Result<PageResult<AutoReplyRuleVO>> rules(
            @RequestParam(required = false) Long accountId,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<AutoReplyRuleVO> result = autoReplyService.rules(tenantId, accountId, current, size);
        return Result.ok(result);
    }

    /**
     * 创建自动回复规则
     */
    @PostMapping
    public Result<Void> createRule(@Valid @RequestBody AutoReplyRuleDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        autoReplyService.createRule(tenantId, dto);
        return Result.ok(null);
    }

    /**
     * 更新自动回复规则
     */
    @PutMapping("/{id}")
    public Result<Void> updateRule(@PathVariable Long id, @Valid @RequestBody AutoReplyRuleDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        autoReplyService.updateRule(tenantId, id, dto);
        return Result.ok(null);
    }

    /**
     * 预览买家消息会命中哪条规则，并输出安全策略。
     */
    @PostMapping("/preview")
    public Result<Map<String, Object>> preview(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long accountId = body.get("accountId") == null ? null : Long.valueOf(String.valueOf(body.get("accountId")));
        String message = String.valueOf(body.getOrDefault("message", ""));
        return Result.ok(autoReplyService.preview(tenantId, accountId, message));
    }


    /**
     * 自动回复命中/预览日志。
     */
    @GetMapping("/logs")
    public Result<PageResult<Map<String, Object>>> logs(
            @RequestParam(required = false) Long accountId,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(autoReplyService.logs(tenantId, accountId, current, size));
    }

    /**
     * 自动回复命中统计。
     */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats(@RequestParam(defaultValue = "7") int days) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(autoReplyService.stats(tenantId, days));
    }

    /**
     * 删除自动回复规则（软删除）
     */
    @DeleteMapping("/{id}")
    public Result<Void> deleteRule(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        autoReplyService.deleteRule(tenantId, id);
        return Result.ok(null);
    }
}
