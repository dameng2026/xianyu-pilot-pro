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
            <div v-else class="m-picker-state">
              <MIcon name="search" :size="36" color="#b0bacb" />
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
  background: rgba(15,25,50,0.5);
  z-index: 300;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.m-picker-sheet {
  width: 100%;
  max-width: 500px;
  max-height: 80vh;
  background: white;
  border-radius: 20px 20px 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: env(safe-area-inset-bottom);
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
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.m-picker-title {
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}

.m-picker-btn {
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 600;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 8px;
}

.m-picker-cancel {
  color: #94a3b8;
}

.m-picker-confirm {
  color: #0d6bff;
}

.m-picker-confirm:disabled {
  color: #cbd5e1;
  cursor: not-allowed;
}

.m-picker-search {
  position: relative;
  padding: 10px 16px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.m-search-icon {
  position: absolute;
  left: 28px;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
  pointer-events: none;
}

.m-search-input {
  width: 100%;
  padding: 10px 36px 10px 36px;
  background: #f5f8ff;
  border: 1px solid #edf1f7;
  border-radius: 12px;
  font-size: 14px;
  color: #15213d;
  box-sizing: border-box;
  outline: none;
  transition: border-color 0.2s;
}

.m-search-input:focus {
  border-color: #0d6bff;
  background: white;
}

.m-search-clear {
  position: absolute;
  right: 28px;
  top: 50%;
  transform: translateY(-50%);
  width: 22px;
  height: 22px;
  border: none;
  background: #cbd5e1;
  color: white;
  border-radius: 50%;
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
  border-right: 1px solid #f1f5f9;
  overflow-y: auto;
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
  padding: 14px 12px;
  font-size: 14px;
  color: #475569;
  cursor: pointer;
  border-bottom: 1px solid #f5f8fc;
  position: relative;
  transition: background 0.15s;
}

.m-cascader-item:active {
  background: #f1f5f9;
}

.m-cascader-item.active {
  background: linear-gradient(90deg, #e8f1ff 0%, #f5f9ff 100%);
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
  background: linear-gradient(180deg, #0d6bff, #3b9bff);
  border-radius: 0 3px 3px 0;
}

.m-cascader-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-cascader-arrow {
  color: #cbd5e1;
  flex-shrink: 0;
  margin-left: 6px;
}

.m-cascader-item.active .m-cascader-arrow {
  color: #0d6bff;
}

.m-cascader-check {
  color: #0d6bff;
  flex-shrink: 0;
  margin-left: 6px;
}

.m-picker-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 20px;
  color: #8c98ae;
  font-size: 14px;
}

.m-picker-error {
  color: #ff4757;
}

.m-picker-spinner {
  width: 28px;
  height: 28px;
  border: 2.5px solid #e7edf7;
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: m-picker-spin 0.8s linear infinite;
}

@keyframes m-picker-spin {
  to { transform: rotate(360deg); }
}

.m-retry-btn {
  margin-top: 6px;
  padding: 6px 18px;
  background: linear-gradient(135deg, #0d6bff, #3b9bff);
  color: white;
  border: none;
  border-radius: 100px;
  font-size: 13px;
  font-weight: 600;
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
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid #f5f8fc;
  cursor: pointer;
  transition: background 0.15s;
}

.m-search-item:active {
  background: #f1f5f9;
}

.m-search-name {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  flex-shrink: 0;
}

.m-search-path {
  flex: 1;
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-search-check {
  color: #0d6bff;
  flex-shrink: 0;
}

.m-picker-footer {
  flex-shrink: 0;
  padding: 10px 16px;
  background: #f5f8ff;
  border-top: 1px solid #edf1f7;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.m-current-label {
  color: #94a3b8;
}

.m-current-value {
  color: #0d6bff;
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 360px) {
  .m-cascader-item {
    padding: 12px 10px;
    font-size: 13px;
  }
}
</style>
