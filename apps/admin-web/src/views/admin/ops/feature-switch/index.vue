<!-- 系统运维 - 功能管理页面 -->
<template>
  <div class="feature-switch-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>功能管理</h2>
          <p>控制前台各功能页面的访问开关与最低账号等级。关闭后用户在前台访问该页面时会提示"暂未开放"；等级不足时会提示需要升级。</p>
        </div>
        <div class="toolbar-actions">
          <ElButton :disabled="configState !== 'ready'" @click="loadConfig">
            <ElIcon><RefreshRight /></ElIcon>刷新
          </ElButton>
          <ElButton :disabled="configState !== 'ready'" @click="handleInit" :loading="initializing">
            初始化默认
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
      title="正在读取功能开关配置"
      description="读取完成前不会开放编辑和保存。"
    />
    <AdminDataState
      v-else-if="configState === 'error'"
      state="error"
      title="功能开关配置暂不可用"
      :description="configError"
      retry-text="重新读取"
      @retry="loadConfig"
    />

    <template v-else>
      <ElCard
        v-for="group in orderedGroups"
        :key="group.key"
        shadow="never"
        class="table-card"
      >
        <h4 class="section-title">{{ group.label }}</h4>
        <div class="feature-rows">
          <div
            v-for="item in featuresByGroup[group.key] || []"
            :key="item.key"
            class="feature-row"
          >
            <div class="feature-info">
              <span class="feature-title">{{ item.title || item.key }}</span>
              <span class="feature-key">{{ item.key }}</span>
            </div>
            <div class="feature-controls">
              <ElSwitch
                v-model="item.enabled"
                :active-value="true"
                :inactive-value="false"
                active-text="启用"
                inactive-text="停用"
                inline-prompt
              />
              <ElSelect
                v-model="item.minLevel"
                placeholder="最低等级"
                style="width: 140px"
                :disabled="!item.enabled"
              >
                <ElOption label="普通用户" value="normal" />
                <ElOption label="VIP" value="vip" />
                <ElOption label="SVP" value="svp" />
              </ElSelect>
            </div>
          </div>
          <div v-if="!(featuresByGroup[group.key] || []).length" class="empty-group">
            暂无功能项
          </div>
        </div>
      </ElCard>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshRight, Check } from '@element-plus/icons-vue'
import AdminDataState from '@/components/business/admin-data-state/index.vue'
import {
  fetchGetFeatureSwitches,
  fetchSaveFeatureSwitches,
  fetchInitFeatureSwitches,
  type FeatureSwitchItem
} from '@/api/feature-switch'

defineOptions({ name: 'AdminFeatureSwitch' })

interface FeatureGroup {
  key: string
  label: string
}

const GROUPS: FeatureGroup[] = [
  { key: 'overview', label: '概览' },
  { key: 'account', label: '账号与商品' },
  { key: 'message', label: '消息与商机' },
  { key: 'automation', label: '自动化' },
  { key: 'system', label: '系统设置' },
  { key: 'hidden', label: '会员' },
  { key: 'misc', label: '其他' }
]

const saving = ref(false)
const initializing = ref(false)
const configState = ref<'loading' | 'ready' | 'error'>('loading')
const configError = ref('')
const features = reactive<FeatureSwitchItem[]>([])

const featuresByGroup = computed(() => {
  const map: Record<string, FeatureSwitchItem[]> = {}
  for (const f of features) {
    const g = f.group || 'misc'
    if (!map[g]) map[g] = []
    map[g].push(f)
  }
  return map
})

const orderedGroups = computed(() => GROUPS)

async function loadConfig() {
  configState.value = 'loading'
  configError.value = ''
  try {
    const list = await fetchGetFeatureSwitches()
    features.splice(0, features.length, ...list)
    configState.value = 'ready'
  } catch (e: any) {
    configError.value = e?.message || '请求失败，请稍后重试。'
    configState.value = 'error'
  }
}

async function handleSave() {
  if (saving.value) return
  saving.value = true
  try {
    await fetchSaveFeatureSwitches(features.map(f => ({ ...f })))
    ElMessage.success('功能开关配置已保存')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

async function handleInit() {
  try {
    await ElMessageBox.confirm(
      '将写入默认配置（全部开启 + 普通用户可访问）。若已存在配置则保持不变。是否继续？',
      '初始化默认配置',
      { type: 'warning', confirmButtonText: '继续', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  if (initializing.value) return
  initializing.value = true
  try {
    await fetchInitFeatureSwitches()
    ElMessage.success('默认配置已就绪')
    await loadConfig()
  } catch (e: any) {
    ElMessage.error(e?.message || '初始化失败，请稍后重试')
  } finally {
    initializing.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.feature-switch-page { padding: 16px; }
.filter-card { margin-bottom: 16px; }
.page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 0;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.toolbar-actions { display: flex; gap: 8px; }
.table-card { margin-bottom: 16px; }
.section-title { margin: 0 0 12px; font-size: 15px; font-weight: 600; }
.feature-rows { display: flex; flex-direction: column; gap: 8px; }
.feature-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-blank);
}
.feature-info { display: flex; flex-direction: column; gap: 2px; }
.feature-title { font-size: 14px; font-weight: 500; }
.feature-key { font-size: 12px; color: var(--el-text-color-secondary); }
.feature-controls { display: flex; align-items: center; gap: 12px; }
.empty-group { padding: 16px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 13px; }
</style>
