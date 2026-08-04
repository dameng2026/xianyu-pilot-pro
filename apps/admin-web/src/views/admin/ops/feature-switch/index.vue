<!-- 系统运维 - 功能管理页面（表格布局：功能列 + 普通用户/VIP（单店版）/VIP/SVP 四档 + 店铺数量首行） -->
<template>
  <div class="feature-switch-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>功能管理</h2>
          <p>按账号等级控制前台各功能页面的访问开关。第一行为「店铺数量」：填写各等级可绑定的闲鱼店铺数，0 表示无限制（普通用户 1 / VIP 单店版 1 / VIP 不限 / SVIP 不限）。后续功能行分别控制普通用户、VIP（单店版）、VIP、SVP 四档的独立开关；VIP（单店版）与 VIP 功能权限保持一致，随 VIP 开关联动。"全部"为快捷开关：开启时三列全部打开，关闭时三列全部关闭。"维护"列开启后，所有用户进入该页面都会弹窗提示"正在维护升级中"，优先级高于等级开关。"限制模式"列为单选：无限制（默认正常使用）/ 预览模式（可进入页面查看数据、调整配置，但不可执行业务操作如运行/发送）/ 不可进入（直接无法访问该页面）。优先级：维护 &gt; 限制模式=不可进入 &gt; 等级开关 &gt; 限制模式=预览。</p>
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
              <ElInputNumber
                v-if="isStoreLimitRow(row as FeatureSwitchItem)"
                v-model="row.storeLimitNormal"
                :min="0"
                :max="999"
                :controls="false"
                size="small"
                style="width:76px"
                :title="'普通用户店铺数量（0=无限制）'"
                @change="onStoreLimitChange(row as FeatureSwitchItem, 'storeLimitNormal')"
              />
              <ElSwitch v-else v-model="row.normal" :active-value="true" :inactive-value="false" inline-prompt active-text="开" inactive-text="关" @change="onLevelChange(row as FeatureSwitchItem)" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="VIP（单店版）" width="130" align="center">
            <template #default="{ row }">
              <ElInputNumber
                v-if="isStoreLimitRow(row as FeatureSwitchItem)"
                v-model="row.storeLimitVipSingle"
                :min="0"
                :max="999"
                :controls="false"
                size="small"
                style="width:76px"
                :title="'VIP（单店版）店铺数量（0=无限制）'"
                @change="onStoreLimitChange(row as FeatureSwitchItem, 'storeLimitVipSingle')"
              />
              <ElTooltip v-else content="VIP（单店版）与 VIP 功能权限保持一致，随 VIP 开关联动" placement="top">
                <span class="vip-single-mirror">
                  <ElSwitch :model-value="row.vip" disabled inline-prompt active-text="同VIP" inactive-text="关" />
                </span>
              </ElTooltip>
            </template>
          </ElTableColumn>
          <ElTableColumn label="VIP" width="110" align="center">
            <template #default="{ row }">
              <ElInputNumber
                v-if="isStoreLimitRow(row as FeatureSwitchItem)"
                v-model="row.storeLimitVip"
                :min="0"
                :max="999"
                :controls="false"
                size="small"
                style="width:76px"
                :title="'VIP 店铺数量（0=无限制）'"
                @change="onStoreLimitChange(row as FeatureSwitchItem, 'storeLimitVip')"
              />
              <ElSwitch v-else v-model="row.vip" :active-value="true" :inactive-value="false" inline-prompt active-text="开" inactive-text="关" @change="onLevelChange(row as FeatureSwitchItem)" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="SVP" width="110" align="center">
            <template #default="{ row }">
              <ElInputNumber
                v-if="isStoreLimitRow(row as FeatureSwitchItem)"
                v-model="row.storeLimitSvp"
                :min="0"
                :max="999"
                :controls="false"
                size="small"
                style="width:76px"
                :title="'SVIP 店铺数量（0=无限制）'"
                @change="onStoreLimitChange(row as FeatureSwitchItem, 'storeLimitSvp')"
              />
              <ElSwitch v-else v-model="row.svp" :active-value="true" :inactive-value="false" inline-prompt active-text="开" inactive-text="关" @change="onLevelChange(row as FeatureSwitchItem)" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="全部" width="110" align="center">
            <template #default="{ row }">
              <span v-if="isStoreLimitRow(row as FeatureSwitchItem)" class="reason-placeholder">—</span>
              <ElSwitch
                v-else
                :model-value="isAllOn(row as FeatureSwitchItem)"
                :active-value="true"
                :inactive-value="false"
                inline-prompt
                active-text="开"
                inactive-text="关"
                @change="(val: boolean) => onAllChange(row as FeatureSwitchItem, val)"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn label="维护" width="100" align="center">
            <template #default="{ row }">
              <span v-if="isStoreLimitRow(row as FeatureSwitchItem)" class="reason-placeholder">—</span>
              <ElSwitch
                v-else
                v-model="row.maintenance"
                :active-value="true"
                :inactive-value="false"
                inline-prompt
                active-text="维护"
                inactive-text="—"
                class="maintenance-switch"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn label="限制模式" width="130" align="center">
            <template #default="{ row }">
              <span v-if="isStoreLimitRow(row as FeatureSwitchItem)" class="reason-placeholder">—</span>
              <ElSelect
                v-else
                v-model="row.limitMode"
                size="small"
                :class="['limit-mode-select', `limit-mode-${row.limitMode || 'none'}`]"
                popper-class="limit-mode-popper"
              >
                <ElOption label="无限制" value="none" />
                <ElOption label="预览模式" value="preview" />
                <ElOption label="不可进入" value="blocked" />
              </ElSelect>
            </template>
          </ElTableColumn>
          <ElTableColumn label="关闭原因" min-width="240">
            <template #default="{ row }">
              <ElInput
                v-if="row.key === 'manual-slider-solve'"
                v-model="row.reason"
                type="textarea"
                :rows="1"
                :disabled="isAllOn(row as FeatureSwitchItem)"
                placeholder="选填，被拦截时展示给用户。如：会员专属功能，升级 VIP 即可使用"
                maxlength="120"
                show-word-limit
                resize="none"
              />
              <span v-else class="reason-placeholder">—</span>
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

/** 是否为「店铺数量」配置行（数字配置，不参与开关控制） */
function isStoreLimitRow(row: FeatureSwitchItem): boolean {
  return row?.key === 'store-limit'
}

/** 店铺数量输入归一化：非法值回退为 0（0=无限制） */
function onStoreLimitChange(row: FeatureSwitchItem, field: 'storeLimitNormal' | 'storeLimitVipSingle' | 'storeLimitVip' | 'storeLimitSvp') {
  const value = Number(row[field])
  row[field] = Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0
}

/** 判断某功能三个级别是否全部开启 */
function isAllOn(row: FeatureSwitchItem): boolean {
  if (isStoreLimitRow(row)) return false
  return row.normal === true && row.vip === true && row.svp === true
}

/** 单个级别开关变化时无需额外处理（"全部"列由 isAllOn 自动计算） */
function onLevelChange(_row: FeatureSwitchItem) {
  // 空函数：单个级别变化时"全部"列的显示由 :model-value="isAllOn(row)" 自动更新
}

/** "全部"开关变化时：开启→三列全开；关闭→三列全关 */
function onAllChange(row: FeatureSwitchItem, val: boolean) {
  if (isStoreLimitRow(row)) return
  row.normal = val
  row.vip = val
  row.svp = val
  row.vipSingle = val
}

async function loadConfig() {
  configState.value = 'loading'
  configError.value = ''
  try {
    const list = await fetchGetFeatureSwitches()
    // 兜底：确保 limitMode 字段有默认值（后端已返回，但向前兼容旧数据）
    const normalized = list.map(f => ({
      ...f,
      limitMode: (f.limitMode === 'preview' || f.limitMode === 'blocked') ? f.limitMode : 'none' as 'none' | 'preview' | 'blocked'
    }))
    features.splice(0, features.length, ...normalized)
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
.reason-placeholder { color: var(--el-text-color-placeholder); font-size: 13px; }
.vip-single-mirror { display: inline-flex; cursor: help; }
.empty-state { padding: 16px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 13px; }
/* 维护开关：开启时使用红色（danger）醒目提示 */
.maintenance-switch.is-checked :deep(.el-switch__core) {
  background-color: var(--el-color-danger) !important;
  border-color: var(--el-color-danger) !important;
}
.maintenance-switch :deep(.el-switch__label) {
  color: var(--el-color-danger);
}
/* 限制模式下拉框：按模式着色，便于管理员快速识别 */
.limit-mode-select :deep(.el-input__wrapper) {
  border-radius: 8px;
}
.limit-mode-preview :deep(.el-input__wrapper) {
  background-color: var(--el-color-warning-light-9);
  box-shadow: 0 0 0 1px var(--el-color-warning-light-5) inset;
}
.limit-mode-preview :deep(.el-input__inner) {
  color: var(--el-color-warning-dark-2);
  font-weight: 600;
}
.limit-mode-blocked :deep(.el-input__wrapper) {
  background-color: var(--el-color-danger-light-9);
  box-shadow: 0 0 0 1px var(--el-color-danger-light-5) inset;
}
.limit-mode-blocked :deep(.el-input__inner) {
  color: var(--el-color-danger);
  font-weight: 600;
}
.limit-mode-none :deep(.el-input__inner) {
  color: var(--el-text-color-secondary);
}
</style>
