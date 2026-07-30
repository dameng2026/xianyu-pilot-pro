<template>
  <div class="ai-cs-page">
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>AI 客服配置</h2>
          <p>
            统一管理"小梦"客服的运营统计、会话审计、计费配置与 RAG 知识库。前台用户向小梦发送的消息会按下方配置扣费并匹配知识库内容回复。
          </p>
        </div>
        <div class="actions">
          <ElButton :loading="statsLoading" @click="loadStats">刷新统计</ElButton>
        </div>
      </div>
    </ElCard>

    <ElCard shadow="never" class="tabs-card">
      <ElTabs v-model="activeTab" type="border-card" class="ai-cs-tabs">
        <!-- ===== Tab 1: 运营统计 ===== -->
        <ElTabPane label="运营统计" name="stats">
          <AdminDataState v-if="statsState === 'loading'" state="loading" title="正在读取运营统计" compact />
          <AdminDataState
            v-else-if="statsState === 'error'"
            state="error"
            title="运营统计暂不可用"
            :description="statsError"
            retry-text="重新加载"
            compact
            @retry="loadStats"
          />
          <template v-else>
            <div class="stats-grid">
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">总会话数</div>
                <div class="metric-value">{{ formatNumber(stats.totalSessions) }}</div>
                <div class="metric-sub">历史累计创建</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">活跃会话</div>
                <div class="metric-value">{{ formatNumber(stats.activeSessions) }}</div>
                <div class="metric-sub">当前 status=active</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">今日新增会话</div>
                <div class="metric-value">{{ formatNumber(stats.todaySessions) }}</div>
                <div class="metric-sub">按创建时间统计</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">总消息数</div>
                <div class="metric-value">{{ formatNumber(stats.totalMessages) }}</div>
                <div class="metric-sub">含用户与 AI 双向</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">今日消息数</div>
                <div class="metric-value">{{ formatNumber(stats.todayMessages) }}</div>
                <div class="metric-sub">按 created_time 当日</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">累计扣费 Token</div>
                <div class="metric-value">{{ formatNumber(stats.totalChargeTokens) }}</div>
                <div class="metric-sub">所有会话汇总</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">今日扣费 Token</div>
                <div class="metric-value">{{ formatNumber(stats.todayChargeTokens) }}</div>
                <div class="metric-sub">实际从用户余额扣除</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">闲聊次数</div>
                <div class="metric-value">{{ formatNumber(stats.casualCount) }}</div>
                <div class="metric-sub">is_casual=1 消息数</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">知识库条数</div>
                <div class="metric-value">{{ formatNumber(stats.knowledgeCount) }}</div>
                <div class="metric-sub">已启用的 RAG 条目</div>
              </ElCard>
              <ElCard shadow="never" class="metric-card">
                <div class="metric-label">工具调用次数</div>
                <div class="metric-value">{{ formatNumber(stats.toolCallCount) }}</div>
                <div class="metric-sub">累计工具调用记录</div>
              </ElCard>
            </div>
          </template>
        </ElTabPane>

        <!-- ===== Tab 2: 会话审计 ===== -->
        <ElTabPane label="会话审计" name="sessions">
          <div class="filter-bar">
            <ElInput
              v-model="sessionQuery.userId"
              placeholder="用户 ID"
              clearable
              style="width: 160px"
              @keyup.enter="searchSessions"
            />
            <ElSelect
              v-model="sessionQuery.status"
              clearable
              placeholder="状态"
              style="width: 120px"
              @change="searchSessions"
            >
              <ElOption label="活跃" value="active" />
              <ElOption label="已关闭" value="closed" />
            </ElSelect>
            <ElButton type="primary" @click="searchSessions">查询</ElButton>
            <ElButton @click="resetSessionQuery">重置</ElButton>
          </div>

          <AdminDataState v-if="sessionState === 'loading'" state="loading" title="正在读取会话列表" compact />
          <AdminDataState
            v-else-if="sessionState === 'error'"
            state="error"
            title="会话列表暂不可用"
            :description="sessionError"
            retry-text="重新加载"
            compact
            @retry="loadSessions"
          />
          <template v-else>
            <ElTable :data="sessionList.records" border stripe height="480">
              <template #empty><div class="empty-state">暂无会话记录</div></template>
              <ElTableColumn prop="id" label="ID" width="70" />
              <ElTableColumn label="用户" min-width="140">
                <template #default="{ row }">
                  <span>{{ row.userId }}</span>
                  <span v-if="row.username" class="session-username">（{{ row.username }}）</span>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="tenantId" label="租户 ID" width="90" />
              <ElTableColumn label="状态" width="100">
                <template #default="{ row }">
                  <ElTag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                    {{ row.status === 'active' ? '活跃' : '已关闭' }}
                  </ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="messageCount" label="消息数" width="90" />
              <ElTableColumn prop="casualCount" label="闲聊数" width="90" />
              <ElTableColumn prop="lastActiveTime" label="最后活跃" min-width="160" show-overflow-tooltip />
              <ElTableColumn prop="createdTime" label="创建时间" min-width="160" show-overflow-tooltip />
              <ElTableColumn label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <ElButton link type="primary" size="small" @click="openSessionMessages(row as AiCsSessionRow)">查看对话</ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
            <div class="pagination-bar">
              <ElPagination
                v-model:current-page="sessionQuery.current"
                v-model:page-size="sessionQuery.size"
                :total="sessionList.total"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="loadSessions"
                @size-change="loadSessions"
              />
            </div>
          </template>
        </ElTabPane>

        <!-- ===== Tab 3: 计费配置 ===== -->
        <ElTabPane label="计费配置" name="billing">
          <AdminDataState v-if="billingState === 'loading'" state="loading" title="正在读取计费配置" compact />
          <AdminDataState
            v-else-if="billingState === 'error'"
            state="error"
            title="计费配置暂不可用"
            :description="billingError"
            retry-text="重新加载"
            compact
            @retry="loadBillingConfig"
          />
          <template v-else>
            <ElAlert type="info" :closable="false" class="tip-alert" show-icon>
              <template #title>
                <span>
                  <b>计费规则</b>：每用户每日前 <b>{{ billingForm.dailyFreeQuota }}</b> 条消息免费；
                  超过后每条消息扣费 <b>{{ billingForm.perMessageTokens }}</b> Token。
                  当用户 Token 余额为 0 时，前端会引导充值。
                </span>
              </template>
            </ElAlert>

            <ElForm ref="billingFormRef" :model="billingForm" label-width="160px" style="max-width: 720px">
              <ElFormItem label="启用客服计费">
                <ElSwitch
                  v-model="billingForm.enabled"
                  :active-value="1"
                  :inactive-value="0"
                  active-text="启用"
                  inactive-text="禁用"
                />
                <div class="form-tip">关闭后，所有用户消息不扣费（仍受服务可用性限制）</div>
              </ElFormItem>
              <ElFormItem label="每条扣费 Token 数">
                <ElInputNumber
                  v-model="billingForm.perMessageTokens"
                  :min="0"
                  :step="1"
                  controls-position="right"
                  style="width: 220px"
                />
                <div class="form-tip">超出免费额度后，每条消息从用户余额扣除的 Token 数（默认 3）</div>
              </ElFormItem>
              <ElFormItem label="每日免费额度">
                <ElInputNumber
                  v-model="billingForm.dailyFreeQuota"
                  :min="0"
                  :step="1"
                  controls-position="right"
                  style="width: 220px"
                />
                <div class="form-tip">每用户每天可免费发送的消息条数（默认 10）</div>
              </ElFormItem>
              <ElFormItem label="上下文最大条数">
                <ElInputNumber
                  v-model="billingForm.maxContextMessages"
                  :min="1"
                  :step="1"
                  controls-position="right"
                  style="width: 220px"
                />
                <div class="form-tip">超过后会触发上下文压缩或提示用户开新会话</div>
              </ElFormItem>
              <ElFormItem label="闲聊阈值">
                <ElInputNumber
                  v-model="billingForm.casualThreshold"
                  :min="0"
                  :step="1"
                  controls-position="right"
                  style="width: 220px"
                />
                <div class="form-tip">连续闲聊超过该条数后，提醒用户创建任务</div>
              </ElFormItem>
              <ElFormItem label="闲聊提醒文案">
                <ElInput
                  v-model="billingForm.casualReminderText"
                  type="textarea"
                  :rows="2"
                  placeholder="例如：已闲聊多次，建议创建任务让我帮你处理具体业务哦。"
                />
              </ElFormItem>
              <ElFormItem>
                <ElButton type="primary" :loading="billingSaving" @click="onSaveBilling">保存配置</ElButton>
                <ElButton @click="loadBillingConfig">重置</ElButton>
              </ElFormItem>
            </ElForm>
          </template>
        </ElTabPane>

        <!-- ===== Tab 4: 知识库（RAG） ===== -->
        <ElTabPane label="RAG 知识库" name="knowledge">
          <div class="filter-bar">
            <ElSelect
              v-model="knowledgeQuery.category"
              clearable
              placeholder="分类"
              style="width: 180px"
              @change="searchKnowledge"
            >
              <ElOption
                v-for="cat in knowledgeCategories"
                :key="cat.key"
                :label="cat.label"
                :value="cat.key"
              />
            </ElSelect>
            <ElInput
              v-model="knowledgeQuery.keyword"
              placeholder="标题/关键词"
              clearable
              style="width: 220px"
              @keyup.enter="searchKnowledge"
            />
            <ElSelect
              v-model="knowledgeQuery.enabled"
              clearable
              placeholder="状态"
              style="width: 120px"
              @change="searchKnowledge"
            >
              <ElOption label="启用" value="1" />
              <ElOption label="禁用" value="0" />
            </ElSelect>
            <ElButton type="primary" @click="searchKnowledge">查询</ElButton>
            <ElButton @click="resetKnowledgeQuery">重置</ElButton>
            <div class="filter-bar-right">
              <ElButton type="warning" :loading="rebuilding" @click="onRebuildIndex">重建向量索引</ElButton>
              <ElButton type="primary" @click="openCreateKnowledge">新增条目</ElButton>
            </div>
          </div>

          <AdminDataState v-if="knowledgeState === 'loading'" state="loading" title="正在读取知识库" compact />
          <AdminDataState
            v-else-if="knowledgeState === 'error'"
            state="error"
            title="知识库列表暂不可用"
            :description="knowledgeError"
            retry-text="重新加载"
            compact
            @retry="loadKnowledge"
          />
          <template v-else>
            <ElTable :data="knowledgeList.records" border stripe height="480">
              <template #empty><div class="empty-state">暂无知识库条目</div></template>
              <ElTableColumn prop="id" label="ID" width="70" />
              <ElTableColumn label="分类" width="140">
                <template #default="{ row }">
                  <ElTag size="small">{{ categoryLabel(row.category) }}</ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="title" label="标题" min-width="180" show-overflow-tooltip />
              <ElTableColumn prop="keywords" label="关键词" min-width="160" show-overflow-tooltip />
              <ElTableColumn prop="priority" label="优先级" width="90" />
              <ElTableColumn prop="sortOrder" label="排序" width="80" />
              <ElTableColumn label="状态" width="90">
                <template #default="{ row }">
                  <ElTag :type="isRowEnabled(row.enabled) ? 'success' : 'info'" size="small">
                    {{ isRowEnabled(row.enabled) ? '启用' : '禁用' }}
                  </ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="updatedTime" label="更新时间" min-width="160" show-overflow-tooltip />
              <ElTableColumn label="操作" width="140" fixed="right">
                <template #default="{ row }">
                  <ElButton link type="primary" size="small" @click="openEditKnowledge(row as AiCsKnowledgeRow)">编辑</ElButton>
                  <ElButton link type="danger" size="small" @click="onDeleteKnowledge(row as AiCsKnowledgeRow)">删除</ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
            <div class="pagination-bar">
              <ElPagination
                v-model:current-page="knowledgeQuery.current"
                v-model:page-size="knowledgeQuery.size"
                :total="knowledgeList.total"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="loadKnowledge"
                @size-change="loadKnowledge"
              />
            </div>
          </template>
        </ElTabPane>
      </ElTabs>
    </ElCard>

    <!-- ===== 会话消息审计抽屉 ===== -->
    <ElDrawer v-model="sessionDrawerVisible" title="会话消息审计" size="60%" destroy-on-close>
      <div v-if="currentSession" class="session-meta">
        <ElTag type="info">会话 #{{ currentSession.id }}</ElTag>
        <ElTag>用户 {{ currentSession.userId }}{{ currentSession.username ? ` (${currentSession.username})` : '' }}</ElTag>
        <ElTag :type="currentSession.status === 'active' ? 'success' : 'info'">
          {{ currentSession.status === 'active' ? '活跃' : '已关闭' }}
        </ElTag>
        <div class="session-meta-right">
          <ElRadioGroup v-model="messageView" size="small" @change="onMessageViewChange">
            <ElRadioButton label="bubble">对话视图</ElRadioButton>
            <ElRadioButton label="table">表格视图</ElRadioButton>
          </ElRadioGroup>
        </div>
      </div>
      <AdminDataState v-if="messageState === 'loading'" state="loading" title="正在读取消息" compact />
      <AdminDataState
        v-else-if="messageState === 'error'"
        state="error"
        title="消息读取失败"
        :description="messageError"
        retry-text="重试"
        compact
        @retry="reloadSessionMessages"
      />
      <template v-else>
        <!-- 对话气泡视图：按时间正序展示完整对话 -->
        <div v-if="messageView === 'bubble'" class="chat-bubble-view">
          <template v-if="bubbleMessages.length === 0">
            <div class="empty-state">暂无消息</div>
          </template>
          <template v-else>
            <div
              v-for="msg in bubbleMessages"
              :key="msg.id"
              class="chat-row"
              :class="`chat-${msg.role || 'system'}`"
            >
              <div class="chat-avatar" :class="`avatar-${msg.role || 'system'}`">
                {{ roleInitial(msg.role) }}
              </div>
              <div class="chat-content-wrap">
                <div class="chat-meta">
                  <span class="chat-role">{{ roleLabel(msg.role) }}</span>
                  <span v-if="msg.username" class="chat-username">{{ msg.username }}</span>
                  <ElTag v-if="isRowEnabled(msg.isCasual)" type="warning" size="small" effect="plain">闲聊</ElTag>
                  <span v-if="msg.tokensCharged" class="chat-tokens">扣 {{ msg.tokensCharged }} Token</span>
                  <span class="chat-time">{{ msg.createdTime || '' }}</span>
                </div>
                <div class="chat-bubble" :class="`bubble-${msg.role || 'system'}`">
                  <pre class="chat-bubble-text">{{ msg.content || '' }}</pre>
                </div>
                <details v-if="parseToolCalls(msg.toolCalls).length" class="chat-tool-details">
                  <summary>工具调用 ({{ parseToolCalls(msg.toolCalls).length }})</summary>
                  <pre class="chat-tool-json">{{ formatToolCalls(msg.toolCalls) }}</pre>
                </details>
              </div>
            </div>
          </template>
        </div>
        <!-- 表格视图：保留原分页表格 -->
        <template v-else>
          <ElTable :data="messageList.records" border stripe height="600">
            <template #empty><div class="empty-state">暂无消息</div></template>
            <ElTableColumn prop="id" label="ID" width="70" />
            <ElTableColumn label="角色" width="100">
              <template #default="{ row }">
                <ElTag :type="roleTagType(row.role)" size="small">{{ roleLabel(row.role) }}</ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn label="内容" min-width="320">
              <template #default="{ row }">
                <div class="message-content-cell">{{ row.content }}</div>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="tokensCharged" label="扣费 Token" width="110" />
            <ElTableColumn label="闲聊" width="80">
              <template #default="{ row }">
                <ElTag v-if="isRowEnabled(row.isCasual)" type="warning" size="small">闲聊</ElTag>
                <span v-else>—</span>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="createdTime" label="时间" min-width="160" show-overflow-tooltip />
          </ElTable>
          <div class="pagination-bar">
            <ElPagination
              v-model:current-page="messageQuery.current"
              v-model:page-size="messageQuery.size"
              :total="messageList.total"
              :page-sizes="[20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              @current-change="loadSessionMessages"
              @size-change="loadSessionMessages"
            />
          </div>
        </template>
      </template>
    </ElDrawer>

    <!-- ===== 知识库新增/编辑抽屉 ===== -->
    <ElDrawer v-model="knowledgeDrawerVisible" :title="knowledgeDrawerTitle" size="55%" destroy-on-close>
      <ElForm
        ref="knowledgeFormRef"
        :model="knowledgeForm"
        :rules="knowledgeRules"
        label-width="100px"
      >
        <ElFormItem label="分类" prop="category">
          <ElSelect v-model="knowledgeForm.category" placeholder="选择分类" style="width: 100%">
            <ElOption
              v-for="cat in knowledgeCategories"
              :key="cat.key"
              :label="cat.label"
              :value="cat.key"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="标题" prop="title">
          <ElInput v-model="knowledgeForm.title" placeholder="知识库条目标题" maxlength="200" show-word-limit />
        </ElFormItem>
        <ElFormItem label="关键词" prop="keywords">
          <ElInput
            v-model="knowledgeForm.keywords"
            placeholder="多个关键词用英文逗号分隔，例如：退货,退款,售后"
            maxlength="500"
          />
        </ElFormItem>
        <ElFormItem label="内容" prop="content">
          <ElInput
            v-model="knowledgeForm.content"
            type="textarea"
            :rows="10"
            placeholder="知识库条目正文，支持多行文本"
            maxlength="10000"
            show-word-limit
          />
        </ElFormItem>
        <ElRow :gutter="12">
          <ElCol :span="12">
            <ElFormItem label="优先级">
              <ElInputNumber
                v-model="knowledgeForm.priority"
                :min="0"
                :max="9999"
                :step="1"
                controls-position="right"
                style="width: 100%"
              />
              <div class="form-tip">数值越大优先级越高</div>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="排序">
              <ElInputNumber
                v-model="knowledgeForm.sortOrder"
                :min="0"
                :max="9999"
                :step="1"
                controls-position="right"
                style="width: 100%"
              />
              <div class="form-tip">同优先级下数值小的靠前</div>
            </ElFormItem>
          </ElCol>
        </ElRow>
        <ElFormItem label="状态">
          <ElSwitch
            v-model="knowledgeForm.enabled"
            :active-value="1"
            :inactive-value="0"
            active-text="启用"
            inactive-text="禁用"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="knowledgeDrawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="knowledgeSaving" @click="onSaveKnowledge">保存</ElButton>
      </template>
    </ElDrawer>
  </div>
</template>

<script setup lang="ts">
  import type { FormInstance, FormRules } from 'element-plus'
  import { ElMessage, ElMessageBox } from 'element-plus'
  import {
    deleteAiCsKnowledge,
    getAiCsBillingConfig,
    getAiCsKnowledgeCategories,
    getAiCsKnowledgeDetail,
    getAiCsStats,
    listSessionAiCsMessages,
    pageAiCsKnowledge,
    pageAiCsMessages,
    pageAiCsSessions,
    rebuildAiCsKnowledgeIndex,
    saveAiCsBillingConfig,
    saveAiCsKnowledge,
    type AiCsBillingConfig,
    type AiCsKnowledgeCategory,
    type AiCsKnowledgeForm,
    type AiCsKnowledgeRow,
    type AiCsMessageRow,
    type AiCsSessionRow,
    type AiCsStats,
  } from '@/api/ai-cs'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminAiCs' })

  const route = useRoute()

  // ===== Tab 切换（支持路由 meta.activeTab 进入指定 Tab） =====
  const activeTab = ref<'stats' | 'sessions' | 'billing' | 'knowledge'>(
    (route.meta?.activeTab as any) === 'knowledge' ? 'knowledge' : 'stats'
  )

  // ===== 统计 =====
  const stats = ref<AiCsStats>({})
  const statsLoading = ref(false)
  const statsState = ref<'loading' | 'ready' | 'error'>('loading')
  const statsError = ref('')

  async function loadStats() {
    statsLoading.value = true
    statsState.value = 'loading'
    statsError.value = ''
    try {
      const data = await getAiCsStats()
      stats.value = data || {}
      statsState.value = 'ready'
    } catch (error: unknown) {
      stats.value = {}
      statsError.value = getErrorMessage(error, '统计读取失败，请稍后重试。')
      statsState.value = 'error'
    } finally {
      statsLoading.value = false
    }
  }

  // ===== 会话审计 =====
  const sessionQuery = reactive({
    current: 1,
    size: 20,
    userId: '' as string | number | null,
    status: '' as string | null,
  })
  const sessionList = reactive({ records: [] as AiCsSessionRow[], total: 0 })
  const sessionState = ref<'loading' | 'ready' | 'error'>('loading')
  const sessionError = ref('')

  async function loadSessions() {
    sessionState.value = 'loading'
    sessionError.value = ''
    try {
      const params: any = { current: sessionQuery.current, size: sessionQuery.size }
      if (sessionQuery.userId !== '' && sessionQuery.userId !== null) {
        const uid = Number(sessionQuery.userId)
        if (Number.isFinite(uid)) params.userId = uid
      }
      if (sessionQuery.status) params.status = sessionQuery.status
      const p = await pageAiCsSessions(params)
      sessionList.records = p.records || []
      sessionList.total = Number.isFinite(Number(p.total)) ? Number(p.total) : p.records.length
      sessionState.value = 'ready'
    } catch (error: unknown) {
      sessionError.value = getErrorMessage(error, '会话列表读取失败。')
      sessionState.value = 'error'
    }
  }

  function searchSessions() {
    sessionQuery.current = 1
    loadSessions()
  }

  function resetSessionQuery() {
    sessionQuery.userId = ''
    sessionQuery.status = ''
    sessionQuery.current = 1
    loadSessions()
  }

  // ===== 会话消息抽屉 =====
  const sessionDrawerVisible = ref(false)
  const currentSession = ref<AiCsSessionRow | null>(null)
  const messageQuery = reactive({ current: 1, size: 50, sessionId: null as number | null })
  const messageList = reactive({ records: [] as AiCsMessageRow[], total: 0 })
  const messageState = ref<'loading' | 'ready' | 'error'>('loading')
  const messageError = ref('')
  // 消息视图切换：bubble=对话气泡视图（按时间正序，完整内容），table=表格视图（分页）
  // 默认 bubble，更直观地查看完整对话流，符合"点击查看详情查看对话记录"的需求
  const messageView = ref<'bubble' | 'table'>('bubble')
  // 对话气泡视图数据：一次性加载该会话全部消息（按时间正序）
  const bubbleMessages = ref<AiCsMessageRow[]>([])

  function openSessionMessages(row: AiCsSessionRow) {
    currentSession.value = row
    messageQuery.sessionId = Number(row.id)
    messageQuery.current = 1
    bubbleMessages.value = []
    sessionDrawerVisible.value = true
    // 默认对话视图：加载完整消息流；切换到表格视图时再走分页
    if (messageView.value === 'bubble') {
      loadBubbleMessages()
    } else {
      loadSessionMessages()
    }
  }

  async function loadSessionMessages() {
    if (!messageQuery.sessionId) return
    messageState.value = 'loading'
    messageError.value = ''
    try {
      const p = await pageAiCsMessages({
        current: messageQuery.current,
        size: messageQuery.size,
        sessionId: messageQuery.sessionId,
      })
      messageList.records = p.records || []
      messageList.total = Number.isFinite(Number(p.total)) ? Number(p.total) : p.records.length
      messageState.value = 'ready'
    } catch (error: unknown) {
      messageError.value = getErrorMessage(error, '消息读取失败。')
      messageState.value = 'error'
    }
  }

  // 加载该会话的全部消息（按时间正序，完整内容），用于对话气泡视图
  async function loadBubbleMessages() {
    if (!messageQuery.sessionId) return
    messageState.value = 'loading'
    messageError.value = ''
    try {
      const list = await listSessionAiCsMessages(messageQuery.sessionId)
      bubbleMessages.value = Array.isArray(list) ? list : []
      messageState.value = 'ready'
    } catch (error: unknown) {
      messageError.value = getErrorMessage(error, '消息读取失败。')
      bubbleMessages.value = []
      messageState.value = 'error'
    }
  }

  // 视图切换：从 bubble 切到 table 时按需加载分页数据；从 table 切到 bubble 时加载完整流
  function onMessageViewChange(val: 'bubble' | 'table') {
    if (val === 'table') {
      if (messageList.records.length === 0) loadSessionMessages()
    } else if (val === 'bubble') {
      if (bubbleMessages.value.length === 0) loadBubbleMessages()
    }
  }

  // 错误重试：按当前视图选择对应的加载方式
  function reloadSessionMessages() {
    if (messageView.value === 'bubble') loadBubbleMessages()
    else loadSessionMessages()
  }

  // ===== 计费配置 =====
  const billingFormRef = ref<FormInstance>()
  const billingForm = reactive<AiCsBillingConfig>({
    enabled: 1,
    perMessageTokens: 3,
    dailyFreeQuota: 10,
    maxContextMessages: 50,
    casualThreshold: 5,
    casualReminderText: '已闲聊多次，建议创建任务让我帮你处理具体业务哦。',
  })
  const billingState = ref<'loading' | 'ready' | 'error'>('loading')
  const billingError = ref('')
  const billingSaving = ref(false)

  async function loadBillingConfig() {
    billingState.value = 'loading'
    billingError.value = ''
    try {
      const data = await getAiCsBillingConfig()
      if (data) {
        billingForm.enabled = Number(data.enabled ?? 1)
        billingForm.perMessageTokens = Number(data.perMessageTokens ?? 3)
        billingForm.dailyFreeQuota = Number(data.dailyFreeQuota ?? 10)
        billingForm.maxContextMessages = Number(data.maxContextMessages ?? 50)
        billingForm.casualThreshold = Number(data.casualThreshold ?? 5)
        billingForm.casualReminderText = data.casualReminderText || billingForm.casualReminderText
      }
      billingState.value = 'ready'
    } catch (error: unknown) {
      billingError.value = getErrorMessage(error, '计费配置读取失败。')
      billingState.value = 'error'
    }
  }

  async function onSaveBilling() {
    billingSaving.value = true
    try {
      await saveAiCsBillingConfig({ ...billingForm })
      ElMessage.success('计费配置已保存')
    } catch (error: unknown) {
      ElMessage.error(getErrorMessage(error, '保存失败，请稍后重试。'))
    } finally {
      billingSaving.value = false
    }
  }

  // ===== 知识库（RAG） =====
  const knowledgeQuery = reactive({
    current: 1,
    size: 20,
    category: '' as string | null,
    keyword: '' as string | null,
    enabled: '' as string | null,
  })
  const knowledgeList = reactive({ records: [] as AiCsKnowledgeRow[], total: 0 })
  const knowledgeState = ref<'loading' | 'ready' | 'error'>('loading')
  const knowledgeError = ref('')
  const knowledgeCategories = ref<AiCsKnowledgeCategory[]>([])
  const rebuilding = ref(false)

  async function loadKnowledgeCategories() {
    try {
      const data = await getAiCsKnowledgeCategories()
      knowledgeCategories.value = Array.isArray(data) ? data : []
    } catch (_) {
      knowledgeCategories.value = []
    }
  }

  async function loadKnowledge() {
    knowledgeState.value = 'loading'
    knowledgeError.value = ''
    try {
      const params: any = { current: knowledgeQuery.current, size: knowledgeQuery.size }
      if (knowledgeQuery.category) params.category = knowledgeQuery.category
      if (knowledgeQuery.keyword) params.keyword = knowledgeQuery.keyword
      if (knowledgeQuery.enabled) params.enabled = knowledgeQuery.enabled
      const p = await pageAiCsKnowledge(params)
      knowledgeList.records = p.records || []
      knowledgeList.total = Number.isFinite(Number(p.total)) ? Number(p.total) : p.records.length
      knowledgeState.value = 'ready'
    } catch (error: unknown) {
      knowledgeError.value = getErrorMessage(error, '知识库读取失败。')
      knowledgeState.value = 'error'
    }
  }

  function searchKnowledge() {
    knowledgeQuery.current = 1
    loadKnowledge()
  }

  function resetKnowledgeQuery() {
    knowledgeQuery.category = ''
    knowledgeQuery.keyword = ''
    knowledgeQuery.enabled = ''
    knowledgeQuery.current = 1
    loadKnowledge()
  }

  // ===== 知识库新增/编辑 =====
  const knowledgeDrawerVisible = ref(false)
  const knowledgeDrawerTitle = ref('新增知识库条目')
  const knowledgeSaving = ref(false)
  const knowledgeFormRef = ref<FormInstance>()
  const knowledgeForm = reactive<AiCsKnowledgeForm>({
    id: null,
    category: '',
    title: '',
    content: '',
    keywords: '',
    priority: 50,
    enabled: 1,
    sortOrder: 0,
  })
  const knowledgeRules: FormRules = {
    category: [{ required: true, message: '请选择分类', trigger: 'change' }],
    title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
    content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
  }

  function openCreateKnowledge() {
    knowledgeDrawerTitle.value = '新增知识库条目'
    Object.assign(knowledgeForm, {
      id: null,
      category: knowledgeQuery.category || '',
      title: '',
      content: '',
      keywords: '',
      priority: 50,
      enabled: 1,
      sortOrder: 0,
    })
    knowledgeDrawerVisible.value = true
  }

  async function openEditKnowledge(row: AiCsKnowledgeRow) {
    knowledgeDrawerTitle.value = `编辑 #${row.id}`
    try {
      const detail = await getAiCsKnowledgeDetail(row.id)
      Object.assign(knowledgeForm, {
        id: detail.id ?? row.id,
        category: detail.category ?? '',
        title: detail.title ?? '',
        content: detail.content ?? '',
        keywords: detail.keywords ?? '',
        priority: Number(detail.priority ?? 50),
        enabled: isRowEnabled(detail.enabled) ? 1 : 0,
        sortOrder: Number(detail.sortOrder ?? 0),
      })
      knowledgeDrawerVisible.value = true
    } catch (error: unknown) {
      ElMessage.error(getErrorMessage(error, '加载详情失败，请重试。'))
    }
  }

  async function onSaveKnowledge() {
    if (!knowledgeFormRef.value) return
    await knowledgeFormRef.value.validate(async (valid) => {
      if (!valid) return
      knowledgeSaving.value = true
      try {
        await saveAiCsKnowledge({ ...knowledgeForm })
        ElMessage.success(knowledgeForm.id ? '已更新' : '已新增')
        knowledgeDrawerVisible.value = false
        loadKnowledge()
      } catch (error: unknown) {
        ElMessage.error(getErrorMessage(error, '保存失败，请稍后重试。'))
      } finally {
        knowledgeSaving.value = false
      }
    })
  }

  async function onDeleteKnowledge(row: AiCsKnowledgeRow) {
    try {
      await ElMessageBox.confirm(`确认删除知识库条目 #${row.id} "${row.title || ''}" 吗？`, '删除确认', {
        type: 'warning',
      })
    } catch (_) {
      return
    }
    try {
      await deleteAiCsKnowledge(row.id)
      ElMessage.success('已删除')
      loadKnowledge()
    } catch (error: unknown) {
      ElMessage.error(getErrorMessage(error, '删除失败，请稍后重试。'))
    }
  }

  async function onRebuildIndex() {
    try {
      await ElMessageBox.confirm(
        '重建向量索引会重新计算所有知识库条目的向量，期间用户检索可能受影响。确认继续？',
        '重建索引确认',
        { type: 'warning' }
      )
    } catch (_) {
      return
    }
    rebuilding.value = true
    try {
      const res: any = await rebuildAiCsKnowledgeIndex()
      if (res && res.success === false) {
        ElMessage.error(`重建失败：${res.message || '未知错误'}`)
      } else {
        ElMessage.success('向量索引重建已触发，请稍后查看服务日志确认完成。')
      }
    } catch (error: unknown) {
      ElMessage.error(getErrorMessage(error, '重建请求失败，请稍后重试。'))
    } finally {
      rebuilding.value = false
    }
  }

  // ===== 工具函数 =====
  function formatNumber(value: unknown): string {
    const n = Number(value)
    if (!Number.isFinite(n)) return '0'
    return n.toLocaleString()
  }

  function isRowEnabled(value: unknown): boolean {
    if (typeof value === 'boolean') return value
    const n = Number(value)
    return n === 1
  }

  function categoryLabel(key: unknown): string {
    if (!key) return '—'
    const found = knowledgeCategories.value.find((c) => c.key === key)
    return found ? found.label : String(key)
  }

  function roleLabel(role: unknown): string {
    if (role === 'user') return '用户'
    if (role === 'assistant') return '小梦'
    if (role === 'system') return '系统'
    return String(role || '—')
  }

  function roleTagType(role: unknown): 'primary' | 'success' | 'info' | 'warning' | 'danger' {
    if (role === 'user') return 'primary'
    if (role === 'assistant') return 'success'
    if (role === 'system') return 'warning'
    return 'info'
  }

  // 对话气泡视图：角色头像首字符
  function roleInitial(role: unknown): string {
    if (role === 'user') return '用'
    if (role === 'assistant') return '梦'
    if (role === 'system') return '系'
    return '?'
  }

  // 解析 tool_calls 字段（可能是 JSON 字符串或数组）
  function parseToolCalls(raw: unknown): any[] {
    if (!raw) return []
    if (Array.isArray(raw)) return raw as any[]
    if (typeof raw === 'string') {
      const trimmed = raw.trim()
      if (!trimmed) return []
      try {
        const parsed = JSON.parse(trimmed)
        return Array.isArray(parsed) ? parsed : []
      } catch (_) {
        return []
      }
    }
    return []
  }

  // 格式化 tool_calls 为可读 JSON
  function formatToolCalls(raw: unknown): string {
    const arr = parseToolCalls(raw)
    if (!arr.length) return ''
    try {
      return JSON.stringify(arr, null, 2)
    } catch (_) {
      return String(raw)
    }
  }

  function getErrorMessage(error: unknown, fallback: string): string {
    return error instanceof Error && error.message.trim() ? error.message : fallback
  }

  // ===== 初始化 =====
  onMounted(async () => {
    await Promise.allSettled([loadStats(), loadSessions(), loadBillingConfig(), loadKnowledgeCategories(), loadKnowledge()])
  })

  // 切到 sessions/billing/knowledge tab 时按需懒加载
  watch(activeTab, (tab) => {
    if (tab === 'sessions' && sessionState.value === 'loading') loadSessions()
    if (tab === 'billing' && billingState.value === 'loading') loadBillingConfig()
    if (tab === 'knowledge') {
      if (knowledgeCategories.value.length === 0) loadKnowledgeCategories()
      if (knowledgeState.value === 'loading') loadKnowledge()
    }
  })
</script>

<style scoped>
  .ai-cs-page {
    padding: 16px;
  }
  .toolbar-card {
    margin-bottom: 16px;
  }
  .tabs-card {
    margin-bottom: 16px;
  }
  .page-title-row {
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
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
  }
  .metric-card {
    padding: 4px 0;
  }
  .metric-label {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
  .metric-value {
    font-size: 22px;
    font-weight: 600;
    margin: 4px 0;
    color: var(--el-color-primary);
  }
  .metric-sub {
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
  .filter-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }
  .filter-bar-right {
    margin-left: auto;
    display: flex;
    gap: 8px;
  }
  .pagination-bar {
    margin-top: 12px;
    display: flex;
    justify-content: flex-end;
  }
  .tip-alert {
    margin-bottom: 16px;
  }
  .form-tip {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.4;
    margin-top: 4px;
  }
  .empty-state {
    padding: 24px;
    color: var(--el-text-color-secondary);
  }
  .session-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }
  .session-meta-right {
    margin-left: auto;
  }
  .session-username {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    margin-left: 2px;
  }
  .message-content-cell {
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 200px;
    overflow-y: auto;
    font-size: 13px;
    line-height: 1.55;
  }

  /* ===== 对话气泡视图 ===== */
  .chat-bubble-view {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 4px 4px 24px;
    max-height: 70vh;
    overflow-y: auto;
  }
  .chat-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  /* 用户消息靠右，助手/系统靠左 */
  .chat-user {
    flex-direction: row-reverse;
  }
  .chat-avatar {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 600;
    color: #fff;
    user-select: none;
  }
  .avatar-user {
    background: var(--el-color-primary, #409eff);
  }
  .avatar-assistant {
    background: var(--el-color-success, #67c23a);
  }
  .avatar-system {
    background: var(--el-color-warning, #e6a23c);
  }
  .chat-content-wrap {
    min-width: 0;
    max-width: 78%;
    display: flex;
    flex-direction: column;
  }
  .chat-user .chat-content-wrap {
    align-items: flex-end;
  }
  .chat-assistant .chat-content-wrap,
  .chat-system .chat-content-wrap {
    align-items: flex-start;
  }
  .chat-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-bottom: 4px;
    flex-wrap: wrap;
  }
  .chat-user .chat-meta {
    flex-direction: row-reverse;
  }
  .chat-role {
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
  .chat-username {
    color: var(--el-text-color-secondary);
  }
  .chat-tokens {
    color: var(--el-color-warning);
  }
  .chat-time {
    color: var(--el-text-color-placeholder);
  }
  .chat-bubble {
    padding: 10px 14px;
    border-radius: 10px;
    max-width: 100%;
    word-break: break-word;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  }
  .bubble-user {
    background: var(--el-color-primary-light-1, #409eff);
    color: #fff;
    border-top-right-radius: 2px;
  }
  .bubble-assistant {
    background: var(--el-fill-color-light, #f5f7fa);
    color: var(--el-text-color-primary);
    border-top-left-radius: 2px;
  }
  .bubble-system {
    background: var(--el-color-warning-light-9, #fdf6ec);
    color: var(--el-text-color-primary);
    border: 1px dashed var(--el-color-warning-light-5, #e6a23c);
    border-top-left-radius: 2px;
  }
  .chat-bubble-text {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 13.5px;
    line-height: 1.6;
  }
  .chat-tool-details {
    margin-top: 6px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .chat-tool-details summary {
    cursor: pointer;
    user-select: none;
    color: var(--el-color-primary);
  }
  .chat-tool-json {
    margin: 6px 0 0;
    padding: 8px 10px;
    background: var(--el-fill-color-darker, #f0f2f5);
    border-radius: 4px;
    font-size: 12px;
    max-height: 240px;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
  @media (max-width: 1280px) {
    .stats-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
  @media (max-width: 768px) {
    .stats-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
