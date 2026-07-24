package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.AccountAuthStatusResult;
import com.xianyu.admin.dto.XianyuAccountDTO;
import com.xianyu.admin.dto.XianyuAccountSummaryVO;
import com.xianyu.admin.dto.XianyuAccountVO;
import com.xianyu.admin.entity.*;
import com.xianyu.admin.mapper.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;

@Service
public class XianyuAccountService {
    private static final Logger log = LoggerFactory.getLogger(XianyuAccountService.class);

    private final XianyuAccountMapper accountMapper;
    private final XianyuAccountAuthMapper authMapper;
    private final XianyuAccountRuntimeMapper runtimeMapper;
    private final XianyuAccountMembershipMapper membershipMapper;
    private final XianyuAccountHealthSnapshotMapper healthSnapshotMapper;
    private final CookieCryptoService cookieCryptoService;
    private final AutomationClient automationClient;
    private final XianyuAccountAuthStatusService accountAuthStatusService;

    public XianyuAccountService(XianyuAccountMapper accountMapper,
                                 XianyuAccountAuthMapper authMapper,
                                 XianyuAccountRuntimeMapper runtimeMapper,
                                 XianyuAccountMembershipMapper membershipMapper,
                                 XianyuAccountHealthSnapshotMapper healthSnapshotMapper,
                                 CookieCryptoService cookieCryptoService,
                                 AutomationClient automationClient,
                                 XianyuAccountAuthStatusService accountAuthStatusService) {
        this.accountMapper = accountMapper;
        this.authMapper = authMapper;
        this.runtimeMapper = runtimeMapper;
        this.membershipMapper = membershipMapper;
        this.healthSnapshotMapper = healthSnapshotMapper;
        this.cookieCryptoService = cookieCryptoService;
        this.automationClient = automationClient;
        this.accountAuthStatusService = accountAuthStatusService;
    }

    /**
     * 分页查询账号列表
     */
    public PageResult<XianyuAccountVO> page(Long tenantId, String keyword, Integer status,
                                             int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = accountMapper.count(tenantId, keyword, status);
        List<Map<String, Object>> rows = accountMapper.list(tenantId, keyword, status, offset, limit);

        List<XianyuAccountVO> records = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            XianyuAccountVO vo = mapRowToVO(row);
            Object expiredTimeObj = row.get("membership_expired_time");
            if (expiredTimeObj instanceof LocalDateTime) {
                vo.setMembershipExpiredTime((LocalDateTime) expiredTimeObj);
            }
            records.add(vo);
        }

        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    public PageResult<XianyuAccountVO> pageLite(Long tenantId, String keyword, Integer status,
                                                int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = accountMapper.count(tenantId, keyword, status);
        List<Map<String, Object>> rows = accountMapper.listLite(tenantId, keyword, status, offset, limit);

        List<XianyuAccountVO> records = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            records.add(mapRowToVO(row));
        }

        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 查询账号详情
     */
    public XianyuAccountVO detail(Long tenantId, Long id) {
        XianyuAccount account = accountMapper.findById(tenantId, id);
        if (account == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }

        XianyuAccountVO vo = new XianyuAccountVO();
        vo.setId(account.getId());
        vo.setExternalUid(account.getExternalUid());
        vo.setNickname(account.getNickname());
        vo.setAvatarUrl(normalizeAvatarUrl(account.getAvatarUrl()));
        vo.setProvince(account.getProvince());
        vo.setCity(account.getCity());
        vo.setAccountLevel(account.getAccountLevel());
        vo.setRemark(account.getRemark());
        vo.setStatus(account.getStatus());

        // 刷新资料字段
        vo.setDisplayName(account.getDisplayName());
        vo.setIpLocation(account.getIpLocation());
        vo.setIntroduction(account.getIntroduction());
        vo.setFollowers(account.getFollowers());
        vo.setFollowing(account.getFollowing());
        vo.setSellerLevel(account.getSellerLevel());
        vo.setFishShopScore(account.getFishShopScore());
        vo.setFishShopUser(account.getFishShopUser());
        vo.setPraiseRatio(account.getPraiseRatio());
        vo.setReviewNum(account.getReviewNum());
        vo.setSoldCount(account.getSoldCount());
        vo.setMessageExpireTime(account.getMessageExpireTime());
        vo.setScheduledRedelivery(account.getScheduledRedelivery());
        vo.setAutoPolish(account.getAutoPolish());

        // 会员信息
        XianyuAccountMembership membership = membershipMapper.findByAccountId(tenantId, id);
        if (membership != null) {
            vo.setMembershipLevel(membership.getMembershipLevel());
            vo.setMembershipExpiredTime(membership.getExpiredTime());
        }

        // 认证信息
        XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, id);
        if (auth != null) {
            vo.setCookieStatus(auth.getCookieStatus());
            vo.setLoginStatusCode(auth.getLastLoginStatusCode());
            vo.setLoginStatusMessage(auth.getLastLoginStatusMessage());
            vo.setLoginCheckTime(auth.getLastLoginCheckTime());
            vo.setAuthUsable(auth.getCookieStatus() != null
                    && auth.getCookieStatus() == 1
                    && "OK".equalsIgnoreCase(auth.getLastLoginStatusCode()));
        }

        // 运行时信息
        XianyuAccountRuntime runtime = runtimeMapper.findByAccountId(tenantId, id);
        if (runtime != null) {
            vo.setWsStatus(runtime.getWsStatus());
            vo.setOnlineStatus(runtime.getOnlineStatus());
            vo.setLastSyncTime(runtime.getLastSyncTime());
            vo.setLastOnlineTime(runtime.getLastOnlineTime());
            vo.setWsLatencyMs(runtime.getWsLatencyMs());
            if (vo.getLoginStatusCode() == null) {
                vo.setLoginStatusCode(runtime.getLastLoginStatusCode());
                vo.setLoginStatusMessage(runtime.getLastLoginStatusMessage());
                vo.setLoginCheckTime(runtime.getLastLoginCheckTime());
            }
            if (vo.getAuthUsable() == null) {
                vo.setAuthUsable(runtime.getCookieStatus() != null
                        && runtime.getCookieStatus() == 1
                        && "OK".equalsIgnoreCase(runtime.getLastLoginStatusCode()));
            }
        }

        // 健康快照
        XianyuAccountHealthSnapshot snapshot = healthSnapshotMapper.findLatestByAccountId(tenantId, id);
        if (snapshot != null) {
            vo.setApiSuccessRate(snapshot.getApiSuccessRate());
            vo.setAvgResponseMs(snapshot.getAvgResponseMs());
            vo.setHealthScore(snapshot.getHealthScore());
        }

        return vo;
    }

    /**
     * 创建账号
     */
    @Transactional
    public XianyuAccountVO create(Long tenantId, Long userId, XianyuAccountDTO dto) {
        // 检查 external_uid 是否已存在
        XianyuAccount existing = accountMapper.findByExternalUid(tenantId, dto.getExternalUid());
        if (existing != null) {
            throw new BizException(400, "externalUid已存在");
        }

        // 1. 插入主账号
        XianyuAccount account = new XianyuAccount();
        account.setTenantId(tenantId);
        account.setUserId(userId);
        account.setExternalUid(dto.getExternalUid());
        account.setNickname(dto.getNickname());
        account.setAvatarUrl(dto.getAvatarUrl());
        account.setProvince(dto.getProvince());
        account.setCity(dto.getCity());
        account.setAccountLevel(dto.getAccountLevel());
        account.setRemark(dto.getRemark());
        account.setStatus(dto.getStatus() != null ? dto.getStatus() : 1);
        accountMapper.insert(account);

        Long accountId = account.getId();

        // 2. 插入认证记录（空加密字段）
        XianyuAccountAuth auth = new XianyuAccountAuth();
        auth.setTenantId(tenantId);
        auth.setAccountId(accountId);
        auth.setEncryptedCookie(null);
        auth.setEncryptedToken(null);
        auth.setCookieStatus(0);
        auth.setWsToken(null);
        auth.setTokenExpireTime(null);
        authMapper.insert(auth);

        // 3. 插入运行时记录（默认值）
        XianyuAccountRuntime runtime = new XianyuAccountRuntime();
        runtime.setTenantId(tenantId);
        runtime.setAccountId(accountId);
        runtime.setOnlineStatus(0);
        runtime.setWsStatus(0);
        runtime.setWsLatencyMs(null);
        runtime.setCookieStatus(0);
        runtime.setLastLoginTime(null);
        runtime.setLastHeartbeatTime(null);
        runtime.setLastOnlineTime(null);
        runtime.setLastSyncTime(null);
        runtimeMapper.insert(runtime);

        // 4. 插入会员记录（默认normal）
        XianyuAccountMembership membership = new XianyuAccountMembership();
        membership.setTenantId(tenantId);
        membership.setAccountId(accountId);
        membership.setMembershipLevel("normal");
        membership.setExpiredTime(null);
        membership.setStatus(1);
        membershipMapper.insert(membership);

        // 5. 插入健康快照初始化
        XianyuAccountHealthSnapshot snapshot = new XianyuAccountHealthSnapshot();
        snapshot.setTenantId(tenantId);
        snapshot.setAccountId(accountId);
        snapshot.setHealthScore(100);
        snapshot.setApiSuccessRate(100.0);
        snapshot.setAvgResponseMs(0);
        snapshot.setWsLatencyMs(0);
        snapshot.setCollectedTime(LocalDateTime.now());
        healthSnapshotMapper.insert(snapshot);

        log.info("创建闲鱼账号成功: id={}, externalUid={}, tenantId={}", accountId, dto.getExternalUid(), tenantId);
        return detail(tenantId, accountId);
    }

    /**
     * 更新账号
     */
    @Transactional
    public XianyuAccountVO update(Long tenantId, Long id, XianyuAccountDTO dto) {
        XianyuAccount existing = accountMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }

        // 如果修改了external_uid，检查是否重复
        if (dto.getExternalUid() != null && !dto.getExternalUid().equals(existing.getExternalUid())) {
            XianyuAccount duplicate = accountMapper.findByExternalUid(tenantId, dto.getExternalUid());
            if (duplicate != null) {
                throw new BizException(400, "externalUid已存在");
            }
        }

        XianyuAccount account = new XianyuAccount();
        account.setId(id);
        account.setTenantId(tenantId);
        account.setExternalUid(dto.getExternalUid() != null ? dto.getExternalUid() : existing.getExternalUid());
        account.setNickname(dto.getNickname() != null ? dto.getNickname() : existing.getNickname());
        account.setAvatarUrl(dto.getAvatarUrl() != null ? dto.getAvatarUrl() : existing.getAvatarUrl());
        account.setProvince(dto.getProvince() != null ? dto.getProvince() : existing.getProvince());
        account.setCity(dto.getCity() != null ? dto.getCity() : existing.getCity());
        account.setAccountLevel(dto.getAccountLevel() != null ? dto.getAccountLevel() : existing.getAccountLevel());
        account.setRemark(dto.getRemark() != null ? dto.getRemark() : existing.getRemark());
        account.setStatus(dto.getStatus() != null ? dto.getStatus() : existing.getStatus());
        accountMapper.update(account);

        log.info("更新闲鱼账号成功: id={}, tenantId={}", id, tenantId);
        return detail(tenantId, id);
    }

    /**
     * 删除账号（软删除）
     */
    @Transactional
    public void delete(Long tenantId, Long id) {
        XianyuAccount existing = accountMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }
        stopAccountAutomation(tenantId, id);
        authMapper.softDeleteByAccountId(tenantId, id);
        runtimeMapper.softDeleteByAccountId(tenantId, id);
        accountMapper.softDelete(tenantId, id);
        log.info("删除闲鱼账号: id={}, tenantId={}", id, tenantId);
    }


    /**
     * 通过前台手动粘贴 Cookie 创建或更新闲鱼账号。
     */
    @Transactional
    public XianyuAccountVO createFromCookie(Long tenantId, Long userId, String accountNote, String cookieText) {
        try {
            if (cookieText == null || cookieText.isBlank()) {
                throw new BizException(400, "Cookie不能为空");
            }
            Map<String, String> cookieMap = parseCookieText(cookieText);
            String externalUid = firstNonBlank(cookieMap.get("unb"), cookieMap.get("userId"), cookieMap.get("userid"));
            if (externalUid == null || externalUid.isBlank()) {
                throw new BizException(400, "Cookie缺少unb，无法确认账号身份");
            }
            String nickname = (accountNote == null || accountNote.isBlank()) ? externalUid : accountNote.trim();
            XianyuAccount existing = accountMapper.findByExternalUid(tenantId, externalUid);
            XianyuAccount account;
            if (existing == null) {
                XianyuAccountDTO dto = new XianyuAccountDTO();
                dto.setExternalUid(externalUid);
                dto.setNickname(nickname);
                dto.setRemark(accountNote);
                dto.setStatus(1);
                XianyuAccountVO created = create(tenantId, userId, dto);
                account = accountMapper.findById(tenantId, created.getId());
            } else {
                account = existing;
                restoreRelatedRecords(tenantId, existing.getId());
                XianyuAccountDTO dto = new XianyuAccountDTO();
                dto.setNickname(nickname);
                dto.setRemark(accountNote);
                dto.setStatus(1);
                update(tenantId, existing.getId(), dto);
            }
            upsertAuthCookie(tenantId, account.getId(), cookieText);
            ensureRuntimeOnline(tenantId, account.getId());
            return detail(tenantId, account.getId());
        } catch (BizException e) {
            // BizException 直接透传，GlobalExceptionHandler 会正确处理
            throw e;
        } catch (IllegalStateException e) {
            // 加密/解密失败
            log.error("Cookie处理失败: tenantId={}, errorType={}", tenantId, e.getClass().getSimpleName());
            throw new BizException(500, "Cookie 安全处理失败，请检查服务端加密配置后重试");
        } catch (org.springframework.dao.DataAccessException e) {
            // 数据库操作异常
            log.error("数据库操作失败: tenantId={}, errorType={}", tenantId, e.getClass().getSimpleName(), e);
            throw new BizException(500, "账号保存失败，数据库异常，请稍后重试");
        } catch (Exception e) {
            // 兜底：记录详细日志后转为BizException
            log.error("手动添加账号未知异常: tenantId={}, errorType={}", tenantId, e.getClass().getSimpleName(), e);
            throw new BizException(500, "账号保存失败，请检查Cookie格式或稍后重试");
        }
    }

    /**
     * 通过扫码登录返回的 Cookie Map 创建或更新账号。
     */
    @Transactional
    public XianyuAccountVO createFromQrCookies(Long tenantId, Long userId, Map<String, String> cookies) {
        if (cookies == null || cookies.isEmpty()) {
            throw new BizException(400, "扫码登录未返回Cookie");
        }
        StringJoiner joiner = new StringJoiner("; ");
        cookies.forEach((k, v) -> {
            if (k != null && v != null) {
                joiner.add(k + "=" + v);
            }
        });
        String cookieText = joiner.toString();
        String externalUid = firstNonBlank(cookies.get("unb"), cookies.get("userId"), cookies.get("userid"), cookies.get("cna"));
        String note = externalUid == null ? "扫码登录账号" : "扫码登录账号 " + externalUid;
        return createFromCookie(tenantId, userId, note, cookieText);
    }

    private void upsertAuthCookie(Long tenantId, Long accountId, String cookieText) {
        LocalDateTime now = LocalDateTime.now();
        String mh5Token = parseCookieText(cookieText).get("_m_h5_tk");
        XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, accountId);
        if (auth == null) {
            auth = authMapper.findLatestByAccountIdIncludingDeleted(tenantId, accountId);
        }
        if (auth == null) {
            auth = new XianyuAccountAuth();
            auth.setTenantId(tenantId);
            auth.setAccountId(accountId);
            auth.setEncryptedToken(mh5Token == null || mh5Token.isBlank() ? null : cookieCryptoService.encrypt(mh5Token));
            auth.setWsToken(null);
            auth.setTokenExpireTime(null);
            auth.setEncryptedCookie(cookieCryptoService.encrypt(cookieText));
            auth.setCookieStatus(0);
            auth.setLastLoginStatusCode("COOKIE_UPDATED");
            auth.setLastLoginStatusMessage("Cookie 已更新，等待统一登录校验");
            auth.setLastLoginCheckTime(now);
            authMapper.insert(auth);
        } else {
            authMapper.restoreByAccountId(tenantId, accountId);
            auth.setTenantId(tenantId);
            auth.setAccountId(accountId);
            auth.setEncryptedCookie(cookieCryptoService.encrypt(cookieText));
            auth.setEncryptedToken(mh5Token == null || mh5Token.isBlank() ? null : cookieCryptoService.encrypt(mh5Token));
            auth.setCookieStatus(0);
            auth.setLastLoginStatusCode("COOKIE_UPDATED");
            auth.setLastLoginStatusMessage("Cookie 已更新，等待统一登录校验");
            auth.setLastLoginCheckTime(now);
            authMapper.update(auth);
        }

        XianyuAccountRuntime runtime = runtimeMapper.findByAccountId(tenantId, accountId);
        if (runtime == null) {
            runtime = runtimeMapper.findLatestByAccountIdIncludingDeleted(tenantId, accountId);
        }
        if (runtime != null) {
            runtimeMapper.restoreByAccountId(tenantId, accountId);
            runtime.setCookieStatus(0);
            runtime.setLastLoginStatusCode("COOKIE_UPDATED");
            runtime.setLastLoginStatusMessage("Cookie 已更新，等待统一登录校验");
            runtime.setLastLoginCheckTime(now);
            runtimeMapper.update(runtime);
        }
    }

    private void ensureRuntimeOnline(Long tenantId, Long accountId) {
        LocalDateTime now = LocalDateTime.now();
        XianyuAccountRuntime runtime = runtimeMapper.findByAccountId(tenantId, accountId);
        if (runtime == null) {
            runtime = runtimeMapper.findLatestByAccountIdIncludingDeleted(tenantId, accountId);
        }
        if (runtime == null) {
            runtime = new XianyuAccountRuntime();
            runtime.setTenantId(tenantId);
            runtime.setAccountId(accountId);
            runtime.setOnlineStatus(1);
            runtime.setWsStatus(1);
            runtime.setWsLatencyMs(0);
            runtime.setCookieStatus(0);
            runtime.setLastLoginTime(now);
            runtime.setLastHeartbeatTime(now);
            runtime.setLastOnlineTime(now);
            runtime.setLastSyncTime(now);
            runtime.setLastLoginStatusCode("COOKIE_UPDATED");
            runtime.setLastLoginStatusMessage("Cookie 已更新，等待统一登录校验");
            runtime.setLastLoginCheckTime(now);
            runtimeMapper.insert(runtime);
        } else {
            runtimeMapper.restoreByAccountId(tenantId, accountId);
            runtimeMapper.updateHeartbeat(tenantId, accountId, 1, 1, 0, now);
        }
    }

    private void restoreRelatedRecords(Long tenantId, Long accountId) {
        authMapper.restoreByAccountId(tenantId, accountId);
        runtimeMapper.restoreByAccountId(tenantId, accountId);
    }

    private void stopAccountAutomation(Long tenantId, Long accountId) {
        try {
            automationClient.postInternal("/api/websocket/stop", Map.of(
                    "tenantId", tenantId,
                    "tenant_id", tenantId,
                    "accountId", accountId,
                    "xianyuAccountId", accountId
            ), tenantId);
        } catch (Exception e) {
            log.warn("停止已删除账号的自动回复失败，将继续执行软删除: tenantId={}, accountId={}, errorType={}",
                    tenantId,
                    accountId,
                    e.getClass().getSimpleName());
        }
    }

    private Map<String, String> parseCookieText(String cookieText) {
        Map<String, String> map = new java.util.HashMap<>();
        for (String part : cookieText.split(";")) {
            String[] kv = part.trim().split("=", 2);
            if (kv.length == 2 && !kv[0].isBlank()) map.put(kv[0].trim(), kv[1].trim());
        }
        return map;
    }

    private String firstNonBlank(String... values) {
        if (values == null) return null;
        for (String value : values) {
            if (value != null && !value.isBlank()) return value.trim();
        }
        return null;
    }

    /**
     * 汇总统计
     */
    public XianyuAccountSummaryVO summary(Long tenantId) {
        XianyuAccountSummaryVO summary = new XianyuAccountSummaryVO();

        // 基础统计
        Map<String, Object> basicSummary = accountMapper.selectSummary(tenantId);
        summary.setTotal(longOrZero(getLong(basicSummary, "total")));
        summary.setNormal(longOrZero(getLong(basicSummary, "active_count")));

        // WebSocket在线数
        int wsOnline = runtimeMapper.countByWsStatus(tenantId, 1);
        summary.setWsOnline((long) wsOnline);

        // Cookie预警数
        int cookieWarn = authMapper.countByCookieStatus(tenantId, 0);
        summary.setCookieWarn((long) cookieWarn);

        // 待验证数（status=0）
        Map<String, Object> statusSummary = accountMapper.selectByStatus(tenantId);
        summary.setVerify(longOrZero(getLong(statusSummary, "verify_count")));

        return summary;
    }

    // ==================== 私有辅助方法 ====================

    private XianyuAccountVO mapRowToVO(Map<String, Object> row) {
        XianyuAccountVO vo = new XianyuAccountVO();
        vo.setId(getLong(row, "id"));
        vo.setExternalUid(getString(row, "external_uid"));
        vo.setNickname(getString(row, "nickname"));
        vo.setAvatarUrl(normalizeAvatarUrl(getString(row, "avatar_url")));
        vo.setProvince(getString(row, "province"));
        vo.setCity(getString(row, "city"));
        vo.setAccountLevel(getInteger(row, "account_level"));
        vo.setRemark(getString(row, "remark"));
        vo.setStatus(getInteger(row, "status"));
        vo.setMembershipLevel(getString(row, "membership_level"));
        vo.setCookieStatus(getInteger(row, "cookie_status"));
        String loginStatusCode = getString(row, "last_login_status_code");
        vo.setAuthUsable(getInteger(row, "cookie_status") != null
                && getInteger(row, "cookie_status") == 1
                && "OK".equalsIgnoreCase(loginStatusCode));
        vo.setLoginStatusCode(loginStatusCode);
        vo.setLoginStatusMessage(getString(row, "last_login_status_message"));
        vo.setLoginCheckTime(getLocalDateTime(row, "last_login_check_time"));
        vo.setWsStatus(getInteger(row, "ws_status"));
        vo.setOnlineStatus(getInteger(row, "online_status"));
        vo.setLastSyncTime(getLocalDateTime(row, "last_heartbeat_time"));
        vo.setLastOnlineTime(getLocalDateTime(row, "last_online_time"));
        vo.setWsLatencyMs(getInteger(row, "ws_latency_ms"));
        vo.setApiSuccessRate(getDouble(row, "api_success_rate"));
        vo.setAvgResponseMs(getInteger(row, "avg_response_ms"));
        vo.setHealthScore(getInteger(row, "health_score"));
        // 刷新资料字段
        vo.setDisplayName(getString(row, "display_name"));
        vo.setIpLocation(getString(row, "ip_location"));
        vo.setIntroduction(getString(row, "introduction"));
        vo.setFollowers(getInteger(row, "followers"));
        vo.setFollowing(getInteger(row, "following"));
        vo.setSellerLevel(getString(row, "seller_level"));
        vo.setFishShopScore(getInteger(row, "fish_shop_score"));
        vo.setFishShopUser(getBoolean(row, "fish_shop_user"));
        vo.setPraiseRatio(getString(row, "praise_ratio"));
        vo.setReviewNum(getInteger(row, "review_num"));
        vo.setSoldCount(getInteger(row, "sold_count"));
        vo.setMessageExpireTime(getInteger(row, "message_expire_time"));
        vo.setScheduledRedelivery(getBoolean(row, "scheduled_redelivery"));
        vo.setAutoPolish(getBoolean(row, "auto_polish"));
        return vo;
    }

    private Long getLong(Map<String, Object> map, String key) {
        if (map == null) return null;
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Long) return (Long) val;
        if (val instanceof Number) return ((Number) val).longValue();
        return Long.parseLong(String.valueOf(val));
    }

    private String getString(Map<String, Object> map, String key) {
        if (map == null) return null;
        Object val = map.get(key);
        return val != null ? String.valueOf(val) : null;
    }

    private Integer getInteger(Map<String, Object> map, String key) {
        if (map == null) return null;
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Integer) return (Integer) val;
        if (val instanceof Number) return ((Number) val).intValue();
        return Integer.parseInt(String.valueOf(val));
    }

    private Double getDouble(Map<String, Object> map, String key) {
        if (map == null) return null;
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Double) return (Double) val;
        if (val instanceof Number) return ((Number) val).doubleValue();
        return Double.parseDouble(String.valueOf(val));
    }

    private LocalDateTime getLocalDateTime(Map<String, Object> map, String key) {
        if (map == null) return null;
        Object val = map.get(key);
        if (val instanceof LocalDateTime) return (LocalDateTime) val;
        return null;
    }

    private Boolean getBoolean(Map<String, Object> map, String key) {
        if (map == null) return null;
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Boolean) return (Boolean) val;
        if (val instanceof Number) return ((Number) val).intValue() != 0;
        return Boolean.parseBoolean(String.valueOf(val));
    }

    private Long longOrZero(Long value) {
        return value == null ? 0L : value;
    }

    // ==================== 刷新账号资料 ====================

    /**
     * 调用闲鱼 API 刷新账号资料，并更新数据库。
     */
    @Transactional
    public XianyuAccountVO refreshProfile(Long tenantId, Long accountId) {
        XianyuAccount account = accountMapper.findById(tenantId, accountId);
        if (account == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }

        // 获取 Cookie
        XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, accountId);
        if (auth == null || auth.getEncryptedCookie() == null || auth.getEncryptedCookie().isBlank()) {
            throw new BizException(400, "该账号无 Cookie，无法刷新资料");
        }
        String cookie = cookieCryptoService.decryptIfNeeded(auth.getEncryptedCookie());

        // 获取 unb
        String unb = account.getExternalUid();
        if (unb == null || unb.isBlank()) {
            throw new BizException(400, "该账号无 externalUid，无法刷新资料");
        }

        // 调用闲鱼 API
        XianyuAccountRuntime runtime = runtimeMapper.findByAccountId(tenantId, accountId);
        Map<String, Object> headData = XianyuApiUtils.callPageHead(cookie, unb);
        if (headData == null) {
            throw new BizException(500, "调用闲鱼 user.page.head API 失败，请检查 Cookie 是否有效");
        }
        Map<String, Object> navData = XianyuApiUtils.callPageNav(cookie, unb);

        // 解析 page.head 返回数据
        @SuppressWarnings("unchecked")
        Map<String, Object> base = (Map<String, Object>) headData.get("base");
        @SuppressWarnings("unchecked")
        Map<String, Object> social = (Map<String, Object>) headData.get("social");
        @SuppressWarnings("unchecked")
        Map<String, Object> shop = (Map<String, Object>) headData.get("shop");

        if (base != null) {
            String displayName = strVal(base, "displayName");
            String ipLocation = strVal(base, "ipLocation");
            String introduction = strVal(base, "introduction");
            String avatar = strVal(base, "avatar");

            if (displayName != null && !displayName.isBlank()) {
                account.setDisplayName(displayName);
                account.setNickname(displayName);
            }
            if (ipLocation != null && !ipLocation.isBlank()) {
                account.setIpLocation(ipLocation);
            }
            if (introduction != null && !introduction.isBlank()) {
                account.setIntroduction(introduction);
            }
            if (avatar != null && !avatar.isBlank()) {
                account.setAvatarUrl(normalizeAvatarUrl(avatar));
            }
        }

        if (social != null) {
            account.setFollowers(intVal(social, "followers"));
            account.setFollowing(intVal(social, "following"));
        }

        if (shop != null) {
            String level = strVal(shop, "level");
            if (level != null && !level.isBlank()) {
                account.setSellerLevel(level);
            }
            account.setFishShopScore(intVal(shop, "score"));
            account.setFishShopUser(boolVal(shop, "superShow"));
            account.setPraiseRatio(strVal(shop, "praiseRatio"));
            account.setReviewNum(intVal(shop, "reviewNum"));
        }

        // 解析 page.nav 返回数据 —— 获取 tabs 中的卖出数
        if (navData != null) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> tabs = (List<Map<String, Object>>) navData.get("tabs");
            if (tabs != null) {
                for (Map<String, Object> tab : tabs) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> item = (Map<String, Object>) tab.get("item");
                    if (item != null) {
                        String type = strVal(item, "type");
                        if ("sold".equals(type)) {
                            account.setSoldCount(intVal(item, "number"));
                            break;
                        }
                    }
                }
            }
        }

        accountMapper.update(account);

        // 更新运行时状态中的 last_sync_time
        LocalDateTime now = LocalDateTime.now();
        if (runtime != null) {
            runtime.setLastSyncTime(now);
            runtimeMapper.update(runtime);
        } else {
            XianyuAccountRuntime newRuntime = new XianyuAccountRuntime();
            newRuntime.setTenantId(tenantId);
            newRuntime.setAccountId(accountId);
            newRuntime.setLastSyncTime(now);
            newRuntime.setOnlineStatus(0);
            newRuntime.setWsStatus(0);
            runtimeMapper.insert(newRuntime);
        }

        log.info("刷新账号资料成功: id={}, unb={}, tenantId={}", accountId, unb, tenantId);
        return detail(tenantId, accountId);
    }

    @Transactional
    public AccountAuthStatusResult checkAuthStatus(Long tenantId, Long accountId, String source) {
        return accountAuthStatusService.check(tenantId, accountId, source);
    }

    @Transactional
    public XianyuAccountVO updateCookie(Long tenantId, Long accountId, String cookieText) {
        XianyuAccount account = accountMapper.findById(tenantId, accountId);
        if (account == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }
        if (cookieText == null || cookieText.isBlank()) {
            throw new BizException(400, "Cookie不能为空");
        }

        Map<String, String> cookieMap = parseCookieText(cookieText);
        String externalUid = firstNonBlank(cookieMap.get("unb"), cookieMap.get("userId"), cookieMap.get("userid"));
        if (externalUid == null || externalUid.isBlank()) {
            throw new BizException(400, "Cookie缺少unb，无法确认账号身份");
        }
        if (account.getExternalUid() != null
                && !account.getExternalUid().isBlank()
                && !account.getExternalUid().equals(externalUid)) {
            throw new BizException(400, "Cookie所属账号与当前账号不一致，请确认后重试");
        }

        upsertAuthCookie(tenantId, accountId, cookieText);
        accountAuthStatusService.check(tenantId, accountId, "cookie_updated");
        return detail(tenantId, accountId);
    }

    public Map<String, Object> getLoginCredentialConfig(Long tenantId, Long accountId) {
        requireAccount(tenantId, accountId);
        XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, accountId);
        Map<String, Object> result = new java.util.LinkedHashMap<>();
        result.put("accountId", accountId);
        result.put("loginUsername", auth == null ? null : trimToNull(auth.getLoginUsername()));
        result.put("hasLoginPassword", auth != null && trimToNull(auth.getEncryptedLoginPassword()) != null);
        result.put("showBrowser", auth != null && Boolean.TRUE.equals(auth.getShowBrowser()));
        return result;
    }

    @Transactional
    public Map<String, Object> saveLoginCredentialConfig(Long tenantId, Long accountId, Map<String, Object> body) {
        requireAccount(tenantId, accountId);

        XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, accountId);
        if (auth == null) {
            auth = authMapper.findLatestByAccountIdIncludingDeleted(tenantId, accountId);
        }
        boolean isNew = auth == null;
        if (isNew) {
            auth = new XianyuAccountAuth();
            auth.setTenantId(tenantId);
            auth.setAccountId(accountId);
            auth.setCookieStatus(0);
        } else {
            authMapper.restoreByAccountId(tenantId, accountId);
        }

        String requestedUsername = trimToNull(body == null ? null : body.get("loginUsername"));
        String requestedPassword = trimToNull(body == null ? null : body.get("loginPassword"));
        boolean clearPassword = Boolean.TRUE.equals(boolVal(body, "clearLoginPassword"));
        Boolean requestedShowBrowser = boolVal(body, "showBrowser");
        boolean showBrowser = requestedShowBrowser != null
                ? requestedShowBrowser
                : Boolean.TRUE.equals(auth.getShowBrowser());

        String effectiveUsername = requestedUsername != null ? requestedUsername : trimToNull(auth.getLoginUsername());
        String encryptedLoginPassword = auth.getEncryptedLoginPassword();
        if (clearPassword) {
            encryptedLoginPassword = null;
        }
        if (requestedPassword != null) {
            encryptedLoginPassword = cookieCryptoService.encrypt(requestedPassword);
        }
        if (encryptedLoginPassword != null && effectiveUsername == null) {
            throw new BizException(400, "保存账号密码前请先填写登录账号");
        }

        auth.setTenantId(tenantId);
        auth.setAccountId(accountId);
        auth.setLoginUsername(effectiveUsername);
        auth.setEncryptedLoginPassword(encryptedLoginPassword);
        auth.setShowBrowser(showBrowser);

        if (isNew) {
            authMapper.insert(auth);
        } else {
            authMapper.update(auth);
        }

        return getLoginCredentialConfig(tenantId, accountId);
    }

    /**
     * 清理 avatarUrl 中的错误格式。
     * 修复之前存入库中的 {avatar=http://...} 或 {avatar= "http://..."} 等格式，提取出纯 URL。
     * 同步发送端（DataSyncService）与接收端（SyncReceiveService）写入数据库前必须调用此方法，
     * 防止脏数据在本地→线上链路中传播。
     */
    public static String normalizeAvatarUrl(String url) {
        if (url == null || url.isBlank()) return url;
        String trimmed = url.trim();
        // 尝试直接从字符串中提取 http/https URL
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("https?://[^\\s}\"',]+").matcher(trimmed);
        if (m.find()) {
            return m.group();
        }
        return url;
    }

    private static String strVal(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return null;
        // 处理嵌套 Map：如 avatar 字段返回 {avatar= "http://..."}
        if (val instanceof Map) {
            Map<?, ?> nested = (Map<?, ?>) val;
            // 优先取同名 key
            Object inner = nested.get(key);
            if (inner instanceof String && !((String) inner).isBlank()) {
                return (String) inner;
            }
            // 否则取第一个字符串值
            for (Object v : nested.values()) {
                if (v instanceof String && !((String) v).isBlank()) {
                    return (String) v;
                }
            }
            return null;
        }
        return String.valueOf(val);
    }

    private static Integer intVal(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Number) return ((Number) val).intValue();
        try {
            return Integer.parseInt(String.valueOf(val));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static Boolean boolVal(Map<String, Object> map, String key) {
        if (map == null) return null;
        Object val = map.get(key);
        if (val == null) return null;
        if (val instanceof Boolean) return (Boolean) val;
        return Boolean.parseBoolean(String.valueOf(val));
    }

    private XianyuAccount requireAccount(Long tenantId, Long accountId) {
        XianyuAccount account = accountMapper.findById(tenantId, accountId);
        if (account == null) {
            throw new BizException(404, "闲鱼账号不存在");
        }
        return account;
    }

    private String trimToNull(Object value) {
        if (value == null) return null;
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? null : text;
    }
}
