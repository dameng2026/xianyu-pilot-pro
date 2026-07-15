package com.xianyu.admin.config;

import com.xianyu.admin.service.AuthService;
import com.xianyu.admin.service.UserAuthService;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

/**
 * 在 schema runner 成功后触发可选的开发种子。
 *
 * 两个服务各自根据 admin.seed.enabled 与生产 profile 决定是否真正写入，
 * 因此这里不复制安全策略，也不会在生产环境创建默认账号。
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 100)
public class SeedDataRunner implements ApplicationRunner {
    private final AuthService authService;
    private final UserAuthService userAuthService;

    public SeedDataRunner(AuthService authService, UserAuthService userAuthService) {
        this.authService = authService;
        this.userAuthService = userAuthService;
    }

    @Override
    public void run(ApplicationArguments args) {
        authService.seedAdmin();
        userAuthService.seedUser();
    }
}
