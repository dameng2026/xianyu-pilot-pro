package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.ImageGenerationService;
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
    private final ImageGenerationService imageGenerationService;

    @Value("${xianyu.automation.internal-token:}")
    private String internalToken;

    public InternalWorkflowController(WorkflowService workflowService, JdbcTemplate jdbcTemplate,
                                       ImageGenerationService imageGenerationService) {
        this.workflowService = workflowService;
        this.jdbcTemplate = jdbcTemplate;
        this.imageGenerationService = imageGenerationService;
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

    /**
     * 内部接口：Python automation-service 工作流生图成功后回传历史记录。
     *
     * 工作流 IMAGE_GENERATE 节点直接调用 AI 提供商 API 生图（不经 Java generate-images 端点），
     * 因此需要本接口将生图结果（含 source=workflow 溯源字段）回传到 Java 端统一落库，
     * 供前台「工作流 → 图片生成记录」页面查询展示。
     *
     * 请求体字段（JSON）：
     *   tenantId, userId, requestId, model, prompt, size, imageUrl, method,
     *   source(默认 workflow), workflowId, workflowExecutionId, workflowNodeKey,
     *   status(默认 success), errorMessage
     *
     * 该接口为 fire-and-forget：调用方失败不应阻塞工作流执行；落库失败仅记录 warn 日志。
     */
    @PostMapping("/image-history/record")
    public Result<Map<String, Object>> recordImageHistory(@RequestBody(required = false) Map<String, Object> body,
                                                            HttpServletRequest request) {
        verifyInternalToken(request);
        if (body == null || body.isEmpty()) {
            throw new BizException(400, "请求体不能为空");
        }
        Long tenantId = asLong(body.get("tenantId"));
        Long userId = asLong(body.get("userId"));
        if (tenantId == null || tenantId <= 0) {
            throw new BizException(400, "tenantId 必须为正整数");
        }
        if (userId == null || userId <= 0) {
            throw new BizException(400, "userId 必须为正整数");
        }
        String requestId = asString(body.get("requestId"));
        String model = asString(body.get("model"));
        String prompt = asString(body.get("prompt"));
        String size = asString(body.get("size"));
        String imageUrl = asString(body.get("imageUrl"));
        String method = asString(body.get("method"));
        String source = asString(body.get("source"));
        if (source.isBlank()) source = "workflow";
        Long workflowId = asLong(body.get("workflowId"));
        Long workflowExecutionId = asLong(body.get("workflowExecutionId"));
        String workflowNodeKey = asString(body.get("workflowNodeKey"));
        String status = asString(body.get("status"));
        if (status.isBlank()) status = "success";
        String errorMessage = asString(body.get("errorMessage"));

        imageGenerationService.recordExternalGenerationHistory(
                tenantId, userId, requestId, model, prompt, size, imageUrl, method,
                source, workflowId, workflowExecutionId, workflowNodeKey, status, errorMessage);
        return Result.ok(Map.of("ok", true));
    }

    private Long asLong(Object v) {
        if (v == null) return null;
        if (v instanceof Number n) return n.longValue();
        try { return Long.parseLong(String.valueOf(v).trim()); } catch (Exception e) { return null; }
    }

    private String asString(Object v) {
        return v == null ? "" : String.valueOf(v);
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
