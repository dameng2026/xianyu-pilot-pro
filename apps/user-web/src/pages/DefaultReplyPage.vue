<template>
  <div class="dr-page">
    <section class="dr-hero">
      <div class="dr-hero-copy">
        <h2>默认回复</h2>
        <p>
          当买家消息未命中任何关键词规则、且 AI 客服关闭时，系统按账号发送兜底回复，避免买家消息石沉大海。
          支持文本（可附带图片）与外部 API 两种回复类型，可限制同一买家仅回复一次。
        </p>
      </div>
    </section>

    <section class="dr-panel card">
      <label class="dr-field">
        <span>适用账号</span>
        <select v-model="accountId" :disabled="loading" @change="loadConfig">
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
          </option>
        </select>
      </label>

      <div v-if="loadError" class="dr-error">{{ loadError }}</div>

      <template v-if="config">
        <div class="dr-row">
          <label class="dr-switch">
            <input v-model="form.enabled" type="checkbox" />
            <span>启用默认回复</span>
          </label>
          <label class="dr-switch">
            <input v-model="form.replyOnce" type="checkbox" />
            <span>同一买家仅回复一次</span>
          </label>
        </div>

        <div class="dr-field">
          <span>回复类型</span>
          <div class="dr-radio-row">
            <label class="dr-radio">
              <input v-model="form.replyType" type="radio" value="text" />
              <span>文本（可附图片）</span>
            </label>
            <label class="dr-radio">
              <input v-model="form.replyType" type="radio" value="api" />
              <span>外部 API</span>
            </label>
          </div>
        </div>

        <template v-if="form.replyType === 'text'">
          <label class="dr-field">
            <span>回复内容</span>
            <textarea
              v-model="form.replyContent"
              rows="4"
              placeholder="例如：亲，咨询较多回复慢了，看到消息会第一时间处理哦~"
            />
            <small>支持变量：{'{send_user_name}'} 买家昵称、{'{send_user_id}'} 买家ID、{'{send_message}'} 买家消息</small>
          </label>
          <div class="dr-field">
            <span>回复图片（可选）</span>
            <div class="dr-upload-row">
              <input
                v-model="form.replyImage"
                type="text"
                placeholder="本地图片地址或闲鱼CDN图片URL"
              />
              <label class="dr-file-btn">
                上传图片
                <input
                  type="file"
                  accept="image/*"
                  :disabled="uploading"
                  @change="handleImageUpload"
                />
              </label>
            </div>
            <small>上传后自动填入图片地址；文本回复包含图片时，买家将收到图片消息。</small>
          </div>
        </template>

        <template v-else>
          <label class="dr-field">
            <span>API 地址（仅 https 公网）</span>
            <input v-model="form.apiUrl" type="text" placeholder="https://example.com/reply" />
            <small>系统 POST JSON：{ '{account_id}' }、{ '{message}' }、chat_id、item_id、send_user_id、send_user_name；返回 {{ '{reply}' }} / {{ '{data}' }} / {{ '{content}' }} / {{ '{message}' }} 或纯文本。</small>
          </label>
          <label class="dr-field">
            <span>API 超时（秒）</span>
            <input v-model.number="form.apiTimeout" type="number" min="1" max="60" />
          </label>
        </template>

        <p v-if="formError" class="dr-error">{{ formError }}</p>
        <div class="dr-actions">
          <button type="button" class="dr-primary-btn" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存配置' }}
          </button>
          <button type="button" class="dr-ghost-btn" :disabled="saving" @click="clearRecords">
            清空已回复记录
          </button>
          <button type="button" class="dr-danger-btn" :disabled="saving" @click="removeConfig">
            删除配置
          </button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { getAccounts } from '../api/accounts.js'
import {
  clearDefaultReplyRecords,
  deleteDefaultReply,
  getDefaultReply,
  saveDefaultReply,
} from '../api/defaultReply.js'
import { uploadImage } from '../api/misc.js'

const accounts = ref([])
const accountId = ref('')
const config = ref(null)
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const loadError = ref('')
const formError = ref('')

const form = reactive({
  enabled: false,
  replyType: 'text',
  replyContent: '',
  replyImage: '',
  apiUrl: '',
  apiTimeout: 30,
  replyOnce: false,
})

watch(accountId, () => {
  if (accountId.value) loadConfig()
})

async function loadAccounts() {
  try {
    const res = await getAccounts({ current: 1, size: 100 })
    const list = Array.isArray(res?.data) ? res.data : (res?.data?.records || [])
    accounts.value = list
    if (list.length) accountId.value = list[0].id
  } catch (e) {
    loadError.value = e?.message || '账号列表加载失败'
  }
}

async function loadConfig() {
  if (!accountId.value) return
  loading.value = true
  loadError.value = ''
  formError.value = ''
  try {
    const res = await getDefaultReply(accountId.value)
    const data = res?.data || {}
    config.value = data
    form.enabled = !!data.enabled
    form.replyType = data.replyType || 'text'
    form.replyContent = data.replyContent || ''
    form.replyImage = data.replyImage || ''
    form.apiUrl = data.apiUrl || ''
    form.apiTimeout = Number(data.apiTimeout) || 30
    form.replyOnce = !!data.replyOnce
  } catch (e) {
    loadError.value = e?.message || '配置加载失败'
    config.value = null
  } finally {
    loading.value = false
  }
}

async function save() {
  formError.value = ''
  if (form.replyType === 'api' && !form.apiUrl.trim()) {
    formError.value = 'API 类型必须填写 API 地址'
    return
  }
  if (form.replyType === 'text' && !form.replyContent.trim() && !form.replyImage.trim()) {
    formError.value = '文本回复请至少填写回复内容或图片'
    return
  }
  saving.value = true
  try {
    await saveDefaultReply(accountId.value, {
      enabled: form.enabled,
      replyType: form.replyType,
      replyContent: form.replyContent,
      replyImage: form.replyImage,
      apiUrl: form.apiUrl,
      apiTimeout: Number(form.apiTimeout) || 30,
      replyOnce: form.replyOnce,
    })
    formError.value = ''
    await loadConfig()
  } catch (e) {
    formError.value = e?.message || '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}

async function handleImageUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const res = await uploadImage(accountId.value, file)
    const url = res?.data?.url || res?.data?.imageUrl || res?.url
    if (!url) throw new Error('上传成功但未返回图片地址')
    form.replyImage = url
  } catch (err) {
    formError.value = err?.message || '图片上传失败'
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

async function clearRecords() {
  if (!window.confirm('确定清空该账号的“仅回复一次”记录吗？清空后买家可再次收到默认回复。')) return
  try {
    await clearDefaultReplyRecords(accountId.value)
    loadError.value = ''
  } catch (e) {
    loadError.value = e?.message || '清空失败'
  }
}

async function removeConfig() {
  if (!window.confirm('确定删除该账号的默认回复配置吗？')) return
  try {
    await deleteDefaultReply(accountId.value)
    await loadConfig()
  } catch (e) {
    loadError.value = e?.message || '删除失败'
  }
}

onMounted(async () => {
  await loadAccounts()
  if (accountId.value) await loadConfig()
})
</script>

<style scoped>
.dr-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.dr-hero {
  padding: 18px 20px;
  background: linear-gradient(135deg, #0e9f6e 0%, #1f6feb 100%);
  border-radius: 14px;
  color: #fff;
}

.dr-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.dr-hero-copy p {
  margin: 0;
  max-width: 780px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.94;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.dr-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  max-width: 760px;
}

.dr-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dr-field > span {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.dr-field small {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}

.dr-field input,
.dr-field select,
.dr-field textarea {
  width: 100%;
  padding: 9px 11px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  color: #111827;
  background: #fff;
  outline: none;
  box-sizing: border-box;
}

.dr-field textarea {
  resize: vertical;
}

.dr-field input:focus,
.dr-field select:focus,
.dr-field textarea:focus {
  border-color: #1f6feb;
  box-shadow: 0 0 0 2px rgba(31, 111, 235, 0.12);
}

.dr-row {
  display: flex;
  gap: 28px;
  flex-wrap: wrap;
}

.dr-switch,
.dr-radio {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  cursor: pointer;
}

.dr-radio-row {
  display: flex;
  gap: 22px;
}

.dr-upload-row {
  display: flex;
  gap: 10px;
}

.dr-upload-row input {
  flex: 1;
}

.dr-file-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: 38px;
  padding: 0 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  background: #fff;
  white-space: nowrap;
}

.dr-file-btn input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.dr-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.dr-primary-btn,
.dr-ghost-btn,
.dr-danger-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid transparent;
}

.dr-primary-btn {
  background: #1f6feb;
  color: #fff;
}

.dr-primary-btn:hover {
  background: #1858c0;
}

.dr-ghost-btn {
  background: #fff;
  border-color: #d1d5db;
  color: #374151;
}

.dr-ghost-btn:hover {
  border-color: #1f6feb;
  color: #1f6feb;
}

.dr-danger-btn {
  background: #fff;
  border-color: #fca5a5;
  color: #dc2626;
}

.dr-danger-btn:hover {
  background: #fef2f2;
}

.dr-primary-btn:disabled,
.dr-ghost-btn:disabled,
.dr-danger-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.dr-error {
  margin: 0;
  color: #dc2626;
  font-size: 13px;
}
</style>
