<template>
  <ElDialog
    v-model="dialogVisible"
    :title="dialogType === 'add' ? '新增用户' : '编辑用户'"
    width="550px"
    align-center
    @closed="handleClosed"
  >
    <ElForm ref="formRef" :model="form" :rules="rules" label-width="110px">
      <ElFormItem label="登录账号" prop="username">
        <ElInput v-model="form.username" placeholder="请输入登录账号" :disabled="dialogType === 'edit'" />
      </ElFormItem>
      <template v-if="dialogType === 'add'">
        <ElFormItem label="密码" prop="password">
          <ElInput v-model="form.password" type="password" placeholder="请输入密码（至少8位，含字母+数字）" show-password />
        </ElFormItem>
        <ElFormItem label="确认密码" prop="confirmPassword">
          <ElInput v-model="form.confirmPassword" type="password" placeholder="请再次输入密码" show-password />
        </ElFormItem>
      </template>
      <ElFormItem label="昵称" prop="nickname">
        <ElInput v-model="form.nickname" placeholder="请输入昵称" />
      </ElFormItem>
      <ElFormItem label="手机号" prop="phone">
        <ElInput
          v-model="form.phone"
          :placeholder="dialogType === 'edit' ? phonePlaceholder : '请输入手机号（选填）'"
        />
        <div v-if="dialogType === 'edit' && form.phone === ''" class="text-xs text-gray-400 mt-1">
          留空表示不修改手机号
        </div>
      </ElFormItem>
      <ElFormItem label="邮箱" prop="email">
        <ElInput
          v-model="form.email"
          :placeholder="dialogType === 'edit' ? emailPlaceholder : '请输入邮箱（选填）'"
        />
        <div v-if="dialogType === 'edit' && form.email === ''" class="text-xs text-gray-400 mt-1">
          留空表示不修改邮箱
        </div>
      </ElFormItem>
      <ElFormItem label="租户" prop="tenantId">
        <ElSelect
          v-model="form.tenantId"
          placeholder="留空则自动分配默认租户"
          clearable
          filterable
          :loading="tenantLoading"
        >
          <ElOption
            v-for="t in tenantOptions"
            :key="t.id"
            :label="`${t.name} (ID: ${t.id})`"
            :value="String(t.id)"
          />
        </ElSelect>
        <ElAlert
          v-if="tenantState === 'error'"
          class="mt-2"
          type="error"
          :closable="false"
          show-icon
          title="租户列表暂时不可用"
        >
          <template #default>
            <ElButton size="small" type="danger" plain @click="loadTenants">重试</ElButton>
          </template>
        </ElAlert>
      </ElFormItem>
      <ElFormItem label="状态" prop="status">
        <ElSelect v-model="form.status" placeholder="请选择状态">
          <ElOption label="正常" value="正常" />
          <ElOption label="禁用" value="禁用" />
        </ElSelect>
      </ElFormItem>
      <template v-if="dialogType === 'edit'">
        <ElDivider />
        <ElFormItem label="修改密码">
          <ElSwitch v-model="changePassword" />
          <span class="ml-2 text-xs text-gray-400">开启后可设置新密码</span>
        </ElFormItem>
        <template v-if="changePassword">
          <ElFormItem label="新密码" prop="password">
            <ElInput v-model="form.password" type="password" placeholder="请输入新密码（至少8位，含字母+数字）" show-password />
          </ElFormItem>
          <ElFormItem label="确认密码" prop="confirmPassword">
            <ElInput v-model="form.confirmPassword" type="password" placeholder="请再次输入新密码" show-password />
          </ElFormItem>
        </template>
        <ElFormItem label="VIP 级别" prop="vipLevel">
          <ElSelect v-model="form.vipLevel" placeholder="选择 VIP 级别">
            <ElOption label="普通用户" :value="0" />
            <ElOption label="VIP（单店版）" :value="3" />
            <ElOption label="VIP" :value="1" />
            <ElOption label="SVP" :value="2" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="Token 余额" prop="tokenBalance">
          <ElInputNumber v-model="form.tokenBalance" :min="0" style="width: 100%" placeholder="输入 Token 余额" />
        </ElFormItem>
      </template>
    </ElForm>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton
        type="primary"
        :loading="submitting"
        :disabled="tenantState !== 'ready'"
        @click="handleSubmit"
      >确定</ElButton>
    </template>
  </ElDialog>
</template>

<script setup lang="ts">
  import { fetchCreateUser, fetchUpdateUser, fetchGetTenantList } from '@/api/system-manage'
  import type { FormInstance, FormRules } from 'element-plus'

  type UserListItem = Api.SystemManage.UserListItem

  interface Props {
    visible: boolean
    type: 'add' | 'edit'
    userData?: Partial<UserListItem> | null
  }

  interface Emits {
    (e: 'update:visible', value: boolean): void
    (e: 'success'): void
  }

  const props = withDefaults(defineProps<Props>(), {
    visible: false,
    type: 'add',
    userData: null
  })

  const emit = defineEmits<Emits>()
  const formRef = ref<FormInstance>()
  const submitting = ref(false)
  const emitSuccessAfterClose = ref(false)
  // 编辑模式下是否修改密码
  const changePassword = ref(false)
  // 编辑模式下原手机号/邮箱的脱敏占位提示（仅用于 placeholder，不参与提交）
  const phonePlaceholder = ref('')
  const emailPlaceholder = ref('')
  // 租户下拉选项
  const tenantOptions = ref<{ id: number; name: string }[]>([])
  const tenantLoading = ref(false)
  const tenantState = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')

  const dialogVisible = computed({
    get: () => props.visible,
    set: (value) => emit('update:visible', value)
  })

  const dialogType = computed(() => props.type)

  const form = reactive({
    username: '',
    password: '',
    confirmPassword: '',
    nickname: '',
    phone: '',
    email: '',
    tenantId: '',
    status: '正常',
    vipLevel: 0,
    tokenBalance: 0
  })

  const validatePassword = (_rule: any, value: string, callback: any) => {
    // 新增模式必填；编辑模式仅当 changePassword 开启时校验
    if (dialogType.value === 'add') {
      if (!value) {
        callback(new Error('请输入密码'))
        return
      }
      // 密码强度：至少 8 位，且必须同时包含字母和数字
      if (value.length < 8 || !/[A-Za-z]/.test(value) || !/\d/.test(value)) {
        callback(new Error('密码至少8位，且需同时包含字母和数字'))
        return
      }
    } else if (!changePassword.value) {
      callback()
      return
    } else {
      if (!value) {
        callback(new Error('请输入新密码'))
        return
      }
      if (value.length < 8 || !/[A-Za-z]/.test(value) || !/\d/.test(value)) {
        callback(new Error('密码至少8位，且需同时包含字母和数字'))
        return
      }
    }
    callback()
  }

  const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
    // 新增模式必填；编辑模式仅当 changePassword 开启时校验
    if (dialogType.value === 'add' || changePassword.value) {
      if (!value) {
        callback(new Error('请确认密码'))
        return
      }
      if (value !== form.password) {
        callback(new Error('两次输入的密码不一致'))
        return
      }
    }
    callback()
  }

  const validatePhone = (_rule: any, value: string, callback: any) => {
    if (!value) {
      callback()
      return
    }
    if (!/^1\d{10}$/.test(value)) {
      callback(new Error('手机号格式不正确'))
    } else {
      callback()
    }
  }

  const validateEmail = (_rule: any, value: string, callback: any) => {
    if (!value) {
      callback()
      return
    }
    if (!/^[\w.+-]+@[\w-]+\.[\w.]+$/.test(value)) {
      callback(new Error('邮箱格式不正确'))
    } else {
      callback()
    }
  }

  const rules: FormRules = {
    username: [
      { required: true, message: '请输入登录账号', trigger: 'blur' },
      { min: 2, max: 80, message: '长度 2-80 个字符', trigger: 'blur' }
    ],
    password: [{ validator: validatePassword, trigger: 'blur' }],
    confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }],
    phone: [{ validator: validatePhone, trigger: 'blur' }],
    email: [{ validator: validateEmail, trigger: 'blur' }],
    status: [{ required: true, message: '请选择状态', trigger: 'change' }]
  }

  const initForm = () => {
    changePassword.value = false
    phonePlaceholder.value = ''
    emailPlaceholder.value = ''
    if (dialogType.value === 'edit' && props.userData) {
      const data = props.userData
      form.username = data.username || ''
      form.password = ''
      form.confirmPassword = ''
      form.nickname = data.nickname || ''
      // PII 字段处理：编辑模式下表单值留空，原脱敏值仅作 placeholder 提示
      // 后端 update 接口在 data 不含 phone/email 字段时保持原值
      form.phone = ''
      form.email = ''
      phonePlaceholder.value = data.phone ? `当前：${data.phone}（留空不修改）` : '请输入手机号（选填）'
      emailPlaceholder.value = data.email ? `当前：${data.email}（留空不修改）` : '请输入邮箱（选填）'
      form.tenantId = data.tenantId === undefined || data.tenantId === null ? '' : String(data.tenantId)
      form.status = data.status || '正常'
      // VIP 等级映射：从 userLevel 字符串转换成数值
      const levelMap: Record<string, number> = { svp: 2, vip: 1, 'vip-single': 3 }
      form.vipLevel = levelMap[data.userLevel || ''] || 0
      form.tokenBalance = data.tokenBalance ?? 0
    } else {
      form.username = ''
      form.password = ''
      form.confirmPassword = ''
      form.nickname = ''
      form.phone = ''
      form.email = ''
      form.tenantId = ''
      form.status = '正常'
      form.vipLevel = 0
      form.tokenBalance = 0
    }
  }

  // 加载租户列表（首次打开弹窗时拉取，缓存复用）
  const loadTenants = async () => {
    if (tenantOptions.value.length > 0) {
      tenantState.value = 'ready'
      return
    }
    tenantLoading.value = true
    tenantState.value = 'loading'
    try {
      const list = await fetchGetTenantList()
      tenantOptions.value = list
      tenantState.value = 'ready'
    } catch {
      tenantOptions.value = []
      tenantState.value = 'error'
    } finally {
      tenantLoading.value = false
    }
  }

  watch(
    () => props.visible,
    (visible) => {
      if (visible) {
        initForm()
        loadTenants()
        nextTick(() => {
          formRef.value?.clearValidate()
        })
      }
    }
  )

  // 关闭修改密码开关时，清空密码字段并清除校验
  watch(changePassword, (val) => {
    if (!val) {
      form.password = ''
      form.confirmPassword = ''
      nextTick(() => {
        formRef.value?.clearValidate(['password', 'confirmPassword'])
      })
    }
  })

  const resetFormModel = () => {
    form.username = ''
    form.password = ''
    form.confirmPassword = ''
    form.nickname = ''
    form.phone = ''
    form.email = ''
    form.tenantId = ''
    form.status = '正常'
    form.vipLevel = 0
    form.tokenBalance = 0
  }

  const closeDialog = (shouldEmitSuccess = false) => {
    emitSuccessAfterClose.value = shouldEmitSuccess
    dialogVisible.value = false
  }

  const handleClose = () => {
    closeDialog(false)
  }

  const handleClosed = () => {
    const shouldEmitSuccess = emitSuccessAfterClose.value
    emitSuccessAfterClose.value = false
    try {
      changePassword.value = false
      phonePlaceholder.value = ''
      emailPlaceholder.value = ''
      resetFormModel()
      formRef.value?.resetFields()
      formRef.value?.clearValidate()
    } catch {
      // 忽略表单重置异常，确保 success 事件能正常发出
    }
    if (shouldEmitSuccess) {
      emit('success')
    }
  }

  const handleSubmit = async () => {
    if (!formRef.value) return
    if (tenantState.value !== 'ready') {
      ElMessage.warning('租户列表尚未成功读取，当前不能保存用户')
      return
    }
    try {
      await formRef.value.validate()
    } catch {
      return
    }

    submitting.value = true
    try {
      if (dialogType.value === 'add') {
        const payload: any = {
          username: form.username,
          password: form.password,
          confirmPassword: form.confirmPassword,
          nickname: form.nickname,
          phone: form.phone,
          email: form.email,
          tenantId: form.tenantId,
          status: form.status === '正常' ? 1 : 0
        }
        await fetchCreateUser(payload)
        ElMessage.success('用户创建成功')
      } else {
        // 编辑模式：单事务合并提交，避免多次 API 调用导致数据不一致
        const payload: any = {
          username: form.username,
          nickname: form.nickname,
          tenantId: form.tenantId,
          status: form.status === '正常' ? 1 : 0,
          vipLevel: form.vipLevel,
          tokenBalance: form.tokenBalance
        }
        // PII 字段：仅当用户主动输入新值时才传给后端（避免脱敏值写回）
        if (form.phone !== '') {
          payload.phone = form.phone
        }
        if (form.email !== '') {
          payload.email = form.email
        }
        // 密码：仅当开启修改密码开关并填入新密码时才传给后端
        if (changePassword.value && form.password) {
          payload.password = form.password
        }
        await fetchUpdateUser(props.userData!.id!, payload)
        ElMessage.success('用户更新成功')
      }

      closeDialog(true)
    } catch (error: any) {
      const msg = error?.data?.msg || error?.msg || error?.message || '操作失败'
      ElMessage.error(msg)
    } finally {
      submitting.value = false
    }
  }
</script>
