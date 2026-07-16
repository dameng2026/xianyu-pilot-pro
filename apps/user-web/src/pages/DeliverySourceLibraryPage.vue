<template>
  <div>
    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <CardPanel title="货源库">
      <div class="toolbar">
        <input v-model="query.keyword" class="input" placeholder="搜索标题 / 正文 / 备注" @keyup.enter="loadSources" />
        <AppButton type="primary" @click="loadSources">搜索</AppButton>
        <AppButton :disabled="!sourcesAvailable" @click="openCreate">新增货源</AppButton>
      </div>

      <EmptyState v-if="loadError" variant="error" title="货源库暂时无法加载" :description="loadError">
        <template #actions><AppButton @click="loadSources">重新加载</AppButton></template>
      </EmptyState>
      <BaseTable v-else :columns="columns" :rows="rows" @row-click="selectSource">
        <template #title="{ row }">
          <div>
            <div class="strong">{{ row.title }}</div>
            <div class="subtle">{{ row.remark || '无备注' }}</div>
          </div>
        </template>
        <template #content="{ row }">
          <div class="content-preview">{{ row.content }}</div>
        </template>
        <template #usage="{ row }">
          <Badge>{{ row.usageCount ?? '—' }} 个商品</Badge>
        </template>
        <template #op="{ row }">
          <button class="link" @click.stop="editSource(row)">编辑</button>
          <button class="link" @click.stop="analyzeSource(row)">AI一键配置</button>
          <button class="link danger-text" @click.stop="removeSource(row)">删除</button>
        </template>
      </BaseTable>
    </CardPanel>

    <CardPanel v-if="editing" :title="editing.id ? '编辑货源' : '新增货源'" style="margin-top:16px">
      <div class="form-grid">
        <div class="form-row">
          <label>标题</label>
          <input v-model="form.title" class="input" placeholder="给用户和 AI 模型看的标题" />
        </div>
        <div class="form-row">
          <label>正文</label>
          <textarea v-model="form.content" rows="6" placeholder="实际发货文本内容"></textarea>
        </div>
        <div class="form-row">
          <label>备注</label>
          <textarea v-model="form.remark" rows="3" placeholder="可选备注"></textarea>
        </div>
      </div>
      <div class="toolbar" style="justify-content:flex-start">
        <AppButton type="primary" @click="saveSource">保存</AppButton>
        <AppButton @click="cancelEdit">取消</AppButton>
      </div>
    </CardPanel>

    <template v-if="selected">
      <CardPanel title="货源详情" style="margin-top:16px">
        <div class="source-summary">
          <div class="summary-item">
            <div class="summary-label">当前货源</div>
            <div class="summary-value">{{ selected.title || '-' }}</div>
          </div>
          <div class="summary-item">
            <div class="summary-label">已配置商品</div>
            <div class="summary-value">{{ goodsAvailable ? configuredGoods.length : '—' }}</div>
          </div>
          <div class="summary-item">
            <div class="summary-label">可选商品总数</div>
            <div class="summary-value">{{ goodsAvailable ? allGoods.length : '—' }}</div>
          </div>
        </div>
        <div class="subtle source-preview">{{ selected.content || '暂无正文内容' }}</div>
      </CardPanel>

      <CardPanel title="已配置商品" style="margin-top:16px">
        <div class="toolbar">
          <span class="subtle">用于查看当前货源已经绑定过的商品</span>
          <AppButton @click="refreshSelectedGoods">刷新商品列表</AppButton>
          <AppButton
            :disabled="!goodsAvailable || selectedConfiguredIds.length === 0"
            @click="batchRemoveConfiguredGoods"
          >批量删除</AppButton>
        </div>
        <EmptyState v-if="goodsLoading" title="正在加载商品数据" description="正在读取当前货源的已配置商品。" />
        <EmptyState v-else-if="goodsLoadError" variant="error" title="已配置商品暂时无法加载" :description="goodsLoadError">
          <template #actions><AppButton @click="refreshSelectedGoods">重新加载</AppButton></template>
        </EmptyState>
        <BaseTable
          v-else
          v-model:selected-keys="selectedConfiguredIds"
          :columns="configuredColumns"
          :rows="filteredConfiguredGoods"
          :selectable="true"
          :row-key="row => row.id"
        >
          <template #title="{ row }">
            <div class="goods-cell">
              <img v-if="goodsCover(row)" :src="goodsCover(row)" class="goods-thumb" alt="" />
              <div v-else class="goods-thumb placeholder"></div>
              <div class="goods-main">
                <div class="strong">{{ row.title }}</div>
                <div class="subtle">{{ row.category || '-' }}</div>
                <div class="account-chip">
                  <img v-if="accountAvatar(row)" :src="accountAvatar(row)" class="account-avatar" alt="" />
                  <div v-else class="account-avatar placeholder avatar-placeholder"></div>
                  <span class="subtle">{{ accountDisplayLabel(row) }}</span>
                </div>
              </div>
            </div>
          </template>
          <template #bind="{ row }">
            <Badge type="green">{{ bindStateLabel(row) }}</Badge>
          </template>
          <template #single="{ row }">
            <button class="link" :disabled="!goodsAvailable" @click.stop="applyOne(row)">再次配置</button>
            <button class="link danger-text" :disabled="!goodsAvailable" @click.stop="removeConfiguredGoods(row)">删除</button>
          </template>
        </BaseTable>
      </CardPanel>

      <CardPanel :title="goodsView === 'recommend' ? 'AI 推荐商品' : '商品列表'" style="margin-top:16px">
        <div class="toolbar">
          <input
            v-model="goodsKeyword"
            class="input"
            placeholder="搜索商品标题 / 分类"
            style="max-width:260px"
          />
          <AppButton :type="goodsView === 'all' ? 'primary' : 'default'" @click="showAllGoods">全部商品</AppButton>
          <AppButton :type="goodsView === 'recommend' ? 'primary' : 'default'" :disabled="!goodsAvailable" @click="showRecommendedGoods">智能推荐</AppButton>
          <AppButton type="primary" :disabled="!goodsAvailable" @click="analyzeSource(selected)">分析匹配商品</AppButton>
          <select v-model="applyTiming" class="input" style="max-width:200px" :disabled="!goodsAvailable">
            <option value="payDelivery">付款后发货</option>
            <option value="confirmDelivery">确认收货后赠送</option>
            <option value="reviewDelivery">好评后赠送</option>
          </select>
          <AppButton :disabled="!goodsAvailable || selectedGoodsIds.length === 0" @click="applySelectedGoods">批量配置</AppButton>
        </div>
        <div class="subtle" style="margin-bottom:12px">
          {{ goodsView === 'recommend' ? recommendedHint : '可先查看全部商品，再使用 AI 自动筛选高匹配商品。' }}
        </div>
        <EmptyState v-if="goodsLoading" title="正在加载商品数据" description="正在读取可配置商品。" />
        <EmptyState v-else-if="goodsLoadError" variant="error" title="商品列表暂时无法加载" :description="goodsLoadError">
          <template #actions><AppButton @click="refreshSelectedGoods">重新加载</AppButton></template>
        </EmptyState>
        <BaseTable
          v-else
          v-model:selected-keys="selectedGoodsIds"
          :columns="goodsColumns"
          :rows="filteredDisplayGoods"
          :selectable="true"
          :row-key="row => row.id"
        >
          <template #title="{ row }">
            <div class="goods-cell">
              <img v-if="goodsCover(row)" :src="goodsCover(row)" class="goods-thumb" alt="" />
              <div v-else class="goods-thumb placeholder"></div>
              <div class="goods-main">
                <div class="strong">{{ row.title }}</div>
                <div class="subtle">{{ row.category || '-' }}</div>
                <div class="account-chip">
                  <img v-if="accountAvatar(row)" :src="accountAvatar(row)" class="account-avatar" alt="" />
                  <div v-else class="account-avatar placeholder avatar-placeholder"></div>
                  <span class="subtle">{{ accountDisplayLabel(row) }}</span>
                </div>
              </div>
            </div>
          </template>
          <template #bind="{ row }">
            <Badge :type="row.configured ? 'green' : 'gray'">{{ bindStateLabel(row) }}</Badge>
          </template>
          <template #score="{ row }">
            <Badge :type="confidenceType(row.confidence, row.configured)">
              {{ confidenceLabel(row.confidence, row.configured) }}
            </Badge>
          </template>
          <template #reason="{ row }">
            <span class="subtle">{{ row.reason || (row.configured ? '该商品已配置当前货源' : '可手动配置') }}</span>
          </template>
          <template #single="{ row }">
            <button class="link" :disabled="!goodsAvailable" @click.stop="applyOne(row)">{{ row.configured ? '重新配置' : '配置到该商品' }}</button>
          </template>
        </BaseTable>
      </CardPanel>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import AppButton from '../components/AppButton.vue'
import Badge from '../components/Badge.vue'
import EmptyState from '../components/EmptyState.vue'
import {
  applyDeliverySourceToGoods,
  createDeliverySource,
  deleteDeliverySource,
  getDeliverySourceGoods,
  getDeliverySources,
  recommendDeliverySourceGoods,
  removeDeliverySourceFromGoods,
  updateDeliverySource
} from '../api/autoDelivery.js'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { confirmAction } from '../utils/confirmAction.js'
import { accountName } from '../utils/format.js'

const error = ref('')
const loadError = ref('')
const sourcesAvailable = ref(false)
const success = ref('')
const rows = ref([])
const selected = ref(null)
const editing = ref(null)
const configuredGoods = ref([])
const allGoods = ref([])
const recommendedGoods = ref([])
const goodsAvailable = ref(false)
const goodsLoading = ref(false)
const goodsLoadError = ref('')
const selectedGoodsIds = ref([])
const selectedConfiguredIds = ref([])
const applyTiming = ref('payDelivery')
const goodsKeyword = ref('')
const goodsView = ref('all')
const recommendedHint = ref('点击“分析匹配商品”后，将展示适配度较高的候选商品，并注明使用 AI 或本地规则。')

const query = reactive({
  keyword: '',
  current: 1,
  size: 20
})

const form = reactive({
  title: '',
  content: '',
  remark: ''
})

const columns = [
  { key: 'title', title: '货源信息' },
  { key: 'content', title: '正文' },
  { key: 'usage', title: '已配置商品' },
  { key: 'op', title: '操作' }
]

const configuredColumns = [
  { key: 'title', title: '商品' },
  { key: 'bind', title: '状态' },
  { key: 'single', title: '操作' }
]

const goodsColumns = [
  { key: 'title', title: '商品' },
  { key: 'bind', title: '配置状态' },
  { key: 'score', title: '匹配度' },
  { key: 'reason', title: 'AI/规则理由' },
  { key: 'single', title: '操作' }
]

const configuredGoodsIds = computed(() => new Set(configuredGoods.value.map(row => String(row.id))))

const normalizedConfiguredGoods = computed(() => decorateGoodsRows(configuredGoods.value, false))
const normalizedAllGoods = computed(() => decorateGoodsRows(allGoods.value, false))
const normalizedRecommendedGoods = computed(() => decorateGoodsRows(recommendedGoods.value, true))

const filteredConfiguredGoods = computed(() => normalizedConfiguredGoods.value.filter(matchesGoodsKeyword))

const filteredDisplayGoods = computed(() => {
  const rows = goodsView.value === 'recommend' ? normalizedRecommendedGoods.value : normalizedAllGoods.value
  return rows.filter(matchesGoodsKeyword)
})

function matchesGoodsKeyword(row) {
  const keyword = goodsKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return true
  }
  return [row.title, row.category, row.description, row.detailInfo]
    .filter(Boolean)
    .some(value => String(value).toLowerCase().includes(keyword))
}

function decorateGoodsRows(rows, fromAi) {
  return (rows || []).map(row => {
    const configured = configuredGoodsIds.value.has(String(row.id))
    return {
      ...row,
      account: accountOf(row),
      configured,
      confidence: row.confidence ?? null,
      reason: row.reason || (configured ? '该商品已配置当前货源' : (fromAi ? '推荐候选未返回匹配理由' : '可手动配置')),
      recommended: fromAi || Boolean(row.recommended)
    }
  })
}

function accountOf(row) {
  return row?.account || {
    id: row?.accountId,
    avatarUrl: row?.accountAvatarUrl || '',
    nickname: row?.accountNickname || '',
    displayName: row?.accountDisplayName || '',
    accountNote: row?.accountRemark || '',
    externalUid: row?.accountExternalUid || ''
  }
}

function goodsCover(row) {
  return row?.coverPic || row?.imageUrl || ''
}

function accountAvatar(row) {
  return accountOf(row)?.avatarUrl || ''
}

function accountDisplayLabel(row) {
  const account = accountOf(row)
  const id = row?.accountId || account?.id
  const label = accountName(account || {})
  if (!id) {
    return label || '-'
  }
  return `${label || '账号'}（${id}）`
}

async function loadSources() {
  error.value = ''
  loadError.value = ''
  sourcesAvailable.value = false
  try {
    const res = await getDeliverySources(query)
    rows.value = recordsOfOrThrow(res?.data, '货源列表响应格式异常')
    if (selected.value?.id) {
      const latest = rows.value.find(row => String(row.id) === String(selected.value.id))
      if (latest) {
        selected.value = { ...selected.value, ...latest }
      } else {
        clearSelected()
      }
    }
    sourcesAvailable.value = true
  } catch (e) {
    rows.value = []
    clearSelected()
    editing.value = null
    loadError.value = `${e.message || '货源库加载失败'}；数据成功加载前禁止新增、编辑或应用货源。`
  }
}

function openCreate() {
  if (!sourcesAvailable.value) return
  editing.value = {}
  Object.assign(form, { title: '', content: '', remark: '' })
}

function editSource(row) {
  if (!sourcesAvailable.value) return
  editing.value = row
  Object.assign(form, {
    title: row.title || '',
    content: row.content || '',
    remark: row.remark || ''
  })
}

function cancelEdit() {
  editing.value = null
}

function clearSelected() {
  selected.value = null
  configuredGoods.value = []
  allGoods.value = []
  recommendedGoods.value = []
  goodsAvailable.value = false
  goodsLoading.value = false
  goodsLoadError.value = ''
  selectedGoodsIds.value = []
  selectedConfiguredIds.value = []
  goodsView.value = 'all'
}

async function saveSource() {
  if (!sourcesAvailable.value) return
  error.value = ''
  success.value = ''
  try {
    const editingId = editing.value?.id
    if (editingId) {
      await updateDeliverySource(editingId, { ...form })
      success.value = '货源已更新'
    } else {
      await createDeliverySource({ ...form })
      success.value = '货源已新增'
    }
    editing.value = null
    await loadSources()
    if (editingId) {
      await loadSelectedGoods(editingId)
    }
  } catch (e) {
    error.value = e.message || '保存失败'
  }
}

async function removeSource(row) {
  if (!sourcesAvailable.value) return
  if (!await confirmAction({
    title: '确认删除该货源？',
    description: '删除后不会自动解除商品上的既有配置，请确认后继续。',
    dangerous: true,
    confirmText: '删除'
  })) return
  try {
    await deleteDeliverySource(row.id)
    if (selected.value?.id === row.id) {
      clearSelected()
    }
    success.value = '货源已删除'
    await loadSources()
  } catch (e) {
    error.value = e.message || '删除失败'
  }
}

async function loadSelectedGoods(sourceId = selected.value?.id) {
  if (!sourceId) return
  goodsAvailable.value = false
  goodsLoading.value = true
  goodsLoadError.value = ''
  try {
    const res = await getDeliverySourceGoods(sourceId)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('货源商品响应格式异常')
    }
    if (!data.source || typeof data.source !== 'object' || Array.isArray(data.source)) {
      throw new Error('货源详情响应格式异常')
    }
    if (!Array.isArray(data.configuredGoods) || !Array.isArray(data.allGoods)) {
      throw new Error('货源商品列表响应格式异常')
    }
    selected.value = { ...(selected.value || {}), ...data.source }
    configuredGoods.value = data.configuredGoods
    allGoods.value = data.allGoods
    goodsAvailable.value = true
    selectedConfiguredIds.value = []
  } catch (loadFailure) {
    configuredGoods.value = []
    allGoods.value = []
    recommendedGoods.value = []
    selectedGoodsIds.value = []
    goodsLoadError.value = `${loadFailure?.message || '货源商品加载失败'}；商品绑定状态确认前禁止配置。`
    throw loadFailure
  } finally {
    goodsLoading.value = false
  }
}

async function selectSource(row) {
  success.value = ''
  error.value = ''
  selected.value = row
  goodsView.value = 'all'
  selectedGoodsIds.value = []
  recommendedGoods.value = []
  try {
    await loadSelectedGoods(row.id)
  } catch (loadFailure) {
    error.value = loadFailure?.message || '货源商品加载失败'
  }
}

async function analyzeSource(row) {
  if (!sourcesAvailable.value) return
  selected.value = row
  error.value = ''
  success.value = ''
  try {
    await loadSelectedGoods(row.id)
    const res = await recommendDeliverySourceGoods(row.id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('商品推荐响应格式异常')
    }
    if (!data.source || typeof data.source !== 'object' || Array.isArray(data.source)) {
      throw new Error('推荐结果缺少有效货源详情')
    }
    if (!Array.isArray(data.configuredGoods) || !Array.isArray(data.candidates)) {
      throw new Error('商品推荐列表响应格式异常')
    }
    if (typeof data.aiEnabled !== 'boolean') {
      throw new Error('商品推荐模式响应格式异常')
    }
    selected.value = { ...(selected.value || {}), ...data.source }
    configuredGoods.value = data.configuredGoods
    recommendedGoods.value = data.candidates
    goodsView.value = 'recommend'
    recommendedHint.value = data.message || (data.aiEnabled === true
      ? 'AI 已根据标题、正文和备注给出匹配候选。'
      : 'AI 当前未启用，已使用本地规则给出匹配候选。')
    selectedGoodsIds.value = normalizedRecommendedGoods.value
      .filter(rowItem => !rowItem.configured)
      .map(rowItem => rowItem.id)
    if (!recommendedGoods.value.length) {
      success.value = recommendedHint.value || '暂未匹配到适合的商品'
    }
  } catch (e) {
    recommendedGoods.value = []
    selectedGoodsIds.value = []
    error.value = e.message || '商品匹配分析失败'
  }
}

async function applySelectedGoods() {
  if (!sourcesAvailable.value || !goodsAvailable.value) return
  if (!selected.value || selectedGoodsIds.value.length === 0) return
  try {
    await applyDeliverySourceToGoods(selected.value.id, {
      goodsIds: selectedGoodsIds.value,
      timing: applyTiming.value
    })
    success.value = `已配置 ${selectedGoodsIds.value.length} 个商品`
    selectedGoodsIds.value = []
  } catch (e) {
    error.value = e.message || '批量配置失败'
    return
  }
  try {
    await loadSelectedGoods(selected.value.id)
  } catch (refreshError) {
    error.value = `配置已提交，但刷新商品绑定状态失败：${refreshError?.message || '请手动刷新'}。`
  }
}

async function applyOne(row) {
  if (!sourcesAvailable.value || !goodsAvailable.value) return
  if (!selected.value) return
  try {
    await applyDeliverySourceToGoods(selected.value.id, {
      goodsIds: [row.id],
      timing: applyTiming.value
    })
    success.value = '已配置到商品'
  } catch (e) {
    error.value = e.message || '配置失败'
    return
  }
  try {
    await loadSelectedGoods(selected.value.id)
  } catch (refreshError) {
    error.value = `配置已提交，但刷新商品绑定状态失败：${refreshError?.message || '请手动刷新'}。`
  }
}

async function removeConfiguredGoods(row) {
  if (!sourcesAvailable.value || !goodsAvailable.value) return
  if (!selected.value) return
  if (!await confirmAction({
    title: '确认删除该已配置商品？',
    description: '删除后将解除该商品与当前货源的绑定关系，该商品的发货配置将被禁用。',
    dangerous: true,
    confirmText: '删除'
  })) return
  try {
    await removeDeliverySourceFromGoods(selected.value.id, row.id)
  } catch (e) {
    error.value = e.message || '删除失败'
    return
  }
  // 无感刷新：本地移除被删商品，不触发整表 loading
  configuredGoods.value = configuredGoods.value.filter(item => String(item.id) !== String(row.id))
  selectedConfiguredIds.value = selectedConfiguredIds.value.filter(id => String(id) !== String(row.id))
  if (typeof selected.value.usageCount === 'number') {
    selected.value = { ...selected.value, usageCount: Math.max(0, selected.value.usageCount - 1) }
  }
  success.value = '已删除已配置商品'
  // 静默同步货源列表计数（不阻塞、不显示 loading）
  loadSources().catch(() => {})
}

async function batchRemoveConfiguredGoods() {
  if (!sourcesAvailable.value || !goodsAvailable.value) return
  if (!selected.value) return
  const ids = [...selectedConfiguredIds.value]
  if (ids.length === 0) return
  if (!await confirmAction({
    title: `确认删除选中的 ${ids.length} 个已配置商品？`,
    description: '删除后将解除这些商品与当前货源的绑定关系，相关商品的发货配置将被禁用。',
    dangerous: true,
    confirmText: '删除'
  })) return
  const sourceId = selected.value.id
  const results = await Promise.allSettled(ids.map(goodsId => removeDeliverySourceFromGoods(sourceId, goodsId)))
  const successIds = new Set()
  let failureCount = 0
  results.forEach((r, i) => {
    if (r.status === 'fulfilled') {
      successIds.add(String(ids[i]))
    } else {
      failureCount += 1
    }
  })
  // 无感刷新：仅移除删除成功的商品
  if (successIds.size > 0) {
    configuredGoods.value = configuredGoods.value.filter(item => !successIds.has(String(item.id)))
    selectedConfiguredIds.value = selectedConfiguredIds.value.filter(id => !successIds.has(String(id)))
    if (typeof selected.value.usageCount === 'number') {
      selected.value = { ...selected.value, usageCount: Math.max(0, selected.value.usageCount - successIds.size) }
    }
  }
  if (failureCount > 0) {
    error.value = `部分删除失败：成功 ${successIds.size} 个，失败 ${failureCount} 个`
  } else {
    success.value = `已删除 ${successIds.size} 个已配置商品`
  }
  // 静默同步货源列表计数
  loadSources().catch(() => {})
}

async function refreshSelectedGoods() {
  error.value = ''
  if (!selected.value?.id) return
  try {
    await loadSelectedGoods(selected.value.id)
  } catch (e) {
    error.value = e.message || '商品列表刷新失败'
  }
}

function showAllGoods() {
  goodsView.value = 'all'
}

function showRecommendedGoods() {
  if (recommendedGoods.value.length) {
    goodsView.value = 'recommend'
    return
  }
  analyzeSource(selected.value)
}

function confidenceLabel(confidence, configured) {
  if (configured) return '已配置'
  if (confidence === 'high') return '高度匹配'
  if (confidence === 'medium') return '中等匹配'
  return '待确认'
}

function confidenceType(confidence, configured) {
  if (configured) return 'green'
  if (confidence === 'high') return 'green'
  if (confidence === 'medium') return 'orange'
  return 'gray'
}

function bindStateLabel(row) {
  return row.configured ? '已配置' : '未配置'
}

function onHeaderAction(event) {
  if (event.detail === 'source-new') openCreate()
  if (event.detail === 'source-refresh') {
    loadSources()
    refreshSelectedGoods()
  }
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  loadSources()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
.content-preview {
  max-width: 520px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.strong {
  font-weight: 600;
}

.goods-cell {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 260px;
}

.goods-thumb {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  object-fit: cover;
  background: #eef2ff;
  flex-shrink: 0;
}

.goods-thumb.placeholder,
.account-avatar.placeholder {
  background: #eef2ff;
}

.goods-main {
  min-width: 0;
}

.account-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.account-avatar {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  object-fit: cover;
  flex-shrink: 0;
}

.avatar-placeholder {
  position: relative;
}

.avatar-placeholder::before {
  content: '';
  position: absolute;
  inset: 5px;
  border-radius: 999px;
  background: #cbd5e1;
}

.source-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.summary-item {
  padding: 14px 16px;
  border: 1px solid #e7ecf3;
  border-radius: 12px;
  background: #f8fafc;
}

.summary-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}

.summary-value {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}

.source-preview {
  white-space: pre-wrap;
  line-height: 1.6;
}
</style>
