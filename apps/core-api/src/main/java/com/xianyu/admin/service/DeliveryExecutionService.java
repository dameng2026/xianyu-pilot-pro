package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.mapper.*;
import com.xianyu.admin.entity.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 自动发货执行引擎 —— 核心发货逻辑。
 * 1. 扫描 delivery_record 中 status=0 的待处理记录
 * 2. 读取商品发货配置（delivery_goods_config）
 * 3. 解析模板变量（替换 {买家昵称}、{卡密} 等）
 * 4. 卡密模式从卡密仓库原子认领
 * 5. 通过 AutomationClient 调用 Python 服务发送闲鱼消息
 * 6. 更新订单 delivery_status = 'shipped'
 * 7. 更新 delivery_record 状态
 */
@Service
public class DeliveryExecutionService {
    private static final Logger log = LoggerFactory.getLogger(DeliveryExecutionService.class);
    private static final DateTimeFormatter DT_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final int DELIVERY_MESSAGE_TIMEOUT_SECONDS = 60;

    private final JdbcTemplate jdbcTemplate;
    private final AutomationClient automationClient;
    private final XianyuTradeOrderMapper orderMapper;
    private final XianyuTradeOrderItemMapper orderItemMapper;
    private final XianyuAccountAuthMapper authMapper;
    private final CardItemMapper cardItemMapper;
    private final CardGroupMapper cardGroupMapper;
    private final CookieCryptoService cookieCryptoService;
    private final UserNotificationService userNotificationService;
    private final DeliveryGoodsConfigService goodsConfigService;
    private final TransactionTemplate transactionTemplate;

    public DeliveryExecutionService(JdbcTemplate jdbcTemplate,
                                    AutomationClient automationClient,
                                    XianyuTradeOrderMapper orderMapper,
                                    XianyuTradeOrderItemMapper orderItemMapper,
                                    XianyuAccountAuthMapper authMapper,
                                    CardItemMapper cardItemMapper,
                                    CardGroupMapper cardGroupMapper,
                                    CookieCryptoService cookieCryptoService,
                                    UserNotificationService userNotificationService,
                                    DeliveryGoodsConfigService goodsConfigService,
                                    PlatformTransactionManager transactionManager) {
        this.jdbcTemplate = jdbcTemplate;
        this.automationClient = automationClient;
        this.orderMapper = orderMapper;
        this.orderItemMapper = orderItemMapper;
        this.authMapper = authMapper;
        this.cardItemMapper = cardItemMapper;
        this.cardGroupMapper = cardGroupMapper;
        this.cookieCryptoService = cookieCryptoService;
        this.userNotificationService = userNotificationService;
        this.goodsConfigService = goodsConfigService;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    /**
     * 扫描并处理所有待执行的发货记录。
     * 由调度任务定时调用。
     */
    public int processPendingDeliveries() {
        List<Map<String, Object>> pendingRecords = jdbcTemplate.queryForList(
                "SELECT dr.*, o.account_id AS order_account_id, o.buyer_name, o.buyer_id, o.external_order_id " +
                        "FROM delivery_record dr " +
                        "JOIN xianyu_trade_order o ON o.id = dr.order_id AND o.deleted = 0 " +
                        "WHERE dr.tenant_id IS NOT NULL AND dr.deleted = 0 AND dr.status = 0 " +
                        "AND dr.retry_count < 5 " +
                        "ORDER BY dr.created_time ASC " +
                        "LIMIT 20"
        );

        int processed = 0;
        int success = 0;
        int failed = 0;
        for (Map<String, Object> record : pendingRecords) {
            Long recordId = ((Number) record.get("id")).longValue();
            Long tenantId = ((Number) record.get("tenant_id")).longValue();
            try {
                transactionTemplate.executeWithoutResult(status -> executeDelivery(record));
                success++;
            } catch (Exception e) {
                log.error("发货执行失败 recordId={}, errorType={}", recordId, e.getClass().getSimpleName());
                markRecordFailed(recordId, tenantId, publicDeliveryFailure(e));
                failed++;
            }
            processed++;
        }
        if (processed > 0) {
            log.info("批量发货处理完成: 总{}个, 成功{}个, 失败{}个", processed, success, failed);
        }
        return processed;
    }

    /**
     * 执行单个发货
     */
    @Transactional
    public void executeDelivery(Map<String, Object> record) {
        Long recordId = ((Number) record.get("id")).longValue();
        Long tenantId = ((Number) record.get("tenant_id")).longValue();
        Long orderId = ((Number) record.get("order_id")).longValue();
        Long claimedCardItemId = null;
        Long claimedCardGroupId = null;
        boolean cardConsumed = false;

        try {
            // 标记为执行中
            jdbcTemplate.update(
                    "UPDATE delivery_record SET status=1, updated_time=NOW() WHERE id=? AND tenant_id=?",
                    recordId, tenantId);

            // 1. 获取订单信息
            XianyuTradeOrder order = orderMapper.findById(tenantId, orderId);
            if (order == null) {
                throw new BizException(404, "订单不存在或已删除");
            }
            Long accountId = order.getAccountId();
            if (accountId == null) {
                throw new BizException(409, "订单缺少可用的闲鱼账号，无法发货");
            }

            // 2. 获取订单商品
            List<XianyuTradeOrderItem> items = orderItemMapper.findByOrderId(tenantId, orderId);
            if (items == null || items.isEmpty()) {
                throw new BizException(409, "订单缺少商品明细，无法发货");
            }
            XianyuTradeOrderItem firstItem = items.get(0);

            // 判断发货时机（优先从 record 的 timing 字段获取）
            String timing = record.get("delivery_timing") != null
                    ? String.valueOf(record.get("delivery_timing"))
                    : "after_payment";
            String timingKey = mapTimingToKey(timing);

            // 检查是否为手动发货（记录中已预填发货内容）
            String recordMode = record.get("delivery_mode") != null
                    ? String.valueOf(record.get("delivery_mode"))
                    : "text";
            String recordContent = record.get("content") != null
                    ? String.valueOf(record.get("content"))
                    : "";
            boolean isManualWithContent = "text".equals(recordMode) && !recordContent.isBlank();

            String mode = recordMode;
            String header = "";
            String content = recordContent;
            String footer = "";
            Object segmentSend = false;
            String cardContent = null;
            String cardNumber = null;
            String cardPassword = null;
            String cardLink = null;
            String cardCode = null;

            if (!isManualWithContent) {
                // 3. 非手动发货：获取商品发货配置
                // 注意：xianyu_trade_order_item.goods_id 可能存储的是闲鱼 external_goods_id
                // （Python sync_sold_orders 直接将 MTOP 返回的 itemId 写入 goods_id 字段）。
                // 需要先尝试用 goods_id 查 xianyu_goods.id；若查不到，尝试用 external_goods_id 映射。
                Long internalGoodsId = resolveInternalGoodsId(tenantId, firstItem);
                Map<String, Object> goodsConfig = getGoodsDeliveryConfig(tenantId, internalGoodsId);
                if (goodsConfig == null || goodsConfig.isEmpty()) {
                    throw new BizException(422, "商品未配置自动发货规则");
                }

                @SuppressWarnings("unchecked")
                Map<String, Object> timingConfig = (Map<String, Object>) goodsConfig.get(timingKey);
                if (timingConfig == null) {
                    throw new BizException(422, "未找到当前发货时机的配置");
                }
                Object enabled = timingConfig.get("enabled");
                if (enabled == null || "0".equals(String.valueOf(enabled)) || Boolean.FALSE.equals(enabled)) {
                    throw new BizException(422, "当前发货时机已禁用");
                }

                mode = (String) timingConfig.getOrDefault("mode", "text");
                header = (String) timingConfig.getOrDefault("header", "");
                content = (String) timingConfig.getOrDefault("content", "");
                footer = (String) timingConfig.getOrDefault("footer", "");
                segmentSend = timingConfig.getOrDefault("segmentSend", false);
                Long sourceId = toLong(timingConfig.get("sourceId"));

                if ("text".equals(mode) && sourceId != null && (content == null || content.isBlank())) {
                    Map<String, Object> source = getTextSource(tenantId, sourceId);
                    if (source != null) {
                        content = String.valueOf(source.getOrDefault("content", ""));
                    }
                }

                // 4. 卡密模式：原子认领一张未使用卡密
                if ("card".equals(mode)) {
                    Object cardGroupIdObj = timingConfig.get("cardGroupId");
                    if (cardGroupIdObj == null) {
                        throw new BizException(422, "卡密模式未绑定卡密分组");
                    }
                    Long cardGroupId = ((Number) cardGroupIdObj).longValue();
                    claimedCardGroupId = cardGroupId;
                    CardItem claimed = claimCard(tenantId, cardGroupId, orderId);
                    if (claimed == null) {
                        throw new BizException(409, "卡密库存不足，请补充库存后重试");
                    }
                    claimedCardItemId = claimed.getId();
                    cardContent = claimed.getCardContent();
                    // 解析卡密内容
                    String raw = claimed.getCardContent();
                    if (raw != null) {
                        String[] parts = raw.split("----", 2);
                        cardNumber = parts[0].trim();
                        cardPassword = parts.length > 1 ? parts[1].trim() : "";
                        // 判断是否为链接
                        if (cardNumber.startsWith("http://") || cardNumber.startsWith("https://")) {
                            cardLink = cardNumber;
                        }
                        cardCode = raw;
                    }
                    // 使用卡密模板
                    String cardTemplate = (String) timingConfig.getOrDefault("cardTemplate", "");
                    if (!cardTemplate.isBlank()) {
                        cardContent = cardTemplate
                                .replace("{卡号}", cardNumber != null ? cardNumber : "")
                                .replace("{密码}", cardPassword != null ? cardPassword : "")
                                .replace("{链接}", cardLink != null ? cardLink : "")
                                .replace("{提取码}", cardPassword)
                                .replace("{卡密}", cardCode != null ? cardCode : "");
                    }
                }
            }

            // 5. 获取账号 Cookie
            String cookie = getAccountCookie(tenantId, accountId);
            if (cookie == null || cookie.isBlank()) {
                throw new BizException(409, "账号登录状态不可用，请重新登录后重试");
            }

            // 6. 解析买家信息
            String buyerId = order.getBuyerId();
            String buyerName = order.getBuyerName() != null ? order.getBuyerName() : "买家";
            String goodsTitle = firstItem.getGoodsTitle() != null ? firstItem.getGoodsTitle() : "";
            String orderIdStr = order.getExternalOrderId() != null ? order.getExternalOrderId() : String.valueOf(orderId);
            String shopName = ""; // 可以从店铺信息获取
            MessageTarget target = resolveMessageTarget(tenantId, accountId, firstItem, buyerId);

            // 7. 构建消息内容
            String resolvedContent = resolveContent(mode, header, content, footer, cardContent,
                    buyerName, orderIdStr, goodsTitle, String.valueOf(firstItem.getGoodsId()),
                    shopName, null);

            // 8. 发送消息（支持分段发送）
            boolean segmented = segmentSend != null && (Boolean.TRUE.equals(segmentSend) || "true".equals(String.valueOf(segmentSend)));
            List<String> messages = segmented ? splitBySegment(resolvedContent) : List.of(resolvedContent);

            for (String msg : messages) {
                if (msg.isBlank()) continue;
                sendMessage(tenantId, accountId, target, msg.trim());
            }

            if (claimedCardItemId != null && claimedCardGroupId != null) {
                markCardUsed(tenantId, claimedCardGroupId, claimedCardItemId, orderId);
                cardConsumed = true;
            }

            // 9. 调用闲鱼确认发货 API，只有平台真正标记为已发货后才更新本地 order_status=3
            // 避免本地标记 3 但闲鱼平台实际未发货的状态不一致问题
            Map<String, Object> confirmPayload = new LinkedHashMap<>();
            confirmPayload.put("tenantId", tenantId);
            confirmPayload.put("accountId", accountId);
            confirmPayload.put("externalOrderId", order.getExternalOrderId());
            confirmPayload.put("isBargain", Boolean.TRUE.equals(order.getIsBargain()));
            String itemId = firstItem.getExternalGoodsId() != null && !firstItem.getExternalGoodsId().isBlank()
                    ? firstItem.getExternalGoodsId()
                    : String.valueOf(firstItem.getGoodsId());
            confirmPayload.put("itemId", itemId);
            confirmPayload.put("buyerId", buyerId);

            Map<String, Object> confirmResult;
            try {
                confirmResult = automationClient.postInternalForData(
                        "/api/internal/orders/confirm-shipment", confirmPayload, 30, tenantId);
            } catch (Exception e) {
                log.warn("确认发货调用失败 orderId={}, errorType={}, message={}",
                        orderId, e.getClass().getSimpleName(), e.getMessage());
                throw new BizException(503, "确认发货服务暂时不可用，请稍后重试");
            }

            boolean confirmSuccess = confirmResult != null
                    && (Boolean.TRUE.equals(confirmResult.get("success"))
                        || "true".equals(String.valueOf(confirmResult.get("success"))));
            if (!confirmSuccess) {
                String confirmError = confirmResult != null
                        ? String.valueOf(confirmResult.getOrDefault("message", "确认发货失败"))
                        : "确认发货失败";
                log.warn("确认发货失败 orderId={}, error={}", orderId, confirmError);
                throw new BizException(503, "发货消息已发送，但确认发货失败：" + confirmError);
            }

            // 10. 确认发货成功，更新订单发货状态
            orderMapper.updateDeliveryStatus(tenantId, orderId, 1, 3);

            // 11. 更新发货记录为成功
            jdbcTemplate.update(
                    "UPDATE delivery_record SET account_id=?, status=2, delivery_status='success', delivery_type=?, delivery_mode=?, delivery_content=?, content=?, delivery_timing=?, " +
                            "delivery_time=NOW(), completed_time=NOW(), card_item_id=?, updated_time=NOW() WHERE id=? AND tenant_id=?",
                    accountId, mode, mode, resolvedContent, resolvedContent, timing, claimedCardItemId, recordId, tenantId);

            log.info("发货成功 recordId={}, orderId={}, mode={}, timing={}", recordId, orderId, mode, timing);
        } catch (Exception e) {
            if (!cardConsumed && claimedCardItemId != null && claimedCardGroupId != null) {
                releaseClaimedCard(tenantId, claimedCardGroupId, claimedCardItemId);
            }
            throw e;
        }
    }

    /**
     * 解析消息内容，替换变量
     */
    private String resolveContent(String mode, String header, String content, String footer,
                                   String cardContent, String buyerName, String orderId,
                                   String goodsTitle, String goodsId, String shopName,
                                   Map<String, Object> timingConfig) {
        StringBuilder sb = new StringBuilder();
        if (header != null && !header.isBlank()) {
            sb.append(header).append("\n");
        }
        if ("text".equals(mode)) {
            if (content != null) sb.append(content);
        } else {
            // card mode - cardContent already resolved from cardTemplate
            if (cardContent != null) sb.append(cardContent);
        }
        if (footer != null && !footer.isBlank()) {
            sb.append("\n").append(footer);
        }

        String now = LocalDateTime.now().format(DT_FMT);
        String result = sb.toString()
                .replace("{买家昵称}", buyerName != null ? buyerName : "")
                .replace("{订单编号}", orderId != null ? orderId : "")
                .replace("{商品标题}", goodsTitle != null ? goodsTitle : "")
                .replace("{商品ID}", goodsId != null ? goodsId : "")
                .replace("{当前时间}", now)
                .replace("{店铺名称}", shopName != null ? shopName : "");

        // 卡密相关变量（可能在头部或底部中使用）
        result = result
                .replace("{卡密}", cardContent != null ? cardContent : "");
        return result;
    }

    /**
     * 按 {分段} 变量拆分消息
     */
    private List<String> splitBySegment(String content) {
        if (content == null || content.isBlank()) return List.of();
        String[] parts = content.split("\\{分段\\}");
        List<String> result = new ArrayList<>();
        for (String part : parts) {
            String trimmed = part.trim();
            if (!trimmed.isBlank()) {
                result.add(trimmed);
            }
        }
        return result;
    }

    /**
     * 通过 Python 自动化服务发送闲鱼消息
     *
     * 注意：原实现先调 /api/websocket/sendMessage，失败后立即调 /api/msg/send 作为降级。
     * 但 /api/msg/send 端点已不存在（会返回 404），且双路径重试可能导致：
     * 1. 第一个请求实际已发送消息但返回超时/错误，第二个请求再次发送 → 重复发送
     * 2. 重复发送会触发闲鱼滑块验证，影响账号稳定性
     *
     * 现在改为单路径调用，Python 端的 send_text_message 已内置 60 秒去重缓存，
     * 相同 account_id+cid+to_id+text 的重复调用会被自动去重。
     */
    private void sendMessage(Long tenantId, Long accountId, MessageTarget target, String content) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenantId", tenantId);
        payload.put("xianyuAccountId", accountId);
        payload.put("content", content);
        payload.put("buyerId", target.buyerId());
        payload.put("toId", target.buyerId());
        payload.put("peerUserId", target.buyerId());
        payload.put("cid", target.cid());
        payload.put("sid", target.sid());
        payload.put("msgType", "text");
        if (target.goodsId() != null && !target.goodsId().isBlank()) {
            payload.put("goodsId", target.goodsId());
            payload.put("xyGoodsId", target.goodsId());
        }

        try {
            automationClient.postInternalForData("/api/websocket/sendMessage", payload, DELIVERY_MESSAGE_TIMEOUT_SECONDS, tenantId);
            log.debug("消息发送完成 accountId={}", accountId);
        } catch (Exception e) {
            log.warn("消息发送失败 accountId={}, errorType={}, message={}",
                    accountId,
                    e.getClass().getSimpleName(),
                    e.getMessage());
            // 不再降级到 /api/msg/send（该端点不存在且会导致重复发送）
            // Python 端 send_text_message 已内置 60 秒去重缓存，重复调用会自动跳过
            throw new BizException(503, "闲鱼消息发送服务暂时不可用，请稍后重试");
        }
    }

    private MessageTarget resolveMessageTarget(Long tenantId,
                                               Long accountId,
                                               XianyuTradeOrderItem orderItem,
                                               String buyerId) {
        String goodsId = firstNonBlank(
                orderItem != null ? orderItem.getExternalGoodsId() : null,
                orderItem != null && orderItem.getGoodsId() != null ? String.valueOf(orderItem.getGoodsId()) : null
        );
        String normalizedBuyerId = normalizeGoofishId(buyerId);

        if (goodsId != null && normalizedBuyerId != null) {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT s_id, sender_user_id, receiver_user_id " +
                            "FROM xianyu_chat_message " +
                            "WHERE tenant_id=? AND account_id=? AND deleted=0 " +
                            "AND xy_goods_id=? " +
                            "AND (peer_external_uid=? OR sender_user_id=? OR receiver_user_id=? OR sender_user_id=? OR receiver_user_id=?) " +
                            "AND s_id IS NOT NULL AND s_id<>'' " +
                            "ORDER BY message_time DESC, id DESC LIMIT 1",
                    tenantId, accountId, goodsId,
                    normalizedBuyerId, normalizedBuyerId, normalizedBuyerId,
                    withGoofishSuffix(normalizedBuyerId), withGoofishSuffix(normalizedBuyerId)
            );
            MessageTarget target = toMessageTarget(rows, normalizedBuyerId, goodsId);
            if (target != null) {
                return target;
            }
        }

        if (goodsId != null) {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT s_id, sender_user_id, receiver_user_id " +
                            "FROM xianyu_chat_message " +
                            "WHERE tenant_id=? AND account_id=? AND deleted=0 " +
                            "AND xy_goods_id=? " +
                            "AND s_id IS NOT NULL AND s_id<>'' " +
                            "ORDER BY message_time DESC, id DESC LIMIT 1",
                    tenantId, accountId, goodsId
            );
            MessageTarget target = toMessageTarget(rows, normalizedBuyerId, goodsId);
            if (target != null) {
                return target;
            }
        }

        if (normalizedBuyerId != null) {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT s_id, sender_user_id, receiver_user_id " +
                            "FROM xianyu_chat_message " +
                            "WHERE tenant_id=? AND account_id=? AND deleted=0 " +
                            "AND (peer_external_uid=? OR sender_user_id=? OR receiver_user_id=? OR sender_user_id=? OR receiver_user_id=?) " +
                            "AND s_id IS NOT NULL AND s_id<>'' " +
                            "ORDER BY message_time DESC, id DESC LIMIT 1",
                    tenantId, accountId,
                    normalizedBuyerId, normalizedBuyerId, normalizedBuyerId,
                    withGoofishSuffix(normalizedBuyerId), withGoofishSuffix(normalizedBuyerId)
            );
            MessageTarget target = toMessageTarget(rows, normalizedBuyerId, goodsId);
            if (target != null) {
                return target;
            }
        }

        String conversationBuyerKey = normalizedBuyerId == null ? null : "sid:" + normalizedBuyerId;
        List<Map<String, Object>> conversationRows = jdbcTemplate.queryForList(
                "SELECT external_buyer_id, peer_external_uid, peer_key " +
                        "FROM xianyu_conversation " +
                        "WHERE tenant_id=? AND account_id=? AND deleted=0 " +
                        "AND (? IS NULL OR goods_id=? OR goods_id=CAST(? AS UNSIGNED) OR goods_title=?) " +
                        "AND (? IS NULL OR external_buyer_id IN (?, ?) OR peer_external_uid IN (?, ?) OR peer_key IN (?, ?)) " +
                        "ORDER BY updated_time DESC, id DESC LIMIT 1",
                tenantId, accountId,
                goodsId, goodsId, goodsId, goodsId,
                normalizedBuyerId,
                normalizedBuyerId, withGoofishSuffix(normalizedBuyerId),
                normalizedBuyerId, withGoofishSuffix(normalizedBuyerId),
                conversationBuyerKey, withGoofishSuffix(conversationBuyerKey)
        );
        if (!conversationRows.isEmpty()) {
            Map<String, Object> row = conversationRows.get(0);
            String sid = firstNonBlank(
                    normalizeGoofishId(asString(row.get("peerKey"))),
                    normalizeGoofishId(asString(row.get("externalBuyerId")))
            );
            String resolvedBuyerId = firstNonBlank(
                    normalizeGoofishId(asString(row.get("peerExternalUid"))),
                    normalizedBuyerId
            );
            if (sid != null && resolvedBuyerId != null) {
                return new MessageTarget(withGoofishSuffix(sid), sid, withGoofishSuffix(resolvedBuyerId), goodsId);
            }
        }

        if (normalizedBuyerId == null) {
            throw new BizException(409, "无法解析买家会话：订单缺少买家标识");
        }
        throw new BizException(409, "无法解析买家会话，请先确保该商品与买家存在可发送的聊天记录");
    }

    private MessageTarget toMessageTarget(List<Map<String, Object>> rows, String preferredBuyerId, String goodsId) {
        if (rows == null || rows.isEmpty()) return null;
        Map<String, Object> row = rows.get(0);
        String sid = normalizeGoofishId(readValue(row, "sId", "s_id"));
        String sender = normalizeGoofishId(readValue(row, "senderUserId", "sender_user_id"));
        String receiver = normalizeGoofishId(readValue(row, "receiverUserId", "receiver_user_id"));
        String buyer = preferredBuyerId != null ? preferredBuyerId : firstNonBlank(sender, receiver);
        if (sid == null || buyer == null) return null;
        return new MessageTarget(withGoofishSuffix(sid), sid, withGoofishSuffix(buyer), goodsId);
    }

    private String normalizeGoofishId(String value) {
        if (value == null) return null;
        String normalized = value.trim();
        if (normalized.isEmpty()) return null;
        if (normalized.startsWith("sid:")) {
            normalized = normalized.substring(4);
        }
        if (normalized.endsWith("@goofish")) {
            normalized = normalized.substring(0, normalized.length() - 8);
        }
        return normalized.isBlank() ? null : normalized;
    }

    private String withGoofishSuffix(String value) {
        String normalized = normalizeGoofishId(value);
        return normalized == null ? null : normalized + "@goofish";
    }

    private String asString(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private String readValue(Map<String, Object> row, String... keys) {
        if (row == null || keys == null) return null;
        for (String key : keys) {
            if (row.containsKey(key)) {
                return asString(row.get(key));
            }
        }
        return null;
    }

    private String firstNonBlank(String... values) {
        if (values == null) return null;
        return Arrays.stream(values)
                .filter(Objects::nonNull)
                .map(String::trim)
                .filter(v -> !v.isEmpty())
                .findFirst()
                .orElse(null);
    }

    private record MessageTarget(String cid, String sid, String buyerId, String goodsId) {}

    /**
     * 原子认领一张卡密
     */
    private CardItem claimCard(Long tenantId, Long groupId, Long orderId) {
        int affected = cardItemMapper.claimUnusedOne(tenantId, groupId, orderId);
        if (affected == 0) return null;
        cardGroupMapper.refreshCounts(tenantId, groupId);
        return cardItemMapper.findClaimedByOrder(tenantId, groupId, orderId);
    }

    private void markCardUsed(Long tenantId, Long groupId, Long itemId, Long orderId) {
        int affected = cardItemMapper.updateStatus(tenantId, itemId, 2, orderId, LocalDateTime.now());
        if (affected == 0) {
            cardItemMapper.updateStatusOnly(tenantId, groupId, itemId, 2);
        }
        cardGroupMapper.refreshCounts(tenantId, groupId);
    }

    private void releaseClaimedCard(Long tenantId, Long groupId, Long itemId) {
        try {
            cardItemMapper.reset(tenantId, groupId, itemId);
            cardGroupMapper.refreshCounts(tenantId, groupId);
        } catch (Exception releaseError) {
            log.warn("释放已认领卡密失败 tenantId={}, groupId={}, itemId={}, errorType={}",
                    tenantId,
                    groupId,
                    itemId,
                    releaseError.getClass().getSimpleName());
        }
    }

    /**
     * 读取商品发货配置
     */
    private Map<String, Object> getGoodsDeliveryConfig(Long tenantId, Long goodsId) {
        return goodsConfigService.read(tenantId, goodsId);
    }

    /**
     * 将订单项中的 goods_id 解析为 xianyu_goods 内部 ID。
     *
     * 背景：Python sync_sold_orders 将闲鱼 MTOP 返回的 itemId（external_goods_id）
     * 直接写入 xianyu_trade_order_item.goods_id，而非 xianyu_goods.id。
     * delivery_goods_config.goods_id 关联的是 xianyu_goods.id，因此需要映射。
     *
     * 解析策略：
     * 1. 先用 firstItem.goods_id 查 xianyu_goods.id（正常场景，goods_id 已是内部 ID）
     * 2. 若查不到，将 goods_id 视为 external_goods_id 再查一次
     * 3. 若仍查不到，尝试 firstItem.externalGoodsId 字段
     */
    private Long resolveInternalGoodsId(Long tenantId, XianyuTradeOrderItem firstItem) {
        Long rawGoodsId = firstItem.getGoodsId();
        if (rawGoodsId == null || rawGoodsId <= 0) {
            throw new BizException(409, "订单商品信息缺失，无法发货");
        }

        // 策略1：直接作为 xianyu_goods.id 查询
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id=?",
                    Integer.class, tenantId, rawGoodsId);
            if (count != null && count > 0) {
                return rawGoodsId;
            }
        } catch (Exception e) {
            log.debug("按 xianyu_goods.id 查询失败 goodsId={}, errorType={}", rawGoodsId, e.getClass().getSimpleName());
        }

        // 策略2：将 goods_id 视为 external_goods_id 查询
        String extId = String.valueOf(rawGoodsId);
        try {
            Long internalId = jdbcTemplate.queryForObject(
                    "SELECT id FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND external_goods_id=? ORDER BY id DESC LIMIT 1",
                    Long.class, tenantId, extId);
            if (internalId != null && internalId > 0) {
                log.info("goods_id 映射: rawGoodsId={} -> internalId={} (via external_goods_id)", rawGoodsId, internalId);
                return internalId;
            }
        } catch (EmptyResultDataAccessException e) {
            // 继续策略3
        } catch (Exception e) {
            log.debug("按 external_goods_id 查询失败 extId={}, errorType={}", extId, e.getClass().getSimpleName());
        }

        // 策略3：使用 firstItem.externalGoodsId 字段
        String externalGoodsId = firstItem.getExternalGoodsId();
        if (externalGoodsId != null && !externalGoodsId.isBlank()) {
            try {
                Long internalId = jdbcTemplate.queryForObject(
                        "SELECT id FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND external_goods_id=? ORDER BY id DESC LIMIT 1",
                        Long.class, tenantId, externalGoodsId);
                if (internalId != null && internalId > 0) {
                    log.info("goods_id 映射: externalGoodsId={} -> internalId={}", externalGoodsId, internalId);
                    return internalId;
                }
            } catch (Exception e) {
                log.debug("按 externalGoodsId 字段查询失败 externalGoodsId={}, errorType={}", externalGoodsId, e.getClass().getSimpleName());
            }
        }

        log.warn("无法解析内部商品ID tenantId={} rawGoodsId={} externalGoodsId={}", tenantId, rawGoodsId, externalGoodsId);
        // 返回 rawGoodsId 让上层 getGoodsDeliveryConfig → requireGoods 抛出明确错误
        return rawGoodsId;
    }

    /**
     * 映射发货时机字符串到配置 key
     */
    private String mapTimingToKey(String timing) {
        if (timing == null) return "payDelivery";
        return switch (timing) {
            case "after_payment", "payDelivery" -> "payDelivery";
            case "after_receipt", "confirmDelivery" -> "confirmDelivery";
            case "after_review", "reviewDelivery" -> "reviewDelivery";
            default -> "payDelivery";
        };
    }

    /**
     * 获取账号已解密的 Cookie
     */
    private String getAccountCookie(Long tenantId, Long accountId) {
        try {
            XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, accountId);
            if (auth != null && auth.getEncryptedCookie() != null && !auth.getEncryptedCookie().isBlank()) {
                return cookieCryptoService.decryptIfNeeded(auth.getEncryptedCookie());
            }
        } catch (Exception e) {
            log.warn("获取账号Cookie失败 accountId={}, errorType={}", accountId, e.getClass().getSimpleName());
        }
        return null;
    }

    /**
     * 标记发货记录为失败
     */
    private void markRecordFailed(Long recordId, Long tenantId, String errorMessage) {
        Map<String, Object> row = null;
        try {
            row = jdbcTemplate.queryForMap(
                    "SELECT dr.tenant_id, dr.account_id, dr.order_id, o.external_order_id, " +
                            "(SELECT i.goods_title FROM xianyu_trade_order_item i WHERE i.order_id=dr.order_id AND i.deleted=0 ORDER BY i.id ASC LIMIT 1) AS goods_title " +
                            "FROM delivery_record dr " +
                            "LEFT JOIN xianyu_trade_order o ON o.id=dr.order_id AND o.deleted=0 " +
                            "WHERE dr.id=? AND dr.tenant_id=? AND dr.deleted=0 LIMIT 1",
                    recordId, tenantId
            );
        } catch (Exception lookupError) {
            log.warn("加载失败发货记录通知上下文失败 recordId={}, errorType={}",
                    recordId, lookupError.getClass().getSimpleName());
        }
        String safeMsg = errorMessage == null || errorMessage.isBlank()
                ? "自动发货执行失败，请稍后重试"
                : errorMessage.substring(0, Math.min(errorMessage.length(), 500));
        try {
            jdbcTemplate.update(
                    "UPDATE delivery_record SET status=3, delivery_status='failed', error_message=?, fail_reason=?, retry_count=COALESCE(retry_count,0)+1, " +
                            "updated_time=NOW() WHERE id=? AND tenant_id=? AND deleted=0",
                    safeMsg, safeMsg, recordId, tenantId);
        } catch (Exception updateError) {
            log.error("持久化发货失败状态失败 recordId={}, errorType={}",
                    recordId, updateError.getClass().getSimpleName());
            return;
        }
        if (row != null) {
            try {
                userNotificationService.notifyManualDeliveryReminder(
                        toLong(row.get("tenant_id")),
                        toLong(row.get("account_id")),
                        toLong(row.get("order_id")),
                        row.get("external_order_id") == null ? null : String.valueOf(row.get("external_order_id")),
                        row.get("goods_title") == null ? null : String.valueOf(row.get("goods_title")),
                        safeMsg
                );
            } catch (Exception notifyError) {
                log.warn("发送发货失败提醒失败 recordId={}, errorType={}",
                        recordId, notifyError.getClass().getSimpleName());
            }
        }
    }

    private Map<String, Object> getTextSource(Long tenantId, Long sourceId) {
        try {
            return jdbcTemplate.queryForMap(
                    "SELECT id, title, content, remark FROM delivery_text_source WHERE tenant_id=? AND id=? AND deleted=0",
                    tenantId, sourceId
            );
        } catch (Exception ignored) {
            return null;
        }
    }

    private Long toLong(Object value) {
        if (value instanceof Number number) {
            return number.longValue();
        }
        if (value == null) {
            return null;
        }
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception ignored) {
            return null;
        }
    }

    /**
     * 对外暴露：执行指定发货记录的重试
     */
    @Transactional
    public void retryDelivery(Long recordId, Long tenantId) {
        Map<String, Object> record;
        try {
            record = jdbcTemplate.queryForMap(
                    "SELECT dr.*, o.account_id AS order_account_id, o.buyer_name, o.buyer_id, o.external_order_id " +
                            "FROM delivery_record dr " +
                            "JOIN xianyu_trade_order o ON o.id = dr.order_id AND o.deleted = 0 " +
                            "WHERE dr.id=? AND dr.tenant_id=? AND dr.deleted=0",
                    recordId, tenantId);
        } catch (EmptyResultDataAccessException e) {
            throw new BizException(404, "发货记录不存在");
        } catch (Exception e) {
            log.error("读取待重试发货记录失败 recordId={}, errorType={}", recordId, e.getClass().getSimpleName());
            throw new BizException(503, "发货记录暂时无法读取，请稍后重试");
        }

        try {
            transactionTemplate.executeWithoutResult(status -> {
                jdbcTemplate.update(
                        "UPDATE delivery_record SET status=0, delivery_status='pending', error_message=NULL, fail_reason=NULL, updated_time=NOW() "
                                + "WHERE id=? AND tenant_id=? AND deleted=0",
                        recordId, tenantId
                );
                executeDelivery(record);
            });
        } catch (Exception e) {
            log.error("重试发货失败 recordId={}, errorType={}", recordId, e.getClass().getSimpleName());
            String publicFailure = publicDeliveryFailure(e);
            markRecordFailed(recordId, tenantId, publicFailure);
            int code = e instanceof BizException bizException ? bizException.getCode() : 503;
            throw new BizException(code, publicFailure);
        }
    }

    private String publicDeliveryFailure(Exception error) {
        if (error instanceof BizException bizException
                && bizException.getMessage() != null
                && !bizException.getMessage().isBlank()) {
            return bizException.getMessage();
        }
        return "自动发货执行失败，请检查账号登录状态和发货配置后重试";
    }
}
