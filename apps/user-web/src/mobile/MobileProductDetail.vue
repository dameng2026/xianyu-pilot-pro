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
      <!-- ============ 顶部 Hero 卡 ============ -->
      <div class="m-product-hero">
        <div class="m-hero-images">
          <div class="m-main-image" @click="openImagePreview(0)">
            <img
              v-if="mainImage"
              :src="mainImage"
              :alt="formData.title"
              class="m-img-main"
              loading="lazy"
              @error="onImgError"
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
              @click="openImagePreview(idx)"
            >
              <img :src="img" alt="" class="m-thumb-img" loading="lazy" />
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
              :class="{ on: isOnShelf, loading: togglingStatus }"
              :disabled="togglingStatus"
              :aria-label="isOnShelf ? '下架商品' : '上架商品'"
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
            <span
              v-if="formData.soldPrice && Number(formData.soldPrice) > 0 && Number(formData.soldPrice) < Number(formData.price)"
              class="m-price-original"
            >
              ¥{{ formatPrice(formData.soldPrice) }}
            </span>
          </div>
          <div class="m-meta-row">
            <span class="m-meta-item">
              <MIcon name="database" :size="14" />
              库存 {{ formData.quantity ?? 0 }}
            </span>
            <span class="m-meta-item">
              <MIcon name="heart" :size="14" />
              想要 {{ formData.wantCount ?? 0 }}
            </span>
            <span class="m-meta-item">
              <MIcon name="eye" :size="14" />
              曝光 {{ formData.exposureCount ?? 0 }}
            </span>
          </div>
        </div>
      </div>

      <!-- ============ Tabs 导航 ============ -->
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
        <!-- ============ Tab 1: 商品信息 ============ -->
        <div v-if="activeTab === 'info'" class="m-tab-panel">
          <div class="m-form-section">
            <div class="m-section-title">基本信息</div>
            <div class="m-form-field">
              <label class="m-field-label">商品标题 <span class="m-required">*</span></label>
              <input
                v-model="formData.title"
                type="text"
                class="m-field-input"
                placeholder="请输入商品标题"
                maxlength="100"
              />
              <div class="m-field-count">{{ formData.title.length }}/100</div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">商品分类</label>
              <div class="m-field-select" @click="showCategoryPicker = true">
                <span :class="{ placeholder: !formData.category }">
                  {{ formData.category || '请选择商品分类' }}
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
              <div class="m-field-count">{{ formData.description.length }}/2000</div>
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">价格与库存</div>
            <div class="m-form-field">
              <label class="m-field-label">售价 <span class="m-required">*</span></label>
              <div class="m-price-input">
                <span class="m-price-prefix">¥</span>
                <input
                  v-model="formData.price"
                  type="text"
                  class="m-field-input"
                  placeholder="0.00"
                  inputmode="decimal"
                />
              </div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">原价（划线价）</label>
              <div class="m-price-input">
                <span class="m-price-prefix">¥</span>
                <input
                  v-model="formData.soldPrice"
                  type="text"
                  class="m-field-input"
                  placeholder="0.00（选填）"
                  inputmode="decimal"
                />
              </div>
            </div>
            <div class="m-form-field">
              <label class="m-field-label">库存数量</label>
              <input
                v-model.number="formData.quantity"
                type="number"
                class="m-field-input"
                placeholder="0"
                min="0"
                step="1"
              />
            </div>
            <div class="m-form-field">
              <label class="m-field-label">排序权重</label>
              <input
                v-model.number="formData.sortOrder"
                type="number"
                class="m-field-input"
                placeholder="0"
                min="0"
                step="1"
              />
              <div class="m-field-hint">数值越大排序越靠前</div>
            </div>
          </div>
        </div>

        <!-- ============ Tab 2: 图片 ============ -->
        <div v-if="activeTab === 'images'" class="m-tab-panel">
          <div class="m-form-section">
            <div class="m-section-title">商品图片</div>
            <div class="m-field-hint" style="margin-bottom: 12px;">
              最多上传 10 张图片，第一张为封面图。点击图片可设为封面。
            </div>
            <div class="m-upload-grid">
              <div
                v-for="(img, idx) in formData.imageUrls"
                :key="idx"
                class="m-upload-item"
                :class="{ cover: idx === 0 }"
              >
                <img :src="img" alt="" class="m-upload-img" loading="lazy" />
                <span v-if="idx === 0" class="m-cover-tag">封面</span>
                <div class="m-upload-actions">
                  <button
                    v-if="idx > 0"
                    class="m-img-action"
                    aria-label="设为封面"
                    @click="setAsCover(idx)"
                  >
                    <MIcon name="star" :size="14" />
                  </button>
                  <button
                    class="m-img-action m-img-action-danger"
                    aria-label="删除图片"
                    @click="removeImage(idx)"
                  >
                    <MIcon name="x" :size="14" />
                  </button>
                </div>
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

        <!-- ============ Tab 3: 参数 ============ -->
        <div v-if="activeTab === 'params'" class="m-tab-panel">
          <div class="m-form-section">
            <div class="m-section-title">商品数据</div>
            <div class="m-param-grid">
              <div class="m-param-item">
                <div class="m-param-label">曝光数</div>
                <div class="m-param-value">{{ formData.exposureCount ?? 0 }}</div>
              </div>
              <div class="m-param-item">
                <div class="m-param-label">浏览数</div>
                <div class="m-param-value">{{ formData.viewCount ?? 0 }}</div>
              </div>
              <div class="m-param-item">
                <div class="m-param-label">想要数</div>
                <div class="m-param-value">{{ formData.wantCount ?? 0 }}</div>
              </div>
              <div class="m-param-item">
                <div class="m-param-label">库存</div>
                <div class="m-param-value">{{ formData.quantity ?? 0 }}</div>
              </div>
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">商品链接</div>
            <div class="m-form-field">
              <label class="m-field-label">详情链接</label>
              <input
                v-model="formData.detailUrl"
                type="text"
                class="m-field-input"
                placeholder="商品详情页链接"
              />
            </div>
            <div class="m-form-field">
              <label class="m-field-label">外部商品ID</label>
              <input
                v-model="formData.externalGoodsId"
                type="text"
                class="m-field-input"
                placeholder="闲鱼商品ID"
                readonly
              />
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">详情信息</div>
            <div class="m-form-field">
              <label class="m-field-label">详情内容</label>
              <textarea
                v-model="formData.detailInfo"
                class="m-field-textarea"
                placeholder="商品详情信息（选填）"
                rows="6"
                maxlength="5000"
              ></textarea>
              <div class="m-field-count">{{ (formData.detailInfo || '').length }}/5000</div>
            </div>
          </div>
        </div>

        <!-- ============ Tab 4: 自动化配置 ============ -->
        <div v-if="activeTab === 'automation'" class="m-tab-panel">
          <div class="m-form-section">
            <div class="m-section-title">自动回复</div>
            <div class="m-switch-field">
              <div class="m-switch-info">
                <div class="m-switch-label">商品级自动回复</div>
                <div class="m-switch-desc">
                  开启后，买家咨询此商品时使用 AI 自动回复
                </div>
              </div>
              <button
                class="m-switch-btn"
                :class="{ on: autoReplyEnabled, loading: togglingAutoReply }"
                :disabled="togglingAutoReply"
                :aria-label="autoReplyEnabled ? '关闭自动回复' : '开启自动回复'"
                @click="toggleAutoReply"
              >
                <span class="m-switch-knob"></span>
              </button>
            </div>
            <div class="m-switch-status">
              当前状态：
              <span :class="autoReplyEnabled ? 'm-status-on' : 'm-status-off'">
                {{ autoReplyEnabled ? '已开启' : '已关闭' }}
              </span>
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">快捷操作</div>
            <button class="m-action-row" @click="goAutoDeliveryConfig">
              <MIcon name="truck" :size="20" color="#ff9f22" />
              <div class="m-action-row-info">
                <div class="m-action-row-label">配置自动发货</div>
                <div class="m-action-row-desc">设置发货内容、卡密或网盘链接</div>
              </div>
              <MIcon name="chevronRight" :size="16" />
            </button>
          </div>
        </div>

        <!-- ============ Tab 5: 发货配置 ============ -->
        <div v-if="activeTab === 'delivery'" class="m-tab-panel">
          <div class="m-form-section">
            <div class="m-section-title">自动发货</div>
            <div class="m-delivery-status">
              <div class="m-delivery-status-label">当前状态</div>
              <div class="m-delivery-status-value">
                <span
                  class="m-delivery-badge"
                  :class="autoDeliveryOn ? 'on' : 'off'"
                >
                  {{ autoDeliveryOn ? '已启用' : '未启用' }}
                </span>
                <span class="m-delivery-type">{{ deliveryTypeText }}</span>
              </div>
            </div>
            <div class="m-field-hint" style="margin-top: 12px;">
              自动发货规则通过发货配置页管理，支持卡密、文本、自定义内容。
            </div>
          </div>

          <div class="m-form-section">
            <div class="m-section-title">操作</div>
            <button
              class="m-action-row"
              @click="goAutoDeliveryConfig"
            >
              <MIcon name="settings" :size="20" color="#3380ff" />
              <div class="m-action-row-info">
                <div class="m-action-row-label">前往发货配置</div>
                <div class="m-action-row-desc">配置自动发货内容与规则</div>
              </div>
              <MIcon name="chevronRight" :size="16" />
            </button>
            <button
              class="m-action-row"
              @click="goDeliveryRecords"
            >
              <MIcon name="fileText" :size="20" color="#16bf78" />
              <div class="m-action-row-info">
                <div class="m-action-row-label">查看发货记录</div>
                <div class="m-action-row-desc">查看此商品的历史自动发货记录</div>
              </div>
              <MIcon name="chevronRight" :size="16" />
            </button>
          </div>
        </div>
      </div>

      <!-- ============ 底部固定操作栏 ============ -->
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

    <!-- ============ 上下架确认弹窗 ============ -->
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
          <button
            class="m-dialog-btn"
            :class="isOnShelf ? 'm-dialog-btn-danger' : 'm-dialog-btn-confirm'"
            @click="confirmToggleStatus"
          >
            确认{{ isOnShelf ? '下架' : '上架' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 未保存离开确认弹窗 ============ -->
    <div v-if="showBackDialog" class="m-dialog-mask" @click="showBackDialog = false">
      <div class="m-dialog" @click.stop>
        <div class="m-dialog-title">有未保存的更改</div>
        <div class="m-dialog-msg">您有未保存的修改，确定要离开吗？</div>
        <div class="m-dialog-actions">
          <button class="m-dialog-btn m-dialog-btn-cancel" @click="showBackDialog = false">继续编辑</button>
          <button class="m-dialog-btn m-dialog-btn-danger" @click="confirmBack">确认离开</button>
        </div>
      </div>
    </div>

    <!-- ============ 图片预览 ============ -->
    <div v-if="previewImage" class="m-preview-mask" @click="previewImage = ''">
      <img :src="previewImage" alt="" class="m-preview-img" />
    </div>

    <MobileCategoryPicker
      :visible="showCategoryPicker"
      :initial-category-id="formData.category"
      @close="showCategoryPicker = false"
      @select="handleCategorySelect"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileCategoryPicker from './components/MobileCategoryPicker.vue'
import { getGoodsDetail, updateGoods } from '../api/goods.js'
import { offShelfItem, republishItem, updateAutoReplyStatus } from '../api/items.js'
import { uploadImage } from '../api/misc.js'
import { resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'

const props = defineProps({
  productId: [String, Number],
  product: Object
})

const emit = defineEmits(['navigate', 'force-desktop', 'back', 'updated'])

// FE 状态码（与后端 XianyuGoodsService 一致）：0=在售 1=下架 2=已售 3=已删除
const FE_STATUS_ON_SALE = 0
const FE_STATUS_OFF_SHELF = 1

const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const togglingStatus = ref(false)
const togglingAutoReply = ref(false)
const activeTab = ref('info')
const imageInputRef = ref(null)
const showCategoryPicker = ref(false)
const showStatusDialog = ref(false)
const showBackDialog = ref(false)
const previewImage = ref('')
let initialData = null

const tabs = [
  { key: 'info', label: '商品信息' },
  { key: 'images', label: '图片' },
  { key: 'params', label: '参数' },
  { key: 'automation', label: '自动化' },
  { key: 'delivery', label: '发货' }
]

// formData 对齐后端 XianyuGoodsVO 字段
const formData = reactive({
  id: null,
  title: '',
  price: '',
  soldPrice: '',
  coverPic: '',
  imageUrl: '',
  stock: '',
  quantity: 0,
  exposureCount: 0,
  viewCount: 0,
  wantCount: 0,
  detailUrl: '',
  detailInfo: '',
  description: '',
  category: '',
  sortOrder: 0,
  status: FE_STATUS_OFF_SHELF,
  externalGoodsId: '',
  accountId: null,
  autoDeliveryType: null,
  xianyuAutoDeliveryOn: 0,
  xianyuAutoReplyOn: 0,
  // 前端派生字段
  imageUrls: []
})

const isOnShelf = computed(() => Number(formData.status) === FE_STATUS_ON_SALE)

const autoReplyEnabled = computed(() => Number(formData.xianyuAutoReplyOn) === 1)
const autoDeliveryOn = computed(() => Number(formData.xianyuAutoDeliveryOn) === 1)

const deliveryTypeText = computed(() => {
  const t = formData.autoDeliveryType
  if (t === 0) return '卡密发货'
  if (t === 1) return '文本发货'
  if (t === 2) return '自定义发货'
  return '未配置'
})

const mainImage = computed(() => {
  if (formData.imageUrls.length > 0) return formData.imageUrls[0]
  if (formData.coverPic) return resolveTrustedMediaUrl(formData.coverPic)
  return ''
})

const statusText = computed(() => {
  if ((formData.quantity ?? 0) <= 0 && isOnShelf.value) return '已售罄'
  return isOnShelf.value ? '上架中' : '已下架'
})

const statusClass = computed(() => {
  if ((formData.quantity ?? 0) <= 0 && isOnShelf.value) return 'm-status-soldout'
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

function parseImageUrls(data) {
  const urls = []
  if (Array.isArray(data.imageUrls)) {
    urls.push(...data.imageUrls)
  } else if (typeof data.imageUrl === 'string' && data.imageUrl) {
    urls.push(...data.imageUrl.split(',').filter(Boolean))
  }
  if (data.coverPic && !urls.includes(data.coverPic)) {
    urls.unshift(data.coverPic)
  }
  return urls.map(u => resolveTrustedMediaUrl(u)).filter(Boolean)
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
      data = res?.data || res || {}
    }

    Object.assign(formData, {
      id: data.id || id,
      title: data.title || data.name || '',
      price: data.price != null ? String(data.price) : '',
      soldPrice: data.soldPrice != null ? String(data.soldPrice) : '',
      coverPic: data.coverPic || '',
      imageUrl: data.imageUrl || '',
      stock: data.stock != null ? String(data.stock) : '',
      quantity: Number(data.quantity ?? 0),
      exposureCount: Number(data.exposureCount ?? 0),
      viewCount: Number(data.viewCount ?? 0),
      wantCount: Number(data.wantCount ?? 0),
      detailUrl: data.detailUrl || '',
      detailInfo: data.detailInfo || '',
      description: data.description || data.detail || '',
      category: data.category || data.categoryName || '',
      sortOrder: Number(data.sortOrder ?? 0),
      status: data.status != null ? Number(data.status) : FE_STATUS_OFF_SHELF,
      externalGoodsId: data.externalGoodsId || '',
      accountId: data.accountId || data.xianyuAccountId || null,
      autoDeliveryType: data.autoDeliveryType != null ? Number(data.autoDeliveryType) : null,
      xianyuAutoDeliveryOn: Number(data.xianyuAutoDeliveryOn ?? 0),
      xianyuAutoReplyOn: Number(data.xianyuAutoReplyOn ?? 0),
      imageUrls: parseImageUrls(data)
    })

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

  const accountId = formData.accountId
  if (!accountId) {
    showToast('缺少账号信息，无法上传图片', 'error')
    e.target.value = ''
    return
  }

  const remaining = 10 - formData.imageUrls.length
  const toUpload = Array.from(files).slice(0, remaining)

  for (const file of toUpload) {
    try {
      const res = await uploadImage(accountId, file)
      const url = res?.data?.url || res?.url || res?.data
      if (url) {
        formData.imageUrls.push(resolveTrustedMediaUrl(url))
      }
    } catch (err) {
      showToast(err?.message || '图片上传失败', 'error')
    }
  }

  e.target.value = ''
}

function removeImage(idx) {
  formData.imageUrls.splice(idx, 1)
  if (idx === 0 && formData.imageUrls.length > 0) {
    formData.coverPic = formData.imageUrls[0]
  } else if (formData.imageUrls.length === 0) {
    formData.coverPic = ''
  }
}

function setAsCover(idx) {
  if (idx === 0) return
  const [img] = formData.imageUrls.splice(idx, 1)
  formData.imageUrls.unshift(img)
  formData.coverPic = img
  showToast('已设为封面')
}

function openImagePreview(idx) {
  const url = formData.imageUrls[idx]
  if (url) previewImage.value = url
}

function onImgError(e) {
  e.target.style.display = 'none'
}

function toggleStatus() {
  showStatusDialog.value = true
}

async function confirmToggleStatus() {
  showStatusDialog.value = false
  const id = formData.id || props.productId || props.product?.id
  const accountId = formData.accountId
  if (!id || !accountId) {
    showToast('缺少商品ID或账号信息', 'error')
    return
  }

  togglingStatus.value = true
  try {
    if (isOnShelf.value) {
      await offShelfItem({ id, accountId })
      formData.status = FE_STATUS_OFF_SHELF
      showToast('已下架')
    } else {
      await republishItem({ id, accountId })
      formData.status = FE_STATUS_ON_SALE
      showToast('已上架')
    }
    initialData = JSON.parse(JSON.stringify(formData))
    emit('updated', { ...formData })
  } catch (e) {
    showToast(e?.message || '操作失败', 'error')
  } finally {
    togglingStatus.value = false
  }
}

async function toggleAutoReply() {
  const id = formData.id || props.productId || props.product?.id
  if (!id) {
    showToast('缺少商品ID', 'error')
    return
  }

  togglingAutoReply.value = true
  const target = autoReplyEnabled.value ? 0 : 1
  try {
    await updateAutoReplyStatus({ itemId: id, enabled: target })
    formData.xianyuAutoReplyOn = target
    initialData = JSON.parse(JSON.stringify(formData))
    showToast(target === 1 ? '已开启自动回复' : '已关闭自动回复')
    emit('updated', { ...formData })
  } catch (e) {
    showToast(e?.message || '操作失败', 'error')
  } finally {
    togglingAutoReply.value = false
  }
}

function goAutoDeliveryConfig() {
  const id = formData.id || props.productId || props.product?.id
  if (!id) {
    showToast('缺少商品ID', 'error')
    return
  }
  emit('navigate', 'auto-delivery-config', { productId: id })
}

function goDeliveryRecords() {
  emit('navigate', 'delivery-records')
}

async function handleSave() {
  if (!formData.title.trim()) {
    showToast('请输入商品标题', 'error')
    activeTab.value = 'info'
    return
  }
  const priceNum = Number(formData.price)
  if (isNaN(priceNum) || priceNum < 0) {
    showToast('价格必须为非负数字', 'error')
    activeTab.value = 'info'
    return
  }
  if (formData.quantity < 0) {
    showToast('库存不能为负数', 'error')
    activeTab.value = 'info'
    return
  }

  saving.value = true
  try {
    const id = formData.id || props.productId || props.product?.id
    if (!id) {
      showToast('缺少商品ID，无法保存', 'error')
      return
    }

    const payload = {
      title: formData.title,
      price: formData.price,
      soldPrice: formData.soldPrice,
      coverPic: formData.imageUrls[0] || formData.coverPic || '',
      imageUrl: formData.imageUrls.join(','),
      stock: String(formData.quantity),
      quantity: formData.quantity,
      detailUrl: formData.detailUrl,
      detailInfo: formData.detailInfo,
      description: formData.description,
      category: formData.category,
      sortOrder: formData.sortOrder,
      status: formData.status,
      accountId: formData.accountId
    }

    await updateGoods(id, payload)
    formData.coverPic = payload.coverPic
    formData.imageUrl = payload.imageUrl
    initialData = JSON.parse(JSON.stringify(formData))
    showToast('保存成功')
    emit('updated', { ...formData })
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
  formData.category = payload.path || payload.categoryName || ''
  showCategoryPicker.value = false
}

defineExpose({
  handleBack,
  handleSave
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
  border-radius: var(--m-radius-lg);
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
  box-shadow: var(--m-shadow-xs);
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
  cursor: pointer;
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
  cursor: pointer;
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

.m-toggle-status.loading {
  opacity: 0.5;
  cursor: not-allowed;
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
  box-shadow: var(--m-shadow-xs);
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
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.m-tab-btn {
  flex: 1;
  min-width: 60px;
  padding: var(--m-space-3) var(--m-space-2);
  background: var(--m-color-bg-card);
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  box-shadow: var(--m-shadow-xs);
}

.m-tab-btn.active {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-weight: var(--m-font-weight-semibold);
  box-shadow: none;
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
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-xs);
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

.m-field-input[readonly] {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  cursor: not-allowed;
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

/* === 图片上传 === */
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
  border: 2px solid transparent;
}

.m-upload-item.cover {
  border-color: var(--m-color-primary);
}

.m-upload-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.m-cover-tag {
  position: absolute;
  top: var(--m-space-1);
  left: var(--m-space-1);
  padding: 2px 6px;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  border-radius: var(--m-radius-pill);
}

.m-upload-actions {
  position: absolute;
  bottom: var(--m-space-1);
  right: var(--m-space-1);
  display: flex;
  gap: var(--m-space-1);
}

.m-img-action {
  width: 24px;
  height: 24px;
  background: var(--m-mask-modal);
  border: none;
  border-radius: var(--m-radius-circle);
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.m-img-action-danger {
  background: var(--m-color-danger);
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

/* === 参数网格 === */
.m-param-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--m-space-3);
}

.m-param-item {
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  text-align: center;
}

.m-param-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-1);
}

.m-param-value {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}

/* === 开关字段 === */
.m-switch-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) 0;
  border-bottom: 1px solid var(--m-color-border-light);
}

.m-switch-field:last-of-type {
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

.m-switch-btn.loading {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-switch-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 22px;
  height: 22px;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-circle);
  box-shadow: var(--m-shadow-xs);
  transition: transform 0.2s;
}

.m-switch-btn.on .m-switch-knob {
  transform: translateX(20px);
}

.m-switch-status {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-top: var(--m-space-3);
}

.m-status-on {
  color: var(--m-color-success-text);
  font-weight: var(--m-font-weight-semibold);
}

.m-status-off {
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-semibold);
}

/* === 发货状态 === */
.m-delivery-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) 0;
}

.m-delivery-status-label {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}

.m-delivery-status-value {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
}

.m-delivery-badge {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
}

.m-delivery-badge.on {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}

.m-delivery-badge.off {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}

.m-delivery-type {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

/* === 操作行 === */
.m-action-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) 0;
  background: none;
  border: none;
  border-bottom: 1px solid var(--m-color-border-light);
  cursor: pointer;
  text-align: left;
}

.m-action-row:last-child {
  border-bottom: none;
}

.m-action-row-info {
  flex: 1;
  min-width: 0;
}

.m-action-row-label {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
}

.m-action-row-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

/* === 底部固定操作栏 === */
.m-bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--m-color-bg-card);
  padding: var(--m-space-3) var(--m-space-4) calc(var(--m-space-3) + var(--m-safe-area-bottom));
  display: flex;
  gap: var(--m-space-3);
  z-index: 50;
  box-shadow: var(--m-shadow-xs);
}

.m-bar-btn {
  flex: 1;
  padding: var(--m-space-3);
  border-radius: var(--m-radius-lg);
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
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-6);
  width: 100%;
  max-width: 320px;
  box-shadow: var(--m-shadow-xs);
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
  border-radius: var(--m-radius-lg);
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

.m-dialog-btn-danger {
  background: var(--m-color-danger);
  color: var(--m-color-text-inverse);
}

/* === 图片预览 === */
.m-preview-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-4);
}

.m-preview-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
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
  .m-upload-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .m-param-grid {
    grid-template-columns: 1fr;
  }
}
</style>
