package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.UserProfileService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/** 兼容 user-web 旧 system API 的安全设置接口。 */
@RestController
@RequestMapping("/api/system")
public class UserSystemSecurityController {
    private final UserProfileService userProfileService;

    public UserSystemSecurityController(UserProfileService userProfileService) {
        this.userProfileService = userProfileService;
    }

    @PostMapping("/changePassword")
    public Result<Void> changePassword(@RequestBody Map<String, String> body, HttpServletRequest request) {
        String oldPassword = body.getOrDefault("oldPassword", body.get("old_password"));
        String newPassword = body.getOrDefault("newPassword", body.get("new_password"));
        userProfileService.changePassword(oldPassword, newPassword, clientIp(request), request.getHeader("User-Agent"));
        return Result.ok(null);
    }

    private String clientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }
}
