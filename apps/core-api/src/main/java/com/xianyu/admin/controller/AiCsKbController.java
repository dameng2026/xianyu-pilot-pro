package com.xianyu.admin.controller;

import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AiCsLearnedKbService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/ai-cs/kb")
public class AiCsKbController {

    private final AiCsLearnedKbService kbService;

    public AiCsKbController(AiCsLearnedKbService kbService) {
        this.kbService = kbService;
    }

    /* ===== 平台学习 KB（只读） ===== */

    @GetMapping("/learned")
    public ResponseEntity<List<Map<String, Object>>> listLearned(
        @RequestParam(required = false) String category,
        @RequestParam(required = false) String keyword
    ) {
        return ResponseEntity.ok(kbService.listLearnedKbForUser(category, keyword));
    }

    @GetMapping("/learned/{id}")
    public ResponseEntity<Map<String, Object>> getLearned(@PathVariable Long id) {
        return ResponseEntity.ok(kbService.getLearnedKbForUser(id));
    }

    /**
     * V1.47: 获取某条 Q&A 关联的原始对话消息（按时间排序）。
     */
    @GetMapping("/learned/{id}/conversation")
    public ResponseEntity<List<Map<String, Object>>> getConversation(@PathVariable Long id) {
        return ResponseEntity.ok(kbService.getConversationMessages(id));
    }

    /* ===== 分类列表（前台只读） ===== */

    @GetMapping("/categories")
    public ResponseEntity<List<Map<String, Object>>> categories() {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        // V1.47: 返回分类列表时附带用户启用状态
        return ResponseEntity.ok(kbService.listCategoriesForUser(tenantId, userId));
    }

    /**
     * V1.47: 按分类 code 列出该分类下所有 Q&A。
     */
    @GetMapping("/categories/{code}/learned")
    public ResponseEntity<List<Map<String, Object>>> listLearnedByCategory(
        @PathVariable String code,
        @RequestParam(required = false) String keyword
    ) {
        return ResponseEntity.ok(kbService.listLearnedKbByCategoryCode(code, keyword));
    }

    /**
     * V1.47: 一键启用某个分类下的所有 Q&A。
     */
    @PostMapping("/categories/{code}/bind")
    public ResponseEntity<Map<String, Object>> bindCategory(@PathVariable String code) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        int count = kbService.bindCategory(tenantId, userId, code);
        return ResponseEntity.ok(Map.of("bound_count", count));
    }

    /**
     * V1.47: 一键取消启用某个分类下的所有 Q&A。
     */
    @DeleteMapping("/categories/{code}/bind")
    public ResponseEntity<Map<String, Object>> unbindCategory(@PathVariable String code) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        int count = kbService.unbindCategory(tenantId, userId, code);
        return ResponseEntity.ok(Map.of("unbound_count", count));
    }

    /* ===== 一级大类（V1.49 三级分类） ===== */

    /**
     * V1.49: 按一级分类 code 列出其下所有二级分类的所有 Q&A。
     */
    @GetMapping("/parent-categories/{code}/learned")
    public ResponseEntity<List<Map<String, Object>>> listLearnedByParentCategory(
        @PathVariable String code,
        @RequestParam(required = false) String keyword
    ) {
        return ResponseEntity.ok(kbService.listLearnedKbByParentCategoryCode(code, keyword));
    }

    /**
     * V1.49: 一键启用某个一级分类下所有二级分类的所有 Q&A（按大类启用）。
     */
    @PostMapping("/parent-categories/{code}/bind")
    public ResponseEntity<Map<String, Object>> bindParentCategory(@PathVariable String code) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        int count = kbService.bindParentCategory(tenantId, userId, code);
        return ResponseEntity.ok(Map.of("bound_count", count));
    }

    /**
     * V1.49: 一键取消启用某个一级分类下所有二级分类的所有 Q&A。
     */
    @DeleteMapping("/parent-categories/{code}/bind")
    public ResponseEntity<Map<String, Object>> unbindParentCategory(@PathVariable String code) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        int count = kbService.unbindParentCategory(tenantId, userId, code);
        return ResponseEntity.ok(Map.of("unbound_count", count));
    }

    /* ===== 用户私有 KB ===== */

    @GetMapping("/user-kb")
    public ResponseEntity<List<Map<String, Object>>> listUserKb() {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        return ResponseEntity.ok(kbService.listUserKb(tenantId, userId));
    }

    @PostMapping("/user-kb")
    public ResponseEntity<Long> createUserKb(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        Long id = kbService.createUserKb(
            tenantId, userId,
            (String) body.get("title"),
            (String) body.get("content"),
            (String) body.get("category"),
            (String) body.get("tags")
        );
        return ResponseEntity.ok(id);
    }

    @PutMapping("/user-kb/{id}")
    public ResponseEntity<Void> updateUserKb(@PathVariable Long id,
                                              @RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        kbService.updateUserKb(tenantId, userId, id,
            (String) body.get("title"),
            (String) body.get("content"),
            (String) body.get("category"),
            (String) body.get("tags")
        );
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/user-kb/{id}")
    public ResponseEntity<Void> deleteUserKb(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        kbService.deleteUserKb(tenantId, userId, id);
        return ResponseEntity.ok().build();
    }

    /* ===== 绑定关系 ===== */

    @GetMapping("/bindings")
    public ResponseEntity<List<Map<String, Object>>> listBindings() {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        return ResponseEntity.ok(kbService.listBindings(tenantId, userId));
    }

    @PostMapping("/bindings")
    public ResponseEntity<Void> bindKbs(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        List<Map<String, Object>> items = (List<Map<String, Object>>) body.get("items");
        kbService.bindKbs(tenantId, userId, items);
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/bindings")
    public ResponseEntity<Void> unbind(@RequestParam String kbType, @RequestParam Long kbId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        kbService.unbindKb(tenantId, userId, kbType, kbId);
        return ResponseEntity.ok().build();
    }
}
