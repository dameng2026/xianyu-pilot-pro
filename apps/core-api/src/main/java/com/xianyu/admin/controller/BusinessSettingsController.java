package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AiProviderService;
import com.xianyu.admin.service.BusinessSettingsService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/**
 * 业务设置控制器。
 * 提供给 user-web 前端读写的业务配置接口（按当前登录用户隔离）。
 *
 * 路径：/api/business-settings/{category}
 *   GET  读取配置（合并默认值）
 *   POST 保存配置
 *
 * 额外：
 *   POST /api/business-settings/ai-customer-service/test  测试 AI 客服回复
 */
@RestController
@RequestMapping("/api/business-settings")
public class BusinessSettingsController {
    private static final Logger log = LoggerFactory.getLogger(BusinessSettingsController.class);

    private static final Set<String> ALLOWED_CATEGORIES = new HashSet<>(Arrays.asList(
            "ai-customer-service", "xiaomeng-assistant",
            "message-settings", "delivery-settings", "product-op-settings"
    ));

    private final BusinessSettingsService settingsService;
    private final AiProviderService aiProviderService;
    private final com.xianyu.admin.service.AutomationClient automationClient;

    public BusinessSettingsController(BusinessSettingsService settingsService,
                                     AiProviderService aiProviderService,
                                     com.xianyu.admin.service.AutomationClient automationClient) {
        this.settingsService = settingsService;
        this.aiProviderService = aiProviderService;
        this.automationClient = automationClient;
    }

    @GetMapping("/{category}")
    public Result<Map<String, Object>> getConfig(@PathVariable String category) {
        if (!ALLOWED_CATEGORIES.contains(category)) {
            throw new BizException(400, "不支持的配置分类");
        }
        return Result.ok(settingsService.getConfig(category));
    }

    @PostMapping("/{category}")
    public Result<Void> saveConfig(@PathVariable String category,
                                    @RequestBody Map<String, Object> config) {
        if (!ALLOWED_CATEGORIES.contains(category)) {
            throw new BizException(400, "不支持的配置分类");
        }
        settingsService.saveConfig(category, config);
        return Result.ok(null);
    }

    /**
     * 测试 AI 客服回复
     * 使用当前配置的 systemPrompt 对买家消息生成回复
     */
    @PostMapping("/ai-customer-service/test")
    public Result<Map<String, Object>> testAiReply(@RequestBody Map<String, Object> body) {
        try {
            if (body == null) throw new BizException(400, "测试消息不能为空");
            Map<String, Object> settings = settingsService.getConfig("ai-customer-service");
            String systemPrompt = String.valueOf(settings.getOrDefault("systemPrompt", ""));
            String userMessage = String.valueOf(body.getOrDefault("message", "你好，这个商品还能再优惠点吗？"));
            if (userMessage.isBlank() || userMessage.length() > 5_000) {
                throw new BizException(400, "测试消息不能为空且不能超过 5000 个字符");
            }

            // 如果未启用 AI Provider，使用欢迎语兜底
            Map<String, Object> status = aiProviderService.isConfigured()
                    ? Collections.singletonMap("configured", true)
                    : Collections.singletonMap("configured", false);
            if (!Boolean.TRUE.equals(status.get("configured"))) {
                throw new BizException(503, "AI 客服模型尚未配置，当前无法测试");
            }

            Map<String, Object> result = aiProviderService.generateText(
                    "ai_customer_service_test",
                    systemPrompt,
                    userMessage,
                    0.6,
                    true);
            Map<String, Object> response = new LinkedHashMap<>();
            response.put("ok", Boolean.TRUE.equals(result.get("ok")));
            response.put("reply", result.getOrDefault("content", ""));
            response.put("configured", true);
            response.put("usage", result.get("usage"));
            return Result.ok(response);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("AI 客服测试失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "AI 客服测试暂时不可用，请稍后重试");
        }
    }

    /**
     * 获取 AI 客服配置的默认值（用于前端"恢复默认"按钮）。
     */
    @GetMapping("/ai-customer-service/defaults")
    public Result<Map<String, Object>> getAiCsDefaults() {
        return Result.ok(settingsService.getDefaults("ai-customer-service"));
    }

    /**
     * 获取小梦运营助手配置的默认值。
     * 与 ai-customer-service/defaults 区分：小梦是前台用户主动对话的运营助手，
     * ai-customer-service 是买家消息触发的自动回复（售前客服）。
     */
    @GetMapping("/xiaomeng-assistant/defaults")
    public Result<Map<String, Object>> getXiaomengDefaults() {
        return Result.ok(settingsService.getDefaults("xiaomeng-assistant"));
    }

    /**
     * 测试小梦运营助手回复（与 ai-customer-service/test 区分）。
     * 使用小梦专用配置的 systemPrompt + 硬编码人设进行测试。
     */
    @PostMapping("/xiaomeng-assistant/test")
    public Result<Map<String, Object>> testXiaomengReply(@RequestBody Map<String, Object> body) {
        try {
            if (body == null) throw new BizException(400, "测试消息不能为空");
            Map<String, Object> settings = settingsService.getConfig("xiaomeng-assistant");
            // 小梦人设由 ai_cs_runtime.py 硬编码，此处测试仅取用户自定义提示词作为补充
            String userCustomPrompt = String.valueOf(settings.getOrDefault("systemPrompt", ""));
            String systemPrompt = "你是闲鱼运营助手的智能客服小梦，负责帮助卖家管理闲鱼店铺。";
            if (!userCustomPrompt.isBlank()) {
                systemPrompt = systemPrompt + "\n\n【用户自定义补充】\n" + userCustomPrompt;
            }
            String userMessage = String.valueOf(body.getOrDefault("message", "你好，小梦，能帮我查一下账号状态吗？"));
            if (userMessage.isBlank() || userMessage.length() > 5_000) {
                throw new BizException(400, "测试消息不能为空且不能超过 5000 个字符");
            }

            Map<String, Object> status = aiProviderService.isConfigured()
                    ? Collections.singletonMap("configured", true)
                    : Collections.singletonMap("configured", false);
            if (!Boolean.TRUE.equals(status.get("configured"))) {
                throw new BizException(503, "AI 客服模型尚未配置，当前无法测试");
            }

            Map<String, Object> result = aiProviderService.generateText(
                    "xiaomeng_assistant_test",
                    systemPrompt,
                    userMessage,
                    0.6,
                    true);
            Map<String, Object> response = new LinkedHashMap<>();
            response.put("ok", Boolean.TRUE.equals(result.get("ok")));
            response.put("reply", result.getOrDefault("content", ""));
            response.put("configured", true);
            response.put("usage", result.get("usage"));
            return Result.ok(response);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("小梦客服测试失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "小梦客服测试暂时不可用，请稍后重试");
        }
    }

    /**
     * 上传知识库文件，透传到 Python automation-service 进行 AI 规则提取。
     */
    @PostMapping("/ai-customer-service/upload-knowledge")
    public Result<Object> uploadKnowledge(
            @RequestParam("file") org.springframework.web.multipart.MultipartFile file) {
        try {
            if (file == null || file.isEmpty()) {
                throw new BizException(400, "请选择要上传的文件");
            }
            String fileName = file.getOriginalFilename();
            if (fileName == null || fileName.isBlank()) {
                throw new BizException(400, "文件名为空");
            }
            String ext = fileName.contains(".") ? fileName.substring(fileName.lastIndexOf('.')).toLowerCase() : "";
            // The downstream parsers support OOXML, not the legacy OLE-based
            // .xls/.ppt formats. Reject those formats here instead of accepting
            // an upload that automation-service cannot truthfully process.
            java.util.Set<String> allowed = java.util.Set.of(".md", ".txt", ".pptx", ".xlsx", ".csv");
            if (!allowed.contains(ext)) {
                throw new BizException(400, "不支持的文件格式，仅支持 " + String.join("/", allowed));
            }
            if (file.getSize() > 10L * 1024 * 1024) {
                throw new BizException(400, "文件不能超过 10MB");
            }

            // 透传到 Python /api/knowledge-base/extract
            // 同时透传 userId/tenantId 用于 AI 调用扣费（Python 端读取后调用 charge_text_usage）
            Map<String, Object> extraForm = new HashMap<>();
            Long userId = com.xianyu.admin.security.TenantContext.getCurrentUserId();
            Long tenantId = com.xianyu.admin.security.TenantContext.getCurrentTenantId();
            if (userId == null || tenantId == null) throw new BizException(401, "登录状态已失效");
            extraForm.put("userId", String.valueOf(userId));
            extraForm.put("tenantId", String.valueOf(tenantId));
            Map<String, Object> result = automationClient.uploadInternalForData(
                    "/api/knowledge-base/extract",
                    file.getInputStream(),
                    fileName,
                    extraForm
            );
            return Result.ok(result);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("知识库文件上传失败, errorType={}", e.getClass().getSimpleName());
            throw new BizException(503, "知识库文件暂时无法处理，请稍后重试");
        }
    }
}
