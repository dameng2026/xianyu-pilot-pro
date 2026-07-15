package com.xianyu.admin.service;

import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import javax.imageio.ImageIO;
import javax.imageio.ImageReader;
import javax.imageio.stream.ImageInputStream;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.Iterator;
import java.util.zip.CRC32;

/** Verifies upload bytes and chooses a safe server-owned file extension. */
@Component
public class UploadedImageValidator {

    public ValidatedImage validate(MultipartFile file, long maxBytes) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("上传图片为空");
        }
        if (maxBytes <= 0 || file.getSize() > maxBytes) {
            throw new IllegalArgumentException("图片大小超出限制");
        }
        final byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (IOException e) {
            throw new IllegalArgumentException("无法读取上传图片", e);
        }
        return validate(bytes, maxBytes);
    }

    public ValidatedImage validate(byte[] bytes, long maxBytes) {
        if (bytes == null || bytes.length == 0 || maxBytes <= 0 || bytes.length > maxBytes) {
            throw new IllegalArgumentException("图片大小超出限制");
        }
        if (startsWith(bytes, new int[]{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a})) {
            assertCompletePngContainer(bytes);
            assertSafeRasterDimensions(bytes);
            return new ValidatedImage(bytes, "image/png", ".png");
        }
        if (startsWith(bytes, new int[]{0xff, 0xd8, 0xff})) {
            assertCompleteJpegContainer(bytes);
            assertSafeRasterDimensions(bytes);
            return new ValidatedImage(bytes, "image/jpeg", ".jpg");
        }
        if (asciiAt(bytes, 0, "GIF87a") || asciiAt(bytes, 0, "GIF89a")) {
            if ((bytes[bytes.length - 1] & 0xff) != 0x3b) {
                throw new IllegalArgumentException("GIF 图片缺少完整结束标记");
            }
            assertSafeRasterDimensions(bytes);
            return new ValidatedImage(bytes, "image/gif", ".gif");
        }
        WebpDimensions webp = parseWebpDimensions(bytes);
        if (webp != null) {
            assertCompleteWebpContainer(bytes);
            assertSafeDimensions(webp.width(), webp.height());
            // A RIFF/VP8 header is not proof of a complete bitstream.  Accept
            // WebP only when an installed ImageIO provider can fully decode it;
            // the stock runtime has no such provider and therefore fails closed.
            assertSafeRasterDimensions(bytes);
            return new ValidatedImage(bytes, "image/webp", ".webp");
        }
        throw new IllegalArgumentException("图片内容无效，仅支持可完整解码的 PNG、JPEG、GIF 和 WebP");
    }

    /**
     * ImageIO intentionally accepts some truncated PNG streams. Persisting
     * those bytes creates browser/worker dependent behaviour, so also verify
     * the complete chunk envelope and every chunk CRC before decoding.
     */
    private void assertCompletePngContainer(byte[] bytes) {
        int offset = 8;
        boolean firstChunk = true;
        boolean sawImageData = false;
        while (offset <= bytes.length - 12) {
            long dataLength = bigEndianUInt32(bytes, offset);
            long chunkEnd = (long) offset + 12L + dataLength;
            if (dataLength > Integer.MAX_VALUE || chunkEnd > bytes.length) {
                throw new IllegalArgumentException("PNG 图片文件已截断");
            }
            int typeOffset = offset + 4;
            boolean ihdr = asciiAt(bytes, typeOffset, "IHDR");
            boolean idat = asciiAt(bytes, typeOffset, "IDAT");
            boolean iend = asciiAt(bytes, typeOffset, "IEND");
            if (firstChunk && (!ihdr || dataLength != 13L)) {
                throw new IllegalArgumentException("PNG 图片头无效");
            }
            if (idat) sawImageData = true;

            int crcOffset = Math.toIntExact((long) offset + 8L + dataLength);
            CRC32 crc = new CRC32();
            crc.update(bytes, typeOffset, Math.toIntExact(4L + dataLength));
            if (crc.getValue() != bigEndianUInt32(bytes, crcOffset)) {
                throw new IllegalArgumentException("PNG 图片校验失败");
            }
            offset = Math.toIntExact(chunkEnd);
            firstChunk = false;
            if (iend) {
                if (dataLength != 0L || !sawImageData || offset != bytes.length) {
                    throw new IllegalArgumentException("PNG 图片结束标记无效");
                }
                return;
            }
        }
        throw new IllegalArgumentException("PNG 图片缺少完整结束标记");
    }

    private void assertCompleteJpegContainer(byte[] bytes) {
        if (bytes.length < 4
                || (bytes[bytes.length - 2] & 0xff) != 0xff
                || (bytes[bytes.length - 1] & 0xff) != 0xd9) {
            throw new IllegalArgumentException("JPEG 图片缺少完整结束标记");
        }
    }

    private boolean startsWith(byte[] bytes, int[] signature) {
        if (bytes.length < signature.length) return false;
        for (int i = 0; i < signature.length; i++) {
            if ((bytes[i] & 0xff) != signature[i]) return false;
        }
        return true;
    }

    private boolean asciiAt(byte[] bytes, int offset, String value) {
        if (bytes.length < offset + value.length()) return false;
        for (int i = 0; i < value.length(); i++) {
            if ((bytes[offset + i] & 0xff) != value.charAt(i)) return false;
        }
        return true;
    }

    private void assertSafeRasterDimensions(byte[] bytes) {
        try (ImageInputStream input = ImageIO.createImageInputStream(new ByteArrayInputStream(bytes))) {
            if (input == null) throw new IllegalArgumentException("无法解析图片");
            Iterator<ImageReader> readers = ImageIO.getImageReaders(input);
            if (!readers.hasNext()) throw new IllegalArgumentException("图片文件已损坏");
            ImageReader reader = readers.next();
            try {
                reader.setInput(input, true, true);
                int width = reader.getWidth(0);
                int height = reader.getHeight(0);
                assertSafeDimensions(width, height);
                // Metadata dimensions alone do not prove that the compressed
                // bitstream is complete. Decode the first frame so truncated
                // or corrupt uploads cannot be persisted as apparently valid
                // media and fail later in browsers/workers.
                java.awt.image.BufferedImage decoded = reader.read(0);
                if (decoded == null || decoded.getWidth() != width || decoded.getHeight() != height) {
                    throw new IllegalArgumentException("图片文件无法完整解码");
                }
            } finally {
                reader.dispose();
            }
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (IOException e) {
            throw new IllegalArgumentException("图片文件已损坏", e);
        }
    }

    private void assertSafeDimensions(int width, int height) {
        long pixels = (long) width * height;
        if (width <= 0 || height <= 0 || width > 10_000 || height > 10_000
                || pixels > 40_000_000L) {
            throw new IllegalArgumentException("图片尺寸超出安全限制");
        }
    }

    private WebpDimensions parseWebpDimensions(byte[] bytes) {
        if (bytes.length < 30 || !asciiAt(bytes, 0, "RIFF") || !asciiAt(bytes, 8, "WEBP")) {
            return null;
        }
        long riffSize = littleEndianUInt32(bytes, 4);
        long chunkSize = littleEndianUInt32(bytes, 16);
        if (riffSize + 8 > bytes.length || chunkSize > bytes.length - 20L) {
            return null;
        }
        if (asciiAt(bytes, 12, "VP8 ")) {
            if (chunkSize < 10 || (bytes[23] & 0xff) != 0x9d
                    || (bytes[24] & 0xff) != 0x01 || (bytes[25] & 0xff) != 0x2a) {
                return null;
            }
            int width = littleEndianUInt16(bytes, 26) & 0x3fff;
            int height = littleEndianUInt16(bytes, 28) & 0x3fff;
            return new WebpDimensions(width, height);
        }
        if (asciiAt(bytes, 12, "VP8L")) {
            if (chunkSize < 5 || (bytes[20] & 0xff) != 0x2f) {
                return null;
            }
            int b1 = bytes[21] & 0xff;
            int b2 = bytes[22] & 0xff;
            int b3 = bytes[23] & 0xff;
            int b4 = bytes[24] & 0xff;
            int width = 1 + (((b2 & 0x3f) << 8) | b1);
            int height = 1 + (((b4 & 0x0f) << 10) | (b3 << 2) | ((b2 & 0xc0) >> 6));
            return new WebpDimensions(width, height);
        }
        if (asciiAt(bytes, 12, "VP8X")) {
            if (chunkSize < 10) {
                return null;
            }
            int width = 1 + littleEndianUInt24(bytes, 24);
            int height = 1 + littleEndianUInt24(bytes, 27);
            return new WebpDimensions(width, height);
        }
        return null;
    }

    private void assertCompleteWebpContainer(byte[] bytes) {
        long riffSize = littleEndianUInt32(bytes, 4);
        if (riffSize + 8L != bytes.length) {
            throw new IllegalArgumentException("WebP 图片容器长度无效");
        }
        int offset = 12;
        int chunks = 0;
        boolean sawImagePayload = false;
        while (offset <= bytes.length - 8) {
            if (++chunks > 10_000) {
                throw new IllegalArgumentException("WebP 图片块数量超出限制");
            }
            long chunkSize = littleEndianUInt32(bytes, offset + 4);
            long dataEnd = (long) offset + 8L + chunkSize;
            long paddedEnd = dataEnd + (chunkSize & 1L);
            if (chunkSize > Integer.MAX_VALUE || dataEnd > bytes.length || paddedEnd > bytes.length) {
                throw new IllegalArgumentException("WebP 图片文件已截断");
            }
            if (asciiAt(bytes, offset, "VP8 ") || asciiAt(bytes, offset, "VP8L")
                    || asciiAt(bytes, offset, "ANMF")) {
                sawImagePayload = true;
            }
            offset = Math.toIntExact(paddedEnd);
        }
        if (offset != bytes.length || !sawImagePayload) {
            throw new IllegalArgumentException("WebP 图片缺少完整图像数据");
        }
    }

    private int littleEndianUInt16(byte[] bytes, int offset) {
        return (bytes[offset] & 0xff) | ((bytes[offset + 1] & 0xff) << 8);
    }

    private int littleEndianUInt24(byte[] bytes, int offset) {
        return (bytes[offset] & 0xff)
                | ((bytes[offset + 1] & 0xff) << 8)
                | ((bytes[offset + 2] & 0xff) << 16);
    }

    private long littleEndianUInt32(byte[] bytes, int offset) {
        return (bytes[offset] & 0xffL)
                | ((bytes[offset + 1] & 0xffL) << 8)
                | ((bytes[offset + 2] & 0xffL) << 16)
                | ((bytes[offset + 3] & 0xffL) << 24);
    }

    private long bigEndianUInt32(byte[] bytes, int offset) {
        return ((bytes[offset] & 0xffL) << 24)
                | ((bytes[offset + 1] & 0xffL) << 16)
                | ((bytes[offset + 2] & 0xffL) << 8)
                | (bytes[offset + 3] & 0xffL);
    }

    public record ValidatedImage(byte[] bytes, String contentType, String extension) {
        public ValidatedImage {
            bytes = bytes.clone();
        }

        @Override
        public byte[] bytes() {
            return bytes.clone();
        }
    }

    private record WebpDimensions(int width, int height) {}
}
