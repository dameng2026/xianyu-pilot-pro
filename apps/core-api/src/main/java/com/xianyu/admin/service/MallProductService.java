package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * 货源商城商品服务。
 * 管理端：商品/卡密/FAQ CRUD；用户端：商品列表、详情、分类、FAQ。
 * 卡密商品库存量 = mall_card_key 表中 status='available' 的数量。
 * price_cent 以分为单位存储，与 PaymentService 保持一致。
 */
@Service
public class MallProductService {
    private static final Logger log = LoggerFactory.getLogger(MallProductService.class);
    private static final long MAX_PRICE_CENT = 100_000_000L;
    private static final int MAX_TITLE_LENGTH = 200;
    private static final int MAX_SUBTITLE_LENGTH = 200;
    private static final int MAX_CONTENT_LENGTH = 20_000;
    private static final int MAX_CATEGORY_LENGTH = 50;
    private static final int MAX_COVER_URL_LENGTH = 500;
    private static final int MAX_CARD_CONTENT_LENGTH = 10_000;
    private static final int MAX_FAQ_QUESTION_LENGTH = 500;
    private static final int MAX_FAQ_ANSWER_LENGTH = 5_000;
    /**
     * 深分页阈值：OFFSET 超过此值时启用延迟关联优化。
     * 阈值依据：常规列表 size=20，OFFSET < 1000 时直接 LIMIT OFFSET 性能可接受；
     * 超过 1000 时扫描跳过代价过大，改用 INNER JOIN 子查询先走覆盖索引定位 id。
     */
    private static final int DEFERRED_JOIN_OFFSET_THRESHOLD = 1000;

    private final JdbcTemplate jdbcTemplate;
    private final AutomationClient automationClient;

    /**
     * 并行查询线程池：用于商品列表/详情的 count + records 并行、详情 + 库存并行。
     * 命名线程、守护线程，避免阻塞 JVM 退出。池大小 8 足够支撑当前 QPS。
     */
    private final ExecutorService queryPool = Executors.newFixedThreadPool(8, r -> {
        Thread t = new Thread(r, "mall-product-query");
        t.setDaemon(true);
        return t;
    });

    public MallProductService(JdbcTemplate jdbcTemplate, AutomationClient automationClient) {
        this.jdbcTemplate = jdbcTemplate;
        this.automationClient = automationClient;
    }

    /**
     * 应用关闭时释放线程池（Spring 通过 @PreDestroy 回调）。
     */
    @jakarta.annotation.PreDestroy
    public void shutdown() {
        queryPool.shutdown();
        try {
            if (!queryPool.awaitTermination(5, TimeUnit.SECONDS)) {
                queryPool.shutdownNow();
            }
        } catch (InterruptedException e) {
            queryPool.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }

    // ==================== 管理端：商品 ====================

    /**
     * 管理端商品列表（含 count + records 并行查询 + 深分页延迟关联）。
     */
    public PageResult<Map<String, Object>> listProducts(String type, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 100);
        int offset = (safeCurrent - 1) * safeSize;
        String normalizedType = normalizeProductType(type);
        StringBuilder where = new StringBuilder(" WHERE deleted=0");
        List<Object> args = new ArrayList<>();
        if (StringUtils.hasText(normalizedType)) {
            where.append(" AND product_type=?");
            args.add(normalizedType);
        }
        // 并行：count 查询与 records 查询同时发起
        CompletableFuture<Long> totalFuture = CompletableFuture.supplyAsync(
                () -> queryCount("SELECT COUNT(*) FROM mall_product" + where, args), queryPool);
        String recordsSql = buildListProductsSql(where, offset);
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        CompletableFuture<List<Map<String, Object>>> recordsFuture = CompletableFuture.supplyAsync(
                () -> jdbcTemplate.queryForList(recordsSql, pageArgs.toArray()), queryPool);
        Long total;
        List<Map<String, Object>> records;
        try {
            total = totalFuture.join();
            records = recordsFuture.join();
        } catch (Exception e) {
            throw new BizException(503, "商品列表查询暂时不可用，请稍后重试");
        }
        // 附带卡密商品库存数
        for (Map<String, Object> record : records) {
            attachStockInfo(record);
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 构造商品列表 SQL：OFFSET 较小时直接 LIMIT/OFFSET，OFFSET 较大时改用延迟关联。
     */
    private String buildListProductsSql(StringBuilder where, int offset) {
        String selectFields = "id, tenant_id AS tenantId, product_type AS productType, title, subtitle, content, copy, " +
                "delivery_content AS deliveryContent, " +
                "price_cent AS priceCent, ROUND(price_cent/100,2) AS priceYuan, " +
                "cover_url AS coverUrl, status, category, ai_category_confidence AS aiCategoryConfidence, " +
                "sort_order AS sortOrder, bought_count AS boughtCount, " +
                "created_time AS createdTime, updated_time AS updatedTime";
        if (offset < DEFERRED_JOIN_OFFSET_THRESHOLD) {
            return "SELECT " + selectFields + " FROM mall_product" + where +
                    " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?";
        }
        // 延迟关联：子查询仅走覆盖索引 (sort_order, id, deleted) 定位 id，再回表取完整字段。
        // 深分页时主表的 LIMIT OFFSET 会逐行扫描跳过，子查询在覆盖索引上完成跳跃代价显著降低。
        return "SELECT " + selectFields + " FROM mall_product INNER JOIN (" +
                "SELECT id FROM mall_product" + where +
                " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?" +
                ") AS t ON mall_product.id = t.id ORDER BY mall_product.sort_order ASC, mall_product.id DESC";
    }

    public Map<String, Object> getProduct(long id) {
        Map<String, Object> product = queryOne(
                "SELECT id, tenant_id AS tenantId, product_type AS productType, title, subtitle, content, copy, " +
                        "delivery_content AS deliveryContent, " +
                        "price_cent AS priceCent, ROUND(price_cent/100,2) AS priceYuan, " +
                        "cover_url AS coverUrl, status, category, ai_category_confidence AS aiCategoryConfidence, " +
                        "sort_order AS sortOrder, bought_count AS boughtCount, " +
                        "created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM mall_product WHERE id=? AND deleted=0",
                id);
        if (product == null) throw new BizException(404, "商品不存在");
        // 异步附加库存信息，不阻塞主查询线程
        attachStockInfoAsync(product);
        return product;
    }

    @Transactional
    public Map<String, Object> createProduct(Map<String, Object> data) {
        if (data == null) throw new BizException(400, "商品参数不能为空");
        // 兼容前端发送的 type 字段（与 productType 等价）
        Object productTypeValue = first(data, "productType", "type");
        if (productTypeValue == null || String.valueOf(productTypeValue).isBlank()) {
            throw new BizException(400, "商品类型不能为空");
        }
        String productType = normalizeProductType(String.valueOf(productTypeValue).trim());
        String title = boundedRequired(data, "title", "商品标题不能为空", MAX_TITLE_LENGTH);
        String subtitle = boundedOptional(data, "subtitle", MAX_SUBTITLE_LENGTH);
        String content = boundedOptional(data, "content", MAX_CONTENT_LENGTH);
        String copy = boundedOptional(data, "copy", MAX_CONTENT_LENGTH);
        String deliveryContent = boundedOptional(data, "deliveryContent", MAX_CONTENT_LENGTH);
        long priceCent = parseMoneyCent(data);
        if (priceCent < 0 || priceCent > MAX_PRICE_CENT) {
            throw new BizException(400, "商品价格必须在 0 至 1000000 元之间");
        }
        String coverUrl = boundedOptional(data, "coverUrl", MAX_COVER_URL_LENGTH);
        // 兼容前端 enabled 字段（与 status 等价：true=1 上架, false=0 下架）
        int status = optionalEnabled(first(data, "status", "enabled"), 1, "商品状态");
        String category = boundedOptional(data, "category", MAX_CATEGORY_LENGTH);
        int sortOrder = optionalInt(data.get("sortOrder"), "排序值", -1_000_000, 1_000_000, 0);
        int affected = safeUpdate("创建商品失败",
                "INSERT INTO mall_product(tenant_id, product_type, title, subtitle, content, copy, delivery_content, price_cent, " +
                        "cover_url, status, category, ai_category_confidence, sort_order, bought_count, " +
                        "created_time, updated_time, deleted) " +
                        "VALUES(0,?,?,?,?,?,?,?,?,?,?,0,?,0,NOW(),NOW(),0)",
                productType, title, subtitle, content.isEmpty() ? null : content,
                copy.isEmpty() ? null : copy,
                deliveryContent.isEmpty() ? null : deliveryContent,
                priceCent, coverUrl, status, category, sortOrder);
        if (affected != 1) throw new BizException(503, "创建商品失败，数据库未确认写入");
        Long newId = lastInsertId();
        return getProduct(newId);
    }

    @Transactional
    public Map<String, Object> updateProduct(long id, Map<String, Object> data) {
        if (data == null) throw new BizException(400, "商品参数不能为空");
        Map<String, Object> existing = getProduct(id);
        // 兼容前端发送的 type 字段（与 productType 等价）
        Object productTypeValue = first(data, "productType", "type");
        String productType = StringUtils.hasText(productTypeValue == null ? "" : String.valueOf(productTypeValue))
                ? normalizeProductType(String.valueOf(productTypeValue).trim()) : text(existing.get("productType"));
        String title = data.containsKey("title")
                ? boundedRequired(data, "title", "商品标题不能为空", MAX_TITLE_LENGTH)
                : text(existing.get("title"));
        String subtitle = data.containsKey("subtitle")
                ? boundedOptional(data, "subtitle", MAX_SUBTITLE_LENGTH)
                : text(existing.get("subtitle"));
        String content = data.containsKey("content")
                ? boundedOptional(data, "content", MAX_CONTENT_LENGTH)
                : text(existing.get("content"));
        String copy = data.containsKey("copy")
                ? boundedOptional(data, "copy", MAX_CONTENT_LENGTH)
                : text(existing.get("copy"));
        String deliveryContent = data.containsKey("deliveryContent")
                ? boundedOptional(data, "deliveryContent", MAX_CONTENT_LENGTH)
                : text(existing.get("deliveryContent"));
        long priceCent = data.containsKey("priceCent") || data.containsKey("priceYuan") || data.containsKey("price")
                ? parseMoneyCent(data) : storedLong(existing.get("priceCent"), "商品价格", 0, MAX_PRICE_CENT);
        if (priceCent < 0 || priceCent > MAX_PRICE_CENT) {
            throw new BizException(400, "商品价格必须在 0 至 1000000 元之间");
        }
        String coverUrl = data.containsKey("coverUrl")
                ? boundedOptional(data, "coverUrl", MAX_COVER_URL_LENGTH)
                : text(existing.get("coverUrl"));
        int status = data.containsKey("status") || data.containsKey("enabled")
                ? optionalEnabled(first(data, "status", "enabled"), 1, "商品状态")
                : storedInt(existing.get("status"), "商品状态", 0, 1);
        String category = data.containsKey("category")
                ? boundedOptional(data, "category", MAX_CATEGORY_LENGTH)
                : text(existing.get("category"));
        int sortOrder = data.containsKey("sortOrder")
                ? optionalInt(data.get("sortOrder"), "排序值", -1_000_000, 1_000_000, 0)
                : storedInt(existing.get("sortOrder"), "排序值", -1_000_000, 1_000_000);
        int affected = safeUpdate("更新商品失败",
                "UPDATE mall_product SET product_type=?, title=?, subtitle=?, content=?, copy=?, delivery_content=?, price_cent=?, " +
                        "cover_url=?, status=?, category=?, sort_order=?, updated_time=NOW() WHERE id=? AND deleted=0",
                productType, title, subtitle, content.isEmpty() ? null : content,
                copy.isEmpty() ? null : copy,
                deliveryContent.isEmpty() ? null : deliveryContent,
                priceCent, coverUrl, status, category, sortOrder, id);
        if (affected != 1) throw new BizException(404, "商品不存在");
        return getProduct(id);
    }

    @Transactional
    public void deleteProduct(long id) {
        int affected = safeUpdate("删除商品失败",
                "UPDATE mall_product SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
        if (affected != 1) throw new BizException(404, "商品不存在");
        // 级联软删除前台用户的货源库中引用该商品的记录（from_mall=1 AND mall_product_id=id）
        // 不删除用户自定义内容会残留无效货源，故同步标记为已删除
        try {
            jdbcTemplate.update(
                    "UPDATE delivery_text_source SET deleted=1, updated_time=NOW() " +
                            "WHERE from_mall=1 AND mall_product_id=? AND deleted=0", id);
        } catch (DataAccessException e) {
            log.warn("级联删除前台货源库记录失败, mallProductId={}, errorType={}", id, e.getClass().getSimpleName());
            // 不抛异常：mall_product 已成功删除，货源库残留记录在前台会显示"商品已下架或被删除"
        }
    }

    // ==================== 管理端：卡密 ====================

    @Transactional
    public Map<String, Object> importCardKeys(long productId, String cards) {
        // 校验商品存在且为卡密类型
        Map<String, Object> product = getProduct(productId);
        if (!"card".equals(text(product.get("productType")))) {
            throw new BizException(400, "仅卡密商品支持导入卡密");
        }
        if (cards == null || cards.isBlank()) {
            throw new BizException(400, "卡密内容不能为空");
        }
        String[] lines = cards.split("\\r?\\n");
        int imported = 0;
        int skipped = 0;
        for (String raw : lines) {
            String line = raw == null ? "" : raw.trim();
            if (line.isEmpty()) {
                skipped++;
                continue;
            }
            if (line.length() > MAX_CARD_CONTENT_LENGTH) {
                throw new BizException(400, "单条卡密长度不能超过 " + MAX_CARD_CONTENT_LENGTH + " 个字符");
            }
            try {
                jdbcTemplate.update(
                        "INSERT INTO mall_card_key(product_id, card_content, status, order_no, created_time) " +
                                "VALUES(?,?,'available','',NOW())",
                        productId, line);
                imported++;
            } catch (DataAccessException e) {
                log.error("导入卡密失败, productId={}, errorType={}", productId, e.getClass().getSimpleName());
                throw new BizException(503, "卡密导入暂时不可用，请稍后重试");
            }
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("productId", productId);
        result.put("imported", imported);
        result.put("skipped", skipped);
        return result;
    }

    public PageResult<Map<String, Object>> listCardKeys(long productId, int current, int size) {
        // 校验商品存在
        getProduct(productId);
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        Long total = queryCount(
                "SELECT COUNT(*) FROM mall_card_key WHERE product_id=?", List.of(productId));
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT id, product_id AS productId, card_content AS cardContent, status, order_no AS orderNo, " +
                        "created_time AS createdTime, sold_time AS soldTime " +
                        "FROM mall_card_key WHERE product_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                productId, safeSize, offset);
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    public Map<String, Object> getCardKeyStock(long productId) {
        getProduct(productId);
        Long available = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM mall_card_key WHERE product_id=? AND status='available'",
                Long.class, productId);
        Long sold = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM mall_card_key WHERE product_id=? AND status='sold'",
                Long.class, productId);
        Long disabled = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM mall_card_key WHERE product_id=? AND status='disabled'",
                Long.class, productId);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("productId", productId);
        result.put("available", available == null ? 0 : available);
        result.put("sold", sold == null ? 0 : sold);
        result.put("disabled", disabled == null ? 0 : disabled);
        result.put("total", (available == null ? 0 : available) + (sold == null ? 0 : sold) + (disabled == null ? 0 : disabled));
        return result;
    }

    // ==================== 管理端：FAQ ====================

    public List<Map<String, Object>> listFaqs() {
        return jdbcTemplate.queryForList(
                "SELECT id, tenant_id AS tenantId, question, answer, sort_order AS sortOrder, status, " +
                        "created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM mall_faq WHERE deleted=0 ORDER BY sort_order ASC, id DESC");
    }

    @Transactional
    @CacheEvict(value = "mallPublic", allEntries = true)
    public Map<String, Object> createFaq(Map<String, Object> data) {
        if (data == null) throw new BizException(400, "FAQ 参数不能为空");
        String question = boundedRequired(data, "question", "问题不能为空", MAX_FAQ_QUESTION_LENGTH);
        String answer = boundedRequired(data, "answer", "答案不能为空", MAX_FAQ_ANSWER_LENGTH);
        int sortOrder = optionalInt(data.get("sortOrder"), "排序值", -1_000_000, 1_000_000, 0);
        int status = optionalEnabled(data.get("status"), 1, "FAQ 状态");
        int affected = safeUpdate("创建 FAQ 失败",
                "INSERT INTO mall_faq(tenant_id, question, answer, sort_order, status, " +
                        "created_time, updated_time, deleted) VALUES(0,?,?,?,?,NOW(),NOW(),0)",
                question, answer, sortOrder, status);
        if (affected != 1) throw new BizException(503, "创建 FAQ 失败，数据库未确认写入");
        Long newId = lastInsertId();
        return getFaq(newId);
    }

    @Transactional
    @CacheEvict(value = "mallPublic", allEntries = true)
    public Map<String, Object> updateFaq(long id, Map<String, Object> data) {
        if (data == null) throw new BizException(400, "FAQ 参数不能为空");
        Map<String, Object> existing = getFaq(id);
        String question = data.containsKey("question")
                ? boundedRequired(data, "question", "问题不能为空", MAX_FAQ_QUESTION_LENGTH)
                : text(existing.get("question"));
        String answer = data.containsKey("answer")
                ? boundedRequired(data, "answer", "答案不能为空", MAX_FAQ_ANSWER_LENGTH)
                : text(existing.get("answer"));
        int sortOrder = data.containsKey("sortOrder")
                ? optionalInt(data.get("sortOrder"), "排序值", -1_000_000, 1_000_000, 0)
                : storedInt(existing.get("sortOrder"), "排序值", -1_000_000, 1_000_000);
        int status = data.containsKey("status")
                ? optionalEnabled(data.get("status"), 1, "FAQ 状态")
                : storedInt(existing.get("status"), "FAQ 状态", 0, 1);
        int affected = safeUpdate("更新 FAQ 失败",
                "UPDATE mall_faq SET question=?, answer=?, sort_order=?, status=?, updated_time=NOW() " +
                        "WHERE id=? AND deleted=0",
                question, answer, sortOrder, status, id);
        if (affected != 1) throw new BizException(404, "FAQ 不存在");
        return getFaq(id);
    }

    @Transactional
    @CacheEvict(value = "mallPublic", allEntries = true)
    public void deleteFaq(long id) {
        int affected = safeUpdate("删除 FAQ 失败",
                "UPDATE mall_faq SET deleted=1, updated_time=NOW() WHERE id=? AND deleted=0", id);
        if (affected != 1) throw new BizException(404, "FAQ 不存在");
    }

    private Map<String, Object> getFaq(long id) {
        Map<String, Object> faq = queryOne(
                "SELECT id, tenant_id AS tenantId, question, answer, sort_order AS sortOrder, status, " +
                        "created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM mall_faq WHERE id=? AND deleted=0", id);
        if (faq == null) throw new BizException(404, "FAQ 不存在");
        return faq;
    }

    // ==================== 用户端：商品 ====================

    /**
     * 用户端商品列表（含 count + records 并行查询 + 深分页延迟关联）。
     */
    public PageResult<Map<String, Object>> listShopProducts(String type, String category, String keyword,
                                                             int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 100);
        int offset = (safeCurrent - 1) * safeSize;
        String normalizedType = StringUtils.hasText(type) ? normalizeProductType(type) : null;
        StringBuilder where = new StringBuilder(" WHERE deleted=0 AND status=1");
        List<Object> args = new ArrayList<>();
        if (StringUtils.hasText(normalizedType)) {
            where.append(" AND product_type=?");
            args.add(normalizedType);
        }
        if (StringUtils.hasText(category)) {
            where.append(" AND category=?");
            args.add(category.trim());
        }
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (title LIKE ? OR subtitle LIKE ? OR content LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw);
        }
        // 并行：count 查询与 records 查询同时发起
        CompletableFuture<Long> totalFuture = CompletableFuture.supplyAsync(
                () -> queryCount("SELECT COUNT(*) FROM mall_product" + where, args), queryPool);
        String recordsSql = buildListShopProductsSql(where, offset);
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add(offset);
        CompletableFuture<List<Map<String, Object>>> recordsFuture = CompletableFuture.supplyAsync(
                () -> jdbcTemplate.queryForList(recordsSql, pageArgs.toArray()), queryPool);
        Long total;
        List<Map<String, Object>> records;
        try {
            total = totalFuture.join();
            records = recordsFuture.join();
        } catch (Exception e) {
            throw new BizException(503, "商品列表查询暂时不可用，请稍后重试");
        }
        // 批量附加库存信息，避免 N+1 查询
        attachStockInfoBatch(records);
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 构造前台商品列表 SQL：OFFSET 较小时直接 LIMIT/OFFSET，OFFSET 较大时改用延迟关联。
     */
    private String buildListShopProductsSql(StringBuilder where, int offset) {
        String selectFields = "id, product_type AS productType, title, subtitle, content, copy, " +
                "price_cent AS priceCent, ROUND(price_cent/100,2) AS priceYuan, " +
                "cover_url AS coverUrl, category, sort_order AS sortOrder, bought_count AS boughtCount, " +
                "created_time AS createdTime";
        if (offset < DEFERRED_JOIN_OFFSET_THRESHOLD) {
            return "SELECT " + selectFields + " FROM mall_product" + where +
                    " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?";
        }
        // 延迟关联：深分页时子查询走覆盖索引跳跃定位 id，再回表取完整字段
        return "SELECT " + selectFields + " FROM mall_product INNER JOIN (" +
                "SELECT id FROM mall_product" + where +
                " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?" +
                ") AS t ON mall_product.id = t.id ORDER BY mall_product.sort_order ASC, mall_product.id DESC";
    }

    public Map<String, Object> getShopProduct(long id) {
        Map<String, Object> product = queryOne(
                "SELECT id, product_type AS productType, title, subtitle, content, copy, " +
                        "delivery_content AS deliveryContent, " +
                        "price_cent AS priceCent, ROUND(price_cent/100,2) AS priceYuan, " +
                        "cover_url AS coverUrl, category, sort_order AS sortOrder, bought_count AS boughtCount, " +
                        "created_time AS createdTime " +
                        "FROM mall_product WHERE id=? AND deleted=0 AND status=1",
                id);
        if (product == null) throw new BizException(404, "商品不存在或已下架");
        // 异步附加库存信息，不阻塞主查询线程
        attachStockInfoAsync(product);
        return product;
    }

    /**
     * 商城前台分类列表（聚合查询）。
     * 缓存：结果缓存到 mallPublic key='categories'。
     * 商品 CRUD 不会显式失效此缓存（写入路径分散），依赖 5min TTL 自然收敛。
     */
    @Cacheable(value = "mallPublic", key = "'categories'")
    public List<Map<String, Object>> listCategories() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT category, COUNT(*) AS product_count FROM mall_product " +
                        "WHERE deleted=0 AND status=1 AND category<>'' GROUP BY category ORDER BY product_count DESC, category ASC");
        List<Map<String, Object>> categories = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("category", row.get("category"));
            item.put("productCount", row.get("product_count"));
            categories.add(item);
        }
        return categories;
    }

    /**
     * 商城前台 FAQ 列表。
     * 缓存：结果缓存到 mallPublic key='shop_faqs'；FAQ CRUD 后失效整个 mallPublic cache。
     */
    @Cacheable(value = "mallPublic", key = "'shop_faqs'")
    public List<Map<String, Object>> listShopFaqs() {
        return jdbcTemplate.queryForList(
                "SELECT id, question, answer, sort_order AS sortOrder " +
                        "FROM mall_faq WHERE deleted=0 AND status=1 ORDER BY sort_order ASC, id DESC");
    }

    // ==================== AI 分类 ====================

    /**
     * 获取闲鱼商品分类树（供后台货源商城新增商品时手动选择分类使用）。
     * 转发到 automation-service 的 /api/xianyu/categories 接口，返回与前台发布商品页面一致的分类树结构。
     *
     * <p>分类树是全局公共数据，与具体租户无关。但 automation-service 的内部认证要求
     * X-Internal-Tenant-Id 必须存在且 > 0。超级管理员（platform admin）的 tenantId 为 null，
     * 因此这里在 tenantId 为空时从 sys_user 表取一个有效 tenantId 作为内部调用凭证。
     * 该 tenantId 仅用于满足内部认证要求，不影响返回的全局分类树内容。</p>
     *
     * <p>缓存：远程调用成本高（30s 超时），结果缓存到 mallPublic key='category_tree'。
     * 分类树变更频率极低，依赖 5min TTL 自然收敛。</p>
     */
    @Cacheable(value = "mallPublic", key = "'category_tree'")
    public Object getCategoryTree() {
        Long tenantId = com.xianyu.admin.security.TenantContext.getCurrentTenantId();
        if (tenantId == null || tenantId <= 0) {
            // 超级管理员：从 sys_user 表取一个有效 tenantId 作为内部调用凭证
            try {
                Long fallback = jdbcTemplate.queryForObject(
                        "SELECT tenant_id FROM sys_user WHERE tenant_id IS NOT NULL AND tenant_id > 0 LIMIT 1",
                        Long.class);
                if (fallback == null || fallback <= 0) {
                    throw new BizException(503, "暂无可用租户，无法获取分类树");
                }
                tenantId = fallback;
            } catch (BizException e) {
                throw e;
            } catch (Exception e) {
                throw new BizException(503, "分类树暂时无法读取，请稍后重试");
            }
        }
        return automationClient.getInternalForData("/api/xianyu/categories", Map.of(), 30, tenantId);
    }

    /**
     * 触发 AI 自动分类。查询所有 category 为空或需要重新分类的商品，
     * 调用 automation-service 的 /api/mall/categorize 接口（批量），
     * 更新商品的 category 和 ai_category_confidence 字段。
     */
    public Map<String, Object> refreshCategories() {
        List<Map<String, Object>> products = jdbcTemplate.queryForList(
                "SELECT id, title, subtitle, content, category FROM mall_product " +
                        "WHERE deleted=0 AND (category='' OR category IS NULL) ORDER BY id ASC LIMIT 200");
        int total = products.size();
        if (total == 0) {
            Map<String, Object> emptyResult = new LinkedHashMap<>();
            emptyResult.put("total", 0);
            emptyResult.put("updated", 0);
            emptyResult.put("failed", 0);
            return emptyResult;
        }

        // 构建批量请求
        List<Map<String, Object>> productBatch = new ArrayList<>();
        Map<Object, Long> idMap = new LinkedHashMap<>();
        for (Map<String, Object> product : products) {
            Map<String, Object> item = new LinkedHashMap<>();
            Object rawId = product.get("id");
            Long productId = ((Number) rawId).longValue();
            item.put("id", productId);
            item.put("title", product.get("title"));
            item.put("content", product.get("content"));
            productBatch.add(item);
            idMap.put(productId, productId);
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("products", productBatch);

        int updated = 0;
        int failed = 0;
        try {
            Map<String, Object> result = automationClient.postInternalForData(
                    "/api/mall/categorize", payload, 60);
            Object resultsObj = result.get("results");
            if (resultsObj instanceof List<?> resultList) {
                for (Object item : resultList) {
                    if (!(item instanceof Map<?, ?> itemMap)) continue;
                    Object idVal = itemMap.get("id");
                    Long productId = null;
                    if (idVal instanceof Number num) {
                        productId = num.longValue();
                    } else if (idVal != null) {
                        try { productId = Long.parseLong(String.valueOf(idVal)); } catch (NumberFormatException ignored) {}
                    }
                    String category = text(itemMap.get("category"));
                    BigDecimal confidence = parseConfidence(itemMap.get("confidence"));
                    if (productId != null && StringUtils.hasText(category)) {
                        safeUpdate("更新商品分类失败",
                                "UPDATE mall_product SET category=?, ai_category_confidence=?, updated_time=NOW() " +
                                        "WHERE id=? AND deleted=0",
                                category, confidence, productId);
                        updated++;
                    } else {
                        failed++;
                    }
                }
            }
        } catch (Exception e) {
            log.warn("AI 批量分类失败, errorType={}", e.getClass().getSimpleName());
            failed = total - updated;
        }

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("total", total);
        summary.put("updated", updated);
        summary.put("failed", failed);
        return summary;
    }

    // ==================== 辅助方法 ====================

    private void attachStockInfo(Map<String, Object> product) {
        Object idValue = product.get("id");
        if (idValue == null) return;
        long productId = storedLong(idValue, "商品 ID", 1, Long.MAX_VALUE);
        Object typeValue = product.get("productType");
        if (typeValue != null && "card".equals(text(typeValue))) {
            Long stock = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM mall_card_key WHERE product_id=? AND status='available'",
                    Long.class, productId);
            product.put("stock", stock == null ? 0 : stock);
        } else {
            // 文本商品库存视为无限
            product.put("stock", -1);
        }
    }

    /**
     * 异步附加库存信息：商品详情查询完成后，库存查询走独立线程，不阻塞主请求线程。
     * 文本商品直接填 -1，不发起 DB 查询；卡密商品并发起一次 COUNT 查询并 join 等待。
     * 单商品详情场景下，相比同步 attachStockInfo 节省一次串行 DB 往返时间。
     */
    private void attachStockInfoAsync(Map<String, Object> product) {
        Object typeValue = product.get("productType");
        if (typeValue == null || !"card".equals(text(typeValue))) {
            product.put("stock", -1);
            return;
        }
        Object idValue = product.get("id");
        if (idValue == null) {
            product.put("stock", -1);
            return;
        }
        long productId;
        try {
            productId = storedLong(idValue, "商品 ID", 1, Long.MAX_VALUE);
        } catch (BizException e) {
            product.put("stock", -1);
            return;
        }
        try {
            Long stock = CompletableFuture.supplyAsync(() -> {
                Long cnt = jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM mall_card_key WHERE product_id=? AND status='available'",
                        Long.class, productId);
                return cnt == null ? 0L : cnt;
            }, queryPool).join();
            product.put("stock", stock);
        } catch (Exception e) {
            log.warn("异步查询商品库存失败, productId={}, errorType={}", productId, e.getClass().getSimpleName());
            product.put("stock", -1);
        }
    }

    /**
     * 批量为商品列表附加库存信息（避免 N+1 查询）。
     * 卡密商品一次 IN 查询聚合所有库存，文本商品直接标记为无限。
     */
    private void attachStockInfoBatch(List<Map<String, Object>> products) {
        if (products == null || products.isEmpty()) return;
        // 收集所有卡密商品的 ID
        List<Long> cardProductIds = new ArrayList<>();
        for (Map<String, Object> product : products) {
            Object typeValue = product.get("productType");
            if (typeValue != null && "card".equals(text(typeValue))) {
                Object idValue = product.get("id");
                if (idValue != null) {
                    try {
                        cardProductIds.add(storedLong(idValue, "商品 ID", 1, Long.MAX_VALUE));
                    } catch (BizException ignored) { /* 跳过异常 ID */ }
                }
            }
        }
        // 一次 GROUP BY 查询所有卡密商品库存
        Map<Long, Long> stockMap = new java.util.HashMap<>();
        if (!cardProductIds.isEmpty()) {
            String placeholders = String.join(",", java.util.Collections.nCopies(cardProductIds.size(), "?"));
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT product_id, COUNT(*) AS cnt FROM mall_card_key " +
                            "WHERE status='available' AND product_id IN (" + placeholders + ") " +
                            "GROUP BY product_id",
                    cardProductIds.toArray());
            for (Map<String, Object> row : rows) {
                Object pid = row.get("product_id");
                Object cnt = row.get("cnt");
                if (pid != null && cnt != null) {
                    stockMap.put(((Number) pid).longValue(), ((Number) cnt).longValue());
                }
            }
        }
        // 回填到每条商品记录
        for (Map<String, Object> product : products) {
            Object typeValue = product.get("productType");
            if (typeValue != null && "card".equals(text(typeValue))) {
                Object idValue = product.get("id");
                long stock = 0;
                if (idValue != null) {
                    try {
                        long productId = storedLong(idValue, "商品 ID", 1, Long.MAX_VALUE);
                        stock = stockMap.getOrDefault(productId, 0L);
                    } catch (BizException ignored) { /* 默认 0 */ }
                }
                product.put("stock", stock);
            } else {
                // 文本商品库存视为无限
                product.put("stock", -1);
            }
        }
    }

    /**
     * 查询用户是否已购买指定商城商品（已支付订单）。
     */
    public boolean hasUserPurchased(long userId, long productId) {
        try {
            Long count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM payment_order WHERE user_id=? AND order_type='mall_product' " +
                            "AND target_id=? AND status=1 AND deleted=0",
                    Long.class, userId, productId);
            return count != null && count > 0;
        } catch (DataAccessException e) {
            log.warn("查询用户购买状态失败, userId={}, productId={}, errorType={}", userId, productId, e.getClass().getSimpleName());
            return false;
        }
    }

    /**
     * 批量为商品列表附加 purchased 字段（用户是否已购买）。
     * 使用 IN 批量查询替代循环单查，避免 N+1 性能问题。
     * 单个商品 ID 异常不影响整体列表，降级为 false。
     */
    public void attachPurchasedInfo(List<Map<String, Object>> products, long userId) {
        if (products == null || products.isEmpty() || userId <= 0) {
            if (products != null) {
                for (Map<String, Object> product : products) {
                    product.put("purchased", false);
                }
            }
            return;
        }
        // 收集所有合法商品 ID
        List<Long> productIds = new ArrayList<>();
        Map<Long, Map<String, Object>> idToProduct = new java.util.HashMap<>();
        for (Map<String, Object> product : products) {
            Object idValue = product.get("id");
            if (idValue == null) {
                product.put("purchased", false);
                continue;
            }
            try {
                long productId = storedLong(idValue, "商品 ID", 1, Long.MAX_VALUE);
                productIds.add(productId);
                idToProduct.put(productId, product);
                product.put("purchased", false); // 默认 false，命中后覆盖
            } catch (BizException e) {
                product.put("purchased", false);
            }
        }
        if (productIds.isEmpty()) return;
        // 一次 IN 查询所有已购商品 ID
        String placeholders = String.join(",", java.util.Collections.nCopies(productIds.size(), "?"));
        List<Object> args = new ArrayList<>(productIds);
        args.add(0, userId);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT DISTINCT target_id FROM payment_order " +
                        "WHERE user_id=? AND order_type='mall_product' " +
                        "AND target_id IN (" + placeholders + ") AND status=1 AND deleted=0",
                args.toArray());
        for (Map<String, Object> row : rows) {
            Object tid = row.get("target_id");
            if (tid != null) {
                long pid = ((Number) tid).longValue();
                Map<String, Object> product = idToProduct.get(pid);
                if (product != null) {
                    product.put("purchased", true);
                }
            }
        }
    }

    /**
     * 为单个商品附加 purchased 字段。
     */
    public void attachPurchasedInfo(Map<String, Object> product, long userId) {
        if (product == null || userId <= 0) return;
        Object idValue = product.get("id");
        if (idValue == null) return;
        try {
            long productId = storedLong(idValue, "商品 ID", 1, Long.MAX_VALUE);
            product.put("purchased", hasUserPurchased(userId, productId));
        } catch (BizException e) {
            product.put("purchased", false);
        }
    }

    private String normalizeProductType(String value) {
        if (!StringUtils.hasText(value)) return "";
        String t = value.trim().toLowerCase(Locale.ROOT);
        if ("text".equals(t) || "card".equals(t)) return t;
        throw new BizException(400, "非法商品类型，仅支持 text 或 card");
    }

    private long parseMoneyCent(Map<String, Object> data) {
        Object cent = first(data, "priceCent", "price_cent", "amountCent", "amount_cent");
        if (cent != null && !String.valueOf(cent).isBlank()) {
            return requireWholeNumber(cent, "价格（分）", 0, MAX_PRICE_CENT);
        }
        Object yuan = first(data, "priceYuan", "price", "amount");
        if (yuan == null || String.valueOf(yuan).isBlank()) {
            throw new BizException(400, "商品价格不能为空");
        }
        try {
            String normalized = String.valueOf(yuan).replace("¥", "").replace("元", "").trim();
            long cents = new BigDecimal(normalized).movePointRight(2).longValueExact();
            if (cents < 0 || cents > MAX_PRICE_CENT) throw new BizException(400, "商品价格超出允许范围");
            return cents;
        } catch (BizException e) {
            throw e;
        } catch (RuntimeException e) {
            throw new BizException(400, "商品价格最多保留两位小数");
        }
    }

    private BigDecimal parseConfidence(Object value) {
        if (value == null || String.valueOf(value).isBlank()) return BigDecimal.ZERO;
        try {
            BigDecimal decimal = value instanceof BigDecimal bd ? bd : new BigDecimal(String.valueOf(value).trim());
            if (decimal.compareTo(BigDecimal.ZERO) < 0 || decimal.compareTo(new BigDecimal("100")) > 0) {
                return BigDecimal.ZERO;
            }
            return decimal;
        } catch (RuntimeException e) {
            return BigDecimal.ZERO;
        }
    }

    private Long queryCount(String sql, List<Object> args) {
        try {
            Long count = jdbcTemplate.queryForObject(sql, Long.class, args.toArray());
            return count == null ? 0L : count;
        } catch (DataAccessException e) {
            throw new BizException(503, "数据统计暂时不可用，请稍后重试");
        }
    }

    private Map<String, Object> queryOne(String sql, Object... args) {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, args);
            return rows.isEmpty() ? null : rows.get(0);
        } catch (DataAccessException e) {
            throw new BizException(503, "数据暂时无法读取，请稍后重试");
        }
    }

    private Long lastInsertId() {
        try {
            Long newId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
            if (newId == null || newId <= 0) {
                throw new BizException(503, "记录已写入但无法确认记录编号，请稍后核验");
            }
            return newId;
        } catch (DataAccessException e) {
            throw new BizException(503, "记录已写入但无法确认记录编号，请稍后核验");
        }
    }

    private int safeUpdate(String unavailableMessage, String sql, Object... args) {
        try {
            return jdbcTemplate.update(sql, args);
        } catch (DataAccessException e) {
            throw new BizException(503, unavailableMessage + "，请稍后重试");
        }
    }

    private Object first(Map<String, Object> data, String... keys) {
        if (data == null) return null;
        for (String k : keys) if (data.containsKey(k)) return data.get(k);
        return null;
    }

    private String required(Map<String, Object> data, String key, String msg) {
        Object value = first(data, key);
        if (value == null || String.valueOf(value).isBlank()) throw new BizException(400, msg);
        return String.valueOf(value).trim();
    }

    private String boundedRequired(Map<String, Object> data, String key, String msg, int maxLength) {
        String value = required(data, key, msg);
        if (value.length() > maxLength) throw new BizException(400, msg + "，且不能超过 " + maxLength + " 个字符");
        return value;
    }

    private String boundedOptional(Map<String, Object> data, String key, int maxLength) {
        Object value = first(data, key);
        String text = value == null ? "" : String.valueOf(value).trim();
        if (text.length() > maxLength) throw new BizException(400, key + " 不能超过 " + maxLength + " 个字符");
        return text;
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private long requireWholeNumber(Object value, String field, long min, long max) {
        if (value == null || String.valueOf(value).isBlank()) throw new BizException(400, field + "不能为空");
        try {
            BigDecimal decimal = value instanceof BigDecimal bd ? bd : new BigDecimal(String.valueOf(value).trim());
            long parsed = decimal.longValueExact();
            if (parsed < min || parsed > max) throw new BizException(400, field + "超出允许范围");
            return parsed;
        } catch (BizException e) {
            throw e;
        } catch (RuntimeException e) {
            throw new BizException(400, field + "必须是合法整数");
        }
    }

    private long storedLong(Object value, String field, long min, long max) {
        try {
            if (value == null || String.valueOf(value).isBlank()) throw new ArithmeticException();
            BigDecimal decimal = value instanceof BigDecimal bd ? bd : new BigDecimal(String.valueOf(value).trim());
            long parsed = decimal.longValueExact();
            if (parsed < min || parsed > max) throw new ArithmeticException();
            return parsed;
        } catch (RuntimeException e) {
            throw new BizException(503, field + "数据异常，请联系管理员核验");
        }
    }

    private int storedInt(Object value, String field, int min, int max) {
        return (int) storedLong(value, field, min, max);
    }

    private int optionalInt(Object value, String field, int min, int max, int defaultValue) {
        if (value == null || String.valueOf(value).isBlank()) return defaultValue;
        return (int) requireWholeNumber(value, field, min, max);
    }

    private int optionalEnabled(Object value, int defaultValue, String field) {
        if (value == null || String.valueOf(value).isBlank()) return defaultValue;
        String s = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        if ("1".equals(s) || "true".equals(s) || "启用".equals(s) || "上架".equals(s)) return 1;
        if ("0".equals(s) || "false".equals(s) || "禁用".equals(s) || "下架".equals(s)) return 0;
        try {
            int parsed = Integer.parseInt(s);
            if (parsed == 0 || parsed == 1) return parsed;
        } catch (NumberFormatException ignored) {}
        throw new BizException(400, field + "只能为启用或禁用");
    }

    @SuppressWarnings("unused")
    private boolean equalsText(Object a, Object b) {
        return Objects.equals(text(a), text(b));
    }
}
