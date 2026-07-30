package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.function.Executable;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class AdminModuleServiceTruthfulStateTest {
    private JdbcTemplate jdbcTemplate;
    private AiBillingService aiBillingService;
    private AdminModuleService service;

    @BeforeEach
    void setUp() {
        jdbcTemplate = mock(JdbcTemplate.class);
        aiBillingService = mock(AiBillingService.class);
        service = new AdminModuleService(
                jdbcTemplate,
                new ModuleCatalog(),
                mock(SysUserService.class),
                mock(AdminXianyuAccountService.class),
                mock(BillingPlanService.class),
                mock(AdminRealDataModuleService.class),
                aiBillingService
        );
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "licenses", "notify-channels", "notify-logs", "rag"
    })
    void modulesWithoutRealBackendAreExplicitlyUnavailable(String moduleKey) {
        assertUnavailable(() -> service.page(moduleKey, 1, 10, null, null));
        verifyNoInteractions(jdbcTemplate);
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "risk-events", "runtime", "backups", "versions", "alerts", "files"
    })
    void removedModulesAreRejectedAsUnknown(String moduleKey) {
        assertBadRequest(() -> service.page(moduleKey, 1, 10, null, null));
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void unavailableModuleIsRejectedAcrossEveryGenericOperation() {
        assertAll(
                () -> assertUnavailable(() -> service.meta("notify-channels")),
                () -> assertUnavailable(() -> service.detail("notify-channels", 1)),
                () -> assertUnavailable(() -> service.save("notify-channels", Map.of("name", "fake"))),
                () -> assertUnavailable(() -> service.updateStatus("notify-channels", 1, "enabled")),
                () -> assertUnavailable(() -> service.batchUpdateStatus("notify-channels", List.of(1L), "enabled")),
                () -> assertUnavailable(() -> service.delete("notify-channels", 1)),
                () -> assertUnavailable(() -> service.batchDelete("notify-channels", List.of(1L))),
                () -> assertUnavailable(() -> service.stats("notify-channels")),
                () -> assertUnavailable(() -> service.exportCsv("notify-channels", null, null))
        );
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void xianyuStatsDatabaseFailureReturnsSanitized503InsteadOfZeroes() {
        String databaseSecret = "jdbc:mysql://admin:secret@db";
        when(jdbcTemplate.queryForObject(anyString(), eq(Long.class)))
                .thenThrow(new RuntimeException(databaseSecret));

        BizException exception = assertThrows(BizException.class,
                () -> service.stats("xianyu-accounts"));

        assertEquals(503, exception.getCode());
        assertFalse(exception.getMessage().contains(databaseSecret));
    }

    @Test
    void missingOperationLogCapabilityReturns503InsteadOfEmptyEvents() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class))).thenReturn(0);

        assertUnavailable(service::recentEvents);
    }

    @Test
    void dynamicMenusEndpointDoesNotPretendAnEmptyMenuIsAWorkingBackend() {
        assertUnavailable(service::menus);
    }

    @Test
    void saveIsTransactionalAndRollsBackOnAnyException() throws Exception {
        Transactional transactional = AdminModuleService.class
                .getMethod("save", String.class, Map.class)
                .getAnnotation(Transactional.class);

        org.junit.jupiter.api.Assertions.assertNotNull(transactional);
        org.junit.jupiter.api.Assertions.assertArrayEquals(
                new Class<?>[]{Exception.class}, transactional.rollbackFor());
    }

    @Test
    void modelSynchronizationFailureCannotBecomeASuccessfulSave() {
        String dependencySecret = "provider-token-and-private-diagnostic";
        org.mockito.Mockito.doThrow(new RuntimeException(dependencySecret))
                .when(aiBillingService)
                .normalizeAndSyncModelConfig(eq("model-config-chat"), org.mockito.ArgumentMatchers.anyMap());

        BizException exception = assertThrows(BizException.class, () -> service.save(
                "model-config-chat",
                new java.util.LinkedHashMap<>(Map.of("modelName", "demo", "apiKey", "key"))
        ));

        assertEquals(503, exception.getCode());
        assertFalse(exception.getMessage().contains(dependencySecret));
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void dangerousModelEndpointIsRejectedBeforeSecretsCanBeSentOrPersisted() {
        BizException exception = assertThrows(BizException.class, () -> service.save(
                "model-config-general",
                new java.util.LinkedHashMap<>(Map.of(
                        "modelName", "demo",
                        "apiKey", "secret",
                        "baseUrl", "http://169.254.169.254/latest/meta-data"
                ))
        ));

        assertEquals(400, exception.getCode());
        verifyNoInteractions(aiBillingService, jdbcTemplate);
    }

    @Test
    void imageProxyEndpointMustBeIndependentlyAllowedBeforeBearerKeyCanBeUsed() throws Exception {
        AiProviderEndpointPolicy policy = new AiProviderEndpointPolicy(
                java.util.Set.of("api.trusted.example"),
                ignored -> new java.net.InetAddress[]{java.net.InetAddress.getByName("8.8.8.8")});
        AdminModuleService guarded = new AdminModuleService(
                jdbcTemplate,
                new ModuleCatalog(),
                mock(SysUserService.class),
                mock(AdminXianyuAccountService.class),
                mock(BillingPlanService.class),
                mock(AdminRealDataModuleService.class),
                aiBillingService,
                policy
        );

        BizException exception = assertThrows(BizException.class, () -> guarded.save(
                "model-config-image",
                new java.util.LinkedHashMap<>(Map.of(
                        "modelName", "image-model",
                        "apiKey", "secret",
                        "baseUrl", "https://api.trusted.example",
                        "proxyBaseUrl", "https://proxy.attacker.example"
                ))
        ));

        assertEquals(400, exception.getCode());
        verifyNoInteractions(aiBillingService, jdbcTemplate);
    }

    @Test
    void zeroAffectedRowsCannotBecomeSuccessfulGenericMutations() {
        assertAll(
                () -> assertNotFound(() -> service.save("model-config-chat",
                        new java.util.LinkedHashMap<>(Map.of("id", 1L, "modelName", "demo")))),
                () -> assertNotFound(() -> service.updateStatus("model-config-chat", 1L, "正常")),
                () -> assertNotFound(() -> service.batchUpdateStatus("model-config-chat", List.of(1L), "正常")),
                () -> assertNotFound(() -> service.delete("model-config-chat", 1L)),
                () -> assertNotFound(() -> service.batchDelete("model-config-chat", List.of(1L)))
        );
    }

    @Test
    void emptyBatchRequestsAreValidationErrorsInsteadOfSuccessfulZeroCounts() {
        assertAll(
                () -> assertBadRequest(() -> service.batchUpdateStatus("model-config-chat", List.of(), "正常")),
                () -> assertBadRequest(() -> service.batchDelete("model-config-chat", null))
        );
    }

    @Test
    void malformedMutationInputReturns400BeforeCallingDependencies() {
        assertAll(
                () -> assertBadRequest(() -> service.save("model-config-chat",
                        new java.util.LinkedHashMap<>(Map.of("id", "not-a-number")))),
                () -> assertBadRequest(() -> service.updateStatus("model-config-chat", 1L, " ")),
                () -> assertBadRequest(() -> service.batchDelete("model-config-chat", java.util.Arrays.asList(1L, null)))
        );
    }

    private static void assertUnavailable(Executable executable) {
        BizException exception = assertThrows(BizException.class, executable);
        assertEquals(503, exception.getCode());
    }

    private static void assertNotFound(Executable executable) {
        BizException exception = assertThrows(BizException.class, executable);
        assertEquals(404, exception.getCode());
    }

    private static void assertBadRequest(Executable executable) {
        BizException exception = assertThrows(BizException.class, executable);
        assertEquals(400, exception.getCode());
    }
}
