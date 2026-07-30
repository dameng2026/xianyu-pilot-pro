package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.dto.XianyuAccountDTO;
import com.xianyu.admin.dto.XianyuAccountSummaryVO;
import com.xianyu.admin.dto.XianyuAccountVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import com.xianyu.admin.service.XianyuAccountFeatureService;
import com.xianyu.admin.service.XianyuAccountService;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/xianyu/accounts")
@Validated
public class XianyuAccountController {

    private final XianyuAccountService accountService;
    private final XianyuAccountFeatureService accountFeatureService;

    public XianyuAccountController(XianyuAccountService accountService,
                                   XianyuAccountFeatureService accountFeatureService) {
        this.accountService = accountService;
        this.accountFeatureService = accountFeatureService;
    }

    /**
     * 分页查询账号列表
     */
    @GetMapping
    public Result<PageResult<XianyuAccountVO>> page(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer status,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<XianyuAccountVO> result = accountService.page(tenantId, keyword, status, current, size);
        return Result.ok(result);
    }

    @GetMapping("/lite")
    public Result<PageResult<XianyuAccountVO>> pageLite(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer status,
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        PageResult<XianyuAccountVO> result = accountService.pageLite(tenantId, keyword, status, current, size);
        return Result.ok(result);
    }

    /**
     * 创建账号
     */
    @PostMapping
    public Result<XianyuAccountVO> create(@Valid @RequestBody XianyuAccountDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        XianyuAccountVO result = accountService.create(tenantId, userId, dto);
        return Result.ok(result);
    }


    /**
     * 前台手动粘贴 Cookie 添加账号。
     */
    @PostMapping("/manual-cookie")
    public Result<XianyuAccountVO> createByCookie(@RequestBody Map<String, String> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        XianyuAccountVO result = accountService.createFromCookie(tenantId, userId, body.get("accountNote"), body.get("cookie"));
        return Result.ok(result);
    }

    /**
     * 查询账号详情
     */
    @GetMapping("/{id}")
    public Result<XianyuAccountVO> detail(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        XianyuAccountVO result = accountService.detail(tenantId, id);
        return Result.ok(result);
    }

    /**
     * 更新账号
     */
    @PutMapping("/{id}")
    public Result<XianyuAccountVO> update(@PathVariable Long id, @Valid @RequestBody XianyuAccountDTO dto) {
        Long tenantId = TenantContext.getCurrentTenantId();
        XianyuAccountVO result = accountService.update(tenantId, id, dto);
        return Result.ok(result);
    }

    @PostMapping("/{id}/cookie")
    public Result<XianyuAccountVO> updateCookie(@PathVariable Long id, @RequestBody Map<String, String> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        XianyuAccountVO result = accountService.updateCookie(tenantId, id, body == null ? null : body.get("cookie"));
        return Result.ok(result);
    }

    /**
     * 获取账号当前 Cookie 明文，供前台"编辑 Cookie"弹窗回填展示（可复制或微调）。
     */
    @GetMapping("/{id}/cookie")
    public Result<Map<String, Object>> getCurrentCookie(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(accountService.getCurrentCookie(tenantId, id));
    }

    /**
     * 删除账号（软删除）
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        accountService.delete(tenantId, id);
        return Result.ok(null);
    }

    /**
     * 汇总统计
     */
    @GetMapping("/summary")
    public Result<XianyuAccountSummaryVO> summary() {
        Long tenantId = TenantContext.getCurrentTenantId();
        XianyuAccountSummaryVO result = accountService.summary(tenantId);
        return Result.ok(result);
    }

    /**
     * 刷新账号资料（调用闲鱼 API 获取最新用户信息）
     */
    @PostMapping("/{id}/refresh-profile")
    public Result<XianyuAccountVO> refreshProfile(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        XianyuAccountVO result = accountService.refreshProfile(tenantId, id);
        return Result.ok(result);
    }

    @PostMapping("/{id}/check-auth")
    public Result<AccountAuthStatusResult> checkAuth(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        AccountAuthStatusResult result = accountService.checkAuthStatus(tenantId, id, "account-page");
        return Result.ok(result);
    }

    @GetMapping("/{id}/auto-rate")
    public Result<Map<String, Object>> autoRate(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(accountFeatureService.getAutoRateConfig(tenantId, id));
    }

    @PutMapping("/{id}/auto-rate")
    public Result<Map<String, Object>> saveAutoRate(@PathVariable Long id,
                                                    @RequestBody(required = false) Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        return Result.ok(accountFeatureService.saveAutoRateConfig(tenantId, userId, id, body));
    }

    @GetMapping("/{id}/strategy-config")
    public Result<Map<String, Object>> strategyConfig(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(accountFeatureService.getStrategyConfig(tenantId, id));
    }

    @PutMapping("/{id}/strategy-config")
    public Result<Map<String, Object>> saveStrategyConfig(@PathVariable Long id,
                                                          @RequestBody(required = false) Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(accountFeatureService.saveStrategyConfig(tenantId, id, body));
    }

    @GetMapping("/{id}/login-credential")
    public Result<Map<String, Object>> loginCredential(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(accountService.getLoginCredentialConfig(tenantId, id));
    }

    @PutMapping("/{id}/login-credential")
    public Result<Map<String, Object>> saveLoginCredential(@PathVariable Long id,
                                                           @RequestBody(required = false) Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        return Result.ok(accountService.saveLoginCredentialConfig(tenantId, id, body));
    }

    @GetMapping("/face-verifications")
    public Result<PageResult<Map<String, Object>>> faceVerifications(@RequestParam(required = false) Long accountId,
                                                                     @RequestParam(defaultValue = "1") int current,
                                                                     @RequestParam(defaultValue = "20") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        return Result.ok(accountFeatureService.pageFaceVerifications(tenantId, userId, accountId, current, size));
    }

    @PostMapping("/face-verifications/{notificationId}/read")
    public Result<Void> readFaceVerification(@PathVariable Long notificationId) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        accountFeatureService.markFaceVerificationRead(tenantId, userId, notificationId);
        return Result.ok(null);
    }
}
