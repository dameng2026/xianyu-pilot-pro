package com.xianyu.admin.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class SchemaCompatibilityRunner implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(SchemaCompatibilityRunner.class);

    private final JdbcTemplate jdbcTemplate;
    private final boolean runtimeMutationsEnabled;
    private final boolean productionLike;
    private final List<String> failures = new ArrayList<>();

    public SchemaCompatibilityRunner(JdbcTemplate jdbcTemplate) {
        this(jdbcTemplate, true, "");
    }

    public SchemaCompatibilityRunner(JdbcTemplate jdbcTemplate, boolean runtimeMutationsEnabled) {
        this(jdbcTemplate, runtimeMutationsEnabled, "");
    }

    @Autowired
    public SchemaCompatibilityRunner(
            JdbcTemplate jdbcTemplate,
            @Value("${xianyu.schema.runtime-mutations-enabled:true}") boolean runtimeMutationsEnabled,
            @Value("${spring.profiles.active:}") String activeProfiles
    ) {
        this.jdbcTemplate = jdbcTemplate;
        this.runtimeMutationsEnabled = runtimeMutationsEnabled;
        this.productionLike = isProductionLike(activeProfiles);
    }

    @Override
    public void run(ApplicationArguments args) {
        if (productionLike && runtimeMutationsEnabled) {
            throw new IllegalStateException("runtime schema mutations are forbidden in production-like profiles");
        }
        failures.clear();
        log.info("SchemaCompatibilityRunner: schema check runtimeMutationsEnabled={}", runtimeMutationsEnabled);
        ensureSecurityTables();
        ensureAccountTables();
        ensureDashboardAndNotificationTables();
        ensureDeliveryAndCardTables();
        ensureBillingAndPaymentTables();
        ensureWorkflowTables();
        ensureMiscTables();
        ensureOpenSourceBridgeTables();
        ensureMallTables();
        ensureSupplyTables();
        ensureAiCsTables();
        ensureRateTables();
        ensureRefundTables();
        ensureGrowthTables();
        ensureCompatibilityColumns();
        backfillCompatibilityData();
        if (!failures.isEmpty()) {
            String summary = String.join(", ", failures.stream().limit(5).toList());
            throw new IllegalStateException(
                    "schema compatibility failed (" + failures.size() + " operation(s)): " + summary
            );
        }
        log.info("SchemaCompatibilityRunner: done runtimeMutationsEnabled={}", runtimeMutationsEnabled);
    }

    private void ensureSecurityTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS sys_admin_user (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(80) NOT NULL UNIQUE,
                    password_hash VARCHAR(200) NOT NULL,
                    nickname VARCHAR(100),
                    email VARCHAR(150),
                    avatar TEXT,
                    roles VARCHAR(500),
                    status TINYINT DEFAULT 1,
                    security_version BIGINT NOT NULL DEFAULT 1,
                    last_login_time DATETIME,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "sys_admin_user");

        createTable("""
                CREATE TABLE IF NOT EXISTS sys_tenant (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_name VARCHAR(100),
                    name VARCHAR(80),
                    display_name VARCHAR(200),
                    contact_name VARCHAR(100),
                    contact_phone VARCHAR(50),
                    contact_email VARCHAR(120),
                    status TINYINT DEFAULT 1,
                    remark TEXT,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "sys_tenant");

        createTable("""
                CREATE TABLE IF NOT EXISTS sys_user (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(80) NOT NULL,
                    password_hash VARCHAR(200) NOT NULL,
                    nickname VARCHAR(100),
                    phone VARCHAR(50),
                    email VARCHAR(120),
                    avatar TEXT,
                    user_type TINYINT DEFAULT 1,
                    tenant_id BIGINT,
                    status TINYINT DEFAULT 1,
                    token_balance BIGINT DEFAULT 0,
                    phone_verified TINYINT DEFAULT 0,
                    email_verified TINYINT DEFAULT 0,
                    last_security_update_time DATETIME,
                    security_version BIGINT NOT NULL DEFAULT 1,
                    vip_level INT DEFAULT 0,
                    last_login_time DATETIME,
                    last_login_ip VARCHAR(50),
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_user_tenant(tenant_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "sys_user");

        createTable("""
                CREATE TABLE IF NOT EXISTS admin_module_record (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    module_key VARCHAR(80) NOT NULL,
                    status VARCHAR(40),
                    json_text JSON NOT NULL,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_module_deleted(module_key, deleted),
                    INDEX idx_module_status(module_key, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "admin_module_record");

        createTable("""
                CREATE TABLE IF NOT EXISTS tenant_storage_asset (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NULL,
                    storage_key VARCHAR(512) NOT NULL UNIQUE,
                    public_url VARCHAR(700) NOT NULL,
                    media_type VARCHAR(100),
                    source_type VARCHAR(50) NOT NULL,
                    visibility VARCHAR(16) NOT NULL DEFAULT 'private',
                    purpose VARCHAR(64) NOT NULL DEFAULT 'user-media',
                    owner_type VARCHAR(32),
                    owner_id BIGINT,
                    size_bytes BIGINT NOT NULL,
                    sha256 CHAR(64) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'reserved',
                    request_id VARCHAR(128),
                    deletion_reason VARCHAR(255),
                    cleaned_by VARCHAR(120),
                    reviewed_by VARCHAR(120),
                    approved_by VARCHAR(120),
                    activated_time DATETIME,
                    published_time DATETIME,
                    deleted_time DATETIME,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_storage_asset_tenant_status(tenant_id, status),
                    INDEX idx_storage_asset_created(created_time),
                    INDEX idx_storage_asset_status_created(status, created_time),
                    INDEX idx_storage_asset_status_size(status, size_bytes),
                    INDEX idx_storage_asset_visibility_status(visibility, status, updated_time),
                    INDEX idx_storage_asset_owner(tenant_id, owner_type, owner_id, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "tenant_storage_asset");

        createTable("""
                CREATE TABLE IF NOT EXISTS tenant_upload_rate_event (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT,
                    request_id VARCHAR(128),
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_upload_rate_tenant_time(tenant_id, created_time),
                    INDEX idx_upload_rate_created(created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "tenant_upload_rate_event");
    }

    private void ensureAccountTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_account (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT,
                    created_by_user_id BIGINT,
                    platform VARCHAR(50) DEFAULT 'xianyu',
                    external_uid VARCHAR(120),
                    nickname VARCHAR(120),
                    avatar_url TEXT,
                    province VARCHAR(80),
                    city VARCHAR(80),
                    account_level INT,
                    remark TEXT,
                    status TINYINT DEFAULT 1,
                    risk_level TINYINT DEFAULT 0,
                    disabled_by_admin TINYINT DEFAULT 0,
                    admin_remark TEXT,
                    display_name VARCHAR(100),
                    ip_location VARCHAR(100),
                    introduction TEXT,
                    followers INT,
                    following INT,
                    seller_level VARCHAR(50),
                    fish_shop_score INT,
                    fish_shop_user TINYINT,
                    praise_ratio VARCHAR(20),
                    review_num INT,
                    sold_count INT,
                    message_expire_time INT DEFAULT 3600,
                    scheduled_redelivery TINYINT DEFAULT 0,
                    auto_polish TINYINT DEFAULT 0,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_xianyu_account_tenant_user(tenant_id, user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_account");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_account_auth (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    account_id BIGINT NOT NULL,
                    auth_type VARCHAR(50) DEFAULT 'cookie',
                    encrypted_cookie TEXT,
                    encrypted_token TEXT,
                    login_username VARCHAR(255),
                    encrypted_login_password TEXT,
                    show_browser TINYINT DEFAULT 0,
                    cookie_status TINYINT DEFAULT 0,
                    ws_token TEXT,
                    token_expire_time DATETIME,
                    last_login_status_code VARCHAR(64),
                    last_login_status_message VARCHAR(255),
                    last_login_check_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_auth_account(tenant_id, account_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_account_auth");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_account_runtime (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    account_id BIGINT NOT NULL,
                    online_status TINYINT DEFAULT 0,
                    ws_status TINYINT DEFAULT 0,
                    ws_latency_ms INT DEFAULT 0,
                    cookie_status TINYINT DEFAULT 0,
                    last_login_time DATETIME,
                    last_heartbeat_time DATETIME,
                    last_online_time DATETIME,
                    last_sync_time DATETIME,
                    last_login_status_code VARCHAR(64),
                    last_login_status_message VARCHAR(255),
                    last_login_check_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_runtime_account(tenant_id, account_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_account_runtime");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_account_health_snapshot (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    account_id BIGINT NOT NULL,
                    health_score INT DEFAULT 100,
                    api_success_rate DOUBLE DEFAULT 100.0,
                    avg_response_ms INT DEFAULT 0,
                    ws_latency_ms INT DEFAULT 0,
                    collected_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_health_account(tenant_id, account_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_account_health_snapshot");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_account_membership (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    account_id BIGINT NOT NULL,
                    tenant_id BIGINT,
                    level VARCHAR(50) DEFAULT 'normal',
                    status VARCHAR(40) DEFAULT '1',
                    expired_time DATETIME,
                    membership_type VARCHAR(50),
                    is_expired TINYINT DEFAULT 0,
                    expire_time DATETIME,
                    auto_renew TINYINT DEFAULT 0,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_am_account(account_id),
                    INDEX idx_am_tenant(tenant_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_account_membership");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_account_auto_rate_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NULL,
                    account_id BIGINT NOT NULL,
                    enabled TINYINT DEFAULT 0,
                    rate_type VARCHAR(30) DEFAULT 'text',
                    text_content TEXT NULL,
                    api_url TEXT NULL,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_xyaarc_tenant_account(tenant_id, account_id),
                    INDEX idx_xyaarc_tenant(tenant_id, deleted),
                    INDEX idx_xyaarc_account(account_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_account_auto_rate_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_trade_order (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    account_id BIGINT,
                    user_id BIGINT,
                    external_order_id VARCHAR(120),
                    order_id VARCHAR(120),
                    buyer_id VARCHAR(120),
                    buyer_name VARCHAR(120),
                    buyer_nickname VARCHAR(120),
                    total_amount DECIMAL(12,2) DEFAULT 0,
                    total_amount_cent BIGINT DEFAULT 0,
                    order_status VARCHAR(50),
                    pay_status VARCHAR(50),
                    delivery_status VARCHAR(16),
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_xto_tenant_account(tenant_id, account_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_trade_order");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_trade_order_item (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    order_id BIGINT NOT NULL,
                    goods_id BIGINT,
                    goods_title VARCHAR(500),
                    goods_price DECIMAL(12,2) DEFAULT 0,
                    goods_count INT DEFAULT 1,
                    spec_name VARCHAR(120),
                    spec_value VARCHAR(255),
                    external_goods_id VARCHAR(120),
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_xtoi_order(order_id),
                    INDEX idx_xtoi_tenant_order(tenant_id, order_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_trade_order_item");
    }

    private void ensureDashboardAndNotificationTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS dashboard_daily_stat (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT,
                    account_id BIGINT,
                    stat_date DATE NOT NULL,
                    account_count INT DEFAULT 0,
                    goods_count INT DEFAULT 0,
                    on_sale_goods_count INT DEFAULT 0,
                    selling_goods_count INT DEFAULT 0,
                    order_count INT DEFAULT 0,
                    sales_amount DECIMAL(12,2) DEFAULT 0,
                    order_amount DECIMAL(12,2) DEFAULT 0,
                    message_count INT DEFAULT 0,
                    auto_reply_hit_count INT DEFAULT 0,
                    auto_reply_count INT DEFAULT 0,
                    delivery_success_count INT DEFAULT 0,
                    delivery_fail_count INT DEFAULT 0,
                    ws_online_rate DOUBLE DEFAULT 0,
                    api_success_rate DOUBLE DEFAULT 0,
                    avg_response_ms INT DEFAULT 0,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    UNIQUE KEY uk_dds_tenant_date_account(tenant_id, stat_date, account_id),
                    INDEX idx_dds_tenant_date(tenant_id, stat_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "dashboard_daily_stat");

        createTable("""
                CREATE TABLE IF NOT EXISTS notification (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT,
                    account_id BIGINT,
                    notice_type VARCHAR(80),
                    notification_type VARCHAR(80),
                    title VARCHAR(200),
                    content TEXT,
                    level VARCHAR(40),
                    priority INT DEFAULT 0,
                    is_read TINYINT DEFAULT 0,
                    read_time DATETIME,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_notice_tenant_user(tenant_id, user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "notification");

        createTable("""
                CREATE TABLE IF NOT EXISTS notification_delivery_log (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT,
                    channel_key VARCHAR(80),
                    channel_name VARCHAR(120),
                    event_type VARCHAR(80),
                    success TINYINT DEFAULT 0,
                    status_code INT DEFAULT 0,
                    cost_ms BIGINT DEFAULT 0,
                    message VARCHAR(500),
                    request_body TEXT,
                    response_body TEXT,
                    retry_count INT DEFAULT 0,
                    created_time DATETIME,
                    INDEX idx_ndl_user_time(tenant_id, user_id, created_time),
                    INDEX idx_ndl_success(success, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "notification_delivery_log");

        createTable("""
                CREATE TABLE IF NOT EXISTS user_notification_setting (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    config_json JSON NOT NULL,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_uns_tenant_user(tenant_id, user_id),
                    INDEX idx_uns_user(user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "user_notification_setting");

        createTable("""
                CREATE TABLE IF NOT EXISTS notification_dedup (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    account_id BIGINT NOT NULL,
                    event_type VARCHAR(80) NOT NULL,
                    last_sent_time DATETIME NOT NULL,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_nd_tenant_account_event(tenant_id, account_id, event_type),
                    INDEX idx_nd_account(tenant_id, account_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "notification_dedup");

        createTable("""
                CREATE TABLE IF NOT EXISTS sys_notification_read (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    admin_user_id BIGINT NOT NULL,
                    event_source VARCHAR(60) NOT NULL DEFAULT 'recent_event',
                    event_id BIGINT NOT NULL,
                    read_at DATETIME NOT NULL,
                    UNIQUE KEY uk_admin_event(admin_user_id, event_source, event_id),
                    INDEX idx_snr_admin_time(admin_user_id, read_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "sys_notification_read");

        createTable("""
                CREATE TABLE IF NOT EXISTS system_service_status (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    service_key VARCHAR(80) NOT NULL,
                    service_name VARCHAR(120),
                    status VARCHAR(40),
                    message VARCHAR(300),
                    metadata_json JSON,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_service_status_tenant(tenant_id, service_key, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "system_service_status");

        createTable("""
                CREATE TABLE IF NOT EXISTS sys_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    config_key VARCHAR(100) NOT NULL,
                    config_value TEXT,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_config_key(config_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "sys_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS auto_reply_log (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    account_id BIGINT,
                    conversation_id BIGINT,
                    rule_id BIGINT,
                    trigger_message TEXT,
                    reply_content TEXT,
                    hit_type VARCHAR(60),
                    status TINYINT DEFAULT 1,
                    fail_reason VARCHAR(500),
                    action VARCHAR(40),
                    safety_reasons TEXT,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_auto_reply_log_tenant(tenant_id, created_time),
                    INDEX idx_auto_reply_log_account(account_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "auto_reply_log");

        createTable("""
                CREATE TABLE IF NOT EXISTS client_error_log (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT,
                    error_type VARCHAR(80),
                    message VARCHAR(500),
                    stack TEXT,
                    source VARCHAR(200),
                    route VARCHAR(300),
                    user_agent VARCHAR(600),
                    ip_address VARCHAR(80),
                    payload_json TEXT,
                    created_time DATETIME,
                    INDEX idx_client_error_tenant_time(tenant_id, created_time),
                    INDEX idx_client_error_user_time(user_id, created_time),
                    INDEX idx_client_error_type(error_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "client_error_log");
    }

    private void ensureDeliveryAndCardTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS auto_reply_rule (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    account_id BIGINT,
                    rule_name VARCHAR(200),
                    match_type VARCHAR(50),
                    match_keywords TEXT,
                    reply_content TEXT,
                    reply_mode VARCHAR(50),
                    status TINYINT DEFAULT 1,
                    priority INT DEFAULT 0,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_arr_tenant_account(tenant_id, account_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "auto_reply_rule");

        createTable("""
                CREATE TABLE IF NOT EXISTS delivery_rule (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    account_id BIGINT,
                    goods_id BIGINT,
                    rule_name VARCHAR(200),
                    delivery_type VARCHAR(50),
                    status TINYINT DEFAULT 1,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_dr_tenant_account(tenant_id, account_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "delivery_rule");

        createTable("""
                CREATE TABLE IF NOT EXISTS delivery_goods_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    goods_id BIGINT NOT NULL,
                    config_json TEXT,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_dgc_tenant_goods(tenant_id, goods_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "delivery_goods_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS delivery_statement (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    enabled TINYINT DEFAULT 0,
                    content TEXT,
                    scope VARCHAR(32) DEFAULT 'all',
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_ds_tenant(tenant_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "delivery_statement");

        createTable("""
                CREATE TABLE IF NOT EXISTS delivery_template (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    type TINYINT DEFAULT 6,
                    status TINYINT DEFAULT 1,
                    content TEXT,
                    random_enabled TINYINT DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_dt_tenant(tenant_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "delivery_template");

        createTable("""
                CREATE TABLE IF NOT EXISTS delivery_text_source (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    source_type VARCHAR(30) DEFAULT 'text',
                    delivery_mode VARCHAR(20) NOT NULL DEFAULT 'text',
                    card_group_id BIGINT DEFAULT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    remark VARCHAR(500),
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_dts_tenant(tenant_id, deleted, updated_time),
                    INDEX idx_dts_card_group(tenant_id, delivery_mode, card_group_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "delivery_text_source");

        createTable("""
                CREATE TABLE IF NOT EXISTS delivery_global_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    config_json TEXT,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_dgc_tenant(tenant_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "delivery_global_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS delivery_record (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    account_id BIGINT,
                    order_id BIGINT,
                    rule_id BIGINT,
                    delivery_type VARCHAR(50),
                    content TEXT,
                    status TINYINT DEFAULT 0,
                    delivery_status VARCHAR(50),
                    error_message TEXT,
                    retry_count INT DEFAULT 0,
                    fail_reason TEXT,
                    delivery_mode VARCHAR(16),
                    delivery_content TEXT,
                    delivery_timing VARCHAR(32),
                    delivery_method VARCHAR(50),
                    delivery_fail_reason TEXT,
                    quantity_requested INT DEFAULT 0,
                    quantity_sent INT DEFAULT 0,
                    platform_sync_time DATETIME,
                    completed_time DATETIME,
                    card_item_id BIGINT,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_delivery_tenant(tenant_id),
                    INDEX idx_delivery_status(status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "delivery_record");

        createTable("""
                CREATE TABLE IF NOT EXISTS card_group (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT,
                    group_name VARCHAR(200),
                    description TEXT,
                    group_type VARCHAR(80),
                    card_prefix VARCHAR(120),
                    password_prefix VARCHAR(120),
                    remark TEXT,
                    alert_threshold INT DEFAULT 10,
                    cost_price DECIMAL(10,2),
                    suggested_price DECIMAL(10,2),
                    total_count INT DEFAULT 0,
                    used_count INT DEFAULT 0,
                    remain_count INT DEFAULT 0,
                    available_count INT DEFAULT 0,
                    sku_property_key VARCHAR(512) NULL,
                    status TINYINT DEFAULT 1,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_card_group_tenant(tenant_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "card_group");

        createTable("""
                CREATE TABLE IF NOT EXISTS card_item (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    group_id BIGINT,
                    card_content TEXT,
                    card_key TEXT,
                    card_value TEXT,
                    extra_info TEXT,
                    is_used TINYINT DEFAULT 0,
                    status TINYINT DEFAULT 0,
                    used_order_id BIGINT,
                    used_by_order_id BIGINT,
                    used_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_card_item_group(group_id, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "card_item");

        createTable("""
                CREATE TABLE IF NOT EXISTS scheduled_task (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    account_id BIGINT,
                    task_type VARCHAR(80) NOT NULL,
                    task_name VARCHAR(200),
                    cron_expression VARCHAR(120),
                    config_json TEXT,
                    enabled TINYINT NOT NULL DEFAULT 1,
                    last_run_time DATETIME(6),
                    next_run_time DATETIME(6),
                    last_status VARCHAR(40),
                    last_result TEXT,
                    last_started_time DATETIME(6),
                    last_finished_time DATETIME(6),
                    lease_token CHAR(32),
                    lease_owner VARCHAR(120),
                    lease_expires_at DATETIME(6),
                    run_attempt_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
                    consecutive_failure_count INT UNSIGNED NOT NULL DEFAULT 0,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted TINYINT NOT NULL DEFAULT 0,
                    INDEX idx_task_tenant(tenant_id),
                    INDEX idx_task_enabled(enabled),
                    INDEX idx_scheduled_task_due_claim(enabled, deleted, next_run_time, lease_expires_at),
                    INDEX idx_scheduled_task_tenant_lease(tenant_id, lease_token)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "scheduled_task");
    }

    private void ensureBillingAndPaymentTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS billing_plan (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    plan_name VARCHAR(100) NOT NULL,
                    plan_code VARCHAR(100) NOT NULL UNIQUE,
                    price_cent BIGINT DEFAULT 0,
                    duration_days INT DEFAULT 30,
                    max_xianyu_accounts INT DEFAULT 1,
                    max_goods_count INT DEFAULT 100,
                    max_ai_reply_per_day INT DEFAULT 100,
                    max_workflow_per_day INT DEFAULT 0,
                    max_storage_mb INT DEFAULT 500,
                    enable_auto_delivery TINYINT DEFAULT 0,
                    enable_kami TINYINT DEFAULT 0,
                    enable_ai_reply TINYINT DEFAULT 0,
                    enable_workflow TINYINT DEFAULT 0,
                    features_text TEXT NULL,
                    period_type VARCHAR(20) NOT NULL DEFAULT 'month',
                    price_month_cent BIGINT DEFAULT 0,
                    price_quarter_cent BIGINT DEFAULT 0,
                    price_year_cent BIGINT DEFAULT 0,
                    status TINYINT DEFAULT 1,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "billing_plan");

        createTable("""
                CREATE TABLE IF NOT EXISTS billing_subscription (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    plan_id BIGINT NOT NULL,
                    target_type VARCHAR(50) DEFAULT 'user_account',
                    target_id BIGINT,
                    start_time DATETIME,
                    end_time DATETIME,
                    status TINYINT DEFAULT 1,
                    source VARCHAR(50),
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_sub_user(user_id),
                    INDEX idx_sub_tenant(tenant_id),
                    INDEX idx_sub_end_time(end_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "billing_subscription");

        createTable("""
                CREATE TABLE IF NOT EXISTS payment_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    channel_type VARCHAR(30) NOT NULL,
                    provider_type VARCHAR(30) DEFAULT 'official',
                    config_name VARCHAR(120),
                    merchant_id VARCHAR(160),
                    app_id VARCHAR(200),
                    private_key TEXT,
                    public_key TEXT,
                    api_key TEXT,
                    notify_url VARCHAR(500),
                    gateway_url VARCHAR(500),
                    enabled TINYINT DEFAULT 0,
                    sandbox TINYINT DEFAULT 0,
                    remark TEXT,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_payment_config_channel(channel_type, enabled, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "payment_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS payment_order (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT NOT NULL,
                    order_no VARCHAR(80) NOT NULL UNIQUE,
                    order_type VARCHAR(30) NOT NULL,
                    target_type VARCHAR(50) DEFAULT 'user_account',
                    target_id BIGINT,
                    plan_id BIGINT,
                    token_plan_id BIGINT,
                    title VARCHAR(200),
                    amount_cent BIGINT NOT NULL,
                    token_amount BIGINT DEFAULT 0,
                    payment_method VARCHAR(30) NOT NULL,
                    provider_type VARCHAR(30) DEFAULT 'official',
                    payment_config_id BIGINT,
                    status TINYINT DEFAULT 0,
                    client_ip VARCHAR(80),
                    qr_content TEXT,
                    pay_url TEXT,
                    out_trade_no VARCHAR(120),
                    paid_time DATETIME,
                    expire_time DATETIME,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    period_type VARCHAR(10) DEFAULT NULL COMMENT 'VIP订单计费周期：month/quarter/year；NULL 视为 month（兼容历史订单）',
                    UNIQUE KEY uk_payment_order_gateway_trade(out_trade_no),
                    INDEX idx_payment_order_user(user_id, created_time),
                    INDEX idx_payment_order_status(status),
                    INDEX idx_payment_order_type(order_type),
                    INDEX idx_payment_order_config(payment_config_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "payment_order");

        createTable("""
                CREATE TABLE IF NOT EXISTS payment_callback_log (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    order_no VARCHAR(80),
                    channel_type VARCHAR(30),
                    provider_type VARCHAR(30),
                    request_body MEDIUMTEXT,
                    signature VARCHAR(500),
                    verify_status TINYINT DEFAULT 0,
                    process_status TINYINT DEFAULT 0,
                    message VARCHAR(500),
                    created_time DATETIME,
                    INDEX idx_payment_callback_order(order_no),
                    INDEX idx_payment_callback_time(created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "payment_callback_log");

        createTable("""
                CREATE TABLE IF NOT EXISTS token_recharge_plan (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    plan_name VARCHAR(120) NOT NULL,
                    token_amount BIGINT NOT NULL,
                    bonus_token BIGINT DEFAULT 0,
                    price_cent BIGINT NOT NULL,
                    status TINYINT DEFAULT 1,
                    sort_order INT DEFAULT 100,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_token_plan_status(status, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "token_recharge_plan");

        createTable("""
                CREATE TABLE IF NOT EXISTS token_recharge_record (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT NOT NULL,
                    payment_order_id BIGINT,
                    order_no VARCHAR(80),
                    token_amount BIGINT NOT NULL,
                    before_balance BIGINT DEFAULT 0,
                    after_balance BIGINT DEFAULT 0,
                    source VARCHAR(80),
                    remark VARCHAR(300),
                    created_time DATETIME,
                    INDEX idx_token_record_user(user_id, created_time),
                    UNIQUE KEY uk_token_record_order(order_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "token_recharge_record");
    }

    private void ensureWorkflowTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_definition (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT,
                    name VARCHAR(160) NOT NULL,
                    description TEXT,
                    version INT DEFAULT 1,
                    status VARCHAR(30) DEFAULT 'draft',
                    trigger_type VARCHAR(60) DEFAULT 'manual',
                    config_json JSON,
                    canvas_json JSON,
                    enabled TINYINT DEFAULT 0,
                    published_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_wf_tenant_status(tenant_id, status, deleted),
                    INDEX idx_wf_user(user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_definition");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_node (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    workflow_id BIGINT NOT NULL,
                    node_key VARCHAR(80) NOT NULL,
                    node_name VARCHAR(160) NOT NULL,
                    node_type VARCHAR(60) NOT NULL,
                    position_x INT DEFAULT 80,
                    position_y INT DEFAULT 80,
                    config_json JSON,
                    retry_enabled TINYINT DEFAULT 0,
                    retry_count INT DEFAULT 0,
                    retry_interval_seconds INT DEFAULT 30,
                    sort_order INT DEFAULT 0,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_wf_node_workflow(workflow_id, deleted),
                    INDEX idx_wf_node_key(workflow_id, node_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_node");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_edge (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    workflow_id BIGINT NOT NULL,
                    source_node_key VARCHAR(80) NOT NULL,
                    target_node_key VARCHAR(80) NOT NULL,
                    condition_expr VARCHAR(500),
                    sort_order INT DEFAULT 0,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_wf_edge_workflow(workflow_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_edge");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_execution (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    workflow_id BIGINT NOT NULL,
                    execution_no VARCHAR(80) NOT NULL UNIQUE,
                    trigger_mode VARCHAR(60) DEFAULT 'manual',
                    status VARCHAR(30) DEFAULT 'queued',
                    progress INT DEFAULT 0,
                    input_json JSON,
                    output_json JSON,
                    error_message TEXT,
                    started_time DATETIME,
                    finished_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_wf_exec_workflow(workflow_id, created_time),
                    INDEX idx_wf_exec_tenant_status(tenant_id, status, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_execution");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_node_execution (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    execution_id BIGINT NOT NULL,
                    workflow_id BIGINT NOT NULL,
                    node_key VARCHAR(80),
                    node_name VARCHAR(160),
                    node_type VARCHAR(60),
                    status VARCHAR(30) DEFAULT 'queued',
                    input_json JSON,
                    output_json JSON,
                    error_message TEXT,
                    duration_ms BIGINT DEFAULT 0,
                    started_time DATETIME,
                    finished_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_wf_node_exec(execution_id, deleted),
                    INDEX idx_wf_node_exec_workflow(workflow_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_node_execution");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_artifact (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    execution_id BIGINT NOT NULL,
                    node_key VARCHAR(80),
                    artifact_type VARCHAR(60) DEFAULT 'json',
                    title VARCHAR(200),
                    content_json JSON,
                    file_url VARCHAR(500),
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    INDEX idx_wf_artifact_exec(execution_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_artifact");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_item_timing (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    execution_id BIGINT NOT NULL,
                    workflow_id BIGINT,
                    item_index INT DEFAULT 0,
                    source_item_id VARCHAR(80),
                    source_title VARCHAR(200),
                    polish_ms BIGINT DEFAULT 0,
                    image_generate_ms BIGINT DEFAULT 0,
                    publish_ms BIGINT DEFAULT 0,
                    total_ms BIGINT DEFAULT 0,
                    created_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_wit_exec(execution_id),
                    INDEX idx_wit_tenant_time(tenant_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_item_timing");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_timeline (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    execution_id BIGINT NOT NULL,
                    workflow_id BIGINT,
                    node_key VARCHAR(80),
                    event_level VARCHAR(20) DEFAULT 'INFO',
                    event_type VARCHAR(60) DEFAULT 'node',
                    title VARCHAR(200),
                    content TEXT,
                    payload_json JSON,
                    created_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_wf_timeline_exec(execution_id, created_time),
                    INDEX idx_wf_timeline_workflow(workflow_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_timeline");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_state_variable (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    execution_id BIGINT NOT NULL,
                    node_key VARCHAR(80),
                    var_name VARCHAR(120) NOT NULL,
                    var_value JSON,
                    var_type VARCHAR(60) DEFAULT 'string',
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_wf_state_exec(execution_id, var_name),
                    INDEX idx_wf_state_node(execution_id, node_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_state_variable");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_checkpoint (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    execution_id BIGINT NOT NULL,
                    workflow_id BIGINT,
                    node_key VARCHAR(80),
                    checkpoint_type VARCHAR(60) DEFAULT 'snapshot',
                    state_snapshot JSON,
                    context_json JSON,
                    retry_count INT DEFAULT 0,
                    max_retries INT DEFAULT 3,
                    status VARCHAR(30) DEFAULT 'active',
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_wf_cp_exec(execution_id, node_key),
                    INDEX idx_wf_cp_workflow(workflow_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_checkpoint");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_definition_version_snapshot (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    workflow_id BIGINT NOT NULL,
                    version INT NOT NULL,
                    name VARCHAR(160),
                    description TEXT,
                    trigger_type VARCHAR(60),
                    config_json JSON,
                    canvas_json JSON,
                    nodes_json JSON,
                    edges_json JSON,
                    snapshot_type VARCHAR(40) DEFAULT 'publish',
                    created_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_wf_snapshot_version(workflow_id, version, deleted),
                    INDEX idx_wf_snapshot_tenant(tenant_id, workflow_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_definition_version_snapshot");

        createTable("""
                CREATE TABLE IF NOT EXISTS workflow_published_goods (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    account_id BIGINT NOT NULL,
                    source_item_id VARCHAR(80) NOT NULL DEFAULT '',
                    source_title_hash CHAR(32) NOT NULL DEFAULT '',
                    source_image_url VARCHAR(500),
                    goods_id VARCHAR(80),
                    published_title VARCHAR(200),
                    workflow_id BIGINT,
                    execution_id BIGINT,
                    created_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_acct_item(tenant_id, account_id, source_item_id, deleted),
                    UNIQUE KEY uk_acct_title(tenant_id, account_id, source_title_hash, deleted),
                    INDEX idx_wpg_account(tenant_id, account_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "workflow_published_goods");
    }

    private void ensureMiscTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS ai_model_price_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NULL,
                    module_key VARCHAR(80) NOT NULL,
                    provider_name VARCHAR(120) DEFAULT 'default',
                    model_name VARCHAR(200) NOT NULL,
                    model_type VARCHAR(30) DEFAULT 'chat',
                    billing_mode VARCHAR(30) DEFAULT 'token',
                    input_price_per_1k DECIMAL(18,8) DEFAULT 0,
                    output_price_per_1k DECIMAL(18,8) DEFAULT 0,
                    cached_input_price_per_1k DECIMAL(18,8) DEFAULT 0,
                    per_call_price DECIMAL(18,8) DEFAULT 0,
                    spec_price_json TEXT,
                    token_exchange_rate DECIMAL(18,8) DEFAULT 100,
                    min_charge_token BIGINT DEFAULT 1,
                    billing_unit VARCHAR(20) DEFAULT '1K',
                    cost_per_image DECIMAL(18,8) DEFAULT 0,
                    tokens_per_image BIGINT DEFAULT 0,
                    cost_per_call DECIMAL(18,8) DEFAULT 0,
                    tokens_per_call BIGINT DEFAULT 0,
                    enabled TINYINT DEFAULT 1,
                    remark VARCHAR(500),
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_ai_price_lookup(model_type, model_name, provider_name, enabled, deleted),
                    INDEX idx_ai_price_module(module_key, enabled, deleted),
                    INDEX idx_ai_price_tenant(tenant_id, enabled, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "ai_model_price_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS ai_usage_log (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT NOT NULL,
                    scene VARCHAR(80),
                    provider_name VARCHAR(120),
                    model_name VARCHAR(200),
                    model_type VARCHAR(30) DEFAULT 'chat',
                    request_id VARCHAR(120) NOT NULL,
                    prompt_tokens BIGINT DEFAULT 0,
                    completion_tokens BIGINT DEFAULT 0,
                    total_tokens BIGINT DEFAULT 0,
                    cached_tokens BIGINT DEFAULT 0,
                    image_count BIGINT DEFAULT 0,
                    spec_key VARCHAR(120),
                    cost_cent BIGINT DEFAULT 0,
                    charge_tokens BIGINT DEFAULT 0,
                    balance_before BIGINT DEFAULT 0,
                    balance_after BIGINT DEFAULT 0,
                    status TINYINT DEFAULT 1,
                    error_message VARCHAR(500),
                    raw_usage_json MEDIUMTEXT,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_ai_usage_request(request_id),
                    INDEX idx_ai_usage_user(user_id, created_time),
                    INDEX idx_ai_usage_scene(scene, created_time),
                    INDEX idx_ai_usage_model(model_name, created_time),
                    INDEX idx_ai_usage_status(status, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "ai_usage_log");

        createTable("""
                CREATE TABLE IF NOT EXISTS token_balance_ledger (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT NOT NULL,
                    change_type VARCHAR(40) NOT NULL,
                    change_amount BIGINT NOT NULL,
                    before_balance BIGINT DEFAULT 0,
                    after_balance BIGINT DEFAULT 0,
                    ref_type VARCHAR(60),
                    ref_id BIGINT,
                    ref_no VARCHAR(120),
                    remark VARCHAR(500),
                    created_time DATETIME,
                    INDEX idx_token_ledger_user(user_id, created_time),
                    INDEX idx_token_ledger_ref(ref_type, ref_id),
                    INDEX idx_token_ledger_type(change_type, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "token_balance_ledger");

        createTable("""
                CREATE TABLE IF NOT EXISTS ai_scene_sell_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NULL,
                    scene_key VARCHAR(120) NOT NULL,
                    scene_name VARCHAR(120) NOT NULL,
                    scene_group VARCHAR(60) DEFAULT 'other',
                    charge_mode VARCHAR(60) NOT NULL,
                    price_unit VARCHAR(40) DEFAULT 'call',
                    enabled TINYINT DEFAULT 1,
                    is_metered TINYINT DEFAULT 1,
                    show_estimate TINYINT DEFAULT 1,
                    allow_trial TINYINT DEFAULT 0,
                    trial_quota INT DEFAULT 0,
                    base_tokens BIGINT DEFAULT 0,
                    step_size INT DEFAULT 0,
                    step_tokens BIGINT DEFAULT 0,
                    sell_tokens_per_call BIGINT DEFAULT 0,
                    sell_tokens_per_item BIGINT DEFAULT 0,
                    sell_tokens_per_image BIGINT DEFAULT 0,
                    sell_tokens_per_reply BIGINT DEFAULT 0,
                    sell_tokens_per_file BIGINT DEFAULT 0,
                    sell_tokens_per_1k_chars BIGINT DEFAULT 0,
                    min_tokens BIGINT DEFAULT 0,
                    max_tokens BIGINT DEFAULT 0,
                    member_discount_rate DECIMAL(10,4) DEFAULT 1.0000,
                    cost_markup_rate DECIMAL(10,4) DEFAULT 1.0000,
                    fallback_exchange_rate DECIMAL(18,8) DEFAULT 160,
                    daily_cap_count INT DEFAULT 0,
                    daily_cap_tokens BIGINT DEFAULT 0,
                    monthly_cap_count INT DEFAULT 0,
                    monthly_cap_tokens BIGINT DEFAULT 0,
                    sort_order INT DEFAULT 100,
                    remark VARCHAR(500),
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_ai_scene_sell_tenant_scene(tenant_id, scene_key, deleted),
                    INDEX idx_ai_scene_sell_scene(scene_key, enabled, deleted),
                    INDEX idx_ai_scene_sell_group(scene_group, enabled, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "ai_scene_sell_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS ai_model_tier_price (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    module_key VARCHAR(80) NOT NULL,
                    vip_level INT NOT NULL DEFAULT 0,
                    tokens_per_call BIGINT NOT NULL DEFAULT 3,
                    created_time DATETIME,
                    updated_time DATETIME,
                    UNIQUE KEY uk_tier_module_level (module_key, vip_level),
                    INDEX idx_tier_module (module_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "ai_model_tier_price");

        // 迁移现有 ai_model_price_config.tokens_per_call 到 ai_model_tier_price 三档（默认 3）
        // 仅在 ai_model_tier_price 中 model-config-general 三档记录不存在时插入
        try {
            Long existingGeneral = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM ai_model_tier_price WHERE module_key='model-config-general'",
                    Long.class);
            if (existingGeneral != null && existingGeneral == 0) {
                Long currentTokensPerCall = jdbcTemplate.queryForObject(
                        "SELECT COALESCE(tokens_per_call, 3) FROM ai_model_price_config " +
                                "WHERE deleted=0 AND module_key='model-config-general' ORDER BY id DESC LIMIT 1",
                        Long.class);
                long initialTokens = currentTokensPerCall != null && currentTokensPerCall > 0
                        ? currentTokensPerCall : 3L;
                jdbcTemplate.update("INSERT INTO ai_model_tier_price(module_key, vip_level, tokens_per_call, created_time, updated_time) " +
                        "VALUES('model-config-general', 0, ?, NOW(), NOW())", initialTokens);
                jdbcTemplate.update("INSERT INTO ai_model_tier_price(module_key, vip_level, tokens_per_call, created_time, updated_time) " +
                        "VALUES('model-config-general', 1, ?, NOW(), NOW())", initialTokens);
                jdbcTemplate.update("INSERT INTO ai_model_tier_price(module_key, vip_level, tokens_per_call, created_time, updated_time) " +
                        "VALUES('model-config-general', 2, ?, NOW(), NOW())", initialTokens);
            }
        } catch (Exception e) {
            log.warn("迁移 ai_model_tier_price 默认数据失败（可忽略，将使用代码层默认值 3）: {}", e.getMessage());
        }

        createTable("""
                CREATE TABLE IF NOT EXISTS ai_scene_plan_benefit (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NULL,
                    scene_key VARCHAR(120) NOT NULL,
                    plan_code VARCHAR(80) NOT NULL,
                    enabled TINYINT DEFAULT 1,
                    free_quota_daily INT DEFAULT 0,
                    free_quota_monthly INT DEFAULT 0,
                    discount_rate DECIMAL(10,4) DEFAULT 1.0000,
                    override_charge_mode VARCHAR(60) NULL,
                    override_tokens_per_call BIGINT DEFAULT 0,
                    override_tokens_per_item BIGINT DEFAULT 0,
                    override_tokens_per_image BIGINT DEFAULT 0,
                    override_tokens_per_reply BIGINT DEFAULT 0,
                    override_base_tokens BIGINT DEFAULT 0,
                    override_step_size INT DEFAULT 0,
                    override_step_tokens BIGINT DEFAULT 0,
                    daily_cap_count INT DEFAULT 0,
                    daily_cap_tokens BIGINT DEFAULT 0,
                    remark VARCHAR(500),
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_ai_scene_plan_benefit(tenant_id, scene_key, plan_code, deleted),
                    INDEX idx_ai_scene_plan_scene(scene_key, enabled, deleted),
                    INDEX idx_ai_scene_plan_code(plan_code, enabled, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "ai_scene_plan_benefit");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_message (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    account_id BIGINT,
                    conversation_id BIGINT,
                    session_id VARCHAR(200),
                    from_user_id VARCHAR(200),
                    to_user_id VARCHAR(200),
                    content TEXT,
                    message_type VARCHAR(50) DEFAULT 'text',
                    direction VARCHAR(20) DEFAULT 'received',
                    is_auto_reply SMALLINT DEFAULT 0,
                    msg_time DATETIME NULL,
                    ext_message_id VARCHAR(200),
                    deleted SMALLINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_msg_conv(conversation_id),
                    INDEX idx_msg_tenant(tenant_id, account_id, deleted),
                    INDEX idx_msg_ext(tenant_id, account_id, ext_message_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_message");

        createTable("""
                CREATE TABLE IF NOT EXISTS opportunity_rewrite_draft (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT,
                    goods_id BIGINT,
                    external_goods_id VARCHAR(120),
                    source_title VARCHAR(260),
                    style VARCHAR(40) DEFAULT 'init',
                    title VARCHAR(260),
                    description TEXT,
                    tags_json JSON,
                    safety_json JSON,
                    provider_name VARCHAR(120),
                    model_name VARCHAR(200),
                    request_id VARCHAR(120),
                    source_json JSON,
                    rewrite_json JSON,
                    status VARCHAR(30) DEFAULT 'draft',
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_opp_draft_tenant_time(tenant_id, created_time),
                    INDEX idx_opp_draft_goods(goods_id),
                    INDEX idx_opp_draft_ext(external_goods_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "opportunity_rewrite_draft");

        createTable("""
                CREATE TABLE IF NOT EXISTS opportunity_image_history (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    request_id VARCHAR(64) NOT NULL,
                    model VARCHAR(128) DEFAULT '',
                    prompt TEXT,
                    image_size VARCHAR(20) DEFAULT '1024x1024',
                    image_count INT DEFAULT 0,
                    result_images TEXT,
                    method_used VARCHAR(32) DEFAULT '',
                    status VARCHAR(16) DEFAULT 'success',
                    error_message TEXT,
                    raw_response TEXT,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_oih_tenant_user(tenant_id, user_id, deleted),
                    INDEX idx_oih_request_id(request_id),
                    INDEX idx_oih_created_time(created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "opportunity_image_history");

        createTable("""
                CREATE TABLE IF NOT EXISTS operation_log (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT,
                    user_id BIGINT,
                    operation_type VARCHAR(120),
                    operation_desc TEXT,
                    target_type VARCHAR(120),
                    target_id BIGINT,
                    ip_address VARCHAR(80),
                    result TINYINT DEFAULT 1,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_oplog_tenant_time(tenant_id, created_time),
                    INDEX idx_oplog_type(operation_type),
                    INDEX idx_oplog_target(target_type, target_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "operation_log");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_goods_sync_task (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    sync_id VARCHAR(80) NOT NULL UNIQUE,
                    tenant_id BIGINT NOT NULL,
                    account_id BIGINT NOT NULL,
                    status VARCHAR(30) NOT NULL DEFAULT 'queued',
                    progress INT DEFAULT 0,
                    total_count INT DEFAULT 0,
                    new_count INT DEFAULT 0,
                    updated_count INT DEFAULT 0,
                    skipped_count INT DEFAULT 0,
                    off_shelf_count INT DEFAULT 0,
                    detail_synced_count INT DEFAULT 0,
                    duration_seconds DOUBLE DEFAULT 0,
                    error_message TEXT,
                    started_time DATETIME,
                    finished_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_sync_tenant_account(tenant_id, account_id, status),
                    INDEX idx_sync_created(created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_goods_sync_task");

        createTable("""
                CREATE TABLE IF NOT EXISTS user_business_setting (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    setting_key VARCHAR(64) NOT NULL,
                    config_json JSON NOT NULL,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    UNIQUE KEY uk_ubs_tenant_user_key(tenant_id, user_id, setting_key),
                    INDEX idx_ubs_user(user_id),
                    INDEX idx_ubs_key(setting_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "user_business_setting");
    }

    private void ensureOpenSourceBridgeTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(120),
                    category VARCHAR(40) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    contact VARCHAR(200),
                    site_source VARCHAR(40) DEFAULT 'commercial',
                    site_name VARCHAR(120),
                    status VARCHAR(40) DEFAULT 'open',
                    priority VARCHAR(20) DEFAULT 'normal',
                    replier_user_id BIGINT,
                    replier_username VARCHAR(120),
                    replied_time DATETIME,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_uf_tenant_time(tenant_id, created_time),
                    INDEX idx_uf_status(status),
                    INDEX idx_uf_user(user_id),
                    INDEX idx_uf_site_source(site_source)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "user_feedback");

        createTable("""
                CREATE TABLE IF NOT EXISTS user_feedback_reply (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    feedback_id BIGINT NOT NULL,
                    tenant_id BIGINT NOT NULL,
                    replier_user_id BIGINT NOT NULL,
                    replier_username VARCHAR(120),
                    replier_role VARCHAR(20),
                    content TEXT NOT NULL,
                    created_time DATETIME,
                    INDEX idx_fr_feedback(feedback_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "user_feedback_reply");

        createTable("""
                CREATE TABLE IF NOT EXISTS open_source_ad_application (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    site_code VARCHAR(40) NOT NULL DEFAULT 'open-source',
                    site_name VARCHAR(120),
                    application_no VARCHAR(40),
                    position_type VARCHAR(40) NOT NULL,
                    position_label VARCHAR(120),
                    plan_code VARCHAR(80),
                    plan_title VARCHAR(160),
                    company_name VARCHAR(200) NOT NULL,
                    contact_name VARCHAR(80) NOT NULL,
                    contact_phone VARCHAR(80),
                    contact_wechat VARCHAR(80),
                    contact_value VARCHAR(200),
                    title VARCHAR(200) NOT NULL,
                    landing_url VARCHAR(500),
                    creative_image_url VARCHAR(500),
                    budget VARCHAR(80),
                    start_date VARCHAR(40),
                    duration_days VARCHAR(40),
                    remark TEXT,
                    status VARCHAR(40) NOT NULL DEFAULT 'pending_payment',
                    status_message VARCHAR(255),
                    payment_order_no VARCHAR(80),
                    published_record_id BIGINT,
                    published_record_type VARCHAR(40),
                    reviewer_user_id BIGINT,
                    reviewer_username VARCHAR(120),
                    reviewed_time DATETIME,
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT DEFAULT 0,
                    INDEX idx_osaa_tenant_site(tenant_id, site_code, status),
                    INDEX idx_osaa_site_created(tenant_id, site_code, created_time),
                    INDEX idx_osaa_status(status),
                    INDEX idx_osaa_position(position_type),
                    INDEX idx_osaa_payment_order(payment_order_no),
                    INDEX idx_osaa_application_no(application_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "open_source_ad_application");
    }

    private void ensureMallTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS mall_product (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '租户ID(0=全局共享)',
                    product_type VARCHAR(10) NOT NULL DEFAULT 'text' COMMENT '商品类型: text=文本商品, card=卡密商品',
                    title VARCHAR(200) NOT NULL COMMENT '商品标题',
                    subtitle VARCHAR(200) NOT NULL DEFAULT '' COMMENT '副标题(卡密商品)',
                    content TEXT COMMENT '商品正文/描述',
                    copy TEXT COMMENT '商品文案(供AI改写使用)',
                    price_cent BIGINT NOT NULL DEFAULT 0 COMMENT '价格(分)',
                    delivery_content TEXT COMMENT '发货内容(文本商品)',
                    cover_url VARCHAR(500) NOT NULL DEFAULT '' COMMENT '封面图URL',
                    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=下架, 1=上架',
                    category VARCHAR(50) NOT NULL DEFAULT '' COMMENT 'AI自动分类',
                    ai_category_confidence DECIMAL(5,2) NOT NULL DEFAULT 0 COMMENT 'AI分类置信度',
                    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
                    bought_count INT NOT NULL DEFAULT 0 COMMENT '已购买人数',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '软删除',
                    PRIMARY KEY (id),
                    INDEX idx_mall_product_type (product_type, status, deleted),
                    INDEX idx_mall_product_category (category, status, deleted),
                    INDEX idx_mall_product_tenant (tenant_id, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "mall_product");

        createTable("""
                CREATE TABLE IF NOT EXISTS mall_card_key (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    product_id BIGINT NOT NULL COMMENT '商品ID',
                    card_content TEXT NOT NULL COMMENT '卡密内容',
                    status VARCHAR(15) NOT NULL DEFAULT 'available' COMMENT '状态: available=可用, sold=已售, disabled=已禁用',
                    order_no VARCHAR(64) NOT NULL DEFAULT '' COMMENT '售出订单号',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    sold_time DATETIME NULL COMMENT '售出时间',
                    PRIMARY KEY (id),
                    INDEX idx_card_key_product (product_id, status),
                    INDEX idx_card_key_order (order_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "mall_card_key");

        createTable("""
                CREATE TABLE IF NOT EXISTS mall_faq (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '租户ID',
                    question VARCHAR(500) NOT NULL COMMENT '问题',
                    answer TEXT NOT NULL COMMENT '答案',
                    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
                    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=禁用, 1=启用',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '软删除',
                    PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "mall_faq");

        // API 滑块求解对接凭证表（V1.33，运行时自动建表以保证本地与线上首次启用即可用）
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_api_credential (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL UNIQUE COMMENT '租户ID（一租户一密钥）',
                    api_key_hash VARCHAR(64) NOT NULL UNIQUE COMMENT 'sha256(apiKey)',
                    api_key_prefix VARCHAR(8) NOT NULL COMMENT 'apiKey 前 8 位明文，用于展示识别',
                    api_key_encrypted VARCHAR(512) NULL COMMENT 'API 密钥 AES-GCM 密文',
                    enabled TINYINT NOT NULL DEFAULT 1 COMMENT '1启用 0禁用',
                    last_used_at DATETIME NULL COMMENT '最近调用时间',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_api_credential_hash (api_key_hash)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='API 对接凭证'
                """, "xianyu_api_credential");

        // API 对接滑块求解记录表（V1.17 automation 侧同名表，core-api 侧查询/统计依赖）
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_api_credential_reset_operation (
                    operation_key VARCHAR(128) NOT NULL PRIMARY KEY,
                    status VARCHAR(16) NOT NULL,
                    completed_time DATETIME NULL,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='API 密钥全量重置操作门禁'
                """, "xianyu_api_credential_reset_operation");

        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_api_captcha_solve_record (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    tenant_id BIGINT NOT NULL COMMENT '调用方租户',
                    api_key_prefix VARCHAR(8) NOT NULL COMMENT '调用方密钥前 8 位',
                    client_ip VARCHAR(45) NULL COMMENT '调用方 IP（IPv4/IPv6）',
                    request_id VARCHAR(32) NOT NULL UNIQUE COMMENT '请求唯一 ID（幂等用，req_ 开头）',
                    event_desc VARCHAR(255) NULL COMMENT '事件描述',
                    trigger_scene VARCHAR(64) NOT NULL DEFAULT 'api' COMMENT '触发场景，固定 api',
                    result VARCHAR(32) NULL COMMENT '处理结果：slider_success/slider_fail',
                    status VARCHAR(32) NOT NULL DEFAULT 'queued' COMMENT 'queued/retrying/success/fail/timeout/precheck_rejected/stale_terminated',
                    engine VARCHAR(64) NOT NULL DEFAULT 'Playwright',
                    retry_count INT NOT NULL DEFAULT 0,
                    error_message TEXT NULL COMMENT '错误详情（cookie 已脱敏）',
                    priority INT NOT NULL DEFAULT 0,
                    failure_reason VARCHAR(64) NOT NULL DEFAULT '' COMMENT '失败原因分类',
                    queued_at DATETIME NULL,
                    started_at DATETIME NULL,
                    finished_at DATETIME NULL,
                    open_reason VARCHAR(255) NULL,
                    solve_reason VARCHAR(255) NULL,
                    token_charged INT NOT NULL DEFAULT 0 COMMENT '实际扣费 Token 数（0=未扣）',
                    token_charge_failed TINYINT NOT NULL DEFAULT 0 COMMENT '1=成功但扣费失败（极端竞态），需后台对账',
                    duration_ms INT NULL COMMENT '求解耗时毫秒',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted TINYINT NOT NULL DEFAULT 0,
                    INDEX idx_acsr_tenant_status (tenant_id, status, deleted),
                    INDEX idx_acsr_tenant_created (tenant_id, created_at),
                    INDEX idx_acsr_request_id (request_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='API 对接滑块求解记录'
                """, "xianyu_api_captcha_solve_record");

        // API 滑块求解默认价格配置：module_key='api-slider-solve'，0.05 元/次，兑换比例 100 → 5 Token/次
        executeQuietly("INSERT INTO ai_model_price_config " +
                "(tenant_id, module_key, provider_name, model_name, model_type, billing_mode, " +
                " input_price_per_1k, output_price_per_1k, cached_input_price_per_1k, " +
                " per_call_price, token_exchange_rate, min_charge_token, billing_unit, " +
                " enabled, created_time, updated_time, deleted) " +
                "SELECT NULL, 'api-slider-solve', 'default', 'default', 'chat', 'per_call', " +
                " 0, 0, 0, 0.05, 100, 1, '1K', 1, NOW(), NOW(), 0 " +
                "WHERE NOT EXISTS (SELECT 1 FROM ai_model_price_config WHERE module_key = 'api-slider-solve' AND tenant_id IS NULL AND deleted = 0)");
    }

    /**
     * AI 客服（小梦）相关表：会话、消息、扣费配置、知识库分类/条目、每日统计快照。
     * 对应迁移 V1.39__add_ai_cs_tables.sql，运行时幂等建表并初始化默认配置与 12 个预设知识库分类。
     */
    private void ensureAiCsTables() {
        // 1. AI 客服会话表
        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_session (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    session_token VARCHAR(64) NOT NULL UNIQUE COMMENT '会话标识（前端持有）',
                    user_id BIGINT NOT NULL COMMENT '所属用户',
                    tenant_id BIGINT NOT NULL COMMENT '租户隔离',
                    status TINYINT NOT NULL DEFAULT 1 COMMENT '1=活跃 0=已关闭',
                    message_count INT NOT NULL DEFAULT 0 COMMENT '当前会话消息计数',
                    casual_count INT NOT NULL DEFAULT 0 COMMENT '连续闲聊计数',
                    casual_reminded TINYINT NOT NULL DEFAULT 0 COMMENT '本会话是否已提醒过闲聊',
                    compressed_summary TEXT NULL COMMENT '历史压缩摘要',
                    last_active_time DATETIME NULL,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_cs_session_user(user_id, status, last_active_time),
                    INDEX idx_cs_session_tenant(tenant_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服会话'
                """, "ai_cs_session");
        // 兼容旧库：若 ai_cs_session 已存在但缺少 archived 字段，则补列
        // archived=1 表示已归档（前台历史会话列表不再展示，但后台审计仍可查询）
        // 用于 enforceSessionRetentionLimit：每用户仅保留最近 30 条未归档会话
        addColumnIfMissing("ai_cs_session", "archived",
                "TINYINT NOT NULL DEFAULT 0 COMMENT '是否已归档：0=未归档（前台可见）1=已归档（仅后台可见），用于保留每用户最近30条会话'");

        // 2. AI 客服消息表
        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_message (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    session_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    tenant_id BIGINT NOT NULL,
                    role VARCHAR(16) NOT NULL COMMENT 'user / assistant / system',
                    content MEDIUMTEXT NOT NULL,
                    tokens_charged INT NOT NULL DEFAULT 0 COMMENT '本条消息扣费 Token（assistant 才扣费，0 表示未扣费）',
                    is_casual TINYINT NOT NULL DEFAULT 0 COMMENT '是否被判定为闲聊（0/1）',
                    tool_calls TEXT NULL COMMENT 'AI 触发的工具调用 JSON',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_cs_msg_session(session_id, id),
                    INDEX idx_cs_msg_user(user_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服消息'
                """, "ai_cs_message");

        // 3. AI 客服计费配置表（按租户隔离，tenant_id=NULL 表示全局默认）
        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_billing_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NULL COMMENT '租户隔离；NULL 表示全局默认',
                    per_message_tokens INT NOT NULL DEFAULT 3 COMMENT '每条成功回复扣费 Token 数',
                    max_context_messages INT NOT NULL DEFAULT 50 COMMENT '单会话上下文上限',
                    casual_threshold INT NOT NULL DEFAULT 5 COMMENT '连续闲聊提醒阈值',
                    casual_reminder_text TEXT NULL COMMENT '闲聊提醒文案',
                    daily_free_quota INT NOT NULL DEFAULT 10 COMMENT '用户每日免费额度（条数），超出后按 per_message_tokens 扣费',
                    enabled TINYINT NOT NULL DEFAULT 1 COMMENT '客服总开关',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_cs_billing_tenant(tenant_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服计费/行为配置'
                """, "ai_cs_billing_config");
        // 兼容旧库：若 ai_cs_billing_config 已存在但缺少 daily_free_quota 字段，则补列
        addColumnIfMissing("ai_cs_billing_config", "daily_free_quota",
                "INT NOT NULL DEFAULT 10 COMMENT '用户每日免费额度（条数），超出后按 per_message_tokens 扣费'");

        // 4. AI 客服知识库表（单表设计，category 字段标识分类）
        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_knowledge (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NULL COMMENT '租户隔离；NULL 表示全局共享',
                    category VARCHAR(64) NOT NULL COMMENT '分类 key（如 system_usage / xianyu_account / auto_reply）',
                    title VARCHAR(255) NOT NULL,
                    content MEDIUMTEXT NOT NULL,
                    keywords VARCHAR(512) NULL COMMENT '检索关键词，逗号分隔',
                    priority INT NOT NULL DEFAULT 50 COMMENT '优先级，数字越大越优先',
                    enabled TINYINT NOT NULL DEFAULT 1,
                    sort_order INT NOT NULL DEFAULT 0,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_cs_kb_category(category, enabled, sort_order),
                    INDEX idx_cs_kb_tenant(tenant_id, category)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服知识库'
                """, "ai_cs_knowledge");

        // 5. AI 客服每日统计表
        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_daily_stat (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    stat_date DATE NOT NULL,
                    user_id BIGINT NOT NULL,
                    tenant_id BIGINT NOT NULL,
                    session_count INT NOT NULL DEFAULT 0,
                    user_message_count INT NOT NULL DEFAULT 0,
                    assistant_message_count INT NOT NULL DEFAULT 0,
                    tokens_charged INT NOT NULL DEFAULT 0,
                    casual_count INT NOT NULL DEFAULT 0,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_cs_daily(stat_date, user_id),
                    INDEX idx_cs_daily_tenant(tenant_id, stat_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服每日统计'
                """, "ai_cs_daily_stat");

        // 6. AI 客服工具调用日志表
        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_tool_call (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    session_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    tenant_id BIGINT NOT NULL,
                    tool_name VARCHAR(64) NOT NULL,
                    arguments TEXT NULL COMMENT '调用参数 JSON',
                    status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending / confirmed / executed / rejected / failed',
                    result TEXT NULL COMMENT '执行结果 JSON',
                    requires_confirm TINYINT NOT NULL DEFAULT 1 COMMENT '是否需要用户确认',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_cs_tool_session(session_id, status),
                    INDEX idx_cs_tool_user(user_id, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服工具调用日志'
                """, "ai_cs_tool_call");

        // 7. 预置 12 个知识库分类的种子条目（每个分类一条概览）
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'system_usage', '系统使用总览', '闲鱼助手是面向闲鱼卖家的全功能运营工具，涵盖账号管理、商品发布、自动回复、自动发货、工作流、定时任务、AI 客服等。用户登录后可在左侧导航栏切换各功能模块。', '系统,使用,总览,功能,模块', 100, 1, 1, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='system_usage' AND title='系统使用总览')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'xianyu_account', '闲鱼账号管理', '在【账号管理】页面可添加闲鱼账号。添加方式有三种：A.扫码登录（推荐）B.Cookie 登录 C.手机号登录。账号添加后会自动同步商品、订单、消息。Cookie 失效时需重新登录。', '闲鱼,账号,添加,扫码,cookie,登录', 100, 1, 2, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='xianyu_account' AND title='闲鱼账号管理')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'product_publish', '商品发布与鱼小铺多规格', '在【发布商品】页面可发布普通商品或鱼小铺多规格商品。鱼小铺账号支持多规格（颜色/尺寸/款式等）。商品发布前必须先生成 AI 封面图。系统会自动同步闲鱼商品到本地。', '商品,发布,鱼小铺,多规格,封面,同步', 100, 1, 3, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='product_publish' AND title='商品发布与鱼小铺多规格')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'auto_reply', '自动回复配置', '在【自动回复】页面可创建关键词/正则匹配规则。支持商品级作用域、工作时段设置、转人工。AI 自动回复使用通用模型，每条成功回复扣 3 Token。', '自动回复,关键词,正则,作用域,工作时段,转人工', 100, 1, 4, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='auto_reply' AND title='自动回复配置')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'auto_delivery', '自动发货配置', '在【自动发货】页面可配置发货规则。支持 6 种发货模板：文本、卡密、链接、附件、组合、声明。订单支付后自动触发发货。发货记录可在【发货记录】页面查看。', '自动发货,发货,模板,卡密,链接,声明', 100, 1, 5, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='auto_delivery' AND title='自动发货配置')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'card_key', '卡密管理', '在【卡密管理】页面可创建卡密组、批量导入卡密。卡密组可绑定到商品的发货规则，订单触发时自动取出一张卡密发送给买家。', '卡密,卡密组,导入,绑定,发货', 100, 1, 6, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='card_key' AND title='卡密管理')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'workflow', '工作流设计', '在【工作流】页面可设计自动化流程。支持多种节点类型：触发器、条件、动作、延迟。工作流比自动回复更强大，可串联多步骤。工作流与自动回复的区别：自动回复是单条消息响应，工作流是多步骤流程。', '工作流,节点,触发器,条件,动作,流程', 100, 1, 7, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='workflow' AND title='工作流设计')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'scheduled_task', '定时任务配置', '在【定时任务】页面可创建定时任务。支持 cron 表达式、固定间隔。常见任务：自动重发已售完商品、自动同步商品数据、自动清理过期记录。', '定时任务,cron,间隔,自动重发,同步', 100, 1, 8, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='scheduled_task' AND title='定时任务配置')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'ai_customer_service', 'AI 客服配置', 'AI 客服小梦对接后台通用模型。每条成功回复扣 3 Token（按次计费）。上下文默认 50 条，超出可新建会话或压缩上下文（不扣费）。连续闲聊 5 条后礼貌提醒一次。', 'ai客服,小梦,通用模型,token,上下文,闲聊', 100, 1, 9, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='ai_customer_service' AND title='AI 客服配置')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'membership', '会员权益说明', '会员分三档：普通（免费）/ VIP / SVP。普通用户有基础功能限制；VIP 解锁全部功能、优先求解权；SVP 为最高等级，享最高优先级与专属服务。Token 充值后可用于 AI 功能调用。升级路径：在个人中心选择套餐升级。具体权益差异请以系统实际展示为准。', '会员,vip,svp,普通,token,充值,升级,权益', 100, 1, 10, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='membership' AND title='会员权益说明')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'troubleshoot', '故障排查指南', '常见故障：1.Cookie 失效→重新登录账号 2.WS 掉线→检查网络或重启服务 3.滑块求解失败→切换求解方式或手动提取 Cookie 4.多账号同时掉线→检查 IP 是否被风控 5.消息不同步→检查 WS 连接状态。', '故障,排查,cookie,ws,滑块,掉线,风控', 100, 1, 11, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='troubleshoot' AND title='故障排查指南')");
        executeQuietly("INSERT INTO ai_cs_knowledge(tenant_id, category, title, content, keywords, priority, enabled, sort_order, created_time, updated_time) "
                + "SELECT NULL, 'faq', '常见问题', 'Q:如何添加闲鱼账号？A:在账号管理页面点击添加，选择扫码/Cookie/手机号登录。Q:Token 怎么充值？A:点击右上角余额或充值按钮。Q:商品为什么不同步？A:检查账号 Cookie 是否失效。Q:自动回复不生效？A:检查规则启用状态和工作时段设置。', '常见问题,faq,添加账号,充值,同步,自动回复', 100, 1, 12, NOW(), NOW() "
                + "WHERE NOT EXISTS (SELECT 1 FROM ai_cs_knowledge WHERE tenant_id IS NULL AND category='faq' AND title='常见问题')");

        // 8. 加载 V1.45 迁移文件中的详细知识库条目（35 条，覆盖 12 个分类的操作步骤/参数限制/常见错误/业务规则）
        //    SQL 文件为唯一权威来源，Java 仅负责读取并执行，避免重复维护
        seedAiCsKnowledgeBaseFromMigrationV1_45();

        // 9. 加载 V1.46 深度扩展知识库条目（43 条，覆盖 17 个分类的深度操作步骤/API 清单/字段限制/故障排查）
        //    针对 V1.45 的深度补充：路由系统、移动端、SSE、账号 API 清单、商品发布字段、订单 API 清单、
        //    工作流操作 API、定时任务字段、AI 客服工具调用、商机搜索、数据面板、在线消息、FAQ 等
        seedAiCsKnowledgeBaseFromMigrationV1_46();

        // 10. KB 学习相关 5 张表（V1.43）：与 ensureAiCsTables 区分开，这些表服务于自主学习作业
        ensureLearnedKbTables();
    }

    /**
     * 创建 AI 客服自主学习知识库相关的 5 张表（V1.43）。
     *
     * <p>SchemaCompatibilityRunner 不依赖 Flyway，需要在启动时幂等创建。
     * 表结构必须与 V1.43__add_ai_cs_learned_kb.sql 保持一致。
     */
    private void ensureLearnedKbTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_kb_category (
                    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
                    name            VARCHAR(64) NOT NULL COMMENT '分类名称（AI 自动生成）',
                    name_hash       CHAR(32) NOT NULL COMMENT '分类名 MD5，用于去重',
                    parent_id       BIGINT NULL COMMENT '父分类 ID，支持二级分类（NULL 为一级）',
                    sort_order      INT NOT NULL DEFAULT 0,
                    entry_count     INT NOT NULL DEFAULT 0 COMMENT '该分类下条目数（冗余计数）',
                    source          VARCHAR(16) NOT NULL DEFAULT 'ai' COMMENT 'ai=AI 自动生成 / manual=后台手动',
                    deleted         TINYINT NOT NULL DEFAULT 0,
                    created_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_kb_cat_name_hash (name_hash, deleted),
                    INDEX idx_kb_cat_parent (parent_id, sort_order)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服学习 KB 动态分类表'
                """, "ai_cs_kb_category");

        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_learned_kb (
                    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
                    category_id     BIGINT NULL COMMENT '关联 ai_cs_kb_category.id',
                    question        VARCHAR(1000) NOT NULL COMMENT '买家问题（已脱敏）',
                    answer          MEDIUMTEXT NOT NULL COMMENT '卖家回复（已脱敏）',
                    tags            VARCHAR(512) NULL COMMENT 'AI 标签，逗号分隔',
                    source_summary  VARCHAR(500) NULL COMMENT '一句话摘要',
                    content_hash    CHAR(32) NOT NULL COMMENT 'question+answer 的 MD5',
                    score           INT NOT NULL DEFAULT 50 COMMENT '价值评分 0-100',
                    review_status   VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected',
                    reviewed_by     BIGINT NULL,
                    reviewed_time   DATETIME NULL,
                    reject_reason   VARCHAR(255) NULL,
                    enabled         TINYINT NOT NULL DEFAULT 1,
                    vector_indexed  TINYINT NOT NULL DEFAULT 0 COMMENT '是否已写入 RAG 向量库',
                    vector_error    VARCHAR(255) NULL,
                    source_count    INT NOT NULL DEFAULT 1 COMMENT '该 Q&A 被多少会话提取出来',
                    source_conv_ids TEXT NULL COMMENT '来源会话 ID 列表（JSON 数组，最多 20 个）',
                    learn_batch_id  VARCHAR(64) NOT NULL COMMENT '学习批次 ID',
                    sensitive_filtered TINYINT NOT NULL DEFAULT 1 COMMENT '是否已完成敏感信息过滤',
                    deleted         TINYINT NOT NULL DEFAULT 0,
                    created_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_learned_kb_hash (content_hash, deleted),
                    INDEX idx_learned_kb_cat (category_id, enabled, score),
                    INDEX idx_learned_kb_status (review_status, enabled, vector_indexed),
                    INDEX idx_learned_kb_batch (learn_batch_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服学习知识库主表（跨租户共享）'
                """, "ai_cs_learned_kb");

        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_user_kb (
                    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id       BIGINT NOT NULL,
                    user_id         BIGINT NOT NULL,
                    title           VARCHAR(255) NOT NULL,
                    content         MEDIUMTEXT NOT NULL,
                    category        VARCHAR(64) NULL,
                    tags            VARCHAR(512) NULL,
                    vector_indexed  TINYINT NOT NULL DEFAULT 0,
                    vector_error    VARCHAR(255) NULL,
                    enabled         TINYINT NOT NULL DEFAULT 1,
                    deleted         TINYINT NOT NULL DEFAULT 0,
                    created_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_kb_user (tenant_id, user_id, enabled, deleted),
                    INDEX idx_user_kb_vector (vector_indexed, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户私有知识库表（仅本人可见）'
                """, "ai_cs_user_kb");

        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_user_kb_binding (
                    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id       BIGINT NOT NULL,
                    user_id         BIGINT NOT NULL,
                    kb_type         VARCHAR(16) NOT NULL COMMENT 'learned=平台学习 KB / user=用户私有 KB',
                    kb_id           BIGINT NOT NULL,
                    enabled         TINYINT NOT NULL DEFAULT 1,
                    bound_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted         TINYINT NOT NULL DEFAULT 0,
                    UNIQUE KEY uk_user_kb_binding (tenant_id, user_id, kb_type, kb_id, deleted),
                    INDEX idx_binding_user (tenant_id, user_id, enabled, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户启用的知识库绑定关系'
                """, "ai_cs_user_kb_binding");

        createTable("""
                CREATE TABLE IF NOT EXISTS ai_cs_kb_learning_log (
                    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
                    batch_id            VARCHAR(64) NOT NULL,
                    started_at          DATETIME NOT NULL,
                    finished_at         DATETIME NULL,
                    status              VARCHAR(16) NOT NULL COMMENT 'running/success/failed/partial',
                    total_conversations INT NOT NULL DEFAULT 0,
                    kept_conversations  INT NOT NULL DEFAULT 0,
                    rejected_by_ai_ratio INT NOT NULL DEFAULT 0,
                    extracted_items     INT NOT NULL DEFAULT 0,
                    deduplicated_items  INT NOT NULL DEFAULT 0,
                    llm_tokens_used     INT NOT NULL DEFAULT 0,
                    llm_cost_yuan       DECIMAL(10,4) NOT NULL DEFAULT 0,
                    error_message       TEXT NULL,
                    config_snapshot     JSON NULL,
                    deleted             TINYINT NOT NULL DEFAULT 0,
                    created_time        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_learning_log_batch (batch_id),
                    INDEX idx_learning_log_status (status, started_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 客服 KB 学习作业审计日志'
                """, "ai_cs_kb_learning_log");

        // V1.47: 客服知识库分类化改造（幂等）
        ensureLearnedKbCategoryV1_47();
    }

    /**
     * V1.47: 客服知识库分类化改造。
     *
     * <p>1. ai_cs_kb_category 扩展 code/keywords/is_system 字段
     * <p>2. ai_cs_learned_kb 扩展 conversation_turn_count 字段
     * <p>3. 预定义 15 个业务场景分类（is_system=1，不可删）
     * <p>4. 历史数据迁移：现有 LLM 自动分类归到最接近的预定义分类
     *
     * <p>幂等：可重复执行，已存在的字段/分类会跳过。
     */
    private void ensureLearnedKbCategoryV1_47() {
        // 1. ai_cs_kb_category 扩展字段
        addColumnIfMissing("ai_cs_kb_category", "code",
            "VARCHAR(32) NULL COMMENT '分类业务代码（预定义分类的唯一标识）'");
        addColumnIfMissing("ai_cs_kb_category", "keywords",
            "JSON NULL COMMENT '关键词规则数组，用于检索时分类预过滤'");
        addColumnIfMissing("ai_cs_kb_category", "is_system",
            "TINYINT NOT NULL DEFAULT 0 COMMENT '1=预定义不可删，0=可删'");

        // 2. ai_cs_learned_kb 扩展字段
        addColumnIfMissing("ai_cs_learned_kb", "conversation_turn_count",
            "INT NOT NULL DEFAULT 0 COMMENT '原始对话轮数'");

        // 3. 预定义 15 个业务场景分类（幂等插入）
        // 使用 name_hash 唯一约束保证幂等：同名分类已存在则 INSERT IGNORE 跳过
        String[][] predefinedCategories = {
            {"库存查询", "stock_query", "[\"库存\",\"有货\",\"现货\",\"还有吗\",\"没货\",\"缺货\",\"断货\",\"在不在\"]", "1"},
            {"发货跟踪", "shipping_track", "[\"发货\",\"物流\",\"快递\",\"什么时候发\",\"单号\",\"运单\",\"发出\",\"揽收\"]", "2"},
            {"退款售后", "refund_aftersale", "[\"退款\",\"退货\",\"换货\",\"质量\",\"坏了\",\"破损\",\"不想要\",\"退钱\"]", "3"},
            {"商品咨询", "product_consult", "[\"规格\",\"材质\",\"尺寸\",\"功能\",\"详情\",\"什么样\",\"多大\",\"多重\"]", "4"},
            {"价格优惠", "price_discount", "[\"便宜点\",\"优惠\",\"满减\",\"折扣\",\"券\",\"降价\",\"打折\",\"少点\"]", "5"},
            {"账号登录", "account_login", "[\"登录\",\"cookie\",\"失效\",\"掉线\",\"登不上\",\"扫码\",\"二维码\"]", "6"},
            {"卡密发货", "card_key_delivery", "[\"卡密\",\"激活码\",\"自动发货\",\"虚拟商品\",\"兑换码\"]", "7"},
            {"工作流配置", "workflow_config", "[\"工作流\",\"节点\",\"流程\",\"触发\",\"条件\"]", "8"},
            {"定时任务", "scheduled_task", "[\"定时\",\"上架\",\"定时回复\",\"计划任务\",\"每天\"]", "9"},
            {"自动回复", "auto_reply", "[\"自动回复\",\"模板\",\"AI回复\",\"智能回复\",\"话术\"]", "10"},
            {"自动发货", "auto_delivery", "[\"自动发货\",\"发货规则\",\"自动发货设置\"]", "11"},
            {"会员充值", "membership_recharge", "[\"Token\",\"充值\",\"VIP\",\"会员\",\"SVP\",\"余额\"]", "12"},
            {"系统使用", "system_usage", "[\"怎么用\",\"功能\",\"操作\",\"使用\",\"教程\",\"怎么操作\"]", "13"},
            {"故障排查", "troubleshoot", "[\"报错\",\"错误\",\"不能用\",\"失败\",\"异常\",\"bug\",\"崩溃\"]", "14"},
            {"其他", "other", "[\"其他\",\"其它\",\"杂项\"]", "99"}
        };

        for (String[] cat : predefinedCategories) {
            String name = cat[0];
            String code = cat[1];
            String keywords = cat[2];
            int sortOrder = Integer.parseInt(cat[3]);
            String nameHash = md5Hash(name);
            try {
                // 幂等：name_hash 唯一约束保证同名分类只插入一次
                // 若已存在（如 LLM 之前生成过同名分类），则补充 code/keywords/is_system 字段
                int inserted = jdbcTemplate.update(
                    "INSERT IGNORE INTO ai_cs_kb_category (name, name_hash, code, keywords, is_system, " +
                    "sort_order, source, deleted, created_time, updated_time) " +
                    "VALUES (?, ?, ?, ?, 1, ?, 'manual', 0, NOW(), NOW())",
                    name, nameHash, code, keywords, sortOrder
                );
                if (inserted == 0) {
                    // 已存在同名分类，补充 code/keywords/is_system 字段（若为空）
                    jdbcTemplate.update(
                        "UPDATE ai_cs_kb_category SET code=COALESCE(code, ?), " +
                        "keywords=COALESCE(keywords, ?), is_system=1, sort_order=? " +
                        "WHERE name_hash=? AND deleted=0 AND (code IS NULL OR code=?)",
                        code, keywords, sortOrder, nameHash, code
                    );
                }
            } catch (Exception e) {
                recordFailure("seed predefined category " + code, e);
            }
        }

        // 4. 更新 entry_count 冗余计数
        try {
            jdbcTemplate.update(
                "UPDATE ai_cs_kb_category c SET entry_count = " +
                "(SELECT COUNT(*) FROM ai_cs_learned_kb k WHERE k.category_id=c.id AND k.deleted=0) " +
                "WHERE c.deleted=0"
            );
        } catch (Exception e) {
            recordFailure("refresh ai_cs_kb_category.entry_count V1.47", e);
        }
    }

    private static String md5Hash(String s) {
        try {
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("MD5");
            byte[] bytes = md.digest(s.getBytes("UTF-8"));
            StringBuilder sb = new StringBuilder();
            for (byte b : bytes) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * 从 V1.46 迁移文件加载深度扩展知识库条目。
     *
     * <p>SQL 文件位于 classpath:db/migration/V1.46__deepen_ai_cs_knowledge_base.sql，
     * 包含 43 条 INSERT ... WHERE NOT EXISTS 语句（幂等可重入），覆盖 17 个分类：
     * system_usage、xianyu_account、product_publish、orders、auto_reply、auto_delivery、
     * card_key、delivery_source、workflow、scheduled_task、ai_customer_service、
     * opportunity、membership、data_panel、messages、troubleshoot、faq。
     *
     * <p>本方法读取文件并按分号分割后逐条执行，单条失败不影响其他语句（与 executeQuietly 行为一致）。
     *
     * <p>注：本迁移文件的所有 content 字段均不含 ASCII 分号（使用中文标点），可安全按 ; 分割。
     */
    private void seedAiCsKnowledgeBaseFromMigrationV1_46() {
        try {
            var resource = new org.springframework.core.io.ClassPathResource(
                    "db/migration/V1.46__deepen_ai_cs_knowledge_base.sql"
            );
            if (!resource.exists()) {
                log.debug("V1.46 knowledge base migration file not found on classpath, skipping");
                return;
            }
            String sql;
            try (var is = resource.getInputStream()) {
                sql = new String(is.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
            }
            if (sql == null || sql.isBlank()) {
                return;
            }
            int executed = 0;
            int skipped = 0;
            for (String stmt : sql.split(";")) {
                // 移除注释行（-- 开头）和空行
                StringBuilder clean = new StringBuilder();
                for (String line : stmt.split("\n")) {
                    String trimmedLine = line.trim();
                    if (trimmedLine.startsWith("--") || trimmedLine.isEmpty()) {
                        continue;
                    }
                    clean.append(line).append("\n");
                }
                String finalStmt = clean.toString().trim();
                if (finalStmt.isEmpty()) {
                    continue;
                }
                try {
                    jdbcTemplate.execute(finalStmt);
                    executed++;
                } catch (Exception e) {
                    // 单条失败不阻塞其他语句；常见原因：唯一约束冲突（已存在）等
                    skipped++;
                    log.debug("V1.46 knowledge seed statement skipped: {}", e.getMessage());
                }
            }
            log.info("V1.46 knowledge base seed: executed={}, skipped={}", executed, skipped);
        } catch (Exception e) {
            log.warn("V1.46 knowledge base seed failed: {}", e.getMessage());
        }
    }

    /**
     * 从 V1.45 迁移文件加载详细知识库条目。
     *
     * <p>SQL 文件位于 classpath:db/migration/V1.45__expand_ai_cs_knowledge_base.sql，
     * 包含 35 条 INSERT ... WHERE NOT EXISTS 语句（幂等可重入）。本方法读取文件并按分号分割后逐条执行，
     * 单条失败不影响其他语句（与 executeQuietly 行为一致）。
     *
     * <p>注：本迁移文件的所有 content 字段均不含 ASCII 分号（使用中文标点），可安全按 ; 分割。
     */
    private void seedAiCsKnowledgeBaseFromMigrationV1_45() {
        try {
            var resource = new org.springframework.core.io.ClassPathResource(
                    "db/migration/V1.45__expand_ai_cs_knowledge_base.sql"
            );
            if (!resource.exists()) {
                log.debug("V1.45 knowledge base migration file not found on classpath, skipping");
                return;
            }
            String sql;
            try (var is = resource.getInputStream()) {
                sql = new String(is.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
            }
            if (sql == null || sql.isBlank()) {
                return;
            }
            int executed = 0;
            int skipped = 0;
            for (String stmt : sql.split(";")) {
                // 移除注释行（-- 开头）和空行
                StringBuilder clean = new StringBuilder();
                for (String line : stmt.split("\n")) {
                    String trimmedLine = line.trim();
                    if (trimmedLine.startsWith("--") || trimmedLine.isEmpty()) {
                        continue;
                    }
                    clean.append(line).append("\n");
                }
                String finalStmt = clean.toString().trim();
                if (finalStmt.isEmpty()) {
                    continue;
                }
                try {
                    jdbcTemplate.execute(finalStmt);
                    executed++;
                } catch (Exception e) {
                    // 单条失败不阻塞其他语句；常见原因：唯一约束冲突（已存在）等
                    skipped++;
                    log.debug("V1.45 knowledge seed statement skipped: {}", e.getMessage());
                }
            }
            log.info("V1.45 knowledge base seed: executed={}, skipped={}", executed, skipped);
        } catch (Exception e) {
            log.warn("V1.45 knowledge base seed failed: {}", e.getMessage());
        }
    }

    /**
     * 评价管理表：评价记录 + 同步任务追踪 + 账号级同步状态。
     *
     * 与 automation-service/migrations/V1.23__add_rate_management_tables.sql 保持一致。
     * 评价记录以 (tenant_id, account_id, external_order_id) 唯一标识，
     * 一个订单只允许一次卖家评价（has_seller_rate 字段标识是否已评价）。
     */
    private void ensureRateTables() {
        // 1. 评价记录表
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_rate (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    tenant_id BIGINT NOT NULL COMMENT '租户ID',
                    account_id BIGINT NOT NULL COMMENT '所属闲鱼账号ID',
                    external_order_id VARCHAR(64) NOT NULL COMMENT '订单ID（字符串存储避免大整数精度丢失）',
                    external_item_id VARCHAR(64) NULL COMMENT '商品ID（字符串存储）',
                    buyer_id VARCHAR(120) NULL COMMENT '买家ID（字符串存储）',
                    buyer_nick VARCHAR(255) NULL COMMENT '买家昵称（脱敏存储）',
                    buyer_icon TEXT NULL COMMENT '买家头像URL',
                    item_title VARCHAR(500) NULL COMMENT '商品标题',
                    item_pic_url TEXT NULL COMMENT '商品图片URL',
                    item_info_lines TEXT NULL COMMENT '商品规格补充信息',
                    order_status VARCHAR(64) NULL COMMENT '订单状态',
                    seller_rate_status VARCHAR(16) NULL COMMENT '卖家评价状态码（原始字符串存储，无确认映射）',
                    in_refund VARCHAR(16) NULL COMMENT '是否在退款中（原始字符串）',
                    consign_time DATETIME NULL COMMENT '发货时间',
                    order_create_time DATETIME NULL COMMENT '订单创建时间',
                    pay_success_time DATETIME NULL COMMENT '支付成功时间',
                    finish_time DATETIME NULL COMMENT '交易完成时间',
                    logistics_company VARCHAR(128) NULL COMMENT '物流公司',
                    logistics_mail_no VARCHAR(128) NULL COMMENT '物流单号（脱敏存储）',
                    buyer_rate_content TEXT NULL COMMENT '买家评价内容（seller=false 的 feedBack）',
                    buyer_rate_level VARCHAR(16) NULL COMMENT '买家评价等级',
                    buyer_rate_time DATETIME NULL COMMENT '买家评价时间',
                    buyer_rate_images TEXT NULL COMMENT '买家评价图片列表 JSON',
                    seller_rate_content TEXT NULL COMMENT '卖家评价内容（seller=true 的 feedBack）',
                    seller_rate_level VARCHAR(16) NULL COMMENT '卖家评价等级',
                    seller_rate_time DATETIME NULL COMMENT '卖家评价时间',
                    seller_rate_images TEXT NULL COMMENT '卖家评价图片列表 JSON',
                    seller_rate_id VARCHAR(64) NULL COMMENT '卖家评价ID',
                    has_seller_rate TINYINT NOT NULL DEFAULT 0 COMMENT '是否已存在卖家评价：1=已评价, 0=未评价',
                    rate_reviewable TINYINT NOT NULL DEFAULT 0 COMMENT '当前订单是否可评价：1=可评价, 0=不可评价',
                    raw_json TEXT NULL COMMENT '原始响应记录（脱敏后）',
                    sync_status VARCHAR(32) NOT NULL DEFAULT 'synced' COMMENT '同步状态：synced=已同步, pending_refresh=待刷新',
                    last_synced_time DATETIME(6) NULL COMMENT '最后一次同步时间',
                    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '软删除',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '本项目记录创建时间',
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '本项目记录更新时间',
                    PRIMARY KEY (id),
                    UNIQUE KEY uk_rate_tenant_account_order (tenant_id, account_id, external_order_id),
                    KEY idx_rate_tenant_account (tenant_id, account_id, deleted),
                    KEY idx_rate_tenant_status (tenant_id, deleted, rate_reviewable),
                    KEY idx_rate_tenant_time (tenant_id, deleted, finish_time),
                    KEY idx_rate_sync_status (tenant_id, account_id, sync_status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='闲鱼评价记录（多账号聚合，按 account_id+external_order_id 唯一）'
                """, "xianyu_rate");

        // 2. 评价同步任务追踪表
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_rate_sync_task (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    sync_id VARCHAR(80) NOT NULL COMMENT '同步任务ID（唯一）',
                    tenant_id BIGINT NOT NULL COMMENT '租户ID',
                    account_id BIGINT NULL COMMENT '账号ID（NULL 表示全部账号聚合任务）',
                    scope VARCHAR(20) NOT NULL DEFAULT 'single' COMMENT '同步范围：single=单账号, all=全部账号',
                    status VARCHAR(30) NOT NULL DEFAULT 'queued' COMMENT '任务状态：queued/running/completed/failed',
                    progress INT NOT NULL DEFAULT 0 COMMENT '进度百分比 0-100',
                    total_count INT NOT NULL DEFAULT 0 COMMENT '本次同步的评价总数',
                    new_count INT NOT NULL DEFAULT 0 COMMENT '新增评价数',
                    updated_count INT NOT NULL DEFAULT 0 COMMENT '更新评价数',
                    failed_count INT NOT NULL DEFAULT 0 COMMENT '失败账号数（全部账号模式）',
                    succeeded_count INT NOT NULL DEFAULT 0 COMMENT '成功账号数（全部账号模式）',
                    duration_seconds FLOAT NOT NULL DEFAULT 0 COMMENT '同步耗时（秒）',
                    error_message TEXT NULL COMMENT '错误信息（脱敏）',
                    started_time DATETIME(6) NULL COMMENT '开始时间',
                    finished_time DATETIME(6) NULL COMMENT '完成时间',
                    deleted TINYINT NOT NULL DEFAULT 0,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uk_rate_sync_id (sync_id),
                    KEY idx_rate_sync_tenant (tenant_id, deleted),
                    KEY idx_rate_sync_account (tenant_id, account_id, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评价同步任务追踪'
                """, "xianyu_rate_sync_task");

        // 3. 账号级评价同步状态表
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_rate_account_state (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    tenant_id BIGINT NOT NULL COMMENT '租户ID',
                    account_id BIGINT NOT NULL COMMENT '闲鱼账号ID',
                    last_sync_time DATETIME(6) NULL COMMENT '最后一次成功同步时间',
                    last_sync_status VARCHAR(30) NULL COMMENT '最后一次同步状态：success/failed/partial',
                    last_sync_error VARCHAR(500) NULL COMMENT '最后一次同步错误信息（脱敏）',
                    last_total_count INT NULL COMMENT '最后一次同步的评价总数',
                    is_syncing TINYINT NOT NULL DEFAULT 0 COMMENT '是否正在同步（1=同步中，用于任务去重）',
                    sync_started_time DATETIME(6) NULL COMMENT '当前同步任务开始时间',
                    last_full_sync_time DATETIME(6) NULL COMMENT '最后一次完整同步时间',
                    deleted TINYINT NOT NULL DEFAULT 0,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uk_rate_state_account (tenant_id, account_id),
                    KEY idx_rate_state_syncing (tenant_id, is_syncing)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账号级评价同步状态'
                """, "xianyu_rate_account_state");
    }

    /**
     * 退款管理表：退款记录 + 同步任务追踪 + 账号级同步状态。
     *
     * 与 automation-service/migrations/V1.22__add_refund_management_tables.sql 保持一致。
     * 退款记录以 (tenant_id, account_id, external_refund_id) 唯一标识，支持多账号聚合。
     * 仅鱼小铺账号（fish_shop_user=1）允许调用退款接口；普通账号由 Python 端拒绝。
     */
    private void ensureRefundTables() {
        // 1. 退款记录表
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_refund (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    tenant_id BIGINT NOT NULL COMMENT '租户ID',
                    account_id BIGINT NOT NULL COMMENT '所属闲鱼账号ID',
                    external_refund_id VARCHAR(64) NOT NULL COMMENT '闲鱼退款ID（refundInfoVO.refundId，字符串存储避免大整数精度丢失）',
                    external_order_id VARCHAR(64) NULL COMMENT '订单ID（commonData.orderId，字符串存储）',
                    external_item_id VARCHAR(64) NULL COMMENT '商品ID（commonData.itemId，字符串存储）',
                    item_title VARCHAR(500) NULL COMMENT '商品标题（itemVO.title）',
                    item_pic_url TEXT NULL COMMENT '商品图片URL（itemVO.itemPicUrl）',
                    item_info_lines TEXT NULL COMMENT '商品规格补充信息（itemVO.itemInfoLines）',
                    buy_num VARCHAR(32) NULL COMMENT '购买件数（priceVO.buyNum，保留原始字符串）',
                    refund_fee DECIMAL(18,4) NULL COMMENT '退款金额（priceVO.refundFee，十进制存储避免浮点误差）',
                    auction_price DECIMAL(18,4) NULL COMMENT '商品成交单价（priceVO.auctionPrice）',
                    order_status VARCHAR(64) NULL COMMENT '退款大类（commonData.orderStatus）',
                    order_simple_remark VARCHAR(255) NULL COMMENT '订单退款简要状态（commonData.orderSimpleRemark）',
                    refund_status VARCHAR(64) NULL COMMENT '退款详细状态（refundInfoVO.refundStatus）',
                    refund_status_desc VARCHAR(500) NULL COMMENT '状态倒计时或补充说明（refundInfoVO.refundStatusDesc）',
                    common_refund_status VARCHAR(64) NULL COMMENT '服务端状态代码（commonData.refundStatus）',
                    refund_reason VARCHAR(500) NULL COMMENT '退款原因（refundInfoVO.reason）',
                    cs_status VARCHAR(64) NULL COMMENT '客服介入状态（refundInfoVO.csStatus）',
                    logistics_company VARCHAR(128) NULL COMMENT '物流公司（commonData.companyName）',
                    logistics_mail_no VARCHAR(128) NULL COMMENT '物流单号（commonData.mailNo，脱敏存储）',
                    consign_time DATETIME NULL COMMENT '发货时间（commonData.consignTime）',
                    refund_create_time DATETIME NULL COMMENT '退款申请时间（refundInfoVO.gmtCreate）',
                    common_create_time DATETIME NULL COMMENT '订单创建时间回退字段（commonData.createTime）',
                    buyer_nick VARCHAR(255) NULL COMMENT '买家昵称（buyerInfoVO.userNick，脱敏存储）',
                    right_buttons_json TEXT NULL COMMENT '操作按钮列表（rightVO.btnList 的 JSON）',
                    ext_total_refund_fee DECIMAL(18,4) NULL COMMENT '当前查询范围的退款总金额（data.data.ext.totalRefundFee，仅单账号有意义）',
                    raw_json TEXT NULL COMMENT '原始响应记录（脱敏后的退款记录 JSON）',
                    sync_status VARCHAR(32) NOT NULL DEFAULT 'synced' COMMENT '同步状态：synced=已同步, pending_refresh=待刷新',
                    last_synced_time DATETIME(6) NULL COMMENT '最后一次同步时间',
                    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '软删除：退款历史通常不物理删除',
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    PRIMARY KEY (id),
                    UNIQUE KEY uk_refund_tenant_account_external (tenant_id, account_id, external_refund_id),
                    KEY idx_refund_tenant_account (tenant_id, account_id, deleted),
                    KEY idx_refund_tenant_status (tenant_id, deleted, order_status),
                    KEY idx_refund_tenant_time (tenant_id, deleted, refund_create_time),
                    KEY idx_refund_sync_status (tenant_id, account_id, sync_status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='闲鱼退款记录（多账号聚合，按 account_id+external_refund_id 唯一）'
                """, "xianyu_refund");

        // 2. 退款同步任务追踪表
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_refund_sync_task (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    sync_id VARCHAR(80) NOT NULL COMMENT '同步任务ID（唯一）',
                    tenant_id BIGINT NOT NULL COMMENT '租户ID',
                    account_id BIGINT NULL COMMENT '账号ID（NULL 表示全部账号聚合任务）',
                    scope VARCHAR(20) NOT NULL DEFAULT 'single' COMMENT '同步范围：single=单账号, all=全部账号',
                    status VARCHAR(30) NOT NULL DEFAULT 'queued' COMMENT '任务状态：queued/running/completed/failed',
                    progress INT NOT NULL DEFAULT 0 COMMENT '进度百分比 0-100',
                    total_count INT NOT NULL DEFAULT 0 COMMENT '本次同步的退款总数',
                    new_count INT NOT NULL DEFAULT 0 COMMENT '新增退款数',
                    updated_count INT NOT NULL DEFAULT 0 COMMENT '更新退款数',
                    failed_count INT NOT NULL DEFAULT 0 COMMENT '失败账号数（全部账号模式）',
                    succeeded_count INT NOT NULL DEFAULT 0 COMMENT '成功账号数（全部账号模式）',
                    duration_seconds FLOAT NOT NULL DEFAULT 0 COMMENT '同步耗时（秒）',
                    error_message TEXT NULL COMMENT '错误信息（脱敏）',
                    started_time DATETIME(6) NULL COMMENT '开始时间',
                    finished_time DATETIME(6) NULL COMMENT '完成时间',
                    deleted TINYINT NOT NULL DEFAULT 0,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uk_refund_sync_id (sync_id),
                    KEY idx_refund_sync_tenant (tenant_id, deleted),
                    KEY idx_refund_sync_account (tenant_id, account_id, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='退款同步任务追踪'
                """, "xianyu_refund_sync_task");

        // 3. 账号级退款同步状态表
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_refund_account_state (
                    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
                    tenant_id BIGINT NOT NULL COMMENT '租户ID',
                    account_id BIGINT NOT NULL COMMENT '闲鱼账号ID',
                    last_sync_time DATETIME(6) NULL COMMENT '最后一次成功同步时间',
                    last_sync_status VARCHAR(30) NULL COMMENT '最后一次同步状态：success/failed/partial',
                    last_sync_error VARCHAR(500) NULL COMMENT '最后一次同步错误信息（脱敏）',
                    last_total_count INT NULL COMMENT '最后一次同步的退款总数',
                    is_syncing TINYINT NOT NULL DEFAULT 0 COMMENT '是否正在同步（1=同步中，用于任务去重）',
                    sync_started_time DATETIME(6) NULL COMMENT '当前同步任务开始时间',
                    last_full_sync_time DATETIME(6) NULL COMMENT '最后一次完整同步时间（用于区分快速刷新和完整校验）',
                    deleted TINYINT NOT NULL DEFAULT 0,
                    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uk_refund_state_account (tenant_id, account_id),
                    KEY idx_refund_state_syncing (tenant_id, is_syncing)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账号级退款同步状态'
                """, "xianyu_refund_account_state");
    }

    /**
     * 供货中心表（V1.67/V1.68）：供货商品 / 通用审核记录。
     * supply_product 存储供货商提交的文本/卡密货源，audit_record 记录通用审核流转。
     */
    private void ensureSupplyTables() {
        createTable("""
                CREATE TABLE IF NOT EXISTS supply_product (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    seller_id BIGINT NOT NULL COMMENT '供货商用户ID',
                    product_type VARCHAR(10) NOT NULL DEFAULT 'text' COMMENT 'text=文本货源, card=卡密货源',
                    title VARCHAR(200) NOT NULL,
                    subtitle VARCHAR(200) DEFAULT '',
                    content TEXT COMMENT '商品描述/正文',
                    delivery_content TEXT COMMENT '文本货源的发货内容',
                    cover_url VARCHAR(500) DEFAULT '',
                    images_json JSON COMMENT '商品图片数组',
                    category VARCHAR(50) DEFAULT '' COMMENT 'AI分类',
                    price_cent BIGINT NOT NULL DEFAULT 0 COMMENT '售价(分)',
                    stock INT NOT NULL DEFAULT -1 COMMENT '库存(-1=无限,文本货源默认-1)',
                    card_group_id BIGINT NULL COMMENT '卡密货源关联的 card_group.id',
                    audit_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/rejected/approved',
                    audit_reason VARCHAR(500) DEFAULT '' COMMENT '驳回原因',
                    audit_at DATETIME NULL,
                    auditor_id BIGINT NULL,
                    status TINYINT NOT NULL DEFAULT 0 COMMENT '0=下架,1=上架(仅 audit_status=approved 时可上架)',
                    weight INT NOT NULL DEFAULT 0 COMMENT '展示权重(越大越靠前,后台可调)',
                    bought_count INT NOT NULL DEFAULT 0 COMMENT '销量',
                    rating_avg DECIMAL(3,2) DEFAULT 5.00 COMMENT '平均评分',
                    rating_count INT DEFAULT 0,
                    sort_order INT DEFAULT 0,
                    commission_rate DECIMAL(5,4) DEFAULT 0.0500 COMMENT '单品抽佣率(默认5%),0=用全局配置',
                    created_time DATETIME,
                    updated_time DATETIME,
                    deleted TINYINT NOT NULL DEFAULT 0,
                    INDEX idx_supply_seller(seller_id, deleted, audit_status),
                    INDEX idx_supply_status(audit_status, status, deleted),
                    INDEX idx_supply_category(category, status, deleted),
                    INDEX idx_supply_card_group(card_group_id),
                    INDEX idx_supply_weight(weight, status, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供货商品表'
                """, "supply_product");

        createTable("""
                CREATE TABLE IF NOT EXISTS audit_record (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    module_key VARCHAR(40) NOT NULL COMMENT 'supply_product/other_module',
                    business_id BIGINT NOT NULL COMMENT '业务记录ID(如 supply_product.id)',
                    submitter_id BIGINT NOT NULL,
                    auditor_id BIGINT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected',
                    reason VARCHAR(500) DEFAULT '' COMMENT '驳回原因或通过备注',
                    snapshot_json JSON COMMENT '提交时数据快照',
                    submitted_at DATETIME,
                    audited_at DATETIME,
                    INDEX idx_audit_module(module_key, status),
                    INDEX idx_audit_submitter(submitter_id, status),
                    INDEX idx_audit_auditor(auditor_id, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通用审核记录'
                """, "audit_record");
    }

    /**
     * 增长合伙人系统表（V1.65）：代理等级配置 / 邀请码 / 推荐关系 / 奖励记录 / 余额 / 提现申请。
     * 同时为 sys_user 增加 balance（现金余额，分）与 referrer_id（直接推荐人）两列。
     */
    private void ensureGrowthTables() {
        // sys_user 扩展列：balance 现金余额（分） + referrer_id 直接推荐人
        addColumnIfMissing("sys_user", "balance", "BIGINT NOT NULL DEFAULT 0 COMMENT '现金余额（分），用于增长合伙人提现'");
        addColumnIfMissing("sys_user", "referrer_id", "BIGINT NULL COMMENT '直接推荐人用户ID'");

        createTable("""
                CREATE TABLE IF NOT EXISTS growth_global_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    token_reward_per_referral BIGINT NOT NULL DEFAULT 100,
                    min_withdrawal_amount BIGINT NOT NULL DEFAULT 5000,
                    first_month_only TINYINT NOT NULL DEFAULT 1,
                    withdraw_enabled TINYINT NOT NULL DEFAULT 1,
                    updated_by VARCHAR(100),
                    created_time DATETIME,
                    updated_time DATETIME
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "growth_global_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS growth_agent_tier_config (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tier_code VARCHAR(40) NOT NULL,
                    tier_name VARCHAR(80) NOT NULL,
                    sort_order INT NOT NULL DEFAULT 0,
                    min_referrals INT NOT NULL DEFAULT 0,
                    commission_rate DECIMAL(5,2) NOT NULL DEFAULT 0.00,
                    token_reward BIGINT NOT NULL DEFAULT 100,
                    icon VARCHAR(120),
                    color VARCHAR(20),
                    badge_url VARCHAR(500),
                    description VARCHAR(500),
                    enabled TINYINT NOT NULL DEFAULT 1,
                    created_time DATETIME,
                    updated_time DATETIME,
                    UNIQUE KEY uk_growth_tier_code (tier_code)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "growth_agent_tier_config");

        createTable("""
                CREATE TABLE IF NOT EXISTS growth_invite_code (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    code VARCHAR(64) NOT NULL,
                    owner_user_id BIGINT NOT NULL,
                    tenant_id BIGINT NOT NULL,
                    code_type VARCHAR(20) NOT NULL DEFAULT 'code',
                    channel VARCHAR(60),
                    usage_count INT NOT NULL DEFAULT 0,
                    expires_at DATETIME,
                    remark VARCHAR(200),
                    created_time DATETIME,
                    updated_time DATETIME,
                    UNIQUE KEY uk_growth_invite_code (code),
                    INDEX idx_growth_invite_owner (owner_user_id),
                    INDEX idx_growth_invite_tenant (tenant_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "growth_invite_code");

        createTable("""
                CREATE TABLE IF NOT EXISTS growth_referral_relation (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    inviter_id BIGINT NOT NULL,
                    invitee_id BIGINT NOT NULL,
                    invitee_tenant_id BIGINT,
                    level TINYINT NOT NULL DEFAULT 1,
                    invite_code VARCHAR(64),
                    channel VARCHAR(60),
                    first_consumed_at DATETIME,
                    first_month_end_at DATETIME,
                    created_time DATETIME,
                    UNIQUE KEY uk_growth_referral (inviter_id, invitee_id),
                    INDEX idx_growth_referral_inviter (inviter_id),
                    INDEX idx_growth_referral_invitee (invitee_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "growth_referral_relation");

        createTable("""
                CREATE TABLE IF NOT EXISTS growth_reward_record (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    inviter_id BIGINT NOT NULL,
                    invitee_id BIGINT NOT NULL,
                    invitee_tenant_id BIGINT,
                    reward_type VARCHAR(20) NOT NULL,
                    level TINYINT NOT NULL DEFAULT 1,
                    source_amount BIGINT NOT NULL DEFAULT 0,
                    source_order_no VARCHAR(80),
                    source_product VARCHAR(120),
                    commission_rate DECIMAL(5,2) DEFAULT 0.00,
                    token_amount BIGINT DEFAULT 0,
                    cash_amount BIGINT DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'settled',
                    settled_at DATETIME,
                    created_time DATETIME,
                    INDEX idx_growth_reward_inviter (inviter_id, created_time),
                    INDEX idx_growth_reward_invitee (invitee_id),
                    INDEX idx_growth_reward_order (source_order_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "growth_reward_record");

        createTable("""
                CREATE TABLE IF NOT EXISTS growth_user_balance (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    user_id BIGINT NOT NULL,
                    tenant_id BIGINT NOT NULL,
                    total_earnings BIGINT NOT NULL DEFAULT 0,
                    available_balance BIGINT NOT NULL DEFAULT 0,
                    frozen_balance BIGINT NOT NULL DEFAULT 0,
                    withdrawn_amount BIGINT NOT NULL DEFAULT 0,
                    total_token_reward BIGINT NOT NULL DEFAULT 0,
                    total_referrals INT NOT NULL DEFAULT 0,
                    valid_referrals INT NOT NULL DEFAULT 0,
                    tier_code VARCHAR(40) NOT NULL DEFAULT 'normal',
                    tier_updated_at DATETIME,
                    created_time DATETIME,
                    updated_time DATETIME,
                    UNIQUE KEY uk_growth_balance_user (user_id),
                    INDEX idx_growth_balance_tenant (tenant_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "growth_user_balance");

        createTable("""
                CREATE TABLE IF NOT EXISTS growth_withdrawal_request (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    user_id BIGINT NOT NULL,
                    tenant_id BIGINT NOT NULL,
                    amount BIGINT NOT NULL,
                    payment_method VARCHAR(20) NOT NULL,
                    payment_account VARCHAR(500) NOT NULL,
                    payment_name VARCHAR(100),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    reject_reason VARCHAR(500),
                    reviewed_by VARCHAR(100),
                    reviewed_at DATETIME,
                    paid_at DATETIME,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_growth_wd_user (user_id, status, created_time),
                    INDEX idx_growth_wd_status (status, created_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "growth_withdrawal_request");

        // 初始化全局配置单行（id=1）
        try {
            Long cfgCount = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM growth_global_config WHERE id=1", Long.class);
            if (cfgCount != null && cfgCount == 0) {
                jdbcTemplate.update("INSERT INTO growth_global_config(id, token_reward_per_referral, min_withdrawal_amount, first_month_only, withdraw_enabled, created_time, updated_time) VALUES(1,100,5000,1,1,NOW(),NOW())");
            }
        } catch (Exception e) {
            log.warn("初始化 growth_global_config 失败（可忽略）: {}", e.getMessage());
        }

        // 初始化默认四级代理配置（普通/青铜/黄金/钻石）
        try {
            Long tierCount = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM growth_agent_tier_config", Long.class);
            if (tierCount != null && tierCount == 0) {
                jdbcTemplate.update("INSERT INTO growth_agent_tier_config(tier_code, tier_name, sort_order, min_referrals, commission_rate, token_reward, icon, color, description, enabled, created_time, updated_time) VALUES('normal','普通代理',1,0,20.00,100,'users','#2378f3','默认等级，有效邀请 0 人',1,NOW(),NOW())");
                jdbcTemplate.update("INSERT INTO growth_agent_tier_config(tier_code, tier_name, sort_order, min_referrals, commission_rate, token_reward, icon, color, description, enabled, created_time, updated_time) VALUES('bronze','青铜代理',2,10,30.00,100,'shield','#1fa768','有效邀请 10 人自动升级',1,NOW(),NOW())");
                jdbcTemplate.update("INSERT INTO growth_agent_tier_config(tier_code, tier_name, sort_order, min_referrals, commission_rate, token_reward, icon, color, description, enabled, created_time, updated_time) VALUES('gold','黄金代理',3,50,40.00,100,'crown','#ef8110','有效邀请 50 人自动升级',1,NOW(),NOW())");
                jdbcTemplate.update("INSERT INTO growth_agent_tier_config(tier_code, tier_name, sort_order, min_referrals, commission_rate, token_reward, icon, color, description, enabled, created_time, updated_time) VALUES('diamond','钻石代理',4,100,50.00,100,'gem','#7150f2','有效邀请 100 人自动升级',1,NOW(),NOW())");
            }
        } catch (Exception e) {
            log.warn("初始化 growth_agent_tier_config 失败（可忽略）: {}", e.getMessage());
        }

        // 修复历史 tier_name 乱码：UTF-8 字节被当作 CP1252 解释后再以 UTF-8 存储
        // 现象：tier_name 显示为 "é’»çŸ³ä»£ç†" 等 12 字符乱码（原始中文 4 字符）
        // 检测：默认 4 级（normal/bronze/gold/diamond）且 CHAR_LENGTH(tier_name) > 6
        // 安全性：不影响管理员自定义的合法名称（如 "白银代理" 4 字符）
        try {
            int fixed = jdbcTemplate.update(
                    "UPDATE growth_agent_tier_config SET tier_name = CASE tier_code " +
                    "WHEN 'normal' THEN '普通代理' " +
                    "WHEN 'bronze' THEN '青铜代理' " +
                    "WHEN 'gold' THEN '黄金代理' " +
                    "WHEN 'diamond' THEN '钻石代理' " +
                    "ELSE tier_name END " +
                    "WHERE tier_code IN ('normal','bronze','gold','diamond') " +
                    "AND CHAR_LENGTH(tier_name) > 6");
            if (fixed > 0) {
                log.info("修复 growth_agent_tier_config.tier_name 乱码：{} 条", fixed);
            }
        } catch (Exception e) {
            log.warn("修复 tier_name 乱码失败（可忽略）: {}", e.getMessage());
        }
    }

    private void ensureCompatibilityColumns() {
        // billing_plan：V1.26 自定义介绍文本与周期类型 + V1.29 月/季/年三档价格
        addColumnIfMissing("billing_plan", "features_text", "TEXT NULL COMMENT '自定义套餐介绍文本（换行分隔多条权益）'");
        addColumnIfMissing("billing_plan", "period_type", "VARCHAR(20) NOT NULL DEFAULT 'month' COMMENT '周期类型：month=月 / quarter=季 / year=年'");
        addColumnIfMissing("billing_plan", "price_month_cent", "BIGINT DEFAULT 0 COMMENT '月度价格（分），0 表示未配置'");
        addColumnIfMissing("billing_plan", "price_quarter_cent", "BIGINT DEFAULT 0 COMMENT '季度价格（分），0 表示未配置'");
        addColumnIfMissing("billing_plan", "price_year_cent", "BIGINT DEFAULT 0 COMMENT '年度价格（分），0 表示未配置'");
        // 回填：将现有 price_cent 按 period_type 写入对应周期字段（仅回填 price>0 且目标字段仍为 0 的记录）
        executeQuietly("UPDATE billing_plan SET price_month_cent = price_cent WHERE period_type = 'month' AND price_cent > 0 AND price_month_cent = 0 AND deleted = 0");
        executeQuietly("UPDATE billing_plan SET price_quarter_cent = price_cent WHERE period_type = 'quarter' AND price_cent > 0 AND price_quarter_cent = 0 AND deleted = 0");
        executeQuietly("UPDATE billing_plan SET price_year_cent = price_cent WHERE period_type = 'year' AND price_cent > 0 AND price_year_cent = 0 AND deleted = 0");

        addColumnIfMissing("mall_product", "copy", "TEXT NULL");
        addColumnIfMissing("mall_product", "weight", "INT NOT NULL DEFAULT 0 COMMENT '展示权重(越大越靠前)'");
        addColumnIfMissing("card_group", "linked_supply_product_id", "BIGINT NULL COMMENT '关联的供货商品ID'");

        // 售整自动上架功能字段（V1.38）
        addColumnIfMissing("xianyu_goods", "auto_relist_enabled", "TINYINT NOT NULL DEFAULT 0 COMMENT '售整自动上架开关：0关 1开'");
        addColumnIfMissing("xianyu_goods", "next_relist_goods_id", "BIGINT NULL COMMENT '重发后的新商品记录ID'");
        addColumnIfMissing("xianyu_goods", "relist_source_goods_id", "BIGINT NULL COMMENT '本商品是从哪个原商品重发来的'");
        addColumnIfMissing("xianyu_goods", "last_relist_at", "DATETIME NULL COMMENT '上次重发时间'");
        addColumnIfMissing("xianyu_goods", "has_snapshot", "TINYINT NOT NULL DEFAULT 0 COMMENT '是否有完整数据快照'");
        addColumnIfMissing("xianyu_goods", "original_quantity", "INT NULL COMMENT '商品原始库存'");
        createIndexIfMissing("xianyu_goods", "idx_auto_relist_enabled",
                "CREATE INDEX idx_auto_relist_enabled ON xianyu_goods(auto_relist_enabled, status, next_relist_goods_id)");

        addColumnIfMissing("xianyu_account", "created_by_user_id", "BIGINT NULL");
        addColumnIfMissing("xianyu_account", "risk_level", "TINYINT DEFAULT 0");
        addColumnIfMissing("xianyu_account", "disabled_by_admin", "TINYINT DEFAULT 0");
        addColumnIfMissing("xianyu_account", "admin_remark", "TEXT NULL");
        addColumnIfMissing("xianyu_account", "display_name", "VARCHAR(100) NULL");
        addColumnIfMissing("xianyu_account", "ip_location", "VARCHAR(100) NULL");
        addColumnIfMissing("xianyu_account", "introduction", "TEXT NULL");
        addColumnIfMissing("xianyu_account", "followers", "INT NULL");
        addColumnIfMissing("xianyu_account", "following", "INT NULL");
        addColumnIfMissing("xianyu_account", "seller_level", "VARCHAR(50) NULL");
        addColumnIfMissing("xianyu_account", "fish_shop_score", "INT NULL");
        addColumnIfMissing("xianyu_account", "fish_shop_user", "TINYINT NULL");
        addColumnIfMissing("xianyu_account", "praise_ratio", "VARCHAR(20) NULL");
        addColumnIfMissing("xianyu_account", "review_num", "INT NULL");
        addColumnIfMissing("xianyu_account", "sold_count", "INT NULL");
        addColumnIfMissing("xianyu_account", "message_expire_time", "INT DEFAULT 3600");
        addColumnIfMissing("xianyu_account", "scheduled_redelivery", "TINYINT DEFAULT 0");
        addColumnIfMissing("xianyu_account", "auto_polish", "TINYINT DEFAULT 0");
        addColumnIfMissing("scheduled_task", "last_status", "VARCHAR(40) NULL");
        addColumnIfMissing("scheduled_task", "last_result", "TEXT NULL");
        addColumnIfMissing("scheduled_task", "last_started_time", "DATETIME(6) NULL");
        addColumnIfMissing("scheduled_task", "last_finished_time", "DATETIME(6) NULL");
        addColumnIfMissing("scheduled_task", "lease_token", "CHAR(32) NULL");
        addColumnIfMissing("scheduled_task", "lease_owner", "VARCHAR(120) NULL");
        addColumnIfMissing("scheduled_task", "lease_expires_at", "DATETIME(6) NULL");
        addColumnIfMissing("scheduled_task", "run_attempt_count", "BIGINT UNSIGNED NOT NULL DEFAULT 0");
        addColumnIfMissing("scheduled_task", "consecutive_failure_count", "INT UNSIGNED NOT NULL DEFAULT 0");
        createIndexIfMissing("scheduled_task", "idx_scheduled_task_due_claim",
                "CREATE INDEX idx_scheduled_task_due_claim ON scheduled_task(enabled, deleted, next_run_time, lease_expires_at)");
        createIndexIfMissing("scheduled_task", "idx_scheduled_task_tenant_lease",
                "CREATE INDEX idx_scheduled_task_tenant_lease ON scheduled_task(tenant_id, lease_token)");
        addColumnIfMissing("xianyu_account_auto_rate_config", "tenant_id", "BIGINT NOT NULL DEFAULT 0");
        addColumnIfMissing("xianyu_account_auto_rate_config", "user_id", "BIGINT NULL");
        addColumnIfMissing("xianyu_account_auto_rate_config", "account_id", "BIGINT NOT NULL DEFAULT 0");
        addColumnIfMissing("xianyu_account_auto_rate_config", "enabled", "TINYINT DEFAULT 0");
        addColumnIfMissing("xianyu_account_auto_rate_config", "rate_type", "VARCHAR(30) DEFAULT 'text'");
        addColumnIfMissing("xianyu_account_auto_rate_config", "text_content", "TEXT NULL");
        addColumnIfMissing("xianyu_account_auto_rate_config", "api_url", "TEXT NULL");
        // 自动评价每天执行时间（0-23，默认 9 点）
        addColumnIfMissing("xianyu_account_auto_rate_config", "schedule_hour", "INT NOT NULL DEFAULT 9");
        addColumnIfMissing("xianyu_account_auto_rate_config", "created_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_account_auto_rate_config", "updated_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_account_auto_rate_config", "deleted", "TINYINT DEFAULT 0");
        createIndexIfMissing("xianyu_account_auto_rate_config", "uk_xyaarc_tenant_account",
                "CREATE UNIQUE INDEX uk_xyaarc_tenant_account ON xianyu_account_auto_rate_config(tenant_id, account_id)");
        createIndexIfMissing("xianyu_account_auto_rate_config", "idx_xyaarc_tenant",
                "CREATE INDEX idx_xyaarc_tenant ON xianyu_account_auto_rate_config(tenant_id, deleted)");
        createIndexIfMissing("xianyu_account_auto_rate_config", "idx_xyaarc_account",
                "CREATE INDEX idx_xyaarc_account ON xianyu_account_auto_rate_config(account_id)");
        createIndexIfMissing("xianyu_account_auto_rate_config", "idx_xyaarc_enabled_hour",
                "CREATE INDEX idx_xyaarc_enabled_hour ON xianyu_account_auto_rate_config(enabled, schedule_hour, deleted)");

        // 自动补评价执行日志表（与 V1.25 迁移脚本对齐）
        createTable("""
                CREATE TABLE IF NOT EXISTS xianyu_auto_rate_log (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    tenant_id BIGINT NOT NULL,
                    account_id BIGINT NOT NULL,
                    run_time DATETIME(6) NOT NULL,
                    schedule_hour INT NULL,
                    trigger_type VARCHAR(20) NOT NULL DEFAULT 'scheduled',
                    status VARCHAR(20) NOT NULL DEFAULT 'success',
                    total_pending INT NOT NULL DEFAULT 0,
                    total_success INT NOT NULL DEFAULT 0,
                    total_failed INT NOT NULL DEFAULT 0,
                    total_skipped INT NOT NULL DEFAULT 0,
                    error_message VARCHAR(500) NULL,
                    details_json TEXT NULL,
                    duration_seconds FLOAT NOT NULL DEFAULT 0,
                    deleted TINYINT DEFAULT 0,
                    created_time DATETIME,
                    updated_time DATETIME,
                    INDEX idx_arl_tenant_account_time(tenant_id, account_id, run_time),
                    INDEX idx_arl_tenant_time(tenant_id, run_time),
                    INDEX idx_arl_status(tenant_id, status, deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """, "xianyu_auto_rate_log");
        addColumnIfMissing("open_source_ad_application", "site_name", "VARCHAR(120) NULL");
        addColumnIfMissing("open_source_ad_application", "instance_token", "VARCHAR(120) NULL");
        addColumnIfMissing("open_source_ad_application", "application_no", "VARCHAR(40) NULL");
        addColumnIfMissing("open_source_ad_application", "position_label", "VARCHAR(120) NULL");
        addColumnIfMissing("open_source_ad_application", "plan_code", "VARCHAR(80) NULL");
        addColumnIfMissing("open_source_ad_application", "plan_title", "VARCHAR(160) NULL");
        addColumnIfMissing("open_source_ad_application", "contact_value", "VARCHAR(200) NULL");
        addColumnIfMissing("open_source_ad_application", "creative_image_url", "VARCHAR(500) NULL");
        addColumnIfMissing("open_source_ad_application", "payment_order_no", "VARCHAR(80) NULL");
        addColumnIfMissing("open_source_ad_application", "published_record_id", "BIGINT NULL");
        addColumnIfMissing("open_source_ad_application", "published_record_type", "VARCHAR(40) NULL");
        addColumnIfMissing("open_source_ad_application", "reviewer_user_id", "BIGINT NULL");
        addColumnIfMissing("open_source_ad_application", "reviewer_username", "VARCHAR(120) NULL");
        addColumnIfMissing("open_source_ad_application", "reviewed_time", "DATETIME NULL");
        addColumnIfMissing("open_source_ad_application", "created_time", "DATETIME NULL");
        addColumnIfMissing("open_source_ad_application", "updated_time", "DATETIME NULL");
        addColumnIfMissing("open_source_ad_application", "deleted", "TINYINT NOT NULL DEFAULT 0");
        createIndexIfMissing("open_source_ad_application", "idx_osaa_site_created",
                "CREATE INDEX idx_osaa_site_created ON open_source_ad_application(tenant_id, site_code, created_time)");
        createIndexIfMissing("open_source_ad_application", "idx_osaa_position",
                "CREATE INDEX idx_osaa_position ON open_source_ad_application(position_type)");
        createIndexIfMissing("open_source_ad_application", "idx_osaa_payment_order",
                "CREATE INDEX idx_osaa_payment_order ON open_source_ad_application(payment_order_no)");
        createIndexIfMissing("open_source_ad_application", "idx_osaa_instance_token",
                "CREATE INDEX idx_osaa_instance_token ON open_source_ad_application(instance_token)");

        // payment_order 表补列：早期 DataInitializer 创建的旧 schema 缺少 provider_type 等字段，
        // 会导致 OpenSourceAdService.pageApplications() 的 LEFT JOIN SELECT 抛 Unknown column。
        addColumnIfMissing("payment_order", "tenant_id", "BIGINT NULL");
        addColumnIfMissing("payment_order", "order_type", "VARCHAR(30) NOT NULL DEFAULT 'ad_application'");
        addColumnIfMissing("payment_order", "target_type", "VARCHAR(50) DEFAULT 'user_account'");
        addColumnIfMissing("payment_order", "target_id", "BIGINT NULL");
        addColumnIfMissing("payment_order", "plan_id", "BIGINT NULL");
        addColumnIfMissing("payment_order", "token_plan_id", "BIGINT NULL");
        addColumnIfMissing("payment_order", "title", "VARCHAR(200) NULL");
        addColumnIfMissing("payment_order", "amount_cent", "BIGINT NOT NULL DEFAULT 0");
        addColumnIfMissing("payment_order", "token_amount", "BIGINT DEFAULT 0");
        addColumnIfMissing("payment_order", "payment_method", "VARCHAR(30) NOT NULL DEFAULT 'alipay'");
        addColumnIfMissing("payment_order", "provider_type", "VARCHAR(30) DEFAULT 'official'");
        addColumnIfMissing("payment_order", "payment_config_id", "BIGINT NULL");
        addColumnIfMissing("payment_order", "status", "TINYINT DEFAULT 0");
        addColumnIfMissing("payment_order", "client_ip", "VARCHAR(80) NULL");
        addColumnIfMissing("payment_order", "qr_content", "TEXT NULL");
        addColumnIfMissing("payment_order", "pay_url", "TEXT NULL");
        addColumnIfMissing("payment_order", "out_trade_no", "VARCHAR(120) NULL");
        addColumnIfMissing("payment_order", "paid_time", "DATETIME NULL");
        addColumnIfMissing("payment_order", "expire_time", "DATETIME NULL");
        addColumnIfMissing("payment_order", "created_time", "DATETIME NULL");
        addColumnIfMissing("payment_order", "updated_time", "DATETIME NULL");
        addColumnIfMissing("payment_order", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("payment_order", "period_type", "VARCHAR(10) NULL");
        createIndexIfMissing("payment_order", "idx_payment_order_config",
                "CREATE INDEX idx_payment_order_config ON payment_order(payment_config_id)");
        createIndexIfMissing("payment_order", "uk_payment_order_gateway_trade",
                "CREATE UNIQUE INDEX uk_payment_order_gateway_trade ON payment_order(out_trade_no)");
        addColumnIfMissing("xianyu_account_auth", "auth_type", "VARCHAR(50) DEFAULT 'cookie'");

        addColumnIfMissing("xianyu_account_membership", "tenant_id", "BIGINT NULL");
        addColumnIfMissing("xianyu_account_membership", "level", "VARCHAR(50) DEFAULT 'normal'");
        addColumnIfMissing("xianyu_account_membership", "membership_type", "VARCHAR(50) NULL");
        addColumnIfMissing("xianyu_account_membership", "is_expired", "TINYINT DEFAULT 0");
        addColumnIfMissing("xianyu_account_membership", "expire_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_account_membership", "auto_renew", "TINYINT DEFAULT 0");

        addColumnIfMissing("xianyu_account_health_snapshot", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("notification", "account_id", "BIGINT NULL");
        addColumnIfMissing("notification", "notice_type", "VARCHAR(80) NULL");
        addColumnIfMissing("notification", "level", "VARCHAR(40) NULL");
        addColumnIfMissing("notification_delivery_log", "channel_name", "VARCHAR(120) NULL");
        addColumnIfMissing("notification_delivery_log", "event_type", "VARCHAR(80) NULL");
        addColumnIfMissing("notification_delivery_log", "success", "TINYINT DEFAULT 0");
        addColumnIfMissing("notification_delivery_log", "status_code", "INT DEFAULT 0");
        addColumnIfMissing("notification_delivery_log", "cost_ms", "BIGINT DEFAULT 0");
        addColumnIfMissing("notification_delivery_log", "message", "VARCHAR(500) NULL");
        addColumnIfMissing("notification_delivery_log", "request_body", "TEXT NULL");
        addColumnIfMissing("notification_delivery_log", "response_body", "TEXT NULL");
        addColumnIfMissing("notification_delivery_log", "retry_count", "INT DEFAULT 0");
        addColumnIfMissing("user_notification_setting", "config_json", "JSON NULL");
        addColumnIfMissing("user_notification_setting", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("operation_log", "result", "TINYINT DEFAULT 1");
        addColumnIfMissing("operation_log", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("operation_log", "updated_time", "DATETIME NULL");
        addColumnIfMissing("opportunity_image_history", "tenant_id", "BIGINT NOT NULL DEFAULT 0");
        addColumnIfMissing("opportunity_image_history", "user_id", "BIGINT NOT NULL DEFAULT 0");
        addColumnIfMissing("opportunity_image_history", "request_id", "VARCHAR(64) NOT NULL DEFAULT ''");
        addColumnIfMissing("opportunity_image_history", "model", "VARCHAR(128) DEFAULT ''");
        addColumnIfMissing("opportunity_image_history", "prompt", "TEXT NULL");
        addColumnIfMissing("opportunity_image_history", "image_size", "VARCHAR(20) DEFAULT '1024x1024'");
        addColumnIfMissing("opportunity_image_history", "image_count", "INT DEFAULT 0");
        addColumnIfMissing("opportunity_image_history", "result_images", "TEXT NULL");
        addColumnIfMissing("opportunity_image_history", "method_used", "VARCHAR(32) DEFAULT ''");
        addColumnIfMissing("opportunity_image_history", "status", "VARCHAR(16) DEFAULT 'success'");
        addColumnIfMissing("opportunity_image_history", "error_message", "TEXT NULL");
        addColumnIfMissing("opportunity_image_history", "raw_response", "TEXT NULL");
        addColumnIfMissing("opportunity_image_history", "created_time", "DATETIME NULL");
        addColumnIfMissing("opportunity_image_history", "updated_time", "DATETIME NULL");
        addColumnIfMissing("opportunity_image_history", "deleted", "TINYINT DEFAULT 0");
        createIndexIfMissing("opportunity_image_history", "idx_oih_tenant_user",
                "CREATE INDEX idx_oih_tenant_user ON opportunity_image_history(tenant_id, user_id, deleted)");
        createIndexIfMissing("opportunity_image_history", "idx_oih_request_id",
                "CREATE INDEX idx_oih_request_id ON opportunity_image_history(request_id)");
        createIndexIfMissing("opportunity_image_history", "idx_oih_created_time",
                "CREATE INDEX idx_oih_created_time ON opportunity_image_history(created_time)");
        // V1.25: 生图来源相关字段（兼容旧库自动补字段）
        addColumnIfMissing("opportunity_image_history", "source", "VARCHAR(20) NOT NULL DEFAULT 'opportunity'");
        addColumnIfMissing("opportunity_image_history", "workflow_id", "BIGINT NULL");
        addColumnIfMissing("opportunity_image_history", "workflow_execution_id", "BIGINT NULL");
        addColumnIfMissing("opportunity_image_history", "workflow_node_key", "VARCHAR(100) NULL");
        createIndexIfMissing("opportunity_image_history", "idx_oih_source_tenant_created",
                "CREATE INDEX idx_oih_source_tenant_created ON opportunity_image_history(source, tenant_id, created_time DESC)");
        addColumnIfMissing("workflow_definition", "enabled", "TINYINT DEFAULT 0");
        addColumnIfMissing("workflow_definition", "published_time", "DATETIME NULL");
        // 早期 DataInitializer 创建的 workflow_edge 表缺少 updated_time 列，
        // 导致 WorkflowService.replaceNodesAndEdges 的 UPDATE/INSERT 报 Unknown column 'updated_time'，
        // 触发 GlobalExceptionHandler 兜底返回"系统繁忙"。此处补列修复。
        addColumnIfMissing("workflow_edge", "updated_time", "DATETIME NULL");
        addColumnIfMissing("workflow_node", "updated_time", "DATETIME NULL");
        // 早期 DataInitializer 创建的 workflow_execution 表缺少 input_json 列，
        // 导致 WorkflowService.insertExecution 的 INSERT 报 Unknown column 'input_json'，
        // 触发 GlobalExceptionHandler 兜底返回"系统繁忙"。此处补列修复。
        addColumnIfMissing("workflow_execution", "input_json", "JSON NULL");
        addColumnIfMissing("workflow_published_goods", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("workflow_published_goods", "created_time", "DATETIME NULL");
        addColumnIfMissing("auto_reply_rule", "match_type", "VARCHAR(50) NULL");
        addColumnIfMissing("auto_reply_rule", "match_keywords", "TEXT NULL");
        addColumnIfMissing("auto_reply_rule", "reply_content", "TEXT NULL");
        addColumnIfMissing("auto_reply_rule", "reply_mode", "VARCHAR(50) NULL");
        addColumnIfMissing("auto_reply_rule", "priority", "INT DEFAULT 0");
        addColumnIfMissing("auto_reply_rule", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("delivery_rule", "goods_id", "BIGINT NULL");
        addColumnIfMissing("delivery_rule", "delivery_type", "VARCHAR(50) NULL");
        addColumnIfMissing("delivery_rule", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("delivery_text_source", "source_type", "VARCHAR(30) DEFAULT 'text'");
        addColumnIfMissing("delivery_text_source", "delivery_mode", "VARCHAR(20) NOT NULL DEFAULT 'text'");
        addColumnIfMissing("delivery_text_source", "card_group_id", "BIGINT NULL");
        addColumnIfMissing("delivery_text_source", "title", "VARCHAR(200) NULL");
        addColumnIfMissing("delivery_text_source", "content", "TEXT NULL");
        addColumnIfMissing("delivery_text_source", "remark", "VARCHAR(500) NULL");
        addColumnIfMissing("delivery_text_source", "deleted", "TINYINT DEFAULT 0");
        // V1.66: 多条正文 + 图片发货（每条 segment 为 text 或 image 二选一，空则回退 content 单条发送）
        addColumnIfMissing("delivery_text_source", "segments", "JSON NULL COMMENT '多条正文配置（JSON 数组，每条 type=text/image 二选一，空则回退 content 单条发送）'");
        addColumnIfMissing("card_group", "description", "TEXT NULL");
        addColumnIfMissing("card_group", "card_prefix", "VARCHAR(120) NULL");
        addColumnIfMissing("card_group", "password_prefix", "VARCHAR(120) NULL");
        addColumnIfMissing("card_group", "alert_threshold", "INT DEFAULT 10");
        addColumnIfMissing("card_group", "cost_price", "DECIMAL(10,2) NULL");
        addColumnIfMissing("card_group", "suggested_price", "DECIMAL(10,2) NULL");
        addColumnIfMissing("card_group", "remain_count", "INT DEFAULT 0");
        addColumnIfMissing("card_group", "available_count", "INT DEFAULT 0");
        // V1.63: 多规格商品自动发货 - card_group 新增 sku_property_key 字段支持 SKU 专属卡密池
        addColumnIfMissing("card_group", "sku_property_key", "VARCHAR(512) NULL");
        addColumnIfMissing("card_item", "card_content", "TEXT NULL");
        addColumnIfMissing("card_item", "card_key", "TEXT NULL");
        addColumnIfMissing("card_item", "card_value", "TEXT NULL");
        addColumnIfMissing("card_item", "extra_info", "TEXT NULL");
        addColumnIfMissing("card_item", "status", "TINYINT DEFAULT 0");
        addColumnIfMissing("card_item", "is_used", "TINYINT DEFAULT 0");
        addColumnIfMissing("card_item", "used_order_id", "BIGINT NULL");
        addColumnIfMissing("card_item", "used_by_order_id", "BIGINT NULL");
        addColumnIfMissing("card_item", "used_time", "DATETIME NULL");
        addColumnIfMissing("card_item", "deleted", "TINYINT DEFAULT 0");

        addColumnIfMissing("delivery_record", "status", "TINYINT DEFAULT 0");
        addColumnIfMissing("delivery_record", "fail_reason", "TEXT NULL");
        addColumnIfMissing("delivery_record", "delivery_mode", "VARCHAR(16) NULL");
        addColumnIfMissing("delivery_record", "delivery_content", "TEXT NULL");
        addColumnIfMissing("delivery_record", "delivery_timing", "VARCHAR(32) NULL");
        addColumnIfMissing("delivery_record", "delivery_method", "VARCHAR(50) NULL");
        addColumnIfMissing("delivery_record", "delivery_fail_reason", "TEXT NULL");
        addColumnIfMissing("delivery_record", "quantity_requested", "INT DEFAULT 0");

        // mall_product 表补列（兼容早期版本）
        addColumnIfMissing("mall_product", "delivery_content", "TEXT NULL");
        addColumnIfMissing("delivery_record", "quantity_sent", "INT DEFAULT 0");
        addColumnIfMissing("delivery_record", "platform_sync_time", "DATETIME NULL");
        addColumnIfMissing("delivery_record", "completed_time", "DATETIME NULL");
        addColumnIfMissing("delivery_record", "card_item_id", "BIGINT NULL");

        addColumnIfMissing("sys_user", "token_balance", "BIGINT DEFAULT 0");
        addColumnIfMissing("sys_user", "phone_verified", "TINYINT DEFAULT 0");
        addColumnIfMissing("sys_user", "email_verified", "TINYINT DEFAULT 0");
        addColumnIfMissing("sys_user", "last_security_update_time", "DATETIME NULL");
        addColumnIfMissing("sys_user", "security_version", "BIGINT NOT NULL DEFAULT 1");
        addColumnIfMissing("sys_admin_user", "security_version", "BIGINT NOT NULL DEFAULT 1");
        addColumnIfMissing("tenant_storage_asset", "visibility", "VARCHAR(16) NOT NULL DEFAULT 'private'");
        addColumnIfMissing("tenant_storage_asset", "purpose", "VARCHAR(64) NOT NULL DEFAULT 'user-media'");
        addColumnIfMissing("tenant_storage_asset", "owner_type", "VARCHAR(32) NULL");
        addColumnIfMissing("tenant_storage_asset", "owner_id", "BIGINT NULL");
        addColumnIfMissing("tenant_storage_asset", "published_time", "DATETIME NULL");
        createIndexIfMissing("tenant_storage_asset", "idx_storage_asset_visibility_status",
                "CREATE INDEX idx_storage_asset_visibility_status ON tenant_storage_asset(visibility, status, updated_time)");
        createIndexIfMissing("tenant_storage_asset", "idx_storage_asset_owner",
                "CREATE INDEX idx_storage_asset_owner ON tenant_storage_asset(tenant_id, owner_type, owner_id, status)");
        addColumnIfMissing("sys_user", "vip_level", "INT DEFAULT 0");
        addColumnIfMissing("ai_model_price_config", "cached_input_price_per_1k", "DECIMAL(18,8) DEFAULT 0");
        addColumnIfMissing("ai_model_price_config", "billing_unit", "VARCHAR(20) DEFAULT '1K'");
        addColumnIfMissing("ai_model_price_config", "cost_per_image", "DECIMAL(18,8) DEFAULT 0");
        addColumnIfMissing("ai_model_price_config", "tokens_per_image", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_model_price_config", "cost_per_call", "DECIMAL(18,8) DEFAULT 0");
        addColumnIfMissing("ai_model_price_config", "tokens_per_call", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_model_price_config", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("ai_usage_log", "cached_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_usage_log", "image_count", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_usage_log", "spec_key", "VARCHAR(120) NULL");
        addColumnIfMissing("ai_usage_log", "cost_cent", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_usage_log", "charge_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_usage_log", "balance_before", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_usage_log", "balance_after", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_usage_log", "status", "TINYINT DEFAULT 1");
        addColumnIfMissing("ai_usage_log", "error_message", "VARCHAR(500) NULL");
        addColumnIfMissing("ai_usage_log", "raw_usage_json", "MEDIUMTEXT NULL");
        addColumnIfMissing("ai_usage_log", "updated_time", "DATETIME NULL");
        addColumnIfMissing("ai_usage_log", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "tenant_id", "BIGINT NULL");
        addColumnIfMissing("ai_scene_sell_config", "scene_name", "VARCHAR(120) NOT NULL DEFAULT ''");
        addColumnIfMissing("ai_scene_sell_config", "scene_group", "VARCHAR(60) DEFAULT 'other'");
        addColumnIfMissing("ai_scene_sell_config", "charge_mode", "VARCHAR(60) NOT NULL DEFAULT 'fixed_per_call'");
        addColumnIfMissing("ai_scene_sell_config", "price_unit", "VARCHAR(40) DEFAULT 'call'");
        addColumnIfMissing("ai_scene_sell_config", "enabled", "TINYINT DEFAULT 1");
        addColumnIfMissing("ai_scene_sell_config", "is_metered", "TINYINT DEFAULT 1");
        addColumnIfMissing("ai_scene_sell_config", "show_estimate", "TINYINT DEFAULT 1");
        addColumnIfMissing("ai_scene_sell_config", "allow_trial", "TINYINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "trial_quota", "INT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "base_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "step_size", "INT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "step_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "sell_tokens_per_call", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "sell_tokens_per_item", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "sell_tokens_per_image", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "sell_tokens_per_reply", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "sell_tokens_per_file", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "sell_tokens_per_1k_chars", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "min_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "max_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "member_discount_rate", "DECIMAL(10,4) DEFAULT 1.0000");
        addColumnIfMissing("ai_scene_sell_config", "cost_markup_rate", "DECIMAL(10,4) DEFAULT 1.0000");
        addColumnIfMissing("ai_scene_sell_config", "fallback_exchange_rate", "DECIMAL(18,8) DEFAULT 160");
        addColumnIfMissing("ai_scene_sell_config", "daily_cap_count", "INT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "daily_cap_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "monthly_cap_count", "INT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "monthly_cap_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_sell_config", "sort_order", "INT DEFAULT 100");
        addColumnIfMissing("ai_scene_sell_config", "remark", "VARCHAR(500) NULL");
        addColumnIfMissing("ai_scene_sell_config", "created_time", "DATETIME NULL");
        addColumnIfMissing("ai_scene_sell_config", "updated_time", "DATETIME NULL");
        addColumnIfMissing("ai_scene_sell_config", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "tenant_id", "BIGINT NULL");
        addColumnIfMissing("ai_scene_plan_benefit", "scene_key", "VARCHAR(120) NOT NULL DEFAULT ''");
        addColumnIfMissing("ai_scene_plan_benefit", "plan_code", "VARCHAR(80) NOT NULL DEFAULT 'normal'");
        addColumnIfMissing("ai_scene_plan_benefit", "enabled", "TINYINT DEFAULT 1");
        addColumnIfMissing("ai_scene_plan_benefit", "free_quota_daily", "INT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "free_quota_monthly", "INT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "discount_rate", "DECIMAL(10,4) DEFAULT 1.0000");
        addColumnIfMissing("ai_scene_plan_benefit", "override_charge_mode", "VARCHAR(60) NULL");
        addColumnIfMissing("ai_scene_plan_benefit", "override_tokens_per_call", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "override_tokens_per_item", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "override_tokens_per_image", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "override_tokens_per_reply", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "override_base_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "override_step_size", "INT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "override_step_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "daily_cap_count", "INT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "daily_cap_tokens", "BIGINT DEFAULT 0");
        addColumnIfMissing("ai_scene_plan_benefit", "remark", "VARCHAR(500) NULL");
        addColumnIfMissing("ai_scene_plan_benefit", "created_time", "DATETIME NULL");
        addColumnIfMissing("ai_scene_plan_benefit", "updated_time", "DATETIME NULL");
        addColumnIfMissing("ai_scene_plan_benefit", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("sys_tenant", "tenant_name", "VARCHAR(100) NULL");
        addColumnIfMissing("sys_tenant", "name", "VARCHAR(80) NULL");
        addColumnIfMissing("sys_tenant", "display_name", "VARCHAR(200) NULL");
        addColumnIfMissing("sys_tenant", "contact_name", "VARCHAR(100) NULL");
        addColumnIfMissing("sys_tenant", "contact_phone", "VARCHAR(50) NULL");
        addColumnIfMissing("sys_tenant", "contact_email", "VARCHAR(120) NULL");

        addColumnIfMissing("workflow_item_timing", "tenant_id", "BIGINT NULL");
        addColumnIfMissing("workflow_item_timing", "execution_id", "BIGINT NULL");
        addColumnIfMissing("workflow_item_timing", "workflow_id", "BIGINT NULL");
        addColumnIfMissing("workflow_item_timing", "item_index", "INT DEFAULT 0");
        addColumnIfMissing("workflow_item_timing", "source_item_id", "VARCHAR(80) NULL");
        addColumnIfMissing("workflow_item_timing", "source_title", "VARCHAR(200) NULL");
        addColumnIfMissing("workflow_item_timing", "polish_ms", "BIGINT DEFAULT 0");
        addColumnIfMissing("workflow_item_timing", "image_generate_ms", "BIGINT DEFAULT 0");
        addColumnIfMissing("workflow_item_timing", "publish_ms", "BIGINT DEFAULT 0");
        addColumnIfMissing("workflow_item_timing", "total_ms", "BIGINT DEFAULT 0");
        addColumnIfMissing("workflow_item_timing", "created_time", "DATETIME NULL");
        addColumnIfMissing("workflow_item_timing", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("workflow_timeline", "event_level", "VARCHAR(20) DEFAULT 'INFO'");
        addColumnIfMissing("workflow_timeline", "title", "VARCHAR(200) NULL");
        addColumnIfMissing("workflow_timeline", "payload_json", "JSON NULL");

        addColumnIfMissing("xianyu_conversation", "deleted", "SMALLINT DEFAULT 0");
        addColumnIfMissing("xianyu_trade_order_item", "tenant_id", "BIGINT NULL");
        addColumnIfMissing("xianyu_trade_order_item", "order_id", "BIGINT NULL");
        addColumnIfMissing("xianyu_trade_order_item", "goods_id", "BIGINT NULL");
        addColumnIfMissing("xianyu_trade_order_item", "goods_title", "VARCHAR(500) NULL");
        addColumnIfMissing("xianyu_trade_order_item", "goods_price", "DECIMAL(12,2) DEFAULT 0");
        addColumnIfMissing("xianyu_trade_order_item", "goods_count", "INT DEFAULT 1");
        addColumnIfMissing("xianyu_trade_order_item", "spec_name", "VARCHAR(120) NULL");
        addColumnIfMissing("xianyu_trade_order_item", "spec_value", "VARCHAR(255) NULL");
        addColumnIfMissing("xianyu_trade_order_item", "external_goods_id", "VARCHAR(120) NULL");
        addColumnIfMissing("xianyu_trade_order_item", "created_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_trade_order_item", "updated_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_trade_order_item", "deleted", "TINYINT DEFAULT 0");
        addColumnIfMissing("xianyu_message", "account_id", "BIGINT NULL");
        addColumnIfMissing("xianyu_message", "conversation_id", "BIGINT NULL");
        addColumnIfMissing("xianyu_message", "session_id", "VARCHAR(200) NULL");
        addColumnIfMissing("xianyu_message", "from_user_id", "VARCHAR(200) NULL");
        addColumnIfMissing("xianyu_message", "to_user_id", "VARCHAR(200) NULL");
        addColumnIfMissing("xianyu_message", "content", "TEXT NULL");
        addColumnIfMissing("xianyu_message", "message_type", "VARCHAR(50) DEFAULT 'text'");
        addColumnIfMissing("xianyu_message", "direction", "VARCHAR(20) DEFAULT 'received'");
        addColumnIfMissing("xianyu_message", "is_auto_reply", "SMALLINT DEFAULT 0");
        addColumnIfMissing("xianyu_message", "msg_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_message", "ext_message_id", "VARCHAR(200) NULL");
        addColumnIfMissing("xianyu_message", "updated_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_message", "deleted", "SMALLINT DEFAULT 0");
        addColumnIfMissing("user_feedback", "site_source", "VARCHAR(40) DEFAULT 'commercial'");
        addColumnIfMissing("user_feedback", "site_name", "VARCHAR(120) NULL");
    }

    private void backfillCompatibilityData() {
        executeQuietly("UPDATE xianyu_account SET user_id = created_by_user_id WHERE user_id IS NULL AND created_by_user_id IS NOT NULL");
        executeQuietly("UPDATE xianyu_account SET created_by_user_id = user_id WHERE created_by_user_id IS NULL AND user_id IS NOT NULL");
        executeBackfillIfColumnExists("xianyu_account_membership", "membership_level", "UPDATE xianyu_account_membership SET level = membership_level WHERE (level IS NULL OR level = '') AND membership_level IS NOT NULL");
        executeBackfillIfColumnExists("xianyu_account_membership", "membership_type", "UPDATE xianyu_account_membership SET level = membership_type WHERE (level IS NULL OR level = '') AND membership_type IS NOT NULL");
        executeQuietly("UPDATE xianyu_account_membership SET level = 'normal' WHERE level IS NULL OR level = ''");
        executeQuietly("UPDATE xianyu_account_membership SET status = '1' WHERE status IS NULL OR status = ''");
        executeQuietly("UPDATE xianyu_account_membership SET deleted = 0 WHERE deleted IS NULL");
        executeQuietly("UPDATE notification SET notification_type = COALESCE(notification_type, notice_type) WHERE notification_type IS NULL OR notification_type = ''");
        executeQuietly("UPDATE notification SET notice_type = COALESCE(notice_type, notification_type) WHERE notice_type IS NULL OR notice_type = ''");
        executeQuietly("UPDATE card_group SET remain_count = COALESCE(remain_count, available_count, 0) WHERE remain_count IS NULL OR remain_count = 0");
        executeQuietly("UPDATE card_group SET available_count = COALESCE(available_count, remain_count, 0) WHERE available_count IS NULL OR available_count = 0");
        executeBackfillIfColumnExists("card_item", "content", "UPDATE card_item SET card_content = COALESCE(card_content, content) WHERE (card_content IS NULL OR card_content = '') AND content IS NOT NULL");
        executeQuietly("UPDATE card_item SET card_content = COALESCE(NULLIF(card_content, ''), CASE WHEN card_value IS NOT NULL AND card_value <> '' THEN CONCAT(card_key, '----', card_value) ELSE card_key END) WHERE (card_content IS NULL OR card_content = '') AND card_key IS NOT NULL");
        executeQuietly("UPDATE card_item SET used_order_id = COALESCE(used_order_id, used_by_order_id) WHERE used_order_id IS NULL AND used_by_order_id IS NOT NULL");
        executeQuietly("UPDATE card_item SET status = CASE WHEN COALESCE(status, 0) = 0 AND is_used = 1 THEN 2 ELSE COALESCE(status, 0) END");
        executeQuietly("UPDATE card_item SET deleted = 0 WHERE deleted IS NULL");
        executeQuietly("UPDATE card_group g SET total_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.deleted = 0), used_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.deleted = 0 AND i.status = 2), remain_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.deleted = 0 AND i.status = 0), available_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.deleted = 0 AND i.status = 0)");
        executeQuietly("UPDATE workflow_definition SET enabled = 1 WHERE status = 'published' AND (enabled IS NULL OR enabled = 0)");
        executeQuietly("UPDATE xianyu_account_health_snapshot SET deleted = 0 WHERE deleted IS NULL");
        executeQuietly("UPDATE xianyu_conversation SET deleted = 0 WHERE deleted IS NULL");
        executeQuietly("UPDATE xianyu_message SET deleted = 0 WHERE deleted IS NULL");
        executeQuietly("UPDATE xianyu_message SET updated_time = COALESCE(updated_time, created_time, NOW()) WHERE updated_time IS NULL");
        executeQuietly("UPDATE xianyu_message SET msg_time = COALESCE(msg_time, created_time) WHERE msg_time IS NULL");
        executeQuietly("INSERT INTO payment_config(channel_type, provider_type, config_name, enabled, sandbox, notify_url, gateway_url, created_time, updated_time, deleted) SELECT 'wechat','official','init',0,0,'/open-api/payment/callback/wechat','',NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM payment_config WHERE channel_type='wechat' AND provider_type='official' AND deleted=0)");
        executeQuietly("INSERT INTO payment_config(channel_type, provider_type, config_name, enabled, sandbox, notify_url, gateway_url, created_time, updated_time, deleted) SELECT 'alipay','official','init',0,0,'/open-api/payment/callback/alipay','',NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM payment_config WHERE channel_type='alipay' AND provider_type='official' AND deleted=0)");
        executeQuietly("INSERT INTO token_recharge_plan(plan_name, token_amount, bonus_token, price_cent, status, sort_order, created_time, updated_time, deleted) SELECT '100 Token',100,0,100,1,10,NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM token_recharge_plan WHERE plan_name='100 Token' AND deleted=0)");
        executeQuietly("INSERT INTO token_recharge_plan(plan_name, token_amount, bonus_token, price_cent, status, sort_order, created_time, updated_time, deleted) SELECT '1000 Token',1000,100,1000,1,20,NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM token_recharge_plan WHERE plan_name='1000 Token' AND deleted=0)");
        executeQuietly("INSERT INTO token_recharge_plan(plan_name, token_amount, bonus_token, price_cent, status, sort_order, created_time, updated_time, deleted) SELECT '10000 Token',10000,2000,10000,1,30,NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM token_recharge_plan WHERE plan_name='10000 Token' AND deleted=0)");
        executeQuietly("INSERT INTO billing_plan(plan_name, plan_code, price_cent, duration_days, max_xianyu_accounts, max_goods_count, max_ai_reply_per_day, max_workflow_per_day, max_storage_mb, enable_auto_delivery, enable_kami, enable_ai_reply, enable_workflow, status, created_time, updated_time, deleted) SELECT 'init','normal',0,0,1,20,100,0,100,0,0,1,0,1,NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM billing_plan WHERE plan_code='normal' AND deleted=0)");
        executeQuietly("INSERT INTO billing_plan(plan_name, plan_code, price_cent, duration_days, max_xianyu_accounts, max_goods_count, max_ai_reply_per_day, max_workflow_per_day, max_storage_mb, enable_auto_delivery, enable_kami, enable_ai_reply, enable_workflow, status, created_time, updated_time, deleted) SELECT 'VIP','vip',2990,30,3,200,3000,100,1024,1,1,1,1,1,NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM billing_plan WHERE plan_code='vip' AND deleted=0)");
        executeQuietly("INSERT INTO billing_plan(plan_name, plan_code, price_cent, duration_days, max_xianyu_accounts, max_goods_count, max_ai_reply_per_day, max_workflow_per_day, max_storage_mb, enable_auto_delivery, enable_kami, enable_ai_reply, enable_workflow, status, created_time, updated_time, deleted) SELECT 'SVP','svp',6990,30,10,1000,20000,1000,10240,1,1,1,1,1,NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM billing_plan WHERE plan_code IN ('svp','svip') AND deleted=0)");
        executeQuietly("INSERT INTO ai_model_price_config(module_key, provider_name, model_name, model_type, billing_mode, input_price_per_1k, output_price_per_1k, per_call_price, spec_price_json, token_exchange_rate, min_charge_token, billing_unit, cost_per_image, tokens_per_image, cost_per_call, tokens_per_call, enabled, remark, created_time, updated_time, deleted) SELECT 'model-config-chat','default','default','chat','token',0,0,0,'',100,0,'1K',0,0,0,0,1,'schema-seed',NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM ai_model_price_config WHERE provider_name='default' AND model_name='default' AND model_type='chat' AND deleted=0)");
        executeQuietly("INSERT INTO ai_model_price_config(module_key, provider_name, model_name, model_type, billing_mode, input_price_per_1k, output_price_per_1k, per_call_price, spec_price_json, token_exchange_rate, min_charge_token, billing_unit, cost_per_image, tokens_per_image, cost_per_call, tokens_per_call, enabled, remark, created_time, updated_time, deleted) SELECT 'model-config-image','default','default','image','spec',0,0,0.05,'{\"1024x1024\":0.05,\"1024x1536\":0.08,\"1536x1024\":0.08}',100,1,'1K',0.05,0,0,0,1,'schema-seed',NOW(),NOW(),0 WHERE NOT EXISTS (SELECT 1 FROM ai_model_price_config WHERE provider_name='default' AND model_name='default' AND model_type='image' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'category_suggest', 'Category Suggest', 'classify', 'fixed_per_call', 'call', 1, 1, 1, 15, 15, 160, 20, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='category_suggest' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_category_suggest', 'Workflow Category Suggest', 'classify', 'fixed_per_call', 'call', 1, 1, 1, 15, 15, 160, 21, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='workflow_category_suggest' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'opportunity_rewrite', 'Opportunity Rewrite', 'rewrite', 'fixed_per_call', 'call', 1, 1, 1, 30, 30, 160, 30, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='opportunity_rewrite' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_rewrite', 'Workflow Rewrite', 'rewrite', 'fixed_per_call', 'call', 1, 1, 1, 30, 30, 160, 31, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='workflow_rewrite' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_extract_keywords', 'Workflow Extract Keywords', 'keyword', 'fixed_per_call', 'call', 1, 1, 1, 20, 20, 160, 40, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='workflow_extract_keywords' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_reply, min_tokens, fallback_exchange_rate, daily_cap_count, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'auto_reply', 'AI Auto Reply', 'reply', 'fixed_per_call', 'reply', 1, 1, 1, 3, 3, 160, 1000, 80, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='auto_reply' AND deleted=0)");
        // 自动回复场景无免费额度（2026-07-30 调整：移除每日免费自动回复额度，仅保留小梦客服系统额度）
        executeQuietly("UPDATE ai_scene_sell_config SET charge_mode='fixed_per_call', sell_tokens_per_reply=3, min_tokens=3 WHERE scene_key='auto_reply' AND deleted=0");
        executeQuietly("UPDATE ai_scene_plan_benefit SET free_quota_daily=0, free_quota_monthly=0, override_tokens_per_reply=3 WHERE scene_key='auto_reply' AND deleted=0");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_image, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_image', 'Workflow Image', 'image', 'fixed_per_image', 'image', 1, 1, 1, 12, 12, 160, 110, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='workflow_image' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_image, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'opportunity_image', 'Opportunity Image', 'image', 'fixed_per_image', 'image', 1, 1, 1, 12, 12, 160, 111, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='opportunity_image' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_screen', 'Workflow Screen', 'screen', 'fixed_per_call', 'call', 1, 1, 1, 20, 20, 160, 50, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='workflow_screen' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'product_filter', 'Product Filter', 'screen', 'fixed_per_call', 'item_call', 1, 1, 1, 2, 2, 160, 51, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='product_filter' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'product_polish', 'Product Polish', 'rewrite', 'fixed_per_call', 'item_call', 1, 1, 1, 3, 3, 160, 52, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='product_polish' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, cost_markup_rate, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'knowledge_base_extract', 'Knowledge Base Extract', 'knowledge', 'cost_plus_rate', 'file', 1, 1, 0, 2.2000, 50, 160, 70, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='knowledge_base_extract' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, daily_cap_count, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'delivery_source_match', 'Delivery Source Match', 'screen', 'fixed_per_call', 'call', 1, 1, 1, 20, 20, 160, 30, 120, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='delivery_source_match' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'ai_customer_service_test', 'AI Customer Service Test', 'support', 'fixed_per_call', 'call', 1, 1, 0, 20, 20, 160, 140, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='ai_customer_service_test' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_reply, daily_cap_count, remark, created_time, updated_time, deleted) SELECT NULL, 'auto_reply', 'normal', 1, 0, 1.0000, 3, 100, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='auto_reply' AND plan_code='normal' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_reply, daily_cap_count, remark, created_time, updated_time, deleted) SELECT NULL, 'auto_reply', 'vip', 1, 0, 1.0000, 3, 500, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='auto_reply' AND plan_code='vip' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_reply, daily_cap_count, remark, created_time, updated_time, deleted) SELECT NULL, 'auto_reply', 'svp', 1, 0, 1.0000, 3, 2000, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='auto_reply' AND plan_code='svp' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_image, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_image', 'vip', 1, 0, 1.0000, 10, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='workflow_image' AND plan_code='vip' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_image, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_image', 'svp', 1, 0, 1.0000, 8, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='workflow_image' AND plan_code='svp' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_image, remark, created_time, updated_time, deleted) SELECT NULL, 'opportunity_image', 'vip', 1, 0, 1.0000, 10, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='opportunity_image' AND plan_code='vip' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_image, remark, created_time, updated_time, deleted) SELECT NULL, 'opportunity_image', 'svp', 1, 0, 1.0000, 8, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='opportunity_image' AND plan_code='svp' AND deleted=0)");
        executeQuietly("UPDATE user_feedback SET site_source = 'commercial', site_name = '商业版' WHERE site_source IS NULL OR site_source = ''");
    }

    private void createTable(String ddl, String label) {
        try {
            if (!runtimeMutationsEnabled) {
                if (!tableExists(label)) failures.add("missing table " + label);
                return;
            }
            jdbcTemplate.execute(ddl);
        } catch (Exception e) {
            recordFailure("create " + label, e);
        }
    }

    private void addColumnIfMissing(String tableName, String columnName, String definition) {
        try {
            if (!tableExists(tableName)) {
                if (!runtimeMutationsEnabled) failures.add("missing table " + tableName);
                return;
            }
            if (columnExists(tableName, columnName)) return;
            if (!runtimeMutationsEnabled) {
                failures.add("missing column " + tableName + "." + columnName);
                return;
            }
            jdbcTemplate.execute("ALTER TABLE " + tableName + " ADD COLUMN " + columnName + " " + definition);
        } catch (Exception e) {
            recordFailure("add column " + tableName + "." + columnName, e);
        }
    }

    private void createIndexIfMissing(String tableName, String indexName, String ddl) {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = ? AND index_name = ?",
                    Integer.class,
                    tableName,
                    indexName
            );
            if (count == null || count == 0) {
                if (!runtimeMutationsEnabled) {
                    failures.add("missing index " + tableName + "." + indexName);
                    return;
                }
                jdbcTemplate.execute(ddl);
            }
        } catch (Exception e) {
            recordFailure("create index " + tableName + "." + indexName, e);
        }
    }

    private void executeQuietly(String sql) {
        if (!runtimeMutationsEnabled) return;
        try {
            jdbcTemplate.execute(sql);
        } catch (Exception e) {
            recordFailure("required data backfill", e);
        }
    }

    private void executeBackfillIfColumnExists(String tableName, String columnName, String sql) {
        if (!runtimeMutationsEnabled) return;
        try {
            if (!tableExists(tableName) || !columnExists(tableName, columnName)) return;
            jdbcTemplate.execute(sql);
        } catch (Exception e) {
            recordFailure("required data backfill", e);
        }
    }

    private void recordFailure(String operation, Exception error) {
        String errorType = error == null ? "UnknownError" : error.getClass().getSimpleName();
        failures.add(operation + ": " + errorType);
        log.error("SchemaCompatibilityRunner: {} failed, errorType={}", operation, errorType);
    }

    private boolean tableExists(String tableName) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = ?",
                Integer.class,
                tableName
        );
        return count != null && count > 0;
    }

    private boolean columnExists(String tableName, String columnName) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = ? AND column_name = ?",
                Integer.class,
                tableName,
                columnName
        );
        return count != null && count > 0;
    }

    private static boolean isProductionLike(String activeProfiles) {
        if (activeProfiles == null || activeProfiles.isBlank()) return false;
        for (String profile : activeProfiles.split("[,\\s]+")) {
            String normalized = profile.trim().toLowerCase();
            if (normalized.equals("dev") || normalized.equals("development")
                    || normalized.equals("local") || normalized.equals("test") || normalized.equals("testing")) {
                continue;
            }
            if (!normalized.isEmpty()) return true;
        }
        return false;
    }
}
