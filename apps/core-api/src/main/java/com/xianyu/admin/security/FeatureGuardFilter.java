package com.xianyu.admin.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.FeatureSwitchService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 前台用户业务接口的功能开关强制校验过滤器（后端兜底，防绕过前端拦截）。
 *
 * 语义：与 FeatureSwitchService 保持一致——限制模式（preview/blocked）只作用于
 * 等级开关未开启的用户；等级开关开启的用户不受影响。前端 request.js 已做写请求拦截，
 * 本过滤器用于防止普通会员绕过前端直接构造请求调用核心业务写接口。
 *
 * 仅对核心业务写操作（POST/PUT/DELETE/PATCH）按「路径模式 → 功能 key」映射校验，
 * 未映射的请求一律放行；校验失败时返回 403（可进入页面查看，但不可执行业务操作）。
 */
@Component
public class FeatureGuardFilter extends OncePerRequestFilter {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    /** 写请求方法集合：仅这些方法参与功能开关校验 */
    private static final java.util.Set<String> WRITE_METHODS =
            java.util.Set.of("POST", "PUT", "DELETE", "PATCH");

    /** 路径模式 → 功能 key 映射：第一列 HTTP 方法，中间列路径段（* 匹配任意单段），最后一列功能 key */
    private static final String[][] GUARD_RULES = new String[][] {
            // ==================== 工作流（SVIP 专属） ====================
            {"POST", "api", "workflow", "definitions", "workflow"},
            {"PUT", "api", "workflow", "definitions", "*", "workflow"},
            {"DELETE", "api", "workflow", "definitions", "*", "workflow"},
            {"POST", "api", "workflow", "definitions", "*", "publish", "workflow"},
            {"POST", "api", "workflow", "definitions", "*", "rollback", "workflow"},
            {"POST", "api", "workflow", "definitions", "*", "execute", "workflow"},
            {"POST", "api", "workflow", "executions", "*", "terminate", "workflow"},
            {"POST", "api", "workflow", "executions", "*", "retry-failed-node", "workflow"},
            {"POST", "api", "workflow", "executions", "*", "continue", "workflow"},
            {"POST", "api", "workflow", "ai", "screen", "workflow"},
            {"POST", "api", "workflow", "ai", "rewrite", "workflow"},
            {"POST", "api", "workflow", "ai", "generate-images", "workflow"},
            {"POST", "api", "workflow", "ai", "extract-keywords", "workflow"},
            // 工作流 - 商品草稿箱
            {"POST", "api", "workflow", "drafts", "*", "retry-publish", "workflow-drafts"},
            {"POST", "api", "workflow", "drafts", "batch-retry-publish", "workflow-drafts"},
            {"DELETE", "api", "workflow", "drafts", "*", "workflow-drafts"},

            // ==================== 商机发掘（VIP 及以上） ====================
            {"POST", "api", "crawler", "import", "goofish", "opportunities"},
            {"POST", "api", "opportunity", "analyze", "opportunities"},
            {"POST", "api", "opportunity", "rewrite", "opportunities"},
            {"POST", "api", "opportunity", "generate-images", "opportunities"},
            {"POST", "api", "opportunity", "image-recover", "*", "opportunities"},

            // ==================== 账号 ====================
            {"POST", "api", "account", "updateCookie", "accounts"},
            {"POST", "api", "account", "refresh", "force", "accounts"},
            {"POST", "api", "xianyu", "accounts", "*", "auto-category", "accounts"},
            {"POST", "api", "xianyu", "accounts", "*", "auto-category", "upload", "accounts"},
            {"POST", "api", "xianyu", "categories", "sync", "accounts"},

            // ==================== 商品管理 ====================
            {"POST", "api", "item", "refresh", "products"},
            {"POST", "api", "item", "delete", "products"},
            {"POST", "api", "item", "offShelf", "products"},
            {"POST", "api", "item", "remoteDelete", "products"},
            {"POST", "api", "item", "batch", "delete", "products"},
            {"POST", "api", "item", "batch", "remoteDelete", "products"},
            {"POST", "api", "item", "batch", "offShelf", "products"},
            {"POST", "api", "item", "updateStock", "products"},
            {"POST", "api", "item", "updateAutoDeliveryStatus", "products"},
            {"POST", "api", "item", "updateAutoConfirmShipment", "products"},
            {"POST", "api", "item", "auto-relist", "toggle", "products"},
            {"POST", "api", "item", "polish", "products"},
            // 商品改价（独立功能 key）
            {"POST", "api", "item", "updatePrice", "product-price-edit"},
            // 鱼小铺编辑（独立功能 key）
            {"POST", "api", "fish-shop", "edit", "fish-shop-edit"},

            // ==================== 商品发布 ====================
            {"POST", "api", "item", "publish", "product-publish"},
            {"POST", "api", "item", "republish", "product-publish"},
            {"POST", "api", "fish-shop", "publish", "product-publish"},

            // ==================== 自动发货 ====================
            {"POST", "api", "autoDelivery", "config", "save", "auto-delivery"},
            {"POST", "api", "autoDelivery", "config", "delete", "auto-delivery"},
            {"POST", "api", "autoDelivery", "config", "test", "auto-delivery"},
            {"POST", "api", "autoDelivery", "trigger", "auto-delivery"},

            // ==================== 自动回复 ====================
            {"POST", "api", "item", "updateAutoReplyStatus", "auto-reply"},
            {"POST", "api", "item", "updateRagAutoReplyConfig", "auto-reply"},

            // ==================== 滑块求解（VIP 及以上） ====================
            {"POST", "api", "captcha", "auto-solve", "auto-slider-solve"},
            // 手动滑块求解：由 AutomationProxyController.checkManualSliderSolveAllowed 方法级校验，此处不重复拦截

            // ==================== 卡密仓库 ====================
            {"POST", "api", "kami", "config", "save", "card-warehouse"},
            {"POST", "api", "kami", "config", "delete", "card-warehouse"},
            {"POST", "api", "kami", "stock", "import", "card-warehouse"},

            // ==================== 退款管理 ====================
            {"POST", "api", "refunds", "sync", "refunds"},
            {"POST", "api", "refunds", "*", "agree", "refunds"},
            {"POST", "api", "refunds", "detail", "refresh", "refunds"},
            {"POST", "api", "refunds", "detail", "retry", "refunds"},

            // ==================== 评价管理 ====================
            {"POST", "api", "rates", "sync", "rates"},
            {"POST", "api", "rates", "create", "rates"},
            {"POST", "api", "rates", "auto-rate", "run", "rates"},

            // ==================== 学习知识库（RAG） ====================
            {"POST", "api", "knowledge-base", "rag", "add", "learning-kb"},
            {"POST", "api", "knowledge-base", "rag", "delete", "learning-kb"},
            {"POST", "api", "knowledge-base", "rag", "extract-and-add", "learning-kb"},
            {"POST", "api", "knowledge-base", "rag", "chat", "learning-kb"}
    };

    private final FeatureSwitchService featureSwitchService;

    public FeatureGuardFilter(FeatureSwitchService featureSwitchService) {
        this.featureSwitchService = featureSwitchService;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String method = request.getMethod();
        if (!WRITE_METHODS.contains(method.toUpperCase(java.util.Locale.ROOT))) return true;
        String uri = applicationPath(request);
        if (!uri.startsWith("/api/")) return true;
        // 公开接口与内部接口不参与功能开关校验
        return uri.equals("/api/login/login") || uri.equals("/api/login/register")
                || uri.equals("/api/login/sendEmailCode") || uri.equals("/api/login/verifyResetCode")
                || uri.equals("/api/login/resetPassword")
                || uri.startsWith("/api/sync/")
                || uri.startsWith("/api/payment/")
                || uri.startsWith("/api/v1/slider/")
                || uri.equals("/api/ai-cs/complete") || uri.equals("/api/ai-cs/tool/result")
                || uri.equals("/api/client-errors");
    }

    @Override
    protected boolean shouldNotFilterAsyncDispatch() {
        return true;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        Long userId = TenantContext.getCurrentUserId();
        if (userId == null) {
            filterChain.doFilter(request, response);
            return;
        }
        String featureKey;
        try {
            featureKey = resolveFeatureKey(request);
        } catch (Exception e) {
            filterChain.doFilter(request, response);
            return;
        }
        if (featureKey == null) {
            filterChain.doFilter(request, response);
            return;
        }
        Map<String, Object> status;
        try {
            status = featureSwitchService.getFeatureStatusForUser(userId, featureKey);
        } catch (Exception e) {
            filterChain.doFilter(request, response);
            return;
        }
        if (!Boolean.TRUE.equals(status.get("allowed"))) {
            String reason = String.valueOf(status.get("reason"));
            String reasonText = status.get("reason_text") == null
                    ? "该功能当前不可用" : String.valueOf(status.get("reason_text"));
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("feature_key", featureKey);
            data.put("reason", reason);
            data.put("required_level", status.get("required_level") == null
                    ? "" : String.valueOf(status.get("required_level")));
            data.put("preview", "preview".equals(reason));
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(OBJECT_MAPPER.writeValueAsString(
                    new Result<>(403, reasonText, data)));
            return;
        }
        filterChain.doFilter(request, response);
    }

    /** 按路径规则解析功能 key，未匹配返回 null */
    private String resolveFeatureKey(HttpServletRequest request) {
        String method = request.getMethod().toUpperCase(java.util.Locale.ROOT);
        String[] segments = applicationPath(request).split("/");
        for (String[] rule : GUARD_RULES) {
            if (!rule[0].equals(method)) continue;
            String featureKey = rule[rule.length - 1];
            if (matchSegments(rule, 1, rule.length - 1, segments)) {
                return featureKey;
            }
        }
        return null;
    }

    private boolean matchSegments(String[] rule, int ruleFrom, int ruleTo, String[] actual) {
        if (actual.length != ruleTo - ruleFrom) return false;
        for (int i = ruleFrom; i < ruleTo; i++) {
            String pattern = rule[i];
            if ("*".equals(pattern)) continue;
            if (!pattern.equals(actual[i - ruleFrom])) return false;
        }
        return true;
    }

    private String applicationPath(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String contextPath = request.getContextPath();
        if (contextPath != null && !contextPath.isEmpty() && uri.startsWith(contextPath)) {
            return uri.substring(contextPath.length());
        }
        return uri;
    }
}
