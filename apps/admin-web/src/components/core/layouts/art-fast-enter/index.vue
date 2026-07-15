<!-- 顶部快速入口面板 -->
<template>
  <ElPopover
    ref="popoverRef"
    :width="700"
    :offset="0"
    :show-arrow="false"
    trigger="click"
    placement="bottom-start"
    popper-class="fast-enter-popover"
    :popper-style="{
      border: '1px solid var(--default-border)',
      borderRadius: 'calc(var(--custom-radius) / 2 + 4px)'
    }"
  >
    <template #reference>
      <slot />
    </template>

    <div class="grid grid-cols-[2fr_0.8fr]">
      <div>
        <div class="grid grid-cols-2 gap-1.5">
          <!-- 应用列表 -->
          <button
            v-for="application in enabledApplications"
            :key="application.name"
            type="button"
            class="mr-3 c-p flex-c gap-3 rounded-lg border-0 bg-transparent p-2 text-left hover:bg-g-200/70 dark:hover:bg-g-200/90 hover:[&_.app-icon]:!bg-transparent disabled:cursor-not-allowed disabled:opacity-60"
            :aria-label="`${application.name}：${application.description}`"
            :disabled="navigating"
            @click="handleApplicationClick(application)"
          >
            <span class="app-icon size-12 flex-cc rounded-lg bg-g-200/80 dark:bg-g-300/30" aria-hidden="true">
              <ArtSvgIcon
                class="text-xl"
                :icon="application.icon"
                :style="{ color: application.iconColor }"
              />
            </span>
            <span>
              <span class="block text-sm font-medium text-g-800">{{ application.name }}</span>
              <span class="mt-1 block text-xs text-g-600">{{ application.description }}</span>
            </span>
          </button>
        </div>
      </div>

      <div class="border-l-d pl-6 pt-2">
        <h3 class="mb-2.5 text-base font-medium text-g-800">快速链接</h3>
        <ul>
          <li
            v-for="quickLink in enabledQuickLinks"
            :key="quickLink.name"
            class="py-0"
          >
            <button
              type="button"
              class="c-p w-full border-0 bg-transparent py-2 text-left text-g-600 hover:text-theme disabled:cursor-not-allowed disabled:opacity-60"
              :aria-label="`打开${quickLink.name}`"
              :disabled="navigating"
              @click="handleQuickLinkClick(quickLink)"
            >
              {{ quickLink.name }}
            </button>
          </li>
        </ul>
      </div>
    </div>
  </ElPopover>
</template>

<script setup lang="ts">
  import { ElMessage } from 'element-plus'
  import { isNavigationFailure, NavigationFailureType } from 'vue-router'
  import { useFastEnter } from '@/hooks/core/useFastEnter'
  import type { FastEnterApplication, FastEnterQuickLink } from '@/types/config'

  defineOptions({ name: 'ArtFastEnter' })

  const router = useRouter()
  const popoverRef = ref()
  const navigating = ref(false)

  // 使用快速入口配置
  const { enabledApplications, enabledQuickLinks } = useFastEnter()

  /**
   * 处理导航跳转
   * @param routeName 路由名称
   * @param link 外部链接
   */
  const showUnavailable = (): void => {
    ElMessage.warning('该功能暂不可用，请从左侧菜单选择可用功能')
  }

  const handleNavigate = async (routeName?: string, link?: string): Promise<void> => {
    if (navigating.value) return
    navigating.value = true

    try {
      if (routeName) {
        if (!router.hasRoute(routeName)) {
          showUnavailable()
          return
        }
        try {
          const failure = await router.push({ name: routeName })
          if (isNavigationFailure(failure, NavigationFailureType.duplicated)) {
            popoverRef.value?.hide()
            return
          }
          if (isNavigationFailure(failure) || router.currentRoute.value.name !== routeName) {
            ElMessage.error('页面未能打开，请检查当前账号权限或稍后重试')
            return
          }
          popoverRef.value?.hide()
        } catch {
          ElMessage.error('页面未能打开，请检查当前账号权限或稍后重试')
        }
        return
      }

      if (link) {
        ElMessage.warning('外部快捷链接未开放，请使用站内导航')
        return
      }

      showUnavailable()
    } finally {
      navigating.value = false
    }
  }

  /**
   * 处理应用项点击
   * @param application 应用配置对象
   */
  const handleApplicationClick = async (application: FastEnterApplication): Promise<void> => {
    await handleNavigate(application.routeName, application.link)
  }

  /**
   * 处理快速链接点击
   * @param quickLink 快速链接配置对象
   */
  const handleQuickLinkClick = async (quickLink: FastEnterQuickLink): Promise<void> => {
    await handleNavigate(quickLink.routeName, quickLink.link)
  }
</script>
