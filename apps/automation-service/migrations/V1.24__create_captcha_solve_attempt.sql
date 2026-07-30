-- 滑块求解每次尝试明细记录表
-- 用于统计每种求解方案/拖动方法/速度策略的使用次数与成功率，
-- 便于后续优化：淘汰成功率低的方案，更换成功率更高的方案。
-- 关联 xianyu_captcha_solve_record.id（一条求解记录对应 0~N 条 attempt 明细）。
-- 仅追加建表，不修改已有表，不删除数据。
CREATE TABLE IF NOT EXISTS `xianyu_captcha_solve_attempt` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `record_id` BIGINT NOT NULL COMMENT '关联 xianyu_captcha_solve_record.id',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID（冗余便于聚合查询）',
  `account_id` BIGINT NOT NULL COMMENT '账号ID（冗余便于聚合查询）',
  `attempt_no` INT NOT NULL COMMENT '尝试轮次编号（1-5，对应 crawler-service 内部 attempt 计数）',
  `solve_scheme` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '求解方案: python_script(Python脚本) / playwright(Playwright CDP)',
  `drag_method` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '拖动方法: in_container(容器内Y±8px) / out_container(超出容器Y±50-120px) / none(未拖动)',
  `speed_strategy` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '速度策略: standard(标准) / medium(中速) / fast(较快) / slow_pause(慢速+停顿) / random(随机) / none(未拖动)',
  `success` TINYINT NOT NULL DEFAULT 0 COMMENT '本次尝试是否成功: 0=失败 1=成功',
  `duration_ms` INT NOT NULL DEFAULT 0 COMMENT '本次尝试耗时（毫秒）',
  `error_message` VARCHAR(500) DEFAULT '' COMMENT '失败原因简述（成功时为空）',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  INDEX `idx_csa_record_id` (`record_id`),
  INDEX `idx_csa_tenant_created` (`tenant_id`, `created_at`),
  INDEX `idx_csa_scheme_success` (`solve_scheme`, `success`),
  INDEX `idx_csa_drag_success` (`drag_method`, `success`),
  INDEX `idx_csa_speed_success` (`speed_strategy`, `success`),
  INDEX `idx_csa_attempt_success` (`attempt_no`, `success`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='滑块求解每次尝试明细记录表（用于成功率统计）';
