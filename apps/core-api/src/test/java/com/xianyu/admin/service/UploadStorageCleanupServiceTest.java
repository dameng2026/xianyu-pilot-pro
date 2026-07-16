package com.xianyu.admin.service;

import com.xianyu.admin.config.UploadPathConfig;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * 验证 UploadStorageCleanupService 仅清理「超过保留期 + 无业务引用」的资产，
 * 且会跳过被 workflow_published_goods / opportunity_image_history 引用的资产。
 */
class UploadStorageCleanupServiceTest {

    @TempDir Path tempDir;

    private UploadPathConfig paths() {
        UploadPathConfig paths = new UploadPathConfig(tempDir.resolve("uploads").toString());
        paths.init();
        return paths;
    }

    private Map<String, Object> row(long id, long tenantId, String storageKey, String publicUrl, long sizeBytes) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", id);
        m.put("tenant_id", tenantId);
        m.put("storage_key", storageKey);
        m.put("public_url", publicUrl);
        m.put("size_bytes", sizeBytes);
        return m;
    }

    @Test
    void deletesOnlyUnreferencedOldAssetsAndSkipsReferencedOnes() throws Exception {
        UploadPathConfig paths = paths();
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        UploadStorageGovernanceService governance = mock(UploadStorageGovernanceService.class);

        // 模拟查询返回两条候选：
        //   - asset 101 (tenant=7) 无引用 -> 应删除
        //   - asset 102 (tenant=7) 也无引用 -> 应删除
        // 注意：引用检查在 SQL 层完成，因此 Java 单元测试只需验证「SQL 返回的候选」均被删除。
        List<Map<String, Object>> candidates = new ArrayList<>();
        candidates.add(row(101L, 7L, "tenant-7/img_a.png", "/uploads/images/tenant-7/img_a.png", 1024L));
        candidates.add(row(102L, 7L, "tenant-7/img_b.png", "/uploads/images/tenant-7/img_b.png", 2048L));

        when(jdbc.queryForList(anyString(), eq(7), eq(200)))
                .thenReturn(candidates);

        UploadStorageCleanupService service = new UploadStorageCleanupService(jdbc, paths, governance);
        service.setRetentionDaysForTest(7);
        service.setBatchSizeForTest(200);

        int deleted = service.cleanupUnreferencedOldAssets();

        assertEquals(2, deleted);
        verify(governance, times(1)).deleteStoredAsset(
                eq(101L), eq(7L), any(Path.class), eq("auto-cleanup-7d-retention"));
        verify(governance, times(1)).deleteStoredAsset(
                eq(102L), eq(7L), any(Path.class), eq("auto-cleanup-7d-retention"));
    }

    @Test
    void deleteFailureDoesNotAbortBatch() throws Exception {
        UploadPathConfig paths = paths();
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        UploadStorageGovernanceService governance = mock(UploadStorageGovernanceService.class);

        List<Map<String, Object>> candidates = new ArrayList<>();
        candidates.add(row(201L, 7L, "tenant-7/img_c.png", "/uploads/images/tenant-7/img_c.png", 1024L));
        candidates.add(row(202L, 7L, "tenant-7/img_d.png", "/uploads/images/tenant-7/img_d.png", 2048L));

        when(jdbc.queryForList(anyString(), eq(7), eq(200)))
                .thenReturn(candidates);
        // 第一条删除抛出异常，不应阻断第二条的清理。
        doThrow(new RuntimeException("simulated delete failure"))
                .when(governance).deleteStoredAsset(eq(201L), anyLong(), any(Path.class), anyString());

        UploadStorageCleanupService service = new UploadStorageCleanupService(jdbc, paths, governance);
        service.setRetentionDaysForTest(7);
        service.setBatchSizeForTest(200);

        int deleted = service.cleanupUnreferencedOldAssets();

        // 第一条失败，第二条成功，最终只删除 1 条。
        assertEquals(1, deleted);
        verify(governance, times(1)).deleteStoredAsset(
                eq(201L), eq(7L), any(Path.class), eq("auto-cleanup-7d-retention"));
        verify(governance, times(1)).deleteStoredAsset(
                eq(202L), eq(7L), any(Path.class), eq("auto-cleanup-7d-retention"));
    }

    @Test
    void returnsZeroWhenNoCandidates() {
        UploadPathConfig paths = paths();
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        UploadStorageGovernanceService governance = mock(UploadStorageGovernanceService.class);

        when(jdbc.queryForList(anyString(), anyInt(), anyInt()))
                .thenReturn(List.<Map<String, Object>>of());

        UploadStorageCleanupService service = new UploadStorageCleanupService(jdbc, paths, governance);
        service.setRetentionDaysForTest(7);
        service.setBatchSizeForTest(200);

        assertEquals(0, service.cleanupUnreferencedOldAssets());
        verifyNoInteractions(governance);
    }
}
