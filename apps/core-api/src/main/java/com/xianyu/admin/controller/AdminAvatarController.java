package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.service.UploadedImageValidator;
import com.xianyu.admin.service.UploadStorageGovernanceService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 管理员头像上传控制器。
 * 头像保存在 uploads/avatars/yyyyMMdd/ 目录下，仅由 MediaAssetController
 * 在当前管理员的短期媒体会话与数据库头像字段都匹配时返回。
 */
@RestController
@RequestMapping("/admin-api/admin")
public class AdminAvatarController {
    private static final Logger log = LoggerFactory.getLogger(AdminAvatarController.class);

    private final JdbcTemplate jdbcTemplate;
    private final UploadedImageValidator imageValidator;
    private final UploadStorageGovernanceService storageGovernance;

    @Value("${admin.upload.avatar-subdir:avatars}")
    private String avatarSubdir;

    public AdminAvatarController(JdbcTemplate jdbcTemplate, UploadedImageValidator imageValidator,
                                 UploadStorageGovernanceService storageGovernance) {
        this.jdbcTemplate = jdbcTemplate;
        this.imageValidator = imageValidator;
        this.storageGovernance = storageGovernance;
    }

    /**
     * 上传当前登录管理员头像
     * multipart 字段：file（图片文件，<=2MB，支持 PNG/JPEG）
     */
    @PostMapping("/avatar/upload")
    public Result<Map<String, Object>> uploadAvatar(@RequestParam("file") MultipartFile file) {
        Long adminUserId = AdminContext.userId();
        if (adminUserId == null) {
            return Result.fail("未登录");
        }
        final UploadedImageValidator.ValidatedImage image;
        try {
            image = imageValidator.validate(file, 2L * 1024 * 1024);
        } catch (IllegalArgumentException e) {
            return new Result<>(400, e.getMessage(), null);
        }
        try {
            String dateStr = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
            String originalName = file.getOriginalFilename();
            String fileName = "admin_" + adminUserId + "_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12) + image.extension();
            String fileUrl = "/uploads/" + avatarSubdir + "/" + dateStr + "/" + fileName;
            storageGovernance.store(
                    0L, adminUserId, avatarSubdir + "/" + dateStr + "/" + fileName,
                    fileUrl, image.contentType(), "admin-avatar", image.bytes());

            // 更新 sys_admin_user.avatar 字段
            jdbcTemplate.update("UPDATE sys_admin_user SET avatar = ?, updated_time = NOW() WHERE id = ?", fileUrl, adminUserId);

            log.info("管理员头像上传成功 userId={} url={}", adminUserId, fileUrl);

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("url", fileUrl);
            result.put("fileName", originalName);
            return Result.ok(result);
        } catch (BizException e) {
            log.error("管理员头像上传失败 userId={}, errorType={}", adminUserId, e.getClass().getSimpleName());
            return new Result<>(e.getCode(), e.getMessage(), null);
        }
    }

}
