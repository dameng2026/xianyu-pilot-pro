package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.WorkflowService;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;

/**
 * 工作流内部触发接口。
 *
 * - /open-api/internal/workflow/definitions/{id}/trigger  供 Python automation-service 通过 X-Internal-Token 调用，
 *   用于定时任务触发已配置的工作流执行。
 *
 * 与 /api/workflow/definitions/{id}/execute 的区别：
 *   - 不依赖用户登录态（定时任务由后台调度，无用户上下文）
 *   - 通过 X-Internal-Token 鉴权 + tenantId 路径参数明确租户范围
 *   - 复用 WorkflowService.execute 的全部校验与执行逻辑
 */
@RestController
@RequestMapping("/open-api/internal/workflow")
public class InternalWorkflowController {
    private static final Logger log = LoggerFactory.getLogger(InternalWorkflowController.class);

    private final WorkflowService workflowService;
    private final JdbcTemplate jdbcTemplate;

    @Value("${xianyu.automation.internal-token:}")
    private String internalToken;

    public InternalWorkflowController(WorkflowService workflowService, JdbcTemplate jdbcTemplate) {
        this.workflowService = workflowService;
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 内部接口：定时任务触发工作流执行。
     * tenantId 通过查询参数传递，input 通过请求体传递。
     */
    @PostMapping("/definitions/{id}/trigger")
    public Result<Map<String, Object>> trigger(@PathVariable("id") Long id,
                                                @RequestParam("tenantId") Long tenantId,
                                                @RequestBody(required = false) Map<String, Object> body,
                                                HttpServletRequest request) {
        verifyInternalToken(request);
        if (tenantId == null || tenantId <= 0) {
            throw new BizException(400, "tenantId 必须为正整数");
        }
        requireOwnedWorkflow(id, tenantId);
        Map<String, Object> input = extractInput(body);

        // WorkflowService.execute 内部通过 TenantContext 获取 tenantId/userId，
        // 定时任务无用户上下文，仅设置 tenantId，userId 留空
        TenantContext.setCurrentTenantId(tenantId);
        TenantContext.setCurrentUserId(null);
        try {
            return Result.ok(workflowService.execute(id, input));
        } finally {
            TenantContext.clear();
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> extractInput(Map<String, Object> body) {
        if (body == null) return Map.of();
        Object inputObj = body.get("input");
        if (inputObj instanceof Map<?, ?> map) {
            return (Map<String, Object>) map;
        }
        return Map.of();
    }

    private void requireOwnedWorkflow(Long workflowId, Long tenantId) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM workflow_definition WHERE id=? AND tenant_id=? AND deleted=0",
                    Integer.class,
                    workflowId,
                    tenantId
            );
            if (count == null || count != 1) {
                throw new BizException(404, "工作流不存在或无权执行");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("校验工作流归属失败 id={}, tenantId={}, errorType={}", workflowId, tenantId, e.getClass().getSimpleName());
            throw new BizException(503, "工作流归属校验暂时不可用，请稍后重试");
        }
    }

    private void verifyInternalToken(HttpServletRequest request) {
        if (internalToken == null || internalToken.isBlank()) {
            throw new BizException(503, "internal API token is not configured");
        }
        String token = request.getHeader("X-Internal-Token");
        if (token == null || !MessageDigest.isEqual(
                internalToken.getBytes(StandardCharsets.UTF_8),
                token.getBytes(StandardCharsets.UTF_8))) {
            throw new BizException(403, "invalid internal token");
        }
    }
}
