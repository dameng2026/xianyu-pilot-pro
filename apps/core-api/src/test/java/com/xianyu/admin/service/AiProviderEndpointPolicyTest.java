package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.Test;

import java.net.InetAddress;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class AiProviderEndpointPolicyTest {

    @Test
    void returnsTheOriginalTlsHostAndTheExactVerifiedDnsSnapshot() throws Exception {
        InetAddress first = InetAddress.getByName("8.8.8.8");
        InetAddress second = InetAddress.getByName("1.1.1.1");
        AtomicInteger resolutions = new AtomicInteger();
        AiProviderEndpointPolicy policy = new AiProviderEndpointPolicy(Set.of("api.trusted.example"), host -> {
            resolutions.incrementAndGet();
            assertEquals("api.trusted.example", host);
            return new InetAddress[]{first, second};
        });

        AiProviderEndpointPolicy.ValidatedEndpoint endpoint =
                policy.validateAndResolveBaseUrl("https://api.trusted.example/v1/");

        assertEquals("https://api.trusted.example/v1", endpoint.baseUrl());
        assertEquals("api.trusted.example", endpoint.tlsHost());
        assertArrayEquals(new InetAddress[]{first, second}, endpoint.verifiedAddresses());
        assertEquals(1, resolutions.get());
    }

    @Test
    void blocksPrivateMetadataAndMixedDnsAnswers() throws Exception {
        AiProviderEndpointPolicy policy = new AiProviderEndpointPolicy(Set.of(), host -> switch (host) {
            case "private.example" -> addresses("10.12.0.8");
            case "metadata.example" -> addresses("169.254.169.254");
            case "mixed.example" -> addresses("8.8.8.8", "192.168.1.10");
            default -> addresses("8.8.8.8");
        });

        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://private.example"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://metadata.example/latest/meta-data"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://mixed.example/v1"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://127.0.0.1/v1"));
    }

    @Test
    void requiresStandardHttpsWithoutCredentialsQueryFragmentOrRedirectPort() throws Exception {
        AiProviderEndpointPolicy policy = publicPolicy(Set.of());

        assertEquals("https://provider.example/openai",
                policy.validateBaseUrl("https://provider.example/openai/"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("http://provider.example/v1"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://user:password@provider.example/v1"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://provider.example/v1?target=internal"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://provider.example/v1#fragment"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://provider.example:8443/v1"));
    }

    @Test
    void optionalAllowlistRestrictsProviderDestinationsAndPermitsSubdomains() throws Exception {
        AiProviderEndpointPolicy policy = publicPolicy(Set.of("*.trusted.example"));

        assertEquals("https://api.trusted.example/v1",
                policy.validateBaseUrl("https://api.trusted.example/v1"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://trusted.example/v1"));
        assertThrows(BizException.class,
                () -> policy.validateBaseUrl("https://attacker.example/v1"));

        AiProviderEndpointPolicy exact = publicPolicy(Set.of("api.trusted.example"));
        assertEquals("https://api.trusted.example/v1",
                exact.validateBaseUrl("https://api.trusted.example/v1"));
        assertThrows(BizException.class,
                () -> exact.validateBaseUrl("https://child.api.trusted.example/v1"));
    }

    private static AiProviderEndpointPolicy publicPolicy(Set<String> allowedHosts) throws Exception {
        InetAddress publicAddress = InetAddress.getByName("8.8.8.8");
        return new AiProviderEndpointPolicy(allowedHosts,
                ignored -> new InetAddress[]{publicAddress});
    }

    private static InetAddress[] addresses(String... values) throws Exception {
        InetAddress[] result = new InetAddress[values.length];
        for (int i = 0; i < values.length; i++) {
            result[i] = InetAddress.getByName(values[i]);
        }
        return result;
    }
}
