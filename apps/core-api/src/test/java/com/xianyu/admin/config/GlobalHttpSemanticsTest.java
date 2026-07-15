package com.xianyu.admin.config;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.http.server.ServletServerHttpRequest;
import org.springframework.http.server.ServletServerHttpResponse;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

class GlobalHttpSemanticsTest {

    @Test
    void businessErrorsUseTheirRealHttpStatus() {
        GlobalExceptionHandler handler = new GlobalExceptionHandler();

        ResponseEntity<Result<Object>> response = handler.handleBiz(
                new BizException(429, "请求过于频繁")
        );

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, response.getStatusCode());
        assertEquals(429, response.getBody().getCode());
    }

    @Test
    void unhandledErrorsReturnHttp500WithoutLeakingTheCause() {
        GlobalExceptionHandler handler = new GlobalExceptionHandler();

        ResponseEntity<Result<Void>> response = handler.handle(
                new IllegalStateException("database-password=secret")
        );

        assertEquals(HttpStatus.INTERNAL_SERVER_ERROR, response.getStatusCode());
        assertEquals(500, response.getBody().getCode());
        assertFalse(response.getBody().getMsg().contains("database-password"));
        assertFalse(response.getBody().getMsg().contains("secret"));
    }

    @Test
    void databaseOutagesReturnServiceUnavailableWithoutLeakingSqlDetails() {
        GlobalExceptionHandler handler = new GlobalExceptionHandler();

        ResponseEntity<Result<Void>> response = handler.handleDataAccess(
                new DataAccessResourceFailureException("jdbc:mysql://db/internal?password=secret")
        );

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response.getStatusCode());
        assertEquals(503, response.getBody().getCode());
        assertFalse(response.getBody().getMsg().contains("jdbc:mysql"));
        assertFalse(response.getBody().getMsg().contains("secret"));
    }

    @Test
    void controllerResultFailuresCannotRemainHttp200() {
        ResultHttpStatusAdvice advice = new ResultHttpStatusAdvice();
        MockHttpServletResponse servletResponse = new MockHttpServletResponse();
        ServletServerHttpResponse response = new ServletServerHttpResponse(servletResponse);

        advice.beforeBodyWrite(
                Result.fail("依赖服务不可用"),
                null,
                null,
                MappingJackson2HttpMessageConverter.class,
                new ServletServerHttpRequest(new MockHttpServletRequest()),
                response
        );

        assertEquals(HttpStatus.INTERNAL_SERVER_ERROR.value(), servletResponse.getStatus());
    }

    @Test
    void controllerResultSuccessRemainsHttp200() {
        ResultHttpStatusAdvice advice = new ResultHttpStatusAdvice();
        MockHttpServletResponse servletResponse = new MockHttpServletResponse();
        ServletServerHttpResponse response = new ServletServerHttpResponse(servletResponse);

        advice.beforeBodyWrite(
                Result.ok("ok"),
                null,
                null,
                MappingJackson2HttpMessageConverter.class,
                new ServletServerHttpRequest(new MockHttpServletRequest()),
                response
        );

        assertEquals(HttpStatus.OK.value(), servletResponse.getStatus());
    }
}
