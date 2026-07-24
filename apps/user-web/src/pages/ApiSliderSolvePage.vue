<template>
  <div class="api-slider-page">
    <!-- 1. 五个概览卡片 -->
    <ApiOverviewCards
      :credential="credential"
      :overview="overview"
      :loading="overviewLoading"
      @copy="onCopy"
      @recharge="onRecharge"
      @reset-key="onResetKey"
    />

    <!-- 3. 重要说明区域 -->
    <CardPanel class="notice-card">
      <div class="notice-item">
        <div class="notice-icon notice-icon-blue">i</div>
        <div>
          <strong>能力范围：</strong>
          <span class="notice-text">本功能主要用于处理 WS 掉线引起的滑块问题。Cookie 失效引起的滑块问题不能通过该能力直接解决。Cookie 失效通常代表账号登录状态已被拒绝或失效，需要您先重新扫码登录或通过账号密码重新登录，再继续滑块求解。</span>
        </div>
      </div>
      <div class="notice-item">
        <div class="notice-icon notice-icon-green">¥</div>
        <div>
          <strong>扣费保证：</strong>
          <span class="notice-text">仅对成功求解的滑块任务扣除 Token。失败、预检测未通过、超时、服务不可用等情况一律不扣费。</span>
        </div>
      </div>
      <div class="notice-item">
        <div class="notice-icon notice-icon-orange">?</div>
        <div>
          <strong>服务支持：</strong>
          <span class="notice-text">如果对功能有建议、反馈，或发现疑似误扣费，可联系客服技术人员。客服微信：<b class="wechat">JiShu0724</b></span>
        </div>
      </div>
    </CardPanel>

    <!-- 4. 三块内容区域（各占一行：前台对接配置 → API 对接文档 → Token 消费说明） -->
    <div class="content-stack">
      <ApiConfigCard
        :credential="credential"
        :overview="overview"
        @copy="onCopy"
        @reset-key="onResetKey"
      />
      <ApiDocsCard />
      <ApiTokenUsageCard :overview="overview" :stats="stats" />
    </div>

    <!-- 5. 记录区域 -->
    <ApiRecordsCard />

    <!-- 密钥操作弹窗（页面内 Modal） -->
    <div v-if="keyModal.visible" class="key-modal-mask" @click.self="closeKeyModal">
      <div class="key-modal">
        <div class="key-modal-header">
          <h3>{{ keyModal.title }}</h3>
          <button class="key-modal-close" @click="closeKeyModal" aria-label="关闭">×</button>
        </div>
        <div class="key-modal-body">
          <!-- 确认步骤 -->
          <template v-if="keyModal.step === 'confirm'">
            <p class="key-modal-text">{{ keyModal.message }}</p>
          </template>
          <!-- 结果步骤 -->
          <template v-else-if="keyModal.step === 'result'">
            <p class="key-modal-text">新密钥已生成，请复制保存：</p>
            <div class="key-modal-result">
              <code class="key-modal-key">{{ keyModal.newKey }}</code>
              <button class="key-modal-copy" @click="copyNewKey">复制</button>
            </div>
            <p class="key-modal-warn">密钥会持续有效，只有点击“重置密钥”后旧密钥才会失效。</p>
          </template>
          <!-- 错误步骤 -->
          <template v-else>
            <p class="key-modal-error">{{ keyModal.errorMsg }}</p>
          </template>
        </div>
        <div class="key-modal-footer">
          <button class="key-btn key-btn-ghost" @click="closeKeyModal">
            {{ keyModal.step === 'result' ? '我已保存' : '取消' }}
          </button>
          <button
            v-if="keyModal.step === 'confirm'"
            class="key-btn key-btn-primary"
            :disabled="keyModal.submitting"
            @click="confirmResetKey"
          >
            {{ keyModal.submitting ? '处理中…' : '确定' }}
          </button>
          <button
            v-else-if="keyModal.step === 'error'"
            class="key-btn key-btn-primary"
            @click="confirmResetKey"
          >
            重试
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import ApiOverviewCards from '../components/api-slider/ApiOverviewCards.vue'
import ApiDocsCard from '../components/api-slider/ApiDocsCard.vue'
import ApiConfigCard from '../components/api-slider/ApiConfigCard.vue'
import ApiTokenUsageCard from '../components/api-slider/ApiTokenUsageCard.vue'
import ApiRecordsCard from '../components/api-slider/ApiRecordsCard.vue'
import { getApiCredential, resetApiCredential, getApiOverview, getApiStats } from '../api/apiSliderSolve.js'

const credential = ref(null)
const overview = ref({})
const stats = ref({ kpi: {}, trend: [] })
const overviewLoading = ref(false)

// 密钥操作弹窗（页面内 Modal，替代浏览器 confirm/alert）
const keyModal = reactive({
  visible: false,
  step: 'confirm', // 'confirm' | 'result' | 'error'
  title: '',
  message: '',
  newKey: '',
  submitting: false,
  errorMsg: '',
})

async function loadCredential() {
  try {
    const res = await getApiCredential()
    credential.value = res?.data || null
  } catch (e) {
    console.error('load credential failed', e)
  }
}

async function loadOverview() {
  overviewLoading.value = true
  try {
    const res = await getApiOverview()
    overview.value = res?.data || {}
  } catch (e) {
    console.error('load overview failed', e)
  } finally {
    overviewLoading.value = false
  }
}

async function loadStats() {
  try {
    const res = await getApiStats({ days: 7 })
    stats.value = res?.data || { kpi: {}, trend: [] }
  } catch (e) {
    console.error('load stats failed', e)
  }
}

async function onCopy(text, label) {
  if (!text) {
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '完整密钥仅生成时显示一次，如需获取请重置密钥', isError: true } }))
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: `${label}已复制` } }))
  } catch {
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '复制失败，请手动复制', isError: true } }))
  }
}

function onRecharge() {
  window.dispatchEvent(new CustomEvent('xya-open-payment'))
}

function onResetKey() {
  const hasExisting = !!credential.value?.api_key_prefix
  keyModal.title = hasExisting ? '重置对接密钥' : '生成对接密钥'
  keyModal.message = hasExisting
    ? '重置后旧密钥立即失效，已对接的系统需更新密钥。确定要重置吗？'
    : '将为您生成新的对接密钥，生成后可查看和复制。'
  keyModal.step = 'confirm'
  keyModal.newKey = ''
  keyModal.errorMsg = ''
  keyModal.submitting = false
  keyModal.visible = true
}

async function confirmResetKey() {
  keyModal.submitting = true
  try {
    const res = await resetApiCredential()
    const newKey = res?.data?.apiKey
    if (newKey) {
      keyModal.newKey = newKey
      keyModal.step = 'result'
      await loadCredential()
      window.dispatchEvent(new CustomEvent('xya-toast', {
        detail: { message: credential.value?.api_key_prefix ? '密钥已重置' : '密钥已生成' }
      }))
    } else {
      keyModal.errorMsg = '服务器未返回新密钥，请稍后重试'
      keyModal.step = 'error'
    }
  } catch (e) {
    const msg = e?.message || e?.data?.msg || '操作失败，请稍后重试'
    keyModal.errorMsg = msg
    keyModal.step = 'error'
  } finally {
    keyModal.submitting = false
  }
}

function copyNewKey() {
  if (!keyModal.newKey) return
  navigator.clipboard.writeText(keyModal.newKey)
    .then(() => window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '新密钥已复制' } })))
    .catch(() => window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '复制失败，请手动选中复制', isError: true } })))
}

function closeKeyModal() {
  keyModal.visible = false
}

onMounted(() => {
  loadCredential()
  loadOverview()
  loadStats()
})
</script>

<style scoped>
.api-slider-page {
  padding: 0;
  width: 100%;
  max-width: none;
  margin: 0;
}
.notice-card { margin-bottom: 16px; background: #f0f7ff; border: 1px solid #d6e8ff; }
.notice-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px 0; }
.notice-item + .notice-item { border-top: 1px dashed #d6e8ff; }
.notice-icon {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: bold; font-size: 14px; flex-shrink: 0;
}
.notice-icon-blue { background: #e3f2fd; color: var(--primary); }
.notice-icon-green { background: #e8f5e9; color: var(--green); }
.notice-icon-orange { background: #fff3e0; color: var(--orange); }
.notice-text { color: var(--muted); font-size: 13px; line-height: 1.6; }
.wechat { color: var(--primary); }
.content-stack { display: flex; flex-direction: column; gap: 16px; margin-bottom: 16px; }

/* 密钥操作弹窗（页面内 Modal） */
.key-modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
}
.key-modal {
  width: 480px; max-width: 92vw; background: #fff; border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.2); overflow: hidden;
  animation: keyModalIn 0.18s ease-out;
}
@keyframes keyModalIn { from { opacity: 0; transform: translateY(-12px) scale(0.98); } to { opacity: 1; transform: none; } }
.key-modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--line);
}
.key-modal-header h3 { margin: 0; font-size: 16px; font-weight: 600; color: var(--text); }
.key-modal-close {
  width: 28px; height: 28px; border: none; background: transparent;
  font-size: 20px; color: var(--muted); cursor: pointer; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
}
.key-modal-close:hover { background: #f5f5f5; color: var(--text); }
.key-modal-body { padding: 20px; }
.key-modal-text { margin: 0 0 12px; font-size: 14px; color: var(--text); line-height: 1.6; }
.key-modal-text b { color: var(--orange); }
.key-modal-result {
  display: flex; gap: 8px; align-items: center; margin: 12px 0;
  background: #f6f8fa; border: 1px solid var(--line); border-radius: 8px; padding: 12px;
}
.key-modal-key {
  flex: 1; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px; color: var(--primary); word-break: break-all; background: transparent;
}
.key-modal-copy {
  padding: 6px 14px; border: none; background: var(--primary); color: #fff;
  border-radius: 6px; font-size: 13px; cursor: pointer; flex-shrink: 0;
}
.key-modal-copy:hover { opacity: 0.9; }
.key-modal-warn { margin: 8px 0 0; font-size: 12px; color: var(--orange); }
.key-modal-error { margin: 0; padding: 12px; background: #fff0f0; border: 1px solid #ffcdc; border-radius: 8px; color: #d32f2f; font-size: 13px; line-height: 1.6; }
.key-modal-footer {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 12px 20px; border-top: 1px solid var(--line); background: #fafbfc;
}
.key-btn { padding: 8px 18px; border-radius: 6px; font-size: 13px; cursor: pointer; border: 1px solid transparent; }
.key-btn-ghost { background: #fff; border-color: var(--line); color: var(--muted); }
.key-btn-ghost:hover { border-color: var(--primary); color: var(--primary); }
.key-btn-primary { background: var(--primary); color: #fff; }
.key-btn-primary:hover { opacity: 0.9; }
.key-btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
