package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.security.SecureRandom;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * 增长合伙人系统核心服务。
 *
 * 职责：
 * 1. 全局配置读写（token 奖励数 / 最低提现金额 / 代理等级）
 * 2. 邀请码与推广链接生成
 * 3. 注册时绑定推荐关系（一级 / 二级）
 * 4. 消费触发奖励：一级用户获得 Token + 现金分成（按代理等级）
 * 5. 代理等级自动升级
 * 6. 排行榜
 * 7. 提现申请与审批
 * 8. 仪表盘统计（前台 / 后台）
 *
 * 金额单位约定：所有现金金额以「分」存储（BIGINT），对外展示时由前端除以 100 转元。
 */
@Service
public class GrowthService {
    private static final Logger log = LoggerFactory.getLogger(GrowthService.class);
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final String CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
    private static final DateTimeFormatter DAY_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final JdbcTemplate jdbcTemplate;

    public GrowthService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    // ==================== 全局配置 ====================

    public Map<String, Object> getGlobalConfig() {
        Map<String, Object> cfg = jdbcTemplate.queryForList(
                "SELECT * FROM growth_global_config WHERE id=1 LIMIT 1").stream().findFirst().orElse(null);
        if (cfg == null) {
            // 兜底：返回默认值
            Map<String, Object> fallback = new LinkedHashMap<>();
            fallback.put("token_reward_per_referral", 100L);
            fallback.put("min_withdrawal_amount", 5000L);
            fallback.put("first_month_only", 1);
            fallback.put("withdraw_enabled", 1);
            return fallback;
        }
        return cfg;
    }

    @Transactional
    public Map<String, Object> saveGlobalConfig(Long tokenReward, Long minWithdrawal, Integer firstMonthOnly,
                                                 Integer withdrawEnabled, String updatedBy) {
        Long token = tokenReward == null ? 100L : tokenReward;
        Long minWd = minWithdrawal == null ? 5000L : minWithdrawal;
        int fmo = firstMonthOnly == null ? 1 : firstMonthOnly;
        int we = withdrawEnabled == null ? 1 : withdrawEnabled;
        int updated = jdbcTemplate.update(
                "UPDATE growth_global_config SET token_reward_per_referral=?, min_withdrawal_amount=?, first_month_only=?, withdraw_enabled=?, updated_by=?, updated_time=NOW() WHERE id=1",
                token, minWd, fmo, we, updatedBy == null ? "system" : updatedBy);
        if (updated == 0) {
            jdbcTemplate.update(
                    "INSERT INTO growth_global_config(id, token_reward_per_referral, min_withdrawal_amount, first_month_only, withdraw_enabled, updated_by, created_time, updated_time) VALUES(1,?,?,?,?,?,NOW(),NOW())",
                    token, minWd, fmo, we, updatedBy == null ? "system" : updatedBy);
        }
        return getGlobalConfig();
    }

    public long getMinWithdrawalAmount() {
        Map<String, Object> cfg = getGlobalConfig();
        Object v = cfg.get("min_withdrawal_amount");
        if (v == null) return 5000L;
        return ((Number) v).longValue();
    }

    public long getTokenRewardPerReferral() {
        Map<String, Object> cfg = getGlobalConfig();
        Object v = cfg.get("token_reward_per_referral");
        if (v == null) return 100L;
        return ((Number) v).longValue();
    }

    // ==================== 代理等级配置 ====================

    public List<Map<String, Object>> getTierConfigs() {
        return jdbcTemplate.queryForList(
                "SELECT * FROM growth_agent_tier_config WHERE enabled=1 ORDER BY sort_order ASC, id ASC");
    }

    public List<Map<String, Object>> getAllTierConfigs() {
        return jdbcTemplate.queryForList(
                "SELECT * FROM growth_agent_tier_config ORDER BY sort_order ASC, id ASC");
    }

    @Transactional
    public Map<String, Object> upsertTierConfig(Map<String, Object> body) {
        String tierCode = str(body.get("tierCode"));
        if (tierCode == null || tierCode.isBlank()) throw new BizException(400, "等级编码不能为空");
        String tierName = str(body.get("tierName"));
        if (tierName == null || tierName.isBlank()) throw new BizException(400, "等级名称不能为空");
        int sortOrder = intVal(body.get("sortOrder"), 0);
        int minReferrals = intVal(body.get("minReferrals"), 0);
        BigDecimal rate = bd(body.get("commissionRate"), BigDecimal.ZERO);
        if (rate.compareTo(BigDecimal.ZERO) < 0 || rate.compareTo(new BigDecimal("100")) > 0) {
            throw new BizException(400, "分成比例需在 0-100 之间");
        }
        long tokenReward = longVal(body.get("tokenReward"), 100L);
        String icon = str(body.get("icon"));
        String color = str(body.get("color"));
        String badgeUrl = str(body.get("badgeUrl"));
        String description = str(body.get("description"));

        Integer existing = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM growth_agent_tier_config WHERE tier_code=?", Integer.class, tierCode);
        if (existing != null && existing > 0) {
            jdbcTemplate.update(
                    "UPDATE growth_agent_tier_config SET tier_name=?, sort_order=?, min_referrals=?, commission_rate=?, token_reward=?, icon=?, color=?, badge_url=?, description=?, updated_time=NOW() WHERE tier_code=?",
                    tierName, sortOrder, minReferrals, rate, tokenReward, icon, color, badgeUrl, description, tierCode);
        } else {
            jdbcTemplate.update(
                    "INSERT INTO growth_agent_tier_config(tier_code, tier_name, sort_order, min_referrals, commission_rate, token_reward, icon, color, badge_url, description, enabled, created_time, updated_time) VALUES(?,?,?,?,?,?,?,?,?,1,NOW(),NOW())",
                    tierCode, tierName, sortOrder, minReferrals, rate, tokenReward, icon, color, badgeUrl, description);
        }
        return jdbcTemplate.queryForList(
                "SELECT * FROM growth_agent_tier_config WHERE tier_code=? LIMIT 1", tierCode).stream().findFirst().orElse(null);
    }

    /** 查询用户当前代理等级配置 */
    public Map<String, Object> getUserTierConfig(long userId) {
        String tierCode = jdbcTemplate.queryForObject(
                "SELECT COALESCE(tier_code,'normal') FROM growth_user_balance WHERE user_id=?",
                String.class, userId);
        if (tierCode == null) tierCode = "normal";
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT * FROM growth_agent_tier_config WHERE tier_code=? LIMIT 1", tierCode);
        return rows.isEmpty() ? null : rows.get(0);
    }

    // ==================== 邀请码与推广链接 ====================

    /** 为用户生成默认邀请码（若不存在） */
    @Transactional
    public String ensureInviteCode(long userId, long tenantId) {
        List<Map<String, Object>> existing = jdbcTemplate.queryForList(
                "SELECT code FROM growth_invite_code WHERE owner_user_id=? ORDER BY id ASC LIMIT 1", userId);
        if (!existing.isEmpty()) return str(existing.get(0).get("code"));
        String code = generateCode(6);
        jdbcTemplate.update(
                "INSERT INTO growth_invite_code(code, owner_user_id, tenant_id, code_type, created_time, updated_time) VALUES(?,?,?,'code',NOW(),NOW())",
                code, userId, tenantId);
        return code;
    }

    /** 生成推广链接 */
    public String getPromoteLink(long userId, long tenantId, String baseUrl) {
        String code = ensureInviteCode(userId, tenantId);
        String origin = baseUrl == null || baseUrl.isBlank() ? "" : baseUrl.replaceAll("/+$", "");
        return origin + "/register?ref=" + code;
    }

    /** 创建额外邀请码 */
    @Transactional
    public Map<String, Object> createInviteCode(long userId, long tenantId, String channel, String remark) {
        String code = generateCode(6);
        jdbcTemplate.update(
                "INSERT INTO growth_invite_code(code, owner_user_id, tenant_id, code_type, channel, remark, created_time, updated_time) VALUES(?,?,?,'code',?,?,NOW(),NOW())",
                code, userId, tenantId, channel == null ? null : channel, remark);
        return jdbcTemplate.queryForList(
                "SELECT * FROM growth_invite_code WHERE code=?", code).stream().findFirst().orElse(null);
    }

    /** 用户的邀请码列表 */
    public List<Map<String, Object>> listInviteCodes(long userId) {
        return jdbcTemplate.queryForList(
                "SELECT * FROM growth_invite_code WHERE owner_user_id=? ORDER BY id DESC", userId);
    }

    /** 校验邀请码有效性（注册时）并返回归属用户 */
    public Long resolveInviteCodeOwner(String code) {
        if (code == null || code.isBlank()) return null;
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT owner_user_id, expires_at, usage_count FROM growth_invite_code WHERE code=? LIMIT 1", code.trim());
        if (rows.isEmpty()) return null;
        Map<String, Object> row = rows.get(0);
        Object expiresAt = row.get("expires_at");
        if (expiresAt != null) {
            LocalDateTime exp = toLocalDateTime(expiresAt);
            if (exp != null && exp.isBefore(LocalDateTime.now())) return null;
        }
        return ((Number) row.get("owner_user_id")).longValue();
    }

    // ==================== 推荐关系绑定 ====================

    /**
     * 注册成功后绑定推荐关系。幂等：同一 (inviter, invitee) 只绑定一次。
     * invitee 的 referrer_id 也回写到 sys_user。
     */
    @Transactional
    public void bindReferral(long inviteeId, long inviteeTenantId, String inviteCode) {
        if (inviteCode == null || inviteCode.isBlank()) return;
        Long inviterId = resolveInviteCodeOwner(inviteCode);
        if (inviterId == null) return;
        if (inviterId == inviteeId) return; // 不能自己邀请自己

        // 幂等：已存在则跳过
        Integer exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM growth_referral_relation WHERE inviter_id=? AND invitee_id=?",
                Integer.class, inviterId, inviteeId);
        if (exists != null && exists > 0) return;

        // 计算首月分成结束时间（注册后 30 天）
        LocalDateTime firstMonthEnd = LocalDateTime.now().plusDays(30);
        jdbcTemplate.update(
                "INSERT INTO growth_referral_relation(inviter_id, invitee_id, invitee_tenant_id, level, invite_code, first_month_end_at, created_time) VALUES(?,?,?,1,?,?,NOW())",
                inviterId, inviteeId, inviteeTenantId, inviteCode, firstMonthEnd);

        // 回写 sys_user.referrer_id
        jdbcTemplate.update("UPDATE sys_user SET referrer_id=? WHERE id=? AND referrer_id IS NULL", inviterId, inviteeId);

        // 邀请码使用次数 +1
        jdbcTemplate.update("UPDATE growth_invite_code SET usage_count=usage_count+1, updated_time=NOW() WHERE code=?", inviteCode.trim());

        // 确保邀请人存在余额记录，并累计邀请人数
        ensureBalanceRecord(inviterId, inviteeTenantId);
        jdbcTemplate.update(
                "UPDATE growth_user_balance SET total_referrals=total_referrals+1, updated_time=NOW() WHERE user_id=?",
                inviterId);

        // 检查是否升级
        checkAndUpgradeTier(inviterId);

        log.info("增长合伙人：绑定推荐关系 inviter={} invitee={} code={}", inviterId, inviteeId, inviteCode);
    }

    // ==================== 消费触发奖励 ====================

    /**
     * 消费成功后触发奖励（由 PaymentService.markPaid 调用）。
     * 规则：
     * 1. 二级用户首单消费 → 一级用户获得 Token 奖励（按等级 tokenReward 或全局配置）
     * 2. 若处于首月分成窗口 → 按代理等级 commission_rate 计算现金分成
     * 幂等：同一订单不重复发放。
     */
    @Transactional
    public void onConsumptionPaid(long userId, long tenantId, String orderNo, String orderType,
                                   long amountCent, String productTitle) {
        // 仅 vip / token / mall_product 视为有效消费
        if (!"vip".equals(orderType) && !"token".equals(orderType) && !"mall_product".equals(orderType)) return;
        if (amountCent <= 0) return;

        Long inviterId = jdbcTemplate.queryForObject(
                "SELECT referrer_id FROM sys_user WHERE id=?", Long.class, userId);
        if (inviterId == null || inviterId <= 0) return;

        // 幂等：同一订单不重复发放
        Integer dup = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM growth_reward_record WHERE source_order_no=?", Integer.class, orderNo);
        if (dup != null && dup > 0) return;

        // 查询推荐关系，判断是否首月
        List<Map<String, Object>> relations = jdbcTemplate.queryForList(
                "SELECT * FROM growth_referral_relation WHERE inviter_id=? AND invitee_id=? LIMIT 1", inviterId, userId);
        if (relations.isEmpty()) return;
        Map<String, Object> relation = relations.get(0);

        // 首次消费：更新 first_consumed_at
        Object firstConsumed = relation.get("first_consumed_at");
        if (firstConsumed == null) {
            jdbcTemplate.update(
                    "UPDATE growth_referral_relation SET first_consumed_at=NOW() WHERE inviter_id=? AND invitee_id=?",
                    inviterId, userId);
        }

        // Token 奖励（每次首单消费都发）
        Map<String, Object> tierCfg = getUserTierConfig(inviterId);
        long tokenReward = tierCfg != null ? longVal(tierCfg.get("token_reward"), getTokenRewardPerReferral()) : getTokenRewardPerReferral();
        if (tokenReward > 0) {
            grantTokenReward(inviterId, userId, tenantId, orderNo, productTitle, amountCent, tokenReward, tierCfg);
            // 给邀请人加 Token 余额
            jdbcTemplate.update("UPDATE sys_user SET token_balance=token_balance+?, updated_time=NOW() WHERE id=?", tokenReward, inviterId);
            // 写 Token 账本
            jdbcTemplate.update(
                    "INSERT INTO token_balance_ledger(tenant_id, user_id, change_type, change_amount, before_balance, after_balance, ref_type, ref_id, ref_no, remark, created_time) " +
                            "SELECT ?, ?, 'growth_reward', ?, token_balance - ?, token_balance, 'growth_reward', NULL, ?, '增长合伙人邀请奖励', NOW() FROM sys_user WHERE id=?",
                    resolveTenantId(inviterId), inviterId, tokenReward, tokenReward, tokenReward, orderNo, inviterId);
            // 累计 Token 奖励
            ensureBalanceRecord(inviterId, resolveTenantId(inviterId));
            jdbcTemplate.update(
                    "UPDATE growth_user_balance SET total_token_reward=total_token_reward+?, updated_time=NOW() WHERE user_id=?",
                    tokenReward, inviterId);
        }

        // 现金分成：仅首月窗口内
        Object firstMonthEndObj = relation.get("first_month_end_at");
        boolean inFirstMonth = firstMonthEndObj != null
                && toLocalDateTime(firstMonthEndObj) != null
                && toLocalDateTime(firstMonthEndObj).isAfter(LocalDateTime.now());
        // 全局配置 first_month_only=1 时仅首月；=0 时长期分成
        Map<String, Object> gcfg = getGlobalConfig();
        int firstMonthOnly = intVal(gcfg.get("first_month_only"), 1);
        boolean commissionEligible = firstMonthOnly == 1 ? inFirstMonth : true;

        if (commissionEligible && tierCfg != null) {
            BigDecimal rate = bd(tierCfg.get("commission_rate"), BigDecimal.ZERO);
            if (rate.compareTo(BigDecimal.ZERO) > 0) {
                // cash_amount = amountCent * rate / 100
                long cashAmount = BigDecimal.valueOf(amountCent)
                        .multiply(rate)
                        .divide(new BigDecimal("100"), 0, RoundingMode.HALF_UP)
                        .longValue();
                if (cashAmount > 0) {
                    grantCashCommission(inviterId, userId, tenantId, orderNo, productTitle, amountCent, cashAmount, rate);
                    // 累计收益与可提现余额
                    jdbcTemplate.update(
                            "UPDATE growth_user_balance SET total_earnings=total_earnings+?, available_balance=available_balance+?, updated_time=NOW() WHERE user_id=?",
                            cashAmount, cashAmount, inviterId);
                    // 同步 sys_user.balance
                    jdbcTemplate.update("UPDATE sys_user SET balance=balance+?, updated_time=NOW() WHERE id=?", cashAmount, inviterId);
                }
            }
        }

        // 被邀请人产生有效消费 → 邀请人 valid_referrals +1
        if (firstConsumed == null) {
            jdbcTemplate.update(
                    "UPDATE growth_user_balance SET valid_referrals=valid_referrals+1, updated_time=NOW() WHERE user_id=?",
                    inviterId);
            checkAndUpgradeTier(inviterId);
        }
        log.info("增长合伙人：消费触发奖励 inviter={} invitee={} orderNo={} amount={} token={}",
                inviterId, userId, orderNo, amountCent, tokenReward);
    }

    private void grantTokenReward(long inviterId, long inviteeId, long inviteeTenantId,
                                  String orderNo, String product, long amountCent, long tokenReward, Map<String, Object> tierCfg) {
        BigDecimal rate = tierCfg != null ? bd(tierCfg.get("commission_rate"), BigDecimal.ZERO) : BigDecimal.ZERO;
        jdbcTemplate.update(
                "INSERT INTO growth_reward_record(inviter_id, invitee_id, invitee_tenant_id, reward_type, level, source_amount, source_order_no, source_product, commission_rate, token_amount, cash_amount, status, settled_at, created_time) " +
                        "VALUES(?,?,?,'token',1,?,?,?,?,?,0,'settled',NOW(),NOW())",
                inviterId, inviteeId, inviteeTenantId, amountCent, orderNo, product, rate, tokenReward);
    }

    private void grantCashCommission(long inviterId, long inviteeId, long inviteeTenantId,
                                      String orderNo, String product, long amountCent, long cashAmount, BigDecimal rate) {
        jdbcTemplate.update(
                "INSERT INTO growth_reward_record(inviter_id, invitee_id, invitee_tenant_id, reward_type, level, source_amount, source_order_no, source_product, commission_rate, token_amount, cash_amount, status, settled_at, created_time) " +
                        "VALUES(?,?,?,'cash',1,?,?,?,?,0,?,'settled',NOW(),NOW())",
                inviterId, inviteeId, inviteeTenantId, amountCent, orderNo, product, rate, cashAmount);
    }

    // ==================== 代理等级自动升级 ====================

    /** 根据有效邀请人数自动升级代理等级（只升不降） */
    @Transactional
    public boolean checkAndUpgradeTier(long userId) {
        ensureBalanceRecord(userId, resolveTenantId(userId));
        Integer validReferrals = jdbcTemplate.queryForObject(
                "SELECT COALESCE(valid_referrals,0) FROM growth_user_balance WHERE user_id=?", Integer.class, userId);
        int valid = validReferrals == null ? 0 : validReferrals;
        String currentTier = jdbcTemplate.queryForObject(
                "SELECT COALESCE(tier_code,'normal') FROM growth_user_balance WHERE user_id=?", String.class, userId);

        // 查找满足 min_referrals <= valid 且 sort_order 最大的等级（只升不降）
        List<Map<String, Object>> candidates = jdbcTemplate.queryForList(
                "SELECT tier_code, sort_order, tier_name FROM growth_agent_tier_config WHERE enabled=1 AND min_referrals<=? ORDER BY sort_order DESC", valid);
        if (candidates.isEmpty()) return false;
        String targetTier = str(candidates.get(0).get("tier_code"));
        if (targetTier == null || targetTier.equals(currentTier)) return false;

        // 校验目标等级排序高于当前等级（只升不降）
        int currentSort = jdbcTemplate.queryForObject(
                "SELECT COALESCE(sort_order,0) FROM growth_agent_tier_config WHERE tier_code=?", Integer.class, currentTier);
        int targetSort = ((Number) candidates.get(0).get("sort_order")).intValue();
        if (targetSort <= currentSort) return false;

        jdbcTemplate.update(
                "UPDATE growth_user_balance SET tier_code=?, tier_updated_at=NOW(), updated_time=NOW() WHERE user_id=?",
                targetTier, userId);
        log.info("增长合伙人：代理等级升级 userId={} {} -> {}", userId, currentTier, targetTier);
        return true;
    }

    // ==================== 余额记录 ====================

    private void ensureBalanceRecord(long userId, long tenantId) {
        Integer exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM growth_user_balance WHERE user_id=?", Integer.class, userId);
        if (exists != null && exists > 0) return;
        try {
            jdbcTemplate.update(
                    "INSERT INTO growth_user_balance(user_id, tenant_id, tier_code, created_time, updated_time) VALUES(?,?,'normal',NOW(),NOW())",
                    userId, tenantId == 0 ? resolveTenantId(userId) : tenantId);
        } catch (Exception ignored) {
            // 并发可能冲突，忽略
        }
    }

    private long resolveTenantId(long userId) {
        try {
            Long t = jdbcTemplate.queryForObject(
                    "SELECT tenant_id FROM sys_user WHERE id=?", Long.class, userId);
            return t == null ? 0L : t;
        } catch (Exception e) {
            return 0L;
        }
    }

    // ==================== 排行榜 ====================

    /** 拉新排行榜 TOP N */
    public List<Map<String, Object>> getLeaderboard(int limit) {
        if (limit <= 0 || limit > 100) limit = 10;
        return jdbcTemplate.queryForList(
                "SELECT b.user_id, b.tier_code, b.valid_referrals, b.total_earnings, b.total_token_reward, " +
                        "       COALESCE(u.nickname, u.username, CONCAT('用户', b.user_id)) AS nickname, u.avatar " +
                        "FROM growth_user_balance b LEFT JOIN sys_user u ON u.id=b.user_id " +
                        "WHERE b.valid_referrals > 0 ORDER BY b.valid_referrals DESC, b.total_earnings DESC LIMIT ?", limit);
    }

    // ==================== 提现 ====================

    @Transactional
    public Map<String, Object> requestWithdrawal(long userId, long tenantId, long amountCent,
                                                   String paymentMethod, String paymentAccount, String paymentName) {
        if (amountCent <= 0) throw new BizException(400, "提现金额必须大于 0");
        long minWd = getMinWithdrawalAmount();
        if (amountCent < minWd) throw new BizException(400, "最低提现金额为 " + (minWd / 100.0) + " 元");
        Map<String, Object> gcfg = getGlobalConfig();
        int withdrawEnabled = intVal(gcfg.get("withdraw_enabled"), 1);
        if (withdrawEnabled != 1) throw new BizException(400, "提现功能暂未开放");

        ensureBalanceRecord(userId, tenantId);
        Map<String, Object> bal = jdbcTemplate.queryForList(
                "SELECT available_balance, frozen_balance FROM growth_user_balance WHERE user_id=? FOR UPDATE", userId)
                .stream().findFirst().orElseThrow(() -> new BizException(400, "余额记录不存在"));
        long available = longVal(bal.get("available_balance"), 0L);
        if (amountCent > available) throw new BizException(400, "可提现余额不足");

        // 冻结金额
        jdbcTemplate.update(
                "UPDATE growth_user_balance SET available_balance=available_balance-?, frozen_balance=frozen_balance+?, updated_time=NOW() WHERE user_id=?",
                amountCent, amountCent, userId);
        // 同步 sys_user.balance
        jdbcTemplate.update("UPDATE sys_user SET balance=balance-?, updated_time=NOW() WHERE id=?", amountCent, userId);

        validPaymentMethod(paymentMethod);
        jdbcTemplate.update(
                "INSERT INTO growth_withdrawal_request(user_id, tenant_id, amount, payment_method, payment_account, payment_name, status, created_time, updated_time) " +
                        "VALUES(?,?,?,?,?,?,'pending',NOW(),NOW())",
                userId, tenantId, amountCent, paymentMethod, paymentAccount, paymentName);
        Long wdId = jdbcTemplate.queryForObject(
                "SELECT LAST_INSERT_ID()", Long.class);
        return jdbcTemplate.queryForList(
                "SELECT * FROM growth_withdrawal_request WHERE id=?", wdId).stream().findFirst().orElse(null);
    }

    private void validPaymentMethod(String method) {
        if (method == null) throw new BizException(400, "请选择收款方式");
        Set<String> allowed = Set.of("wechat_qr", "alipay_qr", "alipay_account", "bank_card");
        if (!allowed.contains(method)) throw new BizException(400, "不支持的收款方式");
    }

    /** 用户提现记录 */
    public List<Map<String, Object>> listUserWithdrawals(long userId, int page, int size) {
        int offset = Math.max(0, (page - 1) * size);
        return jdbcTemplate.queryForList(
                "SELECT * FROM growth_withdrawal_request WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                userId, size, offset);
    }

    @Transactional
    public Map<String, Object> approveWithdrawal(long wdId, String reviewer, boolean approve, String rejectReason) {
        Map<String, Object> wd = jdbcTemplate.queryForList(
                "SELECT * FROM growth_withdrawal_request WHERE id=? FOR UPDATE", wdId)
                .stream().findFirst().orElseThrow(() -> new BizException(404, "提现申请不存在"));
        String status = str(wd.get("status"));
        if (!"pending".equals(status)) throw new BizException(400, "该申请已处理");

        long userId = longVal(wd.get("user_id"), 0L);
        long amount = longVal(wd.get("amount"), 0L);

        if (approve) {
            // 通过：从冻结转为已提现
            jdbcTemplate.update(
                    "UPDATE growth_withdrawal_request SET status='approved', reviewed_by=?, reviewed_at=NOW(), paid_at=NOW(), updated_time=NOW() WHERE id=?",
                    reviewer, wdId);
            jdbcTemplate.update(
                    "UPDATE growth_user_balance SET frozen_balance=frozen_balance-?, withdrawn_amount=withdrawn_amount+?, updated_time=NOW() WHERE user_id=?",
                    amount, amount, userId);
        } else {
            // 驳回：冻结金额退回可提现
            jdbcTemplate.update(
                    "UPDATE growth_withdrawal_request SET status='rejected', reviewed_by=?, reviewed_at=NOW(), reject_reason=?, updated_time=NOW() WHERE id=?",
                    reviewer, rejectReason, wdId);
            jdbcTemplate.update(
                    "UPDATE growth_user_balance SET frozen_balance=frozen_balance-?, available_balance=available_balance+?, updated_time=NOW() WHERE user_id=?",
                    amount, amount, userId);
            // 退回 sys_user.balance
            jdbcTemplate.update("UPDATE sys_user SET balance=balance+?, updated_time=NOW() WHERE id=?", amount, userId);
        }
        return jdbcTemplate.queryForList(
                "SELECT * FROM growth_withdrawal_request WHERE id=?", wdId).stream().findFirst().orElse(null);
    }

    // ==================== 仪表盘统计 ====================

    /** 前台用户仪表盘 */
    public Map<String, Object> getUserDashboard(long userId, long tenantId) {
        ensureBalanceRecord(userId, tenantId);
        Map<String, Object> bal = jdbcTemplate.queryForList(
                "SELECT * FROM growth_user_balance WHERE user_id=? LIMIT 1", userId)
                .stream().findFirst().orElse(new HashMap<>());
        long totalReferrals = longVal(bal.get("total_referrals"), 0L);
        long validReferrals = longVal(bal.get("valid_referrals"), 0L);
        long totalEarnings = longVal(bal.get("total_earnings"), 0L);
        long availableBalance = longVal(bal.get("available_balance"), 0L);
        long totalTokenReward = longVal(bal.get("total_token_reward"), 0L);
        long withdrawnAmount = longVal(bal.get("withdrawn_amount"), 0L);
        long frozenBalance = longVal(bal.get("frozen_balance"), 0L);
        String tierCode = str(bal.get("tier_code"));
        if (tierCode == null) tierCode = "normal";

        Map<String, Object> dashboard = new LinkedHashMap<>();
        dashboard.put("totalReferrals", totalReferrals);
        dashboard.put("validReferrals", validReferrals);
        dashboard.put("totalEarnings", totalEarnings);
        dashboard.put("availableBalance", availableBalance);
        dashboard.put("totalTokenReward", totalTokenReward);
        dashboard.put("withdrawnAmount", withdrawnAmount);
        dashboard.put("frozenBalance", frozenBalance);
        dashboard.put("tierCode", tierCode);
        dashboard.put("tierConfig", getUserTierConfig(userId));
        dashboard.put("minWithdrawalAmount", getMinWithdrawalAmount());
        dashboard.put("tokenRewardPerReferral", getTokenRewardPerReferral());
        dashboard.put("tierConfigs", getTierConfigs());

        // 上月对比
        Map<String, Object> lastMonth = getLastMonthStats(userId);
        dashboard.put("lastMonth", lastMonth);
        return dashboard;
    }

    private Map<String, Object> getLastMonthStats(long userId) {
        LocalDateTime monthStart = LocalDate.now().minusMonths(1).withDayOfMonth(1).atStartOfDay();
        LocalDateTime monthEnd = LocalDate.now().withDayOfMonth(1).atStartOfDay();
        Map<String, Object> stats = new LinkedHashMap<>();
        try {
            Long earnings = jdbcTemplate.queryForObject(
                    "SELECT COALESCE(SUM(cash_amount),0) FROM growth_reward_record WHERE inviter_id=? AND created_time>=? AND created_time<?",
                    Long.class, userId, monthStart, monthEnd);
            Long tokens = jdbcTemplate.queryForObject(
                    "SELECT COALESCE(SUM(token_amount),0) FROM growth_reward_record WHERE inviter_id=? AND created_time>=? AND created_time<?",
                    Long.class, userId, monthStart, monthEnd);
            stats.put("earnings", earnings == null ? 0L : earnings);
            stats.put("tokens", tokens == null ? 0L : tokens);
        } catch (Exception e) {
            stats.put("earnings", 0L);
            stats.put("tokens", 0L);
        }
        return stats;
    }

    /** 收益趋势（近 30 天） */
    public Map<String, Object> getRevenueTrend(long userId, int days) {
        if (days <= 0 || days > 90) days = 30;
        LocalDate today = LocalDate.now();
        LocalDate start = today.minusDays(days - 1L);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT DATE(created_time) AS d, COALESCE(SUM(cash_amount),0) AS cash, COALESCE(SUM(token_amount),0) AS token " +
                        "FROM growth_reward_record WHERE inviter_id=? AND created_time>=? GROUP BY DATE(created_time) ORDER BY d ASC",
                userId, start.atStartOfDay());

        Map<String, Object> result = new LinkedHashMap<>();
        List<String> dates = new ArrayList<>();
        List<Long> cashSeries = new ArrayList<>();
        List<Long> tokenSeries = new ArrayList<>();
        // 填充空日期
        Map<String, Map<String, Object>> map = new LinkedHashMap<>();
        for (Map<String, Object> r : rows) {
            Object d = r.get("d");
            String key = d == null ? "" : d.toString();
            map.put(key, r);
        }
        long totalCash = 0, totalToken = 0;
        for (int i = 0; i < days; i++) {
            LocalDate d = start.plusDays(i);
            String key = d.format(DAY_FMT);
            dates.add(key);
            Map<String, Object> r = map.get(key);
            long cash = r == null ? 0L : longVal(r.get("cash"), 0L);
            long token = r == null ? 0L : longVal(r.get("token"), 0L);
            cashSeries.add(cash);
            tokenSeries.add(token);
            totalCash += cash;
            totalToken += token;
        }
        result.put("dates", dates);
        result.put("cashSeries", cashSeries);
        result.put("tokenSeries", tokenSeries);
        result.put("totalCash", totalCash);
        result.put("totalToken", totalToken);
        return result;
    }

    /** 二级用户明细（被邀请人消费记录） */
    public Map<String, Object> listReferralDetails(long userId, int page, int size, String keyword, String tierCode, String status) {
        int offset = Math.max(0, (page - 1) * size);
        StringBuilder where = new StringBuilder("WHERE rel.inviter_id=? ");
        List<Object> params = new ArrayList<>();
        params.add(userId);
        if (keyword != null && !keyword.isBlank()) {
            where.append("AND (u.nickname LIKE ? OR u.email LIKE ?) ");
            params.add("%" + keyword + "%");
            params.add("%" + keyword + "%");
        }
        if (status != null && !status.isBlank()) {
            where.append("AND rel.reward_type=? ");
            params.add(status);
        }

        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM growth_referral_relation rel LEFT JOIN sys_user u ON u.id=rel.invitee_id " + where,
                Long.class, params.toArray());
        if (total == null) total = 0L;

        // SQL 占位符顺序：4 个子查询的 inviter_id=? + where 子句参数 + LIMIT ? + OFFSET ?
        List<Object> pageParams = new ArrayList<>();
        pageParams.add(userId); // subquery 1: total_consume
        pageParams.add(userId); // subquery 2: total_earn
        pageParams.add(userId); // subquery 3: total_token
        pageParams.add(userId); // subquery 4: products
        pageParams.addAll(params); // where 子句参数（rel.inviter_id=? + 可选 keyword/status）
        pageParams.add(size);
        pageParams.add(offset);
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT rel.invitee_id, rel.created_time AS register_time, rel.first_consumed_at, " +
                        "COALESCE(u.nickname, u.username, CONCAT('用户', rel.invitee_id)) AS nickname, u.avatar, " +
                        "(SELECT COALESCE(SUM(source_amount),0) FROM growth_reward_record WHERE inviter_id=? AND invitee_id=rel.invitee_id) AS total_consume, " +
                        "(SELECT COALESCE(SUM(cash_amount),0) FROM growth_reward_record WHERE inviter_id=? AND invitee_id=rel.invitee_id) AS total_earn, " +
                        "(SELECT COALESCE(SUM(token_amount),0) FROM growth_reward_record WHERE inviter_id=? AND invitee_id=rel.invitee_id) AS total_token, " +
                        "(SELECT GROUP_CONCAT(DISTINCT source_product) FROM growth_reward_record WHERE inviter_id=? AND invitee_id=rel.invitee_id) AS products " +
                        "FROM growth_referral_relation rel LEFT JOIN sys_user u ON u.id=rel.invitee_id " +
                        where + "ORDER BY rel.id DESC LIMIT ? OFFSET ?",
                pageParams.toArray());

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", total);
        result.put("list", records);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    // ==================== 后台统计 ====================

    /** 后台增长中心仪表盘 */
    public Map<String, Object> getAdminDashboard() {
        Map<String, Object> dashboard = new LinkedHashMap<>();

        // 总体统计
        Long totalUsers = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE deleted=0", Long.class);
        Long totalReferrers = jdbcTemplate.queryForObject("SELECT COUNT(DISTINCT inviter_id) FROM growth_referral_relation", Long.class);
        Long totalReferrals = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM growth_referral_relation", Long.class);
        Long validReferrals = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM growth_referral_relation WHERE first_consumed_at IS NOT NULL", Long.class);
        Long totalEarnings = jdbcTemplate.queryForObject("SELECT COALESCE(SUM(cash_amount),0) FROM growth_reward_record", Long.class);
        Long totalTokenReward = jdbcTemplate.queryForObject("SELECT COALESCE(SUM(token_amount),0) FROM growth_reward_record", Long.class);
        Long totalWithdrawn = jdbcTemplate.queryForObject("SELECT COALESCE(SUM(withdrawn_amount),0) FROM growth_user_balance", Long.class);
        Long pendingWithdrawals = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM growth_withdrawal_request WHERE status='pending'", Long.class);
        Long totalInviteCodes = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM growth_invite_code", Long.class);
        Long totalCommissionPaid = jdbcTemplate.queryForObject("SELECT COALESCE(SUM(cash_amount),0) FROM growth_reward_record WHERE reward_type='cash'", Long.class);

        dashboard.put("totalUsers", totalUsers == null ? 0L : totalUsers);
        dashboard.put("totalReferrers", totalReferrers == null ? 0L : totalReferrers);
        dashboard.put("totalReferrals", totalReferrals == null ? 0L : totalReferrals);
        dashboard.put("validReferrals", validReferrals == null ? 0L : validReferrals);
        dashboard.put("totalEarnings", totalEarnings == null ? 0L : totalEarnings);
        dashboard.put("totalTokenReward", totalTokenReward == null ? 0L : totalTokenReward);
        dashboard.put("totalWithdrawn", totalWithdrawn == null ? 0L : totalWithdrawn);
        dashboard.put("pendingWithdrawals", pendingWithdrawals == null ? 0L : pendingWithdrawals);
        dashboard.put("totalInviteCodes", totalInviteCodes == null ? 0L : totalInviteCodes);
        dashboard.put("totalCommissionPaid", totalCommissionPaid == null ? 0L : totalCommissionPaid);

        // 等级分布
        List<Map<String, Object>> tierDist = jdbcTemplate.queryForList(
                "SELECT tier_code, COUNT(*) AS cnt FROM growth_user_balance GROUP BY tier_code");
        dashboard.put("tierDistribution", tierDist);

        // 近 30 天趋势
        dashboard.put("trend", getAdminRevenueTrend(30));

        // TOP 10 排行
        dashboard.put("leaderboard", getLeaderboard(10));

        // 全局配置
        dashboard.put("config", getGlobalConfig());

        return dashboard;
    }

    public Map<String, Object> getAdminRevenueTrend(int days) {
        if (days <= 0 || days > 90) days = 30;
        LocalDate start = LocalDate.now().minusDays(days - 1L);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT DATE(created_time) AS d, COALESCE(SUM(cash_amount),0) AS cash, COALESCE(SUM(token_amount),0) AS token, COUNT(*) AS cnt " +
                        "FROM growth_reward_record WHERE created_time>=? GROUP BY DATE(created_time) ORDER BY d ASC",
                start.atStartOfDay());
        Map<String, Object> result = new LinkedHashMap<>();
        List<String> dates = new ArrayList<>();
        List<Long> cashSeries = new ArrayList<>();
        List<Long> tokenSeries = new ArrayList<>();
        List<Long> countSeries = new ArrayList<>();
        Map<String, Map<String, Object>> map = new LinkedHashMap<>();
        for (Map<String, Object> r : rows) {
            Object d = r.get("d");
            map.put(d == null ? "" : d.toString(), r);
        }
        for (int i = 0; i < days; i++) {
            LocalDate d = start.plusDays(i);
            String key = d.format(DAY_FMT);
            dates.add(key);
            Map<String, Object> r = map.get(key);
            cashSeries.add(r == null ? 0L : longVal(r.get("cash"), 0L));
            tokenSeries.add(r == null ? 0L : longVal(r.get("token"), 0L));
            countSeries.add(r == null ? 0L : longVal(r.get("cnt"), 0L));
        }
        result.put("dates", dates);
        result.put("cashSeries", cashSeries);
        result.put("tokenSeries", tokenSeries);
        result.put("countSeries", countSeries);
        return result;
    }

    /** 后台提现列表 */
    public Map<String, Object> adminListWithdrawals(String status, int page, int size) {
        int offset = Math.max(0, (page - 1) * size);
        StringBuilder where = new StringBuilder("WHERE 1=1 ");
        List<Object> params = new ArrayList<>();
        if (status != null && !status.isBlank() && !"all".equals(status)) {
            where.append("AND status=? ");
            params.add(status);
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM growth_withdrawal_request " + where, Long.class, params.toArray());
        if (total == null) total = 0L;
        params.add(size);
        params.add(offset);
        List<Map<String, Object>> list = jdbcTemplate.queryForList(
                "SELECT w.*, COALESCE(u.nickname, u.username, CONCAT('用户', w.user_id)) AS nickname, u.email " +
                        "FROM growth_withdrawal_request w LEFT JOIN sys_user u ON u.id=w.user_id " +
                        where + "ORDER BY w.id DESC LIMIT ? OFFSET ?", params.toArray());
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", total);
        result.put("list", list);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    /** 后台邀请码列表 */
    public Map<String, Object> adminListInviteCodes(int page, int size, String keyword) {
        int offset = Math.max(0, (page - 1) * size);
        StringBuilder where = new StringBuilder("WHERE 1=1 ");
        List<Object> params = new ArrayList<>();
        if (keyword != null && !keyword.isBlank()) {
            where.append("AND (c.code LIKE ? OR u.nickname LIKE ? OR u.email LIKE ?) ");
            String kw = "%" + keyword + "%";
            params.add(kw);
            params.add(kw);
            params.add(kw);
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM growth_invite_code c LEFT JOIN sys_user u ON u.id=c.owner_user_id " + where,
                Long.class, params.toArray());
        if (total == null) total = 0L;
        params.add(size);
        params.add(offset);
        List<Map<String, Object>> list = jdbcTemplate.queryForList(
                "SELECT c.*, COALESCE(u.nickname, u.username, CONCAT('用户', c.owner_user_id)) AS owner_name, u.email " +
                        "FROM growth_invite_code c LEFT JOIN sys_user u ON u.id=c.owner_user_id " +
                        where + "ORDER BY c.id DESC LIMIT ? OFFSET ?", params.toArray());
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", total);
        result.put("list", list);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    /** 后台全部推荐关系 */
    public Map<String, Object> adminListReferrals(int page, int size, String keyword) {
        int offset = Math.max(0, (page - 1) * size);
        StringBuilder where = new StringBuilder("WHERE 1=1 ");
        List<Object> params = new ArrayList<>();
        if (keyword != null && !keyword.isBlank()) {
            where.append("AND (inv.nickname LIKE ? OR inv.email LIKE ? OR ite.nickname LIKE ? OR ite.email LIKE ?) ");
            String kw = "%" + keyword + "%";
            params.add(kw);
            params.add(kw);
            params.add(kw);
            params.add(kw);
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM growth_referral_relation r " +
                        "LEFT JOIN sys_user inv ON inv.id=r.inviter_id LEFT JOIN sys_user ite ON ite.id=r.invitee_id " + where,
                Long.class, params.toArray());
        if (total == null) total = 0L;
        params.add(size);
        params.add(offset);
        List<Map<String, Object>> list = jdbcTemplate.queryForList(
                "SELECT r.*, " +
                        "COALESCE(inv.nickname, inv.username, CONCAT('用户', r.inviter_id)) AS inviter_name, inv.email AS inviter_email, " +
                        "COALESCE(ite.nickname, ite.username, CONCAT('用户', r.invitee_id)) AS invitee_name, ite.email AS invitee_email " +
                        "FROM growth_referral_relation r " +
                        "LEFT JOIN sys_user inv ON inv.id=r.inviter_id LEFT JOIN sys_user ite ON ite.id=r.invitee_id " +
                        where + "ORDER BY r.id DESC LIMIT ? OFFSET ?", params.toArray());
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", total);
        result.put("list", list);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    // ==================== 工具方法 ====================

    private String generateCode(int length) {
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            sb.append(CODE_CHARS.charAt(RANDOM.nextInt(CODE_CHARS.length())));
        }
        return sb.toString();
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o).trim();
    }

    private static int intVal(Object o, int def) {
        if (o == null) return def;
        try {
            return Integer.parseInt(String.valueOf(o));
        } catch (Exception e) {
            return def;
        }
    }

    private static long longVal(Object o, long def) {
        if (o == null) return def;
        try {
            return Long.parseLong(String.valueOf(o));
        } catch (Exception e) {
            try {
                return ((Number) o).longValue();
            } catch (Exception ex) {
                return def;
            }
        }
    }

    private static BigDecimal bd(Object o, BigDecimal def) {
        if (o == null) return def;
        try {
            return new BigDecimal(String.valueOf(o));
        } catch (Exception e) {
            return def;
        }
    }

    private static LocalDateTime toLocalDateTime(Object o) {
        if (o == null) return null;
        if (o instanceof LocalDateTime) return (LocalDateTime) o;
        if (o instanceof java.util.Date) {
            return ((java.util.Date) o).toInstant()
                    .atZone(java.time.ZoneId.systemDefault())
                    .toLocalDateTime();
        }
        try {
            return LocalDateTime.parse(String.valueOf(o).replace(' ', 'T'));
        } catch (Exception e) {
            return null;
        }
    }
}
