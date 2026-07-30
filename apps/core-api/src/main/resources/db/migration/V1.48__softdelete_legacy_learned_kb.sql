-- ============================================================
-- V1.48: 软删旧的 LLM 自动学习知识库条目与 V1.47 平级分类
-- 背景：V1.47 引入了 15 个平级业务分类，但 LLM 自动学习积累的 Q&A
--       质量参差不齐、分类混乱、与新的三级分类体系不兼容。
--       为保证 V1.49 三级分类（13 一级 + 68 二级）的种子数据干净，
--       此迁移将：
--   1. 软删 ai_cs_learned_kb 中所有 LLM 自动学习条目（source_type='ai' 或 NULL）
--   2. 软删 ai_cs_user_kb_binding 中所有 learned 类型的绑定（与被软删的 KB 级联）
--   3. 软删 V1.47 创建的 15 个平级分类（is_system=1，由 V1.49 重建为三级）
--   4. 重置 ai_cs_kb_category.entry_count = 0（V1.49 将重新填充）
-- 注意：
--   - 仅软删（deleted=1），不物理删除，保证可回滚
--   - 用户私有 KB（ai_cs_user_kb）和其绑定关系（kb_type='user'）不受影响
--   - V1.49 将插入新的三级分类与种子 Q&A
-- ============================================================

-- 1. 软删所有 LLM 自动学习 KB 条目（保留用户手动添加的，但 learned_kb 表都是 LLM 生成的）
UPDATE ai_cs_learned_kb
SET deleted = 1, vector_indexed = 0, updated_time = NOW()
WHERE deleted = 0;

-- 2. 软删所有 learned 类型的用户绑定关系（用户启用过的平台学习 KB）
--    kb_type='user' 的用户私有 KB 绑定不受影响
UPDATE ai_cs_user_kb_binding
SET deleted = 1
WHERE kb_type = 'learned' AND deleted = 0;

-- 3. 软删 V1.47 创建的所有平级分类（无论 is_system 还是 LLM 自动生成）
--    V1.49 将重建为 13 一级 + 68 二级的三级结构
UPDATE ai_cs_kb_category
SET deleted = 1, updated_time = NOW()
WHERE deleted = 0;

-- 4. 重置 entry_count（V1.49 将在插入种子数据时重新计算）
UPDATE ai_cs_kb_category
SET entry_count = 0
WHERE entry_count != 0;
