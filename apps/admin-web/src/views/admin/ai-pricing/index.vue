<template>
  <div class="ai-pricing-page">
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>费用设置</h2>
          <p>
            配置各模型的成本价与用户使用价格（售价 Token）。支持 chat 按次固定扣费、image 按张计费、按实际 Token
            计费三种模式。
          </p>
        </div>
        <div class="actions">
          <ElButton type="primary" :disabled="listState !== 'ready'" @click="openCreate">新增价格配置</ElButton>
          <ElButton :loading="loading" @click="loadAll">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <AdminDataState v-if="summaryState === 'loading'" state="loading" title="正在读取计费汇总" compact />
    <AdminDataState
      v-else-if="summaryState === 'error'"
      state="error"
      title="计费汇总暂不可用"
      :description="summaryError"
      retry-text="重试汇总"
      compact
      @retry="loadSummary"
    />

    <!-- 概览卡片 -->
    <div v-else class="summary-grid">
      <ElCard shadow="never">
        <div class="metric-label">启用模型数</div>
        <div class="metric-value">
          {{ formatSummaryMetric(summary.enabledModels) }}
        </div>
        <div class="metric-sub">已启用的价格配置</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">今日扣费 Token</div>
        <div class="metric-value">
          {{ formatSummaryMetric(summary.todayChargeTokens, true) }}
        </div>
        <div class="metric-sub">实际从用户余额扣除</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">今日成本</div>
        <div class="metric-value">{{ cost(summary.todayCostCent) }}</div>
        <div class="metric-sub">上游模型成本</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">低余额用户</div>
        <div class="metric-value" :class="{ warn: Number(summary.lowBalanceUsers) > 0 }">
          {{ formatSummaryMetric(summary.lowBalanceUsers) }}
        </div>
        <div class="metric-sub">余额 &lt; 100 Token</div>
      </ElCard>
    </div>

    <!-- 说明条 -->
    <ElAlert type="info" :closable="false" class="tip-alert" show-icon>
      <template #title>
        <span
          ><b>计费示例</b>：润色场景设置 chat 模型 —「每次成本」填 0.03 元、「每次售价 Token」填 10，则用户每次调用扣 10
          Token（按 1元=100Token 折合 0.1 元），单次利润 0.07 元。当「每次售价 Token」>0 时优先按固定价扣费，否则按实际
          Token 用量计费。</span
        >
      </template>
    </ElAlert>

    <!-- 价格配置列表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>价格配置列表</span>
          <div class="actions small">
            <ElInput
              v-model="query.keyword"
              placeholder="Provider/模型/模块"
              clearable
              style="width: 200px"
              @keyup.enter="loadList"
            />
            <ElSelect v-model="query.modelType" clearable placeholder="类型" style="width: 110px" @change="loadList">
              <ElOption label="对话 chat" value="chat" />
              <ElOption label="生图 image" value="image" />
            </ElSelect>
            <ElSelect v-model="query.enabled" clearable placeholder="状态" style="width: 110px" @change="loadList">
              <ElOption label="启用" value="1" />
              <ElOption label="禁用" value="0" />
            </ElSelect>
            <ElButton @click="loadList">查询</ElButton>
          </div>
        </div>
      </template>
      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取价格配置" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="价格配置列表暂不可用"
        :description="listError"
        retry-text="重新加载列表"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe height="520">
          <template #empty><div class="empty-state">暂无价格配置</div></template>
          <ElTableColumn prop="id" label="ID" width="60" />
          <ElTableColumn prop="modelType" label="类型" width="80">
            <template #default="scope">
              <ElTag :type="scope.row.modelType === 'image' ? 'warning' : 'primary'" size="small">{{
                scope.row.modelType === 'image' ? '生图' : '对话'
              }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="moduleKey" label="模块" min-width="140" show-overflow-tooltip />
          <ElTableColumn prop="providerName" label="Provider" min-width="100" />
          <ElTableColumn prop="modelName" label="模型" min-width="140" show-overflow-tooltip />
          <ElTableColumn label="成本价" width="110">
            <template #default="scope">
              <span class="cost-text">{{
                scope.row.modelType === 'image' ? scope.row.costPerImageText : scope.row.costPerCallText
              }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="用户售价" width="120">
            <template #default="scope">
              <span class="price-text">{{
                scope.row.modelType === 'image' ? scope.row.tokensPerImageText : scope.row.tokensPerCallText
              }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="单次利润" width="110">
            <template #default="scope">
              <span :class="profitClass(scope.row)">{{ scope.row.profitText || '—' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="billingMode" label="计费模式" width="100" />
          <ElTableColumn label="Token单价" min-width="160">
            <template #default="scope">
              <div class="cell-stack">
                <span>输入 {{ scope.row.inputPriceText }}</span>
                <span>输出 {{ scope.row.outputPriceText }}</span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="tokenExchangeRate" label="兑换率" width="90" />
          <ElTableColumn label="状态" width="75">
            <template #default="scope">
              <ElTag :type="scope.row.enabled == 1 ? 'success' : 'info'" size="small">{{
                scope.row.enabledText
              }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="130" fixed="right">
            <template #default="scope">
              <ElButton link type="primary" size="small" @click="openEdit(scope.row)">编辑</ElButton>
              <ElButton link type="danger" size="small" @click="onDelete(scope.row)">删除</ElButton>
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
            @change="loadList"
          />
        </div>
      </template>
    </ElCard>

    <!-- 编辑对话框 -->
    <ElDialog
      v-model="dialogVisible"
      :title="form.id ? '编辑价格配置' : '新增价格配置'"
      width="640px"
      @close="onDialogClose"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="120px" label-position="right">
        <ElFormItem label="模型类型" prop="modelType">
          <ElRadioGroup v-model="form.modelType" @change="onModelTypeChange">
            <ElRadioButton value="chat">对话 chat</ElRadioButton>
            <ElRadioButton value="image">生图 image</ElRadioButton>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="模块 Key">
          <ElInput v-model="form.moduleKey" placeholder="如 model-config-chat，可留空自动推断" />
        </ElFormItem>
        <ElFormItem label="Provider">
          <ElInput v-model="form.providerName" placeholder="default 或供应商名" />
        </ElFormItem>
        <ElFormItem label="模型名称" prop="modelName">
          <ElInput v-model="form.modelName" placeholder="具体模型名，或 default 表示通用" />
        </ElFormItem>

        <!-- chat 固定售价（核心） -->
        <ElDivider v-if="form.modelType === 'chat'" content-position="left">按次计费（成本与售价分离）</ElDivider>
        <template v-if="form.modelType === 'chat'">
          <ElFormItem label="每次成本(元)">
            <ElInputNumber
              v-model="form.costPerCall"
              :min="0"
              :precision="6"
              :step="0.001"
              controls-position="right"
              style="width: 100%"
            />
            <div class="form-tip">上游模型每次调用成本，如 0.03。留空 0 则按下方 Token 单价估算成本。</div>
          </ElFormItem>
          <ElFormItem label="每次售价 Token">
            <ElInputNumber
              v-model="form.tokensPerCall"
              :min="0"
              :step="1"
              controls-position="right"
              style="width: 100%"
            />
            <div class="form-tip">用户每次调用固定扣 N Token（售价）。>0 时优先按固定价扣费，与成本独立。</div>
          </ElFormItem>
        </template>

        <!-- image 按张计费 -->
        <ElDivider v-if="form.modelType === 'image'" content-position="left">按张计费</ElDivider>
        <template v-if="form.modelType === 'image'">
          <ElFormItem label="每张成本(元)">
            <ElInputNumber
              v-model="form.costPerImage"
              :min="0"
              :precision="6"
              :step="0.01"
              controls-position="right"
              style="width: 100%"
            />
          </ElFormItem>
          <ElFormItem label="每张售价 Token">
            <ElInputNumber
              v-model="form.tokensPerImage"
              :min="0"
              :step="1"
              controls-position="right"
              style="width: 100%"
            />
            <div class="form-tip">用户每张图固定扣 N Token。>0 时优先按固定价扣费。</div>
          </ElFormItem>
          <ElFormItem label="规格价格JSON">
            <ElInput
              v-model="form.specPriceJson"
              type="textarea"
              :rows="2"
              placeholder='{"1024x1024":0.05,"1024x1536":0.08}'
            />
          </ElFormItem>
        </template>

        <ElDivider content-position="left">按实际 Token 计费（可选/兜底）</ElDivider>
        <ElFormItem label="计费模式">
          <ElSelect v-model="form.billingMode" style="width: 100%">
            <ElOption label="按 Token 用量" value="token" />
            <ElOption label="按次计费" value="per_call" />
            <ElOption label="按规格计费" value="spec" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="计费单位">
          <ElSelect v-model="form.billingUnit" style="width: 100%">
            <ElOption label="1K Tokens" value="1K" />
            <ElOption label="百万 Tokens" value="百万" />
            <ElOption label="兆 Tokens" value="兆" />
          </ElSelect>
        </ElFormItem>
        <ElRow :gutter="12">
          <ElCol :span="12">
            <ElFormItem label="输入单价">
              <ElInputNumber
                v-model="form.inputPricePer1k"
                :min="0"
                :precision="6"
                :step="0.0001"
                controls-position="right"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="输出单价">
              <ElInputNumber
                v-model="form.outputPricePer1k"
                :min="0"
                :precision="6"
                :step="0.0001"
                controls-position="right"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>
        <ElRow :gutter="12">
          <ElCol :span="12">
            <ElFormItem label="缓存输入单价">
              <ElInputNumber
                v-model="form.cachedInputPricePer1k"
                :min="0"
                :precision="6"
                :step="0.0001"
                controls-position="right"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="每次附加费">
              <ElInputNumber
                v-model="form.perCallPrice"
                :min="0"
                :precision="6"
                :step="0.001"
                controls-position="right"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>
        <ElRow :gutter="12">
          <ElCol :span="12">
            <ElFormItem label="Token兑换率">
              <ElInputNumber
                v-model="form.tokenExchangeRate"
                :min="1"
                :step="10"
                controls-position="right"
                style="width: 100%"
              />
              <div class="form-tip">1 元 = N Token，默认 100</div>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="最低扣费Token">
              <ElInputNumber
                v-model="form.minChargeToken"
                :min="0"
                :step="1"
                controls-position="right"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>
        <ElFormItem label="状态">
          <ElSwitch
            v-model="form.enabled"
            :active-value="1"
            :inactive-value="0"
            active-text="启用"
            inactive-text="禁用"
          />
        </ElFormItem>
        <ElFormItem label="备注">
          <ElInput v-model="form.remark" type="textarea" :rows="2" placeholder="可选" />
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
  import type { FormInstance, FormRules } from 'element-plus'
  import { ElMessage, ElMessageBox } from 'element-plus'
  import {
    deleteModelPrice,
    getBillingSummary,
    getModelPricesPage,
    saveModelPrice,
    type BillingSummary,
    type ModelPriceForm,
    type ModelPriceRow,
  } from '@/api/billing'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminAiPricing' })

  type NumericFormField =
    | 'inputPricePer1k'
    | 'outputPricePer1k'
    | 'cachedInputPricePer1k'
    | 'perCallPrice'
    | 'tokenExchangeRate'
    | 'minChargeToken'
    | 'costPerImage'
    | 'tokensPerImage'
    | 'costPerCall'
    | 'tokensPerCall'
    | 'enabled'

  type EditableModelPriceForm = Omit<ModelPriceForm, 'id' | NumericFormField> & {
    id?: number
    inputPricePer1k: number
    outputPricePer1k: number
    cachedInputPricePer1k: number
    perCallPrice: number
    tokenExchangeRate: number
    minChargeToken: number
    costPerImage: number
    tokensPerImage: number
    costPerCall: number
    tokensPerCall: number
    enabled: number
  }

  const loading = ref(false)
  const saving = ref(false)
  const dialogVisible = ref(false)
  const formRef = ref<FormInstance>()
  const summary = ref<BillingSummary>({})
  const list = reactive({ records: [] as ModelPriceRow[], total: 0 })
  const query = reactive({
    current: 1,
    size: 20,
    keyword: '',
    modelType: '',
    enabled: '',
  })
  const summaryState = ref<'loading' | 'ready' | 'error'>('loading')
  const listState = ref<'loading' | 'ready' | 'error'>('loading')
  const summaryError = ref('')
  const listError = ref('')

  const defaultForm = (): EditableModelPriceForm => ({
    modelType: 'chat',
    providerName: 'default',
    modelName: 'default',
    billingMode: 'token',
    billingUnit: '1K',
    tokenExchangeRate: 100,
    minChargeToken: 0,
    enabled: 1,
    inputPricePer1k: 0,
    outputPricePer1k: 0,
    cachedInputPricePer1k: 0,
    perCallPrice: 0,
    costPerImage: 0,
    tokensPerImage: 0,
    costPerCall: 0,
    tokensPerCall: 0,
  })
  const form = reactive<EditableModelPriceForm>(defaultForm())
  const rules: FormRules = {
    modelType: [{ required: true, message: '请选择模型类型', trigger: 'change' }],
    modelName: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  }

  onMounted(() => {
    loadAll()
  })

  async function loadAll() {
    loading.value = true
    try {
      await Promise.all([loadSummary(), loadList()])
    } finally {
      loading.value = false
    }
  }

  async function loadSummary() {
    summaryState.value = 'loading'
    summaryError.value = ''
    try {
      const data = await getBillingSummary()
      if (!data) throw new Error('服务未返回计费汇总')
      summary.value = data
      summaryState.value = 'ready'
    } catch (error: unknown) {
      summary.value = {}
      summaryError.value = getErrorMessage(error, '计费汇总读取失败，请稍后重试。')
      summaryState.value = 'error'
    }
  }

  async function loadList() {
    loading.value = true
    listState.value = 'loading'
    listError.value = ''
    try {
      const p = await getModelPricesPage(query)
      if (!p || !Array.isArray(p.records)) throw new Error('价格配置接口返回格式异常')
      list.records = p.records
      list.total = Number.isFinite(Number(p.total)) ? Number(p.total) : p.records.length
      listState.value = 'ready'
    } catch (error: unknown) {
      listError.value = getErrorMessage(error, '价格配置读取失败，请检查服务状态后重试。')
      listState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  function openCreate() {
    if (listState.value !== 'ready') return
    replaceForm(defaultForm())
    dialogVisible.value = true
  }

  function openEdit(value: unknown) {
    if (!isModelPriceRow(value)) {
      ElMessage.error('该价格配置缺少有效 ID，暂时无法编辑，请刷新后重试')
      return
    }

    try {
      replaceForm(editableFormFromRow(value))
      dialogVisible.value = true
    } catch (error: unknown) {
      ElMessage.error(getErrorMessage(error, '该价格配置数据异常，暂时无法编辑'))
    }
  }

  function onModelTypeChange(v: string) {
    if (v === 'image' && (!form.billingMode || form.billingMode === 'token')) {
      form.billingMode = 'spec'
    }
    if (v === 'chat' && form.billingMode === 'spec') {
      form.billingMode = 'token'
    }
  }

  function onDialogClose() {
    formRef.value?.resetFields()
  }

  async function onSave() {
    if (listState.value !== 'ready') {
      ElMessage.error('价格配置列表尚未成功读取，已阻止保存')
      return
    }
    if (!formRef.value) return
    await formRef.value.validate(async (valid) => {
      if (!valid) return
      saving.value = true
      try {
        await saveModelPrice({ ...form })
        ElMessage.success('保存成功')
        dialogVisible.value = false
        await loadAll()
      } catch (error: unknown) {
        ElMessage.error(getErrorMessage(error, '保存失败'))
      } finally {
        saving.value = false
      }
    })
  }

  async function onDelete(value: unknown) {
    if (!isModelPriceRow(value)) {
      ElMessage.error('该价格配置缺少有效 ID，暂时无法删除，请刷新后重试')
      return
    }

    try {
      const providerName = displayName(value.providerName, '未知 Provider')
      const modelName = displayName(value.modelName, '未知模型')
      await ElMessageBox.confirm(`确认删除 ${providerName}/${modelName} 的价格配置？`, '提示', { type: 'warning' })
      await deleteModelPrice(value.id)
      ElMessage.success('已删除')
      await loadAll()
    } catch (error: unknown) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getErrorMessage(error, '删除失败，请稍后重试'))
      }
    }
  }

  function profitClass(value: unknown) {
    if (!isRecord(value)) return 'muted'
    const profit = finiteNumber(value.profitYuan)
    if (profit === undefined) return 'muted'
    return profit >= 0 ? 'profit-positive' : 'profit-negative'
  }

  function formatSummaryMetric(value: unknown, grouped = false): string | number {
    if (value === null || value === undefined || value === '') return '--'
    const number = finiteNumber(value)
    if (number === undefined) return '--'
    return grouped ? number.toLocaleString() : number
  }

  function cost(value: unknown): string {
    const n = finiteNumber(value)
    if (n === undefined) return '--'
    const amount = (n / 100).toFixed(4).replace(/0+$/, '').replace(/\.$/, '') || '0'
    return `¥${amount}`
  }

  function editableFormFromRow(row: ModelPriceRow): EditableModelPriceForm {
    return {
      id: row.id,
      moduleKey: row.moduleKey,
      providerName: row.providerName,
      modelName: row.modelName,
      modelType: row.modelType,
      billingMode: row.billingMode,
      billingUnit: row.billingUnit || '1K',
      inputPricePer1k: requiredFiniteNumber(row.inputPricePer1k, '输入单价', 0),
      outputPricePer1k: requiredFiniteNumber(row.outputPricePer1k, '输出单价', 0),
      cachedInputPricePer1k: requiredFiniteNumber(row.cachedInputPricePer1k, '缓存输入单价', 0),
      perCallPrice: requiredFiniteNumber(row.perCallPrice, '每次附加费', 0),
      specPriceJson: row.specPriceJson,
      tokenExchangeRate: requiredFiniteNumber(row.tokenExchangeRate, 'Token 兑换率', 100),
      minChargeToken: requiredFiniteNumber(row.minChargeToken, '最低扣费 Token', 0),
      costPerImage: requiredFiniteNumber(row.costPerImage, '每张成本', 0),
      tokensPerImage: requiredFiniteNumber(row.tokensPerImage, '每张售价 Token', 0),
      costPerCall: requiredFiniteNumber(row.costPerCall, '每次成本', 0),
      tokensPerCall: requiredFiniteNumber(row.tokensPerCall, '每次售价 Token', 0),
      enabled: requiredEnabledValue(row.enabled),
      remark: row.remark,
    }
  }

  function replaceForm(next: EditableModelPriceForm): void {
    Object.assign(form, next)
    // Object.assign does not remove optional fields left by the previous edit.
    // Explicitly clear them so "新增" can never accidentally update the last row.
    form.id = next.id
    form.moduleKey = next.moduleKey
    form.specPriceJson = next.specPriceJson
    form.remark = next.remark
  }

  function requiredEnabledValue(value: unknown): number {
    const enabled = finiteNumber(value)
    if (enabled !== 0 && enabled !== 1) {
      throw new Error('启用状态数据异常，暂时无法编辑')
    }
    return enabled
  }

  function requiredFiniteNumber(value: unknown, label: string, fallback: number): number {
    if (value === null || value === undefined || value === '') return fallback
    const number = finiteNumber(value)
    if (number === undefined) {
      throw new Error(`${label}数据异常，暂时无法编辑`)
    }
    return number
  }

  function finiteNumber(value: unknown): number | undefined {
    if (typeof value === 'number') return Number.isFinite(value) ? value : undefined
    if (typeof value !== 'string' || value.trim() === '') return undefined
    const number = Number(value)
    return Number.isFinite(number) ? number : undefined
  }

  function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
  }

  function isModelPriceRow(value: unknown): value is ModelPriceRow {
    return isRecord(value) && typeof value.id === 'number' && Number.isSafeInteger(value.id) && value.id > 0
  }

  function displayName(value: unknown, fallback: string): string {
    return typeof value === 'string' && value.trim() ? value.trim() : fallback
  }

  function getErrorMessage(error: unknown, fallback: string): string {
    return error instanceof Error && error.message.trim() ? error.message : fallback
  }
</script>

<style scoped>
  .ai-pricing-page {
    padding: 16px;
  }
  .toolbar-card {
    margin-bottom: 16px;
  }
  .page-title-row,
  .table-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .page-title-row h2 {
    margin: 0 0 6px;
    font-size: 20px;
  }
  .page-title-row p {
    margin: 0;
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .actions.small {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }
  .metric-label {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
  .metric-value {
    font-size: 24px;
    font-weight: 700;
    margin: 8px 0;
  }
  .metric-sub {
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
  .metric-value.warn {
    color: var(--el-color-danger);
  }
  .tip-alert {
    margin-bottom: 16px;
  }
  .section-card {
    margin-bottom: 16px;
  }
  .cell-stack {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .cost-text {
    color: var(--el-color-info);
    font-weight: 600;
  }
  .price-text {
    color: var(--el-color-primary);
    font-weight: 600;
  }
  .profit-positive {
    color: var(--el-color-success);
    font-weight: 600;
  }
  .profit-negative {
    color: var(--el-color-danger);
    font-weight: 600;
  }
  .muted {
    color: var(--el-text-color-secondary);
  }
  .empty-state {
    padding: 40px 0;
    text-align: center;
    color: var(--el-text-color-secondary);
  }
  .pagination-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 16px;
  }
  .form-tip {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    line-height: 1.4;
    margin-top: 4px;
  }
  @media (max-width: 1200px) {
    .summary-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (max-width: 640px) {
    .summary-grid {
      grid-template-columns: 1fr;
    }
    .page-title-row,
    .table-header {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
