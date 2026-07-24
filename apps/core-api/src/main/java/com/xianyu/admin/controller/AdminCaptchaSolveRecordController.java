package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.AdminCaptchaSolveRecordVO;
import com.xianyu.admin.dto.CaptchaSolveStatsVO;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.service.AdminCaptchaSolveRecordService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;

/**
 * 后台管理员专用滑块求解记录查询接口（只读）。
 * 挂载在 /admin-api/admin/captcha-records，由 JwtAuthFilter 校验管理员身份。
 *
 * 数据来源：xianyu_captcha_solve_record 表（由 automation-service 写入）。
 * 不修改任何求解记录，仅提供后台查询视角。
 */
@RestController
@RequestMapping("/admin-api/admin/captcha-records")
public class AdminCaptchaSolveRecordController {

    private final AdminCaptchaSolveRecordService recordService;

    public AdminCaptchaSolveRecordController(AdminCaptchaSolveRecordService recordService) {
        this.recordService = recordService;
    }

    /**
     * 概览统计：KPI + 趋势 + 账号分组。
     *
     * @param days      时间范围（1=今天，7 或 30 天），省略或 <=0 表示全量
     * @param userId    用户 ID 过滤（与 accountId 互斥）
     * @param accountId 账号 ID 过滤（优先于 userId）
     */
    @GetMapping("/stats")
    public Result<CaptchaSolveStatsVO> stats(
            @RequestParam(required = false) Integer days,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) Long accountId) {
        requireAdmin();
        CaptchaSolveStatsVO vo = recordService.stats(days, userId, accountId);
        return Result.ok(vo);
    }

    /**
     * 队列实时状态：当前排队中 / 求解中任务数（跨租户汇总）。
     * 用于列表页实时徽标，让管理员一眼看到队列瞬时状态。
     */
    @GetMapping("/queue-status")
    public Result<java.util.Map<String, Object>> queueStatus() {
        requireAdmin();
        return Result.ok(recordService.queueStatus());
    }

    /**
     * 分页查询明细记录。
     */
    @GetMapping
    public Result<PageResult<AdminCaptchaSolveRecordVO>> page(
            @RequestParam(required = false) Long accountId,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String triggerScene,
            @RequestParam(required = false) String accountName,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime startTime,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime endTime,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size) {
        requireAdmin();
        PageResult<AdminCaptchaSolveRecordVO> result = recordService.page(
                accountId, userId, status, triggerScene, accountName,
                startTime, endTime, current, size);
        return Result.ok(result);
    }

    /**
     * 权限校验：允许超级管理员（R_SUPER）和运营管理员（R_ADMIN）查看。
     * 与 AdminXianyuAccountController（仅 R_SUPER）不同，本端点放宽到 R_ADMIN，
     * 因为求解记录属于运营监控数据，不涉及账号 Cookie 等敏感凭据。
     */
    private void requireAdmin() {
        if (!AdminContext.hasRole("R_SUPER") && !AdminContext.hasRole("R_ADMIN")) {
            throw new BizException(403, "需要管理员权限");
        }
    }
}
