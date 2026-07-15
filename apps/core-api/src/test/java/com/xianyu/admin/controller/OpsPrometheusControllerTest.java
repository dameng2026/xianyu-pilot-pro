package com.xianyu.admin.controller;

import org.junit.jupiter.api.Test;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;
import java.sql.Connection;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class OpsPrometheusControllerTest {

    @Test
    void exposesDependencyHealthAsPrometheusGauges() throws Exception {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        DataSource dataSource = mock(DataSource.class);
        Connection database = mock(Connection.class);
        RedisConnectionFactory redisConnectionFactory = mock(RedisConnectionFactory.class);
        RedisConnection redis = mock(RedisConnection.class);

        when(dataSource.getConnection()).thenReturn(database);
        when(database.isValid(2)).thenReturn(true);
        when(redisConnectionFactory.getConnection()).thenReturn(redis);
        when(redis.ping()).thenReturn("PONG");
        String metrics = new OpsPrometheusController(
                jdbcTemplate,
                dataSource,
                redisConnectionFactory
        ).prometheus();

        assertTrue(metrics.contains("xianyu_core_database_up 1"));
        assertTrue(metrics.contains("xianyu_core_redis_up 1"));
    }
}
