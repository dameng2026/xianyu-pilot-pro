package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 数据同步接收端服务。
 * <p>
 * 接收来自本地版推送的 SyncPackage，按模块分发到 applyXxx 方法。
 * 每个模块在独立事务中执行，单个模块失败不影响其他模块。
 * <p>
 * 事务策略：使用 TransactionTemplate 显式控制（非 @Transactional），
 * 避免 Spring 代理自调用导致事务失效。
 * <p>
 * 解析流程：
 * 1. 从 package.targetUsername 查 sys_user 表 → 获取 tenant_id + user_id
 * 2. applyXianyuAccount 按 external_uid 在该 tenant/user 下找/建 xianyu_account
 * 3. 其他模块全部在该 tenant_id + user_id 下执行
 */
@Service
public class SyncReceiveService {
    private static final Logger log = LoggerFactory.getLogger(SyncReceiveService.class);
    private static final ObjectMapper JSON = new ObjectMapper();

    private final JdbcTemplate jdbcTemplate;
    private final CookieCryptoService cookieCryptoService;
    private final TransactionTemplate transactionTemplate;

    public SyncReceiveService(JdbcTemplate jdbcTemplate,
                              CookieCryptoService cookieCryptoService,
                              PlatformTransactionManager transactionManager) {
        this.jdbcTemplate = jdbcTemplate;
        this.cookieCryptoService = cookieCryptoService;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    /**
     * 接收并应用同步包。
     *
     * @param pkg 同步包结构：
     *            {
     *              "targetUsername": "slfasd",
     *              "modules": {
     *                "xianyuAccount": { "externalUid": "...", "cookie": "plain_text", ... },
     *                "workflows": [...],
     *                "aiCsConfig": {...},
     *                "autoDeliveryAndReply": {...},
     *                "cardInventory": {...},
     *                "notification": {...}
     *              }
     *            }
     * @return 每个模块的执行结果
     */
    public Map<String, Object> receive(Map<String, Object> pkg) {
        String targetUsername = str(pkg, "targetUsername");
        if (targetUsername == null || targetUsername.isBlank()) {
            throw new IllegalArgumentException("targetUsername is required");
        }

        // 解析目标用户的 tenant_id 和 user_id
        Map<String, Object> target = resolveTargetUser(targetUsername);
        Long tenantId = ((Number) target.get("tenant_id")).longValue();
        Long userId = ((Number) target.get("id")).longValue();

        @SuppressWarnings("unchecked")
        Map<String, Object> rawModules = (Map<String, Object>) pkg.get("modules");
        final Map<String, Object> modules = rawModules == null ? Map.of() : rawModules;

        Map<String, Object> results = new LinkedHashMap<>();
        results.put("targetUsername", targetUsername);
        results.put("tenantId", tenantId);
        results.put("userId", userId);

        Map<String, Object> moduleResults = new LinkedHashMap<>();
        final Long[] accountIdHolder = new Long[1];

        // xianyuAccount 模块先执行（可能创建账号），其他模块依赖 accountId
        runModule(moduleResults, "xianyuAccount", () ->
                accountIdHolder[0] = applyXianyuAccount(tenantId, userId, modules.get("xianyuAccount")));
        Long accountId = accountIdHolder[0];
        results.put("accountId", accountId);

        runModule(moduleResults, "workflows", () ->
                applyWorkflow(tenantId, userId, accountId, modules.get("workflows")));
        runModule(moduleResults, "aiCsConfig", () ->
                applyAiCsConfig(tenantId, userId, accountId, modules.get("aiCsConfig")));
        runModule(moduleResults, "autoDeliveryAndReply", () ->
                applyAutoDeliveryAndReply(tenantId, userId, accountId, modules.get("autoDeliveryAndReply")));
        runModule(moduleResults, "cardInventory", () ->
                applyCardInventory(tenantId, userId, accountId, modules.get("cardInventory")));
        runModule(moduleResults, "notification", () ->
                applyNotification(tenantId, userId, modules.get("notification")));

        results.put("modules", moduleResults);
        return results;
    }

    /**
     * 在独立事务中运行单个模块，捕获异常记录结果。
     */
    private void runModule(Map<String, Object> results, String name, Runnable fn) {
        Map<String, Object> r = new LinkedHashMap<>();
        try {
            transactionTemplate.executeWithoutResult(status -> fn.run());
            r.put("status", "success");
        } catch (Exception e) {
            log.error("同步模块 {} 执行失败: {}", name, e.getMessage(), e);
            r.put("status", "failed");
            r.put("error", e.getMessage());
        }
        results.put(name, r);
    }

    /**
     * 通过 username 查询 sys_user 表，获取 tenant_id 和 user_id。
     */
    private Map<String, Object> resolveTargetUser(String username) {
        try {
            return jdbcTemplate.queryForMap(
                    "SELECT id, tenant_id FROM sys_user WHERE username = ? AND deleted = 0 LIMIT 1",
                    username);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            throw new IllegalArgumentException("target user not found: " + username);
        }
    }

    // ==================== 模块应用方法（Task 3-8 实现） ====================

    /**
     * Task 3: 闲鱼账号 cookie 同步与账号自动创建。
     * <p>
     * 流程：
     * 1. 按 external_uid 在目标 tenant/user 下查找 xianyu_account
     * 2. 不存在则创建（含空 auth + runtime 记录）
     * 3. cookie 非空时，重新加密并 upsert 到 xianyu_account_auth
     * 4. 确保 xianyu_account_runtime 存在
     * 5. 返回 account_id
     *
     * @return 目标账号的 account_id
     */
    protected Long applyXianyuAccount(Long tenantId, Long userId, Object data) {
        Map<String, Object> acct = asMap(data);
        String externalUid = str(acct, "externalUid");
        if (externalUid == null || externalUid.isBlank()) {
            throw new IllegalArgumentException("xianyuAccount.externalUid is required");
        }
        String plainCookie = str(acct, "cookie");
        String cookieStatus = str(acct, "cookieStatus");

        // 1. 查找或创建 xianyu_account
        Long accountId = findAccountIdByExternalUid(tenantId, externalUid);
        if (accountId == null) {
            accountId = createXianyuAccount(tenantId, userId, acct);
            log.info("同步创建闲鱼账号: tenantId={}, externalUid={}, accountId={}", tenantId, externalUid, accountId);
        } else {
            updateXianyuAccount(accountId, acct);
            log.info("同步更新闲鱼账号: tenantId={}, externalUid={}, accountId={}", tenantId, externalUid, accountId);
        }

        // 2. cookie 非空且非 decrypt_failed 时，重新加密并 upsert
        if (plainCookie != null && !plainCookie.isBlank() && !"decrypt_failed".equals(cookieStatus)) {
            String encryptedCookie = cookieCryptoService.encrypt(plainCookie);
            String mh5Token = extractCookieValue(plainCookie, "_m_h5_tk");
            String encryptedToken = (mh5Token == null || mh5Token.isBlank())
                    ? null : cookieCryptoService.encrypt(mh5Token);
            upsertAccountAuth(tenantId, accountId, encryptedCookie, encryptedToken);
        } else {
            log.warn("跳过 Cookie 同步: accountId={}, cookieStatus={}", accountId, cookieStatus);
        }

        // 3. 确保 runtime 记录存在
        ensureAccountRuntime(tenantId, accountId);

        return accountId;
    }

    private Long findAccountIdByExternalUid(Long tenantId, String externalUid) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT id FROM xianyu_account WHERE tenant_id = ? AND external_uid = ? AND deleted = 0 LIMIT 1",
                    Long.class, tenantId, externalUid);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            return null;
        }
    }

    private Long createXianyuAccount(Long tenantId, Long userId, Map<String, Object> acct) {
        org.springframework.jdbc.support.GeneratedKeyHolder keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        // 写入前清理 avatar_url 脏数据（历史可能存有 {avatar=http://...} 等格式）
        String normalizedAvatar = XianyuAccountService.normalizeAvatarUrl(str(acct, "avatarUrl"));
        jdbcTemplate.update(con -> {
            java.sql.PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO xianyu_account (tenant_id, user_id, external_uid, nickname, avatar_url, " +
                            "province, city, account_level, remark, status, display_name, " +
                            "message_expire_time, scheduled_redelivery, auto_polish, created_time, updated_time) " +
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())",
                    java.sql.Statement.RETURN_GENERATED_KEYS);
            ps.setLong(1, tenantId);
            ps.setLong(2, userId);
            ps.setString(3, str(acct, "externalUid"));
            setNullableString(ps, 4, str(acct, "nickname"));
            setNullableString(ps, 5, normalizedAvatar);
            setNullableString(ps, 6, str(acct, "province"));
            setNullableString(ps, 7, str(acct, "city"));
            setNullableInt(ps, 8, inte(acct, "accountLevel"));
            setNullableString(ps, 9, str(acct, "remark"));
            ps.setInt(10, 1);
            setNullableString(ps, 11, str(acct, "displayName"));
            setNullableInt(ps, 12, inte(acct, "messageExpireTime") != null ? inte(acct, "messageExpireTime") : 3600);
            setNullableInt(ps, 13, inte(acct, "scheduledRedelivery"));
            setNullableInt(ps, 14, inte(acct, "autoPolish"));
            return ps;
        }, keyHolder);
        return keyHolder.getKey().longValue();
    }

    private void updateXianyuAccount(Long accountId, Map<String, Object> acct) {
        // 写入前清理 avatar_url 脏数据（历史可能存有 {avatar=http://...} 等格式）
        String normalizedAvatar = XianyuAccountService.normalizeAvatarUrl(str(acct, "avatarUrl"));
        jdbcTemplate.update(
                "UPDATE xianyu_account SET nickname = ?, avatar_url = ?, province = ?, city = ?, " +
                        "account_level = ?, remark = ?, display_name = ?, message_expire_time = ?, " +
                        "scheduled_redelivery = ?, auto_polish = ?, updated_time = NOW() " +
                        "WHERE id = ?",
                str(acct, "nickname"), normalizedAvatar, str(acct, "province"), str(acct, "city"),
                inte(acct, "accountLevel"), str(acct, "remark"), str(acct, "displayName"),
                inte(acct, "messageExpireTime") != null ? inte(acct, "messageExpireTime") : 3600,
                inte(acct, "scheduledRedelivery"), inte(acct, "autoPolish"),
                accountId);
    }

    private void upsertAccountAuth(Long tenantId, Long accountId, String encryptedCookie, String encryptedToken) {
        Long authId = findAuthId(tenantId, accountId);
        if (authId == null) {
            jdbcTemplate.update(
                    "INSERT INTO xianyu_account_auth (tenant_id, account_id, auth_type, encrypted_cookie, " +
                            "encrypted_token, cookie_status, last_login_status_code, last_login_status_message, " +
                            "last_login_check_time, created_time, updated_time) " +
                            "VALUES (?, ?, 'cookie', ?, ?, 0, 'COOKIE_UPDATED', '同步更新Cookie', NOW(), NOW(), NOW())",
                    tenantId, accountId, encryptedCookie, encryptedToken);
        } else {
            jdbcTemplate.update(
                    "UPDATE xianyu_account_auth SET encrypted_cookie = ?, encrypted_token = ?, " +
                            "cookie_status = 0, last_login_status_code = 'COOKIE_UPDATED', " +
                            "last_login_status_message = '同步更新Cookie', last_login_check_time = NOW(), " +
                            "updated_time = NOW() WHERE id = ?",
                    encryptedCookie, encryptedToken, authId);
        }
    }

    private Long findAuthId(Long tenantId, Long accountId) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT id FROM xianyu_account_auth WHERE tenant_id = ? AND account_id = ? AND deleted = 0 LIMIT 1",
                    Long.class, tenantId, accountId);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            return null;
        }
    }

    private void ensureAccountRuntime(Long tenantId, Long accountId) {
        Long runtimeId;
        try {
            runtimeId = jdbcTemplate.queryForObject(
                    "SELECT id FROM xianyu_account_runtime WHERE tenant_id = ? AND account_id = ? AND deleted = 0 LIMIT 1",
                    Long.class, tenantId, accountId);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            runtimeId = null;
        }
        if (runtimeId == null) {
            jdbcTemplate.update(
                    "INSERT INTO xianyu_account_runtime (tenant_id, account_id, online_status, ws_status, " +
                            "ws_latency_ms, cookie_status, created_time, updated_time) " +
                            "VALUES (?, ?, 0, 0, 0, 0, NOW(), NOW())",
                    tenantId, accountId);
        }
    }

    private static String extractCookieValue(String cookieText, String key) {
        for (String part : cookieText.split(";")) {
            String[] kv = part.trim().split("=", 2);
            if (kv.length == 2 && kv[0].trim().equals(key)) return kv[1].trim();
        }
        return null;
    }

    private static void setNullableString(java.sql.PreparedStatement ps, int idx, String value)
            throws java.sql.SQLException {
        if (value == null || value.isBlank()) ps.setNull(idx, java.sql.Types.VARCHAR);
        else ps.setString(idx, value);
    }

    private static void setNullableInt(java.sql.PreparedStatement ps, int idx, Integer value)
            throws java.sql.SQLException {
        if (value == null) ps.setNull(idx, java.sql.Types.INTEGER);
        else ps.setInt(idx, value);
    }

    /**
     * Task 4: 工作流定义同步。
     * <p>
     * 按 name 匹配：存在则更新定义并替换 nodes/edges，不存在则创建。
     * nodes/edges 采用软删除后重新插入的策略（与 WorkflowService.replaceNodesAndEdges 一致）。
     */
    protected void applyWorkflow(Long tenantId, Long userId, Long accountId, Object data) {
        List<Map<String, Object>> workflows = asList(data);
        for (Map<String, Object> wf : workflows) {
            String name = str(wf, "name");
            if (name == null || name.isBlank()) continue;
            Long workflowId = findWorkflowIdByName(tenantId, name);
            if (workflowId == null) {
                workflowId = createWorkflowDefinition(tenantId, userId, wf);
                log.info("同步创建工作流: tenantId={}, name={}, id={}", tenantId, name, workflowId);
            } else {
                updateWorkflowDefinition(tenantId, workflowId, wf);
                log.info("同步更新工作流: tenantId={}, name={}, id={}", tenantId, name, workflowId);
            }
            replaceWorkflowNodesAndEdges(tenantId, workflowId,
                    asList(wf.get("nodes")), asList(wf.get("edges")));
        }
    }

    private Long findWorkflowIdByName(Long tenantId, String name) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT id FROM workflow_definition WHERE tenant_id = ? AND name = ? AND deleted = 0 LIMIT 1",
                    Long.class, tenantId, name);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            return null;
        }
    }

    private Long createWorkflowDefinition(Long tenantId, Long userId, Map<String, Object> wf) {
        org.springframework.jdbc.support.GeneratedKeyHolder keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbcTemplate.update(con -> {
            java.sql.PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO workflow_definition (tenant_id, user_id, name, description, version, " +
                            "status, trigger_type, config_json, canvas_json, enabled, deleted, " +
                            "created_time, updated_time) " +
                            "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, 0, NOW(), NOW())",
                    Statement.RETURN_GENERATED_KEYS);
            ps.setLong(1, tenantId);
            ps.setLong(2, userId);
            ps.setString(3, str(wf, "name"));
            setNullableString(ps, 4, str(wf, "description"));
            ps.setString(5, strOrDefault(wf, "status", "draft"));
            ps.setString(6, strOrDefault(wf, "triggerType", "manual"));
            ps.setString(7, toJson(wf.get("config")));
            ps.setString(8, toJson(wf.get("canvas")));
            ps.setInt(9, intOrDefault(wf, "enabled", 0));
            return ps;
        }, keyHolder);
        return keyHolder.getKey().longValue();
    }

    private void updateWorkflowDefinition(Long tenantId, Long workflowId, Map<String, Object> wf) {
        jdbcTemplate.update(
                "UPDATE workflow_definition SET name = ?, description = ?, trigger_type = ?, " +
                        "config_json = ?, canvas_json = ?, enabled = ?, updated_time = NOW() " +
                        "WHERE tenant_id = ? AND id = ? AND deleted = 0",
                str(wf, "name"), str(wf, "description"), strOrDefault(wf, "triggerType", "manual"),
                toJson(wf.get("config")), toJson(wf.get("canvas")), intOrDefault(wf, "enabled", 0),
                tenantId, workflowId);
    }

    private void replaceWorkflowNodesAndEdges(Long tenantId, Long workflowId,
                                               List<Map<String, Object>> nodes, List<Map<String, Object>> edges) {
        jdbcTemplate.update(
                "UPDATE workflow_node SET deleted = 1, updated_time = NOW() " +
                        "WHERE tenant_id = ? AND workflow_id = ? AND deleted = 0", tenantId, workflowId);
        jdbcTemplate.update(
                "UPDATE workflow_edge SET deleted = 1, updated_time = NOW() " +
                        "WHERE tenant_id = ? AND workflow_id = ? AND deleted = 0", tenantId, workflowId);
        int sort = 0;
        for (Map<String, Object> n : nodes) {
            String nodeKey = strOrDefault(n, "nodeKey", "node_" + sort);
            String nodeName = strOrDefault(n, "nodeName", nodeKey);
            String nodeType = strOrDefault(n, "nodeType", "action");
            int x = intOrDefault(n, "x", intOrDefault(n, "positionX", 80));
            int y = intOrDefault(n, "y", intOrDefault(n, "positionY", 80));
            Object config = n.getOrDefault("config", n.getOrDefault("params", Map.of()));
            jdbcTemplate.update(
                    "INSERT INTO workflow_node (tenant_id, workflow_id, node_key, node_name, node_type, " +
                            "position_x, position_y, config_json, sort_order, deleted, created_time, updated_time) " +
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NOW(), NOW())",
                    tenantId, workflowId, nodeKey, nodeName, nodeType, x, y, toJson(config), sort++);
        }
        sort = 0;
        for (Map<String, Object> e : edges) {
            String source = strOrDefault(e, "sourceNodeKey", strOrDefault(e, "source", ""));
            String target = strOrDefault(e, "targetNodeKey", strOrDefault(e, "target", ""));
            String condition = strOrDefault(e, "conditionExpr", strOrDefault(e, "condition", ""));
            jdbcTemplate.update(
                    "INSERT INTO workflow_edge (tenant_id, workflow_id, source_node_key, target_node_key, " +
                            "condition_expr, sort_order, deleted, created_time, updated_time) " +
                            "VALUES (?, ?, ?, ?, ?, ?, 0, NOW(), NOW())",
                    tenantId, workflowId, source, target, condition, sort++);
        }
    }

    private static String strOrDefault(Map<String, Object> map, String key, String def) {
        String v = str(map, key);
        return v == null || v.isBlank() ? def : v;
    }

    private static int intOrDefault(Map<String, Object> map, String key, int def) {
        Integer v = inte(map, key);
        return v == null ? def : v;
    }

    private static String toJson(Object obj) {
        if (obj == null) return "{}";
        if (obj instanceof String) return (String) obj;
        try {
            return JSON.writeValueAsString(obj);
        } catch (Exception e) {
            return "{}";
        }
    }

    /**
     * Task 5: AI 客服配置同步。
     * <p>
     * 同步 3 部分：
     * 1. user_business_setting (setting_key=ai-customer-service) - UPSERT
     * 2. auto_reply_rule (account 维度) - 软删后重建
     * 3. admin_module_record (model-config-* 系列) - 按 module_key UPSERT
     */
    protected void applyAiCsConfig(Long tenantId, Long userId, Long accountId, Object data) {
        Map<String, Object> cfg = asMap(data);

        // 1. user_business_setting: ai-customer-service
        @SuppressWarnings("unchecked")
        Map<String, Object> businessSettings = (Map<String, Object>) cfg.get("businessSettings");
        if (businessSettings != null) {
            for (Map.Entry<String, Object> entry : businessSettings.entrySet()) {
                String key = entry.getKey();
                String json = toJson(entry.getValue());
                jdbcTemplate.update(
                        "INSERT INTO user_business_setting (tenant_id, user_id, setting_key, config_json, " +
                                "created_time, updated_time, deleted) " +
                                "VALUES (?, ?, ?, ?, NOW(), NOW(), 0) " +
                                "ON DUPLICATE KEY UPDATE config_json = VALUES(config_json), updated_time = NOW()",
                        tenantId, userId, key, json);
            }
            log.info("同步业务配置: tenantId={}, userId={}, keys={}", tenantId, userId, businessSettings.keySet());
        }

        // 2. auto_reply_rule: account 维度全量替换
        List<Map<String, Object>> rules = asList(cfg.get("autoReplyRules"));
        if (accountId != null && !rules.isEmpty()) {
            jdbcTemplate.update(
                    "UPDATE auto_reply_rule SET deleted = 1, updated_time = NOW() " +
                            "WHERE tenant_id = ? AND account_id = ? AND deleted = 0",
                    tenantId, accountId);
            for (Map<String, Object> r : rules) {
                jdbcTemplate.update(
                        "INSERT INTO auto_reply_rule (tenant_id, account_id, rule_name, match_type, " +
                                "match_keywords, reply_content, reply_mode, status, priority, " +
                                "deleted, created_time, updated_time) " +
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NOW(), NOW())",
                        tenantId, accountId,
                        str(r, "ruleName"), str(r, "matchType"), str(r, "matchKeywords"),
                        str(r, "replyContent"), str(r, "replyMode"),
                        intOrDefault(r, "status", 1), intOrDefault(r, "priority", 0));
            }
            log.info("同步自动回复规则: tenantId={}, accountId={}, count={}", tenantId, accountId, rules.size());
        }

        // 3. admin_module_record: 按 module_key UPSERT
        List<Map<String, Object>> moduleRecords = asList(cfg.get("moduleRecords"));
        for (Map<String, Object> m : moduleRecords) {
            String moduleKey = str(m, "moduleKey");
            if (moduleKey == null || moduleKey.isBlank()) continue;
            String status = strOrDefault(m, "status", "1");
            String jsonText = toJson(m.get("jsonText"));
            upsertModuleRecord(moduleKey, status, jsonText);
        }
        if (!moduleRecords.isEmpty()) {
            log.info("同步模块记录: count={}, keys={}", moduleRecords.size(),
                    moduleRecords.stream().map(m -> str(m, "moduleKey")).toList());
        }
    }

    private void upsertModuleRecord(String moduleKey, String status, String jsonText) {
        Long existingId;
        try {
            existingId = jdbcTemplate.queryForObject(
                    "SELECT id FROM admin_module_record WHERE module_key = ? AND deleted = 0 LIMIT 1",
                    Long.class, moduleKey);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            existingId = null;
        }
        if (existingId == null) {
            jdbcTemplate.update(
                    "INSERT INTO admin_module_record (module_key, status, json_text, created_time, updated_time, deleted) " +
                            "VALUES (?, ?, ?, NOW(), NOW(), 0)",
                    moduleKey, status, jsonText);
        } else {
            jdbcTemplate.update(
                    "UPDATE admin_module_record SET status = ?, json_text = ?, updated_time = NOW() " +
                            "WHERE id = ? AND deleted = 0",
                    status, jsonText, existingId);
        }
    }

    /**
     * Task 6: 自动发货配置同步。
     * <p>
     * 同步 delivery_rule（account 维度，软删后重建）、
     * delivery_template（按 name UPSERT）、
     * delivery_statement（tenant 维度，软删后重建）。
     * 注意：delivery_rule.goods_id 在线上可能不匹配，由用户后续重新关联。
     */
    protected void applyAutoDeliveryAndReply(Long tenantId, Long userId, Long accountId, Object data) {
        Map<String, Object> cfg = asMap(data);

        // 1. delivery_rule: account 维度全量替换
        List<Map<String, Object>> rules = asList(cfg.get("deliveryRules"));
        if (accountId != null && !rules.isEmpty()) {
            jdbcTemplate.update(
                    "UPDATE delivery_rule SET deleted = 1, updated_time = NOW() " +
                            "WHERE tenant_id = ? AND account_id = ? AND deleted = 0",
                    tenantId, accountId);
            for (Map<String, Object> r : rules) {
                jdbcTemplate.update(
                        "INSERT INTO delivery_rule (tenant_id, account_id, goods_id, rule_name, " +
                                "delivery_type, status, deleted, created_time, updated_time) " +
                                "VALUES (?, ?, ?, ?, ?, ?, 0, NOW(), NOW())",
                        tenantId, accountId, lng(r, "goodsId"), str(r, "ruleName"),
                        str(r, "deliveryType"), intOrDefault(r, "status", 1));
            }
            log.info("同步发货规则: tenantId={}, accountId={}, count={}", tenantId, accountId, rules.size());
        }

        // 2. delivery_template: 按 name UPSERT
        List<Map<String, Object>> templates = asList(cfg.get("deliveryTemplates"));
        for (Map<String, Object> t : templates) {
            String name = str(t, "name");
            if (name == null || name.isBlank()) continue;
            upsertDeliveryTemplate(tenantId, name, t);
        }

        // 3. delivery_statement: tenant 维度全量替换
        List<Map<String, Object>> statements = asList(cfg.get("deliveryStatements"));
        if (!statements.isEmpty()) {
            jdbcTemplate.update(
                    "UPDATE delivery_statement SET deleted = 1, updated_time = NOW() " +
                            "WHERE tenant_id = ? AND deleted = 0", tenantId);
            for (Map<String, Object> s : statements) {
                jdbcTemplate.update(
                        "INSERT INTO delivery_statement (tenant_id, enabled, content, scope, " +
                                "created_time, updated_time, deleted) " +
                                "VALUES (?, ?, ?, ?, NOW(), NOW(), 0)",
                        tenantId, intOrDefault(s, "enabled", 0), str(s, "content"),
                        strOrDefault(s, "scope", "all"));
            }
            log.info("同步发货声明: tenantId={}, count={}", tenantId, statements.size());
        }
    }

    private void upsertDeliveryTemplate(Long tenantId, String name, Map<String, Object> t) {
        Long existingId;
        try {
            existingId = jdbcTemplate.queryForObject(
                    "SELECT id FROM delivery_template WHERE tenant_id = ? AND name = ? AND deleted = 0 LIMIT 1",
                    Long.class, tenantId, name);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            existingId = null;
        }
        int type = intOrDefault(t, "type", 6);
        int status = intOrDefault(t, "status", 1);
        String content = str(t, "content");
        int randomEnabled = intOrDefault(t, "randomEnabled", 0);
        if (existingId == null) {
            jdbcTemplate.update(
                    "INSERT INTO delivery_template (tenant_id, name, type, status, content, " +
                            "random_enabled, created_time, updated_time, deleted) " +
                            "VALUES (?, ?, ?, ?, ?, ?, NOW(), NOW(), 0)",
                    tenantId, name, type, status, content, randomEnabled);
        } else {
            jdbcTemplate.update(
                    "UPDATE delivery_template SET type = ?, status = ?, content = ?, " +
                            "random_enabled = ?, updated_time = NOW() WHERE id = ?",
                    type, status, content, randomEnabled, existingId);
        }
    }

    /**
     * Task 7: 货源库（卡密组+卡密项）同步。
     * <p>
     * 流程：
     * 1. card_group: 按 group_name 在目标 tenant 下匹配，存在则更新，不存在则创建；
     *    维护 groupNameToNewId 映射（group_id 在目标系统会变化）。
     * 2. card_item: 按新 group_id 软删除该组下所有旧卡密项，然后重新插入；
     *    保留 is_used / status / used_time 原值，但 used_order_id / used_by_order_id 置 NULL
     *    （避免引用线上不存在的订单）。
     * <p>
     * 数据结构：data = { "groups": [ { groupName, description, groupType, ..., items: [...] } ] }
     */
    protected void applyCardInventory(Long tenantId, Long userId, Long accountId, Object data) {
        Map<String, Object> cfg = asMap(data);
        List<Map<String, Object>> groups = asList(cfg.get("groups"));
        for (Map<String, Object> g : groups) {
            String groupName = str(g, "groupName");
            if (groupName == null || groupName.isBlank()) continue;

            Long groupId = findCardGroupIdByName(tenantId, groupName);
            if (groupId == null) {
                groupId = createCardGroup(tenantId, userId, g);
                log.info("同步创建卡密组: tenantId={}, name={}, id={}", tenantId, groupName, groupId);
            } else {
                updateCardGroup(tenantId, groupId, g);
                log.info("同步更新卡密组: tenantId={}, name={}, id={}", tenantId, groupName, groupId);
            }

            // 软删除目标组下所有旧卡密项，避免残留脏数据
            jdbcTemplate.update(
                    "UPDATE card_item SET deleted = 1, updated_time = NOW() " +
                            "WHERE tenant_id = ? AND group_id = ? AND deleted = 0",
                    tenantId, groupId);

            // 重新插入卡密项，保留使用状态但清空订单引用
            List<Map<String, Object>> items = asList(g.get("items"));
            int usedCount = 0;
            for (Map<String, Object> it : items) {
                int isUsed = intOrDefault(it, "isUsed", 0);
                int status = intOrDefault(it, "status", 0);
                jdbcTemplate.update(
                        "INSERT INTO card_item (tenant_id, group_id, card_content, card_key, card_value, " +
                                "extra_info, is_used, status, used_time, deleted, created_time, updated_time) " +
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NOW(), NOW())",
                        tenantId, groupId, str(it, "cardContent"), str(it, "cardKey"),
                        str(it, "cardValue"), str(it, "extraInfo"),
                        isUsed, status, null);
                if (isUsed == 1 || status == 2) usedCount++;
            }
            // 回填统计字段
            jdbcTemplate.update(
                    "UPDATE card_group SET total_count = ?, used_count = ?, remain_count = ?, " +
                            "available_count = ?, updated_time = NOW() WHERE id = ?",
                    items.size(), usedCount, items.size() - usedCount, items.size() - usedCount, groupId);
        }
    }

    private Long findCardGroupIdByName(Long tenantId, String groupName) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT id FROM card_group WHERE tenant_id = ? AND group_name = ? AND deleted = 0 LIMIT 1",
                    Long.class, tenantId, groupName);
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            return null;
        }
    }

    private Long createCardGroup(Long tenantId, Long userId, Map<String, Object> g) {
        org.springframework.jdbc.support.GeneratedKeyHolder keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbcTemplate.update(con -> {
            java.sql.PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO card_group (tenant_id, user_id, group_name, description, group_type, " +
                            "card_prefix, password_prefix, remark, alert_threshold, cost_price, suggested_price, " +
                            "status, deleted, created_time, updated_time) " +
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NOW(), NOW())",
                    Statement.RETURN_GENERATED_KEYS);
            ps.setLong(1, tenantId);
            ps.setLong(2, userId);
            ps.setString(3, str(g, "groupName"));
            setNullableString(ps, 4, str(g, "description"));
            setNullableString(ps, 5, str(g, "groupType"));
            setNullableString(ps, 6, str(g, "cardPrefix"));
            setNullableString(ps, 7, str(g, "passwordPrefix"));
            setNullableString(ps, 8, str(g, "remark"));
            setNullableInt(ps, 9, inte(g, "alertThreshold") != null ? inte(g, "alertThreshold") : 10);
            setNullableBigDecimal(ps, 10, str(g, "costPrice"));
            setNullableBigDecimal(ps, 11, str(g, "suggestedPrice"));
            ps.setInt(12, intOrDefault(g, "status", 1));
            return ps;
        }, keyHolder);
        return keyHolder.getKey().longValue();
    }

    private void updateCardGroup(Long tenantId, Long groupId, Map<String, Object> g) {
        jdbcTemplate.update(
                "UPDATE card_group SET description = ?, group_type = ?, card_prefix = ?, " +
                        "password_prefix = ?, remark = ?, alert_threshold = ?, cost_price = ?, " +
                        "suggested_price = ?, status = ?, updated_time = NOW() " +
                        "WHERE tenant_id = ? AND id = ? AND deleted = 0",
                str(g, "description"), str(g, "groupType"), str(g, "cardPrefix"),
                str(g, "passwordPrefix"), str(g, "remark"),
                inte(g, "alertThreshold") != null ? inte(g, "alertThreshold") : 10,
                toBigDecimal(str(g, "costPrice")), toBigDecimal(str(g, "suggestedPrice")),
                intOrDefault(g, "status", 1),
                tenantId, groupId);
    }

    private static java.math.BigDecimal toBigDecimal(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            return new java.math.BigDecimal(value);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static void setNullableBigDecimal(java.sql.PreparedStatement ps, int idx, String value)
            throws java.sql.SQLException {
        if (value == null || value.isBlank()) {
            ps.setNull(idx, java.sql.Types.DECIMAL);
        } else {
            try {
                ps.setBigDecimal(idx, new java.math.BigDecimal(value));
            } catch (NumberFormatException e) {
                ps.setNull(idx, java.sql.Types.DECIMAL);
            }
        }
    }

    /**
     * Task 8: 通知设置同步。
     * <p>
     * 仅同步 user_notification_setting.config_json（用户级通知偏好）。
     * 按 tenant_id + user_id 唯一键 UPSERT。
     * 不同步：notification（运行时消息）、notification_delivery_log（投递日志）、
     * notification_dedup（去重状态）、sys_notification_read（管理员已读状态）。
     * <p>
     * 数据结构：data = { "configJson": "..." } 或 { "settings": [ { "userId":..., "configJson":... } ] }
     */
    protected void applyNotification(Long tenantId, Long userId, Object data) {
        Map<String, Object> cfg = asMap(data);

        // 兼容两种数据格式：单用户（直接 configJson）和多用户列表（settings）
        Object configJsonObj = cfg.get("configJson");
        if (configJsonObj != null) {
            // 单用户格式：直接用解析到的目标 userId
            String configJson = toJson(configJsonObj);
            upsertNotificationSetting(tenantId, userId, configJson);
            log.info("同步通知设置: tenantId={}, userId={}", tenantId, userId);
            return;
        }

        // 多用户格式：按 settings 数组逐个 UPSERT
        // 注意：本地 demo 的 userId 与线上 userId 不同，这里全部用线上 userId 落库
        List<Map<String, Object>> settings = asList(cfg.get("settings"));
        for (Map<String, Object> s : settings) {
            String configJson = toJson(s.get("configJson"));
            upsertNotificationSetting(tenantId, userId, configJson);
        }
        if (!settings.isEmpty()) {
            log.info("同步通知设置(多用户): tenantId={}, targetUserId={}, count={}",
                    tenantId, userId, settings.size());
        }
    }

    private void upsertNotificationSetting(Long tenantId, Long userId, String configJson) {
        // config_json 列定义为 NOT NULL，空值兜底为 "{}"
        String safeJson = (configJson == null || configJson.isBlank()) ? "{}" : configJson;
        jdbcTemplate.update(
                "INSERT INTO user_notification_setting (tenant_id, user_id, config_json, " +
                        "created_time, updated_time, deleted) " +
                        "VALUES (?, ?, ?, NOW(), NOW(), 0) " +
                        "ON DUPLICATE KEY UPDATE config_json = VALUES(config_json), " +
                        "updated_time = NOW(), deleted = 0",
                tenantId, userId, safeJson);
    }

    // ==================== 工具方法 ====================

    @SuppressWarnings("unchecked")
    static Map<String, Object> asMap(Object obj) {
        if (obj instanceof Map) return (Map<String, Object>) obj;
        if (obj == null) return Map.of();
        return JSON.convertValue(obj, Map.class);
    }

    @SuppressWarnings("unchecked")
    static List<Map<String, Object>> asList(Object obj) {
        if (obj instanceof List) return (List<Map<String, Object>>) obj;
        if (obj == null) return List.of();
        return JSON.convertValue(obj, List.class);
    }

    static String str(Map<String, Object> map, String key) {
        Object v = map.get(key);
        return v == null ? null : String.valueOf(v);
    }

    static Long lng(Map<String, Object> map, String key) {
        Object v = map.get(key);
        if (v == null) return null;
        if (v instanceof Number) return ((Number) v).longValue();
        return Long.parseLong(String.valueOf(v));
    }

    static Integer inte(Map<String, Object> map, String key) {
        Object v = map.get(key);
        if (v == null) return null;
        if (v instanceof Number) return ((Number) v).intValue();
        return Integer.parseInt(String.valueOf(v));
    }
}
