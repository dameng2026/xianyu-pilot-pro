package com.xianyu.admin.config;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class UploadPathConfigTest {

    @TempDir Path tempDir;

    @Test
    void startupProbeAndAtomicWritesUseTheConfiguredRoot() throws Exception {
        UploadPathConfig paths = new UploadPathConfig(tempDir.resolve("uploads").toString());

        paths.init();
        Path target = paths.resolve("images", "tenant-7", "asset.png");
        paths.writeAtomically(target, new byte[]{1, 2, 3});

        assertTrue(paths.isWritable());
        assertArrayEquals(new byte[]{1, 2, 3}, Files.readAllBytes(target));
    }

    @Test
    void startupFailsClosedWhenConfiguredRootCannotBeADirectory() throws Exception {
        Path file = tempDir.resolve("not-a-directory");
        Files.writeString(file, "occupied");
        UploadPathConfig paths = new UploadPathConfig(file.toString());

        assertThrows(IOException.class, paths::init);
    }

    @Test
    void atomicPublishNeverOverwritesAnExistingAsset() throws Exception {
        UploadPathConfig paths = new UploadPathConfig(tempDir.resolve("uploads").toString());
        paths.init();
        Path target = paths.resolve("images", "tenant-7", "asset.png");
        Files.createDirectories(target.getParent());
        Files.write(target, new byte[]{9, 8, 7});

        assertThrows(IOException.class, () -> paths.writeAtomically(target, new byte[]{1, 2, 3}));

        assertArrayEquals(new byte[]{9, 8, 7}, Files.readAllBytes(target));
    }
}
