<!-- 注册页面 -->
<template>
  <div class="flex w-full h-screen">
    <LoginLeftView />

    <div class="relative flex-1">
      <AuthTopBar />

      <div class="auth-right-wrap">
        <div class="form">
          <h2 class="title">{{ $t('register.title') }}</h2>
          <p class="sub-title">{{ $t('register.subTitle') }}</p>

          <ElAlert
            class="mt-7.5"
            type="info"
            :closable="false"
            show-icon
            title="管理员账号由超级管理员创建"
            description="本平台暂不开放自助注册。如需开通管理员账号，请联系系统超级管理员在「用户管理」页面为您创建账号并分配角色。"
          />

          <div class="mt-7.5 p-4 bg-g-100 rounded-lg text-sm text-g-700 leading-6">
            <p class="font-medium mb-2">联系方式：</p>
            <p>· 联系上级管理员</p>
            <p>· 提供您的姓名、邮箱、所属部门</p>
            <p>· 管理员将在后台为您分配账号与权限</p>
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
  defineOptions({ name: 'Register' })

  const router = useRouter()

  const toLogin = () => {
    router.push({ name: 'Login' })
  }
</script>

<style scoped>
  @import '../login/style.css';
</style>
