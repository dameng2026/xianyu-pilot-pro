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
            <div class="m-card-header" style="padding: 0; margin-bottom: 4px">
              <div class="m-card-icon m-icon-purple" style="width: 36px; height: 36px">
                <MIcon name="truck" :size="18" />
              </div>
              <h3 style="font-size: 16px">自动发货</h3>
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
import { uploadImage, uploadImageFromUrl } from '../api/misc.js'
import { accountName } from '../utils/format.js'
import { fetchCategories } from '../api/categories.js'
import { aiRewriteGoods } from '../api/workflow.js'
import { ensureAiTokenBalance } from '../utils/aiTokenGuard.js'
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
  try {
    await new Promise(r => setTimeout(r, 1500))
    alert('发布成功！（演示）')
    clearDraftData()
    emit('back')
  } catch (e) {
    alert('发布失败：' + (e.message || '未知错误'))
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
  background: linear-gradient(180deg, #f0f5ff 0%, #f5f7fb 300px);
  padding-bottom: 100px;
}

.m-publish-hero {
  position: relative;
  padding: 24px 20px 32px;
  overflow: hidden;
}

.m-publish-hero-bg {
  position: absolute;
  top: -50%;
  left: -20%;
  right: -20%;
  bottom: 0;
  background: linear-gradient(135deg, #052e6e 0%, #0a4db0 40%, #0d6bff 100%);
  border-radius: 0 0 40px 40px;
  box-shadow: 0 10px 30px rgba(10, 77, 176, 0.35);
}

.m-publish-hero-bg::before {
  content: '';
  position: absolute;
  top: -80px;
  right: -60px;
  width: 260px;
  height: 260px;
  background: radial-gradient(circle, rgba(99, 179, 255, 0.4) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.m-publish-hero-bg::after {
  content: '';
  position: absolute;
  bottom: -40px;
  left: -40px;
  width: 180px;
  height: 180px;
  background: radial-gradient(circle, rgba(59, 155, 255, 0.25) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.m-publish-hero-content {
  position: relative;
  z-index: 1;
  text-align: center;
  color: white;
}

.m-publish-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  padding: 4px 12px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 12px;
}

.m-publish-hero-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #4ade80;
  box-shadow: 0 0 8px #4ade80;
  animation: m-pulse 2s infinite;
}

@keyframes m-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.m-publish-hero-icon {
  width: 68px;
  height: 68px;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.15);
  animation: iconPop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes iconPop {
  0% { transform: scale(0) rotate(-10deg); opacity: 0; }
  100% { transform: scale(1) rotate(0); opacity: 1; }
}

.m-publish-hero h1 {
  font-size: 28px;
  font-weight: 800;
  margin: 0 0 6px;
  letter-spacing: -0.5px;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.m-publish-hero p {
  font-size: 14px;
  opacity: 0.85;
  margin: 0;
}

.m-publish-draft-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 16px 16px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #fff8e6 0%, #fff0c8 50%, #ffe8a8 100%);
  border: 1px solid #ffe0a0;
  border-radius: 18px;
  font-size: 13px;
  color: #92650a;
  animation: slideDown 0.4s ease-out;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.1);
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.m-draft-icon {
  color: #f59e0b;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(245, 158, 11, 0.3));
}

.m-draft-clear {
  margin-left: auto;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: none;
  background: rgba(245, 158, 11, 0.12);
  color: #c77800;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.m-draft-clear:active {
  transform: scale(0.95);
  background: rgba(245, 158, 11, 0.22);
}

.m-form-section {
  padding: 0 16px;
}

.m-section-card {
  background: white;
  border-radius: 22px;
  padding: 20px;
  margin-bottom: 14px;
  box-shadow: 0 2px 4px rgba(21, 33, 61, 0.02), 0 8px 24px rgba(21, 33, 61, 0.04);
  border: 1px solid rgba(240, 244, 250, 0.95);
  position: relative;
  overflow: hidden;
  animation: cardSlideUp 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
}

.m-section-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.8), transparent);
}

.m-section-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 12px;
  right: 12px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(13, 107, 255, 0.08), transparent);
}

@keyframes cardSlideUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.m-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.m-card-icon {
  width: 42px;
  height: 42px;
  border-radius: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.5), 0 2px 8px rgba(0, 0, 0, 0.04);
}

.m-icon-blue {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 50%, #1d4ed8 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-icon-purple {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 50%, #6d28d9 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-icon-orange {
  background: linear-gradient(135deg, #f97316 0%, #ea580c 50%, #c2410c 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-icon-green {
  background: linear-gradient(135deg, #10b981 0%, #059669 50%, #047857 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-icon-cyan {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 50%, #0e7490 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-icon-red {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-card-header h3 {
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
  margin: 0;
  flex: 1;
}

.m-card-hint {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 500;
  background: #f5f8ff;
  padding: 3px 10px;
  border-radius: 100px;
}

.m-required {
  color: #ef4444;
}

.m-form-group {
  margin-bottom: 18px;
}

.m-form-group:last-child {
  margin-bottom: 0;
}

.m-form-group label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 8px;
}

.m-input-wrap {
  position: relative;
}

.m-input {
  width: 100%;
  height: 50px;
  padding: 0 70px 0 16px;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  font-size: 15px;
  color: #15213d;
  background: #f8fafc;
  box-sizing: border-box;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.m-input:focus {
  border-color: #0d6bff;
  background: white;
  box-shadow: 0 0 0 4px rgba(13, 107, 255, 0.12), 0 2px 8px rgba(13, 107, 255, 0.08);
  transform: translateY(-1px);
}

.m-input.error {
  border-color: #ef4444;
  background: #fef2f2;
  animation: shake 0.4s ease;
}

.m-char-count {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 3px 10px;
  border-radius: 100px;
  font-weight: 500;
}

.m-textarea {
  width: 100%;
  min-height: 120px;
  padding: 14px 16px;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  font-size: 15px;
  color: #15213d;
  background: #f8fafc;
  box-sizing: border-box;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  resize: none;
  font-family: inherit;
  line-height: 1.6;
}

.m-textarea:focus {
  border-color: #0d6bff;
  background: white;
  box-shadow: 0 0 0 4px rgba(13, 107, 255, 0.12), 0 2px 8px rgba(13, 107, 255, 0.08);
  transform: translateY(-1px);
}

.m-chips-row {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.m-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 16px;
  border: none;
  border-radius: 100px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  background: #f1f5f9;
  color: #64748b;
}

.m-chip:hover {
  background: #e2e8f0;
}

.m-chip:active {
  transform: scale(0.96);
}

.m-chip-primary {
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 50%, #5eb5ff 100%);
  color: white;
  box-shadow: 0 6px 16px rgba(13, 127, 255, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-chip-primary:hover {
  background: linear-gradient(135deg, #0b6fe6 0%, #2f8af0 50%, #4fa8f0 100%);
  box-shadow: 0 8px 20px rgba(13, 127, 255, 0.35);
}

.m-chip-primary.loading {
  opacity: 0.7;
  pointer-events: none;
}

.m-error-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 13px;
  color: #ef4444;
  animation: shake 0.5s cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
  20%, 40%, 60%, 80% { transform: translateX(5px); }
}

.m-account-selector {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-account-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

.m-account-item:hover {
  border-color: #dbeafe;
  background: #f5f9ff;
}

.m-account-item:active {
  transform: scale(0.98);
}

.m-account-item.active {
  border-color: #0d6bff;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f0ff 100%);
  box-shadow: 0 4px 16px rgba(13, 107, 255, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.m-account-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 4px;
  background: linear-gradient(180deg, #0d7fff 0%, #3b9bff 100%);
  border-radius: 0 4px 4px 0;
}

.m-account-avatar {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, #4a8fff 0%, #2d6bff 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: 0 6px 16px rgba(74, 143, 255, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-account-info {
  flex: 1;
  min-width: 0;
}

.m-account-name {
  font-size: 15px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-account-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #f59e0b;
  background: #fffbeb;
  padding: 3px 10px;
  border-radius: 100px;
  font-weight: 500;
}

.m-account-status.authorized {
  color: #059669;
  background: #ecfdf5;
}

.m-account-check {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(13, 127, 255, 0.35);
  animation: checkPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes checkPop {
  0% { transform: scale(0); }
  50% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

.m-empty-accounts {
  text-align: center;
  padding: 32px 20px;
  color: #94a3b8;
}

.m-empty-accounts p {
  margin: 12px 0 0;
  font-size: 14px;
}

.m-image-tip {
  font-size: 13px;
  color: #94a3b8;
  margin: -8px 0 14px;
}

.m-image-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.m-image-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 16px;
  overflow: hidden;
  background: #f1f5f9;
  animation: imgPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 2px 8px rgba(21, 33, 61, 0.06);
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s;
}

.m-image-item:hover {
  transform: scale(1.02);
  box-shadow: 0 6px 16px rgba(21, 33, 61, 0.1);
}

@keyframes imgPop {
  from { opacity: 0; transform: scale(0.8); }
  to { opacity: 1; transform: scale(1); }
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
  border: 3px solid #0d6bff;
  border-radius: 16px;
  pointer-events: none;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.3);
}

.m-image-cover-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 100%);
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 100px;
  box-shadow: 0 4px 12px rgba(13, 127, 255, 0.4);
}

.m-image-remove {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  border: none;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: all 0.25s;
  transform: scale(0.8);
}

.m-image-item:hover .m-image-remove,
.m-image-item:active .m-image-remove {
  opacity: 1;
  transform: scale(1);
}

.m-image-add {
  aspect-ratio: 1;
  border-radius: 16px;
  border: 2px dashed #cbd5e1;
  background: radial-gradient(circle at center, #f8fafc 0%, #f1f5f9 100%);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.m-image-add:hover {
  border-color: #93c5fd;
  background: radial-gradient(circle at center, #f0f7ff 0%, #e8f0ff 100%);
}

.m-image-add:active {
  transform: scale(0.97);
  border-color: #0d6bff;
  background: radial-gradient(circle at center, #e8f1ff 0%, #dbeafe 100%);
}

.m-image-add-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 500;
  transition: color 0.25s;
}

.m-image-add:hover .m-image-add-inner {
  color: #0d6bff;
}

.m-url-input-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 4px 4px 14px;
  background: #f8fafc;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.m-url-input-wrap:focus-within {
  border-color: #0d6bff;
  background: white;
  box-shadow: 0 0 0 4px rgba(13, 107, 255, 0.08);
}

.m-url-icon {
  color: #94a3b8;
  flex-shrink: 0;
}

.m-url-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  color: #15213d;
  outline: none;
  padding: 10px 0;
  min-width: 0;
}

.m-url-btn {
  padding: 10px 18px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 100%);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(13, 127, 255, 0.25);
}

.m-url-btn:hover:not(:disabled) {
  box-shadow: 0 6px 16px rgba(13, 127, 255, 0.35);
}

.m-url-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-url-btn:not(:disabled):active {
  transform: scale(0.96);
}

.m-auto-category-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-radius: 14px;
  font-size: 13px;
  color: #92400e;
  margin-bottom: 12px;
}

.m-loading-dot {
  color: #f59e0b;
  font-weight: 500;
}

.m-category-msg {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  margin-bottom: 12px;
}

.m-category-msg.info {
  background: #eff6ff;
  color: #1d4ed8;
}

.m-category-msg.success {
  background: #ecfdf5;
  color: #059669;
}

.m-category-msg.error {
  background: #fef2f2;
  color: #dc2626;
}

.m-candidates-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.m-candidates-label {
  font-size: 13px;
  color: #64748b;
  align-self: center;
}

.m-candidate-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border: 2px solid #e2e8f0;
  border-radius: 100px;
  background: white;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  font-weight: 500;
}

.m-candidate-btn:hover {
  border-color: #bfdbfe;
  background: #f8fafc;
}

.m-candidate-btn:active {
  transform: scale(0.97);
}

.m-candidate-btn.active {
  border-color: #0d6bff;
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(13, 127, 255, 0.25);
}

.m-candidate-btn small {
  opacity: 0.75;
  font-size: 11px;
}

.m-category-selected {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border-radius: 14px;
  font-size: 14px;
  color: #059669;
  font-weight: 500;
  margin-bottom: 12px;
}

.m-selected-icon {
  flex-shrink: 0;
}

.m-cascader-wrap {
  background: #f8fafc;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid #f1f5f9;
}

.m-cascader-cols {
  display: flex;
  max-height: 240px;
  overflow-y: auto;
}

.m-cascader-col {
  flex: 1;
  min-width: 0;
  border-right: 1px solid #f1f5f9;
}

.m-cascader-col:last-child {
  border-right: none;
}

.m-cascader-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

.m-cascader-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  font-size: 14px;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 1px solid #f1f5f9;
  position: relative;
}

.m-cascader-item:last-child {
  border-bottom: none;
}

.m-cascader-item:hover {
  background: #f1f5f9;
}

.m-cascader-item:active {
  background: #e8f1ff;
}

.m-cascader-item.active {
  background: linear-gradient(90deg, #e8f1ff 0%, #f0f7ff 100%);
  color: #0d6bff;
  font-weight: 600;
}

.m-cascader-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: linear-gradient(180deg, #0d7fff, #3b9bff);
  border-radius: 0 3px 3px 0;
}

.m-cascader-arrow {
  color: #94a3b8;
  flex-shrink: 0;
}

.m-cascader-item.active .m-cascader-arrow {
  color: #0d6bff;
}

.m-recent-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  align-items: center;
}

.m-recent-label {
  font-size: 13px;
  color: #64748b;
}

.m-recent-btn {
  padding: 7px 14px;
  border: none;
  border-radius: 100px;
  background: #f1f5f9;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  font-weight: 500;
}

.m-recent-btn:hover {
  background: #e2e8f0;
  color: #475569;
}

.m-recent-btn:active {
  transform: scale(0.97);
  background: #e2e8f0;
}

.m-location-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 16px;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: left;
}

.m-location-btn:hover {
  border-color: #dbeafe;
  background: #f5f9ff;
}

.m-location-btn:active {
  transform: scale(0.98);
  border-color: #0d6bff;
  background: #f0f7ff;
}

.m-location-icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(6, 182, 212, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.m-location-info {
  flex: 1;
  min-width: 0;
}

.m-location-label {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 2px;
}

.m-location-desc {
  font-size: 12px;
  color: #94a3b8;
}

.m-location-arrow {
  color: #cbd5e1;
  flex-shrink: 0;
}

.m-price-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.m-price-input-wrap {
  flex: 1;
  position: relative;
}

.m-price-symbol {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 24px;
  font-weight: 800;
  color: #ef4444;
  z-index: 1;
}

.m-price-input {
  width: 100%;
  height: 58px;
  padding: 0 16px 0 42px;
  border: 2px solid #f1f5f9;
  border-radius: 18px;
  font-size: 26px;
  font-weight: 800;
  color: #ef4444;
  background: #f8fafc;
  box-sizing: border-box;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.m-price-input:focus {
  border-color: #ef4444;
  background: white;
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1), 0 2px 8px rgba(239, 68, 68, 0.08);
}

.m-price-input.error {
  border-color: #ef4444;
  animation: shake 0.4s ease;
}

.m-stock-wrap {
  width: 150px;
}

.m-stock-wrap label {
  display: block;
  font-size: 13px;
  color: #64748b;
  margin-bottom: 6px;
  font-weight: 600;
}

.m-stepper {
  display: flex;
  align-items: center;
  height: 50px;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  background: #f8fafc;
  overflow: hidden;
  transition: all 0.3s;
}

.m-stepper:focus-within {
  border-color: #0d6bff;
  background: white;
  box-shadow: 0 0 0 4px rgba(13, 107, 255, 0.08);
}

.m-stepper-btn {
  width: 46px;
  height: 100%;
  border: none;
  background: transparent;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.m-stepper-btn:hover {
  background: #e8f1ff;
  color: #0d6bff;
}

.m-stepper-btn:active {
  background: #dbeafe;
  transform: scale(0.95);
}

.m-stepper-input {
  flex: 1;
  width: 100%;
  text-align: center;
  border: none;
  background: transparent;
  font-size: 18px;
  font-weight: 700;
  color: #15213d;
  outline: none;
}

.m-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.m-toggle-info {
  flex: 1;
  min-width: 0;
}

.m-toggle-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 0;
}

.m-switch {
  width: 54px;
  height: 34px;
  border-radius: 100px;
  border: none;
  background: linear-gradient(135deg, #e2e8f0, #cbd5e1);
  position: relative;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  padding: 0;
  flex-shrink: 0;
  box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.1);
}

.m-switch.on {
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 50%, #5eb5ff 100%);
  box-shadow: 0 8px 24px rgba(13, 127, 255, 0.4), inset 0 1px 2px rgba(255, 255, 255, 0.25);
}

.m-switch-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 28px;
  height: 28px;
  background: white;
  border-radius: 50%;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.15);
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.m-switch.on .m-switch-knob {
  transform: translateX(20px);
  animation: knobBounce 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes knobBounce {
  0% { transform: translateX(0); }
  50% { transform: translateX(22px); }
  70% { transform: translateX(19px); }
  100% { transform: translateX(20px); }
}

.m-auto-delivery-body {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.m-auto-delivery-body label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 8px;
}

.m-select {
  width: 100%;
  height: 50px;
  padding: 0 16px;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  font-size: 15px;
  color: #15213d;
  background: #f8fafc;
  box-sizing: border-box;
  outline: none;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 40px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.m-select:focus {
  border-color: #0d6bff;
  background-color: white;
  box-shadow: 0 0 0 4px rgba(13, 107, 255, 0.08);
}

.m-loading-text,
.m-success-text,
.m-warning-text,
.m-error-text {
  margin-top: 8px;
  font-size: 13px;
}

.m-loading-text { color: #64748b; }
.m-success-text { color: #059669; }
.m-warning-text { color: #d97706; }
.m-error-text { color: #dc2626; }

.m-shipping-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-shipping-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.m-shipping-item:hover {
  border-color: #dbeafe;
  background: #f5f9ff;
}

.m-shipping-item:active {
  transform: scale(0.98);
}

.m-shipping-item.active {
  border-color: #0d6bff;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f0ff 100%);
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.1);
}

.m-radio-circle {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid #cbd5e1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.m-shipping-item.active .m-radio-circle {
  border-color: #0d6bff;
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 100%);
  box-shadow: 0 4px 12px rgba(13, 127, 255, 0.3);
  animation: radioPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes radioPop {
  0% { transform: scale(0); }
  40% { transform: scale(1.25); }
  70% { transform: scale(0.95); }
  100% { transform: scale(1); }
}

.m-shipping-info {
  flex: 1;
}

.m-shipping-label {
  font-size: 15px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 2px;
}

.m-shipping-desc {
  font-size: 12px;
  color: #94a3b8;
}

.m-preview-card {
  background: white;
  border-radius: 22px;
  padding: 20px;
  margin-bottom: 14px;
  box-shadow: 0 2px 4px rgba(21, 33, 61, 0.02), 0 8px 24px rgba(21, 33, 61, 0.04);
  border: 1px solid transparent;
  background-clip: padding-box;
  position: relative;
  animation: cardSlideUp 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
}

.m-preview-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 22px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(13, 107, 255, 0.15), rgba(139, 92, 246, 0.1), rgba(16, 185, 129, 0.1));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.m-preview-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(13, 107, 255, 0.12), transparent);
}

.m-preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 14px;
}

.m-preview-body {
  display: flex;
  gap: 12px;
  padding: 14px;
  background: linear-gradient(135deg, #f8fafc 0%, #f5f9ff 100%);
  border-radius: 16px;
}

.m-preview-thumb {
  width: 90px;
  height: 90px;
  border-radius: 12px;
  overflow: hidden;
  background: linear-gradient(135deg, #e2e8f0, #f1f5f9);
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(21, 33, 61, 0.06);
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
  color: #94a3b8;
}

.m-preview-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.m-preview-title {
  font-size: 15px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.m-preview-price {
  font-size: 24px;
  font-weight: 800;
  color: #ef4444;
  margin-bottom: 4px;
}

.m-preview-stock {
  font-size: 12px;
  color: #94a3b8;
}

.m-safe-publish {
  height: 20px;
}

.m-publish-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-top: 1px solid rgba(231, 237, 247, 0.6);
  display: flex;
  gap: 12px;
  z-index: 100;
  box-shadow: 0 -8px 32px rgba(31, 53, 94, 0.08);
}

.m-publish-footer::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(13, 107, 255, 0.08), transparent);
}

.m-save-draft-btn {
  width: 88px;
  height: 54px;
  border: 2px solid #e2e8f0;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  color: #64748b;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}

.m-save-draft-btn:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.m-save-draft-btn:active {
  transform: scale(0.97);
  background: #f1f5f9;
}

.m-publish-btn {
  flex: 1;
  height: 54px;
  border: none;
  border-radius: 16px;
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 45%, #5eb5ff 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 10px 28px rgba(13, 127, 255, 0.4), 0 4px 12px rgba(13, 127, 255, 0.2);
  position: relative;
  overflow: hidden;
}

.m-publish-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  transition: left 0.6s ease;
}

.m-publish-btn:not(:disabled):hover {
  box-shadow: 0 12px 32px rgba(13, 127, 255, 0.45), 0 6px 16px rgba(13, 127, 255, 0.25);
  transform: translateY(-1px);
}

.m-publish-btn:not(:disabled):active {
  transform: scale(0.98);
  box-shadow: 0 6px 16px rgba(13, 127, 255, 0.35);
}

.m-publish-btn:not(:disabled):active::before {
  left: 100%;
}

.m-publish-btn:disabled {
  opacity: 0.7;
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
  transition-duration: 0.1s;
}

@media (max-width: 360px) {
  .m-publish-hero h1 { font-size: 24px; }
  .m-publish-hero-icon { width: 60px; height: 60px; }
  .m-section-card { padding: 16px; border-radius: 20px; }
  .m-image-grid { gap: 8px; }
  .m-price-input { font-size: 22px; }
  .m-stock-wrap { width: 130px; }
  .m-publish-btn { font-size: 16px; }
}

@media (min-width: 430px) {
  .m-form-section { max-width: 500px; margin: 0 auto; }
  .m-publish-draft-tip { max-width: 500px; margin-left: auto; margin-right: auto; }
  .m-publish-footer { max-width: 500px; margin: 0 auto; border-radius: 20px 20px 0 0; }
}
</style>
