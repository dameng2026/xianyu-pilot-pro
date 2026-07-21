package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.net.InetAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 数据同步发送端服务。
 * <p>
 * 从本地数据库读取当前登录用户（demo 账号）的所有配置数据，
 * 组装 SyncPackage 后通过 HTTPS 推送到线上 /open-api/internal/sync/receive。
 * <p>
 * 同步范围：闲鱼账号 cookie、工作流、AI 客服配置、货源库、自动发货、自动回复、通知设置。
 * 不同步：商品数据、订单数据、消息数据（线上可自行获取）。
 * <p>
 * 全量覆盖策略：目标账号原有配置会被软删除后重建，确保"一切按照本地配置执行"。
 */
@Service
public class DataSyncService {
    private static final Logger log = LoggerFactory.getLogger(DataSyncService.class);
    private static final ObjectMapper JSON = new ObjectMapper().findAndRegisterModules();

    private final JdbcTemplate jdbcTemplate;
    private final CookieCryptoService cookieCryptoService;
    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    @Value("${xianyu.sync.read-timeout-seconds:120}")
    private int readTimeoutSeconds;

    public DataSyncService(JdbcTemplate jdbcTemplate, CookieCryptoService cookieCryptoService) {
        this.jdbcTemplate = jdbcTemplate;
        this.cookieCryptoService = cookieCryptoService;
    }

    /**
     * 执行同步推送。
     *
     * @param config 同步配置（targetBaseUrl, targetToken, targetUsername, sourceAccountId 可选）
     * @return 线上接收端的响应结果
     */
    public Map<String, Object> syncToRemote(Map<String, Object> config) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        if (tenantId == null || userId == null) {
            throw new IllegalStateException("未识别当前登录用户，无法同步");
        }

        String targetBaseUrl = str(config, "targetBaseUrl");
        String targetToken = str(config, "targetToken");
        String targetUsername = str(config, "targetUsername");
        Long sourceAccountId = lng(config, "sourceAccountId");

        if (targetBaseUrl == null || targetBaseUrl.isBlank()) {
            throw new IllegalArgumentException("targetBaseUrl is required");
        }
        if (targetToken == null || targetToken.isBlank()) {
            throw new IllegalArgumentException("targetToken is required");
        }
        if (targetUsername == null || targetUsername.isBlank()) {
            throw new IllegalArgumentException("targetUsername is required");
        }

        // SSRF 防护：校验目标地址不是内网/云元数据地址
        validateTargetUrl(targetBaseUrl);

        // 1. 读取本地数据并组装 SyncPackage
        Map<String, Object> pkg = buildSyncPackage(tenantId, userId, sourceAccountId, targetUsername);
        log.info("数据同步包已组装: tenantId={}, userId={}, targetUsername={}, modules={}",
                tenantId, userId, targetUsername, ((Map<?, ?>) pkg.get("modules")).keySet());

        // 2. 推送到线上
        return pushToRemote(targetBaseUrl, targetToken, pkg);
    }

    /**
     * 仅测试与线上接收端的连通性（不传输数据）。
     */
    public Map<String, Object> pingRemote(Map<String, Object> config) {
        String targetBaseUrl = str(config, "targetBaseUrl");
        String targetToken = str(config, "targetToken");
        if (targetBaseUrl == null || targetBaseUrl.isBlank()) {
            throw new IllegalArgumentException("targetBaseUrl is required");
        }
        if (targetToken == null || targetToken.isBlank()) {
            throw new IllegalArgumentException("targetToken is required");
        }

        // SSRF 防护：校验目标地址不是内网/云元数据地址
        validateTargetUrl(targetBaseUrl);

        String url = normalizeUrl(targetBaseUrl) + "/api/sync/ping";
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("X-Sync-Token", targetToken)
                    .timeout(Duration.ofSeconds(15))
                    .GET()
                    .build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("status", resp.statusCode());
            result.put("body", resp.body());
            return result;
        } catch (Exception e) {
            throw new RuntimeException("ping 远端失败: " + e.getMessage(), e);
        }
    }

    // ==================== 组装 SyncPackage ====================

    private Map<String, Object> buildSyncPackage(Long tenantId, Long userId, Long sourceAccountId, String targetUsername) {
        Map<String, Object> pkg = new LinkedHashMap<>();
        pkg.put("targetUsername", targetUsername);

        Map<String, Object> modules = new LinkedHashMap<>();
        modules.put("xianyuAccount", buildXianyuAccountModule(tenantId, userId, sourceAccountId));
        modules.put("workflows", buildWorkflowsModule(tenantId));
        modules.put("aiCsConfig", buildAiCsConfigModule(tenantId, userId, sourceAccountId));
        modules.put("autoDeliveryAndReply", buildAutoDeliveryAndReplyModule(tenantId, sourceAccountId));
        modules.put("cardInventory", buildCardInventoryModule(tenantId, userId));
        modules.put("notification", buildNotificationModule(tenantId, userId));
        pkg.put("modules", modules);
        return pkg;
    }

    /**
     * 读取闲鱼账号 + cookie（解密为明文）。
     * 如果指定了 sourceAccountId，只读取该账号；否则读取该用户下第一个账号。
     */
    private Map<String, Object> buildXianyuAccountModule(Long tenantId, Long userId, Long sourceAccountId) {
        Map<String, Object> acct;
        if (sourceAccountId != null) {
            try {
                acct = jdbcTemplate.queryForMap(
                        "SELECT * FROM xianyu_account WHERE tenant_id = ? AND id = ? AND deleted = 0 LIMIT 1",
                        tenantId, sourceAccountId);
            } catch (EmptyResultDataAccessException e) {
                throw new IllegalArgumentException("指定的源账号不存在: accountId=" + sourceAccountId);
            }
        } else {
            try {
                acct = jdbcTemplate.queryForMap(
                        "SELECT * FROM xianyu_account WHERE tenant_id = ? AND user_id = ? AND deleted = 0 ORDER BY id ASC LIMIT 1",
                        tenantId, userId);
            } catch (EmptyResultDataAccessException e) {
                throw new IllegalArgumentException("当前用户下没有可同步的闲鱼账号");
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("externalUid", acct.get("external_uid"));
        result.put("nickname", acct.get("nickname"));
        // 推送前清理 avatar_url 脏数据：本地库可能存有 {avatar=http://...} 等历史脏格式，
        // 不清理会导致线上 <img> 标签无法加载头像。同时补 https 协议缺失。
        result.put("avatarUrl", XianyuAccountService.normalizeAvatarUrl(str(acct, "avatar_url")));
        result.put("province", acct.get("province"));
        result.put("city", acct.get("city"));
        result.put("accountLevel", acct.get("account_level"));
        result.put("remark", acct.get("remark"));
        result.put("displayName", acct.get("display_name"));
        result.put("messageExpireTime", acct.get("message_expire_time"));
        result.put("scheduledRedelivery", acct.get("scheduled_redelivery"));
        result.put("autoPolish", acct.get("auto_polish"));

        // 读取并解密 cookie
        Long accountId = ((Number) acct.get("id")).longValue();
        Map<String, Object> auth = null;
        try {
            auth = jdbcTemplate.queryForMap(
                    "SELECT encrypted_cookie, cookie_status FROM xianyu_account_auth " +
                            "WHERE tenant_id = ? AND account_id = ? AND deleted = 0 LIMIT 1",
                    tenantId, accountId);
        } catch (EmptyResultDataAccessException e) {
            log.warn("源账号无 auth 记录: accountId={}", accountId);
        }
        if (auth != null) {
            String encrypted = (String) auth.get("encrypted_cookie");
            String plainCookie = null;
            if (encrypted != null && !encrypted.isBlank()) {
                try {
                    plainCookie = cookieCryptoService.decryptIfNeeded(encrypted);
                    result.put("cookie", plainCookie);
                    result.put("cookieStatus", "ok");
                } catch (Exception e) {
                    log.error("Cookie 解密失败: accountId={}", accountId, e);
                    result.put("cookie", null);
                    result.put("cookieStatus", "decrypt_failed");
                }
            } else {
                result.put("cookie", null);
                result.put("cookieStatus", "empty");
            }
        } else {
            result.put("cookie", null);
            result.put("cookieStatus", "no_auth");
        }
        return result;
    }

    /**
     * 读取工作流定义 + nodes + edges。
     */
    private List<Map<String, Object>> buildWorkflowsModule(Long tenantId) {
        List<Map<String, Object>> workflows = jdbcTemplate.queryForList(
                "SELECT * FROM workflow_definition WHERE tenant_id = ? AND deleted = 0 ORDER BY id ASC",
                tenantId);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> wf : workflows) {
            Map<String, Object> w = new LinkedHashMap<>();
            Long wfId = ((Number) wf.get("id")).longValue();
            w.put("name", wf.get("name"));
            w.put("description", wf.get("description"));
            w.put("status", wf.get("status"));
            w.put("triggerType", wf.get("trigger_type"));
            w.put("enabled", wf.get("enabled"));
            w.put("config", wf.get("config_json"));
            w.put("canvas", wf.get("canvas_json"));
            w.put("nodes", buildWorkflowNodes(tenantId, wfId));
            w.put("edges", buildWorkflowEdges(tenantId, wfId));
            result.add(w);
        }
        return result;
    }

    private List<Map<String, Object>> buildWorkflowNodes(Long tenantId, Long workflowId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM workflow_node WHERE tenant_id = ? AND workflow_id = ? AND deleted = 0 ORDER BY sort_order ASC, id ASC",
                tenantId, workflowId);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> r : rows) {
            Map<String, Object> n = new LinkedHashMap<>();
            n.put("nodeKey", r.get("node_key"));
            n.put("nodeName", r.get("node_name"));
            n.put("nodeType", r.get("node_type"));
            n.put("positionX", r.get("position_x"));
            n.put("positionY", r.get("position_y"));
            n.put("config", r.get("config_json"));
            n.put("sortOrder", r.get("sort_order"));
            result.add(n);
        }
        return result;
    }

    private List<Map<String, Object>> buildWorkflowEdges(Long tenantId, Long workflowId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM workflow_edge WHERE tenant_id = ? AND workflow_id = ? AND deleted = 0 ORDER BY sort_order ASC, id ASC",
                tenantId, workflowId);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> r : rows) {
            Map<String, Object> e = new LinkedHashMap<>();
            e.put("sourceNodeKey", r.get("source_node_key"));
            e.put("targetNodeKey", r.get("target_node_key"));
            e.put("conditionExpr", r.get("condition_expr"));
            e.put("sortOrder", r.get("sort_order"));
            result.add(e);
        }
        return result;
    }

    /**
     * 读取 AI 客服配置（user_business_setting + auto_reply_rule + admin_module_record 模型配置）。
     */
    private Map<String, Object> buildAiCsConfigModule(Long tenantId, Long userId, Long accountId) {
        Map<String, Object> result = new LinkedHashMap<>();

        // 1. user_business_setting（ai-customer-service 相关）
        List<Map<String, Object>> settings = jdbcTemplate.queryForList(
                "SELECT setting_key, config_json FROM user_business_setting " +
                        "WHERE tenant_id = ? AND user_id = ? AND deleted = 0",
                tenantId, userId);
        Map<String, Object> businessSettings = new LinkedHashMap<>();
        for (Map<String, Object> s : settings) {
            String key = (String) s.get("setting_key");
            String json = (String) s.get("config_json");
            try {
                businessSettings.put(key, JSON.readValue(json, Object.class));
            } catch (Exception e) {
                businessSettings.put(key, json);
            }
        }
        result.put("businessSettings", businessSettings);

        // 2. auto_reply_rule（account 维度）
        List<Map<String, Object>> rules = new ArrayList<>();
        if (accountId != null) {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT rule_name, match_type, match_keywords, reply_content, reply_mode, status, priority " +
                            "FROM auto_reply_rule WHERE tenant_id = ? AND account_id = ? AND deleted = 0 ORDER BY id ASC",
                    tenantId, accountId);
            for (Map<String, Object> r : rows) {
                Map<String, Object> rule = new LinkedHashMap<>();
                rule.put("ruleName", r.get("rule_name"));
                rule.put("matchType", r.get("match_type"));
                rule.put("matchKeywords", r.get("match_keywords"));
                rule.put("replyContent", r.get("reply_content"));
                rule.put("replyMode", r.get("reply_mode"));
                rule.put("status", r.get("status"));
                rule.put("priority", r.get("priority"));
                rules.add(rule);
            }
        }
        result.put("autoReplyRules", rules);

        // 3. admin_module_record（model-config-* 系列）
        List<Map<String, Object>> moduleRows = jdbcTemplate.queryForList(
                "SELECT module_key, status, json_text FROM admin_module_record " +
                        "WHERE module_key LIKE 'model-config-%' AND deleted = 0 ORDER BY id ASC");
        List<Map<String, Object>> moduleRecords = new ArrayList<>();
        for (Map<String, Object> r : moduleRows) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("moduleKey", r.get("module_key"));
            m.put("status", r.get("status"));
            String jsonText = (String) r.get("json_text");
            try {
                m.put("jsonText", JSON.readValue(jsonText, Object.class));
            } catch (Exception e) {
                m.put("jsonText", jsonText);
            }
            moduleRecords.add(m);
        }
        result.put("moduleRecords", moduleRecords);
        return result;
    }

    /**
     * 读取自动发货 + 自动回复 + 发货声明配置。
     */
    private Map<String, Object> buildAutoDeliveryAndReplyModule(Long tenantId, Long accountId) {
        Map<String, Object> result = new LinkedHashMap<>();

        // 1. delivery_rule（account 维度）
        List<Map<String, Object>> rules = new ArrayList<>();
        if (accountId != null) {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT goods_id, rule_name, delivery_type, status FROM delivery_rule " +
                            "WHERE tenant_id = ? AND account_id = ? AND deleted = 0 ORDER BY id ASC",
                    tenantId, accountId);
            for (Map<String, Object> r : rows) {
                Map<String, Object> rule = new LinkedHashMap<>();
                rule.put("goodsId", r.get("goods_id"));
                rule.put("ruleName", r.get("rule_name"));
                rule.put("deliveryType", r.get("delivery_type"));
                rule.put("status", r.get("status"));
                rules.add(rule);
            }
        }
        result.put("deliveryRules", rules);

        // 2. delivery_template（按 name UPSERT）
        List<Map<String, Object>> templates = new ArrayList<>();
        List<Map<String, Object>> tRows = jdbcTemplate.queryForList(
                "SELECT name, type, status, content, random_enabled FROM delivery_template " +
                        "WHERE tenant_id = ? AND deleted = 0 ORDER BY id ASC",
                tenantId);
        for (Map<String, Object> r : tRows) {
            Map<String, Object> t = new LinkedHashMap<>();
            t.put("name", r.get("name"));
            t.put("type", r.get("type"));
            t.put("status", r.get("status"));
            t.put("content", r.get("content"));
            t.put("randomEnabled", r.get("random_enabled"));
            templates.add(t);
        }
        result.put("deliveryTemplates", templates);

        // 3. delivery_statement（tenant 维度）
        List<Map<String, Object>> statements = new ArrayList<>();
        List<Map<String, Object>> sRows = jdbcTemplate.queryForList(
                "SELECT enabled, content, scope FROM delivery_statement " +
                        "WHERE tenant_id = ? AND deleted = 0 ORDER BY id ASC",
                tenantId);
        for (Map<String, Object> r : sRows) {
            Map<String, Object> s = new LinkedHashMap<>();
            s.put("enabled", r.get("enabled"));
            s.put("content", r.get("content"));
            s.put("scope", r.get("scope"));
            statements.add(s);
        }
        result.put("deliveryStatements", statements);
        return result;
    }

    /**
     * 读取货源库（card_group + card_item）。
     */
    private Map<String, Object> buildCardInventoryModule(Long tenantId, Long userId) {
        Map<String, Object> result = new LinkedHashMap<>();
        List<Map<String, Object>> groups = new ArrayList<>();

        List<Map<String, Object>> gRows = jdbcTemplate.queryForList(
                "SELECT * FROM card_group WHERE tenant_id = ? AND deleted = 0 ORDER BY id ASC",
                tenantId);
        for (Map<String, Object> g : gRows) {
            Map<String, Object> group = new LinkedHashMap<>();
            Long groupId = ((Number) g.get("id")).longValue();
            group.put("groupName", g.get("group_name"));
            group.put("description", g.get("description"));
            group.put("groupType", g.get("group_type"));
            group.put("cardPrefix", g.get("card_prefix"));
            group.put("passwordPrefix", g.get("password_prefix"));
            group.put("remark", g.get("remark"));
            group.put("alertThreshold", g.get("alert_threshold"));
            group.put("costPrice", g.get("cost_price") != null ? String.valueOf(g.get("cost_price")) : null);
            group.put("suggestedPrice", g.get("suggested_price") != null ? String.valueOf(g.get("suggested_price")) : null);
            group.put("status", g.get("status"));

            // 读取卡密项
            List<Map<String, Object>> items = new ArrayList<>();
            List<Map<String, Object>> iRows = jdbcTemplate.queryForList(
                    "SELECT card_content, card_key, card_value, extra_info, is_used, status, used_time " +
                            "FROM card_item WHERE tenant_id = ? AND group_id = ? AND deleted = 0 ORDER BY id ASC",
                    tenantId, groupId);
            for (Map<String, Object> i : iRows) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("cardContent", i.get("card_content"));
                item.put("cardKey", i.get("card_key"));
                item.put("cardValue", i.get("card_value"));
                item.put("extraInfo", i.get("extra_info"));
                item.put("isUsed", i.get("is_used"));
                item.put("status", i.get("status"));
                item.put("usedTime", i.get("used_time"));
                items.add(item);
            }
            group.put("items", items);
            groups.add(group);
        }
        result.put("groups", groups);
        return result;
    }

    /**
     * 读取通知设置（user_notification_setting.config_json）。
     */
    private Map<String, Object> buildNotificationModule(Long tenantId, Long userId) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            String configJson = jdbcTemplate.queryForObject(
                    "SELECT config_json FROM user_notification_setting WHERE tenant_id = ? AND user_id = ? AND deleted = 0 LIMIT 1",
                    String.class, tenantId, userId);
            if (configJson != null && !configJson.isBlank()) {
                try {
                    result.put("configJson", JSON.readValue(configJson, Object.class));
                } catch (Exception e) {
                    result.put("configJson", configJson);
                }
            }
        } catch (EmptyResultDataAccessException e) {
            log.info("源用户无通知设置: tenantId={}, userId={}", tenantId, userId);
        }
        return result;
    }

    // ==================== HTTP 推送 ====================

    private Map<String, Object> pushToRemote(String targetBaseUrl, String targetToken, Map<String, Object> pkg) {
        String url = normalizeUrl(targetBaseUrl) + "/api/sync/receive";
        String body;
        try {
            body = JSON.writeValueAsString(pkg);
        } catch (Exception e) {
            throw new IllegalStateException("序列化 SyncPackage 失败: " + e.getMessage(), e);
        }

        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Content-Type", "application/json; charset=UTF-8")
                    .header("X-Sync-Token", targetToken)
                    .timeout(Duration.ofSeconds(readTimeoutSeconds))
                    .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("status", resp.statusCode());
            try {
                @SuppressWarnings("unchecked")
                Map<String, Object> respBody = JSON.readValue(resp.body(), Map.class);
                result.put("body", respBody);
            } catch (Exception e) {
                result.put("body", resp.body());
            }

            if (resp.statusCode() >= 200 && resp.statusCode() < 300) {
                log.info("数据同步推送成功: url={}, status={}, bodySize={}", url, resp.statusCode(), body.length());
            } else {
                log.error("数据同步推送失败: url={}, status={}, body={}", url, resp.statusCode(), resp.body());
            }
            return result;
        } catch (java.net.ConnectException ce) {
            // ConnectException 的 getMessage() 常为 null，需明确提示
            String msg = ce.getMessage();
            if (msg == null || msg.isBlank()) {
                msg = "无法连接到目标服务器 " + url + "（连接被拒绝或超时，请检查地址/端口/防火墙）";
            }
            throw new RuntimeException("推送数据同步包失败: " + msg, ce);
        } catch (Exception e) {
            String msg = e.getMessage();
            if (msg == null || msg.isBlank()) {
                msg = e.getClass().getSimpleName() + "（无详细错误信息）";
            }
            throw new RuntimeException("推送数据同步包失败: " + msg, e);
        }
    }

    private static String normalizeUrl(String url) {
        if (url == null) return "";
        String trimmed = url.trim();
        while (trimmed.endsWith("/")) trimmed = trimmed.substring(0, trimmed.length() - 1);
        return trimmed;
    }

    /**
     * SSRF 防护：校验目标 URL 不是内网/保留/云元数据地址。
     * 允许 localhost（本地联调场景）和公网地址；拦截 10/172.16-31/192.168/169.254/127（非localhost）/fc00::/7 等。
     */
    private static void validateTargetUrl(String targetBaseUrl) {
        URI uri;
        try {
            uri = URI.create(normalizeUrl(targetBaseUrl));
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("targetBaseUrl 格式无效");
        }
        String scheme = uri.getScheme();
        if (scheme == null || (!scheme.equalsIgnoreCase("http") && !scheme.equalsIgnoreCase("https"))) {
            throw new IllegalArgumentException("targetBaseUrl 必须是 http 或 https 协议");
        }
        String host = uri.getHost();
        if (host == null || host.isBlank()) {
            throw new IllegalArgumentException("targetBaseUrl 缺少有效的 host");
        }
        String hostLower = host.toLowerCase(java.util.Locale.ROOT);
        // 允许 localhost（本地联调）
        if (hostLower.equals("localhost") || hostLower.equals("127.0.0.1") || hostLower.equals("::1")) {
            return;
        }
        // 云元数据地址一律拦截
        if (hostLower.equals("169.254.169.254") || hostLower.equals("metadata.google.internal")
                || hostLower.endsWith(".internal") || hostLower.endsWith(".local")) {
            throw new IllegalArgumentException("目标地址不允许指向云元数据或内部地址");
        }
        // 如果 host 是 IP 字面量，校验是否为私网/保留段
        if (hostLower.matches("^(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})$")) {
            try {
                InetAddress addr = InetAddress.getByName(hostLower);
                if (addr.isSiteLocalAddress() || addr.isLinkLocalAddress()
                        || addr.isLoopbackAddress() || addr.isAnyLocalAddress()
                        || addr.isMulticastAddress()) {
                    throw new IllegalArgumentException("目标地址不允许指向内网/保留 IP 段");
                }
            } catch (java.net.UnknownHostException e) {
                // 不会发生，因为已经是 IP 字面量
            }
        }
    }

    // ==================== 工具方法 ====================

    private static String str(Map<String, Object> map, String key) {
        Object v = map.get(key);
        return v == null ? null : String.valueOf(v);
    }

    private static Long lng(Map<String, Object> map, String key) {
        Object v = map.get(key);
        if (v == null) return null;
        if (v instanceof Number) return ((Number) v).longValue();
        try {
            return Long.parseLong(String.valueOf(v));
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
