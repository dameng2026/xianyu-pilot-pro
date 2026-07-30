package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.GrowthService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 前台用户增长合伙人接口（/api/growth/*）。
 * 所有接口需用户 JWT 登录（UserJwtAuthFilter 默认拦截 /api/*）。
 */
@RestController
@RequestMapping("/api/growth")
public class UserGrowthController {

    private final GrowthService growthService;

    public UserGrowthController(GrowthService growthService) {
        this.growthService = growthService;
    }

    /** 仪表盘统计（统计卡片数据 + 代理等级 + 配置） */
    @GetMapping("/dashboard")
    public Result<Map<String, Object>> dashboard() {
        Long userId = requireUser();
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(growthService.getUserDashboard(userId, tenantId == null ? 0 : tenantId));
    }

    /** 收益趋势（近 N 天） */
    @GetMapping("/trend")
    public Result<Map<String, Object>> trend(@RequestParam(defaultValue = "30") int days) {
        Long userId = requireUser();
        return Result.ok(growthService.getRevenueTrend(userId, days));
    }

    /** 拉新排行榜 */
    @GetMapping("/leaderboard")
    public Result<List<Map<String, Object>>> leaderboard(@RequestParam(defaultValue = "10") int limit) {
        return Result.ok(growthService.getLeaderboard(limit));
    }

    /** 二级用户明细 */
    @GetMapping("/referrals")
    public Result<Map<String, Object>> referrals(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String tierCode,
            @RequestParam(required = false) String status) {
        Long userId = requireUser();
        if (size > 100) size = 100;
        return Result.ok(growthService.listReferralDetails(userId, page, size, keyword, tierCode, status));
    }

    /** 我的邀请码列表 */
    @GetMapping("/invite-codes")
    public Result<List<Map<String, Object>>> myInviteCodes() {
        Long userId = requireUser();
        // 确保有默认邀请码
        Long tenantId = TenantContext.getCurrentTenantId();
        growthService.ensureInviteCode(userId, tenantId == null ? 0 : tenantId);
        return Result.ok(growthService.listInviteCodes(userId));
    }

    /** 创建邀请码 */
    @PostMapping("/invite-codes")
    public Result<Map<String, Object>> createInviteCode(@RequestBody Map<String, Object> body) {
        Long userId = requireUser();
        Long tenantId = TenantContext.getCurrentTenantId();
        String channel = body == null ? null : (String) body.get("channel");
        String remark = body == null ? null : (String) body.get("remark");
        return Result.ok(growthService.createInviteCode(userId, tenantId == null ? 0 : tenantId, channel, remark));
    }

    /** 获取推广链接 */
    @GetMapping("/promote-link")
    public Result<Map<String, Object>> promoteLink(HttpServletRequest request) {
        Long userId = requireUser();
        Long tenantId = TenantContext.getCurrentTenantId();
        String baseUrl = resolveBaseUrl(request);
        String link = growthService.getPromoteLink(userId, tenantId == null ? 0 : tenantId, baseUrl);
        return Result.ok(Map.of("link", link, "code", extractCode(link)));
    }

    /** 代理等级配置（前台展示用） */
    @GetMapping("/tier-config")
    public Result<List<Map<String, Object>>> tierConfig() {
        return Result.ok(growthService.getTierConfigs());
    }

    /** 我的余额（用于个人中心卡片） */
    @GetMapping("/balance")
    public Result<Map<String, Object>> balance() {
        Long userId = requireUser();
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(growthService.getUserDashboard(userId, tenantId == null ? 0 : tenantId));
    }

    /** 提现申请 */
    @PostMapping("/withdrawal")
    public Result<Map<String, Object>> requestWithdrawal(@RequestBody Map<String, Object> body) {
        Long userId = requireUser();
        Long tenantId = TenantContext.getCurrentTenantId();
        if (body == null) throw new BizException(400, "请求体不能为空");
        long amount = parseLong(body.get("amount"));
        String paymentMethod = (String) body.get("paymentMethod");
        String paymentAccount = (String) body.get("paymentAccount");
        String paymentName = (String) body.get("paymentName");
        if (paymentAccount == null || paymentAccount.isBlank()) {
            throw new BizException(400, "收款信息不能为空");
        }
        return Result.ok(growthService.requestWithdrawal(userId, tenantId == null ? 0 : tenantId,
                amount, paymentMethod, paymentAccount, paymentName));
    }

    /** 我的提现记录 */
    @GetMapping("/withdrawals")
    public Result<List<Map<String, Object>>> myWithdrawals(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        Long userId = requireUser();
        if (size > 100) size = 100;
        return Result.ok(growthService.listUserWithdrawals(userId, page, size));
    }

    // ==================== 工具 ====================

    private Long requireUser() {
        Long userId = TenantContext.getCurrentUserId();
        if (userId == null || userId <= 0) throw new BizException(401, "请先登录");
        return userId;
    }

    private long parseLong(Object o) {
        if (o == null) throw new BizException(400, "金额不能为空");
        try {
            if (o instanceof Number) return ((Number) o).longValue();
            return Long.parseLong(String.valueOf(o));
        } catch (Exception e) {
            throw new BizException(400, "金额格式不正确");
        }
    }

    private String resolveBaseUrl(HttpServletRequest request) {
        String scheme = request.getScheme();
        String serverName = request.getServerName();
        int port = request.getServerPort();
        String context = request.getContextPath();
        StringBuilder sb = new StringBuilder().append(scheme).append("://").append(serverName);
        if (port != 80 && port != 443) sb.append(":").append(port);
        sb.append(context);
        return sb.toString();
    }

    private String extractCode(String link) {
        if (link == null) return "";
        int idx = link.indexOf("ref=");
        return idx >= 0 ? link.substring(idx + 4) : "";
    }
}
