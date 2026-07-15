package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.OpenSourceAdService;
import com.xianyu.admin.service.OpenSourceContentService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/admin-api/open-source-admin")
public class OpenSourceAdminController {
    private final OpenSourceContentService contentService;
    private final OpenSourceAdService adService;

    public OpenSourceAdminController(OpenSourceContentService contentService, OpenSourceAdService adService) {
        this.contentService = contentService;
        this.adService = adService;
    }

    @GetMapping("/home/carousels")
    public Result<Object> listHomeCarousels() {
        return Result.ok(contentService.listHomeCarousels());
    }

    @PostMapping("/home/carousels")
    public Result<Object> saveHomeCarousel(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.saveHomeCarousel(body));
    }

    @PutMapping("/home/carousels")
    public Result<Object> updateHomeCarousel(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.updateHomeCarousel(body));
    }

    @DeleteMapping("/home/carousels/{id}")
    public Result<Object> deleteHomeCarousel(@PathVariable("id") long id) {
        return Result.ok(contentService.deleteHomeCarousel(id));
    }

    @GetMapping("/home/announcements")
    public Result<Object> listHomeAnnouncements() {
        return Result.ok(contentService.listHomeAnnouncements());
    }

    @PostMapping("/home/announcements")
    public Result<Object> saveHomeAnnouncement(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.saveHomeAnnouncement(body));
    }

    @PutMapping("/home/announcements")
    public Result<Object> updateHomeAnnouncement(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.updateHomeAnnouncement(body));
    }

    @DeleteMapping("/home/announcements/{id}")
    public Result<Object> deleteHomeAnnouncement(@PathVariable("id") long id) {
        return Result.ok(contentService.deleteHomeAnnouncement(id));
    }

    @GetMapping("/about")
    public Result<Object> getAboutContent() {
        return Result.ok(contentService.getAboutContent());
    }

    @PostMapping("/about")
    public Result<Object> saveAboutContent(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.saveAboutContent(body));
    }

    @GetMapping("/ads/text")
    public Result<Object> listTextAds() {
        return Result.ok(adService.listAllTextAds());
    }

    @PostMapping("/ads/text")
    public Result<Object> saveTextAd(@RequestBody Map<String, Object> body) {
        return Result.ok(adService.saveTextAd(body));
    }

    @PutMapping("/ads/text")
    public Result<Object> updateTextAd(@RequestBody Map<String, Object> body) {
        return Result.ok(adService.updateTextAd(body));
    }

    @DeleteMapping("/ads/text/{id}")
    public Result<Object> deleteTextAd(@PathVariable("id") long id) {
        return Result.ok(adService.deleteTextAd(id));
    }

    @GetMapping("/ads/plans")
    public Result<Object> listAdPlans() {
        return Result.ok(adService.listAllAdPlans());
    }

    @PostMapping("/ads/plans")
    public Result<Object> saveAdPlan(@RequestBody Map<String, Object> body) {
        return Result.ok(adService.saveAdPlan(body));
    }

    @PutMapping("/ads/plans")
    public Result<Object> updateAdPlan(@RequestBody Map<String, Object> body) {
        return Result.ok(adService.updateAdPlan(body));
    }

    @DeleteMapping("/ads/plans/{id}")
    public Result<Object> deleteAdPlan(@PathVariable("id") long id) {
        return Result.ok(adService.deleteAdPlan(id));
    }

    @GetMapping("/ads/applications")
    public Result<PageResult<Map<String, Object>>> listAdApplications(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String positionType,
            @RequestParam(required = false) String keyword
    ) {
        return Result.ok(adService.pageApplications(current, size, status, positionType, keyword));
    }

    @GetMapping("/ads/applications/{id}")
    public Result<Object> adApplicationDetail(@PathVariable("id") long id) {
        return Result.ok(adService.getApplicationDetail(id));
    }

    @PostMapping("/ads/applications/{id}/status")
    public Result<Object> updateAdApplicationStatus(@PathVariable("id") long id, @RequestBody Map<String, Object> body) {
        return Result.ok(adService.updateApplicationStatus(id, body));
    }
}
