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
        addColumnIfMissing("xianyu_account_auto_rate_config", "created_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_account_auto_rate_config", "updated_time", "DATETIME NULL");
        addColumnIfMissing("xianyu_account_auto_rate_config", "deleted", "TINYINT DEFAULT 0");
        createIndexIfMissing("xianyu_account_auto_rate_config", "uk_xyaarc_tenant_account",
                "CREATE UNIQUE INDEX uk_xyaarc_tenant_account ON xianyu_account_auto_rate_config(tenant_id, account_id)");
        createIndexIfMissing("xianyu_account_auto_rate_config", "idx_xyaarc_tenant",
                "CREATE INDEX idx_xyaarc_tenant ON xianyu_account_auto_rate_config(tenant_id, deleted)");
        createIndexIfMissing("xianyu_account_auto_rate_config", "idx_xyaarc_account",
                "CREATE INDEX idx_xyaarc_account ON xianyu_account_auto_rate_config(account_id)");
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
        addColumnIfMissing("card_group", "description", "TEXT NULL");
        addColumnIfMissing("card_group", "card_prefix", "VARCHAR(120) NULL");
        addColumnIfMissing("card_group", "password_prefix", "VARCHAR(120) NULL");
        addColumnIfMissing("card_group", "alert_threshold", "INT DEFAULT 10");
        addColumnIfMissing("card_group", "cost_price", "DECIMAL(10,2) NULL");
        addColumnIfMissing("card_group", "suggested_price", "DECIMAL(10,2) NULL");
        addColumnIfMissing("card_group", "remain_count", "INT DEFAULT 0");
        addColumnIfMissing("card_group", "available_count", "INT DEFAULT 0");
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
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_reply, min_tokens, fallback_exchange_rate, daily_cap_count, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'auto_reply', 'AI Auto Reply', 'reply', 'member_quota_then_fixed', 'reply', 1, 1, 1, 8, 0, 160, 1000, 80, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='auto_reply' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_image, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_image', 'Workflow Image', 'image', 'fixed_per_image', 'image', 1, 1, 1, 12, 12, 160, 110, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='workflow_image' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_image, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'opportunity_image', 'Opportunity Image', 'image', 'fixed_per_image', 'image', 1, 1, 1, 12, 12, 160, 111, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='opportunity_image' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'workflow_screen', 'Workflow Screen', 'screen', 'fixed_per_call', 'call', 1, 1, 1, 20, 20, 160, 50, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='workflow_screen' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'product_filter', 'Product Filter', 'screen', 'fixed_per_call', 'item_call', 1, 1, 1, 2, 2, 160, 51, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='product_filter' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'product_polish', 'Product Polish', 'rewrite', 'fixed_per_call', 'item_call', 1, 1, 1, 3, 3, 160, 52, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='product_polish' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, cost_markup_rate, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'knowledge_base_extract', 'Knowledge Base Extract', 'knowledge', 'cost_plus_rate', 'file', 1, 1, 0, 2.2000, 50, 160, 70, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='knowledge_base_extract' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, daily_cap_count, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'delivery_source_match', 'Delivery Source Match', 'screen', 'fixed_per_call', 'call', 1, 1, 1, 20, 20, 160, 30, 120, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='delivery_source_match' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_sell_config(tenant_id, scene_key, scene_name, scene_group, charge_mode, price_unit, enabled, is_metered, show_estimate, sell_tokens_per_call, min_tokens, fallback_exchange_rate, sort_order, remark, created_time, updated_time, deleted) SELECT NULL, 'ai_customer_service_test', 'AI Customer Service Test', 'support', 'fixed_per_call', 'call', 1, 1, 0, 20, 20, 160, 140, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_sell_config WHERE tenant_id IS NULL AND scene_key='ai_customer_service_test' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_reply, daily_cap_count, remark, created_time, updated_time, deleted) SELECT NULL, 'auto_reply', 'normal', 1, 10, 1.0000, 8, 100, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='auto_reply' AND plan_code='normal' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_reply, daily_cap_count, remark, created_time, updated_time, deleted) SELECT NULL, 'auto_reply', 'vip', 1, 30, 1.0000, 6, 500, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='auto_reply' AND plan_code='vip' AND deleted=0)");
        executeQuietly("INSERT INTO ai_scene_plan_benefit(tenant_id, scene_key, plan_code, enabled, free_quota_daily, discount_rate, override_tokens_per_reply, daily_cap_count, remark, created_time, updated_time, deleted) SELECT NULL, 'auto_reply', 'svp', 1, 200, 1.0000, 4, 2000, 'schema-seed', NOW(), NOW(), 0 WHERE NOT EXISTS (SELECT 1 FROM ai_scene_plan_benefit WHERE tenant_id IS NULL AND scene_key='auto_reply' AND plan_code='svp' AND deleted=0)");
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
