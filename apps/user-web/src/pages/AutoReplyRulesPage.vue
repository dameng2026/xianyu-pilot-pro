<template>
  <div class="arr-page">
    <section class="arr-hero">
      <div class="arr-hero-copy">
        <h2>自动回复规则</h2>
        <p>
          当买家发送的消息命中你设置的规则时，系统会自动回复对应内容；未命中时可按规则交给 AI 生成或转人工处理。
        </p>
        <div class="arr-guide">
          <div class="arr-guide-step">
            <span class="arr-guide-num">1</span>
            <span class="arr-guide-text">选择适用账号与商品</span>
          </div>
          <span class="arr-guide-arrow">→</span>
          <div class="arr-guide-step">
            <span class="arr-guide-num">2</span>
            <span class="arr-guide-text">设置匹配关键词与回复内容</span>
          </div>
          <span class="arr-guide-arrow">→</span>
          <div class="arr-guide-step">
            <span class="arr-guide-num">3</span>
            <span class="arr-guide-text">保存并开启规则即生效</span>
          </div>
        </div>
      </div>
      <div class="arr-hero-right">
        <button type="button" class="arr-primary-btn" :disabled="!accounts.length" @click="openCreate">
          + 新增规则
        </button>
        <div class="arr-hero-actions">
          <button type="button" class="arr-hero-btn" :disabled="!filteredRules.length" @click="exportRulesCsv">
            导出 CSV
          </button>
          <button type="button" class="arr-hero-btn" :disabled="!accounts.length" @click="importInputRef?.click()">
            导入 CSV
          </button>
          <input ref="importInputRef" type="file" accept=".csv,text/csv" class="hidden" @change="handleImportCsv" />
        </div>
      </div>
    </section>

    <section v-if="stats" class="arr-stats card">
      <div class="arr-stat">
        <span class="arr-stat-icon">⚡</span>
        <div class="arr-stat-body">
          <span>今日命中</span>
          <strong>{{ stats.todayCount ?? 0 }}</strong>
        </div>
      </div>
      <div class="arr-stat">
        <span class="arr-stat-icon">📅</span>
        <div class="arr-stat-body">
          <span>统计天数</span>
          <strong>{{ stats.days ?? 0 }}</strong>
        </div>
      </div>
      <div class="arr-stat">
        <span class="arr-stat-icon">📤</span>
        <div class="arr-stat-body">
          <span>自动发送</span>
          <strong>{{ stats.actions?.auto_send_allowed ?? 0 }}</strong>
        </div>
      </div>
      <div class="arr-stat">
        <span class="arr-stat-icon">👤</span>
        <div class="arr-stat-body">
          <span>建议人工</span>
          <strong>{{ stats.actions?.suggest_only ?? 0 }}</strong>
        </div>
      </div>
      <button type="button" class="arr-ghost-btn" @click="openPreview">命中预览</button>
    </section>

    <section class="arr-toolbar card">
      <div class="arr-view-switch">
        <button
          type="button"
          class="arr-view-btn"
          :class="{ active: viewMode === 'rules' }"
          @click="switchView('rules')"
        >
          规则列表
        </button>
        <button
          type="button"
          class="arr-view-btn"
          :class="{ active: viewMode === 'logs' }"
          @click="switchView('logs')"
        >
          命中日志
        </button>
      </div>
      <label class="arr-field">
        <span>账号</span>
        <select v-model="query.accountId" @change="onAccountChange">
          <option value="">全部账号</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
          </option>
        </select>
      </label>
      <label class="arr-field grow">
        <span>本地搜索</span>
        <input v-model="localKeyword" type="text" placeholder="按规则名称 / 关键词 / 回复内容过滤" />
      </label>
      <div class="arr-pager">
        <button type="button" class="arr-ghost-btn" :disabled="current <= 1 || loading" @click="loadRules(current - 1)">
          上一页
        </button>
        <span>第 {{ current }} / {{ totalPages }} 页</span>
        <button type="button" class="arr-ghost-btn" :disabled="current >= totalPages || loading" @click="loadRules(current + 1)">
          下一页
        </button>
      </div>
    </section>

    <section v-if="viewMode === 'rules'" class="arr-list card">
      <div v-if="loading" class="arr-state">规则加载中…</div>
      <div v-else-if="loadError" class="arr-state error">
        {{ loadError }}
        <button type="button" class="arr-link-btn" @click="loadRules(current)">重试</button>
      </div>
      <div v-else-if="!rules.length" class="arr-empty">
        <div class="arr-empty-icon">⚡</div>
        <strong class="arr-empty-title">还没有自动回复规则</strong>
        <p class="arr-empty-desc">
          设置规则后，买家消息命中关键词即自动回复，第一时间响应咨询、避免漏单。
        </p>
        <div class="arr-empty-steps">
          <span><b>1</b> 选择账号与商品</span>
          <span><b>2</b> 设置关键词与回复</span>
          <span><b>3</b> 保存并开启</span>
        </div>
        <button type="button" class="arr-primary-btn" :disabled="!accounts.length" @click="openCreate">
          + 创建第一条规则
        </button>
        <button v-if="!accounts.length" type="button" class="arr-link-btn" @click="loadAccounts">重新加载账号</button>
      </div>
      <div v-else-if="!filteredRules.length" class="arr-empty">
        <div class="arr-empty-icon">🔍</div>
        <strong class="arr-empty-title">未找到匹配的规则</strong>
        <p class="arr-empty-desc">当前本地搜索没有命中任何规则，试试其他关键词。</p>
      </div>
      <div v-else class="arr-table-wrap">
        <table class="arr-table">
          <thead>
            <tr>
              <th>规则名称</th>
              <th>账号</th>
              <th>商品</th>
              <th>匹配模式</th>
              <th>关键词</th>
              <th>回复模式</th>
              <th>优先级</th>
              <th>状态</th>
              <th class="arr-op-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rule in filteredRules" :key="rule.id">
              <td>{{ rule.ruleName }}</td>
              <td>{{ accountLabel(rule.accountId) }}</td>
              <td>{{ rule.xyGoodsId ? goodsLabel(rule.xyGoodsId) : '通用' }}</td>
              <td>
                <span class="arr-type-badge">{{ matchTypeLabel(rule.matchType) }}</span>
              </td>
              <td class="arr-keyword-cell" :title="rule.matchKeywords">{{ rule.matchKeywords || '—' }}</td>
              <td>
                <span class="arr-mode-badge" :class="rule.replyMode === 'ai' ? 'ai' : 'text'">
                  {{ rule.replyMode === 'ai' ? 'AI 生成' : '固定文本' }}
                </span>
              </td>
              <td><span class="arr-priority-pill">{{ rule.priority ?? 0 }}</span></td>
              <td>
                <button
                  type="button"
                  class="arr-toggle"
                  :class="{ on: rule.status === 1 }"
                  @click="toggleRule(rule)"
                >
                  {{ rule.status === 1 ? '启用' : '禁用' }}
                </button>
              </td>
              <td>
                <div class="arr-ops">
                  <button type="button" class="arr-link-btn" @click="openEdit(rule)">编辑</button>
                  <button type="button" class="arr-link-btn danger" @click="removeRule(rule)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-else class="arr-list card">
      <div v-if="logLoading" class="arr-state">日志加载中…</div>
      <div v-else-if="logError" class="arr-state error">
        {{ logError }}
        <button type="button" class="arr-link-btn" @click="loadLogs(logPage)">重试</button>
      </div>
      <div v-else-if="!logs.length" class="arr-state empty">暂无自动回复命中日志。</div>
      <div v-else class="arr-table-wrap">
        <table class="arr-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>账号</th>
              <th>规则</th>
              <th>买家消息</th>
              <th>回复内容</th>
              <th>动作</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in logs" :key="item.id">
              <td>{{ formatTime(item.createdTime) }}</td>
              <td>{{ accountLabel(item.accountId) }}</td>
              <td>{{ item.ruleId ? `规则 #${item.ruleId}` : (item.hitType === 'default_reply' ? '默认回复' : 'AI 客服') }}</td>
              <td class="arr-keyword-cell" :title="item.triggerMessage">{{ item.triggerMessage || '—' }}</td>
              <td class="arr-keyword-cell" :title="item.replyContent">{{ item.replyContent || '—' }}</td>
              <td>{{ item.action === 'auto_send_allowed' ? '自动发送' : (item.action === 'suggest_only' ? '仅建议' : item.action || '—') }}</td>
              <td>{{ item.status === 1 ? '成功' : (item.status === 0 ? '失败/未发送' : item.status) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="arr-log-pager">
          <button type="button" class="arr-ghost-btn" :disabled="logPage <= 1 || logLoading" @click="loadLogs(logPage - 1)">
            上一页
          </button>
          <span>第 {{ logPage }} / {{ logTotalPages }} 页</span>
          <button type="button" class="arr-ghost-btn" :disabled="logPage >= logTotalPages || logLoading" @click="loadLogs(logPage + 1)">
            下一页
          </button>
        </div>
      </div>
    </section>

    <div v-if="showForm" class="arr-modal-mask" @click.self="closeForm">
      <div class="arr-modal">
        <div class="arr-modal-head">
          <h3>{{ editing ? '编辑自动回复规则' : '新增自动回复规则' }}</h3>
          <button type="button" class="arr-icon-btn" aria-label="关闭" @click="closeForm">×</button>
        </div>
        <div class="arr-modal-body">
          <div class="arr-form-section">
            <div class="arr-form-section-title">
              <span>基础信息</span>
              <small>确定规则作用在哪个账号与商品</small>
            </div>
            <label class="arr-field">
              <span>规则名称 <em>*</em></span>
              <input v-model="form.ruleName" type="text" placeholder="例如：常见咨询自动应答" maxlength="80" />
            </label>
            <label class="arr-field">
              <span>适用账号 <em>*</em></span>
              <select v-model="form.accountId" :disabled="!!editing">
                <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                  {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
                </option>
              </select>
            </label>
            <label class="arr-field">
              <span>绑定商品（可选）</span>
              <select v-model="form.xyGoodsId">
                <option value="">通用（所有商品）</option>
                <option v-for="p in products" :key="p.goodsId" :value="p.goodsId">
                  {{ p.title || p.goodsId }}（{{ p.goodsId }}）
                </option>
              </select>
              <small>绑定后仅该商品会话命中此规则；优先级高于通用规则。</small>
            </label>
          </div>

          <div class="arr-form-section">
            <div class="arr-form-section-title">
              <span>匹配与回复</span>
              <small>设置买家消息如何命中、回复什么内容</small>
            </div>
            <div class="arr-grid">
              <label class="arr-field">
                <span>匹配模式 <em>*</em></span>
                <select v-model="form.matchType">
                  <option value="any">任意关键词（默认）</option>
                  <option value="all">全部关键词</option>
                  <option value="regex">正则表达式</option>
                  <option value="ai">AI 意图（全部消息）</option>
                </select>
              </label>
              <label class="arr-field">
                <span>回复模式 <em>*</em></span>
                <select v-model="form.replyMode">
                  <option value="text">固定文本</option>
                  <option value="ai">AI 生成</option>
                </select>
              </label>
            </div>
            <label v-if="form.matchType !== 'ai'" class="arr-field">
              <span>匹配关键词 <em>*</em></span>
              <textarea
                v-model="form.matchKeywords"
                rows="3"
                placeholder="多个关键词用逗号或换行分隔；all 模式需全部命中，regex 模式每行一个正则"
              />
            </label>
            <label class="arr-field">
              <span>回复内容 <em>*</em></span>
              <textarea
                v-model="form.replyContent"
                rows="4"
                placeholder="支持变量：{send_user_name} 买家昵称、{send_user_id} 买家ID、{send_message} 买家消息；用 ###### 分隔可拆分为多条消息；图片关键词可留空"
              />
            </label>
            <label class="arr-field">
              <span>回复图片（图片关键词，可选）</span>
              <div class="arr-image-row">
                <input v-model="form.replyImage" type="text" placeholder="本地图片地址或闲鱼CDN图片URL" />
                <label class="arr-file-btn">
                  上传图片
                  <input type="file" accept="image/*" :disabled="uploading" @change="handleImageUpload" />
                </label>
              </div>
              <img v-if="form.replyImage" :src="form.replyImage" alt="回复图片预览" class="arr-image-preview" />
              <small>文本模式且填写图片时，命中关键词会先发图片再发文本；AI 模式忽略图片。</small>
            </label>
          </div>

          <div class="arr-form-section">
            <div class="arr-form-section-title">
              <span>高级选项（可选）</span>
              <small>控制优先级、每日上限与安全策略</small>
            </div>
            <div class="arr-grid">
              <label class="arr-field">
                <span>优先级</span>
                <input v-model.number="form.priority" type="number" min="0" max="9999" />
                <small>数字越大越先命中</small>
              </label>
              <label class="arr-field">
                <span>每日回复上限（0 不限）</span>
                <input v-model.number="form.maxDailyReplies" type="number" min="0" max="10000" />
              </label>
            </div>
            <div class="arr-grid">
              <label class="arr-field">
                <span>人工接管关键词</span>
                <input v-model="form.handoffKeywords" type="text" placeholder="例如：退款,投诉,平台介入" />
                <small>命中后不再自动回复，转人工处理</small>
              </label>
              <label class="arr-field">
                <span>议价底线（选填）</span>
                <input v-model.number="form.priceFloor" type="number" min="0" step="0.01" />
                <small>低于此价的议价消息自动建议人工</small>
              </label>
            </div>
            <label class="arr-switch">
              <input v-model="form.safeMode" type="checkbox" :true-value="1" :false-value="0" />
              <span>安全模式：命中人工接管关键词或高风险消息时仅建议不自动发送</span>
            </label>
          </div>

          <p v-if="formError" class="arr-error">{{ formError }}</p>
        </div>
        <div class="arr-modal-foot">
          <button type="button" class="arr-ghost-btn" @click="closeForm">取消</button>
          <button type="button" class="arr-primary-btn" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showPreview" class="arr-modal-mask" @click.self="showPreview = false">
      <div class="arr-modal small">
        <div class="arr-modal-head">
          <h3>命中预览</h3>
          <button type="button" class="arr-icon-btn" aria-label="关闭" @click="showPreview = false">×</button>
        </div>
        <div class="arr-modal-body">
          <label class="arr-field">
            <span>账号</span>
            <select v-model="preview.accountId">
              <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
              </option>
            </select>
          </label>
          <label class="arr-field">
            <span>买家消息 <em>*</em></span>
            <textarea v-model="preview.message" rows="3" placeholder="输入一条买家消息测试命中规则" />
          </label>
          <div v-if="previewResult" class="arr-preview-result">
            <div class="arr-preview-line">
              <span>命中：</span>
              <strong>{{ previewResult.matched ? `是（${previewResult.ruleName || '规则' + previewResult.ruleId}）` : '否' }}</strong>
            </div>
            <div class="arr-preview-line">
              <span>动作：</span>
              <strong>{{ previewResult.action === 'auto_send_allowed' ? '自动发送' : '仅建议/人工确认' }}</strong>
            </div>
            <div class="arr-preview-line">
              <span>回复内容：</span>
              <span>{{ previewResult.replySuggestion || '—' }}</span>
            </div>
            <div v-if="previewResult.safety?.reasons?.length" class="arr-preview-reasons">
              <div v-for="(reason, i) in previewResult.safety.reasons" :key="i">• {{ reason }}</div>
            </div>
          </div>
          <p v-if="previewError" class="arr-error">{{ previewError }}</p>
        </div>
        <div class="arr-modal-foot">
          <button type="button" class="arr-ghost-btn" @click="showPreview = false">关闭</button>
          <button type="button" class="arr-primary-btn" :disabled="previewing" @click="runPreview">
            {{ previewing ? '测试中…' : '测试命中' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getAccounts } from '../api/accounts.js'
import { getAutoReplyScopeProducts } from '../api/autoReplyScope.js'
import {
  createAutoReplyRule,
  deleteAutoReplyRule,
  getAutoReplyRules,
  getAutoReplyLogs,
  getAutoReplyStats,
  previewAutoReplyRule,
  updateAutoReplyRule,
} from '../api/autoReply.js'
import { uploadImage } from '../api/misc.js'

const accounts = ref([])
const products = ref([])
const rules = ref([])
const stats = ref(null)
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const previewing = ref(false)
const uploading = ref(false)
const loadError = ref('')
const formError = ref('')
const previewError = ref('')
const current = ref(1)
const pageSize = 20
const total = ref(0)
const showForm = ref(false)
const showPreview = ref(false)
const editing = ref(null)
const localKeyword = ref('')

const query = reactive({ accountId: '' })
const form = reactive({
  ruleName: '',
  accountId: '',
  xyGoodsId: '',
  matchType: 'any',
  matchKeywords: '',
  replyContent: '',
  replyImage: '',
  replyMode: 'text',
  priority: 0,
  safeMode: 1,
  handoffKeywords: '',
  priceFloor: null,
  maxDailyReplies: 0,
  status: 1,
})
const preview = reactive({ accountId: '', message: '' })
const previewResult = ref(null)
const importInputRef = ref(null)
const viewMode = ref('rules')
const logs = ref([])
const logPage = ref(1)
const logTotal = ref(0)
const logLoading = ref(false)
const logError = ref('')
const logPageSize = 20

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const logTotalPages = computed(() => Math.max(1, Math.ceil(logTotal.value / logPageSize)))
const accountMap = computed(() => {
  const map = {}
  for (const acc of accounts.value) map[acc.id] = acc
  return map
})
const productMap = computed(() => {
  const map = {}
  for (const p of products.value) map[p.goodsId] = p
  return map
})

const filteredRules = computed(() => {
  const kw = localKeyword.value.trim().toLowerCase()
  if (!kw) return rules.value
  return rules.value.filter(r => {
    return [r.ruleName, r.matchKeywords, r.replyContent, matchTypeLabel(r.matchType)]
      .filter(Boolean)
      .some(v => String(v).toLowerCase().includes(kw))
  })
})

function accountLabel(accountId) {
  const acc = accountMap.value[accountId]
  return acc ? (acc.nickname || acc.accountName || `账号 ${accountId}`) : `账号 ${accountId}`
}

function goodsLabel(goodsId) {
  const p = productMap.value[goodsId]
  return p ? (p.title || goodsId) : goodsId
}

function matchTypeLabel(type) {
  return {
    any: '任意关键词',
    all: '全部关键词',
    regex: '正则',
    ai: 'AI 意图',
  }[type] || type || '—'
}

function formatTime(value) {
  if (!value) return '—'
  const d = new Date(String(value).includes('T') ? value : String(value).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return value
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadAccounts() {
  try {
    const res = await getAccounts({ current: 1, size: 100 })
    const list = Array.isArray(res?.data) ? res.data : (res?.data?.records || [])
    accounts.value = list
    if (list.length && !form.accountId) form.accountId = list[0].id
    if (list.length && !preview.accountId) preview.accountId = list[0].id
  } catch (e) {
    loadError.value = e?.message || '账号列表加载失败'
  }
}

async function loadProducts(accountId) {
  if (!accountId) {
    products.value = []
    return
  }
  try {
    const res = await getAutoReplyScopeProducts(accountId, { force: true })
    products.value = Array.isArray(res?.data?.items) ? res.data.items : []
  } catch {
    products.value = []
  }
}

async function loadRules(page = 1) {
  loading.value = true
  loadError.value = ''
  try {
    const params = { current: page, size: pageSize }
    if (query.accountId) params.accountId = query.accountId
    const res = await getAutoReplyRules(params)
    rules.value = res?.data?.records || []
    total.value = Number(res?.data?.total || rules.value.length)
    current.value = page
  } catch (e) {
    loadError.value = e?.message || '规则加载失败'
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const res = await getAutoReplyStats({ days: 7 })
    stats.value = res?.data || null
  } catch {
    stats.value = null
  }
}

async function loadLogs(page = 1) {
  logLoading.value = true
  logError.value = ''
  try {
    const params = { current: page, size: logPageSize }
    if (query.accountId) params.accountId = query.accountId
    const res = await getAutoReplyLogs(params)
    logs.value = res?.data?.records || []
    logTotal.value = Number(res?.data?.total || logs.value.length)
    logPage.value = page
  } catch (e) {
    logError.value = e?.message || '日志加载失败'
  } finally {
    logLoading.value = false
  }
}

function switchView(mode) {
  viewMode.value = mode
  if (mode === 'logs') loadLogs(1)
}

function onAccountChange() {
  if (viewMode.value === 'logs') {
    loadLogs(1)
  } else {
    loadRules(1)
  }
}

async function openCreate() {
  editing.value = null
  formError.value = ''
  Object.assign(form, {
    ruleName: '',
    accountId: accounts.value[0]?.id || '',
    xyGoodsId: '',
    matchType: 'any',
    matchKeywords: '',
    replyContent: '',
    replyImage: '',
    replyMode: 'text',
    priority: 0,
    safeMode: 1,
    handoffKeywords: '',
    priceFloor: null,
    maxDailyReplies: 0,
    status: 1,
  })
  await loadProducts(form.accountId)
  showForm.value = true
}

function openEdit(rule) {
  editing.value = rule
  formError.value = ''
  Object.assign(form, {
    ruleName: rule.ruleName || '',
    accountId: rule.accountId,
    xyGoodsId: rule.xyGoodsId || '',
    matchType: rule.matchType || 'any',
    matchKeywords: rule.matchKeywords || '',
    replyContent: rule.replyContent || '',
    replyImage: rule.replyImage || '',
    replyMode: rule.replyMode || 'text',
    priority: rule.priority ?? 0,
    safeMode: rule.safeMode ?? 1,
    handoffKeywords: rule.handoffKeywords || '',
    priceFloor: rule.priceFloor ?? null,
    maxDailyReplies: rule.maxDailyReplies ?? 0,
    status: rule.status ?? 1,
  })
  loadProducts(rule.accountId)
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editing.value = null
  formError.value = ''
}

async function save() {
  formError.value = ''
  if (!form.ruleName.trim()) {
    formError.value = '请输入规则名称'
    return
  }
  if (!form.accountId) {
    formError.value = '请选择适用账号'
    return
  }
  if (form.matchType !== 'ai' && !form.matchKeywords.trim()) {
    formError.value = '非 AI 匹配模式必须填写匹配关键词'
    return
  }
  if (!form.replyContent.trim() && !form.replyImage.trim()) {
    formError.value = '请输入回复内容或上传回复图片'
    return
  }
  saving.value = true
  try {
    const payload = {
      ruleName: form.ruleName.trim(),
      accountId: form.accountId,
      xyGoodsId: form.xyGoodsId || null,
      matchType: form.matchType,
      matchKeywords: form.matchType === 'ai' ? '' : form.matchKeywords,
      replyContent: form.replyContent,
      replyImage: form.replyImage,
      replyMode: form.replyMode,
      priority: Number(form.priority) || 0,
      safeMode: Number(form.safeMode) || 0,
      handoffKeywords: form.handoffKeywords,
      priceFloor: form.priceFloor == null || form.priceFloor === '' ? null : Number(form.priceFloor),
      maxDailyReplies: Number(form.maxDailyReplies) || 0,
      status: form.status,
    }
    if (editing.value) {
      await updateAutoReplyRule(editing.value.id, payload)
    } else {
      await createAutoReplyRule(payload)
    }
    closeForm()
    await loadRules(current.value)
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
    const res = await uploadImage(form.accountId, file)
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

async function toggleRule(rule) {
  try {
    await updateAutoReplyRule(rule.id, {
      ruleName: rule.ruleName,
      accountId: rule.accountId,
      xyGoodsId: rule.xyGoodsId || null,
      matchType: rule.matchType,
      matchKeywords: rule.matchKeywords,
      replyContent: rule.replyContent,
      replyImage: rule.replyImage || '',
      replyMode: rule.replyMode,
      priority: rule.priority,
      safeMode: rule.safeMode,
      handoffKeywords: rule.handoffKeywords,
      priceFloor: rule.priceFloor,
      maxDailyReplies: rule.maxDailyReplies,
      status: rule.status === 1 ? 0 : 1,
    })
    rule.status = rule.status === 1 ? 0 : 1
  } catch (e) {
    loadError.value = e?.message || '切换状态失败'
  }
}

async function removeRule(rule) {
  if (!window.confirm(`确定删除规则「${rule.ruleName}」吗？`)) return
  deleting.value = true
  try {
    await deleteAutoReplyRule(rule.id)
    await loadRules(current.value)
  } catch (e) {
    loadError.value = e?.message || '删除失败'
  } finally {
    deleting.value = false
  }
}

function exportRulesCsv() {
  const header = [
    '规则名称', '账号ID', '匹配模式', '匹配关键词', '回复内容', '回复图片',
    '商品ID', '优先级', '安全模式', '人工接管关键词', '议价底线', '每日上限',
  ]
  const escape = value => {
    const text = value == null ? '' : String(value)
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  const lines = [header.map(escape).join(',')]
  for (const rule of filteredRules.value) {
    lines.push([
      rule.ruleName, rule.accountId, rule.matchType, rule.matchKeywords, rule.replyContent,
      rule.replyImage || '', rule.xyGoodsId || '', rule.priority ?? 0, rule.safeMode ?? 1,
      rule.handoffKeywords || '', rule.priceFloor ?? '', rule.maxDailyReplies ?? 0,
    ].map(escape).join(','))
  }
  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `auto-reply-rules-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        field += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      row.push(field)
      field = ''
    } else if (ch === '\n') {
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else if (ch !== '\r') {
      field += ch
    }
  }
  if (field || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows
}

async function handleImportCsv(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  try {
    const text = await file.text()
    const rows = parseCsv(text.replace(/^\ufeff/, ''))
    if (rows.length < 2) throw new Error('CSV 文件为空或缺少表头')
    const header = rows[0].map(h => h.trim())
    const idx = name => {
      const i = header.indexOf(name)
      if (i < 0) throw new Error(`CSV 缺少列：${name}`)
      return i
    }
    const iRule = idx('规则名称')
    const iAccount = idx('账号ID')
    const iMatch = idx('匹配模式')
    const iKeywords = idx('匹配关键词')
    const iContent = idx('回复内容')
    const iImage = idx('回复图片')
    const iGoods = idx('商品ID')
    const iPriority = idx('优先级')
    const iSafe = idx('安全模式')
    const iHandoff = idx('人工接管关键词')
    const iPrice = idx('议价底线')
    const iDaily = idx('每日上限')

    let success = 0
    let failed = 0
    const errors = []
    for (const row of rows.slice(1)) {
      if (!row.length || !row.some(c => String(c).trim())) continue
      const ruleName = (row[iRule] || '').trim()
      const accountId = (row[iAccount] || '').trim()
      if (!ruleName || !accountId) {
        failed++
        errors.push('缺少规则名称或账号ID')
        continue
      }
      try {
        await createAutoReplyRule({
          ruleName,
          accountId: Number(accountId),
          matchType: (row[iMatch] || 'any').trim(),
          matchKeywords: (row[iKeywords] || '').trim(),
          replyContent: (row[iContent] || '').trim(),
          replyImage: (row[iImage] || '').trim(),
          xyGoodsId: (row[iGoods] || '').trim() || null,
          replyMode: 'text',
          priority: Number(row[iPriority]) || 0,
          safeMode: Number(row[iSafe] ?? 1) || 1,
          handoffKeywords: (row[iHandoff] || '').trim(),
          priceFloor: row[iPrice] ? Number(row[iPrice]) : null,
          maxDailyReplies: Number(row[iDaily]) || 0,
        })
        success++
      } catch (err) {
        failed++
        errors.push(err?.message || '导入失败')
      }
    }
    await loadRules(1)
    loadError.value = ''
    window.alert(`导入完成：成功 ${success} 条，失败 ${failed} 条${errors.length ? `；${errors.slice(0, 3).join('；')}` : ''}`)
  } catch (err) {
    loadError.value = err?.message || 'CSV 导入失败'
  }
}

function openPreview() {
  previewError.value = ''
  previewResult.value = null
  if (!preview.accountId && accounts.value.length) preview.accountId = accounts.value[0].id
  showPreview.value = true
}

async function runPreview() {
  previewError.value = ''
  previewResult.value = null
  if (!preview.message.trim()) {
    previewError.value = '请输入买家消息'
    return
  }
  previewing.value = true
  try {
    const res = await previewAutoReplyRule({
      accountId: preview.accountId,
      message: preview.message,
    })
    previewResult.value = res?.data || res
  } catch (e) {
    previewError.value = e?.message || '预览失败'
  } finally {
    previewing.value = false
  }
}

onMounted(async () => {
  await loadAccounts()
  await Promise.all([loadRules(1), loadStats()])
})
</script>

<style scoped>
.arr-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.arr-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  background: linear-gradient(135deg, #7c3aed 0%, #1f6feb 100%);
  border-radius: 14px;
  color: #fff;
}

.arr-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.arr-hero-copy p {
  margin: 0;
  max-width: 780px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.94;
}

.arr-hero-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  flex-shrink: 0;
}

.arr-guide {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.arr-guide-step {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 999px;
  padding: 5px 12px 5px 6px;
}

.arr-guide-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  color: #1f6feb;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.arr-guide-text {
  font-size: 12px;
  line-height: 1.4;
  opacity: 0.98;
}

.arr-guide-arrow {
  font-size: 13px;
  opacity: 0.7;
}

.arr-hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.arr-hero-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.45);
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

.arr-hero-btn:hover {
  background: rgba(255, 255, 255, 0.24);
}

.arr-hero-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hidden {
  display: none;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.arr-stats {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 14px 18px;
  flex-wrap: wrap;
}

.arr-stat {
  display: flex;
  align-items: center;
  gap: 10px;
}

.arr-stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: #eef5ff;
  font-size: 17px;
  flex-shrink: 0;
}

.arr-stat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.arr-stat-body > span {
  font-size: 12px;
  color: #6b7280;
}

.arr-stat-body strong {
  font-size: 20px;
  color: #111827;
  line-height: 1.1;
}

.arr-stats .arr-ghost-btn {
  margin-left: auto;
}

.arr-toolbar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 16px;
  flex-wrap: wrap;
}

.arr-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 150px;
}

.arr-field.grow {
  flex: 1;
  min-width: 200px;
}

.arr-field > span {
  font-size: 12px;
  color: #6b7280;
}

.arr-field em {
  color: #ef4444;
  font-style: normal;
}

.arr-field input,
.arr-field select,
.arr-field textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  color: #111827;
  background: #fff;
  outline: none;
  box-sizing: border-box;
}

.arr-field textarea {
  resize: vertical;
}

.arr-field small {
  font-size: 12px;
  color: #8a94a6;
  line-height: 1.5;
}

.arr-field input:focus,
.arr-field select:focus,
.arr-field textarea:focus {
  border-color: #1f6feb;
  box-shadow: 0 0 0 2px rgba(31, 111, 235, 0.12);
}

.arr-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.arr-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
}

.arr-image-row {
  display: flex;
  gap: 10px;
}

.arr-image-row input {
  flex: 1;
}

.arr-file-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: 36px;
  padding: 0 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  background: #fff;
  white-space: nowrap;
}

.arr-file-btn input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.arr-image-preview {
  max-width: 180px;
  max-height: 120px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  object-fit: contain;
}

.arr-primary-btn,
.arr-ghost-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid transparent;
}

.arr-primary-btn {
  background: #1f6feb;
  color: #fff;
}

.arr-primary-btn:hover {
  background: #1858c0;
}

.arr-ghost-btn {
  background: #fff;
  border-color: #d1d5db;
  color: #374151;
}

.arr-ghost-btn:hover {
  border-color: #1f6feb;
  color: #1f6feb;
}

.arr-primary-btn:disabled,
.arr-ghost-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.arr-pager {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #6b7280;
  margin-left: auto;
}

.arr-view-switch {
  display: flex;
  background: #f3f4f6;
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}

.arr-view-btn {
  border: none;
  background: transparent;
  color: #6b7280;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
}

.arr-view-btn.active {
  background: #fff;
  color: #1f6feb;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.arr-log-pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 16px;
  font-size: 13px;
  color: #6b7280;
}

.arr-list {
  min-height: 180px;
}

.arr-state {
  padding: 48px 20px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}

.arr-state.error {
  color: #dc2626;
}

.arr-empty {
  padding: 56px 20px 48px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.arr-empty-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, #eef5ff 0%, #f3e8ff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  margin-bottom: 6px;
}

.arr-empty-title {
  font-size: 16px;
  color: #111827;
}

.arr-empty-desc {
  margin: 0;
  max-width: 460px;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.7;
}

.arr-empty-steps {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
  margin: 8px 0 14px;
}

.arr-empty-steps span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fafafa;
  font-size: 12px;
  color: #4b5563;
}

.arr-empty-steps b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #1f6feb;
  color: #fff;
  font-size: 11px;
}

.arr-table-wrap {
  overflow-x: auto;
}

.arr-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.arr-table th,
.arr-table td {
  padding: 11px 12px;
  border-bottom: 1px solid #f0f0f0;
  text-align: left;
  white-space: nowrap;
}

.arr-table th {
  background: #fafafa;
  color: #6b7280;
  font-weight: 600;
}

.arr-table tbody tr:hover {
  background: #f8faff;
}

.arr-keyword-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.arr-type-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #374151;
  font-size: 12px;
}

.arr-mode-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.arr-mode-badge.text {
  background: #eef2ff;
  color: #4338ca;
}

.arr-mode-badge.ai {
  background: #ecfdf5;
  color: #047857;
}

.arr-priority-pill {
  display: inline-block;
  min-width: 32px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  text-align: center;
}

.arr-toggle {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #6b7280;
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12px;
  cursor: pointer;
}

.arr-toggle.on {
  border-color: #10b981;
  background: #ecfdf5;
  color: #047857;
}

.arr-ops {
  display: flex;
  gap: 8px;
}

.arr-link-btn {
  border: none;
  background: none;
  color: #1f6feb;
  font-size: 13px;
  cursor: pointer;
  padding: 2px 4px;
}

.arr-link-btn.danger {
  color: #dc2626;
}

.arr-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(17, 24, 39, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.arr-modal {
  width: 620px;
  max-width: 100%;
  max-height: 92vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.18);
}

.arr-modal.small {
  width: 520px;
}

.arr-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 1;
}

.arr-modal-head h3 {
  margin: 0;
  font-size: 16px;
}

.arr-icon-btn {
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: #9ca3af;
  cursor: pointer;
}

.arr-form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid #eceff3;
  border-radius: 12px;
  background: #fcfcfd;
}

.arr-form-section + .arr-form-section {
  margin-top: 2px;
}

.arr-form-section-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 2px;
}

.arr-form-section-title span {
  font-size: 14px;
  font-weight: 600;
  color: #16213e;
}

.arr-form-section-title small {
  font-size: 12px;
  color: #8a94a6;
}

.arr-modal-body {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.arr-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f0f0f0;
  position: sticky;
  bottom: 0;
  background: #fff;
}

.arr-error {
  margin: 0;
  color: #dc2626;
  font-size: 13px;
}

.arr-preview-result {
  background: #f9fafb;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}

.arr-preview-line {
  display: flex;
  gap: 8px;
}

.arr-preview-line span:first-child {
  color: #6b7280;
  white-space: nowrap;
}

.arr-preview-reasons {
  color: #b45309;
  font-size: 12px;
  line-height: 1.7;
}
</style>
