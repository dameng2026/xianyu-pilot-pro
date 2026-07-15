package com.xianyu.admin.config;

import com.xianyu.admin.service.AuthService;
import com.xianyu.admin.service.UserAuthService;
import org.junit.jupiter.api.Test;
import org.springframework.boot.DefaultApplicationArguments;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class SeedDataRunnerTest {

    @Test
    void delegatesToServicesWhoseOwnPoliciesGuardProductionSeeding() throws Exception {
        AuthService authService = mock(AuthService.class);
        UserAuthService userAuthService = mock(UserAuthService.class);
        SeedDataRunner runner = new SeedDataRunner(authService, userAuthService);

        runner.run(new DefaultApplicationArguments(new String[0]));

        verify(authService).seedAdmin();
        verify(userAuthService).seedUser();
    }
}
