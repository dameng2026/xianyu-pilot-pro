<template>
  <teleport to="body">
    <transition name="m-sheet">
      <div v-if="visible" class="m-picker-mask" @click="handleMaskClick">
        <div class="m-picker-sheet" @click.stop>
          <div class="m-picker-header">
            <button class="m-picker-btn m-picker-cancel" @click="handleCancel">取消</button>
            <div class="m-picker-title">选择商品分类</div>
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
              placeholder="搜索分类名称"
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
            <button class="m-retry-btn" @click="loadCategories">重试</button>
          </div>
          <div v-else-if="searchMode" class="m-picker-body">
            <div v-if="searchResults.length" class="m-search-list">
              <div
                v-for="item in searchResults"
                :key="item.pathKey"
                class="m-search-item"
                @click="selectSearchResult(item)"
              >
                <div class="m-search-name">{{ item.leafName }}</div>
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
              <span>未找到匹配分类</span>
            </div>
          </div>
          <div v-else class="m-picker-body">
            <div class="m-cascader-cols">
              <div class="m-cascader-col">
                <div
                  v-for="cat in filteredLevel1"
                  :key="cat.id"
                  :class="['m-cascader-item', { active: level1Id === cat.id }]"
                  @click="selectLevel1(cat)"
                >
                  <span class="m-cascader-label">{{ cat.label || cat.title }}</span>
                  <MIcon
                    v-if="cat.children && cat.children.length"
                    name="chevronRight"
                    :size="14"
                    class="m-cascader-arrow"
                  />
                </div>
                <div v-if="!filteredLevel1.length" class="m-cascader-empty">暂无分类</div>
              </div>
              <div v-if="level2List.length" class="m-cascader-col">
                <div
                  v-for="cat in level2List"
                  :key="cat.id"
                  :class="['m-cascader-item', { active: level2Id === cat.id }]"
                  @click="selectLevel2(cat)"
                >
                  <span class="m-cascader-label">{{ cat.label || cat.title }}</span>
                  <MIcon
                    v-if="cat.children && cat.children.length"
                    name="chevronRight"
                    :size="14"
                    class="m-cascader-arrow"
                  />
                </div>
              </div>
              <div v-if="level3List.length" class="m-cascader-col">
                <div
                  v-for="cat in level3List"
                  :key="cat.id"
                  :class="['m-cascader-item', { active: level3Id === cat.id }]"
                  @click="selectLevel3(cat)"
                >
                  <span class="m-cascader-label">{{ cat.label || cat.title }}</span>
                  <MIcon
                    v-if="level3Id === cat.id"
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
import { fetchCategories } from '../../api/categories.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialCategoryId: { type: [String, Number], default: '' }
})
const emit = defineEmits(['close', 'select'])

const loading = ref(false)
const loadError = ref('')
const categories = ref([])
const keyword = ref('')
const level1Id = ref(null)
const level2Id = ref(null)
const level3Id = ref(null)
const level2List = ref([])
const level3List = ref([])
const pendingLeaf = ref(null)

const searchMode = computed(() => keyword.value.trim().length > 0)

const filteredLevel1 = computed(() => categories.value)

const canConfirm = computed(() => !!pendingLeaf.value)

const currentPathText = computed(() => pendingLeaf.value?.path || '')

const searchResults = computed(() => {
  if (!searchMode.value) return []
  const kw = keyword.value.trim().toLowerCase()
  const results = []

  function walk(list, parentPath, parentIds) {
    list.forEach(cat => {
      const name = cat.label || cat.title || ''
      const path = parentPath ? `${parentPath} ＞ ${name}` : name
      const ids = [...parentIds, cat.id]
      const hasChildren = cat.children && cat.children.length > 0
      if (name.toLowerCase().includes(kw)) {
        results.push({
          id: cat.id,
          leafName: name,
          path,
          pathIds: ids,
          isLeaf: !hasChildren
        })
      }
      if (hasChildren) {
        walk(cat.children, path, ids)
      }
    })
  }
  walk(categories.value, '', [])
  return results
})

function isSearchSelected(item) {
  return pendingLeaf.value && pendingLeaf.value.categoryId === item.id
}

function selectSearchResult(item) {
  pendingLeaf.value = {
    categoryId: item.id,
    categoryName: item.leafName,
    path: item.path,
    pathIds: item.pathIds
  }
  const ids = item.pathIds || []
  level1Id.value = ids[0] || null
  if (ids[0]) {
    const l1 = categories.value.find(c => c.id === ids[0])
    level2List.value = l1?.children || []
  }
  level2Id.value = ids[1] || null
  if (ids[1]) {
    const l2 = level2List.value.find(c => c.id === ids[1])
    level3List.value = l2?.children || []
  }
  level3Id.value = ids[2] || null
}

function selectLevel1(cat) {
  level1Id.value = cat.id
  level2Id.value = null
  level3Id.value = null
  level2List.value = cat.children || []
  level3List.value = []
  const name = cat.label || cat.title
  pendingLeaf.value = {
    categoryId: cat.id,
    categoryName: name,
    path: name,
    pathIds: [cat.id]
  }
}

function selectLevel2(cat) {
  level2Id.value = cat.id
  level3Id.value = null
  level3List.value = cat.children || []
  const l1 = categories.value.find(c => c.id === level1Id.value)
  const l1Name = l1?.label || l1?.title || ''
  const name = cat.label || cat.title
  pendingLeaf.value = {
    categoryId: cat.id,
    categoryName: name,
    path: `${l1Name} ＞ ${name}`,
    pathIds: [level1Id.value, cat.id]
  }
}

function selectLevel3(cat) {
  level3Id.value = cat.id
  const l1 = categories.value.find(c => c.id === level1Id.value)
  const l2 = level2List.value.find(c => c.id === level2Id.value)
  const l1Name = l1?.label || l1?.title || ''
  const l2Name = l2?.label || l2?.title || ''
  const name = cat.label || cat.title
  pendingLeaf.value = {
    categoryId: cat.id,
    categoryName: name,
    path: `${l1Name} ＞ ${l2Name} ＞ ${name}`,
    pathIds: [level1Id.value, level2Id.value, cat.id]
  }
}

function resetState() {
  level1Id.value = null
  level2Id.value = null
  level3Id.value = null
  level2List.value = []
  level3List.value = []
  pendingLeaf.value = null
  keyword.value = ''
}

function syncFromInitial() {
  if (!props.initialCategoryId || !categories.value.length) {
    resetState()
    return
  }
  const targetId = props.initialCategoryId
  function findIn(list, parentPath, parentIds) {
    for (const cat of list) {
      const name = cat.label || cat.title || ''
      const path = parentPath ? `${parentPath} ＞ ${name}` : name
      const ids = [...parentIds, cat.id]
      if (String(cat.id) === String(targetId)) {
        return { cat, path, ids }
      }
      if (cat.children && cat.children.length) {
        const found = findIn(cat.children, path, ids)
        if (found) return found
      }
    }
    return null
  }
  const found = findIn(categories.value, '', [])
  if (!found) {
    resetState()
    return
  }
  const { cat, path, ids } = found
  if (ids.length >= 1) {
    level1Id.value = ids[0]
    const l1 = categories.value.find(c => c.id === ids[0])
    level2List.value = l1?.children || []
  }
  if (ids.length >= 2) {
    level2Id.value = ids[1]
    const l2 = level2List.value.find(c => c.id === ids[1])
    level3List.value = l2?.children || []
  }
  if (ids.length >= 3) {
    level3Id.value = ids[2]
  }
  pendingLeaf.value = {
    categoryId: cat.id,
    categoryName: cat.label || cat.title,
    path,
    pathIds: ids
  }
}

async function loadCategories() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await fetchCategories()
    categories.value = res?.data || []
    if (props.visible) syncFromInitial()
  } catch (e) {
    loadError.value = e?.message || '分类加载失败'
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
    if (!categories.value.length) {
      loadCategories()
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
