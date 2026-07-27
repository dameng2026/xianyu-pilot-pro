<template>
  <div class="multi-spec-editor">
    <!-- 顶部说明卡片 -->
    <div class="ms-header">
      <div class="ms-header-left">
        <span class="ms-header-icon" aria-hidden="true">⚙</span>
        <div class="ms-header-text">
          <div class="ms-title">多规格商品</div>
          <div class="ms-hint">仅鱼小铺账号可用 · 最多 2 个规格类型 · 自动生成 SKU 笛卡尔积</div>
        </div>
      </div>
      <div class="ms-header-stats">
        <span class="ms-stat-chip ms-stat-prop">{{ propertyCount }} 规格类型</span>
        <span class="ms-stat-chip ms-stat-sku">{{ modelValue.skuList.length }} SKU</span>
      </div>
    </div>

    <!-- 规格类型列表 -->
    <div v-for="(prop, pIdx) in modelValue.propertyGroups" :key="pIdx" class="ms-prop-block">
      <div class="ms-prop-header">
        <span class="ms-prop-index">{{ pIdx + 1 }}</span>
        <input
          v-model="prop.propertyName"
          type="text"
          class="ms-input ms-prop-name"
          placeholder="规格名称（如：颜色、尺码）"
          :maxlength="20"
        />
        <span class="ms-prop-values-count">{{ validValueCount(pIdx) }} 个规格值</span>
        <label class="ms-checkbox" :class="{ 'ms-checkbox-checked': prop.supportImage }" :title="hasOtherSupportImage(pIdx) ? '已选中其他规格支持图片，将自动切换' : '仅支持一个规格类型启用图片'">
          <input
            type="checkbox"
            :checked="prop.supportImage"
            @change="onSupportImageChange(pIdx, $event.target.checked)"
          />
          <span class="ms-checkbox-box" aria-hidden="true">{{ prop.supportImage ? '✓' : '' }}</span>
          <span>支持规格图片</span>
        </label>
        <button type="button" class="ms-btn-danger" @click="removeProperty(pIdx)">
          <span aria-hidden="true">✕</span> 删除规格
        </button>
      </div>

      <!-- 规格值列表 -->
      <div class="ms-values">
        <div v-for="(val, vIdx) in prop.propertyValues" :key="vIdx" class="ms-value-row">
          <input
            v-model="val.propertyValue"
            type="text"
            class="ms-input ms-value-input"
            placeholder="如：红色"
            :maxlength="30"
          />
          <!-- 规格图片（仅 supportImage=true 时显示） -->
          <div v-if="prop.supportImage" class="ms-value-img">
            <div class="ms-img-wrapper">
              <img v-if="val.propertyValueImg" :src="displayUrl(val.propertyValueImg)" alt="" @error="onImgError($event)" />
              <div v-else class="ms-img-placeholder">
                <span aria-hidden="true">🖼</span>
                <span class="ms-img-placeholder-text">未上传</span>
              </div>
            </div>
            <div class="ms-img-actions">
              <button
                type="button"
                class="ms-btn-mini"
                @click="$emit('upload-spec-image', { pIdx, vIdx })"
              >{{ val.propertyValueImg ? '更换' : '上传' }}</button>
              <button
                v-if="val.propertyValueImg"
                type="button"
                class="ms-btn-mini ms-btn-danger-mini"
                @click="val.propertyValueImg = ''"
              >清除</button>
            </div>
          </div>
          <button
            type="button"
            class="ms-btn-remove-value"
            :title="`删除规格值 ${val.propertyValue || ''}`"
            @click="removeValue(pIdx, vIdx)"
          ><span aria-hidden="true">×</span></button>
        </div>
        <button type="button" class="ms-btn-add" @click="addValue(pIdx)">
          <span aria-hidden="true">＋</span> 添加规格值
        </button>
      </div>
    </div>

    <!-- 添加规格类型按钮 -->
    <button
      v-if="modelValue.propertyGroups.length < 2"
      type="button"
      class="ms-btn-add ms-btn-add-prop"
      @click="addProperty"
    >
      <span aria-hidden="true">＋</span> 添加规格类型（还剩 {{ 2 - modelValue.propertyGroups.length }} 个）
    </button>
    <div v-else class="ms-prop-limit-hint">
      <span aria-hidden="true">⚠</span> 已达到最多 2 个规格类型上限
    </div>

    <!-- 单规格模式提示 -->
    <div v-if="modelValue.propertyGroups.length === 0" class="ms-single-mode-hint">
      <span class="ms-single-mode-icon" aria-hidden="true">📦</span>
      <div class="ms-single-mode-text">
        <div class="ms-single-mode-title">当前为单规格模式</div>
        <div class="ms-single-mode-desc">可直接在下方 SKU 表格中设置售价、库存与封面图。如需多规格组合，请点击上方"添加规格类型"。</div>
      </div>
    </div>

    <!-- SKU 表格 -->
    <div v-if="modelValue.skuList.length > 0" class="ms-sku-table">
      <div class="ms-sku-header">
        <div class="ms-sku-header-left">
          <span class="ms-sku-title">SKU 列表</span>
          <span class="ms-sku-count">{{ modelValue.skuList.length }} 个组合</span>
        </div>
        <div class="ms-sku-header-right">
          <span class="ms-sku-stat" :class="{ 'ms-sku-stat-warn': !allSkusFilled }">
            <span class="ms-sku-stat-label">总库存</span>
            <span class="ms-sku-stat-value">{{ totalStock }}</span>
          </span>
          <span class="ms-sku-stat" :class="{ 'ms-sku-stat-warn': !allSkusFilled }">
            <span class="ms-sku-stat-label">起售价</span>
            <span class="ms-sku-stat-value">¥{{ minPrice }}</span>
          </span>
          <span v-if="!allSkusFilled" class="ms-sku-stat ms-sku-stat-error">
            <span aria-hidden="true">⚠</span> 有 {{ unfilledSkuCount }} 个 SKU 未填完
          </span>
        </div>
      </div>

      <!-- 批量填充工具条 -->
      <div class="ms-sku-batch">
        <span class="ms-sku-batch-label">批量填充：</span>
        <input
          v-model="batchPrice"
          type="number"
          step="0.01"
          min="0"
          class="ms-input ms-batch-input"
          placeholder="统一价格"
        />
        <input
          v-model="batchQuantity"
          type="number"
          step="1"
          min="0"
          class="ms-input ms-batch-input"
          placeholder="统一库存"
        />
        <button type="button" class="ms-btn-batch" @click="applyBatch">应用到全部</button>
      </div>

      <div class="ms-sku-table-scroll">
        <table>
          <thead>
            <tr>
              <th class="ms-sku-th-idx">#</th>
              <th v-for="(prop, pIdx) in modelValue.propertyGroups" :key="pIdx">
                {{ prop.propertyName || `规格${pIdx+1}` }}
              </th>
              <th class="ms-sku-th-cover">封面图</th>
              <th>价格（元）</th>
              <th>库存</th>
              <th class="ms-sku-th-status">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(sku, sIdx) in modelValue.skuList" :key="sIdx" :class="{ 'ms-sku-row-incomplete': !isSkuFilled(sku) }">
              <td class="ms-sku-td-idx">{{ sIdx + 1 }}</td>
              <td v-for="(prop, pIdx) in modelValue.propertyGroups" :key="pIdx">
                <span class="ms-sku-value-chip">{{ getSkuValue(sku, pIdx) || '-' }}</span>
              </td>
              <td class="ms-sku-td-cover">
                <div class="ms-sku-cover-cell">
                  <div class="ms-sku-cover-thumb">
                    <img v-if="sku.coverImage" :src="displayUrl(sku.coverImage)" alt="" @error="onImgError($event)" />
                    <div v-else class="ms-sku-cover-placeholder">
                      <span aria-hidden="true">🖼</span>
                    </div>
                  </div>
                  <div class="ms-sku-cover-actions">
                    <button
                      type="button"
                      class="ms-btn-mini"
                      @click="$emit('upload-sku-cover', { sIdx })"
                    >{{ sku.coverImage ? '更换' : '上传' }}</button>
                    <button
                      v-if="sku.coverImage"
                      type="button"
                      class="ms-btn-mini ms-btn-danger-mini"
                      @click="sku.coverImage = ''"
                    >清除</button>
                  </div>
                </div>
              </td>
              <td>
                <input
                  v-model="sku.price"
                  type="number"
                  step="0.01"
                  min="0"
                  class="ms-input ms-sku-input"
                  :class="{ 'ms-sku-input-error': !isPriceValid(sku.price) }"
                  placeholder="0.00"
                />
              </td>
              <td>
                <input
                  v-model="sku.quantity"
                  type="number"
                  step="1"
                  min="0"
                  class="ms-input ms-sku-input"
                  :class="{ 'ms-sku-input-error': !isQuantityValid(sku.quantity) }"
                  placeholder="0"
                />
              </td>
              <td class="ms-sku-td-status">
                <span v-if="isSkuFilled(sku)" class="ms-sku-status-ok" title="已填完">✓</span>
                <span v-else class="ms-sku-status-missing" title="未填完">⚠</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 空状态：未生成 SKU -->
    <div v-else-if="hasValidProperty" class="ms-sku-empty">
      <span aria-hidden="true">📋</span>
      <span>已添加规格，待填写有效规格值后自动生成 SKU</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
    // { propertyGroups: [{propertyName, supportImage, propertyValues: [{propertyValue, propertyValueImg}]}], skuList: [{price, quantity, propertyList, coverImage, skuId, inventoryId}] }
  },
})

const emit = defineEmits(['upload-spec-image', 'upload-sku-cover'])

// 批量填充工具
const batchPrice = ref('')
const batchQuantity = ref('')

function applyBatch() {
  const price = batchPrice.value
  const qty = batchQuantity.value
  if (!price && !qty) return
  // 直接修改 reactive 对象的属性，触发响应式更新
  for (const sku of props.modelValue.skuList) {
    if (price !== '') sku.price = price
    if (qty !== '') sku.quantity = qty
  }
}

// ---- 规格类型操作 ----
// 注意：直接修改 props.modelValue 的属性（而非 emit 替换整个对象）
// 因为父组件 multiSpecData 是 reactive，直接修改其属性会触发响应式更新
// 如果通过 emit 替换整个对象，会导致父组件 setup 中的局部变量 multiSpecData
// 与 setup 返回的对象的 multiSpecData 属性失去同步，从而破坏响应式
function addProperty() {
  if (props.modelValue.propertyGroups.length >= 2) return
  props.modelValue.propertyGroups.push({
    propertyName: '',
    supportImage: false,
    propertyValues: [{ propertyValue: '', propertyValueImg: '' }],
  })
  // watch 会自动触发 rebuildSkus
}

function removeProperty(pIdx) {
  const prop = props.modelValue.propertyGroups[pIdx]
  const propName = prop?.propertyName || `规格 ${pIdx + 1}`
  if (!window.confirm(`确定删除规格类型「${propName}」？关联的 SKU 和规格图片将一并清理。`)) return
  props.modelValue.propertyGroups.splice(pIdx, 1)
  rebuildSkus()
}

function addValue(pIdx) {
  props.modelValue.propertyGroups[pIdx].propertyValues.push({ propertyValue: '', propertyValueImg: '' })
}

function removeValue(pIdx, vIdx) {
  const prop = props.modelValue.propertyGroups[pIdx]
  const valName = prop?.propertyValues?.[vIdx]?.propertyValue || ''
  if (valName && !window.confirm(`确定删除规格值「${valName}」？关联的 SKU 将被移除。`)) return
  props.modelValue.propertyGroups[pIdx].propertyValues.splice(vIdx, 1)
  rebuildSkus()
}

function onSupportImageChange(pIdx, checked) {
  // 单选行为：选中当前规格时，自动取消其他规格的 supportImage
  // 后端约束：最多一个规格类型 supportImage=true
  if (checked) {
    for (let i = 0; i < props.modelValue.propertyGroups.length; i++) {
      if (i !== pIdx) props.modelValue.propertyGroups[i].supportImage = false
    }
  }
  props.modelValue.propertyGroups[pIdx].supportImage = checked
}

function hasOtherSupportImage(currentIdx) {
  return props.modelValue.propertyGroups.some((g, i) => i !== currentIdx && g.supportImage)
}

// ---- SKU 笛卡尔积重建 ----
// 当规格类型或规格值变化时，重建 SKU 列表，保留已存在的价格库存
function rebuildSkus() {
  const groups = props.modelValue.propertyGroups
  const validGroups = []
  for (const g of groups) {
    const name = (g.propertyName || '').trim()
    if (!name) continue
    const values = (g.propertyValues || [])
      .map(v => typeof v === 'object' ? (v.propertyValue || '').trim() : '')
      .filter(v => v)
    if (values.length === 0) continue
    validGroups.push({ propertyName: name, values })
  }

  if (validGroups.length === 0) {
    // 无规格模式：保留一个不带规格属性的 SKU（单 SKU）
    // 用户开启多规格但未添加规格类型时，仍可设置价格和库存
    // 编辑场景下保留 skuId/inventoryId/coverImage，避免重建后丢失
    const existing = props.modelValue.skuList[0]
    const newSku = {
      price: existing?.price ?? '',
      quantity: existing?.quantity ?? '',
      propertyList: [],
      skuId: existing?.skuId || '',
      inventoryId: existing?.inventoryId || '',
      coverImage: existing?.coverImage || '',
    }
    props.modelValue.skuList.splice(0, props.modelValue.skuList.length, newSku)
    return
  }

  // 笛卡尔积
  const pools = validGroups.map(g => g.values.map(v => ({ propertyText: g.propertyName, valueText: v })))
  const combos = []
  // 笛卡尔积生成（手动实现，避免引入 lodash）
  const indices = new Array(pools.length).fill(0)
  while (true) {
    const combo = indices.map((idx, i) => pools[i][idx])
    combos.push(combo)
    // 进位
    let k = pools.length - 1
    while (k >= 0) {
      indices[k]++
      if (indices[k] < pools[k].length) break
      indices[k] = 0
      k--
    }
    if (k < 0) break
  }

  // 保留旧 SKU 的价格库存（按 property_key 匹配）
  const oldSkuMap = new Map()
  for (const sku of props.modelValue.skuList) {
    const key = buildPropertyKey(sku.propertyList || [])
    oldSkuMap.set(key, sku)
  }

  const newSkuList = combos.map(combo => {
    const key = buildPropertyKey(combo)
    const old = oldSkuMap.get(key)
    return {
      price: old?.price ?? '',
      quantity: old?.quantity ?? '',
      propertyList: combo,
      // 编辑场景下保留 skuId/inventoryId/coverImage，避免重建后丢失
      skuId: old?.skuId || '',
      inventoryId: old?.inventoryId || '',
      coverImage: old?.coverImage || '',
    }
  })

  props.modelValue.skuList.splice(0, props.modelValue.skuList.length, ...newSkuList)
}

function buildPropertyKey(propertyList) {
  if (!propertyList || propertyList.length === 0) return ''
  const sorted = [...propertyList].sort((a, b) => String(a.propertyText).localeCompare(String(b.propertyText)))
  return sorted.map(p => `${p.propertyText}=${p.valueText}`).join('|')
}

// 监听规格类型/规格值变化，自动重建 SKU
// immediate: true 确保组件初始化时即为单 SKU 模式生成默认 SKU
watch(
  () => JSON.stringify(props.modelValue.propertyGroups.map(g => ({
    name: g.propertyName,
    values: g.propertyValues.map(v => typeof v === 'object' ? v.propertyValue : ''),
  }))),
  () => rebuildSkus(),
  { immediate: true },
)

// ---- SKU 表格辅助 ----
function getSkuValue(sku, pIdx) {
  const prop = props.modelValue.propertyGroups[pIdx]
  if (!prop) return ''
  const found = (sku.propertyList || []).find(p => p.propertyText === prop.propertyName)
  return found?.valueText || ''
}

function displayUrl(url) {
  const v = String(url || '').trim()
  if (!v) return ''
  if (/^data:image\//i.test(v)) return v
  if (v.startsWith('//')) return `https:${v}`
  if (v.startsWith('http://') || v.startsWith('https://')) return v
  if (v.startsWith('/uploads/')) return v
  if (v.startsWith('/')) return `https://img.alicdn.com${v}`
  return v
}

function onImgError(e) {
  // 图片加载失败时隐藏 img，露出背景
  if (e && e.target) e.target.style.display = 'none'
}

// ---- 校验辅助 ----
function isPriceValid(price) {
  if (price === '' || price === null || price === undefined) return false
  const n = parseFloat(price)
  return !isNaN(n) && n >= 0
}

function isQuantityValid(qty) {
  if (qty === '' || qty === null || qty === undefined) return false
  const n = Number(qty)
  // 必须是合法数字、非负、整数（拒绝小数如 1.5）
  return !isNaN(n) && n >= 0 && Number.isInteger(n)
}

function isSkuFilled(sku) {
  return isPriceValid(sku.price) && isQuantityValid(sku.quantity)
}

// ---- 计算属性 ----
const propertyCount = computed(() => props.modelValue.propertyGroups.length)

const hasValidProperty = computed(() => {
  return props.modelValue.propertyGroups.some(g => {
    const name = (g.propertyName || '').trim()
    if (!name) return false
    return (g.propertyValues || []).some(v => typeof v === 'object' && (v.propertyValue || '').trim())
  })
})

function validValueCount(pIdx) {
  const prop = props.modelValue.propertyGroups[pIdx]
  if (!prop) return 0
  return (prop.propertyValues || []).filter(v => typeof v === 'object' && (v.propertyValue || '').trim()).length
}

const totalStock = computed(() => {
  return props.modelValue.skuList.reduce((sum, s) => {
    const q = parseInt(s.quantity, 10)
    return sum + (isNaN(q) || q < 0 ? 0 : q)
  }, 0)
})

const minPrice = computed(() => {
  const prices = props.modelValue.skuList
    .map(s => parseFloat(s.price))
    .filter(p => !isNaN(p) && p > 0)
  if (prices.length === 0) return '0.00'
  return Math.min(...prices).toFixed(2)
})

const allSkusFilled = computed(() => {
  if (props.modelValue.skuList.length === 0) return true
  return props.modelValue.skuList.every(isSkuFilled)
})

const unfilledSkuCount = computed(() => {
  return props.modelValue.skuList.filter(s => !isSkuFilled(s)).length
})
</script>

<style scoped>
.multi-spec-editor {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
  margin-top: 12px;
  background: linear-gradient(180deg, #fafbfc 0%, #f3f4f6 100%);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

/* ---- 顶部说明卡片 ---- */
.ms-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border: 1px solid #bfdbfe;
  border-radius: 8px;
}
.ms-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ms-header-icon {
  font-size: 20px;
  line-height: 1;
}
.ms-header-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ms-title {
  font-weight: 600;
  color: #1e3a8a;
  font-size: 14px;
}
.ms-hint {
  color: #1e40af;
  font-size: 12px;
  opacity: 0.85;
}
.ms-header-stats {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.ms-stat-chip {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: #fff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
}
.ms-stat-sku {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

/* ---- 规格类型块 ---- */
.ms-prop-block {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  transition: border-color 0.18s, box-shadow 0.18s;
}
.ms-prop-block:hover {
  border-color: #cbd5e1;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
}
.ms-prop-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.ms-prop-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.ms-input {
  padding: 6px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  font-family: inherit;
}
.ms-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}
.ms-prop-name {
  width: 180px;
  font-weight: 500;
}
.ms-prop-values-count {
  font-size: 12px;
  color: #6b7280;
  padding: 2px 8px;
  background: #f3f4f6;
  border-radius: 10px;
}
.ms-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  user-select: none;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  background: #fff;
  transition: all 0.15s;
}
.ms-checkbox:hover {
  border-color: #cbd5e1;
}
.ms-checkbox-checked {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1e40af;
}
.ms-checkbox input[type="checkbox"] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.ms-checkbox-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: 1.5px solid #9ca3af;
  border-radius: 4px;
  font-size: 11px;
  color: transparent;
  background: #fff;
  transition: all 0.15s;
}
.ms-checkbox-checked .ms-checkbox-box {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #fff;
}

/* ---- 规格值列表 ---- */
.ms-values {
  padding-left: 14px;
  border-left: 2px solid #e5e7eb;
  margin-left: 12px;
  padding-top: 4px;
}
.ms-value-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.ms-value-input {
  width: 160px;
}
.ms-value-img {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ms-img-wrapper {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}
.ms-value-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.2s;
}
.ms-value-img img:hover {
  transform: scale(1.08);
}
.ms-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
  color: #9ca3af;
  font-size: 18px;
  gap: 1px;
}
.ms-img-placeholder-text {
  font-size: 9px;
}
.ms-img-actions {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.ms-btn-remove-value {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #fee2e2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0;
  transition: all 0.15s;
  flex-shrink: 0;
}
.ms-btn-remove-value:hover {
  background: #fecaca;
  transform: scale(1.08);
}

/* ---- 按钮 ---- */
.ms-btn-add {
  background: #fff;
  border: 1px dashed #93c5fd;
  color: #1e40af;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  margin-top: 6px;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ms-btn-add:hover {
  background: #eff6ff;
  border-color: #3b82f6;
  border-style: solid;
}
.ms-btn-add-prop {
  display: inline-flex;
  margin-top: 4px;
  margin-bottom: 8px;
}
.ms-prop-limit-hint {
  margin-top: 4px;
  margin-bottom: 8px;
  padding: 6px 12px;
  background: #fef3c7;
  border: 1px solid #fde68a;
  color: #92400e;
  border-radius: 6px;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.ms-btn-danger {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 5px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}
.ms-btn-danger:hover {
  background: #fee2e2;
  border-color: #fca5a5;
}
.ms-btn-mini {
  background: #dbeafe;
  border: 1px solid #bfdbfe;
  color: #1e40af;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  transition: all 0.15s;
}
.ms-btn-mini:hover {
  background: #bfdbfe;
}
.ms-btn-danger-mini {
  background: #fee2e2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}
.ms-btn-danger-mini:hover {
  background: #fecaca;
}

/* ---- 单规格模式提示 ---- */
.ms-single-mode-hint {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 10px;
  margin-bottom: 6px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border: 1px solid #6ee7b7;
  border-radius: 8px;
}
.ms-single-mode-icon {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
}
.ms-single-mode-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ms-single-mode-title {
  font-weight: 600;
  color: #065f46;
  font-size: 13px;
}
.ms-single-mode-desc {
  color: #047857;
  font-size: 12px;
  opacity: 0.9;
}

/* ---- SKU 表格 ---- */
.ms-sku-table {
  margin-top: 14px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.ms-sku-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
  color: #374151;
  flex-wrap: wrap;
  gap: 8px;
}
.ms-sku-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ms-sku-title {
  font-weight: 600;
  color: #111827;
}
.ms-sku-count {
  padding: 2px 8px;
  background: #eff6ff;
  color: #1e40af;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}
.ms-sku-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.ms-sku-stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
.ms-sku-stat-label {
  color: #6b7280;
}
.ms-sku-stat-value {
  color: #111827;
  font-weight: 600;
}
.ms-sku-stat-warn .ms-sku-stat-value {
  color: #d97706;
}
.ms-sku-stat-error {
  padding: 2px 8px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 10px;
  font-weight: 500;
}

/* 批量填充工具条 */
.ms-sku-batch {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fffbeb;
  border-bottom: 1px solid #fde68a;
  font-size: 12px;
  flex-wrap: wrap;
}
.ms-sku-batch-label {
  color: #92400e;
  font-weight: 500;
}
.ms-batch-input {
  width: 110px;
  padding: 4px 8px;
  font-size: 12px;
}
.ms-btn-batch {
  background: #f59e0b;
  border: 1px solid #d97706;
  color: #fff;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s;
}
.ms-btn-batch:hover {
  background: #d97706;
}

/* 表格滚动容器 */
.ms-sku-table-scroll {
  overflow-x: auto;
  max-height: 480px;
  overflow-y: auto;
}
.ms-sku-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.ms-sku-table th,
.ms-sku-table td {
  border-bottom: 1px solid #f3f4f6;
  padding: 8px 10px;
  text-align: left;
  vertical-align: middle;
}
.ms-sku-table th {
  background: #f9fafb;
  font-weight: 600;
  color: #374151;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid #e5e7eb;
}
.ms-sku-table tbody tr:nth-child(even) {
  background: #fafbfc;
}
.ms-sku-table tbody tr:hover {
  background: #eff6ff;
}
.ms-sku-row-incomplete {
  background: #fffbeb !important;
}
.ms-sku-row-incomplete:hover {
  background: #fef3c7 !important;
}
.ms-sku-th-idx,
.ms-sku-td-idx {
  width: 40px;
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
}
.ms-sku-th-status,
.ms-sku-td-status {
  width: 50px;
  text-align: center;
}
.ms-sku-th-cover {
  width: 130px;
}
.ms-sku-td-cover {
  width: 130px;
}
.ms-sku-cover-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ms-sku-cover-thumb {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  flex-shrink: 0;
}
.ms-sku-cover-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.ms-sku-cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
  color: #9ca3af;
  font-size: 18px;
}
.ms-sku-cover-actions {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.ms-sku-value-chip {
  display: inline-block;
  padding: 2px 8px;
  background: #f3f4f6;
  border-radius: 10px;
  font-size: 12px;
  color: #374151;
}
.ms-sku-input {
  width: 110px;
  min-width: 80px;
}
.ms-sku-input-error {
  border-color: #fca5a5;
  background: #fef2f2;
}
.ms-sku-input-error:focus {
  border-color: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.12);
}
.ms-sku-status-ok {
  color: #10b981;
  font-weight: 600;
}
.ms-sku-status-missing {
  color: #f59e0b;
  font-weight: 600;
}

/* 空状态 */
.ms-sku-empty {
  margin-top: 14px;
  padding: 16px;
  background: #fff;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 13px;
  text-align: center;
  justify-content: center;
}

/* 响应式：移动端适配 */
@media (max-width: 768px) {
  .multi-spec-editor {
    padding: 12px;
  }
  .ms-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .ms-prop-header {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .ms-prop-name,
  .ms-value-input {
    width: 100%;
  }
  .ms-btn-danger {
    margin-left: 0;
    align-self: flex-start;
  }
  .ms-sku-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .ms-sku-header-right {
    width: 100%;
    justify-content: flex-start;
  }
  .ms-sku-batch {
    flex-direction: column;
    align-items: stretch;
  }
  .ms-batch-input {
    width: 100%;
  }
}
</style>
