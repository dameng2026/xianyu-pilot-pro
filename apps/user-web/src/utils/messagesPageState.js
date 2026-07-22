function normalizeSid(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const withoutPrefix = raw.startsWith('sid:') ? raw.slice(4) : raw
  return withoutPrefix.endsWith('@goofish') ? withoutPrefix.slice(0, -8) : withoutPrefix
}

function normalizePeerUserId(value) {
  const raw = String(value || '').trim()
  if (!raw || raw.startsWith('sid:')) return ''
  return raw.endsWith('@goofish') ? raw.slice(0, -8) : raw
}

function getConversationSid(conv) {
  return normalizeSid(conv?.sid || conv?.sId || conv?.sessionId || conv?.conversationId || '')
}

function getConversationPeer(conv) {
  return normalizePeerUserId(
    conv?.peerUserId ||
    conv?.peerExternalUid ||
    conv?.externalBuyerId ||
    conv?.receiverUserId ||
    ''
  )
}

function getConversationAccount(conv) {
  const raw = conv?.xianyuAccountId ?? conv?.accountId ?? conv?.raw?.xianyuAccountId ?? conv?.raw?.accountId
  const accountId = Number(raw)
  return Number.isFinite(accountId) && accountId > 0 ? String(accountId) : ''
}

function getPayloadSid(payload) {
  return normalizeSid(payload?.sId || payload?.sid || payload?.cid || payload?.sessionId || '')
}

function getPayloadPeer(payload) {
  return normalizePeerUserId(
    payload?.peerUserId ||
    payload?.peerExternalUid ||
    payload?.senderUserId ||
    payload?.receiverUserId ||
    ''
  )
}

function getPayloadAccount(payload) {
  const raw = payload?.xianyuAccountId ?? payload?.accountId
  const accountId = Number(raw)
  return Number.isFinite(accountId) && accountId > 0 ? String(accountId) : ''
}

function isSameAccountIfKnown(left, right) {
  return !(left && right) || left === right
}

export function parseMessageTimestamp(raw) {
  if (raw === null || raw === undefined || raw === '') return 0
  const numeric = Number(raw)
  if (Number.isFinite(numeric) && numeric > 0) {
    return numeric < 1e10 ? numeric * 1000 : numeric
  }
  if (typeof raw === 'string') {
    const normalized = raw.includes(' ') && raw.includes('-') ? raw.replace(' ', 'T') : raw
    const parsed = Date.parse(normalized)
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  return 0
}

function pad2(value) {
  return String(value).padStart(2, '0')
}

export function formatDisplayDateTime(raw, { withSeconds = true } = {}) {
  const timestamp = parseMessageTimestamp(raw)
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  const year = date.getFullYear()
  const month = pad2(date.getMonth() + 1)
  const day = pad2(date.getDate())
  const hour = pad2(date.getHours())
  const minute = pad2(date.getMinutes())
  const second = pad2(date.getSeconds())
  return withSeconds
    ? `${year}-${month}-${day} ${hour}:${minute}:${second}`
    : `${year}-${month}-${day} ${hour}:${minute}`
}

function getConversationSortTime(conv) {
  const raw = conv?.lastMessageTime ?? conv?.updatedAt ?? conv?.messageTime ?? conv?.createdAt ?? 0
  return parseMessageTimestamp(raw)
}

export function sortConversationSnapshots(list, { descending = true } = {}) {
  return [...(Array.isArray(list) ? list : [])].sort((left, right) => {
    const leftTime = getConversationSortTime(left)
    const rightTime = getConversationSortTime(right)
    return descending ? rightTime - leftTime : leftTime - rightTime
  })
}

export function filterRecentConversationSnapshots(list, { now = Date.now(), maxAgeMs = 7 * 24 * 60 * 60 * 1000 } = {}) {
  return (Array.isArray(list) ? list : []).filter(item => {
    const time = getConversationSortTime(item)
    return Boolean(time) && now - time <= maxAgeMs
  })
}

export function sortMessagesByTime(list) {
  const getStableMessageId = message => {
    const candidate = String(
      message?.pnmId ??
      message?.messageUid ??
      message?.messageId ??
      message?.id ??
      ''
    ).trim()
    return candidate
  }
  return [...(Array.isArray(list) ? list : [])]
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const leftTime = parseMessageTimestamp(left.item?.messageTime ?? left.item?.createdTime ?? left.item?.sendTime ?? left.item?.time ?? 0)
      const rightTime = parseMessageTimestamp(right.item?.messageTime ?? right.item?.createdTime ?? right.item?.sendTime ?? right.item?.time ?? 0)
      if (leftTime !== rightTime) return leftTime - rightTime
      const leftId = getStableMessageId(left.item)
      const rightId = getStableMessageId(right.item)
      if (leftId && rightId && leftId !== rightId) {
        const leftNumeric = /^\d+$/.test(leftId) ? Number(leftId) : Number.NaN
        const rightNumeric = /^\d+$/.test(rightId) ? Number(rightId) : Number.NaN
        if (Number.isFinite(leftNumeric) && Number.isFinite(rightNumeric) && leftNumeric !== rightNumeric) {
          return leftNumeric - rightNumeric
        }
        return leftId.localeCompare(rightId)
      }
      return left.index - right.index
    })
    .map(entry => entry.item)
}

function collectMessageTextCandidates(message) {
  const rawCandidates = [
    message?.displayText,
    message?.msgContent,
    message?.content,
    message?.message,
    message?.text,
    message?.lastMessage,
    message?.lastMessageContent,
    message?.reminderContent,
    message?.title,
    message?.subtitle,
    message?.desc,
    message?.description,
    message?.cardTitle,
    message?.cardSubtitle,
    message?.media?.text,
    message?.media?.title,
    message?.media?.subtitle,
    message?.ext?.text,
    message?.ext?.title,
    message?.ext?.content
  ]
  const results = []
  for (const candidate of rawCandidates) {
    const value = typeof candidate === 'string' ? candidate.trim() : ''
    if (value && !results.includes(value)) {
      results.push(value)
    }
  }
  return results
}

export function resolveConversationGoodsTitle(message, fallback = '未关联商品') {
  const goodsIdCandidates = [
    message?.xyGoodsId,
    message?.goodsId,
    message?.itemId,
    message?.raw?.xyGoodsId,
    message?.raw?.goodsId,
    message?.raw?.itemId
  ]
    .map(value => String(value || '').trim())
    .filter(Boolean)

  const titleCandidates = [
    message?.goodsTitle,
    message?.product,
    message?.itemTitle,
    message?.cardTitle,
    message?.raw?.goodsTitle,
    message?.raw?.product,
    message?.raw?.itemTitle,
    message?.raw?.cardTitle,
    message?.sessionInfo?.extensions?.itemTitle,
    message?.rawPayload?.sessionInfo?.extensions?.itemTitle
  ]

  for (const candidate of titleCandidates) {
    const value = typeof candidate === 'string' ? candidate.trim() : ''
    if (!value) continue
    if (goodsIdCandidates.includes(value)) continue
    if (value === '[图片]') continue
    return value
  }
  return fallback
}

function parseStructuredPayload(value) {
  if (!value) return null
  if (typeof value === 'object') return value
  if (typeof value !== 'string') return null
  const text = value.trim()
  if (!text || (!text.startsWith('{') && !text.startsWith('['))) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export function resolveConversationGoodsId(message, fallback = '') {
  const candidates = [
    message?.xyGoodsId,
    message?.goodsId,
    message?.itemId,
    message?.raw?.xyGoodsId,
    message?.raw?.goodsId,
    message?.raw?.itemId,
    message?.sessionInfo?.extensions?.itemId,
    message?.rawPayload?.sessionInfo?.extensions?.itemId,
  ]
  const parsedPayloads = [
    parseStructuredPayload(message?.completeMsg),
    parseStructuredPayload(message?.complete_msg),
  ].filter(Boolean)
  parsedPayloads.forEach(payload => {
    candidates.push(payload?.sessionInfo?.extensions?.itemId)
    candidates.push(payload?.rawPayload?.sessionInfo?.extensions?.itemId)
  })
  for (const candidate of candidates) {
    const value = String(candidate || '').trim()
    if (value) return value
  }
  return String(fallback || '').trim()
}

function normalizeDisplayImageUrl(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (/^data:image\//i.test(text)) return text
  if (text.startsWith('//')) return `https:${text}`
  if (text.startsWith('http://') || text.startsWith('https://')) return text
  if (text.startsWith('/uploads/')) return text
  if (text.startsWith('/')) return `https://img.alicdn.com${text}`
  return text
}

function isLikelyImageUrl(value) {
  const normalized = normalizeDisplayImageUrl(value)
  if (!normalized) return false
  if (/^data:image\//i.test(normalized)) return true
  if (normalized.startsWith('/uploads/')) return true
  const withoutQuery = normalized.split('#', 1)[0].split('?', 1)[0].toLowerCase()
  return /\.(apng|avif|bmp|gif|heic|heif|jpe?g|png|svg|webp)$/i.test(withoutQuery)
}

function pushNormalizedImage(results, candidate, { allowGenericUrl = false } = {}) {
  const normalized = normalizeDisplayImageUrl(candidate)
  if (normalized && (allowGenericUrl || isLikelyImageUrl(normalized)) && !results.includes(normalized)) {
    results.push(normalized)
  }
}

function extractImageUrlsFromStructuredValue(value, results, { allowGenericStringUrl = false } = {}) {
  if (!value) return
  if (Array.isArray(value)) {
    value.forEach(item => extractImageUrlsFromStructuredValue(item, results, { allowGenericStringUrl }))
    return
  }
  if (typeof value === 'object') {
    extractImageUrlsFromStructuredValue(value.imageUrls, results, { allowGenericStringUrl: true })
    extractImageUrlsFromStructuredValue(value.images, results, { allowGenericStringUrl: true })
    extractImageUrlsFromStructuredValue(value.pics, results, { allowGenericStringUrl: true })
    extractImageUrlsFromStructuredValue(value.image, results, { allowGenericStringUrl: true })
    pushNormalizedImage(results, value.imageUrl, { allowGenericUrl: true })
    pushNormalizedImage(results, value.url)
    pushNormalizedImage(results, value.picUrl, { allowGenericUrl: true })
    pushNormalizedImage(results, value.fileUrl)
    pushNormalizedImage(results, value.downloadUrl)
    return
  }
  if (typeof value !== 'string') return
  const text = value.trim()
  if (!text || text === '[图片]') return
  if ((text.startsWith('{') || text.startsWith('[')) && text.length > 1) {
    try {
      extractImageUrlsFromStructuredValue(JSON.parse(text), results, { allowGenericStringUrl: true })
      if (results.length) return
    } catch {
      // Fall through to URL heuristics.
    }
  }
  if (/^(data:image\/|https?:\/\/|\/\/|\/uploads\/)/i.test(text)) {
    pushNormalizedImage(results, text, { allowGenericUrl: allowGenericStringUrl })
    return
  }
  const matches = text.match(/https?:\/\/[^\s"'<>]+|\/\/[^\s"'<>]+/gi) || []
  matches.forEach(match => pushNormalizedImage(results, match))
}

export function extractImageMessageUrls(message) {
  const results = []
  const contentType = Number(message?.contentType ?? message?.messageType ?? message?.lastContentType ?? 1)
  const isImageMessage = contentType === 2
  extractImageUrlsFromStructuredValue(message?.imageUrls, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.images, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.image, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.media, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.msgContent, results, { allowGenericStringUrl: isImageMessage })
  extractImageUrlsFromStructuredValue(message?.content, results, { allowGenericStringUrl: isImageMessage })
  extractImageUrlsFromStructuredValue(message?.message, results, { allowGenericStringUrl: isImageMessage })
  extractImageUrlsFromStructuredValue(message?.text, results, { allowGenericStringUrl: isImageMessage })
  extractImageUrlsFromStructuredValue(message?.imageUrl, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.url, results, { allowGenericStringUrl: isImageMessage })
  extractImageUrlsFromStructuredValue(message?.mediaUrl, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.picUrl, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.completeMsg, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.complete_msg, results, { allowGenericStringUrl: true })
  extractImageUrlsFromStructuredValue(message?.raw, results, { allowGenericStringUrl: true })
  return results
}

export function resolveConversationGoodsCover(message, fallback = '') {
  const results = []
  const directCandidates = [
    message?.goodsCoverPic,
    message?.coverPic,
    message?.itemMainPic,
    message?.itemMainPicUrl,
    message?.raw?.goodsCoverPic,
    message?.raw?.coverPic,
    message?.raw?.itemMainPic,
    message?.sessionInfo?.extensions?.itemMainPic,
    message?.rawPayload?.sessionInfo?.extensions?.itemMainPic,
  ]
  directCandidates.forEach(candidate => pushNormalizedImage(results, candidate, { allowGenericUrl: true }))

  const parsedPayloads = [
    parseStructuredPayload(message?.completeMsg),
    parseStructuredPayload(message?.complete_msg),
  ].filter(Boolean)
  parsedPayloads.forEach(payload => {
    pushNormalizedImage(results, payload?.sessionInfo?.extensions?.itemMainPic, { allowGenericUrl: true })
    pushNormalizedImage(results, payload?.rawPayload?.sessionInfo?.extensions?.itemMainPic, { allowGenericUrl: true })
  })

  return results[0] || normalizeDisplayImageUrl(fallback)
}

export function extractMessageDisplayText(message, fallback = '') {
  const contentType = Number(message?.contentType ?? message?.messageType ?? message?.lastContentType ?? 1)
  if (contentType === 2) return '[图片]'
  const [primaryText = ''] = collectMessageTextCandidates(message)
  return primaryText || String(fallback || '').trim()
}

export function isSameConversationByPayload(conv, payload) {
  if (!conv || !payload) return false
  const selectedSid = getConversationSid(conv)
  const payloadSid = getPayloadSid(payload)
  const conversationAccount = getConversationAccount(conv)
  const payloadAccount = getPayloadAccount(payload)
  if (selectedSid && payloadSid) {
    return selectedSid === payloadSid && isSameAccountIfKnown(conversationAccount, payloadAccount)
  }
  const selectedPeer = getConversationPeer(conv)
  const payloadPeer = getPayloadPeer(payload)
  if (!isSameAccountIfKnown(conversationAccount, payloadAccount)) return false
  return Boolean(selectedPeer && payloadPeer && selectedPeer === payloadPeer)
}

export function findConversationMatchIndex(list, payload) {
  const conversations = Array.isArray(list) ? list : []
  const payloadSid = getPayloadSid(payload)
  const payloadAccount = getPayloadAccount(payload)
  if (payloadSid) {
    const sidIndex = conversations.findIndex(item =>
      getConversationSid(item) === payloadSid &&
      isSameAccountIfKnown(getConversationAccount(item), payloadAccount)
    )
    if (sidIndex >= 0) return sidIndex
  }
  const payloadPeer = getPayloadPeer(payload)
  if (payloadPeer) {
    return conversations.findIndex(item =>
      getConversationPeer(item) === payloadPeer &&
      isSameAccountIfKnown(getConversationAccount(item), payloadAccount)
    )
  }
  return -1
}

export function findPreservedConversation(list, currentSelection) {
  const conversations = Array.isArray(list) ? list : []
  if (!currentSelection) return null
  const currentSid = getConversationSid(currentSelection)
  const currentAccount = getConversationAccount(currentSelection)
  if (currentSid) {
    const sidMatch = conversations.find(item =>
      getConversationSid(item) === currentSid &&
      isSameAccountIfKnown(getConversationAccount(item), currentAccount)
    )
    if (sidMatch) return sidMatch
  }
  const currentPeer = getConversationPeer(currentSelection)
  if (currentPeer) {
    return conversations.find(item =>
      getConversationPeer(item) === currentPeer &&
      isSameAccountIfKnown(getConversationAccount(item), currentAccount)
    ) || null
  }
  return null
}

export function findConversationByIdentity(list, targetConversation) {
  const key = getConversationIdentityKey(targetConversation)
  if (!key) return null
  return (Array.isArray(list) ? list : []).find(item => getConversationIdentityKey(item) === key) || null
}

export function didPreservedConversationIdentityChange(previousSelection, nextSelection) {
  return getConversationIdentityKey(previousSelection) !== getConversationIdentityKey(nextSelection)
}

export function getConversationRecordId(conv) {
  // 注意：Python get_online_conversations 返回的会话主键字段名是 conversationId
  // （SQL: MIN(conv.id) AS conversationId），而非 id。此处需同时兼容两种字段名，
  // 否则 markConversationRead(id) 会因 id 为 null 被静默跳过，导致未读状态无法清除。
  const id = conv?.id || conv?.rawId || conv?.conversationDbId || conv?.conversationId
  return Number.isFinite(Number(id)) ? Number(id) : null
}

export function getConversationIdentityKey(conv) {
  if (!conv) return ''
  const account = getConversationAccount(conv)
  const sid = getConversationSid(conv)
  if (sid) return `account:${account || 'unknown'}|sid:${sid}`
  const peer = getConversationPeer(conv)
  if (peer) return `account:${account || 'unknown'}|peer:${peer}`
  const recordId = getConversationRecordId(conv)
  return recordId ? `record:${recordId}` : ''
}

export function isConversationDeleted(deletedSet, conv) {
  if (!(deletedSet instanceof Set) || !conv) return false
  const key = getConversationIdentityKey(conv)
  const sid = getConversationSid(conv)
  return (key && deletedSet.has(key)) || (sid && deletedSet.has(sid))
}

export function mergeConversationSnapshots(list) {
  const merged = new Map()
  for (const item of Array.isArray(list) ? list : []) {
    const key = getConversationIdentityKey(item)
    if (!key) continue
    const previous = merged.get(key)
    if (!previous || getConversationSortTime(item) >= getConversationSortTime(previous)) {
      merged.set(key, item)
    }
  }
  return Array.from(merged.values()).sort((left, right) => getConversationSortTime(right) - getConversationSortTime(left))
}

export function compareConversationStatus(status, statusText) {
  const text = String(statusText || '').toLowerCase()
  if (text.includes('转接') || text.includes('已转接')) return 'transferred'
  if (text.includes('完成') || text.includes('已完成')) return 'completed'
  if (text.includes('关闭') || text.includes('已关闭')) return 'closed'
  const code = Number(status)
  if (code === 1) return 'completed'
  if (code === 2) return 'closed'
  if (code === 3) return 'transferred'
  return 'inProgress'
}

export function isConversationMissingError(message) {
  const text = String(message || '')
  if (!text) return false
  return /conversation not exist|会话已删除|会话不存在|该会话已被删除|会话已过期/i.test(text)
}

export function getConversationDurationMs(messages) {
  const sorted = sortMessagesByTime(messages)
  const first = sorted[0]?.messageTime ?? sorted[0]?.createdTime ?? sorted[0]?.sendTime ?? sorted[0]?.time
  const last = sorted[sorted.length - 1]?.messageTime ?? sorted[sorted.length - 1]?.createdTime ?? sorted[sorted.length - 1]?.sendTime ?? sorted[sorted.length - 1]?.time
  const firstTime = parseMessageTimestamp(first)
  const lastTime = parseMessageTimestamp(last)
  if (!firstTime || !lastTime) return 0
  return Math.max(0, lastTime - firstTime)
}

export function formatConversationReadCountText(unreadCount) {
  const count = Number(unreadCount || 0)
  return count > 0 ? `${Math.max(1, count)} 次` : '-'
}

export function shouldMarkConversationAsRead(conversation) {
  return Number(conversation?.unreadCount || 0) > 0
}

export function applyConversationUnreadState(conversation, unreadCount, fallbackStatusResolver = compareConversationStatus) {
  const count = Number(unreadCount || 0)
  const status = typeof fallbackStatusResolver === 'function'
    ? fallbackStatusResolver(conversation?.statusCode, conversation?.statusText)
    : compareConversationStatus(conversation?.statusCode, conversation?.statusText)
  const badgeText = count > 0
    ? '新消息'
    : status === 'completed'
      ? '已完成'
      : status === 'closed'
        ? '已关闭'
        : status === 'transferred'
          ? '已转接'
          : '会话'
  return {
    ...conversation,
    unreadCount: count,
    readCountText: formatConversationReadCountText(count),
    badgeText
  }
}

export function pruneDeletedConversationMarks(deletedSet, conversations) {
  const next = new Set(deletedSet instanceof Set ? deletedSet : [])
  for (const conversation of Array.isArray(conversations) ? conversations : []) {
    const key = getConversationIdentityKey(conversation)
    const sid = getConversationSid(conversation)
    if (key) next.delete(key)
    if (sid) next.delete(sid)
  }
  return next
}

export function parseImageUrlBatchInput(value) {
  return String(value || '')
    .split(/[\n,，]+/g)
    .map(item => item.trim())
    .filter(Boolean)
}

export function shouldEnableMainComposerSend({
  accountId,
  conversationSid,
  isSystemConversation,
  sending,
  isDeletedConversation,
  draftText
}) {
  if (!Number(accountId || 0)) return false
  if (!conversationSid) return false
  if (isSystemConversation) return false
  if (sending) return false
  if (isDeletedConversation) return false
  return String(draftText || '').trim().length > 0
}

export function resolveImageBatchPreviewState(batchMessages, previousConversation) {
  const messages = Array.isArray(batchMessages) ? batchMessages : []
  const hasSent = messages.some(item => item?.sendStatus === 'sent')
  return hasSent
    ? { shouldRestorePrevious: false, nextPreviewText: '[图片]' }
    : { shouldRestorePrevious: true, nextPreviewText: previousConversation?.msg || '' }
}

export function markImageRetryBatchFailure(messages, batchIds) {
  const ids = batchIds instanceof Set ? batchIds : new Set()
  return (Array.isArray(messages) ? messages : []).map(item => {
    if (!ids.has(item?.id)) return item
    if (item?.sendStatus === 'sent') return item
    return { ...item, sendStatus: 'failed' }
  })
}

export function resolveAccountSwitchState({
  selectedAccountId,
  previousSelectedConversation,
  deletedConversations,
  contextMessages,
  error
}) {
  const nextAccount = Number(selectedAccountId || 0)
  const previousAccount = Number(
    previousSelectedConversation?.xianyuAccountId ??
    previousSelectedConversation?.accountId ??
    previousSelectedConversation?.raw?.xianyuAccountId ??
    previousSelectedConversation?.raw?.accountId ??
    0
  )
  if (!nextAccount || !previousAccount || nextAccount === previousAccount) {
    return {
      selected: previousSelectedConversation ?? null,
      contextMessages: Array.isArray(contextMessages) ? contextMessages : [],
      hasMoreContext: false,
      deletedConversations: deletedConversations instanceof Set ? deletedConversations : new Set(),
      error: error || ''
    }
  }
  return {
    selected: null,
    contextMessages: [],
    hasMoreContext: false,
    deletedConversations: new Set(),
    error: ''
  }
}

export function mergeConversationDisplaySnapshot(previousConversation, nextConversation) {
  if (!previousConversation) return nextConversation || null
  if (!nextConversation) return previousConversation
  const merged = { ...previousConversation, ...nextConversation }
  // 保留本地实时未读数：服务器轮询返回的 unreadCount 往往滞后于 WS 实时事件，
  // 若让服务端值覆盖本地值，会导致红色未读徽标在“显示/隐藏”之间反复闪烁。
  // 本地 unreadCount 由 WS 事件累加、由用户操作（标记已读/发送消息）重置，更具实时性。
  if (typeof previousConversation.unreadCount === 'number') {
    merged.unreadCount = previousConversation.unreadCount
  }
  if (!merged.avatarUrl && previousConversation.avatarUrl) {
    merged.avatarUrl = previousConversation.avatarUrl
  }
  if (!merged.buyerAvatar && previousConversation.buyerAvatar) {
    merged.buyerAvatar = previousConversation.buyerAvatar
  }
  const prevName = previousConversation.name
  if (prevName && (!merged.name || /^\d+$/.test(merged.name)) && !/^\d+$/.test(prevName)) {
    merged.name = prevName
  }
  if (!merged.product && previousConversation.product) {
    merged.product = previousConversation.product
  }
  if (!merged.goodsTitle && previousConversation.goodsTitle) {
    merged.goodsTitle = previousConversation.goodsTitle
  }
  if (!merged.goodsCoverPic && previousConversation.goodsCoverPic) {
    merged.goodsCoverPic = previousConversation.goodsCoverPic
  }
  if (!merged.xyGoodsId && previousConversation.xyGoodsId) {
    merged.xyGoodsId = previousConversation.xyGoodsId
  }
  if (!merged.goodsId && previousConversation.goodsId) {
    merged.goodsId = previousConversation.goodsId
  }
  return merged
}

export function mergeSelectedConversationSnapshot(previousSelectedConversation, nextConversation, { preserveUnreadAsRead = false } = {}) {
  if (!previousSelectedConversation) return nextConversation || null
  if (!nextConversation) return previousSelectedConversation
  const merged = mergeConversationDisplaySnapshot(previousSelectedConversation, nextConversation)
  // 保留已有关键展示字段：服务器刷新的快照若缺失头像/昵称，不应覆盖前端已补全的值
  // （fetchMissingAvatars 已补全的 avatarUrl/name 在 loadConversations(true) 轮询时会丢失）
  if (!merged.avatarUrl && previousSelectedConversation.avatarUrl) {
    merged.avatarUrl = previousSelectedConversation.avatarUrl
  }
  if (!merged.buyerAvatar && previousSelectedConversation.buyerAvatar) {
    merged.buyerAvatar = previousSelectedConversation.buyerAvatar
  }
  const prevName = previousSelectedConversation.name
  if (prevName && (!merged.name || /^\d+$/.test(merged.name)) && !/^\d+$/.test(prevName)) {
    merged.name = prevName
  }
  if (!preserveUnreadAsRead) return merged
  return applyConversationUnreadState(
    { ...merged, statusCode: nextConversation.statusCode, statusText: nextConversation.statusText },
    0
  )
}

export function shouldApplyConversationLoadResult({
  requestId,
  latestRequestId,
  requestedAccountId,
  currentAccountId
}) {
  return requestId === latestRequestId && Number(requestedAccountId || 0) === Number(currentAccountId || 0)
}

export function shouldApplyContextLoadResult({
  requestId,
  latestRequestId,
  requestedAccountId,
  currentAccountId,
  requestedConversation,
  currentConversation
}) {
  return shouldApplyConversationLoadResult({
    requestId,
    latestRequestId,
    requestedAccountId,
    currentAccountId
  }) && !didPreservedConversationIdentityChange(requestedConversation, currentConversation)
}

export function resolveRetryMessageAction(message) {
  const contentType = Number(message?.contentType ?? message?.messageType ?? 1)
  const imageUrls = extractImageMessageUrls(message)
  if (contentType === 2) {
    const imageUrl = imageUrls[0] || ''
    return imageUrl
      ? { kind: 'image', imageUrl }
      : { kind: 'unsupported', reason: 'image' }
  }
  const rawText = extractMessageDisplayText(message)
  return rawText
    ? { kind: 'text', text: rawText }
    : { kind: 'unsupported', reason: 'empty' }
}

export function matchesAccountSelection(selectedAccountId, payload) {
  const selected = Number(selectedAccountId || 0)
  if (!selected) return true
  const payloadAccount = Number(payload?.xianyuAccountId ?? payload?.accountId ?? 0)
  return payloadAccount > 0 && payloadAccount === selected
}

export function isRealtimeConversationEvent(eventType, payload) {
  const data = payload && typeof payload === 'object' ? payload : {}
  const sid = normalizeSid(data?.sId || data?.sid || data?.cid || data?.sessionId || '')
  return eventType === 'message' || Boolean(data?.message || data?.content || data?.msgContent || sid)
}

export function isRealtimeConversationSignalStale(lastActivityAt, now = Date.now(), staleTimeout = 15000) {
  const last = Number(lastActivityAt || 0)
  return !last || now - last > staleTimeout
}

export function shouldRunMessagePolling({ accountId, documentHidden = false } = {}) {
  return !documentHidden && String(accountId ?? '').trim() !== ''
}

export async function confirmTemplateDeletion(confirm, remove, id) {
  if (typeof confirm !== 'function') return false
  const confirmed = await confirm()
  if (!confirmed) return false
  await remove(id)
  return true
}
