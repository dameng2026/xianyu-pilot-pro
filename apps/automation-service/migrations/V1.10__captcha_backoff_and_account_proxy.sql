-- 全自动滑块：失败指数退避状态 + 账号绑定代理
-- 代理用于按账号固定出口，降低设备/IP 画像串扰

CREATE TABLE IF NOT EXISTS `xianyu_captcha_backoff` (
  `account_id` BIGINT NOT NULL COMMENT '账号ID',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `fail_count` INT NOT NULL DEFAULT 0 COMMENT '连续失败次数',
  `next_allowed_at` DATETIME NULL COMMENT '下次允许自动求解时间',
  `last_fail_at` DATETIME NULL COMMENT '最近失败时间',
  `last_success_at` DATETIME NULL COMMENT '最近成功时间',
  `last_error` VARCHAR(512) DEFAULT '' COMMENT '最近失败摘要',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`account_id`),
  KEY `idx_cb_tenant_next` (`tenant_id`, `next_allowed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='滑块自动求解指数退避';

-- 账号级代理（绑定固定出口）。列已存在时请手动跳过对应语句。
ALTER TABLE `xianyu_account`
  ADD COLUMN `proxy_type` VARCHAR(16) DEFAULT '' COMMENT 'http/https/socks5' AFTER `admin_remark`,
  ADD COLUMN `proxy_host` VARCHAR(255) DEFAULT '' COMMENT '代理主机' AFTER `proxy_type`,
  ADD COLUMN `proxy_port` INT NULL COMMENT '代理端口' AFTER `proxy_host`,
  ADD COLUMN `proxy_username` VARCHAR(128) DEFAULT '' COMMENT '代理用户名' AFTER `proxy_port`,
  ADD COLUMN `encrypted_proxy_password` TEXT NULL COMMENT '代理密码(enc:v1)' AFTER `proxy_username`;
