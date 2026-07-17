package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 敏感词策略查询服务。
 *
 * 数据存储在 admin_module_record 表（module_key = 'sensitive-words'），每条记录的 JSON 结构：
 *   { "word": "ChatGPT", "scene": "polish|product|all", "category": "AI品牌词", "action": "拦截|审核" }
 *
 * 应用场景：
 *   - polish  → AI 润色文案时注入到 systemPrompt，明确告知 AI 不可携带
 *   - product → 工作流商品提取后过滤掉包含敏感词的商品
 *   - all     → 同时应用于两个场景
 *
 * 启用判定：status='正常' 视为启用；其他状态（禁用/异常等）不生效。
 */
@Service
public class SensitiveWordService {
    private static final Logger log = LoggerFactory.getLogger(SensitiveWordService.class);
    public static final String MODULE_KEY = "sensitive-words";
    public static final String SCENE_POLISH = "polish";
    public static final String SCENE_PRODUCT = "product";
    public static final String SCENE_ALL = "all";

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SensitiveWordService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 查询指定场景下启用的敏感词列表。
     * scene 为 polish/product 时，同时包含 scene=all 的记录。
     * 返回的 List 元素为 {id, word, scene, category, action, status}。
     */
    public List<Map<String, Object>> listEnabledByScene(String scene) {
        String normalized = normalizeScene(scene);
        List<Map<String, Object>> raw = loadEnabledRecords();
        List<Map<String, Object>> result = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        for (Map<String, Object> rec : raw) {
            String recScene = normalizeScene(String.valueOf(rec.getOrDefault("scene", SCENE_ALL)));
            if (!matchesScene(recScene, normalized)) {
                continue;
            }
            String word = normalizeWord(String.valueOf(rec.getOrDefault("word", "")));
            if (word == null || !seen.add(word)) {
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rec.get("id"));
            item.put("word", word);
            item.put("scene", recScene);
            item.put("category", rec.getOrDefault("category", ""));
            item.put("action", rec.getOrDefault("action", "拦截"));
            item.put("status", rec.getOrDefault("status", "正常"));
            result.add(item);
        }
        return result;
    }

    /**
     * 返回指定场景下启用的敏感词纯词表（去重、保序）。无数据时返回空 List。
     */
    public List<String> listWordsByScene(String scene) {
        List<Map<String, Object>> records = listEnabledByScene(scene);
        List<String> words = new ArrayList<>(records.size());
        for (Map<String, Object> rec : records) {
            words.add(String.valueOf(rec.get("word")));
        }
        return words;
    }

    /**
     * 检测文本是否命中指定场景的敏感词；命中返回命中的词表（去重保序），未命中返回空 List。
     * 匹配规则：大小写不敏感，子串包含即视为命中。
     */
    public List<String> findHits(String text, String scene) {
        if (text == null || text.isEmpty()) {
            return List.of();
        }
        String haystack = text.toLowerCase();
        List<String> words = listWordsByScene(scene);
        List<String> hits = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        for (String w : words) {
            if (w == null || w.isEmpty()) continue;
            if (haystack.contains(w.toLowerCase()) && seen.add(w)) {
                hits.add(w);
            }
        }
        return hits;
    }

    private List<Map<String, Object>> loadEnabledRecords() {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, status, json_text FROM admin_module_record " +
                            "WHERE module_key=? AND deleted=0 AND status='正常' ORDER BY id ASC",
                    MODULE_KEY
            );
            List<Map<String, Object>> result = new ArrayList<>(rows.size());
            for (Map<String, Object> row : rows) {
                Object json = row.get("json_text");
                if (json == null || String.valueOf(json).isBlank()) continue;
                try {
                    Map<String, Object> data = objectMapper.readValue(
                            String.valueOf(json), new TypeReference<LinkedHashMap<String, Object>>() {});
                    data.put("id", row.get("id"));
                    data.putIfAbsent("status", row.get("status"));
                    result.add(data);
                } catch (Exception parseError) {
                    log.warn("sensitive word record parse failed id={} errorType={}",
                            row.get("id"), parseError.getClass().getSimpleName());
                }
            }
            return result;
        } catch (Exception e) {
            log.error("load sensitive words failed errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "敏感词策略暂时不可用，请稍后重试");
        }
    }

    private String normalizeScene(String scene) {
        if (scene == null) return SCENE_ALL;
        String s = scene.trim().toLowerCase();
        if (s.isEmpty()) return SCENE_ALL;
        // 容错：常见的中文输入
        if (s.contains("润色") || s.contains("polish")) return SCENE_POLISH;
        if (s.contains("商品") || s.contains("product")) return SCENE_PRODUCT;
        if (s.contains("全部") || s.contains("all")) return SCENE_ALL;
        return s;
    }

    private boolean matchesScene(String recScene, String queryScene) {
        if (SCENE_ALL.equals(recScene)) return true;
        return recScene.equals(queryScene);
    }

    private String normalizeWord(String word) {
        if (word == null) return null;
        String w = word.trim();
        return w.isEmpty() ? null : w;
    }
}
