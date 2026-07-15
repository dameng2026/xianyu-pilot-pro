<!-- 一个让 SVG 图片跟随主题的组件，只对特定 svg 图片生效，不建议开发者使用 -->
<!-- 图片地址 https://iconpark.oceanengine.com/illustrations/13 -->
<template>
  <div class="theme-svg" :style="sizeStyle">
    <div v-if="src" class="svg-container" v-html="svgContent"></div>
  </div>
</template>

<script setup lang="ts">
  import { ref, computed, watch } from 'vue'
  import {
    isTrustedSvgSource,
    MAX_SVG_BYTES,
    sanitizeSvg,
    svgByteLength
  } from '@/utils/sanitizeSvg'

  interface Props {
    size?: string | number
    themeColor?: string
    src?: string
  }

  const props = withDefaults(defineProps<Props>(), {
    size: 500,
    themeColor: 'var(--el-color-primary)'
  })

  const svgContent = ref('')

  // 计算样式
  const sizeStyle = computed(() => {
    const sizeValue = typeof props.size === 'number' ? `${props.size}px` : props.size
    return {
      width: sizeValue,
      height: sizeValue
    }
  })

  // 颜色映射配置
  const COLOR_MAPPINGS = {
    '#C7DEFF': 'var(--el-color-primary-light-6)',
    '#071F4D': 'var(--el-color-primary-dark-2)',
    '#00E4E5': 'var(--el-color-primary-light-1)',
    '#fff': 'var(--default-box-color)',
    '#ffffff': 'var(--default-box-color)',
    '#DEEBFC': 'var(--el-color-primary-light-7)'
  } as const

  // 将主题色应用到 SVG 内容
  const applyThemeToSvg = (content: string, themeColor: string): string => {
    const mappings = { ...COLOR_MAPPINGS, '#006EFF': themeColor }
    return Object.entries(mappings).reduce(
      (processedContent, [originalColor, themeColor]) => {
        const fillRegex = new RegExp(`fill="${originalColor}"`, 'gi')
        const strokeRegex = new RegExp(`stroke="${originalColor}"`, 'gi')

        return processedContent
          .replace(fillRegex, `fill="${themeColor}"`)
          .replace(strokeRegex, `stroke="${themeColor}"`)
      },
      content
    )
  }

  const readBoundedSvg = async (response: Response): Promise<string> => {
    const declaredLength = Number(response.headers.get('content-length'))
    if (Number.isFinite(declaredLength) && declaredLength > MAX_SVG_BYTES) {
      throw new Error('SVG asset exceeds the configured size limit')
    }

    const reader = response.body?.getReader()
    if (!reader) {
      const content = await response.text()
      if (svgByteLength(content) > MAX_SVG_BYTES) {
        throw new Error('SVG asset exceeds the configured size limit')
      }
      return content
    }

    const chunks: Uint8Array[] = []
    let receivedBytes = 0
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      receivedBytes += value.byteLength
      if (receivedBytes > MAX_SVG_BYTES) {
        await reader.cancel()
        throw new Error('SVG asset exceeds the configured size limit')
      }
      chunks.push(value)
    }

    const bytes = new Uint8Array(receivedBytes)
    let offset = 0
    for (const chunk of chunks) {
      bytes.set(chunk, offset)
      offset += chunk.byteLength
    }
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  }

  // 加载 SVG 文件内容
  const loadSvgContent = async (source: string, themeColor: string, signal: AbortSignal) => {
    try {
      if (!isTrustedSvgSource(source)) {
        throw new Error('SVG source is not a trusted local asset')
      }
      const response = await fetch(source, {
        credentials: 'same-origin',
        redirect: 'error',
        signal
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const contentType = response.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase()
      if (contentType && contentType !== 'image/svg+xml') {
        throw new Error('SVG asset returned an unexpected content type')
      }

      const content = await readBoundedSvg(response)
      const sanitized = sanitizeSvg(applyThemeToSvg(content, themeColor))
      if (!sanitized) {
        throw new Error('SVG asset failed sanitization')
      }
      if (signal.aborted) return
      svgContent.value = sanitized
    } catch (error) {
      if (signal.aborted || (error instanceof Error && error.name === 'AbortError')) return
      console.error('Failed to load SVG:', error)
      svgContent.value = ''
    }
  }

  watch(
    () => [props.src, props.themeColor] as const,
    ([source, themeColor], _previous, onCleanup) => {
      const controller = new AbortController()
      onCleanup(() => controller.abort())

      // Never display an asset for the previous src while its replacement loads.
      svgContent.value = ''
      if (!source) return
      void loadSvgContent(source, themeColor, controller.signal)
    },
    { immediate: true }
  )
</script>

<style lang="scss" scoped>
  .theme-svg {
    display: inline-block;

    .svg-container {
      width: 100%;
      height: 100%;

      :deep(svg) {
        width: 100%;
        height: 100%;
      }
    }
  }
</style>
