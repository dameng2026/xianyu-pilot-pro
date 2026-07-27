package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.service.AiCsLearnedKbService;
import com.xianyu.admin.service.KnowledgeLearningJob;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin-api/learned-kb")
public class AdminLearnedKbController {

    private static final Logger log = LoggerFactory.getLogger(AdminLearnedKbController.class);

    private final AiCsLearnedKbService kbService;
    private final KnowledgeLearningJob learningJob;

    public AdminLearnedKbController(AiCsLearnedKbService kbService,
                                     KnowledgeLearningJob learningJob) {
        this.kbService = kbService;
        this.learningJob = learningJob;
    }

    /* ===== KB 条目管理 ===== */

    @GetMapping("/list")
    public Result<Map<String, Object>> list(
        @RequestParam(defaultValue = "1") int page,
        @RequestParam(defaultValue = "20") int size,
        @RequestParam(required = false) String category,
        @RequestParam(required = false) String status,
        @RequestParam(required = false) Integer minScore,
        @RequestParam(required = false) String keyword
    ) {
        // 边界校验
        if (page < 1) page = 1;
        if (size < 1 || size > 100) size = 20;
        return Result.ok(kbService.listLearnedKb(page, size, category, status, minScore, keyword));
    }

    @GetMapping("/{id}")
    public Result<Map<String, Object>> detail(@PathVariable Long id) {
        return Result.ok(kbService.getLearnedKbDetail(id));
    }

    @PostMapping("/{id}/approve")
    public Result<Void> approve(@PathVariable Long id) {
        kbService.approve(id, AdminContext.userId());
        return Result.ok(null);
    }

    @PostMapping("/{id}/reject")
    public Result<Void> reject(@PathVariable Long id, @RequestBody Map<String, String> body) {
        String reason = body.get("reason");
        if (reason == null || reason.isBlank()) reason = "未填写";
        kbService.reject(id, AdminContext.userId(), reason);
        return Result.ok(null);
    }

    @PostMapping("/batch-approve")
    public Result<Void> batchApprove(@RequestBody Map<String, Object> body) {
        @SuppressWarnings("unchecked")
        List<Number> rawIds = (List<Number>) body.get("ids");
        if (rawIds == null || rawIds.isEmpty()) return Result.fail("ids 为空");
        if (rawIds.size() > 500) return Result.fail("单次批量最多 500 条");
        List<Long> ids = rawIds.stream().map(Number::longValue).toList();
        kbService.batchApprove(ids, AdminContext.userId());
        return Result.ok(null);
    }

    @PostMapping("/batch-reject")
    public Result<Void> batchReject(@RequestBody Map<String, Object> body) {
        @SuppressWarnings("unchecked")
        List<Number> rawIds = (List<Number>) body.get("ids");
        if (rawIds == null || rawIds.isEmpty()) return Result.fail("ids 为空");
        List<Long> ids = rawIds.stream().map(Number::longValue).toList();
        String reason = (String) body.get("reason");
        if (reason == null || reason.isBlank()) reason = "未填写";
        kbService.batchReject(ids, AdminContext.userId(), reason);
        return Result.ok(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        kbService.softDelete(id);
        return Result.ok(null);
    }

    /**
     * V1.47: 获取某条 Q&A 关联的原始对话消息（按时间排序）。
     */
    @GetMapping("/{id}/conversation")
    public Result<List<Map<String, Object>>> conversation(@PathVariable Long id) {
        return Result.ok(kbService.getConversationMessages(id));
    }

    /* ===== 分类管理 ===== */

    @GetMapping("/categories")
    public Result<List<Map<String, Object>>> categories() {
        return Result.ok(kbService.listCategories());
    }

    @PostMapping("/categories")
    public Result<Long> createCategory(@RequestBody Map<String, Object> body) {
        String name = (String) body.get("name");
        if (name == null || name.isBlank()) return Result.fail("name 为空");
        Long parentId = body.get("parent_id") != null
            ? ((Number) body.get("parent_id")).longValue() : null;
        return Result.ok(kbService.createCategory(name, parentId));
    }

    @PutMapping("/categories/{id}")
    public Result<Void> renameCategory(@PathVariable Long id, @RequestBody Map<String, String> body) {
        String name = body.get("name");
        if (name == null || name.isBlank()) return Result.fail("name 为空");
        kbService.renameCategory(id, name);
        return Result.ok(null);
    }

    @PostMapping("/categories/merge")
    public Result<Void> mergeCategory(@RequestBody Map<String, Long> body) {
        Long fromId = body.get("from_id");
        Long toId = body.get("to_id");
        if (fromId == null || toId == null || fromId.equals(toId)) {
            return Result.fail("from_id / to_id 不合法");
        }
        kbService.mergeCategory(fromId, toId);
        return Result.ok(null);
    }

    @DeleteMapping("/categories/{id}")
    public Result<Void> deleteCategory(@PathVariable Long id) {
        kbService.deleteCategory(id);
        return Result.ok(null);
    }

    /* ===== 学习日志 ===== */

    @GetMapping("/logs")
    public Result<Map<String, Object>> logs(
        @RequestParam(defaultValue = "1") int page,
        @RequestParam(defaultValue = "20") int size
    ) {
        if (page < 1) page = 1;
        if (size < 1 || size > 100) size = 20;
        return Result.ok(kbService.listLogs(page, size));
    }

    @GetMapping("/logs/{batchId}")
    public Result<Map<String, Object>> logDetail(@PathVariable String batchId) {
        return Result.ok(kbService.getLogDetail(batchId));
    }

    /* ===== 触发与回填 ===== */

    @PostMapping("/trigger")
    public Result<String> trigger() {
        Long adminId = AdminContext.userId();
        log.info("admin={} triggered kb-learning manually", adminId);
        // 使用 KnowledgeLearningJob 内的有界线程池，避免裸 new Thread
        learningJob.runLearningAsync();
        return Result.ok("学习任务已触发，约几分钟后可在日志查看结果");
    }

    @PostMapping("/backfill")
    public Result<String> backfill(@RequestBody Map<String, Object> body) {
        if (!"confirm".equals(body.get("confirm"))) {
            return Result.fail("需要 confirm=confirm 才能执行回填");
        }
        Long adminId = AdminContext.userId();
        log.info("admin={} triggered kb-learning backfill manually", adminId);
        // 当前 backfill 与 trigger 行为一致（均调用 runLearning），
        // 后续如需差异化（如扩大 lookback-hours），可在 KnowledgeLearningJob 中新增 runBackfill 方法
        learningJob.runLearningAsync();
        return Result.ok("回填任务已触发");
    }
}
