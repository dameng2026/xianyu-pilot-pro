package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AiScenePricingAdminService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
public class AiScenePricingAdminController {
    private final AiScenePricingAdminService service;

    public AiScenePricingAdminController(AiScenePricingAdminService service) {
        this.service = service;
    }

    @GetMapping("/admin-api/ai-scene-sell-config/page")
    public Result<PageResult<Map<String, Object>>> scenePage(@RequestParam(defaultValue = "1") int current,
                                                             @RequestParam(defaultValue = "20") int size,
                                                             @RequestParam(required = false) String keyword,
                                                             @RequestParam(required = false) String sceneGroup) {
        return Result.ok(service.pageScenes(current, size, keyword, sceneGroup));
    }

    @GetMapping("/admin-api/ai-scene-sell-config/{id}")
    public Result<Map<String, Object>> sceneDetail(@PathVariable long id) {
        return Result.ok(service.sceneDetail(id));
    }

    @PostMapping("/admin-api/ai-scene-sell-config")
    public Result<Map<String, Object>> createScene(@RequestBody Map<String, Object> data) {
        return Result.ok(service.createScene(data));
    }

    @PutMapping("/admin-api/ai-scene-sell-config/{id}")
    public Result<Map<String, Object>> updateScene(@PathVariable long id, @RequestBody Map<String, Object> data) {
        return Result.ok(service.updateScene(id, data));
    }

    @DeleteMapping("/admin-api/ai-scene-sell-config/{id}")
    public Result<Void> deleteScene(@PathVariable long id) {
        service.deleteScene(id);
        return Result.ok(null);
    }

    @GetMapping("/admin-api/ai-scene-plan-benefit/page")
    public Result<PageResult<Map<String, Object>>> benefitPage(@RequestParam(defaultValue = "1") int current,
                                                               @RequestParam(defaultValue = "20") int size,
                                                               @RequestParam(required = false) String keyword,
                                                               @RequestParam(required = false) String planCode) {
        return Result.ok(service.pageBenefits(current, size, keyword, planCode));
    }

    @GetMapping("/admin-api/ai-scene-plan-benefit/{id}")
    public Result<Map<String, Object>> benefitDetail(@PathVariable long id) {
        return Result.ok(service.benefitDetail(id));
    }

    @PostMapping("/admin-api/ai-scene-plan-benefit")
    public Result<Map<String, Object>> createBenefit(@RequestBody Map<String, Object> data) {
        return Result.ok(service.createBenefit(data));
    }

    @PutMapping("/admin-api/ai-scene-plan-benefit/{id}")
    public Result<Map<String, Object>> updateBenefit(@PathVariable long id, @RequestBody Map<String, Object> data) {
        return Result.ok(service.updateBenefit(id, data));
    }

    @DeleteMapping("/admin-api/ai-scene-plan-benefit/{id}")
    public Result<Void> deleteBenefit(@PathVariable long id) {
        service.deleteBenefit(id);
        return Result.ok(null);
    }
}
