package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.AiCsLearnedKbService;
import com.xianyu.admin.service.AutomationClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/ai-cs/kb")
public class AiCsKbController {

    private static final Logger log = LoggerFactory.getLogger(AiCsKbController.class);

    private final AiCsLearnedKbService kbService;
    private final AutomationClient automationClient;

    public AiCsKbController(AiCsLearnedKbService kbService, AutomationClient automationClient) {
        this.kbService = kbService;
        this.automationClient = automationClient;
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

    /* ===== 新建知识库弹窗：文件上传 / 会话提取 / AI 推荐会话 / 批量创建 ===== */

    /**
     * 文件上传模式：multipart 文件 → Python 解析 + AI 提取 Q&A → 返回 Q&A 数组（不写库）。
     * 支持格式：.md .txt .csv .xlsx .pptx .docx .pdf（最大 10MB）。
     * 可选参数 fileType：auto(默认) / chat_records / product_docs / company_docs / general
     */
    @PostMapping("/user-kb/extract-from-file")
    public Result<Object> extractFromFile(
        @RequestParam("file") MultipartFile file,
        @RequestParam(value = "fileType", required = false) String fileType
    ) {
        try {
            if (file == null || file.isEmpty()) {
                throw new BizException(400, "请选择要上传的文件");
            }
            String fileName = file.getOriginalFilename();
            if (fileName == null || fileName.isBlank()) {
                throw new BizException(400, "文件名为空");
            }
            String ext = fileName.contains(".")
                ? fileName.substring(fileName.lastIndexOf('.')).toLowerCase()
                : "";
            java.util.Set<String> allowed = java.util.Set.of(
                ".md", ".txt", ".pptx", ".xlsx", ".csv", ".docx", ".pdf"
            );
            if (!allowed.contains(ext)) {
                throw new BizException(400, "不支持的文件格式，仅支持 " + String.join("/", allowed));
            }
            if (file.getSize() > 10L * 1024 * 1024) {
                throw new BizException(400, "文件不能超过 10MB");
            }

            Long userId = TenantContext.getCurrentUserId();
            Long tenantId = TenantContext.getCurrentTenantId();
            if (userId == null || tenantId == null) {
                throw new BizException(401, "登录状态已失效");
            }
            Map<String, Object> extraForm = new HashMap<>();
            extraForm.put("userId", String.valueOf(userId));
            extraForm.put("tenantId", String.valueOf(tenantId));
            // 透传文件类型（auto/chat_records/product_docs/company_docs/general）
            if (fileType != null && !fileType.isBlank()) {
                extraForm.put("fileType", fileType.trim().toLowerCase());
            }
            // AI 提取可能耗时较长（解析+LLM），用 180s 超时
            Map<String, Object> result = automationClient.uploadInternalForData(
                "/api/knowledge-base/extract-qa-from-file",
                file.getInputStream(),
                fileName,
                extraForm
            );
            return Result.ok(result);
        } catch (BizException e) {
            throw e;
        } catch (IOException e) {
            log.error("读取上传文件失败", e);
            throw new BizException(400, "读取文件失败");
        } catch (Exception e) {
            log.error("文件提取 Q&A 失败, errorType={}", e.getClass().getSimpleName(), e);
            throw new BizException(503, "文件处理暂时不可用，请稍后重试");
        }
    }

    /**
     * 会话聊天提取模式：根据 accountId + conversationIds 拉取消息 → AI 提取 Q&A。
     * 请求体: { accountId, conversationIds:[], conversations:[{conversationId,sid,...}] }
     */
    @PostMapping("/user-kb/extract-from-conversations")
    public Result<Object> extractFromConversations(@RequestBody Map<String, Object> body) {
        Long userId = TenantContext.getCurrentUserId();
        Long tenantId = TenantContext.getCurrentTenantId();
        if (userId == null || tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        Map<String, Object> payload = new HashMap<>(body);
        payload.put("userId", userId);
        payload.put("tenantId", tenantId);
        // AI 提取可能耗时较长（多会话+LLM），用 180s 超时
        Map<String, Object> result = automationClient.postInternalForData(
            "/api/knowledge-base/extract-qa-from-conversations",
            payload,
            180L
        );
        return Result.ok(result);
    }

    /**
     * AI 智能推荐高价值会话：传入会话列表，AI 返回推荐会话 + 推荐理由 + 价值评分。
     * 请求体: { accountId, conversations:[{conversationId,peerUserName,goodsTitle,lastMessage,messageCount}] }
     */
    @PostMapping("/user-kb/recommend-conversations")
    public Result<Object> recommendConversations(@RequestBody Map<String, Object> body) {
        Long userId = TenantContext.getCurrentUserId();
        Long tenantId = TenantContext.getCurrentTenantId();
        if (userId == null || tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        Map<String, Object> payload = new HashMap<>(body);
        payload.put("userId", userId);
        payload.put("tenantId", tenantId);
        Map<String, Object> result = automationClient.postInternalForData(
            "/api/knowledge-base/recommend-conversations",
            payload,
            180L
        );
        return Result.ok(result);
    }

    /**
     * 批量创建用户私有 KB（用于文件上传/会话提取模式确认保存）。
     * 请求体: { entries:[{title,content,category,tags}], defaultCategory, defaultTags }
     */
    @PostMapping("/user-kb/batch")
    public Result<Object> batchCreateUserKb(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        Object entriesRaw = body.get("entries");
        if (!(entriesRaw instanceof List)) {
            throw new BizException(400, "entries 必须为数组");
        }
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> entries = (List<Map<String, Object>>) entriesRaw;
        String defaultCategory = body.get("defaultCategory") == null ? "" : String.valueOf(body.get("defaultCategory"));
        String defaultTags = body.get("defaultTags") == null ? "" : String.valueOf(body.get("defaultTags"));
        Map<String, Object> result = kbService.batchCreateUserKb(tenantId, userId, entries, defaultCategory, defaultTags);
        return Result.ok(result);
    }
}
