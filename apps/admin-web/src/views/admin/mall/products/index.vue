<template>
  <div class="admin-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>货源商城 - 商品管理</h2>
          <p>维护商城文本商品与卡密商品，支持封面图上传、卡密批量导入与库存查看</p>
        </div>
        <div class="toolbar-actions">
          <ElButton :loading="refreshingCategories" @click="handleRefreshCategories">
            <ElIcon><Refresh /></ElIcon>刷新分类
          </ElButton>
          <ElButton type="primary" @click="openDialog()">
            <ElIcon><Plus /></ElIcon>新增商品
          </ElButton>
        </div>
      </div>

      <ElTabs v-model="activeTab" @tab-change="onTabChange">
        <ElTabPane label="文本商品" name="text" />
        <ElTabPane label="卡密商品" name="card" />
      </ElTabs>

      <ElForm :inline="true" :model="query" class="search-form">
        <ElFormItem label="关键词">
          <ElInput
            v-model="query.keyword"
            placeholder="商品标题 / 内容"
            clearable
            style="width: 240px"
            @keyup.enter="search"
          />
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="search">查询</ElButton>
          <ElButton @click="reset">重置</ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard shadow="never" class="table-card">
      <AdminDataState
        v-if="listState === 'loading'"
        state="loading"
        title="正在加载商品列表"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="商品列表暂时不可用"
        description="请求失败，请重试。"
        @retry="load"
      />
      <template v-else>
        <ElTable :data="records" v-loading="loading" border stripe style="width: 100%">
          <template #empty><div class="empty-state">暂无商品记录</div></template>
          <ProductTableColumn prop="id" label="ID" width="80" align="center" />
          <ProductTableColumn label="封面" width="90" align="center">
            <template #default="{ row }">
              <ElImage
                v-if="row.coverUrl"
                :src="resolveImage(row.coverUrl)"
                fit="cover"
                style="width: 60px; height: 60px; border-radius: 6px"
                :preview-src-list="[resolveImage(row.coverUrl)]"
                preview-teleported
              />
              <span v-else class="row-muted">-</span>
            </template>
          </ProductTableColumn>
          <ProductTableColumn label="标题" min-width="220">
            <template #default="{ row }">
              <div class="title-cell">
                <strong>{{ row.title }}</strong>
              </div>
            </template>
          </ProductTableColumn>
          <ProductTableColumn label="价格" width="120" align="center">
            <template #default="{ row }">
              <span class="price-text">¥{{ formatPrice(row.price) }}</span>
            </template>
          </ProductTableColumn>
          <ProductTableColumn label="分类" width="140" align="center">
            <template #default="{ row }">
              <ElTag v-if="row.category" type="info" effect="light">{{ row.category }}</ElTag>
              <span v-else class="row-muted">-</span>
            </template>
          </ProductTableColumn>
          <ProductTableColumn v-if="activeTab === 'card'" label="库存" width="100" align="center">
            <template #default="{ row }">
              <ElTag :type="stockTagType(row.stock)" effect="plain">{{ row.stock ?? 0 }}</ElTag>
            </template>
          </ProductTableColumn>
          <ProductTableColumn label="状态" width="100" align="center">
            <template #default="{ row }">
              <ElTag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '禁用' }}</ElTag>
            </template>
          </ProductTableColumn>
          <ProductTableColumn label="操作" width="220" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton size="small" type="primary" link @click="openDialog(row)">编辑</ElButton>
              <ElButton v-if="activeTab === 'card'" size="small" type="warning" link @click="openCardKeys(row)">查看卡密</ElButton>
              <ElButton size="small" type="danger" link @click="handleDelete(row)">删除</ElButton>
            </template>
          </ProductTableColumn>
        </ElTable>

        <div class="pagination-row">
          <span class="muted">共 {{ total }} 条商品</span>
          <ElPagination
            v-model:current-page="query.page"
            v-model:page-size="query.size"
            layout="total, sizes, prev, pager, next, jumper"
            :total="total"
            @change="load"
          />
        </div>
      </template>
    </ElCard>

    <!-- 新增/编辑弹窗 -->
    <ElDialog v-if="dialogRendered" v-model="dialogVisible" :title="isEdit ? '编辑商品' : '新增商品'" width="720px" destroy-on-close append-to-body>
      <ElForm :model="form" :rules="rules" ref="formRef" label-width="120px" label-position="right">
        <ElFormItem label="商品类型" prop="type">
          <ElRadioGroup v-model="form.type" :disabled="isEdit">
            <ElRadioButton value="text">文本商品</ElRadioButton>
            <ElRadioButton value="card">卡密商品</ElRadioButton>
          </ElRadioGroup>
          <div class="form-tip">
            {{ form.type === 'card' ? '卡密商品需要逐条导入可发货的卡密内容' : '文本商品需要填写发货内容，购买后直接展示给用户' }}
          </div>
        </ElFormItem>
        <ElFormItem label="商品标题" prop="title">
          <ElInput v-model="form.title" placeholder="输入商品标题" maxlength="100" show-word-limit />
        </ElFormItem>
        <ElFormItem label="商品正文" prop="content">
          <ElInput
            v-model="form.content"
            type="textarea"
            :rows="4"
            :placeholder="form.type === 'card' ? '卡密商品购买后展示的说明文案' : '前台商品详情页展示的商品介绍'"
            maxlength="5000"
            show-word-limit
          />
        </ElFormItem>
        <ElFormItem label="商品文案" prop="copy">
          <ElInput
            v-model="form.copy"
            type="textarea"
            :rows="4"
            placeholder="供 AI 改写板块使用的原始文案，将作为 AI 生成新标题与正文的依据（不直接展示给前台用户）"
            maxlength="5000"
            show-word-limit
          />
          <div class="form-tip">
            此文案与上方标题将作为 AI 改写板块的输入：AI 会根据此文案与标题生成新的标题和正文，生图板块再依据新文案与标题生成封面图
          </div>
        </ElFormItem>
        <ElFormItem v-if="form.type === 'text'" label="发货内容" prop="deliveryContent">
          <ElInput
            v-model="form.deliveryContent"
            type="textarea"
            :rows="6"
            placeholder="用户购买后收到的实际发货内容（文本商品必填）"
            maxlength="20000"
            show-word-limit
          />
          <div class="form-tip">用户付款后将直接看到此内容，请确保填写完整</div>
        </ElFormItem>
        <ElFormItem label="价格（元）" prop="price">
          <ElInputNumber v-model="form.price" :min="0" :precision="2" :step="1" style="width: 220px" />
        </ElFormItem>
        <ElFormItem label="封面图" prop="coverUrl">
          <div class="cover-upload-area">
            <div v-if="form.coverUrl" class="cover-preview">
              <ElImage :src="resolveImage(form.coverUrl)" fit="cover" class="cover-preview-image" />
              <ElButton size="small" type="danger" plain @click="form.coverUrl = ''">移除</ElButton>
            </div>
            <div v-show="!form.coverUrl" class="cover-input-area">
              <ElRadioGroup v-model="coverUploadMode" size="small" style="margin-bottom: 8px">
                <ElRadioButton value="file">文件上传</ElRadioButton>
                <ElRadioButton value="url">URL导入</ElRadioButton>
              </ElRadioGroup>
              <ElUpload
                v-if="coverUploadMode === 'file'"
                :show-file-list="false"
                :before-upload="beforeImageUpload"
                :http-request="handleImageUpload"
                accept="image/png, image/jpeg"
              >
                <ElButton type="primary" plain>
                  <ElIcon><Upload /></ElIcon>选择文件上传
                </ElButton>
                <template #tip>
                  <div class="upload-tip">PNG、JPEG，不超过 5MB</div>
                </template>
              </ElUpload>
              <div v-else class="url-import-row">
                <ElInput
                  v-model="coverUrlInput"
                  placeholder="粘贴图片URL，自动下载保存到本地"
                  clearable
                  style="flex: 1"
                  @keyup.enter="handleUrlImport"
                />
                <ElButton type="primary" plain :loading="urlImporting" @click="handleUrlImport">导入</ElButton>
              </div>
            </div>
          </div>
        </ElFormItem>
        <ElFormItem label="商品分类" prop="category">
          <div class="category-selector">
            <div class="category-tools">
              <ElInput
                v-model="categoryKeyword"
                size="small"
                placeholder="搜索分类，如 手机 / 图书 / 家居"
                clearable
                style="width: 240px"
              />
              <ElButton v-if="selectedCategoryPath" size="small" type="warning" plain @click="resetCategorySelection">清除选择</ElButton>
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
            <div class="cascader-levels">
              <div class="cascader-col">
                <div v-if="categoriesLoading" class="cascader-item muted">分类加载中...</div>
                <div v-else-if="categoryLoadError" class="cascader-item muted">分类加载失败，请关闭弹窗重试</div>
                <div v-else-if="!filteredCategories.length" class="cascader-item muted">暂无分类</div>
                <div
                  v-for="cat in filteredCategories"
                  :key="cat.id"
                  :class="['cascader-item', { active: level1Id === cat.id }]"
                  @click="selectLevel1(cat)"
                >
                  {{ nodeLabel(cat) }}
                </div>
              </div>
              <div v-if="level2List.length" class="cascader-col">
                <div
                  v-for="cat in level2List"
                  :key="cat.id"
                  :class="['cascader-item', { active: level2Id === cat.id }]"
                  @click="selectLevel2(cat)"
                >
                  {{ nodeLabel(cat) }}
                </div>
              </div>
              <div v-if="level3List.length" class="cascader-col">
                <div
                  v-for="cat in level3List"
                  :key="cat.id"
                  :class="['cascader-item', { active: level3Id === cat.id }]"
                  @click="selectLevel3(cat)"
                >
                  {{ nodeLabel(cat) }}
                </div>
              </div>
            </div>
            <p class="form-tip">
              已选分类：{{ selectedCategoryPath || '请选择分类（仅手动选择，不会根据封面图自动判定）' }}
            </p>
            <p class="form-tip">前台用户上架此商品时，将直接使用此处配置的分类，无需再次选择</p>
          </div>
        </ElFormItem>
        <ElFormItem v-if="form.type === 'card'" label="卡密批量导入" prop="cards">
          <div class="cards-import-area">
            <ElInput
              v-model="form.cards"
              type="textarea"
              :rows="6"
              placeholder="每行一条卡密，保存后会自动入库。编辑现有商品时此处仅追加新卡密。"
            />
            <div class="cards-stock-tip" v-if="isEdit && form.id">
              当前库存：<strong>{{ form.stock ?? 0 }}</strong> 条 · 本次待导入：<strong>{{ cardsLineCount }}</strong> 条
            </div>
            <div class="cards-stock-tip" v-else>
              待导入：<strong>{{ cardsLineCount }}</strong> 条
            </div>
          </div>
        </ElFormItem>
        <ElFormItem label="启用状态" prop="enabled">
          <ElSwitch v-model="form.enabled" active-text="启用" inactive-text="禁用" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="handleSave">保存</ElButton>
      </template>
    </ElDialog>

    <!-- 卡密查看弹窗 -->
    <ElDialog v-if="cardKeysRendered" v-model="cardKeysDialogVisible" title="卡密列表" width="760px" destroy-on-close append-to-body>
      <div class="card-keys-head">
        <span>商品：<strong>{{ cardKeysProduct?.title }}</strong></span>
        <span class="muted">共 {{ cardKeysTotal }} 条</span>
      </div>
      <ElTable :data="cardKeys" v-loading="cardKeysLoading" border stripe style="width: 100%" max-height="420">
        <template #empty><div class="empty-state">暂无卡密</div></template>
        <CardKeyTableColumn prop="id" label="ID" width="80" align="center" />
        <CardKeyTableColumn prop="content" label="卡密内容" min-width="280" show-overflow-tooltip />
        <CardKeyTableColumn label="状态" width="110" align="center">
          <template #default="{ row }">
            <ElTag :type="cardKeyStatusTagType(row.status)" effect="plain">
              {{ cardKeyStatusLabel(row.status) }}
            </ElTag>
          </template>
        </CardKeyTableColumn>
        <CardKeyTableColumn prop="createdAt" label="创建时间" width="180" />
      </ElTable>
      <div class="pagination-row">
        <span class="muted">第 {{ cardKeysQuery.page }} 页</span>
        <ElPagination
          v-model:current-page="cardKeysQuery.page"
          v-model:page-size="cardKeysQuery.size"
          layout="prev, pager, next"
          :total="cardKeysTotal"
          @change="loadCardKeys"
        />
      </div>
      <template #footer>
        <ElButton @click="cardKeysDialogVisible = false">关闭</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox, ElTableColumn } from 'element-plus'
import { Plus, Refresh, Upload } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadRequestOptions } from 'element-plus'
import {
  getMallProducts,
  createMallProduct,
  updateMallProduct,
  deleteMallProduct,
  getCardKeys,
  importCardKeys,
  refreshCategories,
  uploadMallImage,
  uploadMallImageFromUrl,
  getMallCategoryTree,
  type MallProduct,
  type MallProductType,
  type MallCategoryNode,
  type CardKeyItem
} from '@/api/mall'

defineOptions({ name: 'AdminMallProductsPage' })

const ProductTableColumn: typeof ElTableColumn<MallProduct> = ElTableColumn
const CardKeyTableColumn: typeof ElTableColumn<CardKeyItem> = ElTableColumn

const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const records = ref<MallProduct[]>([])
const total = ref(0)
const activeTab = ref<MallProductType>('text')

const query = reactive({
  keyword: '',
  page: 1,
  size: 20
})

const refreshingCategories = ref(false)

const dialogVisible = ref(false)
const dialogRendered = ref(false)
const saving = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()

// 强制每次打开弹窗时重新挂载 ElDialog，避免 Teleport + Transition 持久化导致的 overlay 不插入 DOM 问题
watch(dialogVisible, (val) => {
  if (val) {
    dialogRendered.value = true
  } else {
    setTimeout(() => {
      if (!dialogVisible.value) dialogRendered.value = false
    }, 350)
  }
}, { flush: 'post' })

const defaultForm = () => ({
  id: undefined as number | undefined,
  type: activeTab.value as MallProductType,
  title: '',
  content: '',
  copy: '',
  deliveryContent: '',
  price: 0,
  coverUrl: '',
  category: '',
  stock: 0,
  cards: '',
  enabled: true
})

const form = reactive(defaultForm())

const rules: FormRules = {
  type: [{ required: true, message: '请选择商品类型', trigger: 'change' }],
  title: [{ required: true, message: '请输入商品标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入商品正文', trigger: 'blur' }],
  price: [{ required: true, message: '请输入价格', trigger: 'blur' }]
}

// ---- 商品分类级联（手动选择，与前台发布商品使用同一分类源） ----
const categoryTree = ref<MallCategoryNode[]>([])
const categoriesLoading = ref(false)
const categoryLoadError = ref('')
const level1Id = ref<string | number | null>(null)
const level2Id = ref<string | number | null>(null)
const level3Id = ref<string | number | null>(null)
const level2List = ref<MallCategoryNode[]>([])
const level3List = ref<MallCategoryNode[]>([])
const categoryKeyword = ref('')
const selectedCategoryName = ref('')
const selectedCategoryPath = ref('')

function resetCategorySelection() {
  level1Id.value = null
  level2Id.value = null
  level3Id.value = null
  level2List.value = []
  level3List.value = []
  categoryKeyword.value = ''
  selectedCategoryName.value = ''
  selectedCategoryPath.value = ''
}

function nodeLabel(node?: MallCategoryNode): string {
  return node ? (node.label || node.title || String(node.id || '')) : ''
}

function selectLevel1(cat: MallCategoryNode) {
  level1Id.value = cat.id
  level2Id.value = null
  level3Id.value = null
  level2List.value = cat.children || []
  level3List.value = []
  selectedCategoryName.value = nodeLabel(cat)
  selectedCategoryPath.value = nodeLabel(cat)
}

function selectLevel2(cat: MallCategoryNode) {
  level2Id.value = cat.id
  level3Id.value = null
  level3List.value = cat.children || []
  const l1 = categoryTree.value.find(c => c.id === level1Id.value)
  selectedCategoryName.value = nodeLabel(cat)
  selectedCategoryPath.value = `${nodeLabel(l1)} ＞ ${nodeLabel(cat)}`
}

function selectLevel3(cat: MallCategoryNode) {
  level3Id.value = cat.id
  const l1 = categoryTree.value.find(c => c.id === level1Id.value)
  const l2 = level2List.value.find(c => c.id === level2Id.value)
  selectedCategoryName.value = nodeLabel(cat)
  selectedCategoryPath.value = `${nodeLabel(l1)} ＞ ${nodeLabel(l2)} ＞ ${nodeLabel(cat)}`
}

const filteredCategories = computed(() => {
  if (!categoryKeyword.value.trim()) return categoryTree.value
  const kw = categoryKeyword.value.trim().toLowerCase()
  return categoryTree.value.filter(cat =>
    nodeLabel(cat).toLowerCase().includes(kw)
    || (cat.children || []).some(child => nodeLabel(child).toLowerCase().includes(kw))
  )
})

const categorySearchResults = computed(() => {
  const kw = categoryKeyword.value.trim().toLowerCase()
  if (!kw) return [] as { name: string; path: string; pathIds: (string | number)[] }[]
  const res: { name: string; path: string; pathIds: (string | number)[] }[] = []
  const walk = (nodes: MallCategoryNode[], parents: string[] = [], parentIds: (string | number)[] = []) => {
    for (const node of nodes || []) {
      const name = nodeLabel(node)
      const pathParts = [...parents, name]
      const pathIds = [...parentIds, node.id]
      if (String(name).toLowerCase().includes(kw)) {
        res.push({ name, path: pathParts.join(' ＞ '), pathIds })
      }
      if (res.length < 20) walk(node.children || [], pathParts, pathIds)
      if (res.length >= 20) return
    }
  }
  walk(categoryTree.value)
  return res.slice(0, 20)
})

function selectCategoryByPath(item: { name: string; path: string; pathIds: (string | number)[] }) {
  const ids = item.pathIds || []
  const l1 = categoryTree.value.find(c => String(c.id) === String(ids[0]))
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
}

/**
 * 编辑商品时根据已保存的 category 字符串（叶子分类名）反查分类树并回填选中状态。
 * 优先匹配叶子名等于 category 的路径；若无匹配则仅回填 category 字符串。
 */
function findAndSelectCategoryByName(categoryName: string) {
  if (!categoryName || !categoryTree.value.length) {
    selectedCategoryName.value = categoryName || ''
    selectedCategoryPath.value = categoryName || ''
    return
  }
  const target = String(categoryName).trim()
  const walk = (nodes: MallCategoryNode[], parents: MallCategoryNode[] = []): MallCategoryNode[] | null => {
    for (const node of nodes || []) {
      if (nodeLabel(node) === target) {
        return [...parents, node]
      }
      const matched = walk(node.children || [], [...parents, node])
      if (matched) return matched
    }
    return null
  }
  const path = walk(categoryTree.value)
  if (!path || !path.length) {
    selectedCategoryName.value = target
    selectedCategoryPath.value = target
    return
  }
  const [l1, l2, l3] = path
  if (l1) selectLevel1(l1)
  if (l2) selectLevel2(l2)
  if (l3) selectLevel3(l3)
}

async function loadCategoryTree() {
  if (categoryTree.value.length) return
  categoriesLoading.value = true
  categoryLoadError.value = ''
  try {
    const tree = await getMallCategoryTree()
    const list = tree?.cation || tree?.categories || []
    if (!Array.isArray(list)) throw new Error('商品分类响应格式异常')
    categoryTree.value = list
  } catch (e: any) {
    categoryLoadError.value = e?.message || '商品分类加载失败'
    categoryTree.value = []
  } finally {
    categoriesLoading.value = false
  }
}

const cardsLineCount = computed(() => {
  const text = (form.cards || '').trim()
  if (!text) return 0
  return text.split(/\r?\n/).filter(line => line.trim()).length
})

const cardKeysDialogVisible = ref(false)
const cardKeysRendered = ref(false)
const cardKeysLoading = ref(false)

watch(cardKeysDialogVisible, (val) => {
  if (val) {
    cardKeysRendered.value = true
  } else {
    setTimeout(() => {
      if (!cardKeysDialogVisible.value) cardKeysRendered.value = false
    }, 350)
  }
}, { flush: 'post' })
const cardKeys = ref<CardKeyItem[]>([])
const cardKeysTotal = ref(0)
const cardKeysProduct = ref<MallProduct | null>(null)
const cardKeysQuery = reactive({ page: 1, size: 20 })

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function formatPrice(price?: number) {
  const value = Number(price || 0)
  return value.toFixed(2)
}

function resolveImage(imageUrl?: string) {
  const value = String(imageUrl || '').trim()
  if (!value) return ''
  if (/^(https?:)?\/\//.test(value) || value.startsWith('/')) return value
  return `/${value.replace(/^\/+/, '')}`
}

function stockTagType(stock?: number): TagType {
  if (!stock || stock <= 0) return 'danger'
  if (stock < 10) return 'warning'
  return 'success'
}

function cardKeyStatusLabel(status?: string): string {
  if (status === 'used') return '已使用'
  if (status === 'disabled') return '已禁用'
  return '未使用'
}

function cardKeyStatusTagType(status?: string): TagType {
  if (status === 'used') return 'info'
  if (status === 'disabled') return 'danger'
  return 'success'
}

onMounted(load)

async function load() {
  loading.value = true
  listState.value = 'loading'
  try {
    const page = await getMallProducts({
      type: activeTab.value,
      keyword: query.keyword,
      page: query.page,
      size: query.size
    })
    records.value = page.records
    total.value = page.total
    listState.value = records.value.length > 0 ? 'ready' : 'empty'
  } catch {
    records.value = []
    total.value = 0
    listState.value = 'error'
  } finally {
    loading.value = false
  }
}

function onTabChange() {
  query.page = 1
  load()
}

function search() {
  query.page = 1
  load()
}

function reset() {
  query.keyword = ''
  query.page = 1
  load()
}

function openDialog(row?: MallProduct) {
  isEdit.value = !!row
  if (row) {
    form.id = row.id
    form.type = row.type
    form.title = row.title || ''
    form.content = row.content || ''
    form.copy = row.copy || ''
    form.deliveryContent = row.deliveryContent || ''
    form.price = Number(row.price || 0)
    form.coverUrl = row.coverUrl || ''
    form.category = row.category || ''
    form.stock = row.stock ?? 0
    form.cards = ''
    form.enabled = row.enabled !== false
  } else {
    Object.assign(form, defaultForm())
    form.type = activeTab.value
  }
  // 每次打开弹窗时重置分类选中状态，避免上次选择残留
  resetCategorySelection()
  // 异步加载分类树（首次加载会请求后端，后续使用缓存）
  loadCategoryTree().then(() => {
    if (isEdit.value && form.category) {
      findAndSelectCategoryByName(form.category)
    }
  })
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload: Partial<MallProduct> = {
      type: form.type,
      productType: form.type,
      title: form.title,
      content: form.content,
      copy: form.copy?.trim() || undefined,
      deliveryContent: form.type === 'text' ? form.deliveryContent : undefined,
      price: Number(form.price),
      coverUrl: form.coverUrl || undefined,
      category: selectedCategoryName.value || form.category || '',
      enabled: form.enabled
    }
    let productId = form.id
    if (isEdit.value && form.id) {
      await updateMallProduct(form.id, payload)
    } else {
      const created = await createMallProduct(payload)
      productId = created?.id
    }
    // 卡密商品且填入了卡密，导入卡密
    if (form.type === 'card' && productId && (form.cards || '').trim()) {
      await importCardKeys(productId, form.cards.trim())
    }
    ElMessage.success(isEdit.value ? '商品更新成功' : '商品添加成功')
    dialogVisible.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: MallProduct) {
  if (!row.id) return
  try {
    await ElMessageBox.confirm(`确认删除商品「${row.title}」？删除后无法恢复。`, '确认删除', { type: 'warning' })
    await deleteMallProduct(row.id)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // cancelled
  }
}

async function openCardKeys(row: MallProduct) {
  if (!row.id) return
  cardKeysProduct.value = row
  cardKeysDialogVisible.value = true
  cardKeysQuery.page = 1
  await loadCardKeys()
}

async function loadCardKeys() {
  if (!cardKeysProduct.value?.id) return
  cardKeysLoading.value = true
  try {
    const page = await getCardKeys(cardKeysProduct.value.id, {
      page: cardKeysQuery.page,
      size: cardKeysQuery.size
    })
    cardKeys.value = page.records
    cardKeysTotal.value = page.total
  } catch {
    cardKeys.value = []
    cardKeysTotal.value = 0
  } finally {
    cardKeysLoading.value = false
  }
}

async function handleRefreshCategories() {
  refreshingCategories.value = true
  try {
    await refreshCategories()
  } catch (e: any) {
    ElMessage.error(e?.message || '刷新分类失败')
  } finally {
    refreshingCategories.value = false
  }
}

function beforeImageUpload(file: File) {
  const validType = ['image/png', 'image/jpeg'].includes(file.type)
  if (!validType) {
    ElMessage.error('仅支持 PNG、JPEG 格式')
    return false
  }
  if (file.size / 1024 / 1024 > 5) {
    ElMessage.error('图片大小不能超过 5MB')
    return false
  }
  return true
}

async function handleImageUpload(options: UploadRequestOptions) {
  try {
    const res = await uploadMallImage(options.file)
    if (res?.url) {
      form.coverUrl = res.url
      ElMessage.success('图片上传成功')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '上传失败')
  }
}

const coverUploadMode = ref<'file' | 'url'>('file')
const coverUrlInput = ref('')
const urlImporting = ref(false)

async function handleUrlImport() {
  const url = coverUrlInput.value.trim()
  if (!url) {
    ElMessage.warning('请输入图片URL')
    return
  }
  urlImporting.value = true
  try {
    const res = await uploadMallImageFromUrl(url)
    if (res?.url) {
      form.coverUrl = res.url
      coverUrlInput.value = ''
      ElMessage.success('图片导入成功，已保存到本地')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || 'URL导入失败')
  } finally {
    urlImporting.value = false
  }
}
</script>

<style scoped>
.admin-page { padding: 4px; }
.filter-card { margin-bottom: 16px; border-radius: 16px; }
.table-card { min-height: 420px; border-radius: 16px; }
.page-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 22px; font-weight: 800; }
.page-title-row p { margin: 0; color: var(--art-gray-500); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.search-form { margin-top: 12px; row-gap: 8px; }
.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
}
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.row-muted { color: var(--art-gray-400); }
.title-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.title-cell strong {
  color: var(--el-text-color-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}
.row-subtitle {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}
.price-text {
  color: #d97706;
  font-weight: 700;
}
.form-tip {
  font-size: 12px;
  color: var(--art-gray-500);
  margin-top: 4px;
  line-height: 1.6;
}
.cover-upload-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cover-preview {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cover-preview-image {
  width: 160px;
  height: 90px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-light);
}
.upload-tip {
  font-size: 12px;
  color: var(--art-gray-500);
  margin-top: 4px;
}
.cover-input-area {
  display: flex;
  flex-direction: column;
}
.url-import-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.cards-import-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.cards-stock-tip {
  font-size: 12px;
  color: var(--art-gray-500);
}
.cards-stock-tip strong {
  color: var(--el-color-primary);
  font-weight: 700;
}
.category-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.category-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.category-search-results {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  max-height: 200px;
  overflow-y: auto;
}
.category-result {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter);
  transition: background-color 0.15s;
}
.category-result:last-child {
  border-bottom: none;
}
.category-result:hover {
  background: var(--el-fill-color-light);
}
.category-result strong {
  color: var(--el-text-color-primary);
  font-size: 13px;
}
.category-result span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.category-result.muted {
  color: var(--el-text-color-secondary);
  font-style: normal;
  cursor: default;
}
.category-result.muted:hover {
  background: transparent;
}
.cascader-levels {
  display: flex;
  gap: 8px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  min-height: 180px;
  max-height: 280px;
  overflow: hidden;
}
.cascader-col {
  flex: 1;
  min-width: 140px;
  max-width: 220px;
  overflow-y: auto;
  border-right: 1px solid var(--el-border-color-lighter);
  padding: 4px 0;
}
.cascader-col:last-child {
  border-right: none;
}
.cascader-item {
  padding: 6px 12px;
  font-size: 13px;
  color: var(--el-text-color-primary);
  cursor: pointer;
  transition: background-color 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cascader-item:hover {
  background: var(--el-fill-color-light);
}
.cascader-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}
.cascader-item.muted {
  color: var(--el-text-color-secondary);
  cursor: default;
  font-style: italic;
}
.cascader-item.muted:hover {
  background: transparent;
}
.card-keys-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.card-keys-head strong { color: var(--el-text-color-primary); }
@media (max-width: 900px) {
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-actions {
    flex-wrap: wrap;
  }
}
</style>
