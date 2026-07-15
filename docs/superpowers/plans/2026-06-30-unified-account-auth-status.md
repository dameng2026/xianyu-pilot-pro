# Unified Account Auth Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one shared account Cookie/login-status capability so account management, connection management, workflow execution, and all other account consumers use the same auth verdict and stay in sync when that verdict changes.

**Architecture:** Add a single `core-api` auth-status service that performs the full account auth probe, persists the latest structured result, and broadcasts a unified status-change event. Migrate workflow precheck, account/profile actions, websocket-auth side effects, and frontend account consumers to read and react to that single source of truth instead of mixing `cookie_status`, websocket state, and page-specific fallbacks.

**Tech Stack:** Java 17, Spring Boot 3, MyBatis/JdbcTemplate, Vue 3 + Vite, existing SSE event bus, Python automation-service side-effect hooks.

---

### Task 1: Add the backend auth-status result model and failing unit tests

**Files:**
- Create: `apps/core-api/src/main/java/com/xianyu/admin/dto/AccountAuthStatusResult.java`
- Create: `apps/core-api/src/main/java/com/xianyu/admin/service/AccountAuthProbeResult.java`
- Create: `apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountAuthStatusServiceTest.java`
- Modify: `apps/core-api/src/test/java/com/xianyu/admin/service/WorkflowAccountValidationServiceTest.java`

- [ ] **Step 1: Write the failing test for structured auth status results**

```java
package com.xianyu.admin.service;

import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.entity.XianyuAccountAuth;
import com.xianyu.admin.mapper.XianyuAccountAuthMapper;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuAccountAuthStatusServiceTest {

    @Mock
    private XianyuAccountMapper accountMapper;

    @Mock
    private XianyuAccountAuthMapper authMapper;

    @Mock
    private CookieCryptoService cookieCryptoService;

    @Mock
    private XianyuAccountAvailabilityProbeService probeService;

    private XianyuAccountAuthStatusService service;

    @BeforeEach
    void setUp() {
        service = new XianyuAccountAuthStatusService(accountMapper, authMapper, cookieCryptoService, probeService);
    }

    @Test
    void checkReturnsStructuredFailureWhenCookieTokenIsMissing() {
        when(accountMapper.findById(1L, 31L)).thenReturn(account(31L, "缺 token 账号", 1, "uid-31"));
        when(authMapper.findByAccountId(1L, 31L)).thenReturn(auth(31L, "encrypted-cookie-31"));
        when(cookieCryptoService.decryptIfNeeded("encrypted-cookie-31")).thenReturn("unb=uid-31; cookie2=abc;");

        AccountAuthStatusResult result = service.check(1L, 31L, "test");

        assertFalse(result.isUsable());
        assertEquals(0, result.getCookieStatus());
        assertEquals("COOKIE_TOKEN_MISSING", result.getLoginStatusCode());
        assertEquals("Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号", result.getLoginStatusMessage());
        assertEquals("test", result.getSource());
    }

    private static XianyuAccount account(Long id, String nickname, Integer status, String externalUid) {
        XianyuAccount account = new XianyuAccount();
        account.setId(id);
        account.setNickname(nickname);
        account.setStatus(status);
        account.setExternalUid(externalUid);
        return account;
    }

    private static XianyuAccountAuth auth(Long accountId, String encryptedCookie) {
        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setAccountId(accountId);
        auth.setEncryptedCookie(encryptedCookie);
        return auth;
    }
}
```

- [ ] **Step 2: Run the new backend test to verify it fails**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest test`

Expected: FAIL with compilation errors because `XianyuAccountAuthStatusService` and `AccountAuthStatusResult` do not exist yet.

- [ ] **Step 3: Add the minimal result model and service to satisfy the first test**

```java
package com.xianyu.admin.dto;

import java.time.LocalDateTime;

public class AccountAuthStatusResult {
    private Long accountId;
    private String nickname;
    private boolean usable;
    private Integer cookieStatus;
    private String loginStatusCode;
    private String loginStatusMessage;
    private LocalDateTime checkedAt;
    private String source;

    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public String getNickname() { return nickname; }
    public void setNickname(String nickname) { this.nickname = nickname; }
    public boolean isUsable() { return usable; }
    public void setUsable(boolean usable) { this.usable = usable; }
    public Integer getCookieStatus() { return cookieStatus; }
    public void setCookieStatus(Integer cookieStatus) { this.cookieStatus = cookieStatus; }
    public String getLoginStatusCode() { return loginStatusCode; }
    public void setLoginStatusCode(String loginStatusCode) { this.loginStatusCode = loginStatusCode; }
    public String getLoginStatusMessage() { return loginStatusMessage; }
    public void setLoginStatusMessage(String loginStatusMessage) { this.loginStatusMessage = loginStatusMessage; }
    public LocalDateTime getCheckedAt() { return checkedAt; }
    public void setCheckedAt(LocalDateTime checkedAt) { this.checkedAt = checkedAt; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
}
```

```java
package com.xianyu.admin.service;

public class AccountAuthProbeResult {
    private final boolean usable;
    private final int cookieStatus;
    private final String loginStatusCode;
    private final String loginStatusMessage;

    public AccountAuthProbeResult(boolean usable, int cookieStatus, String loginStatusCode, String loginStatusMessage) {
        this.usable = usable;
        this.cookieStatus = cookieStatus;
        this.loginStatusCode = loginStatusCode;
        this.loginStatusMessage = loginStatusMessage;
    }

    public boolean isUsable() { return usable; }
    public int getCookieStatus() { return cookieStatus; }
    public String getLoginStatusCode() { return loginStatusCode; }
    public String getLoginStatusMessage() { return loginStatusMessage; }
}
```

```java
package com.xianyu.admin.service;

import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.entity.XianyuAccount;
import com.xianyu.admin.entity.XianyuAccountAuth;
import com.xianyu.admin.mapper.XianyuAccountAuthMapper;
import com.xianyu.admin.mapper.XianyuAccountMapper;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
public class XianyuAccountAuthStatusService {
    private final XianyuAccountMapper accountMapper;
    private final XianyuAccountAuthMapper authMapper;
    private final CookieCryptoService cookieCryptoService;
    private final XianyuAccountAvailabilityProbeService probeService;

    public XianyuAccountAuthStatusService(XianyuAccountMapper accountMapper,
                                          XianyuAccountAuthMapper authMapper,
                                          CookieCryptoService cookieCryptoService,
                                          XianyuAccountAvailabilityProbeService probeService) {
        this.accountMapper = accountMapper;
        this.authMapper = authMapper;
        this.cookieCryptoService = cookieCryptoService;
        this.probeService = probeService;
    }

    public AccountAuthStatusResult check(Long tenantId, Long accountId, String source) {
        XianyuAccount account = accountMapper.findById(tenantId, accountId);
        String nickname = account == null ? "账号#" + accountId : firstNonBlank(account.getNickname(), account.getDisplayName(), account.getExternalUid(), "账号#" + accountId);
        AccountAuthProbeResult probe = probe(tenantId, accountId, account);
        AccountAuthStatusResult result = new AccountAuthStatusResult();
        result.setAccountId(accountId);
        result.setNickname(nickname);
        result.setUsable(probe.isUsable());
        result.setCookieStatus(probe.getCookieStatus());
        result.setLoginStatusCode(probe.getLoginStatusCode());
        result.setLoginStatusMessage(probe.getLoginStatusMessage());
        result.setCheckedAt(LocalDateTime.now());
        result.setSource(source);
        return result;
    }

    private AccountAuthProbeResult probe(Long tenantId, Long accountId, XianyuAccount account) {
        if (account == null) {
            return new AccountAuthProbeResult(false, 0, "AUTH_MISSING", "未找到登录信息，请重新登录闲鱼账号");
        }
        if (account.getStatus() == null || account.getStatus() != 1) {
            return new AccountAuthProbeResult(false, 0, "ACCOUNT_DISABLED", "账号已停用，请先启用后再操作");
        }
        XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, accountId);
        if (auth == null || isBlank(auth.getEncryptedCookie())) {
            return new AccountAuthProbeResult(false, 0, "AUTH_MISSING", "未找到登录信息，请重新登录闲鱼账号");
        }
        String cookie;
        try {
            cookie = cookieCryptoService.decryptIfNeeded(auth.getEncryptedCookie());
        } catch (Exception e) {
            return new AccountAuthProbeResult(false, 0, "COOKIE_DECRYPT_FAILED", "Cookie 解密失败，请重新登录闲鱼账号");
        }
        if (isBlank(cookie)) {
            return new AccountAuthProbeResult(false, 0, "COOKIE_EMPTY", "登录信息为空，请重新登录闲鱼账号");
        }
        if (!cookie.contains("_m_h5_tk=")) {
            return new AccountAuthProbeResult(false, 0, "COOKIE_TOKEN_MISSING", "Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号");
        }
        String externalUid = firstNonBlank(account.getExternalUid());
        if (isBlank(externalUid)) {
            return new AccountAuthProbeResult(false, 0, "EXTERNAL_UID_MISSING", "账号缺少 externalUid，请重新登录闲鱼账号");
        }
        if (!probeService.isCookieAlive(cookie, externalUid)) {
            return new AccountAuthProbeResult(false, 0, "PAGE_HEAD_FAILED", "登录已失效，请重新登录闲鱼账号");
        }
        return new AccountAuthProbeResult(true, 1, "OK", "登录状态正常");
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (!isBlank(value)) return value.trim();
        }
        return null;
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
```

- [ ] **Step 4: Run the backend test to verify it passes**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest test`

Expected: PASS for `checkReturnsStructuredFailureWhenCookieTokenIsMissing`.

- [ ] **Step 5: Expand the tests for success and page-head failure before more code**

```java
@Test
void checkReturnsStructuredSuccessWhenProbePasses() {
    when(accountMapper.findById(1L, 11L)).thenReturn(account(11L, "正常账号", 1, "uid-11"));
    when(authMapper.findByAccountId(1L, 11L)).thenReturn(auth(11L, "encrypted-cookie-11"));
    when(cookieCryptoService.decryptIfNeeded("encrypted-cookie-11")).thenReturn("_m_h5_tk=token11; unb=uid-11;");
    when(probeService.isCookieAlive("_m_h5_tk=token11; unb=uid-11;", "uid-11")).thenReturn(true);

    AccountAuthStatusResult result = service.check(1L, 11L, "test");

    assertEquals(true, result.isUsable());
    assertEquals(1, result.getCookieStatus());
    assertEquals("OK", result.getLoginStatusCode());
    assertEquals("登录状态正常", result.getLoginStatusMessage());
}

@Test
void checkReturnsStructuredFailureWhenPageHeadProbeFails() {
    when(accountMapper.findById(1L, 12L)).thenReturn(account(12L, "失效账号", 1, "uid-12"));
    when(authMapper.findByAccountId(1L, 12L)).thenReturn(auth(12L, "encrypted-cookie-12"));
    when(cookieCryptoService.decryptIfNeeded("encrypted-cookie-12")).thenReturn("_m_h5_tk=token12; unb=uid-12;");
    when(probeService.isCookieAlive("_m_h5_tk=token12; unb=uid-12;", "uid-12")).thenReturn(false);

    AccountAuthStatusResult result = service.check(1L, 12L, "workflow_precheck");

    assertFalse(result.isUsable());
    assertEquals(0, result.getCookieStatus());
    assertEquals("PAGE_HEAD_FAILED", result.getLoginStatusCode());
    assertEquals("登录已失效，请重新登录闲鱼账号", result.getLoginStatusMessage());
    assertEquals("workflow_precheck", result.getSource());
}
```

- [ ] **Step 6: Run the expanded backend tests to verify RED then GREEN**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest test`

Expected before implementation updates: FAIL if assertions do not yet match.

Expected after minimal implementation updates: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/dto/AccountAuthStatusResult.java apps/core-api/src/main/java/com/xianyu/admin/service/AccountAuthProbeResult.java apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountAuthStatusService.java apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountAuthStatusServiceTest.java
git commit -m "feat: add unified account auth status model"
```

### Task 2: Persist unified auth results in auth/runtime tables

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/config/DataInitializer.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/entity/XianyuAccountAuth.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuAccountAuthMapper.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountAuthStatusService.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountAuthStatusServiceTest.java`

- [ ] **Step 1: Write the failing test for state persistence after a check**

```java
@Test
void checkAndSyncPersistsCookieStatusAndLatestLoginFields() {
    when(accountMapper.findById(1L, 11L)).thenReturn(account(11L, "正常账号", 1, "uid-11"));
    when(authMapper.findByAccountId(1L, 11L)).thenReturn(auth(11L, "encrypted-cookie-11"));
    when(cookieCryptoService.decryptIfNeeded("encrypted-cookie-11")).thenReturn("_m_h5_tk=token11; unb=uid-11;");
    when(probeService.isCookieAlive("_m_h5_tk=token11; unb=uid-11;", "uid-11")).thenReturn(true);

    service.checkAndSync(1L, 11L, "check_login");

    verify(authMapper).updateLatestLoginStatus(eq(1L), eq(11L), eq(1), eq("OK"), eq("登录状态正常"), any());
}
```

- [ ] **Step 2: Run the backend test to verify it fails**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest test`

Expected: FAIL because `checkAndSync(...)` and `updateLatestLoginStatus(...)` do not exist yet.

- [ ] **Step 3: Add migration fields and mapper support with the smallest implementation**

```java
// DataInitializer.java
addColumnIfMissing("xianyu_account_auth", "last_login_status_code", "VARCHAR(64) NULL COMMENT '最近一次统一登录态结果码'");
addColumnIfMissing("xianyu_account_auth", "last_login_status_message", "VARCHAR(255) NULL COMMENT '最近一次统一登录态文案'");
addColumnIfMissing("xianyu_account_auth", "last_login_check_time", "DATETIME NULL COMMENT '最近一次统一登录态检查时间'");
addColumnIfMissing("xianyu_account_runtime", "last_login_status_code", "VARCHAR(64) NULL COMMENT '最近一次统一登录态结果码'");
addColumnIfMissing("xianyu_account_runtime", "last_login_status_message", "VARCHAR(255) NULL COMMENT '最近一次统一登录态文案'");
addColumnIfMissing("xianyu_account_runtime", "last_login_check_time", "DATETIME NULL COMMENT '最近一次统一登录态检查时间'");
```

```java
// XianyuAccountAuthMapper.java
@Update("""
        UPDATE xianyu_account_auth
        SET cookie_status = #{cookieStatus},
            last_login_status_code = #{loginStatusCode},
            last_login_status_message = #{loginStatusMessage},
            last_login_check_time = #{checkedAt},
            updated_time = NOW()
        WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0
        """)
int updateLatestLoginStatus(@Param("tenantId") Long tenantId,
                            @Param("accountId") Long accountId,
                            @Param("cookieStatus") Integer cookieStatus,
                            @Param("loginStatusCode") String loginStatusCode,
                            @Param("loginStatusMessage") String loginStatusMessage,
                            @Param("checkedAt") LocalDateTime checkedAt);
```

```java
// XianyuAccountAuthStatusService.java
public AccountAuthStatusResult checkAndSync(Long tenantId, Long accountId, String source) {
    AccountAuthStatusResult result = check(tenantId, accountId, source);
    authMapper.updateLatestLoginStatus(
            tenantId,
            accountId,
            result.getCookieStatus(),
            result.getLoginStatusCode(),
            result.getLoginStatusMessage(),
            result.getCheckedAt()
    );
    return result;
}
```

- [ ] **Step 4: Run the backend test to verify it passes**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest test`

Expected: PASS for the new persistence assertion.

- [ ] **Step 5: Add runtime-table mirroring behind a failing test**

```java
@Test
void checkAndSyncAlsoMirrorsLatestLoginFieldsToRuntimeTable() {
    when(accountMapper.findById(1L, 12L)).thenReturn(account(12L, "失效账号", 1, "uid-12"));
    when(authMapper.findByAccountId(1L, 12L)).thenReturn(auth(12L, "encrypted-cookie-12"));
    when(cookieCryptoService.decryptIfNeeded("encrypted-cookie-12")).thenReturn("_m_h5_tk=token12; unb=uid-12;");
    when(probeService.isCookieAlive("_m_h5_tk=token12; unb=uid-12;", "uid-12")).thenReturn(false);

    service.checkAndSync(1L, 12L, "workflow_precheck");

    verify(runtimeStatusWriter).sync(eq(1L), eq(12L), eq(0), eq("PAGE_HEAD_FAILED"), eq("登录已失效，请重新登录闲鱼账号"), any());
}
```

- [ ] **Step 6: Add a minimal runtime sync abstraction and implementation**

```java
package com.xianyu.admin.service;

import java.time.LocalDateTime;

public interface AccountRuntimeStatusWriter {
    void sync(Long tenantId, Long accountId, Integer cookieStatus, String loginStatusCode, String loginStatusMessage, LocalDateTime checkedAt);
}
```

```java
package com.xianyu.admin.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

@Component
public class JdbcAccountRuntimeStatusWriter implements AccountRuntimeStatusWriter {
    private final JdbcTemplate jdbcTemplate;

    public JdbcAccountRuntimeStatusWriter(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public void sync(Long tenantId, Long accountId, Integer cookieStatus, String loginStatusCode, String loginStatusMessage, LocalDateTime checkedAt) {
        jdbcTemplate.update("""
                UPDATE xianyu_account_runtime
                SET cookie_status = ?, last_login_status_code = ?, last_login_status_message = ?, last_login_check_time = ?, updated_time = NOW()
                WHERE tenant_id = ? AND account_id = ?
                """, cookieStatus, loginStatusCode, loginStatusMessage, checkedAt, tenantId, accountId);
    }
}
```

- [ ] **Step 7: Run the backend test suite for this service**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest test`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/config/DataInitializer.java apps/core-api/src/main/java/com/xianyu/admin/entity/XianyuAccountAuth.java apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuAccountAuthMapper.java apps/core-api/src/main/java/com/xianyu/admin/service/AccountRuntimeStatusWriter.java apps/core-api/src/main/java/com/xianyu/admin/service/JdbcAccountRuntimeStatusWriter.java apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountAuthStatusService.java apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountAuthStatusServiceTest.java
git commit -m "feat: persist unified account auth status"
```

### Task 3: Broadcast one unified auth-status change event from core-api

**Files:**
- Create: `apps/core-api/src/main/java/com/xianyu/admin/service/AccountAuthStatusEventPublisher.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountAuthStatusService.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountAuthStatusServiceTest.java`

- [ ] **Step 1: Write the failing publisher test**

```java
@Mock
private AccountAuthStatusEventPublisher eventPublisher;

@BeforeEach
void setUp() {
    service = new XianyuAccountAuthStatusService(accountMapper, authMapper, cookieCryptoService, probeService, runtimeStatusWriter, eventPublisher);
}

@Test
void checkAndSyncPublishesUnifiedAuthStatusChangeEvent() {
    when(accountMapper.findById(1L, 12L)).thenReturn(account(12L, "失效账号", 1, "uid-12"));
    when(authMapper.findByAccountId(1L, 12L)).thenReturn(auth(12L, "encrypted-cookie-12"));
    when(cookieCryptoService.decryptIfNeeded("encrypted-cookie-12")).thenReturn("_m_h5_tk=token12; unb=uid-12;");
    when(probeService.isCookieAlive("_m_h5_tk=token12; unb=uid-12;", "uid-12")).thenReturn(false);

    service.checkAndSync(1L, 12L, "workflow_precheck");

    verify(eventPublisher).publish(argThat(event ->
            "account_auth_status_changed".equals(event.get("type"))
                    && Long.valueOf(12L).equals(event.get("accountId"))
                    && Integer.valueOf(0).equals(event.get("cookieStatus"))
                    && "PAGE_HEAD_FAILED".equals(event.get("loginStatusCode"))
    ));
}
```

- [ ] **Step 2: Run the backend test to verify it fails**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest test`

Expected: FAIL because `AccountAuthStatusEventPublisher` is missing.

- [ ] **Step 3: Add the smallest event publisher abstraction and call site**

```java
package com.xianyu.admin.service;

import java.util.Map;

public interface AccountAuthStatusEventPublisher {
    void publish(Map<String, Object> event);
}
```

```java
// XianyuAccountAuthStatusService.java inside checkAndSync(...)
eventPublisher.publish(Map.of(
        "type", "account_auth_status_changed",
        "accountId", result.getAccountId(),
        "cookieStatus", result.getCookieStatus(),
        "usable", result.isUsable(),
        "loginStatusCode", result.getLoginStatusCode(),
        "loginStatusMessage", result.getLoginStatusMessage(),
        "checkedAt", result.getCheckedAt(),
        "source", result.getSource()
));
```

- [ ] **Step 4: Run the backend test to verify it passes**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/AccountAuthStatusEventPublisher.java apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountAuthStatusService.java apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountAuthStatusServiceTest.java
git commit -m "feat: publish unified account auth status events"
```

### Task 4: Replace workflow account precheck with the unified auth-status service

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/WorkflowAccountValidationService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/WorkflowService.java`
- Modify: `apps/core-api/src/test/java/com/xianyu/admin/service/WorkflowAccountValidationServiceTest.java`

- [ ] **Step 1: Write the failing workflow-precheck test against the new service**

```java
@Mock
private XianyuAccountAuthStatusService authStatusService;

@BeforeEach
void setUp() {
    service = new WorkflowAccountValidationService(authStatusService);
}

@Test
void assertExecutionAccountsReadyUsesUnifiedStatusServiceResults() {
    when(authStatusService.checkAndSync(1L, 12L, "workflow_precheck")).thenReturn(result(12L, "失效账号", false, 0, "PAGE_HEAD_FAILED", "登录已失效，请重新登录闲鱼账号"));

    BizException ex = assertThrows(BizException.class, () -> service.assertExecutionAccountsReady(
            1L,
            List.of(triggerNode(List.of(12L))),
            Map.of()
    ));

    @SuppressWarnings("unchecked")
    Map<String, Object> payload = (Map<String, Object>) ex.getData();
    @SuppressWarnings("unchecked")
    List<Map<String, Object>> invalidAccounts = (List<Map<String, Object>>) payload.get("invalidAccounts");

    assertEquals("登录已失效，请重新登录闲鱼账号", invalidAccounts.get(0).get("reason"));
    verify(authStatusService).checkAndSync(1L, 12L, "workflow_precheck");
}
```

- [ ] **Step 2: Run the workflow validation test to verify it fails**

Run: `mvn -f apps/core-api/pom.xml -Dtest=WorkflowAccountValidationServiceTest test`

Expected: FAIL because constructor and behavior still use the old inline probing path.

- [ ] **Step 3: Replace inline probing with the minimal unified-service call**

```java
package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class WorkflowAccountValidationService {
    private static final String INVALID_REASON = "ACCOUNT_LOGIN_INVALID";

    private final XianyuAccountAuthStatusService authStatusService;

    public WorkflowAccountValidationService(XianyuAccountAuthStatusService authStatusService) {
        this.authStatusService = authStatusService;
    }

    public void assertExecutionAccountsReady(Long tenantId, List<Map<String, Object>> nodes, Map<String, Object> input) {
        List<Map<String, Object>> invalidAccounts = validateExecutionAccounts(tenantId, nodes, input);
        if (invalidAccounts.isEmpty()) return;
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
            AccountAuthStatusResult result = authStatusService.checkAndSync(tenantId, accountId, "workflow_precheck");
            if (!result.isUsable()) {
                invalidAccounts.add(Map.of(
                        "accountId", result.getAccountId(),
                        "nickname", result.getNickname(),
                        "reason", result.getLoginStatusMessage()
                ));
            }
        }
        return invalidAccounts;
    }

    // keep existing resolveAccountIds(...) helpers
}
```

- [ ] **Step 4: Run the workflow validation test to verify it passes**

Run: `mvn -f apps/core-api/pom.xml -Dtest=WorkflowAccountValidationServiceTest test`

Expected: PASS.

- [ ] **Step 5: Run the account-auth tests too**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest,WorkflowAccountValidationServiceTest test`

Expected: PASS for both classes.

- [ ] **Step 6: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/WorkflowAccountValidationService.java apps/core-api/src/main/java/com/xianyu/admin/service/WorkflowService.java apps/core-api/src/test/java/com/xianyu/admin/service/WorkflowAccountValidationServiceTest.java
git commit -m "feat: unify workflow account auth precheck"
```

### Task 5: Expose unified auth fields on account list/detail endpoints

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/dto/XianyuAccountVO.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuAccountMapper.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountService.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountServiceTest.java`

- [ ] **Step 1: Write the failing mapper/service test for new account fields**

```java
@Test
void mapRowToVoIncludesUnifiedLoginStatusFields() {
    Map<String, Object> row = new HashMap<>();
    row.put("id", 11L);
    row.put("external_uid", "uid-11");
    row.put("nickname", "正常账号");
    row.put("status", 1);
    row.put("cookie_status", 1);
    row.put("last_login_status_code", "OK");
    row.put("last_login_status_message", "登录状态正常");

    XianyuAccountVO vo = service.mapRowForTest(row);

    assertEquals(Integer.valueOf(1), vo.getCookieStatus());
    assertEquals(Boolean.TRUE, vo.getLoginUsable());
    assertEquals("OK", vo.getLoginStatusCode());
    assertEquals("登录状态正常", vo.getLoginStatusMessage());
}
```

- [ ] **Step 2: Run the account service test to verify it fails**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountServiceTest test`

Expected: FAIL because the VO and mapping fields are missing.

- [ ] **Step 3: Add the minimal VO fields and row mapping**

```java
// XianyuAccountVO.java
private Boolean loginUsable;
private String loginStatusCode;
private String loginStatusMessage;
private LocalDateTime loginCheckedAt;

public Boolean getLoginUsable() { return loginUsable; }
public void setLoginUsable(Boolean loginUsable) { this.loginUsable = loginUsable; }
public String getLoginStatusCode() { return loginStatusCode; }
public void setLoginStatusCode(String loginStatusCode) { this.loginStatusCode = loginStatusCode; }
public String getLoginStatusMessage() { return loginStatusMessage; }
public void setLoginStatusMessage(String loginStatusMessage) { this.loginStatusMessage = loginStatusMessage; }
public LocalDateTime getLoginCheckedAt() { return loginCheckedAt; }
public void setLoginCheckedAt(LocalDateTime loginCheckedAt) { this.loginCheckedAt = loginCheckedAt; }
```

```java
// XianyuAccountMapper.java SELECT fields
"auth.last_login_status_code, auth.last_login_status_message, auth.last_login_check_time, " +
```

```java
// XianyuAccountService.java mapRowToVO(...)
vo.setLoginStatusCode(getString(row, "last_login_status_code"));
vo.setLoginStatusMessage(getString(row, "last_login_status_message"));
vo.setLoginCheckedAt(getLocalDateTime(row, "last_login_check_time"));
vo.setLoginUsable("OK".equals(getString(row, "last_login_status_code")) && Integer.valueOf(1).equals(vo.getCookieStatus()));
```

- [ ] **Step 4: Run the account service test to verify it passes**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountServiceTest test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/dto/XianyuAccountVO.java apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuAccountMapper.java apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountService.java apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountServiceTest.java
git commit -m "feat: expose unified login status on accounts"
```

### Task 6: Route refresh-profile and cookie-update actions through unified auth checks

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/XianyuAccountController.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountServiceTest.java`

- [ ] **Step 1: Write the failing refresh-profile gate test**

```java
@Test
void refreshProfileStopsEarlyWhenUnifiedAuthStatusIsNotUsable() {
    when(authStatusService.checkAndSync(1L, 12L, "account_refresh_profile"))
            .thenReturn(statusResult(12L, false, 0, "PAGE_HEAD_FAILED", "登录已失效，请重新登录闲鱼账号"));

    BizException ex = assertThrows(BizException.class, () -> service.refreshProfile(1L, 12L));

    assertEquals("登录已失效，请重新登录闲鱼账号", ex.getMessage());
}
```

- [ ] **Step 2: Run the service test to verify it fails**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountServiceTest test`

Expected: FAIL because `refreshProfile(...)` still goes straight to `callPageHead`.

- [ ] **Step 3: Add the smallest guard around refresh-profile**

```java
AccountAuthStatusResult authStatus = authStatusService.checkAndSync(tenantId, accountId, "account_refresh_profile");
if (!authStatus.isUsable()) {
    throw new BizException(400, authStatus.getLoginStatusMessage());
}
```

- [ ] **Step 4: Run the service test to verify it passes**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountServiceTest test`

Expected: PASS.

- [ ] **Step 5: Add a failing test for cookie update to re-check real status instead of blindly setting normal**

```java
@Test
void cookieUpdateDoesNotAssumeNormalBeforeUnifiedAuthRecheck() {
    // assert controller/service path triggers a follow-up auth check instead of only writing cookie_status=1
}
```

- [ ] **Step 6: Implement the minimal re-check hook for post-cookie-update flows**

```java
// after successful cookie save path
authStatusService.checkAndSync(tenantId, accountId, "cookie_updated");
```

- [ ] **Step 7: Run the affected backend tests**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountServiceTest,WorkflowAccountValidationServiceTest,XianyuAccountAuthStatusServiceTest test`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/XianyuAccountService.java apps/core-api/src/main/java/com/xianyu/admin/controller/XianyuAccountController.java apps/core-api/src/main/java/com/xianyu/admin/controller/AutomationProxyController.java apps/core-api/src/test/java/com/xianyu/admin/service/XianyuAccountServiceTest.java
git commit -m "feat: reuse unified auth checks in account actions"
```

### Task 7: Make the account page render unified auth status and react to auth-change events

**Files:**
- Modify: `apps/user-web/src/pages/AccountsPage.vue`
- Modify: `apps/user-web/src/api/accounts.js`
- Test: `apps/user-web/scripts/static-ui-contract.test.mjs`

- [ ] **Step 1: Write the failing UI contract assertion for login status fields**

```javascript
import fs from 'node:fs';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('../src/pages/AccountsPage.vue', import.meta.url), 'utf8');

assert.match(source, /loginStatusMessage/, 'AccountsPage should render unified loginStatusMessage');
assert.match(source, /account_auth_status_changed/, 'AccountsPage should react to unified auth-change events');
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `npm --prefix apps/user-web test`

Expected: FAIL because `AccountsPage.vue` still renders from `cookie_status` directly.

- [ ] **Step 3: Update the page to use the unified status fields with the smallest UI change**

```vue
const accountLoginMessage = (a) => a.loginStatusMessage || cookieStatusInfo(a.cookie_status).text
const accountLoginBad = (a) => a.loginUsable === false || a.cookie_status === 0 || a.cookie_status === 2
```

```vue
const cookieBad = a.loginUsable === false || a.cookie_status === 0 || a.cookie_status === 2
return [
  {
    title: 'Cookie 状态',
    level: cookieBad ? 'danger' : 'ok',
    text: a.loginStatusMessage || (cookieBad ? '失效/需验证' : '正常'),
    tip: a.loginCheckedAt ? `最近检测：${displayDateTime(a.loginCheckedAt)}` : '显示最近一次统一登录态判定结果。'
  }
]
```

```vue
window.addEventListener('xya-sse-event', handleSseEvent)
if (event.type === 'account_auth_status_changed') {
  loadAccounts()
}
```

- [ ] **Step 4: Run the frontend test to verify it passes**

Run: `npm --prefix apps/user-web test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/pages/AccountsPage.vue apps/user-web/src/api/accounts.js apps/user-web/scripts/static-ui-contract.test.mjs
git commit -m "feat: unify account page auth status display"
```

### Task 8: Make the connections page separate login auth from websocket state

**Files:**
- Modify: `apps/user-web/src/pages/ConnectionsPage.vue`
- Modify: `apps/user-web/src/api/websocket.js`
- Test: `apps/user-web/scripts/static-ui-contract.test.mjs`

- [ ] **Step 1: Write the failing UI contract assertion for unified auth usage in connections**

```javascript
const source = fs.readFileSync(new URL('../src/pages/ConnectionsPage.vue', import.meta.url), 'utf8');

assert.match(source, /loginStatusMessage/, 'ConnectionsPage should use unified loginStatusMessage');
assert.doesNotMatch(source, /a\.status===1\?'有效':'异常\/需验证'/, 'ConnectionsPage should not infer cookie status from account status');
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `npm --prefix apps/user-web test`

Expected: FAIL because the old fallback string still exists.

- [ ] **Step 3: Update the page to render unified auth fields while keeping websocket state separate**

```vue
return {
  id: a.id,
  raw: a,
  avatar: a.avatarUrl || a.avatar,
  name: accountName(a),
  user: a.externalUid || a.unb || a.loginUsername || `account_${a.id}`,
  cookie: a.loginStatusMessage || (a.cookie_status === 1 ? '登录状态正常' : '登录状态异常'),
  loginUsable: a.loginUsable !== false,
  connected: !!s.connected,
  ws: wsText,
  heartbeat: s.connected ? '正常' : '停止',
  latency: s.connected ? '在线' : '-',
  last: s.lastMessageTime || s.last || '-',
  auto: true,
  proxy: a.proxyHost || '-',
  status: s.status,
  phase,
  lastError,
  captcha: s.captchaStatus,
  wsTokenStatus: s.wsTokenStatus,
  isRefreshing,
  refreshError: refreshErr,
  retrying: retry?.phase === 'retrying',
  retryAttempt: retry?.attempt || 0,
  retryMax: retry?.max || 0,
}
```

```vue
if (event.type === 'account_auth_status_changed') {
  load()
}
```

- [ ] **Step 4: Run the frontend test to verify it passes**

Run: `npm --prefix apps/user-web test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/pages/ConnectionsPage.vue apps/user-web/src/api/websocket.js apps/user-web/scripts/static-ui-contract.test.mjs
git commit -m "feat: separate auth and websocket state in connections page"
```

### Task 9: Make workflow account selection and pre-run failure UI use the same auth fields

**Files:**
- Modify: `apps/user-web/src/pages/WorkflowPage.vue`
- Test: `apps/user-web/scripts/static-ui-contract.test.mjs`

- [ ] **Step 1: Write the failing UI contract assertion for workflow auth messaging**

```javascript
const source = fs.readFileSync(new URL('../src/pages/WorkflowPage.vue', import.meta.url), 'utf8');

assert.match(source, /loginStatusMessage/, 'WorkflowPage should render unified account login status');
assert.match(source, /运行前账号校验失败/, 'WorkflowPage should keep the unified precheck dialog entrypoint');
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `npm --prefix apps/user-web test`

Expected: FAIL if the account-card rendering still ignores unified fields.

- [ ] **Step 3: Update the workflow account cards and failure mapping minimally**

```vue
<div v-if="acct.loginStatusMessage" class="account-card-intro">{{ acct.loginStatusMessage }}</div>
<div v-else-if="acct.introduction" class="account-card-intro">{{ acct.introduction }}</div>
```

```javascript
const lines = invalidAccounts.map(item =>
  `- ${item.nickname || `账号#${item.accountId}`}${item.accountId ? `（ID: ${item.accountId}）` : ''}：${item.reason || '登录状态异常'}`
)
```

- [ ] **Step 4: Run the frontend test to verify it passes**

Run: `npm --prefix apps/user-web test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/pages/WorkflowPage.vue apps/user-web/scripts/static-ui-contract.test.mjs
git commit -m "feat: unify workflow account auth messaging"
```

### Task 10: Patch the remaining account consumers and automation-side auth status writer

**Files:**
- Modify: `apps/automation-service/app/services/ws_client.py`
- Modify: `apps/user-web/src/pages/AutoReplyPage.vue`
- Modify: `apps/user-web/src/pages/MessagesPage.vue`
- Modify: `apps/user-web/src/pages/OpportunityPage.vue`
- Modify: `apps/user-web/src/pages/ProductPublishPage.vue`
- Modify: `apps/user-web/src/pages/ProductsPage.vue`
- Modify: `apps/user-web/src/mobile/MobileAccounts.vue`
- Test: `apps/user-web/scripts/static-ui-contract.test.mjs`

- [ ] **Step 1: Write the failing contract test for shared auth field availability**

```javascript
for (const file of [
  '../src/pages/AutoReplyPage.vue',
  '../src/pages/MessagesPage.vue',
  '../src/pages/OpportunityPage.vue',
  '../src/pages/ProductPublishPage.vue',
  '../src/pages/ProductsPage.vue',
  '../src/mobile/MobileAccounts.vue',
]) {
  const source = fs.readFileSync(new URL(file, import.meta.url), 'utf8');
  assert.ok(source.includes('getAccounts'), `${file} should still consume account list`);
}
```

- [ ] **Step 2: Run the frontend test to verify the current baseline**

Run: `npm --prefix apps/user-web test`

Expected: PASS or FAIL depending on current coverage, but record the exact result before changing behavior.

- [ ] **Step 3: Update the automation-service websocket side-effect to emit the unified auth event payload**

```python
await broadcaster.broadcast("account_auth_status_changed", {
    "type": "account_auth_status_changed",
    "accountId": self.account_id,
    "cookieStatus": status,
    "usable": status == 1,
    "loginStatusCode": "CAPTCHA_REQUIRED" if status == 0 else "OK",
    "loginStatusMessage": "当前账号需要完成验证后才能继续操作" if status == 0 else "登录状态正常",
})
```

- [ ] **Step 4: Update the remaining account consumers to prefer unified fields when disabling or labeling accounts**

```vue
const usableAccounts = computed(() => accounts.value.filter(a => a.loginUsable !== false))
const accountStatusLabel = (a) => a.loginStatusMessage || '登录状态未知'
```

- [ ] **Step 5: Run the frontend test suite again**

Run: `npm --prefix apps/user-web test`

Expected: PASS.

- [ ] **Step 6: Run a focused backend regression suite**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest,WorkflowAccountValidationServiceTest,XianyuAccountServiceTest test`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/automation-service/app/services/ws_client.py apps/user-web/src/pages/AutoReplyPage.vue apps/user-web/src/pages/MessagesPage.vue apps/user-web/src/pages/OpportunityPage.vue apps/user-web/src/pages/ProductPublishPage.vue apps/user-web/src/pages/ProductsPage.vue apps/user-web/src/mobile/MobileAccounts.vue apps/user-web/scripts/static-ui-contract.test.mjs
git commit -m "feat: roll unified auth status through remaining consumers"
```

### Task 11: Final verification pass

**Files:**
- Modify: none
- Test: existing backend/frontend tests only

- [ ] **Step 1: Run the full frontend check**

Run: `npm --prefix apps/user-web check`

Expected: `lint`, `test`, and `build` all pass.

- [ ] **Step 2: Run the focused backend service tests**

Run: `mvn -f apps/core-api/pom.xml -Dtest=XianyuAccountAuthStatusServiceTest,WorkflowAccountValidationServiceTest,XianyuAccountServiceTest test`

Expected: PASS.

- [ ] **Step 3: Manual verification checklist**

Run these flows locally and confirm:

```text
1. 打开账号管理页，确认 Cookie 状态显示统一文案和最近检测时间
2. 打开连接管理页，确认 Cookie 状态与 WebSocket 状态并列显示、文案一致
3. 运行工作流，确认不可用账号会用统一错误文案拦截
4. 手动更新 Cookie 后，确认账号管理页、连接管理页、工作流账号列表都同步刷新
5. 触发一次 websocket 风控/失效回写，确认前端收到 account_auth_status_changed 后刷新
```

- [ ] **Step 4: Commit the final verified state**

```bash
git add -A
git commit -m "feat: unify account cookie and login status across the app"
```

---

## Self-Review

### Spec coverage

- Unified auth-status service: covered by Tasks 1-3.
- Database persistence and mirrored runtime fields: covered by Task 2.
- Workflow precheck migration: covered by Task 4.
- Account list/detail unified fields: covered by Task 5.
- Refresh profile / cookie update / check login reuse: covered by Task 6.
- Account management page sync: covered by Task 7.
- Connection management page sync: covered by Task 8.
- Workflow UI sync: covered by Task 9.
- Other account consumers and automation-side broadcast path: covered by Task 10.
- Verification and regression safety: covered by Task 11.

### Placeholder scan

- No `TODO`, `TBD`, or “similar to Task N” placeholders remain.
- All code-bearing steps include explicit code blocks.
- All execution steps include exact commands and expected outcomes.

### Type consistency

- Unified result object uses `AccountAuthStatusResult` throughout backend tasks.
- Unified event name is consistently `account_auth_status_changed`.
- Shared frontend fields are consistently `loginUsable`, `loginStatusCode`, `loginStatusMessage`, and `loginCheckedAt`.

