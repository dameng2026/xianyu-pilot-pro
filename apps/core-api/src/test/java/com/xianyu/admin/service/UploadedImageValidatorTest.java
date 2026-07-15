package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class UploadedImageValidatorTest {
    private static final byte[] PNG = java.util.Base64.getDecoder().decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=");
    private static final byte[] WEBP = java.util.Base64.getDecoder().decode(
            "UklGRhwAAABXRUJQVlA4TA8AAAAvAUAAAAcQ/Y/+ByKi/wEA");

    private final UploadedImageValidator validator = new UploadedImageValidator();

    @Test
    void rejectsContentTypeSpoofingAndSvg() {
        MockMultipartFile spoofed = new MockMultipartFile(
                "file", "payload.html", "image/png", "<script>alert(1)</script>".getBytes());
        MockMultipartFile svg = new MockMultipartFile(
                "file", "logo.svg", "image/svg+xml", "<svg onload='alert(1)'></svg>".getBytes());

        assertThrows(IllegalArgumentException.class, () -> validator.validate(spoofed, 2_000_000));
        assertThrows(IllegalArgumentException.class, () -> validator.validate(svg, 2_000_000));
    }

    @Test
    void serverChoosesExtensionFromVerifiedBytesInsteadOfOriginalName() {
        MockMultipartFile misleadingName = new MockMultipartFile(
                "file", "payload.html", "image/png", PNG);

        UploadedImageValidator.ValidatedImage image = validator.validate(misleadingName, 2_000_000);

        assertEquals(".png", image.extension());
        assertEquals("image/png", image.contentType());
    }

    @Test
    void rejectsTruncatedImageThatStillContainsReadableMetadata() {
        byte[] truncated = java.util.Arrays.copyOf(PNG, PNG.length - 12);

        assertThrows(IllegalArgumentException.class,
                () -> validator.validate(truncated, 2_000_000));
    }

    @Test
    void rejectsPngWithCorruptedChunkDataEvenWhenItsDimensionsRemainReadable() {
        byte[] corrupted = PNG.clone();
        corrupted[45] ^= 0x01;

        assertThrows(IllegalArgumentException.class,
                () -> validator.validate(corrupted, 2_000_000));
    }

    @Test
    void parsesAndBoundsEverySupportedWebpChunkType() {
        assertThrows(IllegalArgumentException.class,
                () -> validator.validate(webp("VP8 ", 640, 480), 2_000_000));
        assertThrows(IllegalArgumentException.class,
                () -> validator.validate(webp("VP8L", 321, 123), 2_000_000));
        assertThrows(IllegalArgumentException.class,
                () -> validator.validate(webp("VP8X", 4096, 2048), 2_000_000));

        assertThrows(IllegalArgumentException.class,
                () -> validator.validate(webp("VP8X", 10_001, 100), 2_000_000));
        assertThrows(IllegalArgumentException.class,
                () -> validator.validate(webp("VP8X", 8_000, 8_000), 2_000_000));
    }

    @Test
    void fullyDecodesSupportedGifAndWebpImages() throws Exception {
        ByteArrayOutputStream gifOutput = new ByteArrayOutputStream();
        ImageIO.write(new BufferedImage(2, 2, BufferedImage.TYPE_INT_RGB), "gif", gifOutput);

        UploadedImageValidator.ValidatedImage gif =
                validator.validate(gifOutput.toByteArray(), 2_000_000);
        UploadedImageValidator.ValidatedImage webp = validator.validate(WEBP, 2_000_000);

        assertEquals("image/gif", gif.contentType());
        assertEquals(".gif", gif.extension());
        assertEquals("image/webp", webp.contentType());
        assertEquals(".webp", webp.extension());
    }

    @Test
    void rejectsGifWithoutTrailer() throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        ImageIO.write(new BufferedImage(2, 2, BufferedImage.TYPE_INT_RGB), "gif", output);
        byte[] truncated = java.util.Arrays.copyOf(output.toByteArray(), output.size() - 1);

        assertThrows(IllegalArgumentException.class,
                () -> validator.validate(truncated, 2_000_000));
    }

    private static byte[] webp(String type, int width, int height) {
        byte[] bytes = new byte[30];
        ascii(bytes, 0, "RIFF");
        putLe32(bytes, 4, 22);
        ascii(bytes, 8, "WEBP");
        ascii(bytes, 12, type);
        putLe32(bytes, 16, 10);
        if ("VP8 ".equals(type)) {
            bytes[23] = (byte) 0x9d;
            bytes[24] = 0x01;
            bytes[25] = 0x2a;
            putLe16(bytes, 26, width);
            putLe16(bytes, 28, height);
        } else if ("VP8L".equals(type)) {
            int w = width - 1;
            int h = height - 1;
            bytes[20] = 0x2f;
            bytes[21] = (byte) (w & 0xff);
            bytes[22] = (byte) (((w >>> 8) & 0x3f) | ((h & 0x03) << 6));
            bytes[23] = (byte) ((h >>> 2) & 0xff);
            bytes[24] = (byte) ((h >>> 10) & 0x0f);
        } else {
            putLe24(bytes, 24, width - 1);
            putLe24(bytes, 27, height - 1);
        }
        return bytes;
    }

    private static void ascii(byte[] bytes, int offset, String value) {
        for (int i = 0; i < value.length(); i++) bytes[offset + i] = (byte) value.charAt(i);
    }

    private static void putLe16(byte[] bytes, int offset, int value) {
        bytes[offset] = (byte) value;
        bytes[offset + 1] = (byte) (value >>> 8);
    }

    private static void putLe24(byte[] bytes, int offset, int value) {
        bytes[offset] = (byte) value;
        bytes[offset + 1] = (byte) (value >>> 8);
        bytes[offset + 2] = (byte) (value >>> 16);
    }

    private static void putLe32(byte[] bytes, int offset, int value) {
        bytes[offset] = (byte) value;
        bytes[offset + 1] = (byte) (value >>> 8);
        bytes[offset + 2] = (byte) (value >>> 16);
        bytes[offset + 3] = (byte) (value >>> 24);
    }
}
