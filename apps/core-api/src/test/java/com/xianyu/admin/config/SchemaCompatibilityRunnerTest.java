package com.xianyu.admin.config;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class SchemaCompatibilityRunnerTest {

    @Test
    void runShouldCreateAndSeedAiScenePricingTables() throws Exception {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        SchemaCompatibilityRunner runner = new SchemaCompatibilityRunner(jdbcTemplate);

        runner.run(new DefaultApplicationArguments(new String[0]));

        ArgumentCaptor<String> sqlCaptor = ArgumentCaptor.forClass(String.class);
        verify(jdbcTemplate, atLeastOnce()).execute(sqlCaptor.capture());
        List<String> sqls = sqlCaptor.getAllValues();

        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS ai_scene_sell_config")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS ai_scene_plan_benefit")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS payment_order")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS payment_order")
                && sql.contains("payment_config_id")
                && sql.contains("uk_payment_order_gateway_trade")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS token_recharge_plan")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS notification_delivery_log")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS user_notification_setting")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS xianyu_account_auto_rate_config")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS user_business_setting")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("CREATE TABLE IF NOT EXISTS tenant_storage_asset")
                && sql.contains("visibility VARCHAR(16)")
                && sql.contains("purpose VARCHAR(64)")
                && sql.contains("published_time DATETIME")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("INSERT INTO ai_scene_sell_config") && sql.contains("'auto_reply'")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("INSERT INTO ai_scene_plan_benefit") && sql.contains("'auto_reply'") && sql.contains("'normal'")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("INSERT INTO token_recharge_plan") && sql.contains("'100 Token'")));
        assertTrue(sqls.stream().anyMatch(sql -> sql.contains("INSERT INTO billing_plan") && sql.contains("'vip'")));
    }

    @Test
    void runShouldFailStartupWhenAnyRequiredSchemaOperationFails() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        doThrow(new IllegalStateException("permission denied"))
                .when(jdbcTemplate)
                .execute(argThat((String sql) -> sql != null && sql.contains("CREATE TABLE IF NOT EXISTS sys_admin_user")));
        SchemaCompatibilityRunner runner = new SchemaCompatibilityRunner(jdbcTemplate);

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> runner.run(new DefaultApplicationArguments(new String[0]))
        );

        assertTrue(error.getMessage().contains("schema compatibility failed"));
        assertTrue(error.getMessage().contains("sys_admin_user"));
    }

    @Test
    void productionValidationModeMustBeReadOnly() throws Exception {
        AtomicInteger mutationCount = new AtomicInteger();
        JdbcTemplate jdbcTemplate = new JdbcTemplate() {
            @Override
            public void execute(String sql) {
                mutationCount.incrementAndGet();
            }

            @Override
            public <T> T queryForObject(String sql, Class<T> requiredType, Object... args) {
                return requiredType.cast(1);
            }
        };
        SchemaCompatibilityRunner runner = new SchemaCompatibilityRunner(jdbcTemplate, false);

        runner.run(new DefaultApplicationArguments(new String[0]));

        assertEquals(0, mutationCount.get(), "validation mode must never execute DDL or DML");
    }

    @Test
    void productionValidationModeFailsClosedWhenARequiredTableIsMissing() {
        JdbcTemplate jdbcTemplate = new JdbcTemplate() {
            @Override
            public void execute(String sql) {
                throw new AssertionError("validation mode attempted to mutate the database");
            }

            @Override
            public <T> T queryForObject(String sql, Class<T> requiredType, Object... args) {
                boolean missing = sql.contains("information_schema.tables")
                        && args.length > 0
                        && "sys_admin_user".equals(args[0]);
                return requiredType.cast(missing ? 0 : 1);
            }
        };
        SchemaCompatibilityRunner runner = new SchemaCompatibilityRunner(jdbcTemplate, false);

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> runner.run(new DefaultApplicationArguments(new String[0]))
        );

        assertTrue(error.getMessage().contains("missing table sys_admin_user"));
    }

    @Test
    void productionProfileMustRejectRuntimeMutationOverrideBeforeTouchingDatabase() {
        AtomicInteger databaseCalls = new AtomicInteger();
        JdbcTemplate jdbcTemplate = new JdbcTemplate() {
            @Override
            public void execute(String sql) {
                databaseCalls.incrementAndGet();
            }

            @Override
            public <T> T queryForObject(String sql, Class<T> requiredType, Object... args) {
                databaseCalls.incrementAndGet();
                return requiredType.cast(1);
            }
        };
        SchemaCompatibilityRunner runner = new SchemaCompatibilityRunner(jdbcTemplate, true, "prod");

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> runner.run(new DefaultApplicationArguments(new String[0]))
        );

        assertTrue(error.getMessage().contains("forbidden"));
        assertEquals(0, databaseCalls.get());
    }
}
