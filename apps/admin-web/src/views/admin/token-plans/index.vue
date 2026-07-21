<template>
  <div class="token-plans-page">
    <!-- 顶部标题区 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>Token 充值套餐</h2>
          <p>
            配置前台个人中心「立即充值」展示的 Token 套餐。支持设置套餐名称、Token 数量、赠送 Token、价格与排序；启用的套餐会按排序展示给前台用户。
          </p>
        </div>
        <div class="actions">
          <ElButton type="primary" :disabled="listState !== 'ready'" @click="openCreate">新增套餐</ElButton>
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 概览统计卡片 -->
    <div class="summary-grid">
      <ElCard shadow="never">
        <div class="metric-label">套餐总数</div>
        <div class="metric-value">{{ summary.total }}</div>
        <div class="metric-sub">含禁用套餐</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">启用中</div>
        <div class="metric-value" :class="{ 'text-success': summary.enabled > 0 }">{{ summary.enabled }}</div>
        <div class="metric-sub">前台可见</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">最低单价</div>
        <div class="metric-value">{{ summary.minPriceText }}</div>
        <div class="metric-sub">¥ / 套餐</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">最高单价</div>
        <div class="metric-value">{{ summary.maxPriceText }}</div>
        <div class="metric-sub">¥ / 套餐</div>
      </ElCard>
    </div>

    <!-- 说明条 -->
    <ElAlert type="info" :closable="false" class="tip-alert" show-icon>
      <template #title>
        <span>
          <b>计费关系</b>：用户支付套餐价格后，账户 Token 余额按 <code>Token 数 + 赠送 Token</code> 增加；通用模型调用按次扣费（默认 3 Token/次），由
          <router-link :to="{ name: 'AdminAiPricing' }" class="inline-link">费用设置</router-link>
          统一管控，不会受套餐影响。
        </span>
      </template>
    </ElAlert>

    <!-- 套餐列表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>套餐列表</span>
          <div class="actions small">
            <ElInput
              v-model="query.keyword"
              placeholder="套餐名称"
              clearable
              style="width: 200px"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <ElSelect v-model="query.status" clearable placeholder="状态" style="width: 120px" @change="onSearch">
              <ElOption label="启用" value="1" />
              <ElOption label="禁用" value="0" />
            </ElSelect>
            <ElButton @click="onSearch">查询</ElButton>
          </div>
        </div>
      </template>

      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取套餐列表" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="套餐列表暂不可用"
        :description="listError"
        retry-text="重新加载"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe>
          <template #empty><div class="empty-state">暂无套餐，点击「新增套餐」创建</div></template>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn prop="planName" label="套餐名称" min-width="160" show-overflow-tooltip />
          <ElTableColumn label="Token 数" width="120">
            <template #default="{ row }">
              <span class="num-text">{{ formatNumber(row.tokenAmount) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="赠送 Token" width="120">
            <template #default="{ row }">
              <span :class="{ 'bonus-text': row.bonusToken > 0 }">+{{ formatNumber(row.bonusToken) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="到账合计" width="130">
            <template #default="{ row }">
              <span class="total-text">{{ formatNumber((Number(row.tokenAmount) || 0) + (Number(row.bonusToken) || 0)) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="价格" width="110">
            <template #default="{ row }"><span class="price-text">¥{{ row.priceYuan }}</span></template>
          </ElTableColumn>
          <ElTableColumn label="单 Token 成本" width="130">
            <template #default="{ row }">
              <span class="muted">{{ tokenUnitCost(row) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="sortOrder" label="排序" width="90" />
          <ElTableColumn label="状态" width="90">
            <template #default="{ row }">
              <ElTag :type="row.status === 1 ? 'success' : 'info'" size="small">{{ row.status === 1 ? '启用' : '禁用' }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <ElButton link type="primary" size="small" @click="openEdit(row)">编辑</ElButton>
              <ElButton link type="danger" size="small" @click="onDelete(row)">删除</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="pagination-row">
          <span class="muted">共 {{ list.total }} 条</span>
          <ElPagination
            v-model:current-page="query.current"
            v-model:page-size="query.size"
            layout="total, sizes, prev, pager, next, jumper"
            :total="list.total"
            :page-sizes="[10, 20, 50, 100]"
            @change="loadList"
          />
        </div>
      </template>
    </ElCard>

    <!-- 新增/编辑对话框 -->
    <ElDialog
      v-model="dialogVisible"
      :title="form.id ? '编辑套餐' : '新增套餐'"
      width="520px"
      @close="onDialogClose"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="110px" label-position="right">
        <ElFormItem label="套餐名称" prop="planName">
          <ElInput v-model="form.planName" placeholder="如：100 Token、新人体验包" maxlength="120" show-word-limit />
        </ElFormItem>
        <ElFormItem label="Token 数" prop="tokenAmount">
          <ElInputNumber
            v-model="form.tokenAmount"
            :min="1"
            :step="100"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">用户支付后实际到账的基础 Token 数量。</div>
        </ElFormItem>
        <ElFormItem label="赠送 Token" prop="bonusToken">
          <ElInputNumber
            v-model="form.bonusToken"
            :min="0"
            :step="100"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">额外赠送的 Token，与 Token 数相加后入账；填 0 表示不赠送。</div>
        </ElFormItem>
        <ElFormItem label="价格/元" prop="priceYuan">
          <ElInputNumber
            v-model="form.priceYuan"
            :min="0.01"
            :max="1000000"
            :precision="2"
            :step="1"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">用户支付金额（人民币元）。1 元 ≈ 100 Token（默认兑换率）。</div>
        </ElFormItem>
        <ElFormItem label="排序" prop="sortOrder">
          <ElInputNumber
            v-model="form.sortOrder"
            :min="0"
            :step="10"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">数值越小越靠前；同排序时按价格升序。</div>
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSwitch
            v-model="form.enabled"
            active-text="启用"
            inactive-text="禁用"
          />
          <div class="form-tip">禁用后前台不再展示此套餐，但历史订单不受影响。</div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="onSave">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import { computed, reactive, ref } from 'vue'
  import type { FormInstance, FormRules } from 'element-plus'
  import { ElMessage, ElMessageBox } from 'element-plus'
  import {
    deleteTokenRechargePlan,
    fetchTokenRechargePlans,
    saveTokenRechargePlan
  } from '@/api/payment'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminTokenPlansPage' })

  type ListState = 'loading' | 'ready' | 'error'

  const loading = ref(false)
  const saving = ref(false)
  const listState = ref<ListState>('loading')
  const listError = ref('')
  const dialogVisible = ref(false)
  const formRef = ref<FormInstance>()

  const list = reactive<any>({ records: [], total: 0 })
  const query = reactive<any>({ current: 1, size: 20, keyword: '', status: '' })
  const form = reactive<any>({
    id: undefined,
    planName: '',
    tokenAmount: 100,
    bonusToken: 0,
    priceYuan: 1,
    sortOrder: 100,
    enabled: true
  })

  const rules: FormRules = {
    planName: [
      { required: true, message: '请输入套餐名称', trigger: 'blur' },
      { max: 120, message: '套餐名称不超过 120 个字符', trigger: 'blur' }
    ],
    tokenAmount: [{ required: true, type: 'number', min: 1, message: 'Token 数必须 ≥ 1', trigger: 'blur' }],
    priceYuan: [{ required: true, type: 'number', min: 0.01, max: 1000000, message: '价格必须在 0.01 至 1000000 元之间', trigger: 'blur' }]
  }

  const summary = computed(() => {
    const records = list.records || []
    const total = records.length
    const enabled = records.filter((r: any) => r.status === 1).length
    const prices = records.map((r: any) => Number(r.priceYuan) || 0).filter((v: number) => v > 0)
    const minPrice = prices.length ? Math.min(...prices) : null
    const maxPrice = prices.length ? Math.max(...prices) : null
    return {
      total,
      enabled,
      minPriceText: minPrice === null ? '—' : `¥${minPrice.toFixed(2)}`,
      maxPriceText: maxPrice === null ? '—' : `¥${maxPrice.toFixed(2)}`
    }
  })

  function formatNumber(value: any): string {
    const n = Number(value) || 0
    return n.toLocaleString('zh-CN')
  }

  function tokenUnitCost(row: any): string {
    const total = (Number(row.tokenAmount) || 0) + (Number(row.bonusToken) || 0)
    const price = Number(row.priceYuan) || 0
    if (total <= 0 || price <= 0) return '—'
    const unit = price / total
    return `¥${unit.toFixed(4)}/Token`
  }

  async function loadList() {
    loading.value = true
    listState.value = 'loading'
    listError.value = ''
    try {
      const params: any = { current: query.current, size: query.size }
      if (query.keyword) params.keyword = query.keyword
      if (query.status !== '' && query.status !== null && query.status !== undefined) params.status = query.status
      const data = await fetchTokenRechargePlans(params)
      if (!data || !Array.isArray(data.records)) throw new Error('充值套餐接口返回格式异常')
      Object.assign(list, data)
      listState.value = 'ready'
    } catch (error: any) {
      listError.value = error?.message || '套餐列表读取失败，请检查服务状态后重试。'
      listState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  function onSearch() {
    query.current = 1
    loadList()
  }

  function resetForm() {
    Object.assign(form, {
      id: undefined,
      planName: '',
      tokenAmount: 100,
      bonusToken: 0,
      priceYuan: 1,
      sortOrder: 100,
      enabled: true
    })
    formRef.value?.clearValidate?.()
  }

  function openCreate() {
    if (listState.value !== 'ready') {
      ElMessage.warning('套餐列表尚未就绪，请稍后再试')
      return
    }
    resetForm()
    dialogVisible.value = true
  }

  function openEdit(row: any) {
    if (!row) return
    resetForm()
    Object.assign(form, {
      id: row.id,
      planName: row.planName || '',
      tokenAmount: Number(row.tokenAmount) || 0,
      bonusToken: Number(row.bonusToken) || 0,
      priceYuan: Number(row.priceYuan) || 0,
      sortOrder: Number(row.sortOrder) ?? 100,
      enabled: row.status === 1
    })
    dialogVisible.value = true
  }

  function onDialogClose() {
    formRef.value?.clearValidate?.()
  }

  async function onSave() {
    if (!formRef.value) return
    try {
      await formRef.value.validate()
    } catch {
      return
    }
    saving.value = true
    try {
      await saveTokenRechargePlan({
        id: form.id,
        planName: form.planName?.trim(),
        tokenAmount: Number(form.tokenAmount),
        bonusToken: Number(form.bonusToken) || 0,
        priceYuan: Number(form.priceYuan),
        sortOrder: Number(form.sortOrder) ?? 100,
        status: form.enabled ? 1 : 0
      })
      dialogVisible.value = false
      await loadList()
    } catch (error: any) {
      ElMessage.error(error?.message || '套餐保存失败')
    } finally {
      saving.value = false
    }
  }

  async function onDelete(row: any) {
    if (!row?.id) return
    try {
      await ElMessageBox.confirm(
        `确认删除套餐「${row.planName}」？\n\n删除后前台将不再展示此套餐，但已生成的历史订单不受影响。`,
        '删除确认',
        { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
    try {
      await deleteTokenRechargePlan(row.id)
      await loadList()
    } catch (error: any) {
      ElMessage.error(error?.message || '套餐删除失败')
    }
  }

  loadList()
</script>

<style scoped lang="scss">
.token-plans-page {
  display: grid;
  gap: 18px;
}

.toolbar-card {
  border-radius: 18px;
}

.page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title-row h2 {
  margin: 0;
  font-size: 24px;
}

.page-title-row p {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  max-width: 720px;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.actions.small {
  flex-wrap: nowrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-grid .el-card {
  border-radius: 18px;
}

.metric-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.metric-value {
  font-size: 26px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-top: 4px;
}

.metric-sub {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-top: 4px;
}

.text-success {
  color: var(--el-color-success);
}

.tip-alert {
  border-radius: 14px;
}

.tip-alert code {
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.inline-link {
  color: var(--el-color-primary);
  text-decoration: none;
  margin: 0 2px;
}

.inline-link:hover {
  text-decoration: underline;
}

.section-card {
  border-radius: 18px;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.num-text {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.bonus-text {
  color: var(--el-color-success);
  font-weight: 600;
}

.total-text {
  color: var(--el-color-primary);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.price-text {
  color: var(--el-color-danger);
  font-weight: 600;
}

.muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.form-tip {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1100px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }
  .actions {
    justify-content: flex-start;
  }
}
</style>
