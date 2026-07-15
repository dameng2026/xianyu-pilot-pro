package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.CookieManager;
import java.net.HttpCookie;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 闲鱼 API 工具类 —— 签名计算、调用闲鱼个人主页接口。
 */
public final class XianyuApiUtils {

    private static final Logger log = LoggerFactory.getLogger(XianyuApiUtils.class);
    private static final ObjectMapper objectMapper = new ObjectMapper();
    private static final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    private static final String APP_KEY = "34839810";
    private static final String H5_API_BASE = "https://h5api.m.goofish.com/h5";
    private static final String PAGE_HEAD_API = "mtop.idle.web.user.page.head";
    private static final String PAGE_NAV_API = "mtop.idle.web.user.page.nav";
    private static final String WS_TOKEN_API = "mtop.taobao.idlemessage.pc.login.token";
    private static final String REFRESH_API = "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get";

    private static final String UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

    private XianyuApiUtils() {}

    /**
     * 调用 user.page.head API，获取主页头部资料。
     *
     * @param cookieStr 完整的 Cookie 字符串
     * @param unb       用户 UNB（闲鱼用户 ID）
     * @return 解析后的 JSON 数据（data.module 节点）
     */
    public static Map<String, Object> callPageHead(String cookieStr, String unb) {
        String dataJson = toJson(buildPageHeadDataJson(unb));
        return callXianyuApi(cookieStr, PAGE_HEAD_API, dataJson);
    }

    /**
     * 调用 user.page.nav API，获取导航栏补充资料。
     *
     * @param cookieStr 完整的 Cookie 字符串
     * @param unb       用户 UNB
     * @return 解析后的 JSON 数据（data.module 节点）
     */
    public static Map<String, Object> callPageNav(String cookieStr, String unb) {
        String dataJson = "{}";
        return callXianyuApi(cookieStr, PAGE_NAV_API, dataJson);
    }

    /**
     * 探测当前 Cookie 是否能成功获取 WebSocket Token。
     * <p>
     * 仅在返回了明确的认证/风控失败信号时返回 failed；如果只是网络抖动或闲鱼接口结构异常，
     * 调用方可以选择回退到更宽松的探测结果，避免把暂时性故障误判为登录失效。
     * </p>
     */
    public static AccountAuthProbeResult probeWebSocketToken(String cookieStr) {
        try {
            String refreshedCookie = refreshMH5Tk(cookieStr);
            if (refreshedCookie == null || refreshedCookie.isBlank()) {
                refreshedCookie = cookieStr;
            }

            String token = extractToken(refreshedCookie);
            if (token.isBlank()) {
                return AccountAuthProbeResult.failed("COOKIE_TOKEN_MISSING", "Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号");
            }

            Map<String, Object> data = new LinkedHashMap<>();
            data.put("appKey", "444e9908a51d1cb236a27862abc769c9");
            data.put("deviceId", token);
            data.put("appName", "xianyu");
            data.put("ttid", "pc_xianyu");
            String dataJson = toJson(data);

            long timestamp = System.currentTimeMillis();
            String sign = md5(token + "&" + timestamp + "&" + APP_KEY + "&" + dataJson);

            String url = H5_API_BASE + "/" + WS_TOKEN_API + "/1.0/"
                    + "?jsv=2.7.2&appKey=" + APP_KEY + "&t=" + timestamp
                    + "&sign=" + sign + "&v=1.0&type=originaljson&accountSite=xianyu"
                    + "&dataType=json&timeout=20000&api=" + WS_TOKEN_API
                    + "&sessionOption=AutoLoginOnly";

            String formBody = "data=" + URLEncoder.encode(dataJson, StandardCharsets.UTF_8);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .header("User-Agent", UA)
                    .header("Referer", "https://www.goofish.com/")
                    .header("Origin", "https://www.goofish.com")
                    .header("Cookie", refreshedCookie)
                    .timeout(Duration.ofSeconds(30))
                    .POST(HttpRequest.BodyPublishers.ofString(formBody))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            JsonNode root = objectMapper.readTree(response.body());
            String retText = joinRet(root.get("ret"));

            if (retText.contains("FAIL_SYS_USER_VALIDATE") || retText.contains("RGV587")) {
                // Baxia 滑块验证：Cookie 触发了反爬/风控，WS 连接也会失败。
                // 必须返回 failed，让 Cookie 预检准确反映"当前 Cookie 无法通过闲鱼消息页面验证"，
                // 否则前端会误显示"Cookie 状态正常"，用户点击连接后又提示失败，体验混乱。
                // 用户需要重新扫码登录或手动更新 Cookie 以获取新的 _m_h5_tk。
                log.warn("WS Token 探测命中 Baxia 滑块验证，Cookie 已触发风控，判定为需要重新登录");
                return AccountAuthProbeResult.failed("COOKIE_EXPIRED", "Cookie 已触发滑块验证，请重新扫码登录或更新 Cookie");
            }
            if (retText.contains("FAIL_SYS_SESSION_EXPIRED")
                    || retText.contains("FAIL_SYS_TOKEN_EXOIRED")
                    || retText.contains("FAIL_SYS_TOKEN_EXPIRED")) {
                log.warn("WS Token 探测命中会话过期");
                return AccountAuthProbeResult.failed("COOKIE_EXPIRED", "Cookie 已过期，请重新登录闲鱼账号");
            }
            if (retText.contains("SUCCESS")) {
                String accessToken = root.path("data").path("accessToken").asText("");
                if (!accessToken.isBlank()) {
                    return AccountAuthProbeResult.ok();
                }
            }

            if (response.statusCode() >= 400) {
                log.warn("WS Token 探测返回 HTTP {}", response.statusCode());
                return null;
            }

            log.warn("WS Token 探测未得到明确结论, status={}, retCount={}",
                    response.statusCode(), root.path("ret").size());
            return null;
        } catch (Exception e) {
            log.warn("WS Token 探测异常, errorType={}", e.getClass().getSimpleName());
            return null;
        }
    }

    /**
     * 通用闲鱼 API 调用。
     * 调用前先刷新 _m_h5_tk 令牌，避免令牌过期导致签名校验失败。
     */
    private static Map<String, Object> callXianyuApi(String cookieStr, String api, String dataJson) {
        try {
            // Step 1: 刷新 _m_h5_tk 令牌
            String refreshedCookie = refreshMH5Tk(cookieStr);
            if (refreshedCookie == null) {
                refreshedCookie = cookieStr;
            }

            String token = extractToken(refreshedCookie);
            if (token.isBlank()) {
                log.warn("闲鱼 API {} Cookie 中缺少 _m_h5_tk，无法签名", api);
                return null;
            }

            long timestamp = System.currentTimeMillis();
            String sign = md5(token + "&" + timestamp + "&" + APP_KEY + "&" + dataJson);

            String url = H5_API_BASE + "/" + api + "/1.0/"
                    + "?jsv=2.7.2&appKey=" + APP_KEY + "&t=" + timestamp
                    + "&sign=" + sign + "&v=1.0&type=originaljson&accountSite=xianyu"
                    + "&dataType=json&timeout=20000&api=" + api
                    + "&sessionOption=AutoLoginOnly";

            if (PAGE_HEAD_API.equals(api)) {
                url += "&spm_cnt=a21ybx.personal";
            } else if (PAGE_NAV_API.equals(api)) {
                url += "&spm_cnt=a21ybx.personal.0";
            }

            String formBody = "data=" + URLEncoder.encode(dataJson, StandardCharsets.UTF_8);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .header("User-Agent", UA)
                    .header("Referer", "https://www.goofish.com/")
                    .header("Origin", "https://www.goofish.com")
                    .header("Cookie", refreshedCookie)
                    .timeout(Duration.ofSeconds(30))
                    .POST(HttpRequest.BodyPublishers.ofString(formBody))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

            if (response.statusCode() >= 400) {
                log.warn("闲鱼 API {} 返回 HTTP {}", api, response.statusCode());
                return null;
            }

            JsonNode root = objectMapper.readTree(response.body());
            JsonNode data = root.get("data");
            if (data == null) {
                log.warn("闲鱼 API {} 返回无 data 字段, status={}", api, response.statusCode());
                return null;
            }

            JsonNode ret = root.get("ret");
            if (ret != null && ret.isArray()) {
                for (JsonNode r : ret) {
                    String msg = r.asText();
                    if (msg.startsWith("FAIL") || msg.contains("FAIL") || msg.contains("错误")) {
                        log.warn("闲鱼 API {} 返回上游业务错误, status={}", api, response.statusCode());
                    }
                }
            }

            JsonNode module = data.get("module");
            if (module == null) {
                log.warn("闲鱼 API {} 返回无 module 字段, status={}, retCount={}",
                        api, response.statusCode(), ret == null ? 0 : ret.size());
                return null;
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> result = objectMapper.convertValue(module, LinkedHashMap.class);
            return result;
        } catch (Exception e) {
            log.error("调用闲鱼 API {} 失败, errorType={}", api, e.getClass().getSimpleName());
            return null;
        }
    }

    private static Map<String, Object> buildPageHeadDataJson(String unb) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("self", false);
        data.put("userId", unb != null ? unb : "");
        return data;
    }

    private static String toJson(Map<String, Object> data) {
        try {
            return objectMapper.writeValueAsString(data);
        } catch (Exception e) {
            throw new IllegalStateException("闲鱼 API 请求参数序列化失败", e);
        }
    }

    /**
     * 刷新 _m_h5_tk 令牌。
     * <p>
     * _m_h5_tk 具有时效性，扫码登录保存后可能已过期。
     * 此方法使用 CookieManager 管理会话，执行 3 步刷新流程：
     * <ol>
     *   <li>GET 请求获取初始 Cookie（cookie2）</li>
     *   <li>空 token POST 触发服务端下发新 _m_h5_tk</li>
     *   <li>真实 token POST 激活令牌</li>
     * </ol>
     * </p>
     *
     * @param cookieStr 原始 Cookie 字符串
     * @return 包含新 _m_h5_tk 的 Cookie 字符串；若刷新失败返回原 cookieStr
     */
    static String refreshMH5Tk(String cookieStr) {
        if (cookieStr == null || cookieStr.isBlank()) {
            return cookieStr;
        }

        CookieManager cookieManager = new CookieManager();
        HttpClient client = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .cookieHandler(cookieManager)
                .connectTimeout(Duration.ofSeconds(10))
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();

        // 将存储的 cookie 还原到会话
        try {
            URI domain = URI.create("https://goofish.com");
            for (String part : cookieStr.split(";")) {
                String trimmed = part.trim();
                int eqIdx = trimmed.indexOf("=");
                if (eqIdx > 0) {
                    String name = trimmed.substring(0, eqIdx).trim();
                    String value = trimmed.substring(eqIdx + 1).trim();
                    cookieManager.getCookieStore().add(domain, new HttpCookie(name, value));
                }
            }
        } catch (Exception e) {
            log.warn("还原 Cookie 到会话失败, errorType={}", e.getClass().getSimpleName());
            return cookieStr;
        }

        String dataStr = "{\"bizScene\":\"home\"}";
        String postUrl = H5_API_BASE + "/" + REFRESH_API + "/1.0/";

        try {
            // Step 1: GET 获取初始 Cookie
            HttpRequest getReq = HttpRequest.newBuilder()
                    .uri(URI.create(postUrl))
                    .header("User-Agent", UA)
                    .GET()
                    .timeout(Duration.ofSeconds(15))
                    .build();
            client.send(getReq, HttpResponse.BodyHandlers.ofString());

            // Step 2: 空 token POST — 触发 _m_h5_tk 下发
            long t1 = System.currentTimeMillis();
            String emptySign = md5("&" + t1 + "&" + APP_KEY + "&" + dataStr);
            String postBody1 = "jsv=2.7.2&appKey=" + APP_KEY + "&t=" + t1 + "&sign=" + emptySign
                    + "&v=1.0&type=originaljson&dataType=json&timeout=20000"
                    + "&api=" + REFRESH_API + "&data=" + URLEncoder.encode(dataStr, StandardCharsets.UTF_8);

            HttpRequest postReq1 = HttpRequest.newBuilder()
                    .uri(URI.create(postUrl))
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .header("User-Agent", UA)
                    .POST(HttpRequest.BodyPublishers.ofString(postBody1))
                    .timeout(Duration.ofSeconds(15))
                    .build();
            client.send(postReq1, HttpResponse.BodyHandlers.ofString());

            // 提取新 _m_h5_tk
            String mh5tk = null;
            for (HttpCookie c : cookieManager.getCookieStore().getCookies()) {
                if ("_m_h5_tk".equals(c.getName())) {
                    mh5tk = c.getValue();
                    break;
                }
            }
            if (mh5tk == null || mh5tk.isBlank()) {
                log.warn("刷新 _m_h5_tk 失败：服务器未下发新令牌，继续使用原 cookie");
                return cookieStr;
            }

            String token = mh5tk.contains("_") ? mh5tk.substring(0, mh5tk.indexOf("_")) : mh5tk;

            // Step 3: 真实 token POST — 激活令牌
            long t2 = System.currentTimeMillis();
            String realSign = md5(token + "&" + t2 + "&" + APP_KEY + "&" + dataStr);
            String postBody2 = "jsv=2.7.2&appKey=" + APP_KEY + "&t=" + t2 + "&sign=" + realSign
                    + "&v=1.0&type=originaljson&dataType=json&timeout=20000"
                    + "&api=" + REFRESH_API + "&data=" + URLEncoder.encode(dataStr, StandardCharsets.UTF_8);

            HttpRequest postReq2 = HttpRequest.newBuilder()
                    .uri(URI.create(postUrl))
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .header("User-Agent", UA)
                    .POST(HttpRequest.BodyPublishers.ofString(postBody2))
                    .timeout(Duration.ofSeconds(15))
                    .build();
            client.send(postReq2, HttpResponse.BodyHandlers.ofString());

            // 合并所有 cookie 到新的 cookie 字符串
            Map<String, String> updatedCookies = parseCookieStrToMap(cookieStr);
            for (HttpCookie c : cookieManager.getCookieStore().getCookies()) {
                updatedCookies.put(c.getName(), c.getValue());
            }

            StringBuilder sb = new StringBuilder();
            for (Map.Entry<String, String> entry : updatedCookies.entrySet()) {
                if (sb.length() > 0) sb.append("; ");
                sb.append(entry.getKey()).append("=").append(entry.getValue());
            }
            String newCookieStr = sb.toString();

            log.info("_m_h5_tk 已刷新, cookieLength={}", newCookieStr.length());
            return newCookieStr;

        } catch (Exception e) {
            log.warn("刷新 _m_h5_tk 异常, errorType={}，继续使用原 cookie", e.getClass().getSimpleName());
            return cookieStr;
        }
    }

    /**
     * 将 Cookie 字符串解析为 Map。
     */
    private static Map<String, String> parseCookieStrToMap(String cookieStr) {
        Map<String, String> map = new LinkedHashMap<>();
        if (cookieStr == null || cookieStr.isBlank()) return map;
        for (String part : cookieStr.split(";")) {
            String trimmed = part.trim();
            int eqIdx = trimmed.indexOf("=");
            if (eqIdx > 0) {
                map.put(trimmed.substring(0, eqIdx).trim(), trimmed.substring(eqIdx + 1).trim());
            }
        }
        return map;
    }

    /**
     * 从 Cookie 中提取 _m_h5_tk 的 token 部分（前半部分，按 _ 拆分）。
     */
    static String extractToken(String cookieStr) {
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
    static String md5(String input) {
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

    private static String abbreviate(String text) {
        if (text == null) return "";
        return text.length() > 300 ? text.substring(0, 300) + "..." : text;
    }

    private static String joinRet(JsonNode retNode) {
        if (retNode == null) {
            return "";
        }
        if (retNode.isArray()) {
            StringBuilder builder = new StringBuilder();
            for (JsonNode item : retNode) {
                if (builder.length() > 0) {
                    builder.append(' ');
                }
                builder.append(item.asText(""));
            }
            return builder.toString();
        }
        return retNode.asText("");
    }
}
