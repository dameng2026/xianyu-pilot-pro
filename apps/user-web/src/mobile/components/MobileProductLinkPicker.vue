<template>
  <Teleport to="body">
    <transition name="m-picker-fade">
      <div v-if="visible" class="m-picker-mask" role="dialog" aria-modal="true" @click.self="onClose">
        <div class="m-picker-sheet" aria-label="选择商品链接" role="dialog">
          <div class="m-picker-header">
            <button type="button" class="m-picker-close" aria-label="关闭" @click="onClose">
              <MIcon name="x" :size="20" />
            </button>
            <h3>选择商品链接</h3>
            <span class="m-picker-header-spacer"></span>
          </div>

          <div class="m-picker-search">
            <MIcon name="search" :size="18" />
            <input
              v-model="keyword"
              type="search"
              placeholder="搜索商品名称或 ID"
              aria-label="搜索商品"
              @keydown.enter.prevent="onSearch"
            />
            <button v-if="keyword" type="button" class="m-picker-clear" aria-label="清空" @click="onClearKeyword">
              <MIcon name="x" :size="14" />
            </button>
          </div>

          <div class="m-picker-body">
            <div v-if="loading" class="m-picker-loading" role="status" aria-live="polite">
              <div class="m-picker-spinner"></div>
              <span>正在加载商品...</span>
            </div>

            <MobileUnavailableState
              v-else-if="loadError"
              compact
              title="商品列表加载失败"
              :description="loadError"
              @retry="loadGoods"
            />

            <div v-else-if="filteredGoods.length === 0" class="m-picker-empty">
              <MIcon name="bag" :size="40" />
              <span>{{ keyword ? '未找到匹配的商品' : '暂无可选商品' }}</span>
              <small v-if="!keyword && accountId">当前账号下没有商品，请先在商品管理中添加</small>
            </div>

            <div v-else class="m-picker-list">
              <button
                v-for="prod in filteredGoods"
                :key="prod.id || prod.itemId"
                type="button"
                class="m-picker-item"
                @click="onSelect(prod)"
              >
                <div class="m-picker-item-cover">
                  <img
                    v-if="coverUrlOf(prod)"
                    :src="coverUrlOf(prod)"
                    :alt="prod.name || prod.title"
                    class="m-picker-item-img"
                    loading="lazy"
                  />
                  <div v-else class="m-picker-item-placeholder">
                    <MIcon name="bag" :size="22" />
                  </div>
                </div>
                <div class="m-picker-item-info">
                  <div class="m-picker-item-name">{{ prod.name || prod.title || '未命名商品' }}</div>
                  <div class="m-picker-item-meta">
                    <span class="m-picker-item-price">¥{{ formatPrice(prod.price ?? prod.soldPrice) }}</span>
                    <span v-if="getItemId(prod)" class="m-picker-item-id">ID：{{ getItemId(prod) }}</span>
                  </div>
                </div>
                <MIcon name="chevronRight" :size="18" class="m-picker-item-arrow" />
              </button>

              <div v-if="hasMore && !loading" class="m-picker-load-more">
                <button type="button" :disabled="loadingMore" @click="loadMore">
                  {{ loadingMore ? '加载中...' : '加载更多' }}
                </button>
              </div>
              <div class="m-picker-list-total">共 {{ total }} 个商品</div>
            </div>
          </div>

          <div class="m-picker-footer">
            <small>选中商品后将插入商品链接到输入框</small>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import MIcon from '../MIcon.vue'
import MobileUnavailableState from '../MobileUnavailableState.vue'
import { getGoods } from '../../api/goods.js'
import { resolveTrustedMediaUrl } from '../../utils/safeMediaUrl.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  accountId: { type: Number, default: 0 },
  pageSize: { type: Number, default: 20 },
})

const emit = defineEmits(['close', 'select'])

const keyword = ref('')
const goods = ref([])
const total = ref(0)
const currentPage = ref(1)
const loading = ref(false)
const loadingMore = ref(false)
const loadError = ref('')

const hasMore = computed(() => goods.value.length < total.value)

const filteredGoods = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return goods.value
  return goods.value.filter(p => {
    const name = String(p.name || p.title || '').toLowerCase()
    const id = String(p.id || p.itemId || '').toLowerCase()
    return name.includes(kw) || id.includes(kw)
  })
})

function coverUrlOf(prod) {
  if (!prod) return ''
  return resolveTrustedMediaUrl(prod.coverPic || prod.imageUrl || prod.mainImage || prod.picUrl || '')
}

function getItemId(prod) {
  return prod.itemId || prod.id || prod.xyGoodsId || ''
}

function formatPrice(price) {
  if (price == null || price === '') return '—'
  const num = Number(price)
  if (isNaN(num)) return String(price)
  return num.toFixed(2)
}

async function loadGoods() {
  if (!props.accountId) {
    loadError.value = '请先选择账号'
    return
  }
  loading.value = true
  loadError.value = ''
  currentPage.value = 1
  try {
    const res = await getGoods({
      page: 1,
      pageSize: props.pageSize,
      xianyuAccountId: props.accountId,
    })
    const data = res?.data
    if (data?.records) {
      goods.value = data.records
      total.value = data.total || data.totalCount || data.records.length
    } else if (data?.list) {
      goods.value = data.list
      total.value = data.total || data.list.length
    } else if (Array.isArray(data)) {
      goods.value = data
      total.value = data.length
    } else {
      goods.value = []
      total.value = 0
    }
  } catch (e) {
    goods.value = []
    total.value = 0
    loadError.value = e?.message || '加载失败，请检查网络后重试'
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const nextPage = currentPage.value + 1
    const res = await getGoods({
      page: nextPage,
      pageSize: props.pageSize,
      xianyuAccountId: props.accountId,
    })
    const data = res?.data
    const list = data?.records || data?.list || (Array.isArray(data) ? data : [])
    if (list.length) {
      goods.value = [...goods.value, ...list]
      currentPage.value = nextPage
    }
  } catch {
    // 加载更多失败不阻塞，静默处理
  } finally {
    loadingMore.value = false
  }
}

function onSearch() {
  // 关键字过滤为前端过滤，无需重新请求
}

function onClearKeyword() {
  keyword.value = ''
}

function onSelect(prod) {
  const itemId = getItemId(prod)
  const link = itemId ? `https://www.goofish.com/item?itemId=${itemId}` : ''
  emit('select', {
    itemId,
    title: prod.name || prod.title || '未命名商品',
    price: prod.price ?? prod.soldPrice,
    picUrl: coverUrlOf(prod),
    link,
    raw: prod,
  })
}

function onClose() {
  if (loading.value) return
  emit('close')
}

watch(
  () => props.visible,
  visible => {
    if (visible) {
      keyword.value = ''
      if (props.accountId && goods.value.length === 0) {
        loadGoods()
      } else if (!props.accountId) {
        loadError.value = '请先选择账号'
      }
    }
  }
)

watch(
  () => props.accountId,
  accountId => {
    if (props.visible && accountId) {
      goods.value = []
      loadGoods()
    }
  }
)
</script>

<style scoped>
.m-picker-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: var(--m-mask-modal);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.m-picker-sheet {
  width: 100%;
  max-width: 100%;
  max-height: 85vh;
  background: var(--m-color-bg-elevated);
  border-top-left-radius: var(--m-radius-xl);
  border-top-right-radius: var(--m-radius-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: env(safe-area-inset-bottom);
  box-shadow: var(--m-shadow-xs);
}
.m-picker-header {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-3) var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-picker-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  flex: 1;
}
.m-picker-header-spacer { width: var(--m-space-8); }
.m-picker-close {
  width: var(--m-space-8);
  height: var(--m-space-8);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-bg-subtle);
  border: none;
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.m-picker-close:active { background: var(--m-color-bg-hover); }

.m-picker-search {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-4);
  background: var(--m-color-bg-page);
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-picker-search :deep(svg) { color: var(--m-color-text-tertiary); flex-shrink: 0; }
.m-picker-search input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-body);
  padding: var(--m-space-1) 0;
}
.m-picker-search input::placeholder { color: var(--m-color-text-placeholder); }
.m-picker-clear {
  width: 22px;
  height: 22px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-border);
  border: none;
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.m-picker-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: var(--m-space-2) 0 var(--m-space-3);
}
.m-picker-loading,
.m-picker-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-12) var(--m-space-5);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}
.m-picker-empty small { color: var(--m-color-text-disabled); font-size: var(--m-font-size-caption); text-align: center; }
.m-picker-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--m-color-border-light);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-picker-spin 0.8s linear infinite;
}
@keyframes m-picker-spin { to { transform: rotate(360deg); } }

.m-picker-list {
  display: flex;
  flex-direction: column;
}
.m-picker-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-4);
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--m-color-border-light);
  cursor: pointer;
  text-align: left;
  width: 100%;
}
.m-picker-item:active { background: var(--m-color-primary-bg); }
.m-picker-item:last-of-type { border-bottom: none; }
.m-picker-item-cover {
  width: 56px;
  height: 56px;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  background: var(--m-color-bg-subtle);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-disabled);
}
.m-picker-item-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-picker-item-placeholder {
  color: var(--m-color-text-disabled);
}
.m-picker-item-info {
  flex: 1;
  min-width: 0;
}
.m-picker-item-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: var(--m-line-height-base);
  margin-bottom: var(--m-space-1);
}
.m-picker-item-meta {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-caption);
}
.m-picker-item-price {
  color: var(--m-color-warning);
  font-weight: var(--m-font-weight-bold);
}
.m-picker-item-id {
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-tiny);
}
.m-picker-item-arrow {
  color: var(--m-color-text-disabled);
  flex-shrink: 0;
}

.m-picker-load-more {
  padding: var(--m-space-3) var(--m-space-4);
  text-align: center;
}
.m-picker-load-more button {
  padding: var(--m-space-2) var(--m-space-5);
  border-radius: var(--m-radius-lg);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-primary);
  font-size: var(--m-font-size-body-sm);
  cursor: pointer;
  box-shadow: var(--m-shadow-xs);
}
.m-picker-load-more button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.m-picker-list-total {
  padding: var(--m-space-3) var(--m-space-4) var(--m-space-1);
  text-align: center;
  color: var(--m-color-text-disabled);
  font-size: var(--m-font-size-caption);
}

.m-picker-footer {
  padding: var(--m-space-2) var(--m-space-4);
  border-top: 1px solid var(--m-color-border-light);
  background: var(--m-color-bg-page);
  text-align: center;
}
.m-picker-footer small {
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
}

.m-picker-fade-enter-active,
.m-picker-fade-leave-active {
  transition: opacity 0.2s ease;
}
.m-picker-fade-enter-active .m-picker-sheet,
.m-picker-fade-leave-active .m-picker-sheet {
  transition: transform 0.25s ease;
}
.m-picker-fade-enter-from,
.m-picker-fade-leave-to {
  opacity: 0;
}
.m-picker-fade-enter-from .m-picker-sheet,
.m-picker-fade-leave-to .m-picker-sheet {
  transform: translateY(100%);
}
</style>
