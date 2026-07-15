<template>
  <div class="feedback-admin-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>用户反馈管理</h2>
          <p>查看前台用户提交的反馈建议，回复用户、调整处理状态与优先级，跟踪每条反馈的处理进度。</p>
        </div>
        <div class="toolbar-actions">
          <ElTag v-if="statsState === 'ready' && stats.open" type="warning">待处理 {{ stats.open }}</ElTag>
          <ElTag v-if="statsState === 'ready' && stats.inProgress" type="info">处理中 {{ stats.inProgress }}</ElTag>
          <ElTag v-if="statsState === 'ready' && stats.replied" type="success">已回复 {{ stats.replied }}</ElTag>
          <ElTag v-if="statsState === 'error'" type="danger">状态汇总暂不可用</ElTag>
          <ElButton type="primary" :loading="loading" @click="load">刷新</ElButton>
        </div>
      </div>

      <ElForm :inline="true" :model="query" class="search-form">
        <ElFormItem label="状态">
          <ElSelect v-model="query.status" placeholder="全部状态" clearable style="width: 140px">
            <ElOption label="待处理" value="open" />
            <ElOption label="处理中" value="in_progress" />
            <ElOption label="已回复" value="replied" />
            <ElOption label="已关闭" value="closed" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="优先级">
          <ElSelect v-model="query.priority" placeholder="全部优先级" clearable style="width: 140px">
            <ElOption label="低" value="low" />
            <ElOption label="普通" value="normal" />
            <ElOption label="高" value="high" />
            <ElOption label="紧急" value="urgent" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="分类">
          <ElSelect v-model="query.category" placeholder="全部分类" clearable style="width: 140px">
            <ElOption label="问题反馈" value="bug" />
            <ElOption label="功能建议" value="feature" />
            <ElOption label="改进提议" value="suggestion" />
            <ElOption label="其他" value="other" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="站点来源">
          <ElSelect v-model="query.siteSource" placeholder="全部站点" clearable style="width: 150px">
            <ElOption label="商业版" value="commercial" />
            <ElOption label="开源版" value="open-source" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput
            v-model="query.keyword"
            placeholder="标题 / 内容 / 用户名 / ID"
            clearable
            style="width: 240px"
            @keyup.enter="search"
          />
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="search">查询</ElButton>
          <ElButton @click="reset">重置</ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard shadow="never" class="table-card">
      <AdminDataState
        v-if="listState === 'loading'"
        state="loading"
        title="正在加载用户反馈"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="用户反馈暂时不可用"
        description="请求失败，不能将当前状态解释为没有反馈。"
        @retry="load"
      />
      <AdminDataState
        v-else-if="listState === 'empty'"
        state="empty"
        title="暂无用户反馈"
        description="查询已成功完成，当前筛选条件下没有记录。"
        :retryable="false"
      />
      <ElTable v-else :data="records" border stripe style="width: 100%" @row-click="openDetail">
        <template #empty><div class="empty-state">暂无反馈记录</div></template>
        <FeedbackTableColumn prop="id" label="ID" width="80" align="center" />
        <FeedbackTableColumn label="分类" width="110" align="center">
          <template #default="{ row }">
            <ElTag :type="categoryTagType(row.category)" effect="light">
              {{ categoryMeta[row.category]?.label || '其他' }}
            </ElTag>
          </template>
        </FeedbackTableColumn>
        <FeedbackTableColumn label="反馈标题" min-width="220">
          <template #default="{ row }">
            <div class="title-cell">
              <strong>{{ row.title }}</strong>
              <span v-if="row.userReplyCount" class="user-reply-badge" :title="`用户追加了 ${row.userReplyCount} 条补充`">
                {{ row.userReplyCount }}
              </span>
            </div>
          </template>
        </FeedbackTableColumn>
        <FeedbackTableColumn label="状态" width="110" align="center">
          <template #default="{ row }">
            <ElTag :type="statusTagType(row.status)" effect="dark">
              {{ statusMeta[row.status]?.label || '待处理' }}
            </ElTag>
          </template>
        </FeedbackTableColumn>
        <FeedbackTableColumn label="优先级" width="100" align="center">
          <template #default="{ row }">
            <ElTag :type="priorityTagType(row.priority)" effect="plain" size="small">
              {{ priorityMeta[row.priority]?.label || '普通' }}
            </ElTag>
          </template>
        </FeedbackTableColumn>
        <FeedbackTableColumn label="提交用户" min-width="160">
          <template #default="{ row }">
            <div class="user-cell">
              <strong>{{ row.username || '-' }}</strong>
              <span>租户 #{{ row.tenantId ?? '-' }} · 用户 #{{ row.userId ?? '-' }}</span>
            </div>
          </template>
        </FeedbackTableColumn>
        <FeedbackTableColumn label="站点来源" width="150" align="center">
          <template #default="{ row }">
            <div class="site-cell">
              <ElTag :type="siteSourceTagType(row.siteSource)" effect="light">
                {{ siteSourceLabel(row.siteSource) }}
              </ElTag>
              <span>{{ row.siteName || '-' }}</span>
            </div>
          </template>
        </FeedbackTableColumn>
        <FeedbackTableColumn prop="replierUsername" label="最后回复" width="130">
          <template #default="{ row }">{{ row.replierUsername || '-' }}</template>
        </FeedbackTableColumn>
        <FeedbackTableColumn prop="createdTime" label="提交时间" width="170" />
        <FeedbackTableColumn label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click.stop="openDetail(row)">查看</ElButton>
            <ElButton link type="success" @click.stop="quickReply(row)">回复</ElButton>
            <ElDropdown trigger="click" @command="(cmd: string) => handleStatusCommand(cmd, row)">
              <ElButton link type="warning" @click.stop>状态<ElIcon><ArrowDown /></ElIcon></ElButton>
              <template #dropdown>
                <ElDropdownMenu>
                  <ElDropdownItem command="open" :disabled="row.status === 'open'">标记为待处理</ElDropdownItem>
                  <ElDropdownItem command="in_progress" :disabled="row.status === 'in_progress'">标记为处理中</ElDropdownItem>
                  <ElDropdownItem command="replied" :disabled="row.status === 'replied'">标记为已回复</ElDropdownItem>
                  <ElDropdownItem command="closed" :disabled="row.status === 'closed'">标记为已关闭</ElDropdownItem>
                </ElDropdownMenu>
              </template>
            </ElDropdown>
            <ElButton link type="danger" @click.stop="handleDelete(row)">删除</ElButton>
          </template>
        </FeedbackTableColumn>
      </ElTable>

      <div v-if="listState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ total }} 条反馈</span>
        <ElPagination
          v-model:current-page="query.current"
          v-model:page-size="query.size"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @change="load"
        />
      </div>
    </ElCard>

    <ElDrawer v-model="detailVisible" title="反馈详情" size="640px" :before-close="handleDetailClose">
      <AdminDataState
        v-if="detailState === 'loading'"
        state="loading"
        title="正在加载反馈详情"
        :retryable="false"
        compact
      />
      <AdminDataState
        v-else-if="detailState === 'error'"
        state="error"
        title="反馈详情暂时不可用"
        description="详情请求失败，请重试。"
        compact
        @retry="retryDetail"
      />
      <template v-else-if="currentDetail">
        <div class="detail-meta">
          <ElTag :type="categoryTagType(currentDetail.category)" effect="light">
            {{ categoryMeta[currentDetail.category]?.label || '其他' }}
          </ElTag>
          <ElTag :type="statusTagType(currentDetail.status)" effect="dark">
            {{ statusMeta[currentDetail.status]?.label || '待处理' }}
          </ElTag>
          <ElTag :type="priorityTagType(currentDetail.priority)" effect="plain" size="small">
            {{ priorityMeta[currentDetail.priority]?.label || '普通' }}
          </ElTag>
          <span class="detail-id">#{{ currentDetail.id }}</span>
        </div>

        <h3 class="detail-title-text">{{ currentDetail.title }}</h3>

        <ElDescriptions :column="2" border size="small" class="detail-desc">
          <ElDescriptionsItem label="提交用户">{{ currentDetail.username || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="租户 ID">{{ currentDetail.tenantId ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="用户 ID">{{ currentDetail.userId ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="站点来源">{{ siteSourceLabel(currentDetail.siteSource) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="站点名称">{{ currentDetail.siteName || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="联系方式">{{ currentDetail.contact || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="提交时间">{{ currentDetail.createdTime || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="最后回复">{{ currentDetail.replierUsername || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="回复时间">{{ currentDetail.repliedTime || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="更新时间">{{ currentDetail.updatedTime || '-' }}</ElDescriptionsItem>
        </ElDescriptions>

        <div class="detail-block">
          <div class="detail-block-label">反馈内容</div>
          <div class="detail-content-text">{{ currentDetail.content }}</div>
        </div>

        <div class="detail-block">
          <div class="detail-block-label">回复记录 ({{ currentDetail.replies?.length || 0 }})</div>
          <div v-if="currentDetail.replies?.length" class="reply-list">
            <div
              v-for="reply in currentDetail.replies"
              :key="reply.id"
              :class="['reply-item', reply.replierRole === 'admin' ? 'is-admin' : 'is-user']"
            >
              <div class="reply-avatar" :class="{ admin: reply.replierRole === 'admin' }">
                {{ reply.replierRole === 'admin' ? '客服' : '用户' }}
              </div>
              <div class="reply-bubble" :class="{ admin: reply.replierRole === 'admin' }">
                <div class="reply-header">
                  <strong>{{ reply.replierUsername || (reply.replierRole === 'admin' ? '管理员' : '用户') }}</strong>
                  <span class="reply-time">{{ reply.createdTime || '' }}</span>
                </div>
                <div class="reply-text">{{ reply.content }}</div>
              </div>
            </div>
          </div>
          <div v-else class="no-reply">暂无回复记录</div>
        </div>

        <div class="detail-actions">
          <div class="detail-actions-left">
            <ElSelect v-model="quickStatus" placeholder="修改状态" size="small" style="width: 130px" @change="onQuickStatusChange">
              <ElOption label="待处理" value="open" />
              <ElOption label="处理中" value="in_progress" />
              <ElOption label="已回复" value="replied" />
              <ElOption label="已关闭" value="closed" />
            </ElSelect>
            <ElSelect v-model="quickPriority" placeholder="修改优先级" size="small" style="width: 130px" @change="onQuickPriorityChange">
              <ElOption label="低" value="low" />
              <ElOption label="普通" value="normal" />
              <ElOption label="高" value="high" />
              <ElOption label="紧急" value="urgent" />
            </ElSelect>
          </div>
          <div class="detail-actions-right">
            <ElButton type="danger" plain size="small" @click="handleDelete(currentDetail)">删除反馈</ElButton>
            <ElButton type="primary" size="small" @click="replyDialogVisible = true">回复用户</ElButton>
          </div>
        </div>
      </template>
    </ElDrawer>

    <ElDialog v-model="replyDialogVisible" title="回复用户反馈" width="640px" destroy-on-close>
      <div v-if="currentDetail" class="reply-dialog-context">
        <div class="reply-dialog-title">{{ currentDetail.title }}</div>
        <div class="reply-dialog-preview">{{ currentDetail.content }}</div>
      </div>
      <ElInput
        v-model="replyContent"
        type="textarea"
        :rows="6"
        placeholder="输入给用户的回复内容，提交后反馈状态会自动变为「已回复」"
        maxlength="5000"
        show-word-limit
      />
      <div class="reply-dialog-tip">提示：回复内容会出现在用户的反馈详情中，请使用专业、礼貌的语气。</div>
      <template #footer>
        <ElButton @click="replyDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="replying" @click="submitReply">提交回复</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox, ElTableColumn } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import {
  getFeedbackList,
  getFeedbackDetail,
  replyFeedback,
  changeFeedbackStatus,
  changeFeedbackPriority,
  deleteFeedback,
  type FeedbackQuery,
  type FeedbackListItem,
  type FeedbackDetail,
  type FeedbackStatus,
  type FeedbackPriority
} from '@/api/feedback'

defineOptions({ name: 'AdminFeedbackPage' })

const FeedbackTableColumn: typeof ElTableColumn<FeedbackListItem> = ElTableColumn

const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const records = ref<FeedbackListItem[]>([])
const total = ref(0)
const query = reactive<FeedbackQuery>({
  status: '',
  category: '',
  priority: '',
  siteSource: '',
  keyword: '',
  current: 1,
  size: 20
})

const detailVisible = ref(false)
const detailState = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const detailTarget = ref<FeedbackListItem | null>(null)
const currentDetail = ref<FeedbackDetail | null>(null)
const quickStatus = ref<FeedbackStatus | ''>('')
const quickPriority = ref<FeedbackPriority | ''>('')

const replyDialogVisible = ref(false)
const replyContent = ref('')
const replying = ref(false)

const stats = reactive({ open: 0, inProgress: 0, replied: 0, closed: 0 })
const statsState = ref<'loading' | 'ready' | 'error'>('loading')

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const categoryMeta: Record<string, { label: string }> = {
  bug: { label: '问题反馈' },
  feature: { label: '功能建议' },
  suggestion: { label: '改进提议' },
  other: { label: '其他' }
}
const statusMeta: Record<string, { label: string; type: TagType }> = {
  open: { label: '待处理', type: 'warning' },
  in_progress: { label: '处理中', type: 'info' },
  replied: { label: '已回复', type: 'success' },
  closed: { label: '已关闭', type: 'info' }
}
const priorityMeta: Record<string, { label: string }> = {
  low: { label: '低' },
  normal: { label: '普通' },
  high: { label: '高' },
  urgent: { label: '紧急' }
}

const categoryTagMap: Record<string, TagType> = {
  bug: 'danger',
  feature: 'primary',
  suggestion: 'warning',
  other: 'info'
}

const priorityTagMap: Record<string, TagType> = {
  low: 'info',
  normal: 'primary',
  high: 'warning',
  urgent: 'danger'
}
const siteSourceMeta: Record<string, { label: string; type: TagType }> = {
  commercial: { label: '商业版', type: 'success' },
  'open-source': { label: '开源版', type: 'warning' }
}

function categoryTagType(category: string): TagType {
  return categoryTagMap[category] || 'info'
}
function statusTagType(status: string): TagType {
  return statusMeta[status]?.type || 'info'
}
function priorityTagType(priority: string): TagType {
  return priorityTagMap[priority] || 'info'
}
function siteSourceTagType(siteSource?: string): TagType {
  return siteSourceMeta[siteSource || '']?.type || 'info'
}
function siteSourceLabel(siteSource?: string): string {
  return siteSourceMeta[siteSource || '']?.label || (siteSource || '未知站点')
}

onMounted(load)

async function load() {
  loading.value = true
  listState.value = 'loading'
  try {
    const params = Object.fromEntries(
      Object.entries(query).filter(([, v]) => v !== '' && v !== null && v !== undefined)
    )
    const page = await getFeedbackList(params as FeedbackQuery)
    records.value = page.records
    total.value = page.total
    listState.value = records.value.length > 0 ? 'ready' : 'empty'
    void refreshStats()
  } catch {
    records.value = []
    total.value = 0
    listState.value = 'error'
    statsState.value = 'error'
  } finally {
    loading.value = false
  }
}

async function refreshStats() {
  statsState.value = 'loading'
  stats.open = 0
  stats.inProgress = 0
  stats.replied = 0
  stats.closed = 0
  const statuses: FeedbackStatus[] = ['open', 'in_progress', 'replied', 'closed']
  const results = await Promise.allSettled(
    statuses.map(s => getFeedbackList({ current: 1, size: 1, status: s, siteSource: query.siteSource || '' }))
  )
  results.forEach((r, i) => {
    if (r.status === 'fulfilled') {
      const count = r.value.total
      if (statuses[i] === 'open') stats.open = count
      else if (statuses[i] === 'in_progress') stats.inProgress = count
      else if (statuses[i] === 'replied') stats.replied = count
      else if (statuses[i] === 'closed') stats.closed = count
    }
  })
  statsState.value = results.every(result => result.status === 'fulfilled') ? 'ready' : 'error'
}

function search() {
  query.current = 1
  load()
}

function reset() {
  query.status = ''
  query.category = ''
  query.priority = ''
  query.siteSource = ''
  query.keyword = ''
  query.current = 1
  load()
}

async function openDetail(row: FeedbackListItem) {
  detailVisible.value = true
  detailState.value = 'loading'
  detailTarget.value = row
  currentDetail.value = null
  try {
    const detail = await getFeedbackDetail(row.id)
    currentDetail.value = detail
    quickStatus.value = detail.status
    quickPriority.value = detail.priority
    detailState.value = 'ready'
  } catch {
    detailState.value = 'error'
  }
}

function retryDetail() {
  if (detailTarget.value) void openDetail(detailTarget.value)
}

function handleDetailClose(done: () => void) {
  currentDetail.value = null
  detailState.value = 'idle'
  detailTarget.value = null
  done()
}

function quickReply(row: FeedbackListItem) {
  openDetail(row).then(() => {
    replyDialogVisible.value = true
  })
}

async function submitReply() {
  if (!currentDetail.value) return
  if (!replyContent.value.trim()) {
    ElMessage.warning('请填写回复内容')
    return
  }
  replying.value = true
  try {
    await replyFeedback(currentDetail.value.id, replyContent.value.trim())
    replyContent.value = ''
    replyDialogVisible.value = false
    // 刷新详情与列表
    const detail = await getFeedbackDetail(currentDetail.value.id)
    currentDetail.value = detail
    quickStatus.value = detail.status
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '回复失败')
  } finally {
    replying.value = false
  }
}

async function onQuickStatusChange(status: FeedbackStatus | '') {
  if (!currentDetail.value || !status) return
  try {
    await changeFeedbackStatus(currentDetail.value.id, status)
    currentDetail.value = { ...currentDetail.value, status }
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '状态修改失败')
    quickStatus.value = currentDetail.value?.status || ''
  }
}

async function onQuickPriorityChange(priority: FeedbackPriority | '') {
  if (!currentDetail.value || !priority) return
  try {
    await changeFeedbackPriority(currentDetail.value.id, priority)
    currentDetail.value = { ...currentDetail.value, priority }
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '优先级修改失败')
    quickPriority.value = currentDetail.value?.priority || ''
  }
}

async function handleStatusCommand(cmd: string, row: FeedbackListItem) {
  try {
    await changeFeedbackStatus(row.id, cmd as FeedbackStatus)
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '状态修改失败')
  }
}

async function handleDelete(row: FeedbackListItem | FeedbackDetail) {
  try {
    await ElMessageBox.confirm(
      `确认删除反馈 #${row.id}「${row.title}」？删除后用户将看不到此反馈。`,
      '确认删除',
      { type: 'warning' }
    )
    await deleteFeedback(row.id)
    if (detailVisible.value && currentDetail.value?.id === row.id) {
      detailVisible.value = false
      currentDetail.value = null
    }
    await load()
  } catch {
    // cancelled
  }
}
</script>

<style scoped>
.feedback-admin-page { padding: 16px; }
.filter-card { margin-bottom: 16px; }
.page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; }
.search-form { row-gap: 8px; }
.table-card { min-height: 420px; }
.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
}
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.title-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title-cell strong {
  color: var(--el-text-color-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}
.user-reply-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #ff9f22;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  flex: 0 0 auto;
  cursor: help;
}
.user-cell { display: grid; gap: 2px; }
.user-cell strong { color: var(--el-text-color-primary); font-size: 13px; }
.user-cell span { color: var(--el-text-color-secondary); font-size: 12px; }
.site-cell {
  display: grid;
  gap: 6px;
  justify-items: center;
}
.site-cell span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.2;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.detail-id { color: var(--el-text-color-secondary); font-size: 12px; }
.detail-title-text {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}
.detail-desc { margin-bottom: 18px; }
.detail-block { margin-top: 16px; }
.detail-block-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}
.detail-content-text {
  padding: 14px 16px;
  background: #f7f9fc;
  border-radius: 10px;
  border: 1px solid #e7edf5;
  color: #2c3e50;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.reply-list { display: flex; flex-direction: column; gap: 12px; }
.reply-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.reply-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #5a9fff, #0d6bff);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}
.reply-avatar.admin {
  background: linear-gradient(135deg, #16bf78, #0fa060);
}
.reply-bubble {
  flex: 1;
  min-width: 0;
  padding: 10px 14px;
  background: #f5f8fc;
  border: 1px solid #e7edf5;
  border-radius: 10px;
}
.reply-bubble.admin {
  background: #e9f7ee;
  border-color: #c5e8d2;
}
.reply-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.reply-header strong {
  font-size: 13px;
  color: var(--el-text-color-primary);
}
.reply-time {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.reply-text {
  font-size: 14px;
  color: #2c3e50;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.no-reply {
  padding: 24px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  background: #f7f9fc;
  border-radius: 10px;
}

.detail-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color);
  gap: 12px;
  flex-wrap: wrap;
}
.detail-actions-left { display: flex; gap: 8px; align-items: center; }
.detail-actions-right { display: flex; gap: 8px; align-items: center; }

.reply-dialog-context {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #f7f9fc;
  border-radius: 10px;
  border-left: 3px solid var(--el-color-primary);
}
.reply-dialog-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 6px;
  color: var(--el-text-color-primary);
}
.reply-dialog-preview {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  max-height: 80px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.reply-dialog-tip {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

@media (max-width: 1100px) {
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-actions {
    flex-wrap: wrap;
  }
}
</style>

