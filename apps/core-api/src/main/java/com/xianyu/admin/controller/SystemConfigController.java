package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.service.SystemConfigService;
import com.xianyu.admin.service.UploadedImageValidator;
import com.xianyu.admin.service.UploadStorageGovernanceService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 系统配置控制器。
 * 处理 admin-web 端的系统配置读写和 LOGO 上传。
 */
@RestController
@RequestMapping("/admin-api/system")
public class SystemConfigController {
    private static final Logger log = LoggerFactory.getLogger(SystemConfigController.class);
    private static final String PUBLIC_LOGO_STORAGE_PREFIX = "public/logos";

    private final SystemConfigService configService;
    private final UploadedImageValidator imageValidator;
    private final UploadStorageGovernanceService storageGovernance;

    public SystemConfigController(SystemConfigService configService, UploadedImageValidator imageValidator,
                                  UploadStorageGovernanceService storageGovernance) {
        this.configService = configService;
        this.imageValidator = imageValidator;
        this.storageGovernance = storageGovernance;
    }

    // ==================== 系统配置 CRUD ====================

    /**
     * 获取系统配置
     */
    @GetMapping("/config")
    public Result<Map<String, Object>> getConfig() {
        return Result.ok(configService.getConfig());
    }

    /**
     * 保存系统配置
     */
    @PostMapping("/config")
    public Result<Void> saveConfig(@RequestBody Map<String, Object> config) {
        configService.saveConfig(config);
        return Result.ok(null);
    }

    // ==================== LOGO 上传 ====================

    /**
     * 上传系统 LOGO
     * 存储到 uploads/public/logos/ 目录，返回显式公开的 URL
     */
    @PostMapping("/config/upload-logo")
    public Result<Map<String, Object>> uploadLogo(@RequestParam("file") MultipartFile file) {
        final UploadedImageValidator.ValidatedImage image;
        try {
            image = imageValidator.validate(file, 2L * 1024 * 1024);
        } catch (IllegalArgumentException e) {
            return new Result<>(400, e.getMessage(), null);
        }

        try {
            String dateStr = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));

            // 生成唯一文件名
            String originalName = file.getOriginalFilename();
            String fileName = UUID.randomUUID().toString().replace("-", "") + image.extension();

            // 构建访问 URL（相对路径，由静态资源配置提供访问）
            String storageKey = PUBLIC_LOGO_STORAGE_PREFIX + "/" + dateStr + "/" + fileName;
            String fileUrl = "/uploads/" + storageKey;
            UploadStorageGovernanceService.StoredAsset stored = storageGovernance.storePublic(
                    0L, null, storageKey, fileUrl,
                    image.contentType(), "system-logo", "system-logo", image.bytes());

            log.info("LOGO上传成功 assetId={} bytes={}", stored.assetId(), stored.sizeBytes());

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("url", fileUrl);
            result.put("fileName", originalName);
            return Result.ok(result);
        } catch (BizException e) {
            log.error("LOGO上传失败, errorType={}", e.getClass().getSimpleName());
            return new Result<>(e.getCode(), e.getMessage(), null);
        }
    }

}
