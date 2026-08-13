<template>
  <div class="rc-page">
    <section class="rc-hero">
      <div class="rc-hero-copy">
        <h2>退款关单</h2>
        <p>
          按账号配置外部注销接口：当系统同步到退款订单时，将订单发货内容按块推送给你自己的注销/回收服务，
          用于在外部系统同步关闭订单或回收卡密。全部推送成功才会标记该订单为已注销。
        </p>
      </div>
    </section>

    <section class="rc-panel card">
      <label class="rc-field">
        <span>适用账号</span>
        <select v-model="accountId" :disabled="loading" @change="loadConfig">
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
          </option>
        </select>
      </label>

      <div v-if="loadError" class="rc-error">{{ loadError }}</div>

      <template v-if="config">
        <label class="rc-switch">
          <input v-model="form.enabled" type="checkbox" />
          <span>启用退款关单</span>
        </label>

        <label class="rc-field">
          <span>外部注销接口 URL（仅 https 公网）</span>
          <input v-model="form.url" type="text" placeholder="https://example.com/refund/unregister" />
          <small>系统以表单方式 POST：delivery_content（每块发货内容）、link_url（块内首个链接）。</small>
        </label>

        <label class="rc-field">
          <span>超时时间（秒）</span>
          <input v-model.number="form.timeout" type="number" min="1" max="120" />
        </label>

        <p v-if="formError" class="rc-error">{{ formError }}</p>
        <div class="rc-actions">
          <button type="button" class="rc-primary-btn" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存配置' }}
          </button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getAccounts } from '../api/accounts.js'
import { getRefundCancelConfig, saveRefundCancelConfig } from '../api/refundCancel.js'

const accounts = ref([])
const accountId = ref('')
const config = ref(null)
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const formError = ref('')

const form = reactive({
  enabled: false,
  url: '',
  timeout: 60,
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
  try {
    const res = await getRefundCancelConfig(accountId.value)
    const data = res?.data || {}
    config.value = data
    form.enabled = !!data.enabled
    form.url = data.url || ''
    form.timeout = Number(data.timeout) || 60
  } catch (e) {
    loadError.value = e?.message || '配置加载失败'
    config.value = null
  } finally {
    loading.value = false
  }
}

async function save() {
  formError.value = ''
  if (form.enabled && !form.url.trim()) {
    formError.value = '启用退款关单时必须填写外部注销接口 URL'
    return
  }
  if (form.enabled && !/^https:\/\//.test(form.url.trim())) {
    formError.value = '为安全起见，注销接口仅支持 https 公网地址'
    return
  }
  saving.value = true
  try {
    await saveRefundCancelConfig(accountId.value, {
      enabled: form.enabled,
      url: form.url.trim(),
      timeout: Number(form.timeout) || 60,
    })
    formError.value = ''
    loadError.value = ''
    await loadConfig()
  } catch (e) {
    formError.value = e?.message || '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadAccounts()
  if (accountId.value) await loadConfig()
})
</script>

<style scoped>
.rc-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.rc-hero {
  padding: 18px 20px;
  background: linear-gradient(135deg, #0f766e 0%, #0ea5e9 100%);
  border-radius: 14px;
  color: #fff;
}

.rc-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.rc-hero-copy p {
  margin: 0;
  max-width: 800px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.94;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.rc-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  max-width: 680px;
}

.rc-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rc-field > span {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.rc-field small {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}

.rc-field select,
.rc-field input {
  height: 36px;
  padding: 0 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  color: #111827;
  outline: none;
  box-sizing: border-box;
}

.rc-field input:focus,
.rc-field select:focus {
  border-color: #0ea5e9;
  box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.12);
}

.rc-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  cursor: pointer;
}

.rc-actions {
  display: flex;
  gap: 10px;
}

.rc-primary-btn {
  height: 36px;
  padding: 0 18px;
  border: none;
  border-radius: 8px;
  background: #0ea5e9;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}

.rc-primary-btn:hover {
  background: #0284c7;
}

.rc-primary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.rc-error {
  margin: 0;
  color: #dc2626;
  font-size: 13px;
}
</style>
