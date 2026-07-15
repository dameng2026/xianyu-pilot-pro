-- Immediate JWT revocation state for tenant users and administrators.
-- Apply during the reviewed maintenance window before deploying filters that
-- require the authVersion claim.

ALTER TABLE `sys_user`
    ADD COLUMN `security_version` BIGINT NOT NULL DEFAULT 1
    COMMENT 'Increment to invalidate all previously issued user JWTs';

ALTER TABLE `sys_admin_user`
    ADD COLUMN `security_version` BIGINT NOT NULL DEFAULT 1
    COMMENT 'Increment to invalidate all previously issued administrator JWTs';
