package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.ScheduleRedeliveryRequest;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryExecutionService;
import com.xianyu.admin.service.OrderDeliveryCommandService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import org.springframework.dao.EmptyResultDataAccessException;

/**
 * 自动发货记录控制器
 * 支持列表查询、详情查看、重试
 */
@RestController
@RequestMapping("/api/auto-delivery/records")
public class AutoDeliveryRecordController {
    private static final Logger log = LoggerFactory.getLogger(AutoDeliveryRecordController.class);
    private final JdbcTemplate jdbcTemplate;
    private final DeliveryExecutionService deliveryExecutionService;
    private final OrderDeliveryCommandService orderDeliveryCommandService;

    public AutoDeliveryRecordController(JdbcTemplate jdbcTemplate,
                                        DeliveryExecutionService deliveryExecutionService,
                                        OrderDeliveryCommandService orderDeliveryCommandService) {
        this.jdbcTemplate = jdbcTemplate;
        this.deliveryExecutionService = deliveryExecutionService;
        this.orderDeliveryCommandService = orderDeliveryCommandService;
    }

    private String buildJoinSql() {
        return " FROM delivery_record dr " +
               "LEFT JOIN xianyu_trade_order o ON o.id=dr.order_id " +
               "LEFT JOIN (SELECT order_id, MIN(goods_id) AS goods_id, MIN(goods_title) AS goods_title FROM xianyu_trade_order_item WHERE deleted=0 GROUP BY order_id) oi ON oi.order_id=o.id " +
               "LEFT JOIN xianyu_goods g ON g.id=oi.goods_id " +
               "LEFT JOIN xianyu_account acc ON acc.id=dr.account_id ";
    }

    /**
     * 构造详情/列表 SELECT 字段：包含订单购买时间、商品（含封面图）、买家、卖家等完整信息。
     * 使用 COALESCE 容错 pay_time/create_time/created_time 三种可能的下单时间字段。
     * goods_cover_pic 优先取商品的 cover_pic，回退到 image_url，便于前端展示商品缩略图。
     */
    private String buildSelectColumns() {
        return "dr.*, o.external_order_id, o.buyer_name, o.buyer_id, o.total_amount, " +
                "COALESCE(o.pay_time, o.create_time, o.created_time) AS purchase_time, " +
                "COALESCE(oi.goods_id, g.id) AS goods_id, " +
                "COALESCE(oi.goods_title, g.title) AS goods_title, " +
                "g.title AS goods_name, " +
                "COALESCE(g.cover_pic, g.image_url) AS goods_cover_pic, " +
                "acc.nickname AS seller_name, acc.display_name AS seller_display_name ";
    }

    @GetMapping
    public Result<PageResult<Map<String, Object>>> list(@RequestParam(required = false) Long accountId,
                                                        @RequestParam(required = false) Integer status,
                                                        @RequestParam(required = false) String timing,
                                                        @RequestParam(required = false) String deliveryMode,
                                                        @RequestParam(required = false) String goodsKeyword,
                                                        @RequestParam(required = false) String buyerKeyword,
                                                        @RequestParam(required = false) String orderKeyword,
                                                        @RequestParam(required = false) String startTime,
                                                        @RequestParam(required = false) String endTime,
                                                        @RequestParam(defaultValue = "1") int current,
                                                        @RequestParam(defaultValue = "20") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        StringBuilder where = new StringBuilder(" WHERE dr.tenant_id=? AND dr.deleted=0 ");
        java.util.ArrayList<Object> args = new java.util.ArrayList<>();
        args.add(tenantId);
        if (accountId != null) { where.append(" AND dr.account_id=? "); args.add(accountId); }
        if (status != null) { where.append(" AND dr.status=? "); args.add(status); }
        if (timing != null && !timing.isEmpty()) { where.append(" AND dr.delivery_timing=? "); args.add(timing); }
        if (deliveryMode != null && !deliveryMode.isEmpty()) {
            where.append(" AND (COALESCE(dr.delivery_mode, dr.delivery_type)=? OR dr.delivery_type=?) ");
            args.add(deliveryMode);
            args.add(deliveryMode);
        }
        if (goodsKeyword != null && !goodsKeyword.isEmpty()) { where.append(" AND COALESCE(oi.goods_title, g.title) LIKE ? "); args.add("%" + goodsKeyword + "%"); }
        if (buyerKeyword != null && !buyerKeyword.isEmpty()) { where.append(" AND o.buyer_name LIKE ? "); args.add("%" + buyerKeyword + "%"); }
        if (orderKeyword != null && !orderKeyword.isEmpty()) {
            where.append(" AND (CAST(dr.order_id AS CHAR) LIKE ? OR o.external_order_id LIKE ?) ");
            args.add("%" + orderKeyword + "%");
            args.add("%" + orderKeyword + "%");
        }
        if (startTime != null && !startTime.isEmpty()) { where.append(" AND dr.created_time >= ? "); args.add(startTime + " 00:00:00"); }
        if (endTime != null && !endTime.isEmpty()) { where.append(" AND dr.created_time <= ? "); args.add(endTime + " 23:59:59"); }

        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) " + buildJoinSql() + where, Long.class, args.toArray());

        java.util.ArrayList<Object> queryArgs = new java.util.ArrayList<>(args);
        queryArgs.add(offset);
        queryArgs.add(safeSize);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT " + buildSelectColumns() + buildJoinSql() + where +
                " ORDER BY dr.created_time DESC LIMIT ?, ?", queryArgs.toArray());
        return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
    }

    /**
     * 获取发货记录详情
     * 返回完整字段：商品、购买时间、商品 ID、商品名称、买家用户、卖家用户、发货内容等。
     * 异常分类记录日志，便于排查"点击详情看不到信息"的问题。
     */
    @GetMapping("/{id}")
    public Result<Map<String, Object>> detail(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        try {
            Map<String, Object> row = jdbcTemplate.queryForMap(
                    "SELECT " + buildSelectColumns() + buildJoinSql() +
                    " WHERE dr.id=? AND dr.tenant_id=? AND dr.deleted=0", id, tenantId);
            return Result.ok(row);
        } catch (EmptyResultDataAccessException e) {
            log.warn("发货记录详情查询返回空记录 recordId={}, tenantId={}", id, tenantId);
            return Result.fail("发货记录不存在或已被删除");
        } catch (Exception e) {
            log.error("发货记录详情查询异常 recordId={}, tenantId={}, errorType={}, message={}",
                    id, tenantId, e.getClass().getSimpleName(), e.getMessage());
            return Result.fail("加载发货记录详情失败：" + e.getClass().getSimpleName());
        }
    }

    @PostMapping("/{id}/retry")
    public Result<Void> retry(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        try {
            deliveryExecutionService.retryDelivery(id, tenantId);
            return Result.ok(null);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("重试发货失败 recordId={}, errorType={}", id, e.getClass().getSimpleName());
            throw new BizException(503, "重试发货暂时不可用，请稍后重试");
        }
    }

    @PostMapping("/{id}/schedule-redelivery")
    public Result<Void> scheduleRedelivery(@PathVariable Long id, @RequestBody ScheduleRedeliveryRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        orderDeliveryCommandService.scheduleRedelivery(tenantId, id, request);
        return Result.ok(null);
    }
}
