package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.dto.XianyuGoodsDTO;
import com.xianyu.admin.dto.XianyuGoodsVO;
import com.xianyu.admin.dto.DeleteResultVO;
import com.xianyu.admin.entity.XianyuGoods;
import com.xianyu.admin.mapper.XianyuGoodsMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class XianyuGoodsService {
    private static final Logger log = LoggerFactory.getLogger(XianyuGoodsService.class);

    private static final int FE_STATUS_ON_SALE = 0;
    private static final int FE_STATUS_OFF_SHELF = 1;
    private static final int FE_STATUS_SOLD = 2;
    private static final int FE_STATUS_DELETED = 3;

    private static final int DB_STATUS_ON_SALE = 1;
    private static final int DB_STATUS_OFF_SHELF = 0;

    private final XianyuGoodsMapper goodsMapper;
    private final XianyuGoodsDeleteService deleteService;

    public XianyuGoodsService(XianyuGoodsMapper goodsMapper,
                               XianyuGoodsDeleteService deleteService) {
        this.goodsMapper = goodsMapper;
        this.deleteService = deleteService;
    }

    private static int feToDbStatus(int feStatus) {
        return switch (feStatus) {
            case FE_STATUS_ON_SALE -> DB_STATUS_ON_SALE;
            case FE_STATUS_OFF_SHELF -> DB_STATUS_OFF_SHELF;
            default -> feStatus;
        };
    }

    private static int dbToFeStatus(Integer dbStatus) {
        if (dbStatus == null) return FE_STATUS_OFF_SHELF;
        return switch (dbStatus) {
            case DB_STATUS_ON_SALE -> FE_STATUS_ON_SALE;
            case DB_STATUS_OFF_SHELF -> FE_STATUS_OFF_SHELF;
            default -> dbStatus;
        };
    }

    private static Integer deliveryTypeToFeCode(String deliveryType) {
        if (deliveryType == null) return null;
        String type = deliveryType.toLowerCase();
        if (type.contains("card") || type.contains("kami")) return 0;
        if (type.contains("text") || type.contains("txt")) return 1;
        if (type.contains("custom") || type.contains("self_define")) return 2;
        return 0;
    }

    /**
     * 分页查询商品列表
     */
    public PageResult<XianyuGoodsVO> page(Long tenantId, Long accountId, String keyword, Integer status,
                                           Integer excludeStatus, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        Integer dbStatus = null;
        Integer dbExcludeStatus = null;
        Integer deleted = 0;

        if (status != null) {
            if (status == FE_STATUS_DELETED) {
                deleted = 1;
            } else {
                dbStatus = feToDbStatus(status);
            }
        }

        if (excludeStatus != null && excludeStatus == FE_STATUS_DELETED) {
            deleted = 0;
        } else if (excludeStatus != null) {
            dbExcludeStatus = feToDbStatus(excludeStatus);
        }

        int total = goodsMapper.count(tenantId, accountId, keyword, dbStatus, dbExcludeStatus, deleted);
        List<XianyuGoods> list = goodsMapper.list(tenantId, accountId, keyword, dbStatus, dbExcludeStatus, deleted, offset, limit);

        List<Long> goodsIds = list.stream().map(XianyuGoods::getId).collect(Collectors.toList());
        List<Long> accountIds = list.stream()
                .map(XianyuGoods::getAccountId)
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());

        Map<Long, Map<String, Object>> deliveryRuleMap = new HashMap<>();
        Set<Long> autoReplyAccountSet = new HashSet<>();

        if (!goodsIds.isEmpty()) {
            List<Map<String, Object>> deliveryRules = goodsMapper.findDeliveryRulesForGoods(tenantId, goodsIds);
            Map<Long, Map<String, Object>> latestRulePerGoods = new HashMap<>();
            for (Map<String, Object> rule : deliveryRules) {
                Long gid = rule.get("goods_id") != null ? ((Number) rule.get("goods_id")).longValue() : null;
                if (gid != null && !latestRulePerGoods.containsKey(gid)) {
                    latestRulePerGoods.put(gid, rule);
                }
            }
            deliveryRuleMap.putAll(latestRulePerGoods);
        }

        if (!accountIds.isEmpty()) {
            List<Long> replyAccounts = goodsMapper.findAccountsWithAutoReply(tenantId, accountIds);
            if (replyAccounts != null) {
                autoReplyAccountSet.addAll(replyAccounts);
            }
        }

        List<XianyuGoodsVO> records = new ArrayList<>();
        for (XianyuGoods g : list) {
            XianyuGoodsVO vo = toVO(g);

            Map<String, Object> rule = deliveryRuleMap.get(g.getId());
            if (rule != null) {
                String dType = rule.get("delivery_type") != null ? String.valueOf(rule.get("delivery_type")) : null;
                Integer dStatus = rule.get("status") != null ? ((Number) rule.get("status")).intValue() : 0;
                Integer feTypeCode = deliveryTypeToFeCode(dType);
                vo.setAutoDeliveryType(feTypeCode);
                vo.setXianyuAutoDeliveryOn(dStatus == 1 ? 1 : 0);
            } else {
                vo.setAutoDeliveryType(null);
                vo.setXianyuAutoDeliveryOn(0);
            }

            if (g.getAccountId() != null && autoReplyAccountSet.contains(g.getAccountId())) {
                vo.setXianyuAutoReplyOn(1);
            } else {
                vo.setXianyuAutoReplyOn(0);
            }

            vo.setSkuCount(0);
            records.add(vo);
        }

        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 统计商品全局数据（不受分页、关键词、状态筛选影响，仅按账号过滤）
     */
    public Map<String, Object> stats(Long tenantId, Long accountId) {
        Map<String, Object> statusStats = goodsMapper.countStatusStats(tenantId, accountId);
        int total = toInt(statusStats != null ? statusStats.get("total") : null);
        int onSale = toInt(statusStats != null ? statusStats.get("onSale") : null);
        int offShelfOrDraft = toInt(statusStats != null ? statusStats.get("offShelfOrDraft") : null);
        int autoDeliveryOn = goodsMapper.countAutoDeliveryOn(tenantId, accountId);
        int autoReplyAccounts = goodsMapper.countAutoReplyAccounts(tenantId, accountId);

        Map<String, Object> result = new HashMap<>();
        result.put("total", total);
        result.put("onSale", onSale);
        result.put("offShelfOrDraft", offShelfOrDraft);
        result.put("autoDeliveryOn", autoDeliveryOn);
        result.put("autoReplyAccounts", autoReplyAccounts);
        return result;
    }

    private static int toInt(Object value) {
        if (value == null) return 0;
        if (value instanceof Number) return ((Number) value).intValue();
        try { return Integer.parseInt(String.valueOf(value)); } catch (NumberFormatException e) { return 0; }
    }

    /**
     * 查询商品详情
     */
    public XianyuGoodsVO detail(Long tenantId, Long id) {
        XianyuGoods goods = goodsMapper.findById(tenantId, id);
        if (goods == null) {
            throw new BizException(404, "商品不存在");
        }
        XianyuGoodsVO vo = toVO(goods);

        List<Long> goodsIds = Collections.singletonList(id);
        List<Map<String, Object>> deliveryRules = goodsMapper.findDeliveryRulesForGoods(tenantId, goodsIds);
        if (!deliveryRules.isEmpty()) {
            Map<String, Object> rule = deliveryRules.get(0);
            String dType = rule.get("delivery_type") != null ? String.valueOf(rule.get("delivery_type")) : null;
            Integer dStatus = rule.get("status") != null ? ((Number) rule.get("status")).intValue() : 0;
            vo.setAutoDeliveryType(deliveryTypeToFeCode(dType));
            vo.setXianyuAutoDeliveryOn(dStatus == 1 ? 1 : 0);
        } else {
            vo.setXianyuAutoDeliveryOn(0);
        }

        if (goods.getAccountId() != null) {
            List<Long> replyAccounts = goodsMapper.findAccountsWithAutoReply(tenantId, Collections.singletonList(goods.getAccountId()));
            vo.setXianyuAutoReplyOn(replyAccounts != null && replyAccounts.contains(goods.getAccountId()) ? 1 : 0);
        } else {
            vo.setXianyuAutoReplyOn(0);
        }

        vo.setSkuCount(0);
        return vo;
    }

    /**
     * 创建商品
     */
    @Transactional
    public void create(Long tenantId, XianyuGoodsDTO dto) {
        validateGoodsFields(dto);
        XianyuGoods goods = new XianyuGoods();
        goods.setTenantId(tenantId);
        goods.setAccountId(dto.getAccountId());
        goods.setExternalGoodsId(dto.getExternalGoodsId());
        goods.setTitle(dto.getTitle());
        goods.setPrice(dto.getPrice());
        goods.setSoldPrice(dto.getSoldPrice());
        goods.setCoverPic(dto.getCoverPic());
        goods.setImageUrl(dto.getImageUrl());
        goods.setStock(dto.getStock());
        goods.setQuantity(dto.getQuantity());
        goods.setExposureCount(dto.getExposureCount());
        goods.setViewCount(dto.getViewCount());
        goods.setWantCount(dto.getWantCount());
        goods.setDetailUrl(dto.getDetailUrl());
        goods.setDetailInfo(dto.getDetailInfo());
        goods.setDescription(dto.getDescription());
        goods.setCategory(dto.getCategory());
        goods.setSortOrder(dto.getSortOrder());
        goods.setStatus(DB_STATUS_ON_SALE);
        goodsMapper.insert(goods);
        log.info("创建商品成功: id={}, tenantId={}", goods.getId(), tenantId);
    }

    /**
     * 更新商品
     */
    @Transactional
    public void update(Long tenantId, Long id, XianyuGoodsDTO dto) {
        validateGoodsFields(dto);
        XianyuGoods existing = goodsMapper.findById(tenantId, id);
        if (existing == null) {
            throw new BizException(404, "商品不存在");
        }

        Integer dbStatus = existing.getStatus();
        if (dto.getStatus() != null) {
            dbStatus = dto.getStatus() == FE_STATUS_ON_SALE ? DB_STATUS_ON_SALE
                    : dto.getStatus() == FE_STATUS_OFF_SHELF ? DB_STATUS_OFF_SHELF
                    : dto.getStatus();
        }

        XianyuGoods goods = new XianyuGoods();
        goods.setId(id);
        goods.setTenantId(tenantId);
        goods.setAccountId(dto.getAccountId() != null ? dto.getAccountId() : existing.getAccountId());
        goods.setExternalGoodsId(dto.getExternalGoodsId() != null ? dto.getExternalGoodsId() : existing.getExternalGoodsId());
        goods.setTitle(dto.getTitle() != null ? dto.getTitle() : existing.getTitle());
        goods.setPrice(dto.getPrice() != null ? dto.getPrice() : existing.getPrice());
        goods.setSoldPrice(dto.getSoldPrice() != null ? dto.getSoldPrice() : existing.getSoldPrice());
        goods.setCoverPic(dto.getCoverPic() != null ? dto.getCoverPic() : existing.getCoverPic());
        goods.setImageUrl(dto.getImageUrl() != null ? dto.getImageUrl() : existing.getImageUrl());
        goods.setStock(dto.getStock() != null ? dto.getStock() : existing.getStock());
        goods.setQuantity(dto.getQuantity() != null ? dto.getQuantity() : existing.getQuantity());
        goods.setExposureCount(dto.getExposureCount() != null ? dto.getExposureCount() : existing.getExposureCount());
        goods.setViewCount(dto.getViewCount() != null ? dto.getViewCount() : existing.getViewCount());
        goods.setWantCount(dto.getWantCount() != null ? dto.getWantCount() : existing.getWantCount());
        goods.setDetailUrl(dto.getDetailUrl() != null ? dto.getDetailUrl() : existing.getDetailUrl());
        goods.setDetailInfo(dto.getDetailInfo() != null ? dto.getDetailInfo() : existing.getDetailInfo());
        goods.setDescription(dto.getDescription() != null ? dto.getDescription() : existing.getDescription());
        goods.setCategory(dto.getCategory() != null ? dto.getCategory() : existing.getCategory());
        goods.setSortOrder(dto.getSortOrder() != null ? dto.getSortOrder() : existing.getSortOrder());
        goods.setStatus(dbStatus);
        goodsMapper.update(goods);
        log.info("更新商品成功: id={}, tenantId={}", id, tenantId);
    }

    /**
     * 兼容旧调用：默认仅删除本地记录，避免误删闲鱼线上商品。
     */
    public DeleteResultVO delete(Long tenantId, Long userId, Long id, String ipAddress) {
        return deleteLocal(tenantId, userId, id, ipAddress);
    }

    /**
     * 仅删除本地记录。
     */
    public DeleteResultVO deleteLocal(Long tenantId, Long userId, Long id, String ipAddress) {
        return deleteService.executeLocalDelete(tenantId, userId, id, ipAddress);
    }

    /**
     * 远端删除，需要强确认。
     */
    public DeleteResultVO deleteRemote(Long tenantId, Long userId, Long id, String confirmText, String ipAddress) {
        if (!"DELETE".equals(confirmText)) {
            throw new BizException(400, "远端删除需要输入 DELETE 确认");
        }
        return deleteService.executeRemoteDelete(tenantId, userId, id, ipAddress);
    }


    private void validateGoodsFields(XianyuGoodsDTO dto) {
        validateMoney(dto.getPrice(), "价格");
        validateMoney(dto.getSoldPrice(), "成交价");
        validateStock(dto.getStock());
        if (dto.getQuantity() != null && (dto.getQuantity() < 0 || dto.getQuantity() > 999999)) {
            throw new BizException(400, "库存数量必须在0到999999之间");
        }
        if (dto.getTitle() != null && dto.getTitle().length() > 200) {
            throw new BizException(400, "商品标题不能超过200个字符");
        }
        if (dto.getDescription() != null && dto.getDescription().length() > 5000) {
            throw new BizException(400, "商品描述不能超过5000个字符");
        }
    }

    private void validateMoney(String value, String fieldName) {
        if (value == null || value.isBlank()) return;
        String raw = value.replace("¥", "").trim();
        if (!raw.matches("^\\d+(\\.\\d{1,2})?$")) {
            throw new BizException(400, fieldName + "必须为大于0的数字，最多两位小数");
        }
        double amount = Double.parseDouble(raw);
        if (amount <= 0 || amount > 9999999D) {
            throw new BizException(400, fieldName + "必须在0到9999999之间");
        }
    }

    private void validateStock(String value) {
        if (value == null || value.isBlank()) return;
        String raw = value.trim();
        if (!raw.matches("^\\d+$")) {
            throw new BizException(400, "库存必须为0到999999之间的整数");
        }
        int stock = Integer.parseInt(raw);
        if (stock < 0 || stock > 999999) {
            throw new BizException(400, "库存必须为0到999999之间的整数");
        }
    }

    private XianyuGoodsVO toVO(XianyuGoods g) {
        XianyuGoodsVO vo = new XianyuGoodsVO();
        vo.setId(g.getId());
        vo.setTenantId(g.getTenantId());
        vo.setAccountId(g.getAccountId());
        vo.setExternalGoodsId(g.getExternalGoodsId());
        vo.setTitle(g.getTitle());
        vo.setPrice(g.getPrice());
        vo.setSoldPrice(g.getSoldPrice());
        vo.setCoverPic(g.getCoverPic());
        vo.setImageUrl(g.getImageUrl());
        vo.setStock(g.getStock());
        vo.setQuantity(g.getQuantity());
        vo.setExposureCount(g.getExposureCount());
        vo.setViewCount(g.getViewCount());
        vo.setWantCount(g.getWantCount());
        vo.setDetailUrl(g.getDetailUrl());
        vo.setDetailInfo(g.getDetailInfo());
        vo.setDescription(g.getDescription());
        vo.setCategory(g.getCategory());
        vo.setSortOrder(g.getSortOrder());
        vo.setStatus(dbToFeStatus(g.getStatus()));
        vo.setCreatedTime(g.getCreatedTime());
        vo.setUpdatedTime(g.getUpdatedTime());
        return vo;
    }
}
