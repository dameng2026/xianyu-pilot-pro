<template>
  <section class="config-card">
    <div class="config-card__header">
      <div>
        <div class="config-card__title-row">
          <h3 class="config-card__title">{{ section.title }}</h3>
          <span class="config-card__status">
            {{ enabled ? section.statusText || '已启用' : '未启用' }}
          </span>
        </div>
        <p class="config-card__desc">{{ section.description }}</p>
      </div>
    </div>

    <AdminDataState
      v-if="loadState === 'loading'"
      state="loading"
      title="正在读取模型配置"
      :retryable="false"
      compact
    />
    <AdminDataState
      v-else-if="loadState === 'error'"
      state="error"
      title="模型配置暂时不可用"
      :description="loadError"
      compact
      @retry="loadRecord"
    />

    <template v-else>

    <div class="config-form-grid">
      <div
        v-for="field in sectionFields"
        :key="field.prop"
        class="field-row"
        :class="{
          'is-textarea': field.type === 'textarea',
          'is-full': field.type === 'textarea'
        }"
      >
        <label class="field-label">{{ field.label }}</label>

        <div class="field-control-wrap">
          <ElSelect
            v-if="field.type === 'select'"
            v-model="formData[field.prop]"
            class="field-control"
            :placeholder="field.placeholder || '请选择'"
            @change="handleFieldChange"
          >
            <ElOption
              v-for="option in field.options || []"
              :key="option"
              :label="option"
              :value="option"
            />
          </ElSelect>

          <ElInput
            v-else-if="field.type === 'password'"
            v-model="formData[field.prop]"
            class="field-control"
            type="password"
            :placeholder="field.placeholder"
            show-password
            @input="handleFieldChange"
          >
            <template #suffix>
              <ElIcon class="field-icon"><View /></ElIcon>
            </template>
          </ElInput>

          <ElInputNumber
            v-else-if="field.type === 'number'"
            v-model="formData[field.prop]"
            class="field-control field-control--number"
            controls-position="right"
            :min="field.min"
            :max="field.max"
            :step="field.step || 1"
            @change="handleFieldChange"
          />

          <ElSwitch
            v-else-if="field.type === 'switch'"
            v-model="formData[field.prop]"
            class="field-switch"
            inline-prompt
            @change="handleSwitchFieldChange(field.prop)"
          />

          <ElInput
            v-else-if="field.type === 'textarea'"
            v-model="formData[field.prop]"
            class="field-control"
            type="textarea"
            resize="none"
            :rows="field.rows || 4"
            :maxlength="field.maxlength"
            :show-word-limit="Boolean(field.maxlength)"
            :placeholder="field.placeholder"
            @input="handleFieldChange"
          />

          <ElAlert
            v-else-if="field.type === 'tip'"
            :title="field.placeholder || field.label || ''"
            type="info"
            :closable="false"
            show-icon
            class="field-tip"
          />

          <ElInput
            v-else
            v-model="formData[field.prop]"
            class="field-control"
            :placeholder="field.placeholder"
            @input="handleFieldChange"
          />
        </div>

        <div class="field-pass" :class="{ 'is-active': getFieldPassed(field) }">
          <ElIcon><CircleCheck /></ElIcon>
          <span>{{ field.passText || '校验通过' }}</span>
        </div>
      </div>
    </div>

    <div class="action-row">
      <ElButton class="action-btn" @click="handleTest" :loading="testing">测试连接</ElButton>
      <ElButton class="action-btn" @click="handleFetchModels" :loading="fetchingModels">
        获取模型列表
      </ElButton>
      <ElButton class="action-btn" @click="handleReset">重置</ElButton>
      <ElButton
        class="action-btn action-btn--primary"
        type="primary"
        @click="handleSave"
        :loading="saving"
      >
        保存配置
      </ElButton>
    </div>

    <div v-if="testResult" class="test-result" :class="testResult.ok ? 'is-success' : 'is-fail'">
      <ElIcon :size="18">
        <CircleCheck v-if="testResult.ok" />
        <WarningFilled v-else />
      </ElIcon>
      <div class="test-result__body">
        <span class="test-result__label">{{ testResult.ok ? '测试通过' : '测试失败' }}</span>
        <span class="test-result__message">{{ testResult.message }}</span>
        <span v-if="testResult.durationMs" class="test-result__duration">耗时 {{ testResult.durationMs }}ms</span>
      </div>
    </div>
    </template>
  </section>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref } from 'vue'
  import { CircleCheck, View, WarningFilled } from '@element-plus/icons-vue'
  import { ElMessage } from 'element-plus'
  import { selectSafeServerMessage } from '@/utils/http/error-policy'
  import {
    getModelConfigRecord,
    saveModelConfigRecord,
    testModelConfigConnection,
    fetchModelList,
    updateModelConfigEnabled
  } from '@/api/admin'

  export interface ModelConfigField {
    prop: string
    label: string
    placeholder?: string
    type?: 'text' | 'password' | 'number' | 'select' | 'textarea' | 'switch' | 'tip'
    options?: string[]
    rows?: number
    maxlength?: number
    required?: boolean
    min?: number
    max?: number
    step?: number
    passText?: string
  }

  export interface ModelConfigSection {
    key: string
    title: string
    moduleKey: string
    description: string
    statusText?: string
    fields: ModelConfigField[]
  }

  export interface SectionStatePayload {
    key: string
    configured: boolean
    enabled: boolean
    tested: boolean
  }

  export interface ModelConfigFormExpose {
    save: () => Promise<void>
    reset: () => Promise<void>
    reload: () => Promise<void>
  }

  const props = defineProps<{
    section: ModelConfigSection
  }>()

  const emit = defineEmits<{
    change: [payload: SectionStatePayload]
  }>()

  const saving = ref(false)
  const testing = ref(false)
  const fetchingModels = ref(false)
  const recordId = ref<number | null>(null)
  const loadState = ref<'loading' | 'ready' | 'error'>('loading')
  const loadError = ref('')
  const tested = ref(false)
  const testResult = ref<{
    ok: boolean
    message: string
    durationMs?: number
    responseSummary?: string
  } | null>(null)
  const formData = reactive<Record<string, any>>({})
  const initialData = ref('')

  const enabled = computed(() => {
    if ('enabled' in formData) {
      return Boolean(formData.enabled)
    }
    return true
  })

  const sectionFields = computed(() => {
    const seen = new Set<string>()
    const deduped = props.section.fields.filter((field) => {
      if (seen.has(field.prop)) {
        return false
      }
      seen.add(field.prop)
      return true
    })

    const isImageSection = ['image', 'image2', 'image3'].includes(props.section.key)
    if (!isImageSection || deduped.some(field => field.prop === 'providerDocText')) {
      return deduped
    }

    const docField: ModelConfigField = {
      prop: 'providerDocText',
      label: '模型说明/文档正文',
      placeholder: '可粘贴接入文档、异步轮询说明、限制、错误码等内容',
      type: 'textarea',
      rows: 8,
      passText: '校验通过'
    }
    const insertAt = deduped.findIndex(field => field.prop === 'providerDocUrl')
    if (insertAt === -1) {
      return [...deduped, docField]
    }
    return [...deduped.slice(0, insertAt + 1), docField, ...deduped.slice(insertAt + 1)]
  })

  function buildDefaultValue(field: ModelConfigField) {
    if (field.type === 'tip') {
      return undefined
    }
    if (field.prop === 'billingMode') {
      return props.section.key === 'image' || props.section.key === 'image2' || props.section.key === 'image3'
        ? '按次计费（每张图片固定费用）'
        : '按Token计费（按输入/输出Token数量计费）'
    }
    if (field.prop === 'billingUnit') {
      return '1K Tokens'
    }
    if (field.prop === 'cost') {
      return 0
    }
    if (field.prop === 'tokenExchangeRate') {
      return 100
    }
    if (field.prop === 'tokensPerImage') {
      return 50
    }
    if (field.prop === 'providerMode') {
      // 生图模型对接方式默认走 OpenAI 兼容同步接口，保证历史配置向后兼容
      return 'openai-compatible'
    }
    if (field.prop === 'defaultSystemPrompt') {
      return '生成一张真实、干净、适合闲鱼商品发布的商品主图。突出商品主体，背景简洁，避免文字水印和夸大宣传。'
    }
    if (field.type === 'number') {
      return field.min ?? 0
    }
    if (field.type === 'switch') {
      return true
    }
    return ''
  }

  function normalizePayload(data?: Record<string, any> | null) {
    sectionFields.value.forEach((field) => {
      if (field.type === 'tip') return
      const nextValue = data?.[field.prop]
      formData[field.prop] =
        nextValue === undefined || nextValue === null ? buildDefaultValue(field) : nextValue
    })

    if (!('enabled' in formData)) {
      formData.enabled = true
    }

    if (data?.status !== undefined && !('enabled' in data)) {
      formData.enabled = !['禁用', '0', 'false'].includes(String(data.status))
    }
  }

  function getPersistPayload() {
    const payload: Record<string, any> = {}
    sectionFields.value.forEach((field) => {
      if (field.type === 'tip') return
      payload[field.prop] = formData[field.prop]
    })
    payload.status = enabled.value ? '正常' : '禁用'
    if (recordId.value) {
      payload.id = recordId.value
    }
    return payload
  }

  function updateState() {
    const configured = sectionFields.value.some((field) => {
      if (field.type === 'tip') return false
      const value = formData[field.prop]
      if (field.type === 'switch') {
        return true
      }
      return String(value ?? '').trim() !== ''
    })

    emit('change', {
      key: props.section.key,
      configured,
      enabled: enabled.value,
      tested: tested.value
    })
  }

  function getFieldPassed(field: ModelConfigField) {
    if (field.type === 'tip' || field.type === 'switch') {
      return true
    }
    if (!field.required) {
      return String(formData[field.prop] ?? '').trim() !== '' || tested.value
    }
    return String(formData[field.prop] ?? '').trim() !== ''
  }

  function handleFieldChange() {
    tested.value = false
    testResult.value = null
    updateState()
  }

  async function handleSwitchFieldChange(prop: string) {
    if (loadState.value !== 'ready') return
    tested.value = false
    if (prop === 'enabled' && recordId.value) {
      await updateModelConfigEnabled(
        props.section.moduleKey,
        recordId.value,
        formData.enabled ? '正常' : '禁用'
      )
    }
    updateState()
  }

  async function loadRecord() {
    loadState.value = 'loading'
    loadError.value = ''
    try {
      const record = await getModelConfigRecord(props.section.moduleKey)
      recordId.value = record?.id ? Number(record.id) : null
      normalizePayload(record)
      tested.value = false
      testResult.value = null
      initialData.value = JSON.stringify(getPersistPayload())
      loadState.value = 'ready'
      updateState()
    } catch {
      recordId.value = null
      initialData.value = ''
      loadState.value = 'error'
      loadError.value = '无法确认线上配置，已禁止保存、测试和切换。请重试或联系运维人员。'
      emit('change', {
        key: props.section.key,
        configured: false,
        enabled: false,
        tested: false
      })
    }
  }

  async function handleSave() {
    if (loadState.value !== 'ready') {
      ElMessage.warning('配置尚未成功读取，当前不能保存')
      return
    }
    const missingField = sectionFields.value.find((field) => {
      if (!field.required || field.type === 'switch' || field.type === 'tip') {
        return false
      }
      return String(formData[field.prop] ?? '').trim() === ''
    })

    if (missingField) {
      ElMessage.warning(`请完善${missingField.label}`)
      return
    }

    saving.value = true
    try {
      const saved = await saveModelConfigRecord(props.section.moduleKey, getPersistPayload())
      if (saved?.id) {
        recordId.value = Number(saved.id)
      }
      initialData.value = JSON.stringify(getPersistPayload())
      ElMessage.success('保存配置成功')
      updateState()
    } finally {
      saving.value = false
    }
  }

  async function handleTest() {
    if (loadState.value !== 'ready') {
      ElMessage.warning('配置尚未成功读取，当前不能测试连接')
      return
    }
    testing.value = true
    testResult.value = null
    try {
      let payload = getPersistPayload()

      // 对于非通用配置模块，需要从通用配置中获取 baseUrl 和 apiKey
      if (props.section.key !== 'general' && (!payload.baseUrl || !payload.apiKey)) {
        const generalRecord = await getModelConfigRecord('model-config-general')
        if (generalRecord) {
          payload = {
            ...payload,
            baseUrl: generalRecord.baseUrl || payload.baseUrl,
            apiKey: generalRecord.apiKey || payload.apiKey
          }
        }
      }

      const result = await testModelConfigConnection(props.section.moduleKey, payload)
      const resultMessage = selectSafeServerMessage(
        result.message,
        result.ok ? '连接成功' : '连接失败'
      )
      const responseSummary = selectSafeServerMessage(result.responseSummary, '')
      tested.value = result.ok
      testResult.value = {
        ok: result.ok,
        message: resultMessage,
        durationMs: result.durationMs,
        responseSummary
      }
      if (result.ok) {
        const summary = responseSummary ? ` (${responseSummary})` : ''
        const duration = result.durationMs ? `，耗时 ${result.durationMs}ms` : ''
        ElMessage.success(`${resultMessage}${summary}${duration}`)
      } else {
        ElMessage.warning(resultMessage)
      }
      updateState()
    } finally {
      testing.value = false
    }
  }

  async function handleFetchModels() {
    if (loadState.value !== 'ready') {
      ElMessage.warning('配置尚未成功读取，当前不能获取模型列表')
      return
    }
    fetchingModels.value = true
    try {
      let payload = getPersistPayload()

      // 对于非通用配置模块，需要从通用配置中获取 baseUrl 和 apiKey
      if (props.section.key !== 'general' && (!payload.baseUrl || !payload.apiKey)) {
        const generalRecord = await getModelConfigRecord('model-config-general')
        if (generalRecord) {
          payload = {
            ...payload,
            baseUrl: generalRecord.baseUrl || payload.baseUrl,
            apiKey: generalRecord.apiKey || payload.apiKey
          }
        }
      }

      if (!payload.baseUrl || !payload.apiKey) {
        ElMessage.warning('请先填写 Base URL 和 API Key')
        return
      }

      const result = await fetchModelList(props.section.moduleKey, {
        id: recordId.value,
        baseUrl: payload.baseUrl,
        apiKey: payload.apiKey
      })

      if (result.ok && result.models.length > 0) {
        ElMessage.success(`获取到 ${result.models.length} 个模型`)
      } else {
        ElMessage.warning(selectSafeServerMessage(result.message, '未获取到模型列表'))
      }
    } finally {
      fetchingModels.value = false
    }
  }

  async function handleReset() {
    if (!initialData.value) {
      await loadRecord()
      return
    }
    const parsed = JSON.parse(initialData.value)
    recordId.value = parsed.id ? Number(parsed.id) : recordId.value
    normalizePayload(parsed)
    tested.value = false
    testResult.value = null
    updateState()
  }

  defineExpose<ModelConfigFormExpose>({
    save: handleSave,
    reset: handleReset,
    reload: loadRecord
  })

  onMounted(async () => {
    await loadRecord()
  })
</script>

<style scoped>
  .config-card {
    padding: 18px 18px 20px;
    border-radius: 18px;
    border: 1px solid #e9edf4;
    background: #fff;
    box-shadow: 0 10px 26px rgba(24, 39, 75, 0.05);
  }

  .config-card__header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
  }

  .config-card__title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 6px;
  }

  .config-card__title {
    margin: 0;
    font-size: 18px;
    line-height: 1.2;
    color: #2f3545;
    font-weight: 700;
  }

  .config-card__status {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 56px;
    height: 28px;
    padding: 0 12px;
    border-radius: 8px;
    background: #dbf8e7;
    color: #3abf72;
    font-size: 13px;
    font-weight: 700;
  }

  .config-card__desc {
    margin: 0;
    font-size: 13px;
    color: #99a1b2;
    font-weight: 500;
  }

  .config-form-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .field-row {
    display: grid;
    grid-template-columns: 104px minmax(0, 1fr) 92px;
    align-items: center;
    gap: 12px;
  }

  .field-row.is-textarea {
    align-items: start;
  }

  .field-row.is-full {
    grid-template-columns: 104px minmax(0, 1fr) 92px;
  }

  .field-label {
    font-size: 13px;
    color: #778096;
    font-weight: 600;
  }

  .field-control-wrap {
    min-width: 0;
  }

  .field-control {
    width: 100%;
  }

  .field-control--number {
    width: 100%;
  }

  .field-switch {
    --el-switch-on-color: #4d78ff;
    --el-switch-off-color: #cfd6e4;
  }

  .field-tip {
    width: 100%;
    margin: 4px 0;
  }

  .field-pass {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    justify-self: end;
    font-size: 12px;
    color: #c1c7d4;
    white-space: nowrap;
  }

  .field-pass.is-active {
    color: #3ac16f;
  }

  .action-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-top: 18px;
  }

  .action-btn {
    height: 38px;
    border-radius: 8px;
    border-color: #dde3ef;
    color: #6d768a;
    background: #fff;
  }

  .action-btn--primary {
    border-color: #4b78ff;
    background: linear-gradient(180deg, #5d89ff 0%, #4b78ff 100%);
    color: #fff;
  }

  .test-result {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 16px;
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.4;
  }

  .test-result.is-success {
    background: #e8f8ee;
    border: 1px solid #b8e6cc;
    color: #1d7a45;
  }

  .test-result.is-success .el-icon {
    color: #3abf72;
  }

  .test-result.is-fail {
    background: #fef0ef;
    border: 1px solid #fad1cf;
    color: #c34138;
  }

  .test-result.is-fail .el-icon {
    color: #f56c6c;
  }

  .test-result__body {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    min-width: 0;
  }

  .test-result__label {
    font-weight: 700;
    white-space: nowrap;
  }

  .test-result__message {
    color: inherit;
    word-break: break-all;
  }

  .test-result__duration {
    opacity: 0.7;
    white-space: nowrap;
  }

  :deep(.el-input__wrapper),
  :deep(.el-select__wrapper),
  :deep(.el-textarea__inner),
  :deep(.el-input-number .el-input__wrapper) {
    min-height: 36px;
    border-radius: 8px;
    box-shadow: none;
    background: #fff;
    border: 1px solid #dde3ef;
  }

  :deep(.el-input__wrapper.is-focus),
  :deep(.el-select__wrapper.is-focused),
  :deep(.el-textarea__inner:focus),
  :deep(.el-input-number .el-input__wrapper.is-focus) {
    border-color: #7ea0ff;
    box-shadow: 0 0 0 2px rgba(77, 120, 255, 0.12);
  }

  :deep(.el-input-number) {
    width: 100%;
  }

  :deep(.el-textarea__inner) {
    padding-top: 9px;
  }

  :deep(.el-input__count),
  :deep(.el-textarea__count) {
    color: #9ca3b5;
  }

  .field-icon {
    color: #a4adbe;
  }

  @media (max-width: 1280px) {
    .field-row {
      grid-template-columns: 96px minmax(0, 1fr);
    }

    .field-pass {
      grid-column: 2;
      justify-self: start;
      margin-top: -4px;
    }

    .action-row {
      grid-template-columns: 1fr;
    }
  }
</style>
