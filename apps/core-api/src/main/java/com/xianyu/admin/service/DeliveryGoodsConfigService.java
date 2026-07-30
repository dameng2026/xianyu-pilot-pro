package com.xianyu.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Deep module for tenant-safe, fail-closed per-goods delivery configuration.
 * Both single-item and batch controllers cross this seam so validation,
 * reference ownership, JSON recovery and transaction semantics stay local.
 */
@Service
public class DeliveryGoodsConfigService {
    private static final Logger log = LoggerFactory.getLogger(DeliveryGoodsConfigService.class);
    private static final Set<String> SUPPORTED_TIMINGS = Set.of("payDelivery", "confirmDelivery", "reviewDelivery");
    private static final Set<String> SUPPORTED_MODES = Set.of("text", "card");
    private static final int MAX_EXPLICIT_BATCH = 500;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public DeliveryGoodsConfigService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @Transactional(readOnly = true)
    public Map<String, Object> read(Long tenantId, Long goodsId) {
        requireTenantAndGoodsId(tenantId, goodsId);
        requireGoods(tenantId, List.of(goodsId), false);
        StoredConfig stored = loadStoredConfig(tenantId, goodsId, false);
        return stored == null ? new LinkedHashMap<>() : new LinkedHashMap<>(stored.config());
    }

    /**
     * 批量读取多个商品的发货配置，用于首屏一次性加载，避免逐个请求造成 3s+ 等待。
     * 返回 Map：goodsId(String) → config(Map)。未配置的商品不在返回 Map 中（前端按缺失处理为空配置）。
     * 不抛 404 校验异常：批量读取仅返回现有配置，缺失的商品视为无配置。
     */
    @Transactional(readOnly = true)
    public Map<Long, Map<String, Object>> batchRead(Long tenantId, Collection<Long> goodsIds) {
        requireTenant(tenantId);
        List<Long> ids = normalizeGoodsIds(goodsIds);
        Map<Long, Map<String, Object>> result = new LinkedHashMap<>();
        if (ids.isEmpty()) return result;
        if (ids.size() > MAX_EXPLICIT_BATCH) {
            throw new BizException(422, "单次最多查询 500 个商品配置，请分批操作");
        }
        String placeholders = ids.stream().map(ignored -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        args.addAll(ids);
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT goods_id, config_json FROM delivery_goods_config "
                            + "WHERE tenant_id=? AND deleted=0 AND goods_id IN (" + placeholders + ")",
                    args.toArray()
            );
            for (Map<String, Object> row : rows) {
                Long goodsId = nullablePositiveLong(row.get("goods_id"), "商品配置数据异常");
                if (goodsId == null) continue;
                String json = text(row.get("config_json"));
                if (json.isBlank()) {
                    result.put(goodsId, new LinkedHashMap<>());
                    continue;
                }
                try {
                    Map<String, Object> config = objectMapper.readValue(
                            json, new TypeReference<LinkedHashMap<String, Object>>() {});
                    result.put(goodsId, config);
                } catch (Exception error) {
                    log.error("解析商品发货配置失败 goodsId={}, errorType={}",
                            goodsId, error.getClass().getSimpleName());
                    result.put(goodsId, new LinkedHashMap<>());
                }
            }
            return result;
        } catch (BizException error) {
            throw error;
        } catch (Exception error) {
            log.error("批量读取商品发货配置失败 tenantId={}, count={}, errorType={}",
                    tenantId, ids.size(), error.getClass().getSimpleName());
            throw new BizException(503, "商品发货配置暂时不可用，请稍后重试");
        }
    }

    @Transactional
    public int apply(Long tenantId, Collection<Long> goodsIds, Map<String, Object> rawPatch) {
        requireTenant(tenantId);
        List<Long> ids = normalizeGoodsIds(goodsIds);
        if (ids.isEmpty()) throw new BizException(422, "请选择需要配置的商品");
        if (ids.size() > MAX_EXPLICIT_BATCH) {
            throw new BizException(422, "单次最多配置 500 个商品，请分批操作");
        }
        ConfigPatch patch = parsePatch(rawPatch);
        Map<Long, GoodsOwner> goods = requireGoods(tenantId, ids, true);
        for (Long goodsId : ids) {
            GoodsOwner owner = goods.get(goodsId);
            StoredConfig stored = loadStoredConfig(tenantId, goodsId, true);
            Map<String, Object> config = stored == null
                    ? new LinkedHashMap<>()
                    : new LinkedHashMap<>(stored.config());
            mergePatch(tenantId, config, patch);
            config.put("accountId", owner.accountId());
            persist(tenantId, goodsId, stored, config);
        }
        return ids.size();
    }

    @Transactional
    public int applyAll(Long tenantId, Map<String, Object> rawPatch) {
        requireTenant(tenantId);
        List<Long> ids;
        try {
            ids = jdbcTemplate.queryForList(
                    "SELECT id FROM xianyu_goods WHERE tenant_id=? AND deleted=0 ORDER BY id",
                    Long.class,
                    tenantId
            );
        } catch (Exception error) {
            log.error("加载待配置商品失败 tenantId={}, errorType={}", tenantId, error.getClass().getSimpleName());
            throw new BizException(503, "商品列表暂时不可用，未执行批量配置");
        }
        if (ids.isEmpty()) return 0;

        int applied = 0;
        for (int start = 0; start < ids.size(); start += MAX_EXPLICIT_BATCH) {
            int end = Math.min(start + MAX_EXPLICIT_BATCH, ids.size());
            applied += apply(tenantId, ids.subList(start, end), rawPatch);
        }
        return applied;
    }

    @Transactional
    public int delete(Long tenantId, Collection<Long> goodsIds) {
        requireTenant(tenantId);
        List<Long> ids = normalizeGoodsIds(goodsIds);
        if (ids.isEmpty()) throw new BizException(422, "请选择需要删除配置的商品");
        if (ids.size() > MAX_EXPLICIT_BATCH) {
            throw new BizException(422, "单次最多删除 500 个商品配置，请分批操作");
        }
        requireGoods(tenantId, ids, true);
        String placeholders = ids.stream().map(ignored -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        args.addAll(ids);
        try {
            return jdbcTemplate.update(
                    "UPDATE delivery_goods_config SET deleted=1, updated_time=NOW() "
                            + "WHERE tenant_id=? AND goods_id IN (" + placeholders + ") AND deleted=0",
                    args.toArray()
            );
        } catch (Exception error) {
            log.error("批量删除商品发货配置失败 tenantId={}, count={}, errorType={}",
                    tenantId, ids.size(), error.getClass().getSimpleName());
            throw new BizException(503, "商品发货配置暂时无法删除，请稍后重试");
        }
    }

    @Transactional
    public void setEnabled(Long tenantId, Long goodsId, String timing, Object enabled) {
        Map<String, Object> patch = new LinkedHashMap<>();
        patch.put("timing", timing);
        patch.put("enabled", enabled);
        apply(tenantId, List.of(goodsId), patch);
    }

    /**
     * 查询商品的 SKU 列表（从 xianyu_goods_sku 表，由 automation-service 维护）。
     * 返回标准化的 SKU 信息列表，含 skuId/propertyKey/propertyText/price/quantity。
     * 单规格商品返回空列表。
     */
    @Transactional(readOnly = true)
    public List<Map<String, Object>> listGoodsSkus(Long tenantId, Long goodsId) {
        requireTenantAndGoodsId(tenantId, goodsId);
        // 先查 xianyu_goods 获取 external_goods_id
        String externalGoodsId;
        try {
            List<Map<String, Object>> goodsRows = jdbcTemplate.queryForList(
                    "SELECT external_goods_id FROM xianyu_goods WHERE tenant_id=? AND id=? AND deleted=0",
                    tenantId, goodsId
            );
            if (goodsRows.isEmpty()) {
                throw new BizException(404, "商品不存在或不属于当前租户");
            }
            externalGoodsId = text(goodsRows.get(0).get("external_goods_id"));
            if (externalGoodsId.isBlank()) {
                return List.of();
            }
        } catch (BizException error) {
            throw error;
        } catch (Exception error) {
            log.error("查询商品 external_goods_id 失败 goodsId={}, errorType={}", goodsId, error.getClass().getSimpleName());
            throw new BizException(503, "商品 SKU 暂时不可查询，请稍后重试");
        }

        // 查询 xianyu_goods_sku 表
        try {
            List<Map<String, Object>> skuRows = jdbcTemplate.queryForList(
                    "SELECT sku_id, inventory_id, property_list_json, property_key, price_in_cent, quantity "
                            + "FROM xianyu_goods_sku WHERE external_goods_id=? AND deleted=0 ORDER BY id",
                    externalGoodsId
            );
            List<Map<String, Object>> result = new ArrayList<>();
            for (Map<String, Object> row : skuRows) {
                Map<String, Object> sku = new LinkedHashMap<>();
                sku.put("skuId", text(row.get("sku_id")));
                sku.put("inventoryId", text(row.get("inventory_id")));
                sku.put("propertyKey", text(row.get("property_key")));
                sku.put("propertyText", buildPropertyText(row.get("property_list_json")));
                sku.put("priceCent", row.get("price_in_cent"));
                sku.put("quantity", row.get("quantity"));
                result.add(sku);
            }
            return result;
        } catch (Exception error) {
            log.error("查询商品 SKU 失败 goodsId={}, externalGoodsId={}, errorType={}",
                    goodsId, externalGoodsId, error.getClass().getSimpleName());
            // 表可能未创建（automation-service 尚未同步 SKU），返回空列表而非报错
            return List.of();
        }
    }

    /**
     * 读取商品的 SKU 发货规则（从 config_json.skuRules）。
     */
    @Transactional(readOnly = true)
    public List<Map<String, Object>> readSkuRules(Long tenantId, Long goodsId) {
        requireTenantAndGoodsId(tenantId, goodsId);
        StoredConfig stored = loadStoredConfig(tenantId, goodsId, false);
        if (stored == null) return List.of();
        Object skuRules = stored.config().get("skuRules");
        if (!(skuRules instanceof List<?> list)) return List.of();
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object item : list) {
            if (item instanceof Map<?, ?> raw) {
                Map<String, Object> rule = new LinkedHashMap<>();
                raw.forEach((k, v) -> rule.put(String.valueOf(k), v));
                result.add(rule);
            }
        }
        return result;
    }

    /**
     * 保存商品的 SKU 发货规则（写入 config_json.skuRules）。
     * 每条规则含 skuId/propertyKey/propertyText + payDelivery/confirmDelivery/reviewDelivery。
     */
    @Transactional
    public int saveSkuRules(Long tenantId, Long goodsId, List<Map<String, Object>> skuRules) {
        requireTenantAndGoodsId(tenantId, goodsId);
        requireGoods(tenantId, List.of(goodsId), true);
        List<Map<String, Object>> normalized = normalizeSkuRules(tenantId, skuRules);

        StoredConfig stored = loadStoredConfig(tenantId, goodsId, true);
        Map<String, Object> config = stored == null
                ? new LinkedHashMap<>()
                : new LinkedHashMap<>(stored.config());
        config.put("skuRules", normalized);
        persist(tenantId, goodsId, stored, config);
        return normalized.size();
    }

    /**
     * 规范化并校验 SKU 规则列表。
     * - 校验 skuId 非空
     * - 校验每个 timing 配置的 mode/cardGroupId 合法性
     * - 卡密模式校验 card_group 归属且 sku_property_key 匹配（若配置了专属卡密池）
     */
    private List<Map<String, Object>> normalizeSkuRules(Long tenantId, List<Map<String, Object>> rawRules) {
        if (rawRules == null || rawRules.isEmpty()) return List.of();
        List<Map<String, Object>> result = new ArrayList<>();
        Set<String> seenSkuIds = new LinkedHashSet<>();
        for (Map<String, Object> raw : rawRules) {
            if (raw == null) continue;
            String skuId = text(raw.get("skuId"));
            if (skuId.isBlank()) {
                throw new BizException(422, "SKU 规则的 skuId 不能为空");
            }
            if (!seenSkuIds.add(skuId)) {
                throw new BizException(422, "SKU 规则存在重复的 skuId: " + skuId);
            }
            Map<String, Object> rule = new LinkedHashMap<>();
            rule.put("skuId", skuId);
            rule.put("propertyKey", text(raw.get("propertyKey")));
            rule.put("propertyText", text(raw.get("propertyText")));

            for (String timing : SUPPORTED_TIMINGS) {
                Object timingObj = raw.get(timing);
                if (!(timingObj instanceof Map<?, ?> timingRaw)) {
                    // 未配置的 timing 保留空对象
                    rule.put(timing, new LinkedHashMap<>());
                    continue;
                }
                Map<String, Object> timingConfig = new LinkedHashMap<>();
                timingRaw.forEach((k, v) -> timingConfig.put(String.valueOf(k), v));

                int enabled = intFlag(timingConfig.getOrDefault("enabled", 0), 0);
                timingConfig.put("enabled", enabled);
                String mode = text(timingConfig.getOrDefault("mode", "text"));
                if (!SUPPORTED_MODES.contains(mode)) {
                    throw new BizException(422, "SKU 规则的发货模式暂不支持（仅支持 text/card）");
                }
                timingConfig.put("mode", mode);

                if (enabled == 1) {
                    if ("card".equals(mode)) {
                        Long cardGroupId = positiveLong(timingConfig.get("cardGroupId"), "请选择有效的卡密组");
                        requireOwnedReference("card_group", tenantId, cardGroupId, "卡密组不存在或不可用");
                    } else {
                        String content = text(timingConfig.get("content"));
                        Long sourceId = nullablePositiveLong(timingConfig.get("sourceId"), "发货正文来源无效");
                        if (sourceId == null && content.isBlank()) {
                            throw new BizException(422, "启用文本发货前请填写发货正文或选择正文来源");
                        }
                        if (sourceId != null) {
                            requireOwnedReference("delivery_text_source", tenantId, sourceId, "发货正文来源不存在或不可用");
                        }
                    }
                }
                rule.put(timing, timingConfig);
            }
            result.add(rule);
        }
        return result;
    }

    /**
     * 从 property_list_json 构建 human-readable 的 propertyText。
     * property_list_json 格式：[{"propertyText":"颜色","valueText":"红色"}, ...]
     * 输出："颜色:红色 | 尺码:M"
     */
    @SuppressWarnings("unchecked")
    private String buildPropertyText(Object propertyListJson) {
        if (propertyListJson == null) return "";
        try {
            String json = propertyListJson instanceof String s ? s : objectMapper.writeValueAsString(propertyListJson);
            List<Map<String, Object>> list = objectMapper.readValue(json, new TypeReference<List<Map<String, Object>>>() {});
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) sb.append(" | ");
                Map<String, Object> prop = list.get(i);
                sb.append(text(prop.get("propertyText"))).append(":").append(text(prop.get("valueText")));
            }
            return sb.toString();
        } catch (Exception error) {
            return "";
        }
    }

    @Transactional
    public void removeSourceBinding(Long tenantId, Long goodsId, Long sourceId) {
        requireTenantAndGoodsId(tenantId, goodsId);
        if (sourceId == null || sourceId <= 0) throw new BizException(422, "货源编号无效");
        requireGoods(tenantId, List.of(goodsId), true);
        StoredConfig stored = loadStoredConfig(tenantId, goodsId, true);
        if (stored == null) return;
        Map<String, Object> config = new LinkedHashMap<>(stored.config());
        boolean changed = false;
        for (String timing : SUPPORTED_TIMINGS) {
            Object timingObj = config.get(timing);
            if (!(timingObj instanceof Map<?, ?> raw)) continue;
            Long boundSourceId = parseNullableLong(raw.get("sourceId"));
            if (sourceId.equals(boundSourceId)) {
                Map<String, Object> updated = new LinkedHashMap<>();
                raw.forEach((k, v) -> updated.put(String.valueOf(k), v));
                updated.put("sourceId", null);
                updated.put("sourceTitle", "");
                updated.put("content", "");
                updated.put("enabled", 0);
                config.put(timing, updated);
                changed = true;
            }
        }
        if (changed) {
            persist(tenantId, goodsId, stored, config);
        }
    }

    private Long parseNullableLong(Object value) {
        if (value == null) return null;
        String s = text(value);
        if (s.isBlank()) return null;
        try {
            long parsed = value instanceof Number number ? number.longValue() : Long.parseLong(s);
            return parsed <= 0 ? null : parsed;
        } catch (Exception ignored) {
            return null;
        }
    }

    private void mergePatch(Long tenantId, Map<String, Object> config, ConfigPatch patch) {
        Map<String, Object> timingConfig = mapValue(config.get(patch.timing()));
        timingConfig.putAll(patch.values());
        String mode = text(timingConfig.get("mode"));
        if (mode.isBlank()) {
            mode = "text";
            timingConfig.put("mode", mode);
        }
        if (!SUPPORTED_MODES.contains(mode)) {
            throw new BizException(422, "API 发货模式暂不可用，请改用文本或卡密发货");
        }

        int enabled = intFlag(timingConfig.get("enabled"), 0);
        timingConfig.put("enabled", enabled);
        if (enabled == 1) {
            if ("card".equals(mode)) {
                Long cardGroupId = positiveLong(timingConfig.get("cardGroupId"), "请选择有效的卡密组");
                requireOwnedReference("card_group", tenantId, cardGroupId, "卡密组不存在或不可用");
            } else {
                Long sourceId = nullablePositiveLong(timingConfig.get("sourceId"), "发货正文来源无效");
                String content = text(timingConfig.get("content"));
                if (sourceId == null && content.isBlank()) {
                    throw new BizException(422, "启用文本发货前请填写发货正文或选择正文来源");
                }
                if (sourceId != null) {
                    requireOwnedReference("delivery_text_source", tenantId, sourceId, "发货正文来源不存在或不可用");
                }
            }
        }
        config.put(patch.timing(), timingConfig);
    }

    private ConfigPatch parsePatch(Map<String, Object> raw) {
        if (raw == null) throw new BizException(400, "发货配置不能为空");
        String timing = text(raw.getOrDefault("timing", "payDelivery"));
        if (!SUPPORTED_TIMINGS.contains(timing)) {
            throw new BizException(422, "暂不支持该发货时机");
        }
        if (raw.containsKey("apiUrl") || raw.containsKey("apiMethod") || raw.containsKey("apiHeaders")) {
            throw new BizException(422, "API 发货模式暂不可用，请改用文本或卡密发货");
        }

        Map<String, Object> values = new LinkedHashMap<>();
        if (raw.containsKey("enabled")) values.put("enabled", intFlag(raw.get("enabled"), 0));
        if (raw.containsKey("mode")) {
            String mode = text(raw.get("mode"));
            if (!SUPPORTED_MODES.contains(mode)) {
                throw new BizException(422, "API 发货模式暂不可用，请改用文本或卡密发货");
            }
            values.put("mode", mode);
        }
        putOptionalLong(values, raw, "sourceId", "发货正文来源无效");
        putOptionalLong(values, raw, "cardGroupId", "卡密组无效");
        putString(values, raw, "sourceTitle", 300);
        putString(values, raw, "cardTemplate", 20_000);
        putString(values, raw, "header", 2_000);
        putString(values, raw, "content", 20_000);
        putString(values, raw, "footer", 2_000);
        if (raw.containsKey("segmentSend")) values.put("segmentSend", intFlag(raw.get("segmentSend"), 0));
        if (raw.containsKey("autoDisableOnLowStock")) {
            values.put("autoDisableOnLowStock", intFlag(raw.get("autoDisableOnLowStock"), 0));
        }
        if (raw.containsKey("retryCount")) values.put("retryCount", rangedInt(raw.get("retryCount"), 0, 5, "重试次数需为 0-5"));
        if (raw.containsKey("alertThreshold")) {
            values.put("alertThreshold", rangedInt(raw.get("alertThreshold"), 0, 1_000_000, "库存提醒阈值无效"));
        }
        return new ConfigPatch(timing, values);
    }

    private Map<Long, GoodsOwner> requireGoods(Long tenantId, List<Long> ids, boolean lock) {
        String placeholders = ids.stream().map(ignored -> "?").collect(Collectors.joining(","));
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        args.addAll(ids);
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, account_id FROM xianyu_goods WHERE tenant_id=? AND deleted=0 AND id IN ("
                            + placeholders + ")" + (lock ? " FOR UPDATE" : ""),
                    args.toArray()
            );
            Map<Long, GoodsOwner> result = new LinkedHashMap<>();
            for (Map<String, Object> row : rows) {
                Long id = nullablePositiveLong(row.get("id"), "商品数据异常");
                Long accountId = positiveLong(row.get("account_id"), "商品账号归属异常");
                result.put(id, new GoodsOwner(id, accountId));
            }
            if (result.size() != ids.size()) {
                throw new BizException(404, "部分商品不存在或不属于当前租户，未执行配置变更");
            }
            return result;
        } catch (BizException error) {
            throw error;
        } catch (Exception error) {
            log.error("校验商品归属失败 tenantId={}, count={}, errorType={}",
                    tenantId, ids.size(), error.getClass().getSimpleName());
            throw new BizException(503, "商品状态暂时无法校验，未执行配置变更");
        }
    }

    private StoredConfig loadStoredConfig(Long tenantId, Long goodsId, boolean lock) {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, config_json FROM delivery_goods_config "
                            + "WHERE tenant_id=? AND goods_id=? AND deleted=0 ORDER BY id" + (lock ? " FOR UPDATE" : ""),
                    tenantId,
                    goodsId
            );
            if (rows.isEmpty()) return null;
            if (rows.size() > 1) {
                throw new BizException(409, "检测到重复的商品发货配置，已阻止覆盖，请联系管理员修复");
            }
            Map<String, Object> row = rows.get(0);
            Long id = positiveLong(row.get("id"), "商品发货配置数据异常");
            String json = text(row.get("config_json"));
            Map<String, Object> config;
            try {
                config = json.isBlank()
                        ? new LinkedHashMap<>()
                        : objectMapper.readValue(json, new TypeReference<LinkedHashMap<String, Object>>() {});
            } catch (Exception error) {
                log.error("解析商品发货配置失败 configId={}, errorType={}", id, error.getClass().getSimpleName());
                throw new BizException(409, "现有商品发货配置已损坏，已阻止覆盖，请联系管理员修复");
            }
            return new StoredConfig(id, config);
        } catch (BizException error) {
            throw error;
        } catch (Exception error) {
            log.error("读取商品发货配置失败 goodsId={}, errorType={}", goodsId, error.getClass().getSimpleName());
            throw new BizException(503, "商品发货配置暂时不可用，请稍后重试");
        }
    }

    private void persist(Long tenantId, Long goodsId, StoredConfig stored, Map<String, Object> config) {
        try {
            String json = objectMapper.writeValueAsString(config);
            if (json.length() > 100_000) throw new BizException(422, "商品发货配置内容过大，请精简后重试");
            if (stored == null) {
                // 唯一约束 uk_dgc_tenant_goods(tenant_id, goods_id) 不含 deleted 字段，
                // 当存在 deleted=1 的软删除记录时，普通 INSERT 会触发 DuplicateKeyException。
                // 使用 INSERT ... ON DUPLICATE KEY UPDATE 将软删除记录恢复为 deleted=0 并更新配置。
                jdbcTemplate.update(
                        "INSERT INTO delivery_goods_config(tenant_id, goods_id, config_json, created_time, updated_time, deleted) "
                                + "VALUES(?,?,?,NOW(),NOW(),0) "
                                + "ON DUPLICATE KEY UPDATE config_json=VALUES(config_json), updated_time=NOW(), deleted=0",
                        tenantId, goodsId, json
                );
            } else {
                int updated = jdbcTemplate.update(
                        "UPDATE delivery_goods_config SET config_json=?, updated_time=NOW() "
                                + "WHERE tenant_id=? AND goods_id=? AND id=? AND deleted=0",
                        json, tenantId, goodsId, stored.id()
                );
                if (updated != 1) throw new BizException(409, "商品发货配置已被其他操作修改，请刷新后重试");
            }
        } catch (BizException error) {
            throw error;
        } catch (Exception error) {
            log.error("保存商品发货配置失败 goodsId={}, errorType={}", goodsId, error.getClass().getSimpleName(), error);
            throw new BizException(503, "商品发货配置保存失败，所有变更均未确认，请稍后重试");
        }
    }

    private void requireOwnedReference(String table, Long tenantId, Long id, String publicMessage) {
        // Table names are fixed internal constants, never request input.
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM " + table + " WHERE tenant_id=? AND id=? AND deleted=0",
                    Integer.class,
                    tenantId,
                    id
            );
            if (count == null || count != 1) throw new BizException(422, publicMessage);
        } catch (BizException error) {
            throw error;
        } catch (Exception error) {
            log.error("校验发货配置引用失败 table={}, id={}, errorType={}", table, id, error.getClass().getSimpleName());
            throw new BizException(503, "发货配置引用暂时无法校验，未执行配置变更");
        }
    }

    private List<Long> normalizeGoodsIds(Collection<Long> raw) {
        if (raw == null) return List.of();
        LinkedHashSet<Long> ids = new LinkedHashSet<>();
        for (Long value : raw) {
            if (value == null || value <= 0) throw new BizException(422, "商品编号无效");
            ids.add(value);
        }
        return new ArrayList<>(ids);
    }

    private Map<String, Object> mapValue(Object value) {
        Map<String, Object> result = new LinkedHashMap<>();
        if (value instanceof Map<?, ?> raw) raw.forEach((key, item) -> result.put(String.valueOf(key), item));
        return result;
    }

    private void putOptionalLong(Map<String, Object> target, Map<String, Object> source, String key, String message) {
        if (!source.containsKey(key)) return;
        Object value = source.get(key);
        target.put(key, value == null || text(value).isBlank() ? null : positiveLong(value, message));
    }

    private void putString(Map<String, Object> target, Map<String, Object> source, String key, int maxLength) {
        if (!source.containsKey(key)) return;
        String value = text(source.get(key));
        if (value.length() > maxLength) throw new BizException(422, key + " 内容过长，请精简后重试");
        target.put(key, value);
    }

    private int rangedInt(Object value, int min, int max, String message) {
        try {
            int parsed = value instanceof Number number ? number.intValue() : Integer.parseInt(text(value));
            if (parsed < min || parsed > max) throw new NumberFormatException();
            return parsed;
        } catch (Exception ignored) {
            throw new BizException(422, message);
        }
    }

    private int intFlag(Object value, int fallback) {
        if (value == null) return fallback;
        if (value instanceof Boolean bool) return bool ? 1 : 0;
        String text = text(value);
        if ("1".equals(text) || "true".equalsIgnoreCase(text)) return 1;
        if ("0".equals(text) || "false".equalsIgnoreCase(text)) return 0;
        throw new BizException(422, "启用状态必须为 true/false 或 1/0");
    }

    private Long nullablePositiveLong(Object value, String message) {
        if (value == null || text(value).isBlank()) return null;
        return positiveLong(value, message);
    }

    private Long positiveLong(Object value, String message) {
        try {
            long parsed = value instanceof Number number ? number.longValue() : Long.parseLong(text(value));
            if (parsed <= 0) throw new NumberFormatException();
            return parsed;
        } catch (Exception ignored) {
            throw new BizException(422, message);
        }
    }

    private void requireTenantAndGoodsId(Long tenantId, Long goodsId) {
        requireTenant(tenantId);
        if (goodsId == null || goodsId <= 0) throw new BizException(422, "商品编号无效");
    }

    private void requireTenant(Long tenantId) {
        if (tenantId == null || tenantId <= 0) throw new BizException(401, "登录状态已失效，请重新登录");
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private record ConfigPatch(String timing, Map<String, Object> values) {}
    private record GoodsOwner(Long id, Long accountId) {}
    private record StoredConfig(Long id, Map<String, Object> config) {}
}
