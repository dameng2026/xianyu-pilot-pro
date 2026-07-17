package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.service.MallProductService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * 货源商城管理端控制器。
 * /admin-api/mall 前缀，需要 AdminContext 鉴权。
 */
@RestController
@RequestMapping("/admin-api/mall")
public class MallProductAdminController {
    private static final Logger log = LoggerFactory.getLogger(MallProductAdminController.class);

    private final MallProductService mallProductService;

    public MallProductAdminController(MallProductService mallProductService) {
        this.mallProductService = mallProductService;
    }

    // ==================== 商品 ====================

    @GetMapping("/products")
    public Result<PageResult<Map<String, Object>>> listProducts(
            @RequestParam(required = false) String type,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        requireAdmin();
        return Result.ok(mallProductService.listProducts(type, page, size));
    }

    @GetMapping("/products/{id}")
    public Result<Map<String, Object>> getProduct(@PathVariable long id) {
        requireAdmin();
        if (id <= 0) throw new BizException(400, "商品 ID 非法");
        return Result.ok(mallProductService.getProduct(id));
    }

    @PostMapping("/products")
    public Result<Map<String, Object>> createProduct(@RequestBody Map<String, Object> body) {
        requireAdmin();
        if (body == null || body.isEmpty()) throw new BizException(400, "商品参数不能为空");
        return Result.ok(mallProductService.createProduct(body));
    }

    @PutMapping("/products/{id}")
    public Result<Map<String, Object>> updateProduct(@PathVariable long id, @RequestBody Map<String, Object> body) {
        requireAdmin();
        if (id <= 0) throw new BizException(400, "商品 ID 非法");
        if (body == null || body.isEmpty()) throw new BizException(400, "商品参数不能为空");
        return Result.ok(mallProductService.updateProduct(id, body));
    }

    @DeleteMapping("/products/{id}")
    public Result<Void> deleteProduct(@PathVariable long id) {
        requireAdmin();
        if (id <= 0) throw new BizException(400, "商品 ID 非法");
        mallProductService.deleteProduct(id);
        return Result.ok(null);
    }

    // ==================== 卡密 ====================

    @PostMapping("/products/{id}/card-keys")
    public Result<Map<String, Object>> importCardKeys(@PathVariable long id, @RequestBody Map<String, Object> body) {
        requireAdmin();
        if (id <= 0) throw new BizException(400, "商品 ID 非法");
        if (body == null) throw new BizException(400, "卡密参数不能为空");
        Object cards = body.get("cards");
        if (cards == null) cards = body.get("cardKeys");
        if (cards == null) throw new BizException(400, "卡密内容不能为空");
        return Result.ok(mallProductService.importCardKeys(id, String.valueOf(cards)));
    }

    @GetMapping("/products/{id}/card-keys")
    public Result<PageResult<Map<String, Object>>> listCardKeys(
            @PathVariable long id,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        requireAdmin();
        if (id <= 0) throw new BizException(400, "商品 ID 非法");
        return Result.ok(mallProductService.listCardKeys(id, page, size));
    }

    // ==================== 分类 ====================

    @PostMapping("/categories/refresh")
    public Result<Map<String, Object>> refreshCategories() {
        requireAdmin();
        try {
            return Result.ok(mallProductService.refreshCategories());
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("AI 分类刷新失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "AI 分类服务暂时不可用，请稍后重试");
        }
    }

    // ==================== FAQ ====================

    @GetMapping("/faqs")
    public Result<List<Map<String, Object>>> listFaqs() {
        requireAdmin();
        return Result.ok(mallProductService.listFaqs());
    }

    @PostMapping("/faqs")
    public Result<Map<String, Object>> createFaq(@RequestBody Map<String, Object> body) {
        requireAdmin();
        if (body == null || body.isEmpty()) throw new BizException(400, "FAQ 参数不能为空");
        return Result.ok(mallProductService.createFaq(body));
    }

    @PutMapping("/faqs/{id}")
    public Result<Map<String, Object>> updateFaq(@PathVariable long id, @RequestBody Map<String, Object> body) {
        requireAdmin();
        if (id <= 0) throw new BizException(400, "FAQ ID 非法");
        if (body == null || body.isEmpty()) throw new BizException(400, "FAQ 参数不能为空");
        return Result.ok(mallProductService.updateFaq(id, body));
    }

    @DeleteMapping("/faqs/{id}")
    public Result<Void> deleteFaq(@PathVariable long id) {
        requireAdmin();
        if (id <= 0) throw new BizException(400, "FAQ ID 非法");
        mallProductService.deleteFaq(id);
        return Result.ok(null);
    }

    // ==================== 鉴权 ====================

    private void requireAdmin() {
        Long adminId = AdminContext.userId();
        if (adminId == null) {
            throw new BizException(401, "管理员登录状态已失效");
        }
        // 仅校验管理员身份，具体角色权限可由前端菜单/按钮控制
        Objects.requireNonNull(adminId);
    }
}
