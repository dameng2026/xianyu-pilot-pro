package com.xianyu.admin.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.*;

/**
 * 货源商城合并查询服务
 * UNION mall_product（平台自营）+ supply_product（供货商品）
 */
@Service
public class SupplyShopService {

    private final JdbcTemplate jdbcTemplate;

    public SupplyShopService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 商城列表（合并展示）
     */
    public Map<String, Object> listProducts(int page, int size, String category, String type, String keyword, String sort) {
        int offset = (page - 1) * size;

        // UNION 查询：mall_product + supply_product
        // 统一字段：id, source, title, subtitle, cover_url, price_cent, product_type, category, bought_count, weight
        StringBuilder unionSql = new StringBuilder(
            "SELECT id, 'mall' as source, title, subtitle, cover_url, price_cent, " +
            "product_type, category, bought_count, weight, sort_order, created_time " +
            "FROM mall_product WHERE status = 1 AND deleted = 0 " +
            "UNION ALL " +
            "SELECT id, 'supply' as source, title, subtitle, cover_url, price_cent, " +
            "product_type, category, bought_count, weight, sort_order, created_time " +
            "FROM supply_product WHERE status = 1 AND audit_status = 'approved' AND deleted = 0"
        );

        List<Object> params = new ArrayList<>();

        // 分类筛选和类型筛选（在 UNION 外部用 WHERE 过滤）
        StringBuilder whereClause = new StringBuilder();
        if (category != null && !category.isEmpty() && !"全部".equals(category)) {
            whereClause.append(" WHERE category = ?");
            params.add(category);
        }
        // type=all 时不过滤；仅当 type=text 或 type=card_key 时才加类型过滤
        if (type != null && !type.isEmpty() && !"all".equals(type)) {
            whereClause.append(whereClause.length() > 0 ? " AND" : " WHERE");
            whereClause.append(" product_type = ?");
            params.add(type);
        }
        if (keyword != null && !keyword.isEmpty()) {
            whereClause.append(whereClause.length() > 0 ? " AND" : " WHERE");
            whereClause.append(" title LIKE ?");
            params.add("%" + keyword + "%");
        }

        // 排序逻辑
        String orderBy;
        switch (sort != null ? sort : "") {
            case "sales":
                orderBy = " ORDER BY bought_count DESC, weight DESC, sort_order DESC, created_time DESC";
                break;
            case "price-asc":
                orderBy = " ORDER BY price_cent ASC, weight DESC, sort_order DESC, created_time DESC";
                break;
            case "price-desc":
                orderBy = " ORDER BY price_cent DESC, weight DESC, sort_order DESC, created_time DESC";
                break;
            case "new":
                orderBy = " ORDER BY created_time DESC, weight DESC, sort_order DESC";
                break;
            default:
                orderBy = " ORDER BY weight DESC, sort_order DESC, created_time DESC";
                break;
        }

        // 统计总数
        String countSql = "SELECT COUNT(*) FROM (" + unionSql + ") AS merged" + whereClause;
        Integer total = jdbcTemplate.queryForObject(countSql, Integer.class, params.toArray());

        // 查询列表
        String listSql = "SELECT * FROM (" + unionSql + ") AS merged" + whereClause +
            orderBy + " LIMIT ? OFFSET ?";
        List<Object> listParams = new ArrayList<>(params);
        listParams.add(size);
        listParams.add(offset);

        List<Map<String, Object>> list = jdbcTemplate.queryForList(listSql, listParams.toArray());

        // 供货商品补充卡密实际库存
        for (Map<String, Object> product : list) {
            if ("supply".equals(product.get("source")) && "card".equals(product.get("product_type"))) {
                Long productId = ((Number) product.get("id")).longValue();
                Integer stock = getCardStock(productId);
                product.put("stock", stock);
            }
        }

        Map<String, Object> result = new HashMap<>();
        result.put("total", total);
        result.put("list", list);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    /**
     * 商品详情（按 source 分发）
     */
    public Map<String, Object> getProductDetail(String source, Long id) {
        if ("mall".equals(source)) {
            return getMallProductDetail(id);
        } else {
            return getSupplyProductDetail(id);
        }
    }

    private Map<String, Object> getMallProductDetail(Long id) {
        List<Map<String, Object>> products = jdbcTemplate.queryForList(
            "SELECT id, 'mall' as source, title, subtitle, content, cover_url, price_cent, " +
            "product_type, category, bought_count, status FROM mall_product WHERE id = ? AND status = 1 AND deleted = 0", id);
        if (products.isEmpty()) {
            throw new RuntimeException("商品不存在");
        }
        return products.get(0);
    }

    private Map<String, Object> getSupplyProductDetail(Long id) {
        List<Map<String, Object>> products = jdbcTemplate.queryForList(
            "SELECT id, 'supply' as source, title, subtitle, content, cover_url, price_cent, " +
            "product_type, category, bought_count, status, card_group_id, seller_id " +
            "FROM supply_product WHERE id = ? AND status = 1 AND audit_status = 'approved' AND deleted = 0", id);
        if (products.isEmpty()) {
            throw new RuntimeException("商品不存在");
        }
        Map<String, Object> product = products.get(0);
        if ("card".equals(product.get("product_type"))) {
            product.put("stock", getCardStock(id));
        }
        return product;
    }

    /**
     * 获取供货商品的卡密库存
     */
    private Integer getCardStock(Long productId) {
        List<Long> cardGroupIds = jdbcTemplate.queryForList(
            "SELECT card_group_id FROM supply_product WHERE id = ? AND card_group_id IS NOT NULL",
            Long.class, productId);
        if (cardGroupIds.isEmpty()) {
            return 0;
        }
        Long cardGroupId = cardGroupIds.get(0);
        return jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM card_item WHERE group_id = ? AND status = 0 AND deleted = 0",
            Integer.class, cardGroupId);
    }
}
