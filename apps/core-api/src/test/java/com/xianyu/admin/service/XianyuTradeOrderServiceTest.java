package com.xianyu.admin.service;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.dto.XianyuTradeOrderVO;
import com.xianyu.admin.entity.XianyuTradeOrder;
import com.xianyu.admin.entity.XianyuTradeOrderItem;
import com.xianyu.admin.mapper.XianyuTradeOrderItemMapper;
import com.xianyu.admin.mapper.XianyuTradeOrderMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.sql.Timestamp;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuTradeOrderServiceTest {

    @Mock
    private XianyuTradeOrderMapper orderMapper;

    @Mock
    private XianyuTradeOrderItemMapper orderItemMapper;

    @Mock
    private JdbcTemplate jdbcTemplate;

    private XianyuTradeOrderService service;

    @BeforeEach
    void setUp() {
        service = new XianyuTradeOrderService(orderMapper, orderItemMapper, jdbcTemplate);
    }

    @Test
    void detailShouldIncludeMultiSpecQuantityAndLatestDeliverySnapshot() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(88L);
        order.setTenantId(1L);
        order.setAccountId(9L);
        order.setExternalOrderId("ORDER-88");
        order.setOrderStatus(2);
        order.setBuyerName("buyer-a");

        XianyuTradeOrderItem item = new XianyuTradeOrderItem();
        item.setId(1L);
        item.setOrderId(88L);
        item.setGoodsTitle("Digital Pack");
        item.setGoodsCount(3);
        item.setSpecName("version");
        item.setSpecValue("standard");

        when(orderMapper.findById(1L, 88L)).thenReturn(order);
        when(orderItemMapper.findByOrderId(1L, 88L)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForList(contains("FROM delivery_record"), eq(1L), eq(88L)))
                .thenReturn(List.of(Map.of(
                        "delivery_method", "manual_text",
                        "delivery_status", "failed",
                        "delivery_fail_reason", "stock out",
                        "delivery_content", "link-1",
                        "quantity_requested", 3,
                        "quantity_sent", 1,
                        "platform_sync_time", Timestamp.valueOf("2026-07-03 10:00:00")
                )));

        XianyuTradeOrderVO detail = service.detail(1L, 88L);

        assertEquals("manual_text", detail.getDeliveryMethod());
        assertEquals("failed", detail.getDeliveryStatus());
        assertEquals("stock out", detail.getDeliveryFailReason());
        assertEquals("link-1", detail.getDeliveryContent());
        assertEquals(3, detail.getQuantityTotal());
        assertEquals(3, detail.getQuantityRequested());
        assertEquals(1, detail.getQuantitySent());
        assertEquals("version: standard", detail.getItems().get(0).getSpecSummary());
    }

    @Test
    void pageShouldExposeItemSummaryForOrdersWithoutEmbeddedItems() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(101L);
        order.setTenantId(1L);
        order.setAccountId(9L);
        order.setExternalOrderId("ORDER-101");
        order.setOrderStatus(3);

        when(orderMapper.count(1L, null, null, null, null)).thenReturn(1);
        when(orderMapper.list(1L, null, null, null, null, 0, 20)).thenReturn(List.of(order));
        when(jdbcTemplate.queryForList(contains("FROM xianyu_trade_order_item"), eq(1L), eq(101L)))
                .thenReturn(List.of(
                        Map.of("order_id", 101L, "goods_title", "Pack A", "goods_count", 2),
                        Map.of("order_id", 101L, "goods_title", "Pack B", "goods_count", 1)
                ));

        PageResult<XianyuTradeOrderVO> result = service.page(1L, null, null, null, null, 1, 20);

        assertEquals("Pack A x2 / Pack B x1", result.getRecords().get(0).getItemSummary());
        assertEquals(3, result.getRecords().get(0).getQuantityTotal());
    }
}
