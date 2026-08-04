package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.FeatureSwitchService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/**
 * 功能开关控制器。
 *
 * 管理端（/admin-api/system/feature-switches，仅超管）：
 *   GET   读取全部开关配置
 *   PUT   保存开关配置（整体覆盖）
 *   POST  /init 初始化默认配置（幂等）
 *
 * 用户端（/api/feature-switches/status，需登录）：
 *   GET   返回当前用户可访问/被拦截的页面状态
 *
 * 不使用类级别 @RequestMapping，参照 BusinessSettingsController 模式。
 * RBAC：/admin-api/system/* 由 AdminRbacFilter 自动强制 R_SUPER 角色，无需额外配置。
 */
@RestController
public class FeatureSwitchController {
    private static final Logger log = LoggerFactory.getLogger(FeatureSwitchController.class);

    private final FeatureSwitchService featureSwitchService;

    public FeatureSwitchController(FeatureSwitchService featureSwitchService) {
        this.featureSwitchService = featureSwitchService;
    }

    // ===================== 管理端 =====================

    @GetMapping("/admin-api/system/feature-switches")
    public Result<List<Map<String, Object>>> listSwitches() {
        return Result.ok(featureSwitchService.listSwitches());
    }

    @PutMapping("/admin-api/system/feature-switches")
    public Result<Void> saveSwitches(@RequestBody Map<String, Object> body) {
        if (body == null) throw new BizException(400, "请求体不能为空");
        Object featuresObj = body.get("features");
        List<Map<String, Object>> features;
        if (featuresObj instanceof List) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> list = (List<Map<String, Object>>) featuresObj;
            features = list;
        } else {
            throw new BizException(400, "features 字段必须为数组");
        }
        featureSwitchService.saveConfig(features);
        return Result.ok(null);
    }

    @PostMapping("/admin-api/system/feature-switches/init")
    public Result<Map<String, Object>> initDefaults() {
        featureSwitchService.initDefaultsIfAbsent();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("initialized", true);
        result.put("features", featureSwitchService.listSwitches());
        return Result.ok(result);
    }

    // ===================== 用户端 =====================

    @GetMapping("/api/feature-switches/status")
    public Result<Map<String, Object>> getStatusForCurrentUser() {
        Long userId = TenantContext.getCurrentUserId();
        if (userId == null) throw new BizException(401, "登录状态已失效");
        return Result.ok(featureSwitchService.getStatusForCurrentUser(userId));
    }

    /**
     * 用户端：返回功能对比数据，用于个人中心「会员等级功能对比」表格展示。
     * 返回结构与 admin 端 listSwitches() 相同（key/title/group/normal/vip/svp），
     * 仅用于只读展示，不暴露保存/初始化等管理操作。
     */
    @GetMapping("/api/feature-switches/comparison")
    public Result<List<Map<String, Object>>> getComparisonForCurrentUser() {
        Long userId = TenantContext.getCurrentUserId();
        if (userId == null) throw new BizException(401, "登录状态已失效");
        return Result.ok(featureSwitchService.listSwitches());
    }

    /**
     * 用户端：返回当前用户店铺数量限制状态（等级、限制数量、当前店铺数）。
     * 用于前台「添加账号」前校验与会员中心/个人中心展示店铺数量。
     */
    @GetMapping("/api/feature-switches/store-limit")
    public Result<Map<String, Object>> getStoreLimitForCurrentUser() {
        Long userId = TenantContext.getCurrentUserId();
        if (userId == null) throw new BizException(401, "登录状态已失效");
        return Result.ok(featureSwitchService.getStoreLimitStatus(userId));
    }
}
