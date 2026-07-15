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

        String filter = kw.isBlank() ? "" : " AND (title LIKE CONCAT('%', ?, '%') OR content LIKE CONCAT('%', ?, '%') OR remark LIKE CONCAT('%', ?, '%'))";
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        if (!kw.isBlank()) {
            args.add(kw);
            args.add(kw);
            args.add(kw);
        }

        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM delivery_text_source WHERE tenant_id=? AND deleted=0" + filter,
                Long.class,
                args.toArray()
        );

        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(offset);
        listArgs.add(safeSize);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, source_type AS sourceType, title, content, remark, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM delivery_text_source WHERE tenant_id=? AND deleted=0" + filter +
                        " ORDER BY updated_time DESC, id DESC LIMIT ?, ?",
                listArgs.toArray()
        );
        enrichUsageStats(tenantId, rows);
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public Map<String, Object> detail(Long tenantId, Long sourceId) {
        Map<String, Object> source = jdbcTemplate.queryForMap(
                "SELECT id, source_type AS sourceType, title, content, remark, created_time AS createdTime, updated_time AS updatedTime " +
                        "FROM delivery_text_source WHERE tenant_id=? AND id=? AND deleted=0",
                tenantId, sourceId
        );
        source.put("configuredGoods", listConfiguredGoods(tenantId, sourceId));
        source.put("usageCount", ((List<?>) source.get("configuredGoods")).size());
        return source;
    }

    public Long create(Long tenantId, Map<String, Object> body) {
        jdbcTemplate.update(
                "INSERT INTO delivery_text_source(tenant_id, source_type, title, content, remark, created_time, updated_time, deleted) VALUES(?, 'text', ?, ?, ?, NOW(), NOW(), 0)",
                tenantId, text(body.get("title")), text(body.get("content")), text(body.get("remark"))
        );
        return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    }

    public void update(Long tenantId, Long sourceId, Map<String, Object> body) {
        jdbcTemplate.update(
                "UPDATE delivery_text_source SET title=?, content=?, remark=?, updated_time=NOW() WHERE tenant_id=? AND id=? AND deleted=0",
                text(body.get("title")), text(body.get("content")), text(body.get("remark")), tenantId, sourceId
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
        Map<String, Object> patch = new LinkedHashMap<>();
        patch.put("timing", normalizeTiming(timing));
        patch.put("enabled", 1);
        patch.put("mode", "text");
        patch.put("sourceId", sourceId);
        patch.put("sourceTitle", source.get("title"));
        patch.put("content", text(source.get("content")));
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
