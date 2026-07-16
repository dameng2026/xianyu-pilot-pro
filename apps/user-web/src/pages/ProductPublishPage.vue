<template>
  <div class="publish-layout">
    <div>
      <div v-if="error" class="global-notice error">{{ error }}</div>
      <div v-if="accountLoadError" class="global-notice error">闲鱼账号列表加载失败：{{ accountLoadError }}</div>
      <div v-if="categoryLoadError" class="global-notice error">商品分类加载失败：{{ categoryLoadError }}</div>
      <div v-if="aiCategoryStatusError" class="global-notice error">AI 分类状态不可用：{{ aiCategoryStatusError }}</div>
      <div v-if="success" class="global-notice success">{{ success }}</div>

      <div class="draft-toolbar">
        <span class="draft-tip">📝 草稿会自动保存本页已输入内容，仅保留上一次未发布的草稿</span>
        <button type="button" class="clear-draft-btn" @click="clearAllData">清空数据</button>
      </div>

      <CardPanel title="宝贝基础信息">
        <div class="form-grid">
          <div class="form-row">
            <label>闲鱼账号</label>
            <select v-model="form.accountId" :disabled="!accountAvailable">
              <option value="">{{ accountAvailable ? '请选择账号' : '账号列表不可用' }}</option>
              <option v-for="a in accounts" :key="a.id" :value="a.id">{{ accountName(a) }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>宝贝标题</label>
            <input v-model="form.title" maxlength="30" placeholder="请填写宝贝标题，建议包含品牌、规格、成色等关键信息">
            <span class="char-count">{{ form.title.length }}/30</span>
          </div>
          <div class="form-row">
            <label>宝贝描述</label>
            <textarea v-model="form.description" rows="4" placeholder="请详细描述宝贝的成色、功能、使用感受等信息..."></textarea>
            <div class="chips">
              <span class="chip" :class="{ disabled: aiDescLoading }" @click="!aiDescLoading && aiDesc()">{{ aiDescLoading ? 'AI 生成中...' : 'AI 生成描述' }}</span>
              <span class="chip" @click="insertPhrase">插入常用语</span>
            </div>
          </div>
        </div>

        <!-- 图片上传区域 -->
        <div style="margin-top:18px">
          <b>宝贝图片（{{ form.imageUrls.length }}/10 张，拖拽可调整顺序）</b>
          <div class="image-strip" style="margin-top:12px">
            <div
              v-for="(img, idx) in form.imageUrls"
              :key="idx"
              class="img-card"
              draggable="true"
              @dragstart="onDragStart(idx, $event)"
              @dragover.prevent="onDragOver(idx, $event)"
              @drop="onDrop(idx, $event)"
            >
              <img :src="displayImageUrl(img)" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:10px">
              <div class="img-remove" @click="removeImage(idx)">×</div>
            </div>
            <div
              v-if="form.imageUrls.length < 10"
              class="img-card add-card"
              @click="triggerUpload"
            >
              <span style="font-size:28px;color:#999">＋</span>
              <span style="font-size:12px;color:#999;margin-top:4px">上传图片</span>
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
        </div>
      </CardPanel>

      <CardPanel title="商品分类" style="margin-top:16px">
        <div class="category-selector">
          <div class="auto-category-hint">
            <span class="hint-icon">💡</span>
            <span>上传封面图之后自动获取分类</span>
            <span v-if="autoCategoryLoading" class="auto-category-spinner">检测中...</span>
          </div>
          <div v-if="autoCategoryMessage" :class="['auto-category-msg', autoCategoryMsgType]">
            {{ autoCategoryMessage }}
          </div>
          <div v-if="autoCategoryCandidates.length" class="auto-category-candidates">
            <span class="candidates-label">推荐分类：</span>
            <button
              v-for="(cat, idx) in autoCategoryCandidates"
              :key="cat.catId || idx"
              type="button"
              :class="['candidate-btn', { active: autoSelectedCatId === (cat.catId || cat.catName) }]"
              @click="applyAutoCategory(cat)"
            >
              {{ cat.catName || cat.catName }}
              <small v-if="cat.score">({{ (cat.score * 100).toFixed(1) }}%)</small>
            </button>
          </div>
          <div class="category-tools">
            <input v-model="categoryKeyword" class="category-search" placeholder="搜索分类，如 手机 / 图书 / 家居" />
            <button v-if="aiCategoryStatus.configured" type="button" class="category-ai-btn" :disabled="aiCategoryLoading || !form.title.trim()" @click="autoSelectCategory">{{ aiCategoryLoading ? 'AI选择中...' : 'AI自动选择' }}</button>
            <button v-if="categoryKeyword" type="button" class="category-clear" @click="categoryKeyword = ''">清空</button>
          </div>
          <div v-if="categoryKeyword" class="category-search-results">
            <div
              v-for="item in categorySearchResults"
              :key="item.pathIds.join('-')"
              class="category-result"
              @click="selectCategoryByPath(item)"
            >
              <strong>{{ item.name }}</strong>
              <span>{{ item.path }}</span>
            </div>
            <div v-if="!categorySearchResults.length" class="category-result muted">未找到匹配分类</div>
          </div>
          <div v-if="favoriteCategories.length" class="recent-categories favorite-categories">
            <span>收藏分类：</span>
            <button v-for="item in favoriteCategories" :key="item.path" type="button" @click="selectCategoryByPath(item)">{{ item.name }}</button>
          </div>
          <div v-if="recentCategories.length" class="recent-categories">
            <span>最近使用：</span>
            <button v-for="item in recentCategories" :key="item.path" type="button" @click="selectCategoryByPath(item)">{{ item.name }}</button>
            <button type="button" class="category-link" @click="clearRecentCategories">清除</button>
          </div>
          <div v-if="selectedCategoryPath" class="category-actions">
            <button type="button" @click="toggleFavoriteCategory">{{ isFavoriteCategory ? '取消收藏当前分类' : '收藏当前分类' }}</button>
          </div>
          <div class="cascader-levels">
            <div class="cascader-col">
              <div v-if="categoriesLoading" class="cascader-item muted">分类加载中...</div>
              <div v-else-if="categoryLoadError" class="cascader-item muted">分类加载失败，请刷新页面重试</div>
              <div v-else-if="!categories.length" class="cascader-item muted">暂无分类</div>
              <div
                v-for="cat in filteredCategories"
                :key="cat.id"
                :class="['cascader-item', { active: level1Id === cat.id }]"
                @click="selectLevel1(cat)"
              >
{{ cat.label || cat.title }}
</div>
            </div>
            <div v-if="level2List.length" class="cascader-col">
              <div
                v-for="cat in level2List"
                :key="cat.id"
                :class="['cascader-item', { active: level2Id === cat.id }]"
                @click="selectLevel2(cat)"
              >
{{ cat.label || cat.title }}
</div>
            </div>
            <div v-if="level3List.length" class="cascader-col">
              <div
                v-for="cat in level3List"
                :key="cat.id"
                :class="['cascader-item', { active: level3Id === cat.id }]"
                @click="selectLevel3(cat)"
              >
{{ cat.label || cat.title }}
</div>
            </div>
          </div>
          <p class="subtle" style="margin-top:8px">
            已选分类：{{ selectedCategoryPath || '请选择分类' }}
            <span v-if="aiCategoryMessage" class="ai-category-tip">{{ aiCategoryMessage }}</span>
          </p>
        </div>
      </CardPanel>

      <CardPanel title="商品位置" style="margin-top:16px">
        <PublishAddressCascader v-model="selectedAddress" />
      </CardPanel>

      <CardPanel title="商品价格与规格" style="margin-top:16px">
        <div class="form-grid">
          <div class="form-row">
            <label>售价（元）</label>
            <input v-model="form.price" type="number" step="0.01" min="0" placeholder="0.00">
          </div>
          <div class="form-row">
            <label>库存</label>
            <input v-model="form.stock" type="number" placeholder="1">
          </div>
        </div>
      </CardPanel>

      <CardPanel title="发货设置" style="margin-top:16px">
        <div class="shipping-grid">
          <div class="shipping-item">
            <span>包邮</span>
            <ToggleSwitch :on="shippingMode === 'free'" @click="setShipping('free')" />
          </div>
          <div class="shipping-item">
            <span>一口价 / 运费</span>
            <ToggleSwitch :on="shippingMode === 'fixed'" @click="setShipping('fixed')" />
          </div>
          <div class="shipping-item">
            <span>无需邮寄</span>
            <ToggleSwitch :on="shippingMode === 'none'" @click="setShipping('none')" />
          </div>
          <div class="shipping-item">
            <span>支持自提</span>
            <ToggleSwitch :on="form.supportSelfPick" @click="form.supportSelfPick = !form.supportSelfPick" />
          </div>
        </div>
      </CardPanel>
      <div style="height:90px"></div>
    </div>

    <div>
      <CardPanel title="商品预览">
        <div class="product-cell">
          <div class="product-thumb" style="width:130px;height:98px">
            <img v-if="displayCoverImage" :src="displayCoverImage" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:10px">
            <div v-else style="width:100%;height:100%;background:#f0f0f0;border-radius:10px;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:12px">暂无图片</div>
          </div>
          <div>
            <h3 style="margin:0 0 8px">{{ form.title || '商品标题' }}</h3>
            <b style="color:#ef4444;font-size:22px">¥{{ displayPrice }}</b>
          </div>
        </div>
      </CardPanel>
      <CardPanel title="发布摘要" style="margin-top:16px">
        <div class="option-line"><span>闲鱼账号</span><b>{{ selectedAccount || '未选择' }}</b></div>
        <div class="option-line"><span>商品分类</span><b>{{ selectedCategoryPath || '未选择' }}</b></div>
        <div class="option-line"><span>商品位置</span><b>{{ selectedPoi?.name || '未选择' }}</b></div>
        <div class="option-line"><span>总库存</span><b>{{ totalStock }}件</b></div>
        <div class="option-line"><span>发货方式</span><b>{{ shippingLabel }}</b></div>
      </CardPanel>
      <CardPanel title="发布检查" style="margin-top:16px">
        <div v-for="i in checks" :key="i.text" class="option-line">
          <span><i :class="['dot', i.ok ? '' : 'orange']"></i>{{ i.text }}</span>
          <b :style="{color:i.ok?'var(--green)':'#f59e0b'}">{{ i.ok ? '通过' : '待完善' }}</b>
        </div>
      </CardPanel>
    </div>

    <div class="bottom-actions">
      <AppButton @click="handleCancel">取消</AppButton>
      <AppButton type="primary" :loading="submitting" :disabled="!initializationAvailable" @click="submit">{{ initializationAvailable ? '立即发布' : '发布服务状态不可用' }}</AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import PublishAddressCascader from '../components/PublishAddressCascader.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { createGoods } from '../api/goods.js'
import { publishItem, autoCategory } from '../api/items.js'
import { uploadImage } from '../api/misc.js'
import { accountName } from '../utils/format.js'
import { accountAuthUsable, pickPreferredAccount } from '../utils/accountAuth.js'
import { confirmAction } from '../utils/confirmAction.js'
import { getAiProviderStatus, suggestCategoryByAi } from '../api/aiProvider.js'
import { fetchCategories } from '../api/categories.js'
import { aiRewriteGoods } from '../api/workflow.js'
import { isPublishAddressComplete, normalizePublishAddress } from '../utils/publishAddress.js'
import { imageUploadValidationMessage } from '../utils/imageUploadPolicy.js'
import { createRequestGate } from '../utils/requestLifecycle.js'
import { loadPublishDraft, savePublishDraft, clearPublishDraft } from '../utils/publishDraft.js'
import { setNavigationGuard, clearNavigationGuard } from '../utils/navigationGuard.js'
import { promptDraftChoice } from '../composables/draftGuardState.js'

const emit = defineEmits(['navigate'])
const accounts = ref([])
const accountAvailable = ref(false)
const accountLoadError = ref('')
const error = ref('')
const success = ref('')
const submitting = ref(false)
const fileInput = ref(null)
const dragIndex = ref(-1)
const categoryRefreshGate = createRequestGate()

// ---- 分类级联 ----
const categories = ref([])
const categoriesLoading = ref(false)
const categoriesAvailable = ref(false)
const categoryLoadError = ref('')
const level1Id = ref(null)
const level2Id = ref(null)
const level3Id = ref(null)
const level2List = ref([])
const level3List = ref([])
const categoryKeyword = ref('')
const recentCategories = ref([])
const favoriteCategories = ref([])
const selectedCategoryPath = ref('')
const selectedCategoryName = ref('')
const aiCategoryStatus = ref({ configured: null })
const aiCategoryStatusError = ref('')
const aiCategoryLoading = ref(false)
const aiCategoryMessage = ref('')

// ---- 自动分类（闲鱼接口） ----
const autoCategoryLoading = ref(false)
const autoCategoryMessage = ref('')
const autoCategoryMsgType = ref('info')
const autoCategoryCandidates = ref([])
const autoSelectedCatId = ref('')
const autoCategorySource = ref(null) // 'xianyu_auto' | 'local_category' | null
const userManuallySelectedCategory = ref(false) // 用户是否手动改过分类

function selectLevel1(cat) {
  userManuallySelectedCategory.value = true
  level1Id.value = cat.id
  level2Id.value = null
  level3Id.value = null
  level2List.value = cat.children || []
  level3List.value = []
  selectedCategoryName.value = cat.label || cat.title
  selectedCategoryPath.value = cat.label || cat.title
  if (!level2List.value.length) rememberCategory({ name: selectedCategoryName.value, path: selectedCategoryPath.value, pathIds: [cat.id] })
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
  if (!level3List.value.length) rememberCategory({ name: selectedCategoryName.value, path, pathIds: [l1?.id, cat.id].filter(Boolean) })
}

function selectLevel3(cat) {
  userManuallySelectedCategory.value = true
  level3Id.value = cat.id
  const l1 = categories.value.find(c => c.id === level1Id.value)
  const l2 = level2List.value.find(c => c.id === level2Id.value)
  const path = (l1?.label || l1?.title) + ' ＞ ' + (l2?.label || l2?.title) + ' ＞ ' + (cat.label || cat.title)
  selectedCategoryName.value = cat.label || cat.title
  selectedCategoryPath.value = path
  rememberCategory({ name: selectedCategoryName.value, path, pathIds: [l1?.id, l2?.id, cat.id].filter(Boolean) })
}


const filteredCategories = computed(() => {
  if (!categoryKeyword.value.trim()) return categories.value
  const kw = categoryKeyword.value.trim().toLowerCase()
  return categories.value.filter(cat => String(cat.label || cat.title || '').toLowerCase().includes(kw) || (cat.children || []).some(child => String(child.label || child.title || '').toLowerCase().includes(kw)))
})

const isFavoriteCategory = computed(() => favoriteCategories.value.some(item => item.path === selectedCategoryPath.value))

const categorySearchResults = computed(() => {
  const kw = categoryKeyword.value.trim().toLowerCase()
  if (!kw) return []
  const res = []
  const walk = (nodes, parents = [], parentIds = []) => {
    for (const node of nodes || []) {
      const name = node.label || node.title || ''
      const pathParts = [...parents, name]
      const pathIds = [...parentIds, node.id]
      if (String(name).toLowerCase().includes(kw)) {
        res.push({ name, path: pathParts.join(' ＞ '), pathIds })
      }
      if (res.length < 20) walk(node.children || [], pathParts, pathIds)
      if (res.length >= 20) return
    }
  }
  walk(categories.value)
  return res.slice(0, 20)
})

function flatCategoryOptions(limit = 5000) {
  const res = []
  const walk = (nodes, parents = [], parentIds = []) => {
    for (const node of nodes || []) {
      if (res.length >= limit) return
      const name = node.label || node.title || ''
      const pathParts = [...parents, name]
      const pathIds = [...parentIds, node.id]
      const children = node.children || []
      if (!children.length) {
        res.push({ id: node.id, name, path: pathParts.join(' ＞ '), pathIds })
      } else {
        walk(children, pathParts, pathIds)
      }
    }
  }
  walk(categories.value)
  return res
}

function findCategoryOption(category) {
  if (!category) return null
  const options = flatCategoryOptions(5000)
  const id = String(category.id || category.categoryId || '')
  const path = String(category.path || category.categoryPath || '')
  const name = String(category.name || category.categoryName || '')
  return options.find(item =>
    (id && String(item.id) === id) ||
    (path && item.path === path) ||
    (name && (item.name === name || item.path.endsWith(name)))
  ) || null
}

async function loadAiCategoryStatus() {
  aiCategoryStatusError.value = ''
  try {
    const res = await getAiProviderStatus()
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data) || typeof res.data.configured !== 'boolean') throw new Error('AI 分类状态响应格式异常')
    aiCategoryStatus.value = res.data
  } catch (e) {
    aiCategoryStatus.value = { configured: null }
    aiCategoryStatusError.value = e?.message || 'AI 分类状态加载失败'
  }
}

async function autoSelectCategory() {
  if (!aiCategoryStatus.value.configured) return
  if (!form.title.trim()) { error.value = '请先填写宝贝标题，AI才能判断分类'; return }
  const options = flatCategoryOptions(5000)
  if (!options.length) { error.value = '分类数据尚未加载完成'; return }
  aiCategoryLoading.value = true
  aiCategoryMessage.value = ''
  error.value = ''
  try {
    const res = await suggestCategoryByAi({
      title: form.title,
      description: form.description,
      categories: options,
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.enabled !== 'boolean' || typeof data.matched !== 'boolean') {
      throw new Error('AI 分类响应格式异常')
    }
    if (data.enabled === false) {
      aiCategoryStatus.value = { configured: false }
      return
    }
    if (!data.matched) {
      error.value = data.error || data.message || 'AI未能匹配到合适分类，请手动选择'
      return
    }
    if (!data.category || typeof data.category !== 'object' || Array.isArray(data.category)) throw new Error('AI 分类结果缺少有效分类')
    const matched = findCategoryOption(data.category)
    if (!matched) throw new Error('AI 返回的分类不在当前可用分类树中')
    selectCategoryByPath(matched)
    aiCategoryMessage.value = data.reason ? `AI已选择：${data.reason}` : 'AI已自动选择分类'
  } catch (e) {
    error.value = e.message || 'AI自动选择分类失败'
  } finally {
    aiCategoryLoading.value = false
  }
}

// ---- 自动分类（上传封面图后触发） ----
async function triggerAutoCategory() {
  if (!form.accountId) {
    autoCategoryMessage.value = '请先选择闲鱼账号'
    autoCategoryMsgType.value = 'warn'
    return
  }
  if (!form.imageUrls.length) {
    return
  }
  // 如果用户已手动选择分类，不要覆盖
  if (userManuallySelectedCategory.value) {
    autoCategoryMessage.value = '已手动选择分类，重新上传封面图可再次自动识别'
    autoCategoryMsgType.value = 'info'
    return
  }
  const coverImageUrl = form.imageUrls[0]
  autoCategoryLoading.value = true
  autoCategoryMessage.value = '正在识别商品分类...'
  autoCategoryMsgType.value = 'info'
  autoCategoryCandidates.value = []
  autoSelectedCatId.value = ''
  try {
    const res = await autoCategory(form.accountId, {
      coverImageUrl,
      title: form.title || undefined,
      description: form.description || undefined,
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.success !== 'boolean') {
      throw new Error('封面自动分类响应格式异常')
    }
    if (data.candidates != null && !Array.isArray(data.candidates)) throw new Error('自动分类候选响应格式异常')
    if (data.success === false) {
      // 自动分类失败，如果是 cookie 问题提示重新登录
      if (data.fallbackReason === 'COOKIE_EXPIRED' || data.fallbackReason === 'COOKIE_MISSING_M_H5_TK') {
        autoCategoryMessage.value = '账号 Cookie 已失效，请重新登录后再试'
        autoCategoryMsgType.value = 'error'
      } else if (data.fallbackReason && data.fallbackReason.includes('LOW_CONFIDENCE')) {
        autoCategoryMessage.value = '封面图自动识别置信度不足，已切换到本地分类'
        autoCategoryMsgType.value = 'warn'
        // 展示能检测到的候选
        if (data.candidates && data.candidates.length) {
          autoCategoryCandidates.value = data.candidates
        }
      } else {
        const reason = data.fallbackReason ? `（${data.fallbackReason}）` : ''
        autoCategoryMessage.value = `封面图自动识别失败，请手动选择分类${reason}`
        autoCategoryMsgType.value = 'warn'
        // 展示能检测到的候选
        if (data.candidates && data.candidates.length) {
          autoCategoryCandidates.value = data.candidates
        }
      }
      autoCategorySource.value = data.source || null
      return
    }
    // 自动分类成功
    autoCategorySource.value = 'xianyu_auto'
    const selected = data.selectedCategory
    const candidates = data.candidates || []
    autoCategoryCandidates.value = candidates
    if (selected) {
      // 尝试在本地分类树中找到匹配项
      const option = findCategoryOption(selected)
      if (option) {
        selectCategoryByPath(option)
        autoSelectedCatId.value = selected.catId || selected.catName || ''
        autoCategoryMessage.value = '已根据封面图自动识别分类'
        autoCategoryMsgType.value = 'success'
      } else {
        // 未匹配到本地分类树：平台已选定分类，直接采用，避免校验空值导致无法发布
        // 候选列表仍然展示，用户可点击切换
        const matchName = String(selected.catName || selected.name || '').trim()
        if (matchName) {
          selectedCategoryName.value = matchName
          selectedCategoryPath.value = matchName
          autoSelectedCatId.value = selected.catId || selected.catName || ''
          autoCategoryMessage.value = candidates.length
            ? '已根据封面图自动识别分类，可点击下方候选切换'
            : '已根据封面图自动识别分类'
          autoCategoryMsgType.value = 'success'
        } else {
          autoCategoryMessage.value = '自动分类返回了候选结果，但当前分类树无法应用，请手动选择分类'
          autoCategoryMsgType.value = 'warn'
        }
      }
    } else if (candidates.length) {
      autoCategoryMessage.value = '已识别候选分类，请点击选择'
      autoCategoryMsgType.value = 'info'
    } else {
      autoCategoryMessage.value = '自动分类未返回可应用的分类，请手动选择'
      autoCategoryMsgType.value = 'warn'
    }
  } catch (e) {
    autoCategoryMessage.value = '自动分类请求失败：' + (e.message || '网络异常')
    autoCategoryMsgType.value = 'error'
    autoCategoryCandidates.value = []
    autoCategorySource.value = null
  } finally {
    autoCategoryLoading.value = false
    // 后台刷新分类树，让新增的分类在前端级联选择器中可见
    refreshCategoriesInBackground()
  }
}

async function refreshCategoriesInBackground() {
  const requestGeneration = categoryRefreshGate.begin()
  try {
    const res = await fetchCategories()
    if (!categoryRefreshGate.isCurrent(requestGeneration)) return
    const newTree = res?.data?.cation || []
    if (newTree.length) {
      categories.value = newTree
    }
  } catch {
    // This is a best-effort refresh; the bundled category tree remains usable.
  }
}

function applyAutoCategory(cat) {
  if (!cat) return
  userManuallySelectedCategory.value = true
  // 用候选分类的名称匹配本地分类树
  const matchName = cat.catName || cat.name || ''
  if (matchName) {
    const options = flatCategoryOptions(5000)
    const matched = options.find(item =>
      item.name === matchName || item.path.endsWith(matchName)
    )
    if (matched) {
      selectCategoryByPath(matched)
      autoSelectedCatId.value = cat.catId || cat.catName || ''
      autoCategoryMessage.value = `已选择分类：${matchName}`
      autoCategoryMsgType.value = 'success'
      return
    }
  }
  // 未匹配到本地分类树时，直接设置分类名称
  selectedCategoryName.value = matchName
  selectedCategoryPath.value = matchName
  autoSelectedCatId.value = cat.catId || cat.catName || ''
  autoCategoryMessage.value = `已选择分类：${matchName}`
  autoCategoryMsgType.value = 'success'
}

function selectCategoryByPath(item) {
  const ids = item.pathIds || []
  const l1 = categories.value.find(c => String(c.id) === String(ids[0]))
  if (!l1) return
  selectLevel1(l1)
  if (ids[1]) {
    const l2 = (l1.children || []).find(c => String(c.id) === String(ids[1]))
    if (l2) selectLevel2(l2)
    if (ids[2]) {
      const l3 = (l2?.children || []).find(c => String(c.id) === String(ids[2]))
      if (l3) selectLevel3(l3)
    }
  }
  categoryKeyword.value = ''
  rememberCategory(item)
}

function rememberCategory(item) {
  if (!item?.path) return
  const normalized = { name: item.name, path: item.path, pathIds: item.pathIds || [] }
  recentCategories.value = [normalized, ...recentCategories.value.filter(i => i.path !== normalized.path)].slice(0, 6)
  try { localStorage.setItem('xianyu_recent_categories', JSON.stringify(recentCategories.value)) } catch {
    // Browsing still works when storage is unavailable or full.
  }
}

function loadRecentCategories() {
  try {
    const list = JSON.parse(localStorage.getItem('xianyu_recent_categories') || '[]')
    recentCategories.value = Array.isArray(list) ? list.slice(0, 6) : []
  } catch {
    recentCategories.value = []
  }
  try {
    const list = JSON.parse(localStorage.getItem('xianyu_favorite_categories') || '[]')
    favoriteCategories.value = Array.isArray(list) ? list.slice(0, 12) : []
  } catch {
    favoriteCategories.value = []
  }
}

function clearRecentCategories() {
  recentCategories.value = []
  try { localStorage.removeItem('xianyu_recent_categories') } catch {
    // The in-memory list is already cleared.
  }
}

function toggleFavoriteCategory() {
  if (!selectedCategoryPath.value) return
  const item = { name: selectedCategoryName.value, path: selectedCategoryPath.value, pathIds: [level1Id.value, level2Id.value, level3Id.value].filter(Boolean) }
  if (isFavoriteCategory.value) {
    favoriteCategories.value = favoriteCategories.value.filter(i => i.path !== item.path)
  } else {
    favoriteCategories.value = [item, ...favoriteCategories.value.filter(i => i.path !== item.path)].slice(0, 12)
  }
  try { localStorage.setItem('xianyu_favorite_categories', JSON.stringify(favoriteCategories.value)) } catch {
    // Favorites remain usable for the current session.
  }
}

// ---- 表单（清除草稿，初始为空） ----
const form = reactive({
  accountId: '',
  title: '',
  description: '',
  imageUrls: [],
  price: '',
  stock: '',
  supportSelfPick: false,
})

function displayImageUrl(url) {
  const value = String(url || '').trim()
  if (!value) return ''
  if (/^data:image\//i.test(value)) return value
  if (value.startsWith('//')) return `https:${value}`
  if (value.startsWith('http://') || value.startsWith('https://')) return value
  if (value.startsWith('/uploads/')) return value
  if (value.startsWith('uploads/')) return `/${value}`
  if (value.startsWith('/')) return `https://img.alicdn.com${value}`
  return value
}

function handleCancel() {
  // 由全局导航守卫统一处理草稿询问
  emit('navigate', 'products')
}

// ---- 发货设置（互斥） ----
const shippingMode = ref('free')

function setShipping(mode) {
  shippingMode.value = mode
}
const shippingLabel = computed(() => {
  const map = { free: '包邮', fixed: '一口价 / 运费', none: '无需邮寄' }
  return map[shippingMode.value] || '包邮'
})

// ---- 地址字典（省市区三级联动，本地数据）----
const selectedAddress = ref(null)

// ---- 请求封装 ----

const selectedAccount = computed(() => {
  const account = accounts.value.find(a => String(a.id) === String(form.accountId))
  return account ? accountName(account) : ''
})
const initializationAvailable = computed(() => accountAvailable.value && categoriesAvailable.value)
const displayCoverImage = computed(() => displayImageUrl(form.imageUrls[0] || ''))
const displayPrice = computed(() => form.price || '0.00')
const totalStock = computed(() => Number(form.stock) || 0)
const checks = computed(() => [
  { text: '账号与分类服务状态可用', ok: initializationAvailable.value },
  { text: '已选择闲鱼账号', ok: !!form.accountId },
  { text: '标题已填写', ok: form.title.trim().length > 0 },
  { text: '商品描述已填写', ok: form.description.trim().length > 0 },
  { text: '已上传商品图片', ok: form.imageUrls.length > 0 },
  { text: '分类已选择', ok: !!selectedCategoryName.value },
  { text: '已完成省、市、区选择', ok: isPublishAddressComplete(selectedAddress.value) },
  { text: '价格已填写', ok: Number(form.price) > 0 },
  { text: '库存数大于 0', ok: totalStock.value > 0 },
])

// 触发文件选择
function triggerUpload() {
  if (!accountAvailable.value || !form.accountId) {
    error.value = accountAvailable.value ? '请先选择闲鱼账号再上传图片' : '账号列表不可用，无法安全上传图片'
    return
  }
  fileInput.value?.click()
}

async function onFileSelect(e) {
  const files = e.target.files
  if (!files || files.length === 0) return
  if (!accountAvailable.value || !form.accountId) {
    error.value = '账号状态不可用，已阻止图片上传'
    e.target.value = ''
    return
  }
  const remaining = 10 - form.imageUrls.length
  const toUpload = Array.from(files).slice(0, remaining)
  const hadNoImages = form.imageUrls.length === 0
  for (const file of toUpload) {
    const validationMessage = imageUploadValidationMessage(file)
    if (validationMessage) {
      error.value = `图片 "${file.name}" ${validationMessage}`
      continue
    }
    try {
      const res = await uploadImage(form.accountId || 0, file)
      if (res.code === 200 && res.data?.url) {
        form.imageUrls.push(res.data.url)
      } else {
        error.value = res.msg || '图片上传失败'
      }
    } catch (err) {
      error.value = err.message || '图片上传失败'
    }
  }
  e.target.value = ''
  // 上传完成后，如果是第一次上传图片（刚有了封面图），触发自动分类
  if (hadNoImages && form.imageUrls.length > 0) {
    await triggerAutoCategory()
  }
}

function removeImage(idx) {
  form.imageUrls.splice(idx, 1)
}

function onDragStart(idx, e) {
  dragIndex.value = idx
  e.dataTransfer.effectAllowed = 'move'
}
function onDragOver(idx, e) {
  e.dataTransfer.dropEffect = 'move'
}
function onDrop(idx, _event) {
  const from = dragIndex.value
  if (from === idx) return
  const item = form.imageUrls.splice(from, 1)[0]
  form.imageUrls.splice(idx, 0, item)
  dragIndex.value = -1
}

async function loadCategories() {
  if (categories.value.length || categoriesLoading.value) return
  categoriesLoading.value = true
  categoriesAvailable.value = false
  categoryLoadError.value = ''
  try {
    // 优先从静态 JSON 文件加载（零网络延迟）
    const module = await import('../assets/data/categories.json')
    const tree = module.default?.cation || module.cation
    if (!Array.isArray(tree)) throw new Error('商品分类响应格式异常')
    categories.value = tree
    categoriesAvailable.value = true
    // 静默从后端拉取最新分类树（含自动分类新增的分类）
    // 自动分类服务在后台已将新分类写入后端 categories.json
    refreshCategoriesInBackground()
  } catch (e) {
    categoryLoadError.value = e?.message || '商品分类加载失败'
    categories.value = []
  } finally {
    categoriesLoading.value = false
  }
}

async function load() {
  accountAvailable.value = false
  accountLoadError.value = ''
  accounts.value = []
  form.accountId = ''
  try {
    loadRecentCategories()
    await loadCategories()
    const [accountRes] = await Promise.all([
      getLiteAccounts({ size: 200 }),
      loadAiCategoryStatus()
    ])
    const data = accountRes?.data
    const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    accountAvailable.value = true
    const currentAccount = accounts.value.find(account => String(account?.id ?? '') === String(form.accountId ?? '')) || null
    const preferredAccount = pickPreferredAccount(accounts.value, form.accountId)
    if (preferredAccount && (!currentAccount || !accountAuthUsable(currentAccount))) form.accountId = preferredAccount.id
    if (!form.accountId && accounts.value[0]) form.accountId = accounts.value[0].id
  } catch (e) {
    accountLoadError.value = e?.message || '账号列表加载失败'
  }
}

const aiDescLoading = ref(false)
async function aiDesc() {
  if (aiDescLoading.value) return
  if (!form.title && !form.description) {
    error.value = '请先填写商品标题或基础描述'
    return
  }
  aiDescLoading.value = true
  error.value = ''
  try {
    const res = await aiRewriteGoods({
      title: form.title,
      description: form.description || ''
    })
    const data = res?.data
    const description = typeof data === 'string'
      ? data.trim()
      : (data && typeof data === 'object' && !Array.isArray(data)
          ? String(data.content || data.description || '').trim()
          : '')
    if (!description) throw new Error('AI 描述响应为空，原描述已保留')
    form.description = description
  } catch (e) {
    error.value = e.message || 'AI 描述生成失败'
  } finally {
    aiDescLoading.value = false
  }
}
function insertPhrase() {
  form.description += (form.description ? '\n' : '') + '下单前请先确认库存，售出不退不换。'
}

function validate() {
  const miss = checks.value.find(i => !i.ok)
  if (miss) { error.value = `"${miss.text}" 检查未通过，请完善后再提交`; return false }
  return true
}

async function submit() {
  error.value = ''
  success.value = ''
  if (!initializationAvailable.value) {
    error.value = '账号或分类服务状态不可用，已阻止发布'
    return
  }
  if (!validate()) return
  const ok = await confirmAction({
    title: '确认立即发布到闲鱼？',
    description: `账号：${selectedAccount.value || '-'}\n分类：${selectedCategoryPath.value || '-'}\n价格：¥${displayPrice.value}\n库存：${totalStock.value}\n发布成功后会同步保存到本地商品库。`,
    dangerous: true
  })
  if (!ok) return
  submitting.value = true
  let publishedItemId = ''
  try {
    const finalPrice = form.price
    const finalStock = Number(form.stock) || 1
    const shippingMap = { free: true, fixed: false, none: false }
    const freeShipping = shippingMap[shippingMode.value] ?? true

    // 构建位置数据（来自本地地址字典三级联动）
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
      // 发布成功，将闲鱼返回的商品 ID 同步保存到本地数据库
      if (!publishRes.data || typeof publishRes.data !== 'object' || Array.isArray(publishRes.data)) {
        throw new Error('发布请求已返回，但结果格式异常，无法确认是否成功，请先到闲鱼核对')
      }
      const itemId = String(publishRes.data.itemId ?? publishRes.data.xyGoodsId ?? publishRes.data.id ?? '').trim()
      const itemUrl = publishRes.data?.itemUrl || ''
      if (!itemId) throw new Error('发布接口未返回有效闲鱼商品ID，本地不会保存为在售商品')
      publishedItemId = itemId
      await createGoods({
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
      })
      success.value = '发布成功！'
      // 发布成功后清除草稿并解除导航守卫，避免跳转时再弹草稿询问
      clearPublishDraft()
      clearNavigationGuard()
      // 标记商品待同步，下次进入商品管理页面时自动触发同步
      localStorage.setItem('xianyu_pending_sync', 'true')
      setTimeout(() => emit('navigate', 'products'), 1000)
    } else {
      error.value = publishRes.msg || '发布到闲鱼失败'
    }
  } catch (e) {
    error.value = publishedItemId
      ? `商品已发布到闲鱼（ID：${publishedItemId}），但本地商品记录保存失败：${e.message || '服务异常'}。请勿重复发布，先到商品管理执行同步。`
      : (e.message || '发布失败')
    if (publishedItemId) localStorage.setItem('xianyu_pending_sync', 'true')
  } finally {
    submitting.value = false
  }
}

// ---- 草稿（自动保存 / 恢复 / 清空） ----
const isRestoring = ref(false)
let saveTimer = null

const hasDraftData = computed(() => {
  // accountId 不计入判定，因为会自动选择
  return !!(form.title.trim()
    || form.description.trim()
    || form.imageUrls.length
    || form.price
    || form.stock
    || selectedCategoryName.value
    || isPublishAddressComplete(selectedAddress.value))
})

function serializeCurrentDraft() {
  return {
    form: {
      accountId: form.accountId,
      title: form.title,
      description: form.description,
      imageUrls: [...form.imageUrls],
      price: form.price,
      stock: form.stock,
      supportSelfPick: form.supportSelfPick,
    },
    shippingMode: shippingMode.value,
    category: {
      name: selectedCategoryName.value,
      path: selectedCategoryPath.value,
      pathIds: [level1Id.value, level2Id.value, level3Id.value].filter(Boolean),
    },
    address: selectedAddress.value ? JSON.parse(JSON.stringify(selectedAddress.value)) : null,
  }
}

function restoreDraft(draft) {
  isRestoring.value = true
  try {
    const f = draft.form || {}
    form.accountId = f.accountId || ''
    form.title = f.title || ''
    form.description = f.description || ''
    form.imageUrls = Array.isArray(f.imageUrls) ? [...f.imageUrls] : []
    form.price = f.price || ''
    form.stock = f.stock || ''
    form.supportSelfPick = !!f.supportSelfPick
    shippingMode.value = draft.shippingMode || 'free'
    // 分类恢复：优先走级联选择，无 pathIds 时回退到直接设置 name/path
    const cat = draft.category || {}
    if (cat.pathIds && cat.pathIds.length) {
      nextTick(() => {
        // 试图在分类树中找到对应路径
        try {
          if (cat.pathIds[0]) selectLevel1(categories.value.find(c => c.id === cat.pathIds[0]))
          if (cat.pathIds[1]) selectLevel2(level2List.value.find(c => c.id === cat.pathIds[1]))
          if (cat.pathIds[2]) selectLevel3(level3List.value.find(c => c.id === cat.pathIds[2]))
        } catch {
          selectedCategoryName.value = cat.name || ''
          selectedCategoryPath.value = cat.path || ''
        }
      })
    } else {
      selectedCategoryName.value = cat.name || ''
      selectedCategoryPath.value = cat.path || ''
    }
    if (draft.address) selectedAddress.value = draft.address
  } finally {
    nextTick(() => { isRestoring.value = false })
  }
}

function scheduleAutoSave() {
  if (isRestoring.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    if (hasDraftData.value) {
      savePublishDraft(serializeCurrentDraft())
    } else {
      clearPublishDraft()
    }
  }, 800)
}

// 监听表单与分类、地址变化，自动保存草稿（防抖 800ms）
watch(
  () => [
    form.accountId, form.title, form.description, form.price, form.stock,
    form.supportSelfPick, form.imageUrls.length,
  ],
  scheduleAutoSave,
)
watch(shippingMode, scheduleAutoSave)
watch(selectedCategoryName, scheduleAutoSave)
watch(selectedAddress, scheduleAutoSave, { deep: true })

function flushDraftBeforeUnload() {
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  // beforeunload 需要立即落盘，不经过防抖
  if (hasDraftData.value) {
    savePublishDraft(serializeCurrentDraft())
  }
}

// 导航守卫：有未发布数据时弹窗询问是否保存草稿
async function navigationGuardFn() {
  if (!hasDraftData.value) return true
  const choice = await promptDraftChoice({
    title: '是否保存草稿？',
    description: '离开后本页已输入的内容将保存为草稿，下次进入可自动恢复。',
  })
  if (choice === 'discard') {
    clearPublishDraft()
    return true
  }
  // save 或未选择（自动保存）
  savePublishDraft(serializeCurrentDraft())
  return true
}

async function clearAllData() {
  const ok = await confirmAction({
    title: '清空本页所有数据？',
    description: '将一键清除已填写的标题、描述、图片、分类、地址、价格等全部内容，且会删除已保存的草稿。此操作不可撤销。',
    confirmText: '清空',
    dangerous: true,
  })
  if (!ok) return
  isRestoring.value = true
  try {
    form.title = ''
    form.description = ''
    form.imageUrls = []
    form.price = ''
    form.stock = ''
    form.supportSelfPick = false
    shippingMode.value = 'free'
    selectedCategoryName.value = ''
    selectedCategoryPath.value = ''
    level1Id.value = null
    level2Id.value = null
    level3Id.value = null
    level2List.value = []
    level3List.value = []
    selectedAddress.value = null
    categoryKeyword.value = ''
    autoCategoryCandidates.value = []
    autoCategoryMessage.value = ''
    autoSelectedCatId.value = null
    aiCategoryMessage.value = ''
    error.value = ''
    success.value = ''
    clearPublishDraft()
  } finally {
    isRestoring.value = false
  }
}

onMounted(async () => {
  setNavigationGuard(navigationGuardFn)
  window.addEventListener('beforeunload', flushDraftBeforeUnload)
  await load()
  // 尝试恢复草稿
  try {
    const draft = loadPublishDraft()
    if (draft && draft.form) {
      // 验证 accountId 是否仍存在于账号列表，避免引用已删除账号
      if (draft.form.accountId) {
        const exists = accounts.value.some(a => String(a.id) === String(draft.form.accountId))
        if (!exists) draft.form.accountId = ''
      }
      restoreDraft(draft)
      success.value = '已恢复上次未发布的草稿'
    }
  } catch {
    // 草稿恢复失败不影响正常使用
  }
})

onBeforeUnmount(() => {
  clearNavigationGuard()
  window.removeEventListener('beforeunload', flushDraftBeforeUnload)
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  categoryRefreshGate.dispose()
})
</script>

<style scoped>
.img-card {
  position: relative;
  width: 100px;
  height: 100px;
  border: 2px solid #e8e8e8;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  cursor: grab;
  transition: border-color 0.2s;
}
.img-card:hover {
  border-color: var(--primary, #1677ff);
}
.img-card.add-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #fbfdff;
  border-style: dashed;
  cursor: pointer;
}
.img-card.add-card:hover {
  border-color: var(--primary, #1677ff);
  background: #f0f5ff;
}
.img-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  background: rgba(0,0,0,0.5);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  cursor: pointer;
  z-index: 2;
}
.img-remove:hover {
  background: rgba(255,0,0,0.7);
}
.image-strip {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
/* ---- 分类级联选择器 ---- */
.category-selector {
  min-height: 60px;
}
.category-tools { display: flex; gap: 8px; margin-bottom: 10px; }
.category-search { flex: 1; padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 10px; outline: none; }
.category-search:focus { border-color: var(--primary, #1677ff); }
.category-clear { border: 1px solid #dbe3ef; background: #fff; border-radius: 10px; padding: 0 12px; cursor: pointer; }
.category-ai-btn { border: 1px solid #bcd7ff; background: #f4f8ff; color: #0d6bff; border-radius: 10px; padding: 0 12px; cursor: pointer; font-weight: 700; }
.category-ai-btn:disabled { cursor: not-allowed; opacity: .55; }
.ai-category-tip { margin-left: 10px; color: #16bf78; font-weight: 700; }
.category-search-results { display: grid; gap: 6px; max-height: 220px; overflow: auto; margin-bottom: 10px; padding: 8px; border: 1px solid #e8edf5; border-radius: 12px; background: #fbfdff; }
.category-result { display: grid; gap: 2px; padding: 8px 10px; border-radius: 9px; cursor: pointer; }
.category-result:hover { background: #eef5ff; }
.category-result strong { color: #111827; font-size: 13px; }
.category-result span { color: #64748b; font-size: 12px; }
.recent-categories { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; color: #64748b; font-size: 12px; }
.recent-categories button { border: 1px solid #dbeafe; background: #eff6ff; color: #1d4ed8; border-radius: 999px; padding: 5px 10px; cursor: pointer; }
.favorite-categories span { color: #92400e; }
.favorite-categories button { border-color: #fed7aa; background: #fff7ed; color: #c2410c; }
.category-actions { margin-bottom: 10px; }
.category-actions button, .category-link { border: 1px solid #dbe3ef; background: #fff; border-radius: 999px; padding: 5px 10px; cursor: pointer; font-size: 12px; color: #2563eb; }
.cascader-levels {
  display: flex;
  gap: 8px;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  overflow: hidden;
}
.cascader-col {
  flex: 1;
  min-width: 120px;
  max-height: 220px;
  overflow-y: auto;
  border-right: 1px solid #e8e8e8;
  background: #fafafa;
}
.cascader-col:last-child {
  border-right: none;
}
.cascader-item {
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cascader-item:hover {
  background: #e6f0ff;
}
.cascader-item.active {
  background: var(--primary, #1677ff);
  color: #fff;
  font-weight: 500;
}
/* ---- 发货设置 ---- */
.shipping-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.shipping-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}
.shipping-item:not(:last-child) {
  border-bottom: 1px solid #f0f0f0;
}
.char-count {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
  white-space: nowrap;
}

/* ---- 自动分类 ---- */
.auto-category-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  padding: 8px 12px;
  background: #f0f7ff;
  border: 1px solid #d4e4ff;
  border-radius: 10px;
  color: #1a56db;
  font-size: 13px;
}
.auto-category-hint .hint-icon {
  font-size: 16px;
}
.auto-category-spinner {
  margin-left: auto;
  color: #0d6bff;
  font-weight: 700;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.auto-category-msg {
  margin-bottom: 10px;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
}
.auto-category-msg.success {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #059669;
}
.auto-category-msg.warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #b45309;
}
.auto-category-msg.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
}
.auto-category-msg.info {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
}
.auto-category-candidates {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  padding: 8px 12px;
  border: 1px solid #e4eaf2;
  border-radius: 10px;
  background: #fafcff;
}
.candidates-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
  white-space: nowrap;
}
.candidate-btn {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
}
.candidate-btn:hover {
  background: #dbeafe;
  border-color: #93c5fd;
}
.candidate-btn.active {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #fff;
}
.candidate-btn small {
  font-weight: 400;
  opacity: 0.8;
}
/* ---- 草稿工具栏 ---- */
.draft-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.draft-tip {
  font-size: 13px;
  color: #475569;
}
.clear-draft-btn {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
  border-radius: 8px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  transition: all 0.15s;
}
.clear-draft-btn:hover {
  background: #fee2e2;
  border-color: #fca5a5;
}
</style>
