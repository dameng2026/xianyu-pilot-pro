package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import jakarta.mail.Authenticator;
import jakarta.mail.Message;
import jakarta.mail.PasswordAuthentication;
import jakarta.mail.Session;
import jakarta.mail.Transport;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;
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
                ? "<p>您的验证码是：<strong>" + code + "</strong>，5分钟内有效。</p>"
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

        try {
            MimeMessage message = new MimeMessage(session);
            message.setFrom(new InternetAddress(fromEmail, fromName, "UTF-8"));
            message.setRecipients(Message.RecipientType.TO, InternetAddress.parse(toEmail));
            message.setSubject(subject, "UTF-8");
            message.setContent(htmlContent, "text/html; charset=UTF-8");
            Transport.send(message);
            log.info("邮件发送成功: to={}", maskEmail(toEmail));
        } catch (Exception e) {
            log.error("邮件发送失败: to={}, error={}", maskEmail(toEmail), e.getMessage());
            throw new BizException(503, "邮件发送失败：" + e.getMessage());
        }
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
