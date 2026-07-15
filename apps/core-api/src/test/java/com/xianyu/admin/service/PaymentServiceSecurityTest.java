package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.UserContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.LinkedHashMap;
import java.util.Map;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

class PaymentServiceSecurityTest {

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void mockPaymentIsGloballyDisabledByDefault() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        PaymentService service = new PaymentService(jdbc);

        BizException error = assertThrows(BizException.class,
                () -> service.mockPayUserOrder("order-1"));

        assertEquals(403, error.getCode());
        verifyNoInteractions(jdbc);
    }

    @Test
    void paymentPrivateKeysAndApiKeysAreEncryptedBeforeDatabaseStorage() {
        class CapturingJdbcTemplate extends JdbcTemplate {
            Object[] inserted;

            @Override
            public int update(String sql, Object... args) {
                if (sql.startsWith("INSERT INTO payment_config")) inserted = args;
                return 1;
            }

            @Override
            public <T> T queryForObject(String sql, Class<T> requiredType, Object... args) {
                if (sql.equals("SELECT LAST_INSERT_ID()")) return requiredType.cast(9L);
                return null;
            }

            @Override
            public <T> T queryForObject(String sql, Class<T> requiredType) {
                if (sql.equals("SELECT LAST_INSERT_ID()")) return requiredType.cast(9L);
                return null;
            }

            @Override
            public java.util.List<Map<String, Object>> queryForList(String sql, Object... args) {
                if (sql.startsWith("SELECT id, channel_type")) {
                    return java.util.List.of(Map.of("id", 9L, "channelType", "wechat"));
                }
                return java.util.List.of();
            }
        }
        CapturingJdbcTemplate jdbc = new CapturingJdbcTemplate();
        PaymentService service = new PaymentService(jdbc);

        service.saveConfig(Map.of(
                "channelType", "wechat",
                "providerType", "official",
                "enabled", 0,
                "sandbox", 0,
                "privateKey", "plain-private-key-material",
                "apiKey", "plain-api-key-material"
        ));

        Object[] values = jdbc.inserted;
        String storedPrivateKey = String.valueOf(values[5]);
        String storedApiKey = String.valueOf(values[7]);
        assertEquals(true, storedPrivateKey.startsWith("enc:v1:"));
        assertEquals(true, storedApiKey.startsWith("enc:v1:"));
        org.junit.jupiter.api.Assertions.assertFalse(storedPrivateKey.contains("plain-private"));
        org.junit.jupiter.api.Assertions.assertFalse(storedApiKey.contains("plain-api"));
    }

    @Test
    void cannotEnableUnimplementedOfficialPaymentInProductionMode() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        PaymentService service = new PaymentService(jdbc);

        BizException error = assertThrows(BizException.class, () -> service.saveConfig(Map.of(
                "channelType", "wechat",
                "providerType", "official",
                "enabled", 1,
                "sandbox", 0
        )));

        assertEquals(503, error.getCode());
        verifyNoInteractions(jdbc);
    }

    @Test
    void cannotEnableYipayWithoutStrongCredentialsAndHttpsGateway() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        PaymentService service = new PaymentService(jdbc);
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("channelType", "alipay");
        config.put("providerType", "yipay");
        config.put("enabled", 1);
        config.put("sandbox", 0);
        config.put("merchantId", "10001");
        config.put("apiKey", "short");
        config.put("gatewayUrl", "http://pay.example.com/submit.php");
        config.put("notifyUrl", "http://merchant.example.com/callback");

        BizException error = assertThrows(BizException.class, () -> service.saveConfig(config));

        assertEquals(400, error.getCode());
        verifyNoInteractions(jdbc);
    }

    @Test
    void unknownPaymentProviderIsRejectedInsteadOfSilentlyUsingOfficial() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        PaymentService service = new PaymentService(jdbc);

        BizException error = assertThrows(BizException.class, () -> service.saveConfig(Map.of(
                "channelType", "alipay",
                "providerType", "unexpected-provider",
                "enabled", 0
        )));

        assertEquals(400, error.getCode());
        verifyNoInteractions(jdbc);
    }

    @Test
    void databaseOutageIsNotReportedAsMissingRechargePlan() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        PaymentService service = new PaymentService(jdbc);
        ReflectionTestUtils.setField(service, "sandboxModeEnabled", true);
        UserContext.set(7L, "payer", 3L);
        when(jdbc.queryForList(startsWith("SELECT * FROM payment_config"), eq("alipay")))
                .thenReturn(java.util.List.of(Map.of(
                        "id", 2L,
                        "provider_type", "yipay",
                        "sandbox", 1
                )));
        when(jdbc.queryForList(startsWith("SELECT id, plan_name, token_amount"), eq(9L)))
                .thenThrow(new DataAccessResourceFailureException("database unavailable"));

        BizException error = assertThrows(BizException.class, () -> service.createOrder(Map.of(
                "orderType", "token",
                "paymentMethod", "alipay",
                "tokenPlanId", 9L
        ), "127.0.0.1"));

        assertEquals(503, error.getCode());
    }

    @Test
    void ledgerFailureAbortsTokenPaymentInsteadOfCreatingAnUnbalancedRecharge() {
        class LedgerFailingJdbcTemplate extends JdbcTemplate {
            @Override
            public java.util.List<Map<String, Object>> queryForList(String sql, Object... args) {
                if (sql.startsWith("SELECT * FROM payment_order")) {
                    return java.util.List.of(new LinkedHashMap<>(Map.of(
                            "id", 11L,
                            "tenant_id", 3L,
                            "user_id", 7L,
                            "order_no", "TOK-1",
                            "order_type", "token",
                            "token_amount", 20L,
                            "status", 0
                    )));
                }
                if (sql.startsWith("SELECT token_balance FROM sys_user")) {
                    return java.util.List.of(Map.of("token_balance", 100L));
                }
                if (sql.startsWith("SELECT o.id")) {
                    return java.util.List.of(new LinkedHashMap<>(Map.of(
                            "id", 11L,
                            "orderNo", "TOK-1",
                            "orderType", "token",
                            "paymentMethod", "alipay",
                            "amountCent", 100L,
                            "status", 1
                    )));
                }
                return java.util.List.of();
            }

            @Override
            public int update(String sql, Object... args) {
                if (sql.startsWith("INSERT INTO token_balance_ledger")) {
                    throw new DataAccessResourceFailureException("ledger unavailable");
                }
                return 1;
            }
        }
        PaymentService service = new PaymentService(new LedgerFailingJdbcTemplate());
        ReflectionTestUtils.setField(service, "sandboxModeEnabled", true);

        BizException error = assertThrows(BizException.class, () -> service.mockPay("TOK-1"));

        assertEquals(503, error.getCode());
    }

    @Test
    void callbackMoneyWithSubCentPrecisionIsRejectedInsteadOfTruncated() {
        JdbcTemplate jdbc = callbackJdbc("order-precision");
        PaymentService service = new PaymentService(jdbc);
        Map<String, Object> payload = signedPayload(Map.of(
                "out_trade_no", "order-precision",
                "money", "1.001",
                "pid", "10001",
                "type", "alipay",
                "trade_no", "gateway-trade-precision",
                "trade_status", "TRADE_SUCCESS"
        ));

        BizException error = assertThrows(BizException.class,
                () -> service.handleCallback("alipay", payload, String.valueOf(payload)));

        assertEquals(400, error.getCode());
        verify(jdbc, never()).update(startsWith("UPDATE payment_order SET status=1"),
                org.mockito.ArgumentMatchers.<Object[]>any());
    }

    @Test
    void signedFailedPaymentNotificationCannotMarkOrderPaid() {
        JdbcTemplate jdbc = callbackJdbc("order-1");
        PaymentService service = new PaymentService(jdbc);
        Map<String, Object> payload = signedPayload(Map.of(
                "out_trade_no", "order-1",
                "money", "1.00",
                "pid", "10001",
                "type", "alipay",
                "trade_no", "gateway-trade-1",
                "trade_status", "TRADE_CLOSED"
        ));

        BizException error = assertThrows(BizException.class,
                () -> service.handleCallback("alipay", payload, String.valueOf(payload)));

        assertEquals(400, error.getCode());
        verify(jdbc, never()).update(startsWith("UPDATE payment_order SET status=1"),
                org.mockito.ArgumentMatchers.<Object[]>any());
    }

    @Test
    void signedCallbackWithoutExplicitAmountCannotUseOrderAmountAsFallback() {
        JdbcTemplate jdbc = callbackJdbc("order-2");
        PaymentService service = new PaymentService(jdbc);
        Map<String, Object> payload = signedPayload(Map.of(
                "out_trade_no", "order-2",
                "pid", "10001",
                "type", "alipay",
                "trade_no", "gateway-trade-2",
                "trade_status", "TRADE_SUCCESS"
        ));

        BizException error = assertThrows(BizException.class,
                () -> service.handleCallback("alipay", payload, String.valueOf(payload)));

        assertEquals(400, error.getCode());
        verify(jdbc, never()).update(startsWith("UPDATE payment_order SET status=1"),
                org.mockito.ArgumentMatchers.<Object[]>any());
    }

    private JdbcTemplate callbackJdbc(String orderNo) {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        Map<String, Object> order = new LinkedHashMap<>();
        order.put("order_no", orderNo);
        order.put("payment_method", "alipay");
        order.put("provider_type", "yipay");
        order.put("amount_cent", 100L);
        order.put("status", 0);
        order.put("order_type", "ad");
        when(jdbc.queryForList(startsWith("SELECT * FROM payment_order"), eq(orderNo)))
                .thenReturn(java.util.List.of(order));
        when(jdbc.queryForList(startsWith("SELECT * FROM payment_config"), eq("alipay")))
                .thenReturn(java.util.List.of(Map.of(
                        "api_key", "0123456789abcdef0123456789abcdef",
                        "merchant_id", "10001"
                )));
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);
        return jdbc;
    }

    private Map<String, Object> signedPayload(Map<String, Object> unsigned) {
        Map<String, Object> payload = new java.util.TreeMap<>(unsigned);
        String base = payload.entrySet().stream()
                .map(entry -> entry.getKey() + "=" + entry.getValue())
                .collect(java.util.stream.Collectors.joining("&"));
        try {
            payload.put("sign", HexFormat.of().formatHex(MessageDigest.getInstance("MD5")
                    .digest((base + "0123456789abcdef0123456789abcdef").getBytes(StandardCharsets.UTF_8))));
        } catch (Exception e) {
            throw new AssertionError(e);
        }
        payload.put("sign_type", "MD5");
        return payload;
    }
}
