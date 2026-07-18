package com.xianyu.admin.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AutomationClient;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.dao.DataAccessException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/scheduled-tasks")
public class ScheduledTaskController {
    private static final Logger log = LoggerFactory.getLogger(ScheduledTaskController.class);
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final int MAX_TASK_NAME_LENGTH = 120;
    private static final int MAX_CRON_LENGTH = 120;
    private static final int MAX_CONFIG_BYTES = 32 * 1024;
    private static final Set<String> SUPPORTED_TASK_TYPES = Set.of(
            "sync_goods",
            "sync_orders",
            "sync_delivery_status",
            "redelivery",
            "polish_goods",
            "workflow",
            "auto_delivery",
            "delivery",
            "auto-delivery",
            "sync_account",
            "account_sync",
            "refresh_account",
            "auto_reply",
            "reply",
            "auto-reply",
            // 新增任务类型：自动补发订单（间隔触发）、一键擦亮商品（每日多账号）
            "auto_redelivery",
            "one_click_polish"
    );

    private final JdbcTemplate jdbcTemplate;
    private final AutomationClient automationClient;
    public ScheduledTaskController(JdbcTemplate jdbcTemplate, AutomationClient automationClient) {
        this.jdbcTemplate = jdbcTemplate;
        this.automationClient = automationClient;
    }

    @GetMapping
    public Result<PageResult<Map<String, Object>>> list(@RequestParam(required = false) String taskType,
                                                        @RequestParam(defaultValue = "1") int current,
                                                        @RequestParam(defaultValue = "20") int size) {
        Long tenantId = requireTenant();
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        String where = " WHERE tenant_id=? AND deleted=0 " + (taskType == null || taskType.isBlank() ? "" : " AND task_type=? ");
        Object[] countArgs = taskType == null || taskType.isBlank() ? new Object[]{tenantId} : new Object[]{tenantId, taskType};
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM scheduled_task" + where, Long.class, countArgs);
        Object[] args = taskType == null || taskType.isBlank() ? new Object[]{tenantId, offset, safeSize} : new Object[]{tenantId, taskType, offset, safeSize};
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("SELECT * FROM scheduled_task" + where + " ORDER BY created_time DESC LIMIT ?, ?", args);
        return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
    }

    @PostMapping
    public Result<Void> create(@RequestBody Map<String, Object> body) {
        if (body == null) throw new BizException(400, "定时任务参数不能为空");
        String taskType = normalizeTaskType(body.get("taskType"));
        if (!SUPPORTED_TASK_TYPES.contains(taskType)) {
            return new Result<>(422, "暂不支持该定时任务类型", null);
        }
        Long tenantId = requireTenant();
        TaskInput input = validateTaskInput(body, taskType, tenantId);
        int affected = jdbcTemplate.update("INSERT INTO scheduled_task(tenant_id, account_id, task_type, task_name, cron_expression, config_json, enabled, created_time, updated_time, deleted) VALUES(?,?,?,?,?,?,?,NOW(),NOW(),0)",
                tenantId, input.accountId(), taskType, input.taskName(), input.cronExpression(), input.configJson(), input.enabled());
        if (affected != 1) {
            throw new BizException(503, "定时任务未被数据库确认创建，请稍后重试");
        }
        return Result.ok(null);
    }

    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        requirePositiveId(id, "任务 ID");
        if (body == null) throw new BizException(400, "定时任务参数不能为空");
        String taskType = normalizeTaskType(body.get("taskType"));
        if (!SUPPORTED_TASK_TYPES.contains(taskType)) {
            return new Result<>(422, "暂不支持该定时任务类型", null);
        }
        Long tenantId = requireTenant();
        TaskInput input = validateTaskInput(body, taskType, tenantId);
        int affected = jdbcTemplate.update("UPDATE scheduled_task SET account_id=?, task_type=?, task_name=?, cron_expression=?, config_json=?, enabled=?, updated_time=NOW() WHERE tenant_id=? AND id=? AND deleted=0",
                input.accountId(), taskType, input.taskName(), input.cronExpression(), input.configJson(), input.enabled(), tenantId, id);
        if (affected != 1) {
            throw new BizException(404, "定时任务不存在或无权修改");
        }
        return Result.ok(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        requirePositiveId(id, "任务 ID");
        int affected = jdbcTemplate.update(
                "UPDATE scheduled_task SET deleted=1, updated_time=NOW() WHERE tenant_id=? AND id=? AND deleted=0",
                requireTenant(), id);
        if (affected != 1) {
            throw new BizException(404, "定时任务不存在或无权删除");
        }
        return Result.ok(null);
    }

    @PostMapping("/{id}/run")
    public Result<Map<String, Object>> run(@PathVariable Long id) {
        requirePositiveId(id, "任务 ID");
        Long tenantId = requireTenant();
        requireOwnedTask(id, tenantId);
        try {
            Map<String, Object> result = automationClient.postInternalForData(
                    "/api/internal/tasks/" + id + "/run",
                    Map.of("tenantId", tenantId)
            );
            return Result.ok(result);
        } catch (Exception e) {
            if (e instanceof BizException bizException) throw bizException;
            // 调用未被确认成功时不得更新 last_run_time，避免把失败伪装成一次已运行。
            log.error("手动运行定时任务失败 taskId={}, errorType={}", id, e.getClass().getSimpleName());
            throw new BizException(503, "自动化服务暂时不可用，任务未确认执行，请稍后重试");
        }
    }

    private TaskInput validateTaskInput(Map<String, Object> body, String taskType, Long tenantId) {
        if (body == null) throw new BizException(400, "定时任务参数不能为空");
        Long accountId = nullablePositiveLong(body.get("accountId"), "账号 ID");
        if (accountId != null) requireOwnedAccount(accountId, tenantId);
        String taskName = boundedText(body.get("taskName"), taskType, MAX_TASK_NAME_LENGTH, "任务名称");
        String cronExpression = boundedText(body.get("cronExpression"), null, MAX_CRON_LENGTH, "Cron 表达式");
        String configJson = normalizeConfigJson(body.get("configJson"));
        // 多账号任务：从 configJson 中读取 accountIds 数组，对每个账号校验归属
        // 工作流任务不使用 accountIds（使用工作流自带的账号配置），跳过校验
        if (!"workflow".equals(taskType)) {
            for (Long id : extractAccountIdsFromConfig(configJson, accountId)) {
                requireOwnedAccount(id, tenantId);
            }
        }
        int enabled = normalizeEnabled(body.get("enabled"));
        return new TaskInput(accountId, taskName, cronExpression, configJson, enabled);
    }

    /**
     * 从 configJson 中提取 accountIds 数组（去重）。
     * 若 accountIds 不存在或为空，回退使用单个 accountId。
     */
    private List<Long> extractAccountIdsFromConfig(String configJson, Long fallbackAccountId) {
        LinkedHashSet<Long> ids = new LinkedHashSet<>();
        try {
            JsonNode node = JSON.readTree(configJson);
            if (node != null && node.has("accountIds") && node.get("accountIds").isArray()) {
                for (JsonNode item : node.get("accountIds")) {
                    if (item != null && item.canConvertToLong()) {
                        long value = item.asLong();
                        if (value > 0) ids.add(value);
                    }
                }
            }
        } catch (Exception ignored) {
            // configJson 已通过 normalizeConfigJson 校验为合法 JSON，这里不应失败
        }
        if (ids.isEmpty() && fallbackAccountId != null) {
            ids.add(fallbackAccountId);
        }
        return new ArrayList<>(ids);
    }

    private void requireOwnedAccount(Long accountId, Long tenantId) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM xianyu_account WHERE id=? AND tenant_id=? AND deleted=0",
                    Integer.class,
                    accountId,
                    tenantId
            );
            if (count == null || count != 1) {
                throw new BizException(404, "闲鱼账号不存在或无权使用");
            }
        } catch (BizException exception) {
            throw exception;
        } catch (DataAccessException exception) {
            throw new BizException(503, "账号归属暂时无法校验，请稍后重试");
        }
    }

    private void requireOwnedTask(Long taskId, Long tenantId) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM scheduled_task WHERE id=? AND tenant_id=? AND deleted=0",
                    Integer.class,
                    taskId,
                    tenantId
            );
            if (count == null || count != 1) {
                throw new BizException(404, "定时任务不存在或无权执行");
            }
        } catch (BizException exception) {
            throw exception;
        } catch (DataAccessException exception) {
            throw new BizException(503, "定时任务状态暂时无法校验，请稍后重试");
        }
    }

    private String normalizeConfigJson(Object value) {
        try {
            String json;
            if (value == null || String.valueOf(value).isBlank()) {
                json = "{}";
            } else if (value instanceof Map<?, ?> map) {
                Map<String, Object> normalized = new LinkedHashMap<>();
                map.forEach((key, item) -> normalized.put(String.valueOf(key), item));
                json = JSON.writeValueAsString(normalized);
            } else {
                json = String.valueOf(value).trim();
            }
            if (json.getBytes(StandardCharsets.UTF_8).length > MAX_CONFIG_BYTES) {
                throw new BizException(413, "任务配置不能超过 32KB");
            }
            JsonNode node = JSON.readTree(json);
            if (node == null || !node.isObject()) {
                throw new BizException(400, "任务配置必须是 JSON 对象");
            }
            return JSON.writeValueAsString(node);
        } catch (BizException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new BizException(400, "任务配置必须是合法 JSON 对象");
        }
    }

    private int normalizeEnabled(Object value) {
        if (value == null) return 1;
        if (value instanceof Boolean enabled) return enabled ? 1 : 0;
        String normalized = String.valueOf(value).trim();
        if ("1".equals(normalized) || "true".equalsIgnoreCase(normalized)) return 1;
        if ("0".equals(normalized) || "false".equalsIgnoreCase(normalized)) return 0;
        throw new BizException(400, "enabled 仅支持 true/false 或 1/0");
    }

    private Long nullablePositiveLong(Object value, String fieldName) {
        if (value == null || String.valueOf(value).isBlank()) return null;
        try {
            long parsed = Long.parseLong(String.valueOf(value));
            if (parsed <= 0) throw new NumberFormatException();
            return parsed;
        } catch (NumberFormatException exception) {
            throw new BizException(400, fieldName + " 必须是正整数");
        }
    }

    private String boundedText(Object value, String fallback, int maximum, String fieldName) {
        String text = value == null ? "" : String.valueOf(value).trim();
        if (text.isBlank()) text = fallback;
        if (text != null && text.length() > maximum) {
            throw new BizException(400, fieldName + "过长");
        }
        return text;
    }

    private Long requireTenant() {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null || tenantId <= 0) {
            throw new BizException(401, "登录租户上下文已失效，请重新登录");
        }
        return tenantId;
    }

    private void requirePositiveId(Long id, String fieldName) {
        if (id == null || id <= 0) throw new BizException(400, fieldName + " 非法");
    }

    private String normalizeTaskType(Object value) {
        return value == null ? "" : String.valueOf(value).trim().toLowerCase(Locale.ROOT);
    }

    private record TaskInput(Long accountId, String taskName, String cronExpression, String configJson, int enabled) {}
}
