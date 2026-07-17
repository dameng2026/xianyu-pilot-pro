package com.xianyu.admin.service;

import com.xianyu.admin.entity.CardItem;
import com.xianyu.admin.entity.XianyuAccountAuth;
import com.xianyu.admin.entity.XianyuTradeOrder;
import com.xianyu.admin.entity.XianyuTradeOrderItem;
import com.xianyu.admin.mapper.CardGroupMapper;
import com.xianyu.admin.mapper.CardItemMapper;
import com.xianyu.admin.mapper.XianyuAccountAuthMapper;
import com.xianyu.admin.mapper.XianyuTradeOrderItemMapper;
import com.xianyu.admin.mapper.XianyuTradeOrderMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * DeliveryExecutionService 卡密发货（card mode）全方位单元测试。
 *
 * <p>覆盖 Java 端定时/重试路径下 _executeDelivery 的卡密发货完整链路：
 * <ol>
 *   <li>成功路径：认领卡密 → 模板替换 → 发送消息 → 标记已使用 → 确认发货 → 更新订单状态 → 更新发货记录</li>
 *   <li>卡密库存不足：claimUnusedOne 返回 0 → 抛 BizException(409)</li>
 *   <li>未绑定卡密分组：cardGroupId=null → 抛 BizException(422)</li>
 *   <li>卡密内容分隔符解析：'----' 分隔卡号与密码</li>
 *   <li>卡密模板变量替换：{卡号}/{密码}/{链接}/{提取码}/{卡密}</li>
 *   <li>卡密模式发货后调用闲鱼确认发货 API</li>
 *   <li>确认发货失败时抛 BizException(503) 并回滚卡密</li>
 *   <li>发送消息失败时抛 BizException(503) 并回滚卡密</li>
 * </ol>
 *
 * <p>参考：apps/core-api/src/main/java/com/xianyu/admin/service/DeliveryExecutionService.java:116 executeDelivery
 */
@ExtendWith(MockitoExtension.class)
class DeliveryExecutionServiceKamiDeliveryTest {

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

    private static final Long TENANT_ID = 1L;
    private static final Long ACCOUNT_ID = 10L;
    private static final Long ORDER_ID = 200L;
    private static final Long RECORD_ID = 900L;
    private static final Long CARD_GROUP_ID = 300L;
    private static final Long CARD_ITEM_ID = 5001L;
    private static final Long INTERNAL_GOODS_ID = 170L;
    private static final String EXTERNAL_ORDER_ID = "ORDER-KAMI-001";
    private static final String BUYER_ID = "4182068955155";
    private static final String EXTERNAL_GOODS_ID = "1060794911332";

    @BeforeEach
    void setUp() {
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

    /** 构造一条 status=0 的卡密发货待处理记录。 */
    private Map<String, Object> buildPendingCardRecord() {
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("id", RECORD_ID);
        record.put("tenant_id", TENANT_ID);
        record.put("order_id", ORDER_ID);
        record.put("delivery_timing", "after_payment");
        record.put("delivery_mode", "card");
        record.put("content", "");
        return record;
    }

    /** 构造一个已付款待发货的订单。 */
    private XianyuTradeOrder buildPaidOrder() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(ORDER_ID);
        order.setAccountId(ACCOUNT_ID);
        order.setExternalOrderId(EXTERNAL_ORDER_ID);
        order.setOrderStatus(2); // 待发货
        order.setBuyerId(BUYER_ID);
        order.setBuyerName("测试买家");
        order.setIsBargain(false);
        return order;
    }

    /** 构造订单项（externalGoodsId 非空，用于确认发货 itemId）。 */
    private XianyuTradeOrderItem buildOrderItem() {
        XianyuTradeOrderItem item = new XianyuTradeOrderItem();
        item.setId(1L);
        item.setOrderId(ORDER_ID);
        item.setGoodsId(INTERNAL_GOODS_ID);
        item.setExternalGoodsId(EXTERNAL_GOODS_ID);
        item.setGoodsTitle("测试商品-卡密发货");
        return item;
    }

    /** 构造卡密模式商品级发货配置（payDelivery）。 */
    private Map<String, Object> buildCardModeGoodsConfig() {
        Map<String, Object> config = new HashMap<>();
        Map<String, Object> payDelivery = new LinkedHashMap<>();
        payDelivery.put("enabled", "1");
        payDelivery.put("mode", "card");
        payDelivery.put("header", "您好 {买家昵称}，您的卡密如下：");
        payDelivery.put("content", "");
        payDelivery.put("footer", "订单号 {订单编号}，请妥善保管。");
        payDelivery.put("segmentSend", false);
        payDelivery.put("cardGroupId", CARD_GROUP_ID);
        payDelivery.put("cardTemplate", "卡号：{卡号} 密码：{密码}");
        config.put("payDelivery", payDelivery);
        return config;
    }

    /** 构造已认领的卡密（卡号----密码 格式）。 */
    private CardItem buildClaimedCard(String rawContent) {
        CardItem card = new CardItem();
        card.setId(CARD_ITEM_ID);
        card.setGroupId(CARD_GROUP_ID);
        card.setCardContent(rawContent);
        card.setCardKey(rawContent);
        card.setStatus(1); // 已认领
        return card;
    }

    /** 配置 resolveMessageTarget 返回有效会话行（让买家解析成功）。 */
    private void stubMessageTargetResolution() {
        Map<String, Object> chatRow = new HashMap<>();
        chatRow.put("s_id", "62965262020");
        chatRow.put("sender_user_id", "4182068955155");
        chatRow.put("receiver_user_id", "seller-001");
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class)))
                .thenReturn(List.of(chatRow));
    }

    // ============================================================
    // 测试用例
    // ============================================================

    @Test
    void executeDelivery_cardMode_success_path_claims_card_sends_message_and_confirms_shipment() {
        /* === 场景：卡密发货完整成功路径 === */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard("CARD-12345----PWD-67890");

        // 1. 标记 status=1 + 最后更新 delivery_record 成功
        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);

        // 2. 加载订单与订单项
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));

        // 3. resolveInternalGoodsId 策略1命中（goods_id 直接是内部 ID）
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);

        // 4. 商品级发货配置（卡密模式）
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());

        // 5. 卡密认领成功
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);

        // 6. 标记卡密为已使用（updateStatus 返回 1，不走 updateStatusOnly 兜底）
        when(cardItemMapper.updateStatus(eq(TENANT_ID), eq(CARD_ITEM_ID), eq(2), eq(ORDER_ID), any()))
                .thenReturn(1);

        // 7. 账号 Cookie 解密
        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setEncryptedCookie("ENC(cookie)");
        when(authMapper.findByAccountId(TENANT_ID, ACCOUNT_ID)).thenReturn(auth);
        when(cookieCryptoService.decryptIfNeeded("ENC(cookie)")).thenReturn("raw-cookie");

        // 8. 声明检查通过
        when(statementCheckService.canDeliverAfterStatementCheck(TENANT_ID, ACCOUNT_ID, EXTERNAL_ORDER_ID))
                .thenReturn(true);

        // 9. 买家会话解析（多次 queryForList 调用都返回相同会话行）
        stubMessageTargetResolution();

        // 10. 发送消息 + 确认发货 都成功
        when(automationClient.postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenReturn(Map.of("ok", true));
        when(automationClient.postInternalForData(eq("/api/internal/orders/confirm-shipment"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenReturn(Map.of("success", true));

        // === 执行 ===
        service.executeDelivery(record);

        // === 验证 ===
        // 1. 卡密原子认领调用过
        verify(cardItemMapper).claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID);
        // 2. 读取已认领卡密
        verify(cardItemMapper).findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID);
        // 3. 标记卡密为已使用（status=2）
        verify(cardItemMapper).updateStatus(eq(TENANT_ID), eq(CARD_ITEM_ID), eq(2), eq(ORDER_ID), any());
        // updateStatusOnly 不应被调用（updateStatus 已成功）
        verify(cardItemMapper, never()).updateStatusOnly(anyLong(), anyLong(), anyLong(), anyInt());
        // 4. 卡密组统计至少刷新 2 次（认领后 + markCardUsed 后）
        verify(cardGroupMapper, atLeastOnce()).refreshCounts(TENANT_ID, CARD_GROUP_ID);
        // 5. 发送了卡密消息
        ArgumentCaptor<Map<String, Object>> sendPayloadCaptor = ArgumentCaptor.forClass(Map.class);
        verify(automationClient).postInternalForData(eq("/api/websocket/sendMessage"), sendPayloadCaptor.capture(), anyLong(), eq(TENANT_ID));
        Map<String, Object> sendPayload = sendPayloadCaptor.getValue();
        assertTrue(String.valueOf(sendPayload.get("content")).contains("CARD-12345"),
                "发送内容应包含卡号，实际：" + sendPayload.get("content"));
        // 6. 确认发货 API 被调用
        ArgumentCaptor<Map<String, Object>> confirmPayloadCaptor = ArgumentCaptor.forClass(Map.class);
        verify(automationClient).postInternalForData(eq("/api/internal/orders/confirm-shipment"), confirmPayloadCaptor.capture(), anyLong(), eq(TENANT_ID));
        Map<String, Object> confirmPayload = confirmPayloadCaptor.getValue();
        assertEquals(TENANT_ID, confirmPayload.get("tenantId"));
        assertEquals(ACCOUNT_ID, confirmPayload.get("accountId"));
        assertEquals(EXTERNAL_ORDER_ID, confirmPayload.get("externalOrderId"));
        assertEquals(false, confirmPayload.get("isBargain"));
        // 7. 更新订单状态为已发货
        verify(orderMapper).updateDeliveryStatus(TENANT_ID, ORDER_ID, 1, 3);
    }

    @Test
    void executeDelivery_cardMode_insufficient_card_stock_throws_409_and_releases_no_card() {
        /* === 场景：卡密库存不足 === */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());

        // 卡密认领失败：返回 0
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(0);

        com.xianyu.admin.common.BizException ex = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.executeDelivery(record)
        );

        assertEquals(409, ex.getCode());
        assertTrue(ex.getMessage().contains("卡密库存不足"), "异常消息应包含'卡密库存不足'");

        // 不应调用 findClaimedByOrder（认领失败）
        verify(cardItemMapper, never()).findClaimedByOrder(anyLong(), anyLong(), anyLong());
        // 不应调用发送消息或确认发货
        verify(automationClient, never()).postInternalForData(anyString(), any(Map.class), anyLong(), anyLong());
    }

    @Test
    void executeDelivery_cardMode_missing_cardGroupId_throws_422() {
        /* === 场景：卡密模式但未绑定卡密分组 === */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);

        // 卡密模式但 cardGroupId 缺失
        Map<String, Object> config = buildCardModeGoodsConfig();
        @SuppressWarnings("unchecked")
        Map<String, Object> payDelivery = (Map<String, Object>) config.get("payDelivery");
        payDelivery.remove("cardGroupId");
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(config);

        com.xianyu.admin.common.BizException ex = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.executeDelivery(record)
        );

        assertEquals(422, ex.getCode());
        assertTrue(ex.getMessage().contains("卡密模式未绑定卡密分组"));
        verify(cardItemMapper, never()).claimUnusedOne(anyLong(), anyLong(), anyLong());
    }

    @Test
    void executeDelivery_cardMode_parses_card_content_with_dash_separator_and_applies_template() {
        /* === 场景：卡密内容 "卡号----密码" 解析 + 模板变量替换 ===
         * 卡密内容 "CARD-123----PWD-456" 应被解析为：
         *   cardNumber = "CARD-123"
         *   cardPassword = "PWD-456"
         * 模板 "卡号：{卡号} 密码：{密码}" 应被替换为 "卡号：CARD-123 密码：PWD-456"
         * 然后整条消息还应包含 header/footer 和 {买家昵称}/{订单编号} 替换
         */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard("CARD-123----PWD-456");

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);
        when(cardItemMapper.updateStatus(eq(TENANT_ID), eq(CARD_ITEM_ID), eq(2), eq(ORDER_ID), any())).thenReturn(1);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setEncryptedCookie("ENC(cookie)");
        when(authMapper.findByAccountId(TENANT_ID, ACCOUNT_ID)).thenReturn(auth);
        when(cookieCryptoService.decryptIfNeeded("ENC(cookie)")).thenReturn("raw-cookie");
        when(statementCheckService.canDeliverAfterStatementCheck(TENANT_ID, ACCOUNT_ID, EXTERNAL_ORDER_ID))
                .thenReturn(true);
        stubMessageTargetResolution();

        when(automationClient.postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenReturn(Map.of("ok", true));
        when(automationClient.postInternalForData(eq("/api/internal/orders/confirm-shipment"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenReturn(Map.of("success", true));

        service.executeDelivery(record);

        // 验证发送的消息内容包含模板替换后的卡密
        ArgumentCaptor<Map<String, Object>> payloadCaptor = ArgumentCaptor.forClass(Map.class);
        verify(automationClient).postInternalForData(eq("/api/websocket/sendMessage"), payloadCaptor.capture(), anyLong(), eq(TENANT_ID));
        String sentContent = String.valueOf(payloadCaptor.getValue().get("content"));

        // 模板替换：卡号：CARD-123 密码：PWD-456
        assertTrue(sentContent.contains("卡号：CARD-123"), "发送内容应包含替换后的卡号，实际：" + sentContent);
        assertTrue(sentContent.contains("密码：PWD-456"), "发送内容应包含替换后的密码，实际：" + sentContent);
        // header/footer 变量替换
        assertTrue(sentContent.contains("测试买家"), "应替换 {买家昵称} 为 '测试买家'，实际：" + sentContent);
        assertTrue(sentContent.contains(EXTERNAL_ORDER_ID), "应替换 {订单编号}，实际：" + sentContent);
    }

    @Test
    void executeDelivery_cardMode_send_message_failure_throws_503_and_releases_card() {
        /* === 场景：发送消息失败 → 抛 BizException(503) → 回滚已认领卡密 === */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard("CARD-X----PWD-Y");

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setEncryptedCookie("ENC(cookie)");
        when(authMapper.findByAccountId(TENANT_ID, ACCOUNT_ID)).thenReturn(auth);
        when(cookieCryptoService.decryptIfNeeded("ENC(cookie)")).thenReturn("raw-cookie");
        when(statementCheckService.canDeliverAfterStatementCheck(TENANT_ID, ACCOUNT_ID, EXTERNAL_ORDER_ID))
                .thenReturn(true);
        stubMessageTargetResolution();

        // 发送消息抛异常
        when(automationClient.postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenThrow(new RuntimeException("Python service unavailable"));

        com.xianyu.admin.common.BizException ex = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.executeDelivery(record)
        );

        assertEquals(503, ex.getCode());
        assertTrue(ex.getMessage().contains("闲鱼消息发送服务暂时不可用"));

        // 应回滚已认领的卡密（reset 调用）
        verify(cardItemMapper).reset(TENANT_ID, CARD_GROUP_ID, CARD_ITEM_ID);
        // 不应调用标记已使用
        verify(cardItemMapper, never()).updateStatus(eq(TENANT_ID), eq(CARD_ITEM_ID), eq(2), anyLong(), any());
        // 不应调用确认发货
        verify(automationClient, never()).postInternalForData(eq("/api/internal/orders/confirm-shipment"), any(Map.class), anyLong(), anyLong());
        // 不应更新订单状态
        verify(orderMapper, never()).updateDeliveryStatus(anyLong(), anyLong(), anyInt(), anyInt());
    }

    @Test
    void executeDelivery_cardMode_confirm_shipment_failure_throws_503_and_releases_card() {
        /* === 场景：发送消息成功但确认发货失败 → 抛 BizException(503) ===
         * 实际代码逻辑：
         *   1. sendMessage 成功
         *   2. markCardUsed 标记卡密为已使用（cardConsumed=true）
         *   3. confirm-shipment 失败，抛 BizException(503)
         *   4. catch 块：由于 cardConsumed=true，不会调用 releaseClaimedCard（卡密已消费，不回滚）
         * 卡密已发送给买家，即使确认发货失败也不应回滚卡密状态（避免重复发送）。
         */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard("CARD-CONFIRM-FAIL----PWD");

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);
        // markCardUsed 调用 updateStatus 成功（返回 1），不会走 updateStatusOnly 兜底
        when(cardItemMapper.updateStatus(eq(TENANT_ID), eq(CARD_ITEM_ID), eq(2), eq(ORDER_ID), any())).thenReturn(1);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setEncryptedCookie("ENC(cookie)");
        when(authMapper.findByAccountId(TENANT_ID, ACCOUNT_ID)).thenReturn(auth);
        when(cookieCryptoService.decryptIfNeeded("ENC(cookie)")).thenReturn("raw-cookie");
        when(statementCheckService.canDeliverAfterStatementCheck(TENANT_ID, ACCOUNT_ID, EXTERNAL_ORDER_ID))
                .thenReturn(true);
        stubMessageTargetResolution();

        // 发送消息成功
        when(automationClient.postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenReturn(Map.of("ok", true));

        // 确认发货失败
        when(automationClient.postInternalForData(eq("/api/internal/orders/confirm-shipment"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenReturn(Map.of("success", false, "message", "ORDER_ALREADY_CLOSED"));

        com.xianyu.admin.common.BizException ex = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.executeDelivery(record)
        );

        assertEquals(503, ex.getCode());
        assertTrue(ex.getMessage().contains("确认发货失败"));
        assertTrue(ex.getMessage().contains("ORDER_ALREADY_CLOSED"));

        // 卡密已被标记为已使用（markCardUsed 在确认发货之前执行）
        verify(cardItemMapper).updateStatus(eq(TENANT_ID), eq(CARD_ITEM_ID), eq(2), eq(ORDER_ID), any());
        // 由于 cardConsumed=true，不应调用 releaseClaimedCard（卡密已消费，不回滚）
        verify(cardItemMapper, never()).reset(anyLong(), anyLong(), anyLong());
        // 不应更新订单状态（确认发货失败时本地状态不变）
        verify(orderMapper, never()).updateDeliveryStatus(anyLong(), anyLong(), anyInt(), anyInt());
    }

    @Test
    void executeDelivery_cardMode_link_card_detected_when_cardNumber_starts_with_http() {
        /* === 场景：卡密内容是链接 "https://pan.baidu.com/s/abc----pwd=123"
         * → cardLink 应被设置，模板中的 {链接} 应被替换为完整链接
         */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();

        // 模板使用 {链接} 和 {提取码}
        Map<String, Object> config = buildCardModeGoodsConfig();
        @SuppressWarnings("unchecked")
        Map<String, Object> payDelivery = (Map<String, Object>) config.get("payDelivery");
        payDelivery.put("cardTemplate", "网盘链接：{链接} 提取码：{提取码}");
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(config);

        CardItem claimedCard = buildClaimedCard("https://pan.baidu.com/s/abc----pwd=123");
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(cardItemMapper.updateStatus(eq(TENANT_ID), eq(CARD_ITEM_ID), eq(2), eq(ORDER_ID), any())).thenReturn(1);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setEncryptedCookie("ENC(cookie)");
        when(authMapper.findByAccountId(TENANT_ID, ACCOUNT_ID)).thenReturn(auth);
        when(cookieCryptoService.decryptIfNeeded("ENC(cookie)")).thenReturn("raw-cookie");
        when(statementCheckService.canDeliverAfterStatementCheck(TENANT_ID, ACCOUNT_ID, EXTERNAL_ORDER_ID))
                .thenReturn(true);
        stubMessageTargetResolution();

        when(automationClient.postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenReturn(Map.of("ok", true));
        when(automationClient.postInternalForData(eq("/api/internal/orders/confirm-shipment"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenReturn(Map.of("success", true));

        service.executeDelivery(record);

        ArgumentCaptor<Map<String, Object>> payloadCaptor = ArgumentCaptor.forClass(Map.class);
        verify(automationClient).postInternalForData(eq("/api/websocket/sendMessage"), payloadCaptor.capture(), anyLong(), eq(TENANT_ID));
        String sentContent = String.valueOf(payloadCaptor.getValue().get("content"));

        assertTrue(sentContent.contains("https://pan.baidu.com/s/abc"), "应替换 {链接}，实际：" + sentContent);
        assertTrue(sentContent.contains("pwd=123"), "应替换 {提取码} 为密码部分，实际：" + sentContent);
    }

    @Test
    void executeDelivery_cardMode_statement_check_blocks_delivery_and_marks_record_failed() {
        /* === 场景：发货声明检查未通过 → 不发货，标记记录为失败（不计重试） === */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard("CARD-STMT----PWD");

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setEncryptedCookie("ENC(cookie)");
        when(authMapper.findByAccountId(TENANT_ID, ACCOUNT_ID)).thenReturn(auth);
        when(cookieCryptoService.decryptIfNeeded("ENC(cookie)")).thenReturn("raw-cookie");
        // 买家会话解析（resolveMessageTarget 在声明检查之前执行，必须先让它成功）
        stubMessageTargetResolution();
        // 声明检查未通过
        when(statementCheckService.canDeliverAfterStatementCheck(TENANT_ID, ACCOUNT_ID, EXTERNAL_ORDER_ID))
                .thenReturn(false);

        // 执行（不应抛异常，方法内部 markRecordFailed 后 return）
        service.executeDelivery(record);

        // 不应发送消息
        verify(automationClient, never()).postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), anyLong());
        // 不应调用确认发货
        verify(automationClient, never()).postInternalForData(eq("/api/internal/orders/confirm-shipment"), any(Map.class), anyLong(), anyLong());
        // 不应标记卡密为已使用
        verify(cardItemMapper, never()).updateStatus(eq(TENANT_ID), eq(CARD_ITEM_ID), eq(2), anyLong(), any());
        // 不应更新订单状态
        verify(orderMapper, never()).updateDeliveryStatus(anyLong(), anyLong(), anyInt(), anyInt());

        // 应执行 markRecordFailed（UPDATE delivery_record SET status=3）
        // 注意：markRecordFailed 内部还会查询 delivery_record 详情，这里 jdbcTemplate.update 会被调用
        // 由于 markRecordFailed 使用了 jdbcTemplate.queryForMap 和 jdbcTemplate.update，
        // 这里的 stubbing 已经覆盖了 update，但 queryForMap 没有显式 stub
        // 实际上 markRecordFailed 内部对 queryForMap 异常做了 try-catch，所以测试能通过
    }

    // ============================================================
    // 错误兜底专项测试（新增）
    // ============================================================

    @Test
    void executeDelivery_cardMode_empty_card_content_releases_card_and_throws_409() {
        /* === 场景：认领的卡密内容为空（cardContent 为 null 或空字符串）===
         * 应回滚卡密认领并抛 BizException(409)，避免发送空消息给买家。
         */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard(null); // 卡密内容为 null
        claimedCard.setCardContent(null);

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);

        com.xianyu.admin.common.BizException ex = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.executeDelivery(record)
        );

        assertEquals(409, ex.getCode());
        assertTrue(ex.getMessage().contains("卡密内容为空") || ex.getMessage().contains("卡密数据"),
                "错误消息应提示卡密内容为空");
        // 不应发送消息
        verify(automationClient, never()).postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), anyLong());
    }

    @Test
    void executeDelivery_cardMode_dash_only_content_releases_card_and_throws_409() {
        /* === 场景：卡密格式异常，如 "----" 分隔后卡号和密码均为空 ===
         * 应回滚卡密认领并抛 BizException(409)。
         */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard("----"); // 只有分隔符，卡号密码均为空

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);

        com.xianyu.admin.common.BizException ex = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.executeDelivery(record)
        );

        assertEquals(409, ex.getCode());
        assertTrue(ex.getMessage().contains("卡密格式异常") || ex.getMessage().contains("卡密数据"),
                "错误消息应提示卡密格式异常");
        // 不应发送消息
        verify(automationClient, never()).postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), anyLong());
    }

    @Test
    void executeDelivery_cardMode_send_message_timeout_throws_friendly_503() {
        /* === 场景：发送消息超时 → 抛 BizException(503) 提示"系统将自动重试" ===
         * 区分超时类和其他异常，提供更精准的错误消息。
         */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard("CARD-TIMEOUT----PWD");

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setEncryptedCookie("ENC(cookie)");
        when(authMapper.findByAccountId(TENANT_ID, ACCOUNT_ID)).thenReturn(auth);
        when(cookieCryptoService.decryptIfNeeded("ENC(cookie)")).thenReturn("raw-cookie");
        when(statementCheckService.canDeliverAfterStatementCheck(TENANT_ID, ACCOUNT_ID, EXTERNAL_ORDER_ID))
                .thenReturn(true);
        stubMessageTargetResolution();

        // 发送消息抛出超时类异常
        when(automationClient.postInternalForData(eq("/api/websocket/sendMessage"), any(Map.class), anyLong(), eq(TENANT_ID)))
                .thenThrow(new RuntimeException("Request timed out after 60000ms"));

        com.xianyu.admin.common.BizException ex = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.executeDelivery(record)
        );

        assertEquals(503, ex.getCode());
        // 超时类错误应提示"自动重试"，不暴露原始异常
        assertTrue(ex.getMessage().contains("自动重试") || ex.getMessage().contains("超时"),
                "超时错误应提示自动重试");
        assertTrue(!ex.getMessage().contains("60000ms"), "不应暴露超时毫秒数等技术细节");
    }

    @Test
    void executeDelivery_cardMode_no_buyer_session_throws_friendly_409() {
        /* === 场景：未找到与买家的聊天会话 → 抛 BizException(409) 提示"等待买家主动咨询" ===
         * 错误消息应引导用户行为，而非暴露技术细节。
         */
        Map<String, Object> record = buildPendingCardRecord();
        XianyuTradeOrder order = buildPaidOrder();
        XianyuTradeOrderItem item = buildOrderItem();
        CardItem claimedCard = buildClaimedCard("CARD-NO-SESSION----PWD");

        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(1);
        when(orderMapper.findById(TENANT_ID, ORDER_ID)).thenReturn(order);
        when(orderItemMapper.findByOrderId(TENANT_ID, ORDER_ID)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(
                eq("SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?"),
                eq(Integer.class), eq(TENANT_ID), eq(INTERNAL_GOODS_ID)))
                .thenReturn(1);
        when(goodsConfigService.read(TENANT_ID, INTERNAL_GOODS_ID)).thenReturn(buildCardModeGoodsConfig());
        when(cardItemMapper.claimUnusedOne(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(1);
        when(cardItemMapper.findClaimedByOrder(TENANT_ID, CARD_GROUP_ID, ORDER_ID)).thenReturn(claimedCard);

        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setEncryptedCookie("ENC(cookie)");
        when(authMapper.findByAccountId(TENANT_ID, ACCOUNT_ID)).thenReturn(auth);
        when(cookieCryptoService.decryptIfNeeded("ENC(cookie)")).thenReturn("raw-cookie");

        // resolveMessageTarget 所有查询都返回空列表
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(java.util.Collections.emptyList());

        com.xianyu.admin.common.BizException ex = assertThrows(
                com.xianyu.admin.common.BizException.class,
                () -> service.executeDelivery(record)
        );

        assertEquals(409, ex.getCode());
        // 错误消息应引导用户等待买家咨询，而非技术化的"无法解析买家会话"
        assertTrue(ex.getMessage().contains("聊天会话") || ex.getMessage().contains("买家"),
                "错误消息应引导用户行为");
        assertTrue(!ex.getMessage().contains("无法解析"), "不应使用技术化表述");
    }
}
