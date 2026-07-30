package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.GrowthService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 后台增长中心接口（/admin-api/growth/*）。
 * 由后台管理员 JWT 鉴权（AdminJwtAuthFilter 拦截 /admin-api/*）。
 */
@RestController
@RequestMapping("/admin-api/growth")
public class AdminGrowthController {

    private final GrowthService growthService;

    public AdminGrowthController(GrowthService growthService) {
        this.growthService = growthService;
    }

    /** 增长中心仪表盘（统计卡片 + 趋势 + 排行榜） */
    @GetMapping("/dashboard")
    public Result<Map<String, Object>> dashboard() {
        return Result.ok(growthService.getAdminDashboard());
    }

    /** 全局配置查询 */
    @GetMapping("/config")
    public Result<Map<String, Object>> getConfig() {
        return Result.ok(growthService.getGlobalConfig());
    }

    /** 全局配置更新（token 奖励数 / 最低提现金额 / 首月分成开关 / 提现开关） */
    @PutMapping("/config")
    public Result<Map<String, Object>> saveConfig(@RequestBody Map<String, Object> body) {
        Long tokenReward = body.get("tokenRewardPerReferral") == null ? null : ((Number) body.get("tokenRewardPerReferral")).longValue();
        Long minWithdrawal = body.get("minWithdrawalAmount") == null ? null : ((Number) body.get("minWithdrawalAmount")).longValue();
        Integer firstMonthOnly = body.get("firstMonthOnly") == null ? null : ((Number) body.get("firstMonthOnly")).intValue();
        Integer withdrawEnabled = body.get("withdrawEnabled") == null ? null : ((Number) body.get("withdrawEnabled")).intValue();
        String updatedBy = body.get("updatedBy") == null ? "admin" : String.valueOf(body.get("updatedBy"));
        return Result.ok(growthService.saveGlobalConfig(tokenReward, minWithdrawal, firstMonthOnly, withdrawEnabled, updatedBy));
    }

    /** 代理等级配置列表（含未启用） */
    @GetMapping("/tier-config")
    public Result<List<Map<String, Object>>> tierConfig() {
        return Result.ok(growthService.getAllTierConfigs());
    }

    /** 代理等级配置新增/更新 */
    @PutMapping("/tier-config")
    public Result<Map<String, Object>> saveTierConfig(@RequestBody Map<String, Object> body) {
        return Result.ok(growthService.upsertTierConfig(body));
    }

    /** 后台排行榜 */
    @GetMapping("/leaderboard")
    public Result<List<Map<String, Object>>> leaderboard(@RequestParam(defaultValue = "50") int limit) {
        return Result.ok(growthService.getLeaderboard(limit));
    }

    /** 后台收益趋势 */
    @GetMapping("/trend")
    public Result<Map<String, Object>> trend(@RequestParam(defaultValue = "30") int days) {
        return Result.ok(growthService.getAdminRevenueTrend(days));
    }

    /** 提现申请列表 */
    @GetMapping("/withdrawals")
    public Result<Map<String, Object>> withdrawals(
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        if (size > 100) size = 100;
        return Result.ok(growthService.adminListWithdrawals(status, page, size));
    }

    /** 提现审批：通过 */
    @PutMapping("/withdrawals/{id}/approve")
    public Result<Map<String, Object>> approveWithdrawal(@PathVariable Long id,
                                                          @RequestBody(required = false) Map<String, Object> body) {
        String reviewer = body == null ? "admin" : (String) body.getOrDefault("reviewer", "admin");
        return Result.ok(growthService.approveWithdrawal(id, reviewer, true, null));
    }

    /** 提现审批：驳回 */
    @PutMapping("/withdrawals/{id}/reject")
    public Result<Map<String, Object>> rejectWithdrawal(@PathVariable Long id,
                                                         @RequestBody Map<String, Object> body) {
        String reviewer = body == null ? "admin" : (String) body.getOrDefault("reviewer", "admin");
        String reason = (String) body.get("rejectReason");
        if (reason == null || reason.isBlank()) throw new BizException(400, "驳回原因不能为空");
        return Result.ok(growthService.approveWithdrawal(id, reviewer, false, reason));
    }

    /** 邀请码列表（带统计） */
    @GetMapping("/invite-codes")
    public Result<Map<String, Object>> inviteCodes(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String keyword) {
        if (size > 100) size = 100;
        return Result.ok(growthService.adminListInviteCodes(page, size, keyword));
    }

    /** 全部推荐关系（二级用户明细） */
    @GetMapping("/referrals")
    public Result<Map<String, Object>> referrals(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String keyword) {
        if (size > 100) size = 100;
        return Result.ok(growthService.adminListReferrals(page, size, keyword));
    }
}
