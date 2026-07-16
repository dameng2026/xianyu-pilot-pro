<template>
  <div class="sync-page">
    <div v-if="loading" class="sync-loading">配置加载中...</div>
    <div v-else-if="loadError" class="sync-load-error" role="alert">
      <strong>数据同步配置暂时无法加载</strong>
      <p>{{ loadError }}</p>
      <button type="button" class="sync-retry-btn" @click="load">重新加载</button>
    </div>
    <div v-else class="sync-grid">
      <div class="sync-main">
        <!-- CardPanel 1: 连接配置 -->
        <CardPanel title="连接配置" desc="目标线上服务器的连接信息">
          <div class="sync-form">
            <div class="sync-row">
              <label class="sync-label">目标服务器地址</label>
              <input
                v-model="form.targetBaseUrl"
                type="text"
                class="sync-input"
                placeholder="https://api.example.com"
                :disabled="!settingsAvailable"
              />
              <p class="sync-hint">线上 core-api 的 baseURL（需以 https:// 开头）</p>
            </div>

            <div class="sync-row">
              <label class="sync-label">目标账号用户名</label>
              <input
                v-model="form.targetUsername"
                type="text"
                class="sync-input"
                placeholder="slfasd"
                :disabled="!settingsAvailable"
              />
              <p class="sync-hint">线上 sys_user.username，同步数据将写入该账号名下</p>
            </div>

            <div class="sync-row">
              <label class="sync-label">同步 API Token</label>
              <input
                v-model="form.targetToken"
                type="password"
                class="sync-input"
                placeholder="线上 DATA_SYNC_API_TOKEN 环境变量值"
                :disabled="!settingsAvailable"
                autocomplete="off"
              />
              <p class="sync-hint">线上服务器配置的同步鉴权 token（至少 32 字符）</p>
            </div>

            <div class="sync-actions">
              <button
                type="button"
                class="sync-save-btn"
                :disabled="saving || !settingsAvailable"
                @click="save"
              >{{ saving ? '保存中...' : '保存配置' }}</button>
              <button
                type="button"
                class="sync-ping-btn"
                :disabled="pinging || !settingsAvailable"
                @click="ping"
              >{{ pinging ? '测试中...' : '测试连接' }}</button>
            </div>
          </div>
        </CardPanel>

        <!-- CardPanel 2: 同步范围 -->
        <CardPanel title="同步范围" desc="以下配置将全量覆盖到目标账号">
          <div class="sync-scope">
            <div class="sync-scope-section">
              <h4 class="sync-scope-title">将同步的数据</h4>
              <ul class="sync-scope-list">
                <li><span class="sync-tag sync-tag-blue">闲鱼账号</span> Cookie（解密后重新加密）、账号信息</li>
                <li><span class="sync-tag sync-tag-blue">工作流</span> 工作流定义、节点、连线</li>
                <li><span class="sync-tag sync-tag-blue">AI 客服</span> 人设、知识库、自动回复规则、模型配置</li>
                <li><span class="sync-tag sync-tag-blue">自动发货</span> 发货规则、发货模板、发货声明</li>
                <li><span class="sync-tag sync-tag-blue">货源库</span> 卡密组、卡密项（保留使用状态）</li>
                <li><span class="sync-tag sync-tag-blue">通知设置</span> 通知偏好配置</li>
              </ul>
            </div>
            <div class="sync-scope-section">
              <h4 class="sync-scope-title sync-scope-warn">不同步的数据</h4>
              <ul class="sync-scope-list">
                <li><span class="sync-tag sync-tag-gray">商品数据</span> 线上可自行获取</li>
                <li><span class="sync-tag sync-tag-gray">订单数据</span> 线上可自行获取</li>
                <li><span class="sync-tag sync-tag-gray">消息数据</span> 线上可自行获取</li>
                <li><span class="sync-tag sync-tag-gray">运行日志</span> 投递日志、已读状态等</li>
              </ul>
            </div>
            <div class="sync-scope-note">
              <strong>注意：</strong>同步采用全量覆盖策略，目标账号原有配置会被软删除后重建。同步后请检查线上功能是否正常。
            </div>
          </div>
        </CardPanel>

        <!-- CardPanel 3: 同步动作 -->
        <CardPanel title="同步动作" desc="一键将本地配置推送到线上">
          <div class="sync-action">
            <div v-if="form.lastSyncAt || form.lastSyncStatus" class="sync-last">
              <div class="sync-last-row">
                <span class="sync-last-label">上次同步时间：</span>
                <span>{{ form.lastSyncAt || '—' }}</span>
              </div>
              <div class="sync-last-row">
                <span class="sync-last-label">上次同步状态：</span>
                <span
                  :class="['sync-status-badge', form.lastSyncStatus === 'success' ? 'sync-status-ok' : (form.lastSyncStatus === 'failed' ? 'sync-status-fail' : '')]"
                >{{ form.lastSyncStatus || '—' }}</span>
              </div>
              <div v-if="form.lastSyncMessage" class="sync-last-row">
                <span class="sync-last-label">消息：</span>
                <span class="sync-last-message">{{ form.lastSyncMessage }}</span>
              </div>
            </div>

            <div class="sync-action-buttons">
              <button
                type="button"
                class="sync-execute-btn"
                :disabled="executing || !settingsAvailable || !form.targetBaseUrl || !form.targetUsername || !form.targetToken"
                @click="execute"
              >{{ executing ? '同步中...' : '立即同步到线上' }}</button>
              <p v-if="!settingsAvailable" class="sync-action-hint">请先保存配置后再执行同步</p>
              <p v-else-if="!form.targetBaseUrl || !form.targetUsername || !form.targetToken" class="sync-action-hint">请先完整填写连接配置</p>
            </div>

            <div v-if="executeResult" class="sync-result">
              <h4 class="sync-result-title">同步结果</h4>
              <div class="sync-result-row">
                <span>HTTP 状态：</span>
                <span>{{ executeResult.status || 0 }}</span>
              </div>
              <div v-if="executeResult.body" class="sync-result-row">
                <pre class="sync-result-body">{{ formatResult(executeResult.body) }}</pre>
              </div>
            </div>
          </div>
        </CardPanel>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import CardPanel from '../../components/CardPanel.vue'
import {
  getDataSyncConfig,
  saveDataSyncConfig,
  pingDataSyncRemote,
  executeDataSync
} from '../../api/dataSync.js'

const loading = ref(true)
const loadError = ref('')
const settingsAvailable = ref(false)
const saving = ref(false)
const pinging = ref(false)
const executing = ref(false)
const executeResult = ref(null)

const form = reactive({
  targetBaseUrl: '',
  targetUsername: '',
  targetToken: '',
  sourceAccountId: null,
  lastSyncAt: null,
  lastSyncStatus: null,
  lastSyncMessage: null
})

async function load() {
  loading.value = true
  loadError.value = ''
  settingsAvailable.value = false
  try {
    const res = await getDataSyncConfig()
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('数据同步配置响应格式异常')
    }
    Object.keys(form).forEach(k => {
      if (data[k] !== undefined) form[k] = data[k]
    })
    settingsAvailable.value = true
  } catch (e) {
    console.error('[Sync] 加载失败:', e)
    loadError.value = `${e.message || '网络异常'}；配置成功加载前不会执行任何同步操作。`
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!settingsAvailable.value) return
  saving.value = true
  try {
    const payload = {
      targetBaseUrl: form.targetBaseUrl,
      targetUsername: form.targetUsername,
      targetToken: form.targetToken,
      sourceAccountId: form.sourceAccountId
    }
    await saveDataSyncConfig(payload)
    showToast('数据同步配置已保存')
  } catch (e) {
    showToast('保存失败：' + (e.message || '网络错误'), true)
  } finally {
    saving.value = false
  }
}

async function ping() {
  if (!settingsAvailable.value) return
  pinging.value = true
  try {
    const res = await pingDataSyncRemote({
      targetBaseUrl: form.targetBaseUrl,
      targetToken: form.targetToken
    })
    const status = res?.data?.status || 0
    if (status >= 200 && status < 300) {
      showToast('连接测试成功（HTTP ' + status + '）')
    } else {
      showToast('连接测试失败（HTTP ' + status + '）', true)
    }
  } catch (e) {
    showToast('连接测试失败：' + (e.message || '网络错误'), true)
  } finally {
    pinging.value = false
  }
}

async function execute() {
  if (!settingsAvailable.value) return
  if (!confirm('确认要将本地配置全量推送到线上目标账号吗？\n\n目标账号原有的配置会被软删除后重建。')) {
    return
  }
  executing.value = true
  executeResult.value = null
  try {
    const res = await executeDataSync({
      targetBaseUrl: form.targetBaseUrl,
      targetToken: form.targetToken,
      targetUsername: form.targetUsername,
      sourceAccountId: form.sourceAccountId
    })
    executeResult.value = res?.data || { status: 0, body: null }
    // 同步后重新加载配置以获取 lastSyncAt/lastSyncStatus
    await load()
    if (executeResult.value.status >= 200 && executeResult.value.status < 300) {
      showToast('数据同步推送成功')
    } else {
      showToast('数据同步推送失败（HTTP ' + executeResult.value.status + '）', true)
    }
  } catch (e) {
    showToast('数据同步失败：' + (e.message || '网络错误'), true)
    executeResult.value = { status: 0, body: { error: e.message || '网络错误' } }
    // 失败后也重新加载配置（lastSyncStatus 会被回写为 failed）
    await load()
  } finally {
    executing.value = false
  }
}

function formatResult(body) {
  if (!body) return ''
  try {
    return typeof body === 'string' ? body : JSON.stringify(body, null, 2)
  } catch (e) {
    return String(body)
  }
}

function showToast(message, isError = false) {
  window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message, isError } }))
}

onMounted(load)
</script>

<style scoped>
.sync-page {
  min-height: 400px;
}
.sync-loading,
.sync-load-error {
  padding: 32px;
  text-align: center;
  color: #6b7280;
}
.sync-load-error {
  color: #b91c1c;
}
.sync-load-error strong {
  display: block;
  margin-bottom: 8px;
  font-size: 16px;
}
.sync-load-error p {
  margin: 0 0 16px;
  word-break: break-all;
}
.sync-retry-btn {
  padding: 8px 20px;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.sync-retry-btn:hover {
  background: #2563eb;
}
.sync-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sync-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sync-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sync-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sync-label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}
.sync-input {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.15s;
  background: #fff;
  color: #111827;
}
.sync-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
.sync-input:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
}
.sync-hint {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
}
.sync-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}
.sync-save-btn,
.sync-ping-btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s;
}
.sync-save-btn {
  background: #3b82f6;
  color: #fff;
}
.sync-save-btn:hover:not(:disabled) {
  background: #2563eb;
}
.sync-ping-btn {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}
.sync-ping-btn:hover:not(:disabled) {
  background: #e5e7eb;
}
.sync-save-btn:disabled,
.sync-ping-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.sync-scope {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.sync-scope-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sync-scope-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}
.sync-scope-warn {
  color: #b45309;
}
.sync-scope-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
  line-height: 1.6;
}
.sync-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  margin-right: 6px;
}
.sync-tag-blue {
  background: #dbeafe;
  color: #1e40af;
}
.sync-tag-gray {
  background: #f3f4f6;
  color: #6b7280;
}
.sync-scope-note {
  padding: 12px 16px;
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
  border-radius: 4px;
  font-size: 13px;
  color: #92400e;
  line-height: 1.6;
}
.sync-action {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.sync-last {
  padding: 16px;
  background: #f9fafb;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sync-last-row {
  display: flex;
  gap: 8px;
  font-size: 13px;
  align-items: flex-start;
}
.sync-last-label {
  font-weight: 600;
  color: #374151;
  flex-shrink: 0;
  min-width: 100px;
}
.sync-last-message {
  word-break: break-all;
  color: #6b7280;
}
.sync-status-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}
.sync-status-ok {
  background: #d1fae5;
  color: #065f46;
}
.sync-status-fail {
  background: #fee2e2;
  color: #991b1b;
}
.sync-action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sync-execute-btn {
  align-self: flex-start;
  padding: 12px 32px;
  background: #10b981;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  transition: background 0.15s;
}
.sync-execute-btn:hover:not(:disabled) {
  background: #059669;
}
.sync-execute-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.sync-action-hint {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
}
.sync-result {
  padding: 16px;
  background: #f9fafb;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sync-result-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}
.sync-result-row {
  font-size: 13px;
  color: #4b5563;
}
.sync-result-body {
  margin: 8px 0 0;
  padding: 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  color: #111827;
}
</style>
