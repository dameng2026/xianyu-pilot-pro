<template>
  <teleport to="body">
    <transition name="m-sheet">
      <div v-if="visible" class="m-picker-mask" @click="handleMaskClick">
        <div class="m-picker-sheet" @click.stop>
          <div class="m-picker-header">
            <button class="m-picker-btn m-picker-cancel" @click="handleCancel">取消</button>
            <div class="m-picker-title">选择发货地区</div>
            <button
              class="m-picker-btn m-picker-confirm"
              :disabled="!canConfirm"
              @click="handleConfirm"
            >
              确定
            </button>
          </div>

          <div class="m-picker-search">
            <MIcon name="search" :size="16" class="m-search-icon" />
            <input
              v-model="keyword"
              type="text"
              class="m-search-input"
              placeholder="搜索省/市/区"
            />
            <button v-if="keyword" class="m-search-clear" @click="keyword = ''">
              <MIcon name="x" :size="14" />
            </button>
          </div>

          <div v-if="loading" class="m-picker-state">
            <div class="m-picker-spinner"></div>
            <span>加载中...</span>
          </div>
          <div v-else-if="loadError" class="m-picker-state m-picker-error">
            <span>{{ loadError }}</span>
            <button class="m-retry-btn" @click="loadAddressTree">重试</button>
          </div>
          <div v-else-if="searchMode" class="m-picker-body">
            <div v-if="searchResults.length" class="m-search-list">
              <div
                v-for="item in searchResults"
                :key="item.pathKey"
                class="m-search-item"
                @click="selectSearchResult(item)"
              >
                <div class="m-search-name">{{ item.districtName }}</div>
                <div class="m-search-path">{{ item.path }}</div>
                <MIcon
                  v-if="isSearchSelected(item)"
                  name="check"
                  :size="18"
                  class="m-search-check"
                />
              </div>
            </div>
            <div v-else class="m-picker-state m-picker-empty">
              <MIcon name="search" :size="36" class="m-empty-icon" />
              <span>未找到匹配地区</span>
            </div>
          </div>
          <div v-else class="m-picker-body">
            <div class="m-cascader-cols">
              <div class="m-cascader-col">
                <div
                  v-for="province in addressTree"
                  :key="province.name"
                  :class="['m-cascader-item', { active: selectedProv === province.name }]"
                  @click="selectProvince(province)"
                >
                  <span class="m-cascader-label">{{ province.name }}</span>
                  <MIcon
                    v-if="province.cities && province.cities.length"
                    name="chevronRight"
                    :size="14"
                    class="m-cascader-arrow"
                  />
                </div>
                <div v-if="!addressTree.length" class="m-cascader-empty">暂无地址数据</div>
              </div>
              <div v-if="cityList.length" class="m-cascader-col">
                <div
                  v-for="city in cityList"
                  :key="city.name"
                  :class="['m-cascader-item', { active: selectedCity === city.name }]"
                  @click="selectCity(city)"
                >
                  <span class="m-cascader-label">{{ city.name }}</span>
                  <MIcon
                    v-if="city.districts && city.districts.length"
                    name="chevronRight"
                    :size="14"
                    class="m-cascader-arrow"
                  />
                </div>
              </div>
              <div v-if="districtList.length" class="m-cascader-col">
                <div
                  v-for="district in districtList"
                  :key="district.adcode || district.name"
                  :class="['m-cascader-item', { active: selectedDistrict === district.name }]"
                  @click="selectDistrict(district)"
                >
                  <span class="m-cascader-label">{{ district.name }}</span>
                  <MIcon
                    v-if="selectedDistrict === district.name"
                    name="check"
                    :size="14"
                    class="m-cascader-check"
                  />
                </div>
              </div>
            </div>
          </div>

          <div v-if="currentPathText && !searchMode" class="m-picker-footer">
            <span class="m-current-label">当前选择：</span>
            <span class="m-current-value">{{ currentPathText }}</span>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import MIcon from '../MIcon.vue'
import { addressDictTree } from '../../api/misc.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialAddress: { type: Object, default: null }
})
const emit = defineEmits(['close', 'select'])

const loading = ref(false)
const loadError = ref('')
const addressTree = ref([])
const keyword = ref('')
const selectedProv = ref('')
const selectedCity = ref('')
const selectedDistrict = ref('')
const pendingLeaf = ref(null)

const searchMode = computed(() => keyword.value.trim().length > 0)

const cityList = computed(() => {
  const province = addressTree.value.find(item => item.name === selectedProv.value)
  return province?.cities || []
})

const districtList = computed(() => {
  const city = cityList.value.find(item => item.name === selectedCity.value)
  return city?.districts || []
})

const canConfirm = computed(() => !!pendingLeaf.value)

const currentPathText = computed(() => {
  if (!pendingLeaf.value) return ''
  const { province, city, district } = pendingLeaf.value
  return [province, city, district].filter(Boolean).join(' ')
})

const searchResults = computed(() => {
  if (!searchMode.value) return []
  const kw = keyword.value.trim().toLowerCase()
  const results = []
  addressTree.value.forEach(province => {
    const provName = province.name || ''
    const hasProvMatch = provName.toLowerCase().includes(kw)
    ;(province.cities || []).forEach(city => {
      const cityName = city.name || ''
      const hasCityMatch = cityName.toLowerCase().includes(kw)
      ;(city.districts || []).forEach(district => {
        const districtName = district.name || ''
        const hasDistrictMatch = districtName.toLowerCase().includes(kw)
        if (hasProvMatch || hasCityMatch || hasDistrictMatch) {
          results.push({
            province: provName,
            city: cityName,
            district: districtName,
            districtName: districtName,
            path: `${provName} ${cityName} ${districtName}`,
            pathKey: `${provName}-${cityName}-${districtName}`,
            divisionId: district.divisionId || district.adcode || '',
            gps: district.gps || '',
            poiId: district.poiId || '',
            poiName: district.poiName || districtName
          })
        }
      })
    })
  })
  return results.slice(0, 100)
})

function isSearchSelected(item) {
  if (!pendingLeaf.value) return false
  return (
    pendingLeaf.value.province === item.province &&
    pendingLeaf.value.city === item.city &&
    pendingLeaf.value.district === item.district
  )
}

function selectSearchResult(item) {
  selectedProv.value = item.province
  selectedCity.value = item.city
  selectedDistrict.value = item.district
  pendingLeaf.value = {
    province: item.province,
    city: item.city,
    district: item.district,
    fullText: item.path,
    divisionId: item.divisionId,
    gps: item.gps,
    poiId: item.poiId,
    poiName: item.poiName
  }
}

function selectProvince(province) {
  selectedProv.value = province.name
  selectedCity.value = ''
  selectedDistrict.value = ''
  pendingLeaf.value = null
}

function selectCity(city) {
  selectedCity.value = city.name
  selectedDistrict.value = ''
  pendingLeaf.value = null
}

function selectDistrict(district) {
  selectedDistrict.value = district.name
  const parts = [selectedProv.value, selectedCity.value, district.name].filter(Boolean)
  pendingLeaf.value = {
    province: selectedProv.value,
    city: selectedCity.value,
    district: district.name,
    fullText: parts.join(' '),
    divisionId: district.divisionId || district.adcode || '',
    gps: district.gps || '',
    poiId: district.poiId || '',
    poiName: district.poiName || district.name
  }
}

function resetState() {
  selectedProv.value = ''
  selectedCity.value = ''
  selectedDistrict.value = ''
  pendingLeaf.value = null
  keyword.value = ''
}

function syncFromInitial() {
  resetState()
  if (!props.initialAddress || !addressTree.value.length) return
  const init = props.initialAddress
  const provName = init.prov || init.province || init.addressProv || ''
  const cityName = init.city || init.addressCity || ''
  const districtName = init.area || init.district || init.addressArea || ''
  const province = addressTree.value.find(p => p.name === provName)
  if (!province) return
  selectedProv.value = province.name
  const city = (province.cities || []).find(c => c.name === cityName)
  if (!city) return
  selectedCity.value = city.name
  const district = (city.districts || []).find(d =>
    d.name === districtName && (!init.divisionId || String(d.divisionId || d.adcode || '') === String(init.divisionId))
  )
  if (!district) return
  selectedDistrict.value = district.name
  selectDistrict(district)
}

async function loadAddressTree() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await addressDictTree()
    const provinces = response?.data?.provinces
    if (!Array.isArray(provinces)) throw new Error('地址字典响应格式异常')
    addressTree.value = provinces
    if (!addressTree.value.length) {
      loadError.value = '地址数据当前为空，请联系管理员初始化'
    } else if (props.visible) {
      syncFromInitial()
    }
  } catch (e) {
    loadError.value = e?.message || '地址数据加载失败'
  } finally {
    loading.value = false
  }
}

function handleMaskClick() {
  handleCancel()
}

function handleCancel() {
  emit('close')
}

function handleConfirm() {
  if (!pendingLeaf.value) return
  emit('select', { ...pendingLeaf.value })
  emit('close')
}

watch(() => props.visible, (val) => {
  if (val) {
    if (!addressTree.value.length) {
      loadAddressTree()
    } else {
      syncFromInitial()
    }
  } else {
    keyword.value = ''
  }
})
</script>

<style scoped>
.m-picker-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-modal);
  z-index: 300;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.m-picker-sheet {
  width: 100%;
  max-width: 500px;
  max-height: 80vh;
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: env(safe-area-inset-bottom);
  box-shadow: var(--m-shadow-xs);
}

.m-sheet-enter-active,
.m-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.m-sheet-enter-active .m-picker-sheet,
.m-sheet-leave-active .m-picker-sheet {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.m-sheet-enter-from,
.m-sheet-leave-to {
  opacity: 0;
}
.m-sheet-enter-from .m-picker-sheet,
.m-sheet-leave-to .m-picker-sheet {
  transform: translateY(100%);
}

.m-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
  flex-shrink: 0;
}

.m-picker-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}

.m-picker-btn {
  border: none;
  background: transparent;
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-2) var(--m-space-3);
  cursor: pointer;
  border-radius: var(--m-radius-lg);
}

.m-picker-cancel {
  color: var(--m-color-text-tertiary);
}

.m-picker-confirm {
  color: var(--m-color-primary);
}

.m-picker-confirm:disabled {
  color: var(--m-color-text-disabled);
  cursor: not-allowed;
}

.m-picker-search {
  position: relative;
  padding: var(--m-space-3) var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
  flex-shrink: 0;
}

.m-search-icon {
  position: absolute;
  left: 28px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--m-color-text-tertiary);
  pointer-events: none;
}

.m-search-input {
  width: 100%;
  padding: var(--m-space-3) 36px var(--m-space-3) 36px;
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  box-sizing: border-box;
  outline: none;
  transition: border-color 0.2s;
}

.m-search-input:focus {
  border-color: var(--m-color-primary);
  background: var(--m-color-bg-card);
}

.m-search-clear {
  position: absolute;
  right: 28px;
  top: 50%;
  transform: translateY(-50%);
  width: 22px;
  height: 22px;
  border: none;
  background: var(--m-color-text-disabled);
  color: var(--m-color-text-inverse);
  border-radius: var(--m-radius-circle);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.m-picker-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.m-cascader-cols {
  display: flex;
  flex: 1;
  max-height: 50vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.m-cascader-col {
  flex: 1;
  min-width: 0;
  border-right: 1px solid var(--m-color-border-light);
  overflow-y: auto;
}

.m-cascader-col:last-child {
  border-right: none;
}

.m-cascader-empty {
  padding: var(--m-space-6) var(--m-space-3);
  text-align: center;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
}

.m-cascader-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  border-bottom: 1px solid var(--m-color-border-light);
  position: relative;
  transition: background 0.15s;
}

.m-cascader-item:active {
  background: var(--m-color-bg-hover);
}

.m-cascader-item.active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

.m-cascader-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: var(--m-space-2);
  bottom: var(--m-space-2);
  width: 3px;
  background: var(--m-color-primary);
  border-radius: 0 var(--m-radius-sm) var(--m-radius-sm) 0;
}

.m-cascader-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-cascader-arrow {
  color: var(--m-color-text-disabled);
  flex-shrink: 0;
  margin-left: var(--m-space-2);
}

.m-cascader-item.active .m-cascader-arrow {
  color: var(--m-color-primary);
}

.m-cascader-check {
  color: var(--m-color-primary);
  flex-shrink: 0;
  margin-left: var(--m-space-2);
}

.m-picker-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-3);
  padding: var(--m-space-12) var(--m-space-5);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body);
}

.m-picker-empty .m-empty-icon {
  color: var(--m-color-text-disabled);
}

.m-picker-error {
  color: var(--m-color-danger);
}

.m-picker-spinner {
  width: 28px;
  height: 28px;
  border: 2.5px solid var(--m-color-border);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-picker-spin 0.8s linear infinite;
}

@keyframes m-picker-spin {
  to { transform: rotate(360deg); }
}

.m-retry-btn {
  margin-top: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-5);
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}

.m-search-list {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  max-height: 50vh;
}

.m-search-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
  cursor: pointer;
  transition: background 0.15s;
}

.m-search-item:active {
  background: var(--m-color-bg-hover);
}

.m-search-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  flex-shrink: 0;
}

.m-search-path {
  flex: 1;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-search-check {
  color: var(--m-color-primary);
  flex-shrink: 0;
}

.m-picker-footer {
  flex-shrink: 0;
  padding: var(--m-space-3) var(--m-space-4);
  background: var(--m-color-bg-subtle);
  border-top: 1px solid var(--m-color-border-light);
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-body-sm);
}

.m-current-label {
  color: var(--m-color-text-tertiary);
}

.m-current-value {
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 360px) {
  .m-cascader-item {
    padding: var(--m-space-3) var(--m-space-2);
    font-size: var(--m-font-size-body-sm);
  }
}
</style>
