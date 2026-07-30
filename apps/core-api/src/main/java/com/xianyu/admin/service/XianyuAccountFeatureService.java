package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class XianyuAccountFeatureService {
    private static final Logger log = LoggerFactory.getLogger(XianyuAccountFeatureService.class);
    private static final String FACE_VERIFICATION_EVENT = "人脸验证";
    private static final int DEFAULT_MESSAGE_EXPIRE_TIME = 3600;
    private static final int MAX_MESSAGE_EXPIRE_TIME = 86400;

    private final JdbcTemplate jdbcTemplate;
    private final XianyuAccountMapper accountMapper;

    public XianyuAccountFeatureService(JdbcTemplate jdbcTemplate, XianyuAccountMapper accountMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.accountMapper = accountMapper;
    }

    public Map<String, Object> getAutoRateConfig(Long tenantId, Long accountId) {
        requireAccountExists(tenantId, accountId);
        try {
            Map<String, Object> result = defaultAutoRateConfig(accountId);
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT enabled, rate_type AS rateType, text_content AS textContent, api_url AS apiUrl, schedule_hour AS scheduleHour, updated_time AS updatedTime " +
                            "FROM xianyu_account_auto_rate_config WHERE tenant_id=? AND account_id=? AND deleted=0 LIMIT 1",
                    tenantId,
                    accountId
            );
            if (rows.isEmpty()) {
                return result;
            }

            Map<String, Object> row = rows.get(0);
            result.put("enabled", asEnabledFlag(row.get("enabled")) == 1);
            result.put("rateType", normalizeRateType(row.get("rateType")));
            result.put("textContent", trimToEmpty(row.get("textContent")));
            result.put("apiUrl", trimToEmpty(row.get("apiUrl")));
            result.put("scheduleHour", normalizeScheduleHour(row.get("scheduleHour")));
            result.put("updatedTime", row.get("updatedTime"));
            return result;
        } catch (Exception e) {
            throw unavailable("自动评价配置", e);
        }
    }

    public Map<String, Object> saveAutoRateConfig(Long tenantId, Long userId, Long accountId, Map<String, Object> body) {
        requireAccountExists(tenantId, accountId);

        int enabled = asEnabledFlag(body == null ? null : body.get("enabled"));
        String rateType = normalizeRateType(body == null ? null : body.get("rateType"));
        String textContent = trimToEmpty(body == null ? null : body.get("textContent"));
        String apiUrl = trimToEmpty(body == null ? null : body.get("apiUrl"));
        int scheduleHour = normalizeScheduleHour(body == null ? null : body.get("scheduleHour"));

        try {
            jdbcTemplate.update(
                    "INSERT INTO xianyu_account_auto_rate_config(tenant_id, user_id, account_id, enabled, rate_type, text_content, api_url, schedule_hour, created_time, updated_time, deleted) " +
                            "VALUES(?,?,?,?,?,?,?,?,NOW(),NOW(),0) " +
                            "ON DUPLICATE KEY UPDATE user_id=VALUES(user_id), enabled=VALUES(enabled), rate_type=VALUES(rate_type), text_content=VALUES(text_content), api_url=VALUES(api_url), schedule_hour=VALUES(schedule_hour), updated_time=NOW(), deleted=0",
                    tenantId,
                    userId,
                    accountId,
                    enabled,
                    rateType,
                    textContent,
                    apiUrl,
                    scheduleHour
            );

            Map<String, Object> result = defaultAutoRateConfig(accountId);
            result.put("enabled", enabled == 1);
            result.put("rateType", rateType);
            result.put("textContent", textContent);
            result.put("apiUrl", apiUrl);
            result.put("scheduleHour", scheduleHour);
            result.put("updatedTime", LocalDateTime.now());
            return result;
        } catch (Exception e) {
            throw unavailable("保存自动评价配置", e);
        }
    }

    public Map<String, Object> getStrategyConfig(Long tenantId, Long accountId) {
        XianyuAccount account = requireAccountExists(tenantId, accountId);
        return defaultStrategyConfig(account);
    }

    @Transactional
    public Map<String, Object> saveStrategyConfig(Long tenantId, Long accountId, Map<String, Object> body) {
        try {
            requireAccountExists(tenantId, accountId);

            int messageExpireTime = normalizeMessageExpireTime(body == null ? null : body.get("messageExpireTime"));
            int scheduledRedelivery = asEnabledFlag(body == null ? null : body.get("scheduledRedelivery"));
            int autoPolish = asEnabledFlag(body == null ? null : body.get("autoPolish"));

            jdbcTemplate.update(
                    "UPDATE xianyu_account SET message_expire_time=?, scheduled_redelivery=?, auto_polish=?, updated_time=NOW() " +
                            "WHERE tenant_id=? AND id=? AND deleted=0",
                    messageExpireTime,
                    scheduledRedelivery,
                    autoPolish,
                    tenantId,
                    accountId
            );
            syncStrategyTask(tenantId, accountId, "redelivery", "账号定时补发货", "0 0/30 * * * ?", 30, scheduledRedelivery == 1);
            syncStrategyTask(tenantId, accountId, "polish_goods", "账号商品擦亮", "0 0 9 * * ?", 1440, autoPolish == 1);

            XianyuAccount refreshed = requireAccountExists(tenantId, accountId);
            refreshed.setMessageExpireTime(messageExpireTime);
            refreshed.setScheduledRedelivery(scheduledRedelivery == 1);
            refreshed.setAutoPolish(autoPolish == 1);
            return defaultStrategyConfig(refreshed);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("账号策略配置", e);
        }
    }

    public PageResult<Map<String, Object>> pageFaceVerifications(Long tenantId, Long userId, Long accountId, int current, int size) {
        if (accountId != null) {
            requireAccountExists(tenantId, accountId);
        }

        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;

        String countSql = "SELECT COUNT(*) FROM notification WHERE tenant_id=? AND deleted=0 " +
                "AND (user_id=? OR user_id IS NULL) " +
                "AND (notice_type='" + FACE_VERIFICATION_EVENT + "' OR notification_type='" + FACE_VERIFICATION_EVENT + "')";
        String listSql = "SELECT id, account_id AS accountId, title, content, level, priority, is_read AS readFlag, created_time AS createdTime " +
                "FROM notification WHERE tenant_id=? AND deleted=0 " +
                "AND (user_id=? OR user_id IS NULL) " +
                "AND (notice_type='" + FACE_VERIFICATION_EVENT + "' OR notification_type='" + FACE_VERIFICATION_EVENT + "')";

        try {
            Long total;
            List<Map<String, Object>> rows;
            if (accountId == null) {
                total = jdbcTemplate.queryForObject(countSql, Long.class, tenantId, userId);
                rows = jdbcTemplate.queryForList(
                        listSql + " ORDER BY is_read ASC, created_time DESC LIMIT ?, ?",
                        tenantId,
                        userId,
                        offset,
                        safeSize
                );
            } else {
                total = jdbcTemplate.queryForObject(countSql + " AND account_id=?", Long.class, tenantId, userId, accountId);
                rows = jdbcTemplate.queryForList(
                        listSql + " AND account_id=? ORDER BY is_read ASC, created_time DESC LIMIT ?, ?",
                        tenantId,
                        userId,
                        accountId,
                        offset,
                        safeSize
                );
            }

            List<Map<String, Object>> records = new ArrayList<>();
            for (Map<String, Object> row : rows) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("id", row.get("id"));
                item.put("accountId", row.get("accountId"));
                item.put("type", FACE_VERIFICATION_EVENT);
                item.put("title", row.get("title"));
                item.put("content", row.get("content"));
                item.put("level", row.get("level"));
                item.put("priority", row.get("priority"));
                item.put("readFlag", asEnabledFlag(row.get("readFlag")));
                item.put("createdTime", row.get("createdTime"));
                records.add(item);
            }
            return new PageResult<>(records, safeCurrent, safeSize, total == null ? 0 : total);
        } catch (Exception e) {
            throw unavailable("人脸验证记录", e);
        }
    }

    public void markFaceVerificationRead(Long tenantId, Long userId, Long notificationId) {
        if (tenantId == null || userId == null) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
        if (notificationId == null || notificationId <= 0) {
            throw new BizException(400, "通知 ID 非法");
        }
        try {
            int affected = jdbcTemplate.update(
                    "UPDATE notification SET is_read=1, read_time=NOW(), updated_time=NOW() " +
                            "WHERE tenant_id=? AND user_id=? AND id=? AND deleted=0 " +
                            "AND (notice_type=? OR notification_type=?)",
                    tenantId, userId, notificationId, FACE_VERIFICATION_EVENT, FACE_VERIFICATION_EVENT
            );
            if (affected != 1) {
                throw new BizException(404, "人脸验证通知不存在或无权操作");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw unavailable("人脸验证状态更新", e);
        }
    }

    private XianyuAccount requireAccountExists(Long tenantId, Long accountId) {
        XianyuAccount account;
        try {
            account = accountMapper.findById(tenantId, accountId);
        } catch (Exception e) {
            throw unavailable("闲鱼账号数据", e);
        }
        if (account == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }
        return account;
    }

    private Map<String, Object> defaultAutoRateConfig(Long accountId) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("accountId", accountId);
        result.put("enabled", false);
        result.put("rateType", "text");
        result.put("textContent", "");
        result.put("apiUrl", "");
        result.put("scheduleHour", 9);
        result.put("updatedTime", null);
        return result;
    }

    private Map<String, Object> defaultStrategyConfig(XianyuAccount account) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("accountId", account.getId());
        result.put("messageExpireTime", normalizeMessageExpireTime(account.getMessageExpireTime()));
        result.put("scheduledRedelivery", Boolean.TRUE.equals(account.getScheduledRedelivery()));
        result.put("autoPolish", Boolean.TRUE.equals(account.getAutoPolish()));
        return result;
    }

    private void syncStrategyTask(Long tenantId,
                                  Long accountId,
                                  String taskType,
                                  String taskName,
                                  String cronExpression,
                                  int intervalMinutes,
                                  boolean enabled) {
        String configJson = "{\"intervalMinutes\":" + intervalMinutes + "}";
        int enabledFlag = enabled ? 1 : 0;
        int updated = jdbcTemplate.update(
                "UPDATE scheduled_task SET task_name=?, cron_expression=?, config_json=?, enabled=?, " +
                        "next_run_time=CASE " +
                        "WHEN ?=1 AND enabled=0 THEN NOW() " +
                        "WHEN ?=1 THEN COALESCE(next_run_time, NOW()) " +
                        "ELSE next_run_time END, " +
                        "updated_time=NOW() " +
                        "WHERE tenant_id=? AND account_id=? AND task_type=? AND deleted=0",
                taskName,
                cronExpression,
                configJson,
                enabledFlag,
                enabledFlag,
                enabledFlag,
                tenantId,
                accountId,
                taskType
        );
        if (updated == 0 && enabled) {
            jdbcTemplate.update(
                    "INSERT INTO scheduled_task(tenant_id, account_id, task_type, task_name, cron_expression, config_json, enabled, next_run_time, created_time, updated_time, deleted) " +
                            "VALUES(?,?,?,?,?,?,?,NOW(),NOW(),NOW(),0)",
                    tenantId,
                    accountId,
                    taskType,
                    taskName,
                    cronExpression,
                    configJson,
                    1
            );
        }
    }

    private int asEnabledFlag(Object value) {
        if (value == null) return 0;
        if (value instanceof Boolean bool) return bool ? 1 : 0;
        if (value instanceof Number number) return number.intValue() == 0 ? 0 : 1;
        String text = String.valueOf(value).trim();
        if (text.isEmpty()) return 0;
        return ("1".equals(text) || "true".equalsIgnoreCase(text) || "yes".equalsIgnoreCase(text)) ? 1 : 0;
    }

    private String normalizeRateType(Object value) {
        String text = trimToEmpty(value).toLowerCase();
        return "api".equals(text) ? "api" : "text";
    }

    private int normalizeScheduleHour(Object value) {
        if (value == null) {
            return 9;
        }
        try {
            int parsed;
            if (value instanceof Number number) {
                parsed = number.intValue();
            } else {
                String text = String.valueOf(value).trim();
                if (text.isEmpty()) {
                    return 9;
                }
                parsed = Integer.parseInt(text);
            }
            if (parsed < 0 || parsed > 23) {
                return 9;
            }
            return parsed;
        } catch (NumberFormatException ignore) {
            return 9;
        }
    }

    private int normalizeMessageExpireTime(Object value) {
        if (value == null) {
            return DEFAULT_MESSAGE_EXPIRE_TIME;
        }
        String text = trimToEmpty(value);
        if (text.isEmpty()) {
            return DEFAULT_MESSAGE_EXPIRE_TIME;
        }
        try {
            int parsed = Integer.parseInt(text);
            if (parsed < 0) {
                return 0;
            }
            return Math.min(parsed, MAX_MESSAGE_EXPIRE_TIME);
        } catch (NumberFormatException ignore) {
            return DEFAULT_MESSAGE_EXPIRE_TIME;
        }
    }

    private BizException unavailable(String operation, Exception cause) {
        if (cause instanceof BizException bizException) {
            return bizException;
        }
        log.error("{}不可用, errorType={}", operation, cause.getClass().getSimpleName());
        return new BizException(503, operation + "暂时不可用，请稍后重试");
    }

    private String trimToEmpty(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }
}
