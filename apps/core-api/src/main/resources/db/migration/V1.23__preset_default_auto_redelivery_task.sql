-- 为每个租户预置一个默认的"自动补发订单"定时任务（10 分钟间隔）。
-- 业务背景：用户上线后无需手动配置即可享受自动补发能力，降低使用门槛。
-- 幂等性：通过 WHERE NOT EXISTS 保证重复执行不会创建重复任务。
-- 数据来源：sys_user.tenant_id 去重（每个租户至少有一个用户）。
-- config_json.accountIds 为空数组，表示该任务覆盖租户下所有账号（运行时由 _load_tenant_account_ids 兜底加载）。

INSERT INTO `scheduled_task` (
    `tenant_id`,
    `account_id`,
    `task_type`,
    `task_name`,
    `cron_expression`,
    `config_json`,
    `enabled`,
    `created_time`,
    `updated_time`,
    `deleted`
)
SELECT
    DISTINCT u.`tenant_id`,
    NULL,
    'auto_redelivery',
    '默认自动补发订单任务（10分钟）',
    '0 */10 * * * ?',
    '{"intervalMinutes": 10, "accountIds": []}',
    1,
    NOW(),
    NOW(),
    0
FROM `sys_user` u
WHERE u.`deleted` = 0
  AND u.`tenant_id` IS NOT NULL
  AND u.`tenant_id` > 0
  AND NOT EXISTS (
    SELECT 1 FROM `scheduled_task` t
    WHERE t.`tenant_id` = u.`tenant_id`
      AND t.`task_type` = 'auto_redelivery'
      AND t.`deleted` = 0
  );
