package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.EmailSenderService;
import com.xianyu.admin.service.NotificationConfigService;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 通知配置控制器（短信、邮件）。
 * 处理 admin-web 端的配置读写和测试发送。
 */
@RestController
@RequestMapping("/admin-api/system")
@Validated
public class NotificationConfigController {

    private final NotificationConfigService configService;
    private final EmailSenderService emailSenderService;

    public NotificationConfigController(NotificationConfigService configService,
                                        EmailSenderService emailSenderService) {
        this.configService = configService;
        this.emailSenderService = emailSenderService;
    }

    // ==================== 短信配置 ====================

    @GetMapping("/sms-config")
    public Result<Map<String, Object>> getSmsConfig() {
        return Result.ok(configService.getSmsConfig());
    }

    @PostMapping("/sms-config")
    public Result<Void> saveSmsConfig(@RequestBody Map<String, Object> config) {
        configService.saveSmsConfig(config);
        return Result.ok(null);
    }

    @PostMapping("/sms-config/test")
    public Result<Void> testSms(@RequestBody @Validated TestSmsReq req) {
        configService.testSms(req.phone());
        return Result.ok(null);
    }

    public record TestSmsReq(@NotBlank String phone) {}

    // ==================== 邮箱配置 ====================

    @GetMapping("/email-config")
    public Result<Map<String, Object>> getEmailConfig() {
        return Result.ok(configService.getEmailConfig());
    }

    @PostMapping("/email-config")
    public Result<Void> saveEmailConfig(@RequestBody Map<String, Object> config) {
        configService.saveEmailConfig(config);
        return Result.ok(null);
    }

    @PostMapping("/email-config/test")
    public Result<Void> testEmail(@RequestBody @Validated TestEmailReq req) {
        emailSenderService.sendTestEmail(req.email(), req.provider());
        return Result.ok(null);
    }

    public record TestEmailReq(@NotBlank String email, String provider) {}
}
