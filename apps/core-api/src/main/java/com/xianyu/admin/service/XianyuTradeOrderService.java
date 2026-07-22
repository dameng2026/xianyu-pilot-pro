package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.XianyuTradeOrderDTO;
import com.xianyu.admin.dto.XianyuTradeOrderItemVO;
import com.xianyu.admin.dto.XianyuTradeOrderVO;
import com.xianyu.admin.entity.XianyuTradeOrder;
import com.xianyu.admin.entity.XianyuTradeOrderItem;
import com.xianyu.admin.mapper.XianyuTradeOrderItemMapper;
import com.xianyu.admin.mapper.XianyuTradeOrderMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class XianyuTradeOrderService {
    private static final Logger log = LoggerFactory.getLogger(XianyuTradeOrderService.class);

    private final XianyuTradeOrderMapper orderMapper;
    private final XianyuTradeOrderItemMapper orderItemMapper;
    private final JdbcTemplate jdbcTemplate;

    public XianyuTradeOrderService(XianyuTradeOrderMapper orderMapper,
                                   XianyuTradeOrderItemMapper orderItemMapper,
                                   JdbcTemplate jdbcTemplate) {
        this.orderMapper = orderMapper;
        this.orderItemMapper = orderItemMapper;
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 分页查询订单列表
     */
    public PageResult<XianyuTradeOrderVO> page(Long tenantId, Long accountId, String keyword, Integer status, String buyerId,
                                                 int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = orderMapper.count(tenantId, accountId, keyword, status, buyerId);
        List<XianyuTradeOrder> list = orderMapper.list(tenantId, accountId, keyword, status, buyerId, offset, limit);

        List<XianyuTradeOrderVO> records = list.stream()
                .map(this::toVO)
                .collect(Collectors.toCollection(ArrayList::new));
        enrichPageItemSummaries(tenantId, records);
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 查询订单详情（含订单项）
     */
    public XianyuTradeOrderVO detail(Long tenantId, Long id) {
        XianyuTradeOrder order = orderMapper.findById(tenantId, id);
        if (order == null) {
            throw new BizException(404, "订单不存在");
        }

        XianyuTradeOrderVO vo = toVO(order);

        List<XianyuTradeOrderItem> items = orderItemMapper.findByOrderId(tenantId, id);
        if (items != null && !items.isEmpty()) {
            List<XianyuTradeOrderItemVO> itemVOs = new ArrayList<>();
            for (XianyuTradeOrderItem item : items) {
                XianyuTradeOrderItemVO itemVO = new XianyuTradeOrderItemVO();
                itemVO.setId(item.getId());
                itemVO.setOrderId(item.getOrderId());
                itemVO.setGoodsTitle(item.getGoodsTitle());
                itemVO.setGoodsPrice(item.getGoodsPrice());
                itemVO.setGoodsCount(item.getGoodsCount());
                itemVO.setSpecName(item.getSpecName());
                itemVO.setSpecValue(item.getSpecValue());
                itemVO.setSpecSummary(buildSpecSummary(item.getSpecName(), item.getSpecValue()));
                itemVO.setExternalGoodsId(item.getExternalGoodsId());
                itemVOs.add(itemVO);
            }
            vo.setItems(itemVOs);
            vo.setItemSummary(buildItemSummary(itemVOs));
            vo.setQuantityTotal(sumItemQuantity(itemVOs));
        }

        enrichDeliverySnapshot(tenantId, vo);

        return vo;
    }

    /**
     * 查询今日订单金额（按 pay_time 优先、create_time/created_time 兜底确定当日订单，
     * 仅统计 order_status IN (1,2,3,4) 且 deleted=0 的订单 total_amount 之和）。
     * accountId 为 null 时统计当前租户全部账号。
     */
    public BigDecimal todayAmount(Long tenantId, Long accountId) {
        if (tenantId == null) {
            return BigDecimal.ZERO;
        }
        return orderMapper.sumTodayAmountByAccount(tenantId, accountId);
    }

    /**
     * 更新订单
     */
    @Transactional
    public void update(Long tenantId, Long id, XianyuTradeOrderDTO dto) {
        XianyuTradeOrder existing = orderMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "订单不存在");
        }

        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(id);
        order.setTenantId(tenantId);
        order.setOrderStatus(dto.getOrderStatus() != null ? dto.getOrderStatus() : existing.getOrderStatus());
        order.setBuyerName(dto.getBuyerName() != null ? dto.getBuyerName() : existing.getBuyerName());
        order.setBuyerId(dto.getBuyerId() != null ? dto.getBuyerId() : existing.getBuyerId());
        order.setSellerRemark(dto.getSellerRemark() != null ? dto.getSellerRemark() : existing.getSellerRemark());
        orderMapper.update(order);
        log.info("更新订单成功: id={}, tenantId={}", id, tenantId);
    }

    private XianyuTradeOrderVO toVO(XianyuTradeOrder o) {
        XianyuTradeOrderVO vo = new XianyuTradeOrderVO();
        vo.setId(o.getId());
        vo.setAccountId(o.getAccountId());
        vo.setExternalOrderId(o.getExternalOrderId());
        vo.setOrderStatus(o.getOrderStatus());
        vo.setTotalAmount(o.getTotalAmount());
        vo.setBuyerName(o.getBuyerName());
        vo.setBuyerId(o.getBuyerId());
        vo.setCreateTime(o.getCreateTime());
        vo.setPayTime(o.getPayTime());
        vo.setShipTime(o.getShipTime());
        vo.setItemId(o.getItemId());
        vo.setSellerRemark(o.getSellerRemark());
        vo.setIsBargain(o.getIsBargain());
        vo.setIsRated(o.getIsRated());
        vo.setIsRedFlower(o.getIsRedFlower());
        return vo;
    }

    private void enrichPageItemSummaries(Long tenantId, List<XianyuTradeOrderVO> records) {
        if (records == null || records.isEmpty()) {
            return;
        }
        List<Long> orderIds = records.stream()
                .map(XianyuTradeOrderVO::getId)
                .filter(Objects::nonNull)
                .toList();
        Map<Long, List<Map<String, Object>>> rowsByOrderId = queryOrderItemsForSummaryBatch(tenantId, orderIds);
        Set<String> externalIds = new HashSet<>();
        // 1) 从订单项表收集 external_goods_id
        for (List<Map<String, Object>> rows : rowsByOrderId.values()) {
            for (Map<String, Object> row : rows) {
                String externalId = asString(row.get("external_goods_id"));
                if (externalId != null && !externalId.isBlank()) {
                    externalIds.add(externalId);
                }
            }
        }
        // 2) 兜底：从订单顶层 item_id 收集（订单项为空时使用）
        for (XianyuTradeOrderVO vo : records) {
            String orderItemId = vo.getItemId();
            if (orderItemId != null && !orderItemId.isBlank()) {
                externalIds.add(orderItemId);
            }
        }
        Map<String, GoodsInfo> goodsInfoMap = loadGoodsInfoByExternalIds(tenantId, externalIds);
        for (XianyuTradeOrderVO vo : records) {
            List<Map<String, Object>> rows = rowsByOrderId.getOrDefault(vo.getId(), Collections.emptyList());
            applyPageItemSummary(vo, rows, goodsInfoMap);
        }
    }

    private void enrichPageItemSummary(Long tenantId, XianyuTradeOrderVO vo) {
        List<Map<String, Object>> rows = queryOrderItemsForSummary(tenantId, vo.getId());
        Set<String> externalIds = new HashSet<>();
        for (Map<String, Object> row : rows) {
            String externalId = asString(row.get("external_goods_id"));
            if (externalId != null && !externalId.isBlank()) {
                externalIds.add(externalId);
            }
        }
        // 兜底：订单顶层 item_id
        String orderItemId = vo.getItemId();
        if (orderItemId != null && !orderItemId.isBlank()) {
            externalIds.add(orderItemId);
        }
        applyPageItemSummary(vo, rows, loadGoodsInfoByExternalIds(tenantId, externalIds));
    }

    private void applyPageItemSummary(XianyuTradeOrderVO vo,
                                      List<Map<String, Object>> rows,
                                      Map<String, GoodsInfo> goodsInfoMap) {
        if (rows == null || rows.isEmpty()) {
            // 订单项为空：用订单顶层 item_id 兜底合成单项
            String orderItemId = vo.getItemId();
            if (orderItemId != null && !orderItemId.isBlank()) {
                GoodsInfo info = goodsInfoMap.get(orderItemId);
                String title = (info != null && info.title != null && !info.title.isBlank())
                        ? info.title
                        : ("商品 " + orderItemId);
                String image = info != null ? info.image : null;

                XianyuTradeOrderItemVO itemVO = new XianyuTradeOrderItemVO();
                itemVO.setGoodsTitle(title);
                itemVO.setGoodsCount(1);
                itemVO.setExternalGoodsId(orderItemId);
                itemVO.setGoodsImage(image);
                vo.setItems(java.util.Collections.singletonList(itemVO));
                vo.setItemSummary(title + " x1");
                vo.setQuantityTotal(1);
                return;
            }
            vo.setItems(Collections.emptyList());
            vo.setItemSummary("View detail");
            vo.setQuantityTotal(0);
            return;
        }
        List<XianyuTradeOrderItemVO> itemVOs = new ArrayList<>();
        List<String> parts = new ArrayList<>();
        int quantityTotal = 0;
        for (Map<String, Object> row : rows) {
            String goodsTitle = asString(row.get("goods_title"));
            int goodsCount = Math.max(asInteger(row.get("goods_count"), 1), 1);
            String externalGoodsId = asString(row.get("external_goods_id"));
            String goodsImage = null;
            if (externalGoodsId != null) {
                GoodsInfo info = goodsInfoMap.get(externalGoodsId);
                if (info != null) {
                    if (info.title != null && !info.title.isBlank()) {
                        goodsTitle = info.title;
                    }
                    goodsImage = info.image;
                }
            }

            quantityTotal += goodsCount;
            if (parts.size() < 2 && goodsTitle != null && !goodsTitle.isBlank()) {
                parts.add(goodsTitle + " x" + goodsCount);
            }

            XianyuTradeOrderItemVO itemVO = new XianyuTradeOrderItemVO();
            itemVO.setGoodsTitle(goodsTitle);
            itemVO.setGoodsCount(goodsCount);
            itemVO.setExternalGoodsId(externalGoodsId);
            itemVO.setGoodsImage(goodsImage);
            itemVOs.add(itemVO);
        }
        vo.setItems(itemVOs);
        vo.setItemSummary(parts.isEmpty() ? "View detail" : String.join(" / ", parts));
        vo.setQuantityTotal(quantityTotal);
    }

    private Map<Long, List<Map<String, Object>>> queryOrderItemsForSummaryBatch(Long tenantId, List<Long> orderIds) {
        if (orderIds == null || orderIds.isEmpty()) {
            return Collections.emptyMap();
        }
        String placeholders = String.join(",", Collections.nCopies(orderIds.size(), "?"));
        List<Object> params = new ArrayList<>();
        params.add(tenantId);
        params.addAll(orderIds);

        List<Map<String, Object>> rows;
        try {
            rows = jdbcTemplate.queryForList(
                    "SELECT order_id, goods_title, goods_count, external_goods_id " +
                            "FROM xianyu_trade_order_item " +
                            "WHERE tenant_id = ? AND order_id IN (" + placeholders + ") AND deleted = 0 " +
                            "ORDER BY order_id ASC, id ASC",
                    params.toArray()
            );
        } catch (org.springframework.jdbc.BadSqlGrammarException error) {
            log.warn("Order items summary batch fallback to legacy schema tenantId={} orderIds={} errorType={}",
                    tenantId,
                    orderIds.size(),
                    error.getClass().getSimpleName());
            rows = jdbcTemplate.queryForList(
                    "SELECT order_id, goods_title, goods_count " +
                            "FROM xianyu_trade_order_item " +
                            "WHERE tenant_id = ? AND order_id IN (" + placeholders + ") AND deleted = 0 " +
                            "ORDER BY order_id ASC, id ASC",
                    params.toArray()
            );
            for (Map<String, Object> row : rows) {
                row.putIfAbsent("external_goods_id", null);
            }
        }

        Map<Long, List<Map<String, Object>>> grouped = new HashMap<>();
        for (Map<String, Object> row : rows) {
            Long orderId = asLong(row.get("order_id"));
            if (orderId == null) {
                continue;
            }
            grouped.computeIfAbsent(orderId, ignored -> new ArrayList<>()).add(row);
        }
        return grouped;
    }

    private List<Map<String, Object>> queryOrderItemsForSummary(Long tenantId, Long orderId) {
        try {
            return jdbcTemplate.queryForList(
                    "SELECT goods_title, goods_count, external_goods_id " +
                            "FROM xianyu_trade_order_item " +
                            "WHERE tenant_id = ? AND order_id = ? AND deleted = 0 ORDER BY id ASC",
                    tenantId,
                    orderId
            );
        } catch (org.springframework.jdbc.BadSqlGrammarException error) {
            log.warn("Order items summary fallback to legacy schema tenantId={} orderId={} errorType={}", tenantId, orderId, error.getClass().getSimpleName());
            List<Map<String, Object>> legacyRows = jdbcTemplate.queryForList(
                    "SELECT goods_title, goods_count FROM xianyu_trade_order_item " +
                            "WHERE tenant_id = ? AND order_id = ? AND deleted = 0 ORDER BY id ASC",
                    tenantId,
                    orderId
            );
            for (Map<String, Object> row : legacyRows) {
                row.putIfAbsent("external_goods_id", null);
            }
            return legacyRows;
        }
    }

    /**
     * 根据 external_goods_id 批量查询商品信息（title + 封面图，cover_pic 优先，image_url 兜底）
     */
    private Map<String, GoodsInfo> loadGoodsInfoByExternalIds(Long tenantId, Set<String> externalIds) {
        if (externalIds == null || externalIds.isEmpty()) {
            return Collections.emptyMap();
        }
        String placeholders = String.join(",", Collections.nCopies(externalIds.size(), "?"));
        List<Object> params = new ArrayList<>();
        params.add(tenantId);
        params.addAll(externalIds);

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT external_goods_id, title, cover_pic, image_url FROM xianyu_goods " +
                        "WHERE tenant_id = ? AND external_goods_id IN (" + placeholders + ") AND deleted = 0",
                params.toArray()
        );

        Map<String, GoodsInfo> result = new HashMap<>();
        for (Map<String, Object> row : rows) {
            String externalId = asString(row.get("external_goods_id"));
            if (externalId == null || result.containsKey(externalId)) {
                continue;
            }
            String title = asString(row.get("title"));
            String coverPic = asString(row.get("cover_pic"));
            String imageUrl = asString(row.get("image_url"));
            String image = (coverPic != null && !coverPic.isBlank()) ? coverPic : imageUrl;
            result.put(externalId, new GoodsInfo(title, image));
        }
        return result;
    }

    /** 商品信息聚合（标题 + 封面图） */
    private static final class GoodsInfo {
        final String title;
        final String image;

        GoodsInfo(String title, String image) {
            this.title = title;
            this.image = image;
        }
    }

    private void enrichDeliverySnapshot(Long tenantId, XianyuTradeOrderVO vo) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT delivery_method, delivery_status, delivery_fail_reason, delivery_content, " +
                        "quantity_requested, quantity_sent, platform_sync_time " +
                        "FROM delivery_record WHERE tenant_id = ? AND order_id = ? AND deleted = 0 " +
                        "ORDER BY created_time DESC LIMIT 1",
                tenantId,
                vo.getId()
        );
        if (rows.isEmpty()) {
            return;
        }

        Map<String, Object> row = rows.get(0);
        vo.setDeliveryMethod(asString(row.get("delivery_method")));
        vo.setDeliveryStatus(asString(row.get("delivery_status")));
        vo.setDeliveryFailReason(asString(row.get("delivery_fail_reason")));
        vo.setDeliveryContent(asString(row.get("delivery_content")));
        vo.setQuantityRequested(asInteger(row.get("quantity_requested"), 0));
        vo.setQuantitySent(asInteger(row.get("quantity_sent"), 0));
        vo.setPlatformSyncTime(asLocalDateTime(row.get("platform_sync_time")));
    }

    private String buildItemSummary(List<XianyuTradeOrderItemVO> items) {
        return items.stream()
                .filter(Objects::nonNull)
                .map(item -> (item.getGoodsTitle() == null || item.getGoodsTitle().isBlank() ? "Item" : item.getGoodsTitle())
                        + " x" + Math.max(item.getGoodsCount() == null ? 1 : item.getGoodsCount(), 1))
                .limit(2)
                .collect(Collectors.joining(" / "));
    }

    private int sumItemQuantity(List<XianyuTradeOrderItemVO> items) {
        return items.stream()
                .filter(Objects::nonNull)
                .map(XianyuTradeOrderItemVO::getGoodsCount)
                .filter(Objects::nonNull)
                .mapToInt(count -> Math.max(count, 1))
                .sum();
    }

    private String buildSpecSummary(String specName, String specValue) {
        String safeName = specName == null ? "" : specName.trim();
        String safeValue = specValue == null ? "" : specValue.trim();
        if (!safeName.isEmpty() && !safeValue.isEmpty()) {
            return safeName + ": " + safeValue;
        }
        if (!safeName.isEmpty()) {
            return safeName;
        }
        return safeValue.isEmpty() ? null : safeValue;
    }

    private String asString(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private int asInteger(Object value, int defaultValue) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value == null) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException ignored) {
            return defaultValue;
        }
    }

    private Long asLong(Object value) {
        if (value instanceof Number number) {
            return number.longValue();
        }
        if (value == null) {
            return null;
        }
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private LocalDateTime asLocalDateTime(Object value) {
        if (value instanceof LocalDateTime dateTime) {
            return dateTime;
        }
        if (value instanceof Timestamp timestamp) {
            return timestamp.toLocalDateTime();
        }
        return null;
    }
}
