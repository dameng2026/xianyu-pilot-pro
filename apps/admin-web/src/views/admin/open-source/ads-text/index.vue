<template>
  <div class="admin-page">
    <ElCard shadow="never" class="hero-card">
      <div class="page-title-row">
        <div>
          <h2>开源版文本广告</h2>
          <p>控制开源版首页右侧文字广告位。前台最多展示 10 条启用广告，按排序值从小到大输出。</p>
        </div>
        <div class="toolbar-actions">
          <ElButton type="primary" :disabled="!canMutate" @click="openDialog()">
            <ElIcon><Plus /></ElIcon>
            新增文本广告
          </ElButton>
        </div>
      </div>

      <div v-if="canMutate" class="summary-grid">
        <div class="summary-card">
          <strong>{{ list.length }}</strong>
          <span>当前配置总数</span>
        </div>
        <div class="summary-card">
          <strong>{{ enabledCount }}</strong>
          <span>启用中的广告</span>
        </div>
        <div class="summary-card">
          <strong>{{ displayCount }}</strong>
          <span>前台可展示数量</span>
        </div>
      </div>
    </ElCard>

    <AdminDataState
      v-if="listState === 'loading'"
      state="loading"
      title="正在加载文字广告"
      :retryable="false"
    />
    <AdminDataState
      v-else-if="listState === 'error'"
      state="error"
      title="文字广告暂时不可用"
      description="无法确认线上广告，统计和写入操作已暂停。"
      @retry="loadList"
    />
    <div v-else class="page-grid">
      <ElCard shadow="never" class="preview-card">
        <div class="section-head">
          <div>
            <h3>前台展示预览</h3>
            <span>这里按照真实前台逻辑，仅预览启用且排序靠前的 10 条</span>
          </div>
        </div>

        <div v-if="displayList.length" class="preview-list">
          <article v-for="item in displayList" :key="item.id" class="preview-item">
            <div class="preview-head">
              <strong>{{ item.title || '广告位招募中' }}</strong>
              <i>{{ item.badge || '文字广告' }}</i>
            </div>
            <p>{{ item.summary || '请填写广告摘要，方便前台展示转化文案。' }}</p>
            <span class="preview-link">{{ item.linkUrl || '#/ad-application' }}</span>
          </article>
        </div>
        <ElEmpty v-else description="暂无可展示的文本广告" />
      </ElCard>

      <ElCard shadow="never" class="table-card">
        <div class="section-head">
          <div>
            <h3>广告列表</h3>
            <span>建议把高转化广告排在前面，把默认招商入口排在靠后位置</span>
          </div>
        </div>

        <ElTable :data="list" v-loading="loading" stripe style="width: 100%">
          <OpenSourceTextAdTableColumn label="标题" min-width="220" prop="title" />
          <OpenSourceTextAdTableColumn label="角标" width="130" prop="badge" />
          <OpenSourceTextAdTableColumn label="摘要" min-width="280">
            <template #default="{ row }">
              <span class="text-ellipsis">{{ row.summary || '-' }}</span>
            </template>
          </OpenSourceTextAdTableColumn>
          <OpenSourceTextAdTableColumn label="排序" width="90" align="center" prop="sortOrder" />
          <OpenSourceTextAdTableColumn label="状态" width="90" align="center">
            <template #default="{ row }">
              <ElTag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '禁用' }}</ElTag>
            </template>
          </OpenSourceTextAdTableColumn>
          <OpenSourceTextAdTableColumn label="更新时间" width="180" align="center" prop="updatedAt" />
          <OpenSourceTextAdTableColumn label="操作" width="180" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton size="small" type="primary" link @click="openDialog(row)">编辑</ElButton>
              <ElButton size="small" type="danger" link @click="handleDelete(row)">删除</ElButton>
            </template>
          </OpenSourceTextAdTableColumn>
        </ElTable>
      </ElCard>
    </div>

    <ElDialog v-model="dialogVisible" :title="isEdit ? '编辑文本广告' : '新增文本广告'" width="720px" destroy-on-close>
      <ElForm :model="form" :rules="rules" ref="formRef" label-width="100px" label-position="right">
        <ElFormItem label="广告标题" prop="title">
          <ElInput v-model="form.title" maxlength="80" show-word-limit />
        </ElFormItem>
        <ElFormItem label="角标文案" prop="badge">
          <ElInput v-model="form.badge" maxlength="24" show-word-limit placeholder="例如：限量席位 / 轮播招商" />
        </ElFormItem>
        <ElFormItem label="广告摘要" prop="summary">
          <ElInput v-model="form.summary" type="textarea" :rows="4" maxlength="200" show-word-limit />
        </ElFormItem>
        <ElFormItem label="跳转链接" prop="linkUrl">
          <ElInput v-model="form.linkUrl" maxlength="300" placeholder="例如：#/ad-application 或 https://example.com" />
        </ElFormItem>
        <ElFormItem label="排序值" prop="sortOrder">
          <ElInputNumber v-model="form.sortOrder" :min="0" :max="999" style="width: 180px" />
        </ElFormItem>
        <ElFormItem label="启用状态" prop="enabled">
          <ElSwitch v-model="form.enabled" active-text="启用" inactive-text="禁用" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, ElTableColumn } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  deleteOpenSourceTextAd,
  getOpenSourceTextAds,
  saveOpenSourceTextAd,
  updateOpenSourceTextAd,
  type OpenSourceTextAdItem
} from '@/api/open-source-ads'

defineOptions({ name: 'AdminOpenSourceTextAdsPage' })

const OpenSourceTextAdTableColumn: typeof ElTableColumn<OpenSourceTextAdItem> = ElTableColumn

const list = ref<OpenSourceTextAdItem[]>([])
const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const saving = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()

const defaultForm = (): OpenSourceTextAdItem => ({
  title: '',
  summary: '',
  badge: '',
  linkUrl: '#/ad-application',
  enabled: true,
  sortOrder: 0
})

const form = reactive<OpenSourceTextAdItem>(defaultForm())

const rules: FormRules = {
  title: [{ required: true, message: '请输入广告标题', trigger: 'blur' }],
  summary: [{ required: true, message: '请输入广告摘要', trigger: 'blur' }],
  linkUrl: [{ required: true, message: '请输入跳转链接', trigger: 'blur' }]
}

const enabledCount = computed(() => list.value.filter(item => item.enabled).length)
const displayList = computed(() => list.value
  .filter(item => item.enabled)
  .slice()
  .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))
  .slice(0, 10))
const displayCount = computed(() => displayList.value.length)
const canMutate = computed(() => listState.value === 'ready' || listState.value === 'empty')

async function loadList() {
  loading.value = true
  listState.value = 'loading'
  try {
    const res = await getOpenSourceTextAds()
    list.value = res.slice().sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))
    listState.value = list.value.length > 0 ? 'ready' : 'empty'
  } catch {
    list.value = []
    listState.value = 'error'
  } finally {
    loading.value = false
  }
}

function openDialog(row?: OpenSourceTextAdItem) {
  if (!canMutate.value) return
  isEdit.value = !!row
  if (row) {
    Object.assign(form, {
      id: row.id,
      title: row.title,
      summary: row.summary,
      badge: row.badge,
      linkUrl: row.linkUrl,
      enabled: row.enabled,
      sortOrder: row.sortOrder
    })
  } else {
    Object.assign(form, defaultForm())
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!canMutate.value) {
    ElMessage.warning('文字广告尚未成功读取，当前不能保存')
    return
  }
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value && !form.id) {
      ElMessage.error('广告标识缺失，无法安全更新')
      return
    }
    if (isEdit.value) {
      await updateOpenSourceTextAd({ ...form })
    } else {
      await saveOpenSourceTextAd({ ...form })
    }
    ElMessage.success(isEdit.value ? '文本广告更新成功' : '文本广告创建成功')
    dialogVisible.value = false
    await loadList()
  } catch (error: any) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: OpenSourceTextAdItem) {
  if (!row.id || !canMutate.value) {
    ElMessage.error('广告标识缺失或列表不可用，无法安全删除')
    return
  }
  try {
    await ElMessageBox.confirm('确定删除这条文本广告？删除后将不再出现在开源版首页右侧广告区域。', '确认删除', { type: 'warning' })
    await deleteOpenSourceTextAd(row.id)
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
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}
.summary-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
  padding: 16px 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #f5f8ff 100%);
}
.summary-card strong {
  display: block;
  color: #17315c;
  font-size: 22px;
  line-height: 1.2;
}
.summary-card span {
  display: block;
  margin-top: 8px;
  color: var(--art-gray-500);
  font-size: 12px;
}
.page-grid {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
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
.preview-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.preview-item {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid #dce8f8;
  background: linear-gradient(180deg, #fff, #f8fbff);
}
.preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.preview-head strong {
  color: #173052;
  font-size: 13px;
}
.preview-head i {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: #edf5ff;
  color: #2f74f6;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}
.preview-item p {
  margin: 8px 0 0;
  color: #63758f;
  font-size: 12px;
  line-height: 1.7;
}
.preview-link {
  display: block;
  margin-top: 8px;
  color: #0d6bff;
  font-size: 12px;
  word-break: break-all;
}
.text-ellipsis {
  display: inline-block;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 1180px) {
  .page-grid,
  .summary-grid {
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
