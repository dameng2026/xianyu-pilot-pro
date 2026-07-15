package com.xianyu.admin.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AiProviderService;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/** Phase3 AI Provider 运行状态与连通性检查。 */
@RestController
public class AiProviderController {
    private static final int MAX_TEST_PROMPT_LENGTH = 2_000;
    private static final int MAX_TITLE_LENGTH = 200;
    private static final int MAX_DESCRIPTION_LENGTH = 5_000;
    private static final int MAX_CATEGORY_CANDIDATES = 10_000;
    private static final int MAX_CATEGORY_PATH_IDS = 32;
    private final AiProviderService aiProviderService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public AiProviderController(AiProviderService aiProviderService) {
        this.aiProviderService = aiProviderService;
    }

    @GetMapping({"/api/ai-provider/status", "/admin-api/ai-provider/status"})
    public Result<Map<String, Object>> status() {
        return Result.ok(aiProviderService.status());
    }

    @PostMapping("/admin-api/ai-provider/test")
    public Result<Map<String, Object>> test(@RequestBody(required = false) Map<String, Object> body) {
        String prompt = body == null ? "请用一句话说明AI Provider已连通" : String.valueOf(body.getOrDefault("prompt", "请用一句话说明AI Provider已连通"));
        prompt = prompt.trim();
        if (prompt.isEmpty() || prompt.length() > MAX_TEST_PROMPT_LENGTH) {
            throw new BizException(400, "测试提示词不能为空且不能超过2000个字符");
        }
        return Result.ok(aiProviderService.generateText("provider_test", "你是连通性测试助手。", prompt, 0.2D, false));
    }

    /**
     * 商品发布页分类 AI 自动选择。
     * 仅当后台“通用模型”完整配置时可用；未配置时前端应禁用，本端也会返回 enabled=false。
     */
    @PostMapping("/api/ai-provider/category-suggest")
    public Result<Map<String, Object>> suggestCategory(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> res = new LinkedHashMap<>();
        if (!aiProviderService.isConfigured()) {
            res.put("enabled", false);
            res.put("matched", false);
            res.put("message", "后台未配置通用模型，AI自动选择分类未启用");
            return Result.ok(res);
        }
        List<Map<String, Object>> candidates = normalizeCandidates(body == null ? null : body.get("categories"));
        if (candidates.isEmpty()) {
            res.put("enabled", true);
            res.put("matched", false);
            res.put("message", "分类数据为空");
            return Result.ok(res);
        }
        String title = boundedText(body == null ? null : body.get("title"), MAX_TITLE_LENGTH, "商品标题");
        String description = boundedText(body == null ? null : body.get("description"), MAX_DESCRIPTION_LENGTH, "商品描述");
        // 分类树可能非常大。先在本地根据标题/描述进行召回排序，再把高相关候选交给 AI，
        // 避免真实类目排在 650 名之后时永远无法被模型看到。
        List<Map<String, Object>> rankedCandidates = rankCandidates(candidates, title, description);
        StringBuilder lines = new StringBuilder();
        int max = Math.min(rankedCandidates.size(), 220);
        for (int i = 0; i < max; i++) {
            Map<String, Object> c = rankedCandidates.get(i);
            lines.append(c.get("index")).append(". ").append(c.get("path")).append("\n");
        }
        String system = "你是闲鱼商品发布助手。请根据商品标题、描述和候选类目，选择最适合的一个类目。只返回JSON，不要输出额外解释。";
        String user = "商品标题：" + title + "\n商品描述：" + description + "\n候选类目：\n" + lines +
                "\n请仅返回：{\"index\":候选序号,\"reason\":\"不超过30字的理由\"}";
        Map<String, Object> ai;
        try {
            ai = aiProviderService.generateText("category_suggest", system, user, 0.1D, true);
        } catch (BizException e) {
            if (e.getCode() == 401 || e.getCode() == 402) {
                throw e;
            }
            Map<String, Object> fallback = fallbackCandidate(rankedCandidates, title, description);
            res.put("enabled", false);
            res.put("degraded", true);
            res.put("matched", fallback != null);
            if (fallback != null) {
                res.put("category", fallback);
                res.put("reason", "AI 暂时不可用，已按标题和描述进行本地规则匹配");
            } else {
                res.put("message", "AI 暂时不可用且本地规则没有可靠匹配，请手动选择分类");
            }
            return Result.ok(res);
        }
        if (!Boolean.TRUE.equals(ai.get("ok"))) {
            Map<String, Object> fallback = fallbackCandidate(rankedCandidates, title, description);
            res.put("enabled", true);
            if (fallback != null) {
                res.put("matched", true);
                res.put("category", fallback);
                res.put("reason", "AI暂不可用，已按标题/描述规则匹配");
            } else {
                res.put("matched", false);
                res.put("error", ai.getOrDefault("error", "AI分类选择失败"));
            }
            return Result.ok(res);
        }
        Map<String, Object> parsed = parseJsonObject(String.valueOf(ai.getOrDefault("content", "")));
        Map<String, Object> matched = matchCandidate(parsed, candidates);
        res.put("enabled", true);
        res.put("matched", matched != null);
        if (matched != null) {
            res.put("category", matched);
            res.put("reason", parsed.getOrDefault("reason", "AI根据标题和描述自动选择"));
        } else {
            Map<String, Object> fallback = fallbackCandidate(rankedCandidates, title, description);
            if (fallback != null) {
                res.put("matched", true);
                res.put("category", fallback);
                res.put("reason", "AI返回未命中，已按标题/描述规则兜底");
            } else {
                res.put("message", "AI 返回的分类未命中候选数据，请手动选择");
            }
        }
        return Result.ok(res);
    }

    private List<Map<String, Object>> normalizeCandidates(Object raw) {
        List<Map<String, Object>> list = new ArrayList<>();
        if (!(raw instanceof List<?> items)) return list;
        if (items.size() > MAX_CATEGORY_CANDIDATES) {
            throw new BizException(413, "候选类目过多，请缩小类目范围后重试");
        }
        int index = 1;
        for (Object item : items) {
            if (!(item instanceof Map<?, ?> m)) continue;
            Map<String, Object> c = new LinkedHashMap<>();
            c.put("index", index++);
            c.put("id", m.get("id"));
            Object rawName = m.get("name");
            Object rawPath = m.get("path");
            c.put("name", boundedText(rawName, 200, "类目名称"));
            c.put("path", boundedText(rawPath, 500, "类目路径"));
            Object pathIds = m.get("pathIds");
            if (pathIds instanceof List<?> ids) {
                if (ids.size() > MAX_CATEGORY_PATH_IDS) {
                    throw new BizException(400, "类目层级数据异常");
                }
                List<Object> safePathIds = new ArrayList<>(ids.size());
                for (Object id : ids) {
                    if (!(id instanceof Number) && !(id instanceof String)) {
                        throw new BizException(400, "类目层级数据异常");
                    }
                    if (id instanceof String text && text.length() > 128) {
                        throw new BizException(400, "类目层级数据异常");
                    }
                    safePathIds.add(id);
                }
                c.put("pathIds", List.copyOf(safePathIds));
            } else {
                c.put("pathIds", List.of());
            }
            if (!String.valueOf(c.get("path")).isBlank()) list.add(c);
        }
        return list;
    }

    private String boundedText(Object value, int maximum, String fieldName) {
        String text = value == null ? "" : String.valueOf(value).trim();
        if (text.length() > maximum) {
            throw new BizException(400, fieldName + "不能超过" + maximum + "个字符");
        }
        return text;
    }

    private List<Map<String, Object>> rankCandidates(List<Map<String, Object>> candidates, String title, String description) {
        List<Map<String, Object>> ranked = new ArrayList<>(candidates);
        ranked.sort(Comparator
                .comparingInt((Map<String, Object> c) -> categoryScore(c, title, description))
                .reversed()
                .thenComparingInt(c -> Integer.parseInt(String.valueOf(c.getOrDefault("index", "0")))));
        return ranked;
    }

    private Map<String, Object> fallbackCandidate(List<Map<String, Object>> rankedCandidates, String title, String description) {
        if (rankedCandidates == null || rankedCandidates.isEmpty()) return null;
        Map<String, Object> first = rankedCandidates.get(0);
        int score = categoryScore(first, title, description);
        // 低于阈值时宁可让用户手动选择，避免误选高风险类目。
        return score >= 2 ? first : null;
    }

    private int categoryScore(Map<String, Object> candidate, String title, String description) {
        String text = normalizeForMatch(title + " " + description);
        String name = normalizeForMatch(String.valueOf(candidate.getOrDefault("name", "")));
        String path = normalizeForMatch(String.valueOf(candidate.getOrDefault("path", "")));
        if (text.isBlank() || path.isBlank()) return 0;
        int score = 0;
        if (!name.isBlank() && text.contains(name)) score += 20;
        for (String part : path.split("[＞>/\\\\|,，;；\\s]+")) {
            String token = normalizeForMatch(part);
            if (token.length() >= 2 && text.contains(token)) score += 8 + Math.min(token.length(), 6);
        }
        score += charOverlapScore(text, name) * 2;
        score += charOverlapScore(text, path);
        return score;
    }

    private String normalizeForMatch(String value) {
        return value == null ? "" : value.toLowerCase(Locale.ROOT)
                .replace(" ", "")
                .replace("　", "")
                .replace("-", "")
                .replace("_", "")
                .trim();
    }

    private int charOverlapScore(String text, String candidate) {
        if (text.isBlank() || candidate.isBlank()) return 0;
        Set<Character> seen = new HashSet<>();
        int score = 0;
        for (int i = 0; i < candidate.length(); i++) {
            char ch = candidate.charAt(i);
            if (Character.isWhitespace(ch) || seen.contains(ch)) continue;
            seen.add(ch);
            if (text.indexOf(ch) >= 0) score += 1;
        }
        return Math.min(score, 12);
    }

    private Map<String, Object> parseJsonObject(String content) {
        try {
            String text = content == null ? "" : content.trim();
            int start = text.indexOf('{');
            int end = text.lastIndexOf('}');
            if (start >= 0 && end > start) text = text.substring(start, end + 1);
            return objectMapper.readValue(text, new TypeReference<LinkedHashMap<String, Object>>() {});
        } catch (Exception ignored) {
            return new LinkedHashMap<>();
        }
    }

    private Map<String, Object> matchCandidate(Map<String, Object> parsed, List<Map<String, Object>> candidates) {
        Object idxRaw = parsed.get("index");
        if (idxRaw != null) {
            try {
                int idx = Integer.parseInt(String.valueOf(idxRaw));
                for (Map<String, Object> c : candidates) {
                    if (Integer.parseInt(String.valueOf(c.get("index"))) == idx) return c;
                }
            } catch (Exception ignored) {}
        }
        String id = String.valueOf(parsed.getOrDefault("categoryId", parsed.getOrDefault("id", ""))).trim();
        String path = String.valueOf(parsed.getOrDefault("categoryPath", parsed.getOrDefault("path", ""))).trim();
        String name = String.valueOf(parsed.getOrDefault("categoryName", parsed.getOrDefault("name", ""))).trim();
        for (Map<String, Object> c : candidates) {
            if (!id.isBlank() && id.equals(String.valueOf(c.get("id")))) return c;
            if (!path.isBlank() && path.equals(String.valueOf(c.get("path")))) return c;
            if (!name.isBlank() && (name.equals(String.valueOf(c.get("name"))) || String.valueOf(c.get("path")).endsWith(name))) return c;
        }
        return null;
    }
}
