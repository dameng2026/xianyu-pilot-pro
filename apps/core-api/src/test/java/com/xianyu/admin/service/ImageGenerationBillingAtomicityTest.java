package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ImageGenerationBillingAtomicityTest {

    @Test
    void balanceUsageAndLedgerCommitTogether() {
        JdbcTemplate jdbc = billingJdbc();
        PlatformTransactionManager tx = mock(PlatformTransactionManager.class);
        TransactionStatus status = mock(TransactionStatus.class);
        when(tx.getTransaction(any(TransactionDefinition.class))).thenReturn(status);
        ImageGenerationService service = service(jdbc, tx);

        ImageGenerationService.BillingResult result = service.recordSuccessfulBilling(
                9L, 77L, "req-1", "image-model", 2, "1024x1024", 30, 12, "{}");

        assertEquals(100L, result.beforeBalance());
        assertEquals(70L, result.afterBalance());
        verify(tx).commit(status);
        verify(tx, never()).rollback(status);
        verify(jdbc).update(
                argThat(sql -> sql.startsWith("UPDATE sys_user SET token_balance=")),
                eq(70L), eq(77L));
    }

    @Test
    void ledgerFailureRollsBackTheWholeBillingTransaction() {
        JdbcTemplate jdbc = billingJdbc();
        doThrow(new DataAccessResourceFailureException("ledger unavailable"))
                .when(jdbc).update(
                        argThat(sql -> sql.startsWith("INSERT INTO token_balance_ledger")),
                        any(Object[].class));
        PlatformTransactionManager tx = mock(PlatformTransactionManager.class);
        TransactionStatus status = mock(TransactionStatus.class);
        when(tx.getTransaction(any(TransactionDefinition.class))).thenReturn(status);
        ImageGenerationService service = service(jdbc, tx);

        assertThrows(DataAccessResourceFailureException.class, () -> service.recordSuccessfulBilling(
                9L, 77L, "req-2", "image-model", 2, "1024x1024", 30, 12, "{}"));

        verify(tx).rollback(status);
        verify(tx, never()).commit(status);
    }

    private JdbcTemplate billingJdbc() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());
        when(jdbc.queryForObject(
                argThat(sql -> sql.contains("FOR UPDATE")),
                eq(Long.class),
                eq(77L))).thenReturn(100L);
        when(jdbc.queryForObject("SELECT LAST_INSERT_ID()", Long.class)).thenReturn(5L);
        doReturn(1).when(jdbc).update(
                argThat(sql -> sql.startsWith("UPDATE sys_user SET token_balance=")),
                any(Object[].class));
        doReturn(1).when(jdbc).update(
                argThat(sql -> sql.startsWith("INSERT INTO ai_usage_log")),
                any(Object[].class));
        doReturn(1).when(jdbc).update(
                argThat(sql -> sql.startsWith("INSERT INTO token_balance_ledger")),
                any(Object[].class));
        return jdbc;
    }

    private ImageGenerationService service(JdbcTemplate jdbc, PlatformTransactionManager tx) {
        return new ImageGenerationService(
                mock(ModelConfigService.class),
                jdbc,
                mock(AiProviderService.class),
                mock(ImageProxyService.class),
                mock(ImageCacheService.class),
                mock(CookieCryptoService.class),
                tx
        );
    }
}
