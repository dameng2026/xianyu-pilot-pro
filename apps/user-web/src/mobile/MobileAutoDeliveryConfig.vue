<template>
  <div class="m-adc">
    <div v-if="loading" class="m-adc-loading">
      <div class="m-adc-spinner"></div>
      <span>加载中...</span>
    </div>

    <div v-else-if="loadError" class="m-adc-error">
      <MIcon name="alertCircle" :size="48" :style="{ color: 'var(--m-color-danger)' }" />
      <div class="m-adc-error-text">{{ loadError }}</div>
      <button class="m-adc-retry" @click="loadAll">重试</button>
    </div>

    <template v-else>
      <div class="m-adc-goods">
        <div class="m-adc-goods-img-wrap">
          <img v-if="goods.imageUrl || goods.coverPic" :src="goods.imageUrl || goods.coverPic" :alt="goods.title || goods.name" class="m-adc-goods-img" />
          <div v-else class="m-adc-goods-img-placeholder">
            <MIcon name="bag" :size="28" />
          </div>
        </div>
        <div class="m-adc-goods-info">
          <div class="m-adc-goods-name" :title="goods.title || goods.name">{{ goods.title || goods.name || '未命名商品' }}</div>
          <div class="m-adc-goods-meta">
            <span class="m-adc-goods-id">ID: {{ goods.id }}</span>
            <span class="m-adc-goods-price">¥{{ formatPrice(goods.price) }}</span>
          </div>
          <div class="m-adc-goods-tags">
            <span v-if="goods.stock != null" class="m-adc-goods-stock">库存：{{ goods.stock }}</span>
          </div>
        </div>
      </div>

      <div class="m-adc-notice">
        <MIcon name="info" :size="16" class="m-adc-notice-icon" />
        <span>切换时机 tab 可分别配置三个发货时机；保存仅作用于当前选中的时机。</span>
      </div>

      <div class="m-adc-tabs">
        <button
          v-for="timing in configTimings"
          :key="timing.key"
          class="m-adc-tab"
          :class="{ active: configTiming === timing.key }"
          @click="switchTiming(timing.key)"
        >
          {{ timing.label }}
        </button>
      </div>

      <div v-if="depsError" class="m-adc-warn">{{ depsError }}</div>

      <div class="m-adc-form">
        <div class="m-adc-row">
          <div class="m-adc-row-label">启用{{ currentTimingLabel }}</div>
          <div class="m-adc-row-control">
            <button
              class="m-adc-switch"
              :class="{ 'm-adc-switch-on': configForm.enabled === 1 }"
              role="switch"
              :aria-checked="configForm.enabled === 1 ? 'true' : 'false'"
              @click="configForm.enabled = configForm.enabled === 1 ? 0 : 1"
            >
              <span class="m-adc-switch-knob"></span>
            </button>
            <span class="m-adc-switch-text">{{ configForm.enabled === 1 ? '启用' : '停用' }}</span>
          </div>
        </div>

        <div class="m-adc-row">
          <div class="m-adc-row-label">发货模式</div>
          <div class="m-adc-row-control">
            <div class="m-adc-seg">
              <button
                class="m-adc-seg-btn"
                :class="{ active: configForm.mode === 'text' }"
                @click="configForm.mode = 'text'"
              >文本发货</button>
              <button
                class="m-adc-seg-btn"
                :class="{ active: configForm.mode === 'card' }"
                @click="configForm.mode = 'card'"
              >卡密发货</button>
            </div>
          </div>
        </div>

        <div v-if="configForm.mode === 'text'" class="m-adc-row">
          <div class="m-adc-row-label">关联货源库</div>
          <div class="m-adc-row-control">
            <select v-model="configForm.sourceId" class="m-adc-select" :disabled="!sourcesAvailable">
              <option value="">不使用货源库，直接手写内容</option>
              <option v-for="source in textSources" :key="source.id" :value="source.id">{{ source.title || '未命名货源' }}</option>
            </select>
            <div v-if="configForm.sourceId" class="m-adc-row-hint">
              已关联货源：{{ sourceTitle(configForm.sourceId) }}
            </div>
          </div>
        </div>

        <div v-if="configForm.mode === 'card'" class="m-adc-row">
          <div class="m-adc-row-label">绑定卡密分组</div>
          <div class="m-adc-row-control">
            <select v-model="configForm.cardGroupId" class="m-adc-select" :disabled="!cardGroupsAvailable">
              <option value="">请选择</option>
              <option v-for="group in cardGroups" :key="group.id" :value="group.id">{{ group.groupName }}（余 {{ group.remainCount ?? '—' }}）</option>
            </select>
          </div>
        </div>

        <div v-if="configForm.mode === 'card'" class="m-adc-row">
          <div class="m-adc-row-label">卡密模板</div>
          <div class="m-adc-row-control">
            <textarea
              v-model="configForm.cardTemplate"
              rows="2"
              class="m-adc-textarea"
              placeholder="例如：您的卡密为：{卡密}"
            ></textarea>
          </div>
        </div>

        <div class="m-adc-row">
          <div class="m-adc-row-label">消息头部</div>
          <div class="m-adc-row-control">
            <textarea
              v-model="configForm.header"
              rows="2"
              class="m-adc-textarea"
              placeholder="可选，发货正文前的说明"
            ></textarea>
          </div>
        </div>

        <div class="m-adc-row">
          <div class="m-adc-row-label">
            <template v-if="configForm.mode === 'text'">正文内容</template>
            <template v-else>消息底部</template>
          </div>
          <div class="m-adc-row-control">
            <textarea
              v-if="configForm.mode === 'text'"
              v-model="configForm.content"
              rows="5"
              class="m-adc-textarea"
              :placeholder="configForm.sourceId ? '已引用货源库正文，可继续补充或覆盖。可使用 {货源:ID} 占位符，发货时会自动替换为对应货源的最新内容' : '请输入买家将收到的发货内容。可使用 {货源:ID} 占位符插入货源'"
            ></textarea>
            <textarea
              v-else
              v-model="configForm.footer"
              rows="2"
              class="m-adc-textarea"
              placeholder="可选，卡密内容后的补充说明"
            ></textarea>
            <button
              v-if="configForm.mode === 'text'"
              type="button"
              class="m-adc-insert-btn"
              :disabled="!sourcesAvailable || textSources.length === 0"
              @click="openSourceDrawer"
            >+ 插入货源占位符</button>
          </div>
        </div>

        <div class="m-adc-row">
          <div class="m-adc-row-label">分段发送</div>
          <div class="m-adc-row-control">
            <label class="m-adc-checkbox">
              <input v-model="configForm.segmentSend" type="checkbox" />
              <span>使用 {分段} 拆成多条消息发送</span>
            </label>
          </div>
        </div>

        <div class="m-adc-row">
          <div class="m-adc-row-label">失败重试次数</div>
          <div class="m-adc-row-control">
            <input
              v-model.number="configForm.retryCount"
              type="number"
              min="0"
              max="10"
              class="m-adc-input"
            />
          </div>
        </div>

        <div class="m-adc-row">
          <div class="m-adc-row-label">库存预警阈值</div>
          <div class="m-adc-row-control">
            <input
              v-model.number="configForm.alertThreshold"
              type="number"
              min="0"
              class="m-adc-input"
            />
          </div>
        </div>

        <div class="m-adc-row">
          <div class="m-adc-row-label">库存不足自动停用</div>
          <div class="m-adc-row-control">
            <label class="m-adc-checkbox">
              <input v-model="configForm.autoDisableOnLowStock" type="checkbox" />
              <span>自动停用</span>
            </label>
          </div>
        </div>
      </div>

      <div class="m-adc-actions">
        <button class="m-adc-btn m-adc-btn-outline" @click="handleBack">取消</button>
        <button
          class="m-adc-btn m-adc-btn-primary"
          :disabled="saving || saveDisabled"
          @click="saveConfig"
        >
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>

      <div class="m-adc-safe-bottom"></div>
    </template>

    <div v-if="sourceDrawerVisible" class="m-adc-sheet-mask" @click="closeSourceDrawer"></div>
    <div v-if="sourceDrawerVisible" class="m-adc-sheet m-adc-sheet-open">
      <div class="m-adc-sheet-header">
        <h3>选择货源插入</h3>
        <button class="m-adc-sheet-close" @click="closeSourceDrawer" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-adc-sheet-body">
        <div class="m-adc-sheet-tip">
          点击任意货源将把 <code>&#123;货源:ID&#125;</code> 占位符追加到正文末尾；发货时会自动替换为对应货源的最新内容。
        </div>
        <div v-if="!sourcesAvailable" class="m-adc-sheet-empty">货源库加载失败，无法插入。</div>
        <div v-else-if="textSources.length === 0" class="m-adc-sheet-empty">暂无货源，请先到货源库添加。</div>
        <button
          v-else
          v-for="source in textSources"
          :key="source.id"
          type="button"
          class="m-adc-sheet-source"
          @click="insertSource(source)"
        >
          <div class="m-adc-sheet-source-main">
            <div class="m-adc-sheet-source-title">{{ source.title || '未命名货源' }}</div>
            <div class="m-adc-sheet-source-meta">
              <span>ID: {{ source.id }}</span>
              <span v-if="source.stockLabel">库存：{{ source.stockLabel }}</span>
            </div>
          </div>
          <span class="m-adc-sheet-source-insert">插入</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import MIcon from './MIcon.vue'
import { getGoodsDetail } from '../api/goods.js'
import { getCards } from '../api/cards.js'
import {
  getGoodsDeliveryConfig,
  saveGoodsDeliveryConfig,
  getDeliverySources
} from '../api/autoDelivery.js'

const props = defineProps({
  goodsId: [String, Number],
  product: Object
})

const emit = defineEmits(['navigate', 'force-desktop', 'back', 'saved'])

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const depsError = ref('')

const goods = ref({ id: null, title: '', name: '', price: 0, stock: null, imageUrl: '', coverPic: '' })
const textSources = ref([])
const cardGroups = ref([])
const sourcesAvailable = ref(false)
const cardGroupsAvailable = ref(false)

const configTiming = ref('payDelivery')
const configTimings = [
  { key: 'payDelivery', label: '付款后发货' },
  { key: 'confirmDelivery', label: '确认收货后赠送' },
  { key: 'reviewDelivery', label: '好评后赠送' }
]

const configForm = reactive({
  enabled: 1,
  mode: 'text',
  sourceId: '',
  sourceTitle: '',
  cardGroupId: '',
  cardTemplate: '',
  header: '',
  content: '',
  footer: '',
  segmentSend: false,
  retryCount: 3,
  alertThreshold: 5,
  autoDisableOnLowStock: false
})

const sourceDrawerVisible = ref(false)

const currentTimingLabel = computed(() =>
  configTimings.find(item => item.key === configTiming.value)?.label || ''
)

const saveDisabled = computed(() => {
  if (configForm.mode === 'card' && !cardGroupsAvailable.value) return true
  return false
})

watch(() => configForm.sourceId, value => {
  const source = textSources.value.find(item => String(item.id) === String(value))
  if (source) {
    configForm.sourceTitle = source.title
    if (!configForm.content) {
      configForm.content = source.content || ''
    }
  } else {
    configForm.sourceTitle = ''
  }
})

function formatPrice(price) {
  if (price == null || price === '') return '—'
  const num = Number(price)
  if (isNaN(num)) return String(price)
  return Number.isInteger(num) ? String(num) : num.toFixed(2)
}

function sourceTitle(id) {
  return textSources.value.find(item => String(item.id) === String(id))?.title || ''
}

function fillConfigForm(config = {}) {
  const legacyApiMode = config.mode === 'api'
  Object.assign(configForm, {
    enabled: legacyApiMode ? 0 : (config.enabled !== undefined ? Number(config.enabled) : 1),
    mode: ['text', 'card'].includes(config.mode) ? config.mode : 'text',
    sourceId: config.sourceId || '',
    sourceTitle: config.sourceTitle || '',
    cardGroupId: config.cardGroupId || '',
    cardTemplate: config.cardTemplate || '',
    header: config.header || '',
    content: config.content || '',
    footer: config.footer || '',
    segmentSend: !!config.segmentSend,
    retryCount: config.retryCount ?? 3,
    alertThreshold: config.alertThreshold ?? 5,
    autoDisableOnLowStock: !!config.autoDisableOnLowStock
  })
}

async function loadGoods() {
  const id = props.goodsId || props.product?.id || props.product?.itemId
  if (!id) {
    loadError.value = '商品 ID 不存在'
    return
  }
  // 优先使用传入的 product 作为基础信息，避免详情接口失败时整个页面无法渲染
  if (props.product) {
    goods.value = { ...goods.value, ...props.product, id }
  }
  try {
    const res = await getGoodsDetail(id)
    const data = res?.data
    if (data && typeof data === 'object') {
      goods.value = { ...goods.value, ...data, id }
    }
  } catch (e) {
    // 详情接口失败但已有 product 数据时，不视为致命错误
    if (!props.product) {
      throw e
    }
  }
}

async function loadConfig() {
  const id = goods.value.id
  if (!id) return
  try {
    const res = await getGoodsDeliveryConfig(id)
    const config = res?.data
    if (config && typeof config === 'object' && !Array.isArray(config)) {
      const timingConfig = config[configTiming.value] || {}
      if (timingConfig.mode === 'api') {
        depsError.value = '该规则使用的是已停用的 API 发货模式；保存时请改用文本或卡密发货。'
      }
      fillConfigForm(timingConfig)
    } else {
      fillConfigForm({})
    }
  } catch (e) {
    // 配置读取失败按空配置处理，仍允许新建保存
    fillConfigForm({})
  }
}

async function loadSources() {
  sourcesAvailable.value = false
  try {
    const res = await getDeliverySources({ current: 1, size: 200 })
    const data = res?.data
    let list = []
    if (Array.isArray(data)) {
      list = data
    } else if (data && Array.isArray(data.records)) {
      list = data.records
    } else if (data && Array.isArray(data.list)) {
      list = data.list
    }
    textSources.value = list
    sourcesAvailable.value = true
  } catch (e) {
    textSources.value = []
  }
}

async function loadCards() {
  cardGroupsAvailable.value = false
  try {
    const res = await getCards({ size: 200 })
    const data = res?.data
    let list = []
    if (Array.isArray(data)) {
      list = data
    } else if (data && Array.isArray(data.records)) {
      list = data.records
    } else if (data && Array.isArray(data.list)) {
      list = data.list
    }
    cardGroups.value = list
    cardGroupsAvailable.value = true
  } catch (e) {
    cardGroups.value = []
  }
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  depsError.value = ''
  try {
    await loadGoods()
    await Promise.all([loadConfig(), loadSources(), loadCards()])
  } catch (e) {
    loadError.value = e?.message || '加载失败，请重试'
  } finally {
    loading.value = false
  }
}

function switchTiming(timing) {
  if (saving.value) return
  configTiming.value = timing
  // 重新拉取一次完整 config（其中包含三个 timing 字段），切换 tab 时复用本地缓存
  loadConfig()
}

function openSourceDrawer() {
  if (!sourcesAvailable.value || textSources.value.length === 0) return
  sourceDrawerVisible.value = true
  document.body.style.overflow = 'hidden'
}

function closeSourceDrawer() {
  sourceDrawerVisible.value = false
  document.body.style.overflow = ''
}

function insertSource(source) {
  const placeholder = `{货源:${source.id}}`
  if (configForm.content) {
    configForm.content = configForm.content + '\n' + placeholder
  } else {
    configForm.content = placeholder
  }
  closeSourceDrawer()
}

async function saveConfig() {
  if (saveDisabled.value || saving.value) return
  const id = goods.value.id
  if (!id) return
  saving.value = true
  try {
    await saveGoodsDeliveryConfig(id, {
      timing: configTiming.value,
      enabled: configForm.enabled,
      mode: configForm.mode,
      sourceId: configForm.mode === 'text' && configForm.sourceId ? Number(configForm.sourceId) : null,
      sourceTitle: configForm.mode === 'text' ? configForm.sourceTitle : '',
      cardGroupId: configForm.mode === 'card' && configForm.cardGroupId ? Number(configForm.cardGroupId) : null,
      cardTemplate: configForm.cardTemplate,
      header: configForm.header,
      content: configForm.content,
      footer: configForm.footer,
      segmentSend: configForm.segmentSend,
      retryCount: configForm.retryCount,
      alertThreshold: configForm.alertThreshold,
      autoDisableOnLowStock: configForm.autoDisableOnLowStock
    })
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '配置已保存' } }))
    emit('saved', { goodsId: id, timing: configTiming.value })
    emit('back')
  } catch (e) {
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: e?.message || '保存失败，请重试', isError: true } }))
  } finally {
    saving.value = false
  }
}

function handleBack() {
  emit('back')
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.m-adc {
  padding: var(--m-space-3) var(--m-space-4) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-adc-loading,
.m-adc-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px var(--m-space-5);
  gap: var(--m-space-3);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body);
}
.m-adc-spinner {
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-circle);
  border: 3px solid var(--m-color-border);
  border-top-color: var(--m-color-primary);
  animation: m-adc-spin 0.8s linear infinite;
}
@keyframes m-adc-spin { to { transform: rotate(360deg); } }
.m-adc-error-text {
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  text-align: center;
}
.m-adc-retry {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border: none;
  padding: var(--m-space-2) var(--m-space-5);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}

.m-adc-goods {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  display: flex;
  gap: var(--m-space-3);
  border: 1px solid var(--m-color-border-light);
  margin-bottom: var(--m-space-3);
}
.m-adc-goods-img-wrap {
  width: 64px;
  height: 64px;
  border-radius: var(--m-radius-md);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
}
.m-adc-goods-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-adc-goods-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-tertiary);
  background: var(--m-color-bg-subtle);
}
.m-adc-goods-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--m-space-1);
}
.m-adc-goods-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-base);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.m-adc-goods-meta {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
}
.m-adc-goods-id {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-adc-goods-price {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-success-text);
}
.m-adc-goods-tags {
  display: flex;
  gap: var(--m-space-1);
}
.m-adc-goods-stock {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-secondary);
  background: var(--m-color-bg-subtle);
  padding: 2px var(--m-space-2);
  border-radius: var(--m-radius-pill);
}

.m-adc-notice {
  background: var(--m-color-warning-bg);
  border: 1px solid var(--m-color-warning-border);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-warning-text);
  line-height: var(--m-line-height-base);
}
.m-adc-notice-icon {
  color: var(--m-color-warning);
  flex-shrink: 0;
  margin-top: 1px;
}

.m-adc-warn {
  background: var(--m-color-danger-bg);
  border: 1px solid var(--m-color-danger-border);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  margin-bottom: var(--m-space-3);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-danger-text);
  line-height: var(--m-line-height-base);
}

.m-adc-tabs {
  display: flex;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  padding: 3px;
  margin-bottom: var(--m-space-3);
  gap: 3px;
}
.m-adc-tab {
  flex: 1;
  background: none;
  border: none;
  padding: var(--m-space-2) var(--m-space-1);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  border-radius: var(--m-radius-md);
  transition: all 0.15s;
  min-width: 0;
  white-space: nowrap;
}
.m-adc-tab.active {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  box-shadow: var(--m-shadow-card);
}

.m-adc-form {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-1) var(--m-space-3);
  border: 1px solid var(--m-color-border-light);
  margin-bottom: var(--m-space-3);
}
.m-adc-row {
  padding: var(--m-space-3) 0;
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-adc-row:last-child {
  border-bottom: none;
}
.m-adc-row-label {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
}
.m-adc-row-control {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}
.m-adc-row-hint {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
}

.m-adc-select,
.m-adc-input {
  width: 100%;
  height: 42px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  padding: 0 var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  outline: none;
  box-sizing: border-box;
}
.m-adc-select:focus,
.m-adc-input:focus {
  border-color: var(--m-color-primary);
}
.m-adc-textarea {
  width: 100%;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  outline: none;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
  line-height: var(--m-line-height-base);
}
.m-adc-textarea:focus {
  border-color: var(--m-color-primary);
}
.m-adc-seg {
  display: flex;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  padding: 3px;
  gap: 3px;
}
.m-adc-seg-btn {
  flex: 1;
  background: none;
  border: none;
  padding: var(--m-space-2) 0;
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  border-radius: var(--m-radius-md);
}
.m-adc-seg-btn.active {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  box-shadow: var(--m-shadow-card);
}

.m-adc-switch {
  width: 44px;
  height: 26px;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-border);
  border: none;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
  padding: 0;
  flex-shrink: 0;
}
.m-adc-switch-on {
  background: var(--m-color-primary);
}
.m-adc-switch-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-bg-card);
  box-shadow: var(--m-shadow-card);
  transition: transform 0.2s;
}
.m-adc-switch-on .m-adc-switch-knob {
  transform: translateX(18px);
}
.m-adc-row-control .m-adc-switch {
  display: inline-flex;
}
.m-adc-row-control:has(.m-adc-switch) {
  flex-direction: row;
  align-items: center;
  gap: var(--m-space-2);
}
.m-adc-switch-text {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
}

.m-adc-checkbox {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  cursor: pointer;
}
.m-adc-checkbox input {
  width: 18px;
  height: 18px;
  accent-color: var(--m-color-primary);
}

.m-adc-insert-btn {
  align-self: flex-start;
  background: var(--m-color-primary-bg);
  border: none;
  color: var(--m-color-primary);
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}
.m-adc-insert-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-adc-actions {
  display: flex;
  gap: var(--m-space-2);
  padding: var(--m-space-1) 0 var(--m-space-4);
  position: sticky;
  bottom: 0;
  background: linear-gradient(180deg, rgba(245, 246, 247, 0) 0%, var(--m-color-bg-page) 30%);
  padding-top: var(--m-space-3);
  margin-top: -10px;
}
.m-adc-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  border: none;
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  padding: var(--m-space-3) var(--m-space-4);
  min-height: 44px;
  transition: all 0.15s;
}
.m-adc-btn:active { transform: scale(0.98); }
.m-adc-btn-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  box-shadow: var(--m-shadow-fab);
}
.m-adc-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-adc-btn-outline {
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  border: 1px solid var(--m-color-border);
}

.m-adc-safe-bottom {
  height: calc(20px + env(safe-area-inset-bottom));
}

.m-adc-sheet-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-drawer);
  z-index: 200;
  backdrop-filter: blur(2px);
}
.m-adc-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  z-index: 201;
  transform: translateY(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 75vh;
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom);
}
.m-adc-sheet-open {
  transform: translateY(0);
}
.m-adc-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-4) var(--m-space-5);
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-adc-sheet-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-adc-sheet-close {
  width: 36px;
  height: 36px;
  border: none;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-circle);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-secondary);
  cursor: pointer;
}
.m-adc-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-space-3) var(--m-space-5) var(--m-space-4);
}
.m-adc-sheet-tip {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  margin-bottom: var(--m-space-3);
  line-height: var(--m-line-height-base);
}
.m-adc-sheet-tip code {
  background: var(--m-color-bg-card);
  padding: 1px var(--m-space-1);
  border-radius: var(--m-radius-sm);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-primary);
  border: 1px solid var(--m-color-border);
}
.m-adc-sheet-empty {
  text-align: center;
  padding: 30px var(--m-space-2);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}
.m-adc-sheet-source {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3);
  border: 1px solid var(--m-color-border-light);
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-md);
  margin-bottom: var(--m-space-2);
  cursor: pointer;
  text-align: left;
}
.m-adc-sheet-source:active {
  background: var(--m-color-bg-hover);
}
.m-adc-sheet-source-main {
  flex: 1;
  min-width: 0;
}
.m-adc-sheet-source-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-adc-sheet-source-meta {
  display: flex;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-adc-sheet-source-insert {
  color: var(--m-color-primary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  flex-shrink: 0;
  padding-left: var(--m-space-2);
}

@media (max-width: 360px) {
  .m-adc { padding: var(--m-space-2) var(--m-space-3) 0; }
  .m-adc-tab { font-size: var(--m-font-size-tiny); padding: 7px 2px; }
  .m-adc-goods-img-wrap { width: 56px; height: 56px; }
}
</style>
