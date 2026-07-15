package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;

import java.util.Arrays;

/**
 * Single source of truth for browser-visible self-service authentication capabilities.
 * Unknown or unconfigured verification delivery is always represented as unavailable.
 *
 * 验证码方式已统一切换为邮箱验证码。生产环境中，仅当后台邮件 SMTP 配置完整时才开放自助能力。
 */
@Service
public class UserAuthCapabilityService {
    private static final String SUPPORT_MESSAGE =
            "请联系管理员或部署方开通账号、重置密码或在后台配置邮箱 SMTP 服务。";
    private static final String PRODUCTION_NOTICE =
            "生产环境不会生成、返回或接受调试验证码；未配置邮箱 SMTP 时自助验证流程保持关闭。";
    private static final String DEVELOPMENT_NOTICE =
            "仅限本地开发：验证码会作为调试字段返回。禁止在公网、共享测试或生产环境启用此模式。";

    private final Environment environment;
    private final NotificationConfigService notificationConfigService;

    public record Capability(boolean available, boolean devOnly, String reason) {}

    public record Capabilities(
            String version,
            String mode,
            boolean failClosed,
            String securityNotice,
            String supportMessage,
            Capability passwordLogin,
            Capability emailVerification,
            Capability selfRegistration,
            Capability passwordReset,
            Capability profileVerification
    ) {}

    public UserAuthCapabilityService(Environment environment,
                                     NotificationConfigService notificationConfigService) {
        this.environment = environment;
        this.notificationConfigService = notificationConfigService;
    }

    public Capabilities current() {
        Capability password = new Capability(true, false, "可使用已创建账号和密码登录。数据库与认证服务仍需保持健康。");
        if (isLocalDevelopment()) {
            Capability debugEmail = developmentOnly("本地调试验证码可用，验证码会随响应返回且不会发送真实邮件。");
            return new Capabilities(
                    "1", "local-development", true, DEVELOPMENT_NOTICE, SUPPORT_MESSAGE,
                    password,
                    debugEmail,
                    developmentOnly("仅本地开发可使用调试验证码创建临时账号。"),
                    developmentOnly("仅本地开发可使用调试验证码重置密码。"),
                    developmentOnly("仅本地开发可使用调试验证码绑定邮箱。"));
        }
        boolean emailReady = notificationConfigService.isEmailConfigured();
        if (emailReady) {
            Capability email = new Capability(true, false, "邮箱 SMTP 已配置，验证码将真实发送至用户邮箱。");
            return new Capabilities(
                    "1", "production-safe", true, PRODUCTION_NOTICE, SUPPORT_MESSAGE,
                    password,
                    email,
                    new Capability(true, false, "邮箱验证码已配置，可使用邮箱自助注册。"),
                    new Capability(true, false, "邮箱验证码已配置，可使用邮箱自助找回密码。"),
                    new Capability(true, false, "邮箱验证码已配置，可绑定或更换邮箱。"));
        }
        Capability email = unavailable("邮箱 SMTP 尚未配置，当前无法发送验证码。");
        Capability registration = unavailable("自助注册依赖邮箱验证，当前请联系管理员开通账号。");
        Capability reset = unavailable("自助密码找回依赖邮箱验证，当前请联系管理员重置密码。");
        Capability profile = unavailable("邮箱绑定依赖 SMTP 配置，当前不可绑定或更换。");
        return new Capabilities(
                "1", "production-safe", true, PRODUCTION_NOTICE, SUPPORT_MESSAGE,
                password, email, registration, reset, profile);
    }

    public void requireSelfRegistration() {
        require(current().selfRegistration());
    }

    public void requireEmailVerification() {
        require(current().emailVerification());
    }

    public void requirePasswordReset() {
        require(current().passwordReset());
    }

    public void requireProfileVerification() {
        require(current().profileVerification());
    }

    private void require(Capability capability) {
        if (!capability.available()) {
            throw new BizException(503, capability.reason());
        }
    }

    private Capability unavailable(String reason) {
        return new Capability(false, false, reason);
    }

    private Capability developmentOnly(String reason) {
        return new Capability(true, true, reason);
    }

    private boolean isLocalDevelopment() {
        String[] profiles = environment.getActiveProfiles();
        if (profiles.length == 0) return false;
        return Arrays.stream(profiles)
                .allMatch(profile -> "local".equals(profile) || "dev".equals(profile));
    }
}
