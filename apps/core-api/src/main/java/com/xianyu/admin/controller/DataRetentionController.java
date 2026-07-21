package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.DataRetentionCleanupService;
import com.xianyu.admin.service.DataRetentionConfigService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 数据保留策略控制器。
 *
 * /admin-api/system/retention-config 系列：管理端读写配置 + 手动触发清理。
 *   - 由 AdminRbacFilter 自动强制 R_SUPER 角色（与 SystemConfigController 同路径前缀）。
 *
 * /api/system/retention-info：公开接口，仅返回 retentionDays + chatMessageCleanupEnabled。
 *   - 供前台 user-web 展示保留天数提示，不暴露内部开关详情。
 */
@RestController
public class DataRetentionController {
    private static final Logger log = LoggerFactory.getLogger(DataRetentionController.class);

    private final DataRetentionConfigService configService;
    private final DataRetentionCleanupService cleanupService;

    public DataRetentionController(DataRetentionConfigService configService,
                                    DataRetentionCleanupService cleanupService) {
        this.configService = configService;
        this.cleanupService = cleanupService;
    }

    // ==================== 管理端：配置读写 ====================

    @GetMapping("/admin-api/system/retention-config")
    public Result<Map<String, Object>> getConfig() {
        return Result.ok(configService.getConfig());
    }

    @PostMapping("/admin-api/system/retention-config")
    public Result<Void> saveConfig(@RequestBody Map<String, Object> config) {
        configService.saveConfig(config);
        return Result.ok(null);
    }

    // ==================== 管理端：手动触发清理 ====================

    @PostMapping("/admin-api/system/retention-config/run")
    public Result<Map<String, Object>> runCleanup() {
        log.info("管理端手动触发数据保留策略清理");
        DataRetentionCleanupService.CleanupResult result = cleanupService.executeCleanup();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("totalDeleted", result.totalDeleted);
        data.put("byCategory", result.byCategory);
        return Result.ok(data);
    }

    // ==================== 公开接口：前台展示用 ====================

    @GetMapping("/api/system/retention-info")
    public Result<Map<String, Object>> getRetentionInfo() {
        return Result.ok(configService.getRetentionInfoForPublic());
    }
}
