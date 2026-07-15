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
            log.error("验证码邮件发送失败: to={}, error={}", maskEmail(toEmail), e.getMessage());
            throw new BizException(503, "验证码发送失败，请稍后重试或联系管理员检查邮件服务配置");
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
