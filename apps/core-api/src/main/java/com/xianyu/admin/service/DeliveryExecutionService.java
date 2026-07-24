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
    private final DeliveryStatementCheckService statementCheckService;
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
                                    DeliveryStatementCheckService statementCheckService,
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
        this.statementCheckService = statementCheckService;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        // 事务超时：发货流程内含 HTTP 调用（最长 60s），设置 90s 超时防止长事务耗尽连接池
        this.transactionTemplate.setTimeout(90);
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
     *
     * 重复发货防护（事故级修复）：
     * 1. 入口检查：该订单是否已有 status=2 的成功发货记录 → 有则跳过（双向验证）
     * 2. 状态判断修复：消息发送成功 + 卡密标记后立即标记 status=2，
     *    确认发货失败不影响 delivery_record 成功状态（避免被 retryFailedDeliveries 重置后再次认领新卡密）
     * 3. 补发逻辑修复：重试时若 delivery_record 已有 delivery_content（首次发送的卡密内容），
     *    直接重发该内容，不再认领新卡密
     * 4. 鱼小铺 vs 普通用户：fishShopUser=true 调用闲鱼 API 确认发货；false 只发 WS 消息
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

            // === 重复发货最后防线：检查该订单是否已有成功的发货记录 ===
            // 背景：用户反馈一个订单发了7张卡密，根因是确认发货失败导致 status=3 →
            // retryFailedDeliveries 重置 → 再次认领新卡密。此处防止任何路径的重复发货。
            Integer existingSuccessCount = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM delivery_record " +
                            "WHERE tenant_id=? AND order_id=? AND deleted=0 AND status=2 " +
                            "AND id<>? LIMIT 1",
                    Integer.class, tenantId, orderId, recordId);
            if (existingSuccessCount != null && existingSuccessCount > 0) {
                log.warn("重复发货最后防线拦截: tenantId={} orderId={} recordId={}（该订单已有成功发货记录，跳过）",
                        tenantId, orderId, recordId);
                // 直接将当前记录标记为成功（已通过其他记录发货），避免后续重试
                jdbcTemplate.update(
                        "UPDATE delivery_record SET status=2, delivery_status='success', " +
                                "error_message=NULL, fail_reason=NULL, " +
                                "updated_time=NOW() WHERE id=? AND tenant_id=?",
                        recordId, tenantId);
                return;
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

            // === 补发货识别：检查 delivery_record 是否已有首次发送的 delivery_content ===
            // 如果已有 delivery_content（首次发送的卡密/文本内容），说明之前已发送过，
            // 本次是重试/补发，应直接重发首次内容，不再认领新卡密。
            String existingDeliveryContent = record.get("delivery_content") != null
                    ? String.valueOf(record.get("delivery_content"))
                    : "";
            boolean isRedeliveryWithContent = !existingDeliveryContent.isBlank();

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

            if (isRedeliveryWithContent) {
                // === 补发逻辑：重发首次发送的内容，不再认领新卡密 ===
                // 背景：用户要求"补发货需要发送首次发送的卡密，将首次卡密记录，补发货时不要发送新卡密"
                log.info("补发货：重发首次内容 recordId={} tenantId={} orderId={}（不再认领新卡密）",
                        recordId, tenantId, orderId);
                // 直接使用首次发送的 delivery_content 作为消息内容
                // mode 保持 recordMode（可能是 card 或 text），但不再走认领逻辑
                content = existingDeliveryContent;
                cardContent = existingDeliveryContent;
            } else if (!isManualWithContent) {
                // 3. 非手动发货且非补发：获取商品发货配置
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

                // 4. 卡密模式：原子认领一张未使用卡密（仅首次发货时执行）
                if ("card".equals(mode)) {
                    Object cardGroupIdObj = timingConfig.get("cardGroupId");
                    if (cardGroupIdObj == null) {
                        throw new BizException(422, "卡密模式未绑定卡密分组，请在商品发货配置中绑定卡密分组");
                    }
                    Long cardGroupId = ((Number) cardGroupIdObj).longValue();
                    claimedCardGroupId = cardGroupId;
                    CardItem claimed = claimCard(tenantId, cardGroupId, orderId);
                    if (claimed == null) {
                        throw new BizException(409, "卡密库存不足，请及时补充库存后系统将自动重试");
                    }
                    claimedCardItemId = claimed.getId();
                    cardContent = claimed.getCardContent();
                    // 解析卡密内容（对异常格式做兜底，避免发送空卡号给买家）
                    String raw = claimed.getCardContent();
                    if (raw == null || raw.isBlank()) {
                        // 卡密内容为空：回滚认领并报错，避免发送无效卡密
                        releaseClaimedCard(tenantId, claimedCardGroupId, claimedCardItemId);
                        claimedCardItemId = null;
                        throw new BizException(409, "认领的卡密内容为空，请检查卡密仓库数据完整性");
                    }
                    try {
                        String[] parts = raw.split("----", 2);
                        cardNumber = parts[0].trim();
                        cardPassword = parts.length > 1 ? parts[1].trim() : "";
                        // 判断是否为链接
                        if (cardNumber.startsWith("http://") || cardNumber.startsWith("https://")) {
                            cardLink = cardNumber;
                        }
                        cardCode = raw;
                        // 校验解析后的卡号非空（避免 ----密码 这种异常格式）
                        if (cardNumber.isEmpty() && cardPassword.isEmpty()) {
                            releaseClaimedCard(tenantId, claimedCardGroupId, claimedCardItemId);
                            claimedCardItemId = null;
                            throw new BizException(409, "卡密格式异常（卡号和密码均为空），请检查卡密数据");
                        }
                    } catch (BizException e) {
                        throw e;
                    } catch (Exception e) {
                        log.error("解析卡密内容异常 tenantId={} cardItemId={} error={}", tenantId, claimedCardItemId, e.getMessage());
                        releaseClaimedCard(tenantId, claimedCardGroupId, claimedCardItemId);
                        claimedCardItemId = null;
                        throw new BizException(409, "卡密内容解析失败，请检查卡密数据格式");
                    }
                    // 使用卡密模板
                    String cardTemplate = (String) timingConfig.getOrDefault("cardTemplate", "");
                    if (!cardTemplate.isBlank()) {
                        try {
                            cardContent = cardTemplate
                                    .replace("{卡号}", cardNumber != null ? cardNumber : "")
                                    .replace("{密码}", cardPassword != null ? cardPassword : "")
                                    .replace("{链接}", cardLink != null ? cardLink : "")
                                    .replace("{提取码}", cardPassword)
                                    .replace("{卡密}", cardCode != null ? cardCode : "");
                        } catch (Exception e) {
                            log.error("卡密模板替换异常 tenantId={} cardItemId={} error={}", tenantId, claimedCardItemId, e.getMessage());
                            // 模板替换失败时回退到原始卡密内容，避免发送失败
                            cardContent = raw;
                        }
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

            // 6.5 发货声明前置校验：
            // 声明开关开启时，必须存在该订单的 confirmed 会话才能发货。
            // 例外：delivery_timing='after_statement_confirm' 的记录是声明确认后创建的，
            //       本身就是声明流程的产物，无需再次校验。
            if (!"after_statement_confirm".equals(timing)
                    && !statementCheckService.canDeliverAfterStatementCheck(tenantId, accountId, orderIdStr)) {
                // 标记失败但不计入重试（fail_reason 含"等待买家确认发货声明"会被 retryFailedDeliveries 排除）
                markRecordFailed(recordId, tenantId, "等待买家确认发货声明，暂不发货");
                log.info("发货声明拦截：订单未确认声明，跳过发货 tenantId={} accountId={} orderId={}",
                        tenantId, accountId, orderIdStr);
                return;
            }

            // 7. 构建消息内容
            // 补发场景（isRedeliveryWithContent=true）：直接使用首次的 delivery_content，不重新解析
            String resolvedContent;
            if (isRedeliveryWithContent) {
                resolvedContent = existingDeliveryContent;
            } else {
                resolvedContent = resolveContent(mode, header, content, footer, cardContent,
                        buyerName, orderIdStr, goodsTitle, String.valueOf(firstItem.getGoodsId()),
                        shopName, null, tenantId);
            }

            // 8. 发送消息（支持分段发送）
            boolean segmented = segmentSend != null && (Boolean.TRUE.equals(segmentSend) || "true".equals(String.valueOf(segmentSend)));
            List<String> messages = segmented ? splitBySegment(resolvedContent) : List.of(resolvedContent);

            for (String msg : messages) {
                if (msg.isBlank()) continue;
                sendMessage(tenantId, accountId, target, msg.trim());
            }

            // === 关键修复：消息发送成功后立即标记 delivery_record 为 status=2 ===
            // 背景：原逻辑在发送成功后调用 confirm-shipment，失败会抛异常导致整条记录被标记为 status=3，
            // 然后 retryFailedDeliveries 60s 后重置为 status=0，再次认领新卡密 → 重复发送。
            // 修复：消息发送成功即表示买家已收到卡密，delivery_record 必须标记为成功。
            // 卡密标记为已使用（仅首次发货时，补发不重复标记）
            if (!isRedeliveryWithContent && claimedCardItemId != null && claimedCardGroupId != null) {
                markCardUsed(tenantId, claimedCardGroupId, claimedCardItemId, orderId);
                cardConsumed = true;
            }

            // 立即更新发货记录为成功（消息已发送给买家，用户感知已发货）
            jdbcTemplate.update(
                    "UPDATE delivery_record SET account_id=?, status=2, delivery_status='success', delivery_type=?, delivery_mode=?, delivery_content=?, content=?, delivery_timing=?, " +
                            "delivery_time=NOW(), completed_time=NOW(), card_item_id=?, updated_time=NOW() WHERE id=? AND tenant_id=?",
                    accountId, mode, mode, resolvedContent, resolvedContent, timing,
                    isRedeliveryWithContent ? null : claimedCardItemId,
                    recordId, tenantId);

            log.info("发货消息发送成功，delivery_record 已标记为成功 recordId={}, orderId={}, mode={}, timing={}, isRedelivery={}",
                    recordId, orderId, mode, timing, isRedeliveryWithContent);

            // 9. 调用闲鱼确认发货 API（区分鱼小铺/普通用户）
            // - 鱼小铺用户（fishShopUser=true）：调用闲鱼 API 确认发货（平台标记为已发货）
            // - 普通用户（fishShopUser=false）：不调用 API，仅发送 WS 消息（闲鱼 WS 会推送待发货通知，
            //   买家点击"无需寄件"按钮即可完成发货）
            // 确认发货失败不影响 delivery_record 成功状态（消息已发给买家）
            Boolean isFishShopUser = isFishShopUser(tenantId, accountId);
            if (Boolean.TRUE.equals(isFishShopUser)) {
                try {
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

                    Map<String, Object> confirmResult = automationClient.postInternalForData(
                            "/api/internal/orders/confirm-shipment", confirmPayload, 30, tenantId);

                    boolean confirmSuccess = confirmResult != null
                            && (Boolean.TRUE.equals(confirmResult.get("success"))
                                || "true".equals(String.valueOf(confirmResult.get("success"))));
                    if (confirmSuccess) {
                        // 确认发货成功，更新订单状态为已发货
                        orderMapper.updateDeliveryStatus(tenantId, orderId, 1, 3);
                        log.info("鱼小铺用户确认发货成功 orderId={}", orderId);
                    } else {
                        String confirmError = confirmResult != null
                                ? String.valueOf(confirmResult.getOrDefault("message", "确认发货失败"))
                                : "确认发货失败";
                        log.warn("鱼小铺用户确认发货失败（delivery_record 已成功，不影响）orderId={} error={}",
                                orderId, confirmError);
                    }
                } catch (Exception e) {
                    // 确认发货失败不影响 delivery_record 成功状态，仅记录日志
                    log.warn("鱼小铺用户确认发货异常（delivery_record 已成功，不影响）orderId={}, errorType={}, message={}",
                            orderId, e.getClass().getSimpleName(), e.getMessage());
                }
            } else {
                // 普通用户：不调用闲鱼 API，仅通过 WS 发送消息已完成发货
                // 闲鱼 WS 会推送待发货通知给买家，买家点击"无需寄件"按钮即可完成发货
                log.info("普通用户发货完成（仅 WS 消息，不调闲鱼 API）orderId={}", orderId);
            }

            log.info("发货成功 recordId={}, orderId={}, mode={}, timing={}", recordId, orderId, mode, timing);
        } catch (Exception e) {
            if (!cardConsumed && claimedCardItemId != null && claimedCardGroupId != null) {
                releaseClaimedCard(tenantId, claimedCardGroupId, claimedCardItemId);
            }
            throw e;
        }
    }

    /**
     * 判断账号是否为鱼小铺用户
     * - fishShopUser=true：鱼小铺用户，需调用闲鱼 API 确认发货
     * - fishShopUser=false/null：普通用户，仅通过 WS 消息发货
     */
    private Boolean isFishShopUser(Long tenantId, Long accountId) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT COALESCE(fish_shop_user, 0) FROM xianyu_account WHERE id=? AND tenant_id=? AND deleted=0",
                    Boolean.class, accountId, tenantId);
        } catch (Exception e) {
            log.debug("查询鱼小铺用户标识失败 accountId={} errorType={}", accountId, e.getClass().getSimpleName());
            return false;
        }
    }

    /**
     * 解析消息内容，替换变量
     */
    private String resolveContent(String mode, String header, String content, String footer,
                                   String cardContent, String buyerName, String orderId,
                                   String goodsTitle, String goodsId, String shopName,
                                   Map<String, Object> timingConfig, Long tenantId) {
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

        // 货源占位符：{货源:ID} → 实时读取对应货源的最新内容（含商城货源 JOIN mall_product）
        result = resolveSourcePlaceholders(result, tenantId);
        return result;
    }

    /**
     * 替换 {货源:ID} 占位符为对应货源的最新内容。
     * - 普通货源：读取 delivery_text_source.content
     * - 商城货源（from_mall=1）：JOIN mall_product 取最新 content，商品下架/删除时使用兜底文案
     * 异常格式（如 {货源:}、{货源:非数字}、{货源}）会被识别为占位符并替换为兜底文案，
     * 避免原始占位符文本被发送给买家。找不到货源时也替换为兜底文案，不发送空字符串。
     */
    private String resolveSourcePlaceholders(String text, Long tenantId) {
        if (text == null || text.isEmpty() || tenantId == null) return text;
        // 匹配 {货源:任意非}内容} 或 {货源} 格式
        java.util.regex.Pattern pattern = java.util.regex.Pattern.compile("\\{货源(?::([^}]*))?\\}");
        java.util.regex.Matcher matcher = pattern.matcher(text);
        if (!matcher.find()) return text;

        java.util.Map<String, String> cache = new HashMap<>();
        StringBuffer sb = new StringBuffer();
        matcher.reset();
        while (matcher.find()) {
            String idRaw = matcher.group(1); // 可能为 null（{货源} 格式）或空字符串（{货源:}）或非数字
            String replacement;
            if (idRaw == null || idRaw.isEmpty()) {
                replacement = "【货源占位符格式错误】请检查发货正文中的 {货源:ID} 占位符";
            } else {
                try {
                    long sourceId = Long.parseLong(idRaw.trim());
                    replacement = cache.computeIfAbsent(idRaw.trim(), id -> loadSourceContent(tenantId, sourceId));
                } catch (NumberFormatException ex) {
                    replacement = "【货源占位符格式错误】请检查发货正文中的 {货源:ID} 占位符";
                }
            }
            matcher.appendReplacement(sb, java.util.regex.Matcher.quoteReplacement(replacement));
        }
        matcher.appendTail(sb);
        return sb.toString();
    }

    /**
     * 加载单个货源的最新内容（含商城货源 JOIN mall_product 实时同步）。
     * 找不到货源或异常时返回兜底文案，避免向买家发送空内容。
     */
    private String loadSourceContent(Long tenantId, Long sourceId) {
        try {
            Map<String, Object> row = jdbcTemplate.queryForMap(
                    "SELECT s.id, s.title, s.content, s.from_mall, s.mall_product_id, " +
                            "mp.title AS mp_title, mp.content AS mp_content, mp.status AS mp_status " +
                            "FROM delivery_text_source s " +
                            "LEFT JOIN mall_product mp ON mp.id = s.mall_product_id " +
                            "WHERE s.id = ? AND s.tenant_id = ? AND s.deleted = 0",
                    sourceId, tenantId);
            boolean fromMall = isMallSource(row.get("from_mall"));
            if (fromMall) {
                Object mpStatus = row.get("mp_status");
                // 商品在线（status=1 上架）时实时使用 mall_product 的最新内容
                if (mpStatus != null && Integer.parseInt(String.valueOf(mpStatus)) == 1) {
                    Object mpContent = row.get("mp_content");
                    if (mpContent != null && !String.valueOf(mpContent).isBlank()) {
                        return String.valueOf(mpContent);
                    }
                }
                // 商品下架/删除时使用兜底文案，避免发送空内容
                return "【商品已下架或被删除】该货源内容暂不可用，请联系管理员";
            }
            Object content = row.get("content");
            String text = content != null ? String.valueOf(content) : "";
            if (text.isBlank()) {
                // 货源内容为空：返回兜底文案，避免发送空内容给买家
                return "【货源内容为空】请联系管理员补充货源内容";
            }
            return text;
        } catch (EmptyResultDataAccessException notFound) {
            log.warn("货源占位符解析：未找到货源 sourceId={} tenantId={}", sourceId, tenantId);
            return "【货源不可用】该货源已被删除或不存在";
        } catch (Exception e) {
            log.error("货源占位符解析异常 sourceId={} tenantId={} error={}", sourceId, tenantId, e.getMessage());
            return "【货源不可用】货源加载失败，请稍后重试";
        }
    }

    private boolean isMallSource(Object value) {
        if (value == null) return false;
        if (value instanceof Boolean) return (Boolean) value;
        String s = String.valueOf(value).trim().toLowerCase();
        return "1".equals(s) || "true".equals(s);
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
        // 校验发送内容非空，避免发送空消息给买家
        if (content == null || content.isBlank()) {
            throw new BizException(422, "发货内容为空，无法发送给买家");
        }
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
        } catch (BizException e) {
            // 已是 BizException 直接抛出
            throw e;
        } catch (Exception e) {
            log.warn("消息发送失败 accountId={}, errorType={}, message={}",
                    accountId,
                    e.getClass().getSimpleName(),
                    e.getMessage());
            // 不再降级到 /api/msg/send（该端点不存在且会导致重复发送）
            // Python 端 send_text_message 已内置 60 秒去重缓存，重复调用会自动跳过
            // 区分超时类和其他异常，提供更精准的错误消息
            String errorMsg = e.getMessage() == null ? "" : e.getMessage().toLowerCase();
            if (errorMsg.contains("timeout") || errorMsg.contains("超时") || errorMsg.contains("timed out")) {
                throw new BizException(503, "发送消息超时，系统将自动重试");
            }
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
            throw new BizException(409, "订单缺少买家标识，无法定位聊天会话，请确认订单数据完整后重试");
        }
        throw new BizException(409, "未找到与买家的聊天会话，请等待买家主动咨询后再触发自动发货");
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
