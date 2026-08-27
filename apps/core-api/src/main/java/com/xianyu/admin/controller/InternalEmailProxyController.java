package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.EmailSenderService;
import com.xianyu.admin.service.NotificationConfigService;
import com.xianyu.admin.service.OutboundNotificationPolicy;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Pattern;

/**
 * 内部邮件代理接口：供 automation-service 通过 X-Internal-Token 调用，
 * 用于用户级业务通知走腾讯云 SES 链路。
 *
 * 设计约束：
 *  - 不接受客户端传入的云凭据（SecretId/SecretKey/Region/TemplateID）
 *  - 后端强制使用 sys_config.email_config 的全局 SES 配置
 *  - provider 不是 tencent_ses 时拒绝发送
 *  - 对收件人格式、主题长度、HTML 正文长度做校验
 *  - 失败响应只返回稳定的业务错误码和友好原因，不返回 SDK 原始异常
 *  - 不在日志中记录 SecretKey/签名/完整堆栈
 */
@RestController
@RequestMapping("/open-api/internal/notification/email")
public class InternalEmailProxyController {
    private static final Logger log = LoggerFactory.getLogger(InternalEmailProxyController.class);

    /** 收件人邮箱格式校验（宽松但足够拦截明显错误）。 */
    private static final Pattern EMAIL_PATTERN =
            Pattern.compile("^[A-Za-z0-9._%+\\-]+@[A-Za-z0-9.\\-]+\\.[A-Za-z]{2,}$");

    /** 主题最大长度（UTF-8 字节）。 */
    private static final int MAX_SUBJECT_BYTES = 200;

    /** HTML 正文最大长度（UTF-8 字节，约 1MB）。 */
    private static final int MAX_HTML_BYTES = 1_000_000;

    /** 纯文本正文最大长度（UTF-8 字节）。 */
    private static final int MAX_TEXT_BYTES = 200_000;

    private final EmailSenderService emailSenderService;
    private final NotificationConfigService notificationConfigService;
    private final OutboundNotificationPolicy outboundNotificationPolicy;

    @Value("${xianyu.automation.internal-token:}")
    private String internalToken;

    public InternalEmailProxyController(EmailSenderService emailSenderService,
                                          NotificationConfigService notificationConfigService,
                                          OutboundNotificationPolicy outboundNotificationPolicy) {
        this.emailSenderService = emailSenderService;
        this.notificationConfigService = notificationConfigService;
        this.outboundNotificationPolicy = outboundNotificationPolicy;
    }

    /**
     * 内部代理：使用全局腾讯云 SES 配置发送 HTML 直发邮件。
     *
     * 请求体字段：
     *   toEmail       收件人邮箱（必填）
     *   subject       邮件主题（必填）
     *   htmlContent   HTML 正文（必填）
     *   textContent   纯文本正文（可选，缺省时由 Java 端从 HTML 简单剥离）
     *
     * 响应体字段：
     *   success       是否发送成功
     *   messageId     成功时返回腾讯云 MessageId（可能为空字符串）
     *   message       失败时返回友好错误原因
     */
    @PostMapping("/tencent-ses")
    public Result<Map<String, Object>> sendTencentSes(@RequestBody Map<String, Object> body,
                                                        HttpServletRequest request) {
        verifyInternalToken(request);

        // 拒绝客户端传入任何云凭据字段：即使传了也忽略，强制使用全局配置
        if (body != null) {
            body.remove("secretId");
            body.remove("tencentSecretId");
            body.remove("secretKey");
            body.remove("tencentSecretKey");
            body.remove("region");
            body.remove("tencentRegion");
            body.remove("templateId");
            body.remove("tencentTemplateId");
            body.remove("fromEmailAddress");
            body.remove("tencentFromEmailAddress");
        }

        // 强制校验 provider：必须为 tencent_ses 才允许走此代理
        Map<String, Object> config = notificationConfigService.getEmailConfigDecrypted();
        String provider = Objects.toString(config.get("provider"), "smtp").trim().toLowerCase(Locale.ROOT);
        if (!"tencent_ses".equals(provider)) {
            log.warn("内部 SES 代理被调用但当前 provider={}, 拒绝发送", provider);
            throw new BizException(403, "当前邮件发送方式不是腾讯云 SES，拒绝内部代理调用");
        }

        if (!notificationConfigService.isTencentSesAvailable()) {
            log.warn("内部 SES 代理被调用但腾讯云 SES 配置不完整");
            throw new BizException(503, "腾讯云 SES 配置不完整，请联系管理员完成配置");
        }

        if (body == null || body.isEmpty()) {
            throw new BizException(400, "请求体不能为空");
        }
        String toEmail = trimToEmpty(body.get("toEmail"));
        String subject = trimToEmpty(body.get("subject"));
        String htmlContent = body.get("htmlContent") == null ? "" : String.valueOf(body.get("htmlContent"));
        String textContent = body.get("textContent") == null ? "" : String.valueOf(body.get("textContent"));

        validateEmail(toEmail);
        validateSubject(subject);
        validateHtmlSize(htmlContent);
        validateTextSize(textContent);

        // 出站策略校验：腾讯云 SES SDK 内部走 HTTPS API，此处通过 OutboundNotificationPolicy
        // 对 SES API 域名做固定白名单校验（域名在 TencentSesSender 内部固定，这里只做防御性记录）
        // 注：SES 调用不经过 OutboundNotificationPolicy.validateWebhook，但保留 hook 以便审计
        try {
            outboundNotificationPolicy.validateSesApiCall();
        } catch (IllegalArgumentException e) {
            log.error("内部 SES 代理出站策略校验失败: {}", e.getMessage());
            throw new BizException(503, "腾讯云 SES 出站策略校验失败");
        }

        try {
            EmailSenderService.SendEmailOutcome outcome =
                    emailSenderService.sendHtmlEmail(toEmail, subject, htmlContent, textContent);
            if (!outcome.success()) {
                log.warn("内部 SES 代理发送失败: to={}, error={}", maskEmail(toEmail), outcome.message());
                return Result.ok(Map.of(
                        "success", false,
                        "messageId", "",
                        "message", outcome.message() == null ? "腾讯云 SES 发送失败" : outcome.message()));
            }
            return Result.ok(Map.of(
                    "success", true,
                    "messageId", outcome.messageId() == null ? "" : outcome.messageId(),
                    "message", ""));
        } catch (BizException e) {
            log.warn("内部 SES 代理发送异常: to={}, error={}", maskEmail(toEmail), e.getMessage());
            return Result.ok(Map.of(
                    "success", false,
                    "messageId", "",
                    "message", e.getMessage() == null ? "腾讯云 SES 发送失败" : e.getMessage()));
        } catch (Exception e) {
            // 兜底：不向调用方暴露原始异常
            log.error("内部 SES 代理未预期异常: to={}, errorType={}",
                    maskEmail(toEmail), e.getClass().getSimpleName());
            return Result.ok(Map.of(
                    "success", false,
                    "messageId", "",
                    "message", "腾讯云 SES 发送失败，请稍后重试"));
        }
    }

    private void verifyInternalToken(HttpServletRequest request) {
        if (internalToken == null || internalToken.isBlank()) {
            throw new BizException(503, "internal API token is not configured");
        }
        String token = request.getHeader("X-Internal-Token");
        if (token == null || !MessageDigest.isEqual(
                internalToken.getBytes(StandardCharsets.UTF_8),
                token.getBytes(StandardCharsets.UTF_8))) {
            throw new BizException(403, "invalid internal token");
        }
    }

    private void validateEmail(String toEmail) {
        if (toEmail == null || toEmail.isBlank()) {
            throw new BizException(400, "收件人邮箱不能为空");
        }
        if (toEmail.length() > 254) {
            throw new BizException(400, "收件人邮箱过长");
        }
        if (!EMAIL_PATTERN.matcher(toEmail).matches()) {
            throw new BizException(400, "收件人邮箱格式不正确");
        }
    }

    private void validateSubject(String subject) {
        if (subject == null || subject.isBlank()) {
            throw new BizException(400, "邮件主题不能为空");
        }
        if (subject.getBytes(StandardCharsets.UTF_8).length > MAX_SUBJECT_BYTES) {
            throw new BizException(400, "邮件主题过长");
        }
    }

    private void validateHtmlSize(String html) {
        if (html == null || html.isBlank()) {
            throw new BizException(400, "HTML 正文不能为空");
        }
        if (html.getBytes(StandardCharsets.UTF_8).length > MAX_HTML_BYTES) {
            throw new BizException(400, "HTML 正文过大");
        }
    }

    private void validateTextSize(String text) {
        if (text == null) return;
        if (text.getBytes(StandardCharsets.UTF_8).length > MAX_TEXT_BYTES) {
            throw new BizException(400, "纯文本正文过大");
        }
    }

    private String trimToEmpty(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private String maskEmail(String email) {
        if (email == null || email.length() < 5) return "***";
        int at = email.indexOf('@');
        if (at < 1) return "***";
        return email.substring(0, Math.min(2, at)) + "***" + email.substring(at);
    }
}
