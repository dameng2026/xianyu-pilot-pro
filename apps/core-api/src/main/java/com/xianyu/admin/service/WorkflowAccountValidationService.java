package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
public class WorkflowAccountValidationService {
    private static final String INVALID_REASON = "ACCOUNT_LOGIN_INVALID";

    private final XianyuAccountMapper accountMapper;
    private final XianyuAccountAuthStatusService accountAuthStatusService;

    public WorkflowAccountValidationService(XianyuAccountMapper accountMapper,
                                            XianyuAccountAuthStatusService accountAuthStatusService) {
        this.accountMapper = accountMapper;
        this.accountAuthStatusService = accountAuthStatusService;
    }

    public void assertExecutionAccountsReady(Long tenantId, List<Map<String, Object>> nodes, Map<String, Object> input) {
        List<Map<String, Object>> invalidAccounts = validateExecutionAccounts(tenantId, nodes, input);
        if (invalidAccounts.isEmpty()) {
            return;
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("ok", false);
        payload.put("reason", INVALID_REASON);
        payload.put("message", "运行前账号校验失败，请先重新登录以下账号");
        payload.put("invalidAccounts", invalidAccounts);
        throw new BizException(400, "运行前账号校验失败，请先重新登录以下账号", payload);
    }

    public List<Map<String, Object>> validateExecutionAccounts(Long tenantId, List<Map<String, Object>> nodes, Map<String, Object> input) {
        Set<Long> accountIds = resolveAccountIds(nodes, input);
        List<Map<String, Object>> invalidAccounts = new ArrayList<>();
        for (Long accountId : accountIds) {
            Map<String, Object> invalid = validateSingleAccount(tenantId, accountId);
            if (invalid != null) {
                invalidAccounts.add(invalid);
            }
        }
        return invalidAccounts;
    }

    private Map<String, Object> validateSingleAccount(Long tenantId, Long accountId) {
        XianyuAccount account = accountMapper.findById(tenantId, accountId);
        if (account == null) {
            // 账号已被删除：跳过校验，不阻塞工作流执行。
            // 前端账号选择 UI 只展示当前存在的账号，已删除账号的残留 ID 用户不可见也无法取消。
            // 这里报错会导致工作流无法运行，而用户根本无法在前端修复。
            // 已删除账号会在实际执行时被自然忽略（无法解析 Cookie）。
            return null;
        }
        String nickname = accountName(account);
        AccountAuthStatusResult result = accountAuthStatusService.check(tenantId, accountId, "workflow");
        if (!result.isUsable()) {
            return invalidAccount(accountId, result.getLoginStatusMessage(), nickname, result.getLoginStatusCode());
        }
        return null;
    }

    private Set<Long> resolveAccountIds(List<Map<String, Object>> nodes, Map<String, Object> input) {
        Set<Long> result = new LinkedHashSet<>();
        for (Map<String, Object> node : nodes) {
            if (node == null) {
                continue;
            }
            String type = text(node.get("type")).toUpperCase(Locale.ROOT);
            Map<String, Object> config = toMap(node.get("config"));
            if ("TRIGGER".equals(type)) {
                // 优先使用 selectedAccountIds 数组；仅当数组缺失/为空时才回退到遗留 selectedAccountId 单值
                // 避免老工作流残留的已删除账号 selectedAccountId 被重复校验
                boolean hasArray = hasAnyAccountId(config.get("selectedAccountIds"));
                addAccountIds(result, config.get("selectedAccountIds"));
                if (!hasArray) {
                    addAccountId(result, config.get("selectedAccountId"));
                }
            }
            if ("PUBLISH".equals(type)) {
                boolean hasArray = hasAnyAccountId(config.get("accountIds"));
                addAccountIds(result, config.get("accountIds"));
                if (!hasArray) {
                    addAccountId(result, config.get("accountId"));
                    addAccountId(result, config.get("selectedAccountId"));
                }
            }
        }
        Map<String, Object> safeInput = input == null ? Map.of() : input;
        addAccountIds(result, safeInput.get("selectedAccountIds"));
        addAccountIds(result, safeInput.get("accountIds"));
        // input 顶层的单值字段保留向后兼容（运行时 input 由前端构造，不会残留已删除账号）
        addAccountId(result, safeInput.get("selectedAccountId"));
        addAccountId(result, safeInput.get("accountId"));
        return result;
    }

    private boolean hasAnyAccountId(Object value) {
        if (value instanceof Collection<?> collection) {
            for (Object item : collection) {
                if (toLong(item) != null) {
                    return true;
                }
            }
        }
        return false;
    }

    private void addAccountIds(Set<Long> result, Object value) {
        if (value instanceof Collection<?> collection) {
            for (Object item : collection) {
                addAccountId(result, item);
            }
        }
    }

    private void addAccountId(Set<Long> result, Object value) {
        Long accountId = toLong(value);
        if (accountId != null && accountId > 0) {
            result.add(accountId);
        }
    }

    private Map<String, Object> toMap(Object value) {
        if (!(value instanceof Map<?, ?> raw)) {
            return Map.of();
        }
        Map<String, Object> map = new LinkedHashMap<>();
        raw.forEach((k, v) -> map.put(String.valueOf(k), v));
        return map;
    }

    private Map<String, Object> invalidAccount(Long accountId, String reason, String nickname, String code) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("accountId", accountId);
        row.put("nickname", isBlank(nickname) ? "账号#" + accountId : nickname);
        row.put("reason", reason);
        row.put("code", code);
        return row;
    }

    private String accountName(XianyuAccount account) {
        return firstNonBlank(account.getNickname(), account.getDisplayName(), account.getExternalUid());
    }

    private Long toLong(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.longValue();
        }
        String text = text(value);
        if (isBlank(text)) {
            return null;
        }
        try {
            return Long.parseLong(text);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (!isBlank(value)) {
                return value.trim();
            }
        }
        return null;
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
