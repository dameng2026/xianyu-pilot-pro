package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.time.LocalDateTime;
import java.net.URI;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.Set;
import java.util.function.Supplier;

@Service
public class OpenSourceContentService {
    private static final Logger log = LoggerFactory.getLogger(OpenSourceContentService.class);

    private static final String HOME_MODULE_KEY = "open-source-home";
    private static final String COMMERCIAL_HOME_MODULE_KEY = "commercial-home";
    private static final String ABOUT_MODULE_KEY = "open-source-about";
    private static final String CONFIG_STATUS = "config";
    private static final int MAX_CAROUSEL_RECORDS = 50;
    private static final int MAX_COVERS_PER_CAROUSEL = 10;
    private static final int MAX_ANNOUNCEMENT_RECORDS = 100;
    private static final Set<String> ABOUT_ACTION_TYPES = Set.of(
            "", "toast", "external", "mailto", "legal", "download", "copy", "navigate"
    );

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public OpenSourceContentService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<Map<String, Object>> listHomeCarousels() {
        return listHomeCarousels(HOME_MODULE_KEY);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> saveHomeCarousel(Map<String, Object> input) {
        return saveHomeCarousel(HOME_MODULE_KEY, input);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> updateHomeCarousel(Map<String, Object> input) {
        return updateHomeCarousel(HOME_MODULE_KEY, input);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> deleteHomeCarousel(long id) {
        return deleteHomeCarousel(HOME_MODULE_KEY, id);
    }

    public List<Map<String, Object>> listHomeAnnouncements() {
        return listHomeAnnouncements(HOME_MODULE_KEY);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> saveHomeAnnouncement(Map<String, Object> input) {
        return saveHomeAnnouncement(HOME_MODULE_KEY, input);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> updateHomeAnnouncement(Map<String, Object> input) {
        return updateHomeAnnouncement(HOME_MODULE_KEY, input);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> deleteHomeAnnouncement(long id) {
        return deleteHomeAnnouncement(HOME_MODULE_KEY, id);
    }

    /** Commercial user-web content. Kept separate from the open-source bridge payload. */
    public List<Map<String, Object>> listCommercialHomeCarousels() {
        return listHomeCarousels(COMMERCIAL_HOME_MODULE_KEY);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> saveCommercialHomeCarousel(Map<String, Object> input) {
        return saveHomeCarousel(COMMERCIAL_HOME_MODULE_KEY, input);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> updateCommercialHomeCarousel(Map<String, Object> input) {
        return updateHomeCarousel(COMMERCIAL_HOME_MODULE_KEY, input);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> deleteCommercialHomeCarousel(long id) {
        return deleteHomeCarousel(COMMERCIAL_HOME_MODULE_KEY, id);
    }

    public List<Map<String, Object>> listCommercialHomeAnnouncements() {
        return listHomeAnnouncements(COMMERCIAL_HOME_MODULE_KEY);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> saveCommercialHomeAnnouncement(Map<String, Object> input) {
        return saveHomeAnnouncement(COMMERCIAL_HOME_MODULE_KEY, input);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> updateCommercialHomeAnnouncement(Map<String, Object> input) {
        return updateHomeAnnouncement(COMMERCIAL_HOME_MODULE_KEY, input);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> deleteCommercialHomeAnnouncement(long id) {
        return deleteHomeAnnouncement(COMMERCIAL_HOME_MODULE_KEY, id);
    }

    private List<Map<String, Object>> listHomeCarousels(String moduleKey) {
        Map<String, Object> config = getHomeConfig(moduleKey, false);
        Object rows = config.get("carousels");
        if (!(rows instanceof List<?> list)) {
            return new ArrayList<>();
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object item : list) {
            if (result.size() >= MAX_CAROUSEL_RECORDS) break;
            if (item instanceof Map<?, ?> map) {
                long id = number(itemValue(map, "id"), 0L);
                if (id > 0) {
                    result.add(normalizeCarousel(castMap(map), id, text(itemValue(map, "createdAt")), false));
                }
            }
        }
        result.sort((left, right) -> Integer.compare(number(left.get("sortOrder"), 0), number(right.get("sortOrder"), 0)));
        return result;
    }

    private Map<String, Object> saveHomeCarousel(String moduleKey, Map<String, Object> input) {
        validateCarouselInput(input);
        return withContentLock(moduleKey, () -> {
            Map<String, Object> config = getHomeConfig(moduleKey, true);
            List<Map<String, Object>> items = mutableMapList(config.get("carousels"));
            if (items.size() >= MAX_CAROUSEL_RECORDS) {
                throw new BizException(409, "轮播配置数量已达上限，请先删除不再使用的配置");
            }
            long nextId = nextId(items);
            Map<String, Object> normalized = normalizeCarousel(input, nextId, null, true);
            items.add(normalized);
            config.put("carousels", items);
            saveHomeConfig(moduleKey, config);
            return normalized;
        });
    }

    private Map<String, Object> updateHomeCarousel(String moduleKey, Map<String, Object> input) {
        validateCarouselInput(input);
        long id = number(input.get("id"), 0L);
        if (id <= 0) {
            throw new BizException(400, "轮播图 ID 不能为空");
        }
        return withContentLock(moduleKey, () -> {
            Map<String, Object> config = getHomeConfig(moduleKey, true);
            List<Map<String, Object>> items = mutableMapList(config.get("carousels"));
            for (int index = 0; index < items.size(); index += 1) {
                Map<String, Object> current = items.get(index);
                if (number(current.get("id"), 0L) == id) {
                    Map<String, Object> merged = new LinkedHashMap<>(current);
                    merged.putAll(input);
                    Map<String, Object> normalized = normalizeCarousel(merged, id, text(current.get("createdAt")), true);
                    items.set(index, normalized);
                    config.put("carousels", items);
                    saveHomeConfig(moduleKey, config);
                    return normalized;
                }
            }
            throw new BizException(404, "轮播图不存在");
        });
    }

    private Map<String, Object> deleteHomeCarousel(String moduleKey, long id) {
        if (id <= 0) throw new BizException(400, "轮播图 ID 无效");
        return withContentLock(moduleKey, () -> {
            Map<String, Object> config = getHomeConfig(moduleKey, true);
            List<Map<String, Object>> items = mutableMapList(config.get("carousels"));
            for (int index = 0; index < items.size(); index += 1) {
                Map<String, Object> current = items.get(index);
                if (number(current.get("id"), 0L) == id) {
                    Map<String, Object> removed = items.remove(index);
                    config.put("carousels", items);
                    saveHomeConfig(moduleKey, config);
                    return removed;
                }
            }
            throw new BizException(404, "轮播图不存在");
        });
    }

    private List<Map<String, Object>> listHomeAnnouncements(String moduleKey) {
        Map<String, Object> config = getHomeConfig(moduleKey, false);
        Object rows = config.get("announcements");
        if (!(rows instanceof List<?> list)) {
            return new ArrayList<>();
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object item : list) {
            if (result.size() >= MAX_ANNOUNCEMENT_RECORDS) break;
            if (item instanceof Map<?, ?> map) {
                long id = number(itemValue(map, "id"), 0L);
                Map<String, Object> source = castMap(map);
                if (id > 0 && !text(firstPresent(source, "title", "name")).isBlank()
                        && !text(firstPresent(source, "content", "body", "desc")).isBlank()) {
                    result.add(normalizeAnnouncement(source, id, text(itemValue(map, "createdAt")), false));
                }
            }
        }
        return result;
    }

    private Map<String, Object> saveHomeAnnouncement(String moduleKey, Map<String, Object> input) {
        validateAnnouncementInput(input);
        return withContentLock(moduleKey, () -> {
            Map<String, Object> config = getHomeConfig(moduleKey, true);
            List<Map<String, Object>> items = mutableMapList(config.get("announcements"));
            if (items.size() >= MAX_ANNOUNCEMENT_RECORDS) {
                throw new BizException(409, "公告数量已达上限，请先删除历史公告");
            }
            long nextId = nextId(items);
            Map<String, Object> normalized = normalizeAnnouncement(input, nextId, null, true);
            items.add(normalized);
            config.put("announcements", items);
            saveHomeConfig(moduleKey, config);
            return normalized;
        });
    }

    private Map<String, Object> updateHomeAnnouncement(String moduleKey, Map<String, Object> input) {
        validateAnnouncementInput(input);
        long id = number(input.get("id"), 0L);
        if (id <= 0) {
            throw new BizException(400, "首页公告 ID 不能为空");
        }
        return withContentLock(moduleKey, () -> {
            Map<String, Object> config = getHomeConfig(moduleKey, true);
            List<Map<String, Object>> items = mutableMapList(config.get("announcements"));
            for (int index = 0; index < items.size(); index += 1) {
                Map<String, Object> current = items.get(index);
                if (number(current.get("id"), 0L) == id) {
                    Map<String, Object> merged = new LinkedHashMap<>(current);
                    merged.putAll(input);
                    Map<String, Object> normalized = normalizeAnnouncement(merged, id, text(current.get("createdAt")), true);
                    items.set(index, normalized);
                    config.put("announcements", items);
                    saveHomeConfig(moduleKey, config);
                    return normalized;
                }
            }
            throw new BizException(404, "首页公告不存在");
        });
    }

    private Map<String, Object> deleteHomeAnnouncement(String moduleKey, long id) {
        if (id <= 0) throw new BizException(400, "首页公告 ID 无效");
        return withContentLock(moduleKey, () -> {
            Map<String, Object> config = getHomeConfig(moduleKey, true);
            List<Map<String, Object>> items = mutableMapList(config.get("announcements"));
            for (int index = 0; index < items.size(); index += 1) {
                Map<String, Object> current = items.get(index);
                if (number(current.get("id"), 0L) == id) {
                    Map<String, Object> removed = items.remove(index);
                    config.put("announcements", items);
                    saveHomeConfig(moduleKey, config);
                    return removed;
                }
            }
            throw new BizException(404, "首页公告不存在");
        });
    }

    public Map<String, Object> getAboutContent() {
        Map<String, Object> raw = loadConfig(ABOUT_MODULE_KEY, CONFIG_STATUS, defaultAboutContent(), false);
        Map<String, Object> defaults = defaultAboutContent();
        Map<String, Object> merged = new LinkedHashMap<>(defaults);
        merged.putAll(raw);
        merged.put("logs", normalizeList(raw.get("logs"), defaults.get("logs")));
        merged.put("supports", normalizeList(raw.get("supports"), defaults.get("supports")));
        merged.put("communityCards", normalizeList(raw.get("communityCards"), defaults.get("communityCards")));
        merged.put("links", normalizeList(raw.get("links"), defaults.get("links")));
        merged.put("legalDocs", normalizeMap(raw.get("legalDocs"), castMap(defaults.get("legalDocs"))));
        return sanitizeAboutForRead(merged, defaults);
    }

    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> saveAboutContent(Map<String, Object> input) {
        Map<String, Object> defaults = defaultAboutContent();
        Map<String, Object> payload = new LinkedHashMap<>(defaults);
        if (input != null) {
            payload.putAll(input);
        }
        payload.put("heroTitle", textOr(payload.get("heroTitle"), text(defaults.get("heroTitle"))));
        payload.put("heroBadgeText", textOr(payload.get("heroBadgeText"), text(defaults.get("heroBadgeText"))));
        payload.put("heroDescription", textOr(payload.get("heroDescription"), text(defaults.get("heroDescription"))));
        payload.put("serviceStatusText", textOr(payload.get("serviceStatusText"), text(defaults.get("serviceStatusText"))));
        payload.put("logs", normalizeList(payload.get("logs"), defaults.get("logs")));
        payload.put("supports", normalizeList(payload.get("supports"), defaults.get("supports")));
        payload.put("communityCards", normalizeList(payload.get("communityCards"), defaults.get("communityCards")));
        payload.put("links", normalizeList(payload.get("links"), defaults.get("links")));
        payload.put("legalDocs", normalizeMap(payload.get("legalDocs"), castMap(defaults.get("legalDocs"))));
        validateAboutPayload(payload);
        return withContentLock(ABOUT_MODULE_KEY, () -> {
            saveConfig(ABOUT_MODULE_KEY, CONFIG_STATUS, payload);
            return payload;
        });
    }

    private Map<String, Object> getHomeConfig(String moduleKey, boolean forUpdate) {
        Map<String, Object> defaults = defaultHomeConfig();
        Map<String, Object> raw = loadConfig(moduleKey, CONFIG_STATUS, defaults, forUpdate);
        Map<String, Object> merged = new LinkedHashMap<>(defaults);
        merged.putAll(raw);
        merged.put("carousels", mutableMapList(merged.get("carousels")));
        merged.put("announcements", mutableMapList(merged.get("announcements")));
        return merged;
    }

    private void saveHomeConfig(String moduleKey, Map<String, Object> config) {
        saveConfig(moduleKey, CONFIG_STATUS, config);
    }

    private Map<String, Object> defaultHomeConfig() {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("carousels", new ArrayList<>());
        config.put("announcements", new ArrayList<>());
        return config;
    }

    private Map<String, Object> defaultAboutContent() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("heroTitle", "XianYuAssistant 闲鱼助手");
        result.put("heroBadgeText", "智能运营版");
        result.put("heroDescription", "让闲鱼生意更简单，智能化运营更稳定。");
        result.put("serviceStatusText", "服务状态待检测");

        List<Map<String, Object>> logs = new ArrayList<>();
        Map<String, Object> logItem = new LinkedHashMap<>();
        logItem.put("v", "");
        logItem.put("t", "");
        logItem.put("tone", "major");
        logItem.put("d", "开源版前台已预留商业版后台桥接能力，可动态管理首页内容、关于页和用户反馈。");
        logItem.put("sections", List.of(
                Map.of("t", "桥接模式", "d", "开源版只通过后端接口读取或写入商业版数据，不暴露商业版数据库。"),
                Map.of("t", "动态管理", "d", "轮播、关于页、广告位和反馈需按 siteCode=open-source 独立管理。")
        ));
        logItem.put("tags", List.of("商业版对接", "动态管理", "开源版桥接"));
        logs.add(logItem);
        result.put("logs", logs);

        result.put("supports", List.of(
                aboutSupport("官方网站", "需由管理员配置正式站点", "aboutSupportWeb", "blue", "toast", "", "官方网站尚未配置"),
                aboutSupport("管理后台", "需由管理员配置可访问的后台入口", "aboutSupportDoc", "green", "toast", "", "管理后台入口尚未配置"),
                aboutSupport("联系客服", "需由管理员配置有效客服联系方式", "aboutSupportChat", "orange", "toast", "", "客服联系方式尚未配置"),
                aboutSupport("意见反馈", "需由管理员配置有效反馈渠道", "aboutSupportFeedback", "violet", "toast", "", "反馈渠道尚未配置")
        ));

        result.put("communityCards", List.of(
                communityCard("交流群", "微信交流群", "用于版本通知、使用答疑、投放交流与功能建议收集。", "GROUP", "待后台配置微信群二维码", "blue", "toast", "配置后可扫码", "请在商业版后台配置交流群二维码"),
                communityCard("QQ群", "QQ群聊二维码", "用于版本通知、使用答疑与功能建议收集。", "QQ", "待后台配置QQ群聊二维码", "violet", "toast", "配置后可扫码", "请在商业版后台配置QQ群聊二维码"),
                communityCard("微信客服", "微信客服二维码", "用于一对一咨询、技术支持与商务合作。", "KEFU", "待后台配置微信客服二维码", "green", "toast", "配置后可扫码", "请在商业版后台配置微信客服二维码"),
                communityCard("赞助支持", "项目赞助码", "用于支持项目维护、桥接联调与后续版本更新。", "SPONSOR", "待后台配置赞助二维码", "orange", "toast", "配置后可扫码", "请在商业版后台配置赞助二维码"),
                contactCard()
        ));

        result.put("links", List.of(
                Map.of("label", "用户协议", "icon", "aboutShield", "actionText", "查看", "actionType", "legal", "actionValue", "terms"),
                Map.of("label", "隐私政策", "icon", "aboutEye", "actionText", "查看", "actionType", "legal", "actionValue", "privacy"),
                Map.of("label", "检查更新", "icon", "refresh", "actionText", "立即检查", "actionType", "toast", "actionValue", "当前已是最新版本"),
                Map.of("label", "导出诊断日志", "icon", "download", "actionText", "导出", "actionType", "download", "actionValue", "diagnostics")
        ));

        result.put("legalDocs", Map.of(
                "termsUrl", "",
                "privacyUrl", "",
                "supportEmail", ""
        ));
        return result;
    }

    private Map<String, Object> aboutSupport(
            String label,
            String desc,
            String icon,
            String tone,
            String actionType,
            String actionValue,
            String actionMessage
    ) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("label", label);
        item.put("desc", desc);
        item.put("icon", icon);
        item.put("tone", tone);
        item.put("actionType", actionType);
        item.put("actionValue", actionValue);
        item.put("actionMessage", actionMessage);
        return item;
    }

    private Map<String, Object> communityCard(
            String label,
            String title,
            String desc,
            String placeholderText,
            String hint,
            String tone,
            String actionType,
            String actionText,
            String actionValue
    ) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("label", label);
        item.put("title", title);
        item.put("desc", desc);
        item.put("placeholderText", placeholderText);
        item.put("hint", hint);
        item.put("tone", tone);
        item.put("actionType", actionType);
        item.put("actionText", actionText);
        item.put("actionValue", actionValue);
        item.put("value", "");
        item.put("imageUrl", "");
        return item;
    }

    private Map<String, Object> contactCard() {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("label", "联系方式");
        item.put("title", "商务合作方式待配置");
        item.put("desc", "管理员配置有效联系方式后，可用于广告投放、功能合作或技术支持。");
        item.put("value", "");
        item.put("hint", "尚未配置服务时间");
        item.put("tone", "green");
        item.put("actionType", "toast");
        item.put("actionText", "待管理员配置");
        item.put("actionValue", "商务合作联系方式尚未配置");
        item.put("imageUrl", "");
        item.put("placeholderText", "");
        return item;
    }

    private Map<String, Object> loadConfig(
            String moduleKey,
            String status,
            Map<String, Object> defaults,
            boolean forUpdate
    ) {
        try {
            String json = jdbcTemplate.queryForObject(
                    "SELECT json_text FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 " +
                            "ORDER BY id ASC LIMIT 1" + (forUpdate ? " FOR UPDATE" : ""),
                    String.class,
                    moduleKey,
                    status
            );
            if (json == null || json.isBlank()) {
                return new LinkedHashMap<>(defaults);
            }
            Map<String, Object> parsed = objectMapper.readValue(json, new TypeReference<LinkedHashMap<String, Object>>() {});
            Map<String, Object> merged = new LinkedHashMap<>(defaults);
            merged.putAll(parsed);
            return merged;
        } catch (EmptyResultDataAccessException ex) {
            return new LinkedHashMap<>(defaults);
        } catch (Exception ex) {
            log.error("load managed content failed: moduleKey={}, errorType={}",
                    moduleKey, ex.getClass().getSimpleName());
            throw new BizException(503, "内容配置暂时无法读取，请稍后重试");
        }
    }

    private void saveConfig(String moduleKey, String status, Map<String, Object> payload) {
        try {
            String json = objectMapper.writeValueAsString(payload);
            List<Long> existingIds = jdbcTemplate.query(
                    "SELECT id FROM admin_module_record WHERE module_key=? AND status=? AND deleted=0 ORDER BY id ASC LIMIT 1",
                    (rs, rowNum) -> rs.getLong("id"),
                    moduleKey,
                    status
            );
            Long existingId = existingIds.isEmpty() ? null : existingIds.get(0);
            if (existingId == null) {
                int inserted = jdbcTemplate.update(
                        "INSERT INTO admin_module_record(module_key, status, json_text, created_time, updated_time, deleted) VALUES(?, ?, ?, NOW(), NOW(), 0)",
                        moduleKey,
                        status,
                        json
                );
                if (inserted != 1) throw new BizException(503, "内容配置写入失败");
            } else {
                int updated = jdbcTemplate.update(
                        "UPDATE admin_module_record SET json_text=?, updated_time=NOW() WHERE id=?",
                        json,
                        existingId
                );
                if (updated != 1) throw new BizException(409, "内容配置已被修改，请刷新后重试");
            }
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("save managed content failed: moduleKey={}, errorType={}", moduleKey, ex.getClass().getSimpleName());
            throw new BizException(503, "内容配置暂时无法保存，请稍后重试");
        }
    }

    private <T> T withContentLock(String moduleKey, Supplier<T> operation) {
        String lockName = "xianyu:content:" + moduleKey;
        try {
            Integer acquired = jdbcTemplate.queryForObject("SELECT GET_LOCK(?, 5)", Integer.class, lockName);
            if (acquired == null || acquired != 1) {
                throw new BizException(409, "内容配置正在被其他管理员修改，请稍后重试");
            }
        } catch (BizException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            log.error("managed content lock acquisition failed: moduleKey={}, errorType={}",
                    moduleKey, ex.getClass().getSimpleName());
            throw new BizException(503, "内容配置暂时无法保存，请稍后重试");
        }

        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            releaseContentLock(lockName);
            throw new BizException(503, "内容配置事务暂时不可用，请稍后重试");
        }
        try {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCompletion(int status) {
                    releaseContentLock(lockName);
                }
            });
        } catch (RuntimeException ex) {
            releaseContentLock(lockName);
            throw new BizException(503, "内容配置事务暂时不可用，请稍后重试");
        }
        return operation.get();
    }

    private void releaseContentLock(String lockName) {
        try {
            Integer released = jdbcTemplate.queryForObject("SELECT RELEASE_LOCK(?)", Integer.class, lockName);
            if (released == null || released != 1) {
                log.error("managed content database lock was not released by its owner");
            }
        } catch (RuntimeException ex) {
            log.error("managed content lock release failed: errorType={}", ex.getClass().getSimpleName());
        }
    }

    private List<Map<String, Object>> mutableMapList(Object value) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    result.add(new LinkedHashMap<>(castMap(map)));
                }
            }
        }
        return result;
    }

    private List<Object> normalizeList(Object value, Object fallback) {
        if (value instanceof List<?> list) {
            return new ArrayList<>(list);
        }
        if (fallback instanceof List<?> list) {
            return new ArrayList<>(list);
        }
        return new ArrayList<>();
    }

    private Map<String, Object> normalizeMap(Object value, Map<String, Object> fallback) {
        Map<String, Object> result = new LinkedHashMap<>(fallback);
        if (value instanceof Map<?, ?> map) {
            result.putAll(castMap(map));
        }
        return result;
    }

    private void validateCarouselInput(Map<String, Object> input) {
        if (input == null) throw new BizException(400, "轮播配置不能为空");
        String title = text(input.get("title"));
        if (title.isBlank()) throw new BizException(400, "轮播标题不能为空");
        ensureTextLength(title, 100, "轮播标题");
        ensureTextLength(text(input.get("description")), 500, "轮播描述");
        ensureTextLength(text(input.get("id")), 40, "轮播标识");

        Object rawCovers = input.get("coverItems");
        List<?> covers;
        if (rawCovers == null) {
            covers = List.of(input);
        } else if (rawCovers instanceof List<?> list) {
            if (list.isEmpty()) throw new BizException(400, "请至少配置一张轮播图片");
            if (list.size() > MAX_COVERS_PER_CAROUSEL) {
                throw new BizException(400, "单个轮播最多配置 " + MAX_COVERS_PER_CAROUSEL + " 张图片");
            }
            covers = list;
        } else {
            throw new BizException(400, "轮播图片列表格式无效");
        }

        boolean hasImage = false;
        for (Object rawCover : covers) {
            if (!(rawCover instanceof Map<?, ?> map)) {
                throw new BizException(400, "轮播图片配置格式无效");
            }
            Map<String, Object> cover = castMap(map);
            String imageUrl = textOr(firstPresent(cover, "imageUrl", "url", "image"), "");
            if (!imageUrl.isBlank()) {
                safeCarouselImage(imageUrl, true);
                hasImage = true;
            }
            safeCarouselLink(textOr(firstPresent(cover, "linkUrl", "targetUrl"), ""), true);
            ensureTextLength(text(cover.get("id")), 80, "轮播图片标识");
            ensureTextLength(text(cover.get("title")), 100, "轮播图片标题");
            ensureTextLength(text(cover.get("description")), 500, "轮播图片描述");
            String sourceType = text(cover.get("sourceType")).toLowerCase();
            if (!sourceType.isBlank() && !sourceType.equals("upload") && !sourceType.equals("url")) {
                throw new BizException(400, "轮播图片来源类型无效");
            }
            validateSortOrder(cover.get("sortOrder"));
        }
        if (!hasImage) throw new BizException(400, "请至少配置一张有效的轮播图片");
        validateSortOrder(input.get("sortOrder"));
    }

    private void validateAnnouncementInput(Map<String, Object> input) {
        if (input == null) throw new BizException(400, "公告配置不能为空");
        String title = textOr(firstPresent(input, "title", "name"), "");
        String content = textOr(firstPresent(input, "content", "body", "desc"), "");
        if (title.isBlank()) throw new BizException(400, "公告标题不能为空");
        if (content.isBlank()) throw new BizException(400, "公告正文不能为空");
        ensureTextLength(title, 100, "公告标题");
        ensureTextLength(content, 2_000, "公告正文");
    }

    private void validateAboutPayload(Map<String, Object> payload) {
        ensureTextLength(text(payload.get("heroTitle")), 200, "首页标题");
        ensureTextLength(text(payload.get("heroBadgeText")), 100, "首页徽标");
        ensureTextLength(text(payload.get("heroDescription")), 2_000, "首页描述");
        ensureTextLength(text(payload.get("serviceStatusText")), 200, "服务状态文案");
        ensureListSize(payload.get("logs"), 100, "更新日志");
        ensureListSize(payload.get("supports"), 50, "支持入口");
        ensureListSize(payload.get("communityCards"), 50, "社区卡片");
        ensureListSize(payload.get("links"), 100, "链接列表");
        validatePlainStructuredValue(payload, 0);
        validateLegalDocs(payload.get("legalDocs"));
        validateAboutActions(payload.get("supports"), "支持入口");
        validateAboutActions(payload.get("communityCards"), "社区卡片");
        validateAboutActions(payload.get("links"), "链接列表");
        try {
            if (objectMapper.writeValueAsBytes(payload).length > 512 * 1024) {
                throw new BizException(413, "关于页配置过大，请精简后重试");
            }
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new BizException(400, "关于页配置格式无效");
        }
    }

    private Map<String, Object> sanitizeAboutForRead(
            Map<String, Object> payload,
            Map<String, Object> defaults
    ) {
        boolean[] changed = {false};
        Object sanitized = sanitizeStructuredValue(payload, 0, changed);
        Map<String, Object> result = sanitized instanceof Map<?, ?> map
                ? new LinkedHashMap<>(castMap(map)) : new LinkedHashMap<>(defaults);
        result.put("heroTitle", safeReadText(
                result.get("heroTitle"), defaults.get("heroTitle"), 200, changed));
        result.put("heroBadgeText", safeReadText(
                result.get("heroBadgeText"), defaults.get("heroBadgeText"), 100, changed));
        result.put("heroDescription", safeReadText(
                result.get("heroDescription"), defaults.get("heroDescription"), 2_000, changed));
        result.put("serviceStatusText", safeReadText(
                result.get("serviceStatusText"), defaults.get("serviceStatusText"), 200, changed));
        result.put("logs", safeReadList(result.get("logs"), 100, changed));
        result.put("supports", sanitizeAboutActionsForRead(result.get("supports"), 50, changed));
        result.put("communityCards", sanitizeAboutActionsForRead(
                result.get("communityCards"), 50, changed));
        result.put("links", sanitizeAboutActionsForRead(result.get("links"), 100, changed));
        result.put("legalDocs", sanitizeLegalDocsForRead(result.get("legalDocs"), changed));
        if (changed[0]) {
            result.put("configurationWarning", "部分历史内容未通过安全校验，已暂时禁用；请管理员检查并重新保存配置");
        } else {
            result.remove("configurationWarning");
        }
        return result;
    }

    private Object sanitizeStructuredValue(Object value, int depth, boolean[] changed) {
        if (depth > 8) {
            changed[0] = true;
            return null;
        }
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            int count = 0;
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (count++ >= 200) {
                    changed[0] = true;
                    break;
                }
                String key = text(entry.getKey());
                if (key.isBlank() || key.length() > 80) {
                    changed[0] = true;
                    continue;
                }
                result.put(key, sanitizeStructuredValue(entry.getValue(), depth + 1, changed));
            }
            return result;
        }
        if (value instanceof List<?> list) {
            List<Object> result = new ArrayList<>();
            for (int index = 0; index < Math.min(list.size(), 200); index += 1) {
                result.add(sanitizeStructuredValue(list.get(index), depth + 1, changed));
            }
            if (list.size() > 200) changed[0] = true;
            return result;
        }
        if (value instanceof String string) {
            StringBuilder safe = new StringBuilder(Math.min(string.length(), 10_000));
            for (int offset = 0; offset < string.length() && safe.length() < 10_000;) {
                int character = string.codePointAt(offset);
                offset += Character.charCount(character);
                if (isUnsafePlainTextCodePoint(character)) {
                    changed[0] = true;
                    continue;
                }
                if (safe.length() + Character.charCount(character) > 10_000) {
                    changed[0] = true;
                    break;
                }
                safe.appendCodePoint(character);
            }
            if (string.length() > 10_000) changed[0] = true;
            return safe.toString();
        }
        if (value == null || value instanceof Number || value instanceof Boolean) return value;
        changed[0] = true;
        return null;
    }

    private String safeReadText(Object value, Object fallback, int limit, boolean[] changed) {
        boolean stringValue = value instanceof String;
        if (!stringValue) changed[0] = true;
        String result = stringValue ? textOr(value, text(fallback)) : text(fallback);
        if (result.length() > limit) {
            changed[0] = true;
            result = result.substring(0, limit);
        }
        return result;
    }

    private List<Object> safeReadList(Object value, int limit, boolean[] changed) {
        if (!(value instanceof List<?> list)) {
            changed[0] = true;
            return new ArrayList<>();
        }
        if (list.size() > limit) changed[0] = true;
        return new ArrayList<>(list.subList(0, Math.min(list.size(), limit)));
    }

    private List<Object> sanitizeAboutActionsForRead(Object value, int limit, boolean[] changed) {
        List<Object> rows = safeReadList(value, limit, changed);
        List<Object> result = new ArrayList<>();
        for (Object row : rows) {
            if (!(row instanceof Map<?, ?> rawMap)) {
                changed[0] = true;
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>(castMap(rawMap));
            String actionType = text(item.get("actionType")).toLowerCase();
            String actionValue = text(item.get("actionValue"));
            boolean actionSafe = ABOUT_ACTION_TYPES.contains(actionType);
            if (actionSafe && "external".equals(actionType)) {
                actionSafe = !actionValue.isBlank() && isSafeHttpsConfigurationUrl(actionValue);
            } else if (actionSafe && "mailto".equals(actionType)) {
                String email = actionValue.toLowerCase().startsWith("mailto:")
                        ? actionValue.substring(7) : actionValue;
                actionSafe = isSafeEmail(email);
            } else if (actionSafe && "legal".equals(actionType)) {
                actionSafe = Set.of("terms", "privacy").contains(actionValue);
            } else if (actionSafe && "navigate".equals(actionType)) {
                actionSafe = actionValue.isBlank() || !safeCarouselLink(actionValue, false).isBlank();
            }
            if (!actionSafe) {
                changed[0] = true;
                item.put("actionType", "toast");
                item.put("actionText", "暂不可用");
                item.put("actionValue", "该入口配置未通过安全校验，请联系管理员");
            }
            String imageUrl = text(item.get("imageUrl"));
            if (!imageUrl.isBlank()) {
                String safeImage = safeCarouselImage(imageUrl, false);
                if (safeImage.isBlank()) changed[0] = true;
                item.put("imageUrl", safeImage);
            }
            result.add(item);
        }
        return result;
    }

    private Map<String, Object> sanitizeLegalDocsForRead(Object value, boolean[] changed) {
        if (!(value instanceof Map<?, ?>)) changed[0] = true;
        Map<String, Object> result = value instanceof Map<?, ?> map
                ? new LinkedHashMap<>(castMap(map)) : new LinkedHashMap<>();
        for (String key : List.of("termsUrl", "privacyUrl")) {
            String url = text(result.get(key));
            if (!url.isBlank() && !isSafeHttpsConfigurationUrl(url)) {
                changed[0] = true;
                url = "";
            }
            result.put(key, url);
        }
        String email = text(result.get("supportEmail"));
        if (!email.isBlank() && !isSafeEmail(email)) {
            changed[0] = true;
            email = "";
        }
        result.put("supportEmail", email);
        return result;
    }

    private boolean isSafeHttpsConfigurationUrl(String value) {
        try {
            validateOptionalHttps(value, "配置地址");
            return !value.isBlank();
        } catch (BizException ex) {
            return false;
        }
    }

    private void validateLegalDocs(Object value) {
        if (!(value instanceof Map<?, ?> map)) throw new BizException(400, "法律与联系信息格式无效");
        validateOptionalHttps(text(map.get("termsUrl")), "用户协议地址");
        validateOptionalHttps(text(map.get("privacyUrl")), "隐私政策地址");
        String supportEmail = text(map.get("supportEmail"));
        if (!supportEmail.isBlank() && !isSafeEmail(supportEmail)) {
            throw new BizException(400, "支持邮箱格式无效");
        }
    }

    private void validateAboutActions(Object value, String label) {
        if (!(value instanceof List<?> list)) throw new BizException(400, label + "格式无效");
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> map)) throw new BizException(400, label + "条目格式无效");
            String actionType = text(map.get("actionType")).toLowerCase();
            String actionValue = text(map.get("actionValue"));
            if (!ABOUT_ACTION_TYPES.contains(actionType)) {
                throw new BizException(400, label + "包含不支持的操作类型");
            }
            switch (actionType) {
                case "external" -> {
                    if (actionValue.isBlank()) throw new BizException(400, label + "的外部地址不能为空");
                    validateOptionalHttps(actionValue, label + "外部地址");
                }
                case "mailto" -> {
                    String email = actionValue.toLowerCase().startsWith("mailto:")
                            ? actionValue.substring(7) : actionValue;
                    if (!isSafeEmail(email)) throw new BizException(400, label + "邮箱格式无效");
                }
                case "legal" -> {
                    if (!Set.of("terms", "privacy").contains(actionValue)) {
                        throw new BizException(400, label + "法律文档操作无效");
                    }
                }
                case "navigate" -> safeCarouselLink(actionValue, true);
                default -> {
                    // Text-only actions are handled by the client and never interpreted as URLs.
                }
            }
            String imageUrl = text(map.get("imageUrl"));
            if (!imageUrl.isBlank()) safeCarouselImage(imageUrl, true);
        }
    }

    private void validateOptionalHttps(String value, String label) {
        if (value.isBlank()) return;
        try {
            URI uri = URI.create(value);
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                    || uri.getHost().isBlank() || uri.getRawUserInfo() != null
                    || uri.getRawFragment() != null || (uri.getPort() != -1 && uri.getPort() != 443)
                    || isReservedConfigurationHost(uri.getHost())) {
                throw new IllegalArgumentException("unsafe URL");
            }
        } catch (RuntimeException ex) {
            throw new BizException(400, label + "仅支持 HTTPS 地址");
        }
    }

    private boolean isSafeEmail(String value) {
        String email = text(value);
        if (email.length() > 254
                || !email.matches("^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)+$")) {
            return false;
        }
        return !isReservedConfigurationHost(email.substring(email.lastIndexOf('@') + 1));
    }

    private boolean isReservedConfigurationHost(String value) {
        String host = text(value).toLowerCase();
        if (host.startsWith("[") && host.endsWith("]")) {
            host = host.substring(1, host.length() - 1);
        }
        return host.equals("localhost") || host.endsWith(".localhost")
                || host.endsWith(".local") || host.endsWith(".invalid")
                || host.endsWith(".test") || host.equals("example.com")
                || host.endsWith(".example.com") || host.equals("example.org")
                || host.endsWith(".example.org") || host.equals("example.net")
                || host.endsWith(".example.net")
                || host.matches("^(?:0|10|127)(?:\\.[0-9]{1,3}){3}$")
                || host.matches("^(?:192\\.168|169\\.254|198\\.(?:18|19))(?:\\.[0-9]{1,3}){2}$")
                || host.matches("^172\\.(?:1[6-9]|2[0-9]|3[01])(?:\\.[0-9]{1,3}){2}$")
                || host.matches("^100\\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])(?:\\.[0-9]{1,3}){2}$")
                || host.matches("^(?:22[4-9]|2[3-5][0-9])(?:\\.[0-9]{1,3}){3}$")
                || host.equals("::1") || (host.indexOf(':') >= 0
                && (host.startsWith("fc") || host.startsWith("fd") || host.startsWith("fe80:")));
    }

    private void validatePlainStructuredValue(Object value, int depth) {
        if (depth > 8) throw new BizException(400, "关于页配置嵌套层级过深");
        if (value instanceof Map<?, ?> map) {
            if (map.size() > 200) throw new BizException(400, "关于页配置字段过多");
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = text(entry.getKey());
                if (key.isBlank() || key.length() > 80) throw new BizException(400, "关于页配置字段名无效");
                validatePlainStructuredValue(entry.getValue(), depth + 1);
            }
        } else if (value instanceof List<?> list) {
            if (list.size() > 200) throw new BizException(400, "关于页配置列表过长");
            for (Object item : list) validatePlainStructuredValue(item, depth + 1);
        } else if (value instanceof String string) {
            if (string.length() > 10_000 || containsUnsafePlainTextCharacter(string)) {
                throw new BizException(400, "关于页配置仅支持安全的纯文本内容");
            }
        } else if (value != null && !(value instanceof Number) && !(value instanceof Boolean)) {
            throw new BizException(400, "关于页配置包含不支持的数据类型");
        }
    }

    private void ensureListSize(Object value, int limit, String label) {
        if (!(value instanceof List<?> list)) throw new BizException(400, label + "格式无效");
        if (list.size() > limit) throw new BizException(400, label + "数量超过上限");
    }

    private void ensureTextLength(String value, int limit, String label) {
        if (value != null && value.length() > limit) {
            throw new BizException(400, label + "不能超过 " + limit + " 个字符");
        }
        if (value != null && containsUnsafePlainTextCharacter(value)) {
            throw new BizException(400, label + "包含不安全的控制或标记字符");
        }
    }

    private boolean containsUnsafePlainTextCharacter(String value) {
        for (int offset = 0; offset < value.length();) {
            int character = value.codePointAt(offset);
            offset += Character.charCount(character);
            if (isUnsafePlainTextCodePoint(character)) return true;
        }
        return false;
    }

    private boolean isUnsafePlainTextCodePoint(int character) {
        return character == '<' || character == '>'
                || isUnsafeFormatControl(character)
                || (Character.isISOControl(character)
                && character != '\n' && character != '\r' && character != '\t');
    }

    private static boolean isUnsafeFormatControl(int character) {
        return character == 0x061c || character == 0x180e || character == 0x200b
                || character == 0x200e || character == 0x200f
                || (character >= 0x202a && character <= 0x202e)
                || character == 0x2060 || (character >= 0x2066 && character <= 0x2069)
                || character == 0xfeff;
    }

    private void validateSortOrder(Object value) {
        if (value == null || text(value).isBlank()) return;
        try {
            int number = Integer.parseInt(text(value));
            if (number < 0 || number > 999) throw new NumberFormatException("out of range");
        } catch (NumberFormatException ex) {
            throw new BizException(400, "轮播排序值必须是 0 到 999 的整数");
        }
    }

    private Map<String, Object> normalizeCarousel(Map<String, Object> input, long id, String createdAt, boolean strictLinks) {
        List<Map<String, Object>> covers = new ArrayList<>();
        Object rawCoverItems = input.get("coverItems");
        if (rawCoverItems instanceof List<?> list) {
            for (int index = 0; index < Math.min(list.size(), MAX_COVERS_PER_CAROUSEL); index += 1) {
                Object cover = list.get(index);
                if (cover instanceof Map<?, ?> map) {
                    Map<String, Object> normalized = normalizeCoverItem(castMap(map), index, strictLinks);
                    if (!text(normalized.get("imageUrl")).isBlank()) {
                        covers.add(normalized);
                    }
                }
            }
        }
        if (covers.isEmpty()) {
            Map<String, Object> primaryCover = new LinkedHashMap<>();
            primaryCover.put("imageUrl", text(input.get("imageUrl")));
            primaryCover.put("linkUrl", text(input.get("linkUrl")));
            primaryCover.put("title", text(input.get("title")));
            primaryCover.put("description", text(input.get("description")));
            primaryCover.put("sourceType", textOr(input.get("sourceType"), "upload"));
            primaryCover.put("sortOrder", 0);
            primaryCover.put("enabled", booleanValue(input.get("enabled"), true));
            Map<String, Object> normalized = normalizeCoverItem(primaryCover, 0, strictLinks);
            if (!text(normalized.get("imageUrl")).isBlank()) {
                covers.add(normalized);
            }
        }
        Map<String, Object> first = covers.isEmpty() ? new LinkedHashMap<>() : covers.get(0);
        String now = LocalDateTime.now().toString();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", id);
        result.put("title", trimToLength(textOr(input.get("title"), text(first.get("title"))), 100));
        result.put("description", trimToLength(textOr(input.get("description"), text(first.get("description"))), 500));
        result.put("imageUrl", text(first.get("imageUrl")));
        result.put("linkUrl", text(first.get("linkUrl")));
        result.put("sourceType", textOr(first.get("sourceType"), "upload"));
        result.put("coverItems", covers);
        result.put("sortOrder", Math.max(0, Math.min(number(input.get("sortOrder"), 0), 999)));
        result.put("enabled", booleanValue(input.get("enabled"), true));
        result.put("createdAt", createdAt == null || createdAt.isBlank() ? now : createdAt);
        String persistedUpdatedAt = text(input.get("updatedAt"));
        result.put("updatedAt", strictLinks || persistedUpdatedAt.isBlank() ? now : persistedUpdatedAt);
        return result;
    }

    private Map<String, Object> normalizeCoverItem(Map<String, Object> input, int index, boolean strictLinks) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", trimToLength(textOr(input.get("id"), "cover-" + UUID.randomUUID().toString().replace("-", "").substring(0, 8)), 80));
        result.put("title", trimToLength(text(input.get("title")), 100));
        result.put("description", trimToLength(text(input.get("description")), 500));
        result.put("imageUrl", safeCarouselImage(textOr(firstPresent(input, "imageUrl", "url", "image"), ""), strictLinks));
        result.put("linkUrl", safeCarouselLink(textOr(firstPresent(input, "linkUrl", "targetUrl"), ""), strictLinks));
        String sourceType = textOr(firstPresent(input, "sourceType", "source"), "upload").toLowerCase();
        if (!sourceType.equals("upload") && !sourceType.equals("url")) {
            sourceType = "upload";
        }
        result.put("sourceType", sourceType);
        result.put("sortOrder", Math.max(0, Math.min(number(input.get("sortOrder"), index), 999)));
        result.put("enabled", booleanValue(input.get("enabled"), true));
        return result;
    }

    static String safeCarouselLink(String rawValue, boolean strict) {
        String link = rawValue == null ? "" : rawValue.trim();
        if (link.isBlank()) return "";
        try {
            if (link.length() > 2_048 || link.indexOf('\\') >= 0
                    || link.chars().anyMatch(character -> Character.isISOControl(character)
                    || isUnsafeFormatControl(character) || character == 127)) {
                throw new IllegalArgumentException("invalid carousel link");
            }
            if ((link.startsWith("/") && !link.startsWith("//")) || link.startsWith("#/")) {
                return link;
            }
            URI uri = URI.create(link);
            String scheme = uri.getScheme();
            if (scheme == null
                    || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))
                    || uri.getHost() == null
                    || uri.getHost().isBlank()) {
                throw new IllegalArgumentException("invalid carousel link");
            }
            return link;
        } catch (RuntimeException error) {
            if (strict) throw new IllegalArgumentException("轮播跳转链接仅支持站内路径或 HTTP/HTTPS 地址");
            return "";
        }
    }

    static String safeCarouselImage(String rawValue, boolean strict) {
        String image = rawValue == null ? "" : rawValue.trim();
        if (image.isBlank()) return "";
        try {
            if (image.length() > 2_048 || image.indexOf('\\') >= 0
                    || image.chars().anyMatch(character -> Character.isISOControl(character)
                    || isUnsafeFormatControl(character) || character == 127)) {
                throw new IllegalArgumentException("invalid carousel image");
            }
            if (image.matches(
                    "^/uploads/images/tenant-[1-9][0-9]*/[A-Za-z0-9_-]{1,180}\\.(?:jpg|jpeg|png|gif|webp)$")) {
                return image;
            }
            URI uri = URI.create(image);
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                    || uri.getHost().isBlank() || uri.getRawUserInfo() != null
                    || uri.getRawFragment() != null || (uri.getPort() != -1 && uri.getPort() != 443)) {
                throw new IllegalArgumentException("invalid carousel image");
            }
            return image;
        } catch (RuntimeException error) {
            if (strict) throw new IllegalArgumentException("轮播图片仅支持已上传的公开图片或 HTTPS 地址");
            return "";
        }
    }

    private Map<String, Object> normalizeAnnouncement(
            Map<String, Object> input,
            long id,
            String createdAt,
            boolean writing
    ) {
        String now = LocalDateTime.now().toString();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", id);
        result.put("title", trimToLength(textOr(firstPresent(input, "title", "name"), ""), 100));
        result.put("content", trimToLength(textOr(firstPresent(input, "content", "body", "desc"), ""), 2_000));
        result.put("enabled", booleanValue(input.get("enabled"), true));
        result.put("createdAt", createdAt == null || createdAt.isBlank() ? now : createdAt);
        String persistedUpdatedAt = text(input.get("updatedAt"));
        result.put("updatedAt", writing || persistedUpdatedAt.isBlank() ? now : persistedUpdatedAt);
        return result;
    }

    private Object firstPresent(Map<String, Object> input, String... keys) {
        for (String key : keys) {
            if (input.containsKey(key) && input.get(key) != null && !text(input.get(key)).isBlank()) {
                return input.get(key);
            }
        }
        return null;
    }

    private long nextId(List<Map<String, Object>> rows) {
        long max = 0L;
        for (Map<String, Object> row : rows) {
            max = Math.max(max, number(row.get("id"), 0L));
        }
        return max + 1L;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> castMap(Object value) {
        return (Map<String, Object>) value;
    }

    private Object itemValue(Map<?, ?> value, String key) {
        return value.get(key);
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private String textOr(Object value, String fallback) {
        String result = text(value);
        return result.isBlank() ? fallback : result;
    }

    private String trimToLength(String value, int limit) {
        String source = value == null ? "" : value.trim();
        StringBuilder result = new StringBuilder(Math.min(source.length(), limit));
        for (int offset = 0; offset < source.length();) {
            int codePoint = source.codePointAt(offset);
            offset += Character.charCount(codePoint);
            if (isUnsafePlainTextCodePoint(codePoint)) continue;
            int encodedLength = Character.charCount(codePoint);
            if (result.length() + encodedLength > limit) break;
            result.appendCodePoint(codePoint);
        }
        return result.toString();
    }

    private int number(Object value, int fallback) {
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception ex) {
            return fallback;
        }
    }

    private long number(Object value, long fallback) {
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception ex) {
            return fallback;
        }
    }

    private boolean booleanValue(Object value, boolean fallback) {
        if (value == null) {
            return fallback;
        }
        if (value instanceof Boolean bool) {
            return bool;
        }
        String text = String.valueOf(value).trim().toLowerCase();
        if (List.of("1", "true", "yes", "on").contains(text)) {
            return true;
        }
        if (List.of("0", "false", "no", "off").contains(text)) {
            return false;
        }
        return fallback;
    }
}
