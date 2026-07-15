package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.UserProfileService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 前台个人中心接口。
 */
@RestController
@RequestMapping("/api/profile")
public class UserProfileController {
    private final UserProfileService userProfileService;

    public UserProfileController(UserProfileService userProfileService) {
        this.userProfileService = userProfileService;
    }

    @GetMapping("/overview")
    public Result<Map<String, Object>> overview() {
        return Result.ok(userProfileService.overview());
    }

    @PostMapping("/send-code")
    public Result<Map<String, Object>> sendCode(@RequestBody Map<String, String> body, HttpServletRequest request) {
        return Result.ok(userProfileService.sendCode(
                body.get("targetType"), body.get("target"), body.get("purpose"), clientIp(request), request.getHeader("User-Agent")));
    }

    @GetMapping("/token-ledger")
    public Result<Map<String, Object>> tokenLedger(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "100") int size) {
        return Result.ok(userProfileService.tokenLedger(current, size));
    }

    @PostMapping("/change-password")
    public Result<Void> changePassword(@RequestBody Map<String, String> body, HttpServletRequest request) {
        userProfileService.changePassword(body.get("oldPassword"), body.get("newPassword"), clientIp(request), request.getHeader("User-Agent"));
        return Result.ok(null);
    }

    @PostMapping("/change-phone")
    public Result<Void> changePhone(@RequestBody Map<String, String> body, HttpServletRequest request) {
        userProfileService.changePhone(body.get("phone"), body.get("code"), clientIp(request), request.getHeader("User-Agent"));
        return Result.ok(null);
    }

    @PostMapping("/change-email")
    public Result<Void> changeEmail(@RequestBody Map<String, String> body, HttpServletRequest request) {
        userProfileService.changeEmail(body.get("email"), body.get("code"), clientIp(request), request.getHeader("User-Agent"));
        return Result.ok(null);
    }

    private String clientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }
}
