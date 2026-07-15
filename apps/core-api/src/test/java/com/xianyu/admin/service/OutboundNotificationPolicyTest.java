package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;

import java.net.InetAddress;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class OutboundNotificationPolicyTest {
    private final InetAddress publicAddress;

    OutboundNotificationPolicyTest() throws Exception {
        publicAddress = InetAddress.getByName("93.184.216.34");
    }

    @Test
    void genericWebhooksRequireAnOperatorAllowlist() {
        OutboundNotificationPolicy policy = policy(Set.of(), Set.of(), ignored -> new InetAddress[]{publicAddress});

        assertThrows(IllegalArgumentException.class,
                () -> policy.validateWebhook("webhook", "https://hooks.example/notify"));
    }

    @Test
    void blocksPrivateMetadataAndNonHttpsDestinationsAfterResolution() throws Exception {
        OutboundNotificationPolicy policy = policy(Set.of("hooks.example"), Set.of(), host -> switch (host) {
            case "private.hooks.example" -> new InetAddress[]{InetAddress.getByName("10.0.0.7")};
            case "metadata.hooks.example" -> new InetAddress[]{InetAddress.getByName("169.254.169.254")};
            case "2130706433" -> new InetAddress[]{InetAddress.getByName("127.0.0.1")};
            default -> new InetAddress[]{publicAddress};
        });

        assertThrows(IllegalArgumentException.class,
                () -> policy.validateWebhook("webhook", "https://private.hooks.example/a"));
        assertThrows(IllegalArgumentException.class,
                () -> policy.validateWebhook("webhook", "https://metadata.hooks.example/a"));
        assertThrows(IllegalArgumentException.class,
                () -> policy.validateWebhook("webhook", "http://hooks.example/a"));
        assertThrows(IllegalArgumentException.class,
                () -> policy.validateWebhook("webhook", "https://user:pass@hooks.example/a"));
        assertThrows(IllegalArgumentException.class,
                () -> policy.validateWebhook("webhook", "https://hooks.example:8443/a"));
        assertThrows(IllegalArgumentException.class,
                () -> policy.validateWebhook("webhook", "https://2130706433/a"));
    }

    @Test
    void providerChannelsRequireTheirOfficialHostAndPath() {
        OutboundNotificationPolicy policy = policy(Set.of(), Set.of(), ignored -> new InetAddress[]{publicAddress});

        assertEquals("open.feishu.cn", policy.validateWebhook(
                "feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/token").getHost());
        assertThrows(IllegalArgumentException.class, () -> policy.validateWebhook(
                "feishu", "https://attacker.example/open-apis/bot/v2/hook/token"));
        assertThrows(IllegalArgumentException.class, () -> policy.validateWebhook(
                "dingtalk", "https://oapi.dingtalk.com/not-a-robot"));
    }

    @Test
    void smtpRequiresTlsPortAllowlistAndPublicResolution() throws Exception {
        OutboundNotificationPolicy policy = policy(Set.of(), Set.of("smtp.example"), host ->
                new InetAddress[]{host.startsWith("private")
                        ? InetAddress.getByName("192.168.1.8")
                        : publicAddress});

        policy.validateSmtp("smtp.example", 465);
        assertThrows(IllegalArgumentException.class, () -> policy.validateSmtp("smtp.example", 25));
        assertThrows(IllegalArgumentException.class, () -> policy.validateSmtp("unlisted.example", 465));
        assertThrows(IllegalArgumentException.class, () -> policy.validateSmtp("private.smtp.example", 465));
    }

    private OutboundNotificationPolicy policy(
            Set<String> webhookHosts,
            Set<String> smtpHosts,
            OutboundNotificationPolicy.HostResolver resolver) {
        return new OutboundNotificationPolicy(webhookHosts, smtpHosts, resolver);
    }
}
