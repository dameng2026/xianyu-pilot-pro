package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.config.UploadPathConfig;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.Answers;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.fail;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockingDetails;
import static org.mockito.Mockito.when;

class UploadStorageGovernanceServiceTest {

    @TempDir Path tempDir;

    @Test
    void productionRefusesImplicitOrDisabledGovernanceLimits() {
        Environment environment = mock(Environment.class);
        when(environment.acceptsProfiles(any(Profiles.class))).thenReturn(true);
        UploadStorageGovernanceService service = new UploadStorageGovernanceService(
                mock(JdbcTemplate.class),
                mock(PlatformTransactionManager.class),
                new UploadPathConfig("uploads"),
                environment,
                "", "", "", "", "", "", ""
        );

        assertThrows(IllegalStateException.class, service::init);
    }

    @Test
    void rejectsGlobalConcurrencySmallerThanTenantConcurrency() {
        Environment environment = mock(Environment.class);
        when(environment.acceptsProfiles(any(Profiles.class))).thenReturn(false);
        UploadStorageGovernanceService service = new UploadStorageGovernanceService(
                mock(JdbcTemplate.class),
                mock(PlatformTransactionManager.class),
                new UploadPathConfig("uploads"),
                environment,
                "true", "1000", "999", "30", "60", "4", "3"
        );

        assertThrows(IllegalStateException.class, service::init);
    }

    @Test
    void tenantAndGlobalQuotaFieldsAreAcceptedButNotEnforced() {
        // 存储配额字段已不再用于 enforcement：即使设置为极小值，初始化也能成功。
        Environment environment = mock(Environment.class);
        when(environment.acceptsProfiles(any(Profiles.class))).thenReturn(false);
        UploadStorageGovernanceService service = new UploadStorageGovernanceService(
                mock(JdbcTemplate.class),
                mock(PlatformTransactionManager.class),
                new UploadPathConfig("uploads"),
                environment,
                "true", "1", "1", "30", "60", "2", "8"
        );

        service.init();
    }

    @Test
    void reservationCommitPrecedesNamedLockReleaseAndPersistsVisibilityMetadata() throws Exception {
        List<String> events = new ArrayList<>();
        List<String> calls = new ArrayList<>();
        JdbcTemplate jdbc = mock(JdbcTemplate.class, invocation -> {
            String method = invocation.getMethod().getName();
            calls.add(method + Arrays.deepToString(invocation.getArguments()));
            if ("queryForObject".equals(method)) {
                Object rawSql = invocation.getArgument(0);
                String sql = String.valueOf(rawSql);
                Class<?> resultType = invocation.getArgument(1);
                if (sql.contains("RELEASE_LOCK")) events.add("release");
                if (Integer.class.equals(resultType)) return 1;
                if (Long.class.equals(resultType)) {
                    return sql.contains("LAST_INSERT_ID") ? 55L : 0L;
                }
            }
            if ("update".equals(method)) return 1;
            return Answers.RETURNS_DEFAULTS.answer(invocation);
        });
        RecordingTransactionManager transactions = new RecordingTransactionManager(events);
        UploadPathConfig paths = new UploadPathConfig(tempDir.resolve("uploads").toString());
        paths.init();
        UploadStorageGovernanceService service = service(jdbc, transactions, paths);

        try {
            service.store(
                    7L, 3L, "images/tenant-7/private.png",
                    "/uploads/images/tenant-7/private.png", "image/png", "user-upload",
                    new byte[]{1, 2, 3});
        } catch (RuntimeException failure) {
            fail("unexpected store failure; events=" + events + "; calls=" + calls, failure);
        }
        service.storePublic(
                0L, null, "public/logos/20260711/0123456789abcdef0123456789abcdef.png",
                "/uploads/public/logos/20260711/0123456789abcdef0123456789abcdef.png", "image/png", "system-logo",
                "system-logo", new byte[]{4, 5, 6});

        assertTrue(events.indexOf("commit") >= 0);
        assertTrue(events.indexOf("commit") < events.indexOf("release"));
        assertTrue(calls.stream().anyMatch(call -> call.contains("DELETE FROM tenant_upload_rate_event")));
        assertTrue(calls.stream().anyMatch(call ->
                call.contains("INSERT INTO tenant_storage_asset")
                        && call.contains("visibility") && call.contains("purpose")
                        && call.contains("private") && call.contains("user-upload")));
        assertTrue(calls.stream().anyMatch(call ->
                call.contains("INSERT INTO tenant_storage_asset")
                        && call.contains("public") && call.contains("system-logo")));
        assertArrayEquals(
                new byte[]{4, 5, 6},
                Files.readAllBytes(paths.resolve(
                        "public/logos/20260711/0123456789abcdef0123456789abcdef.png")));
    }

    @Test
    void reserveFailurePathNeverDeletesAnExistingSameKeyFile() throws Exception {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        UploadPathConfig paths = new UploadPathConfig(tempDir.resolve("uploads").toString());
        paths.init();
        Path target = paths.resolve("images/tenant-7/collision.png");
        Files.createDirectories(target.getParent());
        Files.write(target, new byte[]{9, 8, 7});
        UploadStorageGovernanceService service = service(
                jdbc, mock(PlatformTransactionManager.class), paths);

        BizException error = assertThrows(BizException.class, () -> service.store(
                7L, 3L, "images/tenant-7/collision.png",
                "/uploads/images/tenant-7/collision.png", "image/png", "user-upload",
                new byte[]{1, 2, 3}));

        assertEquals(409, error.getCode());
        assertArrayEquals(new byte[]{9, 8, 7}, Files.readAllBytes(target));
        assertTrue(mockingDetails(jdbc).getInvocations().isEmpty());
    }

    @Test
    void publicStoreRejectsAPathOutsideTheExplicitPublicNamespace() throws Exception {
        UploadPathConfig paths = new UploadPathConfig(tempDir.resolve("uploads").toString());
        paths.init();
        UploadStorageGovernanceService service = service(
                mock(JdbcTemplate.class), mock(PlatformTransactionManager.class), paths);

        BizException error = assertThrows(BizException.class, () -> service.storePublic(
                0L, null, "logos/logo.png", "/uploads/logos/logo.png",
                "image/png", "system-logo", "system-logo", new byte[]{1}));

        assertEquals(400, error.getCode());
    }

    @Test
    void publicStoreRejectsUnservableOrWronglyOwnedSystemLogo() throws Exception {
        UploadPathConfig paths = new UploadPathConfig(tempDir.resolve("uploads").toString());
        paths.init();
        UploadStorageGovernanceService service = service(
                mock(JdbcTemplate.class), mock(PlatformTransactionManager.class), paths);
        String key = "public/logos/20260711/0123456789abcdef0123456789abcdef.png";
        String url = "/uploads/" + key;

        assertEquals(400, assertThrows(BizException.class, () -> service.storePublic(
                0L, null, "public/logos/20260711/logo.png",
                "/uploads/public/logos/20260711/logo.png", "image/png",
                "system-logo", "system-logo", new byte[]{1})).getCode());
        assertEquals(400, assertThrows(BizException.class, () -> service.storePublic(
                7L, null, key, url, "image/png",
                "system-logo", "system-logo", new byte[]{1})).getCode());
        assertEquals(400, assertThrows(BizException.class, () -> service.storePublic(
                0L, 8L, key, url, "image/png",
                "system-logo", "system-logo", new byte[]{1})).getCode());
        assertEquals(400, assertThrows(BizException.class, () -> service.storePublic(
                0L, null, key, url, "image/png",
                "carousel", "carousel", new byte[]{1})).getCode());
        assertEquals(400, assertThrows(BizException.class, () -> service.storePublic(
                0L, null, key, url, "image/jpeg",
                "system-logo", "system-logo", new byte[]{1})).getCode());
    }

    private UploadStorageGovernanceService service(
            JdbcTemplate jdbc,
            PlatformTransactionManager transactions,
            UploadPathConfig paths) {
        Environment environment = mock(Environment.class);
        when(environment.acceptsProfiles(any(Profiles.class))).thenReturn(false);
        UploadStorageGovernanceService service = new UploadStorageGovernanceService(
                jdbc, transactions, paths, environment,
                "true", "1000000", "10000000", "30", "60", "2", "8");
        service.init();
        return service;
    }

    private static final class RecordingTransactionManager extends AbstractPlatformTransactionManager {
        private final List<String> events;

        private RecordingTransactionManager(List<String> events) {
            this.events = events;
            setTransactionSynchronization(SYNCHRONIZATION_ALWAYS);
        }

        @Override
        protected Object doGetTransaction() {
            return new Object();
        }

        @Override
        protected void doBegin(Object transaction, TransactionDefinition definition) {
            events.add("begin");
        }

        @Override
        protected void doCommit(DefaultTransactionStatus status) {
            events.add("commit");
        }

        @Override
        protected void doRollback(DefaultTransactionStatus status) {
            events.add("rollback");
        }
    }
}
