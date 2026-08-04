-- 滑块求解记录新增代理来源字段
-- 用于统计住址IP代理 vs 服务器IP的求解成功率对比
-- 仅追加列，不修改已有数据，不删除列
ALTER TABLE `xianyu_captcha_solve_record`
  ADD COLUMN IF NOT EXISTS `proxy_source` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '代理来源: server_ip(服务器IP) / residential_ip(住址IP) / account_bound(账号绑定代理) / none(无代理)' AFTER `engine`;

-- 添加索引便于按代理来源聚合统计成功率
CREATE INDEX IF NOT EXISTS `idx_xcsr_proxy_source_created` ON `xianyu_captcha_solve_record` (`proxy_source`, `created_at`);
CREATE INDEX IF NOT EXISTS `idx_xcsr_proxy_result` ON `xianyu_captcha_solve_record` (`proxy_source`, `result`, `created_at`);
