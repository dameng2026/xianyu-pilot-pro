package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.DeleteResultVO;
import com.xianyu.admin.dto.XianyuGoodsDTO;
import com.xianyu.admin.dto.XianyuGoodsVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.XianyuGoodsService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/goods")
@Validated
public class XianyuGoodsController {

    private final XianyuGoodsService goodsService;

    public XianyuGoodsController(XianyuGoodsService goodsService) {
        this.goodsService = goodsService;
    }

    /**
     * 分页查询商品列表
     */
    @GetMapping
    public Result<PageResult<XianyuGoodsVO>> page(
            @RequestParam(required = false) Long accountId,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer status,
            @RequestParam(required = false) Integer excludeStatus,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<XianyuGoodsVO> result = goodsService.page(tenantId, accountId, keyword, status, excludeStatus, current, size);
        return Result.ok(result);
    }

    /**
     * 统计商品全局数据（不受分页、关键词、状态筛选影响，仅按账号过滤）
     */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats(@RequestParam(required = false) Long accountId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> stats = goodsService.stats(tenantId, accountId);
        return Result.ok(stats);
    }

    /**
     * 创建商品
     */
    @PostMapping
    public Result<Void> create(@Valid @RequestBody XianyuGoodsDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        goodsService.create(tenantId, dto);
        return Result.ok(null);
    }

    /**
     * 查询商品详情
     */
    @GetMapping("/{id}")
    public Result<XianyuGoodsVO> detail(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        XianyuGoodsVO result = goodsService.detail(tenantId, id);
        return Result.ok(result);
    }

    /**
     * 更新商品
     */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody XianyuGoodsDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        goodsService.update(tenantId, id, dto);
        return Result.ok(null);
    }

    /**
     * 兼容旧接口：为了避免误删闲鱼线上商品，默认仅删除本地记录。
     */
    @DeleteMapping("/{id}")
    public Result<DeleteResultVO> delete(@PathVariable Long id, HttpServletRequest request) {
        return deleteLocal(id, request);
    }

    /**
     * 仅删除本地商品记录，不影响闲鱼线上商品。
     */
    @DeleteMapping("/{id}/local")
    public Result<DeleteResultVO> deleteLocal(@PathVariable Long id, HttpServletRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        String ipAddress = getClientIp(request);
        DeleteResultVO result = goodsService.deleteLocal(tenantId, userId, id, ipAddress);
        return Result.ok(result);
    }

    /**
     * 远端删除：删除闲鱼线上商品，并在本地标记删除。需要前端强确认。
     */
    @DeleteMapping("/{id}/remote")
    public Result<DeleteResultVO> deleteRemote(@PathVariable Long id,
                                               @RequestBody(required = false) java.util.Map<String, Object> body,
                                               HttpServletRequest request) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = TenantContext.getCurrentUserId();
        String confirmText = body == null ? null : String.valueOf(body.getOrDefault("confirmText", ""));
        String ipAddress = getClientIp(request);
        DeleteResultVO result = goodsService.deleteRemote(tenantId, userId, id, confirmText, ipAddress);
        return Result.ok(result);
    }

    private String getClientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }
}
