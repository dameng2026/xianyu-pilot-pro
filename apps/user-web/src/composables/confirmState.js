import { reactive } from 'vue'

// 全局确认弹窗状态
const state = reactive({
  visible: false,
  type: 'confirm',   // 'confirm' | 'alert' | 'prompt'
  title: '确认操作',
  description: '',
  confirmText: '',
  placeholder: '',
  dangerous: false,
  value: ''
})

const requestQueue = []
let activeRequest = null

function activateNextRequest() {
  if (activeRequest || requestQueue.length === 0) {
    if (!activeRequest) state.visible = false
    return
  }

  activeRequest = requestQueue.shift()
  Object.assign(state, activeRequest.options, { visible: true })
}

export function useConfirmState() {
  function show({
    type = 'confirm',
    title = '确认操作',
    description = '',
    confirmText = '',
    placeholder = '',
    dangerous = false,
    value = ''
  } = {}) {
    return new Promise((resolve) => {
      requestQueue.push({
        options: { type, title, description, confirmText, placeholder, dangerous, value },
        resolve
      })
      activateNextRequest()
    })
  }

  function confirm(title, description = '', confirmText = '', dangerous = false) {
    return show({ type: 'confirm', title, description, confirmText, dangerous })
  }

  function alert(title, description = '') {
    return show({ type: 'alert', title, description })
  }

  function prompt(title, placeholder = '', value = '') {
    return show({ type: 'prompt', title, placeholder, value })
  }

  function resolve(result) {
    const completed = activeRequest
    if (!completed) return

    activeRequest = null
    state.visible = false
    completed.resolve(result)

    // Let Vue remove the completed dialog before presenting the next request.
    // This also guarantees that concurrent callers keep FIFO order instead of
    // overwriting one another's unresolved Promise.
    if (requestQueue.length > 0) queueMicrotask(activateNextRequest)
  }

  function cancel() {
    resolve(false)
  }

  function confirm_() {
    if (state.type === 'prompt') {
      resolve(state.value)
    } else {
      resolve(true)
    }
  }

  return { state, show, confirm, alert, prompt, resolve, cancel, doConfirm: confirm_ }
}

// 全局单例，供非 composable 环境（如 confirmAction.js）使用
export const globalConfirm = useConfirmState()
