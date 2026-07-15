package com.xianyu.admin.service;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionSynchronizationUtils;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OpenSourceContentPersistenceTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void startTransactionSynchronization() {
        TransactionSynchronizationManager.initSynchronization();
    }

    @AfterEach
    void finishTransactionSynchronization() {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationUtils.triggerAfterCompletion(
                    TransactionSynchronization.STATUS_COMMITTED);
            TransactionSynchronizationManager.clearSynchronization();
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    void commercialWriteIsSerializedAndLocksTheLatestDatabaseConfig() {
        when(jdbcTemplate.queryForObject(
                eq("SELECT GET_LOCK(?, 5)"), eq(Integer.class), anyString()))
                .thenReturn(1);
        when(jdbcTemplate.queryForObject(
                eq("SELECT RELEASE_LOCK(?)"), eq(Integer.class), anyString()))
                .thenReturn(1);
        when(jdbcTemplate.queryForObject(
                contains("SELECT json_text FROM admin_module_record"),
                eq(String.class),
                eq("commercial-home"),
                eq("config")))
                .thenThrow(new EmptyResultDataAccessException(1));
        when(jdbcTemplate.query(
                contains("SELECT id FROM admin_module_record"),
                any(RowMapper.class),
                eq("commercial-home"),
                eq("config")))
                .thenReturn(List.of());
        when(jdbcTemplate.update(
                startsWith("INSERT INTO admin_module_record"),
                eq("commercial-home"),
                eq("config"),
                anyString()))
                .thenReturn(1);

        Map<String, Object> saved = new OpenSourceContentService(jdbcTemplate)
                .saveCommercialHomeCarousel(Map.of(
                        "title", "商用首页",
                        "imageUrl", "/uploads/images/tenant-7/carousel_abcd1234.png",
                        "enabled", true
                ));

        assertEquals(1L, saved.get("id"));
        verify(jdbcTemplate).queryForObject(
                contains("LIMIT 1 FOR UPDATE"),
                eq(String.class),
                eq("commercial-home"),
                eq("config"));
    }
}
