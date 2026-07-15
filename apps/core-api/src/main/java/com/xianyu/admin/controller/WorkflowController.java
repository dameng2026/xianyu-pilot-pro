package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.WorkflowService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/workflow")
public class WorkflowController {
    private final WorkflowService workflowService;

    public WorkflowController(WorkflowService workflowService) {
        this.workflowService = workflowService;
    }

    @GetMapping("/overview")
    public Result<Map<String, Object>> overview() {
        return Result.ok(workflowService.overview());
    }

    @GetMapping("/definitions")
    public Result<PageResult<Map<String, Object>>> listDefinitions(@RequestParam(name = "keyword", required = false) String keyword,
                                                                   @RequestParam(name = "status", required = false) String status,
                                                                   @RequestParam(name = "current", defaultValue = "1") int current,
                                                                   @RequestParam(name = "size", defaultValue = "20") int size) {
        return Result.ok(workflowService.listDefinitions(keyword, status, current, size));
    }

    @GetMapping("/definitions/{id}")
    public Result<Map<String, Object>> detail(@PathVariable("id") Long id) {
        return Result.ok(workflowService.detail(id));
    }

    @PostMapping("/definitions")
    public Result<Map<String, Object>> create(@RequestBody Map<String, Object> body) {
        return Result.ok(workflowService.create(body));
    }

    @PutMapping("/definitions/{id}")
    public Result<Map<String, Object>> update(@PathVariable("id") Long id, @RequestBody Map<String, Object> body) {
        return Result.ok(workflowService.update(id, body));
    }

    @DeleteMapping("/definitions/{id}")
    public Result<Void> delete(@PathVariable("id") Long id) {
        workflowService.delete(id);
        return Result.ok(null);
    }

    @PostMapping("/definitions/{id}/publish")
    public Result<Map<String, Object>> publish(@PathVariable("id") Long id) {
        return Result.ok(workflowService.publish(id));
    }

    @GetMapping("/definitions/{id}/versions")
    public Result<PageResult<Map<String, Object>>> versions(@PathVariable("id") Long id,
                                                            @RequestParam(name = "current", defaultValue = "1") int current,
                                                            @RequestParam(name = "size", defaultValue = "20") int size) {
        return Result.ok(workflowService.listVersions(id, current, size));
    }

    @PostMapping("/definitions/{id}/rollback")
    public Result<Map<String, Object>> rollback(@PathVariable("id") Long id, @RequestBody Map<String, Object> body) {
        int version = Integer.parseInt(String.valueOf(body.getOrDefault("version", "0")));
        return Result.ok(workflowService.rollback(id, version));
    }

    @PostMapping("/definitions/{id}/execute")
    public Result<Map<String, Object>> execute(@PathVariable("id") Long id, @RequestBody(required = false) Map<String, Object> body) {
        return Result.ok(workflowService.execute(id, body == null ? Map.of() : body));
    }

    @GetMapping("/executions")
    public Result<PageResult<Map<String, Object>>> listExecutions(@RequestParam(name = "workflowId", required = false) Long workflowId,
                                                                  @RequestParam(name = "status", required = false) String status,
                                                                  @RequestParam(name = "accountId", required = false) Long accountId,
                                                                  @RequestParam(name = "current", defaultValue = "1") int current,
                                                                  @RequestParam(name = "size", defaultValue = "20") int size) {
        return Result.ok(workflowService.listExecutions(workflowId, status, accountId, current, size));
    }

    @PostMapping("/executions/{id}/terminate")
    public Result<Map<String, Object>> terminateExecution(@PathVariable("id") Long id, @RequestBody(required = false) Map<String, Object> body) {
        return Result.ok(workflowService.terminateExecution(id, body == null ? Map.of() : body));
    }

    @PostMapping("/executions/{id}/retry-failed-node")
    public Result<Map<String, Object>> retryFailedNode(@PathVariable("id") Long id, @RequestBody(required = false) Map<String, Object> body) {
        return Result.ok(workflowService.retryFailedNode(id, body == null ? Map.of() : body));
    }

    @PostMapping("/executions/{id}/continue")
    public Result<Map<String, Object>> continueExecution(@PathVariable("id") Long id) {
        return Result.ok(workflowService.continueExecution(id));
    }

    @GetMapping("/executions/{id}")
    public Result<Map<String, Object>> executionDetail(@PathVariable("id") Long id) {
        return Result.ok(workflowService.executionDetail(id));
    }

    @GetMapping("/recent-runs")
    public Result<Object> recentRuns(@RequestParam(name = "limit", defaultValue = "5") int limit) {
        return Result.ok(workflowService.recentRuns(limit));
    }

    @GetMapping("/executions/{id}/logs")
    public Result<Object> executionLogs(@PathVariable("id") Long id) {
        return Result.ok(workflowService.executionLogs(id));
    }
}
