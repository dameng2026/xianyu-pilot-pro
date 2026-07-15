package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;

/**
 * 闲鱼商品删除 API 客户端。
 * 通过闲鱼 H5 API 下发商品删除指令，使商品在闲鱼客户端无法被搜索、浏览和查看。
 */
@Component
public class XianyuItemDeleteClient {

    private static final Logger log = LoggerFactory.getLogger(XianyuItemDeleteClient.class);
    private static final ObjectMapper objectMapper = new ObjectMapper();

    private static final String APP_KEY = "34839810";
    private static final String H5_API_BASE = "https://h5api.m.goofish.com/h5";
    private static final String ITEM_DELETE_API = "mtop.idle.item.delete";

    private static final String UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    /**
     * 调用闲鱼商品删除 API。
     *
     * @param cookieStr 完整的 Cookie 字符串
     * @param itemId    闲鱼商品 ID（externalGoodsId）
     * @return true 表示删除成功，false 表示失败
     */
    public boolean deleteItem(String cookieStr, String itemId) {
        if (cookieStr == null || cookieStr.isBlank()) {
            log.warn("闲鱼商品删除 API 调用失败：Cookie 为空");
            return false;
        }
        if (itemId == null || itemId.isBlank()) {
            log.warn("闲鱼商品删除 API 调用失败：itemId 为空");
            return false;
        }

        try {
            String token = extractToken(cookieStr);
            if (token.isBlank()) {
                log.warn("闲鱼商品删除 API Cookie 中缺少 _m_h5_tk，无法签名");
                return false;
            }

            String dataJson = "{\"itemId\":\"" + itemId + "\"}";

            long timestamp = System.currentTimeMillis();
            String sign = md5(token + "&" + timestamp + "&" + APP_KEY + "&" + dataJson);

            String url = H5_API_BASE + "/" + ITEM_DELETE_API + "/1.0/"
                    + "?jsv=2.7.2&appKey=" + APP_KEY + "&t=" + timestamp
                    + "&sign=" + sign + "&v=1.0&api=" + ITEM_DELETE_API
                    + "&data=" + URLEncoder.encode(dataJson, StandardCharsets.UTF_8);

            String formBody = "data=" + URLEncoder.encode(dataJson, StandardCharsets.UTF_8);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .header("User-Agent", UA)
                    .header("Referer", "https://www.goofish.com/")
                    .header("Origin", "https://www.goofish.com")
                    .header("Cookie", cookieStr)
                    .timeout(Duration.ofSeconds(30))
                    .POST(HttpRequest.BodyPublishers.ofString(formBody))
                    .build();

            HttpResponse<String> response = httpClient.send(request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

            if (response.statusCode() >= 400) {
                log.warn("闲鱼商品删除 API 返回 HTTP {}", response.statusCode());
                return false;
            }

            JsonNode root = objectMapper.readTree(response.body());

            // 检查 ret 数组中的返回信息
            JsonNode ret = root.get("ret");
            if (ret != null && ret.isArray()) {
                for (JsonNode r : ret) {
                    String msg = r.asText();
                    if (msg.startsWith("SUCCESS")) {
                        log.info("闲鱼商品删除成功: itemId={}", itemId);
                        return true;
                    }
                    if (msg.startsWith("FAIL") || msg.contains("FAIL")) {
                        log.warn("闲鱼商品删除 API 返回上游业务错误, itemId={}", itemId);
                        return false;
                    }
                }
            }

            log.warn("闲鱼商品删除 API 返回结果不明确: itemId={}, status={}",
                    itemId, response.statusCode());
            return false;

        } catch (Exception e) {
            log.error("调用闲鱼商品删除 API 失败: itemId={}, errorType={}", itemId, e.getClass().getSimpleName());
            return false;
        }
    }

    /**
     * 从 Cookie 中提取 _m_h5_tk 的 token 部分（前半部分，按 _ 拆分）。
     */
    private String extractToken(String cookieStr) {
        if (cookieStr == null || cookieStr.isBlank()) return "";
        for (String part : cookieStr.split(";")) {
            String trimmed = part.trim();
            if (trimmed.startsWith("_m_h5_tk=")) {
                String value = trimmed.substring("_m_h5_tk=".length());
                int underscoreIdx = value.indexOf("_");
                return underscoreIdx > 0 ? value.substring(0, underscoreIdx) : value;
            }
        }
        return "";
    }

    /**
     * MD5 哈希（小写十六进制）。
     */
    private String md5(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException("MD5 计算失败", e);
        }
    }

    private String abbreviate(String text) {
        if (text == null) return "";
        return text.length() > 300 ? text.substring(0, 300) + "..." : text;
    }
}
