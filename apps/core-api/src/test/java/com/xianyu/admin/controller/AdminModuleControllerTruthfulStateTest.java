package com.xianyu.admin.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.config.GlobalExceptionHandler;
import com.xianyu.admin.service.AdminModuleService;
import com.xianyu.admin.service.AiProviderEndpointPolicy;
import com.xianyu.admin.service.DashboardService;
import com.xianyu.admin.service.ImageGenerationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AdminModuleControllerTruthfulStateTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private AdminModuleService moduleService;
    private DashboardService dashboardService;
    private ImageGenerationService imageGenerationService;
    private JdbcTemplate jdbcTemplate;
    private AiProviderEndpointPolicy endpointPolicy;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        moduleService = mock(AdminModuleService.class);
        dashboardService = mock(DashboardService.class);
        imageGenerationService = mock(ImageGenerationService.class);
        jdbcTemplate = mock(JdbcTemplate.class);
        endpointPolicy = mock(AiProviderEndpointPolicy.class);
        when(endpointPolicy.validateBaseUrl(anyString()))
                .thenAnswer(invocation -> invocation.getArgument(0));
        AdminModuleController controller = new AdminModuleController(
                moduleService, dashboardService, imageGenerationService, jdbcTemplate, endpointPolicy);
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void unsupportedConnectionTestReturnsHttp400() throws Exception {
        mockMvc.perform(post("/admin-api/admin/modules/backups/test-connection")
                        .contentType("application/json")
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400));
    }

    @Test
    void missingConnectionConfigurationReturnsHttp400() throws Exception {
        mockMvc.perform(post("/admin-api/admin/modules/model-config-chat/test-connection")
                        .contentType("application/json")
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400));
    }

    @Test
    void privateProviderEndpointIsRejectedBeforeBearerCredentialIsSent() throws Exception {
        AtomicInteger requests = new AtomicInteger();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/v1/chat/completions", exchange -> {
            requests.incrementAndGet();
            byte[] body = "{\"choices\":[{\"message\":{\"content\":\"ok\"}}]}"
                    .getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        try {
            when(endpointPolicy.validateBaseUrl(serverBaseUrl(server) + "/v1"))
                    .thenThrow(new BizException(400, "AI Provider 地址必须是公网 HTTPS 标准地址"));
            mockMvc.perform(post("/admin-api/admin/modules/model-config-chat/test-connection")
                            .contentType("application/json")
                            .content(objectMapper.writeValueAsString(Map.of(
                                    "baseUrl", serverBaseUrl(server) + "/v1",
                                    "apiKey", "must-not-leave-process",
                                    "model", "test-model"))))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code").value(400));
            assert requests.get() == 0;
        } finally {
            server.stop(0);
        }
    }

    @Test
    void oversizedProviderResponseIsRejected() throws Exception {
        String content = "x".repeat(1_100_000);
        HttpServer server = jsonServer(
                "/v1/chat/completions", 200,
                "{\"choices\":[{\"message\":{\"content\":\"" + content + "\"}}]}");
        try {
            mockMvc.perform(post("/admin-api/admin/modules/model-config-chat/test-connection")
                            .contentType("application/json")
                            .content(objectMapper.writeValueAsString(Map.of(
                                    "baseUrl", serverBaseUrl(server) + "/v1",
                                    "apiKey", "test-key",
                                    "model", "test-model"))))
                    .andExpect(status().isServiceUnavailable())
                    .andExpect(jsonPath("$.code").value(503));
        } finally {
            server.stop(0);
        }
    }

    @Test
    void upstreamConnectionFailureReturnsSanitizedHttp503() throws Exception {
        String upstreamSecret = "provider-secret-diagnostic";
        HttpServer server = jsonServer("/v1/chat/completions", 401,
                "{\"error\":\"" + upstreamSecret + "\"}");
        try {
            Map<String, Object> payload = Map.of(
                    "baseUrl", serverBaseUrl(server) + "/v1",
                    "apiKey", "test-key",
                    "model", "test-model"
            );
            mockMvc.perform(post("/admin-api/admin/modules/model-config-chat/test-connection")
                            .contentType("application/json")
                            .content(objectMapper.writeValueAsString(payload)))
                    .andExpect(status().isServiceUnavailable())
                    .andExpect(jsonPath("$.code").value(503))
                    .andExpect(content().string(not(containsString(upstreamSecret))))
                    .andExpect(content().string(not(containsString("test-key"))));
        } finally {
            server.stop(0);
        }
    }

    @Test
    void emptyUpstreamModelListReturnsHttp503InsteadOfOkEmptyList() throws Exception {
        HttpServer server = jsonServer("/v1/models", 200, "{\"data\":[]}");
        try {
            Map<String, Object> payload = Map.of(
                    "baseUrl", serverBaseUrl(server) + "/v1",
                    "apiKey", "test-key"
            );
            mockMvc.perform(post("/admin-api/admin/modules/model-config-chat/fetch-models")
                            .contentType("application/json")
                            .content(objectMapper.writeValueAsString(payload)))
                    .andExpect(status().isServiceUnavailable())
                    .andExpect(jsonPath("$.code").value(503));
        } finally {
            server.stop(0);
        }
    }

    @Test
    void upstreamModelListFailureReturnsSanitizedHttp503() throws Exception {
        String upstreamSecret = "model-list-private-provider-detail";
        HttpServer server = jsonServer("/v1/models", 500,
                "{\"error\":\"" + upstreamSecret + "\"}");
        try {
            Map<String, Object> payload = Map.of(
                    "baseUrl", serverBaseUrl(server) + "/v1",
                    "apiKey", "test-key"
            );
            mockMvc.perform(post("/admin-api/admin/modules/model-config-chat/fetch-models")
                            .contentType("application/json")
                            .content(objectMapper.writeValueAsString(payload)))
                    .andExpect(status().isServiceUnavailable())
                    .andExpect(jsonPath("$.code").value(503))
                    .andExpect(content().string(not(containsString(upstreamSecret))));
        } finally {
            server.stop(0);
        }
    }

    @Test
    void missingSavedMaskedConfigurationReturnsHttp400() throws Exception {
        when(moduleService.unmaskedRecord("model-config-chat", 42L))
                .thenThrow(new BizException(404, "record missing"));
        Map<String, Object> payload = Map.of(
                "id", 42,
                "baseUrl", "https://models.example.test/v1",
                "apiKey", "******",
                "model", "test-model"
        );

        mockMvc.perform(post("/admin-api/admin/modules/model-config-chat/test-connection")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(content().string(not(containsString("record missing"))));
    }

    @Test
    void imageConnectionFailureMapBecomesSanitizedHttp503() throws Exception {
        when(imageGenerationService.testConnection(org.mockito.ArgumentMatchers.anyMap()))
                .thenReturn(Map.of("ok", false, "message", "secret image provider response"));
        Map<String, Object> payload = Map.of(
                "baseUrl", "https://images.example.test/v1",
                "apiKey", "test-key",
                "model", "image-model"
        );

        mockMvc.perform(post("/admin-api/admin/modules/model-config-image/test-connection")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value(503))
                .andExpect(content().string(not(containsString("secret image provider response"))));
    }

    @Test
    void modulePageDependencyFailureReturnsSanitizedHttp503() throws Exception {
        String databaseSecret = "jdbc:mysql://user:password@private-db";
        when(moduleService.page(anyString(), anyInt(), anyInt(), isNull(), isNull()))
                .thenThrow(new RuntimeException(databaseSecret));

        mockMvc.perform(get("/admin-api/admin/modules/users/page"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value(503))
                .andExpect(content().string(not(containsString(databaseSecret))));
    }

    @Test
    void dashboardDatabaseFailureReturnsHttp503InsteadOfZeroCards() throws Exception {
        when(jdbcTemplate.queryForObject(anyString(), org.mockito.ArgumentMatchers.eq(Long.class)))
                .thenThrow(new RuntimeException("private database detail"));

        mockMvc.perform(get("/admin-api/admin/dashboard/summary"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value(503))
                .andExpect(content().string(not(containsString("private database detail"))));
    }

    @Test
    void missingHotGoodsCapabilityReturnsHttp503InsteadOfOkEmptyList() throws Exception {
        when(jdbcTemplate.queryForObject(anyString(), org.mockito.ArgumentMatchers.eq(Integer.class)))
                .thenReturn(0);

        mockMvc.perform(get("/admin-api/admin/dashboard/top-hot-goods"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value(503));
    }

    @Test
    void invalidTrendRangeReturnsHttp400InsteadOfSilentlyUsingSevenDays() throws Exception {
        mockMvc.perform(get("/admin-api/admin/dashboard/trend").param("range", "365"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400));
    }

    private static HttpServer jsonServer(String path, int status, String json) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext(path, exchange -> {
            byte[] body = json.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
            exchange.sendResponseHeaders(status, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        return server;
    }

    private static String serverBaseUrl(HttpServer server) {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }
}
