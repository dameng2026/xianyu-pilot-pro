<!-- 个人中心页面 -->
<template>
  <div class="w-full h-full p-0 bg-transparent border-none shadow-none">
    <div class="relative flex-b mt-2.5 max-md:block max-md:mt-1">
      <div class="w-112 mr-5 max-md:w-full max-md:mr-0">
        <div class="art-card-sm relative p-9 pb-6 overflow-hidden text-center">
          <img class="absolute top-0 left-0 w-full h-50 object-cover" src="@imgs/user/bg.webp" />
          <ElUpload
            :show-file-list="false"
            :auto-upload="true"
            :http-request="handleAvatarUpload"
            accept="image/png,image/jpeg"
            :before-upload="beforeAvatarUpload"
          >
            <div class="relative z-10 inline-block group">
              <img
                v-if="userInfo.avatar"
                class="w-20 h-20 mt-30 mx-auto object-cover border-2 border-white rounded-full"
                :src="userInfo.avatar"
              />
              <div
                v-else
                class="w-20 h-20 mt-30 mx-auto flex-cc text-2xl font-bold text-white border-2 border-white rounded-full"
                :style="{ background: 'linear-gradient(135deg, #2463eb, #7c3aed)' }"
              >
                {{ avatarText }}
              </div>
              <div
                class="absolute inset-0 flex-cc mt-30 mx-auto w-20 h-20 rounded-full bg-black/50 text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                style="top: 0;"
              >
                <ArtSvgIcon icon="ri:camera-line" class="text-xl" />
              </div>
            </div>
          </ElUpload>
          <p class="mt-2 text-xs text-g-500">点击头像上传（≤2MB，PNG/JPEG）</p>
          <h2 class="mt-3 text-xl font-normal">{{ userInfo.userName || '管理员' }}</h2>
          <p class="mt-5 text-sm">{{ greeting }}，欢迎使用闲鱼助手后台</p>

          <div class="w-75 mx-auto mt-7.5 text-left">
            <div class="mt-2.5">
              <ArtSvgIcon icon="ri:mail-line" class="text-g-700" />
              <span class="ml-2 text-sm">{{ userInfo.email || '未设置' }}</span>
            </div>
            <div class="mt-2.5">
              <ArtSvgIcon icon="ri:user-3-line" class="text-g-700" />
              <span class="ml-2 text-sm">{{ userInfo.userName || '-' }}</span>
            </div>
            <div class="mt-2.5">
              <ArtSvgIcon icon="ri:shield-keyhole-line" class="text-g-700" />
              <span class="ml-2 text-sm">{{ roleText }}</span>
            </div>
            <div class="mt-2.5">
              <ArtSvgIcon icon="ri:database-2-line" class="text-g-700" />
              <span class="ml-2 text-sm">用户 ID：{{ userInfo.userId || '-' }}</span>
            </div>
          </div>

          <div class="mt-10" v-if="roleTags.length">
            <h3 class="text-sm font-medium">角色权限</h3>
            <div class="flex flex-wrap justify-center mt-3.5">
              <div
                v-for="item in roleTags"
                :key="item"
                class="py-1 px-1.5 mr-2.5 mb-2.5 text-xs border border-g-300 rounded"
              >
                {{ item }}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="flex-1 overflow-hidden max-md:w-full max-md:mt-3.5">
        <div class="art-card-sm">
          <h1 class="p-4 text-xl font-normal border-b border-g-300">账号信息</h1>

          <ElDescriptions :column="2" border class="p-4">
            <ElDescriptionsItem label="用户名">{{ userInfo.userName || '-' }}</ElDescriptionsItem>
            <ElDescriptionsItem label="用户 ID">{{ userInfo.userId || '-' }}</ElDescriptionsItem>
            <ElDescriptionsItem label="邮箱">{{ userInfo.email || '未设置' }}</ElDescriptionsItem>
            <ElDescriptionsItem label="头像">{{ userInfo.avatar ? '已设置' : '未设置' }}</ElDescriptionsItem>
            <ElDescriptionsItem label="角色">
              <ElTag v-for="r in roleTags" :key="r" class="mr-2" :type="r === '超级管理员' ? 'danger' : 'primary'">{{ r }}</ElTag>
            </ElDescriptionsItem>
            <ElDescriptionsItem label="按钮权限">
              <ElTag v-for="b in buttonPerms" :key="b" class="mr-2 mb-1" type="info" effect="plain">{{ b }}</ElTag>
            </ElDescriptionsItem>
          </ElDescriptions>
        </div>

        <div class="art-card-sm my-5">
          <h1 class="p-4 text-xl font-normal border-b border-g-300">安全设置</h1>
          <div class="p-5 flex-b">
            <div class="flex-1">
              <p class="text-sm font-medium">登录密码</p>
              <p class="mt-1.5 text-xs text-g-500">建议定期修改密码以保障账号安全，修改成功后需重新登录</p>
            </div>
            <ElButton type="primary" plain @click="openPasswordDialog">修改密码</ElButton>
          </div>
        </div>

        <div class="art-card-sm my-5">
          <h1 class="p-4 text-xl font-normal border-b border-g-300">安全提示</h1>
          <div class="p-5 text-sm text-g-700 leading-7">
            <p>· 当前账号信息由超级管理员维护，如需修改请联系管理员。</p>
            <p>· 头像可点击左侧头像区域自行上传。</p>
            <p>· 请妥善保管登录密码，不要在公共设备上保持登录状态。</p>
            <p>· 离开工位时请使用锁屏功能（{{ lockShortcut }}）保护会话安全。</p>
            <p>· 如发现异常登录或权限问题，请立即联系超级管理员处理。</p>
          </div>
        </div>
      </div>
    </div>

    <ElDialog
      v-model="passwordDialogVisible"
      title="修改登录密码"
      width="440px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <ElForm
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="90px"
        @submit.prevent
      >
        <ElFormItem label="原密码" prop="oldPassword">
          <ElInput
            v-model="passwordForm.oldPassword"
            type="password"
            show-password
            placeholder="请输入当前密码"
            autocomplete="current-password"
          />
        </ElFormItem>
        <ElFormItem label="新密码" prop="newPassword">
          <ElInput
            v-model="passwordForm.newPassword"
            type="password"
            show-password
            placeholder="至少 8 位，需同时包含字母和数字"
            autocomplete="new-password"
          />
        </ElFormItem>
        <ElFormItem label="确认密码" prop="confirmPassword">
          <ElInput
            v-model="passwordForm.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            autocomplete="new-password"
            @keyup.enter="submitPasswordChange"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="passwordDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="passwordSubmitting" @click="submitPasswordChange">
          确认修改
        </ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import { useUserStore } from '@/store/modules/user'
  import { uploadAdminAvatar } from '@/api/admin'
  import { changeAdminPassword } from '@/api/auth'
  import { ElMessage, ElMessageBox } from 'element-plus'
  import type { UploadRequestOptions } from 'element-plus'
  import type { FormInstance, FormRules } from 'element-plus'

  defineOptions({ name: 'UserCenter' })

  const userStore = useUserStore()
  const userInfo = computed(() => userStore.getUserInfo || ({} as any))

  const ROLE_MAP: Record<string, string> = {
    R_SUPER: '超级管理员',
    R_ADMIN: '运营管理员',
    R_USER: '普通用户'
  }

  const roleTags = computed<string[]>(() => {
    const roles = (userInfo.value as any).roles
    if (!Array.isArray(roles) || roles.length === 0) return ['普通用户']
    return roles.map((r: string) => ROLE_MAP[r] || r)
  })

  const roleText = computed(() => roleTags.value.join('、'))

  const buttonPerms = computed<string[]>(() => {
    const buttons = (userInfo.value as any).buttons
    if (!Array.isArray(buttons) || buttons.length === 0) return []
    return buttons
  })

  const avatarText = computed(() => {
    const name = String(userInfo.value.userName || '管')
    return name.charAt(0).toUpperCase()
  })

  const greeting = ref('你好')
  const lockShortcut = 'Win+L'

  // ===== 修改密码 =====
  const passwordDialogVisible = ref(false)
  const passwordSubmitting = ref(false)
  const passwordFormRef = ref<FormInstance>()
  const passwordForm = reactive({
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
  })

  const passwordRules: FormRules = {
    oldPassword: [
      { required: true, message: '请输入原密码', trigger: 'blur' }
    ],
    newPassword: [
      { required: true, message: '请输入新密码', trigger: 'blur' },
      { min: 8, message: '新密码至少 8 位', trigger: 'blur' },
      {
        validator: (_rule: any, value: string, callback: any) => {
          if (!value) return callback()
          if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
            return callback(new Error('新密码必须同时包含字母和数字'))
          }
          if (value === passwordForm.oldPassword) {
            return callback(new Error('新密码不能与原密码相同'))
          }
          callback()
        },
        trigger: 'blur'
      }
    ],
    confirmPassword: [
      { required: true, message: '请再次输入新密码', trigger: 'blur' },
      {
        validator: (_rule: any, value: string, callback: any) => {
          if (!value) return callback()
          if (value !== passwordForm.newPassword) {
            return callback(new Error('两次输入的密码不一致'))
          }
          callback()
        },
        trigger: 'blur'
      }
    ]
  }

  function openPasswordDialog() {
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
    passwordDialogVisible.value = true
  }

  async function submitPasswordChange() {
    if (!passwordFormRef.value) return
    try {
      await passwordFormRef.value.validate()
    } catch {
      return
    }
    passwordSubmitting.value = true
    try {
      await changeAdminPassword(passwordForm.oldPassword, passwordForm.newPassword)
      passwordDialogVisible.value = false
      // 修改密码后 security_version+1 使所有令牌失效，需引导用户重新登录
      await ElMessageBox.alert(
        '密码修改成功，为保障账号安全请使用新密码重新登录。',
        '修改成功',
        { type: 'success', confirmButtonText: '重新登录', showClose: false }
      )
      userStore.logOut()
    } catch (e: any) {
      const msg = e?.message || '密码修改失败，请稍后重试'
      ElMessage.error(msg)
    } finally {
      passwordSubmitting.value = false
    }
  }

  function beforeAvatarUpload(file: File): boolean {
    const validTypes = ['image/png', 'image/jpeg']
    if (!validTypes.includes(file.type)) {
      ElMessage.error('仅支持 PNG、JPEG 格式的图片')
      return false
    }
    if (file.size > 2 * 1024 * 1024) {
      ElMessage.error('图片大小不能超过 2MB')
      return false
    }
    return true
  }

  async function handleAvatarUpload(options: UploadRequestOptions): Promise<void> {
    try {
      const result = await uploadAdminAvatar(options.file as File)
      // 更新本地 store 的 userInfo
      userStore.setUserInfo({ ...(userInfo.value as any), avatar: result.url })
      ElMessage.success('头像上传成功')
    } catch (e: any) {
      const msg = e?.message || '头像上传失败'
      ElMessage.error(msg)
    }
  }

  onMounted(() => {
    updateGreeting()
  })

  function updateGreeting() {
    const h = new Date().getHours()
    if (h >= 6 && h < 9) greeting.value = '早上好'
    else if (h >= 9 && h < 11) greeting.value = '上午好'
    else if (h >= 11 && h < 13) greeting.value = '中午好'
    else if (h >= 13 && h < 18) greeting.value = '下午好'
    else if (h >= 18 && h < 24) greeting.value = '晚上好'
    else greeting.value = '夜深了'
  }
</script>
