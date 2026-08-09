package com.xianyu.admin.controller;

import com.xianyu.admin.common.MaskUtil;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.SysUserService;
import com.xianyu.admin.service.UserAuthService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 系统用户管理接口，挂载在 /admin-api/system/user。
 * 通过 JwtAuthFilter 校验 Bearer Token（管理员登录后访问）。
 * phone / email 字段在返回前端时统一做 PII 脱敏处理。
 *
 * <p>注意：page/detail/create/update/delete/batch-delete/status/batch-status 等端点
 * 与 AdminModuleController（/admin-api/admin/modules/users）功能重复，
 * 前端已统一使用 AdminModuleController，以下端点标记 @Deprecated 仅供向后兼容，
 * 新代码请勿调用，后续版本可能移除。</p>
 *
 * <p>当前前端实际使用的端点：
 * <ul>
 *   <li>POST /{id}/reset-password — 重置用户密码</li>
 *   <li>POST /{id}/login-token — 管理员代登：为指定前台用户签发登录 token（仅辅助调试）</li>
 *   <li>PUT /{id}/token-balance — 更新 Token 余额（已合并到 update，保留兼容）</li>
 *   <li>PUT /{id}/vip-level — 更新 VIP 等级（已合并到 update，保留兼容）</li>
 * </ul></p>
 */
@RestController
@RequestMapping("/admin-api/system/user")
public class SysUserController {

    private final SysUserService sysUserService;
    private final UserAuthService userAuthService;

    public SysUserController(SysUserService sysUserService, UserAuthService userAuthService) {
        this.sysUserService = sysUserService;
        this.userAuthService = userAuthService;
    }

    /**
     * @deprecated 前端已改用 GET /admin-api/admin/users，此端点仅供向后兼容。
     */
    @Deprecated
    @GetMapping("/page")
    public Result<PageResult<Map<String, Object>>> page(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String username,
            @RequestParam(required = false) String nickname,
            @RequestParam(required = false) String phone,
            @RequestParam(required = false) String email,
            @RequestParam(required = false) String status) {
        PageResult<Map<String, Object>> result = sysUserService.page(current, size,
                username, nickname, phone, email, status);
        sysUserService.enrichUserLevels(result.getRecords());
        // 列表视图统一脱敏 phone/email
        for (Map<String, Object> row : result.getRecords()) {
            maskPii(row);
        }
        return Result.ok(result);
    }

    /**
     * @deprecated 前端已改用 GET /admin-api/admin/modules/users/{id}，此端点仅供向后兼容。
     */
    @Deprecated
    @GetMapping("/{id}")
    public Result<Map<String, Object>> detail(@PathVariable long id) {
        Map<String, Object> record = sysUserService.detail(id);
        sysUserService.enrichUserLevels(java.util.List.of(record));
        // 详情视图同样脱敏，管理员可通过 username/userId 定位用户
        maskPii(record);
        return Result.ok(record);
    }

    /**
     * 对返回数据中的 phone/email 字段做 PII 脱敏。
     * 保留首尾部分字符，避免明文批量泄露。
     */
    private void maskPii(Map<String, Object> row) {
        if (row == null) return;
        Object phone = row.get("phone");
        if (phone != null && !String.valueOf(phone).isBlank()) {
            row.put("phone", MaskUtil.maskPhone(String.valueOf(phone)));
        }
        Object email = row.get("email");
        if (email != null && !String.valueOf(email).isBlank()) {
            row.put("email", MaskUtil.maskEmail(String.valueOf(email)));
        }
    }

    /**
     * @deprecated 前端已改用 POST /admin-api/admin/modules/users，此端点仅供向后兼容。
     */
    @Deprecated
    @PostMapping
    public Result<Map<String, Object>> create(@RequestBody Map<String, Object> data) {
        return Result.ok(sysUserService.create(data));
    }

    /**
     * @deprecated 前端已改用 PUT /admin-api/admin/modules/users/{id}（单事务合并更新），此端点仅供向后兼容。
     */
    @Deprecated
    @PutMapping("/{id}")
    public Result<Map<String, Object>> update(@PathVariable long id, @RequestBody Map<String, Object> data) {
        return Result.ok(sysUserService.update(id, data));
    }

    /**
     * @deprecated 前端已改用 DELETE /admin-api/admin/modules/users/{id}，此端点仅供向后兼容。
     */
    @Deprecated
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable long id) {
        sysUserService.delete(id);
        return Result.ok(null);
    }

    /**
     * @deprecated 前端已改用 POST /admin-api/admin/modules/users/batch-delete，此端点仅供向后兼容。
     */
    @Deprecated
    @PostMapping("/batch-delete")
    public Result<Map<String, Object>> batchDelete(@RequestBody Map<String, List<Long>> body) {
        List<Long> ids = body.get("ids");
        int count = sysUserService.batchDelete(ids);
        return Result.ok(Map.of("count", count));
    }

    /**
     * @deprecated 前端已改用 PUT /admin-api/admin/modules/users/{id}/status，此端点仅供向后兼容。
     */
    @Deprecated
    @PutMapping("/{id}/status")
    public Result<Void> updateStatus(@PathVariable long id, @RequestBody Map<String, Object> data) {
        int status = Integer.parseInt(String.valueOf(data.getOrDefault("status", "1")));
        sysUserService.updateStatus(id, status);
        return Result.ok(null);
    }

    /**
     * @deprecated 前端已改用 POST /admin-api/admin/modules/users/batch-status，此端点仅供向后兼容。
     */
    @Deprecated
    @PostMapping("/batch-status")
    public Result<Map<String, Object>> batchUpdateStatus(@RequestBody Map<String, Object> body) {
        @SuppressWarnings("unchecked")
        List<Long> ids = (List<Long>) body.get("ids");
        int status = Integer.parseInt(String.valueOf(body.getOrDefault("status", "1")));
        int count = sysUserService.batchUpdateStatus(ids, status);
        return Result.ok(Map.of("count", count));
    }

    /**
     * 重置用户密码。前端 index.vue 行操作"重置密码"调用此端点。
     */
    @PostMapping("/{id}/reset-password")
    public Result<Void> resetPassword(@PathVariable long id, @RequestBody Map<String, Object> data) {
        String newPassword = String.valueOf(data.getOrDefault("newPassword", ""));
        sysUserService.resetPassword(id, newPassword);
        return Result.ok(null);
    }

    /**
     * 管理员代登：为指定前台用户签发登录 token，用于辅助调试。
     * 调用方需持有 R_SUPER 角色（由 AdminRbacFilter 在 /admin-api/system/* 路径上强制校验）。
     * 不校验密码、不消费密码失败计数；不变更 security_version（不吊销用户已有会话）。
     */
    @PostMapping("/{id}/login-token")
    public Result<Map<String, Object>> issueLoginToken(@PathVariable long id) {
        return Result.ok(userAuthService.generateLoginTokenForUser(id));
    }

    /**
     * @deprecated Token 余额已合并到 PUT /admin-api/admin/modules/users/{id} 单事务更新，此端点仅供向后兼容。
     */
    @Deprecated
    @PutMapping("/{id}/token-balance")
    public Result<Void> updateTokenBalance(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        long tokenBalance = ((Number) body.get("tokenBalance")).longValue();
        sysUserService.updateTokenBalance(id, tokenBalance);
        return Result.ok(null);
    }

    /**
     * @deprecated VIP 等级已合并到 PUT /admin-api/admin/modules/users/{id} 单事务更新，此端点仅供向后兼容。
     */
    @Deprecated
    @PutMapping("/{id}/vip-level")
    public Result<Void> updateVipLevel(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        int vipLevel = ((Number) body.get("vipLevel")).intValue();
        Integer vipDurationDays = body.get("vipDurationDays") instanceof Number n ? n.intValue() : null;
        sysUserService.updateVipLevel(id, vipLevel, vipDurationDays);
        return Result.ok(null);
    }
}
