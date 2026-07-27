<template>
  <div class="aics-page">
    <div v-if="loading" class="aics-loading" role="status" aria-live="polite">配置加载中...</div>
    <div v-else-if="loadError" class="aics-load-error" role="alert">
      <strong>AI 客服配置暂时无法加载</strong>
      <p>{{ loadError }}</p>
      <button type="button" class="aics-retry-btn" @click="load">重新加载</button>
    </div>
    <div v-else class="aics-grid">
      <div class="aics-main">
        <!-- 工作模式 -->
        <CardPanel title="AI 客服工作模式" desc="开启后，AI 将根据下方配置自动回复买家消息">
          <div class="aics-form">
            <div class="aics-row aics-row-toggle">
              <div>
                <strong>启用 AI 自动回复</strong>
                <p>开启后买家消息将由 AI 自动响应（受工作时段与安全策略限制）</p>
              </div>
              <button type="button" :class="['aics-switch', { on: form.enabled }]" @click="form.enabled = !form.enabled">
                <span class="aics-switch-knob" />
              </button>
            </div>
            <div class="aics-row aics-row-toggle">
              <div>
                <strong>24 小时全天在线</strong>
                <p>关闭后将按下方工作时段自动回复，工作时段外转人工</p>
              </div>
              <button type="button" :class="['aics-switch', { on: form.workHours24 }]" @click="form.workHours24 = !form.workHours24">
                <span class="aics-switch-knob" />
              </button>
            </div>
            <div v-if="!form.workHours24" class="aics-row">
              <label>工作时段</label>
              <div class="aics-time-pair">
                <input v-model="form.workStart" type="time" class="aics-input" />
                <span>至</span>
                <input v-model="form.workEnd" type="time" class="aics-input" />
              </div>
            </div>
            <div class="aics-row">
              <label>接待模式</label>
              <select v-model="form.mode" class="aics-input">
                <option value="auto">全自动（AI 直接回复）</option>
                <option value="hybrid">混合模式（AI 建议转人工优先）</option>
                <option value="manual">仅人工（AI 仅给建议不发送）</option>
              </select>
            </div>
            <div class="aics-row">
              <label>回复延时（秒）</label>
              <input v-model.number="form.replyDelaySeconds" type="number" min="0" max="120" class="aics-input" />
              <p class="aics-hint">延时过短容易被风控识别为机器人，建议 5-15 秒</p>
            </div>
            <div class="aics-row aics-row-toggle">
              <div>
                <strong>携带对话上下文</strong>
                <p>开启后 AI 会读取最近 10 条历史消息以理解语境</p>
              </div>
              <button type="button" :class="['aics-switch', { on: form.carryContext }]" @click="form.carryContext = !form.carryContext">
                <span class="aics-switch-knob" />
              </button>
            </div>
            <div class="aics-row aics-row-toggle">
              <div>
                <strong>人工干预自动暂停</strong>
                <p>人工接管会话后，AI 自动暂停该会话回复</p>
              </div>
              <button type="button" :class="['aics-switch', { on: form.pauseOnHumanIntervene }]" @click="form.pauseOnHumanIntervene = !form.pauseOnHumanIntervene">
                <span class="aics-switch-knob" />
              </button>
            </div>
          </div>
        </CardPanel>

        <!-- 角色与人设 -->
        <CardPanel title="客服角色与人设" desc="AI 客服的身份设定与回复风格" style="margin-top:16px">
          <div class="aics-form">
            <div class="aics-row">
              <label>客服人设</label>
              <input v-model="form.persona" class="aics-input" placeholder="如：专业客服" />
            </div>
            <div class="aics-row">
              <label>回复语气</label>
              <select v-model="form.tone" class="aics-input">
                <option value="friendly">友好亲切</option>
                <option value="professional">专业严谨</option>
                <option value="casual">轻松活泼</option>
              </select>
            </div>
            <div class="aics-row">
              <label>回复语言</label>
              <select v-model="form.language" class="aics-input">
                <option value="zh-CN">简体中文</option>
                <option value="en">English</option>
              </select>
            </div>
            <div class="aics-row">
              <div class="aics-label-row">
                <label>系统提示词（System Prompt）</label>
                <button type="button" class="aics-restore-btn" @click="restoreDefault('systemPrompt')">恢复默认</button>
              </div>
              <textarea v-model="form.systemPrompt" class="aics-input aics-textarea" rows="4" placeholder="定义 AI 的角色、店铺信息、商品特色与回复边界" />
            </div>
            <div class="aics-row">
              <div class="aics-label-row">
                <label>欢迎语</label>
                <button type="button" class="aics-restore-btn" @click="restoreDefault('welcomeMessage')">恢复默认</button>
              </div>
              <textarea v-model="form.welcomeMessage" class="aics-input aics-textarea" rows="2" placeholder="新会话进入时自动发送" />
            </div>
            <div class="aics-row">
              <div class="aics-label-row">
                <label>知识库（优先于默认配置）</label>
                <span class="aics-kb-count">自定义 {{ form.knowledgeBases.length }} 份 · 默认 {{ form.defaultKnowledgeBases.length }} 份</span>
              </div>
              <div class="aics-upload-area">
                <input ref="kbFileInputRef" type="file" accept=".md,.txt,.pptx,.xlsx,.csv" style="display:none" @change="onKbFileChange" />
                <button type="button" class="aics-upload-btn" :disabled="kbUploading" @click="kbFileInputRef?.click()">
                  {{ kbUploading ? '正在提取...' : '上传知识库文件' }}
                </button>
                <button type="button" class="aics-upload-btn" @click="addKnowledgeBase">新增手动知识库</button>
                <span class="aics-upload-hint">支持重复上传多份内容；AI 将先读用户知识库，再读默认知识库</span>
              </div>
              <div class="aics-entry-list">
                <div v-for="(item, index) in form.knowledgeBases" :key="`kb-${index}`" class="aics-entry-card">
                  <div class="aics-entry-head">
                    <input v-model="item.name" class="aics-input" placeholder="知识库名称" />
                    <button type="button" class="aics-entry-remove" @click="removeKnowledgeBase(index)">删除</button>
                  </div>
                  <textarea v-model="item.content" class="aics-input aics-textarea aics-kb-textarea" rows="6" placeholder="填写商品参数、发货说明、售后口径、店铺边界等"></textarea>
                  <div class="aics-entry-meta">
                    <span>{{ item.source === 'upload' ? '来自文件' : '手动维护' }}</span>
                    <span>{{ (item.content || '').length }} 字</span>
                  </div>
                </div>
                <div v-if="!form.knowledgeBases.length" class="aics-empty-tip">还没有添加自定义知识库，下方系统默认知识库将自动生效。</div>
              </div>

              <!-- 系统默认知识库（只读展示，让用户能看到 AI 客服将引用哪些预置内容） -->
              <div v-if="form.defaultKnowledgeBases.length" class="aics-default-section">
                <div class="aics-default-head">
                  <span class="aics-default-badge">系统默认</span>
                  <span class="aics-default-title">默认知识库（只读，自定义知识库优先）</span>
                </div>
                <details v-for="(item, index) in form.defaultKnowledgeBases" :key="`dkb-${index}`" class="aics-default-card">
                  <summary>
                    <strong>{{ item.name || `默认知识库 ${index + 1}` }}</strong>
                    <span class="aics-default-meta">{{ (item.content || '').length }} 字</span>
                  </summary>
                  <pre class="aics-default-pre">{{ item.content || '（空）' }}</pre>
                </details>
              </div>
            </div>

            <div class="aics-row">
              <div class="aics-label-row">
                <label>聊天规则（优先于默认规则）</label>
                <span class="aics-kb-count">自定义 {{ form.chatRules.length }} 条 · 默认 {{ form.defaultChatRules.length }} 条</span>
              </div>
              <div class="aics-entry-list">
                <div v-for="(item, index) in form.chatRules" :key="`rule-${index}`" class="aics-entry-card">
                  <div class="aics-entry-head">
                    <input v-model="item.name" class="aics-input" placeholder="规则名称" />
                    <button type="button" class="aics-entry-remove" @click="removeChatRule(index)">删除</button>
                  </div>
                  <textarea v-model="item.content" class="aics-input aics-textarea" rows="4" placeholder="例如：只能回答商品本身，不要主动延展售后承诺"></textarea>
                </div>
                <div v-if="!form.chatRules.length" class="aics-empty-tip">暂未添加自定义聊天规则，下方系统默认规则将自动生效。</div>
              </div>
              <button type="button" class="aics-upload-btn" @click="addChatRule">新增聊天规则</button>

              <!-- 系统默认聊天规则（只读展示） -->
              <div v-if="form.defaultChatRules.length" class="aics-default-section">
                <div class="aics-default-head">
                  <span class="aics-default-badge">系统默认</span>
                  <span class="aics-default-title">默认聊天规则（只读，自定义规则优先）</span>
                </div>
                <details v-for="(item, index) in form.defaultChatRules" :key="`dcr-${index}`" class="aics-default-card">
                  <summary>
                    <strong>{{ item.name || `默认规则 ${index + 1}` }}</strong>
                    <span class="aics-default-meta">{{ (item.content || '').length }} 字</span>
                  </summary>
                  <pre class="aics-default-pre">{{ item.content || '（空）' }}</pre>
                </details>
              </div>
            </div>
          </div>
        </CardPanel>

        <!-- 安全策略 -->
        <CardPanel title="安全与会话策略" desc="防止 AI 越权回复，必要时转人工" style="margin-top:16px">
          <div class="aics-form">
            <div class="aics-row aics-row-toggle">
              <div>
                <strong>启用安全模式</strong>
                <p>检测到敏感词或高风险场景时自动转人工</p>
              </div>
              <button type="button" :class="['aics-switch', { on: form.safeMode }]" @click="form.safeMode = !form.safeMode">
                <span class="aics-switch-knob" />
              </button>
            </div>
            <div class="aics-row">
              <label>转人工关键词</label>
              <input v-model="form.handoffKeywords" class="aics-input" placeholder="用 、 分隔，如：退款、投诉、维权" />
            </div>
            <div class="aics-row">
              <label>会话黑名单关键词</label>
              <input v-model="form.blacklistKeywords" class="aics-input" placeholder="命中后 AI 不回复，如：低价、加微" />
            </div>
            <div class="aics-row">
              <label>转人工阈值（分）</label>
              <input v-model.number="form.transferThreshold" type="number" min="0" max="100" class="aics-input" />
              <p class="aics-hint">当 AI 置信度低于此分数时转人工</p>
            </div>
            <div class="aics-row">
              <label>会话超时（分钟）</label>
              <input v-model.number="form.sessionTimeoutMinutes" type="number" min="1" max="120" class="aics-input" />
            </div>
            <div class="aics-row">
              <label>每日最大回复数</label>
              <input v-model.number="form.maxDailyReplies" type="number" min="1" max="10000" class="aics-input" />
              <p class="aics-hint">超出后自动转人工，避免 AI 滥用消耗额度</p>
            </div>
          </div>
        </CardPanel>

        <!-- 计费与额度 -->
        <CardPanel title="计费与每日额度" desc="配置用户每日免费条数与超额扣费规则" style="margin-top:16px">
          <div class="aics-form">
            <div class="aics-row">
              <label>用户每日免费额度（条）</label>
              <input v-model.number="billing.dailyFreeQuota" type="number" min="0" max="1000" class="aics-input" />
              <p class="aics-hint">每个用户每天可免费与客服沟通的消息条数；超出后按下方规则扣费。设为 0 表示无免费额度。</p>
            </div>
            <div class="aics-row">
              <label>每条消息扣费 Token 数</label>
              <input v-model.number="billing.perMessageTokens" type="number" min="1" max="100" class="aics-input" />
              <p class="aics-hint">超出免费额度后，每条客服回复扣减的 Token 数（默认 3）。</p>
            </div>
            <div class="aics-row">
              <label>上下文消息上限（条）</label>
              <input v-model.number="billing.maxContextMessages" type="number" min="10" max="200" class="aics-input" />
              <p class="aics-hint">超出后提示用户新建会话或压缩上下文（压缩不扣费）。</p>
            </div>
            <div class="aics-row aics-row-toggle">
              <div>
                <strong>启用计费</strong>
                <p>关闭后所有客服消息均不扣费（仅限调试用途）</p>
              </div>
              <button type="button" :class="['aics-switch', { on: billing.enabled }]" @click="billing.enabled = !billing.enabled">
                <span class="aics-switch-knob" />
              </button>
            </div>
            <div class="aics-billing-actions">
              <button type="button" class="aics-save-btn" :disabled="billingSaving" @click="saveBilling">{{ billingSaving ? '保存中...' : '保存额度配置' }}</button>
            </div>
          </div>
        </CardPanel>

        <div class="aics-actions">
          <button type="button" class="aics-save-btn" :disabled="saving || !settingsAvailable" @click="save">{{ saving ? '保存中...' : '保存配置' }}</button>
          <button type="button" class="aics-test-btn" :disabled="testing || !settingsAvailable" @click="openTestPanel">{{ testing ? '测试中...' : '测试 AI 回复' }}</button>
        </div>
      </div>

      <!-- 右侧：实时预览与统计 -->
      <aside class="aics-side">
        <CardPanel title="实时回复预览">
          <div class="aics-preview">
            <div class="aics-bubble them">这个价格还能再优惠吗？</div>
            <div v-if="testReply" class="aics-bubble me">{{ testReply }}</div>
            <div v-else class="aics-bubble me">点击下方"测试 AI 回复"按钮查看效果</div>
          </div>
          <div class="aics-test-form">
            <textarea v-model="testMessage" class="aics-input" rows="2" placeholder="输入模拟买家消息..." />
            <button type="button" class="aics-test-btn" :disabled="testing || !testMessage.trim()" @click="runTest">{{ testing ? '生成中...' : '生成回复' }}</button>
          </div>
          <div v-if="testError" class="aics-error-box">
            <p class="aics-error">{{ testError }}</p>
            <button type="button" class="aics-retry-btn" :disabled="testing" @click="runTest">{{ testing ? '重试中...' : '重试' }}</button>
          </div>
          <div v-if="testConfigured === false" class="aics-warn-box">
            <p class="aics-warn">⚠ AI 模型未配置，请到「后台 → 模型配置」先配置通用文本模型</p>
            <button type="button" class="aics-retry-btn" @click="goToModelConfig">前往模型配置</button>
          </div>
          <div v-if="testConfigured === 'NETWORK_ERROR'" class="aics-error-box">
            <p class="aics-error">网络异常，请检查网络连接</p>
            <button type="button" class="aics-retry-btn" :disabled="testing" @click="runTest">{{ testing ? '重试中...' : '重试' }}</button>
          </div>
        </CardPanel>

        <CardPanel title="AI 客服状态" style="margin-top:16px">
          <div class="aics-status-list">
            <div class="aics-status-row">
              <span>当前状态</span>
              <b :class="form.enabled ? 'green' : 'red'">{{ form.enabled ? '已启用' : '已停用' }}</b>
            </div>
            <div class="aics-status-row">
              <span>工作时段</span>
              <b>{{ form.workHours24 ? '24 小时' : `${form.workStart}-${form.workEnd}` }}</b>
            </div>
            <div class="aics-status-row">
              <span>接待模式</span>
              <b>{{ modeText }}</b>
            </div>
            <div class="aics-status-row">
              <span>安全模式</span>
              <b :class="form.safeMode ? 'green' : 'red'">{{ form.safeMode ? '已开启' : '已关闭' }}</b>
            </div>
            <div class="aics-status-row">
              <span>自定义知识库</span>
              <b>{{ form.knowledgeBases.length }} 份</b>
            </div>
            <div class="aics-status-row">
              <span>自定义规则</span>
              <b>{{ form.chatRules.length }} 条</b>
            </div>
          </div>
        </CardPanel>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import CardPanel from '../../components/CardPanel.vue'
import { getBusinessSettings, saveBusinessSettings, testAiCustomerService, getAiCsDefaults, uploadKnowledgeBase } from '../../api/businessSettings.js'
import { getCsConfig, saveCsBillingConfig } from '../../api/aiCs.js'
import { ensureAiTokenBalance } from '../../utils/aiTokenGuard.js'
import { confirmAction } from '../../utils/confirmAction.js'
import { createRequestGate } from '../../utils/requestLifecycle.js'

const loading = ref(true)
const loadError = ref('')
const settingsAvailable = ref(false)
const saving = ref(false)
const testing = ref(false)
const testMessage = ref('你好，这个商品还能再优惠点吗？')
const testReply = ref('')
const testError = ref('')
const testConfigured = ref(null)
const loadGate = createRequestGate()

const kbFileInputRef = ref(null)
const kbUploading = ref(false)

// 计费与额度配置（存储于 ai_cs_billing_config，与上方业务设置独立保存）
const billing = reactive({
  dailyFreeQuota: 10,
  perMessageTokens: 3,
  maxContextMessages: 50,
  enabled: true
})
const billingSaving = ref(false)

const form = reactive({
  enabled: false,
  mode: 'hybrid',
  workHours24: true,
  workStart: '09:00',
  workEnd: '22:00',
  persona: '专业客服',
  tone: 'friendly',
  language: 'zh-CN',
  replyDelaySeconds: 8,
  carryContext: true,
  pauseOnHumanIntervene: true,
  systemPrompt: '',
  welcomeMessage: '',
  knowledgeBase: '',
  knowledgeBases: [],
  defaultKnowledgeBases: [],
  chatRules: [],
  defaultChatRules: [],
  transferThreshold: 85,
  sessionTimeoutMinutes: 30,
  blacklistKeywords: '',
  maxDailyReplies: 200,
  safeMode: true,
  handoffKeywords: '退款、投诉、赔偿、维权、差评'
})

const LEGACY_SYSTEM_PROMPT_MARKERS = [
  '你是闲鱼店铺的专业客服助手',
  '你是本店的AI客服',
  '使用"您好""亲"等称呼',
  '你是一个友好的闲鱼客服助手'
]

const LEGACY_WELCOME_MESSAGE_MARKERS = [
  '我是AI客服小鱼',
  '欢迎光临本店',
  '商品拍下后48小时内发货',
  '您好，欢迎来看看这件商品'
]

function normalizeEntry(item, fallbackName) {
  if (!item) return null
  if (typeof item === 'string') {
    const content = item.trim()
    if (!content) return null
    return { name: fallbackName, content, source: 'manual' }
  }
  const content = String(item.content || '').trim()
  if (!content) return null
  return {
    name: String(item.name || item.title || fallbackName),
    content,
    source: String(item.source || 'manual')
  }
}

function normalizeEntries(raw, fallbackText = '', prefix = '内容') {
  const list = Array.isArray(raw)
    ? raw.map((item, index) => normalizeEntry(item, `${prefix}${index + 1}`)).filter(Boolean)
    : []
  if (!list.length && String(fallbackText || '').trim()) {
    list.push({ name: `${prefix}1`, content: String(fallbackText).trim(), source: 'manual' })
  }
  return list
}

function assertAiCsConfig(data) {
  const booleanFields = ['enabled', 'workHours24', 'carryContext', 'pauseOnHumanIntervene', 'safeMode']
  const stringFields = ['workStart', 'workEnd', 'persona', 'systemPrompt', 'welcomeMessage', 'knowledgeBase', 'blacklistKeywords', 'handoffKeywords']
  const numberFields = ['replyDelaySeconds', 'transferThreshold', 'sessionTimeoutMinutes', 'maxDailyReplies']
  const listFields = ['knowledgeBases', 'defaultKnowledgeBases', 'chatRules', 'defaultChatRules']
  if (booleanFields.some(field => typeof data[field] !== 'boolean')
    || stringFields.some(field => typeof data[field] !== 'string')
    || numberFields.some(field => typeof data[field] !== 'number' || !Number.isFinite(data[field]) || data[field] < 0)
    || listFields.some(field => !Array.isArray(data[field]))
    || !['auto', 'hybrid', 'manual'].includes(data.mode)
    || !['friendly', 'professional', 'casual'].includes(data.tone)
    || !['zh-CN', 'en'].includes(data.language)) {
    throw new Error('AI 客服配置字段格式异常')
  }
}

const modeText = computed(() => ({
  auto: '全自动',
  hybrid: '混合模式',
  manual: '仅人工'
}[form.mode] || '-'))

function looksLikeLegacyText(value, markers) {
  const text = String(value || '').trim()
  return text && markers.some(marker => text.includes(marker))
}

async function load() {
  const requestGeneration = loadGate.begin()
  loading.value = true
  loadError.value = ''
  settingsAvailable.value = false
  try {
    const [configResult, defaultsResult, billingResult] = await Promise.allSettled([
      getBusinessSettings('ai-customer-service'),
      getAiCsDefaults(),
      getCsConfig()
    ])
    if (!loadGate.isCurrent(requestGeneration)) return
    if (configResult.status === 'rejected') throw configResult.reason
    const configRes = configResult.value
    const data = configRes?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('AI 客服配置响应格式异常')
    assertAiCsConfig(data)
    const defaultsData = defaultsResult.status === 'fulfilled' ? defaultsResult.value?.data : null
    const defaults = defaultsData && typeof defaultsData === 'object' && !Array.isArray(defaultsData) ? defaultsData : {}
    Object.keys(form).forEach(k => {
      if (data[k] !== undefined) form[k] = data[k]
    })
    if (looksLikeLegacyText(form.systemPrompt, LEGACY_SYSTEM_PROMPT_MARKERS) && defaults.systemPrompt) {
      form.systemPrompt = defaults.systemPrompt
    }
    if (looksLikeLegacyText(form.welcomeMessage, LEGACY_WELCOME_MESSAGE_MARKERS) && defaults.welcomeMessage) {
      form.welcomeMessage = defaults.welcomeMessage
    }
    form.knowledgeBases = normalizeEntries(data.knowledgeBases, data.knowledgeBase, '知识库')
    form.defaultKnowledgeBases = normalizeEntries(data.defaultKnowledgeBases, '', '默认知识库')
    form.chatRules = normalizeEntries(data.chatRules, '', '规则')
    form.defaultChatRules = normalizeEntries(data.defaultChatRules, '', '默认规则')
    // 计费配置：getCsConfig 返回 { code, msg, data: { dailyFreeQuota, perMessageTokens, ... } }
    if (billingResult.status === 'fulfilled') {
      const bd = billingResult.value?.data
      if (bd && typeof bd === 'object') {
        if (Number.isFinite(Number(bd.dailyFreeQuota))) billing.dailyFreeQuota = Number(bd.dailyFreeQuota)
        if (Number.isFinite(Number(bd.perMessageTokens))) billing.perMessageTokens = Number(bd.perMessageTokens)
        if (Number.isFinite(Number(bd.maxContextMessages))) billing.maxContextMessages = Number(bd.maxContextMessages)
        if (typeof bd.enabled === 'boolean') billing.enabled = bd.enabled
      }
    }
    settingsAvailable.value = true
  } catch {
    if (!loadGate.isCurrent(requestGeneration)) return
    loadError.value = '请检查网络连接后重试；在配置成功加载前不会应用或覆盖任何设置。'
  } finally {
    if (loadGate.isCurrent(requestGeneration)) loading.value = false
  }
}

async function saveBilling() {
  if (billingSaving.value) return
  billingSaving.value = true
  try {
    const payload = {
      dailyFreeQuota: Math.max(0, Math.min(1000, Number(billing.dailyFreeQuota) || 0)),
      perMessageTokens: Math.max(1, Math.min(100, Number(billing.perMessageTokens) || 3)),
      maxContextMessages: Math.max(10, Math.min(200, Number(billing.maxContextMessages) || 50)),
      enabled: !!billing.enabled
    }
    const res = await saveCsBillingConfig(payload)
    const bd = res?.data
    if (bd && typeof bd === 'object') {
      if (Number.isFinite(Number(bd.dailyFreeQuota))) billing.dailyFreeQuota = Number(bd.dailyFreeQuota)
      if (Number.isFinite(Number(bd.perMessageTokens))) billing.perMessageTokens = Number(bd.perMessageTokens)
      if (Number.isFinite(Number(bd.maxContextMessages))) billing.maxContextMessages = Number(bd.maxContextMessages)
      if (typeof bd.enabled === 'boolean') billing.enabled = bd.enabled
    }
    showToast('额度配置已保存')
  } catch (e) {
    showToast('额度配置保存失败：' + (e.message || '网络错误'), true)
  } finally {
    billingSaving.value = false
  }
}

async function save() {
  if (!settingsAvailable.value) return
  saving.value = true
  try {
    const payload = {
      ...form,
      knowledgeBases: form.knowledgeBases.filter(item => item?.content?.trim()),
      chatRules: form.chatRules.filter(item => item?.content?.trim()),
      knowledgeBase: form.knowledgeBases
        .map(item => item?.content?.trim())
        .filter(Boolean)
        .join('\n\n')
    }
    await saveBusinessSettings('ai-customer-service', payload)
    showToast('AI 客服配置已保存')
  } catch (e) {
    showToast('保存失败：' + (e.message || '网络错误'), true)
  } finally {
    saving.value = false
  }
}

function openTestPanel() {
  if (!testReply.value) runTest()
}

async function runTest() {
  if (!testMessage.value.trim()) return
  if (!(await ensureAiTokenBalance({ sceneName: 'AI 客服测试' }))) return
  testing.value = true
  testError.value = ''
  testReply.value = ''
  testConfigured.value = null
  try {
    const res = await testAiCustomerService(testMessage.value.trim())
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.ok !== 'boolean') {
      throw new Error('AI 测试响应格式异常')
    }
    if (data.ok) {
      if (typeof data.reply !== 'string' || !data.reply.trim()) throw new Error('AI 未返回有效回复')
      testReply.value = data.reply
    } else {
      testReply.value = data?.reply || ''
      const errorCode = data?.errorCode
      if (errorCode === 'NOT_CONFIGURED' || data?.configured === false) {
        testConfigured.value = false
      } else if (errorCode === 'AI_ERROR') {
        testError.value = 'AI 调用失败：' + (data?.reply || '未知错误')
      } else {
        testError.value = data?.reply ? '' : 'AI 未返回有效回复'
      }
    }
  } catch {
    testError.value = '网络异常，请检查网络连接后重试'
    testConfigured.value = 'NETWORK_ERROR'
  } finally {
    testing.value = false
  }
}

async function onKbFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  if (file.size > 10 * 1024 * 1024) {
    showToast('文件不能超过 10MB', true)
    return
  }
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!['.md', '.txt', '.pptx', '.xlsx', '.csv'].includes(ext)) {
    showToast('仅支持 .md / .txt / .csv / .xlsx / .pptx', true)
    return
  }
  kbUploading.value = true
  try {
    const res = await uploadKnowledgeBase(file)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('知识库上传响应格式异常')
    const extractedText = typeof data.extractedText === 'string' ? data.extractedText.trim() : ''
    const ruleCount = Number.isFinite(Number(data.ruleCount)) ? Number(data.ruleCount) : null
    const fileName = typeof data.fileName === 'string' && data.fileName.trim() ? data.fileName : file.name
    if (!extractedText) {
      showToast('AI 未能从文件中提取有效规则', true)
      return
    }
    form.knowledgeBases.push({
      name: fileName,
      content: extractedText,
      source: 'upload'
    })
    showToast(ruleCount == null
      ? `已从 ${fileName} 提取内容并加入知识库（规则数量未返回）`
      : `已从 ${fileName} 提取 ${ruleCount} 条内容，并加入知识库`)
  } catch (err) {
    showToast('文件上传失败：' + (err.message || '网络错误'), true)
  } finally {
    kbUploading.value = false
  }
}

function addKnowledgeBase() {
  form.knowledgeBases.push({ name: `知识库${form.knowledgeBases.length + 1}`, content: '', source: 'manual' })
}

function removeKnowledgeBase(index) {
  form.knowledgeBases.splice(index, 1)
}

function addChatRule() {
  form.chatRules.push({ name: `规则${form.chatRules.length + 1}`, content: '', source: 'manual' })
}

function removeChatRule(index) {
  form.chatRules.splice(index, 1)
}

async function restoreDefault(field) {
  if (!['systemPrompt', 'welcomeMessage'].includes(field)) return
  const label = field === 'systemPrompt' ? '系统提示词' : '欢迎语'
  const ok = await confirmAction({
    title: `恢复默认${label}？`,
    description: `恢复默认将覆盖当前${label}内容，是否继续？`,
    confirmText: '恢复默认'
  })
  if (!ok) return
  try {
    const res = await getAiCsDefaults()
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data[field] !== 'string') {
      throw new Error('默认配置响应格式异常')
    }
    form[field] = data[field]
    showToast('已恢复默认值，请点击"保存配置"以生效')
  } catch (err) {
    showToast('恢复默认失败：' + (err.message || '网络错误'), true)
  }
}

function goToModelConfig() {
  window.dispatchEvent(new CustomEvent('xya-navigate', { detail: { route: 'ai-model-config' } }))
  window.open('/admin/#/ai-provider', '_blank')
}

function showToast(message, isError = false) {
  const evt = new CustomEvent('xya-toast', { detail: { message, isError } })
  window.dispatchEvent(evt)
}

onMounted(load)

onBeforeUnmount(() => {
  loadGate.dispose()
})
</script>

<style scoped>
.aics-page { padding: 4px; }
.aics-loading { padding: 40px; text-align: center; color: #6b7a90; }
.aics-load-error {
  display: grid;
  justify-items: start;
  gap: 10px;
  padding: 24px;
  border: 1px solid #fecaca;
  border-radius: 14px;
  background: #fff7f7;
  color: #991b1b;
}
.aics-load-error p { margin: 0; color: #7f1d1d; line-height: 1.6; }
.aics-grid { display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 16px; align-items: start; }
.aics-main, .aics-side { display: flex; flex-direction: column; gap: 0; }

.aics-form { display: grid; gap: 16px; padding: 4px 2px; }
.aics-row { display: flex; flex-direction: column; gap: 6px; }
.aics-row > label { font-size: 12px; color: #6b7a90; font-weight: 600; }
.aics-row-toggle { flex-direction: row; align-items: center; justify-content: space-between; gap: 12px; }
.aics-row-toggle > div { display: flex; flex-direction: column; gap: 4px; }
.aics-row-toggle strong { font-size: 14px; color: #12233f; }
.aics-row-toggle p { font-size: 12px; color: #6b7a90; margin: 0; }

.aics-input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid #dbe6f6;
  border-radius: 12px;
  background: #fff;
  font-size: 13px;
  color: #172b4d;
  outline: 0;
  transition: border-color .2s;
}
.aics-input:focus { border-color: #2563eb; }
.aics-textarea { height: auto; padding: 10px 12px; resize: vertical; line-height: 1.6; min-height: 80px; }
.aics-time-pair { display: flex; gap: 8px; align-items: center; }
.aics-time-pair .aics-input { flex: 1; }
.aics-hint { font-size: 11px; color: #99a4b4; margin: 2px 0 0; }

.aics-switch {
  width: 44px; height: 24px; border-radius: 999px; border: 0;
  background: #cbd5e1; cursor: pointer; position: relative;
  transition: background .2s; flex-shrink: 0; padding: 0;
}
.aics-switch.on { background: #22c55e; }
.aics-switch-knob {
  position: absolute; top: 2px; left: 2px;
  width: 20px; height: 20px; border-radius: 50%;
  background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.2);
  transition: left .2s;
}
.aics-switch.on .aics-switch-knob { left: 22px; }

.aics-actions { display: flex; gap: 12px; margin-top: 16px; }
.aics-billing-actions { display: flex; justify-content: flex-end; margin-top: 4px; }
.aics-save-btn, .aics-test-btn {
  padding: 10px 20px; border-radius: 12px; border: 0; cursor: pointer;
  font-size: 13px; font-weight: 700; transition: all .2s;
}
.aics-save-btn { background: linear-gradient(135deg, #2563eb, #3b82f6); color: #fff; box-shadow: 0 8px 20px rgba(37,99,235,.22); }
.aics-save-btn:hover:not(:disabled) { transform: translateY(-1px); }
.aics-save-btn:disabled { opacity: .6; cursor: not-allowed; }
.aics-test-btn { background: #fff; color: #2563eb; border: 1px solid #bfdbfe; }
.aics-test-btn:hover:not(:disabled) { background: #eff6ff; }
.aics-test-btn:disabled { opacity: .6; cursor: not-allowed; }

.aics-preview { display: flex; flex-direction: column; gap: 10px; padding: 4px 0 12px; }
.aics-bubble { padding: 10px 14px; border-radius: 14px; font-size: 13px; line-height: 1.6; max-width: 90%; }
.aics-bubble.them { background: #f6f9ff; color: #31445f; align-self: flex-start; border-radius: 14px 14px 14px 4px; }
.aics-bubble.me { background: linear-gradient(135deg, #2563eb, #3b82f6); color: #fff; align-self: flex-end; border-radius: 14px 14px 4px 14px; }

.aics-test-form { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.aics-test-form textarea { width: 100%; padding: 8px 12px; border: 1px solid #dbe6f6; border-radius: 10px; font-size: 12px; resize: vertical; outline: 0; }
.aics-test-form button { align-self: flex-end; padding: 6px 14px; }

.aics-error { color: #ef4444; font-size: 12px; margin-top: 8px; }
.aics-warn { color: #f59e0b; font-size: 12px; margin-top: 8px; }

.aics-status-list { display: flex; flex-direction: column; gap: 10px; padding: 4px 0; }
.aics-status-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.aics-status-row span { color: #6b7a90; }
.aics-status-row b { color: #12233f; }
.aics-status-row b.green { color: #16a34a; }
.aics-status-row b.red { color: #ef4444; }

@media (max-width: 1200px) {
  .aics-grid { grid-template-columns: 1fr; }
}

.aics-kb-textarea { min-height: 160px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; line-height: 1.6; }
.aics-kb-footer { display: flex; justify-content: flex-end; margin-top: 4px; }
.aics-kb-count { font-size: 11px; color: #99a4b4; }

.aics-upload-area { display: flex; align-items: center; gap: 10px; margin-top: 8px; padding: 10px; border: 1px dashed #dbe6f6; border-radius: 10px; background: #fafbfc; flex-wrap: wrap; }
.aics-upload-btn { padding: 6px 14px; border-radius: 8px; border: 1px solid #bfdbfe; background: #fff; color: #2563eb; font-size: 12px; font-weight: 600; cursor: pointer; transition: all .2s; }
.aics-upload-btn:hover:not(:disabled) { background: #eff6ff; }
.aics-upload-btn:disabled { opacity: .6; cursor: not-allowed; }
.aics-upload-hint { font-size: 11px; color: #99a4b4; }
.aics-entry-list { display: grid; gap: 12px; margin-top: 10px; }
.aics-entry-card { border: 1px solid #e5edf8; border-radius: 10px; padding: 12px; background: #fbfdff; display: grid; gap: 8px; }
.aics-entry-head { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 8px; align-items: center; }
.aics-entry-remove { padding: 6px 10px; border-radius: 8px; border: 1px solid #fecaca; background: #fff; color: #ef4444; font-size: 12px; cursor: pointer; }
.aics-entry-meta { display: flex; justify-content: space-between; gap: 12px; font-size: 11px; color: #99a4b4; }
.aics-empty-tip { font-size: 12px; color: #94a3b8; padding: 10px 0 2px; }

/* 系统默认知识库 / 默认聊天规则：只读展示，灰底折叠面板 */
.aics-default-section {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.aics-default-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.aics-default-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 999px;
  background: #e0e7ff;
  color: #4338ca;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.3px;
}
.aics-default-title {
  font-size: 12px;
  color: #475569;
  font-weight: 600;
}
.aics-default-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}
.aics-default-card > summary {
  list-style: none;
  cursor: pointer;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: #1e293b;
  user-select: none;
}
.aics-default-card > summary::-webkit-details-marker { display: none; }
.aics-default-card > summary::before {
  content: '▸';
  display: inline-block;
  color: #94a3b8;
  font-size: 11px;
  transition: transform 0.15s;
}
.aics-default-card[open] > summary::before {
  transform: rotate(90deg);
}
.aics-default-card > summary strong {
  flex: 1;
  font-weight: 600;
  font-size: 12.5px;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.aics-default-meta {
  font-size: 11px;
  color: #94a3b8;
  flex-shrink: 0;
}
.aics-default-pre {
  margin: 0;
  padding: 10px 12px;
  border-top: 1px dashed #e2e8f0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 280px;
  overflow-y: auto;
  background: #fbfdff;
}

.aics-label-row { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.aics-restore-btn { padding: 2px 8px; border-radius: 6px; border: 1px solid #e2e8f0; background: #fff; color: #6b7a90; font-size: 11px; cursor: pointer; transition: all .2s; }
.aics-restore-btn:hover { color: #2563eb; border-color: #bfdbfe; }

.aics-error-box, .aics-warn-box { display: flex; flex-direction: column; gap: 8px; padding: 10px; border-radius: 8px; margin-top: 8px; }
.aics-error-box { background: #fef2f2; border: 1px solid #fecaca; }
.aics-warn-box { background: #fffbeb; border: 1px solid #fde68a; }
.aics-retry-btn { align-self: flex-start; padding: 4px 12px; border-radius: 6px; border: 1px solid #dbe6f6; background: #fff; color: #2563eb; font-size: 12px; cursor: pointer; }
.aics-retry-btn:hover:not(:disabled) { background: #eff6ff; }
.aics-retry-btn:disabled { opacity: .6; cursor: not-allowed; }
</style>
