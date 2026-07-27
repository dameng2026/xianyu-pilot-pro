package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;

@Service
public class AiCsLearnedKbService {

    private static final Logger log = LoggerFactory.getLogger(AiCsLearnedKbService.class);

    private final JdbcTemplate jdbc;

    public AiCsLearnedKbService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /* ========== 后台：学习 KB 管理 ========== */

    public Map<String, Object> listLearnedKb(int page, int size,
                                              String category, String status,
                                              Integer minScore, String keyword) {
        StringBuilder sql = new StringBuilder(
            "SELECT k.id, k.category_id, c.name AS category_name, k.question, " +
            "LEFT(k.answer, 200) AS answer_preview, k.tags, k.source_summary, " +
            "k.score, k.review_status, k.enabled, k.vector_indexed, k.source_count, " +
            "k.learn_batch_id, k.created_time " +
            "FROM ai_cs_learned_kb k LEFT JOIN ai_cs_kb_category c ON k.category_id=c.id " +
            "WHERE k.deleted=0"
        );
        List<Object> args = new ArrayList<>();
        if (category != null && !category.isEmpty()) {
            sql.append(" AND c.name=?");
            args.add(category);
        }
        if (status != null && !status.isEmpty()) {
            sql.append(" AND k.review_status=?");
            args.add(status);
        }
        if (minScore != null) {
            sql.append(" AND k.score>=?");
            args.add(minScore);
        }
        if (keyword != null && !keyword.isEmpty()) {
            sql.append(" AND (k.question LIKE ? OR k.answer LIKE ? OR k.tags LIKE ?)");
            args.add("%" + keyword + "%");
            args.add("%" + keyword + "%");
            args.add("%" + keyword + "%");
        }

        // count
        String countSql = "SELECT COUNT(*) FROM (" + sql + ") t";
        Long total = jdbc.queryForObject(countSql, Long.class, args.toArray());

        sql.append(" ORDER BY k.created_time DESC LIMIT ? OFFSET ?");
        args.add(size);
        args.add((page - 1) * size);

        List<Map<String, Object>> rows = jdbc.queryForList(sql.toString(), args.toArray());

        Map<String, Object> result = new HashMap<>();
        result.put("list", rows);
        result.put("total", total);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    public Map<String, Object> getLearnedKbDetail(Long id) {
        return jdbc.queryForMap(
            "SELECT k.*, c.name AS category_name FROM ai_cs_learned_kb k " +
            "LEFT JOIN ai_cs_kb_category c ON k.category_id=c.id WHERE k.id=?",
            id
        );
    }

    public void approve(Long id, Long reviewerUserId) {
        jdbc.update(
            "UPDATE ai_cs_learned_kb SET review_status='approved', reviewed_by=?, " +
            "reviewed_time=NOW(), updated_time=NOW() WHERE id=?",
            reviewerUserId, id
        );
    }

    public void reject(Long id, Long reviewerUserId, String reason) {
        jdbc.update(
            "UPDATE ai_cs_learned_kb SET review_status='rejected', reviewed_by=?, " +
            "reviewed_time=NOW(), reject_reason=?, updated_time=NOW() WHERE id=?",
            reviewerUserId, reason, id
        );
    }

    @Transactional
    public void batchApprove(List<Long> ids, Long reviewerUserId) {
        if (ids == null || ids.isEmpty()) return;
        // 批量 UPDATE：用占位符拼接 IN 子句（ids 来自后台，已校验为 Long 类型，无注入风险）
        String inClause = ids.stream().map(String::valueOf).collect(java.util.stream.Collectors.joining(","));
        int updated = jdbc.update(
            "UPDATE ai_cs_learned_kb SET review_status='approved', reviewed_by=?, " +
            "reviewed_time=NOW(), updated_time=NOW() WHERE id IN (" + inClause + ") AND deleted=0",
            reviewerUserId
        );
        log.info("batchApprove updated {} items by reviewer={}", updated, reviewerUserId);
    }

    @Transactional
    public void batchReject(List<Long> ids, Long reviewerUserId, String reason) {
        if (ids == null || ids.isEmpty()) return;
        String inClause = ids.stream().map(String::valueOf).collect(java.util.stream.Collectors.joining(","));
        int updated = jdbc.update(
            "UPDATE ai_cs_learned_kb SET review_status='rejected', reviewed_by=?, " +
            "reviewed_time=NOW(), reject_reason=?, updated_time=NOW() WHERE id IN (" + inClause + ") AND deleted=0",
            reviewerUserId, reason
        );
        log.info("batchReject updated {} items by reviewer={} reason={}", updated, reviewerUserId, reason);
    }

    @Transactional
    public void softDelete(Long id) {
        // 软删 KB，同时标记 vector_indexed=0 以便 RAG 重新索引时清理（Python 端会跳过 deleted=1 的）
        jdbc.update(
            "UPDATE ai_cs_learned_kb SET deleted=1, vector_indexed=0, updated_time=NOW() WHERE id=?",
            id
        );
        // 级联软删所有用户的绑定关系
        jdbc.update(
            "UPDATE ai_cs_user_kb_binding SET deleted=1 WHERE kb_type='learned' AND kb_id=?",
            id
        );
        log.info("softDelete learned_kb id={}, cascade unbound user bindings", id);
    }

    /* ========== 后台：分类管理 ========== */

    public List<Map<String, Object>> listCategories() {
        return jdbc.queryForList(
            "SELECT id, name, parent_id, sort_order, entry_count, source, created_time " +
            "FROM ai_cs_kb_category WHERE deleted=0 ORDER BY sort_order, id"
        );
    }

    public Long createCategory(String name, Long parentId) {
        String hash = md5Hash(name);
        jdbc.update(
            "INSERT INTO ai_cs_kb_category (name, name_hash, parent_id, sort_order, " +
            "entry_count, source, deleted, created_time, updated_time) " +
            "VALUES (?, ?, ?, 0, 0, 'manual', 0, NOW(), NOW())",
            name, hash, parentId
        );
        return jdbc.queryForObject(
            "SELECT id FROM ai_cs_kb_category WHERE name_hash=? AND deleted=0",
            Long.class, hash
        );
    }

    public void renameCategory(Long id, String newName) {
        jdbc.update(
            "UPDATE ai_cs_kb_category SET name=?, name_hash=?, updated_time=NOW() WHERE id=?",
            newName, md5Hash(newName), id
        );
    }

    @Transactional
    public void mergeCategory(Long fromId, Long toId) {
        // 把 fromId 下的 KB 移到 toId
        jdbc.update("UPDATE ai_cs_learned_kb SET category_id=? WHERE category_id=?", toId, fromId);
        // 更新 entry_count
        jdbc.update(
            "UPDATE ai_cs_kb_category c SET entry_count=(SELECT COUNT(*) FROM ai_cs_learned_kb " +
            "WHERE category_id=c.id AND deleted=0) WHERE id IN (?, ?)",
            toId, fromId
        );
        // 软删 fromId
        jdbc.update("UPDATE ai_cs_kb_category SET deleted=1, updated_time=NOW() WHERE id=?", fromId);
    }

    @Transactional
    public void deleteCategory(Long id) {
        // 校验分类下是否还有 KB，避免出现孤儿 KB（category_id 指向已删除分类）
        Integer cnt = jdbc.queryForObject(
            "SELECT COUNT(*) FROM ai_cs_learned_kb WHERE category_id=? AND deleted=0",
            Integer.class, id
        );
        if (cnt != null && cnt > 0) {
            throw new IllegalStateException("该分类下还有 " + cnt + " 条知识库，请先合并或迁移后再删除");
        }
        // 把 parent_id 指向该分类的子分类的 parent_id 置为 NULL，避免孤儿子分类
        jdbc.update("UPDATE ai_cs_kb_category SET parent_id=NULL WHERE parent_id=?", id);
        jdbc.update("UPDATE ai_cs_kb_category SET deleted=1, updated_time=NOW() WHERE id=?", id);
    }

    /* ========== 后台：学习日志 ========== */

    public Map<String, Object> listLogs(int page, int size) {
        Long total = jdbc.queryForObject(
            "SELECT COUNT(*) FROM ai_cs_kb_learning_log WHERE deleted=0", Long.class
        );
        List<Map<String, Object>> rows = jdbc.queryForList(
            "SELECT id, batch_id, started_at, finished_at, status, total_conversations, " +
            "kept_conversations, extracted_items, deduplicated_items, llm_tokens_used, " +
            "llm_cost_yuan FROM ai_cs_kb_learning_log WHERE deleted=0 " +
            "ORDER BY started_at DESC LIMIT ? OFFSET ?",
            size, (page - 1) * size
        );
        Map<String, Object> result = new HashMap<>();
        result.put("list", rows);
        result.put("total", total);
        return result;
    }

    public Map<String, Object> getLogDetail(String batchId) {
        return jdbc.queryForMap(
            "SELECT * FROM ai_cs_kb_learning_log WHERE batch_id=? AND deleted=0",
            batchId
        );
    }

    /* ========== 前台：用户 KB ========== */

    public List<Map<String, Object>> listLearnedKbForUser(String category, String keyword) {
        StringBuilder sql = new StringBuilder(
            "SELECT k.id, k.question, LEFT(k.answer, 200) AS answer_preview, k.tags, " +
            "k.source_summary, k.score, k.source_count, c.name AS category_name, " +
            "k.created_time FROM ai_cs_learned_kb k " +
            "LEFT JOIN ai_cs_kb_category c ON k.category_id=c.id " +
            "WHERE k.deleted=0 AND k.review_status='approved' AND k.enabled=1 " +
            "AND k.sensitive_filtered=1 AND k.vector_indexed=1"
        );
        List<Object> args = new ArrayList<>();
        if (category != null && !category.isEmpty()) {
            sql.append(" AND c.name=?");
            args.add(category);
        }
        if (keyword != null && !keyword.isEmpty()) {
            sql.append(" AND (k.question LIKE ? OR k.tags LIKE ?)");
            args.add("%" + keyword + "%");
            args.add("%" + keyword + "%");
        }
        sql.append(" ORDER BY k.source_count DESC, k.score DESC LIMIT 200");
        return jdbc.queryForList(sql.toString(), args.toArray());
    }

    public Map<String, Object> getLearnedKbForUser(Long id) {
        return jdbc.queryForMap(
            "SELECT k.id, k.question, k.answer, k.tags, k.source_summary, k.source_count, " +
            "k.conversation_turn_count, k.source_conv_ids, " +
            "c.name AS category_name, c.code AS category_code, k.score FROM ai_cs_learned_kb k " +
            "LEFT JOIN ai_cs_kb_category c ON k.category_id=c.id " +
            "WHERE k.id=? AND k.deleted=0 AND k.review_status='approved' " +
            "AND k.enabled=1 AND k.sensitive_filtered=1",
            id
        );
    }

    /**
     * V1.47: 按分类 code 列出该分类下所有已审核通过的 Q&A（前台用户视图）。
     */
    public List<Map<String, Object>> listLearnedKbByCategoryCode(String categoryCode, String keyword) {
        StringBuilder sql = new StringBuilder(
            "SELECT k.id, k.question, LEFT(k.answer, 200) AS answer_preview, k.tags, " +
            "k.source_summary, k.score, k.source_count, k.conversation_turn_count, " +
            "c.name AS category_name, c.code AS category_code, k.created_time " +
            "FROM ai_cs_learned_kb k " +
            "LEFT JOIN ai_cs_kb_category c ON k.category_id=c.id " +
            "WHERE k.deleted=0 AND k.review_status='approved' AND k.enabled=1 " +
            "AND k.sensitive_filtered=1 AND k.vector_indexed=1 AND c.code=?"
        );
        List<Object> args = new ArrayList<>();
        args.add(categoryCode);
        if (keyword != null && !keyword.isEmpty()) {
            sql.append(" AND (k.question LIKE ? OR k.tags LIKE ?)");
            args.add("%" + keyword + "%");
            args.add("%" + keyword + "%");
        }
        sql.append(" ORDER BY k.source_count DESC, k.score DESC LIMIT 200");
        return jdbc.queryForList(sql.toString(), args.toArray());
    }

    /**
     * V1.47: 列出所有预定义分类及其条目数（前台用户视图，含用户是否启用）。
     * 返回 [{id, name, code, keywords, entry_count, is_system, user_enabled}, ...]
     */
    public List<Map<String, Object>> listCategoriesForUser(Long tenantId, Long userId) {
        // 1. 查所有未删除分类
        List<Map<String, Object>> categories = jdbc.queryForList(
            "SELECT id, name, code, keywords, entry_count, is_system, sort_order " +
            "FROM ai_cs_kb_category WHERE deleted=0 ORDER BY is_system DESC, sort_order, id"
        );
        if (categories.isEmpty()) return categories;

        // 2. 查用户已启用的 learned KB 绑定（一次查询，避免 N+1）
        // 注意：绑定的是具体 KB id，不是分类。用户启用某分类 = 启用该分类下所有 KB
        // 这里返回分类下"已启用 KB 数 / 总 KB 数"，前端可据此显示"全部启用/部分启用/未启用"
        List<Long> categoryIds = categories.stream()
            .map(row -> ((Number) row.get("id")).longValue())
            .collect(java.util.stream.Collectors.toList());

        // 单次查询所有分类的总数和已启用绑定数
        String inClause = categoryIds.stream().map(String::valueOf)
            .collect(java.util.stream.Collectors.joining(","));
        List<Map<String, Object>> stats = jdbc.queryForList(
            "SELECT c.id AS category_id, c.code AS category_code, " +
            "COUNT(k.id) AS total_count, " +
            "COALESCE(SUM(CASE WHEN b.kb_id IS NOT NULL THEN 1 ELSE 0 END), 0) AS bound_count " +
            "FROM ai_cs_kb_category c " +
            "LEFT JOIN ai_cs_learned_kb k ON k.category_id=c.id AND k.deleted=0 " +
            "  AND k.review_status='approved' AND k.enabled=1 AND k.sensitive_filtered=1 AND k.vector_indexed=1 " +
            "LEFT JOIN ai_cs_user_kb_binding b ON b.kb_type='learned' AND b.kb_id=k.id " +
            "  AND b.tenant_id=? AND b.user_id=? AND b.deleted=0 AND b.enabled=1 " +
            "WHERE c.id IN (" + inClause + ") AND c.deleted=0 " +
            "GROUP BY c.id, c.code",
            tenantId, userId
        );

        // 3. 合并统计信息
        Map<Long, Map<String, Object>> statsMap = new HashMap<>();
        for (Map<String, Object> row : stats) {
            Number catId = (Number) row.get("category_id");
            if (catId != null) {
                statsMap.put(catId.longValue(), row);
            }
        }

        for (Map<String, Object> category : categories) {
            Long catId = ((Number) category.get("id")).longValue();
            Map<String, Object> stat = statsMap.get(catId);
            int totalCount = stat != null ? ((Number) stat.get("total_count")).intValue() : 0;
            int boundCount = stat != null ? ((Number) stat.get("bound_count")).intValue() : 0;
            category.put("total_count", totalCount);
            category.put("bound_count", boundCount);
            // user_enabled: total_count > 0 且 bound_count == total_count 表示全部启用
            category.put("user_enabled", totalCount > 0 && boundCount == totalCount);
            category.put("user_partial", boundCount > 0 && boundCount < totalCount);
        }

        return categories;
    }

    /**
     * V1.47: 一键启用某个分类下的所有 Q&A（按分类启用）。
     * 实现：批量 INSERT IGNORE 该分类下所有 KB id 到用户绑定表。
     */
    @Transactional
    public int bindCategory(Long tenantId, Long userId, String categoryCode) {
        // 1. 查分类 id
        List<Long> categoryIds = jdbc.queryForList(
            "SELECT id FROM ai_cs_kb_category WHERE code=? AND deleted=0",
            Long.class, categoryCode
        );
        if (categoryIds.isEmpty()) {
            throw new IllegalArgumentException("分类不存在: " + categoryCode);
        }
        Long categoryId = categoryIds.get(0);

        // 2. 查该分类下所有已审核通过的 KB id
        List<Long> kbIds = jdbc.queryForList(
            "SELECT id FROM ai_cs_learned_kb " +
            "WHERE category_id=? AND deleted=0 AND review_status='approved' " +
            "AND enabled=1 AND sensitive_filtered=1 AND vector_indexed=1",
            Long.class, categoryId
        );
        if (kbIds.isEmpty()) return 0;

        // 3. 批量 INSERT IGNORE（幂等，已启用的不会重复插入）
        List<Object[]> batchArgs = new ArrayList<>(kbIds.size());
        for (Long kbId : kbIds) {
            batchArgs.add(new Object[]{tenantId, userId, "learned", kbId});
        }
        jdbc.batchUpdate(
            "INSERT IGNORE INTO ai_cs_user_kb_binding (tenant_id, user_id, kb_type, kb_id, " +
            "enabled, bound_at, deleted) VALUES (?, ?, ?, ?, 1, NOW(), 0)",
            batchArgs
        );
        return kbIds.size();
    }

    /**
     * V1.47: 一键取消启用某个分类下的所有 Q&A。
     */
    @Transactional
    public int unbindCategory(Long tenantId, Long userId, String categoryCode) {
        // 查该分类下所有 KB id，然后批量软删绑定
        List<Long> kbIds = jdbc.queryForList(
            "SELECT k.id FROM ai_cs_learned_kb k " +
            "JOIN ai_cs_kb_category c ON k.category_id=c.id " +
            "WHERE c.code=? AND k.deleted=0",
            Long.class, categoryCode
        );
        if (kbIds.isEmpty()) return 0;

        // 批量 UPDATE 软删（使用 IN 子句，一次 SQL 完成）
        String inClause = kbIds.stream().map(String::valueOf)
            .collect(java.util.stream.Collectors.joining(","));
        return jdbc.update(
            "UPDATE ai_cs_user_kb_binding SET deleted=1 " +
            "WHERE tenant_id=? AND user_id=? AND kb_type='learned' " +
            "AND kb_id IN (" + inClause + ")"
        );
    }

    /**
     * V1.47: 获取某条 Q&A 关联的原始对话消息（按时间排序）。
     * 通过 source_conv_ids 字段 JOIN xianyu_chat_message 表。
     *
     * @param learnedKbId 学习 KB 条目 ID
     * @return [{sender, content, message_time, is_auto_reply, direction}, ...]
     */
    public List<Map<String, Object>> getConversationMessages(Long learnedKbId) {
        // 1. 查 source_conv_ids
        Map<String, Object> kb = jdbc.queryForMap(
            "SELECT source_conv_ids FROM ai_cs_learned_kb WHERE id=? AND deleted=0",
            learnedKbId
        );
        String convIdsJson = (String) kb.get("source_conv_ids");
        if (convIdsJson == null || convIdsJson.isBlank() || "[]".equals(convIdsJson)) {
            return List.of();
        }

        // 2. 解析 JSON 数组（格式: ["conv_id_1", "conv_id_2"]）
        // 注意：s_id 是字符串类型，需要加引号
        List<String> convIds;
        try {
            com.fasterxml.jackson.databind.ObjectMapper om = new com.fasterxml.jackson.databind.ObjectMapper();
            convIds = om.readValue(convIdsJson, new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {});
        } catch (Exception e) {
            log.warn("解析 source_conv_ids 失败 learnedKbId={} json={}", learnedKbId, convIdsJson, e);
            return List.of();
        }
        if (convIds.isEmpty()) return List.of();

        // 3. 查对话消息（仅取第一个会话，避免消息过多）
        // s_id 是字符串，SQL 用 IN 加引号
        String firstConvId = convIds.get(0);
        return jdbc.queryForList(
            "SELECT sender, content, message_time, is_auto_reply, direction " +
            "FROM xianyu_chat_message " +
            "WHERE s_id=? AND deleted=0 " +
            "ORDER BY message_time ASC LIMIT 50",
            firstConvId
        );
    }

    /* ========== 前台：用户私有 KB ========== */

    public List<Map<String, Object>> listUserKb(Long tenantId, Long userId) {
        return jdbc.queryForList(
            "SELECT id, title, content, category, tags, enabled, created_time, updated_time " +
            "FROM ai_cs_user_kb WHERE tenant_id=? AND user_id=? AND deleted=0 " +
            "ORDER BY updated_time DESC",
            tenantId, userId
        );
    }

    public Long createUserKb(Long tenantId, Long userId, String title, String content,
                              String category, String tags) {
        jdbc.update(
            "INSERT INTO ai_cs_user_kb (tenant_id, user_id, title, content, category, tags, " +
            "vector_indexed, enabled, deleted, created_time, updated_time) " +
            "VALUES (?, ?, ?, ?, ?, ?, 0, 1, 0, NOW(), NOW())",
            tenantId, userId, title, content, category, tags
        );
        return jdbc.queryForObject(
            "SELECT LAST_INSERT_ID()", Long.class
        );
    }

    public void updateUserKb(Long tenantId, Long userId, Long id, String title,
                              String content, String category, String tags) {
        jdbc.update(
            "UPDATE ai_cs_user_kb SET title=?, content=?, category=?, tags=?, " +
            "vector_indexed=0, updated_time=NOW() " +
            "WHERE id=? AND tenant_id=? AND user_id=? AND deleted=0",
            title, content, category, tags, id, tenantId, userId
        );
    }

    @Transactional
    public void deleteUserKb(Long tenantId, Long userId, Long id) {
        jdbc.update(
            "UPDATE ai_cs_user_kb SET deleted=1, updated_time=NOW() " +
            "WHERE id=? AND tenant_id=? AND user_id=?",
            id, tenantId, userId
        );
        // 级联软删绑定
        jdbc.update(
            "UPDATE ai_cs_user_kb_binding SET deleted=1 " +
            "WHERE kb_type='user' AND kb_id=? AND tenant_id=? AND user_id=?",
            id, tenantId, userId
        );
    }

    /* ========== 前台：用户绑定关系 ========== */

    public List<Map<String, Object>> listBindings(Long tenantId, Long userId) {
        return jdbc.queryForList(
            "SELECT kb_type, kb_id, enabled, bound_at FROM ai_cs_user_kb_binding " +
            "WHERE tenant_id=? AND user_id=? AND deleted=0",
            tenantId, userId
        );
    }

    @Transactional
    public void bindKbs(Long tenantId, Long userId, List<Map<String, Object>> items) {
        if (items == null || items.isEmpty()) return;
        // 性能优化：批量 INSERT IGNORE，避免 N+1（依赖 uk_user_kb_binding 唯一约束）
        // 注意：前端传驼峰 kbType/kbId，需兼容下划线 kb_type/kb_id（防止其他调用方）
        // 使用 PreparedStatement + addBatch 批量提交，一次网络往返完成全部插入
        List<Object[]> batchArgs = new ArrayList<>(items.size());
        for (Map<String, Object> item : items) {
            String kbType = (String) (item.get("kbType") != null ? item.get("kbType") : item.get("kb_type"));
            if (kbType == null || kbType.isBlank()) {
                throw new IllegalArgumentException("kbType 不能为空");
            }
            Object kbIdRaw = item.get("kbId") != null ? item.get("kbId") : item.get("kb_id");
            if (kbIdRaw == null) {
                throw new IllegalArgumentException("kbId 不能为空");
            }
            Long kbId = ((Number) kbIdRaw).longValue();
            batchArgs.add(new Object[]{tenantId, userId, kbType, kbId});
        }
        // JdbcTemplate.batchUpdate 一次提交批量大批量 INSERT，比循环 update 快 N 倍
        jdbc.batchUpdate(
            "INSERT IGNORE INTO ai_cs_user_kb_binding (tenant_id, user_id, kb_type, kb_id, " +
            "enabled, bound_at, deleted) VALUES (?, ?, ?, ?, 1, NOW(), 0)",
            batchArgs
        );
    }

    public void unbindKb(Long tenantId, Long userId, String kbType, Long kbId) {
        jdbc.update(
            "UPDATE ai_cs_user_kb_binding SET deleted=1 " +
            "WHERE tenant_id=? AND user_id=? AND kb_type=? AND kb_id=?",
            tenantId, userId, kbType, kbId
        );
    }

    /* ========== 工具 ========== */

    private static String md5Hash(String s) {
        try {
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("MD5");
            byte[] bytes = md.digest(s.getBytes("UTF-8"));
            StringBuilder sb = new StringBuilder();
            for (byte b : bytes) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
