package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.CardGroupDTO;
import com.xianyu.admin.dto.CardGroupVO;
import com.xianyu.admin.dto.CardItemVO;
import com.xianyu.admin.entity.CardGroup;
import com.xianyu.admin.entity.CardItem;
import com.xianyu.admin.mapper.CardGroupMapper;
import com.xianyu.admin.mapper.CardItemMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class CardService {
    private static final Logger log = LoggerFactory.getLogger(CardService.class);
    private static final int MAX_EXPORT_ITEMS = 20_000;
    private static final long MAX_EXPORT_BYTES = 10L * 1024 * 1024;

    private final CardGroupMapper groupMapper;
    private final CardItemMapper itemMapper;

    public CardService(CardGroupMapper groupMapper, CardItemMapper itemMapper) {
        this.groupMapper = groupMapper;
        this.itemMapper = itemMapper;
    }

    /**
     * 分页查询卡片组列表
     */
    public PageResult<CardGroupVO> groups(Long tenantId, String keyword, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = groupMapper.count(tenantId, keyword);
        List<CardGroup> list = groupMapper.list(tenantId, keyword, offset, limit);

        List<CardGroupVO> records = enrichGroupVOBatch(list);
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    public List<CardGroupVO> alerts(Long tenantId) {
        List<CardGroupVO> groups = enrichGroupVOBatch(groupMapper.list(tenantId, null, 0, 200));
        List<CardGroupVO> alerts = new ArrayList<>();
        for (CardGroupVO group : groups) {
            int remain = group.getRemainCount() != null ? group.getRemainCount() : 0;
            int threshold = group.getAlertThreshold() != null ? group.getAlertThreshold() : 10;
            if (remain <= threshold) alerts.add(group);
        }
        return alerts;
    }

    /**
     * 创建卡片组
     */
    @Transactional
    public void createGroup(Long tenantId, CardGroupDTO dto) {
        CardGroup group = new CardGroup();
        group.setTenantId(tenantId);
        group.setGroupName(dto.getGroupName());
        group.setDescription(dto.getDescription());
        group.setGroupType(normalizeCardType(dto.getCardType()));
        group.setCardPrefix(dto.getCardPrefix());
        group.setPasswordPrefix(dto.getPasswordPrefix());
        group.setRemark(dto.getRemark());
        group.setAlertThreshold(dto.getAlertThreshold() != null ? dto.getAlertThreshold() : 10);
        group.setCostPrice(dto.getCostPrice());
        group.setSuggestedPrice(dto.getSuggestedPrice());
        group.setTotalCount(dto.getTotalCount() != null ? dto.getTotalCount() : 0);
        group.setUsedCount(dto.getUsedCount() != null ? dto.getUsedCount() : 0);
        group.setRemainCount(dto.getRemainCount() != null ? dto.getRemainCount() : 0);
        group.setStatus(dto.getStatus() != null ? dto.getStatus() : 1);
        groupMapper.insert(group);
        log.info("创建卡片组成功: id={}, tenantId={}", group.getId(), tenantId);
    }

    /**
     * 更新卡片组
     */
    @Transactional
    public void updateGroup(Long tenantId, Long id, CardGroupDTO dto) {
        CardGroup existing = groupMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "卡片组不存在");
        }

        CardGroup group = new CardGroup();
        group.setId(id);
        group.setTenantId(tenantId);
        group.setGroupName(dto.getGroupName() != null ? dto.getGroupName() : existing.getGroupName());
        group.setDescription(dto.getDescription() != null ? dto.getDescription() : existing.getDescription());
        group.setGroupType(dto.getCardType() != null ? normalizeCardType(dto.getCardType()) : existing.getGroupType());
        group.setCardPrefix(dto.getCardPrefix() != null ? dto.getCardPrefix() : existing.getCardPrefix());
        group.setPasswordPrefix(dto.getPasswordPrefix() != null ? dto.getPasswordPrefix() : existing.getPasswordPrefix());
        group.setRemark(dto.getRemark() != null ? dto.getRemark() : existing.getRemark());
        group.setAlertThreshold(dto.getAlertThreshold() != null ? dto.getAlertThreshold() : existing.getAlertThreshold());
        group.setCostPrice(dto.getCostPrice() != null ? dto.getCostPrice() : existing.getCostPrice());
        group.setSuggestedPrice(dto.getSuggestedPrice() != null ? dto.getSuggestedPrice() : existing.getSuggestedPrice());
        group.setTotalCount(dto.getTotalCount() != null ? dto.getTotalCount() : existing.getTotalCount());
        group.setUsedCount(dto.getUsedCount() != null ? dto.getUsedCount() : existing.getUsedCount());
        group.setRemainCount(dto.getRemainCount() != null ? dto.getRemainCount() : existing.getRemainCount());
        group.setStatus(dto.getStatus() != null ? dto.getStatus() : existing.getStatus());
        groupMapper.update(group);
        log.info("更新卡片组成功: id={}, tenantId={}", id, tenantId);
    }

    /**
     * 删除卡片组（软删除）
     */
    @Transactional
    public void deleteGroup(Long tenantId, Long id) {
        CardGroup existing = groupMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "卡片组不存在");
        }
        groupMapper.softDelete(tenantId, id);
        log.info("删除卡片组: id={}, tenantId={}", id, tenantId);
    }

    /**
     * 分页查询卡片项列表
     */
    public PageResult<CardItemVO> items(Long tenantId, Long groupId, Integer status, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = itemMapper.countByGroupIdAndStatus(tenantId, groupId, status);
        List<CardItem> list = itemMapper.listByGroupIdAndStatus(tenantId, groupId, status, offset, limit);

        List<CardItemVO> records = new ArrayList<>();
        for (CardItem i : list) {
            records.add(toItemVO(i));
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 创建卡片项
     */
    @Transactional
    public void createItem(Long tenantId, Long groupId, String content) {
        String safeContent = content == null ? "" : content.trim();
        if (safeContent.isEmpty()) {
            throw new BizException(400, "卡密内容不能为空");
        }
        if (safeContent.length() > 5000) {
            throw new BizException(400, "卡密内容不能超过5000个字符");
        }
        if (safeContent.indexOf('\r') >= 0 || safeContent.indexOf('\n') >= 0
                || safeContent.indexOf('\u0000') >= 0) {
            throw new BizException(400, "卡密内容不能包含换行或空字符");
        }
        CardGroup group = groupMapper.findById(tenantId, groupId);
        if (group == null) {
            throw new BizException(404, "卡片组不存在");
        }
        if (itemMapper.countDuplicateContent(tenantId, groupId, safeContent) > 0) {
            throw new BizException(400, "卡密内容已存在，请勿重复导入");
        }

        CardItem item = new CardItem();
        item.setTenantId(tenantId);
        item.setGroupId(groupId);
        fillCardItemContent(item, group, safeContent);
        item.setStatus(0);
        itemMapper.insert(item);
        groupMapper.refreshCounts(tenantId, groupId);
        log.info("创建卡片项成功: id={}, groupId={}, tenantId={}", item.getId(), groupId, tenantId);
    }

    /**
     * 原子认领一张未使用卡密。用于自动发货链路，避免 SELECT 后 UPDATE 造成并发重复发卡。
     */
    @Transactional
    public CardItem claimUnusedCard(Long tenantId, Long groupId, Long orderId) {
        CardGroup group = groupMapper.findById(tenantId, groupId);
        if (group == null) {
            throw new BizException(404, "卡密组不存在");
        }
        int affected = itemMapper.claimUnusedOne(tenantId, groupId, orderId);
        if (affected == 0) {
            throw new BizException(409, "卡密库存不足");
        }
        CardItem item = itemMapper.findClaimedByOrder(tenantId, groupId, orderId);
        groupMapper.refreshCounts(tenantId, groupId);
        return item;
    }

    @Transactional
    public void deleteItem(Long tenantId, Long groupId, Long itemId) {
        int affected = itemMapper.softDelete(tenantId, groupId, itemId);
        if (affected == 0) throw new BizException(404, "卡密不存在");
        groupMapper.refreshCounts(tenantId, groupId);
    }

    @Transactional
    public void resetItem(Long tenantId, Long groupId, Long itemId) {
        int affected = itemMapper.reset(tenantId, groupId, itemId);
        if (affected == 0) throw new BizException(404, "卡密不存在");
        groupMapper.refreshCounts(tenantId, groupId);
    }

    @Transactional
    public void lockItem(Long tenantId, Long groupId, Long itemId) {
        int affected = itemMapper.updateStatusOnly(tenantId, groupId, itemId, 1);
        if (affected == 0) throw new BizException(404, "卡密不存在");
        groupMapper.refreshCounts(tenantId, groupId);
    }

    @Transactional
    public void markInvalid(Long tenantId, Long groupId, Long itemId) {
        int affected = itemMapper.updateStatusOnly(tenantId, groupId, itemId, 3);
        if (affected == 0) throw new BizException(404, "卡密不存在");
        groupMapper.refreshCounts(tenantId, groupId);
    }

    private CardGroupVO toGroupVO(CardGroup g) {
        return enrichGroupVO(g);
    }

    public CardGroupVO detail(Long tenantId, Long groupId) {
        CardGroup group = requireGroup(tenantId, groupId);
        return enrichGroupVO(group);
    }

    public Map<String, Object> stockStats(Long tenantId, Long groupId) {
        requireGroup(tenantId, groupId);
        Map<String, Object> raw = itemMapper.statsByGroup(tenantId, groupId);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("totalCount", toInt(raw.get("totalCount")));
        result.put("remainCount", toInt(raw.get("remainCount")));
        result.put("lockedCount", toInt(raw.get("lockedCount")));
        result.put("usedCount", toInt(raw.get("usedCount")));
        result.put("invalidCount", toInt(raw.get("invalidCount")));
        result.put("errorCount", toInt(raw.get("errorCount")));
        return result;
    }

    public PageResult<CardItemVO> usageRecords(Long tenantId, Long groupId, int current, int size) {
        requireGroup(tenantId, groupId);
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int total = itemMapper.countUsedByGroup(tenantId, groupId);
        List<CardItemVO> records = new ArrayList<>();
        for (CardItem item : itemMapper.listUsedByGroup(tenantId, groupId, offset, safeSize)) {
            records.add(toItemVO(item));
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    public List<CardItemVO> exportItems(Long tenantId, Long groupId) {
        requireGroup(tenantId, groupId);
        int total = itemMapper.countByGroupIdAndStatus(tenantId, groupId, null);
        Long estimatedBytes = itemMapper.estimateExportBytes(tenantId, groupId);
        if (total > MAX_EXPORT_ITEMS
                || (estimatedBytes != null && estimatedBytes > MAX_EXPORT_BYTES)) {
            throw new BizException(413, "卡密导出超过安全上限，请先拆分卡密组后再导出");
        }
        List<CardItemVO> records = new ArrayList<>();
        for (CardItem item : itemMapper.listAllByGroup(tenantId, groupId)) {
            records.add(toItemVO(item));
        }
        return records;
    }

    private CardGroupVO enrichGroupVO(CardGroup g) {
        return enrichGroupVO(g, null);
    }

    /**
     * 批量填充 CardGroupVO，避免分页 N+1 查询。
     * 单次 GROUP BY group_id 拉取所有组的 locked/invalid/error 统计，再在内存按 groupId 映射。
     */
    private List<CardGroupVO> enrichGroupVOBatch(List<CardGroup> groups) {
        List<CardGroupVO> records = new ArrayList<>(groups.size());
        if (groups.isEmpty()) return records;
        Long tenantId = groups.get(0).getTenantId();
        List<Long> groupIds = new ArrayList<>(groups.size());
        for (CardGroup g : groups) groupIds.add(g.getId());
        Map<Long, Map<String, Object>> statsMap = new LinkedHashMap<>();
        try {
            if (tenantId != null) {
                for (Map<String, Object> row : itemMapper.statsByGroupIds(tenantId, groupIds)) {
                    Object gidObj = row.get("group_id");
                    if (gidObj != null) {
                        Long gid = gidObj instanceof Number ? ((Number) gidObj).longValue() : Long.parseLong(gidObj.toString());
                        statsMap.put(gid, row);
                    }
                }
            }
        } catch (Exception e) {
            log.warn("批量统计卡密组失败，回退到单组查询, errorType={}", e.getClass().getSimpleName());
        }
        for (CardGroup g : groups) {
            records.add(enrichGroupVO(g, statsMap.get(g.getId())));
        }
        return records;
    }

    private CardGroupVO enrichGroupVO(CardGroup g, Map<String, Object> stats) {
        CardGroupVO vo = new CardGroupVO();
        vo.setId(g.getId());
        vo.setGroupName(g.getGroupName());
        vo.setDescription(g.getDescription());
        vo.setCardType(normalizeCardType(g.getGroupType()));
        vo.setCardPrefix(g.getCardPrefix());
        vo.setPasswordPrefix(g.getPasswordPrefix());
        vo.setRemark(g.getRemark() != null ? g.getRemark() : g.getDescription());
        vo.setAlertThreshold(g.getAlertThreshold() != null ? g.getAlertThreshold() : 10);
        vo.setCostPrice(g.getCostPrice());
        vo.setSuggestedPrice(g.getSuggestedPrice());
        vo.setTotalCount(g.getTotalCount());
        vo.setUsedCount(g.getUsedCount());
        vo.setRemainCount(g.getRemainCount());
        if (stats == null) {
            stats = itemMapper.statsByGroup(g.getTenantId(), g.getId());
        }
        vo.setLockedCount(toInt(stats.get("lockedCount")));
        vo.setInvalidCount(toInt(stats.get("invalidCount")));
        vo.setErrorCount(toInt(stats.get("errorCount")));
        vo.setStatus(g.getStatus());
        return vo;
    }

    private CardItemVO toItemVO(CardItem i) {
        CardItemVO vo = new CardItemVO();
        vo.setId(i.getId());
        vo.setGroupId(i.getGroupId());
        String content = buildDisplayContent(i);
        vo.setCardContent(content);
        vo.setContent(content);
        vo.setStatus(i.getStatus());
        vo.setUsedOrderId(i.getUsedOrderId() != null ? i.getUsedOrderId() : i.getUsedByOrderId());
        vo.setUsedTime(i.getUsedTime());
        return vo;
    }

    private CardGroup requireGroup(Long tenantId, Long groupId) {
        CardGroup group = groupMapper.findById(tenantId, groupId);
        if (group == null) {
            throw new BizException(404, "卡片组不存在");
        }
        return group;
    }

    private void fillCardItemContent(CardItem item, CardGroup group, String rawContent) {
        item.setCardContent(rawContent);
        String normalizedType = normalizeCardType(group.getGroupType());
        if ("card_password".equals(normalizedType) || "link_code".equals(normalizedType) || "account_password".equals(normalizedType)) {
            String[] parts = splitCardParts(rawContent);
            item.setCardKey(parts[0]);
            item.setCardValue(parts[1]);
        } else {
            item.setCardKey(rawContent);
            item.setCardValue(null);
        }
    }

    private String[] splitCardParts(String rawContent) {
        String[] separators = {"----", ",", "\t"};
        for (String separator : separators) {
            int index = rawContent.indexOf(separator);
            if (index > 0) {
                return new String[]{
                        rawContent.substring(0, index).trim(),
                        rawContent.substring(index + separator.length()).trim()
                };
            }
        }
        return new String[]{rawContent, ""};
    }

    private String buildDisplayContent(CardItem item) {
        if (item.getCardContent() != null && !item.getCardContent().isBlank()) return item.getCardContent();
        String key = item.getCardKey();
        String value = item.getCardValue();
        if (key == null && value == null) return "";
        if (value == null || value.isBlank()) return key == null ? "" : key;
        return key + "----" + value;
    }

    private int toInt(Object value) {
        return value instanceof Number number ? number.intValue() : 0;
    }

    private String normalizeCardType(String value) {
        if (value == null || value.isBlank()) return "unique";
        return switch (value) {
            case "kami", "unique", "single" -> "unique";
            case "card_password", "card-password" -> "card_password";
            case "link_code", "link-code" -> "link_code";
            case "account_password", "account-password" -> "account_password";
            default -> value;
        };
    }
}
