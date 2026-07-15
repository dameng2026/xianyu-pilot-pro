<template>
  <div class="flex w-full h-screen">
    <LoginLeftView />

    <div class="relative flex-1">
      <AuthTopBar />

      <div class="auth-right-wrap">
        <div class="form">
          <h2 class="title">{{ $t('forgetPassword.title') }}</h2>
          <p class="sub-title">{{ $t('forgetPassword.subTitle') }}</p>

          <ElAlert
            class="mt-7.5"
            type="warning"
            :closable="false"
            show-icon
            title="请联系超级管理员重置密码"
            description="本平台暂不开放自助找回密码。如忘记登录密码，请联系系统超级管理员，由管理员在「用户管理」页面为您重置密码。"
          />

          <div class="mt-7.5 p-4 bg-g-100 rounded-lg text-sm text-g-700 leading-6">
            <p class="font-medium mb-2">重置流程：</p>
            <p>· 联系超级管理员并提供您的账号</p>
            <p>· 管理员在「用户管理」页面找到您的账号</p>
            <p>· 管理员为您重置密码并告知新密码</p>
            <p>· 首次登录后请及时修改密码</p>
          </div>

          <div style="margin-top: 25px">
            <ElButton
              class="w-full custom-height"
              type="primary"
              @click="toLogin"
              v-ripple
            >
              返回登录
            </ElButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  defineOptions({ name: 'ForgetPassword' })

  const router = useRouter()

  const toLogin = () => {
    router.push({ name: 'Login' })
  }
</script>

<style scoped>
  @import '../login/style.css';
</style>
