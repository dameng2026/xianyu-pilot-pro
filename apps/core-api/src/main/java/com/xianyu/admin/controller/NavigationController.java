package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.NavigationHomeVO;
import com.xianyu.admin.dto.NavigationOverviewVO;
import com.xianyu.admin.dto.NotificationVO;
import com.xianyu.admin.dto.SystemStatusVO;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.service.NavigationService;
import com.xianyu.admin.service.OpenSourceContentService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/api/navigation")
@Validated
public class NavigationController {
    private static final Logger log = LoggerFactory.getLogger(NavigationController.class);

    private final NavigationService navigationService;
    private final OpenSourceContentService contentService;

    public NavigationController(NavigationService navigationService,
                                OpenSourceContentService contentService) {
        this.navigationService = navigationService;
        this.contentService = contentService;
    }

    @GetMapping("/home")
    public Result<NavigationHomeVO> home(@RequestParam(defaultValue = "5") int limit) {
        Long tenantId = TenantContext.getCurrentTenantId();
        int safeLimit = Math.max(1, Math.min(limit, 10));

        NavigationHomeVO result = new NavigationHomeVO();
        loadManagedContent(result);
        result.setOverview(navigationService.overview(tenantId));
        result.setNotifications(navigationService.recentNotifications(tenantId, safeLimit));
        result.setSystemStatus(navigationService.systemStatus());
        return Result.ok(result);
    }

    /**
     * 瀵艰埅姒傝锛堥《閮ㄥ崱鐗囷級
     */
    @GetMapping("/overview")
    public Result<NavigationOverviewVO> overview() {
        Long tenantId = TenantContext.getCurrentTenantId();
        NavigationOverviewVO result = navigationService.overview(tenantId);
        return Result.ok(result);
    }

    /**
     * 鏈€杩戦€氱煡
     */
    @GetMapping("/notifications")
    public Result<List<NotificationVO>> notifications(
            @RequestParam(defaultValue = "10") int limit) {
        Long tenantId = TenantContext.getCurrentTenantId();
        List<NotificationVO> result = navigationService.recentNotifications(tenantId, limit);
        return Result.ok(result);
    }

    /**
     * 绯荤粺鐘舵€?
     */
    @GetMapping("/system-status")
    public Result<List<SystemStatusVO>> systemStatus() {
        List<SystemStatusVO> result = navigationService.systemStatus();
        return Result.ok(result);
    }

    private void loadManagedContent(NavigationHomeVO result) {
        try {
            result.setCarousels(contentService.listCommercialHomeCarousels());
            result.setAnnouncements(contentService.listCommercialHomeAnnouncements());
            result.setContentAvailable(true);
            result.setContentMessage("");
        } catch (Exception ex) {
            log.error("navigation managed content unavailable, errorType={}", ex.getClass().getSimpleName());
            result.setCarousels(Collections.emptyList());
            result.setAnnouncements(Collections.emptyList());
            result.setContentAvailable(false);
            result.setContentMessage("轮播与公告暂时无法读取，其他首页数据不受影响");
        }
    }
}
