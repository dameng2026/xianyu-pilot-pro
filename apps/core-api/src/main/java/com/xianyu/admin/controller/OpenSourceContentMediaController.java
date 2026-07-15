package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.PublicContentMediaService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.multipart.MultipartHttpServletRequest;

import java.util.Map;

/** Super-admin media endpoints for content published through the open-source bridge. */
@RestController
@RequestMapping("/admin-api/open-source-admin/media")
public class OpenSourceContentMediaController {
    private final PublicContentMediaService mediaService;

    public OpenSourceContentMediaController(PublicContentMediaService mediaService) {
        this.mediaService = mediaService;
    }

    @PostMapping("/upload")
    public Result<Object> upload(HttpServletRequest request) {
        if (!(request instanceof MultipartHttpServletRequest multipartRequest)) {
            throw new BizException(400, "请求必须为 multipart/form-data 格式");
        }
        MultipartFile file = multipartRequest.getFile("file");
        return Result.ok(mediaService.upload(
                file,
                PublicContentMediaService.PURPOSE_OPEN_SOURCE_CONTENT
        ));
    }

    @PostMapping("/import-from-url")
    public Result<Object> importFromUrl(@RequestBody(required = false) Map<String, Object> body) {
        String url = body == null ? "" : String.valueOf(body.getOrDefault("url", "")).trim();
        return Result.ok(mediaService.importFromUrl(
                url,
                PublicContentMediaService.PURPOSE_OPEN_SOURCE_CONTENT
        ));
    }
}
