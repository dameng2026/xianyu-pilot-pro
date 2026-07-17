<!-- 用户管理页面 - 对接 admin_module_record（sys_user） -->
<template>
  <div class="user-page art-full-height">
    <!-- 搜索栏 -->
    <UserSearch
      v-model="searchForm"
      @search="handleSearch"
      @reset="resetSearchParams"
    ></UserSearch>

    <ElCard class="art-table-card">
      <!-- 表格头部 -->
      <ArtTableHeader
        v-model:columns="columnChecks"
        :loading="loading"
        @refresh="refreshData"
      >
        <template #left>
          <ElSpace wrap>
            <ElButton type="primary" @click="showDialog('add')" v-ripple>
              <span class="i-ri:add-line mr-1"></span>新增用户
            </ElButton>
            <ElButton
              type="danger"
              :disabled="selectedIds.length === 0"
              @click="handleBatchDelete"
              v-ripple
            >
              批量删除
            </ElButton>
            <ElButton
              :disabled="selectedIds.length === 0"
              @click="handleBatchEnable"
              v-ripple
            >
              批量启用
            </ElButton>
            <ElButton
              :disabled="selectedIds.length === 0"
              @click="handleBatchDisable"
              v-ripple
            >
              批量禁用
            </ElButton>
            <ElButton
              type="success"
              :loading="exporting"
              @click="handleExport"
              v-ripple
            >
              <span class="i-ri:download-2-line mr-1"></span>导出 CSV
            </ElButton>
          </ElSpace>
        </template>
      </ArtTableHeader>

      <!-- 表格 -->
      <AdminDataState
        v-if="error"
        state="error"
        title="用户列表暂时不可用"
        description="无法确认当前用户数据，列表操作已暂停。"
        @retry="refreshData"
      />
      <ArtTable
        v-else
        ref="tableRef"
        row-key="id"
        :loading="loading"
        :data="data"
        :columns="columns"
        :pagination="pagination"
        @pagination:size-change="handleSizeChange"
        @pagination:current-change="handleCurrentChange"
        @selection-change="handleSelectionChange"
      >
      </ArtTable>

      <!-- 用户弹窗 -->
      <UserDialog
        v-model:visible="dialogVisible"
        :type="dialogType"
        :user-data="currentUserData"
        @success="handleDialogSuccess"
      />
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import ArtButtonMore from '@/components/core/forms/art-button-more/index.vue'
  import { useTable } from '@/hooks/core/useTable'
  import { fetchGetUserList, fetchDeleteUser, fetchBatchDeleteUser, fetchUpdateUserStatus, fetchBatchUpdateUserStatus, fetchResetUserPassword, fetchUserLoginToken, exportUsersCsv } from '@/api/system-manage'
  import UserSearch from './modules/user-search.vue'
  import UserDialog from './modules/user-dialog.vue'
  import { ElTag, ElMessageBox, ElAvatar } from 'element-plus'
  import type { ButtonMoreItem } from '@/components/core/forms/art-button-more/index.vue'

  defineOptions({ name: 'User' })

  type UserListItem = Api.SystemManage.UserListItem

  const dialogType = ref<'add' | 'edit'>('add')
  const dialogVisible = ref(false)
  const currentUserData = ref<UserListItem | null>(null)
  const selectedIds = ref<number[]>([])
  const exporting = ref(false)

  const searchForm = ref<Api.SystemManage.UserSearchParams>({
    username: undefined,
    status: undefined
  })

  function normalizeAvatarUrl(value: unknown) {
    const text = String(value ?? '').trim()
    if (!text || text === 'null' || text === 'undefined') return undefined
    return text
  }

  function formatDateTimeLocal(value: unknown) {
    if (!value) return '-'
    const text = String(value).trim()
    if (!text || text === '-') return '-'
    // 兼容带时区的 ISO 格式（如 2026-07-08T10:38:58.000+00:00），转为本地时间
    if (text.includes('T') && (text.includes('+') || text.includes('Z'))) {
      const d = new Date(text)
      if (!isNaN(d.getTime())) {
        const pad = (n: number) => String(n).padStart(2, '0')
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
      }
    }
    // 无时区的 ISO 格式（如 2026-07-10T15:52:23），直接替换 T
    return text.replace('T', ' ').replace(/\.\d+.*$/, '').slice(0, 19)
  }

  const { columns, columnChecks, data, loading, error, pagination, getData, replaceSearchParams, resetSearchParams, handleSizeChange, handleCurrentChange, refreshData } = useTable({
    core: {
      apiFn: fetchGetUserList,
      apiParams: { current: 1, size: 20 },
      columnsFactory: () => [
        { type: 'selection', width: 50, reserveSelection: true },
        { type: 'index', width: 60, label: '序号' },
        {
          prop: 'username',
          label: '用户名',
          width: 130,
          formatter: (row: UserListItem) =>
            h('div', { class: 'flex items-center gap-2' }, [
              h(ElAvatar, {
                size: 32,
                icon: 'UserFilled',
                src: normalizeAvatarUrl(row.avatar)
              }),
              h('span', { class: 'text-sm font-medium' }, row.username)
            ])
        },
        {
          prop: 'nickname',
          label: '昵称',
          width: 120,
          formatter: (row: UserListItem) => row.nickname || '-'
        },
        {
          prop: 'userLevelName',
          label: 'VIP 级别',
          width: 100,
          formatter: (row: UserListItem) => {
            const level = row.userLevel
            const levelName = row.userLevelName || '普通用户'
            let type: any = 'info'
            if (level === 'vip') type = 'warning'
            else if (level === 'svp') type = 'danger'
            return h(ElTag, { type, size: 'small', effect: 'dark' }, () => levelName)
          }
        },
        {
          prop: 'tokenBalance',
          label: 'Token 余额',
          width: 120,
          formatter: (row: UserListItem) => {
            const balance = row.tokenBalance ?? 0
            return h('span', { class: balance < 100 ? 'text-red-500 font-medium' : 'text-green-600 font-medium' }, String(balance))
          }
        },
        {
          prop: 'tenantName',
          label: '所属租户',
          width: 140,
          formatter: (row: UserListItem) => row.tenantName || '-'
        },
        {
          prop: 'xianyuAccountCount',
          label: '闲鱼账号',
          width: 100,
          formatter: (row: UserListItem) => row.xianyuAccountCount || '0'
        },
        {
          prop: 'status',
          label: '状态',
          width: 90,
          formatter: (row: UserListItem) => {
            const isNormal = row.status === '正常'
            return h(ElTag, { type: isNormal ? 'success' : 'danger', size: 'small' }, () => row.status || '未知')
          }
        },
        {
          prop: 'lastLoginTime',
          label: '最后登录',
          width: 170,
          formatter: (row: UserListItem) => formatDateTimeLocal(row.lastLoginTime)
        },
        {
          prop: 'createdTime',
          label: '创建时间',
          width: 170,
          formatter: (row: UserListItem) => formatDateTimeLocal(row.createdTime)
        },
        {
          prop: 'operation',
          label: '操作',
          width: 100,
          fixed: 'right',
          formatter: (row: UserListItem) =>
            h(ArtButtonMore, {
              list: [
                { key: 'edit', label: '编辑', icon: 'ri:edit-2-line' },
                { key: 'login', label: '登录前台', icon: 'ri:login-circle-line', disabled: row.status !== '正常' },
                {
                  key: row.status === '正常' ? 'disable' : 'enable',
                  label: row.status === '正常' ? '禁用' : '启用',
                  icon: row.status === '正常' ? 'ri:forbid-2-line' : 'ri:checkbox-circle-line'
                },
                { key: 'resetPassword', label: '重置密码', icon: 'ri:lock-password-line' },
                { key: 'delete', label: '删除', icon: 'ri:delete-bin-4-line', color: '#f56c6c' }
              ],
              onClick: (item: ButtonMoreItem) => handleMoreAction(item, row)
            })
        }
      ]
    }
  })

  const tableRef = ref()

  const handleSelectionChange = (selection: UserListItem[]) => {
    selectedIds.value = selection.map((row) => row.id)
  }

  const handleSearch = (params: Api.SystemManage.UserSearchParams) => {
    replaceSearchParams(params)
    getData()
  }

  const showDialog = (type: 'add' | 'edit', row?: UserListItem): void => {
    dialogType.value = type
    currentUserData.value = row || null
    dialogVisible.value = true
  }

  const handleDialogSuccess = () => {
    refreshData()
  }

  const handleMoreAction = (item: ButtonMoreItem, row: UserListItem) => {
    switch (item.key) {
      case 'edit': showDialog('edit', row); break
      case 'login': handleLoginAsUser(row); break
      case 'enable': handleToggleStatus(row, 1); break
      case 'disable': handleToggleStatus(row, 0); break
      case 'resetPassword': handleResetPassword(row); break
      case 'delete': handleDelete(row); break
    }
  }

  function showBatchOutcome(action: string, affected: number, requested: number) {
    if (affected === requested) {
      ElMessage.success(`成功${action} ${affected} 个用户`)
      return
    }
    if (affected === 0) {
      ElMessage.warning(`请求已处理，但没有用户被${action}`)
      return
    }
    ElMessage.warning(`仅${action} ${affected}/${requested} 个用户，请刷新后核对未处理项`)
  }

  const handleToggleStatus = (row: UserListItem, status: number) => {
    const actionText = status === 1 ? '启用' : '禁用'
    ElMessageBox.confirm(`确定要${actionText}用户"${row.username}"吗？`, `${actionText}确认`, {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: status === 1 ? 'success' : 'warning'
    })
      .then(async () => {
        try {
          await fetchUpdateUserStatus(row.id, status)
          ElMessage.success(`${actionText}成功`)
          refreshData()
        } catch (error: any) {
          ElMessage.error(error?.data?.msg || `${actionText}失败`)
        }
      })
      .catch(() => ElMessage.info('已取消操作'))
  }

  const handleDelete = (row: UserListItem) => {
    ElMessageBox.confirm(`确定要删除用户"${row.username}"吗？此操作不可恢复！`, '删除确认', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'error'
    })
      .then(async () => {
        try {
          await fetchDeleteUser(row.id)
          ElMessage.success('删除成功')
          refreshData()
        } catch (error: any) {
          ElMessage.error(error?.data?.msg || '删除失败')
        }
      })
      .catch(() => ElMessage.info('已取消删除'))
  }

  const handleBatchDelete = () => {
    if (selectedIds.value.length === 0) return ElMessage.warning('请先选择要删除的用户')
    ElMessageBox.confirm(`确定要删除选中的 ${selectedIds.value.length} 个用户吗？`, '批量删除确认', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'error'
    })
      .then(async () => {
        try {
          const res = await fetchBatchDeleteUser(selectedIds.value)
          showBatchOutcome('删除', res.count, selectedIds.value.length)
          selectedIds.value = []
          refreshData()
        } catch (error: any) {
          ElMessage.error(error?.data?.msg || '批量删除失败')
        }
      })
      .catch(() => ElMessage.info('已取消操作'))
  }

  const handleBatchEnable = () => {
    if (selectedIds.value.length === 0) return ElMessage.warning('请先选择要启用的用户')
    ElMessageBox.confirm(`确定要启用选中的 ${selectedIds.value.length} 个用户吗？`, '批量启用确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'success'
    })
      .then(async () => {
        try {
          const res = await fetchBatchUpdateUserStatus(selectedIds.value, 1)
          showBatchOutcome('启用', res.count, selectedIds.value.length)
          selectedIds.value = []
          refreshData()
        } catch (error: any) {
          ElMessage.error(error?.data?.msg || '批量启用失败')
        }
      })
      .catch(() => ElMessage.info('已取消操作'))
  }

  const handleBatchDisable = () => {
    if (selectedIds.value.length === 0) return ElMessage.warning('请先选择要禁用的用户')
    ElMessageBox.confirm(`确定要禁用选中的 ${selectedIds.value.length} 个用户吗？`, '批量禁用确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
      .then(async () => {
        try {
          const res = await fetchBatchUpdateUserStatus(selectedIds.value, 0)
          showBatchOutcome('禁用', res.count, selectedIds.value.length)
          selectedIds.value = []
          refreshData()
        } catch (error: any) {
          ElMessage.error(error?.data?.msg || '批量禁用失败')
        }
      })
      .catch(() => ElMessage.info('已取消操作'))
  }

  // 管理员代登：为指定前台用户签发 token 并在新标签页打开前台
  // 该操作仅用于辅助调试，需先二次确认；token 通过 URL hash 传递给前台，前台写入 localStorage 后立即清除 URL
  const handleLoginAsUser = (row: UserListItem) => {
    ElMessageBox.confirm(
      `确定要以用户"${row.username}"的身份登录前台吗？\n\n该操作会签发一个有效的登录凭证并在新标签页打开前台，仅用于辅助调试问题。`,
      '代登确认',
      {
        confirmButtonText: '确定登录',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
      .then(async () => {
        try {
          const res = await fetchUserLoginToken(row.id)
          const token = res?.token
          if (!token) {
            ElMessage.error('后端未返回有效凭证')
            return
          }
          const params = new URLSearchParams()
          params.set('token', token)
          if (res.username) params.set('username', res.username)
          const userWebUrl = (import.meta.env.VITE_USER_WEB_URL || '').replace(/\/+$/, '')
          if (!userWebUrl) {
            ElMessage.error('未配置前台地址（VITE_USER_WEB_URL），无法打开前台')
            return
          }
          // 使用 hash 路由 + query 携带 token，避免 token 进入服务器访问日志的 path
          const url = `${userWebUrl}#/auto-login?${params.toString()}`
          const win = window.open(url, '_blank')
          if (!win) {
            ElMessage.warning('浏览器拦截了新窗口，请允许弹窗后重试')
          } else {
            ElMessage.success(`已在新标签页以 ${row.username} 身份登录前台`)
          }
        } catch (error: any) {
          ElMessage.error(error?.data?.msg || error?.message || '代登失败')
        }
      })
      .catch(() => ElMessage.info('已取消代登'))
  }

  const handleResetPassword = (row: UserListItem) => {
    ElMessageBox.prompt(`请输入用户"${row.username}"的新密码（至少8位，需同时包含字母和数字）`, '重置密码', {
      confirmButtonText: '确定重置',
      cancelButtonText: '取消',
      inputPattern: /^(?=.*[A-Za-z])(?=.*\d).{8,}$/,
      inputErrorMessage: '密码至少8位，且需同时包含字母和数字',
      inputPlaceholder: '请输入新密码',
      inputType: 'password'
    })
      .then(async ({ value }) => {
        try {
          await fetchResetUserPassword(row.id, value)
          ElMessage.success('密码重置成功')
        } catch (error: any) {
          ElMessage.error(error?.data?.msg || '密码重置失败')
        }
      })
      .catch(() => ElMessage.info('已取消重置'))
  }

  // 导出用户列表为 CSV（按当前搜索条件，最多 5000 条；phone/email 已在后端脱敏）
  const handleExport = async () => {
    exporting.value = true
    try {
      await exportUsersCsv(searchForm.value.username || '', searchForm.value.status || '')
      ElMessage.success('导出成功')
    } catch (error: any) {
      ElMessage.error(error?.message || '导出失败')
    } finally {
      exporting.value = false
    }
  }
</script>
