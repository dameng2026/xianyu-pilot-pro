<template>
  <div class="admin-page">
    <ElCard shadow="never" class="hero-card">
      <div class="page-title-row">
        <div>
          <h2>开源版首页公告</h2>
          <p>兼容开源版 `/announcement/list` 数据源。当前开源版前台默认不突出展示该区域，但 bridge 接口仍会对外提供，便于后续启用。</p>
        </div>
        <div class="toolbar-actions">
          <ElButton type="primary" :disabled="!canMutate" @click="openDialog()">
            <ElIcon><Plus /></ElIcon>
            新增公告
          </ElButton>
        </div>
      </div>
    </ElCard>

    <AdminDataState
      v-if="listState === 'loading'"
      state="loading"
      title="正在加载开源版公告"
      :retryable="false"
    />
    <AdminDataState
      v-else-if="listState === 'error'"
      state="error"
      title="开源版公告暂时不可用"
      description="无法确认线上公告，新增、编辑和删除已暂停。"
      @retry="loadList"
    />
    <div v-else class="page-grid">
      <ElCard shadow="never" class="preview-card">
        <div class="section-head">
          <div>
            <h3>当前启用项</h3>
            <span>如果后续开源版恢复首页公告展示，将优先使用第一条启用中的记录</span>
          </div>
          <ElTag :type="currentAnnouncement ? 'success' : 'info'">{{ currentAnnouncement ? '已有启用公告' : '暂无启用公告' }}</ElTag>
        </div>

        <div v-if="currentAnnouncement" class="announcement-preview">
          <div class="preview-icon">公告</div>
          <div class="preview-copy">
            <strong>{{ currentAnnouncement.title }}</strong>
            <p>{{ currentAnnouncement.content }}</p>
          </div>
          <div class="preview-actions">
            <ElButton type="primary" plain @click="openDialog(currentAnnouncement)">编辑当前公告</ElButton>
          </div>
        </div>

        <ElEmpty v-else description="当前没有启用中的开源版首页公告" />
      </ElCard>

      <ElCard shadow="never" class="table-card">
        <div class="section-head">
          <div>
            <h3>公告列表</h3>
            <span>专用于开源版首页兼容公告接口，不影响商业版自己的公告数据</span>
          </div>
          <ElTag type="info">{{ list.length }} 条</ElTag>
        </div>

        <ElTable :data="list" v-loading="loading" stripe style="width: 100%">
          <OpenSourceAnnouncementTableColumn label="前台候选" width="110" align="center">
            <template #default="{ row }">
              <ElTag v-if="currentAnnouncement?.id === row.id" type="success">优先返回</ElTag>
              <span v-else class="row-muted">-</span>
            </template>
          </OpenSourceAnnouncementTableColumn>
          <OpenSourceAnnouncementTableColumn label="公告标题" min-width="220" prop="title" />
          <OpenSourceAnnouncementTableColumn label="公告正文" min-width="360">
            <template #default="{ row }">
              <span class="text-ellipsis">{{ row.content || '-' }}</span>
            </template>
          </OpenSourceAnnouncementTableColumn>
          <OpenSourceAnnouncementTableColumn label="状态" width="90" align="center">
            <template #default="{ row }">
              <ElTag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '禁用' }}</ElTag>
            </template>
          </OpenSourceAnnouncementTableColumn>
          <OpenSourceAnnouncementTableColumn label="更新时间" width="180" align="center" prop="updatedAt" />
          <OpenSourceAnnouncementTableColumn label="操作" width="180" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton size="small" type="primary" link @click="openDialog(row)">编辑</ElButton>
              <ElButton size="small" type="danger" link @click="handleDelete(row)">删除</ElButton>
            </template>
          </OpenSourceAnnouncementTableColumn>
        </ElTable>

        <div v-if="!loading && list.length === 0" class="empty-hint">
          <ElButton type="primary" @click="openDialog()"><ElIcon><Plus /></ElIcon>新增公告</ElButton>
        </div>
      </ElCard>
    </div>

    <ElDialog v-model="dialogVisible" :title="isEdit ? '编辑开源版公告' : '新增开源版公告'" width="680px" destroy-on-close>
      <ElForm :model="form" :rules="rules" ref="formRef" label-width="100px" label-position="right">
        <ElFormItem label="公告标题" prop="title">
          <ElInput v-model="form.title" placeholder="输入公告标题" maxlength="100" show-word-limit />
        </ElFormItem>
        <ElFormItem label="公告正文" prop="content">
          <ElInput
            v-model="form.content"
            type="textarea"
            :rows="7"
            placeholder="输入开源版首页公告正文，支持多行文本"
            maxlength="2000"
            show-word-limit
          />
        </ElFormItem>
        <ElFormItem label="启用状态" prop="enabled">
          <ElSwitch v-model="form.enabled" active-text="启用" inactive-text="禁用" />
          <div class="form-tip">bridge 会按列表顺序返回启用记录，前台是否展示由开源版页面决定。</div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="handleSave" :loading="saving">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox, ElTableColumn } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  deleteOpenSourceAnnouncement,
  getOpenSourceAnnouncementList,
  saveOpenSourceAnnouncement,
  updateOpenSourceAnnouncement,
  type OpenSourceAnnouncementItem
} from '@/api/open-source-content'

defineOptions({ name: 'AdminOpenSourceAnnouncementPage' })

const OpenSourceAnnouncementTableColumn: typeof ElTableColumn<OpenSourceAnnouncementItem> = ElTableColumn

const list = ref<OpenSourceAnnouncementItem[]>([])
const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const dialogVisible = ref(false)
const saving = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()

const defaultForm = (): OpenSourceAnnouncementItem => ({
  title: '',
  content: '',
  enabled: true
})

const form = reactive<OpenSourceAnnouncementItem>(defaultForm())

const rules: FormRules = {
  title: [{ required: true, message: '请输入公告标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入公告正文', trigger: 'blur' }]
}

const currentAnnouncement = computed(() => list.value.find(item => item?.enabled) || null)
const canMutate = computed(() => listState.value === 'ready' || listState.value === 'empty')

async function loadList() {
  loading.value = true
  listState.value = 'loading'
  try {
    const res = await getOpenSourceAnnouncementList()
    list.value = res
    listState.value = list.value.length > 0 ? 'ready' : 'empty'
  } catch {
    list.value = []
    listState.value = 'error'
  } finally {
    loading.value = false
  }
}

function openDialog(row?: OpenSourceAnnouncementItem) {
  if (!canMutate.value) return
  isEdit.value = !!row
  if (row) {
    form.id = row.id
    form.title = row.title
    form.content = row.content
    form.enabled = row.enabled
  } else {
    Object.assign(form, defaultForm())
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!canMutate.value) {
    ElMessage.warning('公告配置尚未成功读取，当前不能保存')
    return
  }
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value && !form.id) {
      ElMessage.error('公告标识缺失，无法安全更新')
      return
    }
    if (isEdit.value) {
      await updateOpenSourceAnnouncement({ ...form })
    } else {
      await saveOpenSourceAnnouncement({ ...form })
    }
    ElMessage.success(isEdit.value ? '开源版公告更新成功' : '开源版公告添加成功')
    dialogVisible.value = false
    await loadList()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: OpenSourceAnnouncementItem) {
  if (!row.id || !canMutate.value) {
    ElMessage.error('公告标识缺失或列表不可用，无法安全删除')
    return
  }
  try {
    await ElMessageBox.confirm('确定删除这条开源版公告？删除后 bridge 将不再返回这条内容。', '确认删除', { type: 'warning' })
    await deleteOpenSourceAnnouncement(row.id)
    ElMessage.success('删除成功')
    await loadList()
  } catch {
    // cancelled
  }
}

onMounted(() => loadList())
</script>

<style scoped>
.admin-page { padding: 4px; }
.hero-card, .preview-card, .table-card { border-radius: 18px; }
.page-title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 22px; font-weight: 800; }
.page-title-row p { margin: 0; color: var(--art-gray-500); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; }
.page-grid {
  display: grid;
  grid-template-columns: minmax(320px, 400px) minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
  align-items: start;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}
.section-head h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #17315c;
}
.section-head span {
  display: block;
  margin-top: 6px;
  color: var(--art-gray-500);
  font-size: 12px;
}
.announcement-preview {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid #f4d4a4;
  background: linear-gradient(90deg, #fff8ec 0%, #fffdf8 100%);
}
.preview-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff1cf 0%, #ffe7b6 100%);
  font-size: 16px;
  font-weight: 800;
  color: #8c5a06;
}
.preview-copy strong {
  display: block;
  color: #8c5a06;
  font-size: 16px;
}
.preview-copy p {
  margin: 10px 0 0;
  color: #9c7221;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
}
.preview-actions {
  display: flex;
  justify-content: flex-start;
}
.row-muted {
  color: var(--art-gray-400);
}
.text-ellipsis {
  display: inline-block;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.form-tip {
  font-size: 12px;
  color: var(--art-gray-500);
  margin-top: 4px;
}
.empty-hint { text-align: center; padding: 40px 0; }
@media (max-width: 1180px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 900px) {
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
