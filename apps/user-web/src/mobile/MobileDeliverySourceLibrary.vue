<template>
  <div class="m-dsl">
    <div class="m-dsl-stats-grid">
      <div v-for="card in statCards" :key="card.key" class="m-dsl-stat-card">
        <div class="m-dsl-stat-icon" :class="`m-dsl-stat-icon-${card.color}`">
          <MIcon :name="card.icon" :size="20" />
        </div>
        <div class="m-dsl-stat-info">
          <div class="m-dsl-stat-title">{{ card.title }}</div>
          <div class="m-dsl-stat-value">{{ loading ? '—' : card.value }}</div>
          <div class="m-dsl-stat-desc" :class="`m-dsl-stat-desc-${card.color}`">{{ card.desc }}</div>
        </div>
      </div>
    </div>

    <div class="m-dsl-notice">
      <div class="m-dsl-notice-icon">
        <MIcon name="info" :size="16" />
      </div>
      <div class="m-dsl-notice-text">
        <b>卡密发货</b>从卡密分组自动扣减库存；<b>文本发货</b>直接发送固定文案。删除货源不会自动解除商品上的既有配置。
      </div>
    </div>

    <div class="m-dsl-toolbar">
      <div class="m-dsl-search">
        <MIcon name="search" :size="18" class="m-dsl-search-icon" />
        <input
          v-model="searchKeyword"
          type="text"
          class="m-dsl-search-input"
          placeholder="搜索标题 / 备注"
          aria-label="搜索货源"
          @keyup.enter="handleSearch"
          @input="debouncedSearch"
        />
        <button v-if="searchKeyword" class="m-dsl-search-clear" @click="clearSearch" aria-label="清空搜索">
          <MIcon name="x" :size="16" />
        </button>
      </div>
      <button class="m-dsl-btn m-dsl-btn-primary" :disabled="!sourcesAvailable" @click="openCreate">
        <MIcon name="plus" :size="16" />
        <span>新建</span>
      </button>
    </div>

    <div v-if="loading && sources.length === 0" class="m-dsl-skeleton-list">
      <div v-for="i in 4" :key="i" class="m-dsl-skeleton-card">
        <div class="m-dsl-skeleton-line m-dsl-skeleton-title"></div>
        <div class="m-dsl-skeleton-line m-dsl-skeleton-meta"></div>
        <div class="m-dsl-skeleton-line m-dsl-skeleton-content"></div>
        <div class="m-dsl-skeleton-tags">
          <div class="m-dsl-skeleton-tag"></div>
          <div class="m-dsl-skeleton-tag"></div>
        </div>
      </div>
    </div>

    <MobileUnavailableState v-else-if="loadError" compact title="货源库加载失败" :description="loadError" @retry="loadSources" />

    <div v-else-if="sources.length === 0" class="m-dsl-empty">
      <div class="m-dsl-empty-icon">
        <MIcon name="package" :size="44" />
      </div>
      <div class="m-dsl-empty-text">{{ hasFilter ? '暂无符合条件的货源' : '暂无货源' }}</div>
      <div class="m-dsl-empty-desc">{{ hasFilter ? '请尝试调整搜索关键词' : '点击右上角"新建"创建第一个货源' }}</div>
      <button v-if="hasFilter" class="m-dsl-btn m-dsl-btn-outline m-dsl-btn-sm" @click="clearSearch">清除搜索</button>
      <button v-else class="m-dsl-btn m-dsl-btn-primary m-dsl-btn-sm" :disabled="!sourcesAvailable" @click="openCreate">新建货源</button>
    </div>

    <div v-else class="m-dsl-list">
      <div v-for="src in sources" :key="src.id" class="m-dsl-source-card">
        <div class="m-dsl-source-header">
          <div class="m-dsl-source-icon" :class="src.deliveryMode === 'card' ? 'm-dsl-source-icon-card' : 'm-dsl-source-icon-text'">
            <MIcon :name="src.deliveryMode === 'card' ? 'key' : 'fileText'" :size="18" />
          </div>
          <div class="m-dsl-source-title-wrap">
            <div class="m-dsl-source-title" :title="src.title">{{ src.title || '未命名货源' }}</div>
            <div class="m-dsl-source-tags">
              <span class="m-dsl-tag" :class="src.deliveryMode === 'card' ? 'm-dsl-tag-orange' : 'm-dsl-tag-gray'">
                {{ src.deliveryMode === 'card' ? '卡密发货' : '文本发货' }}
              </span>
              <span v-if="src.fromMall" class="m-dsl-tag m-dsl-tag-purple">商城货源</span>
            </div>
          </div>
        </div>

        <div v-if="src.remark" class="m-dsl-source-remark">{{ src.remark }}</div>

        <div class="m-dsl-source-content">{{ src.content || '暂无正文' }}</div>

        <div class="m-dsl-source-footer">
          <div class="m-dsl-source-stat">
            <span class="m-dsl-source-stat-label">库存</span>
            <span v-if="src.fromMall" class="m-dsl-source-stat-value muted">商城货源</span>
            <span v-else-if="src.deliveryMode === 'card'" class="m-dsl-source-stat-value" :class="{ low: (src.cardRemainCount ?? 0) <= 0 }">
              {{ src.cardRemainCount ?? 0 }}
            </span>
            <span v-else class="m-dsl-source-stat-value muted">文本</span>
          </div>
          <div class="m-dsl-source-stat">
            <span class="m-dsl-source-stat-label">已配置</span>
            <span class="m-dsl-source-stat-value">{{ src.usageCount ?? 0 }} 个商品</span>
          </div>
          <div class="m-dsl-source-stat">
            <span class="m-dsl-source-stat-label">创建</span>
            <span class="m-dsl-source-stat-value muted">{{ formatDate(src.createdAt || src.createTime || src.gmtCreate) }}</span>
          </div>
        </div>

        <div class="m-dsl-source-actions">
          <button
            v-if="src.deliveryMode === 'card' && !src.fromMall && src.cardGroupId"
            class="m-dsl-action-btn"
            @click="viewCardItems(src)"
          >
            <MIcon name="list" :size="14" />
            <span>卡密列表</span>
          </button>
          <button class="m-dsl-action-btn" @click="openEdit(src)">
            <MIcon name="edit" :size="14" />
            <span>编辑</span>
          </button>
          <button class="m-dsl-action-btn m-dsl-action-danger" @click="removeSource(src)">
            <MIcon name="trash" :size="14" />
            <span>删除</span>
          </button>
        </div>
      </div>

      <div v-if="loadingMore" class="m-dsl-loading-more">加载中...</div>
      <div v-else-if="hasMore" class="m-dsl-load-more">
        <button class="m-dsl-btn m-dsl-btn-outline m-dsl-btn-sm" @click="loadMore">加载更多</button>
      </div>
      <div v-else-if="sources.length > 0" class="m-dsl-no-more">没有更多货源</div>
    </div>

    <div class="m-dsl-safe-bottom"></div>

    <div v-if="showEditor" class="m-dsl-sheet-mask" @click="closeEditor"></div>
    <div v-if="showEditor" class="m-dsl-sheet m-dsl-sheet-open">
      <div class="m-dsl-sheet-header">
        <h3>{{ editingId ? '编辑货源' : '新增货源' }}</h3>
        <button class="m-dsl-sheet-close" @click="closeEditor" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-dsl-sheet-body">
        <div v-if="form.fromMall" class="m-dsl-info-tip">
          <MIcon name="info" :size="14" />
          <span>商城货源固定为文本模式，不可切换为卡密发货。可编辑标题、正文、备注。</span>
        </div>

        <div class="m-dsl-form-row">
          <label class="m-dsl-form-label"><span class="m-dsl-required">*</span>标题</label>
          <input v-model="form.title" class="m-dsl-input" placeholder="给用户和 AI 模型看的标题" maxlength="50" />
        </div>

        <div class="m-dsl-form-row">
          <label class="m-dsl-form-label">
            <span class="m-dsl-required">*</span>正文
            <button
              v-if="form.deliveryMode === 'card' && !form.fromMall"
              type="button"
              class="m-dsl-insert-btn"
              @click="insertCardPlaceholder"
            >+ 插入 {卡密占位}</button>
          </label>

          <!-- 卡密发货 / 商城货源：保持单 textarea（向后兼容） -->
          <textarea
            v-if="form.deliveryMode === 'card' || form.fromMall"
            v-model="form.content"
            rows="5"
            class="m-dsl-textarea"
            :placeholder="form.deliveryMode === 'card' ? '需包含 {卡密占位}，发货时会自动替换为认领到的卡密' : '实际发货文本内容'"
            maxlength="5000"
          ></textarea>

          <!-- 文本发货：多条正文 + 图片发货（每条文本/图片二选一互斥） -->
          <div v-else class="m-dsl-segments">
            <div
              v-for="(seg, idx) in form.segments"
              :key="seg._uid"
              class="m-dsl-segment"
            >
              <div class="m-dsl-segment-header">
                <span class="m-dsl-segment-index">第 {{ idx + 1 }} 条</span>
                <div class="m-dsl-segment-switch">
                  <button
                    type="button"
                    class="m-dsl-segment-switch-btn"
                    :class="{ active: seg.type === 'text' }"
                    @click="setSegmentType(idx, 'text')"
                  >文本</button>
                  <button
                    type="button"
                    class="m-dsl-segment-switch-btn"
                    :class="{ active: seg.type === 'image' }"
                    @click="setSegmentType(idx, 'image')"
                  >图片</button>
                </div>
                <button
                  v-if="form.segments.length > 1"
                  type="button"
                  class="m-dsl-segment-remove"
                  @click="removeSegment(idx)"
                >
                  <MIcon name="trash" :size="14" />
                </button>
              </div>

              <div class="m-dsl-segment-body">
                <textarea
                  v-if="seg.type === 'text'"
                  v-model="seg.content"
                  rows="3"
                  class="m-dsl-textarea"
                  placeholder="输入文本内容，发货时按顺序逐条发送"
                  maxlength="5000"
                ></textarea>
                <div v-else class="m-dsl-segment-image">
                  <div v-if="seg.imageUrl" class="m-dsl-segment-image-preview-wrap">
                    <img :src="seg.imageUrl" class="m-dsl-segment-image-preview" alt="发货图片" />
                    <div class="m-dsl-segment-image-actions">
                      <button type="button" class="m-dsl-segment-image-btn" @click="triggerSegmentImagePick(idx)">更换</button>
                      <button type="button" class="m-dsl-segment-image-btn danger" @click="clearSegmentImage(idx)">移除</button>
                    </div>
                  </div>
                  <div v-else class="m-dsl-segment-image-upload">
                    <button
                      type="button"
                      class="m-dsl-segment-image-upload-btn"
                      :disabled="seg._uploading"
                      @click="triggerSegmentImagePick(idx)"
                    >
                      <MIcon name="image" :size="18" />
                      <span>{{ seg._uploading ? '上传中...' : '上传图片' }}</span>
                    </button>
                  </div>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/gif,image/webp"
                    hidden
                    :ref="el => registerSegmentFileInput(idx, el)"
                    @change="onSegmentImagePick(idx, $event)"
                  />
                </div>
              </div>
            </div>

            <button
              v-if="form.segments.length < 20"
              type="button"
              class="m-dsl-add-segment-btn"
              @click="addSegment"
            >
              <MIcon name="plus" :size="14" />
              <span>增加一条对话</span>
            </button>
            <div class="m-dsl-segments-tip">
              每条为"纯文本"或"单张图片"二选一；同时发送文本和图片请分两条配置。多条消息按顺序逐条单独发送。
            </div>
          </div>
        </div>

        <div class="m-dsl-form-row">
          <label class="m-dsl-form-label">备注（选填）</label>
          <textarea v-model="form.remark" rows="2" class="m-dsl-textarea" placeholder="可添加备注信息，方便后续管理" maxlength="200"></textarea>
        </div>

        <div class="m-dsl-form-row">
          <label class="m-dsl-form-label">发送类型</label>
          <div class="m-dsl-seg">
            <button
              type="button"
              class="m-dsl-seg-btn"
              :class="{ active: form.deliveryMode === 'text', disabled: form.fromMall }"
              :disabled="form.fromMall"
              @click="setDeliveryMode('text')"
            >文本发送</button>
            <button
              type="button"
              class="m-dsl-seg-btn"
              :class="{ active: form.deliveryMode === 'card', disabled: form.fromMall }"
              :disabled="form.fromMall"
              @click="setDeliveryMode('card')"
            >卡密发送</button>
          </div>
          <div class="m-dsl-form-hint">
            <MIcon name="info" :size="12" />
            <span v-if="form.fromMall">商城货源固定为文本模式</span>
            <span v-else>卡密发送将在发送时自动替换 {卡密占位} 占位符</span>
          </div>
        </div>

        <div v-if="form.deliveryMode === 'card' && !form.fromMall" class="m-dsl-form-row">
          <label class="m-dsl-form-label"><span class="m-dsl-required">*</span>卡密分组</label>
          <select v-model="form.cardGroupId" class="m-dsl-select">
            <option value="" disabled>请选择卡密分组</option>
            <option v-for="g in cardGroups" :key="g.id" :value="g.id">
              {{ g.groupName }}（余 {{ g.remainCount ?? 0 }} / 共 {{ g.totalCount ?? 0 }}）
            </option>
          </select>
          <div v-if="cardGroupsLoading" class="m-dsl-form-hint">加载中…</div>
          <div v-else-if="cardGroups.length === 0" class="m-dsl-form-hint danger">
            暂无卡密分组，请先到「卡密仓库」创建分组并导入卡密
          </div>
          <div v-else-if="selectedCardGroup" class="m-dsl-form-hint">
            当前剩余 <b :class="{ 'm-dsl-danger': selectedCardRemainCount <= 0 }">{{ selectedCardRemainCount }}</b> 张
          </div>
        </div>
      </div>
      <div class="m-dsl-sheet-footer">
        <button class="m-dsl-btn m-dsl-btn-outline" @click="closeEditor">取消</button>
        <button class="m-dsl-btn m-dsl-btn-primary" :disabled="saving" @click="saveSource">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>

    <div v-if="showCards" class="m-dsl-sheet-mask" @click="closeCards"></div>
    <div v-if="showCards" class="m-dsl-sheet m-dsl-sheet-open" style="max-height: 80vh;">
      <div class="m-dsl-sheet-header">
        <h3>卡密列表</h3>
        <button class="m-dsl-sheet-close" @click="closeCards" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-dsl-sheet-body">
        <div v-if="cardsSource" class="m-dsl-cards-header">
          <div class="m-dsl-cards-source-name">{{ cardsSource.title || '未命名货源' }}</div>
          <div class="m-dsl-cards-source-meta">
            分组：{{ cardsSource.cardGroupName || cardsSource.cardGroupId || '-' }} · 剩余 {{ cardsSource.cardRemainCount ?? 0 }}
          </div>
        </div>

        <div v-if="cardsLoading" class="m-dsl-cards-loading">加载中...</div>
        <div v-else-if="cardsError" class="m-dsl-cards-empty">
          <MIcon name="alertCircle" :size="32" />
          <div>{{ cardsError }}</div>
          <button class="m-dsl-btn m-dsl-btn-outline m-dsl-btn-sm" @click="viewCardItems(cardsSource)">重试</button>
        </div>
        <div v-else-if="cardItems.length === 0" class="m-dsl-cards-empty">
          <MIcon name="list" :size="32" />
          <div>暂无卡密</div>
        </div>
        <div v-else class="m-dsl-cards-list">
          <div v-for="item in cardItems" :key="item.id" class="m-dsl-card-item">
            <div class="m-dsl-card-content">{{ item.content || item.cardKey || item.value || '-' }}</div>
            <span class="m-dsl-card-status" :class="`m-dsl-card-status-${cardStatusType(item.status)}`">
              {{ cardStatusLabel(item.status) }}
            </span>
          </div>
          <div v-if="cardsHasMore" class="m-dsl-cards-more">
            <button class="m-dsl-btn m-dsl-btn-outline m-dsl-btn-sm" :disabled="cardsLoadingMore" @click="loadMoreCards">
              {{ cardsLoadingMore ? '加载中...' : '加载更多' }}
            </button>
          </div>
          <div v-else class="m-dsl-cards-end">共 {{ cardsTotal }} 条</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import {
  getDeliverySources,
  createDeliverySource,
  updateDeliverySource,
  deleteDeliverySource
} from '../api/autoDelivery.js'
import { getCards, getCardItems } from '../api/cards.js'
import { uploadImage } from '../api/misc.js'
import { recordsOfOrThrow, totalOf } from '../utils/apiData.js'
import { confirmAction } from '../utils/confirmAction.js'
import { imageUploadValidationMessage } from '../utils/imageUploadPolicy.js'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])

const CARD_PLACEHOLDER = '{卡密占位}'

const loading = ref(true)
const loadingMore = ref(false)
const loadError = ref('')
const sources = ref([])
const sourcesAvailable = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const hasMore = ref(false)
const searchKeyword = ref('')
let searchTimer = null

const cardGroups = ref([])
const cardGroupsLoading = ref(false)

const showEditor = ref(false)
const editingId = ref(null)
const saving = ref(false)

const form = reactive({
  title: '',
  content: '',
  remark: '',
  deliveryMode: 'text',
  cardGroupId: '',
  fromMall: false,
  // V1.66: 文本发货支持多条正文 + 图片发货（仅 deliveryMode === 'text' && !fromMall 时启用）
  segments: []
})

// segments 编辑器：唯一 id 用于 v-for key 稳定
let _segmentUidSeed = 0
function _nextSegmentUid() {
  _segmentUidSeed += 1
  return `mseg_${Date.now()}_${_segmentUidSeed}`
}

function makeSegment(type = 'text') {
  return {
    _uid: _nextSegmentUid(),
    type,
    content: '',
    imageUrl: '',
    _uploading: false
  }
}

const segmentFileInputs = ref({})
function registerSegmentFileInput(idx, el) {
  if (el) segmentFileInputs.value[idx] = el
  else delete segmentFileInputs.value[idx]
}

function addSegment() {
  if (form.segments.length >= 20) return
  form.segments.push(makeSegment('text'))
}

function removeSegment(idx) {
  if (form.segments.length <= 1) return
  form.segments.splice(idx, 1)
}

function setSegmentType(idx, type) {
  const seg = form.segments[idx]
  if (!seg || seg.type === type) return
  seg.type = type
  if (type === 'text') {
    seg.imageUrl = ''
  } else {
    seg.content = ''
  }
}

function triggerSegmentImagePick(idx) {
  const input = segmentFileInputs.value[idx]
  if (input) input.click()
}

function clearSegmentImage(idx) {
  const seg = form.segments[idx]
  if (!seg) return
  seg.imageUrl = ''
}

async function onSegmentImagePick(idx, event) {
  const seg = form.segments[idx]
  const input = event?.target
  const file = input?.files?.[0]
  if (!seg || !file) return
  if (input) input.value = ''
  const validationMessage = imageUploadValidationMessage(file)
  if (validationMessage) {
    showToast(validationMessage, true)
    return
  }
  seg._uploading = true
  try {
    const res = await uploadImage(0, file)
    const data = res?.data
    const imageUrl = data?.imageUrl || data?.url || data?.data?.url || data?.data?.imageUrl || res?.imageUrl || res?.url || ''
    if (!imageUrl) throw new Error('图片上传成功但未返回可发送地址')
    seg.imageUrl = imageUrl
  } catch (e) {
    showToast(e?.message || '图片上传失败', true)
  } finally {
    seg._uploading = false
  }
}

const showCards = ref(false)
const cardsSource = ref(null)
const cardItems = ref([])
const cardsLoading = ref(false)
const cardsLoadingMore = ref(false)
const cardsError = ref('')
const cardsTotal = ref(0)
const cardsPage = ref(1)
const cardsPageSize = ref(50)
const cardsHasMore = ref(false)

const hasFilter = computed(() => Boolean(searchKeyword.value))

const cardGroupMap = computed(() => {
  const map = new Map()
  for (const g of cardGroups.value) {
    map.set(String(g.id), g)
  }
  return map
})

const statCards = computed(() => {
  const list = sources.value || []
  const totalCount = list.length
  let availableStock = 0
  let usedStock = 0
  for (const r of list) {
    if (r.deliveryMode === 'card') {
      const remain = Number(r.cardRemainCount ?? 0)
      availableStock += remain
      const group = r.cardGroupId ? cardGroupMap.value.get(String(r.cardGroupId)) : null
      const groupTotal = Number(group?.totalCount ?? r.cardTotalCount ?? 0)
      if (groupTotal > 0) {
        usedStock += Math.max(0, groupTotal - remain)
      }
    }
  }
  const lowStock = list.filter(r => r.deliveryMode === 'card' && (r.cardRemainCount ?? 0) <= 0).length
  return [
    { key: 'total', title: '货源总数', value: totalCount, desc: '全部货源条目', icon: 'package', color: 'blue' },
    { key: 'available', title: '可用库存', value: availableStock, desc: '卡密剩余总数', icon: 'key', color: 'green' },
    { key: 'used', title: '已用库存', value: usedStock, desc: '卡密已消耗', icon: 'shoppingCart', color: 'orange' },
    { key: 'low', title: '库存预警', value: lowStock, desc: lowStock > 0 ? '需补充库存' : '库存充足', icon: 'warning', color: 'red' }
  ]
})

const selectedCardGroup = computed(() => {
  const id = form.cardGroupId
  if (!id) return null
  return cardGroups.value.find(g => String(g.id) === String(id)) || null
})

const selectedCardRemainCount = computed(() => {
  const group = selectedCardGroup.value
  return group ? Number(group.remainCount ?? 0) : 0
})

function formatDate(value) {
  if (!value) return '-'
  const str = String(value).replace('T', ' ')
  return str.slice(0, 10) || '-'
}

function cardStatusLabel(status) {
  const map = { 0: '未使用', 1: '已锁定', 2: '已使用', 3: '已作废', 4: '异常' }
  return map[Number(status)] ?? String(status ?? '-')
}

function cardStatusType(status) {
  const n = Number(status)
  if (n === 0) return 'green'
  if (n === 2) return 'gray'
  if (n === 1) return 'orange'
  return 'red'
}

function showToast(message, isError = false) {
  window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message, isError } }))
}

async function loadCardGroups() {
  if (cardGroups.value.length > 0 || cardGroupsLoading.value) return
  cardGroupsLoading.value = true
  try {
    const res = await getCards({ current: 1, size: 200 })
    cardGroups.value = recordsOfOrThrow(res?.data, '卡密分组响应格式异常')
  } catch (e) {
    cardGroups.value = []
  } finally {
    cardGroupsLoading.value = false
  }
}

async function loadSources(append = false) {
  if (!append) {
    loading.value = true
  } else {
    loadingMore.value = true
  }
  loadError.value = ''
  try {
    const params = {
      current: page.value,
      size: pageSize.value
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const res = await getDeliverySources(params)
    const list = recordsOfOrThrow(res?.data, '货源列表响应格式异常')
    total.value = totalOf(res?.data, list.length)
    if (append) {
      sources.value = [...sources.value, ...list]
    } else {
      sources.value = list
    }
    hasMore.value = sources.value.length < total.value
    sourcesAvailable.value = true
    // 静默加载卡密分组用于统计与表单
    loadCardGroups().catch(() => {})
  } catch (e) {
    if (!append) sources.value = []
    sourcesAvailable.value = false
    loadError.value = e?.message || '货源库加载失败，请稍后重试'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  page.value++
  await loadSources(true)
}

function handleSearch() {
  page.value = 1
  loadSources()
}

function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    handleSearch()
  }, 400)
}

function clearSearch() {
  searchKeyword.value = ''
  handleSearch()
}

function openCreate() {
  if (!sourcesAvailable.value) return
  editingId.value = null
  Object.assign(form, {
    title: '',
    content: '',
    remark: '',
    deliveryMode: 'text',
    cardGroupId: '',
    fromMall: false
  })
  // 初始化一条空 segment（文本模式默认显示 segments 编辑器）
  form.segments = [makeSegment('text')]
  showEditor.value = true
  document.body.style.overflow = 'hidden'
  loadCardGroups().catch(() => {})
}

function openEdit(src) {
  if (!sourcesAvailable.value) return
  editingId.value = src.id
  Object.assign(form, {
    title: src.title || '',
    content: src.content || '',
    remark: src.remark || '',
    deliveryMode: src.deliveryMode === 'card' ? 'card' : 'text',
    cardGroupId: src.cardGroupId ?? '',
    fromMall: !!src.fromMall
  })
  // 加载已有 segments：若货源已配置 segments 则回填，否则用 content 作为第一条文本
  const rawSegments = Array.isArray(src.segments) ? src.segments : []
  if (rawSegments.length > 0) {
    form.segments = rawSegments.map(seg => ({
      _uid: _nextSegmentUid(),
      type: seg.type === 'image' ? 'image' : 'text',
      content: seg.content || '',
      imageUrl: seg.imageUrl || '',
      _uploading: false
    }))
  } else {
    const first = makeSegment('text')
    first.content = src.content || ''
    form.segments = [first]
  }
  showEditor.value = true
  document.body.style.overflow = 'hidden'
  loadCardGroups().catch(() => {})
}

function closeEditor() {
  showEditor.value = false
  editingId.value = null
  saving.value = false
  document.body.style.overflow = ''
}

function setDeliveryMode(mode) {
  if (form.fromMall) return
  form.deliveryMode = mode
  if (mode !== 'card') {
    form.cardGroupId = ''
  }
}

function insertCardPlaceholder() {
  form.content = (form.content || '') + CARD_PLACEHOLDER
}

async function saveSource() {
  if (!sourcesAvailable.value) return
  if (!form.title || !form.title.trim()) {
    showToast('请填写标题', true)
    return
  }
  const isTextMode = form.deliveryMode === 'text' && !form.fromMall

  // 卡密发货 / 商城货源：校验单条 content
  if (!isTextMode) {
    if (!form.content || !form.content.trim()) {
      showToast('请填写正文', true)
      return
    }
    if (form.deliveryMode === 'card') {
      if (!form.cardGroupId) {
        showToast('卡密发货模式下必须选择一个卡密分组', true)
        return
      }
      if (!form.content.includes(CARD_PLACEHOLDER)) {
        showToast(`卡密发货的正文必须包含 ${CARD_PLACEHOLDER} 占位符`, true)
        return
      }
    }
  }

  // 文本发货模式：segments 校验 + 互斥校验 + 构造清洗后的 segments
  let cleanedSegments = null
  if (isTextMode) {
    if (!Array.isArray(form.segments) || form.segments.length === 0) {
      showToast('请至少配置一条正文', true)
      return
    }
    if (form.segments.length > 20) {
      showToast('正文条数过多，最多支持 20 条', true)
      return
    }
    const cleaned = []
    for (let i = 0; i < form.segments.length; i++) {
      const seg = form.segments[i]
      const type = seg.type === 'image' ? 'image' : 'text'
      const content = (seg.content || '').trim()
      const imageUrl = (seg.imageUrl || '').trim()
      if (type === 'image') {
        if (!imageUrl) {
          showToast(`第 ${i + 1} 条正文为图片类型，必须上传图片`, true)
          return
        }
        if (content) {
          showToast(`第 ${i + 1} 条为图片类型，不能同时填写文本`, true)
          return
        }
        cleaned.push({ type: 'image', imageUrl })
      } else {
        if (!content) {
          showToast(`第 ${i + 1} 条正文内容不能为空`, true)
          return
        }
        if (imageUrl) {
          showToast(`第 ${i + 1} 条为文本类型，不能同时上传图片`, true)
          return
        }
        if (content.length > 5000) {
          showToast(`第 ${i + 1} 条正文内容超过 5000 字符`, true)
          return
        }
        cleaned.push({ type: 'text', content })
      }
    }
    cleanedSegments = cleaned
    const firstText = cleaned.find(s => s.type === 'text')
    form.content = firstText ? firstText.content : (cleaned[0]?.imageUrl ? '[图片]' : '')
  }

  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content,
      remark: form.remark,
      deliveryMode: form.deliveryMode,
      cardGroupId: form.deliveryMode === 'card' ? form.cardGroupId : null
    }
    if (isTextMode && cleanedSegments) {
      payload.segments = cleanedSegments
    } else {
      payload.segments = null
    }
    if (editingId.value) {
      await updateDeliverySource(editingId.value, payload)
      showToast('货源已更新')
    } else {
      await createDeliverySource(payload)
      showToast('货源已新增')
    }
    closeEditor()
    page.value = 1
    await loadSources()
  } catch (e) {
    showToast(e?.message || '保存失败', true)
  } finally {
    saving.value = false
  }
}

async function removeSource(src) {
  if (!sourcesAvailable.value) return
  const confirmed = await confirmAction({
    title: '确认删除该货源？',
    description: '删除后不会自动解除商品上的既有配置，请确认后继续。',
    dangerous: true,
    confirmText: '删除'
  })
  if (!confirmed) return
  try {
    await deleteDeliverySource(src.id)
    showToast('货源已删除')
    if (cardsSource.value?.id === src.id) {
      closeCards()
    }
    page.value = 1
    await loadSources()
  } catch (e) {
    showToast(e?.message || '删除失败', true)
  }
}

async function viewCardItems(src) {
  if (!src || !src.cardGroupId) return
  cardsSource.value = src
  cardsPage.value = 1
  cardItems.value = []
  cardsError.value = ''
  cardsTotal.value = 0
  cardsHasMore.value = false
  showCards.value = true
  document.body.style.overflow = 'hidden'
  await fetchCardItems()
}

async function fetchCardItems(append = false) {
  const src = cardsSource.value
  if (!src || !src.cardGroupId) return
  if (!append) {
    cardsLoading.value = true
  } else {
    cardsLoadingMore.value = true
  }
  cardsError.value = ''
  try {
    const res = await getCardItems(src.cardGroupId, {
      current: cardsPage.value,
      size: cardsPageSize.value
    })
    const list = recordsOfOrThrow(res?.data, '卡密列表响应格式异常')
    cardsTotal.value = totalOf(res?.data, list.length)
    if (append) {
      cardItems.value = [...cardItems.value, ...list]
    } else {
      cardItems.value = list
    }
    cardsHasMore.value = cardItems.value.length < cardsTotal.value
  } catch (e) {
    if (!append) cardItems.value = []
    cardsError.value = e?.message || '卡密列表加载失败'
  } finally {
    cardsLoading.value = false
    cardsLoadingMore.value = false
  }
}

async function loadMoreCards() {
  if (cardsLoadingMore.value || !cardsHasMore.value) return
  cardsPage.value++
  await fetchCardItems(true)
}

function closeCards() {
  showCards.value = false
  cardsSource.value = null
  cardItems.value = []
  cardsError.value = ''
  document.body.style.overflow = ''
}

onMounted(() => {
  loadSources()
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.m-dsl {
  padding: var(--m-space-2) var(--m-space-4) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-dsl-stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-2);
}

.m-dsl-stat-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
}

.m-dsl-stat-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-dsl-stat-icon-blue {
  background: var(--m-color-info-bg);
  color: var(--m-color-info-text);
}
.m-dsl-stat-icon-green {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-dsl-stat-icon-orange {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-dsl-stat-icon-red {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}

.m-dsl-stat-info {
  flex: 1;
  min-width: 0;
}
.m-dsl-stat-title {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.m-dsl-stat-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
}
.m-dsl-stat-desc {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  margin-top: 2px;
}
.m-dsl-stat-desc-blue { color: var(--m-color-info-text); }
.m-dsl-stat-desc-green { color: var(--m-color-success-text); }
.m-dsl-stat-desc-orange { color: var(--m-color-warning-text); }
.m-dsl-stat-desc-red { color: var(--m-color-danger-text); }

.m-dsl-notice {
  background: var(--m-color-warning-bg);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-3);
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
}
.m-dsl-notice-icon {
  color: var(--m-color-warning);
  flex-shrink: 0;
  margin-top: 1px;
}
.m-dsl-notice-text {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-warning-text);
  line-height: var(--m-line-height-relaxed);
  flex: 1;
}
.m-dsl-notice-text b {
  font-weight: var(--m-font-weight-semibold);
}

.m-dsl-toolbar {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
}
.m-dsl-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-3);
  height: 44px;
  min-width: 0;
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-search-icon {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}
.m-dsl-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: transparent;
  min-width: 0;
}
.m-dsl-search-input::placeholder {
  color: var(--m-color-text-tertiary);
}
.m-dsl-search-clear {
  width: 28px;
  height: 28px;
  border: none;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
}

.m-dsl-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  transition: all 0.15s;
  padding: var(--m-space-2) var(--m-space-4);
  min-height: 40px;
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-btn:active { transform: scale(0.97); }
.m-dsl-btn-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}
.m-dsl-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-dsl-btn-outline {
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
}
.m-dsl-btn-sm {
  padding: var(--m-space-2) var(--m-space-3);
  font-size: var(--m-font-size-caption);
  min-height: 36px;
}

.m-dsl-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-dsl-skeleton-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-skeleton-line {
  height: 14px;
  border-radius: var(--m-radius-sm);
  background: var(--m-color-bg-subtle);
}
.m-dsl-skeleton-title { width: 60%; height: 18px; }
.m-dsl-skeleton-meta { width: 40%; height: 12px; }
.m-dsl-skeleton-content { width: 90%; height: 12px; }
.m-dsl-skeleton-tags { display: flex; gap: var(--m-space-2); }
.m-dsl-skeleton-tag {
  width: 70px;
  height: 20px;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-bg-subtle);
}

.m-dsl-empty {
  text-align: center;
  padding: 50px var(--m-space-5);
}
.m-dsl-empty-icon {
  width: 76px;
  height: 76px;
  margin: 0 auto var(--m-space-3);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-dsl-empty-text {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
}
.m-dsl-empty-desc {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-4);
}

.m-dsl-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}

.m-dsl-source-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
}

.m-dsl-source-header {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-2);
}
.m-dsl-source-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-dsl-source-icon-card {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-dsl-source-icon-text {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-dsl-source-title-wrap {
  flex: 1;
  min-width: 0;
}
.m-dsl-source-title {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-base);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}
.m-dsl-source-tags {
  display: flex;
  gap: var(--m-space-1);
  flex-wrap: wrap;
  margin-top: var(--m-space-1);
}
.m-dsl-tag {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  padding: 3px var(--m-space-2);
  border-radius: var(--m-radius-pill);
  white-space: nowrap;
}
.m-dsl-tag-gray {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-dsl-tag-orange {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-dsl-tag-purple {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}

.m-dsl-source-remark {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-1);
  line-height: var(--m-line-height-base);
}

.m-dsl-source-content {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-relaxed);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  margin-bottom: var(--m-space-2);
  max-height: 100px;
  overflow-y: auto;
  word-break: break-all;
  white-space: pre-wrap;
}

.m-dsl-source-footer {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-space-2);
  padding: var(--m-space-2) 0;
  margin-bottom: var(--m-space-2);
}
.m-dsl-source-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.m-dsl-source-stat-label {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  white-space: nowrap;
}
.m-dsl-source-stat-value {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.m-dsl-source-stat-value.muted {
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}
.m-dsl-source-stat-value.low {
  color: var(--m-color-danger-text);
}

.m-dsl-source-actions {
  display: flex;
  gap: var(--m-space-2);
  flex-wrap: wrap;
}
.m-dsl-action-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  padding: 7px var(--m-space-3);
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-action-btn:active {
  transform: scale(0.97);
  background: var(--m-color-bg-hover);
}
.m-dsl-action-danger {
  color: var(--m-color-danger);
}
.m-dsl-action-danger:active {
  background: var(--m-color-danger-bg);
}

.m-dsl-loading-more,
.m-dsl-load-more,
.m-dsl-no-more {
  text-align: center;
  padding: var(--m-space-5);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
}

.m-dsl-safe-bottom {
  height: calc(84px + env(safe-area-inset-bottom));
}

.m-dsl-sheet-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-drawer);
  z-index: 200;
  backdrop-filter: blur(2px);
}

.m-dsl-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;
  z-index: 201;
  transform: translateY(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom);
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-sheet-open {
  transform: translateY(0);
}
.m-dsl-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-4) var(--m-space-5);
  flex-shrink: 0;
}
.m-dsl-sheet-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-dsl-sheet-close {
  width: 36px;
  height: 36px;
  border: none;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-secondary);
  cursor: pointer;
  flex-shrink: 0;
}
.m-dsl-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-space-4) var(--m-space-5);
}

.m-dsl-info-tip {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-info-bg);
  color: var(--m-color-info-text);
  font-size: var(--m-font-size-caption);
  line-height: var(--m-line-height-relaxed);
  margin-bottom: var(--m-space-4);
}
.m-dsl-info-tip svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.m-dsl-form-row {
  margin-bottom: var(--m-space-4);
}
.m-dsl-form-label {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
}
.m-dsl-required {
  color: var(--m-color-danger);
}
.m-dsl-input {
  width: 100%;
  height: 44px;
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  outline: none;
  box-sizing: border-box;
  transition: box-shadow 0.15s;
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-input:focus {
  box-shadow: 0 0 0 3px var(--m-color-primary-bg);
}
.m-dsl-textarea {
  width: 100%;
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  line-height: var(--m-line-height-relaxed);
  resize: vertical;
  min-height: 100px;
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
  transition: box-shadow 0.15s;
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-textarea:focus {
  box-shadow: 0 0 0 3px var(--m-color-primary-bg);
}
.m-dsl-textarea::placeholder {
  color: var(--m-color-text-tertiary);
}
.m-dsl-insert-btn {
  margin-left: auto;
  padding: 3px var(--m-space-2);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  border-radius: var(--m-radius-lg);
  cursor: pointer;
}
.m-dsl-insert-btn:active {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

/* V1.66: segments 编辑器（多条正文 + 图片发货） */
.m-dsl-segments {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}

.m-dsl-segment {
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-card);
  padding: var(--m-space-3);
}

.m-dsl-segment-header {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-2);
}

.m-dsl-segment-index {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
}

.m-dsl-segment-switch {
  display: inline-flex;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-pill);
  overflow: hidden;
  background: var(--m-color-bg-card);
}

.m-dsl-segment-switch-btn {
  padding: 4px 14px;
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
}
.m-dsl-segment-switch-btn.active {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-dsl-segment-remove {
  margin-left: auto;
  width: 28px;
  height: 28px;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-danger-bg);
  border: none;
  color: var(--m-color-danger-text);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.m-dsl-segment-body {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}

.m-dsl-segment-image {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}

.m-dsl-segment-image-preview-wrap {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-3);
  padding: var(--m-space-2);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-card);
}

.m-dsl-segment-image-preview {
  width: 96px;
  height: 96px;
  object-fit: cover;
  border-radius: var(--m-radius-md);
  flex-shrink: 0;
}

.m-dsl-segment-image-actions {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  align-items: flex-start;
  padding-top: var(--m-space-1);
}

.m-dsl-segment-image-btn {
  padding: 4px 12px;
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-primary);
  background: var(--m-color-primary-bg);
  border: none;
  border-radius: var(--m-radius-pill);
  cursor: pointer;
}
.m-dsl-segment-image-btn.danger {
  color: var(--m-color-danger-text);
  background: var(--m-color-danger-bg);
}

.m-dsl-segment-image-upload {
  padding: var(--m-space-4);
  border: 1.5px dashed var(--m-color-border);
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-page);
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-dsl-segment-image-upload-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-1);
  padding: var(--m-space-2) var(--m-space-4);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-primary);
  background: var(--m-color-primary-bg);
  border: 1px solid var(--m-color-primary);
  border-radius: var(--m-radius-pill);
  cursor: pointer;
}
.m-dsl-segment-image-upload-btn:disabled {
  opacity: .6;
  cursor: not-allowed;
}

.m-dsl-add-segment-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  padding: var(--m-space-2) var(--m-space-3);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-primary);
  background: var(--m-color-primary-bg);
  border: 1px dashed var(--m-color-primary);
  border-radius: var(--m-radius-pill);
  cursor: pointer;
  align-self: flex-start;
}
.m-dsl-add-segment-btn:active {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-dsl-segments-tip {
  padding: var(--m-space-2) var(--m-space-3);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  line-height: var(--m-line-height-base);
}

.m-dsl-seg {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-2);
}
.m-dsl-seg-btn {
  height: 44px;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-seg-btn:active {
  background: var(--m-color-bg-hover);
}
.m-dsl-seg-btn.active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-dsl-seg-btn.disabled,
.m-dsl-seg-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-dsl-form-hint {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  margin-top: var(--m-space-2);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
}
.m-dsl-form-hint.danger {
  color: var(--m-color-danger-text);
}
.m-dsl-form-hint b {
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-bold);
}
.m-dsl-form-hint b.m-dsl-danger {
  color: var(--m-color-danger-text);
}

.m-dsl-select {
  width: 100%;
  height: 44px;
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  outline: none;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M4.5 6l3.5 3.5L11.5 6' stroke='%2394a3b8' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right var(--m-space-3) center;
  cursor: pointer;
  box-shadow: var(--m-shadow-xs);
}

.m-dsl-sheet-footer {
  display: flex;
  gap: var(--m-space-2);
  padding: var(--m-space-3) var(--m-space-5) var(--m-space-4);
  flex-shrink: 0;
}
.m-dsl-sheet-footer .m-dsl-btn {
  flex: 1;
}

.m-dsl-cards-header {
  padding: var(--m-space-3) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  margin-bottom: var(--m-space-3);
}
.m-dsl-cards-source-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
}
.m-dsl-cards-source-meta {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-dsl-cards-loading,
.m-dsl-cards-empty {
  text-align: center;
  padding: 40px var(--m-space-5);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
}

.m-dsl-cards-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-dsl-card-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-2);
  padding: var(--m-space-3) var(--m-space-3);
  border-radius: var(--m-radius-xl);
  background: var(--m-color-bg-card);
  box-shadow: var(--m-shadow-xs);
}
.m-dsl-card-content {
  flex: 1;
  min-width: 0;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  font-family: var(--m-font-family-mono);
  word-break: break-all;
  line-height: var(--m-line-height-base);
}
.m-dsl-card-status {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  padding: 3px var(--m-space-2);
  border-radius: var(--m-radius-pill);
  white-space: nowrap;
  flex-shrink: 0;
}
.m-dsl-card-status-green {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-dsl-card-status-gray {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-dsl-card-status-orange {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-dsl-card-status-red {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
}

.m-dsl-cards-more {
  text-align: center;
  padding: var(--m-space-3) 0;
}
.m-dsl-cards-end {
  text-align: center;
  padding: var(--m-space-3) 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

@media (max-width: 360px) {
  .m-dsl { padding: var(--m-space-2) var(--m-space-3) 0; }
  .m-dsl-stats-grid { gap: var(--m-space-2); }
  .m-dsl-stat-card { padding: var(--m-space-3); gap: var(--m-space-2); }
  .m-dsl-stat-icon { width: 40px; height: 40px; }
  .m-dsl-stat-value { font-size: var(--m-font-size-h2); }
  .m-dsl-source-footer { gap: var(--m-space-1); }
  .m-dsl-source-stat-value { font-size: var(--m-font-size-caption); }
}

@media (min-width: 430px) {
  .m-dsl-stats-grid { gap: var(--m-space-3); }
  .m-dsl-stat-card { padding: var(--m-space-4); }
}
</style>
