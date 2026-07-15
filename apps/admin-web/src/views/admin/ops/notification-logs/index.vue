<template>
  <div class="notify-log-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>通知发送记录</h2>
          <p>查看用户测试通知、Webhook 请求结果、耗时、状态码和失败原因，便于排查告警通道配置问题。</p>
        </div>
        <ElButton type="primary" :loading="loading" @click="load">刷新</ElButton>
      </div>
      <ElForm :inline="true" :model="query" class="search-form">
        <ElFormItem label="发送结果">
          <ElSelect v-model="query.success" placeholder="全部" clearable style="width: 160px">
            <ElOption label="成功" value="1" />
            <ElOption label="失败" value="0" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="渠道">
          <ElInput v-model="query.channelKey" placeholder="webhook / feishu / dingding" clearable @keyup.enter="search" />
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput v-model="query.keyword" placeholder="渠道名 / 消息 / 用户ID" clearable @keyup.enter="search" />
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
        title="正在加载通知发送记录"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="通知发送记录暂时不可用"
        description="请求失败，不能将当前状态解释为没有发送记录。"
        @retry="load"
      />
      <AdminDataState
        v-else-if="listState === 'empty'"
        state="empty"
        title="暂无通知发送记录"
        description="查询已成功完成，当前筛选条件下没有记录。"
        :retryable="false"
      />
      <ElTable v-else :data="records" border stripe style="width: 100%">
        <template #empty><div class="empty-state">暂无通知发送记录</div></template>
        <ElTableColumn prop="createdTime" label="时间" min-width="170" />
        <ElTableColumn prop="channelName" label="渠道" min-width="150">
          <template #default="scope">
            <div class="channel-cell">
              <strong>{{ scope.row.channelName || scope.row.channelKey || '-' }}</strong>
              <span>{{ scope.row.channelKey || '-' }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="eventType" label="事件" width="110" />
        <ElTableColumn label="结果" width="100">
          <template #default="scope">
            <ElTag :type="isSuccess(scope.row.success) ? 'success' : 'danger'">
              {{ isSuccess(scope.row.success) ? '成功' : '失败' }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="statusCode" label="HTTP" width="90" />
        <ElTableColumn prop="costMs" label="耗时" width="100">
          <template #default="scope">{{ scope.row.costMs ?? 0 }} ms</template>
        </ElTableColumn>
        <ElTableColumn label="说明 / 失败原因" min-width="320" show-overflow-tooltip>
          <template #default="scope">{{ redactSensitiveText(scope.row.message) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="tenantId" label="租户" width="90" />
        <ElTableColumn prop="userId" label="用户ID" width="100" />
        <ElTableColumn label="操作" width="96" fixed="right">
          <template #default="scope">
            <ElButton link type="primary" @click="openDetail(scope.row)">详情</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
      <div v-if="listState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ total }} 条发送记录</span>
        <ElPagination
          v-model:current-page="query.current"
          v-model:page-size="query.size"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @change="load"
        />
      </div>
    </ElCard>

    <ElDrawer v-model="detailVisible" title="通知发送详情" size="680px">
      <template v-if="currentDetail">
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="发送时间">{{ currentDetail.createdTime || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="事件">{{ currentDetail.eventType || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="渠道">{{ currentDetail.channelName || currentDetail.channelKey || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="结果">
            <ElTag :type="isSuccess(currentDetail.success) ? 'success' : 'danger'">
              {{ isSuccess(currentDetail.success) ? '成功' : '失败' }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="HTTP 状态">{{ currentDetail.statusCode ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="耗时">{{ currentDetail.costMs ?? 0 }} ms</ElDescriptionsItem>
          <ElDescriptionsItem label="租户">{{ currentDetail.tenantId ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="用户ID">{{ currentDetail.userId ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="重试次数">{{ currentDetail.retryCount ?? 0 }}</ElDescriptionsItem>
          <ElDescriptionsItem label="说明" :span="2">{{ redactSensitiveText(currentDetail.message) }}</ElDescriptionsItem>
        </ElDescriptions>
        <h3 class="detail-title">请求 Body</h3>
        <pre class="payload-block">{{ formatSensitivePayload(currentDetail.requestBody) }}</pre>
        <h3 class="detail-title">响应 Body / 异常</h3>
        <pre class="payload-block">{{ formatSensitivePayload(currentDetail.responseBody) }}</pre>
      </template>
    </ElDrawer>
  </div>
</template>

<script setup lang="ts">
  import { getNotificationDeliveryLogs, type NotificationDeliveryLogRecord } from '@/api/notification-logs'
  import { formatSensitivePayload, redactSensitiveText } from '@/utils/sensitive-display'

  defineOptions({ name: 'AdminNotificationDeliveryLogs' })

  const loading = ref(false)
  const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
  const records = ref<NotificationDeliveryLogRecord[]>([])
  const total = ref(0)
  const query = reactive({ success: '', channelKey: '', keyword: '', current: 1, size: 20 })
  const detailVisible = ref(false)
  const currentDetail = ref<NotificationDeliveryLogRecord | null>(null)

  onMounted(load)

  async function load() {
    loading.value = true
    listState.value = 'loading'
    try {
      const params = Object.fromEntries(Object.entries(query).filter(([, value]) => value !== '' && value !== null && value !== undefined))
      const page = await getNotificationDeliveryLogs(params)
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
  function reset() { query.success = ''; query.channelKey = ''; query.keyword = ''; query.current = 1; load() }
  function isSuccess(value: unknown) { return value === true || value === 1 || value === '1' }
  function openDetail(row: any) { currentDetail.value = row as NotificationDeliveryLogRecord; detailVisible.value = true }
</script>

<style scoped>
.notify-log-page { padding: 16px; }
.filter-card { margin-bottom: 16px; }
.page-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); }
.search-form { row-gap: 8px; }
.table-card { min-height: 420px; }
.pagination-row { display: flex; align-items: center; justify-content: space-between; margin-top: 16px; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.channel-cell { display: grid; gap: 2px; }
.channel-cell strong { color: var(--el-text-color-primary); }
.channel-cell span { color: var(--el-text-color-secondary); font-size: 12px; }
.detail-title { margin: 18px 0 8px; font-size: 15px; }
.payload-block { max-height: 280px; overflow: auto; padding: 12px; border-radius: 10px; background: #0f172a; color: #e5e7eb; white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.55; }
.empty-state { padding: 40px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 14px; }
</style>
