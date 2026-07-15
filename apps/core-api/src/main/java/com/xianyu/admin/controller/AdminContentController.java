package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.OpenSourceContentService;
import com.xianyu.admin.service.PublicContentMediaService;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.multipart.MultipartHttpServletRequest;
import jakarta.servlet.http.HttpServletRequest;

import java.util.Map;

@RestController
@RequestMapping("/admin-api/admin")
public class AdminContentController {
    private final OpenSourceContentService contentService;
    private final PublicContentMediaService mediaService;

    public AdminContentController(OpenSourceContentService contentService,
                                  PublicContentMediaService mediaService) {
        this.contentService = contentService;
        this.mediaService = mediaService;
    }

    // ==================== 轮播图管理 ====================

    @GetMapping("/carousel/list")
    public Result<Object> carouselList() {
        return Result.ok(contentService.listCommercialHomeCarousels());
    }

    @PostMapping("/carousel")
    public Result<Object> carouselSave(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.saveCommercialHomeCarousel(body));
    }

    @PutMapping("/carousel")
    public Result<Object> carouselUpdate(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.updateCommercialHomeCarousel(body));
    }

    @DeleteMapping("/carousel/{id}")
    public Result<Object> carouselDelete(@PathVariable("id") Long id) {
        return Result.ok(contentService.deleteCommercialHomeCarousel(id));
    }

    @PostMapping("/carousel/upload")
    public Result<Object> carouselUpload(HttpServletRequest request) {
        if (!(request instanceof MultipartHttpServletRequest multipartRequest)) {
            throw new BizException(400, "请求必须为 multipart/form-data 格式");
        }
        MultipartFile file = multipartRequest.getFile("file");
        return Result.ok(mediaService.upload(file, PublicContentMediaService.PURPOSE_CAROUSEL));
    }

    @PostMapping("/carousel/upload-from-url")
    public Result<Object> carouselUploadFromUrl(@RequestBody Map<String, Object> body) {
        String url = body == null ? "" : String.valueOf(body.getOrDefault("url", "")).trim();
        return Result.ok(mediaService.importFromUrl(url, PublicContentMediaService.PURPOSE_CAROUSEL));
    }

    // ==================== 公告管理 ====================

    @GetMapping("/announcement/list")
    public Result<Object> announcementList() {
        return Result.ok(contentService.listCommercialHomeAnnouncements());
    }

    @PostMapping("/announcement")
    public Result<Object> announcementSave(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.saveCommercialHomeAnnouncement(body));
    }

    @PutMapping("/announcement")
    public Result<Object> announcementUpdate(@RequestBody Map<String, Object> body) {
        return Result.ok(contentService.updateCommercialHomeAnnouncement(body));
    }

    @DeleteMapping("/announcement/{id}")
    public Result<Object> announcementDelete(@PathVariable("id") Long id) {
        return Result.ok(contentService.deleteCommercialHomeAnnouncement(id));
    }
}
