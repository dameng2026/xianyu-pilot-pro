import request from '../utils/request'
import { pageParams } from '../utils/apiData.js'
import { invalidateRequestCache, withRequestCache } from '../utils/requestCache.js'

const ACCOUNT_CACHE_NAMESPACE = 'api:xianyu/accounts'
const ACCOUNT_LITE_CACHE_NAMESPACE = 'api:xianyu/accounts/lite'
const SHARED_FIRST_PAGE_SIZE = 100

function recordsOf(data) {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object') {
    for (const key of ['records', 'accounts', 'list', 'rows']) {
      if (Array.isArray(data[key])) return data[key]
    }
  }
  throw new Error('账号列表响应格式异常')
}

function totalOf(data, fallback) {
  const total = Array.isArray(data)
    ? fallback
    : Number(data?.total ?? data?.totalCount ?? data?.count ?? fallback)
  if (!Number.isFinite(total) || total < 0 || total < fallback) {
    throw new Error('账号列表总数响应格式异常')
  }
  return total
}

function buildPagedResponse(result, records, total) {
  if (Array.isArray(result?.data)) {
    return {
      ...result,
      data: records,
    }
  }

  const data = result?.data && typeof result.data === 'object'
    ? { ...result.data }
    : {}

  let assigned = false
  for (const key of ['records', 'accounts', 'list', 'rows']) {
    if (Array.isArray(data[key])) {
      data[key] = records
      assigned = true
    }
  }
  if (!assigned) {
    data.records = records
  }
  if ('total' in data || (!('totalCount' in data) && !('count' in data))) data.total = total
  if ('totalCount' in data) data.totalCount = total
  if ('count' in data) data.count = total

  return {
    ...result,
    data,
  }
}

function fetchAccountPage(params, { force = false, cacheTtlMs = 60000 } = {}) {
  return withRequestCache({
    keyParts: [ACCOUNT_CACHE_NAMESPACE, params],
    ttlMs: cacheTtlMs,
    force,
    request: () => request({ url: '/xianyu/accounts', method: 'get', params }),
  })
}

function fetchLiteAccountPage(params, { force = false, cacheTtlMs = 60000 } = {}) {
  return withRequestCache({
    keyParts: [ACCOUNT_LITE_CACHE_NAMESPACE, params],
    ttlMs: cacheTtlMs,
    force,
    request: () => request({ url: '/xianyu/accounts/lite', method: 'get', params }),
  })
}

function canUseSharedFirstPage(params) {
  const current = Number(params?.current ?? 1)
  const size = Number(params?.size ?? 20)
  return current === 1 && size > 0 && size <= SHARED_FIRST_PAGE_SIZE && !params?.keyword && params?.status == null
}

function invalidateAccountCache() {
  invalidateRequestCache(ACCOUNT_CACHE_NAMESPACE)
  invalidateRequestCache(ACCOUNT_LITE_CACHE_NAMESPACE)
}

export function getAccounts(params = {}, options = {}) {
  const normalizedParams = pageParams(params)
  const force = options.force === true
  const cacheTtlMs = force ? 0 : (options.cacheTtlMs ?? 15000)

  if (!canUseSharedFirstPage(normalizedParams)) {
    return fetchAccountPage(normalizedParams, { force, cacheTtlMs })
  }

  const requestedSize = Number(normalizedParams.size ?? 20)
  return fetchAccountPage(
    {
      ...normalizedParams,
      current: 1,
      size: SHARED_FIRST_PAGE_SIZE,
    },
    { force, cacheTtlMs }
  ).then(result => {
    const allRecords = recordsOf(result?.data)
    const total = totalOf(result?.data, allRecords.length)
    return buildPagedResponse(result, allRecords.slice(0, requestedSize), total)
  })
}

export function warmAccountsList(options = {}) {
  return getAccounts({ current: 1, size: SHARED_FIRST_PAGE_SIZE }, options)
}

export function getLiteAccounts(params = {}, options = {}) {
  const normalizedParams = pageParams(params)
  const force = options.force === true
  const cacheTtlMs = force ? 0 : (options.cacheTtlMs ?? 15000)

  if (!canUseSharedFirstPage(normalizedParams)) {
    return fetchLiteAccountPage(normalizedParams, { force, cacheTtlMs })
  }

  const requestedSize = Number(normalizedParams.size ?? 20)
  return fetchLiteAccountPage(
    {
      ...normalizedParams,
      current: 1,
      size: SHARED_FIRST_PAGE_SIZE,
    },
    { force, cacheTtlMs }
  ).then(result => {
    const allRecords = recordsOf(result?.data)
    const total = totalOf(result?.data, allRecords.length)
    return buildPagedResponse(result, allRecords.slice(0, requestedSize), total)
  })
}

export function warmLiteAccountsList(options = {}) {
  return getLiteAccounts({ current: 1, size: SHARED_FIRST_PAGE_SIZE }, options)
}

export function createAccount(data) {
  return request({ url: '/xianyu/accounts', method: 'post', data }).then(result => {
    invalidateAccountCache()
    return result
  })
}

export function createAccountByCookie(data) {
  return request({ url: '/xianyu/accounts/manual-cookie', method: 'post', data }).then(result => {
    invalidateAccountCache()
    return result
  })
}

export function getAccountDetail(id, params) {
  return request({ url: `/xianyu/accounts/${id}`, method: 'get', params })
}

export function updateAccount(id, data) {
  return request({ url: `/xianyu/accounts/${id}`, method: 'put', data }).then(result => {
    invalidateAccountCache()
    return result
  })
}

export function updateAccountCookie(accountId, cookie, extracted) {
  return request({
    url: `/xianyu/accounts/${accountId}/cookie`,
    method: 'post',
    data: {
      cookie,
      extractedUnb: extracted?.unb || null,
      extractedMH5Tk: extracted?.mH5Tk || null,
    },
  }).then(result => {
    invalidateAccountCache()
    return result
  })
}

export function deleteAccount(id) {
  return request({ url: `/xianyu/accounts/${id}`, method: 'delete' }).then(result => {
    invalidateAccountCache()
    return result
  })
}

export function getAccountSummary(params) {
  return request({ url: '/xianyu/accounts/summary', method: 'get', params })
}

export function refreshAccountProfile(id) {
  return request({ url: `/xianyu/accounts/${id}/refresh-profile`, method: 'post' }).then(result => {
    invalidateAccountCache()
    return result
  })
}

export function checkAccountAuth(id) {
  return request({ url: `/xianyu/accounts/${id}/check-auth`, method: 'post' })
}

export function getAccountAutoRateConfig(id) {
  return request({ url: `/xianyu/accounts/${id}/auto-rate`, method: 'get' })
}

export function saveAccountAutoRateConfig(id, data) {
  return request({ url: `/xianyu/accounts/${id}/auto-rate`, method: 'put', data })
}

export function getAccountStrategyConfig(id) {
  return request({ url: `/xianyu/accounts/${id}/strategy-config`, method: 'get' })
}

export function saveAccountStrategyConfig(id, data) {
  return request({ url: `/xianyu/accounts/${id}/strategy-config`, method: 'put', data })
}

export function getAccountLoginCredential(id) {
  return request({ url: `/xianyu/accounts/${id}/login-credential`, method: 'get' })
}

export function saveAccountLoginCredential(id, data) {
  return request({ url: `/xianyu/accounts/${id}/login-credential`, method: 'put', data })
}

export function getAccountFaceVerifications(params = {}) {
  return request({ url: '/xianyu/accounts/face-verifications', method: 'get', params: pageParams(params) })
}

export function markAccountFaceVerificationRead(id) {
  return request({ url: `/xianyu/accounts/face-verifications/${id}/read`, method: 'post' })
}

export function runItemPolish(accountId) {
  return request({
    url: '/item/polish',
    method: 'post',
    data: { xianyuAccountId: accountId },
    timeout: 10000,
  })
}

export function getItemPolishProgress(taskId) {
  return request({
    url: `/item/polishProgress/${taskId}`,
    method: 'get',
  })
}
