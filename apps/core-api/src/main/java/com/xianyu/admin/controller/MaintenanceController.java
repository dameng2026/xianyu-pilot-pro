package com.xianyu.admin.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.MaintenanceStatusVO;
import com.xianyu.admin.service.MaintenanceService;

/**
 * 维护模式公开查询端点。
 * <p>无需登录，供前端在所有页面（含登录页）轮询维护横幅状态。
 * 写入由部署脚本通过 redis-cli 直接操作，不经此 Controller。
 */
@RestController
public class MaintenanceController {

    private final MaintenanceService maintenanceService;

    public MaintenanceController(MaintenanceService maintenanceService) {
        this.maintenanceService = maintenanceService;
    }

    @GetMapping("/api/maintenance/status")
    public Result<MaintenanceStatusVO> status() {
        return Result.ok(maintenanceService.getStatus());
    }
}
