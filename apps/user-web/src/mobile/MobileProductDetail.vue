<template>
  <div class="m-product-detail">
    <div v-if="loading" class="m-loading-state">
      <div class="m-loading-spinner"></div>
      <span>加载中...</span>
    </div>

    <div v-else-if="loadError" class="m-error-state">
      <MIcon name="alertCircle" :size="48" color="#ff4757" />
      <div class="m-error-text">{{ loadError }}</div>
      <button class="m-retry-btn" @click="loadProduct">重试</button>
    </div>

    <template v-else>
      <div class="m-product-hero">
        <div class="m-hero-images">
          <div class="m-main-image">
            <img
              v-if="formData.imageUrls[0] || formData.mainImageUrl"
              :src="formData.imageUrls[0] || formData.mainImageUrl"
              :alt="formData.title"
              class="m-img-main"
            />
            <div v-else class="m-img-placeholder">
              <MIcon name="image" :size="48" />
            </div>
          </div>
          <div v-if="formData.imageUrls.length > 1" class="m-image-thumbs">
            <div
              v-for="(img, idx) in formData.imageUrls.slice(0, 4)"
              :key="idx"
              class="m-thumb-item"
              :class="{ active: idx === 0 }"
            >
              <img :src="img" alt="" class="m-thumb-img" />
            </div>
            <div v-if="formData.imageUrls.length > 4" class="m-thumb-more">
              +{{ formData.imageUrls.length - 4 }}
            </div>
          </div>
        </div>

        <div class="m-hero-info">
          <div class="m-status-row">
            <span class="m-status-badge" :class="statusClass">{{ statusText }}</span>
            <button
              class="m-toggle-status"
              :class="{ on: isOnShelf }"
              @click="toggleStatus"
            >
              <span class="m-toggle-track">
                <span class="m-toggle-thumb"></span>
              </span>
              {{ isOnShelf ? '已上架' : '已下架' }}
            </button>
          </div>
          <h1 class="m-product-title">{{ formData.title || '未命名商品' }}</h1>
          <div class="m-price-row">
            <span class="m-price-symbol">¥</span>
            <span class="m-price-value">{{ formatPrice(formData.price) }}</span>
            <span v-if="formData.originalPrice > formData.price" class="m-price-original">
              ¥{{ formatPrice(formData.originalPrice) }}
            </span>
          </div>
          <div class="m-meta-row">
            <span class="m-meta-item">
              <MIcon name="database" :size="14" />
              库存 {{ formData.stock }}
            </span>
            <span v-if="formData.sales || formData.soldCount" class="m-meta-item">
              <MIcon name="trendingUp" :size="14" />
              已售 {{ formData.sales || formData.soldCount || 0 }}
            </span>
          </div>
        </div>
      </div>

      <div class="m-tabs-nav">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="m-tab-btn"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="m-form-content">
        <div v-if="activeTab === 'basic'" class="m-tab-panel">
          <div class="m-form-section">
            <div class="m-section-title">商品图片</div>
            <div class="m-image-upload">
              <div class="m-upload-grid">
                <div
                  v-for="(img, idx) in formData.imageUrls"
                  :key="idx"
                  class="m-upload-item"
                >
                  <img :src="img" alt="" class="m-upload-img" />
                  <button class="m-remove-img" @click="removeImage(idx)">
                    <MIcon name="x" :size="14" />
                  </button>
                </div>
                <div
                  v-if="formData.imageUrls.length < 10"
                  class="m-upload-add"
                  @click="triggerImageUpload"
                >
                  <MIcon name="camera" :size="24" />
                  <span>添加图片</span>
                </div>
              </div>
              <input
                ref="imageInputRef"
                type="file"
                accept="image/*"
                multiple
                class="m-file-input"
                @change="handleImageUpload"
              />
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">基本信息</div>
            <div class="m-form-field">
              <label class="m-field-label">商品名称 <span class="m-required">*</span></label>
              <input
                v-model="formData.title"
                type="text"
                class="m-field-input"
                placeholder="请输入商品名称"
                maxlength="100"
              />
              <div class="m-field-count">{{ formData.title.length }}/100</div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">商品副标题</label>
              <input
                v-model="formData.subTitle"
                type="text"
                class="m-field-input"
                placeholder="请输入商品副标题（选填）"
                maxlength="200"
              />
            </div>
            <div class="m-form-field">
              <label class="m-field-label">商品分类</label>
              <div class="m-field-select" @click="showCategoryPicker = true">
                <span :class="{ placeholder: !formData.categoryPath }">
                  {{ formData.categoryPath || '请选择商品分类' }}
                </span>
                <MIcon name="chevronRight" :size="16" />
              </div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">发货地区</label>
              <div class="m-field-select" @click="showLocationPicker = true">
                <span :class="{ placeholder: !formData.addressText }">
                  {{ formData.addressText || '请选择发货地区' }}
                </span>
                <MIcon name="chevronRight" :size="16" />
              </div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">商品描述</label>
              <textarea
                v-model="formData.description"
                class="m-field-textarea"
                placeholder="请输入商品详细描述"
                rows="4"
                maxlength="2000"
              ></textarea>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'pricing'" class="m-tab-panel">
          <div class="m-form-section">
            <div class="m-section-title">价格设置</div>
            <div class="m-form-field">
              <label class="m-field-label">售价 <span class="m-required">*</span></label>
              <div class="m-price-input">
                <span class="m-price-prefix">¥</span>
                <input
                  v-model.number="formData.price"
                  type="number"
                  class="m-field-input"
                  placeholder="0.00"
                  min="0"
                  step="0.01"
                />
              </div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">原价（划线价）</label>
              <div class="m-price-input">
                <span class="m-price-prefix">¥</span>
                <input
                  v-model.number="formData.originalPrice"
                  type="number"
                  class="m-field-input"
                  placeholder="0.00"
                  min="0"
                  step="0.01"
                />
              </div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">成本价</label>
              <div class="m-price-input">
                <span class="m-price-prefix">¥</span>
                <input
                  v-model.number="formData.costPrice"
                  type="number"
                  class="m-field-input"
                  placeholder="0.00"
                  min="0"
                  step="0.01"
                />
              </div>
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">库存设置</div>
            <div class="m-form-field">
              <label class="m-field-label">库存数量</label>
              <input
                v-model.number="formData.stock"
                type="number"
                class="m-field-input"
                placeholder="0"
                min="0"
                step="1"
              />
            </div>
            <div class="m-form-field">
              <label class="m-field-label">库存预警阈值</label>
              <input
                v-model.number="formData.lowStockThreshold"
                type="number"
                class="m-field-input"
                placeholder="10"
                min="0"
                step="1"
              />
              <div class="m-field-hint">当库存低于此值时会提醒补货</div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">限购数量</label>
              <input
                v-model.number="formData.purchaseLimit"
                type="number"
                class="m-field-input"
                placeholder="0（不限购）"
                min="0"
                step="1"
              />
              <div class="m-field-hint">0 表示不限购</div>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'settings'" class="m-tab-panel">
          <div class="m-form-section">
            <div class="m-section-title">发货设置</div>
            <div class="m-switch-field">
              <div class="m-switch-info">
                <div class="m-switch-label">自动发货</div>
                <div class="m-switch-desc">开启后买家付款后自动发送发货内容</div>
              </div>
              <button
                class="m-switch-btn"
                :class="{ on: formData.autoDelivery }"
                @click="formData.autoDelivery = !formData.autoDelivery"
              >
                <span class="m-switch-knob"></span>
              </button>
            </div>
            <div v-if="formData.autoDelivery" class="m-form-field">
              <label class="m-field-label">发货内容</label>
              <textarea
                v-model="formData.deliveryContent"
                class="m-field-textarea"
                placeholder="请输入自动发货内容，如卡密、网盘链接等"
                rows="4"
              ></textarea>
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">售后设置</div>
            <div class="m-switch-field">
              <div class="m-switch-info">
                <div class="m-switch-label">支持退款</div>
                <div class="m-switch-desc">允许买家申请退款</div>
              </div>
              <button
                class="m-switch-btn"
                :class="{ on: formData.supportRefund }"
                @click="formData.supportRefund = !formData.supportRefund"
              >
                <span class="m-switch-knob"></span>
              </button>
            </div>
            <div class="m-switch-field">
              <div class="m-switch-info">
                <div class="m-switch-label">7天无理由退货</div>
                <div class="m-switch-desc">支持7天无理由退换货</div>
              </div>
              <button
                class="m-switch-btn"
                :class="{ on: formData.support7DayReturn }"
                @click="formData.support7DayReturn = !formData.support7DayReturn"
              >
                <span class="m-switch-knob"></span>
              </button>
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">其他设置</div>
            <div class="m-switch-field">
              <div class="m-switch-info">
                <div class="m-switch-label">推荐商品</div>
                <div class="m-switch-desc">在首页推荐位展示此商品</div>
              </div>
              <button
                class="m-switch-btn"
                :class="{ on: formData.isFeatured }"
                @click="formData.isFeatured = !formData.isFeatured"
              >
                <span class="m-switch-knob"></span>
              </button>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">排序权重</label>
              <input
                v-model.number="formData.sortWeight"
                type="number"
                class="m-field-input"
                placeholder="0"
                min="0"
                step="1"
              />
              <div class="m-field-hint">数值越大排序越靠前</div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">备注</label>
              <textarea
                v-model="formData.remark"
                class="m-field-textarea"
                placeholder="内部备注（买家不可见）"
                rows="2"
              ></textarea>
            </div>
          </div>
        </div>
      </div>

      <div class="m-bottom-bar">
        <button class="m-bar-btn m-bar-btn-secondary" @click="handleBack">
          返回
        </button>
        <button
          class="m-bar-btn m-bar-btn-primary"
          :class="{ loading: saving }"
          :disabled="saving"
          @click="handleSave"
        >
          <MIcon v-if="saving" name="refreshCw" :size="18" class="m-spin" />
          {{ saving ? '保存中...' : '保存修改' }}
        </button>
      </div>

      <div class="m-safe-bottom"></div>
    </template>

    <div v-if="showStatusDialog" class="m-dialog-mask" @click="showStatusDialog = false">
      <div class="m-dialog" @click.stop>
        <div class="m-dialog-title">
          {{ isOnShelf ? '确认下架商品？' : '确认上架商品？' }}
        </div>
        <div class="m-dialog-msg">
          {{ isOnShelf ? '下架后商品将不在店铺展示，买家无法购买。' : '上架后商品将在店铺展示，买家可以购买。' }}
        </div>
        <div class="m-dialog-actions">
          <button class="m-dialog-btn m-dialog-btn-cancel" @click="showStatusDialog = false">取消</button>
          <button class="m-dialog-btn m-dialog-btn-confirm" @click="confirmToggleStatus">
            确认{{ isOnShelf ? '下架' : '上架' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showBackDialog" class="m-dialog-mask" @click="showBackDialog = false">
      <div class="m-dialog" @click.stop>
        <div class="m-dialog-title">有未保存的更改</div>
        <div class="m-dialog-msg">您有未保存的修改，确定要离开吗？</div>
        <div class="m-dialog-actions">
          <button class="m-dialog-btn m-dialog-btn-cancel" @click="showBackDialog = false">继续编辑</button>
          <button class="m-dialog-btn m-dialog-btn-confirm" @click="confirmBack">确认离开</button>
        </div>
      </div>
    </div>

    <MobileCategoryPicker
      :visible="showCategoryPicker"
      :initial-category-id="formData.categoryId"
      @close="showCategoryPicker = false"
      @select="handleCategorySelect"
    />

    <MobileLocationPicker
      :visible="showLocationPicker"
      :initial-address="formData.location"
      @close="showLocationPicker = false"
      @select="handleLocationSelect"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import MIcon from './MIcon.vue'
import MobileCategoryPicker from './components/MobileCategoryPicker.vue'
import MobileLocationPicker from './components/MobileLocationPicker.vue'
import { getGoodsDetail, updateGoods } from '../api/goods.js'
import { offShelfItem, republishItem } from '../api/items.js'
import { uploadImage } from '../api/misc.js'

const props = defineProps({
  productId: [String, Number],
  product: Object
})

const emit = defineEmits(['navigate', 'force-desktop', 'back', 'updated'])

const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const activeTab = ref('basic')
const imageInputRef = ref(null)
const showCategoryPicker = ref(false)
const showLocationPicker = ref(false)
const showStatusDialog = ref(false)
const showBackDialog = ref(false)
let initialData = null

const tabs = [
  { key: 'basic', label: '基本信息' },
  { key: 'pricing', label: '库存价格' },
  { key: 'settings', label: '其他设置' }
]

const formData = reactive({
  title: '',
  subTitle: '',
  description: '',
  detailContent: '',
  price: 0,
  originalPrice: 0,
  costPrice: 0,
  stock: 0,
  lowStockThreshold: 10,
  purchaseLimit: 0,
  status: 0,
  imageUrls: [],
  mainImageUrl: '',
  categoryId: '',
  categoryPath: '',
  goodsType: '',
  tags: [],
  skus: [],
  autoDelivery: false,
  deliveryContent: '',
  supportRefund: true,
  support7DayReturn: false,
  isFeatured: false,
  sortWeight: 0,
  sales: 0,
  soldCount: 0,
  accountId: null,
  xianyuAccountId: null,
  remark: '',
  province: '',
  city: '',
  district: '',
  addressText: '',
  location: null
})

const isOnShelf = computed(() => formData.status === 1 || formData.onShelf === true)

const statusText = computed(() => {
  if (formData.stock <= 0) return '已售罄'
  return isOnShelf.value ? '上架中' : '已下架'
})

const statusClass = computed(() => {
  if (formData.stock <= 0) return 'm-status-soldout'
  return isOnShelf.value ? 'm-status-onshelf' : 'm-status-offshelf'
})

const hasUnsavedChanges = computed(() => {
  if (!initialData) return false
  return JSON.stringify({ ...formData }) !== JSON.stringify(initialData)
})

function formatPrice(price) {
  if (price == null || price === '') return '0'
  const num = Number(price)
  if (isNaN(num)) return String(price)
  return Number.isInteger(num) ? String(num) : num.toFixed(2)
}

async function loadProduct() {
  const id = props.productId || props.product?.id || props.product?.itemId
  if (!id) {
    loadError.value = '商品ID不存在'
    return
  }

  loading.value = true
  loadError.value = ''
  try {
    let data = props.product
    if (!data || !data.title) {
      const res = await getGoodsDetail(id)
      data = res?.data || {}
    }

    Object.assign(formData, {
      title: data.name || data.title || '',
      subTitle: data.subTitle || data.subtitle || '',
      description: data.description || data.detail || '',
      detailContent: data.detailContent || data.detail || '',
      price: Number(data.price || data.soldPrice || 0),
      originalPrice: Number(data.originalPrice || data.marketPrice || 0),
      costPrice: Number(data.costPrice || 0),
      stock: Number(data.stock || data.quantity || 0),
      lowStockThreshold: Number(data.lowStockThreshold || data.stockWarning || 10),
      purchaseLimit: Number(data.purchaseLimit || data.buyLimit || 0),
      status: data.status != null ? data.status : (data.onShelf ? 1 : 0),
      imageUrls: Array.isArray(data.imageUrls) ? data.imageUrls : (data.images ? data.images.split(',').filter(Boolean) : (data.coverPic ? [data.coverPic] : [])),
      mainImageUrl: data.mainImageUrl || data.coverPic || '',
      categoryId: data.categoryId || '',
      categoryPath: data.categoryPath || data.categoryName || '',
      goodsType: data.goodsType || '',
      tags: Array.isArray(data.tags) ? data.tags : [],
      skus: Array.isArray(data.skus) ? data.skus : [],
      autoDelivery: data.autoDelivery === true || data.autoDeliver === true,
      deliveryContent: data.deliveryContent || data.autoDeliveryContent || '',
      supportRefund: data.supportRefund !== false,
      support7DayReturn: data.support7DayReturn === true || data.sevenDayReturn === true,
      isFeatured: data.isFeatured === true || data.recommended === true,
      sortWeight: Number(data.sortWeight || data.sort || 0),
      sales: Number(data.sales || data.soldCount || 0),
      soldCount: Number(data.soldCount || data.sales || 0),
      accountId: data.accountId || data.xianyuAccountId,
      xianyuAccountId: data.xianyuAccountId || data.accountId,
      remark: data.remark || data.internalRemark || '',
      province: data.province || data.prov || (data.location && data.location.prov) || '',
      city: data.city || (data.location && data.location.city) || '',
      district: data.district || data.area || (data.location && data.location.area) || '',
      addressText: data.addressText || data.locationText || (data.location ? [data.location.prov, data.location.city, data.location.area].filter(Boolean).join(' ') : ''),
      location: data.location || (data.prov ? {
        prov: data.prov,
        city: data.city,
        area: data.area,
        divisionId: data.divisionId,
        gps: data.gps,
        poiId: data.poiId,
        poiName: data.poiName,
        source: data.source || 'legacy'
      } : null)
    })

    if (!formData.mainImageUrl && formData.imageUrls.length > 0) {
      formData.mainImageUrl = formData.imageUrls[0]
    }

    initialData = JSON.parse(JSON.stringify(formData))
  } catch (e) {
    loadError.value = e?.message || '加载失败，请重试'
  } finally {
    loading.value = false
  }
}

function triggerImageUpload() {
  imageInputRef.value?.click()
}

async function handleImageUpload(e) {
  const files = e.target.files
  if (!files || files.length === 0) return

  const accountId = formData.accountId || formData.xianyuAccountId
  const remaining = 10 - formData.imageUrls.length
  const toUpload = Array.from(files).slice(0, remaining)

  for (const file of toUpload) {
    try {
      const res = await uploadImage(file, accountId)
      const url = res?.data?.url || res?.url || res?.data
      if (url) {
        formData.imageUrls.push(url)
      }
    } catch (err) {
      showToast(err?.message || '图片上传失败', 'error')
    }
  }

  e.target.value = ''
}

function removeImage(idx) {
  formData.imageUrls.splice(idx, 1)
}

function toggleStatus() {
  showStatusDialog.value = true
}

async function confirmToggleStatus() {
  showStatusDialog.value = false
  const id = props.productId || props.product?.id || props.product?.itemId
  const accountId = formData.accountId || formData.xianyuAccountId

  try {
    if (isOnShelf.value) {
      await offShelfItem({ id, accountId })
      formData.status = 0
      formData.onShelf = false
      showToast('已下架')
    } else {
      if (formData.stock <= 0) {
        showToast('库存为0，无法上架', 'error')
        return
      }
      await republishItem({ id, accountId })
      formData.status = 1
      formData.onShelf = true
      showToast('已上架')
    }
    initialData = JSON.parse(JSON.stringify(formData))
    emit('updated', { ...formData, id })
  } catch (e) {
    showToast(e?.message || '操作失败', 'error')
  }
}

async function handleSave() {
  if (!formData.title.trim()) {
    showToast('请输入商品名称', 'error')
    activeTab.value = 'basic'
    return
  }
  if (formData.price < 0) {
    showToast('价格不能为负数', 'error')
    activeTab.value = 'pricing'
    return
  }
  if (formData.stock < 0) {
    showToast('库存不能为负数', 'error')
    activeTab.value = 'pricing'
    return
  }

  saving.value = true
  try {
    const id = props.productId || props.product?.id || props.product?.itemId
    const data = { ...formData }
    data.mainImageUrl = data.imageUrls[0] || ''

    if (id) {
      await updateGoods(id, data)
      initialData = JSON.parse(JSON.stringify(formData))
      showToast('保存成功')
      emit('updated', { ...formData, id })
    } else {
      saving.value = false
      emit('navigate', 'product-publish')
      return
    }
  } catch (e) {
    showToast(e?.message || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

function handleBack() {
  if (hasUnsavedChanges.value) {
    showBackDialog.value = true
  } else {
    emit('back')
  }
}

function confirmBack() {
  showBackDialog.value = false
  emit('back')
}

function handleCategorySelect(payload) {
  formData.categoryId = payload.categoryId
  formData.categoryPath = payload.path
  showCategoryPicker.value = false
}

function handleLocationSelect(payload) {
  formData.province = payload.province
  formData.city = payload.city
  formData.district = payload.district
  formData.addressText = payload.fullText
  formData.location = {
    prov: payload.province,
    city: payload.city,
    area: payload.district,
    divisionId: payload.divisionId || '',
    gps: payload.gps || '',
    poiId: payload.poiId || '',
    poiName: payload.poiName || payload.district,
    source: 'address-dict'
  }
  showLocationPicker.value = false
}

defineExpose({
  handleBack
})

let toastTimer = null
function showToast(msg, type = 'success') {
  let el = document.querySelector('.m-toast-global')
  if (!el) {
    el = document.createElement('div')
    el.className = 'm-toast-global'
    document.body.appendChild(el)
  }
  el.textContent = msg
  el.className = `m-toast-global m-toast-${type} m-toast-show`
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    el.className = 'm-toast-global'
  }, 2000)
}

onMounted(() => {
  loadProduct()
})
</script>

<style scoped>
.m-product-detail {
  padding-bottom: 0;
}

/* === 加载 / 错误状态 === */
.m-loading-state,
.m-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-12) var(--m-space-5);
  gap: var(--m-space-4);
  color: var(--m-color-text-tertiary);
}

.m-loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--m-color-border-light);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-spin 0.8s linear infinite;
}

@keyframes m-spin {
  to { transform: rotate(360deg); }
}

.m-spin {
  animation: m-spin 1s linear infinite;
}

.m-error-text {
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-secondary);
  text-align: center;
}

.m-retry-btn {
  padding: var(--m-space-2) var(--m-space-6);
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border: none;
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}

/* === 顶部 hero 卡 === */
.m-product-hero {
  background: var(--m-color-bg-card);
  padding: var(--m-space-4);
  margin: 0 var(--m-space-3) var(--m-space-3);
  border-radius: var(--m-radius-xl);
  border: 1px solid var(--m-color-border-light);
  box-shadow: var(--m-shadow-card);
}

.m-hero-images {
  display: flex;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-4);
}

.m-main-image {
  width: 120px;
  height: 120px;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
}

.m-img-main {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.m-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-disabled);
  background: var(--m-color-bg-subtle);
}

.m-image-thumbs {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--m-space-2);
  align-content: start;
}

.m-thumb-item {
  width: 100%;
  aspect-ratio: 1;
  border-radius: var(--m-radius-md);
  overflow: hidden;
  border: 2px solid transparent;
}

.m-thumb-item.active {
  border-color: var(--m-color-primary);
}

.m-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.m-thumb-more {
  width: 100%;
  aspect-ratio: 1;
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
}

/* === 状态行 === */
.m-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-2);
}

.m-status-badge {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
}

.m-status-onshelf {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}

.m-status-offshelf {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

.m-status-soldout {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}

.m-toggle-status {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-1) var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border: none;
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-tertiary);
  cursor: pointer;
}

.m-toggle-status.on {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}

.m-toggle-track {
  width: 36px;
  height: 20px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-pill);
  position: relative;
  transition: background 0.2s;
}

.m-toggle-status.on .m-toggle-track {
  background: var(--m-color-success);
}

.m-toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-circle);
  box-shadow: var(--m-shadow-card);
  transition: transform 0.2s;
}

.m-toggle-status.on .m-toggle-thumb {
  transform: translateX(16px);
}

/* === 标题 + 价格 === */
.m-product-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  margin: 0 0 var(--m-space-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.m-price-row {
  display: flex;
  align-items: baseline;
  gap: var(--m-space-1);
  margin-bottom: var(--m-space-2);
}

.m-price-symbol {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-danger-text);
}

.m-price-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-danger-text);
  line-height: 1;
}

.m-price-original {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  text-decoration: line-through;
  margin-left: var(--m-space-1);
}

.m-meta-row {
  display: flex;
  gap: var(--m-space-4);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-meta-item {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
}

/* === Tabs === */
.m-tabs-nav {
  display: flex;
  gap: var(--m-space-1);
  padding: 0 var(--m-space-3);
  margin-bottom: var(--m-space-3);
}

.m-tab-btn {
  flex: 1;
  padding: var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.m-tab-btn.active {
  background: var(--m-color-primary);
  border-color: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-weight: var(--m-font-weight-semibold);
}

/* === 表单 === */
.m-form-content {
  padding: 0 var(--m-space-3) 80px;
}

.m-tab-panel {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}

.m-form-section {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border-light);
}

.m-section-title {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-4);
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
}

.m-image-upload {
  width: 100%;
}

.m-upload-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-space-2);
}

.m-upload-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
}

.m-upload-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.m-remove-img {
  position: absolute;
  top: var(--m-space-1);
  right: var(--m-space-1);
  width: 22px;
  height: 22px;
  background: var(--m-mask-modal);
  border: none;
  border-radius: var(--m-radius-circle);
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.m-upload-add {
  aspect-ratio: 1;
  border: 2px dashed var(--m-color-border);
  border-radius: var(--m-radius-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  cursor: pointer;
  transition: all 0.2s;
}

.m-upload-add:active {
  border-color: var(--m-color-primary);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}

.m-file-input {
  display: none;
}

.m-form-field {
  margin-bottom: var(--m-space-4);
}

.m-form-field:last-child {
  margin-bottom: 0;
}

.m-field-label {
  display: block;
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-2);
}

.m-required {
  color: var(--m-color-danger);
}

.m-field-input {
  width: 100%;
  padding: var(--m-space-3) var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.m-field-input:focus {
  outline: none;
  border-color: var(--m-color-primary);
  background: var(--m-color-bg-card);
}

.m-field-input::placeholder {
  color: var(--m-color-text-placeholder);
}

.m-field-count {
  text-align: right;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  margin-top: var(--m-space-1);
}

.m-field-hint {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-top: var(--m-space-1);
}

.m-field-textarea {
  width: 100%;
  padding: var(--m-space-3) var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
  box-sizing: border-box;
  resize: vertical;
  font-family: inherit;
  transition: border-color 0.2s;
}

.m-field-textarea:focus {
  outline: none;
  border-color: var(--m-color-primary);
  background: var(--m-color-bg-card);
}

.m-field-textarea::placeholder {
  color: var(--m-color-text-placeholder);
}

.m-price-input {
  position: relative;
}

.m-price-prefix {
  position: absolute;
  left: var(--m-space-3);
  top: 50%;
  transform: translateY(-50%);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}

.m-price-input .m-field-input {
  padding-left: var(--m-space-8);
}

.m-field-select {
  width: 100%;
  padding: var(--m-space-3) var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

.m-field-select .placeholder {
  color: var(--m-color-text-placeholder);
}

.m-switch-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) 0;
  border-bottom: 1px solid var(--m-color-border-light);
}

.m-switch-field:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.m-switch-info {
  flex: 1;
  min-width: 0;
  padding-right: var(--m-space-3);
}

.m-switch-label {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
}

.m-switch-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-switch-btn {
  width: 48px;
  height: 28px;
  background: var(--m-color-border);
  border: none;
  border-radius: var(--m-radius-pill);
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
  padding: 0;
  flex-shrink: 0;
}

.m-switch-btn.on {
  background: var(--m-color-primary);
}

.m-switch-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 22px;
  height: 22px;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-circle);
  box-shadow: var(--m-shadow-card);
  transition: transform 0.2s;
}

.m-switch-btn.on .m-switch-knob {
  transform: translateX(20px);
}

/* === 底部固定操作栏 === */
.m-bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--m-color-bg-card);
  border-top: 1px solid var(--m-color-border-light);
  padding: var(--m-space-3) var(--m-space-4) calc(var(--m-space-3) + var(--m-safe-area-bottom));
  display: flex;
  gap: var(--m-space-3);
  z-index: 50;
  box-shadow: var(--m-shadow-elevated);
}

.m-bar-btn {
  flex: 1;
  padding: var(--m-space-3);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  transition: transform 0.15s;
}

.m-bar-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.m-bar-btn-secondary {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

.m-bar-btn-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-bar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* === 弹窗 === */
.m-dialog-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-modal);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-5);
}

.m-dialog {
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-2xl);
  padding: var(--m-space-6);
  width: 100%;
  max-width: 320px;
}

.m-dialog-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
}

.m-dialog-msg {
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-relaxed);
  margin-bottom: var(--m-space-5);
}

.m-dialog-actions {
  display: flex;
  gap: var(--m-space-3);
}

.m-dialog-btn {
  flex: 1;
  padding: var(--m-space-3);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
}

.m-dialog-btn-cancel {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

.m-dialog-btn-confirm {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-safe-bottom {
  height: calc(var(--m-space-5) + var(--m-safe-area-bottom));
}

@media (max-width: 360px) {
  .m-product-hero {
    margin: 0 var(--m-space-2) var(--m-space-2);
    padding: var(--m-space-3);
  }
  .m-main-image {
    width: 100px;
    height: 100px;
  }
  .m-form-content {
    padding: 0 var(--m-space-2) 80px;
  }
  .m-tabs-nav {
    padding: 0 var(--m-space-2);
  }
  .m-bottom-bar {
    padding-left: var(--m-space-2);
    padding-right: var(--m-space-2);
  }
}
</style>
