package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.mapper.CardGroupMapper;
import com.xianyu.admin.mapper.CardItemMapper;
import com.xianyu.admin.mapper.XianyuAccountAuthMapper;
import com.xianyu.admin.mapper.XianyuTradeOrderItemMapper;
import com.xianyu.admin.mapper.XianyuTradeOrderMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeliveryExecutionServiceFailureBoundaryTest {
    @Mock private JdbcTemplate jdbcTemplate;
    @Mock private AutomationClient automationClient;
    @Mock private XianyuTradeOrderMapper orderMapper;
    @Mock private XianyuTradeOrderItemMapper orderItemMapper;
    @Mock private XianyuAccountAuthMapper authMapper;
    @Mock private CardItemMapper cardItemMapper;
    @Mock private CardGroupMapper cardGroupMapper;
    @Mock private CookieCryptoService cookieCryptoService;
    @Mock private UserNotificationService userNotificationService;
    @Mock private DeliveryGoodsConfigService goodsConfigService;
    @Mock private DeliveryStatementCheckService statementCheckService;
    @Mock private PlatformTransactionManager transactionManager;

    private DeliveryExecutionService service;
    private TransactionStatus transactionStatus;

    @BeforeEach
    void setUp() {
        transactionStatus = new SimpleTransactionStatus();
        when(transactionManager.getTransaction(any(TransactionDefinition.class))).thenReturn(transactionStatus);
        service = new DeliveryExecutionService(
                jdbcTemplate,
                automationClient,
                orderMapper,
                orderItemMapper,
                authMapper,
                cardItemMapper,
                cardGroupMapper,
                cookieCryptoService,
                userNotificationService,
                goodsConfigService,
                statementCheckService,
                transactionManager
        );
    }

    @Test
    void retryRollsBackExecutionAndPersistsOnlyAStableFailureMessage() {
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("id", 9L);
        record.put("tenant_id", 1L);
        record.put("account_id", 7L);
        record.put("order_id", 2L);
        record.put("external_order_id", "order-2");
        record.put("goods_title", "测试商品");

        when(jdbcTemplate.queryForMap(anyString(), any(Object[].class))).thenReturn(record);
        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(1L, 2L)).thenThrow(new RuntimeException("jdbc://secret-host/private-schema"));

        BizException error = assertThrows(BizException.class, () -> service.retryDelivery(9L, 1L));

        assertEquals(503, error.getCode());
        assertEquals("自动发货执行失败，请检查账号登录状态和发货配置后重试", error.getMessage());
        assertFalse(error.getMessage().contains("secret-host"));
        verify(transactionManager).rollback(eq(transactionStatus));
        verify(jdbcTemplate).update(
                org.mockito.ArgumentMatchers.contains("delivery_status='failed'"),
                eq("自动发货执行失败，请检查账号登录状态和发货配置后重试"),
                eq("自动发货执行失败，请检查账号登录状态和发货配置后重试"),
                eq(9L),
                eq(1L)
        );
    }
}
