/**
 * 移动端全局 Toast 状态管理
 *
 * 用法：
 *   import { toast } from '@/mobile/toast.js'
 *   toast.success('保存成功')
 *   toast.error('操作失败')
 *
 * 在 MobileLite.vue 中挂载 <MToast /> 组件即可渲染。
 */
import { reactive } from 'vue'

let _id = 0

const toasts = reactive([])

function add(type, message, duration = 3000) {
  const id = ++_id
  toasts.push({ id, type, message })
  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }
  return id
}

function remove(id) {
  const idx = toasts.findIndex(t => t.id === id)
  if (idx > -1) toasts.splice(idx, 1)
}

export const toast = {
  success(message, duration) { return add('success', message, duration) },
  error(message, duration) { return add('error', message, duration ?? 4000) },
  warning(message, duration) { return add('warning', message, duration) },
  info(message, duration) { return add('info', message, duration) },
  remove
}

export { toasts, remove }
