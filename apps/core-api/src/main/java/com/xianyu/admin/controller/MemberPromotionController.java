package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.MemberPromotionService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 会员充值限时活动接口。
 *
 * 后台（/admin-api/promotion/*）：活动 CRUD、状态切换、统计、订单明细、名额调整。
 *  前台（/api/promotion/*）：当前有效活动查询、下单前预览（最终价/名额校验）。
 *
 * 权限：/admin-api/promotion/* 由 AdminRbacFilter 限制为 R_SUPER；
 *  /api/promotion/* 由 UserJwtAuthFilter 校验登录态（无白名单）。
 */
@RestController
public class MemberPromotionController {
    private final MemberPromotionService promotionService;

    public MemberPromotionController(MemberPromotionService promotionService) {
        this.promotionService = promotionService;
    }

    // ==================== 后台：活动 CRUD ====================

    @GetMapping("/admin-api/promotion/activities/page")
    public Result<PageResult<Map<String, Object>>> pageActivities(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String status) {
        return Result.ok(promotionService.pageActivities(current, size, keyword, status));
    }

    @GetMapping("/admin-api/promotion/activities/{id}")
    public Result<Map<String, Object>> activityDetail(@PathVariable long id) {
        return Result.ok(promotionService.activityDetail(id));
    }

    @PostMapping("/admin-api/promotion/activities")
    public Result<Map<String, Object>> createActivity(@RequestBody Map<String, Object> data) {
        Long id = promotionService.createActivity(data);
        return Result.ok(promotionService.activityDetail(id));
    }

    @PutMapping("/admin-api/promotion/activities/{id}")
    public Result<Map<String, Object>> updateActivity(@PathVariable long id, @RequestBody Map<String, Object> data) {
        promotionService.updateActivity(id, data);
        return Result.ok(promotionService.activityDetail(id));
    }

    @PostMapping("/admin-api/promotion/activities/{id}/start")
    public Result<Void> startActivity(@PathVariable long id) {
        promotionService.startActivity(id);
        return Result.ok(null);
    }

    @PostMapping("/admin-api/promotion/activities/{id}/close")
    public Result<Void> closeActivity(@PathVariable long id) {
        promotionService.closeActivity(id);
        return Result.ok(null);
    }

    @PostMapping("/admin-api/promotion/activities/{id}/reopen")
    public Result<Void> reopenActivity(@PathVariable long id) {
        promotionService.reopenActivity(id);
        return Result.ok(null);
    }

    @DeleteMapping("/admin-api/promotion/activities/{id}")
    public Result<Void> deleteActivity(@PathVariable long id) {
        promotionService.deleteActivity(id);
        return Result.ok(null);
    }

    // ==================== 后台：统计与订单明细 ====================

    @GetMapping("/admin-api/promotion/activities/{id}/stats")
    public Result<Map<String, Object>> activityStats(@PathVariable long id) {
        return Result.ok(promotionService.activityStats(id));
    }

    @GetMapping("/admin-api/promotion/activities/{id}/orders")
    public Result<PageResult<Map<String, Object>>> activityOrders(
            @PathVariable long id,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String status) {
        return Result.ok(promotionService.activityOrders(id, current, size, status));
    }

    @PostMapping("/admin-api/promotion/activities/{activityId}/plans/{planId}/quota")
    public Result<Void> adjustQuota(@PathVariable long activityId,
                                    @PathVariable long planId,
                                    @RequestParam int newQuota,
                                    @RequestParam(required = false) String remark) {
        promotionService.adjustQuota(activityId, planId, newQuota, remark);
        return Result.ok(null);
    }

    // ==================== 前台：活动查询与下单预览 ====================

    @GetMapping("/api/promotion/active")
    public Result<Map<String, Object>> activeActivity() {
        return Result.ok(promotionService.activeActivity());
    }

    @GetMapping("/api/promotion/preview")
    public Result<Map<String, Object>> previewActivityPlan(@RequestParam long planId,
                                                            @RequestParam String periodType) {
        return Result.ok(promotionService.previewActivityPlan(planId, periodType));
    }
}
