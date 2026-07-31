package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.security.UserContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.*;

/**
 * 供货商品服务
 * 供货商上传/编辑/下架/补库存/改价；销量与库存看板
 */
@Service
public class SupplyProductService {

    private final JdbcTemplate jdbcTemplate;
    private final SupplyAuditService auditService;
    private final TradeConfigService configService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SupplyProductService(JdbcTemplate jdbcTemplate,
                                 SupplyAuditService auditService,
                                 TradeConfigService configService) {
        this.jdbcTemplate = jdbcTemplate;
        this.auditService = auditService;
        this.configService = configService;
    }

    /**
     * 上传货源（触发审核）
     */
    @Transactional
    public Map<String, Object> createProduct(Map<String, Object> body) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        String productType = (String) body.getOrDefault("productType", "text");
        String title = (String) body.get("title");
        Long priceCent = ((Number) body.getOrDefault("priceCent", 0)).longValue();

        // 校验商品数量上限
        int maxProducts = configService.getMaxProductsPerSeller();
        Integer count = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM supply_product WHERE seller_id = ? AND deleted = 0",
            Integer.class, userId);
        if (count != null && count >= maxProducts) {
            throw new RuntimeException("已达供货商商品数量上限：" + maxProducts);
        }

        // 卡密货源校验 card_group_id 归属
        Long cardGroupId = body.get("cardGroupId") != null ? ((Number) body.get("cardGroupId")).longValue() : null;
        if ("card".equals(productType) && cardGroupId != null) {
            validateCardGroupOwnership(cardGroupId, userId);
        }

        // 写入商品
        jdbcTemplate.update(
            "INSERT INTO supply_product(tenant_id, seller_id, product_type, title, subtitle, content, " +
            "delivery_content, cover_url, images_json, category, price_cent, stock, card_group_id, " +
            "audit_status, status, weight, bought_count, commission_rate, created_time, updated_time, deleted) " +
            "VALUES(?,?,?,?,?,?,?,?,?,?,?, ?,?, 'pending', 0, 0, 0, ?, NOW(), NOW(), 0)",
            tenantId, userId, productType, title,
            body.getOrDefault("subtitle", ""),
            body.getOrDefault("content", ""),
            body.getOrDefault("deliveryContent", ""),
            body.getOrDefault("coverUrl", ""),
            body.get("imagesJson") != null ? body.get("imagesJson").toString() : null,
            body.getOrDefault("category", ""),
            priceCent,
            body.getOrDefault("stock", -1),
            cardGroupId,
            body.get("commissionRate") != null ? new BigDecimal(body.get("commissionRate").toString()) : new BigDecimal("0.0500")
        );

        Long productId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);

        // 提交审核
        auditService.submitForAudit("supply_product", productId, userId, tenantId, body);

        Map<String, Object> result = new HashMap<>();
        result.put("id", productId);
        result.put("auditStatus", "pending");
        result.put("message", "货源已提交，等待审核");
        return result;
    }

    /**
     * 我的货源列表
     */
    public Map<String, Object> listMyProducts(int page, int size, String auditStatus) {
        Long userId = UserContext.userId();
        int offset = (page - 1) * size;

        StringBuilder where = new StringBuilder("WHERE seller_id = ? AND deleted = 0");
        List<Object> params = new ArrayList<>();
        params.add(userId);
        if (auditStatus != null && !auditStatus.isEmpty()) {
            where.append(" AND audit_status = ?");
            params.add(auditStatus);
        }

        Integer total = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM supply_product " + where, Integer.class, params.toArray());

        List<Object> listParams = new ArrayList<>(params);
        listParams.add(size);
        listParams.add(offset);

        List<Map<String, Object>> products = jdbcTemplate.queryForList(
            "SELECT id, product_type, title, subtitle, cover_url, price_cent, stock, card_group_id, " +
            "audit_status, audit_reason, status, weight, bought_count, category, created_time, updated_time " +
            "FROM supply_product " + where +
            " ORDER BY created_time DESC LIMIT ? OFFSET ?",
            listParams.toArray());

        // 卡密商品补充实际库存
        for (Map<String, Object> product : products) {
            if ("card".equals(product.get("product_type")) && product.get("card_group_id") != null) {
                Long cardGroupId = ((Number) product.get("card_group_id")).longValue();
                Integer available = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM card_item WHERE group_id = ? AND status = 0 AND deleted = 0",
                    Integer.class, cardGroupId);
                product.put("actualStock", available);
            }
        }

        Map<String, Object> result = new HashMap<>();
        result.put("total", total);
        result.put("list", products);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    /**
     * 货源详情
     */
    public Map<String, Object> getProduct(Long id) {
        List<Map<String, Object>> products = jdbcTemplate.queryForList(
            "SELECT * FROM supply_product WHERE id = ? AND deleted = 0", id);
        if (products.isEmpty()) {
            throw new RuntimeException("货源不存在");
        }
        Map<String, Object> product = products.get(0);
        // 卡密商品补充库存
        if ("card".equals(product.get("product_type")) && product.get("card_group_id") != null) {
            Long cardGroupId = ((Number) product.get("card_group_id")).longValue();
            Integer available = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM card_item WHERE group_id = ? AND status = 0 AND deleted = 0",
                Integer.class, cardGroupId);
            product.put("actualStock", available);
        }
        return product;
    }

    /**
     * 编辑货源
     * 改标题/描述/封面 → 重新审核；改价 → 直接生效
     */
    @Transactional
    public Map<String, Object> updateProduct(Long id, Map<String, Object> body) {
        Long userId = UserContext.userId();
        validateOwnership(id, userId);

        boolean needReaudit = false;
        List<String> updates = new ArrayList<>();
        List<Object> params = new ArrayList<>();

        if (body.containsKey("title")) {
            updates.add("title = ?");
            params.add(body.get("title"));
            needReaudit = true;
        }
        if (body.containsKey("subtitle")) {
            updates.add("subtitle = ?");
            params.add(body.get("subtitle"));
            needReaudit = true;
        }
        if (body.containsKey("content")) {
            updates.add("content = ?");
            params.add(body.get("content"));
            needReaudit = true;
        }
        if (body.containsKey("coverUrl")) {
            updates.add("cover_url = ?");
            params.add(body.get("coverUrl"));
            needReaudit = true;
        }
        if (body.containsKey("deliveryContent")) {
            updates.add("delivery_content = ?");
            params.add(body.get("deliveryContent"));
            needReaudit = true;
        }
        // 改价直接生效，无需重新审核
        if (body.containsKey("priceCent")) {
            updates.add("price_cent = ?");
            params.add(((Number) body.get("priceCent")).longValue());
        }
        if (body.containsKey("weight")) {
            updates.add("weight = ?");
            params.add(body.get("weight"));
        }

        if (updates.isEmpty()) {
            Map<String, Object> result = new HashMap<>();
            result.put("message", "无更新内容");
            return result;
        }

        updates.add("updated_time = NOW()");
        params.add(id);

        jdbcTemplate.update(
            "UPDATE supply_product SET " + String.join(", ", updates) + " WHERE id = ?",
            params.toArray());

        // 如果改了标题/描述/封面，需要重新审核
        if (needReaudit) {
            jdbcTemplate.update(
                "UPDATE supply_product SET audit_status = 'pending' WHERE id = ?", id);
            // 如果当前是上架状态，先下架
            jdbcTemplate.update(
                "UPDATE supply_product SET status = 0 WHERE id = ? AND status = 1", id);
            auditService.submitForAudit("supply_product", id, userId,
                UserContext.getTenantId(), body);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("message", needReaudit ? "已修改，需重新审核" : "修改成功");
        result.put("needReaudit", needReaudit);
        return result;
    }

    /**
     * 上架（仅 audit_status=approved）
     */
    public Map<String, Object> online(Long id) {
        Long userId = UserContext.userId();
        validateOwnership(id, userId);

        Integer auditStatusCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM supply_product WHERE id = ? AND audit_status = 'approved' AND deleted = 0",
            Integer.class, id);
        if (auditStatusCount == null || auditStatusCount == 0) {
            throw new RuntimeException("审核未通过，无法上架");
        }

        jdbcTemplate.update("UPDATE supply_product SET status = 1, updated_time = NOW() WHERE id = ?", id);

        Map<String, Object> result = new HashMap<>();
        result.put("message", "上架成功");
        return result;
    }

    /**
     * 下架
     */
    public Map<String, Object> offline(Long id) {
        Long userId = UserContext.userId();
        validateOwnership(id, userId);
        jdbcTemplate.update("UPDATE supply_product SET status = 0, updated_time = NOW() WHERE id = ?", id);
        Map<String, Object> result = new HashMap<>();
        result.put("message", "下架成功");
        return result;
    }

    /**
     * 删除（软删，有销量则禁止）
     */
    public Map<String, Object> delete(Long id) {
        Long userId = UserContext.userId();
        validateOwnership(id, userId);

        Integer boughtCount = jdbcTemplate.queryForObject(
            "SELECT bought_count FROM supply_product WHERE id = ?", Integer.class, id);
        if (boughtCount != null && boughtCount > 0) {
            throw new RuntimeException("已有销量的商品不可删除");
        }

        jdbcTemplate.update("UPDATE supply_product SET deleted = 1, status = 0, updated_time = NOW() WHERE id = ?", id);
        Map<String, Object> result = new HashMap<>();
        result.put("message", "删除成功");
        return result;
    }

    /**
     * 销量/库存/收入统计
     */
    public Map<String, Object> stats(Long id) {
        Long userId = UserContext.userId();
        validateOwnership(id, userId);

        Map<String, Object> stats = jdbcTemplate.queryForList(
            "SELECT bought_count, price_cent, stock, card_group_id, product_type, status, audit_status " +
            "FROM supply_product WHERE id = ?", id).get(0);

        // 卡密商品补充实际库存
        if ("card".equals(stats.get("product_type")) && stats.get("card_group_id") != null) {
            Long cardGroupId = ((Number) stats.get("card_group_id")).longValue();
            Integer available = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM card_item WHERE group_id = ? AND status = 0 AND deleted = 0",
                Integer.class, cardGroupId);
            stats.put("actualStock", available);
        }

        return stats;
    }

    /**
     * 供货中心首页数据（已上传数/今日收入/收入趋势/余额占位）
     * 注：今日收入与余额在 Phase 2 trade_balance 实现后填充真实数据
     */
    public Map<String, Object> dashboard() {
        Long userId = UserContext.userId();

        Integer uploadedCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM supply_product WHERE seller_id = ? AND deleted = 0",
            Integer.class, userId);

        Integer pendingAuditCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM supply_product WHERE seller_id = ? AND audit_status = 'pending' AND deleted = 0",
            Integer.class, userId);

        Integer onlineCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM supply_product WHERE seller_id = ? AND status = 1 AND deleted = 0",
            Integer.class, userId);

        Map<String, Object> dashboard = new HashMap<>();
        dashboard.put("uploadedCount", uploadedCount);
        dashboard.put("pendingAuditCount", pendingAuditCount);
        dashboard.put("onlineCount", onlineCount);
        // Phase 2 后填充真实收入数据
        dashboard.put("todayIncomeCent", 0);
        dashboard.put("availableBalanceCent", 0);
        dashboard.put("frozenBalanceCent", 0);
        return dashboard;
    }

    /**
     * 收入流水趋势（近30天）
     * Phase 2 实现（依赖 cash_balance_ledger 表）
     */
    public Map<String, Object> salesTrend() {
        Map<String, Object> result = new HashMap<>();
        result.put("message", "收入趋势将在 Phase 2 交易功能上线后可用");
        result.put("trend", Collections.emptyList());
        return result;
    }

    /**
     * 校验商品归属
     */
    private void validateOwnership(Long productId, Long userId) {
        Integer count = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM supply_product WHERE id = ? AND seller_id = ? AND deleted = 0",
            Integer.class, productId, userId);
        if (count == null || count == 0) {
            throw new RuntimeException("无权操作此商品");
        }
    }

    /**
     * 校验卡密组归属
     */
    private void validateCardGroupOwnership(Long cardGroupId, Long userId) {
        Integer count = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM card_group WHERE id = ? AND user_id = ? AND deleted = 0",
            Integer.class, cardGroupId, userId);
        if (count == null || count == 0) {
            throw new RuntimeException("卡密组不存在或无权使用");
        }
    }
}
