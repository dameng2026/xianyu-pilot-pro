import { ref } from 'vue'

import { getAuthCapabilities } from '../api/auth.js'
import {
  createFailClosedAuthCapabilities,
  parseAuthCapabilities,
} from './authCapabilities.js'

const SAFE_LOAD_ERROR = '认证能力状态无法确认，相关入口已安全关闭。请联系管理员或部署方。'

export function useAuthCapabilities(loader = getAuthCapabilities) {
  const authCapabilities = ref(createFailClosedAuthCapabilities())
  const authCapabilityLoading = ref(true)
  const authCapabilityError = ref('')

  async function refreshAuthCapabilities() {
    authCapabilityLoading.value = true
    authCapabilityError.value = ''
    authCapabilities.value = createFailClosedAuthCapabilities()
    try {
      const response = await loader()
      authCapabilities.value = parseAuthCapabilities(response?.data)
      return true
    } catch {
      authCapabilityError.value = SAFE_LOAD_ERROR
      authCapabilities.value = createFailClosedAuthCapabilities(SAFE_LOAD_ERROR)
      return false
    } finally {
      authCapabilityLoading.value = false
    }
  }

  return {
    authCapabilities,
    authCapabilityLoading,
    authCapabilityError,
    refreshAuthCapabilities,
  }
}
