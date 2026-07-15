-- Durable, cross-process storage quota reservations and cleanup audit trail.

CREATE TABLE `tenant_storage_asset` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL,
    `user_id` BIGINT NULL,
    `storage_key` VARCHAR(512) NOT NULL,
    `public_url` VARCHAR(700) NOT NULL,
    `media_type` VARCHAR(100) NULL,
    `source_type` VARCHAR(50) NOT NULL,
    `size_bytes` BIGINT NOT NULL,
    `sha256` CHAR(64) NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'reserved',
    `request_id` VARCHAR(128) NULL,
    `deletion_reason` VARCHAR(255) NULL,
    `cleaned_by` VARCHAR(120) NULL,
    `reviewed_by` VARCHAR(120) NULL,
    `approved_by` VARCHAR(120) NULL,
    `activated_time` DATETIME NULL,
    `deleted_time` DATETIME NULL,
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_storage_asset_key` (`storage_key`),
    KEY `idx_storage_asset_tenant_status` (`tenant_id`, `status`),
    KEY `idx_storage_asset_created` (`created_time`),
    KEY `idx_storage_asset_status_created` (`status`, `created_time`),
    KEY `idx_storage_asset_status_size` (`status`, `size_bytes`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `tenant_upload_rate_event` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL,
    `user_id` BIGINT NULL,
    `request_id` VARCHAR(128) NULL,
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_upload_rate_tenant_time` (`tenant_id`, `created_time`),
    KEY `idx_upload_rate_created` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
