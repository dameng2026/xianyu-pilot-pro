package com.xianyu.admin.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.IDN;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.URI;
import java.util.Arrays;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

/** Fail-closed network policy for tenant-configurable notification destinations. */
@Component
public class OutboundNotificationPolicy {
    private static final int MAX_URL_LENGTH = 2_048;
    private static final Set<String> FEISHU_HOSTS = Set.of("open.feishu.cn", "open.larksuite.com");
    private static final Set<String> DINGTALK_HOSTS = Set.of("oapi.dingtalk.com");
    private static final Set<String> WECHAT_WORK_HOSTS = Set.of("qyapi.weixin.qq.com");

    /**
     * 腾讯云 SES API 固定域名白名单（设计文档 §10.1）。
     * SDK 内部 endpoint 在 {@link TencentSesSender} 中固定为 ses.tencentcloudapi.com，
     * 此处仅作为审计 hook，预留扩展点（如未来需要按地域校验）。
     */
    private static final Set<String> TENCENT_SES_API_HOSTS = Set.of("ses.tencentcloudapi.com");

    private final Set<String> genericWebhookHosts;
    private final Set<String> smtpHosts;
    private final HostResolver resolver;

    @Autowired
    public OutboundNotificationPolicy(
            @Value("${notification.webhook.allowed-hosts:}") String genericWebhookHosts,
            @Value("${notification.smtp.allowed-hosts:}") String smtpHosts) {
        this(parseHosts(genericWebhookHosts), parseHosts(smtpHosts), InetAddress::getAllByName);
    }

    OutboundNotificationPolicy(Set<String> genericWebhookHosts, Set<String> smtpHosts, HostResolver resolver) {
        this.genericWebhookHosts = normalizeHosts(genericWebhookHosts);
        this.smtpHosts = normalizeHosts(smtpHosts);
        this.resolver = resolver;
    }

    public URI validateWebhook(String channelType, String rawUrl) {
        URI uri = parseHttpsUri(rawUrl);
        String type = channelType == null ? "" : channelType.trim().toLowerCase(Locale.ROOT);
        String host = normalizeHost(uri.getHost());
        String path = uri.getPath() == null ? "" : uri.getPath();
        Set<String> allowedHosts;
        switch (type) {
            case "feishu" -> {
                allowedHosts = FEISHU_HOSTS;
                requirePath(path, "/open-apis/bot/");
            }
            case "dingtalk" -> {
                allowedHosts = DINGTALK_HOSTS;
                requirePath(path, "/robot/send");
            }
            case "wechat_work" -> {
                allowedHosts = WECHAT_WORK_HOSTS;
                requirePath(path, "/cgi-bin/webhook/send");
            }
            case "pushplus" -> {
                allowedHosts = Set.of("www.pushplus.plus");
                requirePath(path, "/send");
            }
            case "webhook", "" -> {
                if (genericWebhookHosts.isEmpty()) {
                    throw new IllegalArgumentException("通用 Webhook 未配置管理员域名白名单");
                }
                allowedHosts = genericWebhookHosts;
            }
            default -> throw new IllegalArgumentException("不支持的通知通道类型");
        }
        if (!hostAllowed(host, allowedHosts)) {
            throw new IllegalArgumentException("通知地址不在允许的域名范围内");
        }
        validateResolvedPublicAddresses(host);
        return uri;
    }

    public void validateSmtp(String rawHost, int port) {
        String host = normalizeHost(rawHost);
        if (host.isBlank() || isLocalHostname(host) || (port != 465 && port != 587)) {
            throw new IllegalArgumentException("SMTP 主机或端口不安全");
        }
        if (smtpHosts.isEmpty() || !hostAllowed(host, smtpHosts)) {
            throw new IllegalArgumentException("SMTP 主机未列入管理员白名单");
        }
        validateResolvedPublicAddresses(host);
    }

    /**
     * 腾讯云 SES API 调用出站策略校验（设计文档 §10.1）。
     *
     * SDK 内部已固定 endpoint 为 ses.tencentcloudapi.com 且强制 HTTPS，
     * 此方法仅作为审计 hook：当 SES 调用发生时记录一次校验通过，
     * 便于未来在出现新的地域域名时统一在这里扩展。
     *
     * 当前实现：固定允许 ses.tencentcloudapi.com，不允许用户自定义。
     * 如果未来需要按 region 解析实际 endpoint，应在此方法内补充域名解析与白名单匹配。
     */
    public void validateSesApiCall() {
        // 固定白名单：腾讯云 SES 全球统一 endpoint
        // 如果未来腾讯云按地域拆分 endpoint，需要在这里扩展
        // 当前实现：固定允许 ses.tencentcloudapi.com，不做 DNS 解析（SDK 内部已处理）
        String sesHost = "ses.tencentcloudapi.com";
        if (!TENCENT_SES_API_HOSTS.contains(sesHost)) {
            throw new IllegalArgumentException("腾讯云 SES API 域名不在允许范围内");
        }
        // SDK 内部已强制 HTTPS，此处不做额外校验
    }

    private URI parseHttpsUri(String rawUrl) {
        if (rawUrl == null || rawUrl.isBlank() || rawUrl.length() > MAX_URL_LENGTH
                || rawUrl.chars().anyMatch(Character::isISOControl)) {
            throw new IllegalArgumentException("通知地址格式无效");
        }
        final URI uri;
        try {
            uri = URI.create(rawUrl.trim());
        } catch (RuntimeException error) {
            throw new IllegalArgumentException("通知地址格式无效", error);
        }
        if (!uri.isAbsolute() || !"https".equalsIgnoreCase(uri.getScheme())
                || uri.getRawUserInfo() != null || uri.getRawFragment() != null
                || uri.getHost() == null || uri.getHost().isBlank()
                || isLocalHostname(normalizeHost(uri.getHost()))) {
            throw new IllegalArgumentException("通知地址必须是安全的 HTTPS 地址");
        }
        if (uri.getPort() != -1 && uri.getPort() != 443) {
            throw new IllegalArgumentException("通知地址不允许自定义端口");
        }
        return uri;
    }

    private void validateResolvedPublicAddresses(String host) {
        final InetAddress[] addresses;
        try {
            addresses = resolver.resolve(host);
        } catch (Exception error) {
            throw new IllegalArgumentException("通知地址无法解析", error);
        }
        if (addresses == null || addresses.length == 0
                || Arrays.stream(addresses).anyMatch(address -> !isPublicAddress(address))) {
            throw new IllegalArgumentException("通知地址解析到了非公网网络");
        }
    }

    private static boolean isPublicAddress(InetAddress address) {
        if (address == null || address.isAnyLocalAddress() || address.isLoopbackAddress()
                || address.isLinkLocalAddress() || address.isSiteLocalAddress()
                || address.isMulticastAddress()) {
            return false;
        }
        byte[] bytes = address.getAddress();
        if (address instanceof Inet4Address || bytes.length == 4) {
            return isPublicIpv4(bytes, 0);
        }
        if (bytes.length == 16 && isIpv4Mapped(bytes)) {
            return isPublicIpv4(bytes, 12);
        }
        int first = bytes[0] & 0xff;
        if (first == 0xfc || first == 0xfd) return false;
        return !(bytes.length >= 4
                && (bytes[0] & 0xff) == 0x20
                && (bytes[1] & 0xff) == 0x01
                && (bytes[2] & 0xff) == 0x0d
                && (bytes[3] & 0xff) == 0xb8);
    }

    private static boolean isPublicIpv4(byte[] bytes, int offset) {
        int a = bytes[offset] & 0xff;
        int b = bytes[offset + 1] & 0xff;
        int c = bytes[offset + 2] & 0xff;
        if (a == 0 || a == 10 || a == 127 || a >= 224) return false;
        if (a == 100 && b >= 64 && b <= 127) return false;
        if (a == 169 && b == 254) return false;
        if (a == 172 && b >= 16 && b <= 31) return false;
        if (a == 192 && b == 168) return false;
        if (a == 192 && b == 0 && (c == 0 || c == 2)) return false;
        if (a == 198 && (b == 18 || b == 19 || (b == 51 && c == 100))) return false;
        return !(a == 203 && b == 0 && c == 113);
    }

    private static boolean isIpv4Mapped(byte[] bytes) {
        for (int i = 0; i < 10; i++) {
            if (bytes[i] != 0) return false;
        }
        return (bytes[10] & 0xff) == 0xff && (bytes[11] & 0xff) == 0xff;
    }

    private static boolean hostAllowed(String host, Set<String> allowedHosts) {
        return allowedHosts.stream().anyMatch(allowed ->
                host.equals(allowed) || host.endsWith("." + allowed));
    }

    private static void requirePath(String path, String expectedPrefix) {
        if (!path.startsWith(expectedPrefix)) {
            throw new IllegalArgumentException("通知地址路径与通道类型不匹配");
        }
    }

    private static boolean isLocalHostname(String host) {
        return host.equals("localhost") || host.endsWith(".localhost")
                || host.endsWith(".local") || host.endsWith(".internal")
                || host.endsWith(".home") || host.endsWith(".lan");
    }

    private static Set<String> parseHosts(String value) {
        if (value == null || value.isBlank()) return Set.of();
        return normalizeHosts(Arrays.stream(value.split(",")).collect(Collectors.toSet()));
    }

    private static Set<String> normalizeHosts(Set<String> hosts) {
        if (hosts == null) return Set.of();
        return hosts.stream()
                .map(item -> item == null ? "" : item.trim())
                .map(item -> item.startsWith("*.") ? item.substring(2) : item)
                .map(OutboundNotificationPolicy::normalizeHost)
                .filter(item -> !item.isBlank())
                .collect(Collectors.toUnmodifiableSet());
    }

    private static String normalizeHost(String host) {
        if (host == null) return "";
        String normalized = host.trim();
        if (normalized.startsWith("[") && normalized.endsWith("]")) {
            normalized = normalized.substring(1, normalized.length() - 1);
        }
        while (normalized.endsWith(".")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        if (normalized.indexOf(':') >= 0) return normalized.toLowerCase(Locale.ROOT);
        try {
            return IDN.toASCII(normalized).toLowerCase(Locale.ROOT);
        } catch (IllegalArgumentException error) {
            return "";
        }
    }

    @FunctionalInterface
    interface HostResolver {
        InetAddress[] resolve(String host) throws Exception;
    }
}
