package com.xianyu.admin.service;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.AdminCaptchaSolveRecordVO;
import com.xianyu.admin.dto.CaptchaSolveStatsVO;
import com.xianyu.admin.mapper.XianyuCaptchaSolveRecordMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 后台滑块求解记录查询服务（只读）。
 *
 * 职责：
 * 1. 提供 KPI / 趋势 / 账号分组 聚合查询
 * 2. 提供明细分页查询
 * 3. 解析 error_message 中的元数据（durationMs / screenshot）到独立字段
 *
 * 不修改任何求解记录，不影响前台自动化求解链路。
 */
@Service
public class AdminCaptchaSolveRecordService {
    private static final Logger log = LoggerFactory.getLogger(AdminCaptchaSolveRecordService.class);

    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final DateTimeFormatter DATETIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** error_message 元数据前缀正则，形如 [durationMs=12345, screenshot=/path/to/xxx.png] */
    private static final Pattern META_PATTERN = Pattern.compile("^\\[(.*?)\\]\\s*(.*)$", Pattern.DOTALL);
    private static final Pattern DURATION_PATTERN = Pattern.compile("durationMs=(\\d+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern SCREENSHOT_PATTERN = Pattern.compile("screenshot=([^\\s\\]]+)", Pattern.CASE_INSENSITIVE);

    private final XianyuCaptchaSolveRecordMapper recordMapper;

    public AdminCaptchaSolveRecordService(XianyuCaptchaSolveRecordMapper recordMapper) {
        this.recordMapper = recordMapper;
    }

    /**
     * 概览统计：KPI + 趋势 + 账号分组。
     *
     * @param days      时间范围（最近 N 天），<=0 或 null 表示全量
     * @param userId    用户 ID 过滤（与 accountId 互斥，accountId 优先）
     * @param accountId 账号 ID 过滤
     */
    public CaptchaSolveStatsVO stats(Integer days, Long userId, Long accountId) {
        LocalDateTime startTime = computeStartTime(days);

        CaptchaSolveStatsVO vo = new CaptchaSolveStatsVO();

        // KPI
        Map<String, Object> kpiRow = recordMapper.selectKpi(startTime, userId, accountId);
        CaptchaSolveStatsVO.Kpi kpi = new CaptchaSolveStatsVO.Kpi();
        long total = getLong(kpiRow, "total");
        long success = getLong(kpiRow, "success_count");
        long fail = getLong(kpiRow, "fail_count");
        kpi.setTotal(total);
        kpi.setSuccess(success);
        kpi.setFail(fail);
        kpi.setSuccessRate(total > 0 ? (double) success / total : 0.0);
        vo.setKpi(kpi);

        // 趋势
        List<Map<String, Object>> trendRows = recordMapper.selectTrend(startTime, userId, accountId);
        List<CaptchaSolveStatsVO.TrendPoint> trend = new ArrayList<>(trendRows.size());
        for (Map<String, Object> row : trendRows) {
            CaptchaSolveStatsVO.TrendPoint point = new CaptchaSolveStatsVO.TrendPoint();
            Object dateObj = row.get("date");
            String dateStr = dateObj != null ? String.valueOf(dateObj) : "";
            // MySQL DATE 类型可能返回 LocalDate 或 String，统一格式化为 yyyy-MM-dd
            if (dateObj instanceof LocalDate) {
                dateStr = ((LocalDate) dateObj).format(DATE_FORMATTER);
            } else if (dateStr.length() > 10) {
                dateStr = dateStr.substring(0, 10);
            }
            point.setDate(dateStr);
            long dayTotal = getLong(row, "total");
            long daySuccess = getLong(row, "success_count");
            point.setTotal(dayTotal);
            point.setSuccess(daySuccess);
            point.setFail(getLong(row, "fail_count"));
            point.setSuccessRate(dayTotal > 0 ? (double) daySuccess / dayTotal : 0.0);
            trend.add(point);
        }
        vo.setTrend(trend);

        // 账号分组
        List<Map<String, Object>> accountRows = recordMapper.selectAccountGroups(startTime, userId, accountId);
        List<CaptchaSolveStatsVO.AccountGroup> accounts = new ArrayList<>(accountRows.size());
        for (Map<String, Object> row : accountRows) {
            CaptchaSolveStatsVO.AccountGroup group = new CaptchaSolveStatsVO.AccountGroup();
            group.setAccountId(getLong(row, "account_id"));
            group.setAccountName(getString(row, "account_name"));
            long accTotal = getLong(row, "total");
            long accSuccess = getLong(row, "success_count");
            group.setTotal(accTotal);
            group.setSuccess(accSuccess);
            group.setFail(getLong(row, "fail_count"));
            group.setSuccessRate(accTotal > 0 ? (double) accSuccess / accTotal : 0.0);
            group.setLastSolveTime(formatDateTime(row.get("last_solve_time")));
            accounts.add(group);
        }
        vo.setAccounts(accounts);

        return vo;
    }

    /**
     * 分页查询明细。
     */
    public PageResult<AdminCaptchaSolveRecordVO> page(Long accountId, Long userId,
                                                       String status, String triggerScene, String accountName,
                                                       LocalDateTime startTime, LocalDateTime endTime,
                                                       int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;

        int total = recordMapper.selectCount(accountId, userId, status, triggerScene, accountName, startTime, endTime);
        List<Map<String, Object>> rows = recordMapper.selectList(accountId, userId, status, triggerScene, accountName,
                startTime, endTime, offset, safeSize);

        List<AdminCaptchaSolveRecordVO> records = new ArrayList<>(rows.size());
        for (Map<String, Object> row : rows) {
            records.add(mapRowToVO(row));
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    // ==================== 私有辅助方法 ====================

    private LocalDateTime computeStartTime(Integer days) {
        if (days == null || days <= 0) return null;
        return LocalDate.now().minusDays(days - 1L).atStartOfDay();
    }

    private AdminCaptchaSolveRecordVO mapRowToVO(Map<String, Object> row) {
        AdminCaptchaSolveRecordVO vo = new AdminCaptchaSolveRecordVO();
        vo.setId(getLong(row, "id"));
        vo.setTenantId(getLong(row, "tenant_id"));
        vo.setAccountId(getLong(row, "account_id"));
        vo.setAccountName(getString(row, "account_name"));
        vo.setEventDesc(getString(row, "event_desc"));
        vo.setOpenReason(getString(row, "open_reason"));
        vo.setSolveReason(getString(row, "solve_reason"));
        vo.setTriggerScene(getString(row, "trigger_scene"));
        vo.setResult(getString(row, "result"));
        vo.setStatus(getString(row, "status"));
        vo.setEngine(getString(row, "engine"));
        vo.setRetryCount(getInteger(row, "retry_count"));

        String rawErrorMessage = getString(row, "error_message");
        vo.setErrorMessage(rawErrorMessage);
        parseErrorMessageMeta(rawErrorMessage, vo);

        vo.setPriority(getInteger(row, "priority"));
        vo.setFailureReason(getString(row, "failure_reason"));
        vo.setQueuedAt(toLocalDateTime(row.get("queued_at")));
        vo.setStartedAt(toLocalDateTime(row.get("started_at")));
        vo.setFinishedAt(toLocalDateTime(row.get("finished_at")));

        Object createdAt = row.get("created_at");
        Object updatedAt = row.get("updated_at");
        vo.setCreatedAt(toLocalDateTime(createdAt));
        vo.setUpdatedAt(toLocalDateTime(updatedAt));
        return vo;
    }

    /**
     * 解析 error_message 元数据前缀 [durationMs=xxx, screenshot=/path] 后接错误描述。
     * 提取 durationMs / screenshotPath / errorMessageText 三个字段。
     */
    private void parseErrorMessageMeta(String raw, AdminCaptchaSolveRecordVO vo) {
        if (raw == null || raw.isEmpty()) {
            vo.setErrorMessageText("");
            return;
        }
        Matcher metaMatcher = META_PATTERN.matcher(raw);
        String metaContent = null;
        String textPart = raw;
        if (metaMatcher.find()) {
            metaContent = metaMatcher.group(1);
            textPart = metaMatcher.group(2);
        }
        if (metaContent != null) {
            Matcher durationMatcher = DURATION_PATTERN.matcher(metaContent);
            if (durationMatcher.find()) {
                try {
                    vo.setDurationMs(Long.parseLong(durationMatcher.group(1)));
                } catch (NumberFormatException ignored) {
                }
            }
            Matcher screenshotMatcher = SCREENSHOT_PATTERN.matcher(metaContent);
            if (screenshotMatcher.find()) {
                vo.setScreenshotPath(screenshotMatcher.group(1));
            }
        }
        vo.setErrorMessageText(textPart != null ? textPart.trim() : "");
    }

    private LocalDateTime toLocalDateTime(Object val) {
        if (val == null) return null;
        if (val instanceof LocalDateTime) return (LocalDateTime) val;
        if (val instanceof java.sql.Timestamp) return ((java.sql.Timestamp) val).toLocalDateTime();
        if (val instanceof java.util.Date) return new java.util.Date(((java.util.Date) val).getTime())
                .toInstant().atZone(java.time.ZoneId.systemDefault()).toLocalDateTime();
        return null;
    }

    private String formatDateTime(Object val) {
        LocalDateTime ldt = toLocalDateTime(val);
        if (ldt == null) return null;
        return ldt.format(DATETIME_FORMATTER);
    }

    private long getLong(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return 0L;
        if (val instanceof Number) return ((Number) val).longValue();
        try { return Long.parseLong(String.valueOf(val)); } catch (Exception e) { return 0L; }
    }

    private Integer getInteger(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Integer) return (Integer) val;
        if (val instanceof Number) return ((Number) val).intValue();
        try { return Integer.parseInt(String.valueOf(val)); } catch (Exception e) { return null; }
    }

    private String getString(Map<String, Object> map, String key) {
        Object val = map.get(key);
        return val != null ? String.valueOf(val) : null;
    }
}
