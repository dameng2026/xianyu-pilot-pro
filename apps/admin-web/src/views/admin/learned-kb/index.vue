<template>
  <div class="learned-kb-page">
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>学习知识库</h2>
          <p>管理从会话中学习到的知识条目，支持审核、分类、日志查询与手动触发学习</p>
        </div>
        <div class="actions">
          <ElButton @click="refreshCurrentTab">刷新当前页</ElButton>
        </div>
      </div>
    </ElCard>

    <ElCard shadow="never" class="tabs-card">
      <ElTabs v-model="activeTab" type="border-card" class="learned-kb-tabs">
        <!-- ===== Tab 1: 知识库条目 ===== -->
        <ElTabPane label="知识库条目" name="entries">
          <div class="filter-bar">
            <ElSelect
              v-model="entryQuery.category"
              clearable
              placeholder="分类"
              style="width: 170px"
              @change="searchEntries"
            >
              <ElOption
                v-for="cat in categoryList"
                :key="cat.id"
                :label="cat.name"
                :value="cat.name"
              />
            </ElSelect>
            <ElSelect
              v-model="entryQuery.status"
              clearable
              placeholder="状态"
              style="width: 130px"
              @change="searchEntries"
            >
              <ElOption label="待审核" value="pending" />
              <ElOption label="已通过" value="approved" />
              <ElOption label="已拒绝" value="rejected" />
            </ElSelect>
            <ElInput
              v-model="minScoreInput"
              type="number"
              placeholder="最低分"
              clearable
              style="width: 130px"
              @keyup.enter="searchEntries"
            />
            <ElInput
              v-model="entryQuery.keyword"
              placeholder="问题/回答/标签关键词"
              clearable
              style="width: 220px"
              @keyup.enter="searchEntries"
            />
            <ElButton type="primary" @click="searchEntries">查询</ElButton>
            <ElButton @click="resetEntryQuery">重置</ElButton>
            <div class="filter-bar-right">
              <ElButton
                type="success"
                :disabled="!selectedIds.length"
                :loading="batchApproving"
                @click="onBatchApprove"
              >
                批量通过{{ selectedIds.length ? `(${selectedIds.length})` : '' }}
              </ElButton>
              <ElButton
                type="warning"
                :disabled="!selectedIds.length"
                :loading="batchRejecting"
                @click="onBatchReject"
              >
                批量拒绝{{ selectedIds.length ? `(${selectedIds.length})` : '' }}
              </ElButton>
            </div>
          </div>

          <AdminDataState
            v-if="entryState === 'loading'"
            state="loading"
            title="正在读取知识库条目"
            compact
          />
          <AdminDataState
            v-else-if="entryState === 'error'"
            state="error"
            title="知识库条目暂不可用"
            :description="entryError"
            retry-text="重新加载"
            compact
            @retry="loadEntries"
          />
          <template v-else>
            <ElTable
              :data="entryList.list"
              border
              stripe
              height="480"
              row-key="id"
              @selection-change="onSelectionChange"
            >
              <template #empty><div class="empty-state">暂无知识库条目</div></template>
              <ElTableColumn type="selection" width="50" />
              <ElTableColumn prop="id" label="ID" width="70" />
              <ElTableColumn label="分类" width="130">
                <template #default="{ row }">
                  <ElTag size="small">{{ row.category_name || '—' }}</ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="question" label="问题" min-width="220" show-overflow-tooltip />
              <ElTableColumn prop="answer_preview" label="回答预览" min-width="240" show-overflow-tooltip />
              <ElTableColumn label="置信分" width="90">
                <template #default="{ row }">
                  {{ formatScore(row.score) }}
                </template>
              </ElTableColumn>
              <ElTableColumn label="状态" width="100">
                <template #default="{ row }">
                  <ElTag :type="statusTagType(row.review_status)" size="small">
                    {{ statusLabel(row.review_status) }}
                  </ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="source_count" label="来源数" width="80" />
              <ElTableColumn prop="created_time" label="创建时间" min-width="160" show-overflow-tooltip />
              <ElTableColumn label="操作" width="280" fixed="right">
                <template #default="{ row }">
                  <ElButton link type="primary" size="small" @click="openEntryDetail(row as EntryRow)">详情</ElButton>
                  <ElButton link type="info" size="small" @click="openConversation(row as EntryRow)">查看对话</ElButton>
                  <ElButton
                    v-if="row.review_status === 'pending'"
                    link
                    type="success"
                    size="small"
                    @click="onApprove(row as EntryRow)"
                  >
                    通过
                  </ElButton>
                  <ElButton
                    v-if="row.review_status === 'pending'"
                    link
                    type="warning"
                    size="small"
                    @click="onReject(row as EntryRow)"
                  >
                    拒绝
                  </ElButton>
                  <ElButton
                    link
                    type="danger"
                    size="small"
                    :loading="deletingEntry === row.id"
                    @click="onDeleteEntry(row as EntryRow)"
                  >
                    删除
                  </ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
            <div class="pagination-bar">
              <ElPagination
                v-model:current-page="entryQuery.page"
                v-model:page-size="entryQuery.size"
                :total="entryList.total"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="loadEntries"
                @size-change="loadEntries"
              />
            </div>
          </template>
        </ElTabPane>

        <!-- ===== Tab 2: 分类管理 ===== -->
        <ElTabPane label="分类管理" name="categories">
          <div class="filter-bar">
            <ElButton type="primary" @click="openCreateCategory">新增分类</ElButton>
            <ElButton type="warning" :disabled="categoryList.length < 2" @click="openMergeCategory">合并分类</ElButton>
            <ElButton @click="loadCategories">刷新</ElButton>
          </div>

          <AdminDataState
            v-if="categoryState === 'loading'"
            state="loading"
            title="正在读取分类"
            compact
          />
          <AdminDataState
            v-else-if="categoryState === 'error'"
            state="error"
            title="分类列表暂不可用"
            :description="categoryError"
            retry-text="重新加载"
            compact
            @retry="loadCategories"
          />
          <template v-else>
            <ElTable
              :data="categoryList"
              border
              stripe
              height="480"
              row-key="id"
              :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
              default-expand-all
            >
              <template #empty><div class="empty-state">暂无分类，点击"新增分类"创建</div></template>
              <ElTableColumn prop="id" label="ID" width="70" />
              <ElTableColumn prop="name" label="名称" min-width="200" />
              <ElTableColumn label="层级" width="100">
                <template #default="{ row }">
                  <ElTag size="small" :type="row.parent_id ? 'info' : 'success'">
                    {{ row.parent_id ? '二级' : '一级' }}
                  </ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="entry_count" label="条目数" width="100" />
              <ElTableColumn prop="source" label="来源" width="100">
                <template #default="{ row }">
                  <ElTag size="small" :type="row.source === 'manual' ? 'info' : 'success'">
                    {{ row.source || '—' }}
                  </ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="sort_order" label="排序" width="80" />
              <ElTableColumn prop="created_time" label="创建时间" min-width="160" show-overflow-tooltip />
              <ElTableColumn label="操作" width="160" fixed="right">
                <template #default="{ row }">
                  <ElButton link type="primary" size="small" @click="openRenameCategory(row as CategoryRow)">重命名</ElButton>
                  <ElButton link type="danger" size="small" @click="onDeleteCategory(row as CategoryRow)">删除</ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
          </template>
        </ElTabPane>

        <!-- ===== Tab 3: 学习日志 ===== -->
        <ElTabPane label="学习日志" name="logs">
          <AdminDataState
            v-if="logState === 'loading'"
            state="loading"
            title="正在读取学习日志"
            compact
          />
          <AdminDataState
            v-else-if="logState === 'error'"
            state="error"
            title="学习日志暂不可用"
            :description="logError"
            retry-text="重新加载"
            compact
            @retry="loadLogs"
          />
          <template v-else>
            <ElTable :data="logList.list" border stripe height="480">
              <template #empty><div class="empty-state">暂无学习日志</div></template>
              <ElTableColumn prop="batch_id" label="批次 ID" width="200" show-overflow-tooltip />
              <ElTableColumn label="状态" width="100">
                <template #default="{ row }">
                  <ElTag :type="logStatusTagType(row.status)" size="small">{{ row.status || '—' }}</ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="total_conversations" label="会话数" width="90" />
              <ElTableColumn prop="kept_conversations" label="保留数" width="90" />
              <ElTableColumn prop="extracted_items" label="提取条数" width="100" />
              <ElTableColumn prop="deduplicated_items" label="去重条数" width="100" />
              <ElTableColumn prop="llm_tokens_used" label="LLM Token" width="120" />
              <ElTableColumn prop="started_at" label="开始时间" min-width="160" show-overflow-tooltip />
              <ElTableColumn prop="finished_at" label="结束时间" min-width="160" show-overflow-tooltip />
              <ElTableColumn label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <ElButton link type="primary" size="small" @click="openLogDetail(row as LogRow)">详情</ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
            <div class="pagination-bar">
              <ElPagination
                v-model:current-page="logQuery.page"
                v-model:page-size="logQuery.size"
                :total="logList.total"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="loadLogs"
                @size-change="loadLogs"
              />
            </div>
          </template>
        </ElTabPane>

        <!-- ===== Tab 4: 配置 ===== -->
        <ElTabPane label="配置" name="config">
          <ElAlert type="info" :closable="false" class="tip-alert" show-icon>
            <template #title>
              <span>
                手动触发学习任务会扫描最近的会话记录，提取问答对并写入知识库待审核队列。
                回填操作会重新处理所有历史会话，耗时较长，建议在低峰期执行。
              </span>
            </template>
          </ElAlert>

          <div class="config-actions">
            <ElCard shadow="never" class="action-card">
              <h4>立即触发学习</h4>
              <p>扫描最近的会话记录，提取问答对并写入待审核队列。通常几分钟内完成。</p>
              <ElButton type="primary" :loading="triggering" @click="onTriggerLearning">立即触发</ElButton>
            </ElCard>

            <ElCard shadow="never" class="action-card">
              <h4>回填历史数据</h4>
              <p>重新处理所有历史会话。耗时较长，建议在低峰期执行。</p>
              <ElButton type="danger" :loading="backfilling" @click="onBackfill">执行回填</ElButton>
            </ElCard>
          </div>
        </ElTabPane>
      </ElTabs>
    </ElCard>

    <!-- ===== 条目详情弹窗 ===== -->
    <ElDialog v-model="entryDetailVisible" title="条目详情" width="60%" destroy-on-close>
      <AdminDataState
        v-if="entryDetailState === 'loading'"
        state="loading"
        title="正在读取详情"
        compact
      />
      <AdminDataState
        v-else-if="entryDetailState === 'error'"
        state="error"
        title="加载详情失败"
        description="无法读取该条目的完整详情，请稍后重试。"
        retry-text="重新加载"
        compact
        @retry="openEntryDetail(entryDetail as EntryRow)"
      />
      <template v-else-if="entryDetail">
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="ID">{{ entryDetail.id }}</ElDescriptionsItem>
          <ElDescriptionsItem label="分类">{{ entryDetail.category_name || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="状态">
            <ElTag :type="statusTagType(entryDetail.review_status)" size="small">
              {{ statusLabel(entryDetail.review_status) }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="置信分">{{ formatScore(entryDetail.score) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="启用">
            <ElTag :type="isTruthy(entryDetail.enabled) ? 'success' : 'info'" size="small">
              {{ isTruthy(entryDetail.enabled) ? '启用' : '禁用' }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="向量索引">
            <ElTag :type="isTruthy(entryDetail.vector_indexed) ? 'success' : 'info'" size="small">
              {{ isTruthy(entryDetail.vector_indexed) ? '已索引' : '未索引' }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="来源数">{{ entryDetail.source_count ?? '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="学习批次">{{ entryDetail.learn_batch_id || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建时间">{{ entryDetail.created_time || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="更新时间">{{ entryDetail.updated_time || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="问题" :span="2">
            <div class="detail-text">{{ entryDetail.question }}</div>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="回答" :span="2">
            <div class="detail-text">{{ entryDetail.answer }}</div>
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="entryDetail.tags" label="标签" :span="2">
            <div class="detail-text">{{ entryDetail.tags }}</div>
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="entryDetail.source_summary" label="来源摘要" :span="2">
            <div class="detail-text">{{ entryDetail.source_summary }}</div>
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="entryDetail.reject_reason" label="拒绝原因" :span="2">
            <div class="detail-text detail-text--danger">{{ entryDetail.reject_reason }}</div>
          </ElDescriptionsItem>
        </ElDescriptions>
      </template>
      <template #footer>
        <ElButton @click="entryDetailVisible = false">关闭</ElButton>
        <template v-if="entryDetail && entryDetailState === 'ready' && entryDetail.review_status === 'pending'">
          <ElButton type="success" @click="onApprove(entryDetail as EntryRow)">通过</ElButton>
          <ElButton type="warning" @click="onReject(entryDetail as EntryRow)">拒绝</ElButton>
        </template>
      </template>
    </ElDialog>

    <!-- ===== 学习日志详情弹窗 ===== -->
    <ElDialog v-model="logDetailVisible" title="学习日志详情" width="60%" destroy-on-close>
      <AdminDataState
        v-if="logDetailState === 'loading'"
        state="loading"
        title="正在读取日志详情"
        compact
      />
      <template v-else-if="logDetail">
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="批次 ID">{{ logDetail.batch_id }}</ElDescriptionsItem>
          <ElDescriptionsItem label="状态">
            <ElTag :type="logStatusTagType(logDetail.status)" size="small">{{ logDetail.status || '—' }}</ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="会话总数">{{ logDetail.total_conversations ?? 0 }}</ElDescriptionsItem>
          <ElDescriptionsItem label="保留会话">{{ logDetail.kept_conversations ?? 0 }}</ElDescriptionsItem>
          <ElDescriptionsItem label="提取条数">{{ logDetail.extracted_items ?? 0 }}</ElDescriptionsItem>
          <ElDescriptionsItem label="去重条数">{{ logDetail.deduplicated_items ?? 0 }}</ElDescriptionsItem>
          <ElDescriptionsItem label="LLM Token">{{ logDetail.llm_tokens_used ?? 0 }}</ElDescriptionsItem>
          <ElDescriptionsItem label="LLM 费用">{{ logDetail.llm_cost_yuan ?? '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="开始时间">{{ logDetail.started_at || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="结束时间">{{ logDetail.finished_at || '—' }}</ElDescriptionsItem>
          <ElDescriptionsItem v-if="logDetail.error_message" label="错误信息" :span="2">
            <div class="detail-text detail-text--danger">{{ logDetail.error_message }}</div>
          </ElDescriptionsItem>
        </ElDescriptions>
      </template>
      <template #footer>
        <ElButton @click="logDetailVisible = false">关闭</ElButton>
      </template>
    </ElDialog>

    <!-- ===== 查看对话弹窗 ===== -->
    <ElDialog v-model="conversationVisible" title="原始对话" width="60%" destroy-on-close>
      <AdminDataState
        v-if="conversationState === 'loading'"
        state="loading"
        title="正在加载对话"
        compact
      />
      <template v-else-if="conversationMessages.length">
        <div class="conversation-list">
          <div
            v-for="(msg, idx) in conversationMessages"
            :key="idx"
            :class="['conv-msg', msg.direction === 'outgoing' ? 'conv-msg--seller' : 'conv-msg--buyer']"
          >
            <div class="conv-msg-header">
              <span class="conv-msg-sender">{{ msg.direction === 'outgoing' ? '卖家' : '买家' }}</span>
              <span v-if="msg.is_auto_reply" class="conv-msg-ai-tag">AI</span>
              <span class="conv-msg-time">{{ msg.message_time }}</span>
            </div>
            <div class="conv-msg-content">{{ msg.content }}</div>
          </div>
        </div>
      </template>
      <template v-else>
        <ElEmpty description="该条目无关联对话" />
      </template>
      <template #footer>
        <ElButton @click="conversationVisible = false">关闭</ElButton>
      </template>
    </ElDialog>

    <!-- ===== 新增/重命名分类弹窗 ===== -->
    <ElDialog v-model="categoryDialogVisible" :title="categoryDialogTitle" width="420px" destroy-on-close>
      <ElForm ref="categoryFormRef" :model="categoryForm" :rules="categoryRules" label-width="80px">
        <ElFormItem label="名称" prop="name">
          <ElInput
            v-model="categoryForm.name"
            placeholder="请输入分类名称"
            maxlength="50"
            show-word-limit
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="categoryDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="categorySaving" @click="onSaveCategory">保存</ElButton>
      </template>
    </ElDialog>

    <!-- ===== 合并分类弹窗 ===== -->
    <ElDialog v-model="mergeDialogVisible" title="合并分类" width="480px" destroy-on-close>
      <ElAlert type="warning" :closable="false" show-icon class="tip-alert">
        <template #title>
          <span>合并后，源分类下的所有条目将迁移到目标分类，源分类将被删除。此操作不可撤销。</span>
        </template>
      </ElAlert>
      <ElForm ref="mergeFormRef" :model="mergeForm" :rules="mergeRules" label-width="100px">
        <ElFormItem label="源分类" prop="fromId">
          <ElSelect v-model="mergeForm.fromId" placeholder="选择要被合并的分类" style="width: 100%">
            <ElOption
              v-for="cat in categoryList"
              :key="cat.id"
              :label="`${cat.name} (${cat.entry_count ?? 0} 条)`"
              :value="cat.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="目标分类" prop="toId">
          <ElSelect v-model="mergeForm.toId" placeholder="选择合并到的目标分类" style="width: 100%">
            <ElOption
              v-for="cat in categoryList"
              :key="cat.id"
              :label="`${cat.name} (${cat.entry_count ?? 0} 条)`"
              :value="cat.id"
              :disabled="cat.id === mergeForm.fromId"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="mergeDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="merging" @click="onMergeCategory">确认合并</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import request from '@/utils/http'
import AdminDataState from '@/components/business/admin-data-state/index.vue'

defineOptions({ name: 'AdminLearnedKb' })

// ===== Tab 切换 =====
const activeTab = ref<'entries' | 'categories' | 'logs' | 'config'>('entries')

// ===== 类型定义 =====
interface EntryRow {
  id: number
  category_id?: number
  category_name?: string
  question?: string
  answer?: string
  answer_preview?: string
  tags?: string
  source_summary?: string
  score?: number
  review_status?: string
  enabled?: number | boolean
  vector_indexed?: number | boolean
  source_count?: number
  learn_batch_id?: string
  created_time?: string
  updated_time?: string
  reject_reason?: string
  reviewed_by?: number
  reviewed_time?: string
}

interface CategoryRow {
  id: number
  name: string
  parent_id?: number | null
  sort_order?: number
  entry_count?: number
  source?: string
  created_time?: string
  /** 子分类列表（树形表格使用） */
  children?: CategoryRow[]
  /** 是否有子分类（树形表格懒加载标记，此处始终与 children 同步设置） */
  hasChildren?: boolean
}

/**
 * 将平铺的分类列表转换为树形结构（按 parent_id 建立父子关系）
 * - parent_id 为 null/undefined/0 的视为一级分类
 * - 其余按 parent_id 归类到对应父分类的 children 数组
 * - 同时设置 hasChildren 标记，便于 ElTable tree-props 渲染
 */
function buildCategoryTree(list: CategoryRow[]): CategoryRow[] {
  const map = new Map<number, CategoryRow>()
  list.forEach(item => {
    map.set(item.id, { ...item, children: [], hasChildren: false })
  })
  const roots: CategoryRow[] = []
  map.forEach(item => {
    const parentId = item.parent_id ?? null
    if (parentId === null || parentId === 0 || !map.has(parentId)) {
      roots.push(item)
    } else {
      const parent = map.get(parentId)!
      parent.children!.push(item)
      parent.hasChildren = true
    }
  })
  // 对每个节点的 children 按 sort_order 排序（无 sort_order 视为 0）
  const sortFn = (a: CategoryRow, b: CategoryRow) =>
    (a.sort_order ?? 0) - (b.sort_order ?? 0)
  const sortRecursive = (nodes: CategoryRow[]) => {
    nodes.sort(sortFn)
    nodes.forEach(node => {
      if (node.children && node.children.length > 0) sortRecursive(node.children)
      else {
        // 叶子节点清空 children，避免空数组影响树形展示
        node.children = undefined
        node.hasChildren = false
      }
    })
  }
  sortRecursive(roots)
  return roots
}

interface LogRow {
  id?: number
  batch_id: string
  status?: string
  total_conversations?: number
  kept_conversations?: number
  extracted_items?: number
  deduplicated_items?: number
  llm_tokens_used?: number
  llm_cost_yuan?: number
  started_at?: string
  finished_at?: string
  error_message?: string
}

// ===== 知识库条目 =====
const entryQuery = reactive({
  page: 1,
  size: 20,
  category: '' as string | null,
  status: '' as string | null,
  keyword: '' as string | null,
})
const minScoreInput = ref('')
const entryList = reactive<{ list: EntryRow[]; total: number }>({ list: [], total: 0 })
const entryState = ref<'loading' | 'ready' | 'error'>('loading')
const entryError = ref('')
const selectedIds = ref<number[]>([])
const batchApproving = ref(false)
const batchRejecting = ref(false)
const deletingEntry = ref<number | null>(null)

async function loadEntries() {
  entryState.value = 'loading'
  entryError.value = ''
  try {
    const params: Record<string, any> = { page: entryQuery.page, size: entryQuery.size }
    if (entryQuery.category) params.category = entryQuery.category
    if (entryQuery.status) params.status = entryQuery.status
    const minScoreNum = Number(minScoreInput.value)
    if (minScoreInput.value !== '' && Number.isFinite(minScoreNum)) {
      params.minScore = minScoreNum
    }
    if (entryQuery.keyword) params.keyword = entryQuery.keyword
    const data = await request.get<any>({ url: '/learned-kb/list', params })
    entryList.list = Array.isArray(data?.list) ? data.list : []
    entryList.total = Number(data?.total) || entryList.list.length
    entryState.value = 'ready'
  } catch (error: unknown) {
    entryError.value = getErrorMessage(error, '知识库条目读取失败。')
    entryState.value = 'error'
  }
}

function searchEntries() {
  entryQuery.page = 1
  loadEntries()
}

function resetEntryQuery() {
  entryQuery.category = ''
  entryQuery.status = ''
  entryQuery.keyword = ''
  minScoreInput.value = ''
  entryQuery.page = 1
  loadEntries()
}

function onSelectionChange(rows: EntryRow[]) {
  selectedIds.value = rows.map((r) => r.id)
}

async function onApprove(row: EntryRow) {
  try {
    await ElMessageBox.confirm(`确认通过条目 #${row.id} 吗？`, '审核确认', { type: 'success' })
  } catch {
    return
  }
  try {
    await request.post({ url: `/learned-kb/${row.id}/approve` })
    ElMessage.success('已通过')
    entryDetailVisible.value = false
    loadEntries()
    loadCategories()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '操作失败。'))
  }
}

async function onReject(row: EntryRow) {
  let reason = ''
  try {
    const res = await ElMessageBox.prompt('请输入拒绝原因', '拒绝确认', {
      type: 'warning',
      inputPlaceholder: '例如：答案不准确 / 重复条目',
      inputValidator: (v: string) => (!!v && v.trim().length > 0) || '请输入拒绝原因',
    })
    reason = res.value
  } catch {
    return
  }
  try {
    await request.post({ url: `/learned-kb/${row.id}/reject`, data: { reason } })
    ElMessage.success('已拒绝')
    entryDetailVisible.value = false
    loadEntries()
    loadCategories()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '操作失败。'))
  }
}

async function onBatchApprove() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(
      `确认批量通过 ${selectedIds.value.length} 条吗？`,
      '批量审核',
      { type: 'success' }
    )
  } catch {
    return
  }
  batchApproving.value = true
  try {
    await request.post({ url: '/learned-kb/batch-approve', data: { ids: selectedIds.value } })
    ElMessage.success('已批量通过')
    selectedIds.value = []
    loadEntries()
    loadCategories()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '操作失败。'))
  } finally {
    batchApproving.value = false
  }
}

async function onBatchReject() {
  if (!selectedIds.value.length) return
  let reason = ''
  try {
    const res = await ElMessageBox.prompt(
      `请输入批量拒绝原因（共 ${selectedIds.value.length} 条）`,
      '批量拒绝',
      {
        type: 'warning',
        inputValidator: (v: string) => (!!v && v.trim().length > 0) || '请输入拒绝原因',
      }
    )
    reason = res.value
  } catch {
    return
  }
  batchRejecting.value = true
  try {
    await request.post({
      url: '/learned-kb/batch-reject',
      data: { ids: selectedIds.value, reason },
    })
    ElMessage.success('已批量拒绝')
    selectedIds.value = []
    loadEntries()
    loadCategories()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '操作失败。'))
  } finally {
    batchRejecting.value = false
  }
}

async function onDeleteEntry(row: EntryRow) {
  try {
    await ElMessageBox.confirm(
      `确认删除条目 #${row.id} 吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  deletingEntry.value = row.id
  try {
    await request.del({ url: `/learned-kb/${row.id}` })
    ElMessage.success('已删除')
    loadEntries()
    loadCategories()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '删除失败。'))
  } finally {
    deletingEntry.value = null
  }
}

// ===== 条目详情 =====
const entryDetailVisible = ref(false)
const entryDetail = ref<EntryRow | null>(null)
const entryDetailState = ref<'loading' | 'ready' | 'error'>('loading')

async function openEntryDetail(row: EntryRow) {
  entryDetailVisible.value = true
  entryDetailState.value = 'loading'
  entryDetail.value = row
  try {
    const data = await request.get<any>({ url: `/learned-kb/${row.id}` })
    entryDetail.value = (data || row) as EntryRow
    entryDetailState.value = 'ready'
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '加载详情失败。'))
    entryDetailState.value = 'error'
  }
}

// ===== 查看对话 =====
interface ConversationMessage {
  sender?: string
  content?: string
  message_time?: string
  is_auto_reply?: number | boolean
  direction?: string
}
const conversationVisible = ref(false)
const conversationState = ref<'loading' | 'ready'>('loading')
const conversationMessages = ref<ConversationMessage[]>([])

async function openConversation(row: EntryRow) {
  conversationVisible.value = true
  conversationState.value = 'loading'
  conversationMessages.value = []
  try {
    const data = await request.get<any[]>({ url: `/learned-kb/${row.id}/conversation` })
    conversationMessages.value = Array.isArray(data) ? data : []
    conversationState.value = 'ready'
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '加载对话失败。'))
    conversationState.value = 'ready'
  }
}

// ===== 分类管理 =====
const categoryList = ref<CategoryRow[]>([])
const categoryState = ref<'loading' | 'ready' | 'error'>('loading')
const categoryError = ref('')

async function loadCategories() {
  categoryState.value = 'loading'
  categoryError.value = ''
  try {
    const data = await request.get<any[]>({ url: '/learned-kb/categories' })
    // 修复：将平铺列表转换为树形结构，按 parent_id 建立父子关系
    // 配合 ElTable 的 row-key + tree-props 实现层级显示
    categoryList.value = buildCategoryTree(Array.isArray(data) ? data : [])
    categoryState.value = 'ready'
  } catch (error: unknown) {
    categoryError.value = getErrorMessage(error, '分类读取失败。')
    categoryState.value = 'error'
  }
}

const categoryDialogVisible = ref(false)
const categoryDialogTitle = ref('新增分类')
const categorySaving = ref(false)
const categoryFormRef = ref<FormInstance>()
const categoryForm = reactive<{ id: number | null; name: string }>({ id: null, name: '' })
const categoryRules: FormRules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
}

function openCreateCategory() {
  categoryDialogTitle.value = '新增分类'
  categoryForm.id = null
  categoryForm.name = ''
  categoryDialogVisible.value = true
}

function openRenameCategory(row: CategoryRow) {
  categoryDialogTitle.value = `重命名 #${row.id}`
  categoryForm.id = row.id
  categoryForm.name = row.name
  categoryDialogVisible.value = true
}

async function onSaveCategory() {
  if (!categoryFormRef.value) return
  await categoryFormRef.value.validate(async (valid) => {
    if (!valid) return
    categorySaving.value = true
    try {
      if (categoryForm.id) {
        await request.put({
          url: `/learned-kb/categories/${categoryForm.id}`,
          data: { name: categoryForm.name },
        })
        ElMessage.success('已重命名')
      } else {
        await request.post({
          url: '/learned-kb/categories',
          data: { name: categoryForm.name },
        })
        ElMessage.success('已新增')
      }
      categoryDialogVisible.value = false
      loadCategories()
    } catch (error: unknown) {
      ElMessage.error(getErrorMessage(error, '保存失败。'))
    } finally {
      categorySaving.value = false
    }
  })
}

async function onDeleteCategory(row: CategoryRow) {
  try {
    await ElMessageBox.confirm(
      `确认删除分类 "${row.name}" 吗？该分类下的条目可能需要重新归类。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await request.del({ url: `/learned-kb/categories/${row.id}` })
    ElMessage.success('已删除')
    loadCategories()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '删除失败。'))
  }
}

// ===== 合并分类 =====
const mergeDialogVisible = ref(false)
const merging = ref(false)
const mergeFormRef = ref<FormInstance>()
const mergeForm = reactive<{ fromId: number | null; toId: number | null }>({ fromId: null, toId: null })
const mergeRules: FormRules = {
  fromId: [{ required: true, message: '请选择源分类', trigger: 'change' }],
  toId: [{ required: true, message: '请选择目标分类', trigger: 'change' }],
}

function openMergeCategory() {
  mergeForm.fromId = null
  mergeForm.toId = null
  mergeDialogVisible.value = true
}

async function onMergeCategory() {
  if (!mergeFormRef.value) return
  await mergeFormRef.value.validate(async (valid) => {
    if (!valid) return
    if (mergeForm.fromId === mergeForm.toId) {
      ElMessage.warning('源分类与目标分类不能相同')
      return
    }
    merging.value = true
    try {
      await request.post({
        url: '/learned-kb/categories/merge',
        data: { from_id: mergeForm.fromId, to_id: mergeForm.toId },
      })
      ElMessage.success('已合并')
      mergeDialogVisible.value = false
      loadCategories()
    } catch (error: unknown) {
      ElMessage.error(getErrorMessage(error, '合并失败。'))
    } finally {
      merging.value = false
    }
  })
}

// ===== 学习日志 =====
const logQuery = reactive({ page: 1, size: 20 })
const logList = reactive<{ list: LogRow[]; total: number }>({ list: [], total: 0 })
const logState = ref<'loading' | 'ready' | 'error'>('loading')
const logError = ref('')

async function loadLogs() {
  logState.value = 'loading'
  logError.value = ''
  try {
    const data = await request.get<any>({
      url: '/learned-kb/logs',
      params: { page: logQuery.page, size: logQuery.size },
    })
    logList.list = Array.isArray(data?.list) ? data.list : []
    logList.total = Number(data?.total) || logList.list.length
    logState.value = 'ready'
  } catch (error: unknown) {
    logError.value = getErrorMessage(error, '学习日志读取失败。')
    logState.value = 'error'
  }
}

const logDetailVisible = ref(false)
const logDetail = ref<LogRow | null>(null)
const logDetailState = ref<'loading' | 'ready'>('loading')

async function openLogDetail(row: LogRow) {
  logDetailVisible.value = true
  logDetailState.value = 'loading'
  logDetail.value = null
  try {
    const data = await request.get<any>({ url: `/learned-kb/logs/${row.batch_id}` })
    logDetail.value = (data || row) as LogRow
    logDetailState.value = 'ready'
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '加载日志详情失败。'))
    logDetail.value = row
    logDetailState.value = 'ready'
  }
}

// ===== 配置 =====
const triggering = ref(false)
const backfilling = ref(false)

async function onTriggerLearning() {
  try {
    await ElMessageBox.confirm(
      '确认立即触发学习任务吗？将扫描最近的会话提取问答对。',
      '触发确认',
      { type: 'info' }
    )
  } catch {
    return
  }
  triggering.value = true
  try {
    const data = await request.post<any>({ url: '/learned-kb/trigger' })
    ElMessage.success((data as string) || '学习任务已触发')
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '触发失败。'))
  } finally {
    triggering.value = false
  }
}

async function onBackfill() {
  try {
    await ElMessageBox.confirm(
      '回填会重新处理所有历史会话，耗时较长。确认继续？',
      '回填确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  backfilling.value = true
  try {
    const data = await request.post<any>({
      url: '/learned-kb/backfill',
      data: { confirm: 'confirm' },
    })
    ElMessage.success((data as string) || '回填任务已触发')
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '回填失败。'))
  } finally {
    backfilling.value = false
  }
}

// ===== 工具函数 =====
function statusLabel(status?: string): string {
  if (status === 'pending') return '待审核'
  if (status === 'approved') return '已通过'
  if (status === 'rejected') return '已拒绝'
  return status || '—'
}

function statusTagType(status?: string): 'primary' | 'success' | 'info' | 'warning' | 'danger' {
  if (status === 'pending') return 'warning'
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'info'
  return 'info'
}

function logStatusTagType(status?: string): 'primary' | 'success' | 'info' | 'warning' | 'danger' {
  if (status === 'running') return 'primary'
  if (status === 'success' || status === 'finished') return 'success'
  if (status === 'failed' || status === 'error') return 'danger'
  return 'info'
}

function isTruthy(value: unknown): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value === 1
  if (typeof value === 'string') return value === '1' || value.toLowerCase() === 'true'
  return false
}

function formatScore(value: unknown): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toFixed(2)
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim() ? error.message : fallback
}

function refreshCurrentTab() {
  if (activeTab.value === 'entries') loadEntries()
  else if (activeTab.value === 'categories') loadCategories()
  else if (activeTab.value === 'logs') loadLogs()
}

// ===== 初始化 =====
onMounted(() => {
  loadEntries()
  loadCategories()
})

watch(activeTab, (tab) => {
  if (tab === 'logs' && logState.value === 'loading') loadLogs()
})
</script>

<style scoped>
.learned-kb-page {
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
.empty-state {
  padding: 24px;
  color: var(--el-text-color-secondary);
}
.detail-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
}
.detail-text--danger {
  color: var(--el-color-danger);
}
.config-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}
.action-card h4 {
  margin: 0 0 8px;
  font-size: 16px;
}
.action-card p {
  margin: 0 0 16px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.conversation-list {
  max-height: 60vh;
  overflow-y: auto;
  padding: 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.conv-msg {
  margin-bottom: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
}
.conv-msg--seller {
  border-left: 3px solid var(--el-color-primary);
}
.conv-msg--buyer {
  border-left: 3px solid var(--el-color-success);
}
.conv-msg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.conv-msg-sender {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.conv-msg-ai-tag {
  display: inline-block;
  padding: 0 6px;
  height: 18px;
  line-height: 18px;
  border-radius: 9px;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 11px;
}
.conv-msg-time {
  margin-left: auto;
}
.conv-msg-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}
</style>
