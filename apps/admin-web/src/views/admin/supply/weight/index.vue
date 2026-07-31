<template>
  <div class="supply-weight-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>货源权重调整</h2>
          <p>调整货源商城中商品的展示权重，权重越大在商城列表中越靠前。支持平台自营商品与供货商商品统一管理。</p>
        </div>
        <div class="toolbar-actions">
          <ElButton type="primary" :loading="loading" @click="load">刷新</ElButton>
        </div>
      </div>

      <ElForm :inline="true" :model="query" class="search-form">
        <ElFormItem label="来源">
          <ElSelect v-model="query.source" placeholder="全部来源" clearable style="width: 140px" @change="search">
            <ElOption label="平台自营" value="mall" />
            <ElOption label="供货商" value="supply" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="类型">
          <ElSelect v-model="query.productType" placeholder="全部类型" clearable style="width: 140px" @change="search">
            <ElOption label="文本" value="text" />
            <ElOption label="卡密" value="card" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput
            v-model="query.keyword"
            placeholder="搜索商品标题"
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
        description="请求失败，请稍后重试。"
        @retry="load"
      />
      <AdminDataState
        v-else-if="listState === 'empty'"
        state="empty"
        title="暂无商品"
        description="查询已成功完成，当前筛选条件下没有记录。"
        :retryable="false"
      />
      <ElTable v-else :data="filteredRecords" border stripe style="width: 100%">
        <template #empty><div class="empty-state">暂无商品记录</div></template>
        <ElTableColumn prop="id" label="ID" width="80" align="center" />
        <ElTableColumn label="来源" width="110" align="center">
          <template #default="{ row }">
            <ElTag :type="sourceTagType(row.source)" effect="light">
              {{ sourceLabel(row.source) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="商品信息" min-width="280">
          <template #default="{ row }">
            <div class="product-cell">
              <div class="product-cover" :style="coverStyle(row)"></div>
              <div class="product-info">
                <div class="product-title">{{ row.title || '未命名商品' }}</div>
                <div class="product-meta">
                  <ElTag :type="productTypeTagType(row.product_type)" size="small" effect="plain">
                    {{ productTypeLabel(row.product_type) }}
                  </ElTag>
                  <span v-if="row.category" class="product-category">{{ row.category }}</span>
                  <span class="product-price">¥{{ formatPrice(row.price_cent) }}</span>
                </div>
                <div v-if="row.subtitle" class="product-subtitle">{{ row.subtitle }}</div>
              </div>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="销量" width="100" align="center">
          <template #default="{ row }">{{ Number(row.bought_count ?? 0) }}</template>
        </ElTableColumn>
        <ElTableColumn label="当前权重" width="120" align="center">
          <template #default="{ row }">
            <span class="weight-current">{{ Number(row.weight ?? 0) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="调整权重" width="240" align="center">
          <template #default="{ row }">
            <div class="weight-adjust">
              <ElInputNumber
                v-model="row._newWeight"
                :min="0"
                :max="9999"
                :step="1"
                size="small"
                style="width: 110px"
              />
              <ElButton
                type="primary"
                size="small"
                :loading="savingId === row.id"
                :disabled="!isWeightChanged(row)"
                @click="saveWeight(row)"
              >保存</ElButton>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="批量调整" width="200" align="center">
          <template #default="{ row }">
            <ElButton size="small" @click="quickAdjust(row, 0)">归零</ElButton>
            <ElButton size="small" @click="quickAdjust(row, 10)">设为 10</ElButton>
            <ElButton size="small" @click="quickAdjust(row, 100)">设为 100</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>

      <div v-if="listState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ total }} 条记录</span>
        <ElPagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @change="load"
        />
      </div>
    </ElCard>

    <ElCard shadow="never" class="tips-card">
      <div class="tips-row">
        <div class="tips-icon-wrap">
          <ElIcon><InfoFilled /></ElIcon>
        </div>
        <div class="tips-content">
          <div class="tips-title">权重说明</div>
          <ul class="tips-list">
            <li>权重数值越大，商品在货源商城中越靠前展示；默认权重为 0。</li>
            <li>相同权重下，系统会按销量、创建时间等综合排序。</li>
            <li>权重调整后立即生效，前台商城会在下次刷新时按新权重排序。</li>
            <li>建议权重范围 0-9999；过大的权重不会带来额外收益，反而可能影响推荐体验。</li>
          </ul>
        </div>
      </div>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { getSupplyShopProductsForWeight, updateProductWeight } from '@/api/supply'

defineOptions({ name: 'AdminSupplyWeightPage' })

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

interface SupplyShopProduct {
  id: number
  source: 'mall' | 'supply'
  title: string
  subtitle?: string
  cover_url?: string
  price_cent: number
  product_type: string
  category?: string
  bought_count?: number
  weight: number
  _newWeight: number
  [key: string]: unknown
}

const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const records = ref<SupplyShopProduct[]>([])
const total = ref(0)
const query = reactive({
  source: '',
  productType: '',
  keyword: '',
  page: 1,
  size: 20
})

const savingId = ref<number | null>(null)

const filteredRecords = computed(() => records.value)

onMounted(load)

async function load() {
  loading.value = true
  listState.value = 'loading'
  try {
    const params: { page: number; size: number; keyword?: string } = {
      page: query.page,
      size: query.size
    }
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    const data = await getSupplyShopProductsForWeight(params)
    const payload = (data ?? {}) as Record<string, unknown>
    const list = (Array.isArray(payload.list) ? payload.list : Array.isArray(payload.records) ? payload.records : []) as SupplyShopProduct[]
    records.value = list.map(item => ({
      ...item,
      _newWeight: Number(item.weight ?? 0)
    }))
    total.value = Number(payload.total ?? 0)
    listState.value = records.value.length > 0 ? 'ready' : 'empty'
  } catch (err: any) {
    records.value = []
    total.value = 0
    listState.value = 'error'
    ElMessage.error(err?.message || '商品列表加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  load()
}

function reset() {
  query.source = ''
  query.productType = ''
  query.keyword = ''
  query.page = 1
  load()
}

function sourceLabel(source: string): string {
  if (source === 'mall') return '平台自营'
  if (source === 'supply') return '供货商'
  return source || '未知'
}

function sourceTagType(source: string): TagType {
  if (source === 'mall') return 'success'
  if (source === 'supply') return 'primary'
  return 'info'
}

function productTypeLabel(type: string): string {
  if (type === 'text') return '文本'
  if (type === 'card') return '卡密'
  return '其他'
}

function productTypeTagType(type: string): TagType {
  if (type === 'text') return 'primary'
  if (type === 'card') return 'warning'
  return 'info'
}

function formatPrice(cents: number): string {
  const n = Number(cents ?? 0)
  if (!Number.isFinite(n)) return '0.00'
  return (n / 100).toFixed(2)
}

function coverStyle(row: SupplyShopProduct) {
  const url = row.cover_url || ''
  if (url) return { backgroundImage: `url(${url})`, backgroundSize: 'cover', backgroundPosition: 'center' }
  return { background: 'linear-gradient(135deg, #e2e8f0, #cbd5e1)' }
}

function isWeightChanged(row: SupplyShopProduct): boolean {
  return Number(row._newWeight) !== Number(row.weight)
}

function quickAdjust(row: SupplyShopProduct, value: number) {
  row._newWeight = value
}

async function saveWeight(row: SupplyShopProduct) {
  if (!isWeightChanged(row) || savingId.value !== null) return
  const newWeight = Number(row._newWeight)
  if (!Number.isFinite(newWeight) || newWeight < 0 || newWeight > 9999) {
    ElMessage.warning('权重必须为 0-9999 之间的整数')
    return
  }
  savingId.value = row.id
  try {
    await updateProductWeight({
      source: row.source,
      id: row.id,
      weight: newWeight
    })
    row.weight = newWeight
    ElMessage.success(`已更新「${row.title || '未命名商品'}」的权重为 ${newWeight}`)
  } catch (err: any) {
    ElMessage.error(err?.message || '权重更新失败')
    row._newWeight = Number(row.weight)
  } finally {
    savingId.value = null
  }
}
</script>

<style scoped>
.supply-weight-page { padding: 16px; }
.filter-card { margin-bottom: 16px; }
.page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.search-form { row-gap: 8px; }
.table-card { min-height: 420px; }
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

.product-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.product-cover {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  flex-shrink: 0;
  background-color: #e2e8f0;
}
.product-info { min-width: 0; flex: 1; }
.product-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}
.product-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.product-category {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.product-price {
  font-size: 13px;
  font-weight: 700;
  color: #ff3b30;
}
.product-subtitle {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.weight-current {
  display: inline-block;
  min-width: 40px;
  padding: 2px 10px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

.weight-adjust {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tips-card {
  margin-top: 16px;
}
.tips-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.tips-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--el-color-info-light-9);
  color: var(--el-color-info);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tips-icon-wrap .el-icon,
.tips-icon-wrap svg {
  width: 18px;
  height: 18px;
}
.tips-content { flex: 1; min-width: 0; }
.tips-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}
.tips-list {
  margin: 0;
  padding-left: 20px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.tips-list li {
  margin-bottom: 2px;
}

@media (max-width: 1100px) {
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-actions {
    flex-wrap: wrap;
  }
}
</style>
