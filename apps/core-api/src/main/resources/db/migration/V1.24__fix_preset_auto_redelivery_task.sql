-- V1.24: 修正 V1.23 预置任务的乱码 task_name，并填充 accountIds 为租户全部闲鱼账号
-- 背景：
--   1. V1.23 手动执行时连接字符集为 latin1，导致中文 task_name 双重编码为乱码
--      （UTF-8 字节被当作 latin1 解码后又用 UTF-8 存储）
--   2. V1.23 预置任务 accountIds 为空数组，用户希望预置任务绑定租户下全部闲鱼账号
-- 幂等性：UPDATE 语句可重复执行，不会产生副作用
-- 安全性：仅 UPDATE 已有行，不修改表结构，不删除数据

-- 1. 修正乱码的 task_name（仅修正包含 latin1 双重编码特征字符 é 的行）
UPDATE `scheduled_task`
SET `task_name` = '默认自动补发订单任务（10分钟）'
WHERE `task_type` = 'auto_redelivery'
  AND `deleted` = 0
  AND `task_name` LIKE '%é%';

-- 2. 为每个预置的 auto_redelivery 任务填充 accountIds 为租户全部闲鱼账号
--    使用 JSON_OBJECT + JSON_ARRAYAGG 重建 config_json
--    account_id 设为该租户第一个账号（兼容旧逻辑，前端取 accountIds[0]）
UPDATE `scheduled_task` t
JOIN (
    SELECT
        t2.`id` AS task_id,
        t2.`tenant_id`,
        JSON_OBJECT(
            'intervalMinutes', 10,
            'accountIds', COALESCE(
                (SELECT JSON_ARRAYAGG(xa.`id`)
                 FROM `xianyu_account` xa
                 WHERE xa.`tenant_id` = t2.`tenant_id`
                   AND xa.`deleted` = 0),
                JSON_ARRAY()
            )
        ) AS new_config
    FROM `scheduled_task` t2
    WHERE t2.`task_type` = 'auto_redelivery'
      AND t2.`deleted` = 0
) AS sub ON t.`id` = sub.task_id
SET t.`config_json` = sub.new_config,
    t.`account_id` = (
        SELECT MIN(xa.`id`) FROM `xianyu_account` xa
        WHERE xa.`tenant_id` = t.`tenant_id` AND xa.`deleted` = 0
    ),
    t.`updated_time` = NOW();
