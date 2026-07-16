-- 滑块求解记录表新增字段：开启原因 + 求解原因
-- open_reason: 为什么打开滑块求解流程（用户手动点击 / 账号状态异常自动触发 等）
-- solve_reason: 为什么进行滑块求解（WS Token 失败 / Cookie 保活触发 / HTTP 1001 等 具体业务原因）
ALTER TABLE `xianyu_captcha_solve_record`
  ADD COLUMN `open_reason` VARCHAR(255) DEFAULT '' COMMENT '开启原因：为什么打开滑块求解流程（手动/自动 等）' AFTER `event_desc`,
  ADD COLUMN `solve_reason` VARCHAR(255) DEFAULT '' COMMENT '求解原因：为什么进行滑块求解（具体业务原因，如 WS Token 失败/Cookie 保活触发滑块 等）' AFTER `open_reason`;
