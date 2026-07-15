package com.xianyu.admin.controller;

import com.sun.net.httpserver.HttpServer;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AdminModuleService;
import com.xianyu.admin.service.AiProviderEndpointPolicy;
import com.xianyu.admin.service.DashboardService;
import com.xianyu.admin.service.ImageGenerationService;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;

class AdminModuleControllerHealthTest {

    @Test
    void systemHealthUsesConfiguredServiceBasesAndCrawlerReadinessEndpoint() throws Exception {
        AtomicInteger automationChecks = new AtomicInteger();
        AtomicInteger crawlerChecks = new AtomicInteger();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/ready", exchange -> {
            automationChecks.incrementAndGet();
            byte[] body = "{\"status\":\"ok\",\"service\":\"automation-service\"}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.createContext("/api/ready", exchange -> {
            crawlerChecks.incrementAndGet();
            byte[] body = "{\"status\":\"ready\",\"service\":\"crawler-service\"}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();

        try {
            AdminModuleController controller = new AdminModuleController(
                    mock(AdminModuleService.class),
                    mock(DashboardService.class),
                    mock(ImageGenerationService.class),
                    mock(JdbcTemplate.class),
                    mock(AiProviderEndpointPolicy.class)
            );
            String baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
            ReflectionTestUtils.setField(controller, "automationBaseUrl", baseUrl + "/");
            ReflectionTestUtils.setField(controller, "crawlerBaseUrl", baseUrl + "/");

            Result<Map<String, Object>> response = controller.systemHealth();

            Map<String, Object> automation = castMap(response.getData().get("automationService"));
            Map<String, Object> crawler = castMap(response.getData().get("crawlerService"));
            assertEquals("up", automation.get("status"));
            assertEquals("up", crawler.get("status"));
            assertEquals(1, automationChecks.get());
            assertEquals(1, crawlerChecks.get());
        } finally {
            server.stop(0);
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castMap(Object value) {
        return (Map<String, Object>) value;
    }
}
