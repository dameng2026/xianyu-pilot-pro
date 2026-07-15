package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
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
                baseSelect() + where + " ORDER BY CASE plan_code WHEN 'normal' THEN 1 WHEN 'vip' THEN 2 WHEN 'svp' THEN 3 WHEN 'svip' THEN 3 ELSE 9 END, price_cent ASC, id ASC LIMIT ? OFFSET ?",
                (rs, rowNum) -> toMap(rs),
                pageArgs.toArray()
        );
        return new PageResult<>(records, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public List<Map<String, Object>> enabledPlans() {
        return jdbcTemplate.query(
                baseSelect() + " WHERE deleted=0 AND status=1 ORDER BY CASE plan_code WHEN 'normal' THEN 1 WHEN 'vip' THEN 2 WHEN 'svp' THEN 3 WHEN 'svip' THEN 3 ELSE 9 END, price_cent ASC, id ASC",
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
        jdbcTemplate.update(
                "INSERT INTO billing_plan(plan_name, plan_code, price_cent, duration_days, max_xianyu_accounts, max_goods_count, " +
                        "max_ai_reply_per_day, max_workflow_per_day, max_storage_mb, enable_auto_delivery, enable_kami, enable_ai_reply, enable_workflow, status, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),0)",
                planName,
                planCode,
                parseMoneyCent(data),
                parseInt(first(data, "durationDays", "duration_days"), 30),
                parseInt(first(data, "maxAccounts", "maxXianyuAccounts", "max_xianyu_accounts"), 1),
                parseInt(first(data, "maxGoodsCount", "max_goods_count"), 100),
                parseInt(first(data, "aiQuota", "maxAiReplyPerDay", "max_ai_reply_per_day"), 100),
                parseInt(first(data, "maxWorkflowPerDay", "max_workflow_per_day"), 0),
                parseInt(first(data, "maxStorageMb", "max_storage_mb"), 500),
                boolInt(first(data, "enableAutoDelivery", "enable_auto_delivery")),
                boolInt(first(data, "enableKami", "enable_kami")),
                boolInt(first(data, "enableAiReply", "enable_ai_reply")),
                boolInt(first(data, "enableWorkflow", "enable_workflow")),
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
        jdbcTemplate.update(
                "UPDATE billing_plan SET plan_name=?, plan_code=?, price_cent=?, duration_days=?, max_xianyu_accounts=?, max_goods_count=?, " +
                        "max_ai_reply_per_day=?, max_workflow_per_day=?, max_storage_mb=?, enable_auto_delivery=?, enable_kami=?, enable_ai_reply=?, enable_workflow=?, status=?, updated_time=NOW() " +
                        "WHERE id=? AND deleted=0",
                planName,
                planCode,
                parseMoneyCentWithDefault(data, ((Number) old.get("priceCent")).longValue()),
                parseInt(first(data, "durationDays", "duration_days"), ((Number) old.get("durationDays")).intValue()),
                parseInt(first(data, "maxAccounts", "maxXianyuAccounts", "max_xianyu_accounts"), ((Number) old.get("maxAccounts")).intValue()),
                parseInt(first(data, "maxGoodsCount", "max_goods_count"), ((Number) old.get("maxGoodsCount")).intValue()),
                parseInt(first(data, "aiQuota", "maxAiReplyPerDay", "max_ai_reply_per_day"), ((Number) old.get("aiQuota")).intValue()),
                parseInt(first(data, "maxWorkflowPerDay", "max_workflow_per_day"), ((Number) old.get("maxWorkflowPerDay")).intValue()),
                parseInt(first(data, "maxStorageMb", "max_storage_mb"), ((Number) old.get("maxStorageMb")).intValue()),
                data.containsKey("enableAutoDelivery") || data.containsKey("enable_auto_delivery") ? boolInt(first(data, "enableAutoDelivery", "enable_auto_delivery")) : boolInt(old.get("enableAutoDelivery")),
                data.containsKey("enableKami") || data.containsKey("enable_kami") ? boolInt(first(data, "enableKami", "enable_kami")) : boolInt(old.get("enableKami")),
                data.containsKey("enableAiReply") || data.containsKey("enable_ai_reply") ? boolInt(first(data, "enableAiReply", "enable_ai_reply")) : boolInt(old.get("enableAiReply")),
                data.containsKey("enableWorkflow") || data.containsKey("enable_workflow") ? boolInt(first(data, "enableWorkflow", "enable_workflow")) : boolInt(old.get("enableWorkflow")),
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
        jdbcTemplate.update("UPDATE billing_plan SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
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
                "max_ai_reply_per_day, max_workflow_per_day, max_storage_mb, enable_auto_delivery, enable_kami, enable_ai_reply, enable_workflow, status, created_time, updated_time " +
                "FROM billing_plan";
    }

    private Map<String, Object> toMap(ResultSet rs) throws SQLException {
        Map<String, Object> row = new LinkedHashMap<>();
        long priceCent = rs.getLong("price_cent");
        String planCode = normalizePlanCode(rs.getString("plan_code"));
        String planName = rs.getString("plan_name");
        int durationDays = rs.getInt("duration_days");
        int status = rs.getInt("status");
        int maxAccounts = rs.getInt("max_xianyu_accounts");
        int maxGoods = rs.getInt("max_goods_count");
        int aiQuota = rs.getInt("max_ai_reply_per_day");
        int workflowQuota = rs.getInt("max_workflow_per_day");
        int storageMb = rs.getInt("max_storage_mb");

        row.put("id", rs.getLong("id"));
        row.put("planName", planName);
        row.put("planCode", planCode);
        row.put("level", normalizeLevel(planCode));
        row.put("priceCent", priceCent);
        row.put("price", formatPrice(priceCent));
        row.put("priceYuan", BigDecimal.valueOf(priceCent).divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP));
        row.put("durationDays", durationDays);
        row.put("durationText", durationDays <= 0 ? "永久" : durationDays + "天");
        row.put("maxAccounts", maxAccounts);
        row.put("maxXianyuAccounts", maxAccounts);
        row.put("maxGoodsCount", maxGoods);
        row.put("aiQuota", aiQuota);
        row.put("maxAiReplyPerDay", aiQuota);
        row.put("maxWorkflowPerDay", workflowQuota);
        row.put("maxStorageMb", storageMb);
        row.put("enableAutoDelivery", rs.getInt("enable_auto_delivery") == 1);
        row.put("enableKami", rs.getInt("enable_kami") == 1);
        row.put("enableAiReply", rs.getInt("enable_ai_reply") == 1);
        row.put("enableWorkflow", rs.getInt("enable_workflow") == 1 ? "启用" : "禁用");
        row.put("enableWorkflowValue", rs.getInt("enable_workflow") == 1);
        row.put("status", status == 1 ? "正常" : "禁用");
        row.put("statusValue", status);
        row.put("features", buildFeatures(maxAccounts, maxGoods, aiQuota, workflowQuota, storageMb,
                rs.getInt("enable_auto_delivery") == 1, rs.getInt("enable_kami") == 1,
                rs.getInt("enable_ai_reply") == 1, rs.getInt("enable_workflow") == 1));
        row.put("createdTime", rs.getTimestamp("created_time"));
        row.put("updatedTime", rs.getTimestamp("updated_time"));
        return row;
    }

    private List<String> buildFeatures(int maxAccounts, int maxGoods, int aiQuota, int workflowQuota, int storageMb,
                                       boolean autoDelivery, boolean kami, boolean aiReply, boolean workflow) {
        List<String> features = new ArrayList<>();
        features.add("可绑定 " + maxAccounts + " 个闲鱼账号");
        features.add("最多管理 " + maxGoods + " 个商品");
        features.add("每日 AI 回复额度 " + aiQuota + " 次");
        features.add("存储空间 " + storageMb + "MB");
        if (autoDelivery) features.add("支持自动发货");
        if (kami) features.add("支持卡密仓库");
        if (aiReply) features.add("支持智能自动回复");
        if (workflow) features.add("支持自动化工作流，每日 " + workflowQuota + " 次");
        return features;
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
        String c = normalizePlanCode(code);
        if ("svp".equals(c)) return "svp";
        if ("vip".equals(c)) return "vip";
        return "normal";
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

    private long parseMoneyCent(Map<String, Object> data) {
        return parseMoneyCentWithDefault(data, 0L);
    }

    private long parseMoneyCentWithDefault(Map<String, Object> data, long def) {
        Object value = first(data, "priceCent", "price_cent");
        if (value != null && !String.valueOf(value).isBlank()) {
            if (value instanceof Number) return ((Number) value).longValue();
            try { return Long.parseLong(String.valueOf(value).replaceAll("[^0-9-]", "")); } catch (Exception ignored) {}
        }
        Object price = first(data, "price", "priceYuan");
        if (price == null || String.valueOf(price).isBlank() || "免费".equals(String.valueOf(price))) return def;
        try {
            String clean = String.valueOf(price).replace("¥", "").replace("元", "").trim();
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
