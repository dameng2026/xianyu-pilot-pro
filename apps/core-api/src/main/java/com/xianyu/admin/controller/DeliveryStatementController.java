package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.DeliveryStatementSessionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.Set;

/**
 * 发货声明配置控制器
 * 对应前端 DeliveryStatementPage
 * 同时提供声明会话查询/手动确认/手动取消端点（供 DeliveryRecordsPage 使用）
 */
@RestController
@RequestMapping("/api/auto-delivery/statement")
public class DeliveryStatementController {
    private static final Logger log = LoggerFactory.getLogger(DeliveryStatementController.class);
    private static final Set<String> ALLOWED_SCOPES = Set.of("all", "specific");
    private static final Set<String> ALLOWED_SESSION_STATUSES =
            Set.of("", "declaring", "waiting", "confirmed", "cancelled", "failed");

    private final JdbcTemplate jdbcTemplate;
    private final DeliveryStatementSessionService sessionService;
    private static final String TABLE = "delivery_statement";

    public DeliveryStatementController(JdbcTemplate jdbcTemplate,
                                       DeliveryStatementSessionService sessionService) {
        this.jdbcTemplate = jdbcTemplate;
        this.sessionService = sessionService;
    }

    /**
     * 获取发货声明配置
     */
    @GetMapping
    public Result<Map<String, Object>> get() {
        Long tenantId = requireTenant();
        try {
            Map<String, Object> row = jdbcTemplate.queryForMap(
                    "SELECT * FROM " + TABLE + " WHERE tenant_id=? AND deleted=0 LIMIT 1", tenantId);
            return Result.ok(row);
        } catch (EmptyResultDataAccessException e) {
            return Result.ok(Map.of("enabled", false, "scope", "all"));
        } catch (Exception e) {
            log.error("查询发货声明失败, tenantId={}, errorType={}", tenantId, e.getClass().getSimpleName());
            throw new BizException(503, "发货声明配置暂时无法加载，请稍后重试");
        }
    }

    /**
     * 保存发货声明配置
     */
    @PutMapping
    public Result<Void> save(@RequestBody Map<String, Object> body) {
        Long tenantId = requireTenant();
        requireBody(body);
        boolean enabled = booleanValue(body.getOrDefault("enabled", false), "enabled");
        String content = stringValue(body.getOrDefault("content", ""), "content");
        String scope = stringValue(body.getOrDefault("scope", "all"), "scope").trim();
        if (!ALLOWED_SCOPES.contains(scope)) {
            throw new BizException(400, "scope 仅支持 all 或 specific");
        }
        if (enabled && content.isBlank()) {
            throw new BizException(400, "启用发货声明时内容不能为空");
        }

        saveStatement(tenantId, enabled, content, scope);
        return Result.ok(null);
    }

    /**
     * 切换启用状态
     */
    @PatchMapping("/toggle")
    public Result<Void> toggle(@RequestBody Map<String, Object> body) {
        Long tenantId = requireTenant();
        requireBody(body);
        if (!body.containsKey("enabled")) {
            throw new BizException(400, "enabled 不能为空");
        }
        boolean enabled = booleanValue(body.get("enabled"), "enabled");
        saveToggle(tenantId, enabled);
        return Result.ok(null);
    }

    /**
     * 预览声明
     */
    @PostMapping("/preview")
    public Result<Map<String, Object>> preview(@RequestBody Map<String, Object> body) {
        requireTenant();
        requireBody(body);
        String content = stringValue(body.getOrDefault("content", ""), "content");
        if (content.isBlank()) {
            throw new BizException(400, "声明内容不能为空");
        }
        // 预览仅展示变量替换后的格式，不伪造业务数据
        String preview = content
                .replace("{订单编号}", "【订单编号】")
                .replace("{商品标题}", "【商品标题】")
                .replace("{买家昵称}", "【买家昵称】")
                .replace("{发货确认链接}", "【发货确认链接】");
        return Result.ok(Map.of("preview", preview));
    }

    private void saveStatement(Long tenantId, boolean enabled, String content, String scope) {
        Long id = findExistingId(tenantId, "保存");
        try {
            int affected = id == null
                    ? jdbcTemplate.update(
                            "INSERT INTO " + TABLE + "(tenant_id, enabled, content, scope, created_time, updated_time, deleted) VALUES(?,?,?,?,NOW(),NOW(),0)",
                            tenantId, enabled, content, scope)
                    : jdbcTemplate.update(
                            "UPDATE " + TABLE + " SET enabled=?, content=?, scope=?, updated_time=NOW() WHERE id=? AND tenant_id=?",
                            enabled, content, scope, id, tenantId);
            requireSingleRow(affected);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("保存发货声明失败, tenantId={}, statementId={}, errorType={}", tenantId, id, e.getClass().getSimpleName());
            throw unavailable("保存");
        }
    }

    private void saveToggle(Long tenantId, boolean enabled) {
        Long id = findExistingId(tenantId, "切换");
        if (enabled && id == null) {
            throw new BizException(409, "请先保存声明内容，再启用发货声明");
        }
        try {
            if (enabled) {
                String content = jdbcTemplate.queryForObject(
                        "SELECT content FROM " + TABLE + " WHERE id=? AND tenant_id=? AND deleted=0",
                        String.class,
                        id,
                        tenantId);
                if (content == null || content.isBlank()) {
                    throw new BizException(409, "请先保存声明内容，再启用发货声明");
                }
            }
            int affected = id == null
                    ? jdbcTemplate.update(
                            "INSERT INTO " + TABLE + "(tenant_id, enabled, content, scope, created_time, updated_time, deleted) VALUES(?,?,?,?,NOW(),NOW(),0)",
                            tenantId, enabled, "", "all")
                    : jdbcTemplate.update(
                            "UPDATE " + TABLE + " SET enabled=?, updated_time=NOW() WHERE id=? AND tenant_id=?",
                            enabled, id, tenantId);
            requireSingleRow(affected);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("切换发货声明失败, tenantId={}, statementId={}, errorType={}", tenantId, id, e.getClass().getSimpleName());
            throw unavailable("切换");
        }
    }

    private Long findExistingId(Long tenantId, String operation) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT id FROM " + TABLE + " WHERE tenant_id=? AND deleted=0 LIMIT 1",
                    Long.class,
                    tenantId);
        } catch (EmptyResultDataAccessException e) {
            return null;
        } catch (Exception e) {
            log.error("{}发货声明前查询失败, tenantId={}, errorType={}", operation, tenantId, e.getClass().getSimpleName());
            throw unavailable(operation);
        }
    }

    private void requireSingleRow(int affected) {
        if (affected != 1) {
            throw unavailable("保存");
        }
    }

    private BizException unavailable(String operation) {
        return new BizException(503, "发货声明配置暂时无法" + operation + "，请稍后重试");
    }

    private Long requireTenant() {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        return tenantId;
    }

    private void requireBody(Map<String, Object> body) {
        if (body == null) {
            throw new BizException(400, "请求内容不能为空");
        }
    }

    private boolean booleanValue(Object value, String field) {
        if (value instanceof Boolean bool) return bool;
        if (value instanceof Number number) {
            double numeric = number.doubleValue();
            if (numeric == 0.0d || numeric == 1.0d) return numeric == 1.0d;
        }
        if (value instanceof String text) {
            String normalized = text.trim().toLowerCase();
            if ("true".equals(normalized) || "1".equals(normalized)) return true;
            if ("false".equals(normalized) || "0".equals(normalized)) return false;
        }
        throw new BizException(400, field + " 必须为布尔值");
    }

    private String stringValue(Object value, String field) {
        if (value instanceof String text) return text;
        throw new BizException(400, field + " 必须为字符串");
    }

    // ============================================================
    // 声明会话（sessions）端点：供发货记录页"等待确认"标签使用
    // ============================================================

    /**
     * 分页查询声明会话列表
     *
     * @param status  状态过滤：declaring/waiting/confirmed/cancelled，为空查全部
     * @param accountId 账号 ID 过滤（可选）
     */
    @GetMapping("/sessions")
    public Result<Map<String, Object>> listSessions(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Long accountId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        Long tenantId = requireTenant();
        String normalizedStatus = status == null ? "" : status.trim();
        if (!ALLOWED_SESSION_STATUSES.contains(normalizedStatus)) {
            throw new BizException(400, "status 仅支持 declaring/waiting/confirmed/cancelled");
        }
        try {
            return Result.ok(sessionService.listSessions(tenantId, accountId, normalizedStatus, page, size));
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("查询声明会话列表失败 tenantId={} errorType={}", tenantId, e.getClass().getSimpleName());
            throw new BizException(503, "声明会话列表暂时无法加载，请稍后重试");
        }
    }

    /**
     * 卖家手动确认声明 → 触发该订单发货
     */
    @PostMapping("/sessions/{id}/confirm")
    public Result<Void> manualConfirm(@PathVariable("id") Long sessionId) {
        Long tenantId = requireTenant();
        try {
            sessionService.manualConfirm(tenantId, sessionId);
            return Result.ok(null);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("卖家手动确认声明失败 tenantId={} sessionId={} errorType={}",
                    tenantId, sessionId, e.getClass().getSimpleName());
            throw new BizException(503, "确认操作暂时无法完成，请稍后重试");
        }
    }

    /**
     * 卖家手动取消声明 → 通知买家+不发货
     */
    @PostMapping("/sessions/{id}/cancel")
    public Result<Void> manualCancel(@PathVariable("id") Long sessionId) {
        Long tenantId = requireTenant();
        try {
            sessionService.manualCancel(tenantId, sessionId);
            return Result.ok(null);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("卖家手动取消声明失败 tenantId={} sessionId={} errorType={}",
                    tenantId, sessionId, e.getClass().getSimpleName());
            throw new BizException(503, "取消操作暂时无法完成，请稍后重试");
        }
    }
}
