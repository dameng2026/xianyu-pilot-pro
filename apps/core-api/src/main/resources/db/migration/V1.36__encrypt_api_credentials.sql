SET @api_key_encrypted_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'xianyu_api_credential'
      AND COLUMN_NAME = 'api_key_encrypted'
);
SET @api_key_encrypted_sql := IF(
    @api_key_encrypted_exists = 0,
    'ALTER TABLE xianyu_api_credential ADD COLUMN api_key_encrypted VARCHAR(512) NULL COMMENT ''API 密钥 AES-GCM 密文''',
    'SELECT 1'
);
PREPARE api_key_encrypted_stmt FROM @api_key_encrypted_sql;
EXECUTE api_key_encrypted_stmt;
DEALLOCATE PREPARE api_key_encrypted_stmt;
