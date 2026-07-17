package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.SensitiveWordService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 敏感词策略查询接口。
 *
 * - /open-api/internal/sensitive-words  供 Python automation-service 通过 X-Internal-Token 调用，
 *   用于工作流商品提取后过滤包含敏感词的商品。
 *
 * 前台 AI 润色场景由后端 ModelConfigService.buildPolishRestriction() 直接注入到 systemPrompt，
 * 前台无需主动查询敏感词列表。
 */
@RestController
public class SensitiveWordController {
    private final SensitiveWordService sensitiveWordService;

    @Value("${xianyu.automation.internal-token:}")
    private String internalToken;

    public SensitiveWordController(SensitiveWordService sensitiveWordService) {
        this.sensitiveWordService = sensitiveWordService;
    }

    /**
     * 内部接口：返回指定场景下启用的敏感词列表。
     * scene 取值：polish / product / all；为空时默认 product。
     * 返回结构：{ scene, count, words: [...], records: [{id, word, scene, category, action}] }
     */
    @GetMapping("/open-api/internal/sensitive-words")
    public Result<Map<String, Object>> listInternal(@RequestParam(required = false) String scene,
                                                     HttpServletRequest request) {
        verifyInternal(request);
        String resolved = (scene == null || scene.isBlank()) ? SensitiveWordService.SCENE_PRODUCT : scene;
        List<Map<String, Object>> records = sensitiveWordService.listEnabledByScene(resolved);
        List<String> words = records.stream().map(r -> String.valueOf(r.get("word"))).toList();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("scene", resolved);
        result.put("count", words.size());
        result.put("words", words);
        result.put("records", records);
        return Result.ok(result);
    }

    private void verifyInternal(HttpServletRequest request) {
        if (internalToken == null || internalToken.isBlank()) {
            throw new BizException(503, "internal API token is not configured");
        }
        String token = request.getHeader("X-Internal-Token");
        if (token == null || !MessageDigest.isEqual(
                internalToken.getBytes(StandardCharsets.UTF_8),
                token.getBytes(StandardCharsets.UTF_8))) {
            throw new BizException(403, "invalid internal token");
        }
    }
}
