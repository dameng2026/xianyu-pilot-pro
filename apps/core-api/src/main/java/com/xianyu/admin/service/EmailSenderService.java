package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import jakarta.mail.Authenticator;
import jakarta.mail.BodyPart;
import jakarta.mail.Message;
import jakarta.mail.Multipart;
import jakarta.mail.PasswordAuthentication;
import jakarta.mail.Session;
import jakarta.mail.Transport;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeBodyPart;
import jakarta.mail.internet.MimeMessage;
import jakarta.mail.internet.MimeMultipart;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Properties;

/**
 * 邮件发送服务。
 * 根据后台 sys_config 中保存的 SMTP 配置动态构建会话并发送邮件。
 */
@Service
public class EmailSenderService {
    private static final Logger log = LoggerFactory.getLogger(EmailSenderService.class);

    private final NotificationConfigService notificationConfigService;

    public EmailSenderService(NotificationConfigService notificationConfigService) {
        this.notificationConfigService = notificationConfigService;
    }

    /** 判断后台邮件 SMTP 配置是否完整（可用于动态开关验证码能力）。 */
    public boolean isEmailConfigured() {
        return notificationConfigService.isEmailConfigured();
    }

    /** 发送验证码邮件。 */
    public void sendVerificationCode(String toEmail, String code) {
        Map<String, Object> config = notificationConfigService.getEmailConfigDecrypted();
        String subject = Objects.toString(config.get("subject"), "【闲鱼助手】验证码通知");
        String template = Objects.toString(config.get("template"), "");
        String content = template.isBlank()
                ? buildDefaultVerificationEmail(code)
                : template.replace("{code}", code);
        try {
            sendEmail(config, toEmail, subject, content);
        } catch (BizException e) {
            // 前台用户不应看到 SMTP 服务器返回的技术细节（如 535 认证失败、帮助链接、trace ID 等），
            // 完整错误记录到后台日志便于管理员排查，对外返回友好提示。
            // 根据SMTP错误码区分原因，让用户能区分"自己填错邮箱"和"系统配置问题"。
            String rawError = e.getMessage() == null ? "" : e.getMessage();
            log.error("验证码邮件发送失败: to={}, error={}", maskEmail(toEmail), rawError);
            throw new BizException(503, friendlyEmailError(rawError));
        }
    }

    /**
     * 默认验证码邮件模板（HTML）。
     * 设计要点：
     *  - 同时包含中文正文与英文备用，避免被反垃圾系统误判
     *  - 验证码用大字号醒目展示，降低被截图识别为营销邮件的概率
     *  - 包含发件用途说明，帮助收件方邮件服务商识别为事务性邮件
     */
    private String buildDefaultVerificationEmail(String code) {
        return "<div style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;"
                + "max-width:480px;margin:0 auto;padding:24px;color:#333;\">"
                + "<h2 style=\"margin:0 0 16px;font-size:20px;color:#1a1a1a;\">闲鱼助手登录验证码</h2>"
                + "<p style=\"margin:0 0 8px;font-size:14px;line-height:1.6;\">您好，您正在进行登录/注册操作，验证码为：</p>"
                + "<p style=\"margin:16px 0;text-align:center;\">"
                + "<span style=\"display:inline-block;font-size:32px;font-weight:600;letter-spacing:6px;"
                + "color:#1677ff;background:#f0f5ff;padding:12px 24px;border-radius:6px;\">" + code + "</span>"
                + "</p>"
                + "<p style=\"margin:0 0 4px;font-size:13px;color:#666;\">验证码 5 分钟内有效，请勿泄露给他人。</p>"
                + "<p style=\"margin:0;font-size:12px;color:#999;\">如非本人操作，请忽略此邮件。</p>"
                + "<hr style=\"margin:20px 0;border:none;border-top:1px solid #eee;\">"
                + "<p style=\"margin:0;font-size:12px;color:#999;\">此邮件由闲鱼助手系统自动发送，请勿回复。</p>"
                + "</div>";
    }

    /** 发送测试邮件（后台配置页使用）。 */
    public void sendTestEmail(String toEmail) {
        Map<String, Object> config = notificationConfigService.getEmailConfigDecrypted();
        String subject = "【闲鱼助手】测试邮件";
        String content = "<p>这是一封测试邮件，用于验证 SMTP 配置是否正确。</p>"
                + "<p>如果您收到此邮件，说明邮箱配置已生效。</p>";
        sendEmail(config, toEmail, subject, content);
    }

    /**
     * 将SMTP底层错误信息映射为对前台用户友好的提示。
     * 不同错误码对应不同根因，避免一律返回"系统配置问题"误导用户。
     * 包级可见以便单元测试覆盖各错误码分支。
     */
    String friendlyEmailError(String rawError) {
        if (rawError == null || rawError.isBlank()) {
            return "验证码发送失败，请稍后重试或联系管理员检查邮件服务配置";
        }
        String lower = rawError.toLowerCase(Locale.ROOT);
        // 550 收件人不存在/拒收（最常见：用户填了不存在的QQ邮箱）
        if (lower.contains("550")
                && (lower.contains("non-existent") || lower.contains("not found")
                        || lower.contains("recipient") || lower.contains("mailbox")
                        || lower.contains("user") || lower.contains("account"))) {
            return "邮箱地址可能不存在或无法接收邮件，请确认邮箱地址正确后重试";
        }
        // 551 用户不在本地服务器
        if (lower.contains("551")) {
            return "邮箱地址可能不存在或无法接收邮件，请确认邮箱地址正确后重试";
        }
        // 553 邮箱名不允许
        if (lower.contains("553")) {
            return "邮箱地址格式不被邮件服务接受，请确认邮箱地址正确后重试";
        }
        // 535 认证失败：SMTP授权码/密码错误
        if (lower.contains("535") || lower.contains("authentication")
                || lower.contains("auth ") || lower.contains("authfailed")) {
            return "邮件服务认证失败，请联系管理员检查SMTP授权码配置";
        }
        // 552 存储不足：收件箱已满
        if (lower.contains("552") || lower.contains("quota") || lower.contains("exceeded")) {
            return "收件邮箱已满或暂时无法接收邮件，请稍后重试或更换邮箱";
        }
        // 554 事务失败/被识别为垃圾邮件
        if (lower.contains("554") || lower.contains("spam") || lower.contains("blocked")
                || lower.contains("reject")) {
            return "邮件被收件方拒绝，请稍后重试或更换邮箱";
        }
        // 4xx 临时错误：超时、服务器繁忙
        if (lower.contains("timeout") || lower.contains("timed out")
                || lower.contains("451") || lower.contains("452") || lower.contains("421")) {
            return "邮件服务暂时不可用，请稍后重试";
        }
        // 连接异常
        if (lower.contains("connect") || lower.contains("unknown host")
                || lower.contains("unreachable") || lower.contains("network")) {
            return "邮件服务连接异常，请稍后重试";
        }
        return "验证码发送失败，请稍后重试或联系管理员检查邮件服务配置";
    }

    /**
     * 最大尝试次数：1 次首发 + 最多 2 次重试。
     * 仅对临时性错误（网络超时、421/451/452 等）重试，永久错误（535 认证失败、550 收件人不存在）不重试。
     */
    private static final int MAX_SEND_ATTEMPTS = 3;
    private static final long RETRY_BACKOFF_MS = 1000L; // 1s → 2s 指数退避

    private void sendEmail(Map<String, Object> config, String toEmail, String subject, String htmlContent) {
        String smtpHost = Objects.toString(config.get("smtpHost"), "").trim();
        String fromEmail = Objects.toString(config.get("fromEmail"), "").trim();
        String fromName = Objects.toString(config.get("fromName"), "闲鱼助手");
        String username = Objects.toString(config.get("username"), "").trim();
        String password = Objects.toString(config.get("password"), "").trim();
        int smtpPort = parseInt(Objects.toString(config.get("smtpPort"), "465"), 465);
        String encryption = Objects.toString(config.get("encryption"), "ssl").trim().toLowerCase();

        if (smtpHost.isBlank() || fromEmail.isBlank() || username.isBlank() || password.isBlank()) {
            throw new BizException(503, "邮箱 SMTP 配置不完整，请先在后台完成邮件配置");
        }

        Properties props = new Properties();
        props.put("mail.smtp.host", smtpHost);
        props.put("mail.smtp.port", String.valueOf(smtpPort));
        props.put("mail.smtp.auth", "true");
        props.put("mail.smtp.connectiontimeout", "10000");
        props.put("mail.smtp.timeout", "15000");
        props.put("mail.smtp.writetimeout", "10000");

        if ("ssl".equals(encryption)) {
            props.put("mail.smtp.ssl.enable", "true");
            props.put("mail.smtp.socketFactory.class", "javax.net.ssl.SSLSocketFactory");
            props.put("mail.smtp.socketFactory.port", String.valueOf(smtpPort));
        } else if ("tls".equals(encryption)) {
            props.put("mail.smtp.starttls.enable", "true");
        }

        Session session = Session.getInstance(props, new Authenticator() {
            @Override
            protected PasswordAuthentication getPasswordAuthentication() {
                return new PasswordAuthentication(username, password);
            }
        });

        // 构造 multipart/alternative：同时提供 HTML 和纯文本，降低被识别为垃圾邮件的概率
        Multipart multipart = buildAlternativeContent(htmlContent);

        Exception lastError = null;
        for (int attempt = 1; attempt <= MAX_SEND_ATTEMPTS; attempt++) {
            try {
                MimeMessage message = new MimeMessage(session);
                message.setFrom(new InternetAddress(fromEmail, fromName, "UTF-8"));
                message.setRecipients(Message.RecipientType.TO, InternetAddress.parse(toEmail));
                message.setSubject(subject, "UTF-8");
                message.setContent(multipart);
                Transport.send(message);
                if (attempt > 1) {
                    log.info("邮件发送成功（第 {} 次尝试）: to={}", attempt, maskEmail(toEmail));
                } else {
                    log.info("邮件发送成功: to={}", maskEmail(toEmail));
                }
                return;
            } catch (Exception e) {
                lastError = e;
                String errMsg = e.getMessage() == null ? "" : e.getMessage();
                log.warn("邮件发送第 {} 次失败: to={}, error={}", attempt, maskEmail(toEmail), errMsg);
                if (!isRetryableSmtpError(errMsg) || attempt == MAX_SEND_ATTEMPTS) {
                    break;
                }
                long backoff = RETRY_BACKOFF_MS * (1L << (attempt - 1)); // 1s → 2s
                try {
                    Thread.sleep(backoff);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        String rawError = lastError == null ? "" : Objects.toString(lastError.getMessage(), "");
        log.error("邮件发送最终失败: to={}, error={}", maskEmail(toEmail), rawError);
        // 抛出干净的 rawError，由 sendVerificationCode 转换为友好提示
        throw new BizException(503, rawError.isBlank() ? "邮件发送失败" : rawError);
    }

    /**
     * 判断 SMTP 错误是否值得重试。
     * - 可重试：网络超时、连接异常、4xx 临时错误（421/451/452）
     * - 不可重试：5xx 永久错误（535 认证失败、550 收件人不存在、552 邮箱满、553/554 等）
     */
    private boolean isRetryableSmtpError(String errMsg) {
        if (errMsg == null || errMsg.isBlank()) return true; // 异常无消息时保守重试
        String lower = errMsg.toLowerCase(Locale.ROOT);
        // 永久错误，重试无意义
        if (lower.contains("535") || lower.contains("authentication")
                || lower.contains("550") || lower.contains("551")
                || lower.contains("553") || lower.contains("554")
                || lower.contains("spam") || lower.contains("blocked")
                || lower.contains("recipient") && lower.contains("not")) {
            return false;
        }
        // 临时错误，可重试
        return true;
    }

    /**
     * 构造 multipart/alternative 内容：同时包含 HTML 和纯文本版本。
     * 许多反垃圾系统会优先评分纯文本部分，缺少纯文本的纯 HTML 邮件容易被判为垃圾邮件。
     */
    private Multipart buildAlternativeContent(String htmlContent) {
        try {
            Multipart multipart = new MimeMultipart("alternative");
            // 纯文本部分（从 HTML 简单剥离标签）
            BodyPart textPart = new MimeBodyPart();
            textPart.setContent(stripHtmlToText(htmlContent), "text/plain; charset=UTF-8");
            multipart.addBodyPart(textPart);
            // HTML 部分
            BodyPart htmlPart = new MimeBodyPart();
            htmlPart.setContent(htmlContent, "text/html; charset=UTF-8");
            multipart.addBodyPart(htmlPart);
            return multipart;
        } catch (Exception e) {
            // 极端情况下退回纯 HTML
            Multipart fallback = new MimeMultipart();
            try {
                BodyPart htmlPart = new MimeBodyPart();
                htmlPart.setContent(htmlContent, "text/html; charset=UTF-8");
                fallback.addBodyPart(htmlPart);
            } catch (Exception ignored) {
                // 无法构造时由调用方抛出
            }
            return fallback;
        }
    }

    /** 简单的 HTML → 纯文本转换：移除标签、转义常见实体。 */
    private String stripHtmlToText(String html) {
        if (html == null || html.isBlank()) return "您的验证码请查看 HTML 版本邮件。";
        String text = html.replaceAll("(?is)<style[^>]*>.*?</style>", "")
                .replaceAll("(?is)<script[^>]*>.*?</script>", "")
                .replaceAll("(?i)<br\\s*/?>", "\n")
                .replaceAll("(?i)</p>", "\n\n")
                .replaceAll("(?i)<[^>]+>", "")
                .replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", "\"")
                .replace("&#39;", "'")
                .trim();
        return text.isBlank() ? "您的验证码请查看 HTML 版本邮件。" : text;
    }

    private int parseInt(String value, int defaultValue) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private String maskEmail(String email) {
        if (email == null || email.length() < 5) return "***";
        int at = email.indexOf('@');
        if (at < 1) return "***";
        return email.substring(0, Math.min(2, at)) + "***" + email.substring(at);
    }
}
