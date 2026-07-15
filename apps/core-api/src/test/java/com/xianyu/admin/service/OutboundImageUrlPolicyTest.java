package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;

import java.net.InetAddress;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class OutboundImageUrlPolicyTest {

    @Test
    void blocksPrivateAndMetadataDestinationsAfterDnsResolution() throws Exception {
        OutboundImageUrlPolicy policy = new OutboundImageUrlPolicy(Set.of(), host -> switch (host) {
            case "attacker.example" -> new InetAddress[]{InetAddress.getByName("10.12.0.8")};
            case "metadata.example" -> new InetAddress[]{InetAddress.getByName("169.254.169.254")};
            case "127.0.0.1" -> new InetAddress[]{InetAddress.getByName("127.0.0.1")};
            case "fc00::1" -> new InetAddress[]{InetAddress.getByName("fc00::1")};
            default -> new InetAddress[]{InetAddress.getByName("93.184.216.34")};
        });

        assertThrows(IllegalArgumentException.class,
                () -> policy.validate("https://attacker.example/a.png"));
        assertThrows(IllegalArgumentException.class,
                () -> policy.validate("https://metadata.example/latest/meta-data"));
        assertThrows(IllegalArgumentException.class,
                () -> policy.validate("https://127.0.0.1/internal"));
        assertThrows(IllegalArgumentException.class,
                () -> policy.validate("https://[fc00::1]/internal"));
    }

    @Test
    void allowsOnlyHttpsImagesWithoutCredentialsOrCustomPorts() throws Exception {
        OutboundImageUrlPolicy policy = publicInternetPolicy(Set.of());

        assertEquals("https://cdn.example/image.png", policy.validate("https://cdn.example/image.png").toString());
        assertThrows(IllegalArgumentException.class, () -> policy.validate("http://cdn.example/image.png"));
        assertThrows(IllegalArgumentException.class, () -> policy.validate("file:///etc/passwd"));
        assertThrows(IllegalArgumentException.class, () -> policy.validate("https://user:pass@cdn.example/image.png"));
        assertThrows(IllegalArgumentException.class, () -> policy.validate("https://cdn.example:8443/image.png"));
        assertThrows(IllegalArgumentException.class, () -> policy.validate("https://localhost/image.png"));
    }

    @Test
    void configuredHostAllowlistRestrictsExternalDestinations() throws Exception {
        OutboundImageUrlPolicy policy = publicInternetPolicy(Set.of("images.example.com"));

        assertEquals("cdn.images.example.com", policy.validate("https://cdn.images.example.com/a.png").getHost());
        assertThrows(IllegalArgumentException.class, () -> policy.validate("https://untrusted.example/a.png"));
    }

    private OutboundImageUrlPolicy publicInternetPolicy(Set<String> allowedHosts) throws Exception {
        InetAddress publicAddress = InetAddress.getByName("93.184.216.34");
        return new OutboundImageUrlPolicy(allowedHosts, ignored -> new InetAddress[]{publicAddress});
    }
}
