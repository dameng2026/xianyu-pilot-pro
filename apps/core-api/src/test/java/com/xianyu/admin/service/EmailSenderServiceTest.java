package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * 验证 EmailSenderService 对 SMTP 错误码的友好提示映射。
 * 线上 bug：原实现对所有 SMTP 错误都返回"联系管理员检查邮件服务配置"，
 * 导致用户填错邮箱（550 收件人不存在）时误以为是系统问题。
 */
@ExtendWith(MockitoExtension.class)
class EmailSenderServiceTest {

    @Mock
    NotificationConfigService notificationConfigService;

    @Mock
    TencentSesSender tencentSesSender;

    private EmailSenderService service() {
        return new EmailSenderService(notificationConfigService, tencentSesSender);
    }

    @Test
    void smtp550NonExistentRecipientMapsToInvalidAddressHint() {
        // 线上真实错误："550 The recipient may contain a non-existent account, please check the recipient address."
        String result = service().friendlyEmailError(
                "邮件发送失败：550 The recipient may contain a non-existent account, please check the recipient address.");
        assertEquals("邮箱地址可能不存在或无法接收邮件，请确认邮箱地址正确后重试", result);
    }

    @Test
    void smtp550UserNotFoundAlsoMapsToInvalidAddressHint() {
        String result = service().friendlyEmailError("550 User not found");
        assertEquals("邮箱地址可能不存在或无法接收邮件，请确认邮箱地址正确后重试", result);
    }

    @Test
    void smtp550MailboxUnavailableAlsoMapsToInvalidAddressHint() {
        String result = service().friendlyEmailError("550 Mailbox not found");
        assertEquals("邮箱地址可能不存在或无法接收邮件，请确认邮箱地址正确后重试", result);
    }

    @Test
    void smtp551UserNotLocalMapsToInvalidAddressHint() {
        String result = service().friendlyEmailError("551 User not local");
        assertEquals("邮箱地址可能不存在或无法接收邮件，请确认邮箱地址正确后重试", result);
    }

    @Test
    void smtp553MailboxNameNotAllowedMapsToFormatHint() {
        String result = service().friendlyEmailError("553 Mailbox name not allowed");
        assertEquals("邮箱地址格式不被邮件服务接受，请确认邮箱地址正确后重试", result);
    }

    @Test
    void smtp535AuthFailureMapsToAdminConfigHint() {
        String result = service().friendlyEmailError("535 Authentication failed");
        assertEquals("邮件服务认证失败，请联系管理员检查SMTP授权码配置", result);
    }

    @Test
    void smtp552QuotaExceededMapsToMailboxFullHint() {
        String result = service().friendlyEmailError("552 Quota exceeded");
        assertEquals("收件邮箱已满或暂时无法接收邮件，请稍后重试或更换邮箱", result);
    }

    @Test
    void smtp554BlockedAsSpamMapsToRejectedHint() {
        String result = service().friendlyEmailError("554 Message rejected as spam");
        assertEquals("邮件被收件方拒绝，请稍后重试或更换邮箱", result);
    }

    @Test
    void smtp451TemporaryIssueMapsToRetryHint() {
        String result = service().friendlyEmailError("451 Local error, please try again later");
        assertEquals("邮件服务暂时不可用，请稍后重试", result);
    }

    @Test
    void timeoutErrorMapsToServiceUnavailableHint() {
        String result = service().friendlyEmailError("Connect timed out");
        assertEquals("邮件服务暂时不可用，请稍后重试", result);
    }

    @Test
    void connectionErrorMapsToConnectionHint() {
        String result = service().friendlyEmailError("Unknown host smtp.example.com");
        assertEquals("邮件服务连接异常，请稍后重试", result);
    }

    @Test
    void unknownErrorFallsBackToGenericHint() {
        String result = service().friendlyEmailError("Some unexpected error");
        assertEquals("验证码发送失败，请稍后重试或联系管理员检查邮件服务配置", result);
    }

    @Test
    void nullErrorFallsBackToGenericHint() {
        String result = service().friendlyEmailError(null);
        assertEquals("验证码发送失败，请稍后重试或联系管理员检查邮件服务配置", result);
    }

    @Test
    void blankErrorFallsBackToGenericHint() {
        String result = service().friendlyEmailError("   ");
        assertEquals("验证码发送失败，请稍后重试或联系管理员检查邮件服务配置", result);
    }
}
