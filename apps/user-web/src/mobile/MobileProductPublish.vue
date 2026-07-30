<template>
  <div class="m-publish-page">
    <div class="m-publish-hero">
      <div class="m-publish-hero-bg"></div>
      <div class="m-publish-hero-content">
        <div class="m-publish-hero-badge">
          <span class="m-publish-hero-dot"></span>
          <span>快速发布</span>
        </div>
        <div class="m-publish-hero-icon">
          <MIcon name="plus" :size="32" />
        </div>
        <h1>发布宝贝</h1>
        <p>填写商品信息，快速上架闲鱼</p>
      </div>
    </div>

    <div class="m-publish-draft-tip" v-if="hasDraft">
      <div class="m-draft-icon">
        <MIcon name="save" :size="18" />
      </div>
      <span>检测到未完成的草稿，已自动恢复</span>
      <button class="m-draft-clear" @click="clearDraft">
        <MIcon name="trash" :size="16" />
      </button>
    </div>

    <div class="m-form-section">
      <div class="m-section-card" style="animation-delay: 0.05s">
        <div class="m-card-header">
          <div class="m-card-icon m-icon-blue">
            <MIcon name="user" :size="20" />
          </div>
          <h3>选择账号</h3>
        </div>
        <div class="m-account-selector">
          <div
            v-for="acc in accounts"
            :key="acc.id"
            class="m-account-item"
            :class="{ active: form.accountId === acc.id }"
            @click="selectAccount(acc.id)"
          >
            <div class="m-account-avatar">
              <span>{{ (acc.nickname || acc.username || 'U').charAt(0).toUpperCase() }}</span>
            </div>
            <div class="m-account-info">
              <div class="m-account-name">{{ accountName(acc) }}</div>
              <div class="m-account-status" :class="{ authorized: acc.authorized }">
                <MIcon :name="acc.authorized ? 'checkCircle' : 'alertCircle'" :size="14" />
                {{ acc.authorized ? '已授权' : '未授权' }}
              </div>
            </div>
            <div class="m-account-check" v-if="form.accountId === acc.id">
              <MIcon name="check" :size="18" />
            </div>
          </div>
          <div v-if="!accounts.length" class="m-empty-accounts">
            <MIcon name="users" :size="32" />
            <p>暂无可用账号，请先添加闲鱼账号</p>
          </div>
        </div>
      </div>

      <div class="m-section-card" style="animation-delay: 0.1s">
        <div class="m-card-header">
          <div class="m-card-icon m-icon-purple">
            <MIcon name="edit2" :size="20" />
          </div>
          <h3>宝贝基础信息</h3>
        </div>

        <div class="m-form-group">
          <label>宝贝标题 <span class="m-required">*</span></label>
          <div class="m-input-wrap">
            <input
              v-model="form.title"
              type="text"
              maxlength="30"
              placeholder="请填写宝贝标题，建议包含品牌、规格、成色等"
              class="m-input"
              :class="{ error: errors.title }"
            />
            <span class="m-char-count">{{ form.title.length }}/30</span>
          </div>
          <div class="m-error-tip" v-if="errors.title">
            <MIcon name="alertCircle" :size="14" />
            {{ errors.title }}
          </div>
        </div>

        <div class="m-form-group">
          <label>宝贝描述</label>
          <textarea
            v-model="form.description"
            rows="4"
            placeholder="请详细描述宝贝的成色、功能、使用感受等信息..."
            class="m-textarea"
          ></textarea>
          <div class="m-chips-row">
            <button
              class="m-chip m-chip-primary"
              :class="{ loading: aiDescLoading }"
              :disabled="aiDescLoading"
              @click="aiDesc"
            >
              <MIcon name="zap" :size="16" />
              {{ aiDescLoading ? 'AI生成中...' : 'AI生成描述' }}
            </button>
            <button class="m-chip" @click="insertPhrase">
              <MIcon name="plus" :size="16" />
              常用语
            </button>
          </div>
        </div>
      </div>

      <div class="m-section-card" style="animation-delay: 0.15s">
        <div class="m-card-header">
          <div class="m-card-icon m-icon-orange">
            <MIcon name="image" :size="20" />
          </div>
          <h3>宝贝图片</h3>
          <span class="m-card-hint">{{ form.imageUrls.length }}/10</span>
        </div>
        <p class="m-image-tip">上传商品图片，第一张为封面图（必填）</p>

        <div class="m-image-grid">
          <div
            v-for="(img, idx) in form.imageUrls"
            :key="idx"
            class="m-image-item"
            :class="{ cover: idx === 0 }"
          >
            <img :src="displayImageUrl(img)" alt="" />
            <div class="m-image-cover-badge" v-if="idx === 0">封面</div>
            <button class="m-image-remove" @click="removeImage(idx)">
              <MIcon name="x" :size="16" />
            </button>
          </div>
          <div
            v-if="form.imageUrls.length < 10"
            class="m-image-add"
            @click="triggerUpload"
          >
            <div class="m-image-add-inner">
              <MIcon name="camera" :size="28" />
              <span>上传图片</span>
            </div>
          </div>
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            multiple
            style="display:none"
            @change="onFileSelect"
          >
        </div>

        <div class="m-url-input-wrap">
          <MIcon name="link" :size="16" class="m-url-icon" />
          <input
            v-model="imageUrlInput"
            type="url"
            class="m-url-input"
            placeholder="粘贴图片URL导入"
            :disabled="imageUrlLoading"
            @keydown.enter.prevent="addImageFromUrl"
          >
          <button
            class="m-url-btn"
            :disabled="imageUrlLoading || !imageUrlInput.trim()"
            @click="addImageFromUrl"
          >
            {{ imageUrlLoading ? '导入中' : '导入' }}
          </button>
        </div>
        <div class="m-error-tip" v-if="errors.images">
          <MIcon name="alertCircle" :size="14" />
          {{ errors.images }}
        </div>
      </div>

      <div class="m-section-card" style="animation-delay: 0.2s">
        <div class="m-card-header">
          <div class="m-card-icon m-icon-green">
            <MIcon name="folder" :size="20" />
          </div>
          <h3>商品分类 <span class="m-required">*</span></h3>
        </div>

        <div class="m-auto-category-hint">
          <MIcon name="zap" :size="16" />
          <span>上传封面图后可自动获取分类</span>
          <span v-if="autoCategoryLoading" class="m-loading-dot">检测中...</span>
        </div>

        <div v-if="autoCategoryMessage" :class="['m-category-msg', autoCategoryMsgType]">
          {{ autoCategoryMessage }}
        </div>

        <div v-if="autoCategoryCandidates.length" class="m-candidates-row">
          <span class="m-candidates-label">推荐：</span>
          <button
            v-for="(cat, idx) in autoCategoryCandidates"
            :key="cat.catId || idx"
            type="button"
            :class="['m-candidate-btn', { active: autoSelectedCatId === (cat.catId || cat.catName) }]"
            @click="applyAutoCategory(cat)"
          >
            {{ cat.catName }}
            <small v-if="cat.score">({{ (cat.score * 100).toFixed(0) }}%)</small>
          </button>
        </div>

        <div class="m-category-selected" v-if="selectedCategoryPath">
          <MIcon name="checkCircle" :size="18" class="m-selected-icon" />
          <span>{{ selectedCategoryPath }}</span>
        </div>

        <div class="m-cascader-wrap">
          <div class="m-cascader-cols">
            <div class="m-cascader-col">
              <div v-if="categoriesLoading" class="m-cascader-empty">加载中...</div>
              <div v-else-if="categoryLoadError" class="m-cascader-empty">分类加载失败</div>
              <div v-else-if="!categories.length" class="m-cascader-empty">暂无分类</div>
              <div
                v-for="cat in filteredCategories"
                :key="cat.id"
                :class="['m-cascader-item', { active: level1Id === cat.id }]"
                @click="selectLevel1(cat)"
              >
                {{ cat.label || cat.title }}
                <MIcon v-if="cat.children?.length" name="chevronRight" :size="14" class="m-cascader-arrow" />
              </div>
            </div>
            <div v-if="level2List.length" class="m-cascader-col">
              <div
                v-for="cat in level2List"
                :key="cat.id"
                :class="['m-cascader-item', { active: level2Id === cat.id }]"
                @click="selectLevel2(cat)"
              >
                {{ cat.label || cat.title }}
                <MIcon v-if="cat.children?.length" name="chevronRight" :size="14" class="m-cascader-arrow" />
              </div>
            </div>
            <div v-if="level3List.length" class="m-cascader-col">
              <div
                v-for="cat in level3List"
                :key="cat.id"
                :class="['m-cascader-item', { active: level3Id === cat.id }]"
                @click="selectLevel3(cat)"
              >
                {{ cat.label || cat.title }}
              </div>
            </div>
          </div>
        </div>
        <div class="m-error-tip" v-if="errors.category">
          <MIcon name="alertCircle" :size="14" />
          {{ errors.category }}
        </div>

        <div v-if="recentCategories.length" class="m-recent-row">
          <span class="m-recent-label">最近使用：</span>
          <button
            v-for="item in recentCategories.slice(0, 5)"
            :key="item.path"
            class="m-recent-btn"
            @click="selectCategoryByPath(item)"
          >
            {{ item.name }}
          </button>
        </div>
      </div>

      <div class="m-section-card" style="animation-delay: 0.25s">
        <div class="m-card-header">
          <div class="m-card-icon m-icon-cyan">
            <MIcon name="map" :size="20" />
          </div>
          <h3>商品位置</h3>
        </div>
        <button class="m-location-btn" @click="showLocationPicker = true">
          <MIcon name="map" :size="20" class="m-location-icon" />
          <div class="m-location-info">
            <span class="m-location-label">{{ selectedAddress ? formatAddress(selectedAddress) : '选择发货地区' }}</span>
            <span class="m-location-desc">买家可见</span>
          </div>
          <MIcon name="chevronRight" :size="18" class="m-location-arrow" />
        </button>
      </div>

      <div class="m-section-card" style="animation-delay: 0.3s">
        <div class="m-card-header">
          <div class="m-card-icon m-icon-red">
            <MIcon name="dollar" :size="20" />
          </div>
          <h3>价格与库存</h3>
        </div>

        <div class="m-price-row">
          <div class="m-price-input-wrap">
            <span class="m-price-symbol">¥</span>
            <input
              v-model="form.price"
              type="number"
              step="0.01"
              min="0"
              placeholder="0.00"
              class="m-price-input"
              :class="{ error: errors.price }"
            >
          </div>
          <div class="m-stock-wrap">
            <label>库存</label>
            <div class="m-stepper">
              <button class="m-stepper-btn" @click="adjustStock(-1)">
                <MIcon name="minus" :size="18" />
              </button>
              <input
                v-model="form.stock"
                type="number"
                min="1"
                class="m-stepper-input"
              >
              <button class="m-stepper-btn" @click="adjustStock(1)">
                <MIcon name="plus" :size="18" />
              </button>
            </div>
          </div>
        </div>
        <div class="m-error-tip" v-if="errors.price">
          <MIcon name="alertCircle" :size="14" />
          {{ errors.price }}
        </div>
      </div>

      <div class="m-section-card" style="animation-delay: 0.35s">
        <div class="m-toggle-row">
          <div class="m-toggle-info">
            <div class="m-card-header m-toggle-card-header">
              <div class="m-card-icon m-icon-purple m-toggle-card-icon">
                <MIcon name="truck" :size="18" />
              </div>
              <h3 class="m-toggle-card-title">自动发货</h3>
            </div>
            <p class="m-toggle-desc">开启后买家付款将自动发送货源内容</p>
          </div>
          <button class="m-switch" :class="{ on: autoDelivery.enabled }" @click="toggleAutoDelivery">
            <span class="m-switch-knob"></span>
          </button>
        </div>

        <div v-if="autoDelivery.enabled" class="m-auto-delivery-body">
          <label>关联货源库</label>
          <select v-model="autoDelivery.sourceId" class="m-select" :disabled="sourcesLoading">
            <option value="">请选择货源</option>
            <option v-for="source in deliverySources" :key="source.id" :value="source.id">
              {{ source.title }}
            </option>
          </select>
          <div v-if="sourcesLoading" class="m-loading-text">货源库加载中...</div>
          <div v-else-if="sourcesError" class="m-error-text">{{ sourcesError }}</div>
          <div v-else-if="autoDelivery.sourceId" class="m-success-text">已选货源：{{ selectedSourceTitle }}</div>
          <div v-else-if="sourcesAvailable && !deliverySources.length" class="m-warning-text">暂无货源，请先到货源库创建</div>
        </div>
      </div>

      <div class="m-section-card" style="animation-delay: 0.4s">
        <div class="m-card-header">
          <div class="m-card-icon m-icon-blue">
            <MIcon name="truck2" :size="20" />
          </div>
          <h3>发货设置</h3>
        </div>

        <div class="m-shipping-options">
          <div
            v-for="opt in shippingOptions"
            :key="opt.key"
            class="m-shipping-item"
            :class="{ active: shippingMode === opt.key }"
            @click="setShipping(opt.key)"
          >
            <div class="m-radio-circle" :class="{ checked: shippingMode === opt.key }">
              <MIcon v-if="shippingMode === opt.key" name="check" :size="12" />
            </div>
            <div class="m-shipping-info">
              <div class="m-shipping-label">{{ opt.label }}</div>
              <div class="m-shipping-desc">{{ opt.desc }}</div>
            </div>
          </div>

          <div class="m-shipping-item" :class="{ active: form.supportSelfPick }" @click="form.supportSelfPick = !form.supportSelfPick">
            <div class="m-radio-circle" :class="{ checked: form.supportSelfPick }">
              <MIcon v-if="form.supportSelfPick" name="check" :size="12" />
            </div>
            <div class="m-shipping-info">
              <div class="m-shipping-label">支持自提</div>
              <div class="m-shipping-desc">允许买家上门自提</div>
            </div>
          </div>
        </div>
      </div>

      <div class="m-preview-card" style="animation-delay: 0.45s" v-if="form.title || form.imageUrls.length">
        <div class="m-preview-header">
          <MIcon name="eye" :size="18" />
          <span>商品预览</span>
        </div>
        <div class="m-preview-body">
          <div class="m-preview-thumb">
            <img v-if="displayCoverImage" :src="displayCoverImage" alt="">
            <div v-else class="m-preview-placeholder">
              <MIcon name="image" :size="28" />
            </div>
          </div>
          <div class="m-preview-info">
            <div class="m-preview-title">{{ form.title || '商品标题' }}</div>
            <div class="m-preview-price">¥{{ displayPrice }}</div>
            <div class="m-preview-stock">库存 {{ totalStock }} 件</div>
          </div>
        </div>
      </div>

      <div class="m-safe-publish"></div>
    </div>

    <div class="m-publish-footer">
      <button class="m-save-draft-btn" @click="saveDraft">
        <MIcon name="save" :size="18" />
        存草稿
      </button>
      <button
        class="m-publish-btn"
        :class="{ loading: submitting }"
        :disabled="submitting"
        @click="submit"
      >
        <MIcon v-if="!submitting" name="send" :size="20" />
        <span v-if="submitting">发布中...</span>
        <span v-else>立即发布</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import MIcon from './MIcon.vue'
import { getLiteAccounts, checkAccountAuth } from '../api/accounts.js'
import { createGoods, createGoodsWithRetry, stashPendingLocalGoods } from '../api/goods.js'
import { publishItem } from '../api/items.js'
import { uploadImage, uploadImageFromUrl } from '../api/misc.js'
import { accountName } from '../utils/format.js'
import { fetchCategories } from '../api/categories.js'
import { aiRewriteGoods } from '../api/workflow.js'
import { ensureAiTokenBalance } from '../utils/aiTokenGuard.js'
import { normalizePublishAddress } from '../utils/publishAddress.js'
import { imageUploadValidationMessage } from '../utils/imageUploadPolicy.js'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])

const accounts = ref([])
const accountAvailable = ref(false)
const fileInput = ref(null)
const submitting = ref(false)
const aiDescLoading = ref(false)
const imageUrlLoading = ref(false)
const imageUrlInput = ref('')
const hasDraft = ref(false)
const showLocationPicker = ref(false)
const errors = reactive({})
const sourcesLoading = ref(false)
const sourcesError = ref('')
const deliverySources = ref([])
const sourcesAvailable = ref(false)
const categoriesLoading = ref(false)
const categoryLoadError = ref('')
const categories = ref([])
const level1Id = ref(null)
const level2Id = ref(null)
const level3Id = ref(null)
const level2List = ref([])
const level3List = ref([])
const categoryKeyword = ref('')
const recentCategories = ref([])
const selectedCategoryPath = ref('')
const selectedCategoryName = ref('')
const autoCategoryLoading = ref(false)
const autoCategoryMessage = ref('')
const autoCategoryMsgType = ref('info')
const autoCategoryCandidates = ref([])
const autoSelectedCatId = ref('')
const userManuallySelectedCategory = ref(false)
const selectedAddress = ref(null)

const form = reactive({
  accountId: '',
  title: '',
  description: '',
  imageUrls: [],
  price: '',
  stock: 1,
  supportSelfPick: false,
  categoryId: null,
  categoryPath: '',
  province: '',
  city: '',
  district: ''
})

const autoDelivery = reactive({
  enabled: false,
  sourceId: ''
})

const shippingMode = ref('free')
const shippingOptions = [
  { key: 'free', label: '包邮', desc: '卖家承担运费' },
  { key: 'fixed', label: '运费', desc: '买家承担运费' },
  { key: 'none', label: '无需邮寄', desc: '虚拟商品或线下交易' }
]

const filteredCategories = computed(() => {
  if (!categoryKeyword.value.trim()) return categories.value
  const kw = categoryKeyword.value.trim().toLowerCase()
  return categories.value.filter(cat =>
    String(cat.label || cat.title || '').toLowerCase().includes(kw) ||
    (cat.children || []).some(child => String(child.label || child.title || '').toLowerCase().includes(kw))
  )
})

const displayCoverImage = computed(() => {
  return form.imageUrls.length > 0 ? displayImageUrl(form.imageUrls[0]) : ''
})

const displayPrice = computed(() => {
  const p = parseFloat(form.price)
  return isNaN(p) ? '0.00' : p.toFixed(2)
})

const totalStock = computed(() => {
  const s = parseInt(form.stock)
  return isNaN(s) || s < 1 ? 1 : s
})

const selectedSourceTitle = computed(() => {
  const s = deliverySources.value.find(x => x.id === autoDelivery.sourceId)
  return s?.title || ''
})

function displayImageUrl(img) {
  if (!img) return ''
  if (img.startsWith('http')) return img
  return `/uploads/${img}`
}

function formatAddress(addr) {
  if (!addr) return '选择发货地区'
  const parts = [addr.province, addr.city, addr.district].filter(Boolean)
  return parts.join(' ')
}

function selectAccount(id) {
  form.accountId = id
}

function adjustStock(delta) {
  let s = parseInt(form.stock) || 1
  s = Math.max(1, s + delta)
  form.stock = s
}

function triggerUpload() {
  fileInput.value?.click()
}

function onFileSelect(e) {
  const files = Array.from(e.target.files || [])
  files.forEach(file => {
    const errMsg = imageUploadValidationMessage(file)
    if (errMsg) {
      alert(errMsg)
      return
    }
    if (form.imageUrls.length >= 10) return
    uploadImageFile(file)
  })
  e.target.value = ''
}

async function uploadImageFile(file) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadImage(formData)
    if (res?.data?.url || res?.data?.path) {
      form.imageUrls.push(res.data.url || res.data.path)
    }
  } catch (e) {
    console.error('Upload failed:', e)
    alert('图片上传失败')
  }
}

function removeImage(idx) {
  form.imageUrls.splice(idx, 1)
}

async function addImageFromUrl() {
  const url = imageUrlInput.value.trim()
  if (!url) return
  imageUrlLoading.value = true
  try {
    const res = await uploadImageFromUrl({ url })
    if (res?.data?.url || res?.data?.path) {
      form.imageUrls.push(res.data.url || res.data.path)
      imageUrlInput.value = ''
    }
  } catch (e) {
    alert('URL导入失败')
  } finally {
    imageUrlLoading.value = false
  }
}

async function aiDesc() {
  if (!form.title.trim()) {
    alert('请先填写宝贝标题')
    return
  }
  if (!(await ensureAiTokenBalance())) return
  aiDescLoading.value = true
  try {
    const res = await aiRewriteGoods({ title: form.title, description: form.description })
    if (res?.data?.description) {
      form.description = res.data.description
    }
  } catch (e) {
    alert('AI生成失败')
  } finally {
    aiDescLoading.value = false
  }
}

function insertPhrase() {
  const phrases = [
    '全新未拆封，正品保证',
    '99新，仅拆封试用',
    '自用闲置，成色很好',
    '功能正常，无质量问题',
    '包邮！非诚勿扰~'
  ]
  const phrase = phrases[Math.floor(Math.random() * phrases.length)]
  form.description = form.description ? form.description + '\n' + phrase : phrase
}

function toggleAutoDelivery() {
  autoDelivery.enabled = !autoDelivery.enabled
}

function setShipping(mode) {
  shippingMode.value = mode
}

function selectLevel1(cat) {
  userManuallySelectedCategory.value = true
  level1Id.value = cat.id
  level2Id.value = null
  level3Id.value = null
  level2List.value = cat.children || []
  level3List.value = []
  selectedCategoryName.value = cat.label || cat.title
  selectedCategoryPath.value = cat.label || cat.title
  form.categoryId = cat.id
  form.categoryPath = selectedCategoryPath.value
  if (!level2List.value.length) {
    rememberCategory({ name: selectedCategoryName.value, path: selectedCategoryPath.value, pathIds: [cat.id] })
  }
}

function selectLevel2(cat) {
  userManuallySelectedCategory.value = true
  level2Id.value = cat.id
  level3Id.value = null
  level3List.value = cat.children || []
  const l1 = categories.value.find(c => c.id === level1Id.value)
  const path = (l1?.label || l1?.title) + ' ＞ ' + (cat.label || cat.title)
  selectedCategoryName.value = cat.label || cat.title
  selectedCategoryPath.value = path
  form.categoryId = cat.id
  form.categoryPath = path
  if (!level3List.value.length) {
    const l1 = categories.value.find(c => c.id === level1Id.value)
    rememberCategory({ name: selectedCategoryName.value, path, pathIds: [l1?.id, cat.id].filter(Boolean) })
  }
}

function selectLevel3(cat) {
  userManuallySelectedCategory.value = true
  level3Id.value = cat.id
  const l1 = categories.value.find(c => c.id === level1Id.value)
  const l2 = level2List.value.find(c => c.id === level2Id.value)
  const path = (l1?.label || l1?.title) + ' ＞ ' + (l2?.label || l2?.title) + ' ＞ ' + (cat.label || cat.title)
  selectedCategoryName.value = cat.label || cat.title
  selectedCategoryPath.value = path
  form.categoryId = cat.id
  form.categoryPath = path
  rememberCategory({ name: selectedCategoryName.value, path, pathIds: [l1?.id, l2?.id, cat.id].filter(Boolean) })
}

function rememberCategory(item) {
  const arr = recentCategories.value.filter(x => x.path !== item.path)
  arr.unshift(item)
  recentCategories.value = arr.slice(0, 10)
}

function selectCategoryByPath(item) {
  selectedCategoryPath.value = item.path
  selectedCategoryName.value = item.name
  form.categoryPath = item.path
  if (item.pathIds?.length) {
    form.categoryId = item.pathIds[item.pathIds.length - 1]
  }
}

function applyAutoCategory(cat) {
  autoSelectedCatId.value = cat.catId || cat.catName
  selectedCategoryPath.value = cat.catName
  selectedCategoryName.value = cat.catName
  userManuallySelectedCategory.value = true
}

function validateForm() {
  Object.keys(errors).forEach(k => delete errors[k])
  let ok = true
  if (!form.accountId) {
    errors.account = '请选择闲鱼账号'
    ok = false
  }
  if (!form.title.trim()) {
    errors.title = '请填写宝贝标题'
    ok = false
  } else if (form.title.length < 2) {
    errors.title = '标题至少2个字'
    ok = false
  }
  if (!form.imageUrls.length) {
    errors.images = '请至少上传1张商品图片'
    ok = false
  }
  if (!selectedCategoryPath.value) {
    errors.category = '请选择商品分类'
    ok = false
  }
  const price = parseFloat(form.price)
  if (!form.price || isNaN(price) || price <= 0) {
    errors.price = '请输入有效的商品价格'
    ok = false
  }
  return ok
}

async function submit() {
  if (!validateForm()) {
    return
  }
  submitting.value = true
  let publishedItemId = ''
  try {
    const finalPrice = form.price
    const finalStock = Number(form.stock) || 1
    const shippingMap = { free: true, fixed: false, none: false }
    const freeShipping = shippingMap[shippingMode.value] ?? true

    // 构建位置数据（与 PC 端保持一致的格式）
    const locationData = normalizePublishAddress(selectedAddress.value)

    // 先发布到闲鱼，成功后再保存到本地数据库，避免发布失败时本地却显示商品
    const publishRes = await publishItem({
      xianyuAccountId: Number(form.accountId),
      title: form.title.slice(0, 30),
      description: form.description,
      imageUrls: form.imageUrls,
      price: finalPrice,
      stock: finalStock,
      category: selectedCategoryName.value,
      freeShipping,
      supportSelfPick: form.supportSelfPick,
      location: locationData,
    })

    if (publishRes && typeof publishRes === 'object' && [0, 200].includes(Number(publishRes.code))) {
      if (!publishRes.data || typeof publishRes.data !== 'object' || Array.isArray(publishRes.data)) {
        throw new Error('发布请求已返回，但结果格式异常，无法确认是否成功，请先到闲鱼核对')
      }
      const itemId = String(publishRes.data.itemId ?? publishRes.data.xyGoodsId ?? publishRes.data.id ?? '').trim()
      const itemUrl = publishRes.data?.itemUrl || ''
      if (!itemId) throw new Error('发布接口未返回有效闲鱼商品ID，本地不会保存为在售商品')
      publishedItemId = itemId

      // 发布成功后将闲鱼返回的商品 ID 同步保存到本地数据库
      // 使用带重试的 createGoods：503/网络错误自动重试 3 次；仍失败时暂存到 localStorage，
      // 进入商品管理页面时会自动补建本地记录，避免用户进退两难。
      const localGoodsPayload = {
        accountId: Number(form.accountId),
        externalGoodsId: itemId,
        title: form.title.slice(0, 30),
        description: form.description,
        imageUrls: form.imageUrls,
        imageUrl: form.imageUrls[0] || '',
        category: selectedCategoryName.value,
        price: Number(finalPrice),
        stock: finalStock,
        detailUrl: itemUrl,
        status: 0,
      }
      await createGoodsWithRetry(localGoodsPayload)

      // 发布成功后清除草稿并标记商品待同步
      clearDraftData()
      localStorage.setItem('xianyu_pending_sync', 'true')

      alert('发布成功！')
      // 跳转回商品列表，MobileProducts 重新挂载会自动 loadProducts 刷新列表
      emit('back')
    } else {
      // 发布失败，显示具体错误信息（包括 AI 封面图缺失等后端校验提示）
      const errMsg = publishRes?.msg || '发布到闲鱼失败，请稍后重试'
      alert(errMsg)
    }
  } catch (e) {
    if (publishedItemId) {
      // 商品已发布到闲鱼，但本地保存失败：暂存商品信息，进入商品管理页面时自动补建
      stashPendingLocalGoods(localGoodsPayload)
      localStorage.setItem('xianyu_pending_sync', 'true')
      alert(`商品已发布到闲鱼（ID：${publishedItemId}），本地商品记录因服务暂时繁忙保存失败，已自动暂存。进入「商品管理」页面时会自动补建本地记录，请勿重复发布。`)
    } else {
      alert(e?.message || '发布失败，请稍后重试')
    }
  } finally {
    submitting.value = false
  }
}

function saveDraft() {
  const draft = {
    form: { ...form },
    autoDelivery: { ...autoDelivery },
    shippingMode: shippingMode.value,
    selectedCategoryPath: selectedCategoryPath.value,
    savedAt: Date.now()
  }
  localStorage.setItem('mobile_publish_draft', JSON.stringify(draft))
  hasDraft.value = true
  alert('草稿已保存')
}

function loadDraftData() {
  try {
    const raw = localStorage.getItem('mobile_publish_draft')
    if (raw) {
      const draft = JSON.parse(raw)
      Object.assign(form, draft.form || {})
      Object.assign(autoDelivery, draft.autoDelivery || {})
      shippingMode.value = draft.shippingMode || 'free'
      selectedCategoryPath.value = draft.selectedCategoryPath || ''
      hasDraft.value = true
    }
  } catch (e) {}
}

function clearDraftData() {
  localStorage.removeItem('mobile_publish_draft')
  hasDraft.value = false
}

function clearDraft() {
  if (confirm('确定要清空草稿吗？')) {
    clearDraftData()
    form.accountId = ''
    form.title = ''
    form.description = ''
    form.imageUrls = []
    form.price = ''
    form.stock = 1
    form.supportSelfPick = false
    autoDelivery.enabled = false
    autoDelivery.sourceId = ''
    shippingMode.value = 'free'
    selectedCategoryPath.value = ''
    level1Id.value = null
    level2Id.value = null
    level3Id.value = null
  }
}

async function loadAccounts() {
  try {
    const res = await getLiteAccounts()
    accounts.value = res?.data || []
    accountAvailable.value = accounts.value.length > 0
    if (accounts.value.length && !form.accountId) {
      const preferred = accounts.value.find(a => a.authorized) || accounts.value[0]
      form.accountId = preferred.id
    }
  } catch (e) {
    console.error('Load accounts failed:', e)
  }
}

async function loadCategories() {
  categoriesLoading.value = true
  categoryLoadError.value = ''
  try {
    const res = await fetchCategories()
    categories.value = res?.data || []
  } catch (e) {
    categoryLoadError.value = e?.message || '加载失败'
  } finally {
    categoriesLoading.value = false
  }
}

watch(() => form.title, () => { if (errors.title) delete errors.title })
watch(() => form.imageUrls, () => { if (errors.images) delete errors.images }, { deep: true })
watch(() => form.price, () => { if (errors.price) delete errors.price })

onMounted(() => {
  loadDraftData()
  loadAccounts()
  loadCategories()
})
</script>

<style scoped>
.m-publish-page {
  min-height: 100vh;
  background: var(--m-color-bg-page);
  padding-bottom: 100px;
}

.m-publish-hero {
  position: relative;
  padding: var(--m-space-6) var(--m-space-5) var(--m-space-7);
}

.m-publish-hero-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--m-color-bg-card);
  border-radius: 0 0 var(--m-radius-xl) var(--m-radius-xl);
  box-shadow: var(--m-shadow-xs);
}

.m-publish-hero-content {
  position: relative;
  z-index: 1;
  text-align: center;
  color: var(--m-color-text-primary);
}

.m-publish-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: var(--m-color-bg-subtle);
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-3);
}

.m-publish-hero-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--m-color-success);
}

.m-publish-hero-icon {
  width: 56px;
  height: 56px;
  background: var(--m-color-primary-bg);
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--m-space-3);
  color: var(--m-color-primary);
  box-shadow: var(--m-shadow-xs);
}

.m-publish-hero h1 {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-bold);
  margin: 0 0 var(--m-space-1);
  letter-spacing: -0.3px;
}

.m-publish-hero p {
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-tertiary);
  margin: 0;
}

.m-publish-draft-tip {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin: 0 var(--m-space-4) var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-4);
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-warning-text);
  box-shadow: var(--m-shadow-xs);
}

.m-draft-icon {
  color: var(--m-color-warning);
  flex-shrink: 0;
}

.m-draft-clear {
  margin-left: auto;
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-lg);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
}

.m-draft-clear:active {
  transform: scale(0.96);
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}

.m-form-section {
  padding: 0 var(--m-space-4);
}

.m-section-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-5);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
  animation: cardSlideUp 0.4s ease-out backwards;
}

@keyframes cardSlideUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.m-card-header {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-4);
}

.m-card-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.m-icon-blue {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}

.m-icon-purple {
  background: rgba(139, 92, 246, 0.1);
  color: var(--m-color-purple);
}

.m-icon-orange {
  background: rgba(255, 159, 34, 0.1);
  color: var(--m-color-warning);
}

.m-icon-green {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}

.m-icon-cyan {
  background: rgba(17, 181, 216, 0.1);
  color: var(--m-color-cyan);
}

.m-icon-red {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
}

.m-card-header h3 {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin: 0;
  flex: 1;
}

.m-card-hint {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
  background: var(--m-color-bg-subtle);
  padding: 2px var(--m-space-2);
  border-radius: var(--m-radius-pill);
}

.m-required {
  color: var(--m-color-danger);
}

.m-form-group {
  margin-bottom: var(--m-space-4);
}

.m-form-group:last-child {
  margin-bottom: 0;
}

.m-form-group label {
  display: block;
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-2);
}

.m-input-wrap {
  position: relative;
}

.m-input {
  width: 100%;
  height: 48px;
  padding: 0 68px 0 var(--m-space-4);
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-subtle);
  box-sizing: border-box;
  transition: all 0.15s;
  outline: none;
}

.m-input:focus {
  background: var(--m-color-bg-subtle);
  box-shadow: 0 0 0 2px var(--m-color-primary);
}

.m-input.error {
  box-shadow: 0 0 0 2px var(--m-color-danger);
}

.m-char-count {
  position: absolute;
  right: var(--m-space-3);
  top: 50%;
  transform: translateY(-50%);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  background: var(--m-color-bg-card);
  padding: 2px 8px;
  border-radius: var(--m-radius-pill);
  font-weight: var(--m-font-weight-medium);
}

.m-textarea {
  width: 100%;
  min-height: 110px;
  padding: var(--m-space-3) var(--m-space-4);
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-subtle);
  box-sizing: border-box;
  transition: all 0.15s;
  outline: none;
  resize: none;
  font-family: inherit;
  line-height: 1.6;
}

.m-textarea:focus {
  box-shadow: 0 0 0 2px var(--m-color-primary);
}

.m-chips-row {
  display: flex;
  gap: var(--m-space-2);
  margin-top: var(--m-space-3);
  flex-wrap: wrap;
}

.m-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px var(--m-space-3);
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
  transition: all 0.15s;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

.m-chip:active {
  transform: scale(0.96);
}

.m-chip-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-chip-primary:active {
  opacity: 0.9;
}

.m-chip-primary.loading {
  opacity: 0.7;
  pointer-events: none;
}

.m-error-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--m-space-2);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-danger);
}

.m-account-selector {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}

.m-account-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-4);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  cursor: pointer;
  transition: all 0.15s;
}

.m-account-item:active {
  transform: scale(0.99);
}

.m-account-item.active {
  background: var(--m-color-primary-bg);
}

.m-account-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  flex-shrink: 0;
}

.m-account-info {
  flex: 1;
  min-width: 0;
}

.m-account-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-account-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-warning-text);
  background: var(--m-color-warning-bg);
  padding: 2px 8px;
  border-radius: var(--m-radius-pill);
  font-weight: var(--m-font-weight-medium);
}

.m-account-status.authorized {
  color: var(--m-color-success-text);
  background: var(--m-color-success-bg);
}

.m-account-check {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-empty-accounts {
  text-align: center;
  padding: var(--m-space-6) var(--m-space-4);
  color: var(--m-color-text-tertiary);
}

.m-empty-accounts p {
  margin: var(--m-space-2) 0 0;
  font-size: var(--m-font-size-body-sm);
}

.m-image-tip {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  margin: calc(-1 * var(--m-space-2)) 0 var(--m-space-3);
}

.m-image-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
}

.m-image-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  background: var(--m-color-bg-subtle);
  box-shadow: var(--m-shadow-xs);
}

.m-image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.m-image-item.cover::after {
  content: '';
  position: absolute;
  inset: 0;
  border: 2px solid var(--m-color-primary);
  border-radius: var(--m-radius-lg);
  pointer-events: none;
}

.m-image-cover-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: 10px;
  font-weight: var(--m-font-weight-medium);
  padding: 2px 6px;
  border-radius: var(--m-radius-pill);
}

.m-image-remove {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  border: none;
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
}

.m-image-item:hover .m-image-remove,
.m-image-item:active .m-image-remove {
  opacity: 1;
}

.m-image-add {
  aspect-ratio: 1;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.m-image-add:active {
  transform: scale(0.97);
  background: var(--m-color-primary-bg);
}

.m-image-add-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
}

.m-url-input-wrap {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-1) var(--m-space-1) var(--m-space-1) var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  transition: all 0.15s;
}

.m-url-input-wrap:focus-within {
  box-shadow: 0 0 0 2px var(--m-color-primary);
}

.m-url-icon {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}

.m-url-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  outline: none;
  padding: var(--m-space-2) 0;
  min-width: 0;
}

.m-url-btn {
  padding: var(--m-space-2) var(--m-space-3);
  border: none;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}

.m-url-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-url-btn:not(:disabled):active {
  transform: scale(0.96);
  opacity: 0.9;
}

.m-auto-category-hint {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-3);
  background: var(--m-color-warning-bg);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-warning-text);
  margin-bottom: var(--m-space-3);
}

.m-loading-dot {
  color: var(--m-color-warning);
  font-weight: var(--m-font-weight-medium);
}

.m-category-msg {
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  margin-bottom: var(--m-space-3);
}

.m-category-msg.info {
  background: var(--m-color-info-bg);
  color: var(--m-color-info-text);
}

.m-category-msg.success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}

.m-category-msg.error {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}

.m-candidates-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
}

.m-candidates-label {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  align-self: center;
}

.m-candidate-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px var(--m-space-3);
  border: none;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-bg-subtle);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  font-weight: var(--m-font-weight-medium);
}

.m-candidate-btn:active {
  transform: scale(0.97);
}

.m-candidate-btn.active {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-candidate-btn small {
  opacity: 0.7;
  font-size: 10px;
}

.m-category-selected {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-3);
  background: var(--m-color-success-bg);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-success-text);
  font-weight: var(--m-font-weight-medium);
  margin-bottom: var(--m-space-3);
}

.m-selected-icon {
  flex-shrink: 0;
}

.m-cascader-wrap {
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  overflow: hidden;
}

.m-cascader-cols {
  display: flex;
  max-height: 220px;
  overflow-y: auto;
}

.m-cascader-col {
  flex: 1;
  min-width: 0;
}

.m-cascader-col:not(:last-child) {
  border-right: 1px solid var(--m-color-border-light);
}

.m-cascader-empty {
  padding: var(--m-space-5) var(--m-space-3);
  text-align: center;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
}

.m-cascader-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.m-cascader-item:active {
  background: var(--m-color-primary-bg);
}

.m-cascader-item.active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-medium);
}

.m-cascader-arrow {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}

.m-cascader-item.active .m-cascader-arrow {
  color: var(--m-color-primary);
}

.m-recent-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-2);
  margin-top: var(--m-space-3);
  align-items: center;
}

.m-recent-label {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
}

.m-recent-btn {
  padding: 6px var(--m-space-3);
  border: none;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-bg-subtle);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  font-weight: var(--m-font-weight-medium);
}

.m-recent-btn:active {
  transform: scale(0.97);
  background: var(--m-color-border-light);
}

.m-location-btn {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  width: 100%;
  padding: var(--m-space-3) var(--m-space-4);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
  border: none;
}

.m-location-btn:active {
  transform: scale(0.99);
  background: var(--m-color-primary-bg);
}

.m-location-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--m-radius-lg);
  background: rgba(17, 181, 216, 0.1);
  color: var(--m-color-cyan);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.m-location-info {
  flex: 1;
  min-width: 0;
}

.m-location-label {
  display: block;
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  margin-bottom: 2px;
}

.m-location-desc {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}

.m-location-arrow {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}

.m-price-row {
  display: flex;
  gap: var(--m-space-3);
  align-items: flex-start;
}

.m-price-input-wrap {
  flex: 1;
  position: relative;
}

.m-price-symbol {
  position: absolute;
  left: var(--m-space-4);
  top: 50%;
  transform: translateY(-50%);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-danger);
  z-index: 1;
}

.m-price-input {
  width: 100%;
  height: 52px;
  padding: 0 var(--m-space-4) 0 38px;
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-danger);
  background: var(--m-color-bg-subtle);
  box-sizing: border-box;
  transition: all 0.15s;
  outline: none;
}

.m-price-input:focus {
  box-shadow: 0 0 0 2px var(--m-color-danger);
}

.m-price-input.error {
  box-shadow: 0 0 0 2px var(--m-color-danger);
}

.m-stock-wrap {
  width: 140px;
}

.m-stock-wrap label {
  display: block;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-1);
  font-weight: var(--m-font-weight-medium);
}

.m-stepper {
  display: flex;
  align-items: center;
  height: 48px;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  overflow: hidden;
}

.m-stepper-btn {
  width: 42px;
  height: 100%;
  border: none;
  background: transparent;
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
}

.m-stepper-btn:active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}

.m-stepper-input {
  flex: 1;
  width: 100%;
  text-align: center;
  border: none;
  background: transparent;
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  outline: none;
}

.m-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-3);
}

.m-toggle-info {
  flex: 1;
  min-width: 0;
}

.m-toggle-card-header {
  padding: 0;
  margin-bottom: 4px;
}

.m-toggle-card-icon {
  width: 32px;
  height: 32px;
}

.m-toggle-card-title {
  font-size: var(--m-font-size-body);
}

.m-toggle-desc {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  margin: 0;
}

.m-switch {
  width: 48px;
  height: 28px;
  border-radius: var(--m-radius-pill);
  border: none;
  background: var(--m-color-border);
  position: relative;
  cursor: pointer;
  transition: all 0.2s;
  padding: 0;
  flex-shrink: 0;
}

.m-switch.on {
  background: var(--m-color-primary);
}

.m-switch-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 24px;
  height: 24px;
  background: var(--m-color-bg-card);
  border-radius: 50%;
  box-shadow: var(--m-shadow-xs);
  transition: transform 0.2s;
}

.m-switch.on .m-switch-knob {
  transform: translateX(20px);
}

.m-auto-delivery-body {
  margin-top: var(--m-space-4);
  padding-top: var(--m-space-4);
  border-top: 1px solid var(--m-color-border-light);
}

.m-auto-delivery-body label {
  display: block;
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-2);
}

.m-select {
  width: 100%;
  height: 48px;
  padding: 0 var(--m-space-4);
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-subtle);
  box-sizing: border-box;
  outline: none;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2386909c' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right var(--m-space-3) center;
  padding-right: 36px;
  transition: all 0.15s;
}

.m-select:focus {
  box-shadow: 0 0 0 2px var(--m-color-primary);
}

.m-loading-text,
.m-success-text,
.m-warning-text,
.m-error-text {
  margin-top: var(--m-space-2);
  font-size: var(--m-font-size-body-sm);
}

.m-loading-text { color: var(--m-color-text-tertiary); }
.m-success-text { color: var(--m-color-success); }
.m-warning-text { color: var(--m-color-warning); }
.m-error-text { color: var(--m-color-danger); }

.m-shipping-options {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}

.m-shipping-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-4);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  cursor: pointer;
  transition: all 0.15s;
}

.m-shipping-item:active {
  transform: scale(0.99);
}

.m-shipping-item.active {
  background: var(--m-color-primary-bg);
}

.m-radio-circle {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--m-color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-inverse);
  flex-shrink: 0;
  transition: all 0.15s;
}

.m-shipping-item.active .m-radio-circle {
  border-color: var(--m-color-primary);
  background: var(--m-color-primary);
}

.m-shipping-info {
  flex: 1;
}

.m-shipping-label {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  margin-bottom: 2px;
}

.m-shipping-desc {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}

.m-preview-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
  animation: cardSlideUp 0.4s ease-out backwards;
}

.m-preview-header {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-3);
}

.m-preview-body {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
}

.m-preview-thumb {
  width: 80px;
  height: 80px;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  background: var(--m-color-border-light);
  flex-shrink: 0;
}

.m-preview-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.m-preview-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-tertiary);
}

.m-preview-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.m-preview-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.m-preview-price {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-danger);
  margin-bottom: 4px;
}

.m-preview-stock {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}

.m-safe-publish {
  height: var(--m-space-4);
}

.m-publish-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: var(--m-space-3) var(--m-space-4) calc(var(--m-space-3) + env(safe-area-inset-bottom));
  background: var(--m-color-bg-card);
  display: flex;
  gap: var(--m-space-3);
  z-index: 100;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.04);
}

.m-save-draft-btn {
  width: 80px;
  height: 48px;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-size: 10px;
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
  border: none;
}

.m-save-draft-btn:active {
  transform: scale(0.97);
  background: var(--m-color-border-light);
}

.m-publish-btn {
  flex: 1;
  height: 48px;
  border: none;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  transition: all 0.15s;
}

.m-publish-btn:not(:disabled):active {
  transform: scale(0.98);
  opacity: 0.9;
}

.m-publish-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.m-publish-btn.loading {
  pointer-events: none;
}

button:active,
.m-chip:active,
.m-account-item:active,
.m-candidate-btn:active,
.m-recent-btn:active,
.m-location-btn:active,
.m-stepper-btn:active,
.m-url-btn:not(:disabled):active,
.m-shipping-item:active,
.m-draft-clear:active,
.m-save-draft-btn:active {
  transition-duration: 0.05s;
}

@media (max-width: 360px) {
  .m-publish-hero h1 { font-size: var(--m-font-size-h2); }
  .m-publish-hero-icon { width: 48px; height: 48px; }
  .m-section-card { padding: var(--m-space-4); }
  .m-price-input { font-size: var(--m-font-size-h3); }
  .m-stock-wrap { width: 120px; }
}

@media (min-width: 430px) {
  .m-form-section { max-width: 480px; margin: 0 auto; }
  .m-publish-draft-tip { max-width: 480px; margin-left: auto; margin-right: auto; }
  .m-publish-footer { max-width: 480px; margin: 0 auto; border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0; }
}
</style>
