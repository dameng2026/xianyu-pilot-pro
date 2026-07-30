package com.xianyu.admin.service;

import com.tencentcloudapi.common.Credential;
import com.tencentcloudapi.common.exception.TencentCloudSDKException;
import com.tencentcloudapi.common.profile.ClientProfile;
import com.tencentcloudapi.common.profile.HttpProfile;
import com.tencentcloudapi.ses.v20201002.SesClient;
import com.tencentcloudapi.ses.v20201002.models.SendEmailRequest;
import com.tencentcloudapi.ses.v20201002.models.SendEmailResponse;
import com.tencentcloudapi.ses.v20201002.models.Simple;
import com.tencentcloudapi.ses.v20201002.models.Template;
import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * 腾讯云 SES 邮件发送器。
 *
 * 职责：
 *  - 初始化腾讯云 SES SDK 客户端（基于 SecretId/SecretKey/Region）
 *  - 构造 SendEmailRequest 并调用腾讯云 SES API
 *  - 将腾讯云 SDK 异常归一化为业务友好错误
 *
 * 不负责：
 *  - 读取数据库配置（由 NotificationConfigService 提供）
 *  - 路由判断（由 EmailSenderService 根据 provider 路由）
 *  - 投递日志（由调用方记录）
 *
 * 安全约束：
 *  - 不在日志中记录 SecretId/SecretKey/完整请求体
 *  - 不向调用方返回腾讯云原始异常详情（可能含签名）
 *  - Region 必须经过白名单校验，禁止用户自定义 endpoint
 */
@Service
public class TencentSesSender {
    private static final Logger log = LoggerFactory.getLogger(TencentSesSender.class);

    /** 腾讯云 SES 支持的地域白名单（设计文档 10.1 要求固定域名校验）。 */
    private static final Set<String> ALLOWED_REGIONS = Set.of("ap-hongkong", "ap-guangzhou");

    /** SES API 固定域名（不允许用户自定义）。 */
    private static final String SES_API_ENDPOINT = "ses.tencentcloudapi.com";

    /** 临时性错误关键字（可重试）。 */
    private static final String[] RETRYABLE_KEYWORDS = {
            "timeout", "timed out", "connection", "RequestLimitExceeded",
            "InternalError", "FailedOperation", "502", "503", "504"
    };

    /** 永久性错误关键字（不重试）。 */
    private static final String[] PERMANENT_KEYWORDS = {
            "AuthFailure", "InvalidParameterValue", "UnauthorizedOperation",
            "InvalidSender", "InvalidTemplate", "LimitExceeded", "EmailNotVerified"
    };

    /** 发送验证码邮件（使用腾讯云模板）。 */
    public SendResult sendVerificationEmail(Map<String, Object> config, String toEmail, String code) {
        validateConfig(config);
        String secretId = Objects.toString(config.get("tencentSecretId"), "").trim();
        String secretKey = Objects.toString(config.get("tencentSecretKey"), "").trim();
        String region = Objects.toString(config.get("tencentRegion"), "ap-hongkong").trim();
        String fromEmail = Objects.toString(config.get("tencentFromEmailAddress"), "").trim();
        long templateId = parseLong(config.get("tencentTemplateId"), 0L);

        if (templateId <= 0) {
            throw new BizException(503, "腾讯云 SES 验证码模板 ID 未配置");
        }

        SendEmailRequest req = new SendEmailRequest();
        req.setFromEmailAddress(fromEmail);
        req.setDestination(new String[]{toEmail});
        req.setSubject(Objects.toString(config.get("subject"), "【闲鱼助手】验证码通知"));

        // 验证码模板变量：{"code":"123456"}
        Template template = new Template();
        template.setTemplateID(templateId);
        template.setTemplateData("{\"code\":\"" + escapeJsonString(code) + "\"}");
        req.setTemplate(template);

        return invokeWithRetry(secretId, secretKey, region, req, toEmail, "verification");
    }

    /** 发送 HTML 直发邮件（用于用户级业务通知）。 */
    public SendResult sendHtmlEmail(Map<String, Object> config, String toEmail, String subject,
                                     String htmlContent, String textContent) {
        validateConfig(config);
        String secretId = Objects.toString(config.get("tencentSecretId"), "").trim();
        String secretKey = Objects.toString(config.get("tencentSecretKey"), "").trim();
        String region = Objects.toString(config.get("tencentRegion"), "ap-hongkong").trim();
        String fromEmail = Objects.toString(config.get("tencentFromEmailAddress"), "").trim();

        SendEmailRequest req = new SendEmailRequest();
        req.setFromEmailAddress(fromEmail);
        req.setDestination(new String[]{toEmail});
        req.setSubject(subject);

        // 使用 Simple 字段进行 HTML 直发。
        // 注意：根据腾讯云文档，Simple 字段标记为"已废弃"，仅对部分历史上申请了特殊配置的客户开放。
        // 如未申请特殊配置，需联系腾讯云开通或改用模板发送。
        Simple simple = new Simple();
        simple.setHtml(Base64.getEncoder().encodeToString(
                (htmlContent == null ? "" : htmlContent).getBytes(StandardCharsets.UTF_8)));
        simple.setText(Base64.getEncoder().encodeToString(
                (textContent == null ? "" : textContent).getBytes(StandardCharsets.UTF_8)));
        req.setSimple(simple);

        return invokeWithRetry(secretId, secretKey, region, req, toEmail, "html");
    }

    private SendResult invokeWithRetry(String secretId, String secretKey, String region,
                                        SendEmailRequest req, String toEmail, String sendType) {
        validateRegion(region);
        SesClient client = buildClient(secretId, secretKey, region);

        TencentCloudSDKException lastError = null;
        // 1 次首发 + 最多 2 次重试
        for (int attempt = 1; attempt <= 3; attempt++) {
            try {
                SendEmailResponse resp = client.SendEmail(req);
                String messageId = resp.getMessageId() == null ? "" : resp.getMessageId();
                if (attempt > 1) {
                    log.info("腾讯云 SES 发送成功（第 {} 次尝试）: to={}, type={}, messageId={}",
                            attempt, maskEmail(toEmail), sendType, messageId);
                } else {
                    log.info("腾讯云 SES 发送成功: to={}, type={}, messageId={}",
                            maskEmail(toEmail), sendType, messageId);
                }
                return new SendResult(true, messageId, "");
            } catch (TencentCloudSDKException e) {
                lastError = e;
                String errCode = e.getErrorCode() == null ? "" : e.getErrorCode();
                String errMsg = e.getMessage() == null ? "" : e.getMessage();
                log.warn("腾讯云 SES 发送第 {} 次失败: to={}, type={}, code={}, error={}",
                        attempt, maskEmail(toEmail), sendType, errCode, errMsg);
                if (!isRetryable(errCode, errMsg) || attempt == 3) {
                    break;
                }
                long backoff = 1000L * (1L << (attempt - 1)); // 1s → 2s
                try {
                    Thread.sleep(backoff);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        String errCode = lastError == null ? "" : (lastError.getErrorCode() == null ? "" : lastError.getErrorCode());
        String friendly = friendlySesError(errCode, lastError == null ? "" : lastError.getMessage());
        return new SendResult(false, "", friendly);
    }

    private SesClient buildClient(String secretId, String secretKey, String region) {
        Credential cred = new Credential(secretId, secretKey);
        HttpProfile httpProfile = new HttpProfile();
        httpProfile.setEndpoint(SES_API_ENDPOINT);
        httpProfile.setProtocol(HttpProfile.REQ_HTTPS);
        ClientProfile clientProfile = new ClientProfile();
        clientProfile.setHttpProfile(httpProfile);
        return new SesClient(cred, region, clientProfile);
    }

    private void validateConfig(Map<String, Object> config) {
        if (config == null) {
            throw new BizException(503, "腾讯云 SES 配置不完整");
        }
        String secretId = Objects.toString(config.get("tencentSecretId"), "").trim();
        String secretKey = Objects.toString(config.get("tencentSecretKey"), "").trim();
        String region = Objects.toString(config.get("tencentRegion"), "ap-hongkong").trim();
        String fromEmail = Objects.toString(config.get("tencentFromEmailAddress"), "").trim();
        if (secretId.isBlank() || secretKey.isBlank()) {
            throw new BizException(503, "腾讯云 SES SecretId/SecretKey 未配置");
        }
        if (fromEmail.isBlank()) {
            throw new BizException(503, "腾讯云 SES 发件地址未配置");
        }
        validateRegion(region);
    }

    private void validateRegion(String region) {
        if (region == null || region.isBlank() || !ALLOWED_REGIONS.contains(region.toLowerCase(Locale.ROOT))) {
            throw new BizException(503, "腾讯云 SES 地域不在允许范围内");
        }
    }

    /**
     * 判断腾讯云错误是否可重试。
     * 永久错误（认证失败、参数错误、模板未审核等）不重试；
     * 临时错误（超时、限流、5xx）可重试。
     */
    private boolean isRetryable(String errorCode, String errorMsg) {
        String code = errorCode == null ? "" : errorCode;
        String msg = errorMsg == null ? "" : errorMsg.toLowerCase(Locale.ROOT);
        for (String kw : PERMANENT_KEYWORDS) {
            if (code.contains(kw) || msg.contains(kw.toLowerCase(Locale.ROOT))) {
                return false;
            }
        }
        for (String kw : RETRYABLE_KEYWORDS) {
            if (code.contains(kw) || msg.contains(kw.toLowerCase(Locale.ROOT))) {
                return true;
            }
        }
        // 未知错误保守重试一次
        return true;
    }

    /**
     * 将腾讯云 SDK 异常映射为友好错误提示。
     * 不暴露 SecretId、签名、原始堆栈。
     */
    private String friendlySesError(String errorCode, String errorMsg) {
        String code = errorCode == null ? "" : errorCode;
        String msg = errorMsg == null ? "" : errorMsg.toLowerCase(Locale.ROOT);
        if (code.contains("AuthFailure") || msg.contains("signature")) {
            return "腾讯云 SES 认证失败，请检查 SecretId/SecretKey";
        }
        if (code.contains("InvalidSender") || msg.contains("sender") || msg.contains("fromemail")) {
            return "腾讯云 SES 发件地址未验证，请先在控制台验证发件地址";
        }
        if (code.contains("InvalidTemplate") || code.contains("InvalidParameterValue") || msg.contains("template")) {
            return "腾讯云 SES 模板未审核或不存在，请检查模板 ID";
        }
        if (code.contains("LimitExceeded") || code.contains("RequestLimitExceeded")) {
            return "腾讯云 SES 发送频率或配额超限，请稍后重试";
        }
        if (msg.contains("timeout") || msg.contains("timed out") || msg.contains("connection")) {
            return "腾讯云 SES 网络超时，请稍后重试";
        }
        return "腾讯云 SES 邮件发送失败，请稍后重试或联系管理员";
    }

    private long parseLong(Object value, long defaultValue) {
        if (value == null) return defaultValue;
        if (value instanceof Number n) return n.longValue();
        try {
            return Long.parseLong(String.valueOf(value).trim());
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private String escapeJsonString(String value) {
        if (value == null) return "";
        return value.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    private String maskEmail(String email) {
        if (email == null || email.length() < 5) return "***";
        int at = email.indexOf('@');
        if (at < 1) return "***";
        return email.substring(0, Math.min(2, at)) + "***" + email.substring(at);
    }

    /** 发送结果：成功时 messageId 非空，失败时 message 含友好错误。 */
    public record SendResult(boolean success, String messageId, String message) {}
}
