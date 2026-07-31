<template>
  <div class="supply-edit-page">
    <!-- 页头 -->
    <div class="spe-header">
      <div class="spe-header-left">
        <button type="button" class="spe-back-btn" @click="emit('navigate', 'supply-center-products')">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none">
            <path d="M10 4L6 8L10 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          返回
        </button>
        <h2 class="spe-title">{{ isEdit ? '编辑货源' : '上传货源' }}</h2>
      </div>
    </div>

    <!-- 类型切换 -->
    <div class="spe-type-tabs">
      <button
        v-for="t in productTypes"
        :key="t.value"
        type="button"
        :class="['spe-type-tab', { active: form.productType === t.value }]"
        :disabled="isEdit"
        @click="switchType(t.value)"
      >
        <span class="spe-type-icon" v-html="t.icon"></span>
        <span class="spe-type-text">{{ t.label }}</span>
        <span class="spe-type-desc">{{ t.desc }}</span>
      </button>
    </div>

    <!-- 表单 -->
    <div class="spe-form-card">
      <div v-if="loadError" class="spe-form-error">
        {{ loadError }}
      </div>

      <div class="spe-form-section">
        <h3 class="spe-section-title">基础信息</h3>
        <div class="spe-form-grid">
          <div class="spe-form-row spe-form-row-full">
            <label class="spe-form-label required">商品标题</label>
            <input
              v-model="form.title"
              type="text"
              class="spe-input"
              placeholder="请输入商品标题（最多 60 字）"
              maxlength="60"
            />
          </div>
          <div class="spe-form-row spe-form-row-full">
            <label class="spe-form-label">副标题</label>
            <input
              v-model="form.subtitle"
              type="text"
              class="spe-input"
              placeholder="一句话描述商品亮点（可选）"
              maxlength="100"
            />
          </div>
          <div class="spe-form-row">
            <label class="spe-form-label">商品分类</label>
            <input
              v-model="form.category"
              type="text"
              class="spe-input"
              placeholder="如：教程 / 软件 / 卡密"
              maxlength="20"
            />
          </div>
          <div class="spe-form-row">
            <label class="spe-form-label required">价格（元）</label>
            <input
              v-model.number="priceYuan"
              type="number"
              class="spe-input"
              placeholder="0.00"
              min="0"
              step="0.01"
            />
          </div>
          <div class="spe-form-row spe-form-row-full">
            <label class="spe-form-label">封面图 URL</label>
            <input
              v-model="form.coverUrl"
              type="text"
              class="spe-input"
              placeholder="https:// 或 /uploads/ 开头的图片地址"
            />
            <div class="spe-cover-preview" :style="coverStyle">
              <img v-if="form.coverUrl" :src="form.coverUrl" alt="封面预览" @error="onCoverError" />
            </div>
          </div>
        </div>
      </div>

      <!-- 文本发货内容 -->
      <div v-if="form.productType === 'text'" class="spe-form-section">
        <h3 class="spe-section-title">发货内容</h3>
        <div class="spe-form-row spe-form-row-full">
          <label class="spe-form-label required">文本内容</label>
          <textarea
            v-model="form.deliveryContent"
            class="spe-textarea"
            placeholder="买家付款后将自动收到此文本内容，支持多行"
            rows="8"
          ></textarea>
          <div class="spe-form-tip">
            <svg viewBox="0 0 16 16" width="13" height="13" fill="none">
              <circle cx="8" cy="8" r="6.5" stroke="#94a3b8" stroke-width="1.2"/>
              <path d="M8 5V9M8 11V11.2" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            文本商品无库存限制，可无限次发货
          </div>
        </div>
      </div>

      <!-- 卡密发货配置 -->
      <div v-if="form.productType === 'card'" class="spe-form-section">
        <h3 class="spe-section-title">卡密配置</h3>
        <div v-if="!cardGroupsAvailable" class="spe-form-warn">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
            <path d="M8 2L14 13H2L8 2Z" stroke="#f59e0b" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M8 7V9.5" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          暂无可用卡密分组，请先到「卡密仓库」创建分组并导入卡密
        </div>
        <div class="spe-form-row spe-form-row-full">
          <label class="spe-form-label required">卡密分组</label>
          <select v-model="form.cardGroupId" class="spe-input" :disabled="!cardGroupsAvailable">
            <option value="">请选择卡密分组</option>
            <option v-for="g in cardGroups" :key="g.id" :value="g.id">
              {{ g.groupName }}（余 {{ g.remainCount ?? '—' }}）
            </option>
          </select>
        </div>
        <div class="spe-form-row spe-form-row-full">
          <label class="spe-form-label">商品描述</label>
          <textarea
            v-model="form.content"
            class="spe-textarea"
            placeholder="介绍卡密商品的用途、有效期、使用说明等（可选）"
            rows="4"
          ></textarea>
        </div>
      </div>

      <!-- 佣金设置 -->
      <div class="spe-form-section">
        <h3 class="spe-section-title">分销佣金</h3>
        <div class="spe-form-row spe-form-row-full">
          <label class="spe-form-label">佣金比例</label>
          <div class="spe-commission-wrap">
            <input
              v-model.number="commissionPercent"
              type="number"
              class="spe-input spe-commission-input"
              placeholder="5"
              min="0"
              max="50"
              step="0.5"
            />
            <span class="spe-commission-suffix">%</span>
            <span class="spe-commission-tip">分销商推广此商品时可获得的佣金比例（默认 5%）</span>
          </div>
        </div>
      </div>

      <!-- 操作区 -->
      <div class="spe-form-actions">
        <button type="button" class="spe-btn spe-btn-ghost" @click="emit('navigate', 'supply-center-products')">取消</button>
        <button type="button" class="spe-btn spe-btn-primary" :disabled="submitting || !canSubmit" @click="handleSubmit">
          <span v-if="submitting" class="spe-spinner"></span>
          {{ submitting ? '提交中...' : (isEdit ? '保存修改' : '提交审核') }}
        </button>
      </div>

      <div v-if="formHint" class="spe-form-hint">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
          <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>
          <path d="M8 5V9M8 11V11.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        {{ formHint }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { getCards } from '../api/cards.js'
import {
  createSupplyProduct,
  getSupplyProductDetail,
  updateSupplyProduct
} from '../api/supply.js'

const emit = defineEmits(['navigate'])

const isEdit = computed(() => !!productId.value)
const productId = ref(null)

const form = ref({
  productType: 'text',
  title: '',
  subtitle: '',
  category: '',
  coverUrl: '',
  deliveryContent: '',
  content: '',
  cardGroupId: '',
  commissionRate: 0.05
})

const priceYuan = ref(0)
const commissionPercent = ref(5)

const submitting = ref(false)
const loadError = ref('')
const formHint = ref('')

const cardGroups = ref([])
const cardGroupsAvailable = ref(false)

const productTypes = [
  {
    value: 'text',
    label: '文本货源',
    desc: '文本内容自动发货',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="M4 6H20M4 10H20M4 14H14M4 18H10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
  },
  {
    value: 'card',
    label: '卡密货源',
    desc: '卡密库存自动发货',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><rect x="3" y="6" width="18" height="13" rx="2" stroke="currentColor" stroke-width="2"/><path d="M3 10H21" stroke="currentColor" stroke-width="2"/><rect x="6" y="13" width="6" height="2" rx="1" fill="currentColor"/></svg>'
  }
]

const coverStyle = computed(() => {
  const url = form.value.coverUrl || ''
  if (url) {
    return {
      backgroundImage: `url(${url})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center'
    }
  }
  return { background: 'linear-gradient(135deg, #e2e8f0, #cbd5e1)' }
})

const canSubmit = computed(() => {
  const f = form.value
  if (!f.title || !f.title.trim()) return false
  if (priceYuan.value < 0) return false
  if (f.productType === 'text') {
    if (!f.deliveryContent || !f.deliveryContent.trim()) return false
  } else if (f.productType === 'card') {
    if (!f.cardGroupId) return false
  }
  return true
})

function switchType(type) {
  if (isEdit.value) return
  form.value.productType = type
}

function onCoverError() {
  // 封面加载失败时仅清空预览，不打断输入
}

// 路由参数解析：#/supply-center-products-edit/{id}（编辑模式）
// 无 id 段则为新建模式（#/supply-center-products-new）
function parseRouteParams() {
  const raw = (location.hash || '').replace(/^#\//, '')
  const m = raw.match(/^supply-center-products-edit\/(\d+)/)
  if (m) {
    const id = Number(m[1])
    if (Number.isFinite(id) && id > 0) {
      productId.value = id
      return
    }
  }
  productId.value = null
}

async function loadCardGroups() {
  try {
    const res = await getCards({ size: 200 })
    const records = recordsOfOrThrow(res?.data, '卡密分组响应格式异常')
    cardGroups.value = records
    cardGroupsAvailable.value = records.length > 0
  } catch (e) {
    cardGroups.value = []
    cardGroupsAvailable.value = false
  }
}

async function loadProductDetail() {
  if (!productId.value) return
  loadError.value = ''
  try {
    const res = await getSupplyProductDetail(productId.value)
    const data = res?.data || res || {}
    form.value = {
      productType: data.product_type || data.productType || 'text',
      title: data.title || '',
      subtitle: data.subtitle || '',
      category: data.category || '',
      coverUrl: data.cover_url || data.coverUrl || '',
      deliveryContent: data.delivery_content || data.deliveryContent || '',
      content: data.content || '',
      cardGroupId: data.card_group_id || data.cardGroupId || '',
      commissionRate: Number(data.commission_rate ?? data.commissionRate ?? 0.05)
    }
    const pCent = Number(data.price_cent ?? data.priceCent ?? 0)
    priceYuan.value = Number.isFinite(pCent) ? pCent / 100 : 0
    commissionPercent.value = Number(form.value.commissionRate) * 100
  } catch (e) {
    loadError.value = e?.message || '货源详情加载失败'
  }
}

async function handleSubmit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  formHint.value = ''
  try {
    const priceCent = Math.round(Number(priceYuan.value || 0) * 100)
    const commissionRate = (Number(commissionPercent.value || 0) / 100).toFixed(4)
    const payload = {
      productType: form.value.productType,
      title: form.value.title.trim(),
      subtitle: form.value.subtitle?.trim() || '',
      category: form.value.category?.trim() || '',
      coverUrl: form.value.coverUrl?.trim() || '',
      priceCent,
      commissionRate
    }
    if (form.value.productType === 'text') {
      payload.deliveryContent = form.value.deliveryContent
    } else {
      payload.cardGroupId = Number(form.value.cardGroupId) || null
      payload.content = form.value.content || ''
    }
    if (isEdit.value) {
      const res = await updateSupplyProduct(productId.value, payload)
      const data = res?.data || res || {}
      formHint.value = data.needReaudit ? '修改成功，已重新提交审核' : (data.message || '修改成功')
      setTimeout(() => emit('navigate', 'supply-center-products'), 800)
    } else {
      const res = await createSupplyProduct(payload)
      const data = res?.data || res || {}
      formHint.value = data.message || '货源已提交，等待审核'
      setTimeout(() => emit('navigate', 'supply-center-products'), 800)
    }
  } catch (e) {
    formHint.value = ''
    loadError.value = e?.message || (isEdit.value ? '保存失败，请稍后重试' : '提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  parseRouteParams()
  await loadCardGroups()
  if (isEdit.value) {
    await loadProductDetail()
  }
})
</script>

<style scoped>
.supply-edit-page {
  width: 100%;
  min-height: 100%;
  box-sizing: border-box;
  padding: 4px;
}

/* 页头 */
.spe-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 12px;
  flex-wrap: wrap;
}
.spe-header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.spe-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.spe-back-btn:hover {
  border-color: #4f7cff;
  color: #4f7cff;
}
.spe-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}

/* 类型 tab */
.spe-type-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 20px;
}
@media (max-width: 640px) {
  .spe-type-tabs { grid-template-columns: 1fr; }
}
.spe-type-tab {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 2px solid #e8edf5;
  background: #fff;
  cursor: pointer;
  transition: all 0.18s;
  text-align: left;
  font-family: inherit;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.spe-type-tab:hover:not(:disabled) {
  border-color: #c7d2fe;
  transform: translateY(-1px);
}
.spe-type-tab.active {
  border-color: #4f7cff;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
}
.spe-type-tab:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.spe-type-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(79, 124, 255, 0.1);
  color: #4f7cff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
}
.spe-type-tab.active .spe-type-icon {
  background: #4f7cff;
  color: #fff;
}
.spe-type-text {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.spe-type-desc {
  font-size: 12px;
  color: #94a3b8;
}

/* 表单卡片 */
.spe-form-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e8edf5;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  padding: 24px;
}
@media (max-width: 640px) {
  .spe-form-card { padding: 18px 16px; }
}

.spe-form-error {
  padding: 12px 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
  color: #ef4444;
  font-size: 13px;
  margin-bottom: 18px;
}

.spe-form-section {
  padding: 18px 0;
  border-bottom: 1px solid #f1f5f9;
}
.spe-form-section:last-of-type {
  border-bottom: none;
}
.spe-section-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 14px;
}

.spe-form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
@media (max-width: 640px) {
  .spe-form-grid { grid-template-columns: 1fr; }
}
.spe-form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.spe-form-row-full {
  grid-column: 1 / -1;
}
.spe-form-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.spe-form-label.required::after {
  content: ' *';
  color: #ef4444;
}
.spe-input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  font-size: 14px;
  color: #0f172a;
  transition: border-color 0.15s, box-shadow 0.15s;
  outline: none;
  font-family: inherit;
  width: 100%;
  box-sizing: border-box;
}
.spe-input:focus {
  border-color: #4f7cff;
  box-shadow: 0 0 0 3px rgba(79, 124, 255, 0.12);
}
.spe-input:disabled {
  background: #f8fafc;
  cursor: not-allowed;
}
.spe-textarea {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  font-size: 14px;
  color: #0f172a;
  font-family: inherit;
  outline: none;
  resize: vertical;
  min-height: 100px;
  width: 100%;
  box-sizing: border-box;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.spe-textarea:focus {
  border-color: #4f7cff;
  box-shadow: 0 0 0 3px rgba(79, 124, 255, 0.12);
}

.spe-cover-preview {
  width: 120px;
  height: 80px;
  border-radius: 10px;
  overflow: hidden;
  margin-top: 8px;
  border: 1px solid #e2e8f0;
}
.spe-cover-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.spe-form-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.spe-form-warn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  color: #92400e;
  font-size: 13px;
  margin-bottom: 14px;
}

.spe-commission-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.spe-commission-input {
  width: 100px;
}
.spe-commission-suffix {
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
}
.spe-commission-tip {
  font-size: 12px;
  color: #94a3b8;
  flex: 1;
  min-width: 200px;
}

/* 操作区 */
.spe-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 20px;
  border-top: 1px solid #f1f5f9;
  margin-top: 8px;
}
.spe-btn {
  height: 42px;
  padding: 0 22px;
  border-radius: 12px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.spe-btn-ghost {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #64748b;
}
.spe-btn-ghost:hover {
  border-color: #cbd5e1;
  color: #475569;
}
.spe-btn-primary {
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  box-shadow: 0 4px 10px rgba(13, 107, 255, 0.25);
}
.spe-btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(13, 107, 255, 0.35);
}
.spe-btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spe-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spe-spin 0.7s linear infinite;
}
@keyframes spe-spin {
  to { transform: rotate(360deg); }
}

.spe-form-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  margin-top: 16px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  color: #1e40af;
  font-size: 13px;
}
</style>
