package com.xianyu.admin.service;

import com.xianyu.admin.mapper.ApiCredentialMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ApiCredentialServiceTest {

    @Mock
    private ApiCredentialMapper mapper;

    @Mock
    private ApiKeyCryptoService cryptoService;

    @Test
    void fullResetIsExplicitAndCompletedOnlyOnce() {
        String operationKey = "api-credential-reset-2026-07-24";
        when(mapper.ensureFullResetOperation(operationKey)).thenReturn(1);
        when(mapper.findFullResetOperationForUpdate(operationKey))
                .thenReturn(operation("pending"));
        when(mapper.findAllTenantsWithCredentials()).thenReturn(List.of(11L, 22L));
        when(cryptoService.encrypt(anyString())).thenReturn("encrypted");
        when(mapper.updateCredential(eq(11L), anyString(), anyString(), eq("encrypted"))).thenReturn(1);
        when(mapper.updateCredential(eq(22L), anyString(), anyString(), eq("encrypted"))).thenReturn(1);
        when(mapper.markFullResetCompleted(operationKey)).thenReturn(1);

        ApiCredentialService service = new ApiCredentialService(mapper, cryptoService);

        assertEquals(2, service.resetAllCredentialsOnce(operationKey));

        verify(mapper).markFullResetCompleted(operationKey);
        verify(mapper).findAllTenantsWithCredentials();
    }

    @Test
    void completedFullResetDoesNotGenerateOrRewriteCredentials() {
        String operationKey = "api-credential-reset-2026-07-24";
        when(mapper.ensureFullResetOperation(operationKey)).thenReturn(0);
        when(mapper.findFullResetOperationForUpdate(operationKey))
                .thenReturn(operation("completed"));

        ApiCredentialService service = new ApiCredentialService(mapper, cryptoService);

        assertEquals(0, service.resetAllCredentialsOnce(operationKey));

        verify(mapper, never()).findAllTenantsWithCredentials();
        verify(mapper, never()).markFullResetCompleted(operationKey);
    }

    @Test
    void fullResetRequiresAnExplicitOperationKey() {
        ApiCredentialService service = new ApiCredentialService(mapper, cryptoService);

        assertThrows(IllegalArgumentException.class, () -> service.resetAllCredentialsOnce(" "));
    }

    private static Map<String, Object> operation(String status) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("status", status);
        return row;
    }
}
