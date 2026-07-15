<template>
  <div class="client-error-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>前端错误日志</h2>
          <p>查看用户端白屏、脚本异常、Promise 未捕获异常和支付/通知等关键流程报错。</p>
        </div>
        <ElButton type="primary" :loading="loading" @click="load">刷新</ElButton>
      </div>

      <ElForm :inline="true" :model="query" class="search-form">
        <ElFormItem label="错误类型">
          <ElSelect v-model="query.type" placeholder="全部" clearable style="width: 180px">
            <ElOption label="JavaScript Error" value="error" />
            <ElOption label="Unhandled Rejection" value="unhandledrejection" />
            <ElOption label="Manual Report" value="manual" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput v-model="query.keyword" placeholder="消息 / 路由 / 来源" clearable @keyup.enter="search" />
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
        title="正在加载前端错误日志"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="前端错误日志暂时不可用"
        description="请求失败，不能将当前状态解释为没有错误。"
        @retry="load"
      />
      <AdminDataState
        v-else-if="listState === 'empty'"
        state="empty"
        title="暂无前端错误日志"
        description="查询已成功完成，当前筛选条件下没有记录。"
        :retryable="false"
      />
      <ElTable v-else :data="records" border stripe style="width: 100%">
        <template #empty><div class="empty-state">暂无前端错误日志</div></template>
        <ElTableColumn prop="createdTime" label="时间" min-width="170" />
        <ElTableColumn prop="errorType" label="类型" min-width="150">
          <template #default="scope">
            <ElTag :type="typeTag(scope.row.errorType)">{{ scope.row.errorType || '-' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="错误消息" min-width="320" show-overflow-tooltip>
          <template #default="scope">{{ redactSensitiveText(scope.row.message) }}</template>
        </ElTableColumn>
        <ElTableColumn label="页面路由" min-width="220" show-overflow-tooltip>
          <template #default="scope">{{ redactSensitiveText(scope.row.route) }}</template>
        </ElTableColumn>
        <ElTableColumn label="来源" min-width="220" show-overflow-tooltip>
          <template #default="scope">{{ redactSensitiveText(scope.row.source) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="userId" label="用户ID" min-width="100" />
        <ElTableColumn prop="ipAddress" label="IP" min-width="140" />
        <ElTableColumn prop="userAgent" label="User-Agent" min-width="260" show-overflow-tooltip />
      </ElTable>
      <div v-if="listState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ total }} 条错误记录</span>
        <ElPagination
          v-model:current-page="query.current"
          v-model:page-size="query.size"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @change="load"
        />
      </div>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { getClientErrors, type ClientErrorRecord } from '@/api/client-errors'
  import { redactSensitiveText } from '@/utils/sensitive-display'

  defineOptions({ name: 'AdminClientErrors' })

  const loading = ref(false)
  const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
  const records = ref<ClientErrorRecord[]>([])
  const total = ref(0)
  const query = reactive({ type: '', keyword: '', current: 1, size: 20 })

  onMounted(load)

  async function load() {
    loading.value = true
    listState.value = 'loading'
    try {
      const params = Object.fromEntries(Object.entries(query).filter(([, value]) => value !== '' && value !== null && value !== undefined))
      const page = await getClientErrors(params)
      records.value = page?.records || []
      total.value = page?.total || 0
      listState.value = records.value.length > 0 ? 'ready' : 'empty'
    } catch {
      records.value = []
      total.value = 0
      listState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  function search() { query.current = 1; load() }
  function reset() { query.type = ''; query.keyword = ''; query.current = 1; load() }
  function typeTag(type?: string) {
    if (!type) return 'info'
    if (type.includes('rejection')) return 'warning'
    if (type.includes('error')) return 'danger'
    return 'info'
  }
</script>

<style scoped>
.client-error-page { padding: 16px; }
.filter-card { margin-bottom: 16px; }
.page-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); }
.search-form { row-gap: 8px; }
.table-card { min-height: 420px; }
.pagination-row { display: flex; align-items: center; justify-content: space-between; margin-top: 16px; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.empty-state { padding: 40px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 14px; }
</style>
