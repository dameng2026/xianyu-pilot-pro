package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.AdminXianyuAccountVO;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.service.AdminXianyuAccountService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 后台管理员专用闲鱼账号管理接口。
 * 挂载在 /admin-api/admin/xianyu/accounts，由 JwtAuthFilter 校验管理员身份。
 * 与 /api/xianyu/accounts（user-web 使用，按租户隔离）完全独立。
 */
@RestController
@RequestMapping("/admin-api/admin/xianyu/accounts")
public class AdminXianyuAccountController {

    private final AdminXianyuAccountService adminAccountService;

    public AdminXianyuAccountController(AdminXianyuAccountService adminAccountService) {
        this.adminAccountService = adminAccountService;
    }

    /**
     * 分页查询闲鱼账号。跨租户管理数据仅允许超级管理员访问，tenantId 筛选必须真实生效。
     */
    @GetMapping
    public Result<PageResult<AdminXianyuAccountVO>> page(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer status,
            @RequestParam(required = false) Integer cookieStatus,
            @RequestParam(required = false) Integer wsStatus,
            @RequestParam(required = false) Integer onlineStatus,
            @RequestParam(required = false) String membershipLevel,
            @RequestParam(required = false) Long tenantId,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime createdStart,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime createdEnd,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        requireSuperAdmin();
        PageResult<AdminXianyuAccountVO> result = adminAccountService.page(
                keyword, status, cookieStatus, wsStatus, onlineStatus, membershipLevel,
                tenantId, userId, createdStart, createdEnd, current, size);
        return Result.ok(result);
    }

    /**
     * 查看某账号详情。
     */
    @GetMapping("/{id}")
    public Result<AdminXianyuAccountVO> detail(@PathVariable Long id) {
        requireSuperAdmin();
        AdminXianyuAccountVO vo = adminAccountService.detail(id);
        if (vo == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }
        return Result.ok(vo);
    }

    /**
     * 启用账号。
     */
    @PostMapping("/{id}/enable")
    public Result<Map<String, Object>> enable(@PathVariable Long id) {
        requireSuperAdmin();
        adminAccountService.enable(id);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("id", id);
        data.put("status", 1);
        return Result.ok(data);
    }

    /**
     * 禁用账号。
     */
    @PostMapping("/{id}/disable")
    public Result<Map<String, Object>> disable(@PathVariable Long id) {
        requireSuperAdmin();
        adminAccountService.disable(id);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("id", id);
        data.put("status", 0);
        return Result.ok(data);
    }

    /**
     * 刷新状态（从运行时表重新读取）。
     */
    @PostMapping("/{id}/refresh-status")
    public Result<AdminXianyuAccountVO> refreshStatus(@PathVariable Long id) {
        requireSuperAdmin();
        AdminXianyuAccountVO vo = adminAccountService.detail(id);
        if (vo == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }
        return Result.ok(vo);
    }

    private void requireSuperAdmin() {
        if (!AdminContext.hasRole("R_SUPER")) {
            throw new BizException(403, "需要超级管理员权限");
        }
    }
}
