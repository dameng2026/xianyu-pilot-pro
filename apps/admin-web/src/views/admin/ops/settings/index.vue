<!-- 系统运维 - 系统配置页面 -->
<template>
  <div class="admin-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>系统配置</h2>
          <p>全局配置项，包括网站信息、LOGO、地图密钥、备案号及联系方式</p>
        </div>
        <div class="toolbar-actions">
          <ElButton :disabled="configState !== 'ready'" @click="handleReset">
            <ElIcon><RefreshRight /></ElIcon>重置
          </ElButton>
          <ElButton type="primary" :disabled="configState !== 'ready'" @click="handleSave" :loading="saving">
            <ElIcon><Check /></ElIcon>保存配置
          </ElButton>
        </div>
      </div>
    </ElCard>

    <AdminDataState
      v-if="configState === 'loading'"
      state="loading"
      title="正在读取系统配置"
      description="读取完成前不会开放编辑和保存。"
    />
    <AdminDataState
      v-else-if="configState === 'error'"
      state="error"
      title="系统配置暂不可用"
      :description="configError"
      retry-text="重新读取"
      @retry="loadConfig"
    />

    <template v-else>
    <!-- 基础信息 -->
    <ElCard shadow="never" class="table-card">
      <h4 class="section-title">基础信息</h4>
      <ElForm
        :model="form"
        :rules="rules"
        ref="baseFormRef"
        label-width="150px"
        label-position="right"
        class="config-form"
      >
        <ElFormItem label="网站名称" prop="siteName">
          <ElInput
            v-model="form.siteName"
            placeholder="如：闲鱼助手后台管理系统"
            style="width: 100%; max-width: 500px"
            maxlength="50"
            show-word-limit
          />
        </ElFormItem>

        <ElFormItem label="系统LOGO" prop="logoUrl">
          <div class="logo-upload-area">
            <div class="logo-preview" v-if="form.logoUrl">
              <ElImage
                :src="form.logoUrl"
                fit="contain"
                style="width: 140px; height: 64px"
                :preview-src-list="[form.logoUrl]"
                preview-teleported
              />
              <div class="logo-actions">
                <ElButton size="small" type="primary" @click="triggerUpload">替换LOGO</ElButton>
                <ElButton size="small" type="danger" plain @click="handleRemoveLogo">移除</ElButton>
              </div>
            </div>
            <ElUpload
              v-show="!form.logoUrl"
              ref="uploadRef"
              :show-file-list="false"
              :before-upload="beforeLogoUpload"
              :http-request="handleLogoUpload"
              accept="image/png,image/jpeg"
              drag
            >
              <ElIcon class="upload-icon"><UploadFilled /></ElIcon>
              <div class="upload-text">
                <span>将LOGO拖到此处，或</span>
                <em>点击上传</em>
              </div>
              <template #tip>
                <div class="upload-tip">PNG、JPEG，建议尺寸 200x60，不超过 2MB</div>
              </template>
            </ElUpload>
          </div>
        </ElFormItem>

        <ElFormItem label="ICP备案号" prop="icpFilingNo">
          <ElInput
            v-model="form.icpFilingNo"
            placeholder="如：京ICP备XXXXXXXX号-1"
            style="width: 100%; max-width: 500px"
            maxlength="50"
          />
        </ElFormItem>

        <ElFormItem label="公安备案号" prop="psbFilingNo">
          <ElInput
            v-model="form.psbFilingNo"
            placeholder="如：京公网安备 XXXXXXXXXXXX号"
            style="width: 100%; max-width: 500px"
            maxlength="50"
          />
        </ElFormItem>
      </ElForm>
    </ElCard>

    <!-- 数据保留策略 -->
    <ElCard shadow="never" class="table-card mt-16">
      <h4 class="section-title">数据保留策略</h4>
      <AdminDataState
        v-if="retentionState === 'loading'"
        state="loading"
        title="正在读取数据保留策略"
        description="读取完成前不会开放编辑和保存。"
      />
      <AdminDataState
        v-else-if="retentionState === 'error'"
        state="error"
        title="数据保留策略暂不可用"
        :description="retentionError"
        retry-text="重新读取"
        @retry="loadRetentionConfig"
      />
      <ElForm v-else :model="retentionForm" label-width="150px" label-position="right" class="config-form">
        <ElFormItem label="启用定时清理">
          <ElSwitch v-model="retentionForm.enabled" />
          <span class="form-tip">关闭后所有定时清理任务停止执行</span>
        </ElFormItem>

        <ElFormItem label="保留天数">
          <ElInputNumber
            v-model="retentionForm.retentionDays"
            :min="1"
            :max="365"
            :step="1"
            controls-position="right"
            style="width: 160px"
          />
          <span class="form-tip">超过此天数的旧数据将被定时清理（范围 1-365，默认 14）</span>
        </ElFormItem>

        <ElFormItem label="清理时间">
          <ElInput
            :model-value="retentionForm.cleanupCron"
            readonly
            style="width: 240px"
          />
          <span class="form-tip">cron 表达式，默认每日凌晨 04:00，暂不开放编辑</span>
        </ElFormItem>

        <ElFormItem label="可清理类别">
          <div class="retention-categories">
            <div v-for="cat in categoryList" :key="cat.key" class="retention-cat-item">
              <ElSwitch v-model="retentionForm.categories[cat.key]" />
              <span class="retention-cat-label">{{ cat.label }}</span>
            </div>
          </div>
          <div class="form-tip retention-protect-tip">
            受保护数据（订单、Token 消耗、会员充值、用户账号等）永不清理。
            聊天记录清理后可从闲鱼重新加载历史消息。
          </div>
        </ElFormItem>

        <ElFormItem v-if="retentionForm.lastCleanup" label="最近清理统计">
          <div class="retention-last-cleanup">
            <span>时间：{{ formatCleanupTime(retentionForm.lastCleanup.time) }}</span>
            <span>累计删除：{{ retentionForm.lastCleanup.totalDeleted }} 条</span>
            <span v-if="Object.keys(retentionForm.lastCleanup.byCategory || {}).length > 0">
              明细：{{ formatByCategory(retentionForm.lastCleanup.byCategory) }}
            </span>
          </div>
        </ElFormItem>

        <ElFormItem>
          <div class="retention-actions">
            <ElButton
              type="primary"
              :disabled="retentionState !== 'ready'"
              :loading="retentionSaving"
              @click="handleSaveRetention"
            >
              保存配置
            </ElButton>
            <ElButton
              type="warning"
              plain
              :disabled="retentionState !== 'ready'"
              :loading="retentionRunning"
              @click="handleRunCleanupNow"
            >
              立即清理一次
            </ElButton>
          </div>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <!-- 联系方式 -->
    <ElCard shadow="never" class="table-card mt-16">
      <h4 class="section-title">联系方式</h4>
      <ElForm
        :model="form"
        :rules="rules"
        ref="contactFormRef"
        label-width="150px"
        label-position="right"
        class="config-form"
      >
        <ElFormItem label="客服电话" prop="contactPhone">
          <ElInput
            v-model="form.contactPhone"
            placeholder="如：400-123-4567"
            style="width: 100%; max-width: 400px"
            maxlength="20"
          />
        </ElFormItem>

        <ElFormItem label="客服邮箱" prop="contactEmail">
          <ElInput
            v-model="form.contactEmail"
            placeholder="如：support@xianyu.local"
            style="width: 100%; max-width: 400px"
            maxlength="100"
          />
        </ElFormItem>

        <ElFormItem label="工作时间" prop="workHours">
          <ElInput
            v-model="form.workHours"
            placeholder="如：周一至周五 9:00-18:00"
            style="width: 100%; max-width: 400px"
            maxlength="50"
          />
        </ElFormItem>

        <ElFormItem label="公司地址" prop="companyAddress">
          <ElInput
            v-model="form.companyAddress"
            placeholder="请输入公司地址"
            style="width: 100%; max-width: 600px"
            maxlength="200"
          />
        </ElFormItem>

        <ElFormItem label="微信公众号" prop="wechatOfficial">
          <ElInput
            v-model="form.wechatOfficial"
            placeholder="微信公众号名称"
            style="width: 100%; max-width: 400px"
            maxlength="50"
          />
        </ElFormItem>
      </ElForm>
    </ElCard>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Check, RefreshRight } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadRequestOptions } from 'element-plus'
import request from '@/utils/http'
import AdminDataState from '@/components/business/admin-data-state/index.vue'
import {
  fetchGetRetentionConfig,
  fetchSaveRetentionConfig,
  fetchRunRetentionCleanup,
  type RetentionPolicyConfig
} from '@/api/system-manage'

defineOptions({ name: 'AdminSystemSettings' })

interface SystemConfigForm {
  siteName: string
  logoUrl: string
  icpFilingNo: string
  psbFilingNo: string
  contactPhone: string
  contactEmail: string
  workHours: string
  companyAddress: string
  wechatOfficial: string
}

const baseFormRef = ref<FormInstance>()
const contactFormRef = ref<FormInstance>()
const uploadRef = ref()
const saving = ref(false)
const configState = ref<'loading' | 'ready' | 'error'>('loading')
const configError = ref('')
let loadedSnapshot: SystemConfigForm | null = null

const form = reactive<SystemConfigForm>({
  siteName: '',
  logoUrl: '',
  icpFilingNo: '',
  psbFilingNo: '',
  contactPhone: '',
  contactEmail: '',
  workHours: '',
  companyAddress: '',
  wechatOfficial: ''
})

const rules: FormRules = {
  siteName: [
    { required: true, message: '请输入网站名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度 2 到 50 个字符', trigger: 'blur' }
  ],
  icpFilingNo: [{ max: 50, message: '不能超过 50 个字符', trigger: 'blur' }],
  psbFilingNo: [{ max: 50, message: '不能超过 50 个字符', trigger: 'blur' }],
  contactPhone: [{ pattern: /^[\d\-()（）+\s]*$/, message: '请输入正确的电话号码', trigger: 'blur' }],
  contactEmail: [{ type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }]
}

// ==================== 数据保留策略 ====================
const retentionState = ref<'loading' | 'ready' | 'error'>('loading')
const retentionError = ref('')
const retentionSaving = ref(false)
const retentionRunning = ref(false)

const categoryList = [
  { key: 'operationLog' as const, label: '操作日志' },
  { key: 'clientErrorLog' as const, label: '前端错误日志' },
  { key: 'notificationLog' as const, label: '通知投递日志' },
  { key: 'notificationDedup' as const, label: '通知去重表' },
  { key: 'chatMessage' as const, label: '聊天消息（可重新拉取）' },
  { key: 'captchaRecord' as const, label: '滑块求解记录' },
  { key: 'autoReplyLog' as const, label: '自动回复日志' },
  { key: 'uploadRateEvent' as const, label: '上传限流计数' }
]

interface RetentionForm {
  enabled: boolean
  retentionDays: number
  cleanupCron: string
  categories: {
    operationLog: boolean
    clientErrorLog: boolean
    notificationLog: boolean
    notificationDedup: boolean
    chatMessage: boolean
    captchaRecord: boolean
    autoReplyLog: boolean
    uploadRateEvent: boolean
  }
  lastCleanup: { time: string; totalDeleted: number; byCategory: Record<string, number> } | null
}

const retentionForm = reactive<RetentionForm>({
  enabled: true,
  retentionDays: 14,
  cleanupCron: '0 0 4 * * ?',
  categories: {
    operationLog: true,
    clientErrorLog: true,
    notificationLog: true,
    notificationDedup: true,
    chatMessage: true,
    captchaRecord: true,
    autoReplyLog: true,
    uploadRateEvent: true
  },
  lastCleanup: null
})

const categoryLabelMap: Record<string, string> = Object.fromEntries(
  categoryList.map(c => [c.key, c.label])
)

async function loadRetentionConfig() {
  retentionState.value = 'loading'
  retentionError.value = ''
  try {
    const res = await fetchGetRetentionConfig()
    retentionForm.enabled = res.enabled !== false
    retentionForm.retentionDays = res.retentionDays ?? 14
    retentionForm.cleanupCron = res.cleanupCron ?? '0 0 4 * * ?'
    const cats = res.categories || {}
    for (const cat of categoryList) {
      retentionForm.categories[cat.key] = cats[cat.key] !== false
    }
    retentionForm.lastCleanup = res.lastCleanup || null
    retentionState.value = 'ready'
  } catch (error: any) {
    retentionError.value = error?.message || '读取失败，请检查网络或服务状态后重试。'
    retentionState.value = 'error'
  }
}

async function handleSaveRetention() {
  if (retentionState.value !== 'ready') {
    ElMessage.error('数据保留策略尚未成功读取，已阻止保存')
    return
  }
  retentionSaving.value = true
  try {
    await fetchSaveRetentionConfig({
      enabled: retentionForm.enabled,
      retentionDays: retentionForm.retentionDays,
      cleanupCron: retentionForm.cleanupCron,
      categories: { ...retentionForm.categories }
    })
    ElMessage.success('数据保留策略保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    retentionSaving.value = false
  }
}

async function handleRunCleanupNow() {
  try {
    await ElMessageBox.confirm(
      '立即执行一次数据清理？此操作将按当前配置删除超过保留期的旧数据，不可撤销。',
      '确认清理',
      { type: 'warning', confirmButtonText: '立即清理', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  retentionRunning.value = true
  try {
    const res = await fetchRunRetentionCleanup()
    const total = res?.totalDeleted ?? 0
    ElMessage.success(`清理完成，共删除 ${total} 条旧数据`)
    await loadRetentionConfig()
  } catch (e: any) {
    ElMessage.error(e.message || '清理失败')
  } finally {
    retentionRunning.value = false
  }
}

function formatCleanupTime(time: string): string {
  if (!time) return '-'
  try {
    return new Date(time).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return time
  }
}

function formatByCategory(byCategory: Record<string, number>): string {
  if (!byCategory) return ''
  return Object.entries(byCategory)
    .filter(([_, count]) => count > 0)
    .map(([key, count]) => `${categoryLabelMap[key] || key}: ${count}`)
    .join('，')
}

// 加载配置
async function loadConfig() {
  configState.value = 'loading'
  configError.value = ''
  try {
    const res = await request.get<SystemConfigForm>({ url: '/system/config' })
    if (!res) throw new Error('服务未返回系统配置')
    const loaded: SystemConfigForm = {
      siteName: res.siteName ?? '',
      logoUrl: res.logoUrl ?? '',
      icpFilingNo: res.icpFilingNo ?? '',
      psbFilingNo: res.psbFilingNo ?? '',
      contactPhone: res.contactPhone ?? '',
      contactEmail: res.contactEmail ?? '',
      workHours: res.workHours ?? '',
      companyAddress: res.companyAddress ?? '',
      wechatOfficial: res.wechatOfficial ?? ''
    }
    Object.assign(form, loaded)
    loadedSnapshot = { ...loaded }
    configState.value = 'ready'
  } catch (error: any) {
    loadedSnapshot = null
    configError.value = error?.message || '读取失败，请检查网络或服务状态后重试。'
    configState.value = 'error'
  }
}

// 保存配置
async function handleSave() {
  if (configState.value !== 'ready') {
    ElMessage.error('系统配置尚未成功读取，已阻止保存以保护线上配置')
    return
  }
  const v1 = await baseFormRef.value?.validate().catch(() => false)
  const v3 = await contactFormRef.value?.validate().catch(() => false)
  if (!v1 || !v3) return

  saving.value = true
  try {
    await request.post({ url: '/system/config', data: form })
    loadedSnapshot = { ...form }
    ElMessage.success('系统配置保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  if (!loadedSnapshot) return
  Object.assign(form, loadedSnapshot)
  baseFormRef.value?.clearValidate()
  contactFormRef.value?.clearValidate()
  ElMessage.info('已恢复为最近一次成功读取的配置')
}

function triggerUpload() {
  uploadRef.value?.$el?.querySelector('input[type="file"]')?.click()
}

function beforeLogoUpload(file: File) {
  const validType = ['image/png', 'image/jpeg'].includes(file.type)
  if (!validType) { ElMessage.error('仅支持 PNG、JPEG 格式'); return false }
  if (file.size / 1024 / 1024 > 2) { ElMessage.error('图片大小不能超过 2MB'); return false }
  return true
}

async function handleLogoUpload(options: UploadRequestOptions) {
  const formData = new FormData()
  formData.append('file', options.file)
  try {
    const res = await request.post<{ url: string }>({ url: '/system/config/upload-logo', data: formData })
    if (res && res.url) {
      form.logoUrl = res.url
      ElMessage.success('LOGO上传成功')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
  }
}

function handleRemoveLogo() {
  form.logoUrl = ''
  ElMessage.success('LOGO已移除，保存后生效')
}

onMounted(() => {
  loadConfig()
  loadRetentionConfig()
})
</script>

<style scoped lang="scss">
.admin-page { padding: 4px; }
.filter-card, .table-card { margin-bottom: 16px; border-radius: 16px; }
.mt-16 { margin-top: 16px; }
.page-title-row { display: flex; justify-content: space-between; gap: 16px; }
.page-title-row h2 { margin: 0 0 6px; font-size: 22px; font-weight: 800; }
.page-title-row p { margin: 0; color: var(--art-gray-500); }
.toolbar-actions { display: flex; align-items: center; gap: 10px; }

.section-title {
  font-size: 16px; font-weight: 700; margin: 0 0 20px;
  padding-bottom: 12px; border-bottom: 1px solid var(--el-border-color-lighter);
}

.config-form { max-width: 750px; }

.form-tip {
  font-size: 12px; color: var(--art-gray-500); margin-top: 4px;
  a { color: var(--el-color-primary); }
}

// LOGO上传
.logo-upload-area { display: flex; align-items: flex-start; }
.logo-preview {
  display: flex; align-items: center; gap: 16px;
  padding: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  background: var(--el-bg-color-page);
}
.logo-actions { display: flex; flex-direction: column; gap: 8px; }
.upload-icon { font-size: 34px; color: var(--el-color-primary); margin-bottom: 8px; }
.upload-text { font-size: 14px; color: var(--art-gray-700); }
.upload-text em { color: var(--el-color-primary); font-style: normal; }
.upload-tip { font-size: 12px; color: var(--art-gray-500); margin-top: 4px; }

// 数据保留策略
.retention-categories {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px 24px;
  width: 100%;
  max-width: 600px;
}
.retention-cat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.retention-cat-label {
  font-size: 14px;
  color: var(--art-gray-700);
}
.retention-protect-tip {
  margin-top: 8px;
  color: var(--el-color-warning);
}
.retention-last-cleanup {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--art-gray-700);
}
.retention-actions {
  display: flex;
  gap: 12px;
}
</style>
