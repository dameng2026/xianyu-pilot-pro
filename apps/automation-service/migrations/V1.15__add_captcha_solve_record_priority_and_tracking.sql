-- 滑块求解记录表：新增优先级、失败原因分类、队列时间追踪字段
-- 用于支持：
--   1. 按会员等级(SVIP/VIP/普通)排队的优先级调度
--   2. 失败原因精细化展示（slider_fail/cookie_invalid/service_unavailable/timeout/account_inactive 等）
--   3. 无响应"进行中"记录的超时回收（基于 started_at/queued_at 判定）
--   4. 失败任务自动重试入队（基于 failure_reason 判断是否可重试）
-- 所有字段均为追加型，不修改已有列，不删除数据。

ALTER TABLE `xianyu_captcha_solve_record`
  ADD COLUMN IF NOT EXISTS `priority` TINYINT NOT NULL DEFAULT 0
    COMMENT '优先级: 0=普通 1=VIP 2=SVIP（值越大越优先）' AFTER `retry_count`,
  ADD COLUMN IF NOT EXISTS `failure_reason` VARCHAR(64) NOT NULL DEFAULT ''
    COMMENT '失败原因分类: slider_fail/cookie_invalid/service_unavailable/timeout/account_inactive/precheck_rejected/stale_terminated'
    AFTER `priority`,
  ADD COLUMN IF NOT EXISTS `queued_at` DATETIME NULL
    COMMENT '入队时间（进入优先级队列的时间）' AFTER `failure_reason`,
  ADD COLUMN IF NOT EXISTS `started_at` DATETIME NULL
    COMMENT '开始处理时间（worker 取出任务的时间）' AFTER `queued_at`,
  ADD COLUMN IF NOT EXISTS `finished_at` DATETIME NULL
    COMMENT '完成处理时间（成功/失败/终止的时间）' AFTER `started_at`;

-- 优先级 + 状态索引：用于队列 worker 按优先级取出待处理任务
ALTER TABLE `xianyu_captcha_solve_record`
  ADD INDEX IF NOT EXISTS `idx_csr_priority_status_queued` (`status`, `priority`, `queued_at`);

-- 超时清理索引：用于定时扫描"进行中但超时"的记录
ALTER TABLE `xianyu_captcha_solve_record`
  ADD INDEX IF NOT EXISTS `idx_csr_status_started_at` (`status`, `started_at`);
