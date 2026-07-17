package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.CardGroupDTO;
import com.xianyu.admin.dto.CardGroupVO;
import com.xianyu.admin.dto.CardItemVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.CardService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;


@RestController
@RequestMapping("/api/cards")
@Validated
public class CardController {
    private static final int MAX_BATCH_IMPORT_ITEMS = 1_000;

    private final CardService cardService;

    public CardController(CardService cardService) {
        this.cardService = cardService;
    }

    /**
     * 分页查询卡片组列表
     */
    @GetMapping
    public Result<PageResult<CardGroupVO>> groups(
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<CardGroupVO> result = cardService.groups(tenantId, keyword, current, size);
        return Result.ok(result);
    }

    @GetMapping("/alerts")
    public Result<List<CardGroupVO>> alerts() {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(cardService.alerts(tenantId));
    }

    /**
     * 创建卡片组
     */
    @PostMapping
    public Result<Long> createGroup(@Valid @RequestBody CardGroupDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long groupId = cardService.createGroup(tenantId, dto);
        return Result.ok(groupId);
    }

    /**
     * 更新卡片组
     */
    @PutMapping("/{id}")
    public Result<Void> updateGroup(@PathVariable Long id, @Valid @RequestBody CardGroupDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        cardService.updateGroup(tenantId, id, dto);
        return Result.ok(null);
    }

    /**
     * 删除卡片组（软删除）
     */
    @DeleteMapping("/{id}")
    public Result<Void> deleteGroup(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        cardService.deleteGroup(tenantId, id);
        return Result.ok(null);
    }

    @GetMapping("/{id}")
    public Result<CardGroupVO> detail(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(cardService.detail(tenantId, id));
    }

    /**
     * 分页查询卡片项列表
     */
    @GetMapping("/{id}/items")
    public Result<PageResult<CardItemVO>> items(
            @PathVariable Long id,
            @RequestParam(required = false) Integer status,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<CardItemVO> result = cardService.items(tenantId, id, status, current, size);
        return Result.ok(result);
    }

    /**
     * 创建卡片项
     */
    public record CardItemCreateReq(
            @NotBlank(message = "卡密内容不能为空")
            @Size(max = 5000, message = "卡密内容不能超过5000个字符")
            String content) {}

    @PostMapping("/{id}/items")
    public Result<Void> createItem(@PathVariable Long id, @Valid @RequestBody CardItemCreateReq body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        cardService.createItem(tenantId, id, body.content());
        return Result.ok(null);
    }

    /**
     * 批量导入卡密
     * POST /api/cards/{groupId}/items/batch
     * body: { items: [{ content: "卡密内容", cardContent: "...", password: "..." }, ...] }
     */
    public record BatchItemReq(
            @Size(max = 5000, message = "卡密内容不能超过5000个字符") String content,
            @Size(max = 5000, message = "卡号不能超过5000个字符") String cardContent,
            @Size(max = 5000, message = "卡密密码不能超过5000个字符") String password) {}

    public record BatchImportReq(
            @NotEmpty(message = "导入列表不能为空")
            @Size(max = MAX_BATCH_IMPORT_ITEMS, message = "单次最多导入1000条卡密")
            java.util.List<@Valid BatchItemReq> items) {}

    @PostMapping("/{groupId}/items/batch")
    public Result<java.util.Map<String, Object>> batchCreateItems(@PathVariable Long groupId, @Valid @RequestBody BatchImportReq body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (body == null || body.items() == null || body.items().isEmpty()) {
            throw new com.xianyu.admin.common.BizException(400, "导入列表不能为空");
        }
        if (body.items().size() > MAX_BATCH_IMPORT_ITEMS) {
            throw new com.xianyu.admin.common.BizException(413, "单次最多导入1000条卡密");
        }
        int success = 0, duplicate = 0, fail = 0;
        for (BatchItemReq item : body.items()) {
            String content = batchItemContent(item);
            if (content.isEmpty()) { fail++; continue; }
            try {
                cardService.createItem(tenantId, groupId, content);
                success++;
            } catch (com.xianyu.admin.common.BizException e) {
                if (e.getMessage() != null && e.getMessage().contains("已存在")) {
                    duplicate++;
                } else {
                    fail++;
                }
            } catch (Exception e) {
                fail++;
            }
        }
        return Result.ok(java.util.Map.of("successCount", success, "duplicateCount", duplicate, "failCount", fail));
    }

    private String batchItemContent(BatchItemReq item) {
        if (item == null) return "";
        String direct = item.content() == null ? "" : item.content().trim();
        if (!direct.isEmpty()) return direct;
        String card = item.cardContent() == null ? "" : item.cardContent().trim();
        String password = item.password() == null ? "" : item.password().trim();
        if (!card.isEmpty() && !password.isEmpty()) return card + "----" + password;
        return !card.isEmpty() ? card : password;
    }

    @DeleteMapping("/{groupId}/items/{itemId}")
    public Result<Void> deleteItem(@PathVariable Long groupId, @PathVariable Long itemId) {
        cardService.deleteItem(TenantContext.getCurrentTenantId(), groupId, itemId);
        return Result.ok(null);
    }

    @PostMapping("/{groupId}/items/{itemId}/reset")
    public Result<Void> resetItem(@PathVariable Long groupId, @PathVariable Long itemId) {
        cardService.resetItem(TenantContext.getCurrentTenantId(), groupId, itemId);
        return Result.ok(null);
    }

    @PostMapping("/{groupId}/items/{itemId}/lock")
    public Result<Void> lockItem(@PathVariable Long groupId, @PathVariable Long itemId) {
        cardService.lockItem(TenantContext.getCurrentTenantId(), groupId, itemId);
        return Result.ok(null);
    }

    @PostMapping("/{groupId}/items/{itemId}/invalid")
    public Result<Void> markInvalid(@PathVariable Long groupId, @PathVariable Long itemId) {
        cardService.markInvalid(TenantContext.getCurrentTenantId(), groupId, itemId);
        return Result.ok(null);
    }

    @GetMapping("/{groupId}/stats")
    public Result<Map<String, Object>> stats(@PathVariable Long groupId) {
        return Result.ok(cardService.stockStats(TenantContext.getCurrentTenantId(), groupId));
    }

    @GetMapping("/{groupId}/usage")
    public Result<PageResult<CardItemVO>> usage(@PathVariable Long groupId,
                                                @RequestParam(defaultValue = "1") int current,
                                                @RequestParam(defaultValue = "20") int size) {
        return Result.ok(cardService.usageRecords(TenantContext.getCurrentTenantId(), groupId, current, size));
    }

    @GetMapping("/{groupId}/export")
    public @ResponseBody byte[] export(@PathVariable Long groupId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        List<CardItemVO> items = cardService.exportItems(tenantId, groupId);
        StringBuilder builder = new StringBuilder();
        for (CardItemVO item : items) {
            builder.append(item.getContent() == null ? "" : item.getContent()).append('\n');
        }
        return builder.toString().getBytes(StandardCharsets.UTF_8);
    }
}
