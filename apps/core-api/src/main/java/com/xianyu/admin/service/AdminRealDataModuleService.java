package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.CsvCellEncoder;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 后台监管模块真实数据查询服务。
 *
 * 这些页面必须展示业务表全量数据，不能再依赖 admin_module_record 中的演示 JSON。
 * 本服务只按管理员视角读取全库数据，不使用 TenantContext 过滤。
 */
@Service
public class AdminRealDataModuleService {
    private static final Set<String> SUPPORTED_MODULES = Set.of(
            "goods", "orders", "messages", "delivery", "auto-reply", "kami", "hot-goods"
    );

    private final JdbcTemplate jdbcTemplate;
    private final ModuleCatalog catalog;

    public AdminRealDataModuleService(JdbcTemplate jdbcTemplate, ModuleCatalog catalog) {
        this.jdbcTemplate = jdbcTemplate;
        this.catalog = catalog;
    }

    public boolean supports(String moduleKey) {
        return SUPPORTED_MODULES.contains(moduleKey);
    }

    public PageResult<Map<String, Object>> page(String moduleKey, int current, int size, String keyword, String status) {
        return page(moduleKey, current, size, keyword, status, null, null);
    }

    public PageResult<Map<String, Object>> page(String moduleKey, int current, int size, String keyword, String status, String sortField, String sortOrder) {
        QueryDef def = queryDef(moduleKey);
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;

        List<Object> args = new ArrayList<>();
        String where = buildOuterWhere(def, keyword, status, args);
        String countSql = "SELECT COUNT(*) FROM (" + def.sql() + ") t" + where;
        Long total = queryLong(countSql, args.toArray());

        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        String orderClause = resolveOrderClause(def, sortField, sortOrder);
        String pageSql = "SELECT * FROM (" + def.sql() + ") t" + where + " ORDER BY " + orderClause + " LIMIT ? OFFSET ?";
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(pageSql, pageArgs.toArray());
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    /**
     * 解析排序子句。当前仅支持按订单数（orderCount）排序，其余字段回退到默认创建时间倒序。
     */
    private String resolveOrderClause(QueryDef def, String sortField, String sortOrder) {
        boolean desc = !"asc".equalsIgnoreCase(sortOrder);
        if (StringUtils.hasText(sortField)) {
            if ("orderCount".equals(sortField)) {
                return "t.orderCount " + (desc ? "DESC" : "ASC") + ", t.id DESC";
            }
            // 其他字段按白名单校验后支持排序，防止 SQL 注入
            if (def.sortableFields().contains(sortField)) {
                return "t." + sortField + " " + (desc ? "DESC" : "ASC") + ", t.id DESC";
            }
        }
        return "t.createdTime DESC, t.id DESC";
    }

    public Map<String, Object> detail(String moduleKey, long id) {
        QueryDef def = queryDef(moduleKey);
        String sql = "SELECT * FROM (" + def.sql() + ") t WHERE t.id=? ORDER BY t.createdTime DESC LIMIT 1";
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, id);
        if (rows.isEmpty()) {
            throw new BizException(404, "记录不存在");
        }
        return rows.get(0);
    }

    public Map<String, Object> stats(String moduleKey) {
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("total", page(moduleKey, 1, 1, null, null).getTotal());
        // 统计分类计数时只过滤 status 字段，避免 autoDelivery/autoReply 等非状态字段
        // 误命中关键词（如 autoDelivery='关闭' 误命中"异常"关键词"关闭"）
        res.put("normal", countByStatusOnly(moduleKey, "正常"));
        res.put("warning", countByStatusOnly(moduleKey, "待处理"));
        res.put("danger", countByStatusOnly(moduleKey, "异常"));
        res.put("today", countToday(moduleKey));
        return res;
    }

    /**
     * 仅基于 status 字段统计分类计数，不使用 statusFields 的多字段 OR 匹配。
     * 避免非状态字段（如 autoDelivery='关闭'）误命中"异常"关键词。
     */
    private long countByStatusOnly(String moduleKey, String status) {
        QueryDef def = queryDef(moduleKey);
        List<Object> args = new ArrayList<>();
        StringBuilder sql = new StringBuilder("SELECT COUNT(*) AS cnt FROM (");
        sql.append(def.sql());
        sql.append(") t WHERE 1=1");
        if (StringUtils.hasText(status)) {
            List<String> words = statusWords(status);
            sql.append(" AND (");
            for (int i = 0; i < words.size(); i++) {
                if (i > 0) sql.append(" OR ");
                sql.append("CAST(t.status AS CHAR) LIKE ?");
                args.add("%" + words.get(i) + "%");
            }
            sql.append(")");
        }
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql.toString(), args.toArray());
        if (rows.isEmpty()) return 0L;
        Object cnt = rows.get(0).get("cnt");
        if (cnt instanceof Number) return ((Number) cnt).longValue();
        return 0L;
    }

    public String exportCsv(String moduleKey, String keyword, String status) {
        QueryDef def = queryDef(moduleKey);
        List<Object> args = new ArrayList<>();
        String where = buildOuterWhere(def, keyword, status, args);
        String sql = "SELECT * FROM (" + def.sql() + ") t" + where + " ORDER BY t.createdTime DESC, t.id DESC LIMIT 5000";
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, args.toArray());
        List<Map<String, Object>> columns = catalog.get(moduleKey).columns();

        StringBuilder sb = new StringBuilder("\uFEFF");
        sb.append(columns.stream().map(c -> csv(String.valueOf(c.get("label")))).collect(Collectors.joining(","))).append("\n");
        for (Map<String, Object> row : rows) {
            sb.append(columns.stream()
                    .map(c -> csv(String.valueOf(row.getOrDefault(String.valueOf(c.get("prop")), ""))))
                    .collect(Collectors.joining(","))).append("\n");
        }
        return sb.toString();
    }

    public Map<String, Object> save(String moduleKey, Map<String, Object> ignored) {
        throw new BizException(400, "监管模块展示真实业务数据，不支持在此新增或编辑");
    }

    public void updateStatus(String moduleKey, long id, String status) {
        String normalized = normalizeRequestedStatus(status);
        switch (moduleKey) {
            case "goods" -> updateGoodsStatus(id, normalized);
            case "delivery" -> updateDeliveryStatus(id, normalized);
            case "auto-reply" -> updateAutoReplyStatus(id, normalized);
            case "kami" -> updateKamiStatus(id, normalized);
            case "orders", "messages" -> throw new BizException(400, "该监管模块为业务记录，只读展示，不允许直接改状态");
            default -> throw new BizException(404, "不支持的监管模块");
        }
    }

    public int batchUpdateStatus(String moduleKey, List<Long> ids, String status) {
        if (ids == null || ids.isEmpty()) return 0;
        int count = 0;
        for (Long id : ids) {
            if (id == null) continue;
            updateStatus(moduleKey, id, status);
            count++;
        }
        return count;
    }

    public void delete(String moduleKey, long id) {
        String table = primaryTable(moduleKey);
        if (!tableExists(table)) {
            throw new BizException(404, "业务表不存在");
        }
        if (!columnExists(table, "deleted")) {
            throw new BizException(400, "该真实业务表无软删除字段，已拒绝物理删除");
        }
        jdbcTemplate.update("UPDATE " + table + " SET deleted=1" + updateTimeClause(table) + " WHERE id=?", id);
    }

    public int batchDelete(String moduleKey, List<Long> ids) {
        if (ids == null || ids.isEmpty()) return 0;
        String table = primaryTable(moduleKey);
        if (!tableExists(table)) return 0;
        if (!columnExists(table, "deleted")) {
            throw new BizException(400, "该真实业务表无软删除字段，已拒绝物理删除");
        }
        String placeholders = ids.stream().map(i -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>();
        args.addAll(ids);
        return jdbcTemplate.update("UPDATE " + table + " SET deleted=1" + updateTimeClause(table) + " WHERE id IN (" + placeholders + ")", args.toArray());
    }

    private long countToday(String moduleKey) {
        QueryDef def = queryDef(moduleKey);
        Long c = queryLong("SELECT COUNT(*) FROM (" + def.sql() + ") t WHERE DATE(t.createdTime)=CURRENT_DATE()", new Object[]{});
        return c == null ? 0 : c;
    }

    private QueryDef queryDef(String moduleKey) {
        return switch (moduleKey) {
            case "goods" -> goodsQuery();
            case "orders" -> ordersQuery();
            case "messages" -> messagesQuery();
            case "delivery" -> deliveryQuery();
            case "auto-reply" -> autoReplyQuery();
            case "kami" -> kamiQuery();
            case "hot-goods" -> hotGoodsQuery();
            default -> emptyQuery();
        };
    }

    private QueryDef goodsQuery() {
        List<String> parts = new ArrayList<>();
        if (tableExists("xianyu_goods")) {
            String title = col("xianyu_goods", "g", List.of("title", "goods_title"), "''");
            String price = money(priceAmountExpr("xianyu_goods", "g"));
            String accountName = accountNameExpr("a");
            String username = usernameExpr("u");
            String statusRaw = col("xianyu_goods", "g", List.of("goods_status", "status"), "NULL");
            String status = statusLabel(statusRaw);
            String deliveryType = col("xianyu_goods", "g", List.of("delivery_type", "delivery_mode"), "NULL");
            String autoDelivery = "CASE WHEN " + deliveryType + " IS NULL THEN '-' WHEN " + deliveryType + " LIKE 'auto%' OR " + deliveryType + " IN ('kami','auto_kami','1') THEN '开启' ELSE '关闭' END";
            String created = col("xianyu_goods", "g", List.of("created_time", "published_time"), "NULL");
            // 商品封面图：优先 cover_pic，其次 image_url
            String coverPic = col("xianyu_goods", "g", List.of("cover_pic", "image_url"), "''");
            // 闲鱼商品 itemId（external_goods_id），用于拼闲鱼商品链接
            String itemId = col("xianyu_goods", "g", List.of("external_goods_id", "goods_id"), "''");
            // 商品闲鱼连接：itemId 非空时拼接详情页地址
            String goofishLink = "CASE WHEN " + itemId + " IS NOT NULL AND " + itemId + " <> '' " +
                    "THEN CONCAT('https://www.goofish.com/item?itemId=', " + itemId + ") ELSE '' END";
            // 商品总订单：统计 xianyu_trade_order 中该 itemId 的有效订单数（含全部订单状态，与订单监管口径一致）
            String orderCount = (tableExists("xianyu_trade_order") && columnExists("xianyu_trade_order", "item_id"))
                    ? "COALESCE((SELECT COUNT(*) FROM xianyu_trade_order o WHERE o.item_id=" + itemId + " AND " + notDeleted("xianyu_trade_order", "o") + "),0)"
                    : "0";
            parts.add("SELECT g.id AS id, 'xianyu_goods' AS sourceTable, " + title + " AS goodsTitle, " + coverPic + " AS coverPic, " + username + " AS username, " + accountName + " AS accountName, " + orderCount + " AS orderCount, " + price + " AS price, " + goofishLink + " AS goofishLink, " + autoDelivery + " AS autoDelivery, '-' AS autoReply, " + status + " AS status, " + created + " AS createdTime " +
                    "FROM xianyu_goods g " + accountJoin("xianyu_goods", "g") + userJoin("xianyu_goods", "g", "a") + " WHERE " + notDeleted("xianyu_goods", "g"));
        }
        return new QueryDef(unionOrEmpty(parts), List.of("goodsTitle", "username", "accountName", "price", "status"), List.of("status", "autoDelivery", "autoReply"), List.of("orderCount"));
    }

    private QueryDef ordersQuery() {
        List<String> parts = new ArrayList<>();
        if (tableExists("xianyu_trade_order")) {
            String orderNo = col("xianyu_trade_order", "o", List.of("order_no", "external_order_id", "order_id"), "''");
            String buyer = col("xianyu_trade_order", "o", List.of("buyer_nickname", "buyer_name", "receiver_name", "buyer_id"), "''");
            String amount = money(orderAmountExpr("xianyu_trade_order", "o"));
            String username = usernameExpr("u");
            String payStatus = payStatusLabel(col("xianyu_trade_order", "o", List.of("pay_status"), "NULL"));
            String orderStatus = orderStatusLabel(col("xianyu_trade_order", "o", List.of("order_status"), "NULL"));
            String deliveryStatus = deliveryStatusLabel(col("xianyu_trade_order", "o", List.of("delivery_status", "sync_status"), "NULL"));
            String created = col("xianyu_trade_order", "o", List.of("create_time", "created_time"), "NULL");
            parts.add("SELECT o.id AS id, 'xianyu_trade_order' AS sourceTable, " + orderNo + " AS orderNo, " + buyer + " AS buyerName, " + username + " AS username, " + amount + " AS amount, " + payStatus + " AS payStatus, " + orderStatus + " AS orderStatus, " + deliveryStatus + " AS deliveryStatus, " + created + " AS createdTime, " + orderStatus + " AS status " +
                    "FROM xianyu_trade_order o " + accountJoin("xianyu_trade_order", "o") + userJoin("xianyu_trade_order", "o", "a") + " WHERE " + notDeleted("xianyu_trade_order", "o"));
        }
        return new QueryDef(unionOrEmpty(parts), List.of("orderNo", "buyerName", "username", "amount", "payStatus", "orderStatus", "deliveryStatus"), List.of("status", "payStatus", "orderStatus", "deliveryStatus"));
    }

    private QueryDef messagesQuery() {
        List<String> parts = new ArrayList<>();
        if (tableExists("xianyu_conversation")) {
            String buyer = col("xianyu_conversation", "c", List.of("buyer_nickname", "peer_nickname", "buyer_uid", "peer_id"), "''");
            String accountName = accountNameExpr("a");
            String summary = col("xianyu_conversation", "c", List.of("last_message_content", "last_message"), "''");
            String replyType = "CASE WHEN " + col("xianyu_conversation", "c", List.of("is_auto_reply"), "0") + " IN (1,'1') OR " + col("xianyu_conversation", "c", List.of("auto_reply_count"), "0") + " > 0 THEN '自动回复' ELSE '人工/未回复' END";
            String created = col("xianyu_conversation", "c", List.of("last_message_time", "created_time"), "NULL");
            parts.add("SELECT c.id AS id, 'xianyu_conversation' AS sourceTable, " + buyer + " AS buyerName, " + accountName + " AS accountName, '会话' AS messageType, " + replyType + " AS replyType, " + summary + " AS summary, " + created + " AS createdTime, " + statusLabel(col("xianyu_conversation", "c", List.of("conversation_status", "status"), "'normal'")) + " AS status " +
                    "FROM xianyu_conversation c " + accountJoin("xianyu_conversation", "c") + " WHERE " + notDeleted("xianyu_conversation", "c"));
        }
        if (tableExists("xianyu_message")) {
            String buyer = col("xianyu_message", "m", List.of("sender_name", "from_user_id"), "''");
            String accountName = accountNameExpr("a");
            String type = col("xianyu_message", "m", List.of("msg_type", "message_type"), "'text'");
            String replyType = "CASE WHEN " + col("xianyu_message", "m", List.of("is_auto_reply"), "0") + " IN (1,'1') THEN '自动回复' ELSE '普通消息' END";
            String summary = col("xianyu_message", "m", List.of("content"), "''");
            String created = col("xianyu_message", "m", List.of("msg_time", "created_time"), "NULL");
            parts.add("SELECT m.id AS id, 'xianyu_message' AS sourceTable, " + buyer + " AS buyerName, " + accountName + " AS accountName, " + type + " AS messageType, " + replyType + " AS replyType, " + summary + " AS summary, " + created + " AS createdTime, " + statusLabel(col("xianyu_message", "m", List.of("sync_status"), "'normal'")) + " AS status " +
                    "FROM xianyu_message m " + accountJoin("xianyu_message", "m") + " WHERE " + notDeleted("xianyu_message", "m"));
        }
        return new QueryDef(unionOrEmpty(parts), List.of("buyerName", "accountName", "messageType", "replyType", "summary"), List.of("status", "messageType", "replyType"));
    }

    private QueryDef deliveryQuery() {
        List<String> parts = new ArrayList<>();
        if (tableExists("delivery_record")) {
            String accountName = accountNameExpr("a");
            String deliveryType = col("delivery_record", "dr", List.of("delivery_mode", "delivery_type"), "'kami'");
            String statusRaw = col("delivery_record", "dr", List.of("delivery_status", "status"), "NULL");
            String status = deliveryStatusLabel(statusRaw);
            String retry = col("delivery_record", "dr", List.of("retry_count"), "0");
            String fail = col("delivery_record", "dr", List.of("error_message", "fail_reason"), "''");
            String created = col("delivery_record", "dr", List.of("delivery_time", "created_time"), "NULL");
            parts.add("SELECT dr.id AS id, 'delivery_record' AS sourceTable, " + accountName + " AS accountName, " + deliveryType + " AS deliveryType, " + status + " AS orderStatus, " + retry + " AS retryCount, " + fail + " AS failReason, " + created + " AS createdTime, " + status + " AS status " +
                    "FROM delivery_record dr " + accountJoin("delivery_record", "dr") + " WHERE " + notDeleted("delivery_record", "dr"));
        }
        if (tableExists("delivery_rule")) {
            String accountName = accountNameExpr("a");
            String deliveryType = col("delivery_rule", "r", List.of("delivery_mode", "delivery_type"), "'kami'");
            String status = enabledStatusLabel(col("delivery_rule", "r", List.of("status", "enabled"), "1"));
            String created = col("delivery_rule", "r", List.of("created_time"), "NULL");
            parts.add("SELECT r.id AS id, 'delivery_rule' AS sourceTable, " + accountName + " AS accountName, " + deliveryType + " AS deliveryType, " + status + " AS orderStatus, 0 AS retryCount, '' AS failReason, " + created + " AS createdTime, " + status + " AS status " +
                    "FROM delivery_rule r " + accountJoin("delivery_rule", "r") + " WHERE " + notDeleted("delivery_rule", "r"));
        }
        return new QueryDef(unionOrEmpty(parts), List.of("accountName", "deliveryType", "orderStatus", "failReason"), List.of("status", "orderStatus", "deliveryType"));
    }

    private QueryDef autoReplyQuery() {
        List<String> parts = new ArrayList<>();
        if (tableExists("auto_reply_rule")) {
            String ruleName = col("auto_reply_rule", "r", List.of("rule_name"), "''");
            String accountName = accountNameExpr("a");
            String replyMode = col("auto_reply_rule", "r", List.of("rule_type", "trigger_type", "match_type"), "'keyword'");
            String status = enabledStatusLabel(col("auto_reply_rule", "r", List.of("status", "enabled"), "1"));
            String hitCount = tableExists("auto_reply_log") ? "(SELECT COUNT(*) FROM auto_reply_log l WHERE l.rule_id=r.id" + (columnExists("auto_reply_log", "deleted") ? " AND l.deleted=0" : "") + ")" : "0";
            String created = col("auto_reply_rule", "r", List.of("created_time"), "NULL");
            parts.add("SELECT r.id AS id, 'auto_reply_rule' AS sourceTable, " + ruleName + " AS ruleName, " + accountName + " AS accountName, " + replyMode + " AS replyMode, " + hitCount + " AS hitCount, " + status + " AS status, " + created + " AS createdTime " +
                    "FROM auto_reply_rule r " + accountJoin("auto_reply_rule", "r") + " WHERE " + notDeleted("auto_reply_rule", "r"));
        }
        return new QueryDef(unionOrEmpty(parts), List.of("ruleName", "accountName", "replyMode", "status"), List.of("status", "replyMode"));
    }

    private QueryDef kamiQuery() {
        List<String> parts = new ArrayList<>();
        if (tableExists("card_group")) {
            String configName = col("card_group", "cg", List.of("group_name", "config_name"), "''");
            String accountName = "'-'";
            String total = columnExists("card_group", "total_count") ? "COALESCE(cg.total_count,0)" : (tableExists("card_item") ? "(SELECT COUNT(*) FROM card_item ci WHERE ci.group_id=cg.id" + (columnExists("card_item", "deleted") ? " AND ci.deleted=0" : "") + ")" : "0");
            String used = columnExists("card_group", "used_count") ? "COALESCE(cg.used_count,0)" : (tableExists("card_item") ? "(SELECT COUNT(*) FROM card_item ci WHERE ci.group_id=cg.id AND (" + usedCardPredicate("ci", "card_item") + ")" + (columnExists("card_item", "deleted") ? " AND ci.deleted=0" : "") + ")" : "0");
            String remain = columnExists("card_group", "available_count") ? "COALESCE(cg.available_count,0)" : "(" + total + " - " + used + ")";
            String status = enabledStatusLabel(col("card_group", "cg", List.of("status"), "1"));
            String created = col("card_group", "cg", List.of("created_time"), "NULL");
            parts.add("SELECT cg.id AS id, 'card_group' AS sourceTable, " + configName + " AS configName, " + accountName + " AS accountName, " + total + " AS totalCount, " + used + " AS usedCount, " + remain + " AS remainCount, " + status + " AS status, " + created + " AS createdTime " +
                    "FROM card_group cg WHERE " + notDeleted("card_group", "cg"));
        }
        return new QueryDef(unionOrEmpty(parts), List.of("configName", "accountName", "status"), List.of("status"));
    }

    private QueryDef hotGoodsQuery() {
        List<String> parts = new ArrayList<>();
        if (tableExists("hot_goods_stat")) {
            String title = col("hot_goods_stat", "h", List.of("title"), "''");
            String price = col("hot_goods_stat", "h", List.of("price"), "''");
            String coverPic = col("hot_goods_stat", "h", List.of("cover_pic"), "''");
            String dailySales = col("hot_goods_stat", "h", List.of("daily_sales"), "0");
            String statDate = col("hot_goods_stat", "h", List.of("stat_date"), "NULL");
            String created = col("hot_goods_stat", "h", List.of("created_time"), "NULL");
            String accountName = "'-'";
            if (tableExists("xianyu_account")) {
                accountName = "COALESCE(a.nickname, a.external_uid, '-')";
            }
            String joinAccount = "";
            if (tableExists("xianyu_account") && columnExists("hot_goods_stat", "account_id")) {
                joinAccount = " LEFT JOIN xianyu_account a ON a.id=h.account_id AND " + notDeleted("xianyu_account", "a");
            }
            parts.add("SELECT h.id AS id, 'hot_goods_stat' AS sourceTable, " +
                    title + " AS goodsTitle, " +
                    price + " AS price, " +
                    coverPic + " AS coverPic, " +
                    dailySales + " AS dailySales, " +
                    statDate + " AS statDate, " +
                    accountName + " AS accountName, " +
                    created + " AS createdTime, " +
                    "'正常' AS status " +
                    "FROM hot_goods_stat h" + joinAccount + " WHERE " + notDeleted("hot_goods_stat", "h"));
        }
        return new QueryDef(unionOrEmpty(parts), List.of("goodsTitle", "accountName"), List.of());
    }

    private String buildOuterWhere(QueryDef def, String keyword, String status, List<Object> args) {
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (StringUtils.hasText(keyword) && !def.keywordFields().isEmpty()) {
            where.append(" AND (");
            for (int i = 0; i < def.keywordFields().size(); i++) {
                if (i > 0) where.append(" OR ");
                where.append("CAST(t.").append(def.keywordFields().get(i)).append(" AS CHAR) LIKE ?");
                args.add("%" + keyword + "%");
            }
            where.append(")");
        }
        if (StringUtils.hasText(status) && !def.statusFields().isEmpty()) {
            List<String> words = statusWords(status);
            where.append(" AND (");
            int n = 0;
            for (String field : def.statusFields()) {
                for (String word : words) {
                    if (n++ > 0) where.append(" OR ");
                    where.append("CAST(t.").append(field).append(" AS CHAR) LIKE ?");
                    args.add("%" + word + "%");
                }
            }
            where.append(")");
        }
        return where.toString();
    }

    private List<String> statusWords(String status) {
        String s = status == null ? "" : status;
        if (s.contains("正常") || s.contains("启用") || s.contains("成功") || "1".equals(s)) return List.of("正常", "启用", "成功", "已支付", "在线", "完成");
        if (s.contains("待") || s.contains("过期") || s.contains("离线")) return List.of("待", "过期", "离线", "未发货", "未支付");
        if (s.contains("异常") || s.contains("失败") || s.contains("禁用") || "0".equals(s)) return List.of("异常", "失败", "禁用", "关闭", "失效");
        return List.of(s);
    }

    private QueryDef emptyQuery() {
        return new QueryDef(emptySelectSql(), List.of(), List.of("status"));
    }

    private String unionOrEmpty(List<String> parts) {
        if (parts.isEmpty()) {
            return emptySelectSql();
        }
        return String.join(" UNION ALL ", parts);
    }

    private String emptySelectSql() {
        return "SELECT 0 AS id, 'none' AS sourceTable, '' AS goodsTitle, '' AS coverPic, '' AS username, '' AS accountName, " +
                "0 AS orderCount, '' AS price, '' AS goofishLink, '' AS autoDelivery, '' AS autoReply, '' AS orderNo, '' AS buyerName, '' AS amount, " +
                "'' AS payStatus, '' AS orderStatus, '' AS deliveryStatus, '' AS messageType, '' AS replyType, " +
                "'' AS summary, '' AS deliveryType, 0 AS retryCount, '' AS failReason, '' AS ruleName, 0 AS hitCount, " +
                "'' AS configName, 0 AS totalCount, 0 AS usedCount, 0 AS remainCount, '' AS status, NULL AS createdTime WHERE 1=0";
    }

    private String accountJoin(String ownerTable, String ownerAlias) {
        return accountJoinBy(ownerTable, ownerAlias, List.of("account_id", "xianyu_account_id"));
    }

    private String accountJoinBy(String ownerTable, String ownerAlias, List<String> accountIdCols) {
        if (!tableExists("xianyu_account")) return "";
        for (String c : accountIdCols) {
            if (columnExists(ownerTable, c)) {
                return " LEFT JOIN xianyu_account a ON a.id=" + ownerAlias + "." + c + " AND " + notDeleted("xianyu_account", "a");
            }
        }
        return " LEFT JOIN xianyu_account a ON 1=0";
    }

    private String userJoin(String ownerTable, String ownerAlias, String accountAlias) {
        if (!tableExists("sys_user")) return "";
        List<String> candidates = new ArrayList<>();
        // 优先业务主表 user_id，其次账号 user_id/created_by_user_id。
        if (columnExists(ownerTable, "user_id")) candidates.add(ownerAlias + ".user_id");
        if (tableExists("xianyu_account")) {
            if (columnExists("xianyu_account", "user_id")) candidates.add(accountAlias + ".user_id");
            if (columnExists("xianyu_account", "created_by_user_id")) candidates.add(accountAlias + ".created_by_user_id");
        }
        if (candidates.isEmpty()) return " LEFT JOIN sys_user u ON 1=0";
        return " LEFT JOIN sys_user u ON u.id=COALESCE(" + String.join(",", candidates) + ")" + (columnExists("sys_user", "deleted") ? " AND u.deleted=0" : "");
    }

    private String accountNameExpr(String accountAlias) {
        if (!tableExists("xianyu_account")) return "'-'";
        return coalesce(List.of(
                has("xianyu_account", "nickname") ? accountAlias + ".nickname" : null,
                has("xianyu_account", "external_uid") ? accountAlias + ".external_uid" : null
        ), "'-'");
    }

    private String usernameExpr(String userAlias) {
        if (!tableExists("sys_user")) return "'-'";
        return coalesce(List.of(
                has("sys_user", "username") ? userAlias + ".username" : null,
                has("sys_user", "nickname") ? userAlias + ".nickname" : null,
                has("sys_user", "phone") ? userAlias + ".phone" : null
        ), "'-'");
    }

    private String primaryTable(String moduleKey) {
        return switch (moduleKey) {
            case "goods" -> "xianyu_goods";
            case "orders" -> "xianyu_trade_order";
            case "messages" -> "xianyu_conversation";
            case "delivery" -> tableExists("delivery_record") ? "delivery_record" : "delivery_rule";
            case "auto-reply" -> "auto_reply_rule";
            case "kami" -> "card_group";
            case "hot-goods" -> "hot_goods_stat";
            default -> "admin_module_record";
        };
    }

    private void updateGoodsStatus(long id, String normalized) {
        if (!tableExists("xianyu_goods")) return;
        String col = columnExists("xianyu_goods", "goods_status") ? "goods_status" : (columnExists("xianyu_goods", "status") ? "status" : null);
        if (col == null) return;
        String value = "正常".equals(normalized) ? ("goods_status".equals(col) ? "online" : "normal") : "offline";
        jdbcTemplate.update("UPDATE xianyu_goods SET " + col + "=?" + updateTimeClause("xianyu_goods") + " WHERE id=?", value, id);
    }

    private void updateDeliveryStatus(long id, String normalized) {
        String table = tableExists("delivery_record") ? "delivery_record" : "delivery_rule";
        if (!tableExists(table)) return;
        String col = columnExists(table, "delivery_status") ? "delivery_status" : (columnExists(table, "status") ? "status" : (columnExists(table, "enabled") ? "enabled" : null));
        if (col == null) return;
        Object value = statusValueForColumn(table, col, normalized);
        jdbcTemplate.update("UPDATE " + table + " SET " + col + "=?" + updateTimeClause(table) + " WHERE id=?", value, id);
    }

    private void updateAutoReplyStatus(long id, String normalized) {
        String table = "auto_reply_rule";
        if (!tableExists(table)) return;
        String col = columnExists(table, "status") ? "status" : (columnExists(table, "enabled") ? "enabled" : null);
        if (col == null) return;
        Object value = statusValueForColumn(table, col, normalized);
        jdbcTemplate.update("UPDATE " + table + " SET " + col + "=?" + updateTimeClause(table) + " WHERE id=?", value, id);
    }

    private void updateKamiStatus(long id, String normalized) {
        String table = "card_group";
        if (!tableExists(table) || !columnExists(table, "status")) return;
        Object value = statusValueForColumn(table, "status", normalized);
        jdbcTemplate.update("UPDATE " + table + " SET status=?" + updateTimeClause(table) + " WHERE id=?", value, id);
    }

    private Object statusValueForColumn(String table, String col, String normalized) {
        if ("enabled".equals(col)) return "正常".equals(normalized) ? 1 : 0;
        if ("status".equals(col) && numericStatusTable(table)) return "正常".equals(normalized) ? 1 : 0;
        if ("正常".equals(normalized)) return "success";
        if ("待处理".equals(normalized)) return "pending";
        return "failed";
    }

    private boolean numericStatusTable(String table) {
        return List.of("auto_reply_rule", "delivery_rule", "card_group").contains(table);
    }

    private String normalizeRequestedStatus(String status) {
        if (status == null) return "正常";
        if (status.contains("异常") || status.contains("失败") || status.contains("禁用") || "0".equals(status)) return "异常";
        if (status.contains("待") || status.contains("过期")) return "待处理";
        return "正常";
    }

    private String updateTimeClause(String table) {
        return columnExists(table, "updated_time") ? ", updated_time=NOW()" : "";
    }

    private String col(String table, String alias, List<String> candidates, String defaultSql) {
        for (String c : candidates) {
            if (columnExists(table, c)) return alias + "." + c;
        }
        return defaultSql;
    }

    private String priceAmountExpr(String table, String alias) {
        // 优先使用 price_cent（分），但若为 0/NULL 则回退到 price 字段（字符串金额）
        // 避免price_cent 未填充时所有商品价格显示为 ¥0.00
        if (columnExists(table, "price_cent") && columnExists(table, "price")) {
            return "CASE WHEN COALESCE(" + alias + ".price_cent,0) > 0 THEN " + alias + ".price_cent/100 " +
                   "ELSE CAST(NULLIF(REGEXP_REPLACE(COALESCE(" + alias + ".price,''), '[^0-9.]', ''), '') AS DECIMAL(18,2)) END";
        }
        if (columnExists(table, "price_cent")) return "COALESCE(" + alias + ".price_cent,0)/100";
        if (columnExists(table, "price")) return "COALESCE(" + alias + ".price,0)";
        if (columnExists(table, "goods_price")) return "COALESCE(" + alias + ".goods_price,0)";
        return "0";
    }

    private String orderAmountExpr(String table, String alias) {
        if (columnExists(table, "pay_amount_cent")) return "COALESCE(" + alias + ".pay_amount_cent," + alias + ".total_amount_cent,0)/100";
        if (columnExists(table, "total_amount_cent")) return "COALESCE(" + alias + ".total_amount_cent,0)/100";
        if (columnExists(table, "total_amount")) return "COALESCE(" + alias + ".total_amount,0)";
        if (columnExists(table, "total_price")) return "COALESCE(" + alias + ".total_price,0)";
        return "0";
    }

    private String decimalExpr(String expr) {
        return "COALESCE(" + expr + ",0)";
    }

    private String money(String amountExpr) {
        return "CONCAT('¥', ROUND((" + amountExpr + "), 2))";
    }

    private String enabledStatusLabel(String expr) {
        return "CASE WHEN " + expr + " IN (1,'1','true','启用','正常','success','online') THEN '正常' ELSE '禁用' END";
    }

    private String statusLabel(String expr) {
        return "CASE " +
                "WHEN " + expr + " IN (1,'1','true','normal','online','success','synced','active','completed','paid','已完成','正常','启用') THEN '正常' " +
                "WHEN " + expr + " IN (0,'0','false','disabled','offline','failed','closed','deleted','error','异常','失败','禁用') THEN '异常' " +
                "WHEN " + expr + " IN ('pending','unpaid','waiting','待处理','待支付','过期','离线') THEN '待处理' " +
                "ELSE COALESCE(CAST(" + expr + " AS CHAR),'未知') END";
    }

    private String orderStatusLabel(String expr) {
        return "CASE " +
                "WHEN " + expr + " IN ('completed','received','shipped','paid','success','已完成','已发货','已支付') THEN '正常' " +
                "WHEN " + expr + " IN ('unpaid','pending','waiting','待付款','待发货') THEN '待处理' " +
                "WHEN " + expr + " IN ('closed','refunding','refunded','failed','异常','失败') THEN '异常' " +
                "ELSE COALESCE(CAST(" + expr + " AS CHAR),'未知') END";
    }

    private String payStatusLabel(String expr) {
        return "CASE WHEN " + expr + " IN (1,'1','paid','已支付') THEN '已支付' WHEN " + expr + " IN (2,'2','refunded','已退款') THEN '已退款' ELSE '待支付' END";
    }

    private String deliveryStatusLabel(String expr) {
        return "CASE " +
                "WHEN " + expr + " IN (1,'1','success','shipped','signed','已发货','已签收','成功') THEN '成功' " +
                "WHEN " + expr + " IN (0,'0','pending','waiting','未发货','待处理') THEN '待处理' " +
                "WHEN " + expr + " IN (2,'2','failed','error','失败','异常') THEN '异常' " +
                "ELSE COALESCE(CAST(" + expr + " AS CHAR),'未知') END";
    }

    private String usedCardPredicate(String alias, String table) {
        List<String> predicates = new ArrayList<>();
        if (columnExists(table, "is_used")) predicates.add(alias + ".is_used=1");
        if (columnExists(table, "status")) predicates.add(alias + ".status IN ('used','已使用','1')");
        if (columnExists(table, "used_order_id")) predicates.add(alias + ".used_order_id IS NOT NULL");
        if (columnExists(table, "used_by_order_id")) predicates.add(alias + ".used_by_order_id IS NOT NULL");
        return predicates.isEmpty() ? "1=0" : String.join(" OR ", predicates);
    }

    private String notDeleted(String table, String alias) {
        return columnExists(table, "deleted") ? alias + ".deleted=0" : "1=1";
    }

    private boolean has(String table, String column) {
        return columnExists(table, column);
    }

    private String coalesce(List<String> expressions, String fallback) {
        List<String> real = expressions.stream().filter(Objects::nonNull).collect(Collectors.toList());
        if (real.isEmpty()) return fallback;
        real.add(fallback);
        return "COALESCE(" + String.join(",", real) + ")";
    }

    private Long queryLong(String sql, Object[] args) {
        try {
            return jdbcTemplate.queryForObject(sql, Long.class, args);
        } catch (Exception e) {
            return 0L;
        }
    }

    private boolean tableExists(String tableName) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = ?",
                    Integer.class, tableName);
            return count != null && count > 0;
        } catch (DataAccessException e) {
            return false;
        }
    }

    private boolean columnExists(String tableName, String columnName) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = ? AND column_name = ?",
                    Integer.class, tableName, columnName);
            return count != null && count > 0;
        } catch (DataAccessException e) {
            return false;
        }
    }

    private String csv(String s) {
        return CsvCellEncoder.encode(s);
    }

    private record QueryDef(String sql, List<String> keywordFields, List<String> statusFields, List<String> sortableFields) {
        QueryDef(String sql, List<String> keywordFields, List<String> statusFields) {
            this(sql, keywordFields, statusFields, List.of());
        }
    }
}
