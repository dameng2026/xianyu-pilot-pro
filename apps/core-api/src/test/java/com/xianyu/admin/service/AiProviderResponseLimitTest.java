package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class AiProviderResponseLimitTest {

    @Test
    void acceptsAResponseAtTheExactByteLimit() throws Exception {
        byte[] body = new byte[32];

        byte[] result = AiProviderService.readResponseBodyLimited(
                new ByteArrayInputStream(body),
                body.length
        );

        assertArrayEquals(body, result);
    }

    @Test
    void rejectsAResponseBeyondTheByteLimit() {
        byte[] body = new byte[33];

        assertThrows(
                AiProviderService.ProviderResponseTooLargeException.class,
                () -> AiProviderService.readResponseBodyLimited(
                        new ByteArrayInputStream(body),
                        body.length - 1
                )
        );
    }
}
