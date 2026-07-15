<template>
  <div>
    <div class="page-head">
      <div>
        <h1>发货声明</h1>
        <p>配置发货声明文案与生效范围，买家确认声明后进入正式发货流程</p>
      </div>
    </div>

    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <div v-if="loading" class="statement-loading" role="status">声明配置加载中...</div>
    <EmptyState v-else-if="loadError" variant="error" title="发货声明配置暂时无法加载" :description="loadError">
      <template #actions><AppButton @click="load">重新加载</AppButton></template>
    </EmptyState>

    <div v-else class="statement-layout">
      <div class="statement-main">
        <CardPanel title="发货声明配置">
          <div class="option-line" style="cursor:pointer" @click="toggleEnabled">
            <span>启用发货声明</span>
            <ToggleSwitch :on="enabled" />
          </div>
          <p class="field-desc">开启后，买家付款后系统先发送声明文案，买家确认后再进入自动发货流程</p>

          <div class="form-row" style="margin-top:16px">
            <label>生效范围</label>
            <select v-model="scope" class="input" style="width:100%">
              <option value="all">全店所有自动发货商品生效</option>
              <option value="specific">仅对单独启用声明的商品生效</option>
            </select>
          </div>

          <div class="form-row" style="margin-top:16px">
            <label>声明文案</label>
            <textarea
              ref="textareaRef"
              v-model="content"
              placeholder="请输入发货声明内容，支持插入变量..."
              rows="8"
              :disabled="!enabled"
            ></textarea>
          </div>

          <div class="var-buttons">
            <span class="var-label">插入变量：</span>
            <button
              v-for="v in variables"
              :key="v.key"
              class="var-chip"
              :disabled="!enabled"
              @click="insertVariable(v.key)"
            >
{{ v.key }}
</button>
          </div>

          <div class="form-actions">
            <AppButton type="primary" :loading="saving" :disabled="!settingsAvailable" @click="save">保存配置</AppButton>
            <AppButton :disabled="saving || !enabled || !settingsAvailable" @click="reset">恢复默认</AppButton>
          </div>
        </CardPanel>
      </div>

      <div class="statement-side">
        <CardPanel title="预览">
          <div class="preview-box">
            <div v-if="!enabled" class="subtle" style="text-align:center;padding:20px 0">发货声明已禁用，启用后可预览效果</div>
            <div v-else-if="!previewText" class="subtle" style="text-align:center;padding:20px 0">点击下方按钮预览声明效果</div>
            <pre v-else class="preview-content">{{ previewText }}</pre>
          </div>
          <div style="margin-top:12px">
            <AppButton :disabled="!enabled || !settingsAvailable || previewing" @click="refreshPreview">{{ previewing ? '预览中...' : '预览声明' }}</AppButton>
          </div>
        </CardPanel>

        <CardPanel title="变量说明" style="margin-top:16px">
          <div class="var-desc-list">
            <div v-for="v in variables" :key="v.key" class="var-desc-item">
              <code class="var-desc-key">{{ v.key }}</code>
              <span class="var-desc-text">{{ v.desc }}</span>
            </div>
          </div>
        </CardPanel>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import EmptyState from '../components/EmptyState.vue'
import { getDeliveryStatement, previewDeliveryStatement, saveDeliveryStatement, toggleDeliveryStatement } from '../api/autoDelivery.js'

const error = ref('')
const success = ref('')
const loading = ref(true)
const loadError = ref('')
const settingsAvailable = ref(false)
const saving = ref(false)
const previewing = ref(false)
const textareaRef = ref(null)
const previewText = ref('')

const enabled = ref(false)
const content = ref('')
const scope = ref('all')

const variables = [
  { key: '{订单编号}', desc: '订单编号' },
  { key: '{商品标题}', desc: '商品标题' },
  { key: '{买家昵称}', desc: '买家昵称' },
  { key: '{发货确认链接}', desc: '发货确认链接' }
]

const defaultContent = `订单编号：{订单编号}

您好，该订单包含的商品为虚拟商品，发货后不支持退换。如无异议，请点击下方链接确认发货。

{发货确认链接}`

async function load() {
  error.value = ''
  loadError.value = ''
  loading.value = true
  settingsAvailable.value = false
  try {
    const res = await getDeliveryStatement()
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('发货声明配置响应格式异常')
    const enabledValue = data.enabled
    if (!(typeof enabledValue === 'boolean' || enabledValue === 0 || enabledValue === 1)) {
      throw new Error('发货声明启用状态响应格式异常')
    }
    if (!['all', 'specific'].includes(data.scope)) throw new Error('发货声明生效范围响应格式异常')
    if (data.content != null && typeof data.content !== 'string') throw new Error('发货声明内容响应格式异常')
    enabled.value = enabledValue === true || enabledValue === 1
    content.value = data.content || defaultContent
    scope.value = data.scope
    settingsAvailable.value = true
  } catch (e) {
    loadError.value = `${e.message || '声明内容加载失败'}；配置成功加载前不会应用或覆盖任何设置。`
  } finally {
    loading.value = false
  }
}

async function toggleEnabled() {
  if (!settingsAvailable.value) return
  if (saving.value) return
  error.value = ''
  success.value = ''
  const newVal = !enabled.value
  enabled.value = newVal
  previewText.value = ''
  try {
    await toggleDeliveryStatement(newVal)
    success.value = newVal ? '发货声明已启用' : '发货声明已禁用'
  } catch (e) {
    enabled.value = !newVal
    error.value = e.message || '状态切换失败'
  }
}

function insertVariable(key) {
  const textarea = textareaRef.value
  if (!textarea) return
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const text = content.value
  content.value = text.substring(0, start) + key + text.substring(end)
  nextTick(() => {
    textarea.focus()
    textarea.selectionStart = textarea.selectionEnd = start + key.length
  })
}

async function refreshPreview() {
  if (!settingsAvailable.value) return
  if (!content.value.trim()) {
    error.value = '请先输入声明文案'
    return
  }
  if (previewing.value) return
  error.value = ''
  previewing.value = true
  try {
    const res = await previewDeliveryStatement({ content: content.value, scope: scope.value })
    const preview = res?.data?.preview
    if (typeof preview !== 'string' || !preview.trim()) throw new Error('预览响应格式异常，未覆盖当前预览')
    previewText.value = preview
  } catch (e) {
    error.value = e.message || '预览失败'
  } finally {
    previewing.value = false
  }
}

function reset() {
  if (!settingsAvailable.value) return
  content.value = defaultContent
  scope.value = 'all'
  success.value = ''
  error.value = ''
  previewText.value = ''
}

async function save() {
  if (!settingsAvailable.value) return
  if (saving.value) return
  error.value = ''
  success.value = ''
  if (!content.value.trim()) {
    error.value = '请输入声明文案'
    return
  }
  saving.value = true
  try {
    await saveDeliveryStatement({
      enabled: enabled.value,
      content: content.value,
      scope: scope.value
    })
    success.value = '发货声明配置已保存'
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function onHeaderAction(event) {
  if (event.detail === 'statement-save') save()
  if (event.detail === 'statement-preview') refreshPreview()
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  load()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
.statement-loading {
  padding: 48px;
  text-align: center;
  color: #667491;
}

.page-head {
  height: 62px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-right: 260px;
}
.page-head h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.1;
  letter-spacing: .3px;
}
.page-head p {
  margin: 10px 0 0;
  color: #667491;
  font-size: 15px;
}
.statement-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  gap: 18px;
}
.statement-main {
  min-width: 0;
}
.statement-side {
  min-width: 0;
}
.preview-box {
  border: 1px solid #e8eef8;
  border-radius: 12px;
  padding: 12px;
  background: #fbfdff;
  min-height: 80px;
}
.preview-content {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0;
  color: #333;
  line-height: 1.6;
  font-size: 14px;
}
.var-buttons {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
}
.var-label {
  color: #667085;
  font-size: 13px;
  margin-right: 2px;
  white-space: nowrap;
}
.var-chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 10px;
  background: #fff;
  border: 1px solid #dbe8ff;
  border-radius: 7px;
  font-size: 12px;
  color: #2d6ae3;
  cursor: pointer;
  font-weight: 650;
  transition: all .15s;
  white-space: nowrap;
}
.var-chip:hover:not(:disabled) {
  background: #e0e8ff;
  border-color: #b8ceff;
  transform: translateY(-1px);
}
.var-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.var-desc-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.var-desc-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  background: #f5f7fa;
  border-radius: 8px;
}
.var-desc-key {
  background: #eef2f7;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #0d6bff;
  white-space: nowrap;
}
.var-desc-text {
  color: #344054;
  font-size: 13px;
}
.field-desc {
  color: #667085;
  font-size: 13px;
  margin: 6px 0 0 0;
  line-height: 1.4;
}
.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-row label {
  font-size: 13px;
  font-weight: 700;
  color: #34425d;
}
.form-row textarea {
  width: 100%;
  min-height: 110px;
  padding: 12px;
  border: 1px solid #e7edf7;
  border-radius: 7px;
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
  outline: none;
}
.form-row textarea:focus {
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13,107,255,.1);
}
.form-actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
.subtle {
  color: #758198;
  font-size: 13px;
}
.success {
  background: #ecfdf3;
  color: #067647;
  border-color: #abefc6;
}
@media (max-width:1200px) {
  .statement-layout {
    grid-template-columns: 1fr;
  }
  .page-head {
    padding-right: 0;
  }
}
</style>
