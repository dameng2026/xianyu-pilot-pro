package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.DeliveryRuleDTO;
import com.xianyu.admin.dto.DeliveryRuleVO;
import com.xianyu.admin.entity.DeliveryRule;
import com.xianyu.admin.mapper.DeliveryRuleMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
public class AutoDeliveryService {
    private static final Logger log = LoggerFactory.getLogger(AutoDeliveryService.class);

    private final DeliveryRuleMapper ruleMapper;

    public AutoDeliveryService(DeliveryRuleMapper ruleMapper) {
        this.ruleMapper = ruleMapper;
    }

    /**
     * 分页查询发货规则列表
     */
    public PageResult<DeliveryRuleVO> rules(Long tenantId, Long accountId, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = ruleMapper.count(tenantId, accountId);
        List<DeliveryRule> list = ruleMapper.list(tenantId, accountId, offset, limit);

        List<DeliveryRuleVO> records = new ArrayList<>();
        for (DeliveryRule r : list) {
            records.add(toVO(r));
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 创建发货规则
     */
    @Transactional
    public void createRule(Long tenantId, DeliveryRuleDTO dto) {
        requireSupportedDeliveryType(dto.getDeliveryType());
        DeliveryRule rule = new DeliveryRule();
        rule.setTenantId(tenantId);
        rule.setAccountId(dto.getAccountId());
        rule.setGoodsId(dto.getGoodsId());
        rule.setRuleName(dto.getRuleName());
        rule.setDeliveryType(dto.getDeliveryType());
        rule.setCardGroupId(dto.getCardGroupId());
        rule.setDeliveryContent(dto.getDeliveryContent());
        rule.setTriggerKeyword(dto.getTriggerKeyword());
        rule.setStatus(dto.getStatus() != null ? dto.getStatus() : 1);
        ruleMapper.insert(rule);
        log.info("创建发货规则成功: id={}, tenantId={}", rule.getId(), tenantId);
    }

    /**
     * 更新发货规则
     */
    @Transactional
    public void updateRule(Long tenantId, Long id, DeliveryRuleDTO dto) {
        DeliveryRule existing = ruleMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "发货规则不存在");
        }

        DeliveryRule rule = new DeliveryRule();
        rule.setId(id);
        rule.setTenantId(tenantId);
        rule.setAccountId(dto.getAccountId() != null ? dto.getAccountId() : existing.getAccountId());
        rule.setGoodsId(dto.getGoodsId() != null ? dto.getGoodsId() : existing.getGoodsId());
        rule.setRuleName(dto.getRuleName() != null ? dto.getRuleName() : existing.getRuleName());
        String deliveryType = dto.getDeliveryType() != null ? dto.getDeliveryType() : existing.getDeliveryType();
        requireSupportedDeliveryType(deliveryType);
        rule.setDeliveryType(deliveryType);
        rule.setCardGroupId(dto.getCardGroupId() != null ? dto.getCardGroupId() : existing.getCardGroupId());
        rule.setDeliveryContent(dto.getDeliveryContent() != null ? dto.getDeliveryContent() : existing.getDeliveryContent());
        rule.setTriggerKeyword(dto.getTriggerKeyword() != null ? dto.getTriggerKeyword() : existing.getTriggerKeyword());
        rule.setStatus(dto.getStatus() != null ? dto.getStatus() : existing.getStatus());
        ruleMapper.update(rule);
        log.info("更新发货规则成功: id={}, tenantId={}", id, tenantId);
    }

    /**
     * 删除发货规则（软删除）
     */
    @Transactional
    public void deleteRule(Long tenantId, Long id) {
        DeliveryRule existing = ruleMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "发货规则不存在");
        }
        ruleMapper.softDelete(tenantId, id);
        log.info("删除发货规则: id={}, tenantId={}", id, tenantId);
    }

    private DeliveryRuleVO toVO(DeliveryRule r) {
        DeliveryRuleVO vo = new DeliveryRuleVO();
        vo.setId(r.getId());
        vo.setAccountId(r.getAccountId());
        vo.setGoodsId(r.getGoodsId());
        vo.setRuleName(r.getRuleName());
        vo.setDeliveryType(r.getDeliveryType());
        vo.setCardGroupId(r.getCardGroupId());
        vo.setDeliveryContent(r.getDeliveryContent());
        vo.setTriggerKeyword(r.getTriggerKeyword());
        vo.setStatus(r.getStatus());
        return vo;
    }

    private void requireSupportedDeliveryType(String deliveryType) {
        if (!"text".equalsIgnoreCase(deliveryType) && !"card".equalsIgnoreCase(deliveryType)) {
            throw new BizException(422, "当前仅支持文本或卡密发货；API 发货尚未接入安全执行适配器");
        }
    }
}
