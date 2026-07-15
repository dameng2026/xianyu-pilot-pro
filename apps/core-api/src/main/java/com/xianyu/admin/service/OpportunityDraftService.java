package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.security.TenantContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 保存 AI 改写版本，支持回溯、对比、重新载入草稿。 */
@Service
public class OpportunityDraftService {
    private static final Logger log = LoggerFactory.getLogger(OpportunityDraftService.class);
    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public OpportunityDraftService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Long saveDraft(Long tenantId, Long userId, Map<String, Object> payload, Map<String, Object> rewrite, String provider, String model) {
        requireIdentity(tenantId, userId);
        Map<String, Object> item = asMap(payload.get("item"));
        Long goodsId = longValue(first(item, "id", "goodsId"));
        String externalGoodsId = text(first(item, "externalGoodsId", "itemId", "goodsId"));
        String sourceTitle = text(first(item, "title", "sourceTitle"));
        String style = text(payload.getOrDefault("style", "口语化"));
        Map<String, Object> rw = asMap(rewrite.getOrDefault("rewrite", rewrite));
        String title = text(rw.get("title"));
        String description = text(rw.get("description"));
        Object tags = rw.getOrDefault("tags", List.of());
        Object safety = rw.getOrDefault("safety", Map.of());
        String requestId = text(rewrite.get("requestId"));
        String sourceJson = json(item.isEmpty() ? payload : item);
        String rewriteJson = json(rw);
        int inserted = jdbcTemplate.update("""
                INSERT INTO opportunity_rewrite_draft(tenant_id,user_id,goods_id,external_goods_id,source_title,style,title,description,tags_json,safety_json,provider_name,model_name,request_id,source_json,rewrite_json,status,deleted,created_time,updated_time)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'draft',0,NOW(),NOW())
                """, tenantId, userId, goodsId, abbreviate(externalGoodsId, 160), abbreviate(sourceTitle, 240), abbreviate(style, 40), abbreviate(title, 240), abbreviate(description, 20_000),
                json(tags), json(safety), abbreviate(provider, 80), abbreviate(model, 160), abbreviate(requestId, 120), sourceJson, rewriteJson);
        if (inserted != 1) throw new BizException(503, "AI 改写草稿写入失败");
        Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        if (id == null) throw new BizException(503, "AI 改写草稿编号无法确认");
        return id;
    }

    public PageResult<Map<String, Object>> listDrafts(Long tenantId, String keyword, int current, int size) {
        requireTenant(tenantId);
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE tenant_id=? AND deleted=0 ");
        args.add(tenantId);
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (title LIKE ? OR source_title LIKE ? OR external_goods_id LIKE ?) ");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw);
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM opportunity_rewrite_draft" + where, Long.class, args.toArray());
        List<Object> queryArgs = new ArrayList<>(args);
        queryArgs.add(offset); queryArgs.add(safeSize);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT id, goods_id, external_goods_id, source_title, style, title, description, tags_json, safety_json,
                       provider_name, model_name, request_id, status, created_time, updated_time
                FROM opportunity_rewrite_draft
                """ + where + " ORDER BY created_time DESC, id DESC LIMIT ?, ?", queryArgs.toArray());
        return new PageResult<>(rows.stream().map(this::row).toList(), safeCurrent, safeSize, total == null ? 0 : total);
    }

    public Map<String, Object> detail(Long tenantId, Long id) {
        requireTenant(tenantId);
        if (id == null || id <= 0) throw new BizException(400, "草稿 ID 非法");
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("SELECT * FROM opportunity_rewrite_draft WHERE tenant_id=? AND id=? AND deleted=0", tenantId, id);
        if (rows.isEmpty()) throw new BizException(404, "改写草稿不存在");
        return row(rows.get(0));
    }

    private Map<String, Object> row(Map<String, Object> r) {
        Map<String, Object> m = new LinkedHashMap<>(r);
        m.put("goodsId", r.get("goods_id"));
        m.put("externalGoodsId", r.get("external_goods_id"));
        m.put("sourceTitle", r.get("source_title"));
        m.put("tags", parseJson(r.get("tags_json")));
        m.put("safety", parseJson(r.get("safety_json")));
        m.put("source", parseJson(r.get("source_json")));
        m.put("rewrite", parseJson(r.get("rewrite_json")));
        m.put("providerName", r.get("provider_name"));
        m.put("modelName", r.get("model_name"));
        m.put("requestId", r.get("request_id"));
        m.put("createdTime", r.get("created_time"));
        m.put("updatedTime", r.get("updated_time"));
        m.remove("tags_json");
        m.remove("safety_json");
        m.remove("source_json");
        m.remove("rewrite_json");
        return m;
    }

    private Map<String, Object> asMap(Object obj) {
        Map<String, Object> out = new LinkedHashMap<>();
        if (obj instanceof Map<?, ?> map) map.forEach((k, v) -> out.put(String.valueOf(k), v));
        return out;
    }
    private Object first(Map<String, Object> map, String... keys) { for (String k : keys) if (map.containsKey(k)) return map.get(k); return null; }
    private String text(Object v) { return v == null ? "" : String.valueOf(v); }
    private Long longValue(Object v) { try { if (v == null || String.valueOf(v).isBlank()) return null; return Long.parseLong(String.valueOf(v)); } catch (NumberFormatException e) { return null; } }
    private String abbreviate(String s, int len) { if (s == null) return ""; return s.length() > len ? s.substring(0, len) : s; }
    private String json(Object obj) {
        try {
            return objectMapper.writeValueAsString(obj == null ? Map.of() : obj);
        } catch (Exception e) {
            throw new BizException(400, "草稿内容包含无法保存的数据");
        }
    }

    private Object parseJson(Object raw) {
        try {
            if (raw == null || String.valueOf(raw).isBlank()) return Map.of();
            return objectMapper.readValue(String.valueOf(raw), Object.class);
        } catch (Exception e) {
            log.error("AI 改写草稿 JSON 数据损坏, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "草稿数据损坏，暂时无法读取");
        }
    }

    private void requireIdentity(Long tenantId, Long userId) {
        requireTenant(tenantId);
        if (userId == null || userId <= 0) throw new BizException(401, "用户登录状态已失效");
    }

    private void requireTenant(Long tenantId) {
        if (tenantId == null || tenantId <= 0) throw new BizException(401, "租户登录状态已失效");
    }
}
