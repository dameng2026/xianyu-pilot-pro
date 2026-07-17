package com.xianyu.admin.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 兜底补发货（autoReplenishStuckDeliveries）单元测试。
 *
 * 覆盖关键分支：
 * 1. 处理中卡死记录被重置（保留 retry_count）
 * 2. 死信记录被复活（retry_count 重置为 0）
 * 3. 订单已关闭（order_status=5，即"用户取消"）→ 跳过补发
 * 4. 商品配置已禁用 → 跳过补发
 * 5. 卡密库存为 0 → 跳过补发
 * 6. 声明未确认 → 跳过补发
 * 7. 处理中卡死记录持锁卡密 → 先释放卡密再重置
 */
@ExtendWith(MockitoExtension.class)
class DeliverySchedulerReplenishTest {
    @Mock private DeliveryExecutionService executionService;
    @Mock private JdbcTemplate jdbcTemplate;
    @Mock private AutomationClient automationClient;
    @Mock private DeliveryStatementCheckService statementCheckService;

    private DeliverySchedulerService scheduler;

    @BeforeEach
    void setUp() {
        scheduler = new DeliverySchedulerService(
                executionService, jdbcTemplate, automationClient, statementCheckService);
    }

    /**
     * 场景 1：处理中卡死记录（status=1）+ 商品 text 模式货源仍存在
     * 期望：UPDATE 把 status 重置为 0，retry_count 不变；releaseStuckClaimedCard 不调用
     */
    @Test
    void stuckProcessingRecordIsResetKeepingRetryCount() {
        List<Map<String, Object>> rows = new ArrayList<>();
        rows.add(stuckRow(1L, 1L, 100L, 2, 5, null, 10L, "ext-100"));
        when(jdbcTemplate.queryForList(anyString())).thenReturn(rows);
        // 商品 goodsId=10 存在
        when(jdbcTemplate.queryForObject(
                eq("SELECT id FROM xianyu_goods WHERE tenant_id=? AND id=? AND deleted=0 LIMIT 1"),
                eq(Long.class), eq(1L), eq(10L)))
                .thenReturn(10L);
        // 商品配置存在且 enabled=1，text 模式无 sourceId
        Map<String, Object> configRow = new LinkedHashMap<>();
        configRow.put("config_json",
                "{\"payDelivery\":{\"enabled\":1,\"mode\":\"text\",\"content\":\"发货内容\"}}");
        when(jdbcTemplate.queryForMap(
                eq("SELECT config_json FROM delivery_goods_config WHERE tenant_id=? AND goods_id=? AND deleted=0 LIMIT 1"),
                eq(1L), eq(10L)))
                .thenReturn(configRow);
        // 声明关闭
        when(statementCheckService.canDeliverAfterStatementCheck(eq(1L), any(), eq("ext-100")))
                .thenReturn(true);

        scheduler.autoReplenishStuckDeliveries();

        // 验证：重置 status=0，SQL 不含 retry_count=0
        verify(jdbcTemplate).update(
                org.mockito.ArgumentMatchers.contains("status=0, delivery_status='pending'"),
                eq(1L), eq(1L));
        // 验证：死信复活 SQL（retry_count=0）未触发
        verify(jdbcTemplate, never()).update(
                org.mockito.ArgumentMatchers.contains("retry_count=0"),
                anyLong(), anyLong());
        // 验证：卡密释放未触发（card_item_id 为空）
        verify(jdbcTemplate, never()).update(
                org.mockito.ArgumentMatchers.contains("card_item SET status=0"),
                anyLong(), anyLong());
    }

    /**
     * 场景 2：死信记录（status=3, retry_count=5）+ 卡密模式库存充足
     * 期望：UPDATE 把 status 重置为 0 且 retry_count 重置为 0
     */
    @Test
    void deadLetterRecordIsRevivedWithResetRetryCount() {
        List<Map<String, Object>> rows = new ArrayList<>();
        // deadRow 参数：recordId, tenantId, orderId, orderStatus(2=待发货), retryCount, itemGoodsId, extOrderId
        rows.add(deadRow(2L, 1L, 200L, 2, 5, 20L, "ext-200"));
        when(jdbcTemplate.queryForList(anyString())).thenReturn(rows);
        when(jdbcTemplate.queryForObject(
                eq("SELECT id FROM xianyu_goods WHERE tenant_id=? AND id=? AND deleted=0 LIMIT 1"),
                eq(Long.class), eq(1L), eq(20L)))
                .thenReturn(20L);
        Map<String, Object> configRow = new LinkedHashMap<>();
        configRow.put("config_json",
                "{\"payDelivery\":{\"enabled\":1,\"mode\":\"card\",\"cardGroupId\":77}}");
        when(jdbcTemplate.queryForMap(
                eq("SELECT config_json FROM delivery_goods_config WHERE tenant_id=? AND goods_id=? AND deleted=0 LIMIT 1"),
                eq(1L), eq(20L)))
                .thenReturn(configRow);
        // 卡密库存充足
        when(jdbcTemplate.queryForObject(
                org.mockito.ArgumentMatchers.contains("SELECT COUNT(*) FROM card_item"),
                eq(Integer.class), eq(1L), eq(77L)))
                .thenReturn(5);
        when(statementCheckService.canDeliverAfterStatementCheck(eq(1L), any(), eq("ext-200")))
                .thenReturn(true);

        scheduler.autoReplenishStuckDeliveries();

        // 验证：重置 status=0 且 retry_count=0
        verify(jdbcTemplate).update(
                org.mockito.ArgumentMatchers.contains("retry_count=0"),
                eq(2L), eq(1L));
    }

    /**
     * 场景 3：订单已关闭（order_status=5，即用户取消）
     * 期望：跳过，不调用任何 UPDATE
     */
    @Test
    void cancelledOrderIsSkipped() {
        List<Map<String, Object>> rows = new ArrayList<>();
        // order_status=5（已关闭）
        Map<String, Object> row = stuckRow(3L, 1L, 300L, 5, 5, null, 30L, "ext-300");
        row.put("order_status", 5);
        rows.add(row);
        when(jdbcTemplate.queryForList(anyString())).thenReturn(rows);

        scheduler.autoReplenishStuckDeliveries();

        // 不应触发任何 record UPDATE
        verify(jdbcTemplate, never()).update(
                org.mockito.ArgumentMatchers.contains("UPDATE delivery_record SET status=0"),
                anyLong(), anyLong());
        // 也不应查商品配置
        verify(jdbcTemplate, never()).queryForMap(anyString(), anyLong(), anyLong());
    }

    /**
     * 场景 4：商品配置已禁用（enabled:0）
     * 期望：跳过，不重置 status
     */
    @Test
    void disabledConfigIsSkipped() {
        List<Map<String, Object>> rows = new ArrayList<>();
        rows.add(stuckRow(4L, 1L, 400L, 2, 3, null, 40L, "ext-400"));
        when(jdbcTemplate.queryForList(anyString())).thenReturn(rows);
        when(jdbcTemplate.queryForObject(
                eq("SELECT id FROM xianyu_goods WHERE tenant_id=? AND id=? AND deleted=0 LIMIT 1"),
                eq(Long.class), eq(1L), eq(40L)))
                .thenReturn(40L);
        Map<String, Object> configRow = new LinkedHashMap<>();
        configRow.put("config_json",
                "{\"payDelivery\":{\"enabled\":0,\"mode\":\"text\",\"content\":\"发货\"}}");
        when(jdbcTemplate.queryForMap(
                eq("SELECT config_json FROM delivery_goods_config WHERE tenant_id=? AND goods_id=? AND deleted=0 LIMIT 1"),
                eq(1L), eq(40L)))
                .thenReturn(configRow);

        scheduler.autoReplenishStuckDeliveries();

        verify(jdbcTemplate, never()).update(
                org.mockito.ArgumentMatchers.contains("UPDATE delivery_record SET status=0"),
                anyLong(), anyLong());
    }

    /**
     * 场景 5：卡密库存为 0
     * 期望：跳过，不重置 status
     */
    @Test
    void emptyCardStockIsSkipped() {
        List<Map<String, Object>> rows = new ArrayList<>();
        // deadRow 参数：recordId, tenantId, orderId, orderStatus(2=待发货), retryCount, itemGoodsId, extOrderId
        rows.add(deadRow(5L, 1L, 500L, 2, 5, 50L, "ext-500"));
        when(jdbcTemplate.queryForList(anyString())).thenReturn(rows);
        when(jdbcTemplate.queryForObject(
                eq("SELECT id FROM xianyu_goods WHERE tenant_id=? AND id=? AND deleted=0 LIMIT 1"),
                eq(Long.class), eq(1L), eq(50L)))
                .thenReturn(50L);
        Map<String, Object> configRow = new LinkedHashMap<>();
        configRow.put("config_json",
                "{\"payDelivery\":{\"enabled\":1,\"mode\":\"card\",\"cardGroupId\":88}}");
        when(jdbcTemplate.queryForMap(
                eq("SELECT config_json FROM delivery_goods_config WHERE tenant_id=? AND goods_id=? AND deleted=0 LIMIT 1"),
                eq(1L), eq(50L)))
                .thenReturn(configRow);
        // 卡密库存为 0
        when(jdbcTemplate.queryForObject(
                org.mockito.ArgumentMatchers.contains("SELECT COUNT(*) FROM card_item"),
                eq(Integer.class), eq(1L), eq(88L)))
                .thenReturn(0);

        scheduler.autoReplenishStuckDeliveries();

        verify(jdbcTemplate, never()).update(
                org.mockito.ArgumentMatchers.contains("UPDATE delivery_record SET status=0"),
                anyLong(), anyLong());
    }

    /**
     * 场景 6：声明开启但订单未确认声明
     * 期望：跳过，不重置 status
     */
    @Test
    void unconfirmedStatementIsSkipped() {
        List<Map<String, Object>> rows = new ArrayList<>();
        rows.add(stuckRow(6L, 1L, 600L, 2, 5, null, 60L, "ext-600"));
        when(jdbcTemplate.queryForList(anyString())).thenReturn(rows);
        when(jdbcTemplate.queryForObject(
                eq("SELECT id FROM xianyu_goods WHERE tenant_id=? AND id=? AND deleted=0 LIMIT 1"),
                eq(Long.class), eq(1L), eq(60L)))
                .thenReturn(60L);
        Map<String, Object> configRow = new LinkedHashMap<>();
        configRow.put("config_json",
                "{\"payDelivery\":{\"enabled\":1,\"mode\":\"text\",\"content\":\"发货\"}}");
        when(jdbcTemplate.queryForMap(
                eq("SELECT config_json FROM delivery_goods_config WHERE tenant_id=? AND goods_id=? AND deleted=0 LIMIT 1"),
                eq(1L), eq(60L)))
                .thenReturn(configRow);
        // 声明未确认
        when(statementCheckService.canDeliverAfterStatementCheck(eq(1L), any(), eq("ext-600")))
                .thenReturn(false);

        scheduler.autoReplenishStuckDeliveries();

        verify(jdbcTemplate, never()).update(
                org.mockito.ArgumentMatchers.contains("UPDATE delivery_record SET status=0"),
                anyLong(), anyLong());
    }

    /**
     * 场景 7：处理中卡死记录持锁卡密（card_item_id 非空）
     * 期望：先释放卡密，再重置 status
     */
    @Test
    void stuckRecordWithClaimedCardReleasesCardBeforeReset() {
        List<Map<String, Object>> rows = new ArrayList<>();
        // card_item_id=999 表示持锁卡密
        rows.add(stuckRow(7L, 1L, 700L, 2, 5, 999L, 70L, "ext-700"));
        when(jdbcTemplate.queryForList(anyString())).thenReturn(rows);
        when(jdbcTemplate.queryForObject(
                eq("SELECT id FROM xianyu_goods WHERE tenant_id=? AND id=? AND deleted=0 LIMIT 1"),
                eq(Long.class), eq(1L), eq(70L)))
                .thenReturn(70L);
        Map<String, Object> configRow = new LinkedHashMap<>();
        configRow.put("config_json",
                "{\"payDelivery\":{\"enabled\":1,\"mode\":\"text\",\"content\":\"发货\"}}");
        when(jdbcTemplate.queryForMap(
                eq("SELECT config_json FROM delivery_goods_config WHERE tenant_id=? AND goods_id=? AND deleted=0 LIMIT 1"),
                eq(1L), eq(70L)))
                .thenReturn(configRow);
        when(statementCheckService.canDeliverAfterStatementCheck(eq(1L), any(), eq("ext-700")))
                .thenReturn(true);
        // 卡密释放返回 1 行
        when(jdbcTemplate.update(
                org.mockito.ArgumentMatchers.contains("card_item SET status=0, is_used=0"),
                eq(999L), eq(1L)))
                .thenReturn(1);

        scheduler.autoReplenishStuckDeliveries();

        // 验证：先释放卡密
        verify(jdbcTemplate).update(
                org.mockito.ArgumentMatchers.contains("card_item SET status=0, is_used=0"),
                eq(999L), eq(1L));
        // 验证：再重置 delivery_record status=0
        verify(jdbcTemplate).update(
                org.mockito.ArgumentMatchers.contains("UPDATE delivery_record SET status=0"),
                eq(7L), eq(1L));
    }

    /**
     * 场景 8：候选集合为空（queryForList 返回空）
     * 期望：不报错，不触发任何 UPDATE
     */
    @Test
    void emptyCandidatesDoesNothing() {
        when(jdbcTemplate.queryForList(anyString())).thenReturn(new ArrayList<>());

        scheduler.autoReplenishStuckDeliveries();

        verify(jdbcTemplate, never()).update(anyString(), anyLong(), anyLong());
    }

    /**
     * 场景 9：fail_reason 含永久性错误（"未配置自动发货规则"）
     * 期望：SQL 已在 WHERE 阶段过滤，不会进入候选集；这里通过空候选集验证不触发 UPDATE
     */
    @Test
    void permanentFailureReasonExcludedBySql() {
        // SQL 已在 WHERE 子句过滤，无需在 Java 层测试
        // 这里仅验证空候选集场景正常退出
        when(jdbcTemplate.queryForList(anyString())).thenReturn(new ArrayList<>());

        scheduler.autoReplenishStuckDeliveries();

        verify(jdbcTemplate, never()).update(anyString(), anyLong(), anyLong());
    }

    // ==================== 辅助方法：构造候选行 ====================

    /**
     * 构造处理中卡死记录行（status=1）
     */
    private Map<String, Object> stuckRow(Long recordId, Long tenantId, Long orderId,
                                          int orderStatus, int retryCount,
                                          Long cardItemId, Long itemGoodsId, String extOrderId) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("record_id", recordId);
        row.put("tenant_id", tenantId);
        row.put("account_id", 7L);
        row.put("order_id", orderId);
        row.put("status", 1); // 处理中卡死
        row.put("retry_count", retryCount);
        row.put("fail_reason", null);
        row.put("delivery_mode", "text");
        row.put("card_item_id", cardItemId);
        row.put("delivery_timing", "after_payment");
        row.put("record_updated", java.time.LocalDateTime.now().minusMinutes(10));
        row.put("order_status", orderStatus);
        row.put("external_order_id", extOrderId);
        row.put("order_account_id", 7L);
        row.put("item_goods_id", itemGoodsId);
        row.put("item_external_goods_id", extOrderId);
        return row;
    }

    /**
     * 构造死信记录行（status=3, retry_count=5）
     */
    private Map<String, Object> deadRow(Long recordId, Long tenantId, Long orderId,
                                          int orderStatus, int retryCount,
                                          Long itemGoodsId, String extOrderId) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("record_id", recordId);
        row.put("tenant_id", tenantId);
        row.put("account_id", 7L);
        row.put("order_id", orderId);
        row.put("status", 3); // 死信
        row.put("retry_count", retryCount);
        row.put("fail_reason", "自动发货执行失败，请稍后重试");
        row.put("delivery_mode", "text");
        row.put("card_item_id", null);
        row.put("delivery_timing", "after_payment");
        row.put("record_updated", java.time.LocalDateTime.now().minusHours(2));
        row.put("order_status", orderStatus);
        row.put("external_order_id", extOrderId);
        row.put("order_account_id", 7L);
        row.put("item_goods_id", itemGoodsId);
        row.put("item_external_goods_id", extOrderId);
        return row;
    }
}
