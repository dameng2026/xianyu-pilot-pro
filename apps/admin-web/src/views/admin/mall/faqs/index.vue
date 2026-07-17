<template>
  <div class="admin-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>货源商城 - 常见问题</h2>
          <p>维护商城前台常见问题列表，支持排序与启停控制</p>
        </div>
        <div class="toolbar-actions">
          <ElButton :loading="loading" @click="load">刷新</ElButton>
          <ElButton type="primary" @click="openDialog()">
            <ElIcon><Plus /></ElIcon>新增FAQ
          </ElButton>
        </div>
      </div>
    </ElCard>

    <ElCard shadow="never" class="table-card">
      <AdminDataState
        v-if="listState === 'loading'"
        state="loading"
        title="正在加载FAQ列表"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="FAQ列表暂时不可用"
        description="请求失败，请重试。"
        @retry="load"
      />
      <template v-else>
        <ElTable :data="records" v-loading="loading" border stripe style="width: 100%">
          <template #empty><div class="empty-state">暂无FAQ记录</div></template>
          <FaqTableColumn prop="id" label="ID" width="80" align="center" />
          <FaqTableColumn label="问题" min-width="260">
            <template #default="{ row }">
              <strong>{{ row.question }}</strong>
            </template>
          </FaqTableColumn>
          <FaqTableColumn label="答案" min-width="360">
            <template #default="{ row }">
              <span class="text-ellipsis">{{ row.answer || '-' }}</span>
            </template>
          </FaqTableColumn>
          <FaqTableColumn label="排序" width="100" align="center" prop="sortOrder" />
          <FaqTableColumn label="状态" width="100" align="center">
            <template #default="{ row }">
              <ElTag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '禁用' }}</ElTag>
            </template>
          </FaqTableColumn>
          <FaqTableColumn label="操作" width="160" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton size="small" type="primary" link @click="openDialog(row)">编辑</ElButton>
              <ElButton size="small" type="danger" link @click="handleDelete(row)">删除</ElButton>
            </template>
          </FaqTableColumn>
        </ElTable>
      </template>
    </ElCard>

    <ElDialog v-model="dialogVisible" :title="isEdit ? '编辑FAQ' : '新增FAQ'" width="640px" destroy-on-close>
      <ElForm :model="form" :rules="rules" ref="formRef" label-width="100px" label-position="right">
        <ElFormItem label="问题" prop="question">
          <ElInput v-model="form.question" placeholder="输入常见问题" maxlength="200" show-word-limit />
        </ElFormItem>
        <ElFormItem label="答案" prop="answer">
          <ElInput
            v-model="form.answer"
            type="textarea"
            :rows="6"
            placeholder="输入问题答案"
            maxlength="2000"
            show-word-limit
          />
        </ElFormItem>
        <ElFormItem label="排序值" prop="sortOrder">
          <ElInputNumber v-model="form.sortOrder" :min="0" :max="999" style="width: 180px" />
          <div class="form-tip">数值越小越靠前</div>
        </ElFormItem>
        <ElFormItem label="启用状态" prop="enabled">
          <ElSwitch v-model="form.enabled" active-text="启用" inactive-text="禁用" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="handleSave">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox, ElTableColumn } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  getMallFaqs,
  createMallFaq,
  updateMallFaq,
  deleteMallFaq,
  type MallFaq
} from '@/api/mall'

defineOptions({ name: 'AdminMallFaqsPage' })

const FaqTableColumn: typeof ElTableColumn<MallFaq> = ElTableColumn

const records = ref<MallFaq[]>([])
const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const dialogVisible = ref(false)
const saving = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()

const defaultForm = (): MallFaq => ({
  id: undefined,
  question: '',
  answer: '',
  sortOrder: 0,
  enabled: true
})

const form = reactive<MallFaq>(defaultForm())

const rules: FormRules = {
  question: [{ required: true, message: '请输入问题', trigger: 'blur' }],
  answer: [{ required: true, message: '请输入答案', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  listState.value = 'loading'
  try {
    const res = await getMallFaqs()
    records.value = Array.isArray(res) ? res : []
    listState.value = records.value.length > 0 ? 'ready' : 'empty'
  } catch {
    records.value = []
    listState.value = 'error'
  } finally {
    loading.value = false
  }
}

function openDialog(row?: MallFaq) {
  isEdit.value = !!row
  if (row) {
    form.id = row.id
    form.question = row.question
    form.answer = row.answer
    form.sortOrder = row.sortOrder ?? 0
    form.enabled = row.enabled !== false
  } else {
    Object.assign(form, defaultForm())
  }
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload: Partial<MallFaq> = {
      question: form.question,
      answer: form.answer,
      sortOrder: Number(form.sortOrder || 0),
      enabled: form.enabled
    }
    if (isEdit.value && form.id) {
      await updateMallFaq(form.id, payload)
    } else {
      await createMallFaq(payload)
    }
    ElMessage.success(isEdit.value ? 'FAQ更新成功' : 'FAQ添加成功')
    dialogVisible.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: MallFaq) {
  if (!row.id) return
  try {
    await ElMessageBox.confirm('确认删除该FAQ？删除后无法恢复。', '确认删除', { type: 'warning' })
    await deleteMallFaq(row.id)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // cancelled
  }
}

onMounted(() => load())
</script>

<style scoped>
.admin-page { padding: 4px; }
.filter-card { margin-bottom: 16px; border-radius: 16px; }
.table-card { min-height: 420px; border-radius: 16px; }
.page-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 22px; font-weight: 800; }
.page-title-row p { margin: 0; color: var(--art-gray-500); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.text-ellipsis {
  display: inline-block;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-regular);
}
.form-tip {
  font-size: 12px;
  color: var(--art-gray-500);
  margin-top: 4px;
}
@media (max-width: 900px) {
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
