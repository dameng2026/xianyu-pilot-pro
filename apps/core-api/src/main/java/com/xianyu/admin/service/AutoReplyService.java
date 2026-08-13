package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.AutoReplyRuleDTO;
import com.xianyu.admin.dto.AutoReplyRuleVO;
import com.xianyu.admin.entity.AutoReplyLog;
import com.xianyu.admin.entity.AutoReplyRule;
import com.xianyu.admin.mapper.AutoReplyLogMapper;
import com.xianyu.admin.mapper.AutoReplyRuleMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

@Service
public class AutoReplyService {
    private static final Logger log = LoggerFactory.getLogger(AutoReplyService.class);

    private final AutoReplyRuleMapper ruleMapper;
    private final AutoReplyLogMapper logMapper;

    public AutoReplyService(AutoReplyRuleMapper ruleMapper, AutoReplyLogMapper logMapper) {
        this.ruleMapper = ruleMapper;
        this.logMapper = logMapper;
    }

    /**
     * 分页查询自动回复规则列表
     */
    public PageResult<AutoReplyRuleVO> rules(Long tenantId, Long accountId, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = ruleMapper.count(tenantId, accountId);
        List<AutoReplyRule> list = ruleMapper.list(tenantId, accountId, offset, limit);

        List<AutoReplyRuleVO> records = new ArrayList<>();
        for (AutoReplyRule r : list) {
            records.add(toVO(r));
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 创建自动回复规则
     */
    @Transactional
    public void createRule(Long tenantId, AutoReplyRuleDTO dto) {
        AutoReplyRule rule = new AutoReplyRule();
        rule.setTenantId(tenantId);
        rule.setAccountId(dto.getAccountId());
        rule.setXyGoodsId(dto.getXyGoodsId());
        rule.setRuleName(dto.getRuleName());
        rule.setMatchType(dto.getMatchType());
        rule.setMatchKeywords(dto.getMatchKeywords());
        rule.setReplyContent(dto.getReplyContent());
        rule.setReplyImage(dto.getReplyImage());
        rule.setReplyMode(dto.getReplyMode());
        rule.setStatus(dto.getStatus() != null ? dto.getStatus() : 1);
        rule.setPriority(dto.getPriority() != null ? dto.getPriority() : 0);
        rule.setSafeMode(dto.getSafeMode() != null ? dto.getSafeMode() : 1);
        rule.setHandoffKeywords(dto.getHandoffKeywords());
        rule.setPriceFloor(dto.getPriceFloor());
        rule.setMaxDailyReplies(dto.getMaxDailyReplies() != null ? dto.getMaxDailyReplies() : 0);
        ruleMapper.insert(rule);
        log.info("创建自动回复规则成功: id={}, tenantId={}", rule.getId(), tenantId);
    }

    /**
     * 更新自动回复规则
     */
    @Transactional
    public void updateRule(Long tenantId, Long id, AutoReplyRuleDTO dto) {
        AutoReplyRule existing = ruleMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "自动回复规则不存在");
        }

        AutoReplyRule rule = new AutoReplyRule();
        rule.setId(id);
        rule.setTenantId(tenantId);
        rule.setAccountId(dto.getAccountId() != null ? dto.getAccountId() : existing.getAccountId());
        rule.setXyGoodsId(dto.getXyGoodsId() != null ? dto.getXyGoodsId() : existing.getXyGoodsId());
        rule.setRuleName(dto.getRuleName() != null ? dto.getRuleName() : existing.getRuleName());
        rule.setMatchType(dto.getMatchType() != null ? dto.getMatchType() : existing.getMatchType());
        rule.setMatchKeywords(dto.getMatchKeywords() != null ? dto.getMatchKeywords() : existing.getMatchKeywords());
        rule.setReplyContent(dto.getReplyContent() != null ? dto.getReplyContent() : existing.getReplyContent());
        rule.setReplyImage(dto.getReplyImage() != null ? dto.getReplyImage() : existing.getReplyImage());
        rule.setReplyMode(dto.getReplyMode() != null ? dto.getReplyMode() : existing.getReplyMode());
        rule.setStatus(dto.getStatus() != null ? dto.getStatus() : existing.getStatus());
        rule.setPriority(dto.getPriority() != null ? dto.getPriority() : existing.getPriority());
        rule.setSafeMode(dto.getSafeMode() != null ? dto.getSafeMode() : existing.getSafeMode());
        rule.setHandoffKeywords(dto.getHandoffKeywords() != null ? dto.getHandoffKeywords() : existing.getHandoffKeywords());
        rule.setPriceFloor(dto.getPriceFloor() != null ? dto.getPriceFloor() : existing.getPriceFloor());
        rule.setMaxDailyReplies(dto.getMaxDailyReplies() != null ? dto.getMaxDailyReplies() : existing.getMaxDailyReplies());
        ruleMapper.update(rule);
        log.info("更新自动回复规则成功: id={}, tenantId={}", id, tenantId);
    }

    /**
     * 删除自动回复规则（软删除）
     */
    @Transactional
    public void deleteRule(Long tenantId, Long id) {
        AutoReplyRule existing = ruleMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "自动回复规则不存在");
        }
        ruleMapper.softDelete(tenantId, id);
        log.info("删除自动回复规则: id={}, tenantId={}", id, tenantId);
    }

    private AutoReplyRuleVO toVO(AutoReplyRule r) {
        AutoReplyRuleVO vo = new AutoReplyRuleVO();
        vo.setId(r.getId());
        vo.setAccountId(r.getAccountId());
        vo.setXyGoodsId(r.getXyGoodsId());
        vo.setRuleName(r.getRuleName());
        vo.setMatchType(r.getMatchType());
        vo.setMatchKeywords(r.getMatchKeywords());
        vo.setReplyContent(r.getReplyContent());
        vo.setReplyImage(r.getReplyImage());
        vo.setReplyMode(r.getReplyMode());
        vo.setStatus(r.getStatus());
        vo.setPriority(r.getPriority());
        vo.setSafeMode(r.getSafeMode());
        vo.setHandoffKeywords(r.getHandoffKeywords());
        vo.setPriceFloor(r.getPriceFloor());
        vo.setMaxDailyReplies(r.getMaxDailyReplies());
        return vo;
    }

    public Map<String, Object> preview(Long tenantId, Long accountId, String message) {
        String text = message == null ? "" : message.trim();
        if (text.isEmpty()) {
            throw new BizException(400, "请输入买家消息");
        }
        List<AutoReplyRule> candidates = ruleMapper.findByAccountIdAndStatus(tenantId, accountId, 1);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("message", text);
        result.put("matched", false);
        result.put("action", "manual");
        result.put("safety", Map.of("blocked", false, "reasons", List.of()));
        for (AutoReplyRule r : candidates) {
            if (!matches(r, text)) continue;
            List<String> reasons = safetyReasons(r, text);
            boolean blocked = !reasons.isEmpty() && (r.getSafeMode() == null || r.getSafeMode() == 1);
            result.put("matched", true);
            result.put("ruleId", r.getId());
            result.put("ruleName", r.getRuleName());
            String action = blocked ? "suggest_only" : "auto_send_allowed";
            if (!blocked && r.getMaxDailyReplies() != null && r.getMaxDailyReplies() > 0) {
                int today = logMapper.countTodayByRule(tenantId, r.getId());
                if (today >= r.getMaxDailyReplies()) {
                    blocked = true;
                    action = "suggest_only";
                    reasons.add("已达到该规则每日自动回复上限：" + r.getMaxDailyReplies());
                }
            }
            result.put("replyMode", r.getReplyMode());
            result.put("replySuggestion", r.getReplyContent());
            result.put("action", action);
            result.put("safety", Map.of("blocked", blocked, "reasons", reasons));
            insertPreviewLog(tenantId, accountId, r, text, action, reasons);
            return result;
        }
        result.put("replySuggestion", "未命中自动回复规则，建议人工处理或新增规则。");
        insertPreviewLog(tenantId, accountId, null, text, "manual", List.of("未命中规则"));
        return result;
    }

    public PageResult<Map<String, Object>> logs(Long tenantId, Long accountId, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int total = logMapper.count(tenantId, accountId);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (AutoReplyLog l : logMapper.list(tenantId, accountId, offset, safeSize)) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", l.getId());
            m.put("accountId", l.getAccountId());
            m.put("conversationId", l.getConversationId());
            m.put("ruleId", l.getRuleId());
            m.put("triggerMessage", maskText(l.getTriggerMessage()));
            m.put("replyContent", maskText(l.getReplyContent()));
            m.put("hitType", l.getHitType());
            m.put("status", l.getStatus());
            m.put("failReason", l.getFailReason());
            m.put("action", l.getAction());
            m.put("safetyReasons", l.getSafetyReasons());
            m.put("createdTime", l.getCreatedTime());
            rows.add(m);
        }
        return new PageResult<>(rows, safeCurrent, safeSize, total);
    }

    public Map<String, Object> stats(Long tenantId, int days) {
        int safeDays = Math.min(Math.max(days, 1), 90);
        LocalDate start = LocalDate.now().minusDays(safeDays - 1L);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("days", safeDays);
        m.put("todayCount", logMapper.countTodayHits(tenantId));
        m.put("daily", logMapper.countDaily(tenantId, start));
        m.put("actions", logMapper.countByAction(tenantId, start));
        return m;
    }

    private void insertPreviewLog(Long tenantId, Long accountId, AutoReplyRule rule, String message, String action, List<String> reasons) {
        AutoReplyLog log = new AutoReplyLog();
        log.setTenantId(tenantId);
        log.setAccountId(accountId);
        log.setRuleId(rule == null ? null : rule.getId());
        log.setTriggerMessage(abbreviate(message, 1000));
        log.setReplyContent(rule == null ? "" : abbreviate(rule.getReplyContent(), 1000));
        log.setHitType(rule == null ? "none" : ("ai".equalsIgnoreCase(rule.getMatchType()) ? "ai" : "keyword"));
        log.setStatus("auto_send_allowed".equals(action) ? 1 : 2);
        log.setAction(action);
        log.setSafetyReasons(String.join("；", reasons));
        logMapper.insert(log);
    }

    private boolean matches(AutoReplyRule r, String text) {
        String type = r.getMatchType() == null ? "any" : r.getMatchType().toLowerCase();
        String kw = r.getMatchKeywords() == null ? "" : r.getMatchKeywords();
        // AI 意图模式：直接命中（由 reply_mode 决定走 AI 回复）
        if ("ai".equalsIgnoreCase(type)) {
            return true;
        }
        String[] parts = kw.split("[,，\\s]+");
        List<String> keywords = new ArrayList<>();
        for (String p : parts) {
            String trimmed = p.trim();
            if (!trimmed.isEmpty()) keywords.add(trimmed);
        }
        // 正则模式：每个关键词作为正则，任一匹配即命中
        if ("regex".equalsIgnoreCase(type)) {
            for (String k : keywords) {
                try { if (Pattern.compile(k).matcher(text).find()) return true; }
                catch (Exception e) { /* 忽略非法正则 */ }
            }
            return false;
        }
        // 关键词为空时跳过（避免 any/all 模式误命中所有消息）
        if (keywords.isEmpty()) {
            return false;
        }
        // 全部关键词模式：所有关键词都必须命中
        if ("all".equalsIgnoreCase(type)) {
            for (String k : keywords) {
                if (!text.contains(k)) return false;
            }
            return true;
        }
        // 任意关键词模式（默认，含 keyword/contains/exact 等历史值）：任一关键词命中即生效
        return keywords.stream().anyMatch(text::contains);
    }

    private String maskText(String s) {
        if (s == null) return "";
        String t = s.replaceAll("\\s+", " ").trim();
        return t.length() > 120 ? t.substring(0, 120) + "..." : t;
    }

    private String abbreviate(String s, int len) {
        if (s == null) return "";
        return s.length() > len ? s.substring(0, len) : s;
    }

    private List<String> safetyReasons(AutoReplyRule r, String text) {
        List<String> reasons = new ArrayList<>();
        String handoff = r.getHandoffKeywords() == null ? "" : r.getHandoffKeywords();
        for (String p : handoff.split("[,，\\s]+")) {
            if (!p.isBlank() && text.contains(p.trim())) reasons.add("命中人工接管关键词：" + p.trim());
        }
        if (text.matches(".*(退款|投诉|赔偿|平台介入|账号|支付异常).*")) reasons.add("买家消息涉及高风险售后/支付场景");
        if (r.getPriceFloor() != null && text.matches(".*(便宜|最低|少点|砍价|刀).*")) reasons.add("涉及议价，需确认最低价底线 " + r.getPriceFloor());
        return reasons;
    }
}
