package com.xianyu.admin.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

/**
 * 全局 Jackson 配置：统一注册 JavaTimeModule，解决 LocalDateTime / LocalDate 等时间字段
 * 序列化时抛 InvalidDefinitionException 导致接口 500 的问题。
 *
 * <p>历史上 core-api 中存在 40+ 处 {@code new ObjectMapper()} 实例，仅 4 处正确注册了
 * JavaTimeModule，其余 37 处未注册。本配置提供一个全局 Bean，后续应逐步将各处
 * {@code new ObjectMapper()} 替换为注入此 Bean；同时 Spring Boot 自动装配会使用此 Bean
 * 作为 HTTP 消息转换器，覆盖 Controller 返回的 JSON 序列化场景。
 *
 * <p>注意：直接 {@code new ObjectMapper()} 的场景（非 Spring 管理）仍需手动调用
 * {@code findAndRegisterModules()} 或注入此 Bean，本配置无法替代。
 */
@Configuration
public class JacksonConfig {

    @Bean
    @Primary
    public ObjectMapper objectMapper() {
        return new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }
}
