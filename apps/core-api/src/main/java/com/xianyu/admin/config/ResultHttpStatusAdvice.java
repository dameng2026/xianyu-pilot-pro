package com.xianyu.admin.config;

import com.xianyu.admin.common.Result;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.http.server.ServletServerHttpResponse;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.servlet.mvc.method.annotation.ResponseBodyAdvice;

/**
 * Keeps the JSON business code and the HTTP transport status aligned.
 *
 * <p>Legacy controllers return {@link Result} directly. Without this advice a body such as
 * {@code {"code":503}} is transported as HTTP 200, so load balancers, monitoring and clients
 * cannot distinguish an outage from success.</p>
 */
@ControllerAdvice
public class ResultHttpStatusAdvice implements ResponseBodyAdvice<Object> {

    @Override
    public boolean supports(MethodParameter returnType,
                            Class<? extends HttpMessageConverter<?>> converterType) {
        return true;
    }

    @Override
    public Object beforeBodyWrite(Object body,
                                  MethodParameter returnType,
                                  MediaType selectedContentType,
                                  Class<? extends HttpMessageConverter<?>> selectedConverterType,
                                  ServerHttpRequest request,
                                  ServerHttpResponse response) {
        if (!(body instanceof Result<?> result)) {
            return body;
        }

        int code = result.getCode();
        if (code < 400 || code > 599) {
            return body;
        }

        // Respect filters/controllers that already selected a non-success status.
        if (response instanceof ServletServerHttpResponse servletResponse
                && servletResponse.getServletResponse().getStatus() >= 300) {
            return body;
        }
        response.setStatusCode(HttpStatusCode.valueOf(code));
        return body;
    }
}
