package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.TenantContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.*;

/**
 * 会员充值限时活动服务。
 *
 * 负责活动 CRUD、状态机、名额并发控制（预占/确认/释放）、套餐联动校验、
 * 前台活动查询、后台统计。所有价格/状态/名额判断均由服务端完成。
 *
 * 名额控制采用"创建订单时预占 + 支付成功时确认 + 超时/取消时释放"模式，
 * 复用 payment_order 行锁 + 条件更新 + requireSingleWrite 机制防超卖。
 */
@Service
public class MemberPromotionService {
    private static final Logger log = LoggerFactory.getLogger(MemberPromotionService.class);
    private static final int MAX_ACTIVITY_NAME_LENGTH = 100;
    private static final int MAX_ACTIVITY_CODE_LENGTH = 50;
    private static final int MAX_NOTICE_TITLE_LENGTH = 50;
    private static final int MAX_NOTICE_CONTENT_LENGTH = 500;
    private static final int MAX_DESCRIPTION_LENGTH = 500;
    private static final int MAX_ACTIVITY_TAG_LENGTH = 20;
    private static final int MAX_BATCH_PLANS = 20;
    private static final LocalDateTime FAR_FUTURE = LocalDateTime.of(9999, 12, 31, 23, 59, 59);

    private final JdbcTemplate jdbcTemplate;
    private final OperationAuditService auditService;

    @Autowired
    public MemberPromotionService(JdbcTemplate jdbcTemplate, OperationAuditService auditService) {
        this.jdbcTemplate = jdbcTemplate;
        this.auditService = auditService;
    }

    // ==================== 后台：活动 CRUD ====================

    public PageResult<Map<String, Object>> pageActivities(int current, int size, String keyword, String status) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 100);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (activity_name LIKE ? OR activity_code LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw);
        }
        if (StringUtils.hasText(status)) {
            where.append(" AND status=?");
            args.add(status);
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM member_promotion_activity" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT id, activity_name AS activityName, activity_code AS activityCode, description, status, " +
                        "start_time AS startTime, end_time AS endTime, is_long_term AS isLongTerm, " +
                        "auto_close_on_end AS autoCloseOnEnd, notice_title AS noticeTitle, notice_content AS noticeContent, " +
                        "notice_visible AS noticeVisible, notice_position AS noticePosition, notice_icon AS noticeIcon, " +
                        "total_quota AS totalQuota, sold_count AS soldCount, preoccupied_count AS preoccupiedCount, " +
                        "created_by AS createdBy, created_by_name AS createdByName, rule_version AS ruleVersion, " +
                        "created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM member_promotion_activity" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
                pageArgs.toArray());
        records.forEach(row -> {
            row.put("effectiveStatus", computeEffectiveStatus(toLong(row.get("id"))));
            row.put("planCount", countActivityPlans(toLong(row.get("id"))));
        });
        return new PageResult<>(records, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public Map<String, Object> activityDetail(Long id) {
        Map<String, Object> activity = queryOne(
                "SELECT id, activity_name AS activityName, activity_code AS activityCode, description, status, " +
                        "start_time AS startTime, end_time AS endTime, is_long_term AS isLongTerm, " +
                        "auto_close_on_end AS autoCloseOnEnd, notice_title AS noticeTitle, notice_content AS noticeContent, " +
                        "notice_visible AS noticeVisible, notice_position AS noticePosition, notice_icon AS noticeIcon, " +
                        "total_quota AS totalQuota, sold_count AS soldCount, preoccupied_count AS preoccupiedCount, " +
                        "created_by AS createdBy, created_by_name AS createdByName, rule_version AS ruleVersion, " +
                        "deleted, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM member_promotion_activity WHERE id=? AND deleted=0", id);
        if (activity == null) throw new BizException(404, "活动不存在");
        activity.put("effectiveStatus", computeEffectiveStatus(id));
        activity.put("plans", listActivityPlans(id));
        return activity;
    }

    @Transactional
    public Long createActivity(Map<String, Object> data) {
        String name = requireBoundedText(data.get("activityName"), "活动名称", MAX_ACTIVITY_NAME_LENGTH);
        String code = requireBoundedText(data.get("activityCode"), "活动编码", MAX_ACTIVITY_CODE_LENGTH);
        // 唯一性校验
        Integer existing = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM member_promotion_activity WHERE activity_code=? AND deleted=0",
                Integer.class, code);
        if (existing != null && existing > 0) {
            throw new BizException(409, "活动编码已存在");
        }
        String description = optionalBoundedText(data.get("description"), "活动备注", MAX_DESCRIPTION_LENGTH);
        LocalDateTime startTime = parseDateTime(required(data, "startTime", "开始时间不能为空"), "开始时间");
        boolean isLongTerm = toBool(data.get("isLongTerm"));
        LocalDateTime endTime = isLongTerm ? FAR_FUTURE
                : parseDateTime(required(data, "endTime", "结束时间不能为空"), "结束时间");
        if (!isLongTerm && !endTime.isAfter(startTime)) {
            throw new BizException(400, "结束时间必须晚于开始时间");
        }
        boolean autoClose = toBoolDefault(data.get("autoCloseOnEnd"), true);
        String noticeTitle = optionalBoundedText(data.get("noticeTitle"), "通知标题", MAX_NOTICE_TITLE_LENGTH);
        String noticeContent = optionalBoundedText(data.get("noticeContent"), "通知正文", MAX_NOTICE_CONTENT_LENGTH);
        // 纯文本过滤：移除 HTML 标签
        if (StringUtils.hasText(noticeContent)) {
            noticeContent = stripHtml(noticeContent);
        }
        boolean noticeVisible = toBoolDefault(data.get("noticeVisible"), true);
        String noticePosition = optionalTextDefault(data.get("noticePosition"), "top", "通知位置");
        String noticeIcon = optionalTextDefault(data.get("noticeIcon"), "hot", "通知图标");
        Long createdBy = AdminContext.userId();
        String createdByName = AdminContext.username();
        String status = "draft";
        String sql = "INSERT INTO member_promotion_activity(activity_name, activity_code, description, status, " +
                "start_time, end_time, is_long_term, auto_close_on_end, notice_title, notice_content, notice_visible, " +
                "notice_position, notice_icon, total_quota, sold_count, preoccupied_count, created_by, created_by_name, " +
                "rule_version, deleted, created_time, updated_time) " +
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0,?,?,1,0,NOW(),NOW())";
        requireSingleWrite("创建活动失败", sql,
                name, code, description, status, startTime, endTime, isLongTerm ? 1 : 0, autoClose ? 1 : 0,
                noticeTitle, noticeContent, noticeVisible ? 1 : 0, noticePosition, noticeIcon,
                createdBy, createdByName);
        Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        // 保存套餐配置
        List<Map<String, Object>> plans = extractPlans(data.get("plans"));
        if (!plans.isEmpty()) {
            saveActivityPlans(id, plans);
        }
        auditService.record(TenantContext.getCurrentTenantId(), AdminContext.userId(),
                "CREATE_PROMOTION", "创建会员充值活动：" + name, "member_promotion_activity", id, null);
        return id;
    }

    @Transactional
    public void updateActivity(Long id, Map<String, Object> data) {
        Map<String, Object> existing = activityDetail(id);
        String status = text(existing.get("status"));
        String effectiveStatus = computeEffectiveStatus(id);
        // 仅 draft/closed/ended 可编辑（进行中不可编辑关键字段，避免影响已下单用户）
        if (!"draft".equals(status) && !"closed".equals(status) && !"ended".equals(status)) {
            throw new BizException(400, "当前活动状态（" + effectiveStatus + "）不允许编辑，请先关闭活动");
        }
        String name = requireBoundedText(data.get("activityName"), "活动名称", MAX_ACTIVITY_NAME_LENGTH);
        String description = optionalBoundedText(data.get("description"), "活动备注", MAX_DESCRIPTION_LENGTH);
        LocalDateTime startTime = parseDateTime(required(data, "startTime", "开始时间不能为空"), "开始时间");
        boolean isLongTerm = toBool(data.get("isLongTerm"));
        LocalDateTime endTime = isLongTerm ? FAR_FUTURE
                : parseDateTime(required(data, "endTime", "结束时间不能为空"), "结束时间");
        if (!isLongTerm && !endTime.isAfter(startTime)) {
            throw new BizException(400, "结束时间必须晚于开始时间");
        }
        boolean autoClose = toBoolDefault(data.get("autoCloseOnEnd"), true);
        String noticeTitle = optionalBoundedText(data.get("noticeTitle"), "通知标题", MAX_NOTICE_TITLE_LENGTH);
        String noticeContent = optionalBoundedText(data.get("noticeContent"), "通知正文", MAX_NOTICE_CONTENT_LENGTH);
        if (StringUtils.hasText(noticeContent)) {
            noticeContent = stripHtml(noticeContent);
        }
        boolean noticeVisible = toBoolDefault(data.get("noticeVisible"), true);
        String noticePosition = optionalTextDefault(data.get("noticePosition"), "top", "通知位置");
        String noticeIcon = optionalTextDefault(data.get("noticeIcon"), "hot", "通知图标");
        // 校验套餐配置（若提供）
        List<Map<String, Object>> plans = extractPlans(data.get("plans"));
        if (!plans.isEmpty()) {
            validateActivityPlans(plans);
        }
        // 关键字段变更需 rule_version+1（价格/名额/时间变更）
        boolean ruleChanged = !Objects.equals(text(existing.get("startTime")), startTime.toString())
                || !Objects.equals(text(existing.get("endTime")), endTime.toString())
                || !plans.isEmpty();
        String sql = "UPDATE member_promotion_activity SET activity_name=?, description=?, start_time=?, end_time=?, " +
                "is_long_term=?, auto_close_on_end=?, notice_title=?, notice_content=?, notice_visible=?, " +
                "notice_position=?, notice_icon=?, updated_time=NOW()" +
                (ruleChanged ? ", rule_version=rule_version+1" : "") + " WHERE id=? AND deleted=0";
        requireSingleWrite("更新活动失败", sql,
                name, description, startTime, endTime, isLongTerm ? 1 : 0, autoClose ? 1 : 0,
                noticeTitle, noticeContent, noticeVisible ? 1 : 0, noticePosition, noticeIcon, id);
        if (!plans.isEmpty()) {
            // 替换套餐配置（仅 draft/closed 时允许）
            replaceActivityPlans(id, plans);
        }
        Map<String, Object> after = activityDetail(id);
        auditService.recordRequired(TenantContext.getCurrentTenantId(), AdminContext.userId(),
                "UPDATE_PROMOTION", "修改会员充值活动：" + name,
                "member_promotion_activity", id,
                "修改前：" + toJson(existing) + "；修改后：" + toJson(after));
    }

    @Transactional
    public void startActivity(Long id) {
        Map<String, Object> activity = activityDetail(id);
        String status = text(activity.get("status"));
        if (!"draft".equals(status)) {
            throw new BizException(400, "仅草稿状态的活动可以开启，当前状态：" + status);
        }
        // 校验至少有一个有效套餐配置
        List<Map<String, Object>> plans = listActivityPlans(id);
        if (plans.isEmpty()) {
            throw new BizException(400, "活动至少需要配置一个套餐才能开启");
        }
        // 校验时间
        LocalDateTime startTime = toLocalDateTime(activity.get("startTime"));
        LocalDateTime endTime = toLocalDateTime(activity.get("endTime"));
        if (endTime.isBefore(LocalDateTime.now())) {
            throw new BizException(400, "活动结束时间已过，请修改时间后再开启");
        }
        // 校验套餐无时间重叠
        for (Map<String, Object> plan : plans) {
            if (hasOverlappingActivity(toLong(plan.get("planId")), text(plan.get("periodType")), id)) {
                throw new BizException(409, "套餐 " + text(plan.get("planName")) + " 已参与其他进行中活动");
            }
        }
        // 计算 total_quota
        int totalQuota = plans.stream()
                .filter(p -> toInt(p.get("quota")) > 0)
                .mapToInt(p -> toInt(p.get("quota"))).sum();
        String pendingStatus = startTime.isAfter(LocalDateTime.now()) ? "pending" : "ongoing";
        requireSingleWrite("开启活动失败",
                "UPDATE member_promotion_activity SET status=?, total_quota=?, updated_time=NOW() WHERE id=? AND deleted=0",
                pendingStatus, totalQuota, id);
        auditService.recordRequired(TenantContext.getCurrentTenantId(), AdminContext.userId(),
                "START_PROMOTION", "开启会员充值活动：" + text(activity.get("activityName")),
                "member_promotion_activity", id, "状态：" + status + " → " + pendingStatus);
    }

    @Transactional
    public void closeActivity(Long id) {
        Map<String, Object> activity = activityDetail(id);
        String status = text(activity.get("status"));
        if ("closed".equals(status) || "draft".equals(status)) {
            throw new BizException(400, "当前活动状态不允许关闭");
        }
        requireSingleWrite("关闭活动失败",
                "UPDATE member_promotion_activity SET status='closed', updated_time=NOW() WHERE id=? AND deleted=0", id);
        auditService.recordRequired(TenantContext.getCurrentTenantId(), AdminContext.userId(),
                "CLOSE_PROMOTION", "关闭会员充值活动：" + text(activity.get("activityName")),
                "member_promotion_activity", id, "状态：" + status + " → closed");
    }

    @Transactional
    public void reopenActivity(Long id) {
        Map<String, Object> activity = activityDetail(id);
        String status = text(activity.get("status"));
        if (!"ended".equals(status) && !"closed".equals(status)) {
            throw new BizException(400, "仅已结束或已关闭的活动可以重新开启");
        }
        LocalDateTime endTime = toLocalDateTime(activity.get("endTime"));
        if (endTime.isBefore(LocalDateTime.now())) {
            throw new BizException(400, "活动结束时间已过，请修改结束时间后再重新开启");
        }
        // 校验套餐无时间重叠
        List<Map<String, Object>> plans = listActivityPlans(id);
        for (Map<String, Object> plan : plans) {
            if (hasOverlappingActivity(toLong(plan.get("planId")), text(plan.get("periodType")), id)) {
                throw new BizException(409, "套餐 " + text(plan.get("planName")) + " 已参与其他进行中活动");
            }
        }
        LocalDateTime startTime = toLocalDateTime(activity.get("startTime"));
        String newStatus = startTime.isAfter(LocalDateTime.now()) ? "pending" : "ongoing";
        requireSingleWrite("重新开启活动失败",
                "UPDATE member_promotion_activity SET status=?, updated_time=NOW() WHERE id=? AND deleted=0",
                newStatus, id);
        auditService.recordRequired(TenantContext.getCurrentTenantId(), AdminContext.userId(),
                "REOPEN_PROMOTION", "重新开启会员充值活动：" + text(activity.get("activityName")),
                "member_promotion_activity", id, "状态：" + status + " → " + newStatus);
    }

    @Transactional
    public void deleteActivity(Long id) {
        Map<String, Object> activity = activityDetail(id);
        String status = text(activity.get("status"));
        if (!"draft".equals(status) && !"closed".equals(status)) {
            throw new BizException(400, "仅草稿或已关闭的活动可以删除");
        }
        // 检查是否有活动订单
        Integer orderCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM payment_order WHERE activity_id=? AND deleted=0",
                Integer.class, id);
        if (orderCount != null && orderCount > 0) {
            throw new BizException(400, "活动存在历史订单，无法删除（请改为关闭）");
        }
        requireSingleWrite("删除活动失败",
                "UPDATE member_promotion_activity SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
        jdbcTemplate.update("UPDATE member_promotion_plan SET deleted=1, updated_time=NOW() WHERE activity_id=? AND deleted=0", id);
        auditService.recordRequired(TenantContext.getCurrentTenantId(), AdminContext.userId(),
                "DELETE_PROMOTION", "删除会员充值活动：" + text(activity.get("activityName")),
                "member_promotion_activity", id, "活动编码：" + text(activity.get("activityCode")));
    }

    @Transactional
    public void adjustQuota(Long activityId, Long activityPlanId, int newQuota, String remark) {
        Map<String, Object> plan = queryOne(
                "SELECT id, activity_id, plan_id, period_type, activity_price_cent, quota, sold_count, preoccupied_count " +
                        "FROM member_promotion_plan WHERE id=? AND activity_id=? AND deleted=0 FOR UPDATE",
                activityPlanId, activityId);
        if (plan == null) throw new BizException(404, "活动套餐配置不存在");
        int oldQuota = toInt(plan.get("quota"));
        int sold = toInt(plan.get("sold_count"));
        int preoccupied = toInt(plan.get("preoccupied_count"));
        if (newQuota < 0) throw new BizException(400, "名额不能为负数");
        if (newQuota > 0 && newQuota < sold + preoccupied) {
            throw new BizException(400, "名额不能小于已售+预占份数（" + (sold + preoccupied) + "）");
        }
        requireSingleWrite("调整名额失败",
                "UPDATE member_promotion_plan SET quota=?, updated_time=NOW() WHERE id=? AND deleted=0",
                newQuota, activityPlanId);
        // 重新汇总活动总名额
        refreshActivityTotalQuota(activityId);
        // rule_version+1
        jdbcTemplate.update("UPDATE member_promotion_activity SET rule_version=rule_version+1, updated_time=NOW() WHERE id=? AND deleted=0", activityId);
        // 审计日志
        writeQuotaLog(activityId, activityPlanId, null, "admin_adjust", newQuota - oldQuota, oldQuota, newQuota,
                AdminContext.userId(), AdminContext.username(), remark);
        auditService.recordRequired(TenantContext.getCurrentTenantId(), AdminContext.userId(),
                "ADJUST_PROMOTION_QUOTA",
                "调整活动名额：套餐ID=" + activityPlanId + "，" + oldQuota + " → " + newQuota,
                "member_promotion_plan", activityPlanId,
                "调整前：" + oldQuota + "，调整后：" + newQuota + "，备注：" + remark);
    }

    // ==================== 后台：统计 ====================

    public Map<String, Object> activityStats(Long activityId) {
        Map<String, Object> activity = activityDetail(activityId);
        Map<String, Object> stats = new LinkedHashMap<>(activity);
        // 订单统计
        Map<String, Object> orderStats = queryOne(
                "SELECT COUNT(*) AS totalOrders, " +
                        "SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) AS paidOrders, " +
                        "SUM(CASE WHEN status=0 THEN 1 ELSE 0 END) AS pendingOrders, " +
                        "SUM(CASE WHEN status=2 THEN 1 ELSE 0 END) AS closedOrders, " +
                        "SUM(CASE WHEN status=1 THEN amount_cent ELSE 0 END) AS totalRevenueCent, " +
                        "SUM(CASE WHEN status=1 THEN discount_cent ELSE 0 END) AS totalDiscountCent, " +
                        "COUNT(DISTINCT CASE WHEN status=1 THEN user_id END) AS paidUserCount " +
                        "FROM payment_order WHERE activity_id=? AND deleted=0", activityId);
        if (orderStats != null) {
            long totalRevenueCent = toLong(orderStats.get("totalRevenueCent"));
            long totalDiscountCent = toLong(orderStats.get("totalDiscountCent"));
            stats.put("totalOrders", toLong(orderStats.get("totalOrders")));
            stats.put("paidOrders", toLong(orderStats.get("paidOrders")));
            stats.put("pendingOrders", toLong(orderStats.get("pendingOrders")));
            stats.put("closedOrders", toLong(orderStats.get("closedOrders")));
            stats.put("paidUserCount", toLong(orderStats.get("paidUserCount")));
            stats.put("totalRevenueCent", totalRevenueCent);
            stats.put("totalRevenueYuan", formatYuan(totalRevenueCent));
            stats.put("totalDiscountCent", totalDiscountCent);
            stats.put("totalDiscountYuan", formatYuan(totalDiscountCent));
            long totalOrders = toLong(orderStats.get("totalOrders"));
            long paidOrders = toLong(orderStats.get("paidOrders"));
            stats.put("conversionRate", totalOrders > 0
                    ? new BigDecimal(paidOrders).multiply(BigDecimal.valueOf(100)).divide(BigDecimal.valueOf(totalOrders), 2, RoundingMode.HALF_UP).toString() + "%"
                    : "0%");
        }
        // 各套餐明细
        List<Map<String, Object>> planStats = jdbcTemplate.queryForList(
                "SELECT ap.id AS activityPlanId, ap.plan_id AS planId, bp.plan_name AS planName, ap.period_type AS periodType, " +
                        "ap.activity_price_cent AS activityPriceCent, ROUND(ap.activity_price_cent/100,2) AS activityPriceYuan, " +
                        "bp.price_month_cent AS priceMonthCent, bp.price_quarter_cent AS priceQuarterCent, bp.price_year_cent AS priceYearCent, " +
                        "ap.quota, ap.sold_count AS soldCount, ap.preoccupied_count AS preoccupiedCount, " +
                        "(SELECT SUM(amount_cent) FROM payment_order WHERE activity_plan_id=ap.id AND status=1 AND deleted=0) AS revenueCent, " +
                        "(SELECT ROUND(SUM(amount_cent)/100,2) FROM payment_order WHERE activity_plan_id=ap.id AND status=1 AND deleted=0) AS revenueYuan " +
                        "FROM member_promotion_plan ap LEFT JOIN billing_plan bp ON bp.id=ap.plan_id " +
                        "WHERE ap.activity_id=? AND ap.deleted=0 ORDER BY ap.sort_order ASC, ap.id ASC", activityId);
        planStats.forEach(p -> {
            int quota = toInt(p.get("quota"));
            int sold = toInt(p.get("soldCount"));
            int preoccupied = toInt(p.get("preoccupiedCount"));
            p.put("remainCount", quota > 0 ? Math.max(0, quota - sold - preoccupied) : -1);
            p.put("remainText", quota > 0 ? String.valueOf(Math.max(0, quota - sold - preoccupied)) : "不限量");
            p.put("quotaText", quota > 0 ? sold + " / " + quota : sold + " / 不限量");
            // 原价
            String periodType = text(p.get("periodType"));
            long originalCent = "quarter".equals(periodType) ? toLong(p.get("priceQuarterCent"))
                    : "year".equals(periodType) ? toLong(p.get("priceYearCent"))
                    : toLong(p.get("priceMonthCent"));
            p.put("originalPriceCent", originalCent);
            p.put("originalPriceYuan", formatYuan(originalCent));
        });
        stats.put("planStats", planStats);
        return stats;
    }

    public PageResult<Map<String, Object>> activityOrders(Long activityId, int current, int size, String status) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 100);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        args.add(activityId);
        StringBuilder where = new StringBuilder(" WHERE o.activity_id=? AND o.deleted=0");
        if (StringUtils.hasText(status)) {
            where.append(" AND o.status=?");
            args.add(parseStatusValue(status));
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM payment_order o" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT o.id, o.order_no AS orderNo, o.user_id AS userId, u.username, o.title, " +
                        "o.amount_cent AS amountCent, ROUND(o.amount_cent/100,2) AS amountYuan, " +
                        "o.original_price_cent AS originalPriceCent, ROUND(o.original_price_cent/100,2) AS originalPriceYuan, " +
                        "o.activity_price_cent AS activityPriceCent, ROUND(o.activity_price_cent/100,2) AS activityPriceYuan, " +
                        "o.discount_cent AS discountCent, ROUND(o.discount_cent/100,2) AS discountYuan, " +
                        "o.status, o.paid_time AS paidTime, o.created_time AS createdTime, " +
                        "o.activity_plan_id AS activityPlanId " +
                        "FROM payment_order o LEFT JOIN sys_user u ON u.id=o.user_id" + where +
                        " ORDER BY o.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        records.forEach(row -> {
            int s = toInt(row.get("status"));
            row.put("statusText", statusText(s));
        });
        return new PageResult<>(records, safeCurrent, safeSize, total == null ? 0 : total);
    }

    // ==================== 前台：活动查询 ====================

    public Map<String, Object> activeActivity() {
        // 查找当前有效活动（status=ongoing 或 pending 即将开始）
        List<Map<String, Object>> activities = jdbcTemplate.queryForList(
                "SELECT id, activity_name AS activityName, status, start_time AS startTime, end_time AS endTime, " +
                        "is_long_term AS isLongTerm, notice_title AS noticeTitle, notice_content AS noticeContent, " +
                        "notice_visible AS noticeVisible, notice_position AS noticePosition, notice_icon AS noticeIcon, " +
                        "rule_version AS ruleVersion " +
                        "FROM member_promotion_activity " +
                        "WHERE deleted=0 AND status IN ('ongoing','pending') " +
                        "AND start_time <= NOW() AND end_time >= NOW() " +
                        "ORDER BY id DESC LIMIT 1");
        if (activities.isEmpty()) {
            return Collections.emptyMap();
        }
        Map<String, Object> activity = activities.get(0);
        Long activityId = toLong(activity.get("id"));
        activity.put("serverNow", LocalDateTime.now().toString());
        activity.put("status", computeEffectiveStatus(activityId));
        // 通知信息
        Map<String, Object> notice = new LinkedHashMap<>();
        notice.put("title", activity.get("noticeTitle"));
        notice.put("content", activity.get("noticeContent"));
        notice.put("visible", toInt(activity.get("noticeVisible")) == 1);
        notice.put("position", activity.get("noticePosition"));
        notice.put("icon", activity.get("noticeIcon"));
        activity.put("notice", notice);
        // 套餐配置
        activity.put("plans", listActivePlansForFrontend(activityId));
        return activity;
    }

    private List<Map<String, Object>> listActivePlansForFrontend(Long activityId) {
        List<Map<String, Object>> plans = jdbcTemplate.queryForList(
                "SELECT ap.id AS activityPlanId, ap.plan_id AS planId, bp.plan_name AS planName, bp.plan_code AS planCode, " +
                        "ap.period_type AS periodType, ap.activity_price_cent AS activityPriceCent, " +
                        "ap.quota, ap.sold_count AS soldCount, ap.preoccupied_count AS preoccupiedCount, " +
                        "ap.sort_order AS sortOrder, ap.activity_tag AS activityTag, " +
                        "ap.show_sold_count AS showSoldCount, ap.show_quota AS showQuota, " +
                        "ap.show_remain AS showRemain, ap.allow_repurchase AS allowRepurchase, " +
                        "ap.max_purchase_per_user AS maxPurchasePerUser, ap.rule_version AS ruleVersion, " +
                        "bp.price_month_cent AS priceMonthCent, bp.price_quarter_cent AS priceQuarterCent, " +
                        "bp.price_year_cent AS priceYearCent " +
                        "FROM member_promotion_plan ap " +
                        "INNER JOIN billing_plan bp ON bp.id=ap.plan_id AND bp.deleted=0 AND bp.status=1 " +
                        "WHERE ap.activity_id=? AND ap.deleted=0 " +
                        "ORDER BY ap.sort_order ASC, ap.id ASC", activityId);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> plan : plans) {
            String periodType = text(plan.get("periodType"));
            long originalCent = "quarter".equals(periodType) ? toLong(plan.get("priceQuarterCent"))
                    : "year".equals(periodType) ? toLong(plan.get("priceYearCent"))
                    : toLong(plan.get("priceMonthCent"));
            long activityCent = toLong(plan.get("activityPriceCent"));
            // 实时校验：活动价必须 ≤ 原价
            if (originalCent > 0 && activityCent > originalCent) {
                log.warn("活动套餐 {} 活动价 {} 高于原价 {}，跳过展示", plan.get("activityPlanId"), activityCent, originalCent);
                continue;
            }
            int quota = toInt(plan.get("quota"));
            int sold = toInt(plan.get("soldCount"));
            int preoccupied = toInt(plan.get("preoccupiedCount"));
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("activityPlanId", plan.get("activityPlanId"));
            p.put("planId", plan.get("planId"));
            p.put("planName", plan.get("planName"));
            p.put("planCode", plan.get("planCode"));
            p.put("periodType", periodType);
            p.put("originalPriceCent", originalCent);
            p.put("originalPriceYuan", formatYuan(originalCent));
            p.put("activityPriceCent", activityCent);
            p.put("activityPriceYuan", formatYuan(activityCent));
            long discountCent = Math.max(0, originalCent - activityCent);
            p.put("discountCent", discountCent);
            p.put("discountYuan", formatYuan(discountCent));
            p.put("discountRate", originalCent > 0
                    ? new BigDecimal(activityCent).multiply(BigDecimal.TEN).divide(new BigDecimal(originalCent), 1, RoundingMode.HALF_UP).toString()
                    : "0");
            p.put("quota", quota);
            p.put("soldCount", sold);
            p.put("preoccupiedCount", preoccupied);
            p.put("remainCount", quota > 0 ? Math.max(0, quota - sold - preoccupied) : -1);
            p.put("remainText", quota > 0 ? String.valueOf(Math.max(0, quota - sold - preoccupied)) : "不限量");
            p.put("showSoldCount", toInt(plan.get("showSoldCount")) == 1);
            p.put("showQuota", toInt(plan.get("showQuota")) == 1);
            p.put("showRemain", toInt(plan.get("showRemain")) == 1);
            p.put("allowRepurchase", toInt(plan.get("allowRepurchase")) == 1);
            p.put("maxPurchasePerUser", toInt(plan.get("maxPurchasePerUser")));
            p.put("activityTag", plan.get("activityTag"));
            p.put("sortOrder", toInt(plan.get("sortOrder")));
            p.put("ruleVersion", toInt(plan.get("ruleVersion")));
            result.add(p);
        }
        return result;
    }

    /**
     * 下单前预览：实时校验活动状态、价格、名额。
     * 用于前端点击"立即抢购"后、创建订单前的二次确认。
     */
    public Map<String, Object> previewActivityPlan(Long planId, String periodType) {
        Map<String, Object> plan = queryOne(
                "SELECT ap.id AS activityPlanId, ap.activity_id AS activityId, ap.activity_price_cent AS activityPriceCent, " +
                        "ap.quota, ap.sold_count AS soldCount, ap.preoccupied_count AS preoccupiedCount, " +
                        "ap.allow_repurchase AS allowRepurchase, ap.max_purchase_per_user AS maxPurchasePerUser, " +
                        "ap.rule_version AS ruleVersion, a.status AS activityStatus, a.start_time AS startTime, " +
                        "a.end_time AS endTime, a.activity_name AS activityName, a.rule_version AS activityRuleVersion, " +
                        "bp.plan_name AS planName, bp.price_month_cent AS priceMonthCent, " +
                        "bp.price_quarter_cent AS priceQuarterCent, bp.price_year_cent AS priceYearCent, " +
                        "bp.status AS planStatus, bp.deleted AS planDeleted " +
                        "FROM member_promotion_plan ap " +
                        "INNER JOIN member_promotion_activity a ON a.id=ap.activity_id AND a.deleted=0 " +
                        "INNER JOIN billing_plan bp ON bp.id=ap.plan_id AND bp.deleted=0 " +
                        "WHERE ap.plan_id=? AND ap.period_type=? AND ap.deleted=0 " +
                        "ORDER BY ap.id DESC LIMIT 1", planId, periodType);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("serverNow", LocalDateTime.now().toString());
        if (plan == null) {
            result.put("available", false);
            result.put("reason", "no_activity");
            return result;
        }
        Long activityId = toLong(plan.get("activityId"));
        Long activityPlanId = toLong(plan.get("activityPlanId"));
        String effectiveStatus = computeEffectiveStatus(activityId);
        long originalCent = "quarter".equals(periodType) ? toLong(plan.get("priceQuarterCent"))
                : "year".equals(periodType) ? toLong(plan.get("priceYearCent"))
                : toLong(plan.get("priceMonthCent"));
        long activityCent = toLong(plan.get("activityPriceCent"));
        int quota = toInt(plan.get("quota"));
        int sold = toInt(plan.get("soldCount"));
        int preoccupied = toInt(plan.get("preoccupiedCount"));
        int remain = quota > 0 ? Math.max(0, quota - sold - preoccupied) : -1;
        result.put("activityPlanId", activityPlanId);
        result.put("activityId", activityId);
        result.put("activityName", plan.get("activityName"));
        result.put("finalPriceCent", activityCent);
        result.put("finalPriceYuan", formatYuan(activityCent));
        result.put("originalPriceCent", originalCent);
        result.put("originalPriceYuan", formatYuan(originalCent));
        result.put("remainCount", remain);
        result.put("ruleVersion", toInt(plan.get("activityRuleVersion")));
        result.put("endTime", plan.get("endTime"));
        // 校验可用性
        if (!"ongoing".equals(effectiveStatus)) {
            result.put("available", false);
            result.put("reason", mapUnavailableReason(effectiveStatus));
            return result;
        }
        if (toInt(plan.get("planStatus")) != 1 || toInt(plan.get("planDeleted")) != 0) {
            result.put("available", false);
            result.put("reason", "plan_offline");
            return result;
        }
        if (originalCent > 0 && activityCent > originalCent) {
            result.put("available", false);
            result.put("reason", "price_invalid");
            return result;
        }
        if (quota > 0 && remain <= 0) {
            result.put("available", false);
            result.put("reason", "quota_full");
            return result;
        }
        result.put("available", true);
        result.put("reason", null);
        return result;
    }

    // ==================== 名额控制（被 PaymentService 调用） ====================

    /**
     * 预占名额（创建订单时调用）。
     * 行锁 + 条件更新防超卖。
     */
    @Transactional
    public void preoccupyQuota(Long activityPlanId, String orderNo) {
        Map<String, Object> plan = queryOne(
                "SELECT id, activity_id, quota, sold_count, preoccupied_count " +
                        "FROM member_promotion_plan WHERE id=? AND deleted=0 FOR UPDATE", activityPlanId);
        if (plan == null) {
            throw new BizException(404, "活动套餐配置不存在");
        }
        int quota = toInt(plan.get("quota"));
        int sold = toInt(plan.get("sold_count"));
        int preoccupied = toInt(plan.get("preoccupied_count"));
        if (quota > 0 && sold + preoccupied >= quota) {
            throw new BizException(503, "活动名额已满，请稍后再试");
        }
        // 条件更新：仅 quota=0 或 sold+preoccupied < quota 时才能 +1
        int updated = jdbcTemplate.update(
                "UPDATE member_promotion_plan SET preoccupied_count=preoccupied_count+1, updated_time=NOW() " +
                        "WHERE id=? AND deleted=0 AND (quota=0 OR sold_count+preoccupied_count < quota)",
                activityPlanId);
        if (updated != 1) {
            throw new BizException(503, "活动名额已满，请稍后再试");
        }
        // 同步活动主表
        jdbcTemplate.update(
                "UPDATE member_promotion_activity SET preoccupied_count=preoccupied_count+1, updated_time=NOW() " +
                        "WHERE id=? AND deleted=0", toLong(plan.get("activity_id")));
        // 审计日志
        writeQuotaLog(toLong(plan.get("activity_id")), activityPlanId, orderNo, "preoccupy", 1,
                preoccupied, preoccupied + 1, null, null, "创建订单预占名额");
    }

    /**
     * 确认扣减名额（支付成功时调用）。
     * preoccupied-1, sold+1。幂等：通过 quota_preoccupied 字段控制。
     */
    @Transactional
    public void confirmQuota(Long activityPlanId, String orderNo) {
        Map<String, Object> plan = queryOne(
                "SELECT id, activity_id, sold_count, preoccupied_count " +
                        "FROM member_promotion_plan WHERE id=? AND deleted=0 FOR UPDATE", activityPlanId);
        if (plan == null) {
            log.warn("确认名额扣减时活动套餐配置不存在：activityPlanId={}", activityPlanId);
            return;
        }
        int sold = toInt(plan.get("sold_count"));
        int preoccupied = toInt(plan.get("preoccupied_count"));
        jdbcTemplate.update(
                "UPDATE member_promotion_plan SET preoccupied_count=GREATEST(preoccupied_count-1,0), " +
                        "sold_count=sold_count+1, updated_time=NOW() WHERE id=? AND deleted=0",
                activityPlanId);
        jdbcTemplate.update(
                "UPDATE member_promotion_activity SET preoccupied_count=GREATEST(preoccupied_count-1,0), " +
                        "sold_count=sold_count+1, updated_time=NOW() WHERE id=? AND deleted=0",
                toLong(plan.get("activity_id")));
        writeQuotaLog(toLong(plan.get("activity_id")), activityPlanId, orderNo, "confirm", 1,
                sold, sold + 1, null, null, "支付成功确认扣减");
    }

    /**
     * 释放预占名额（订单关闭/超时时调用）。
     * preoccupied-1。幂等：调用方需先校验 quota_preoccupied=1。
     */
    @Transactional
    public void releaseQuota(Long activityPlanId, String orderNo, String reason) {
        Map<String, Object> plan = queryOne(
                "SELECT id, activity_id, preoccupied_count " +
                        "FROM member_promotion_plan WHERE id=? AND deleted=0 FOR UPDATE", activityPlanId);
        if (plan == null) {
            log.warn("释放名额时活动套餐配置不存在：activityPlanId={}", activityPlanId);
            return;
        }
        int preoccupied = toInt(plan.get("preoccupied_count"));
        jdbcTemplate.update(
                "UPDATE member_promotion_plan SET preoccupied_count=GREATEST(preoccupied_count-1,0), " +
                        "updated_time=NOW() WHERE id=? AND deleted=0", activityPlanId);
        jdbcTemplate.update(
                "UPDATE member_promotion_activity SET preoccupied_count=GREATEST(preoccupied_count-1,0), " +
                        "updated_time=NOW() WHERE id=? AND deleted=0", toLong(plan.get("activity_id")));
        writeQuotaLog(toLong(plan.get("activity_id")), activityPlanId, orderNo, "release", -1,
                preoccupied, Math.max(0, preoccupied - 1), null, null, reason);
    }

    // ==================== 套餐联动（被 BillingPlanService 调用） ====================

    /**
     * 套餐价格变更时校验：活动价必须 ≤ 新原价。
     * 若新原价低于活动价，阻止保存。
     */
    public void validatePlanPriceChange(Long planId, long newPriceMonthCent, long newPriceQuarterCent, long newPriceYearCent) {
        List<Map<String, Object>> conflicts = jdbcTemplate.queryForList(
                "SELECT ap.id, ap.activity_id, ap.period_type, ap.activity_price_cent, a.activity_name, a.status " +
                        "FROM member_promotion_plan ap " +
                        "INNER JOIN member_promotion_activity a ON a.id=ap.activity_id AND a.deleted=0 " +
                        "WHERE ap.plan_id=? AND ap.deleted=0 AND a.status IN ('ongoing','pending')", planId);
        for (Map<String, Object> conflict : conflicts) {
            String periodType = text(conflict.get("period_type"));
            long activityPrice = toLong(conflict.get("activity_price_cent"));
            long newOriginal = "quarter".equals(periodType) ? newPriceQuarterCent
                    : "year".equals(periodType) ? newPriceYearCent : newPriceMonthCent;
            if (newOriginal > 0 && activityPrice > newOriginal) {
                throw new BizException(400, "套餐参与活动「" + conflict.get("activity_name")
                        + "」的" + periodLabel(periodType) + "活动价 " + formatYuan(activityPrice)
                        + " 高于新原价 " + formatYuan(newOriginal) + "，请先调整活动价或暂停活动");
            }
        }
    }

    /**
     * 套餐下架时：活动套餐前台自动停止展示（通过 INNER JOIN billing_plan status=1 实现）。
     * 此处仅记录日志，不修改活动状态。
     */
    public void onPlanOffline(Long planId) {
        List<Map<String, Object>> affected = jdbcTemplate.queryForList(
                "SELECT ap.id, ap.activity_id, a.activity_name " +
                        "FROM member_promotion_plan ap " +
                        "INNER JOIN member_promotion_activity a ON a.id=ap.activity_id AND a.deleted=0 " +
                        "WHERE ap.plan_id=? AND ap.deleted=0 AND a.status IN ('ongoing','pending')", planId);
        if (!affected.isEmpty()) {
            log.info("套餐 {} 下架，影响 {} 个活动套餐配置", planId, affected.size());
        }
    }

    // ==================== 状态机 ====================

    public String computeEffectiveStatus(Long activityId) {
        Map<String, Object> activity = queryOne(
                "SELECT status, start_time, end_time, is_long_term, deleted " +
                        "FROM member_promotion_activity WHERE id=?", activityId);
        if (activity == null) return "deleted";
        if (toInt(activity.get("deleted")) == 1) return "deleted";
        String status = text(activity.get("status"));
        if ("draft".equals(status)) return "draft";
        if ("closed".equals(status)) return "closed";
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime startTime = toLocalDateTime(activity.get("start_time"));
        LocalDateTime endTime = toLocalDateTime(activity.get("end_time"));
        if (now.isBefore(startTime)) return "pending";
        if (toInt(activity.get("is_long_term")) != 1 && now.isAfter(endTime)) return "ended";
        // 检查是否有任何可用套餐
        Integer availablePlans = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM member_promotion_plan ap " +
                        "INNER JOIN billing_plan bp ON bp.id=ap.plan_id AND bp.deleted=0 AND bp.status=1 " +
                        "WHERE ap.activity_id=? AND ap.deleted=0", Integer.class, activityId);
        if (availablePlans == null || availablePlans == 0) return "closed";
        // 检查名额是否已满
        Map<String, Object> quotaInfo = queryOne(
                "SELECT SUM(CASE WHEN ap.quota > 0 THEN ap.quota ELSE 0 END) AS totalQuota, " +
                        "SUM(ap.sold_count) AS totalSold, SUM(ap.preoccupied_count) AS totalPreoccupied " +
                        "FROM member_promotion_plan ap WHERE ap.activity_id=? AND ap.deleted=0", activityId);
        if (quotaInfo != null) {
            int totalQuota = toInt(quotaInfo.get("totalQuota"));
            int totalSold = toInt(quotaInfo.get("totalSold"));
            int totalPreoccupied = toInt(quotaInfo.get("totalPreoccupied"));
            if (totalQuota > 0 && totalSold + totalPreoccupied >= totalQuota) {
                return "quota_full";
            }
        }
        return "ongoing";
    }

    // ==================== 定时任务支持 ====================

    /**
     * 扫描待开始活动（pending → ongoing）。
     */
    @Transactional
    public int activateDueActivities() {
        List<Map<String, Object>> due = jdbcTemplate.queryForList(
                "SELECT id FROM member_promotion_activity " +
                        "WHERE deleted=0 AND status='pending' AND start_time <= NOW() AND end_time > NOW()");
        int count = 0;
        for (Map<String, Object> row : due) {
            Long id = toLong(row.get("id"));
            jdbcTemplate.update("UPDATE member_promotion_activity SET status='ongoing', updated_time=NOW() WHERE id=? AND deleted=0", id);
            log.info("活动 {} 自动激活为 ongoing", id);
            count++;
        }
        return count;
    }

    /**
     * 扫描到期活动（ongoing → ended）。
     */
    @Transactional
    public int endDueActivities() {
        List<Map<String, Object>> due = jdbcTemplate.queryForList(
                "SELECT id FROM member_promotion_activity " +
                        "WHERE deleted=0 AND status='ongoing' AND is_long_term=0 AND auto_close_on_end=1 AND end_time < NOW()");
        int count = 0;
        for (Map<String, Object> row : due) {
            Long id = toLong(row.get("id"));
            jdbcTemplate.update("UPDATE member_promotion_activity SET status='ended', updated_time=NOW() WHERE id=? AND deleted=0", id);
            log.info("活动 {} 已到期自动结束", id);
            count++;
        }
        return count;
    }

    // ==================== 内部辅助方法 ====================

    private List<Map<String, Object>> listActivityPlans(Long activityId) {
        return jdbcTemplate.queryForList(
                "SELECT ap.id, ap.activity_id AS activityId, ap.plan_id AS planId, bp.plan_name AS planName, " +
                        "ap.period_type AS periodType, ap.activity_price_cent AS activityPriceCent, " +
                        "ROUND(ap.activity_price_cent/100,2) AS activityPriceYuan, " +
                        "ap.quota, ap.sold_count AS soldCount, ap.preoccupied_count AS preoccupiedCount, " +
                        "ap.sort_order AS sortOrder, ap.activity_tag AS activityTag, " +
                        "ap.show_sold_count AS showSoldCount, ap.show_quota AS showQuota, " +
                        "ap.show_remain AS showRemain, ap.allow_repurchase AS allowRepurchase, " +
                        "ap.max_purchase_per_user AS maxPurchasePerUser, " +
                        "bp.price_month_cent AS priceMonthCent, bp.price_quarter_cent AS priceQuarterCent, " +
                        "bp.price_year_cent AS priceYearCent, bp.status AS planStatus, bp.deleted AS planDeleted " +
                        "FROM member_promotion_plan ap LEFT JOIN billing_plan bp ON bp.id=ap.plan_id " +
                        "WHERE ap.activity_id=? AND ap.deleted=0 ORDER BY ap.sort_order ASC, ap.id ASC", activityId);
    }

    private int countActivityPlans(Long activityId) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM member_promotion_plan WHERE activity_id=? AND deleted=0",
                Integer.class, activityId);
        return count == null ? 0 : count;
    }

    private void saveActivityPlans(Long activityId, List<Map<String, Object>> plans) {
        for (Map<String, Object> plan : plans) {
            Long planId = toLong(plan.get("planId"));
            String periodType = text(plan.get("periodType"));
            long activityPriceCent = toLong(plan.get("activityPriceCent"));
            int quota = toInt(plan.get("quota"));
            int sortOrder = toIntDefault(plan.get("sortOrder"), 0);
            String activityTag = optionalBoundedText(plan.get("activityTag"), "活动标签", MAX_ACTIVITY_TAG_LENGTH);
            boolean showSold = toBoolDefault(plan.get("showSoldCount"), true);
            boolean showQuota = toBoolDefault(plan.get("showQuota"), true);
            boolean showRemain = toBoolDefault(plan.get("showRemain"), true);
            boolean allowRepurchase = toBoolDefault(plan.get("allowRepurchase"), true);
            int maxPurchase = toIntDefault(plan.get("maxPurchasePerUser"), 0);
            // 唯一性校验：同 activity+plan+periodType
            Integer existing = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM member_promotion_plan WHERE activity_id=? AND plan_id=? AND period_type=? AND deleted=0",
                    Integer.class, activityId, planId, periodType);
            if (existing != null && existing > 0) {
                throw new BizException(409, "套餐 " + planId + " 的 " + periodType + " 周期已存在配置");
            }
            // 校验活动价 ≤ 原价
            Map<String, Object> bp = queryOne(
                    "SELECT price_month_cent, price_quarter_cent, price_year_cent FROM billing_plan WHERE id=? AND deleted=0", planId);
            if (bp == null) throw new BizException(404, "套餐 " + planId + " 不存在");
            long originalCent = "quarter".equals(periodType) ? toLong(bp.get("price_quarter_cent"))
                    : "year".equals(periodType) ? toLong(bp.get("price_year_cent"))
                    : toLong(bp.get("price_month_cent"));
            if (originalCent > 0 && activityPriceCent > originalCent) {
                throw new BizException(400, "活动价不能高于套餐原价（" + formatYuan(originalCent) + "）");
            }
            requireSingleWrite("保存活动套餐配置失败",
                    "INSERT INTO member_promotion_plan(activity_id, plan_id, period_type, activity_price_cent, quota, " +
                            "sold_count, preoccupied_count, sort_order, activity_tag, show_sold_count, show_quota, " +
                            "show_remain, allow_repurchase, max_purchase_per_user, deleted, created_time, updated_time) " +
                            "VALUES(?,?,?,?,?,0,0,?,?,?,?,?,?,?,?,0,NOW(),NOW())",
                    activityId, planId, periodType, activityPriceCent, quota, sortOrder, activityTag,
                    showSold ? 1 : 0, showQuota ? 1 : 0, showRemain ? 1 : 0, allowRepurchase ? 1 : 0, maxPurchase);
        }
    }

    private void replaceActivityPlans(Long activityId, List<Map<String, Object>> plans) {
        // 仅允许在 draft/closed 状态替换（调用方已校验）
        jdbcTemplate.update("UPDATE member_promotion_plan SET deleted=1, updated_time=NOW() WHERE activity_id=? AND deleted=0", activityId);
        saveActivityPlans(activityId, plans);
    }

    private void validateActivityPlans(List<Map<String, Object>> plans) {
        if (plans.size() > MAX_BATCH_PLANS) {
            throw new BizException(400, "单个活动最多配置 " + MAX_BATCH_PLANS + " 个套餐");
        }
        Set<String> seen = new HashSet<>();
        for (Map<String, Object> plan : plans) {
            Long planId = toLong(plan.get("planId"));
            String periodType = text(plan.get("periodType"));
            if (planId == null || planId <= 0) throw new BizException(400, "套餐ID不能为空");
            if (!"month".equals(periodType) && !"quarter".equals(periodType) && !"year".equals(periodType)) {
                throw new BizException(400, "计费周期必须为 month/quarter/year");
            }
            String key = planId + ":" + periodType;
            if (!seen.add(key)) {
                throw new BizException(400, "套餐 " + planId + " 的 " + periodType + " 周期重复配置");
            }
            long activityPriceCent = toLong(plan.get("activityPriceCent"));
            if (activityPriceCent < 0) throw new BizException(400, "活动价不能为负数");
            int quota = toInt(plan.get("quota"));
            if (quota < 0) throw new BizException(400, "名额不能为负数");
        }
    }

    private List<Map<String, Object>> extractPlans(Object plansRaw) {
        if (plansRaw == null) return Collections.emptyList();
        if (plansRaw instanceof List) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> list = (List<Map<String, Object>>) plansRaw;
            return list;
        }
        throw new BizException(400, "套餐配置格式错误");
    }

    private boolean hasOverlappingActivity(Long planId, String periodType, Long excludeActivityId) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM member_promotion_plan ap " +
                        "INNER JOIN member_promotion_activity a ON a.id=ap.activity_id AND a.deleted=0 " +
                        "WHERE ap.plan_id=? AND ap.period_type=? AND ap.deleted=0 AND a.id<>? " +
                        "AND a.status IN ('ongoing','pending') AND a.start_time < NOW() AND a.end_time > NOW()",
                Integer.class, planId, periodType, excludeActivityId);
        return count != null && count > 0;
    }

    private void refreshActivityTotalQuota(Long activityId) {
        Integer totalQuota = jdbcTemplate.queryForObject(
                "SELECT SUM(CASE WHEN quota > 0 THEN quota ELSE 0 END) FROM member_promotion_plan " +
                        "WHERE activity_id=? AND deleted=0", Integer.class, activityId);
        jdbcTemplate.update("UPDATE member_promotion_activity SET total_quota=?, updated_time=NOW() WHERE id=? AND deleted=0",
                totalQuota == null ? 0 : totalQuota, activityId);
    }

    private void writeQuotaLog(Long activityId, Long activityPlanId, String orderNo, String changeType,
                               int delta, int beforeValue, int afterValue,
                               Long operatorId, String operatorName, String remark) {
        try {
            jdbcTemplate.update(
                    "INSERT INTO member_promotion_quota_log(activity_id, activity_plan_id, order_no, change_type, " +
                            "delta, before_value, after_value, operator_id, operator_name, remark, created_time) " +
                            "VALUES(?,?,?,?,?,?,?,?,?,?,NOW())",
                    activityId, activityPlanId, orderNo, changeType, delta, beforeValue, afterValue,
                    operatorId, operatorName, boundedText(remark, 200));
        } catch (Exception e) {
            log.warn("写入名额变更日志失败：activityId={}, planId={}, orderNo={}, type={}", activityId, activityPlanId, orderNo, changeType, e);
        }
    }

    private String mapUnavailableReason(String effectiveStatus) {
        switch (effectiveStatus) {
            case "draft": return "activity_not_started";
            case "pending": return "activity_not_started";
            case "ended": return "activity_ended";
            case "closed": return "activity_closed";
            case "quota_full": return "quota_full";
            default: return "unavailable";
        }
    }

    private String statusText(int s) {
        switch (s) {
            case 1: return "已支付";
            case 2: return "已关闭";
            case 3: return "支付失败";
            case 4: return "已退款";
            default: return "待支付";
        }
    }

    private Integer parseStatusValue(String status) {
        if (!StringUtils.hasText(status)) return null;
        try {
            return Integer.parseInt(status);
        } catch (NumberFormatException e) {
            throw new BizException(400, "非法订单状态");
        }
    }

    private String periodLabel(String periodType) {
        switch (periodType) {
            case "month": return "月";
            case "quarter": return "季";
            case "year": return "年";
            default: return periodType;
        }
    }

    // ==================== 工具方法 ====================

    private Map<String, Object> queryOne(String sql, Object... args) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, args);
        return rows.isEmpty() ? null : rows.get(0);
    }

    private int safeUpdate(String unavailableMessage, String sql, Object... args) {
        try {
            return jdbcTemplate.update(sql, args);
        } catch (Exception e) {
            log.error(unavailableMessage, e);
            throw new BizException(503, unavailableMessage);
        }
    }

    private void requireSingleWrite(String unavailableMessage, String sql, Object... args) {
        int affected = safeUpdate(unavailableMessage, sql, args);
        if (affected != 1) {
            throw new BizException(503, unavailableMessage + "，数据库未确认唯一写入");
        }
    }

    private String required(Map<String, Object> data, String key, String errorMessage) {
        Object v = first(data, key);
        if (v == null || !StringUtils.hasText(String.valueOf(v))) {
            throw new BizException(400, errorMessage);
        }
        return String.valueOf(v).trim();
    }

    private Object first(Map<String, Object> data, String... keys) {
        for (String k : keys) {
            if (data.containsKey(k) && data.get(k) != null) return data.get(k);
        }
        return null;
    }

    private String text(Object v) {
        return v == null ? "" : String.valueOf(v).trim();
    }

    private long toLong(Object v) {
        if (v == null) return 0L;
        if (v instanceof Number) return ((Number) v).longValue();
        try {
            return Long.parseLong(String.valueOf(v).trim());
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    private int toInt(Object v) {
        if (v == null) return 0;
        if (v instanceof Number) return ((Number) v).intValue();
        try {
            return Integer.parseInt(String.valueOf(v).trim());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private int toIntDefault(Object v, int defaultValue) {
        if (v == null) return defaultValue;
        if (v instanceof Number) return ((Number) v).intValue();
        try {
            return Integer.parseInt(String.valueOf(v).trim());
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private boolean toBool(Object v) {
        if (v == null) return false;
        if (v instanceof Boolean) return (Boolean) v;
        String s = String.valueOf(v).trim().toLowerCase();
        return "true".equals(s) || "1".equals(s);
    }

    private boolean toBoolDefault(Object v, boolean defaultValue) {
        if (v == null) return defaultValue;
        if (v instanceof Boolean) return (Boolean) v;
        String s = String.valueOf(v).trim().toLowerCase();
        if ("true".equals(s) || "1".equals(s)) return true;
        if ("false".equals(s) || "0".equals(s)) return false;
        return defaultValue;
    }

    private LocalDateTime toLocalDateTime(Object v) {
        if (v == null) return null;
        if (v instanceof LocalDateTime) return (LocalDateTime) v;
        if (v instanceof java.sql.Timestamp) return ((java.sql.Timestamp) v).toLocalDateTime();
        if (v instanceof java.util.Date) return new java.util.Date(((java.util.Date) v).getTime())
                .toInstant().atZone(java.time.ZoneId.systemDefault()).toLocalDateTime();
        String s = String.valueOf(v);
        try {
            return LocalDateTime.parse(s.replace(" ", "T"));
        } catch (Exception e) {
            try {
                return LocalDateTime.parse(s);
            } catch (Exception e2) {
                throw new BizException(400, "时间格式错误：" + s);
            }
        }
    }

    private LocalDateTime parseDateTime(Object v, String label) {
        if (v == null || !StringUtils.hasText(String.valueOf(v))) {
            throw new BizException(400, label + "不能为空");
        }
        return toLocalDateTime(v);
    }

    private String formatYuan(long cent) {
        return new BigDecimal(cent).divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP).toString();
    }

    private String requireBoundedText(Object v, String label, int maxLength) {
        if (v == null || !StringUtils.hasText(String.valueOf(v))) {
            throw new BizException(400, label + "不能为空");
        }
        String s = String.valueOf(v).trim();
        if (s.length() > maxLength) {
            throw new BizException(400, label + "长度不能超过 " + maxLength + " 字符");
        }
        return s;
    }

    private String optionalBoundedText(Object v, String label, int maxLength) {
        if (v == null || !StringUtils.hasText(String.valueOf(v))) return null;
        String s = String.valueOf(v).trim();
        if (s.length() > maxLength) {
            throw new BizException(400, label + "长度不能超过 " + maxLength + " 字符");
        }
        return s;
    }

    private String optionalTextDefault(Object v, String defaultValue, String label) {
        if (v == null || !StringUtils.hasText(String.valueOf(v))) return defaultValue;
        String s = String.valueOf(v).trim();
        if (s.length() > 30) {
            throw new BizException(400, label + "长度不能超过 30 字符");
        }
        return s;
    }

    private String boundedText(String s, int maxLength) {
        if (s == null) return null;
        return s.length() > maxLength ? s.substring(0, maxLength) : s;
    }

    private String stripHtml(String s) {
        if (s == null) return null;
        return s.replaceAll("<[^>]*>", "").replaceAll("&lt;", "<").replaceAll("&gt;", ">")
                .replaceAll("&amp;", "&").replaceAll("&quot;", "\"").replaceAll("&#39;", "'");
    }

    private String toJson(Object v) {
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(v);
        } catch (Exception e) {
            return String.valueOf(v);
        }
    }
}
