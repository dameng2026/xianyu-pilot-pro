package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.*;

/**
 * AI 客服"小梦"核心服务。
 *
 * 职责：
 * 1. 会话生命周期管理（创建/关闭/归档）
 * 2. 三层鉴权：会话标识 + 用户 ID + 租户隔离
 * 3. 消息持久化与历史拉取
 * 4. 闲聊检测与提醒（仅提醒一次）
 * 5. 上下文压缩（不扣费，生成摘要写入下一会话）
 * 6. 计费配置读写、知识库 CRUD、每日统计
 * 7. 工具调用日志记录
 *
 * SSE 流式调用与上下文压缩的实际 AI 推理由 Python 端完成；
 * Java 端负责权限校验、数据持久化、扣费与统计。
 */
@Service
public class AiCsService {
    private static final Logger log = LoggerFactory.getLogger(AiCsService.class);
    private static final ObjectMapper M = new ObjectMapper();

    /** 小梦开场白：礼貌介绍能力圈，告知可完成权限范围内的事情。 */
    public static final String WELCOME_MESSAGE =
            "你好呀！我是小梦 ✨\n\n" +
            "我是闲鱼助手的 AI 客服，可以帮你完成权限范围内的任何事情：\n\n" +
            "🎯 系统使用指导\n   闲鱼账号登录（可让我直接发二维码给你扫码）、商品管理、自动回复、自动发货、工作流、定时任务、AI 客服配置、卡密配置等\n\n" +
            "🛠️ 辅助操作\n   帮你润色商品标题、生成封面图、配置卡密、创建自动回复规则、设计工作流等\n\n" +
            "💬 问题解答\n   Cookie 掉线、WS 异常、滑块求解、会员权益（普通/VIP/SVP）、本系统任何功能问题\n\n" +
            "📌 小提示\n   每条成功回复扣 3 Token；超出 50 条上下文会提示你新建会话或压缩上下文（压缩不扣费）；连续闲聊 5 条后我会礼貌提醒一次。\n\n" +
            "有什么可以帮你的吗？😊";

    /** 闲聊提醒文案（仅提醒一次，不阻断后续对话）。 */
    public static final String DEFAULT_CASUAL_REMINDER =
            "💡 小梦小提示：我更擅长帮你操作系统功能（如配置自动回复、上架商品、设计工作流等）。" +
            "如果你只是想闲聊，也可以继续，但建议把 Token 留给真正需要的工作哦～";

    private final JdbcTemplate jdbcTemplate;
    private final AiBillingService aiBillingService;

    @Value("${xianyu.automation.internal-token:}")
    private String internalToken;

    private static final String DEV_INTERNAL_TOKEN = "dev-only-internal-api-token-change-me-32-chars";

    public AiCsService(JdbcTemplate jdbcTemplate, AiBillingService aiBillingService) {
        this.jdbcTemplate = jdbcTemplate;
        this.aiBillingService = aiBillingService;
    }

    /** 获取内部 API 令牌（供 AiCsController 校验 Python 回调）。 */
    public String getInternalApiToken() {
        if (internalToken != null && !internalToken.isBlank()) {
            return internalToken.trim();
        }
        return DEV_INTERNAL_TOKEN;
    }

    // ==================== 会话管理 ====================

    @Transactional
    public Map<String, Object> createSession() {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null || tenantId == null) throw new BizException(401, "请先登录");

        // 关闭该用户已有的活跃会话（每用户同时只保留一个活跃会话）
        jdbcTemplate.update("UPDATE ai_cs_session SET status=0 WHERE user_id=? AND tenant_id=? AND status=1", userId, tenantId);

        String sessionToken = generateSessionToken(userId);
        GeneratedKeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            var ps = connection.prepareStatement(
                    "INSERT INTO ai_cs_session(session_token, user_id, tenant_id, status, message_count, casual_count, casual_reminded, last_active_time) " +
                            "VALUES(?,?,?,1,0,0,0,NOW())", java.sql.Statement.RETURN_GENERATED_KEYS);
            ps.setString(1, sessionToken);
            ps.setLong(2, userId);
            ps.setLong(3, tenantId);
            return ps;
        }, keyHolder);
        long sessionId = keyHolder.getKey().longValue();

        // 写入小梦开场白（不计入 message_count，不扣费）
        jdbcTemplate.update(
                "INSERT INTO ai_cs_message(session_id, user_id, tenant_id, role, content, tokens_charged, is_casual, created_time) " +
                        "VALUES(?,?,?,'assistant',?,0,0,NOW())",
                sessionId, userId, tenantId, WELCOME_MESSAGE);

        // 每日统计：会话计数 +1
        bumpDailyStat(userId, tenantId, "session", 1);

        // 保留策略：每用户最多保留 30 条未归档会话，超出的标记为 archived=1
        enforceSessionRetentionLimit(userId, tenantId, 30);

        return Map.of(
                "sessionId", sessionId,
                "sessionToken", sessionToken,
                "welcomeMessage", WELCOME_MESSAGE,
                "messageCount", 0
        );
    }

    /**
     * 列出当前用户最近的历史会话（仅未归档，按最后活跃时间倒序）。
     * 每条会话附带首条用户消息作为预览，便于用户识别会话主题。
     * 默认上限 30 条，与 enforceSessionRetentionLimit 的保留策略一致。
     */
    public List<Map<String, Object>> listUserSessions(int limit) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null || tenantId == null) throw new BizException(401, "请先登录");
        int safeLimit = Math.max(1, Math.min(limit <= 0 ? 30 : limit, 100));

        // 查询用户最近 N 条未归档会话（活跃会话优先，再按最后活跃时间倒序）
        // status=1 排前，便于用户快速回到当前对话
        List<Map<String, Object>> sessions = jdbcTemplate.queryForList(
                "SELECT id, session_token, status, message_count, casual_count, " +
                        "LEFT(compressed_summary, 200) AS compressed_summary_preview, " +
                        "last_active_time, created_time " +
                        "FROM ai_cs_session WHERE user_id=? AND tenant_id=? AND archived=0 " +
                        "ORDER BY status DESC, last_active_time DESC, id DESC LIMIT ?",
                userId, tenantId, safeLimit);

        if (sessions.isEmpty()) return sessions;

        // 批量查询每个会话的首条用户消息作为预览（一次 SQL，避免 N+1）
        List<Long> sessionIds = new ArrayList<>();
        for (Map<String, Object> s : sessions) {
            Object id = s.get("id");
            if (id instanceof Number) sessionIds.add(((Number) id).longValue());
        }
        if (!sessionIds.isEmpty()) {
            // 构建 IN 占位符
            String inClause = sessionIds.stream().map(s -> "?").collect(java.util.stream.Collectors.joining(","));
            Object[] args = new Object[sessionIds.size() + 2];
            args[0] = userId;
            args[1] = tenantId;
            for (int i = 0; i < sessionIds.size(); i++) args[i + 2] = sessionIds.get(i);
            // 子查询：每个 session 的首条 user 消息 id
            List<Map<String, Object>> previews = jdbcTemplate.queryForList(
                    "SELECT m.session_id, m.content FROM ai_cs_message m " +
                            "INNER JOIN (" +
                            "  SELECT session_id, MIN(id) AS min_id FROM ai_cs_message " +
                            "  WHERE user_id=? AND tenant_id=? AND role='user' AND session_id IN (" + inClause + ") " +
                            "  GROUP BY session_id" +
                            ") t ON m.id=t.min_id", args);
            Map<Long, String> previewMap = new HashMap<>();
            for (Map<String, Object> p : previews) {
                Object sid = p.get("session_id");
                Object content = p.get("content");
                if (sid instanceof Number && content instanceof String) {
                    String c = (String) content;
                    // 截取前 80 字符作为预览，避免传输过大
                    previewMap.put(((Number) sid).longValue(), c.length() > 80 ? c.substring(0, 80) + "..." : c);
                }
            }
            // 将预览写入会话列表
            for (Map<String, Object> s : sessions) {
                Object id = s.get("id");
                Long sidLong = id instanceof Number ? ((Number) id).longValue() : null;
                s.put("firstUserMessagePreview", sidLong != null ? previewMap.getOrDefault(sidLong, "") : "");
                // 兼容前端字段命名
                s.put("sessionId", s.get("id"));
                s.put("sessionToken", s.get("session_token"));
                s.put("messageCount", s.get("message_count"));
                s.put("casualCount", s.get("casual_count"));
                s.put("lastActiveTime", s.get("last_active_time"));
                s.put("createdTime", s.get("created_time"));
                s.put("isActive", Integer.valueOf(1).equals(s.get("status")));
            }
        }
        return sessions;
    }

    /**
     * 恢复已关闭的会话为活跃状态，用于"继续对话"。
     * 若目标会话已是活跃状态，直接返回；否则关闭当前活跃会话（如果有），将目标会话 status=1。
     * 不允许恢复已归档（archived=1）的会话。
     */
    @Transactional
    public Map<String, Object> resumeSession(Long sessionId) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null || tenantId == null) throw new BizException(401, "请先登录");
        if (sessionId == null || sessionId <= 0) throw new BizException(400, "会话 ID 非法");
        // 校验会话归属且未归档（不要求 status=1，允许恢复已关闭会话）
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_cs_session WHERE id=? AND user_id=? AND tenant_id=? AND archived=0",
                Integer.class, sessionId, userId, tenantId);
        if (count == null || count == 0) {
            throw new BizException(403, "会话不存在或无权访问");
        }
        // 查询目标会话当前状态
        Integer currentStatus = jdbcTemplate.queryForObject(
                "SELECT status FROM ai_cs_session WHERE id=?", Integer.class, sessionId);
        if (currentStatus != null && currentStatus == 1) {
            // 已是活跃会话，无需恢复
            return buildSessionResponse(sessionId);
        }
        // 关闭该用户已有的活跃会话（每用户同时只保留一个活跃会话）
        jdbcTemplate.update(
                "UPDATE ai_cs_session SET status=0 WHERE user_id=? AND tenant_id=? AND status=1 AND id<>?",
                userId, tenantId, sessionId);
        // 恢复目标会话为活跃
        jdbcTemplate.update(
                "UPDATE ai_cs_session SET status=1, last_active_time=NOW() WHERE id=?",
                sessionId);
        // 应用归档保留策略
        enforceSessionRetentionLimit(userId, tenantId, 30);
        return buildSessionResponse(sessionId);
    }

    /**
     * 保留每用户最近 maxKeep 条未归档会话，超出的标记为 archived=1。
     * 已归档会话仍保留在数据库中（后台审计仍可查询），但前台历史列表不再展示。
     * 在 createSession / resumeSession 后调用，确保数据量可控。
     */
    @Transactional
    public void enforceSessionRetentionLimit(Long userId, Long tenantId, int maxKeep) {
        if (maxKeep <= 0) return;
        try {
            Integer total = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM ai_cs_session WHERE user_id=? AND tenant_id=? AND archived=0",
                    Integer.class, userId, tenantId);
            if (total == null || total <= maxKeep) return;
            int toArchive = total - maxKeep;
            // MySQL 不允许 UPDATE 直接引用同一张表的子查询，需嵌套一层
            jdbcTemplate.update(
                    "UPDATE ai_cs_session SET archived=1 WHERE id IN (" +
                            "  SELECT id FROM (" +
                            "    SELECT id FROM ai_cs_session " +
                            "    WHERE user_id=? AND tenant_id=? AND archived=0 " +
                            "    ORDER BY last_active_time ASC, id ASC LIMIT ?" +
                            "  ) AS t" +
                            ")",
                    userId, tenantId, toArchive);
            log.info("AI 客服会话归档 userId={}, archived {} sessions (keep {})", userId, toArchive, maxKeep);
        } catch (Exception e) {
            log.warn("AI 客服会话归档失败 userId={}: {}", userId, e.getMessage());
        }
    }

    /** 构建会话响应数据（用于 resumeSession 返回）。 */
    private Map<String, Object> buildSessionResponse(Long sessionId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, session_token, message_count, casual_count, casual_reminded, " +
                        "compressed_summary, last_active_time, created_time " +
                        "FROM ai_cs_session WHERE id=?", sessionId);
        if (rows.isEmpty()) throw new BizException(404, "会话不存在");
        Map<String, Object> row = rows.get(0);
        Map<String, Object> res = new LinkedHashMap<>(row);
        res.put("sessionId", row.get("id"));
        res.put("sessionToken", row.get("session_token"));
        res.put("welcomeMessage", WELCOME_MESSAGE);
        res.put("resumed", true);
        return res;
    }

    /**
     * 获取当前用户活跃会话；若不存在则自动创建。
     */
    public Map<String, Object> currentSession() {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null || tenantId == null) throw new BizException(401, "请先登录");
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, session_token, message_count, casual_count, casual_reminded, compressed_summary, last_active_time, created_time " +
                        "FROM ai_cs_session WHERE user_id=? AND tenant_id=? AND status=1 ORDER BY id DESC LIMIT 1", userId, tenantId);
        if (rows.isEmpty()) return createSession();
        Map<String, Object> row = rows.get(0);
        Map<String, Object> res = new LinkedHashMap<>(row);
        res.put("sessionId", row.get("id"));
        res.put("sessionToken", row.get("session_token"));
        res.put("welcomeMessage", WELCOME_MESSAGE);
        return res;
    }

    @Transactional
    public void closeSession(Long sessionId) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        if (userId == null || tenantId == null) throw new BizException(401, "请先登录");
        validateSessionOwnership(sessionId, userId, tenantId);
        jdbcTemplate.update("UPDATE ai_cs_session SET status=0 WHERE id=? AND user_id=? AND tenant_id=?", sessionId, userId, tenantId);
    }

    /**
     * 三层鉴权：校验会话归属（session_token + user_id + tenant_id）。
     * 任何 AI 调用前必须通过此校验，确保不会操作到其他用户的数据。
     */
    public void validateSessionOwnership(Long sessionId, Long userId, Long tenantId) {
        if (sessionId == null || sessionId <= 0) throw new BizException(400, "会话 ID 非法");
        if (userId == null || tenantId == null) throw new BizException(401, "请先登录");
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_cs_session WHERE id=? AND user_id=? AND tenant_id=? AND status=1",
                Integer.class, sessionId, userId, tenantId);
        if (count == null || count == 0) {
            throw new BizException(403, "会话不存在或无权访问");
        }
    }

    /**
     * 校验会话归属但不要求 status=1（允许查看已关闭的历史会话）。
     * 仅用于"查看历史会话消息"等只读场景；发送消息等需调用 validateSessionOwnership（要求活跃）。
     * 不允许访问已归档（archived=1）的会话。
     */
    public void validateSessionOwnershipAnyStatus(Long sessionId, Long userId, Long tenantId) {
        if (sessionId == null || sessionId <= 0) throw new BizException(400, "会话 ID 非法");
        if (userId == null || tenantId == null) throw new BizException(401, "请先登录");
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_cs_session WHERE id=? AND user_id=? AND tenant_id=? AND archived=0",
                Integer.class, sessionId, userId, tenantId);
        if (count == null || count == 0) {
            throw new BizException(403, "会话不存在或无权访问");
        }
    }

    /**
     * 拉取会话历史消息（含开场白）。按 id 升序返回，最多 limit 条。
     * 使用宽松校验（允许查看已关闭的历史会话消息），但要求会话未归档且归属当前用户。
     */
    public List<Map<String, Object>> listMessages(Long sessionId, int limit) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        validateSessionOwnershipAnyStatus(sessionId, userId, tenantId);
        int safeLimit = Math.max(1, Math.min(limit <= 0 ? 100 : limit, 200));
        return jdbcTemplate.queryForList(
                "SELECT id, role, content, tokens_charged, is_casual, tool_calls, created_time " +
                        "FROM ai_cs_message WHERE session_id=? AND user_id=? AND tenant_id=? ORDER BY id ASC LIMIT ?",
                sessionId, userId, tenantId, safeLimit);
    }

    // ==================== 闲聊与上下文 ====================

    /**
     * 检测用户消息是否为闲聊。
     * 简单规则：消息较短且不含系统功能关键词。
     */
    public boolean isCasualMessage(String message) {
        if (message == null) return false;
        String s = message.trim();
        if (s.length() > 60) return false;
        String lower = s.toLowerCase();
        // 包含系统功能关键词则不视为闲聊
        String[] keywords = {
                "闲鱼", "账号", "cookie", "商品", "上架", "下架", "发布", "自动回复", "自动发货",
                "卡密", "工作流", "定时", "任务", "ai客服", "客服", "token", "余额", "充值",
                "vip", "svp", "会员", "订单", "消息", "通知", "ws", "滑块", "验证", "二维码",
                "扫码", "登录", "鱼小铺", "多规格", "封面", "标题", "润色", "商机", "数据",
                "系统", "功能", "怎么", "如何", "为什么", "帮助", "操作", "配置", "设置"
        };
        for (String k : keywords) {
            if (lower.contains(k)) return false;
        }
        // 短消息且不含功能关键词，判定为闲聊
        return s.length() <= 30;
    }

    /**
     * 自增会话的闲聊计数，返回是否需要提醒（仅提醒一次）。
     */
    @Transactional
    public boolean bumpCasualAndShouldRemind(Long sessionId) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        // 原子自增 casual_count
        jdbcTemplate.update("UPDATE ai_cs_session SET casual_count=casual_count+1 WHERE id=?", sessionId);
        Map<String, Object> row = jdbcTemplate.queryForList(
                "SELECT casual_count, casual_reminded FROM ai_cs_session WHERE id=?", sessionId)
                .stream().findFirst().orElse(null);
        if (row == null) return false;
        int casualCount = ((Number) row.get("casual_count")).intValue();
        int reminded = ((Number) row.get("casual_reminded")).intValue();
        int threshold = getCasualThreshold(tenantId);
        // 仅在达到阈值且本会话未提醒过时提醒一次
        if (casualCount >= threshold && reminded == 0) {
            jdbcTemplate.update("UPDATE ai_cs_session SET casual_reminded=1 WHERE id=?", sessionId);
            bumpDailyStat(userId, tenantId, "casual", 1);
            return true;
        }
        return false;
    }

    /**
     * 自增会话消息计数，返回当前计数与上限，判断是否超限。
     */
    @Transactional
    public Map<String, Object> bumpMessageCount(Long sessionId) {
        Long tenantId = UserContext.getTenantId();
        jdbcTemplate.update("UPDATE ai_cs_session SET message_count=message_count+1, last_active_time=NOW() WHERE id=?", sessionId);
        Map<String, Object> row = jdbcTemplate.queryForList(
                "SELECT message_count FROM ai_cs_session WHERE id=?", sessionId)
                .stream().findFirst().orElse(null);
        int count = row == null ? 0 : ((Number) row.get("message_count")).intValue();
        int max = getMaxContextMessages(tenantId);
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("currentCount", count);
        res.put("maxCount", max);
        res.put("exceeded", count > max);
        return res;
    }

    /**
     * 上下文压缩：将历史 50 条消息精简为一条摘要，写入 compressed_summary，
     * 然后关闭当前会话并创建新会话，新会话携带压缩摘要。
     * 注意：压缩不扣费。
     */
    @Transactional
    public Map<String, Object> compressContext(Long sessionId, String summary) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        validateSessionOwnership(sessionId, userId, tenantId);
        // 保存压缩摘要到当前会话，然后关闭
        jdbcTemplate.update("UPDATE ai_cs_session SET compressed_summary=?, status=0 WHERE id=?", summary, sessionId);
        // 创建新会话，携带压缩摘要
        String sessionToken = generateSessionToken(userId);
        GeneratedKeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            var ps = connection.prepareStatement(
                    "INSERT INTO ai_cs_session(session_token, user_id, tenant_id, status, message_count, casual_count, casual_reminded, compressed_summary, last_active_time) " +
                            "VALUES(?,?,?,1,0,0,0,?,NOW())", java.sql.Statement.RETURN_GENERATED_KEYS);
            ps.setString(1, sessionToken);
            ps.setLong(2, userId);
            ps.setLong(3, tenantId);
            ps.setString(4, summary);
            return ps;
        }, keyHolder);
        long newSessionId = keyHolder.getKey().longValue();
        // 写入系统消息：携带压缩摘要的过渡消息
        jdbcTemplate.update(
                "INSERT INTO ai_cs_message(session_id, user_id, tenant_id, role, content, tokens_charged, is_casual, created_time) " +
                        "VALUES(?,?,?,'system',?,0,0,NOW())",
                newSessionId, userId, tenantId, "[上一会话摘要] " + summary);
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("sessionId", newSessionId);
        res.put("sessionToken", sessionToken);
        res.put("compressed", true);
        return res;
    }

    /**
     * 持久化一条用户消息（在 SSE 调用前写入，确保 AI 能读到上下文）。
     */
    @Transactional
    public long appendUserMessage(Long sessionId, String message, boolean isCasual) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        GeneratedKeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            var ps = connection.prepareStatement(
                    "INSERT INTO ai_cs_message(session_id, user_id, tenant_id, role, content, tokens_charged, is_casual, created_time) " +
                            "VALUES(?,?,?,'user',?,0,?,NOW())", java.sql.Statement.RETURN_GENERATED_KEYS);
            ps.setLong(1, sessionId);
            ps.setLong(2, userId);
            ps.setLong(3, tenantId);
            ps.setString(4, message);
            ps.setInt(5, isCasual ? 1 : 0);
            return ps;
        }, keyHolder);
        // 每日统计：用户消息计数 +1
        bumpDailyStat(userId, tenantId, "user_message", 1);
        return keyHolder.getKey().longValue();
    }

    /**
     * 持久化一条 assistant 消息并扣费。
     * 仅在 AI 成功回复后调用；扣费失败不阻断消息保存。
     *
     * @param userId   用户 ID（由 Controller 从请求体传入，支持内部回调场景）
     * @param tenantId 租户 ID（由 Controller 从请求体传入，支持内部回调场景）
     */
    @Transactional
    public Map<String, Object> appendAssistantMessageAndCharge(Long sessionId, String content, String toolCallsJson,
                                                                Long userId, Long tenantId) {
        // 解析 toolCallsJson（Python 端格式：[{"tool":..., "arguments":..., "requiresConfirm":..., "description":...}]）
        // 对每个工具调用写入 ai_cs_tool_call 表并返回真实 ID，供前端确认按钮使用。
        List<Map<String, Object>> toolCallIds = new ArrayList<>();
        if (StringUtils.hasText(toolCallsJson)) {
            try {
                List<Map<String, Object>> parsed = M.readValue(
                        toolCallsJson, new TypeReference<List<Map<String, Object>>>() {});
                for (Map<String, Object> tc : parsed) {
                    String toolName = text(tc.get("tool"));
                    if (!StringUtils.hasText(toolName)) continue;
                    String argsJson;
                    Object args = tc.get("arguments");
                    if (args == null) {
                        argsJson = "{}";
                    } else if (args instanceof String) {
                        argsJson = (String) args;
                    } else {
                        argsJson = M.writeValueAsString(args);
                    }
                    boolean requiresConfirm = Boolean.TRUE.equals(tc.get("requiresConfirm"));
                    long tcId = logToolCall(sessionId, userId, tenantId, toolName, argsJson, requiresConfirm);
                    if (tcId > 0) {
                        Map<String, Object> entry = new LinkedHashMap<>();
                        entry.put("toolCallId", tcId);
                        entry.put("tool", toolName);
                        toolCallIds.add(entry);
                    }
                }
            } catch (Exception e) {
                log.warn("解析 toolCallsJson 失败 sessionId={}: {}", sessionId, e.getMessage());
            }
        }
        int perMessageTokens = getPerMessageTokens(tenantId);
        // AI 客服对话对用户完全免费（项目规则：用户无每日免费自动回复额度限制，
        // 仅系统 AI 客服"小梦"保留额度）。因此这里不再调用 AiBillingService.charge 扣费，
        // 避免因用户 Token 余额不足导致对话中断。
        // 注意：工具调用中涉及通用模型计费的（如 polish_product_title）仍由 AiProviderService 单独扣费。
        long balanceAfter = -1L;
        boolean deducted = false;
        String chargeError = null;
        log.info("AI 客服对话免费 sessionId={}, userId={}", sessionId, userId);
        int charged = deducted ? perMessageTokens : 0;
        GeneratedKeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            var ps = connection.prepareStatement(
                    "INSERT INTO ai_cs_message(session_id, user_id, tenant_id, role, content, tokens_charged, is_casual, tool_calls, created_time) " +
                            "VALUES(?,?,?,'assistant',?,?,0,?,NOW())", java.sql.Statement.RETURN_GENERATED_KEYS);
            ps.setLong(1, sessionId);
            ps.setLong(2, userId);
            ps.setLong(3, tenantId);
            ps.setString(4, content);
            ps.setInt(5, charged);
            ps.setString(6, toolCallsJson);
            return ps;
        }, keyHolder);
        long messageId = keyHolder.getKey().longValue();
        // 每日统计：assistant 消息 +1，扣费 +charged
        bumpDailyStat(userId, tenantId, "assistant_message", 1);
        if (charged > 0) bumpDailyStat(userId, tenantId, "tokens", charged);
        // 会话消息计数 +1（assistant 也计入）
        jdbcTemplate.update("UPDATE ai_cs_session SET message_count=message_count+1, last_active_time=NOW() WHERE id=?", sessionId);
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("messageId", messageId);
        res.put("tokensCharged", charged);
        res.put("balanceAfter", balanceAfter);
        res.put("deducted", deducted);
        res.put("chargeError", chargeError);
        res.put("toolCallIds", toolCallIds);
        return res;
    }

    // ==================== 工具调用日志 ====================

    @Transactional
    public long logToolCall(Long sessionId, String toolName, String argumentsJson, boolean requiresConfirm) {
        Long userId = UserContext.userId();
        Long tenantId = UserContext.getTenantId();
        return logToolCall(sessionId, userId, tenantId, toolName, argumentsJson, requiresConfirm);
    }

    /**
     * 内部回调专用：在 Python /complete 回调链路中写入工具调用记录（无 UserContext）。
     * 返回新生成的 ai_cs_tool_call.id。
     */
    @Transactional
    public long logToolCall(Long sessionId, Long userId, Long tenantId,
                            String toolName, String argumentsJson, boolean requiresConfirm) {
        if (sessionId == null || sessionId <= 0 || userId == null || tenantId == null) return 0L;
        GeneratedKeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            var ps = connection.prepareStatement(
                    "INSERT INTO ai_cs_tool_call(session_id, user_id, tenant_id, tool_name, arguments, status, requires_confirm, created_time) " +
                            "VALUES(?,?,?,?,?,'pending',?,NOW())", java.sql.Statement.RETURN_GENERATED_KEYS);
            ps.setLong(1, sessionId);
            ps.setLong(2, userId);
            ps.setLong(3, tenantId);
            ps.setString(4, toolName);
            ps.setString(5, argumentsJson);
            ps.setInt(6, requiresConfirm ? 1 : 0);
            return ps;
        }, keyHolder);
        return keyHolder.getKey().longValue();
    }

    /**
     * 查询单条工具调用记录（confirmTool 用，用于透传 tool_name/arguments 给 Python）。
     * 返回空 Map 表示不存在。
     */
    public Map<String, Object> getToolCall(Long toolCallId) {
        if (toolCallId == null || toolCallId <= 0) return java.util.Collections.emptyMap();
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, session_id, user_id, tenant_id, tool_name, arguments, status, requires_confirm " +
                        "FROM ai_cs_tool_call WHERE id=?", toolCallId);
        return rows.isEmpty() ? java.util.Collections.emptyMap() : rows.get(0);
    }

    @Transactional
    public void updateToolCallStatus(long toolCallId, String status, String resultJson) {
        jdbcTemplate.update(
                "UPDATE ai_cs_tool_call SET status=?, result=?, updated_time=NOW() WHERE id=?",
                status, resultJson, toolCallId);
    }

    // ==================== 计费配置 ====================

    public Map<String, Object> getBillingConfig() {
        Long tenantId = UserContext.getTenantId();
        return getBillingConfig(tenantId);
    }

    public Map<String, Object> getBillingConfig(Long tenantId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id, per_message_tokens, max_context_messages, casual_threshold, casual_reminder_text, daily_free_quota, enabled " +
                        "FROM ai_cs_billing_config WHERE tenant_id <=> ? ORDER BY tenant_id IS NULL, tenant_id LIMIT 1", tenantId);
        Map<String, Object> res = new LinkedHashMap<>();
        if (rows.isEmpty()) {
            res.put("perMessageTokens", 3);
            res.put("maxContextMessages", 50);
            res.put("casualThreshold", 5);
            res.put("casualReminderText", DEFAULT_CASUAL_REMINDER);
            res.put("dailyFreeQuota", 10);
            res.put("enabled", true);
        } else {
            Map<String, Object> row = rows.get(0);
            res.put("id", row.get("id"));
            res.put("tenantId", row.get("tenant_id"));
            res.put("perMessageTokens", row.get("per_message_tokens"));
            res.put("maxContextMessages", row.get("max_context_messages"));
            res.put("casualThreshold", row.get("casual_threshold"));
            res.put("casualReminderText", row.getOrDefault("casual_reminder_text", DEFAULT_CASUAL_REMINDER));
            Object dfq = row.get("daily_free_quota");
            res.put("dailyFreeQuota", dfq == null ? 10 : ((Number) dfq).intValue());
            res.put("enabled", ((Number) row.get("enabled")).intValue() == 1);
        }
        return res;
    }

    public int getPerMessageTokens(Long tenantId) {
        try {
            Integer v = jdbcTemplate.queryForObject(
                    "SELECT per_message_tokens FROM ai_cs_billing_config WHERE tenant_id <=> ? ORDER BY tenant_id IS NULL, tenant_id LIMIT 1",
                    Integer.class, tenantId);
            return v == null ? 3 : v;
        } catch (Exception e) {
            return 3;
        }
    }

    /** 用户每日免费额度（条数）。 */
    public int getDailyFreeQuota(Long tenantId) {
        try {
            Integer v = jdbcTemplate.queryForObject(
                    "SELECT daily_free_quota FROM ai_cs_billing_config WHERE tenant_id <=> ? ORDER BY tenant_id IS NULL, tenant_id LIMIT 1",
                    Integer.class, tenantId);
            return v == null ? 10 : v;
        } catch (Exception e) {
            return 10;
        }
    }

    /** 用户今日已发送的用户消息条数（基于 ai_cs_message 表统计）。 */
    public int getTodayUserMessageCount(Long userId, Long tenantId) {
        try {
            Integer cnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM ai_cs_message WHERE user_id=? AND tenant_id=? AND role='user' " +
                            "AND DATE(created_time)=CURDATE()",
                    Integer.class, userId, tenantId);
            return cnt == null ? 0 : cnt;
        } catch (Exception e) {
            return 0;
        }
    }

    public int getMaxContextMessages(Long tenantId) {
        try {
            Integer v = jdbcTemplate.queryForObject(
                    "SELECT max_context_messages FROM ai_cs_billing_config WHERE tenant_id <=> ? ORDER BY tenant_id IS NULL, tenant_id LIMIT 1",
                    Integer.class, tenantId);
            return v == null ? 50 : v;
        } catch (Exception e) {
            return 50;
        }
    }

    public int getCasualThreshold(Long tenantId) {
        try {
            Integer v = jdbcTemplate.queryForObject(
                    "SELECT casual_threshold FROM ai_cs_billing_config WHERE tenant_id <=> ? ORDER BY tenant_id IS NULL, tenant_id LIMIT 1",
                    Integer.class, tenantId);
            return v == null ? 5 : v;
        } catch (Exception e) {
            return 5;
        }
    }

    @Transactional
    public Map<String, Object> saveBillingConfig(Map<String, Object> data) {
        // admin 后台调用时 UserContext 未被设置（JwtAuthFilter 仅设置 AdminContext/TenantContext），
        // 此处允许 tenantId 为 null 以写入"平台级"配置（tenant_id IS NULL 的全局记录）。
        Long tenantId = UserContext.getTenantId();
        if (tenantId == null) tenantId = TenantContext.getCurrentTenantId();
        boolean isAdminCall = AdminContext.userId() != null;
        if (tenantId == null && !isAdminCall) {
            throw new BizException(401, "请先登录");
        }
        int perMessageTokens = parseInt(data.get("perMessageTokens"), 3);
        int maxContext = parseInt(data.get("maxContextMessages"), 50);
        int casualThreshold = parseInt(data.get("casualThreshold"), 5);
        int dailyFreeQuota = parseInt(data.get("dailyFreeQuota"), 10);
        if (dailyFreeQuota < 0) dailyFreeQuota = 0;
        String reminderText = text(data.get("casualReminderText"));
        if (!StringUtils.hasText(reminderText)) reminderText = DEFAULT_CASUAL_REMINDER;
        int enabled = parseBool(data.get("enabled")) ? 1 : 0;
        // upsert（使用 queryForList 避免首次保存无记录时抛出 EmptyResultDataAccessException）
        List<Map<String, Object>> existingRows = jdbcTemplate.queryForList(
                "SELECT id FROM ai_cs_billing_config WHERE tenant_id <=> ? ORDER BY tenant_id IS NULL, tenant_id LIMIT 1",
                tenantId);
        if (existingRows.isEmpty()) {
            jdbcTemplate.update(
                    "INSERT INTO ai_cs_billing_config(tenant_id, per_message_tokens, max_context_messages, casual_threshold, casual_reminder_text, daily_free_quota, enabled, created_time, updated_time) " +
                            "VALUES(?,?,?,?,?,?,?,NOW(),NOW())",
                    tenantId, perMessageTokens, maxContext, casualThreshold, reminderText, dailyFreeQuota, enabled);
        } else {
            Integer existing = ((Number) existingRows.get(0).get("id")).intValue();
            jdbcTemplate.update(
                    "UPDATE ai_cs_billing_config SET per_message_tokens=?, max_context_messages=?, casual_threshold=?, casual_reminder_text=?, daily_free_quota=?, enabled=?, updated_time=NOW() WHERE id=?",
                    perMessageTokens, maxContext, casualThreshold, reminderText, dailyFreeQuota, enabled, existing);
        }
        return getBillingConfig(tenantId);
    }

    // ==================== 知识库 CRUD ====================

    public List<Map<String, Object>> knowledgeCategories() {
        // 12 个预设分类
        return Arrays.asList(
                cat("system_usage", "系统使用", 1),
                cat("xianyu_account", "闲鱼账号", 2),
                cat("product_publish", "商品发布", 3),
                cat("auto_reply", "自动回复", 4),
                cat("auto_delivery", "自动发货", 5),
                cat("card_key", "卡密管理", 6),
                cat("workflow", "工作流", 7),
                cat("scheduled_task", "定时任务", 8),
                cat("ai_customer_service", "AI 客服", 9),
                cat("membership", "会员权益", 10),
                cat("troubleshoot", "故障排查", 11),
                cat("faq", "常见问题", 12)
        );
    }

    private Map<String, Object> cat(String key, String label, int order) {
        Map<String, Object> m = new LinkedHashMap<>();
        // 同时返回 key 与 category，前端 AiCsKnowledgeCategory 接口使用 key，
        // 兼容历史代码中可能读取 category 的调用方
        m.put("key", key);
        m.put("category", key);
        m.put("label", label);
        m.put("sortOrder", order);
        return m;
    }

    public PageResult<Map<String, Object>> pageKnowledge(int current, int size, String category, String keyword, String enabled) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 100);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (StringUtils.hasText(category)) {
            where.append(" AND category=?");
            args.add(category.trim());
        }
        if (StringUtils.hasText(keyword)) {
            where.append(" AND (title LIKE ? OR content LIKE ? OR keywords LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw);
        }
        if (StringUtils.hasText(enabled)) {
            where.append(" AND enabled=?");
            args.add("true".equalsIgnoreCase(enabled.trim()) || "1".equals(enabled.trim()) ? 1 : 0);
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM ai_cs_knowledge" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time " +
                        "FROM ai_cs_knowledge" + where + " ORDER BY priority DESC, sort_order ASC, id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    @Transactional
    public Map<String, Object> saveKnowledge(Map<String, Object> data) {
        Long tenantId = UserContext.getTenantId();
        Object id = data.get("id");
        String category = text(data.get("category"));
        String title = text(data.get("title"));
        String content = text(data.get("content"));
        if (!StringUtils.hasText(category)) throw new BizException(400, "分类不能为空");
        if (!StringUtils.hasText(title)) throw new BizException(400, "标题不能为空");
        if (!StringUtils.hasText(content)) throw new BizException(400, "内容不能为空");
        String keywords = text(data.get("keywords"));
        int priority = parseInt(data.get("priority"), 50);
        int enabled = parseBool(data.get("enabled")) ? 1 : 0;
        int sortOrder = parseInt(data.get("sortOrder"), 0);
        if (id == null || String.valueOf(id).isBlank()) {
            GeneratedKeyHolder keyHolder = new GeneratedKeyHolder();
            jdbcTemplate.update(connection -> {
                var ps = connection.prepareStatement(
                        "INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) " +
                                "VALUES(?,?,?,?,?,?,?,?,NOW(),NOW())", java.sql.Statement.RETURN_GENERATED_KEYS);
                ps.setObject(1, tenantId);
                ps.setString(2, category);
                ps.setString(3, title);
                ps.setString(4, content);
                ps.setString(5, keywords);
                ps.setInt(6, priority);
                ps.setInt(7, enabled);
                ps.setInt(8, sortOrder);
                return ps;
            }, keyHolder);
            return knowledgeDetail(keyHolder.getKey().longValue());
        }
        long kid = Long.parseLong(String.valueOf(id));
        jdbcTemplate.update(
                "UPDATE ai_cs_knowledge SET category=?, title=?, content=?, keywords=?, priority=?, enabled=?, sort_order=?, updated_time=NOW() WHERE id=?",
                category, title, content, keywords, priority, enabled, sortOrder, kid);
        return knowledgeDetail(kid);
    }

    public Map<String, Object> knowledgeDetail(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time " +
                        "FROM ai_cs_knowledge WHERE id=?", id);
        if (rows.isEmpty()) throw new BizException(404, "知识库条目不存在");
        return rows.get(0);
    }

    @Transactional
    public void deleteKnowledge(long id) {
        jdbcTemplate.update("DELETE FROM ai_cs_knowledge WHERE id=?", id);
    }

    // ==================== 后台统计/审计 ====================

    public Map<String, Object> adminStats() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("totalSessions", optionalLong("SELECT COUNT(*) FROM ai_cs_session"));
        m.put("activeSessions", optionalLong("SELECT COUNT(*) FROM ai_cs_session WHERE status=1"));
        m.put("totalMessages", optionalLong("SELECT COUNT(*) FROM ai_cs_message"));
        m.put("userMessages", optionalLong("SELECT COUNT(*) FROM ai_cs_message WHERE role='user'"));
        m.put("assistantMessages", optionalLong("SELECT COUNT(*) FROM ai_cs_message WHERE role='assistant'"));
        m.put("totalTokensCharged", optionalLong("SELECT COALESCE(SUM(tokens_charged),0) FROM ai_cs_message"));
        m.put("casualCount", optionalLong("SELECT COALESCE(SUM(casual_count),0) FROM ai_cs_session"));
        m.put("todaySessions", optionalLong("SELECT COUNT(*) FROM ai_cs_session WHERE DATE(created_time)=CURDATE()"));
        m.put("todayMessages", optionalLong("SELECT COUNT(*) FROM ai_cs_message WHERE DATE(created_time)=CURDATE()"));
        m.put("todayTokens", optionalLong("SELECT COALESCE(SUM(tokens_charged),0) FROM ai_cs_message WHERE DATE(created_time)=CURDATE()"));
        m.put("knowledgeCount", optionalLong("SELECT COUNT(*) FROM ai_cs_knowledge"));
        m.put("toolCallCount", optionalLong("SELECT COUNT(*) FROM ai_cs_tool_call"));
        return m;
    }

    public PageResult<Map<String, Object>> adminPageSessions(int current, int size, Long userId, String status) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 100);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (userId != null) {
            where.append(" AND s.user_id=?");
            args.add(userId);
        }
        if (StringUtils.hasText(status)) {
            where.append(" AND s.status=?");
            args.add("active".equalsIgnoreCase(status.trim()) ? 1 : 0);
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_cs_session s" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT s.id, s.session_token, s.user_id, u.username, s.tenant_id, s.status, s.message_count, s.casual_count, s.casual_reminded, " +
                        "LEFT(s.compressed_summary, 200) AS compressed_summary_preview, s.last_active_time, s.created_time " +
                        "FROM ai_cs_session s LEFT JOIN sys_user u ON u.id=s.user_id" + where +
                        " ORDER BY s.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    public PageResult<Map<String, Object>> adminPageMessages(int current, int size, Long sessionId, Long userId, String role) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 100);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (sessionId != null) {
            where.append(" AND m.session_id=?");
            args.add(sessionId);
        }
        if (userId != null) {
            where.append(" AND m.user_id=?");
            args.add(userId);
        }
        if (StringUtils.hasText(role)) {
            where.append(" AND m.role=?");
            args.add(role.trim());
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_cs_message m" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        // 返回 content 字段（完整内容，前端表格有溢出处理）
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT m.id, m.session_id, m.user_id, u.username, m.tenant_id, m.role, m.content, " +
                        "m.tokens_charged, m.is_casual, m.tool_calls, m.created_time " +
                        "FROM ai_cs_message m LEFT JOIN sys_user u ON u.id=m.user_id" + where +
                        " ORDER BY m.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    /**
     * 后台会话审计：获取指定会话的全部消息（按时间正序，返回完整内容）。
     * 供"对话气泡视图"使用，一次性加载完整对话流，不分页。
     * 上限 1000 条以防异常会话拖垮接口。
     */
    public List<Map<String, Object>> adminListSessionMessages(Long sessionId) {
        if (sessionId == null || sessionId <= 0) {
            return java.util.Collections.emptyList();
        }
        return jdbcTemplate.queryForList(
                "SELECT m.id, m.session_id, m.user_id, u.username, m.tenant_id, m.role, m.content, " +
                        "m.tokens_charged, m.is_casual, m.tool_calls, m.created_time " +
                        "FROM ai_cs_message m LEFT JOIN sys_user u ON u.id=m.user_id " +
                        "WHERE m.session_id=? ORDER BY m.id ASC LIMIT 1000",
                sessionId);
    }

    public PageResult<Map<String, Object>> adminPageToolCalls(int current, int size, Long sessionId, String status) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 100);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (sessionId != null) {
            where.append(" AND t.session_id=?");
            args.add(sessionId);
        }
        if (StringUtils.hasText(status)) {
            where.append(" AND t.status=?");
            args.add(status.trim());
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM ai_cs_tool_call t" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize); pageArgs.add(offset);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT t.id, t.session_id, t.user_id, u.username, t.tenant_id, t.tool_name, t.arguments, t.status, t.result, t.requires_confirm, t.created_time, t.updated_time " +
                        "FROM ai_cs_tool_call t LEFT JOIN sys_user u ON u.id=t.user_id" + where +
                        " ORDER BY t.id DESC LIMIT ? OFFSET ?", pageArgs.toArray());
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    // ==================== 工具方法 ====================

    private String generateSessionToken(Long userId) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            String raw = userId + ":" + System.nanoTime() + ":" + UUID.randomUUID();
            byte[] digest = md.digest(raw.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) sb.append(String.format("%02x", b));
            return sb.substring(0, 48);
        } catch (Exception e) {
            return UUID.randomUUID().toString().replace("-", "");
        }
    }

    private void bumpDailyStat(Long userId, Long tenantId, String field, int delta) {
        try {
            String today = LocalDate.now().toString();
            // upsert
            int updated = jdbcTemplate.update(
                    "UPDATE ai_cs_daily_stat SET " + dailyStatColumn(field) + "=" + dailyStatColumn(field) + "+?, updated_time=NOW() " +
                            "WHERE stat_date=? AND user_id=?",
                    delta, java.sql.Date.valueOf(today), userId);
            if (updated == 0) {
                jdbcTemplate.update(
                        "INSERT INTO ai_cs_daily_stat(stat_date, user_id, tenant_id, " + dailyStatColumn(field) + ", created_time, updated_time) " +
                                "VALUES(?,?,?,1,NOW(),NOW()) ON DUPLICATE KEY UPDATE " + dailyStatColumn(field) + "=" + dailyStatColumn(field) + "+?, updated_time=NOW()",
                        java.sql.Date.valueOf(today), userId, tenantId, delta, delta);
            }
        } catch (Exception e) {
            log.warn("更新每日统计失败 userId={}, field={}, delta={}: {}", userId, field, delta, e.getMessage());
        }
    }

    private String dailyStatColumn(String field) {
        switch (field) {
            case "session": return "session_count";
            case "user_message": return "user_message_count";
            case "assistant_message": return "assistant_message_count";
            case "tokens": return "tokens_charged";
            case "casual": return "casual_count";
            default: return "session_count";
        }
    }

    private long optionalLong(String sql) {
        try {
            Long v = jdbcTemplate.queryForObject(sql, Long.class);
            return v == null ? 0 : v;
        } catch (Exception e) {
            return 0;
        }
    }

    private static int parseInt(Object o, int def) {
        if (o == null) return def;
        try { return Integer.parseInt(String.valueOf(o)); } catch (Exception e) { return def; }
    }

    private static boolean parseBool(Object o) {
        if (o == null) return true;
        String s = String.valueOf(o).trim().toLowerCase();
        return "true".equals(s) || "1".equals(s) || "yes".equals(s) || "on".equals(s);
    }

    private static String text(Object o) {
        return o == null ? "" : String.valueOf(o);
    }
}
