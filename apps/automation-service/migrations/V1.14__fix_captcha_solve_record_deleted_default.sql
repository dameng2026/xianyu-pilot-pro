-- 修复 xianyu_captcha_solve_record.deleted 字段：
-- 根因：生产环境表结构与 V1.8 迁移脚本原始定义不一致。
--   V1.8 定义：`deleted` TINYINT DEFAULT 0
--   生产实际：`deleted` smallint DEFAULT NULL
-- 导致 Python INSERT 语句未显式传 deleted 时取默认值 NULL，1347 条记录 deleted 为 NULL。
-- 后台 admin-web 的 SQL 谓词 `WHERE deleted = 0` 无法匹配 NULL（NULL = 0 → NULL，视为 FALSE），
-- 导致后台滑块记录页显示 0/1 次，与前台 user-web 的 `COALESCE(deleted, 0) = 0`（显示 165 次）不一致。
-- 本迁移：
--   1. 将现有 NULL 值回填为 0（未删除）
--   2. 修改字段类型为 TINYINT NOT NULL DEFAULT 0，与 V1.8 原始定义对齐，防止后续 INSERT 再产生 NULL
-- 非破坏性：仅修改 NULL → 0（无业务影响，NULL 本来就被前台视为未删除）。
UPDATE `xianyu_captcha_solve_record` SET `deleted` = 0 WHERE `deleted` IS NULL;
ALTER TABLE `xianyu_captcha_solve_record`
  MODIFY COLUMN `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '0未删除 1已删除';
