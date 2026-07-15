package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayInputStream;
import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Single gateway for public CMS images. Java authenticates/validates the request;
 * Python performs governed file storage, while Java/MySQL owns all content metadata.
 */
@Service
public class PublicContentMediaService {
    public static final String PURPOSE_CAROUSEL = "carousel";
    public static final String PURPOSE_OPEN_SOURCE_CONTENT = "open-source-content";
    private static final Set<String> ALLOWED_PURPOSES = Set.of(
            PURPOSE_CAROUSEL,
            PURPOSE_OPEN_SOURCE_CONTENT
    );
    private static final long MAX_IMAGE_BYTES = 5L * 1024 * 1024;
    private static final Logger log = LoggerFactory.getLogger(PublicContentMediaService.class);

    private final AutomationClient automationClient;
    private final TenantSupportService tenantSupportService;
    private final OutboundImageUrlPolicy outboundImageUrlPolicy;
    private final UploadedImageValidator uploadedImageValidator;

    public PublicContentMediaService(
            AutomationClient automationClient,
            TenantSupportService tenantSupportService,
            OutboundImageUrlPolicy outboundImageUrlPolicy,
            UploadedImageValidator uploadedImageValidator
    ) {
        this.automationClient = automationClient;
        this.tenantSupportService = tenantSupportService;
        this.outboundImageUrlPolicy = outboundImageUrlPolicy;
        this.uploadedImageValidator = uploadedImageValidator;
    }

    public Map<String, Object> upload(MultipartFile file, String purpose) {
        String safePurpose = requirePurpose(purpose);
        if (file == null || file.isEmpty()) throw new BizException(400, "上传文件不能为空");
        final UploadedImageValidator.ValidatedImage image;
        try {
            image = uploadedImageValidator.validate(file, MAX_IMAGE_BYTES);
        } catch (IllegalArgumentException ex) {
            throw new BizException(400, ex.getMessage());
        }
        try {
            String prefix = PURPOSE_CAROUSEL.equals(safePurpose) ? "carousel" : "open-content";
            return automationClient.uploadInternalForData(
                    "/api/internal/content/public-images/upload",
                    new ByteArrayInputStream(image.bytes()),
                    prefix + image.extension(),
                    Map.of("purpose", safePurpose),
                    tenantId()
            );
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("public content image upload failed purpose={}, errorType={}",
                    safePurpose, ex.getClass().getSimpleName());
            throw new BizException(503, "公开内容图片暂时无法上传，请稍后重试");
        }
    }

    public Map<String, Object> importFromUrl(String url, String purpose) {
        String safePurpose = requirePurpose(purpose);
        if (url == null || url.isBlank()) throw new BizException(400, "图片地址不能为空");
        final URI safeUri;
        try {
            safeUri = outboundImageUrlPolicy.validate(url.trim());
        } catch (IllegalArgumentException ex) {
            throw new BizException(400, "图片地址不安全或无法访问");
        }
        try {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("url", safeUri.toString());
            payload.put("visibility", "public");
            payload.put("purpose", safePurpose);
            return asMap(automationClient.postInternalForData(
                    "/api/image/uploadFromUrl", payload, tenantId()));
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("public content URL import failed purpose={}, errorType={}",
                    safePurpose, ex.getClass().getSimpleName());
            throw new BizException(503, "公开内容图片暂时无法导入，请稍后重试");
        }
    }

    private String requirePurpose(String purpose) {
        String normalized = purpose == null ? "" : purpose.trim().toLowerCase();
        if (!ALLOWED_PURPOSES.contains(normalized)) {
            throw new BizException(400, "公开内容图片用途无效");
        }
        return normalized;
    }

    private Long tenantId() {
        Long tenantId = tenantSupportService.resolveCurrentOrDefaultTenantId();
        if (tenantId == null || tenantId <= 0) {
            throw new BizException(503, "当前管理租户暂时无法确认，请稍后重试");
        }
        return tenantId;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) return (Map<String, Object>) map;
        throw new BizException(503, "图片处理服务响应格式异常");
    }
}
