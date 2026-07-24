-- 修复已发送卡密被软删除导致统计/查询不可见的问题
-- 背景：_safe_mark_cards_used 原先设置 status=2, deleted=1，导致已发送卡密从所有统计和查询中消失
--   - total_count 只统计 deleted=0，导致总量减少
--   - used_count 只统计 deleted=0 AND status=2，已发送卡密 deleted=1 导致已使用量永远为0
--   - 卡密明细/使用记录/库存统计均过滤 deleted=0，看不到已发送卡密
-- 修复：将 status=2 AND deleted=1 的卡密恢复为 deleted=0，使其重新可查询可统计
-- 幂等：WHERE status=2 AND deleted=1 确保多次执行结果相同；统计刷新基于实时 COUNT

-- 1. 恢复已发送卡密的可见性（deleted=0），并同步 is_used=1（与 Java updateStatus 逻辑一致）
UPDATE card_item
SET deleted = 0, is_used = 1, updated_time = NOW()
WHERE status = 2 AND deleted = 1;

-- 2. 刷新所有卡密组的统计计数（total/used/remain/available）
UPDATE card_group g SET
    total_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.deleted = 0),
    used_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.deleted = 0 AND i.status = 2),
    remain_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.deleted = 0 AND i.status = 0),
    available_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.deleted = 0 AND i.status = 0),
    updated_time = NOW()
WHERE g.deleted = 0;
