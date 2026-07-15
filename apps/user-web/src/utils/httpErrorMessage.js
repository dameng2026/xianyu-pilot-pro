const TECHNICAL_MESSAGE = /(?:exception|traceback|stack\s*trace|sqlstate|jdbc|pymysql|asyncpg|java\.|org\.[a-z]|request failed|failed to fetch|bad gateway|gateway timeout)/i

function structuredUserMessage(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return ''
  const candidate = typeof body.msg === 'string'
    ? body.msg.trim()
    : typeof body.message === 'string'
      ? body.message.trim()
      : ''
  if (!candidate || candidate.length > 300) return ''
  if (!/[\u3400-\u9fff]/.test(candidate) || TECHNICAL_MESSAGE.test(candidate)) return ''
  return candidate
}

/**
 * Convert an HTTP transport failure into a stable, user-facing Chinese message.
 * Only an explicitly structured, non-technical Chinese server message is trusted.
 */
export function httpErrorMessage(status, body) {
  const serverMessage = structuredUserMessage(body)
  if (serverMessage) return serverMessage

  if (status === 401) return '登录状态无效，请重新登录'
  if (status === 403) return '暂无权限执行此操作'
  if (status === 404) return '请求的服务或资源不存在'
  if (status === 408) return '请求超时，请稍后重试'
  if (status === 413) return '提交内容过大，请缩小后重试'
  if (status === 429) return '操作过于频繁，请稍后再试'
  if (Number(status) >= 500) return '服务暂时不可用，请稍后重试'
  if (Number(status) >= 400) return '请求未成功，请检查输入后重试'
  return '网络请求失败，请稍后重试'
}
