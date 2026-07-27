package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 套餐服务。后台套餐管理与用户前台 VIP 会员中心共用 billing_plan，避免两端维护两份静态数据。
 */
@Service
public class BillingPlanService {
    private final JdbcTemplate jdbcTemplate;

    /**
     * 会员充值活动服务（可选依赖）。
     * 套餐价格变更时校验是否与进行中活动冲突；套餐下架时通知活动模块。
     */
    @Autowired(required = false)
    private MemberPromotionService promotionService;

    public BillingPlanService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public PageResult<Map<String, Object>> page(int current, int size, String keyword, String status) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (plan_name LIKE ? OR plan_code LIKE ?)");
            String kw = "%" + keyword + "%";
            args.add(kw);
            args.add(kw);
        }
        if (StringUtils.hasText(status)) {
            Integer s = parseStatus(status);
            if (s != null) {
                where.append(" AND status=?");
                args.add(s);
            }
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM billing_plan" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        List<Map<String, Object>> records = jdbcTemplate.query(
                baseSelect() + where + " ORDER BY CASE WHEN plan_code LIKE 'normal%' THEN 1 WHEN plan_code LIKE 'svip%' OR plan_code LIKE 'svp%' THEN 3 WHEN plan_code LIKE 'vip%' THEN 2 ELSE 9 END, price_month_cent ASC, id ASC LIMIT ? OFFSET ?",
                (rs, rowNum) -> toMap(rs),
                pageArgs.toArray()
        );
        return new PageResult<>(records, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public List<Map<String, Object>> enabledPlans() {
        return jdbcTemplate.query(
                baseSelect() + " WHERE deleted=0 AND status=1 ORDER BY CASE WHEN plan_code LIKE 'normal%' THEN 1 WHEN plan_code LIKE 'svip%' OR plan_code LIKE 'svp%' THEN 3 WHEN plan_code LIKE 'vip%' THEN 2 ELSE 9 END, price_month_cent ASC, id ASC",
                (rs, rowNum) -> toMap(rs)
        );
    }

    public Map<String, Object> detail(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.query(
                baseSelect() + " WHERE id=? AND deleted=0",
                (rs, rowNum) -> toMap(rs),
                id
        );
        if (rows.isEmpty()) {
            throw new BizException(404, "套餐不存在");
        }
        return rows.get(0);
    }

    @Transactional
    public Map<String, Object> save(Map<String, Object> data) {
        Object id = data.get("id");
        if (id == null || String.valueOf(id).isBlank()) {
            return create(data);
        }
        return update(Long.parseLong(String.valueOf(id)), data);
    }

    @Transactional
    public Map<String, Object> create(Map<String, Object> data) {
        String planName = requiredText(data, "planName", "套餐名称不能为空");
        String planCode = normalizePlanCode(requiredText(data, "planCode", "套餐编码不能为空"));
        Long exists = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM billing_plan WHERE plan_code=? AND deleted=0", Long.class, planCode);
        if (exists != null && exists > 0) {
            throw new BizException(400, "套餐编码已存在");
        }
        long priceMonthCent = parsePeriodMoneyCent(data, "priceMonth", "priceMonthCent", "price_month_cent");
        long priceQuarterCent = parsePeriodMoneyCent(data, "priceQuarter", "priceQuarterCent", "price_quarter_cent");
        long priceYearCent = parsePeriodMoneyCent(data, "priceYear", "priceYearCent", "price_year_cent");
        // price_cent 保留为月度价格，兼容旧逻辑（如排序、向前台暴露单值）
        long priceCent = priceMonthCent;
        jdbcTemplate.update(
                "INSERT INTO billing_plan(plan_name, plan_code, price_cent, duration_days, " +
                        "max_storage_mb, enable_auto_delivery, enable_kami, enable_ai_reply, enable_workflow, " +
                        "features_text, period_type, price_month_cent, price_quarter_cent, price_year_cent, status, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                planName,
                planCode,
                priceCent,
                parseInt(first(data, "durationDays", "duration_days"), 30),
                parseInt(first(data, "maxStorageMb", "max_storage_mb"), 500),
                boolInt(first(data, "enableAutoDelivery", "enable_auto_delivery")),
                boolInt(first(data, "enableKami", "enable_kami")),
                boolInt(first(data, "enableAiReply", "enable_ai_reply")),
                boolInt(first(data, "enableWorkflow", "enable_workflow")),
                textOrNull(first(data, "featuresText", "features_text")),
                "month",
                priceMonthCent,
                priceQuarterCent,
                priceYearCent,
                parseStatus(first(data, "status")) == null ? 1 : parseStatus(first(data, "status"))
        );
        Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        return detail(newId == null ? 0 : newId);
    }

    @Transactional
    public Map<String, Object> update(long id, Map<String, Object> data) {
        Map<String, Object> old = detail(id);
        String planName = textOrDefault(first(data, "planName", "plan_name"), String.valueOf(old.get("planName")));
        String planCode = normalizePlanCode(textOrDefault(first(data, "planCode", "plan_code"), String.valueOf(old.get("planCode"))));
        Long exists = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM billing_plan WHERE plan_code=? AND id<>? AND deleted=0", Long.class, planCode, id);
        if (exists != null && exists > 0) {
            throw new BizException(400, "套餐编码已存在");
        }
        long priceMonthCent = parsePeriodMoneyCentWithDefault(data, "priceMonth", "priceMonthCent", "price_month_cent", ((Number) old.get("priceMonthCent")).longValue());
        long priceQuarterCent = parsePeriodMoneyCentWithDefault(data, "priceQuarter", "priceQuarterCent", "price_quarter_cent", ((Number) old.get("priceQuarterCent")).longValue());
        long priceYearCent = parsePeriodMoneyCentWithDefault(data, "priceYear", "priceYearCent", "price_year_cent", ((Number) old.get("priceYearCent")).longValue());
        // price_cent 跟随月度价格，兼容旧逻辑
        long priceCent = priceMonthCent;
        // 活动联动校验：套餐价格变更后，参与进行中活动的套餐其活动价不得高于新原价
        if (promotionService != null) {
            promotionService.validatePlanPriceChange(id, priceMonthCent, priceQuarterCent, priceYearCent);
        }
        jdbcTemplate.update(
                "UPDATE billing_plan SET plan_name=?, plan_code=?, price_cent=?, duration_days=?, " +
                        "max_storage_mb=?, enable_auto_delivery=?, enable_kami=?, enable_ai_reply=?, enable_workflow=?, " +
                        "features_text=?, period_type=?, price_month_cent=?, price_quarter_cent=?, price_year_cent=?, status=?, updated_time=NOW() " +
                        "WHERE id=? AND deleted=0",
                planName,
                planCode,
                priceCent,
                parseInt(first(data, "durationDays", "duration_days"), ((Number) old.get("durationDays")).intValue()),
                parseInt(first(data, "maxStorageMb", "max_storage_mb"), ((Number) old.get("maxStorageMb")).intValue()),
                data.containsKey("enableAutoDelivery") || data.containsKey("enable_auto_delivery") ? boolInt(first(data, "enableAutoDelivery", "enable_auto_delivery")) : boolInt(old.get("enableAutoDelivery")),
                data.containsKey("enableKami") || data.containsKey("enable_kami") ? boolInt(first(data, "enableKami", "enable_kami")) : boolInt(old.get("enableKami")),
                data.containsKey("enableAiReply") || data.containsKey("enable_ai_reply") ? boolInt(first(data, "enableAiReply", "enable_ai_reply")) : boolInt(old.get("enableAiReply")),
                data.containsKey("enableWorkflow") || data.containsKey("enable_workflow") ? boolInt(first(data, "enableWorkflow", "enable_workflow")) : boolInt(old.get("enableWorkflow")),
                data.containsKey("featuresText") || data.containsKey("features_text") ? textOrNull(first(data, "featuresText", "features_text")) : old.get("featuresText"),
                "month",
                priceMonthCent,
                priceQuarterCent,
                priceYearCent,
                parseStatus(first(data, "status")) == null ? parseStatus(old.get("status")) : parseStatus(first(data, "status")),
                id
        );
        return detail(id);
    }

    public void updateStatus(long id, String status) {
        Integer s = parseStatus(status);
        if (s == null) {
            throw new BizException(400, "非法套餐状态");
        }
        jdbcTemplate.update("UPDATE billing_plan SET status=?, updated_time=NOW() WHERE id=? AND deleted=0", s, id);
    }

    public int batchUpdateStatus(List<Long> ids, String status) {
        if (ids == null || ids.isEmpty()) return 0;
        Integer s = parseStatus(status);
        if (s == null) throw new BizException(400, "非法套餐状态");
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>();
        args.add(s);
        args.addAll(ids);
        return jdbcTemplate.update("UPDATE billing_plan SET status=?, updated_time=NOW() WHERE deleted=0 AND id IN (" + placeholders + ")", args.toArray());
    }

    public void delete(long id) {
        // 活动联动：套餐软删除时通知活动模块（仅记录日志，活动套餐前台通过 INNER JOIN billing_plan status=1 自动停止展示）
        if (promotionService != null) {
            promotionService.onPlanOffline(id);
        }
        jdbcTemplate.update("UPDATE billing_plan SET deleted=1, status=0, updated_time=NOW() WHERE id=? AND deleted=0", id);
    }

    public int batchDelete(List<Long> ids) {
        if (ids == null || ids.isEmpty()) return 0;
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        return jdbcTemplate.update("UPDATE billing_plan SET deleted=1, updated_time=NOW() WHERE deleted=0 AND id IN (" + placeholders + ")", ids.toArray());
    }

    public Map<String, Object> stats() {
        Map<String, Object> res = new LinkedHashMap<>();
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM billing_plan WHERE deleted=0", Long.class);
        Long normal = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM billing_plan WHERE deleted=0 AND status=1", Long.class);
        Long danger = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM billing_plan WHERE deleted=0 AND status=0", Long.class);
        Long today = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM billing_plan WHERE deleted=0 AND DATE(created_time)=CURRENT_DATE()", Long.class);
        res.put("total", total == null ? 0 : total);
        res.put("normal", normal == null ? 0 : normal);
        res.put("warning", 0);
        res.put("danger", danger == null ? 0 : danger);
        res.put("today", today == null ? 0 : today);
        return res;
    }

    private String baseSelect() {
        return "SELECT id, plan_name, plan_code, price_cent, duration_days, max_xianyu_accounts, max_goods_count, " +
                "max_ai_reply_per_day, max_workflow_per_day, max_storage_mb, enable_auto_delivery, enable_kami, enable_ai_reply, enable_workflow, " +
                "features_text, period_type, price_month_cent, price_quarter_cent, price_year_cent, status, created_time, updated_time " +
                "FROM billing_plan";
    }

    private Map<String, Object> toMap(ResultSet rs) throws SQLException {
        Map<String, Object> row = new LinkedHashMap<>();
        long priceCent = rs.getLong("price_cent");
        long priceMonthCent = rs.getLong("price_month_cent");
        long priceQuarterCent = rs.getLong("price_quarter_cent");
        long priceYearCent = rs.getLong("price_year_cent");
        String planCode = normalizePlanCode(rs.getString("plan_code"));
        String planName = rs.getString("plan_name");
        int durationDays = rs.getInt("duration_days");
        int status = rs.getInt("status");
        int storageMb = rs.getInt("max_storage_mb");

        row.put("id", rs.getLong("id"));
        row.put("planName", planName);
        row.put("planCode", planCode);
        row.put("level", normalizeLevel(planCode));
        row.put("priceCent", priceCent);
        row.put("price", formatPrice(priceCent));
        row.put("priceYuan", BigDecimal.valueOf(priceCent).divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP));
        // 三周期价格（前台按 selectedPeriod 取对应值展示）
        row.put("priceMonthCent", priceMonthCent);
        row.put("priceQuarterCent", priceQuarterCent);
        row.put("priceYearCent", priceYearCent);
        row.put("priceMonth", formatPrice(priceMonthCent));
        row.put("priceQuarter", formatPrice(priceQuarterCent));
        row.put("priceYear", formatPrice(priceYearCent));
        row.put("priceMonthYuan", BigDecimal.valueOf(priceMonthCent).divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP));
        row.put("priceQuarterYuan", BigDecimal.valueOf(priceQuarterCent).divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP));
        row.put("priceYearYuan", BigDecimal.valueOf(priceYearCent).divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP));
        row.put("durationDays", durationDays);
        row.put("durationText", durationDays <= 0 ? "永久" : durationDays + "天");
        row.put("maxStorageMb", storageMb);
        row.put("enableAutoDelivery", rs.getInt("enable_auto_delivery") == 1);
        row.put("enableKami", rs.getInt("enable_kami") == 1);
        row.put("enableAiReply", rs.getInt("enable_ai_reply") == 1);
        row.put("enableWorkflow", rs.getInt("enable_workflow") == 1 ? "启用" : "禁用");
        row.put("enableWorkflowValue", rs.getInt("enable_workflow") == 1);
        String featuresText = rs.getString("features_text");
        row.put("featuresText", featuresText);
        row.put("periodType", normalizePeriodType(rs.getString("period_type")));
        row.put("status", status == 1 ? "正常" : "禁用");
        row.put("statusValue", status);
        // features 严格按后台 featuresText 按行拆分；为空时返回空数组（前台展示空列表）
        row.put("features", buildFeatures(featuresText));
        row.put("createdTime", rs.getTimestamp("created_time"));
        row.put("updatedTime", rs.getTimestamp("updated_time"));
        return row;
    }

    private List<String> buildFeatures(String featuresText) {
        // 严格按后台自定义文本按行展示（每行一条权益）；为空时返回空数组
        if (featuresText == null || featuresText.isBlank()) {
            return Collections.emptyList();
        }
        return Arrays.stream(featuresText.split("\\r?\\n"))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toList());
    }

    private String formatPrice(long priceCent) {
        if (priceCent <= 0) return "免费";
        BigDecimal yuan = BigDecimal.valueOf(priceCent).divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP).stripTrailingZeros();
        return "¥" + yuan.toPlainString();
    }

    private Object first(Map<String, Object> data, String... keys) {
        for (String key : keys) {
            if (data.containsKey(key)) return data.get(key);
        }
        return null;
    }

    private String requiredText(Map<String, Object> data, String key, String message) {
        Object v = data.get(key);
        if (v == null || String.valueOf(v).isBlank()) throw new BizException(400, message);
        return String.valueOf(v).trim();
    }

    private String textOrDefault(Object value, String def) {
        return value == null || String.valueOf(value).isBlank() ? def : String.valueOf(value).trim();
    }

    private String normalizePlanCode(String code) {
        if (code == null) return "normal";
        String c = code.trim().toLowerCase(Locale.ROOT);
        if ("svip".equals(c)) return "svp";
        if ("普通用户".equals(c) || "free".equals(c)) return "normal";
        return c;
    }

    private String normalizeLevel(String code) {
        if (code == null) return "normal";
        String c = code.trim().toLowerCase(Locale.ROOT);
        if (c.startsWith("svp") || c.startsWith("svip")) return "svp";
        if (c.startsWith("vip")) return "vip";
        return "normal";
    }

    private String normalizePeriodType(Object value) {
        if (value == null) return "month";
        String s = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        if ("quarter".equals(s) || "season".equals(s)) return "quarter";
        if ("year".equals(s) || "annual".equals(s)) return "year";
        return "month";
    }

    private String textOrNull(Object value) {
        if (value == null) return null;
        String s = String.valueOf(value).trim();
        return s.isEmpty() ? null : s;
    }

    private Integer parseStatus(Object value) {
        if (value == null) return null;
        if (value instanceof Number) return ((Number) value).intValue() == 1 ? 1 : 0;
        String s = String.valueOf(value);
        if ("正常".equals(s) || "启用".equals(s) || "1".equals(s) || "true".equalsIgnoreCase(s)) return 1;
        if ("禁用".equals(s) || "下架".equals(s) || "0".equals(s) || "false".equalsIgnoreCase(s)) return 0;
        return null;
    }

    private int parseInt(Object value, int def) {
        if (value == null || String.valueOf(value).isBlank()) return def;
        if (value instanceof Number) return ((Number) value).intValue();
        try { return Integer.parseInt(String.valueOf(value).replaceAll("[^0-9-]", "")); } catch (Exception e) { return def; }
    }

    /**
     * 解析三周期价格之一（元 → 分）。0 表示未配置，允许传 0 / "0" / "免费"。
     * 支持的 key 顺序：显示元值键（如 priceMonth）、分值键（如 priceMonthCent）、蛇形键（如 price_month_cent）。
     */
    private long parsePeriodMoneyCent(Map<String, Object> data, String... keys) {
        return parsePeriodMoneyCentWithDefault(data, keys[0], keys[1], keys.length > 2 ? keys[2] : keys[1], 0L);
    }

    private long parsePeriodMoneyCentWithDefault(Map<String, Object> data, String displayKey, String centKey, String snakeKey, long def) {
        // 1. 优先读分值（如 priceMonthCent）
        Object centValue = data.containsKey(centKey) ? data.get(centKey) : data.get(snakeKey);
        if (centValue != null && !String.valueOf(centValue).isBlank()) {
            if (centValue instanceof Number) return ((Number) centValue).longValue();
            try { return Long.parseLong(String.valueOf(centValue).replaceAll("[^0-9-]", "")); } catch (Exception ignored) {}
        }
        // 2. 再读元值（如 priceMonth）
        Object yuanValue = data.get(displayKey);
        if (yuanValue == null || String.valueOf(yuanValue).isBlank() || "免费".equals(String.valueOf(yuanValue))) return def;
        if (yuanValue instanceof Number) {
            // 用 BigDecimal 处理，避免 longValue() 先截断小数再乘 100（如 9.99 元 → 9 元的 bug）
            return new BigDecimal(((Number) yuanValue).toString()).multiply(BigDecimal.valueOf(100)).longValue();
        }
        try {
            String clean = String.valueOf(yuanValue).replace("¥", "").replace("元", "").trim();
            return new BigDecimal(clean).multiply(BigDecimal.valueOf(100)).longValue();
        } catch (Exception e) {
            return def;
        }
    }

    private int boolInt(Object value) {
        if (value == null) return 0;
        if (value instanceof Boolean) return (Boolean) value ? 1 : 0;
        if (value instanceof Number) return ((Number) value).intValue() == 1 ? 1 : 0;
        String s = String.valueOf(value);
        return "启用".equals(s) || "正常".equals(s) || "是".equals(s) || "1".equals(s) || "true".equalsIgnoreCase(s) ? 1 : 0;
    }
}
