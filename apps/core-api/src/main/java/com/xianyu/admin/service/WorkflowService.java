package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.PreparedStatementCreator;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * 工作流定义与执行服务。
 * 边界：Java 负责定义、权限、执行记录、DAG 校验、扣费入口；Python 负责真正执行商品搜索、AI、生图、润色、发布与通知动作。
 */
@Service
public class WorkflowService {
    private static final Logger log = LoggerFactory.getLogger(WorkflowService.class);
    private static final long AVG_ITEM_TIMING_CACHE_TTL_MS = 60_000L;
    private final JdbcTemplate jdbcTemplate;
    private final AutomationClient automationClient;
    private final WorkflowAccountValidationService workflowAccountValidationService;
    private final WorkflowAddressValidationService workflowAddressValidationService;
    private final ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule());
    private final Map<String, Boolean> tableColumnExistsCache = new ConcurrentHashMap<>();
    private volatile long cachedAvgItemTimingMs = 0L;
    private volatile long cachedAvgItemTimingAtMs = 0L;

    public WorkflowService(JdbcTemplate jdbcTemplate,
                           AutomationClient automationClient,
                           WorkflowAccountValidationService workflowAccountValidationService,
                           WorkflowAddressValidationService workflowAddressValidationService) {
        this.jdbcTemplate = jdbcTemplate;
        this.automationClient = automationClient;
        this.workflowAccountValidationService = workflowAccountValidationService;
        this.workflowAddressValidationService = workflowAddressValidationService;
    }

    public Map<String, Object> overview() {
        Long tenantId = tenantId();
        Map<String, Object> result = new LinkedHashMap<>();
        // 工作流定义统计：1 条 SQL 替代 2 条 COUNT
        Map<String, Object> defStats = jdbcTemplate.queryForMap(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) AS enabled " +
                "FROM workflow_definition WHERE tenant_id=? AND deleted=0", tenantId);
        long workflowCount = longValue(defStats.get("total"), 0L);
        result.put("workflowCount", workflowCount);
        result.put("enabledCount", longValue(defStats.get("enabled"), 0L));
        // 执行统计：1 条 SQL 替代 5 条 COUNT
        Map<String, Object> execStats = jdbcTemplate.queryForMap(
                "SELECT COUNT(*) AS total, " +
                "SUM(CASE WHEN DATE(created_time)=CURDATE() THEN 1 ELSE 0 END) AS today, " +
                "SUM(CASE WHEN status IN ('running','queued') THEN 1 ELSE 0 END) AS running, " +
                "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, " +
                "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed " +
                "FROM workflow_execution WHERE tenant_id=? AND deleted=0", tenantId);
        long execTotal = longValue(execStats.get("total"), 0L);
        long execSuccess = longValue(execStats.get("success"), 0L);
        result.put("todayExecutionCount", longValue(execStats.get("today"), 0L));
        result.put("runningCount", longValue(execStats.get("running"), 0L));
        result.put("failedCount", longValue(execStats.get("failed"), 0L));
        result.put("successRate", execTotal == 0 ? 0 : Math.round(execSuccess * 10000.0 / execTotal) / 100.0);
        return result;
    }

    public PageResult<Map<String, Object>> listDefinitions(String keyword, String status, int current, int size) {
        Long tenantId = tenantId();
        // 懒初始化：如果当前租户没有任何工作流，自动创建默认工作流（商品搜索+image-2+不筛选）
        ensureDefaultWorkflow(tenantId);
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE d.tenant_id=? AND d.deleted=0 ");
        args.add(tenantId);
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (d.name LIKE ? OR d.description LIKE ?) ");
            args.add("%" + keyword.trim() + "%");
            args.add("%" + keyword.trim() + "%");
        }
        if (status != null && !status.isBlank()) {
            where.append(" AND d.status=? ");
            args.add(status.trim());
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM workflow_definition d" + where, Long.class, args.toArray());
        List<Object> queryArgs = new ArrayList<>(args);
        queryArgs.add(offset);
        queryArgs.add(safeSize);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT d.*,
                       (SELECT COUNT(*) FROM workflow_node n WHERE n.workflow_id=d.id AND n.deleted=0) AS node_count,
                       (SELECT COUNT(*) FROM workflow_execution e WHERE e.workflow_id=d.id AND e.deleted=0) AS execution_count,
                       (SELECT e.status FROM workflow_execution e WHERE e.workflow_id=d.id AND e.deleted=0 ORDER BY e.created_time DESC LIMIT 1) AS last_status,
                       (SELECT e.created_time FROM workflow_execution e WHERE e.workflow_id=d.id AND e.deleted=0 ORDER BY e.created_time DESC LIMIT 1) AS last_run_time
                FROM workflow_definition d
                """ + where + " ORDER BY d.updated_time DESC, d.id DESC LIMIT ?, ?", queryArgs.toArray());
        return new PageResult<>(rows.stream().map(this::definitionRow).collect(Collectors.toList()), safeCurrent, safeSize, total == null ? 0 : total);
    }

    public Map<String, Object> detail(Long id) {
        Long tenantId = tenantId();
        Map<String, Object> workflow = jdbcTemplate.queryForMap("SELECT * FROM workflow_definition WHERE tenant_id=? AND id=? AND deleted=0", tenantId, id);
        List<Map<String, Object>> nodes = jdbcTemplate.queryForList("SELECT * FROM workflow_node WHERE tenant_id=? AND workflow_id=? AND deleted=0 ORDER BY sort_order ASC, id ASC", tenantId, id)
                .stream().map(this::nodeRow).collect(Collectors.toList());
        List<Map<String, Object>> edges = jdbcTemplate.queryForList("SELECT * FROM workflow_edge WHERE tenant_id=? AND workflow_id=? AND deleted=0 ORDER BY id ASC", tenantId, id)
                .stream().map(this::edgeRow).collect(Collectors.toList());
        Map<String, Object> result = definitionRow(workflow);
        result.put("nodes", nodes);
        result.put("edges", edges);
        result.put("validation", validateGraph(nodes, edges));
        return result;
    }

    @Transactional
    public Map<String, Object> create(Map<String, Object> body) {
        Long tenantId = tenantId();
        Long userId = userId();
        String name = text(body.get("name"));
        if (name.isBlank()) throw new BizException(500, "工作流名称不能为空");
        List<Map<String, Object>> nodes = mapList(body.get("nodes"));
        List<Map<String, Object>> edges = mapList(body.get("edges"));
        ensureValidForSave(nodes, edges);
        KeyHolder kh = new GeneratedKeyHolder();
        PreparedStatementCreator psc = con -> {
            PreparedStatement ps = con.prepareStatement("""
                    INSERT INTO workflow_definition(tenant_id,user_id,name,description,version,status,trigger_type,config_json,canvas_json,enabled,deleted,created_time,updated_time)
                    VALUES(?,?,?,?,1,'draft',?,?,?,0,0,NOW(),NOW())
                    """, Statement.RETURN_GENERATED_KEYS);
            ps.setObject(1, tenantId);
            ps.setObject(2, userId);
            ps.setString(3, name);
            ps.setString(4, text(body.get("description")));
            ps.setString(5, textOr(body.get("triggerType"), "manual"));
            ps.setString(6, json(body.getOrDefault("config", Map.of())));
            ps.setString(7, json(body.getOrDefault("canvas", Map.of())));
            return ps;
        };
        jdbcTemplate.update(psc, kh);
        Long id = Objects.requireNonNull(kh.getKey()).longValue();
        replaceNodesAndEdges(id, nodes, edges);
        return detail(id);
    }

    @Transactional
    public Map<String, Object> update(Long id, Map<String, Object> body) {
        Long tenantId = tenantId();
        ensureExists(id, tenantId);
        Map<String, Object> current = detail(id);
        List<Map<String, Object>> nodes = body.containsKey("nodes") ? mapList(body.get("nodes")) : mapList(current.get("nodes"));
        List<Map<String, Object>> edges = body.containsKey("edges") ? mapList(body.get("edges")) : mapList(current.get("edges"));
        ensureValidForSave(nodes, edges);
        Object enabledValue = body.containsKey("enabled") ? body.get("enabled") : current.get("enabled");
        jdbcTemplate.update("""
                UPDATE workflow_definition
                SET name=?, description=?, trigger_type=?, config_json=?, canvas_json=?, enabled=?, updated_time=NOW()
                WHERE tenant_id=? AND id=? AND deleted=0
                """, textOr(body.get("name"), text(current.get("name"))), textOr(body.get("description"), text(current.get("description"))), textOr(body.get("triggerType"), textOr(current.get("triggerType"), "manual")),
                json(body.getOrDefault("config", current.getOrDefault("config", Map.of()))), json(body.getOrDefault("canvas", current.getOrDefault("canvas", Map.of()))), boolInt(enabledValue), tenantId, id);
        replaceNodesAndEdges(id, nodes, edges);
        return detail(id);
    }

    @Transactional
    public void delete(Long id) {
        Long tenantId = tenantId();
        jdbcTemplate.update("UPDATE workflow_definition SET deleted=1, updated_time=NOW() WHERE tenant_id=? AND id=?", tenantId, id);
        jdbcTemplate.update("UPDATE workflow_node SET deleted=1, updated_time=NOW() WHERE tenant_id=? AND workflow_id=?", tenantId, id);
        jdbcTemplate.update("UPDATE workflow_edge SET deleted=1, updated_time=NOW() WHERE tenant_id=? AND workflow_id=?", tenantId, id);
    }

    @Transactional
    public Map<String, Object> publish(Long id) {
        Map<String, Object> detail = detail(id);
        List<Map<String, Object>> nodes = mapList(detail.get("nodes"));
        List<Map<String, Object>> edges = mapList(detail.get("edges"));
        Map<String, Object> validation = validateGraph(nodes, edges);
        if (!Boolean.TRUE.equals(validation.get("valid"))) {
            throw new BizException(500, "工作流校验未通过：" + validation.get("message"));
        }
        jdbcTemplate.update("""
                UPDATE workflow_definition
                SET status='published', enabled=1, version=version+1, published_time=NOW(), updated_time=NOW()
                WHERE tenant_id=? AND id=? AND deleted=0
                """, tenantId(), id);
        snapshotPublishedVersion(id);
        return detail(id);
    }

    // ★ 不加 @Transactional：execute 方法在事务中间调用 Python HTTP 接口，
    //   Python 查询 workflow_execution 表时看不到未提交的执行记录，导致 404 "工作流执行记录不存在"。
    //   移除事务后，insertExecution 立即提交，Python 可以查询到记录并开始后台执行。
    public Map<String, Object> execute(Long id, Map<String, Object> input) {
        try {
            Map<String, Object> definition = detail(id);
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> nodes = (List<Map<String, Object>>) definition.get("nodes");
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> edges = (List<Map<String, Object>>) definition.get("edges");
            if (nodes == null || edges == null) {
                throw new BizException(500, "工作流节点或连线数据异常");
            }
            Map<String, Object> validation = validateGraph(nodes, edges);
            if (!Boolean.TRUE.equals(validation.get("valid"))) {
                throw new BizException(500, "工作流校验未通过：" + validation.get("message"));
            }
            Long tenantId = tenantId();
            workflowAccountValidationService.assertExecutionAccountsReady(tenantId, nodes, input == null ? Map.of() : input);
            // ★ 运行前地址预检：校验 addressPayload 关键字段（prov/divisionId/gps/poiId 等）齐全，
            //   避免执行后才发现地址残缺导致发布失败（FAIL_BIZ_ITEM_EDIT_INVALID_MAP_LOCATION）
            workflowAddressValidationService.assertExecutionAddressReady(input == null ? Map.of() : input);
            String executionNo = "WF"
                    + DateTimeFormatter.ofPattern("yyyyMMddHHmmss").format(LocalDateTime.now())
                    + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
            Long execId;
            try {
                execId = insertExecution(tenantId, id, executionNo, textOr(input.get("triggerMode"), "manual"), json(input));
            } catch (Exception e) {
                log.error("创建工作流执行记录失败 id={}, errorType={}", id, e.getClass().getSimpleName());
                throw new BizException(500, "创建工作流执行记录失败，请稍后重试");
            }
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("tenantId", tenantId);
            payload.put("userId", userId());
            payload.put("workflowId", id);
            payload.put("executionId", execId);
            payload.put("executionNo", executionNo);
            payload.put("workflow", definition);
            payload.put("input", input == null ? Map.of() : input);
            try {
                // 工作流执行涉及多步骤（生图、发布、搜索等），单次同步执行可能远超 30 秒，
                // 这里使用 180 秒（与 GET 上限一致）避免 HttpTimeoutException 把整体执行直接判失败。
                Map<String, Object> result = automationClient.postInternalForData("/api/internal/workflows/" + id + "/execute", payload, 180);
                writeExecutionResult(execId, tenantId, id, result);
                return executionDetail(execId);
            } catch (Exception e) {
                log.error("调用自动化服务执行工作流失败 id={}, errorType={}, message={}", id, e.getClass().getSimpleName(), e.getMessage(), e);
                String publicFailure = "自动化服务暂时不可用，执行结果尚未确认，请稍后查看执行记录或重试";
                try {
                    jdbcTemplate.update("""
                            UPDATE workflow_execution
                            SET status='failed', progress=100, error_message=?, finished_time=NOW(), updated_time=NOW()
                            WHERE tenant_id=? AND id=?
                            """, publicFailure, tenantId, execId);
                    insertNodeExecution(tenantId, execId, id, "system-error", "自动化服务调用", "system", "failed", "{}", "{}", publicFailure, 0L);
                } catch (Exception dbEx) {
                    log.error("写入工作流执行失败记录时出错 id={}, errorType={}", execId, dbEx.getClass().getSimpleName());
                }
                return executionDetail(execId);
            }
        } catch (EmptyResultDataAccessException e) {
            log.error("工作流不存在 id={}", id);
            throw new BizException(404, "工作流不存在");
        }
    }

    public PageResult<Map<String, Object>> listVersions(Long workflowId, int current, int size) {
        Long tenantId = tenantId();
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM workflow_definition_version_snapshot WHERE tenant_id=? AND workflow_id=? AND deleted=0", Long.class, tenantId, workflowId);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT id, workflow_id, version, name, description, snapshot_type, created_time
                FROM workflow_definition_version_snapshot
                WHERE tenant_id=? AND workflow_id=? AND deleted=0
                ORDER BY version DESC, id DESC LIMIT ?, ?
                """, tenantId, workflowId, offset, safeSize);
        return new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total);
    }

    @Transactional
    public Map<String, Object> rollback(Long workflowId, int version) {
        Long tenantId = tenantId();
        if (version <= 0) throw new BizException(500, "请选择需要回滚的版本");
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("SELECT * FROM workflow_definition_version_snapshot WHERE tenant_id=? AND workflow_id=? AND version=? AND deleted=0 ORDER BY id DESC LIMIT 1", tenantId, workflowId, version);
        if (rows.isEmpty()) throw new BizException(404, "工作流版本快照不存在");
        Map<String, Object> snap = rows.get(0);
        jdbcTemplate.update("""
                UPDATE workflow_definition
                SET name=?, description=?, trigger_type=?, config_json=?, canvas_json=?, status='draft', enabled=0, updated_time=NOW()
                WHERE tenant_id=? AND id=? AND deleted=0
                """, text(snap.get("name")), text(snap.get("description")), textOr(snap.get("trigger_type"), "manual"), text(snap.get("config_json")), text(snap.get("canvas_json")), tenantId, workflowId);
        replaceNodesAndEdges(workflowId, mapList(parseJson(snap.get("nodes_json"))), mapList(parseJson(snap.get("edges_json"))));
        return detail(workflowId);
    }

    @Transactional
    public Map<String, Object> terminateExecution(Long executionId, Map<String, Object> body) {
        Long tenantId = tenantId();
        Map<String, Object> execution = executionRaw(tenantId, executionId);
        String status = text(execution.get("status"));
        if (!Set.of("queued", "running").contains(status)) {
            throw new BizException(500, "仅 queued/running 状态的执行可终止");
        }
        String reason = textOr(body.get("reason"), "用户手动终止");
        jdbcTemplate.update("""
                UPDATE workflow_execution SET status='terminated', progress=100, error_message=?, finished_time=NOW(), updated_time=NOW()
                WHERE tenant_id=? AND id=? AND deleted=0
                """, abbreviate(reason, 1000), tenantId, executionId);
        insertTimeline(tenantId, executionId, longValue(execution.get("workflow_id"), 0L), "system", "WARN", "terminated", "执行已终止", reason, Map.of("reason", reason));
        return executionDetail(executionId);
    }

    @Transactional
    public Map<String, Object> retryFailedNode(Long executionId, Map<String, Object> body) {
        Long tenantId = tenantId();
        Map<String, Object> execution = executionRaw(tenantId, executionId);
        Long workflowId = longValue(execution.get("workflow_id"), 0L);
        String nodeKey = textOr(body.get("nodeKey"), text(findFirstFailedNodeKey(tenantId, executionId)));
        Map<String, Object> input = new LinkedHashMap<>();
        Object parsedObj = parseJson(execution.get("input_json"));
        if (parsedObj instanceof Map<?, ?> raw) raw.forEach((k, v) -> input.put(String.valueOf(k), v));
        input.put("triggerMode", "retry");
        input.put("retryOfExecutionId", executionId);
        input.put("retryFromNodeKey", nodeKey);
        insertTimeline(tenantId, executionId, workflowId, nodeKey, "INFO", "retry_requested", "已发起失败节点重试", "从节点 " + nodeKey + " 重新发起一次工作流执行", input);
        return execute(workflowId, input);
    }

    /**
     * 继续执行已失败的工作流：复用原 execution_id，跳过已成功节点，从失败节点继续执行。
     * 调用 Python 内部接口 /api/internal/workflows/executions/{id}/continue
     *
     * ★ 运行前预检：继续执行同样需要校验账号登录状态和地址状态，
     *   避免账号掉线或地址失效时重复失败（与 execute 入口保持一致）。
     */
    public Map<String, Object> continueExecution(Long executionId) {
        Long tenantId = tenantId();
        Map<String, Object> execution = executionRaw(tenantId, executionId);
        String status = text(execution.get("status"));
        if ("running".equals(status)) {
            Map<String, Object> r = new LinkedHashMap<>();
            r.put("ok", false);
            r.put("message", "工作流正在运行中，无法继续执行");
            return r;
        }

        // ★ 运行前预检：解析原 execution 的 input_json，做账号 + 地址双重校验
        //   失效时返回 {ok:false, reason, message, ...}，不调用 Python 后台，
        //   前端可据 reason 提示用户修复账号/地址后再继续执行。
        Map<String, Object> input = parseInputJson(execution.get("input_json"));
        Map<String, Object> preflightFailure = preflightContinue(tenantId, executionId, execution, input);
        if (preflightFailure != null) {
            return preflightFailure;
        }

        // 调用 Python 内部接口，触发后台继续执行
        try {
            Map<String, Object> data = automationClient.postInternalForData(
                    "/api/internal/workflows/executions/" + executionId + "/continue",
                    Map.of("tenantId", tenantId), 30);
            // Python 立即返回 status='running'，不应覆盖 execution 表
            // 让 Python 后台任务完成后自行更新
            return data;
        } catch (Exception e) {
            log.error("继续执行失败 executionId={}, errorType={}", executionId, e.getClass().getSimpleName());
            Map<String, Object> r = new LinkedHashMap<>();
            r.put("ok", false);
            r.put("message", "自动化服务暂时不可用，未能确认继续执行，请稍后重试");
            return r;
        }
    }

    /**
     * 解析 execution.input_json 字符串为 Map。失败时返回空 Map。
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> parseInputJson(Object inputJsonRaw) {
        if (inputJsonRaw == null) return Map.of();
        if (inputJsonRaw instanceof Map) {
            return (Map<String, Object>) inputJsonRaw;
        }
        String s = String.valueOf(inputJsonRaw).trim();
        if (s.isEmpty()) return Map.of();
        try {
            Object parsed = objectMapper.readValue(s, Object.class);
            if (parsed instanceof Map) return (Map<String, Object>) parsed;
        } catch (Exception e) {
            log.warn("解析 execution.input_json 失败, errorType={}", e.getClass().getSimpleName());
        }
        return Map.of();
    }

    /**
     * 继续执行预检：账号登录状态 + 地址状态。
     *
     * @return 失败时返回 {ok:false, reason, message, ...}；通过时返回 null
     */
    private Map<String, Object> preflightContinue(Long tenantId, Long executionId,
                                                  Map<String, Object> execution, Map<String, Object> input) {
        // 0) 兼容历史坏数据：优先尝试用当前工作流定义中的发布节点地址修复旧 execution.input_json 里的残缺 addressPayload
        reconcileExecutionAddressPayload(execution, input);

        // 1) 地址预检（轻量、无外部调用，先做）
        Map<String, Object> addrResult = workflowAddressValidationService.validateExecutionAddress(input);
        if (!Boolean.TRUE.equals(addrResult.get("ok"))) {
            Map<String, Object> r = new LinkedHashMap<>();
            r.put("ok", false);
            r.put("reason", addrResult.get("reason"));
            r.put("message", "继续执行前地址校验失败：" + text(addrResult.get("message")));
            r.put("missingFields", addrResult.get("missingFields"));
            r.put("addressPayload", addrResult.get("addressPayload"));
            r.put("executionId", executionId);
            return r;
        }

        // 2) 账号预检：从 input_json 解析 workflow.nodes 取账号 ID（与 execute 入口同一服务）
        //    若 input.workflow 缺失则跳过节点级账号校验，仅校验 input 顶层的 selectedAccountIds
        Map<String, Object> workflow = (Map<String, Object>) input.get("workflow");
        List<Map<String, Object>> nodes = workflow != null ? mapList(workflow.get("nodes")) : List.of();
        List<Map<String, Object>> invalidAccounts;
        try {
            invalidAccounts = workflowAccountValidationService.validateExecutionAccounts(tenantId, nodes, input);
        } catch (Exception e) {
            log.warn("继续执行账号校验异常 executionId={}, errorType={}", executionId, e.getClass().getSimpleName());
            invalidAccounts = List.of();
        }
        if (!invalidAccounts.isEmpty()) {
            Map<String, Object> r = new LinkedHashMap<>();
            r.put("ok", false);
            r.put("reason", "ACCOUNT_LOGIN_INVALID");
            r.put("message", "继续执行前账号校验失败，请先重新登录以下账号");
            r.put("invalidAccounts", invalidAccounts);
            r.put("executionId", executionId);
            return r;
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private void reconcileExecutionAddressPayload(Map<String, Object> execution, Map<String, Object> input) {
        if (input == null) return;
        Object existingPayload = input.get("addressPayload");
        Map<String, Object> currentPayload = existingPayload instanceof Map<?, ?> raw
                ? new LinkedHashMap<>((Map<String, Object>) raw)
                : new LinkedHashMap<>();
        if (addressPayloadReady(currentPayload)) {
            return;
        }
        Object workflowIdObj = execution == null ? null : execution.get("workflow_id");
        if (!(workflowIdObj instanceof Number workflowIdNum)) {
            return;
        }
        try {
            Map<String, Object> workflow = detail(workflowIdNum.longValue());
            List<Map<String, Object>> nodes = mapList(workflow.get("nodes"));
            for (Map<String, Object> node : nodes) {
                if (!"PUBLISH".equalsIgnoreCase(text(node.get("nodeType")))) continue;
                Object configObj = node.get("config");
                if (!(configObj instanceof Map<?, ?> configRaw)) continue;
                Object addressObj = ((Map<?, ?>) configRaw).get("address");
                if (!(addressObj instanceof Map<?, ?> addressRaw)) continue;
                Map<String, Object> candidate = new LinkedHashMap<>();
                addressRaw.forEach((k, v) -> candidate.put(String.valueOf(k), v));
                if (!addressPayloadReady(candidate)) continue;
                currentPayload.putAll(candidate);
                input.put("addressPayload", currentPayload);
                return;
            }
        } catch (Exception e) {
            log.warn("修复继续执行地址载荷失败 executionId={}, errorType={}", execution == null ? null : execution.get("id"), e.getClass().getSimpleName());
        }
    }

    private boolean addressPayloadReady(Map<String, Object> payload) {
        if (payload == null || payload.isEmpty()) return false;
        for (String key : List.of("poiName", "prov", "city", "area", "divisionId", "gps", "poiId")) {
            Object value = payload.get(key);
            if (value == null) return false;
            String text = String.valueOf(value).trim();
            if (text.isEmpty() || "null".equalsIgnoreCase(text)) return false;
        }
        return true;
    }

    public PageResult<Map<String, Object>> listExecutions(Long workflowId, String status, int current, int size) {
        return listExecutions(workflowId, status, null, current, size);
    }

    public PageResult<Map<String, Object>> listExecutions(Long workflowId, String status, Long accountId, int current, int size) {
        Long tenantId = tenantId();
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE e.tenant_id=? AND e.deleted=0 ");
        args.add(tenantId);
        if (workflowId != null) { where.append(" AND e.workflow_id=? "); args.add(workflowId); }
        if (status != null && !status.isBlank()) { where.append(" AND e.status=? "); args.add(status.trim()); }
        // 按闲鱼账号过滤：优先从 workflow_state_variable 的 selected_account_ids 匹配，
        // 兜底从 workflow_node（TRIGGER 节点 config.selectedAccountIds）匹配，覆盖尚未开始执行的 queued 记录
        if (accountId != null) {
            where.append(" AND (EXISTS (SELECT 1 FROM workflow_state_variable sv WHERE sv.execution_id=e.id AND sv.var_name='selected_account_ids' AND sv.deleted=0 AND JSON_CONTAINS(sv.var_value, CAST(? AS JSON))) OR EXISTS (SELECT 1 FROM workflow_node n WHERE n.workflow_id=e.workflow_id AND n.node_type='TRIGGER' AND n.deleted=0 AND JSON_CONTAINS(JSON_EXTRACT(n.config_json, '$.selectedAccountIds'), CAST(? AS JSON)))) ");
            args.add(accountId);
            args.add(accountId);
        }
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM workflow_execution e" + where, Long.class, args.toArray());
        List<Object> queryArgs = new ArrayList<>(args);
        queryArgs.add(offset);
        queryArgs.add(safeSize);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT e.*, d.name AS workflow_name,
                       (SELECT COUNT(*) FROM workflow_node_execution n WHERE n.execution_id=e.id AND n.deleted=0) AS node_total,
                       (SELECT COUNT(*) FROM workflow_node_execution n WHERE n.execution_id=e.id AND n.deleted=0 AND n.status='success') AS node_success
                FROM workflow_execution e
                INNER JOIN (
                    SELECT id FROM workflow_execution e
                    """ + where + " ORDER BY created_time DESC, id DESC LIMIT ?, ?"
                + ") AS sorted_ids ON sorted_ids.id = e.id "
                + "LEFT JOIN workflow_definition d ON d.id=e.workflow_id", queryArgs.toArray());
        // 获取平均单商品耗时，用于计算预计完成时间
        long avgItemMs = getAverageItemTimingMs();
        // 批量预加载 running 状态执行的 state_variable，消除 N+1 查询（失败时降级为空 Map，不影响列表展示）
        Map<Long, Map<String, String>> stateVarMap;
        try {
            stateVarMap = batchLoadStateVariables(rows);
        } catch (Exception e) {
            log.warn("批量加载工作流状态变量失败，降级为空, errorType={}", e.getClass().getSimpleName());
            stateVarMap = Map.of();
        }
        final Map<Long, Map<String, String>> finalStateVarMap = stateVarMap;
        List<Map<String, Object>> resultList = rows.stream().map(row -> executionRow(row, avgItemMs, finalStateVarMap)).collect(Collectors.toList());
        return new PageResult<>(resultList, safeCurrent, safeSize, total == null ? 0 : total);
    }

    /** 批量加载当前页 running 状态执行的 target_count 和 selected_account_ids 状态变量 */
    private Map<Long, Map<String, String>> batchLoadStateVariables(List<Map<String, Object>> rows) {
        Map<Long, Map<String, String>> result = new HashMap<>();
        List<Long> runningIds = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            if ("running".equals(String.valueOf(row.get("status")))) {
                Object id = row.get("id");
                if (id != null) {
                    Long execId = Long.valueOf(String.valueOf(id));
                    runningIds.add(execId);
                    result.put(execId, new HashMap<>());
                }
            }
        }
        if (runningIds.isEmpty()) return result;
        StringBuilder placeholders = new StringBuilder();
        for (int i = 0; i < runningIds.size(); i++) {
            if (i > 0) placeholders.append(",");
            placeholders.append("?");
        }
        List<Object> sqlArgs = new ArrayList<>(runningIds);
        sqlArgs.add("target_count");
        sqlArgs.add("selected_account_ids");
        List<Map<String, Object>> vars = jdbcTemplate.queryForList(
                "SELECT execution_id, var_name, var_value FROM workflow_state_variable " +
                "WHERE execution_id IN (" + placeholders + ") AND var_name IN (?, ?) AND deleted=0",
                sqlArgs.toArray());
        for (Map<String, Object> v : vars) {
            Long execId = Long.valueOf(String.valueOf(v.get("execution_id")));
            String varName = String.valueOf(v.get("var_name"));
            String varValue = v.get("var_value") == null ? "" : String.valueOf(v.get("var_value"));
            result.computeIfAbsent(execId, k -> new HashMap<>()).put(varName, varValue);
        }
        return result;
    }

    /** 从 Python 统计接口获取最近100个商品的平均单商品耗时（ms）。
     *  非阻塞：缓存命中直接返回；缓存过期时返回上次值并后台异步刷新，避免阻塞 listExecutions。 */
    private long getAverageItemTimingMs() {
        long now = System.currentTimeMillis();
        if (now - cachedAvgItemTimingAtMs < AVG_ITEM_TIMING_CACHE_TTL_MS) {
            return cachedAvgItemTimingMs;
        }
        // 缓存过期：触发后台刷新（仅一个线程实际执行），立即返回上次缓存值
        refreshAvgItemTimingAsync();
        return cachedAvgItemTimingMs;
    }

    private final java.util.concurrent.atomic.AtomicBoolean avgTimingRefreshing = new java.util.concurrent.atomic.AtomicBoolean(false);

    private void refreshAvgItemTimingAsync() {
        if (!avgTimingRefreshing.compareAndSet(false, true)) return;
        new Thread(() -> {
            try {
                Object data = automationClient.getInternalForData("/api/internal/workflows/item-timing-stats", Map.of(), 5);
                long resolved = 0L;
                if (data instanceof Map) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> m = (Map<String, Object>) data;
                    Object avg = m.get("avgMs");
                    if (avg instanceof Number) {
                        resolved = ((Number) avg).longValue();
                    }
                }
                cachedAvgItemTimingMs = resolved;
                cachedAvgItemTimingAtMs = System.currentTimeMillis();
            } catch (Exception ignored) {
                // 刷新失败保持旧值，下次调用会再次尝试
            } finally {
                avgTimingRefreshing.set(false);
            }
        }, "avg-item-timing-refresh").start();
    }

    public List<Map<String, Object>> recentRuns(int limit) {
        Long tenantId = tenantId();
        int safeLimit = Math.max(1, Math.min(limit, 20));
        return jdbcTemplate.queryForList("""
                SELECT e.id AS execution_id,
                       e.execution_no,
                       e.status,
                       e.progress,
                       e.created_time,
                       e.finished_time,
                       e.error_message,
                       d.id AS workflow_id,
                       d.name AS workflow_name,
                       TIMESTAMPDIFF(MICROSECOND, e.started_time, e.finished_time) / 1000 AS duration_ms,
                       (
                           SELECT n.node_name
                           FROM workflow_node_execution n
                           WHERE n.execution_id = e.id AND n.deleted = 0 AND n.status = 'failed'
                           ORDER BY n.id ASC
                           LIMIT 1
                       ) AS failed_node
                FROM workflow_execution e
                LEFT JOIN workflow_definition d ON d.id = e.workflow_id
                WHERE e.tenant_id = ? AND e.deleted = 0
                ORDER BY e.created_time DESC, e.id DESC
                LIMIT ?
                """, tenantId, safeLimit).stream().map(this::recentRunRow).collect(Collectors.toList());
    }

    public List<Map<String, Object>> executionLogs(Long id) {
        Long tenantId = tenantId();
        executionRaw(tenantId, id);
        return loadTimeline(tenantId, id);
    }

    public Map<String, Object> executionDetail(Long id) {
        Long tenantId = tenantId();
        Map<String, Object> execution = jdbcTemplate.queryForMap("""
                SELECT e.*, d.name AS workflow_name
                FROM workflow_execution e LEFT JOIN workflow_definition d ON d.id=e.workflow_id
                WHERE e.tenant_id=? AND e.id=? AND e.deleted=0
                """, tenantId, id);
        long avgItemMs = getAverageItemTimingMs();
        Map<String, Object> result = executionRow(execution, avgItemMs, Map.of());
        // 各子查询独立 try-catch，避免单张表缺列/异常导致整个详情接口 500
        result.put("steps", safeQuery(() -> jdbcTemplate.queryForList("SELECT * FROM workflow_node_execution WHERE tenant_id=? AND execution_id=? AND deleted=0 ORDER BY id ASC", tenantId, id)
                .stream().map(this::nodeExecutionRow).collect(Collectors.toList()), "steps"));
        result.put("artifacts", safeQuery(() -> jdbcTemplate.queryForList("SELECT * FROM workflow_artifact WHERE tenant_id=? AND execution_id=? AND deleted=0 ORDER BY id ASC", tenantId, id), "artifacts"));
        result.put("timeline", safeQuery(() -> loadTimeline(tenantId, id), "timeline"));
        result.put("stateVariables", safeQuery(() -> loadStateVariables(tenantId, id), "stateVariables"));
        result.put("checkpoints", safeQuery(() -> loadCheckpoints(tenantId, id), "checkpoints"));
        return result;
    }

    /** 安全查询包装器：子查询失败时返回空列表而非让整个接口 500 */
    @SuppressWarnings("unchecked")
    private <T> T safeQuery(java.util.function.Supplier<T> supplier, String label) {
        try {
            return supplier.get();
        } catch (Exception e) {
            log.warn("加载工作流详情子数据失败 label={}, errorType={}", label, e.getClass().getSimpleName());
            return (T) (new java.util.ArrayList<>());
        }
    }

    // ==================== 私有方法 ====================

    private void snapshotPublishedVersion(Long workflowId) {
        Map<String, Object> d = detail(workflowId);
        int version = intValue(d.get("version"), 1);
        jdbcTemplate.update("UPDATE workflow_definition_version_snapshot SET deleted=1 WHERE tenant_id=? AND workflow_id=? AND version=? AND deleted=0", tenantId(), workflowId, version);
        jdbcTemplate.update("""
                INSERT INTO workflow_definition_version_snapshot(tenant_id,workflow_id,version,name,description,trigger_type,config_json,canvas_json,nodes_json,edges_json,snapshot_type,created_time,deleted)
                VALUES(?,?,?,?,?,?,?,?,?,?, 'publish', NOW(), 0)
                """, tenantId(), workflowId, version, text(d.get("name")), text(d.get("description")), textOr(d.get("triggerType"), "manual"), json(d.get("config")), json(d.get("canvas")), json(d.get("nodes")), json(d.get("edges")));
    }

    private Map<String, Object> executionRaw(Long tenantId, Long executionId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("SELECT * FROM workflow_execution WHERE tenant_id=? AND id=? AND deleted=0", tenantId, executionId);
        if (rows.isEmpty()) throw new BizException(404, "工作流执行记录不存在");
        return rows.get(0);
    }

    private List<Map<String, Object>> loadTimeline(Long tenantId, Long executionId) {
        if (tableHasColumn("workflow_timeline", "event_level")) {
            return jdbcTemplate.queryForList("""
                    SELECT id, node_key, event_level, event_type, title, content, payload_json, created_time
                    FROM workflow_timeline
                    WHERE tenant_id=? AND execution_id=? AND deleted=0
                    ORDER BY id ASC
                    """, tenantId, executionId).stream().map(this::timelineRow).collect(Collectors.toList());
        }
        return jdbcTemplate.queryForList("""
                SELECT id,
                       node_key,
                       level AS event_level,
                       event_type,
                       COALESCE(NULLIF(event_type,''), 'workflow-event') AS title,
                       content,
                       NULL AS payload_json,
                       created_time
                FROM workflow_timeline
                WHERE execution_id=?
                ORDER BY id ASC
                """, executionId).stream().map(this::timelineRow).collect(Collectors.toList());
    }

    private List<Map<String, Object>> loadStateVariables(Long tenantId, Long executionId) {
        if (tableHasColumn("workflow_state_variable", "var_name")) {
            return jdbcTemplate.queryForList("""
                    SELECT id, node_key, var_name, var_value, var_type, created_time
                    FROM workflow_state_variable
                    WHERE tenant_id=? AND execution_id=? AND deleted=0
                    ORDER BY id ASC
                    """, tenantId, executionId).stream().map(this::stateVariableRow).collect(Collectors.toList());
        }
        return jdbcTemplate.queryForList("""
                SELECT id,
                       NULL AS node_key,
                       variable_key AS var_name,
                       variable_value AS var_value,
                       variable_type AS var_type,
                       created_time
                FROM workflow_state_variable
                WHERE execution_id=?
                ORDER BY id ASC
                """, executionId).stream().map(this::stateVariableRow).collect(Collectors.toList());
    }

    private List<Map<String, Object>> loadCheckpoints(Long tenantId, Long executionId) {
        if (tableHasColumn("workflow_checkpoint", "checkpoint_type")) {
            return jdbcTemplate.queryForList("""
                    SELECT id, node_key, checkpoint_type, retry_count, max_retries, status, created_time
                    FROM workflow_checkpoint
                    WHERE tenant_id=? AND execution_id=? AND deleted=0
                    ORDER BY id ASC
                    """, tenantId, executionId);
        }
        return jdbcTemplate.queryForList("""
                SELECT id,
                       node_key,
                       'snapshot' AS checkpoint_type,
                       0 AS retry_count,
                       3 AS max_retries,
                       status,
                       created_time
                FROM workflow_checkpoint
                WHERE execution_id=?
                ORDER BY id ASC
                """, executionId);
    }

    private String findFirstFailedNodeKey(Long tenantId, Long executionId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("SELECT node_key FROM workflow_node_execution WHERE tenant_id=? AND execution_id=? AND deleted=0 AND status='failed' ORDER BY id ASC LIMIT 1", tenantId, executionId);
        return rows.isEmpty() ? "system-error" : text(rows.get(0).get("node_key"));
    }

    private void insertTimeline(Long tenantId, Long execId, Long workflowId, String nodeKey, String level, String type, String title, String content, Object payload) {
        jdbcTemplate.update("""
                INSERT INTO workflow_timeline(tenant_id,execution_id,workflow_id,node_key,event_level,event_type,title,content,payload_json,created_time,deleted)
                VALUES(?,?,?,?,?,?,?,?,?,NOW(),0)
                """, tenantId, execId, workflowId, nodeKey, level, type, title, content, json(payload));
    }

    private void writeExecutionResult(Long execId, Long tenantId, Long workflowId, Map<String, Object> result) {
        List<Map<String, Object>> nodeResults = mapList(result.get("nodeResults"));
        if (nodeResults.isEmpty()) {
            @SuppressWarnings("unchecked")
            Map<String, Object> wf = result.get("workflow") instanceof Map ? (Map<String, Object>) result.get("workflow") : Map.of();
            nodeResults = mapList(wf.get("nodes"));
        }
        for (Map<String, Object> n : nodeResults) {
            insertNodeExecution(tenantId, execId, workflowId,
                    textOr(first(n, "nodeKey", "id"), "node-" + System.nanoTime()),
                    textOr(first(n, "nodeName", "name"), "未命名节点"),
                    textOr(first(n, "nodeType", "type"), "action"),
                    textOr(n.get("status"), "success"),
                    json(n.getOrDefault("input", Map.of())),
                    json(n.getOrDefault("output", n)),
                    text(n.get("errorMessage")),
                    longValue(n.get("durationMs"), 0L));
        }
        List<Map<String, Object>> artifacts = mapList(result.get("artifacts"));
        for (Map<String, Object> a : artifacts) {
            jdbcTemplate.update("""
                    INSERT INTO workflow_artifact(tenant_id,execution_id,node_key,artifact_type,title,content_json,file_url,created_time,deleted)
                    VALUES(?,?,?,?,?,?,?,NOW(),0)
                    """, tenantId, execId, text(a.get("nodeKey")), textOr(a.get("artifactType"), "json"), text(a.get("title")), json(a.getOrDefault("content", a)), text(a.get("fileUrl")));
        }
        String status = textOr(result.get("status"), "success");
        // ★ Python 端 fire-and-forget：若返回 status='running'，说明工作流仍在后台执行，
        //   此时不应覆盖 execution 表的状态/进度/完成时间（否则会把 running+progress=100+finished_time=NOW
        //   写入，导致前端永远显示"运行中"且进度 100%）。最终状态由 Python 后台任务完成后自行更新。
        if ("running".equals(status)) {
            return;
        }
        int progress = "failed".equals(status) ? 100 : intValue(result.get("progress"), 100);
        jdbcTemplate.update("""
                UPDATE workflow_execution
                SET status=?, progress=?, output_json=?, error_message=?, finished_time=NOW(), updated_time=NOW()
                WHERE tenant_id=? AND id=?
                """, status, progress, json(result), text(result.get("errorMessage")), tenantId, execId);
    }

    private Long insertExecution(Long tenantId, Long workflowId, String executionNo, String triggerMode, String inputJson) {
        KeyHolder kh = new GeneratedKeyHolder();
        jdbcTemplate.update(con -> {
            PreparedStatement ps = con.prepareStatement("""
                    INSERT INTO workflow_execution(tenant_id,workflow_id,execution_no,trigger_mode,status,progress,input_json,started_time,created_time,updated_time,deleted)
                    VALUES(?,?,?,?, 'running', 0, ?, NOW(), NOW(), NOW(), 0)
                    """, Statement.RETURN_GENERATED_KEYS);
            ps.setObject(1, tenantId);
            ps.setObject(2, workflowId);
            ps.setString(3, executionNo);
            ps.setString(4, triggerMode);
            ps.setString(5, inputJson);
            return ps;
        }, kh);
        return Objects.requireNonNull(kh.getKey()).longValue();
    }

    private void insertNodeExecution(Long tenantId, Long execId, Long workflowId, String nodeKey, String nodeName, String nodeType, String status, String inputJson, String outputJson, String errorMessage, Long durationMs) {
        jdbcTemplate.update("""
                INSERT INTO workflow_node_execution(tenant_id,execution_id,workflow_id,node_key,node_name,node_type,status,input_json,output_json,error_message,duration_ms,started_time,finished_time,created_time,deleted)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),NOW(),0)
                """, tenantId, execId, workflowId, nodeKey, nodeName, nodeType, status, inputJson, outputJson, errorMessage, durationMs);
    }

    /**
     * 懒初始化默认工作流：如果租户没有任何工作流，自动创建一条默认的"商品搜索工作流"。
     *
     * <p>默认配置：
     * <ul>
     *   <li>TRIGGER: selectedAccountIds=[], executeCount=1</li>
     *   <li>PRODUCT_FETCH: sourceType=keyword, targetCount=5, fetchMode=random（商品搜索）</li>
     *   <li>PRODUCT_FILTER: enabled=false（不开启筛选）</li>
     *   <li>PRODUCT_POLISH: enabled=false（不开启润色）</li>
     *   <li>IMAGE_GENERATE: modelKey=image-2, imageCount=1（image-2 生图）</li>
     *   <li>PUBLISH: publishIntervalSeconds=30</li>
     * </ul>
     *
     * <p>幂等：仅在租户 0 条工作流时创建，已有工作流则跳过。
     */
    @Transactional
    public void ensureDefaultWorkflow(Long tenantId) {
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM workflow_definition WHERE tenant_id=? AND deleted=0", Long.class, tenantId);
        if (count != null && count > 0) return;
        Long userId = UserContext.userId();
        if (userId == null) userId = 0L;
        final Long finalUserId = userId;
        // 创建工作流定义（直接 published 状态，可立即执行）
        KeyHolder kh = new GeneratedKeyHolder();
        PreparedStatementCreator psc = con -> {
            PreparedStatement ps = con.prepareStatement("""
                    INSERT INTO workflow_definition(tenant_id,user_id,name,description,version,status,trigger_type,config_json,canvas_json,enabled,deleted,created_time,updated_time)
                    VALUES(?,?,?,?,'1','published','manual','{}','{}',1,0,NOW(),NOW())
                    """, Statement.RETURN_GENERATED_KEYS);
            ps.setObject(1, tenantId);
            ps.setObject(2, finalUserId);
            ps.setString(3, "商品搜索工作流");
            ps.setString(4, "根据关键词自动采集闲鱼商品，使用 image-2 生成 AI 封面图并发布。商品数量×账号数=最终发布数量。");
            return ps;
        };
        jdbcTemplate.update(psc, kh);
        Long workflowId = Objects.requireNonNull(kh.getKey()).longValue();
        // 插入 6 个节点
        List<Object[]> nodeRows = new ArrayList<>();
        nodeRows.add(new Object[]{tenantId, workflowId, "trigger_1", "触发器", "TRIGGER", 80, 80, json(Map.of(
                "selectedAccountIds", List.of(), "executeCount", 1)), 0});
        nodeRows.add(new Object[]{tenantId, workflowId, "fetch_1", "商品获取", "PRODUCT_FETCH", 320, 80, json(Map.of(
                "sourceType", "keyword", "keywords", List.of(), "shopUrl", "", "targetCount", 5,
                "fetchMode", "random", "enabled", true)), 1});
        nodeRows.add(new Object[]{tenantId, workflowId, "filter_1", "商品筛选", "PRODUCT_FILTER", 560, 80, json(Map.of(
                "enabled", false, "screenPrompt", "", "onFilterFail", "retry", "maxRetries", 5)), 2});
        nodeRows.add(new Object[]{tenantId, workflowId, "polish_1", "润色文案", "PRODUCT_POLISH", 800, 80, json(Map.of(
                "enabled", false, "style", "", "customPrompt", "")), 3});
        nodeRows.add(new Object[]{tenantId, workflowId, "image_1", "生图节点", "IMAGE_GENERATE", 1040, 80, json(Map.of(
                "imageCount", 1, "imageSize", "1024x1024", "imagePrompt", "", "customImagePrompt", "",
                "promptMode", "default", "modelKey", "image-2", "enabled", true,
                "referenceImages", List.of(), "parallelCount", 3)), 4});
        nodeRows.add(new Object[]{tenantId, workflowId, "publish_1", "发布节点", "PUBLISH", 1280, 80, json(Map.of(
                "publishIntervalSeconds", 30, "category", "", "addressText", "", "address", Map.of(),
                "priceStrategy", "keep", "enabled", true)), 5});
        jdbcTemplate.batchUpdate("""
                INSERT INTO workflow_node(tenant_id,workflow_id,node_key,node_name,node_type,position_x,position_y,config_json,sort_order,deleted,created_time,updated_time)
                VALUES(?,?,?,?,?,?,?,?,?,0,NOW(),NOW())
                """, nodeRows);
        // 插入 5 条连线
        List<Object[]> edgeRows = new ArrayList<>();
        edgeRows.add(new Object[]{tenantId, workflowId, "trigger_1", "fetch_1", "", 0});
        edgeRows.add(new Object[]{tenantId, workflowId, "fetch_1", "filter_1", "", 1});
        edgeRows.add(new Object[]{tenantId, workflowId, "filter_1", "polish_1", "", 2});
        edgeRows.add(new Object[]{tenantId, workflowId, "polish_1", "image_1", "", 3});
        edgeRows.add(new Object[]{tenantId, workflowId, "image_1", "publish_1", "", 4});
        jdbcTemplate.batchUpdate("""
                INSERT INTO workflow_edge(tenant_id,workflow_id,source_node_key,target_node_key,condition_expr,sort_order,deleted,created_time,updated_time)
                VALUES(?,?,?,?,?,?,0,NOW(),NOW())
                """, edgeRows);
        log.info("默认工作流已创建 tenantId={}, workflowId={}", tenantId, workflowId);
    }

    private void replaceNodesAndEdges(Long workflowId, List<Map<String, Object>> nodes, List<Map<String, Object>> edges) {
        Long tenantId = tenantId();
        jdbcTemplate.update("UPDATE workflow_node SET deleted=1, updated_time=NOW() WHERE tenant_id=? AND workflow_id=? AND deleted=0", tenantId, workflowId);
        jdbcTemplate.update("UPDATE workflow_edge SET deleted=1, updated_time=NOW() WHERE tenant_id=? AND workflow_id=? AND deleted=0", tenantId, workflowId);
        int sort = 0;
        for (Map<String, Object> n : nodes) {
            String nodeKey = textOr(first(n, "nodeKey", "id"), "node_" + sort);
            String nodeName = textOr(first(n, "nodeName", "name"), nodeKey);
            String nodeType = textOr(first(n, "nodeType", "type"), "action");
            int x = intValue(first(n, "x", "positionX"), 80);
            int y = intValue(first(n, "y", "positionY"), 80);
            Object config = n.getOrDefault("config", n.getOrDefault("params", Map.of()));
            jdbcTemplate.update("""
                    INSERT INTO workflow_node(tenant_id,workflow_id,node_key,node_name,node_type,position_x,position_y,config_json,sort_order,deleted,created_time,updated_time)
                    VALUES(?,?,?,?,?,?,?,?,?,0,NOW(),NOW())
                    """, tenantId, workflowId, nodeKey, nodeName, nodeType, x, y, json(config), sort++);
        }
        sort = 0;
        for (Map<String, Object> e : edges) {
            String source = textOr(first(e, "sourceNodeKey", "source"), "");
            String target = textOr(first(e, "targetNodeKey", "target"), "");
            String condition = textOr(first(e, "conditionExpr", "condition"), "");
            jdbcTemplate.update("""
                    INSERT INTO workflow_edge(tenant_id,workflow_id,source_node_key,target_node_key,condition_expr,sort_order,deleted,created_time,updated_time)
                    VALUES(?,?,?,?,?,?,0,NOW(),NOW())
                    """, tenantId, workflowId, source, target, condition, sort++);
        }
    }

    private void ensureExists(Long id, Long tenantId) {
        Long c = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM workflow_definition WHERE tenant_id=? AND id=? AND deleted=0", Long.class, tenantId, id);
        if (c == null || c == 0) throw new BizException(500, "工作流不存在");
    }

    private void ensureValidForSave(List<Map<String, Object>> nodes, List<Map<String, Object>> edges) {
        if (nodes == null || nodes.isEmpty()) throw new BizException(500, "工作流至少需要一个节点");
        Map<String, Object> v = validateGraph(nodes, edges == null ? List.of() : edges);
        if (!Boolean.TRUE.equals(v.get("valid"))) throw new BizException(500, String.valueOf(v.get("message")));
    }

    public Map<String, Object> validateGraph(List<Map<String, Object>> nodes, List<Map<String, Object>> edges) {
        Map<String, Object> res = new LinkedHashMap<>();
        if (nodes == null || nodes.isEmpty()) {
            res.put("valid", false); res.put("message", "工作流至少需要一个节点"); return res;
        }
        Set<String> keys = new LinkedHashSet<>();
        List<String> triggerKeys = new ArrayList<>();
        Set<String> terminalTypes = Set.of("PUBLISH", "END", "OUTPUT", "NOTIFY");
        boolean hasTerminal = false;
        for (Map<String, Object> n : nodes) {
            String k = textOr(first(n, "nodeKey", "id"), "");
            String type = textOr(first(n, "nodeType", "type"), "").toUpperCase(Locale.ROOT);
            String name = textOr(first(n, "nodeName", "name"), k);
            if (k.isBlank()) { res.put("valid", false); res.put("message", "存在空节点ID"); return res; }
            if (!keys.add(k)) { res.put("valid", false); res.put("message", "节点ID重复: " + k); return res; }
            if ("TRIGGER".equals(type)) triggerKeys.add(k);
            if (terminalTypes.contains(type)) hasTerminal = true;
            String configMessage = validateNodeConfig(n, type);
            if (!configMessage.isBlank()) {
                res.put("valid", false); res.put("message", "节点「" + name + "」配置不完整：" + configMessage); return res;
            }
        }
        if (triggerKeys.size() != 1) {
            res.put("valid", false); res.put("message", "必须有且只有一个触发节点"); return res;
        }
        if (!hasTerminal) {
            res.put("valid", false); res.put("message", "至少需要一个发布/结束类终态节点"); return res;
        }

        Map<String, List<String>> graph = new HashMap<>();
        Map<String, Integer> indegree = new HashMap<>();
        Map<String, Integer> outdegree = new HashMap<>();
        keys.forEach(k -> { graph.put(k, new ArrayList<>()); indegree.put(k, 0); outdegree.put(k, 0); });
        for (Map<String, Object> e : edges == null ? List.<Map<String,Object>>of() : edges) {
            String s = textOr(first(e, "sourceNodeKey", "source"), "");
            String t = textOr(first(e, "targetNodeKey", "target"), "");
            if (!keys.contains(s) || !keys.contains(t)) { res.put("valid", false); res.put("message", "连线引用了不存在的节点"); return res; }
            if (s.equals(t)) { res.put("valid", false); res.put("message", "节点不能连接到自身"); return res; }
            graph.get(s).add(t); indegree.put(t, indegree.get(t) + 1); outdegree.put(s, outdegree.get(s) + 1);
        }

        // DAG 检测（拓扑排序）
        Queue<String> queue = new LinkedList<>();
        for (String k : keys) { if (indegree.getOrDefault(k, 0) == 0) queue.add(k); }
        int visited = 0;
        while (!queue.isEmpty()) {
            String v = queue.poll();
            visited++;
            for (String next : graph.getOrDefault(v, List.of())) {
                indegree.put(next, indegree.get(next) - 1);
                if (indegree.get(next) == 0) queue.add(next);
            }
        }
        if (visited != keys.size()) {
            res.put("valid", false); res.put("message", "DAG 检测失败：工作流中存在循环依赖"); return res;
        }

        res.put("valid", true); res.put("message", "校验通过");
        res.put("triggerNodeKey", triggerKeys.isEmpty() ? "" : triggerKeys.get(0));
        return res;
    }

    private String validateNodeConfig(Map<String, Object> node, String type) {
        String t = type == null ? "" : type.toUpperCase(Locale.ROOT);
        if ("PUBLISH".equals(t)) {
            Object interval = node.get("publishIntervalSeconds");
            if (interval == null) interval = first(node, "config", "params");
            if (interval instanceof Map<?, ?> cfg) {
                Object v = cfg.get("publishIntervalSeconds");
                if (v == null) return "";
                return intValue(v, 0) <= 0 ? "发布间隔必须大于0" : "";
            }
        }
        return "";
    }

    private Long tenantId() { return TenantContext.getCurrentTenantId(); }

    private Long userId() { return TenantContext.getCurrentUserId(); }

    private long count(String sql, Object... args) {
        Long v = jdbcTemplate.queryForObject(sql, Long.class, args);
        return v == null ? 0 : v;
    }

    private String text(Object value) { return value == null ? "" : String.valueOf(value); }

    private String textOr(Object value, String fallback) {
        String s = text(value);
        return s.isBlank() ? fallback : s;
    }

    private String json(Object value) {
        try { return value == null ? "{}" : objectMapper.writeValueAsString(value); }
        catch (Exception e) { return "{}"; }
    }

    private int intValue(Object value, int def) {
        if (value == null) return def;
        try { return Integer.parseInt(String.valueOf(value)); } catch (Exception e) { return def; }
    }

    private long longValue(Object value, long def) {
        if (value == null) return def;
        try { return Long.parseLong(String.valueOf(value)); } catch (Exception e) { return def; }
    }

    private int boolInt(Object value) {
        if (value instanceof Boolean b) return b ? 1 : 0;
        if (value instanceof Number n) return n.intValue() == 0 ? 0 : 1;
        String s = text(value);
        return "true".equalsIgnoreCase(s) || "1".equals(s) || "yes".equalsIgnoreCase(s) ? 1 : 0;
    }

    private Object first(Map<String, Object> map, String... keys) {
        for (String k : keys) {
            if (map.containsKey(k) && map.get(k) != null) return map.get(k);
        }
        return null;
    }

    private String abbreviate(String s, int maxLen) {
        if (s == null) return "";
        String normalized = s.replaceAll("\\s+", " ").trim();
        return normalized.length() > maxLen ? normalized.substring(0, maxLen) + "..." : normalized;
    }

    private List<Map<String, Object>> mapList(Object value) {
        if (value instanceof List<?> list) {
            List<Map<String, Object>> result = new ArrayList<>();
            for (Object item : list) {
                if (item instanceof Map<?, ?> m) {
                    Map<String, Object> map = new LinkedHashMap<>();
                    m.forEach((k, v) -> map.put(String.valueOf(k), v));
                    result.add(map);
                }
            }
            return result;
        }
        return new ArrayList<>();
    }

    private Object parseJson(Object value) {
        if (value == null) return null;
        String s = String.valueOf(value);
        if (s.isBlank()) return null;
        try { return objectMapper.readValue(s, Object.class); }
        catch (Exception e) { return s; }
    }

    private Map<String, Object> definitionRow(Map<String, Object> row) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("id", row.get("id"));
        r.put("name", row.get("name"));
        r.put("description", row.get("description"));
        r.put("status", row.get("status"));
        r.put("version", intValue(row.get("version"), 1));
        r.put("triggerType", textOr(row.get("trigger_type"), "manual"));
        r.put("config", parseJson(row.get("config_json")));
        r.put("canvas", parseJson(row.get("canvas_json")));
        r.put("enabled", intValue(row.get("enabled"), 0) == 1);
        r.put("executionCount", intValue(row.get("execution_count"), 0));
        r.put("nodeCount", intValue(row.get("node_count"), 0));
        r.put("lastStatus", row.get("last_status"));
        r.put("lastRunTime", text(row.get("last_run_time")));
        r.put("publishedTime", text(row.get("published_time")));
        r.put("createdTime", text(row.get("created_time")));
        r.put("updatedTime", text(row.get("updated_time")));
        return r;
    }

    private Map<String, Object> nodeRow(Map<String, Object> row) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("id", row.get("node_key"));
        r.put("nodeKey", row.get("node_key"));
        r.put("name", row.get("node_name"));
        r.put("nodeName", row.get("node_name"));
        r.put("type", row.get("node_type"));
        r.put("nodeType", row.get("node_type"));
        r.put("x", row.get("position_x"));
        r.put("positionX", row.get("position_x"));
        r.put("y", row.get("position_y"));
        r.put("positionY", row.get("position_y"));
        r.put("config", parseJson(row.get("config_json")));
        r.put("retry", intValue(row.get("retry_enabled"), 0) == 1);
        r.put("retryEnabled", intValue(row.get("retry_enabled"), 0) == 1);
        r.put("retryCount", intValue(row.get("retry_count"), 0));
        r.put("retryIntervalSeconds", intValue(row.get("retry_interval_seconds"), 30));
        return r;
    }

    private Map<String, Object> edgeRow(Map<String, Object> row) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("source", row.get("source_node_key"));
        r.put("sourceNodeKey", row.get("source_node_key"));
        r.put("target", row.get("target_node_key"));
        r.put("targetNodeKey", row.get("target_node_key"));
        r.put("condition", textOr(row.get("condition_expr"), ""));
        r.put("conditionExpr", textOr(row.get("condition_expr"), ""));
        return r;
    }

    private Map<String, Object> executionRow(Map<String, Object> row) {
        return executionRow(row, 0L, Map.of());
    }

    private Map<String, Object> executionRow(Map<String, Object> row, long avgItemMs, Map<Long, Map<String, String>> stateVarMap) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("id", row.get("id"));
        r.put("executionNo", row.get("execution_no"));
        r.put("workflowId", row.get("workflow_id"));
        r.put("workflowName", textOr(row.get("workflow_name"), ""));
        r.put("triggerMode", textOr(row.get("trigger_mode"), "manual"));
        r.put("status", row.get("status"));
        r.put("progress", intValue(row.get("progress"), 0));
        r.put("nodeTotal", intValue(row.get("node_total"), 0));
        r.put("nodeSuccess", intValue(row.get("node_success"), 0));
        r.put("nodeFailed", intValue(row.get("node_failed"), 0));
        r.put("errorMessage", text(row.get("error_message")));
        r.put("startedTime", text(row.get("started_time")));
        r.put("finishedTime", text(row.get("finished_time")));
        r.put("createdTime", text(row.get("created_time")));
        r.put("durationMs", intValue(row.get("duration_ms"), 0));
        // 预计完成时间（分钟）：仅对 running 状态的执行计算
        Object execStatus = row.get("status");
        boolean isRunning = "running".equals(String.valueOf(execStatus));
        if (isRunning && avgItemMs > 0) {
            int targetCount = tryGetTargetCount(row, stateVarMap);
            if (targetCount <= 0) targetCount = intValue(row.get("node_total"), 1);
            long estimatedMs = avgItemMs * targetCount;
            double estimatedMinutes = estimatedMs / 60000.0;
            r.put("estimatedMinutes", Math.max(0.1, Math.round(estimatedMinutes * 10.0) / 10.0));
            r.put("avgItemSeconds", Math.round(avgItemMs / 1000.0 * 10.0) / 10.0);
        } else {
            r.put("estimatedMinutes", 0.0);
            r.put("avgItemSeconds", 0.0);
        }
        return r;
    }

    /** 从预加载的 stateVarMap 中读取 target_count 和 selected_account_ids，消除 N+1 查询 */
    private int tryGetTargetCount(Map<String, Object> row, Map<Long, Map<String, String>> stateVarMap) {
        try {
            Object execId = row.get("id");
            if (execId == null) return 0;
            Long eid = Long.valueOf(String.valueOf(execId));
            Map<String, String> vars = stateVarMap.get(eid);
            if (vars == null || vars.isEmpty()) return 0;
            String tcStr = vars.get("target_count");
            int count = 0;
            if (tcStr != null && !tcStr.isEmpty() && !"null".equalsIgnoreCase(tcStr)) {
                try { count = Integer.parseInt(tcStr); } catch (Exception ignored) {}
            }
            // ★ 多账号：总处理量 = target_count × 账号数（每个商品为每个账号生成独立版本）
            if (count > 0) {
                String acctJson = vars.get("selected_account_ids");
                if (acctJson != null && acctJson.startsWith("[")) {
                    int acctCount = acctJson.split(",").length;
                    count = count * acctCount;
                }
            }
            return count;
        } catch (Exception ignored) {}
        return 0;
    }

    private Map<String, Object> recentRunRow(Map<String, Object> row) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("executionId", row.get("execution_id"));
        r.put("executionNo", row.get("execution_no"));
        r.put("workflowId", row.get("workflow_id"));
        r.put("workflowName", textOr(row.get("workflow_name"), ""));
        r.put("status", row.get("status"));
        r.put("progress", intValue(row.get("progress"), 0));
        r.put("durationMs", longValue(row.get("duration_ms"), 0L));
        r.put("failedNode", text(row.get("failed_node")));
        r.put("errorMessage", text(row.get("error_message")));
        r.put("createdTime", text(row.get("created_time")));
        r.put("finishedTime", text(row.get("finished_time")));
        return r;
    }

    private Map<String, Object> nodeExecutionRow(Map<String, Object> row) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("id", row.get("id"));
        r.put("nodeKey", row.get("node_key"));
        r.put("nodeName", row.get("node_name"));
        r.put("nodeType", row.get("node_type"));
        r.put("status", row.get("status"));
        r.put("input", parseJson(row.get("input_json")));
        r.put("output", parseJson(row.get("output_json")));
        r.put("errorMessage", text(row.get("error_message")));
        r.put("durationMs", intValue(row.get("duration_ms"), 0));
        r.put("startedTime", text(row.get("started_time")));
        r.put("finishedTime", text(row.get("finished_time")));
        return r;
    }

    private Map<String, Object> timelineRow(Map<String, Object> row) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("id", row.get("id"));
        r.put("nodeKey", row.get("node_key"));
        r.put("eventLevel", row.get("event_level"));
        r.put("eventType", row.get("event_type"));
        r.put("title", row.get("title"));
        r.put("content", row.get("content"));
        r.put("payload", parseJson(row.get("payload_json")));
        r.put("createdTime", text(row.get("created_time")));
        return r;
    }

    private Map<String, Object> stateVariableRow(Map<String, Object> row) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("id", row.get("id"));
        r.put("nodeKey", row.get("node_key"));
        r.put("var_name", text(row.get("var_name")));
        r.put("varName", text(row.get("var_name")));
        r.put("var_type", textOr(row.get("var_type"), "string"));
        r.put("varType", textOr(row.get("var_type"), "string"));
        Object parsed = parseJson(row.get("var_value"));
        r.put("var_value", row.get("var_value"));
        r.put("varValue", row.get("var_value"));
        r.put("var_value_parsed", parsed);
        r.put("varValueParsed", parsed);
        r.put("createdTime", text(row.get("created_time")));
        return r;
    }

    private boolean tableHasColumn(String tableName, String columnName) {
        String cacheKey = tableName + "." + columnName;
        Boolean cached = tableColumnExistsCache.get(cacheKey);
        if (cached != null) {
            return cached;
        }
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = ? AND column_name = ?",
                    Integer.class,
                    tableName,
                    columnName
            );
            boolean exists = count != null && count > 0;
            tableColumnExistsCache.put(cacheKey, exists);
            return exists;
        } catch (Exception e) {
            return false;
        }
    }
}
