import { getBusinessSettings } from '../api/businessSettings.js'
import { warmAccountsList } from '../api/accounts.js'

let warmPromise = null

export function warmUserFoundationData({ force = false } = {}) {
  if (warmPromise) return warmPromise

  warmPromise = Promise.allSettled([
    warmAccountsList({ force }),
    getBusinessSettings('ai-customer-service', { force }),
  ]).finally(() => {
    warmPromise = null
  })

  return warmPromise
}
