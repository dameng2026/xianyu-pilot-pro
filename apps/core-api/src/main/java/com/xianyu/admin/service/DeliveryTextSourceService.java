package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.service.XianyuAccountService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class DeliveryTextSourceService {
    private final JdbcTemplate jdbcTemplate;
    private final AiProviderService aiProviderService;
    private final ObjectMapper objectMapper;
    private final DeliveryGoodsConfigService goodsConfigService;

    public DeliveryTextSourceService(JdbcTemplate jdbcTemplate,
                                     AiProviderService aiProviderService,
                                     ObjectMapper objectMapper,
                                     DeliveryGoodsConfigService goodsConfigService) {
        this.jdbcTemplate = jdbcTemplate;
        this.aiProviderService = aiProviderService;
        this.objectMapper = objectMapper;
        this.goodsConfigService = goodsConfigService;
    }

    public PageResult<Map<String, Object>> page(Long tenantId, String keyword, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        String kw = keyword == null ? "" : keyword.trim();

        String filter = kw.isBlank() ? "" : " AND (s.title LIKE CONCAT('%', ?, '%') OR s.content LIKE CONCAT('%', ?, '%') OR s.remark LIKE CONCAT('%', ?, '%') OR (s.from_mall=1 AND mp.title LIKE CONCAT('%', ?, '%')))";
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        if (!kw.isBlank()) {
            args.add(kw);
            args.add(kw);
            args.add(kw);
            args.add(kw);
        }

        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM delivery_text_source s LEFT JOIN mall_product mp ON mp.id=s.mall_product_id AND mp.deleted=0 " +
                        "WHERE s.tenant_id=? AND s.deleted=0" + filter,
                Long.class,
                args.toArray()
        );

        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(offset);
        listArgs.add(safeSize);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT s.id, s.source_type AS sourceType, s.delivery_mode AS deliveryMode, s.card_group_id AS cardGroupId, " +
                        "s.title, s.content, s.remark, s.segments AS segments, s.from_mall AS fromMall, s.mall_product_id AS mallProductId, s.created_time AS createdTime, s.updated_time AS updatedTime, " +
                        "g.group_name AS cardGroupName, g.remain_count AS cardRemainCount, " +
                        "mp.title AS mallProductTitle, mp.content AS mallProductContent, mp.status AS mallProductStatus " +
                        "FROM delivery_text_source s " +
                        "LEFT JOIN card_group g ON g.id=s.card_group_id AND g.tenant_id=s.tenant_id AND g.deleted=0 " +
                        "LEFT JOIN mall_product mp ON mp.id=s.mall_product_id AND mp.deleted=0 " +
                        "WHERE s.tenant_id=? AND s.deleted=0" + filter +
                        " ORDER BY s.updated_time DESC, s.id DESC LIMIT ?, ?",
                listArgs.toArray()
        );
        enrichUsageStats(tenantId, rows);
        for (Map<String, Object> row : rows) {
            // segments 在数据库中是 JSON 字符串，解析为 List 后返回前端
            row.put("segments", parseSegmentsJson(text(row.get("segments"))));
            applyMallProductSnapshot(row);
            row.put("stockLabel", buildStockLabel(row));
        }
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    /**
     * 根据商城货源商品 ID 查询当前租户会员库中对应的货源记录。
     * 用于用户从货源商城上架商品后，前端自动绑定该货源到新上架的闲鱼商品。
     * 返回 null 表示当前租户尚未购买该商城货源（不应出现，因为只有购买后才能上架）。
     */
    public Map<String, Object> findByMallProduct(Long tenantId, Long mallProductId) {
        if (tenantId == null || mallProductId == null || mallProductId <= 0) return null;
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT s.id, s.title, s.delivery_mode AS deliveryMode, s.from_mall AS fromMall, s.mall_product_id AS mallProductId " +
                            "FROM delivery_text_source s " +
                            "WHERE s.tenant_id=? AND s.from_mall=1 AND s.mall_product_id=? AND s.deleted=0 " +
                            "ORDER BY s.id DESC LIMIT 1",
                    tenantId, mallProductId);
            return rows.isEmpty() ? null : rows.get(0);
        } catch (Exception e) {
            return null;
        }
    }

    public Map<String, Object> detail(Long tenantId, Long sourceId) {
        Map<String, Object> source = jdbcTemplate.queryForMap(
                "SELECT s.id, s.source_type AS sourceType, s.delivery_mode AS deliveryMode, s.card_group_id AS cardGroupId, " +
                        "s.title, s.content, s.remark, s.segments AS segments, s.from_mall AS fromMall, s.mall_product_id AS mallProductId, s.created_time AS createdTime, s.updated_time AS updatedTime, " +
                        "g.group_name AS cardGroupName, g.remain_count AS cardRemainCount, " +
                        "mp.title AS mallProductTitle, mp.content AS mallProductContent, mp.status AS mallProductStatus " +
                        "FROM delivery_text_source s " +
                        "LEFT JOIN card_group g ON g.id=s.card_group_id AND g.tenant_id=s.tenant_id AND g.deleted=0 " +
                        "LEFT JOIN mall_product mp ON mp.id=s.mall_product_id AND mp.deleted=0 " +
                        "WHERE s.tenant_id=? AND s.id=? AND s.deleted=0",
                tenantId, sourceId
        );
        // segments 在数据库中是 JSON 字符串，解析为 List 后返回前端
        source.put("segments", parseSegmentsJson(text(source.get("segments"))));
        applyMallProductSnapshot(source);
        source.put("configuredGoods", listConfiguredGoods(tenantId, sourceId));
        source.put("usageCount", ((List<?>) source.get("configuredGoods")).size());
        source.put("stockLabel", buildStockLabel(source));
        return source;
    }

    public Long create(Long tenantId, Map<String, Object> body) {
        String deliveryMode = normalizeDeliveryMode(body.get("deliveryMode"));
        Long cardGroupId = "card".equals(deliveryMode) ? asLong(body.get("cardGroupId")) : null;
        // 仅文本模式支持 segments（多条正文 + 图片发货）；卡密模式保持单条模板语义
        String segmentsJson = "text".equals(deliveryMode) ? serializeSegments(body.get("segments")) : null;
        jdbcTemplate.update(
                "INSERT INTO delivery_text_source(tenant_id, source_type, delivery_mode, card_group_id, title, content, remark, segments, from_mall, mall_product_id, created_time, updated_time, deleted) " +
                        "VALUES(?, 'text', ?, ?, ?, ?, ?, ?, 0, NULL, NOW(), NOW(), 0)",
                tenantId, deliveryMode, cardGroupId, text(body.get("title")), text(body.get("content")), text(body.get("remark")), segmentsJson
        );
        return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    }

    public void update(Long tenantId, Long sourceId, Map<String, Object> body) {
        Map<String, Object> existing = jdbcTemplate.queryForList(
                "SELECT from_mall AS fromMall FROM delivery_text_source WHERE tenant_id=? AND id=? AND deleted=0",
                tenantId, sourceId
        ).stream().findFirst().orElse(null);
        if (existing == null) {
            throw new com.xianyu.admin.common.BizException(404, "货源不存在或已删除");
        }
        boolean isMall = isMallSource(existing.get("fromMall"));
        // 商城货源可编辑标题/正文/备注，但发货类型固定为文本模式（不可改为卡密）
        String deliveryMode = isMall ? "text" : normalizeDeliveryMode(body.get("deliveryMode"));
        Long cardGroupId = "card".equals(deliveryMode) ? asLong(body.get("cardGroupId")) : null;
        String segmentsJson = "text".equals(deliveryMode) ? serializeSegments(body.get("segments")) : null;
        jdbcTemplate.update(
                "UPDATE delivery_text_source SET delivery_mode=?, card_group_id=?, title=?, content=?, remark=?, segments=?, updated_time=NOW() " +
                        "WHERE tenant_id=? AND id=? AND deleted=0",
                deliveryMode, cardGroupId, text(body.get("title")), text(body.get("content")), text(body.get("remark")), segmentsJson, tenantId, sourceId
        );
    }

    public void delete(Long tenantId, Long sourceId) {
        jdbcTemplate.update("UPDATE delivery_text_source SET deleted=1, updated_time=NOW() WHERE tenant_id=? AND id=? AND deleted=0", tenantId, sourceId);
    }

    public List<Map<String, Object>> listConfiguredGoods(Long tenantId, Long sourceId) {
        List<Map<String, Object>> configured = new ArrayList<>();
        for (Map<String, Object> goods : candidateGoods(tenantId)) {
            if (configUsesSource(readGoodsConfig(tenantId, asLong(goods.get("id"))), sourceId)) {
                configured.add(goods);
            }
        }
        return configured;
    }

    public List<Map<String, Object>> candidateGoods(Long tenantId) {
        return jdbcTemplate.queryForList(
                "SELECT g.id, g.account_id AS accountId, g.external_goods_id AS externalGoodsId, g.title, g.description, " +
                        "g.detail_info AS detailInfo, g.category, g.price, g.cover_pic AS coverPic, g.image_url AS imageUrl, g.status, " +
                        "a.avatar_url AS accountAvatarUrl, a.nickname AS accountNickname, a.display_name AS accountDisplayName, " +
                        "a.remark AS accountRemark, a.external_uid AS accountExternalUid " +
                        "FROM xianyu_goods g " +
                        "LEFT JOIN xianyu_account a ON a.id=g.account_id AND a.deleted=0 " +
                        "WHERE g.tenant_id=? AND g.deleted=0 ORDER BY g.updated_time DESC, g.id DESC",
                tenantId
        ).stream().map(this::normalizeGoodsRow).toList();
    }

    public Map<String, Object> recommendGoods(Long tenantId, Long sourceId) {
        Map<String, Object> source = detail(tenantId, sourceId);
        List<Map<String, Object>> ranked = rankCandidates(source, candidateGoods(tenantId));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("source", source);
        result.put("configuredGoods", listConfiguredGoods(tenantId, sourceId));
        result.put("candidates", ranked);
        result.put("aiEnabled", aiProviderService.isConfigured());
        result.put("message", aiProviderService.isConfigured() ? "AI 已分析并给出建议商品" : "AI 未配置，已按标题和正文进行本地匹配");
        return result;
    }

    public void applySourceToGoods(Long tenantId, Long sourceId, List<Long> goodsIds, String timing) {
        Map<String, Object> source = detail(tenantId, sourceId);
        String deliveryMode = normalizeDeliveryMode(source.get("deliveryMode"));
        Map<String, Object> patch = new LinkedHashMap<>();
        patch.put("timing", normalizeTiming(timing));
        patch.put("enabled", 1);
        patch.put("mode", deliveryMode);
        patch.put("sourceId", sourceId);
        patch.put("sourceTitle", source.get("title"));
        patch.put("content", text(source.get("content")));
        // 透传 segments 到商品配置 config_json.payDelivery.segments（仅文本模式有值）
        Object segments = source.get("segments");
        if (segments instanceof List<?> list && !list.isEmpty()) {
            patch.put("segments", list);
        } else {
            // 显式置空，避免旧商品配置中残留的 segments 干扰
            patch.put("segments", null);
        }
        if ("card".equals(deliveryMode)) {
            patch.put("cardGroupId", asLong(source.get("cardGroupId")));
        }
        goodsConfigService.apply(tenantId, goodsIds, patch);
    }

    public void removeGoodsFromSource(Long tenantId, Long sourceId, Long goodsId) {
        detail(tenantId, sourceId);
        goodsConfigService.removeSourceBinding(tenantId, goodsId, sourceId);
    }

    private void enrichUsageStats(Long tenantId, List<Map<String, Object>> rows) {
        if (rows == null || rows.isEmpty()) {
            return;
        }
        Map<Long, Integer> usageMap = new LinkedHashMap<>();
        for (Map<String, Object> row : rows) {
            usageMap.put(asLong(row.get("id")), 0);
        }
        for (Map<String, Object> goods : candidateGoods(tenantId)) {
            for (Long sourceId : extractSourceIds(readGoodsConfig(tenantId, asLong(goods.get("id"))))) {
                if (usageMap.containsKey(sourceId)) {
                    usageMap.put(sourceId, usageMap.get(sourceId) + 1);
                }
            }
        }
        for (Map<String, Object> row : rows) {
            row.put("usageCount", usageMap.getOrDefault(asLong(row.get("id")), 0));
        }
    }

    private List<Map<String, Object>> rankCandidates(Map<String, Object> source, List<Map<String, Object>> candidates) {
        String title = text(source.get("title"));
        String content = text(source.get("content"));
        String remark = text(source.get("remark"));

        List<Map<String, Object>> ranked = candidates.stream()
                .map(candidate -> {
                    Map<String, Object> row = new LinkedHashMap<>(candidate);
                    int localScore = matchScore(title, content, remark, candidate);
                    row.put("score", localScore);
                    row.put("confidence", scoreToConfidence(localScore));
                    row.put("reason", buildReason(localScore));
                    row.put("recommended", localScore >= 25);
                    return row;
                })
                .sorted(Comparator.comparingInt((Map<String, Object> row) -> ((Number) row.getOrDefault("score", 0)).intValue()).reversed())
                .collect(Collectors.toList());

        if (!aiProviderService.isConfigured()) {
            return ranked.stream().filter(row -> Boolean.TRUE.equals(row.get("recommended"))).limit(50).collect(Collectors.toList());
        }

        List<Map<String, Object>> top = ranked.stream().limit(80).collect(Collectors.toList());
        Map<String, Object> aiMatch = askAiForMatches(source, top);
        @SuppressWarnings("unchecked")
        Set<Long> matchedIds = aiMatch == null ? Set.of() : (Set<Long>) aiMatch.getOrDefault("matchedIds", Set.of());
        @SuppressWarnings("unchecked")
        Map<Long, String> aiReasons = aiMatch == null ? Map.of() : (Map<Long, String>) aiMatch.getOrDefault("reasons", Map.of());
        for (Map<String, Object> row : top) {
            Long id = asLong(row.get("id"));
            if (id != null && matchedIds.contains(id)) {
                row.put("recommended", true);
                row.put("confidence", "high");
                row.put("reason", aiReasons.getOrDefault(id, text(row.get("reason"))));
                row.put("score", ((Number) row.getOrDefault("score", 0)).intValue() + 30);
            }
        }
        return top.stream().filter(row -> Boolean.TRUE.equals(row.get("recommended"))).collect(Collectors.toList());
    }

    private Map<String, Object> askAiForMatches(Map<String, Object> source, List<Map<String, Object>> candidates) {
        try {
            StringBuilder candidateLines = new StringBuilder();
            for (Map<String, Object> candidate : candidates) {
                candidateLines.append(candidate.get("id")).append(" | ")
                        .append(text(candidate.get("title"))).append(" | ")
                        .append(text(candidate.get("category"))).append(" | ")
                        .append(text(candidate.get("description"))).append("\n");
            }
            String system = "You are a delivery source matching assistant. Pick the best matching goods and return JSON only.";
            String user = "Source title: " + text(source.get("title")) +
                    "\nSource content: " + text(source.get("content")) +
                    "\nSource remark: " + text(source.get("remark")) +
                    "\nCandidates:\n" + candidateLines +
                    "\nReturn format: {\"matches\":[{\"id\":123,\"reason\":\"short reason\"}]}";
            Map<String, Object> ai = aiProviderService.generateText("delivery_source_match", system, user, 0.1D, false);
            if (!Boolean.TRUE.equals(ai.get("ok"))) {
                return null;
            }
            Map<String, Object> parsed = parseJsonObject(String.valueOf(ai.getOrDefault("content", "")));
            Object matchesObj = parsed.get("matches");
            if (!(matchesObj instanceof List<?> matches)) {
                return null;
            }
            Set<Long> ids = new LinkedHashSet<>();
            Map<Long, String> reasons = new LinkedHashMap<>();
            for (Object item : matches) {
                if (!(item instanceof Map<?, ?> match)) {
                    continue;
                }
                Long id = asLong(match.get("id"));
                if (id != null) {
                    ids.add(id);
                    reasons.put(id, text(match.get("reason")));
                }
            }
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("matchedIds", ids);
            result.put("reasons", reasons);
            return result;
        } catch (Exception ignored) {
            return null;
        }
    }

    private String scoreToConfidence(int score) {
        if (score >= 60) return "high";
        if (score >= 35) return "medium";
        return "low";
    }

    private String buildReason(int score) {
        if (score >= 60) return "标题和正文关键词高度重合，适合直接绑定";
        if (score >= 35) return "与商品标题或描述存在明显相关性，建议人工确认后绑定";
        return "仅存在少量关键词交集";
    }

    private int matchScore(String sourceTitle, String sourceContent, String sourceRemark, Map<String, Object> candidate) {
        String source = normalize(sourceTitle + " " + sourceContent + " " + sourceRemark);
        String target = normalize(
                text(candidate.get("title")) + " " +
                        text(candidate.get("description")) + " " +
                        text(candidate.get("detailInfo")) + " " +
                        text(candidate.get("category"))
        );
        if (source.isBlank() || target.isBlank()) {
            return 0;
        }
        int score = 0;
        for (String token : splitTokens(sourceTitle + " " + sourceContent + " " + sourceRemark)) {
            if (token.length() >= 2 && target.contains(token)) {
                score += 8 + Math.min(token.length(), 8);
            }
        }
        return score + overlap(source, target);
    }

    private int overlap(String source, String target) {
        Set<Character> seen = new LinkedHashSet<>();
        int score = 0;
        for (int i = 0; i < source.length(); i++) {
            char ch = source.charAt(i);
            if (Character.isWhitespace(ch) || !seen.add(ch)) {
                continue;
            }
            if (target.indexOf(ch) >= 0) {
                score++;
            }
        }
        return Math.min(score, 18);
    }

    private List<String> splitTokens(String text) {
        return List.of(normalize(text).split("[^\\p{IsAlphabetic}\\p{IsDigit}\\p{IsIdeographic}]+"))
                .stream()
                .filter(token -> token != null && !token.isBlank())
                .distinct()
                .collect(Collectors.toList());
    }

    private String normalize(String text) {
        return text == null ? "" : text.toLowerCase(Locale.ROOT)
                .replace(" ", "")
                .replace("\n", "")
                .replace("\r", "")
                .replace("-", "")
                .replace("_", "")
                .trim();
    }

    private Map<String, Object> parseJsonObject(String content) {
        try {
            String text = content == null ? "" : content.trim();
            int start = text.indexOf('{');
            int end = text.lastIndexOf('}');
            if (start >= 0 && end > start) {
                text = text.substring(start, end + 1);
            }
            return objectMapper.readValue(text, new TypeReference<LinkedHashMap<String, Object>>() {});
        } catch (Exception ignored) {
            return new LinkedHashMap<>();
        }
    }

    private Set<Long> extractSourceIds(Map<String, Object> config) {
        if (config == null || config.isEmpty()) {
            return Set.of();
        }
        Set<Long> ids = new LinkedHashSet<>();
        for (String key : List.of("payDelivery", "confirmDelivery", "reviewDelivery")) {
            Object timingObj = config.get(key);
            if (timingObj instanceof Map<?, ?> timingMap) {
                Long sourceId = asLong(timingMap.get("sourceId"));
                if (sourceId != null) {
                    ids.add(sourceId);
                }
            }
        }
        return ids;
    }

    private boolean configUsesSource(Map<String, Object> config, Long sourceId) {
        return sourceId != null && extractSourceIds(config).contains(sourceId);
    }

    private Map<String, Object> readGoodsConfig(Long tenantId, Long goodsId) {
        return goodsConfigService.read(tenantId, goodsId);
    }

    private String normalizeTiming(String timing) {
        if (timing == null || timing.isBlank()) {
            return "payDelivery";
        }
        return switch (timing) {
            case "confirmDelivery", "after_receipt" -> "confirmDelivery";
            case "reviewDelivery", "after_review" -> "reviewDelivery";
            default -> "payDelivery";
        };
    }

    private String normalizeDeliveryMode(Object value) {
        if (value == null) return "text";
        String mode = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        return "card".equals(mode) ? "card" : "text";
    }

    /**
     * 序列化前端传入的 segments 数组为 JSON 字符串用于持久化。
     * 校验规则（强约束，违反抛 422）：
     *   - 必须是数组，最多 20 条（防止滥用）
     *   - 每个 segment 必须含 type ∈ {text, image}
     *   - type=text  : content 必填且非空（最长 5000），imageUrl 必须为空
     *   - type=image : imageUrl 必填且非空（最长 500），content 必须为空
     * 返回 null 表示空数组或 null 输入（回退 content 单条发送）。
     */
    private String serializeSegments(Object raw) {
        if (raw == null) return null;
        if (!(raw instanceof List<?> rawList)) {
            throw new com.xianyu.admin.common.BizException(422, "正文配置格式错误，应为数组");
        }
        if (rawList.isEmpty()) return null;
        if (rawList.size() > 20) {
            throw new com.xianyu.admin.common.BizException(422, "正文条数过多，最多支持 20 条");
        }
        List<Map<String, Object>> normalized = new ArrayList<>(rawList.size());
        for (int i = 0; i < rawList.size(); i++) {
            Object item = rawList.get(i);
            if (!(item instanceof Map<?, ?> rawMap)) {
                throw new com.xianyu.admin.common.BizException(422, "第 " + (i + 1) + " 条正文格式错误，应为对象");
            }
            Object typeVal = rawMap.get("type");
            String type = String.valueOf(typeVal != null ? typeVal : "text").trim().toLowerCase(Locale.ROOT);
            String content = text(rawMap.get("content"));
            String imageUrl = text(rawMap.get("imageUrl"));
            if ("image".equals(type)) {
                if (imageUrl.isBlank()) {
                    throw new com.xianyu.admin.common.BizException(422, "第 " + (i + 1) + " 条正文为图片类型，必须上传图片");
                }
                if (!content.isBlank()) {
                    throw new com.xianyu.admin.common.BizException(422, "第 " + (i + 1) + " 条正文为图片类型，不能同时填写文本（每条只能文本或图片二选一）");
                }
                if (imageUrl.length() > 500) {
                    throw new com.xianyu.admin.common.BizException(422, "第 " + (i + 1) + " 条正文图片地址过长");
                }
            } else {
                if (!"text".equals(type)) {
                    throw new com.xianyu.admin.common.BizException(422, "第 " + (i + 1) + " 条正文类型无效，仅支持 text 或 image");
                }
                if (content.isBlank()) {
                    throw new com.xianyu.admin.common.BizException(422, "第 " + (i + 1) + " 条正文内容不能为空");
                }
                if (!imageUrl.isBlank()) {
                    throw new com.xianyu.admin.common.BizException(422, "第 " + (i + 1) + " 条正文为文本类型，不能同时上传图片（每条只能文本或图片二选一）");
                }
                if (content.length() > 5000) {
                    throw new com.xianyu.admin.common.BizException(422, "第 " + (i + 1) + " 条正文内容超过 5000 字符");
                }
            }
            Map<String, Object> seg = new LinkedHashMap<>();
            seg.put("type", type);
            if ("image".equals(type)) {
                seg.put("imageUrl", imageUrl);
                Object assetId = rawMap.get("assetId");
                if (assetId != null) seg.put("assetId", asLong(assetId));
            } else {
                seg.put("content", content);
            }
            normalized.add(seg);
        }
        try {
            return objectMapper.writeValueAsString(normalized);
        } catch (Exception e) {
            throw new com.xianyu.admin.common.BizException(500, "正文配置序列化失败");
        }
    }

    /**
     * 解析数据库中的 segments JSON 字符串为 List。
     * 解析失败或为空时返回空 List（执行端会回退到 content 单条发送）。
     */
    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> parseSegmentsJson(String json) {
        if (json == null || json.isBlank()) return java.util.Collections.emptyList();
        try {
            List<?> parsed = objectMapper.readValue(json, new TypeReference<List<?>>() {});
            List<Map<String, Object>> result = new ArrayList<>(parsed.size());
            for (Object item : parsed) {
                if (item instanceof Map<?, ?> map) {
                    Map<String, Object> seg = new LinkedHashMap<>();
                    Object typeVal = map.get("type");
                    seg.put("type", String.valueOf(typeVal != null ? typeVal : "text").toLowerCase(Locale.ROOT));
                    if ("image".equals(seg.get("type"))) {
                        seg.put("imageUrl", text(map.get("imageUrl")));
                        Object assetId = map.get("assetId");
                        if (assetId != null) seg.put("assetId", asLong(assetId));
                    } else {
                        seg.put("content", text(map.get("content")));
                    }
                    result.add(seg);
                }
            }
            return result;
        } catch (Exception e) {
            return java.util.Collections.emptyList();
        }
    }

    private String buildStockLabel(Map<String, Object> row) {
        if (isMallSource(row.get("fromMall"))) {
            return "商城货源";
        }
        String mode = normalizeDeliveryMode(row.get("deliveryMode"));
        if ("card".equals(mode)) {
            Object remain = row.get("cardRemainCount");
            int remainCount = remain instanceof Number number ? number.intValue() : 0;
            String groupName = text(row.get("cardGroupName"));
            return groupName.isBlank() ? ("剩余 " + remainCount) : (groupName + " · 剩余 " + remainCount);
        }
        return "文本";
    }

    /**
     * 商城购买货源的标题与内容保留用户自定义（可编辑），mall_product 内容作为只读参考。
     * - 标题/正文优先用 delivery_text_source 的用户自定义值；为空时 fallback 到 mall_product 的后台内容
     * - mallProductTitle/mallProductContent/mallProductOnline 字段供前端只读板块展示后台配置
     * - 商品下架/删除时，后台内容板块提示"商品已下架或被删除"，用户自定义内容保留不变
     * 同时附加 fromMallLabel 字段，便于前端展示来源徽章
     */
    private void applyMallProductSnapshot(Map<String, Object> row) {
        boolean isMall = isMallSource(row.get("fromMall"));
        row.put("fromMall", isMall);
        row.put("fromMallLabel", isMall ? "商城购买" : "自有");
        if (!isMall) {
            return;
        }
        Object mallProductStatus = row.get("mallProductStatus");
        boolean productOnline = mallProductStatus instanceof Number number && number.intValue() == 1;
        String mpTitle = text(row.get("mallProductTitle"));
        String mpContent = text(row.get("mallProductContent"));
        // 后台内容快照（供前端只读板块展示，商品下架时给出提示）
        row.put("mallProductTitle", mpTitle);
        row.put("mallProductContent", productOnline ? mpContent : "【商品已下架或被删除】该货源内容暂不可用，请联系管理员");
        row.put("mallProductOnline", productOnline);
        // 标题与正文保留用户自定义内容，仅在为空且商品在线时 fallback 到后台内容
        String userTitle = text(row.get("title"));
        String userContent = text(row.get("content"));
        if (userTitle.isBlank() && !mpTitle.isBlank()) {
            row.put("title", mpTitle);
        }
        if (userContent.isBlank() && productOnline && !mpContent.isBlank()) {
            row.put("content", mpContent);
        }
    }

    private boolean isMallSource(Object value) {
        if (value == null) return false;
        if (value instanceof Boolean b) return b;
        if (value instanceof Number n) return n.intValue() == 1;
        String s = String.valueOf(value).trim();
        return "1".equals(s) || "true".equalsIgnoreCase(s);
    }

    private Long asLong(Object value) {
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

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private Map<String, Object> normalizeGoodsRow(Map<String, Object> row) {
        Map<String, Object> normalized = new LinkedHashMap<>(row);
        String accountAvatarUrl = text(row.get("accountAvatarUrl"));
        if (!accountAvatarUrl.isBlank()) {
            normalized.put("accountAvatarUrl", XianyuAccountService.normalizeAvatarUrl(accountAvatarUrl));
        }
        Map<String, Object> account = new LinkedHashMap<>();
        account.put("id", row.get("accountId"));
        account.put("avatarUrl", normalized.getOrDefault("accountAvatarUrl", ""));
        account.put("nickname", row.get("accountNickname"));
        account.put("displayName", row.get("accountDisplayName"));
        account.put("accountNote", row.get("accountRemark"));
        account.put("externalUid", row.get("accountExternalUid"));
        normalized.put("account", account);
        return normalized;
    }
}
