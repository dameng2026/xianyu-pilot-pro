package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 后台通知发送记录控制器。
 *
 * 修复历史：原本此接口被放在 {@link UserUtilityController} 中，
 * 但该控制器类级 {@code @RequestMapping("/api")} 与方法级
 * {@code @GetMapping("/admin-api/notifications/delivery-logs")} 拼接后实际生效路径为
 * {@code /api/admin-api/notifications/delivery-logs}，与前端调用的
 * {@code /admin-api/notifications/delivery-logs} 不一致，导致 500。
 * 这里以独立控制器重新挂载到正确路径。
 */
@RestController
@RequestMapping("/admin-api/notifications")
public class AdminNotificationLogController {
    private static final Logger log = LoggerFactory.getLogger(AdminNotificationLogController.class);

    private final JdbcTemplate jdbcTemplate;

    public AdminNotificationLogController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/delivery-logs")
    public Result<PageResult<Map<String, Object>>> adminDeliveryLogs(@RequestParam(defaultValue = "1") int current,
                                                                     @RequestParam(defaultValue = "20") int size,
                                                                     @RequestParam(required = false) String keyword,
                                                                     @RequestParam(required = false) String success,
                                                                     @RequestParam(required = false) String channelKey) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size, 200);
        int offset = (safeCurrent - 1) * safeSize;
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new ArrayList<>();
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (channel_name LIKE ? OR channel_key LIKE ? OR message LIKE ? OR CAST(user_id AS CHAR) LIKE ?)");
            String kw = "%" + keyword.trim() + "%";
            args.add(kw); args.add(kw); args.add(kw); args.add(kw);
        }
        if (channelKey != null && !channelKey.isBlank()) {
            where.append(" AND channel_key=?");
            args.add(channelKey.trim());
        }
        if (success != null && !success.isBlank()) {
            where.append(" AND success=?");
            args.add("1".equals(success) || "true".equalsIgnoreCase(success) ? 1 : 0);
        }
        try {
            Long total = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM notification_delivery_log" + where,
                    Long.class,
                    args.toArray());
            List<Object> pageArgs = new ArrayList<>(args);
            pageArgs.add(safeSize);
            pageArgs.add(offset);
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, tenant_id AS tenantId, user_id AS userId, channel_key AS channelKey, channel_name AS channelName, event_type AS eventType, success, status_code AS statusCode, cost_ms AS costMs, message, LEFT(request_body, 3000) AS requestBody, LEFT(response_body, 3000) AS responseBody, retry_count AS retryCount, created_time AS createdTime FROM notification_delivery_log" + where + " ORDER BY created_time DESC LIMIT ? OFFSET ?",
                    pageArgs.toArray());
            return Result.ok(new PageResult<>(rows, safeCurrent, safeSize, total == null ? 0 : total));
        } catch (Exception e) {
            log.error("查询后台通知发送记录失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "通知发送记录暂时无法加载，请稍后重试");
        }
    }
}
