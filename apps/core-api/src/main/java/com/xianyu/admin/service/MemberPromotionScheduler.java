package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 会员充值活动定时维护服务。
 *
 * 三项职责：
 *  1. 关闭超时未支付订单（expire_time < NOW() AND status=0），并释放活动预占名额；
 *  2. 激活待开始活动（pending → ongoing）；
 *  3. 结束到期活动（ongoing → ended，仅 auto_close_on_end=1）。
 *
 * 上述操作均幂等：通过 status / quota_preoccupied 标志控制，重复执行不会产生副作用。
 */
@Service
public class MemberPromotionScheduler {
    private static final Logger log = LoggerFactory.getLogger(MemberPromotionScheduler.class);

    private final JdbcTemplate jdbcTemplate;
    private final MemberPromotionService promotionService;

    @Autowired
    public MemberPromotionScheduler(JdbcTemplate jdbcTemplate, MemberPromotionService promotionService) {
        this.jdbcTemplate = jdbcTemplate;
        this.promotionService = promotionService;
    }

    /**
     * 每 2 分钟扫描一次：关闭超时订单 + 释放活动名额 + 切换活动状态。
     * 频率可由配置 xianyu.promotion.cleanup-cron 覆盖。
     */
    @Scheduled(cron = "${xianyu.promotion.cleanup-cron:0 */2 * * * ?}")
    public void scheduledMaintenance() {
        try {
            int closedOrders = closeExpiredOrders();
            int activated = promotionService.activateDueActivities();
            int ended = promotionService.endDueActivities();
            if (closedOrders > 0 || activated > 0 || ended > 0) {
                log.info("会员活动定时维护完成：expiredOrders={}, activatedActivities={}, endedActivities={}",
                        closedOrders, activated, ended);
            }
        } catch (Exception e) {
            log.error("会员活动定时维护失败 errorType={}", e.getClass().getSimpleName(), e);
        }
    }

    /**
     * 关闭超时未支付订单（expire_time < NOW() AND status=0）。
     * 活动订单需释放预占名额（通过调用 PaymentService 的 closeUserOrder 等价逻辑）。
     *
     * 注意：此处为公共清理逻辑，与 PaymentService.closeUserOrder 区别在于：
     *  - closeUserOrder 是用户主动关闭，校验订单归属；
     *  - 此处是系统自动关闭，不校验归属，但同样通过 quota_preoccupied 标志保证幂等。
     *
     * @return 关闭的订单数
     */
    public int closeExpiredOrders() {
        // 查询所有超时未支付订单（FOR UPDATE 行锁避免与支付回调并发）
        List<Map<String, Object>> expired = jdbcTemplate.queryForList(
                "SELECT order_no, is_activity_order, quota_preoccupied, activity_plan_id " +
                        "FROM payment_order WHERE deleted=0 AND status=0 AND expire_time < NOW() " +
                        "ORDER BY id ASC LIMIT 200 FOR UPDATE");
        if (expired.isEmpty()) return 0;
        int closed = 0;
        for (Map<String, Object> order : expired) {
            String orderNo = String.valueOf(order.get("order_no"));
            try {
                int affected = jdbcTemplate.update(
                        "UPDATE payment_order SET status=2, updated_time=NOW() " +
                                "WHERE order_no=? AND status=0 AND deleted=0", orderNo);
                if (affected == 1) {
                    closed++;
                    // 活动订单：释放预占名额
                    int isActivityOrder = toInt(order.get("is_activity_order"));
                    int quotaPreoccupied = toInt(order.get("quota_preoccupied"));
                    if (isActivityOrder == 1 && quotaPreoccupied == 1) {
                        Long activityPlanId = toLong(order.get("activity_plan_id"));
                        if (activityPlanId != null) {
                            try {
                                promotionService.releaseQuota(activityPlanId, orderNo, "order_expired");
                                jdbcTemplate.update("UPDATE payment_order SET quota_preoccupied=0 WHERE order_no=? AND deleted=0", orderNo);
                            } catch (Exception e) {
                                log.error("超时订单释放活动名额失败 orderNo={} activityPlanId={} errorType={}",
                                        orderNo, activityPlanId, e.getClass().getSimpleName(), e);
                            }
                        }
                    }
                }
            } catch (Exception e) {
                log.warn("关闭超时订单失败 orderNo={} errorType={}", orderNo, e.getClass().getSimpleName());
            }
        }
        return closed;
    }

    private int toInt(Object v) {
        if (v == null) return 0;
        if (v instanceof Number n) return n.intValue();
        try {
            return Integer.parseInt(String.valueOf(v).trim());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private Long toLong(Object v) {
        if (v == null) return null;
        if (v instanceof Number n) return n.longValue();
        try {
            return Long.parseLong(String.valueOf(v).trim());
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
