<!-- 按钮组件 -->
<template>
  <button
    type="button"
    class="size-8.5 inline-flex flex-cc c-p border-0 bg-transparent p-0 text-g-600 dark:text-g-800 text-xl rounded tad-300 hover:bg-hover-color disabled:cursor-not-allowed disabled:opacity-50"
    :class="{ 'rounded-full': circle }"
    :aria-label="label"
    :title="title || label"
    :disabled="disabled"
  >
    <span class="inline-flex" aria-hidden="true"><ArtSvgIcon :icon="icon" /></span>
    <slot></slot>
  </button>
</template>

<script lang="ts" setup>
  defineOptions({ name: 'ArtIconButton' })

  interface Props {
    /** 图标名称 */
    icon: string
    /** 按钮的可访问名称 */
    label: string
    /** 鼠标悬停提示，默认复用可访问名称 */
    title?: string
    /** 圆角按钮 */
    circle?: boolean
    /** 是否禁用 */
    disabled?: boolean
  }

  withDefaults(defineProps<Props>(), {})
</script>
