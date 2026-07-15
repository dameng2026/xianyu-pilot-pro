package com.xianyu.admin.config;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.UUID;

/**
 * Canonical upload root and durable filesystem operations.
 *
 * The application must not start when the shared upload volume is missing or
 * read-only.  Every Java upload producer resolves through this component so
 * Docker volume mounts, static serving, readiness and writers cannot drift.
 */
@Component
public class UploadPathConfig {
    private final Path root;

    public UploadPathConfig(@Value("${xianyu.upload.root-dir:uploads}") String rootDir) {
        this.root = Path.of(rootDir).toAbsolutePath().normalize();
    }

    @PostConstruct
    public void init() throws IOException {
        Files.createDirectories(root);
        for (String directory : new String[]{"images", "avatars", "cache", "public/logos"}) {
            Files.createDirectories(root.resolve(directory));
        }
        probeWritable();
    }

    public Path root() {
        return root;
    }

    public Path resolve(String first, String... more) {
        Path resolved = root.resolve(Path.of(first, more)).normalize();
        if (!resolved.startsWith(root)) {
            throw new IllegalArgumentException("upload path escapes the configured root");
        }
        return resolved;
    }

    /** Write, fsync and atomically publish one file. */
    public Path writeAtomically(Path target, byte[] content) throws IOException {
        Path normalized = target.toAbsolutePath().normalize();
        if (!normalized.startsWith(root)) {
            throw new IOException("upload path escapes the configured root");
        }
        if (Files.exists(normalized)) {
            throw new IOException("upload target already exists");
        }
        Files.createDirectories(normalized.getParent());
        Path temporary = normalized.resolveSibling(
                normalized.getFileName() + ".part-" + UUID.randomUUID().toString().replace("-", ""));
        try {
            try (FileChannel channel = FileChannel.open(
                    temporary,
                    StandardOpenOption.CREATE_NEW,
                    StandardOpenOption.WRITE)) {
                ByteBuffer buffer = ByteBuffer.wrap(content);
                while (buffer.hasRemaining()) {
                    channel.write(buffer);
                }
                channel.force(true);
            }
            try {
                Files.move(temporary, normalized, StandardCopyOption.ATOMIC_MOVE);
            } catch (AtomicMoveNotSupportedException unsupported) {
                throw new IOException("upload filesystem does not support atomic moves", unsupported);
            }
            return normalized;
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    /** Safe write/fsync/atomic-rename/delete probe used by startup and readiness. */
    public synchronized void probeWritable() throws IOException {
        Path probeDir = resolve(".readiness");
        Files.createDirectories(probeDir);
        String suffix = UUID.randomUUID().toString().replace("-", "");
        Path target = probeDir.resolve("probe-" + suffix);
        try {
            writeAtomically(target, new byte[]{0x58, 0x59});
            if (Files.size(target) != 2L) {
                throw new IOException("upload readiness probe size mismatch");
            }
        } finally {
            Files.deleteIfExists(target);
        }
    }

    public boolean isWritable() {
        try {
            probeWritable();
            return true;
        } catch (IOException | RuntimeException ignored) {
            return false;
        }
    }
}
