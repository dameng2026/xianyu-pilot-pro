-- Explicit media visibility and ownership metadata.
-- Existing governed assets remain private until an application workflow
-- deliberately marks them public; random paths are never an access policy.

ALTER TABLE `tenant_storage_asset`
    ADD COLUMN `visibility` VARCHAR(16) NOT NULL DEFAULT 'private' AFTER `source_type`,
    ADD COLUMN `purpose` VARCHAR(64) NOT NULL DEFAULT 'user-media' AFTER `visibility`,
    ADD COLUMN `owner_type` VARCHAR(32) NULL AFTER `purpose`,
    ADD COLUMN `owner_id` BIGINT NULL AFTER `owner_type`,
    ADD COLUMN `published_time` DATETIME NULL AFTER `activated_time`,
    ADD CONSTRAINT `chk_storage_asset_visibility`
        CHECK (`visibility` IN ('private', 'public')),
    ADD KEY `idx_storage_asset_visibility_status`
        (`visibility`, `status`, `updated_time`),
    ADD KEY `idx_storage_asset_owner`
        (`tenant_id`, `owner_type`, `owner_id`, `status`);
