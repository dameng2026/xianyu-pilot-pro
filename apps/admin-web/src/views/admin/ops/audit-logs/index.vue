<template>
  <div class="audit-log-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>操作审计日志</h2>
          <p>集中查看账号 Cookie、商品删除、消息发送、会话转接、工作流发布等高风险操作。</p>
        </div>
        <div class="actions"><ElButton :loading="exporting" @click="exportCsv">导出 CSV</ElButton><ElButton type="primary" :loading="loading" @click="load">刷新</ElButton></div>
      </div>

      <ElForm :inline="true" :model="query" class="search-form">
        <ElFormItem label="操作类型">
          <ElInput v-model="query.operationType" placeholder="如 ACCOUNT_COOKIE_UPDATE" clearable @keyup.enter="search" />
        </ElFormItem>
        <ElFormItem label="对象类型">
          <ElInput v-model="query.targetType" placeholder="如 xianyu_account" clearable @keyup.enter="search" />
        </ElFormItem>
        <ElFormItem label="对象ID">
          <ElInput v-model="query.targetId" placeholder="targetId" clearable @keyup.enter="search" />
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput v-model="query.keyword" placeholder="描述/操作类型" clearable @keyup.enter="search" />
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
        title="正在加载审计日志"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="审计日志暂时不可用"
        description="请求失败，不能将当前状态解释为没有审计记录。"
        @retry="load"
      />
      <AdminDataState
        v-else-if="listState === 'empty'"
        state="empty"
        title="暂无审计日志"
        description="查询已成功完成，当前筛选条件下没有记录。"
        :retryable="false"
      />
      <ElTable v-else :data="records" border stripe style="width: 100%">
        <template #empty><div class="empty-state">暂无审计日志记录</div></template>
        <ElTableColumn prop="createdTime" label="时间" min-width="170" />
        <ElTableColumn prop="operationType" label="操作类型" min-width="220">
          <template #default="scope">
            <ElTag :type="typeTag(scope.row.operationType)">{{ scope.row.operationType || '-' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作说明" min-width="320" show-overflow-tooltip>
          <template #default="scope">{{ redactSensitiveText(scope.row.operationDesc) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="targetType" label="对象类型" min-width="150" />
        <ElTableColumn prop="targetId" label="对象ID" min-width="100" />
        <ElTableColumn prop="userId" label="用户ID" min-width="100" />
        <ElTableColumn prop="ipAddress" label="IP" min-width="140" />
      </ElTable>
      <div v-if="listState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ total }} 条审计记录</span>
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
  import { ElMessage } from 'element-plus'
  import { exportOperationLogsCsv, getOperationLogs, type OperationLogRecord } from '@/api/operation-logs'
  import { redactSensitiveText } from '@/utils/sensitive-display'

  defineOptions({ name: 'AdminAuditLogs' })

  const loading = ref(false)
  const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
  const exporting = ref(false)
  const records = ref<OperationLogRecord[]>([])
  const total = ref(0)
  const query = reactive({
    operationType: '',
    targetType: '',
    targetId: '',
    keyword: '',
    current: 1,
    size: 20
  })

  onMounted(load)

  async function load() {
    loading.value = true
    listState.value = 'loading'
    try {
      const params = Object.fromEntries(Object.entries(query).filter(([, value]) => value !== '' && value !== null && value !== undefined))
      const page = await getOperationLogs(params)
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

  function search() {
    query.current = 1
    load()
  }

  function reset() {
    query.operationType = ''
    query.targetType = ''
    query.targetId = ''
    query.keyword = ''
    query.current = 1
    load()
  }

  async function exportCsv() {
    exporting.value = true
    try {
      const params = Object.fromEntries(Object.entries({ ...query, limit: 5000 }).filter(([, value]) => value !== '' && value !== null && value !== undefined))
      delete params.current
      delete params.size
      await exportOperationLogsCsv(params)
      ElMessage.success('CSV 导出已开始')
    } catch (err: any) {
      ElMessage.error(err?.message || 'CSV 导出失败')
    } finally {
      exporting.value = false
    }
  }

  function typeTag(type?: string) {
    if (!type) return 'info'
    if (type.includes('DELETE') || type.includes('COOKIE')) return 'danger'
    if (type.includes('TRANSFER') || type.includes('WEBSOCKET')) return 'warning'
    if (type.includes('SEND') || type.includes('MARK')) return 'success'
    return 'info'
  }
</script>

<style scoped>
.audit-log-page { padding: 16px; }
.filter-card { margin-bottom: 16px; }
.actions { display: flex; gap: 8px; }
.page-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); }
.search-form { row-gap: 8px; }
.table-card { min-height: 420px; }
.pagination-row { display: flex; align-items: center; justify-content: space-between; margin-top: 16px; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.empty-state { padding: 40px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 14px; }
</style>
