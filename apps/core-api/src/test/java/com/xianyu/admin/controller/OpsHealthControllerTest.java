package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.config.UploadPathConfig;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OpsHealthControllerTest {

    @Mock DataSource dataSource;
    @Mock RedisConnectionFactory redisConnectionFactory;
    @Mock Connection databaseConnection;
    @Mock RedisConnection redisConnection;
    @Mock UploadPathConfig uploadPathConfig;

    @Test
    void readinessUsesHttp200OnlyWhenEveryRequiredDependencyIsReady() throws Exception {
        when(dataSource.getConnection()).thenReturn(databaseConnection);
        when(databaseConnection.isValid(2)).thenReturn(true);
        when(redisConnectionFactory.getConnection()).thenReturn(redisConnection);
        when(redisConnection.ping()).thenReturn("PONG");
        when(uploadPathConfig.isWritable()).thenReturn(true);
        OpsHealthController controller = new OpsHealthController(
                dataSource, redisConnectionFactory, uploadPathConfig, "core-api");

        ResponseEntity<Result<Map<String, Object>>> response = controller.readiness();

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertEquals("UP", response.getBody().getData().get("status"));
    }

    @Test
    void readinessUsesHttp503AndDoesNotExposeDependencyErrors() throws Exception {
        when(dataSource.getConnection()).thenThrow(new SQLException("jdbc:mysql://user:secret@db"));
        when(redisConnectionFactory.getConnection()).thenThrow(new IllegalStateException("redis password secret"));
        OpsHealthController controller = new OpsHealthController(
                dataSource, redisConnectionFactory, uploadPathConfig, "core-api");

        ResponseEntity<Result<Map<String, Object>>> response = controller.readiness();

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response.getStatusCode());
        assertEquals(503, response.getBody().getCode());
        assertEquals("DOWN", response.getBody().getData().get("status"));
        assertFalse(response.toString().contains("jdbc:mysql"));
        assertFalse(response.toString().contains("password"));
        assertFalse(response.toString().contains("secret"));
    }

    @Test
    void readinessFailsWhenUploadVolumeIsNotWritable() throws Exception {
        when(dataSource.getConnection()).thenReturn(databaseConnection);
        when(databaseConnection.isValid(2)).thenReturn(true);
        when(redisConnectionFactory.getConnection()).thenReturn(redisConnection);
        when(redisConnection.ping()).thenReturn("PONG");
        when(uploadPathConfig.isWritable()).thenReturn(false);
        OpsHealthController controller = new OpsHealthController(
                dataSource, redisConnectionFactory, uploadPathConfig, "core-api");

        ResponseEntity<Result<Map<String, Object>>> response = controller.readiness();

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response.getStatusCode());
        assertEquals("DOWN", response.getBody().getData().get("status"));
    }
}
