package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.SyncReceiveService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 数据同步接收端控制器。
 * <p>
 * 暴露两个端点供本地发送端调用：
 *   POST /api/sync/ping     连通性测试（SyncAuthFilter 鉴权）
 *   POST /api/sync/receive  接收并应用同步数据包（SyncAuthFilter 鉴权）
 * <p>
 * 路径选择 /api/sync/* 而非 /open-api/internal/sync/* 的原因：
 * 线上 Nginx 仅反代 /api/ 到后端，/open-api/ 走 SPA fallback 无法到达后端。
 * UserJwtAuthFilter 在 shouldNotFilter 中跳过 /api/sync/，由 SyncAuthFilter 独立鉴权。
 */
@RestController
@RequestMapping("/api/sync")
public class SyncReceiveController {
    private static final Logger log = LoggerFactory.getLogger(SyncReceiveController.class);

    private final SyncReceiveService syncReceiveService;

    public SyncReceiveController(SyncReceiveService syncReceiveService) {
        this.syncReceiveService = syncReceiveService;
    }

    /**
     * 连通性测试。SyncAuthFilter 已完成 token 鉴权，此处直接返回成功。
     */
    @PostMapping("/ping")
    public Result<Map<String, Object>> ping() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("ok", true);
        data.put("service", "core-api");
        data.put("timestamp", System.currentTimeMillis());
        return Result.ok(data);
    }

    /**
     * 接收同步数据包并应用。
     * SyncAuthFilter 已完成 token 鉴权，请求可信，直接交给 SyncReceiveService 处理。
     */
    @PostMapping("/receive")
    public Result<Map<String, Object>> receive(@RequestBody Map<String, Object> pkg) {
        log.info("收到数据同步包: targetUsername={}, modules={}",
                pkg.get("targetUsername"),
                pkg.containsKey("modules") ? ((Map<?, ?>) pkg.get("modules")).keySet() : "unknown");
        Map<String, Object> result = syncReceiveService.receive(pkg);
        return Result.ok(result);
    }
}
