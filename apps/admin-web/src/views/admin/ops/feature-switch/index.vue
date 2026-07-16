<!-- 系统运维 - 功能管理页面（表格布局：功能列 + 普通用户/VIP/SVP/全部 四列开关） -->
<template>
  <div class="feature-switch-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>功能管理</h2>
          <p>按账号等级控制前台各功能页面的访问开关。第一列为功能名称，后续列分别为普通用户、VIP、SVP 的独立开关，最后一列"全部"为快捷开关：开启时三列全部打开，关闭时三列全部关闭。关闭"全部"后可单独控制各级别。</p>
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
        <ElTable :data="featuresByGroup[group.key] || []" border stripe size="small">
          <ElTableColumn label="功能" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="feature-cell">
                <span class="feature-title">{{ row.title || row.key }}</span>
                <span class="feature-key">{{ row.key }}</span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="普通用户" width="110" align="center">
            <template #default="{ row }">
              <ElSwitch v-model="row.normal" :active-value="true" :inactive-value="false" inline-prompt active-text="开" inactive-text="关" @change="onLevelChange(row)" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="VIP" width="110" align="center">
            <template #default="{ row }">
              <ElSwitch v-model="row.vip" :active-value="true" :inactive-value="false" inline-prompt active-text="开" inactive-text="关" @change="onLevelChange(row)" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="SVP" width="110" align="center">
            <template #default="{ row }">
              <ElSwitch v-model="row.svp" :active-value="true" :inactive-value="false" inline-prompt active-text="开" inactive-text="关" @change="onLevelChange(row)" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="全部" width="110" align="center">
            <template #default="{ row }">
              <ElSwitch
                :model-value="isAllOn(row)"
                :active-value="true"
                :inactive-value="false"
                inline-prompt
                active-text="开"
                inactive-text="关"
                @change="(val: boolean) => onAllChange(row, val)"
              />
            </template>
          </ElTableColumn>
          <template #empty>
            <div class="empty-state">暂无功能项</div>
          </template>
        </ElTable>
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

/** 判断某功能三个级别是否全部开启 */
function isAllOn(row: FeatureSwitchItem): boolean {
  return row.normal === true && row.vip === true && row.svp === true
}

/** 单个级别开关变化时无需额外处理（"全部"列由 isAllOn 自动计算） */
function onLevelChange(_row: FeatureSwitchItem) {
  // 空函数：单个级别变化时"全部"列的显示由 :model-value="isAllOn(row)" 自动更新
}

/** "全部"开关变化时：开启→三列全开；关闭→三列全关 */
function onAllChange(row: FeatureSwitchItem, val: boolean) {
  row.normal = val
  row.vip = val
  row.svp = val
}

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
      '将写入默认配置（全部开启）。若已存在配置则保持不变。是否继续？',
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
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; max-width: 720px; }
.toolbar-actions { display: flex; gap: 8px; flex-shrink: 0; }
.table-card { margin-bottom: 16px; }
.section-title { margin: 0 0 12px; font-size: 15px; font-weight: 600; }
.feature-cell { display: flex; flex-direction: column; gap: 2px; }
.feature-title { font-size: 14px; font-weight: 500; }
.feature-key { font-size: 12px; color: var(--el-text-color-secondary); }
.empty-state { padding: 16px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 13px; }
</style>
