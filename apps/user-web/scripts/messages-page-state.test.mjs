import assert from 'node:assert/strict'

import {
  applyConversationUnreadState,
  compareConversationStatus,
  confirmTemplateDeletion,
  didPreservedConversationIdentityChange,
  extractImageMessageUrls,
  extractMessageDisplayText,
  formatDisplayDateTime,
  findConversationMatchIndex,
  findConversationByIdentity,
  findPreservedConversation,
  filterRecentConversationSnapshots,
  formatConversationReadCountText,
  getConversationRecordId,
  getConversationIdentityKey,
  getConversationDurationMs,
  isConversationDeleted,
  isConversationMissingError,
  isRealtimeConversationEvent,
  isRealtimeConversationSignalStale,
  isSameConversationByPayload,
  matchesAccountSelection,
  mergeConversationSnapshots,
  mergeConversationDisplaySnapshot,
  markImageRetryBatchFailure,
  mergeSelectedConversationSnapshot,
  parseImageUrlBatchInput,
  parseMessageTimestamp,
  pruneDeletedConversationMarks,
  resolveRetryMessageAction,
  resolveImageBatchPreviewState,
  resolveAccountSwitchState,
  resolveConversationGoodsTitle,
  resolveConversationGoodsCover,
  shouldApplyContextLoadResult,
  shouldApplyConversationLoadResult,
  shouldEnableMainComposerSend,
  shouldMarkConversationAsRead,
  shouldRunMessagePolling,
  sortConversationSnapshots,
  sortMessagesByTime
} from '../src/utils/messagesPageState.js'

async function run(name, fn) {
  try {
    await fn()
    console.log(`ok - ${name}`)
  } catch (error) {
    console.error(`not ok - ${name}`)
    throw error
  }
}

const duplicatePeerConversations = [
  { sid: '63247704189', peerUserId: '3672669710@goofish', name: 'Conversation A' },
  { sid: '63154569163', peerUserId: '3672669710@goofish', name: 'Conversation B' }
]

const duplicatePeerAcrossAccounts = [
  { sid: '63247704189', peerUserId: '3672669710@goofish', xianyuAccountId: 1, id: 101, name: 'Account 1 Conversation' },
  { sid: '63247704189', peerUserId: '3672669710@goofish', xianyuAccountId: 2, id: 202, name: 'Account 2 Conversation' }
]

await run('does not treat different sid conversations from the same buyer as the current chat', async () => {
  const currentConversation = duplicatePeerConversations[0]
  const payload = {
    sid: '63154569163',
    peerUserId: '3672669710@goofish'
  }

  assert.equal(isSameConversationByPayload(currentConversation, payload), false)
})

await run('still falls back to peer matching when sid is absent', async () => {
  const currentConversation = { sid: '', peerUserId: '3672669710@goofish' }
  const payload = { peerUserId: '3672669710@goofish' }

  assert.equal(isSameConversationByPayload(currentConversation, payload), true)
})

await run('does not treat same sid from different accounts as the same conversation', async () => {
  const currentConversation = duplicatePeerAcrossAccounts[0]
  const payload = {
    sid: '63247704189',
    peerUserId: '3672669710@goofish',
    xianyuAccountId: 2
  }

  assert.equal(isSameConversationByPayload(currentConversation, payload), false)
})

await run('prefers exact sid matches over earlier peer duplicates when updating conversation previews', async () => {
  const index = findConversationMatchIndex(duplicatePeerConversations, {
    sid: '63154569163',
    peerUserId: '3672669710@goofish'
  })

  assert.equal(index, 1)
})

await run('keeps account isolation when matching same sid duplicates', async () => {
  const index = findConversationMatchIndex(duplicatePeerAcrossAccounts, {
    sid: '63247704189',
    peerUserId: '3672669710@goofish',
    xianyuAccountId: 2
  })

  assert.equal(index, 1)
})

await run('preserves the currently selected sid instead of drifting to the first peer match', async () => {
  const selected = { sid: '63154569163', peerUserId: '3672669710@goofish' }
  const matched = findPreservedConversation(duplicatePeerConversations, selected)

  assert.equal(matched?.sid, '63154569163')
})

await run('preserves the currently selected account when peer and sid both overlap', async () => {
  const selected = { sid: '63247704189', peerUserId: '3672669710@goofish', xianyuAccountId: 2 }
  const matched = findPreservedConversation(duplicatePeerAcrossAccounts, selected)

  assert.equal(matched?.id, 202)
})

await run('treats changed preserved-conversation identity as a real selection switch', async () => {
  assert.equal(
    didPreservedConversationIdentityChange(
      { sid: 'sid-a', xianyuAccountId: 1 },
      { sid: 'sid-b', xianyuAccountId: 1 }
    ),
    true
  )
  assert.equal(
    didPreservedConversationIdentityChange(
      { sid: 'sid-a', xianyuAccountId: 1 },
      { sid: 'sid-a', xianyuAccountId: 1, msg: 'new preview' }
    ),
    false
  )
})

await run('does not delete a template when the confirmation is rejected', async () => {
  let deleteCalled = false
  const deleted = await confirmTemplateDeletion(
    async () => false,
    async () => {
      deleteCalled = true
    },
    12
  )

  assert.equal(deleted, false)
  assert.equal(deleteCalled, false)
})

await run('deletes a template only after confirmation resolves truthy', async () => {
  const deletedIds = []
  const deleted = await confirmTemplateDeletion(
    async () => true,
    async id => {
      deletedIds.push(id)
    },
    34
  )

  assert.equal(deleted, true)
  assert.deepEqual(deletedIds, [34])
})

await run('extracts numeric conversation record ids only', async () => {
  assert.equal(getConversationRecordId({ id: 33 }), 33)
  assert.equal(getConversationRecordId({ rawId: '44' }), 44)
  assert.equal(getConversationRecordId({ conversationDbId: 'abc' }), null)
  assert.equal(getConversationRecordId({ sid: '63247704189' }), null)
})

await run('builds conversation identity keys with account isolation', async () => {
  assert.equal(
    getConversationIdentityKey({ sid: '63247704189', xianyuAccountId: 1 }),
    'account:1|sid:63247704189'
  )
  assert.equal(
    getConversationIdentityKey({ sid: '63247704189', xianyuAccountId: 2 }),
    'account:2|sid:63247704189'
  )
})

await run('keeps same sid conversations from different accounts after aggregation', async () => {
  const merged = mergeConversationSnapshots([
    { sid: '63247704189', xianyuAccountId: 1, lastMessageTime: 100, name: 'Account 1' },
    { sid: '63247704189', xianyuAccountId: 2, lastMessageTime: 300, name: 'Account 2' }
  ])

  assert.equal(merged.length, 2)
  assert.deepEqual(merged.map(item => item.name), ['Account 2', 'Account 1'])
})

await run('deduplicates same-account conversation snapshots and keeps the newest one first', async () => {
  const merged = mergeConversationSnapshots([
    { sid: 'sid-a', xianyuAccountId: 1, lastMessageTime: 100, name: 'Older' },
    { sid: 'sid-b', xianyuAccountId: 1, lastMessageTime: 200, name: 'Middle' },
    { sid: 'sid-a', xianyuAccountId: 1, lastMessageTime: 300, name: 'Newest Replacement' }
  ])

  assert.equal(merged.length, 2)
  assert.deepEqual(merged.map(item => item.name), ['Newest Replacement', 'Middle'])
})

await run('preserves enriched avatar and goods fields when realtime snapshots are sparse', async () => {
  const merged = mergeConversationDisplaySnapshot(
    {
      sid: 'sid-a',
      xianyuAccountId: 1,
      name: 'Alice',
      avatarUrl: 'https://example.com/avatar.png',
      goodsCoverPic: 'https://example.com/goods.png',
      goodsTitle: 'Vintage Camera',
      product: 'Vintage Camera',
      xyGoodsId: '9988'
    },
    {
      sid: 'sid-a',
      xianyuAccountId: 1,
      lastMessage: 'new message',
      goodsCoverPic: '',
      goodsTitle: '',
      product: '',
      xyGoodsId: ''
    }
  )

  assert.equal(merged?.avatarUrl, 'https://example.com/avatar.png')
  assert.equal(merged?.goodsCoverPic, 'https://example.com/goods.png')
  assert.equal(merged?.goodsTitle, 'Vintage Camera')
  assert.equal(merged?.product, 'Vintage Camera')
  assert.equal(merged?.xyGoodsId, '9988')
})

await run('treats all-account selection as matching every incoming account', async () => {
  assert.equal(matchesAccountSelection('', { xianyuAccountId: 1 }), true)
  assert.equal(matchesAccountSelection(null, { xianyuAccountId: 2 }), true)
})

await run('filters incoming events when a specific account is selected', async () => {
  assert.equal(matchesAccountSelection('1', { xianyuAccountId: 1 }), true)
  assert.equal(matchesAccountSelection('1', { xianyuAccountId: 2 }), false)
  assert.equal(matchesAccountSelection('1', { xianyuAccountId: 0 }), false)
})

await run('accepts accountId as a fallback when xianyuAccountId is absent', async () => {
  assert.equal(matchesAccountSelection('2', { accountId: 2 }), true)
  assert.equal(matchesAccountSelection('2', { accountId: 3 }), false)
})

await run('ignores realtime payloads without an account id once a concrete account is selected', async () => {
  assert.equal(matchesAccountSelection('3', {}), false)
  assert.equal(matchesAccountSelection('3', { sid: '63247704189' }), false)
})

await run('only treats message-like SSE payloads as realtime conversation updates', async () => {
  assert.equal(isRealtimeConversationEvent('heartbeat', {}), false)
  assert.equal(isRealtimeConversationEvent('cookie_status_changed', { accountId: 1, cookieStatus: 0 }), false)
  assert.equal(isRealtimeConversationEvent('message', { sid: '63247704189' }), true)
  assert.equal(isRealtimeConversationEvent('conversation_updated', { content: '你好' }), true)
})

await run('marks realtime conversation signals stale once message activity times out', async () => {
  assert.equal(isRealtimeConversationSignalStale(0, 20_000, 15_000), true)
  assert.equal(isRealtimeConversationSignalStale(1_000, 20_000, 15_000), true)
  assert.equal(isRealtimeConversationSignalStale(10_000, 20_000, 15_000), false)
})

await run('only runs message fallback polling for a selected account on a visible page', async () => {
  assert.equal(shouldRunMessagePolling({ accountId: 1, documentHidden: false }), true)
  assert.equal(shouldRunMessagePolling({ accountId: 1, documentHidden: true }), false)
  assert.equal(shouldRunMessagePolling({ accountId: '', documentHidden: false }), false)
})

await run('extracts image urls directly from stored image message content', async () => {
  assert.deepEqual(
    extractImageMessageUrls({
      contentType: 2,
      msgContent: 'https://img.alicdn.com/imgextra/demo-a.png'
    }),
    ['https://img.alicdn.com/imgextra/demo-a.png']
  )
})

await run('extracts image urls from serialized legacy image payloads', async () => {
  assert.deepEqual(
    extractImageMessageUrls({
      contentType: 2,
      msgContent: JSON.stringify({
        image: {
          pics: [
            { picUrl: '//img.alicdn.com/imgextra/demo-b.png' }
          ]
        }
      })
    }),
    ['https://img.alicdn.com/imgextra/demo-b.png']
  )
})

await run('extracts image urls from complete message payload snapshots', async () => {
  assert.deepEqual(
    extractImageMessageUrls({
      contentType: 2,
      msgContent: '[图片]',
      completeMsg: JSON.stringify({
        image: {
          pics: [
            { picUrl: '//img.alicdn.com/imgextra/demo-c.png' }
          ]
        }
      })
    }),
    ['https://img.alicdn.com/imgextra/demo-c.png']
  )
})

await run('does not treat plain text cloud-drive links as chat images', async () => {
  assert.deepEqual(
    extractImageMessageUrls({
      contentType: 1,
      msgContent: '通过网盘分享的文件：https://pan.baidu.com/s/1EJlF15-OOdHOU3wca-lVYg?pwd=a003'
    }),
    []
  )
})

await run('prefers explicit goods titles instead of drifting to last-message text', async () => {
  assert.equal(
    resolveConversationGoodsTitle({
      goodsTitle: '',
      product: '',
      reminderContent: '这是一条聊天内容',
      lastMessageContent: '买家刚发来的消息',
      xyGoodsId: '123456'
    }),
    '未关联商品'
  )
  assert.equal(
    resolveConversationGoodsTitle({
      goodsTitle: 'Python 数据采集脚本',
      reminderContent: '这是一条聊天内容',
      lastMessageContent: '买家刚发来的消息',
      xyGoodsId: '123456'
    }),
    'Python 数据采集脚本'
  )
})

await run('extracts goods cover images from nested complete message payload snapshots', async () => {
  assert.equal(
    resolveConversationGoodsCover({
      completeMsg: JSON.stringify({
        rawPayload: {
          sessionInfo: {
            extensions: {
              itemMainPic: '//img.alicdn.com/imgextra/demo-cover.heic'
            }
          }
        }
      })
    }),
    'https://img.alicdn.com/imgextra/demo-cover.heic'
  )
})

await run('still keeps raw image urls for real image messages without file extensions', async () => {
  assert.deepEqual(
    extractImageMessageUrls({
      contentType: 2,
      msgContent: 'https://example.com/media/render?id=42'
    }),
    ['https://example.com/media/render?id=42']
  )
})

await run('ignores stale conversation load results after account changes', async () => {
  assert.equal(shouldApplyConversationLoadResult({
    requestId: 1,
    latestRequestId: 1,
    requestedAccountId: 2,
    currentAccountId: 2
  }), true)
  assert.equal(shouldApplyConversationLoadResult({
    requestId: 1,
    latestRequestId: 2,
    requestedAccountId: 2,
    currentAccountId: 2
  }), false)
  assert.equal(shouldApplyConversationLoadResult({
    requestId: 1,
    latestRequestId: 1,
    requestedAccountId: 2,
    currentAccountId: 3
  }), false)
})

await run('ignores stale context load results after conversation selection changes', async () => {
  assert.equal(shouldApplyContextLoadResult({
    requestId: 1,
    latestRequestId: 1,
    requestedAccountId: 2,
    currentAccountId: 2,
    requestedConversation: { sid: 'sid-a', xianyuAccountId: 2 },
    currentConversation: { sid: 'sid-a', xianyuAccountId: 2 }
  }), true)
  assert.equal(shouldApplyContextLoadResult({
    requestId: 1,
    latestRequestId: 2,
    requestedAccountId: 2,
    currentAccountId: 2,
    requestedConversation: { sid: 'sid-a', xianyuAccountId: 2 },
    currentConversation: { sid: 'sid-a', xianyuAccountId: 2 }
  }), false)
  assert.equal(shouldApplyContextLoadResult({
    requestId: 1,
    latestRequestId: 1,
    requestedAccountId: 2,
    currentAccountId: 2,
    requestedConversation: { sid: 'sid-a', xianyuAccountId: 2 },
    currentConversation: { sid: 'sid-b', xianyuAccountId: 2 }
  }), false)
})

await run('falls back to peer identity when sid is missing and keeps account isolation', async () => {
  assert.equal(
    getConversationIdentityKey({ peerUserId: '3672669710@goofish', xianyuAccountId: 1 }),
    'account:1|peer:3672669710'
  )
  assert.equal(
    getConversationIdentityKey({ peerUserId: '3672669710@goofish', xianyuAccountId: 2 }),
    'account:2|peer:3672669710'
  )
})

await run('parses string-based message timestamps for consistent ordering', async () => {
  assert.equal(parseMessageTimestamp('2026-06-28 16:13:52'), Date.parse('2026-06-28T16:13:52'))
  assert.equal(parseMessageTimestamp('2026-06-28T16:13:52'), Date.parse('2026-06-28T16:13:52'))
  assert.equal(parseMessageTimestamp(1719562432), 1719562432000)
})

await run('formats timestamps as full date and time strings', async () => {
  assert.equal(formatDisplayDateTime('2026-06-28 16:13:52'), '2026-06-28 16:13:52')
  assert.equal(formatDisplayDateTime('2026-06-28 16:13:52', { withSeconds: false }), '2026-06-28 16:13')
})

await run('sorts conversation snapshots by parsed message time instead of raw number coercion', async () => {
  const sorted = sortConversationSnapshots([
    { sid: 'older', lastMessageTime: '2026-06-28 16:13:52' },
    { sid: 'newer', lastMessageTime: '2026-06-28 16:15:39' }
  ])

  assert.deepEqual(sorted.map(item => item.sid), ['newer', 'older'])
})

await run('sorts context messages chronologically when messageTime is a datetime string', async () => {
  const sorted = sortMessagesByTime([
    { id: 'reply', messageTime: '2026-06-28 16:15:39' },
    { id: 'ask', messageTime: '2026-06-28 16:13:52' },
    { id: 'followup', messageTime: '2026-06-28 16:14:29' }
  ])

  assert.deepEqual(sorted.map(item => item.id), ['ask', 'followup', 'reply'])
})

await run('keeps same-second messages in stable id order to avoid chat jitter', async () => {
  const sorted = sortMessagesByTime([
    { id: '12', messageTime: '2026-06-28 16:15:39' },
    { id: '3', messageTime: '2026-06-28 16:15:39' },
    { id: '20', messageTime: '2026-06-28 16:15:39' }
  ])

  assert.deepEqual(sorted.map(item => item.id), ['3', '12', '20'])
})

await run('matches deleted conversations by identity key and legacy sid fallback', async () => {
  const conversation = { sid: '63247704189', xianyuAccountId: 2 }

  assert.equal(isConversationDeleted(new Set(['account:2|sid:63247704189']), conversation), true)
  assert.equal(isConversationDeleted(new Set(['63247704189']), conversation), true)
  assert.equal(isConversationDeleted(new Set(['account:1|sid:63247704189']), conversation), false)
})

await run('finds previous conversations with account isolation instead of first sid match', async () => {
  const found = findConversationByIdentity(duplicatePeerAcrossAccounts, {
    sid: '63247704189',
    xianyuAccountId: 2
  })

  assert.equal(found?.id, 202)
})

await run('detects deleted-conversation send errors in english and chinese', async () => {
  assert.equal(isConversationMissingError('conversation not exist'), true)
  assert.equal(isConversationMissingError('该会话已删除，无法继续发送'), true)
  assert.equal(isConversationMissingError('会话不存在，请刷新后重试'), true)
  assert.equal(isConversationMissingError('网络错误'), false)
})

await run('normalizes transferred conversation statuses from readable chinese labels', async () => {
  assert.equal(compareConversationStatus(0, '已转接'), 'transferred')
  assert.equal(compareConversationStatus(1, '已完成'), 'completed')
  assert.equal(compareConversationStatus(2, '已关闭'), 'closed')
})

await run('computes conversation duration using parsed timestamps', async () => {
  const duration = getConversationDurationMs([
    { id: 'reply', messageTime: '2026-06-28 16:15:39' },
    { id: 'ask', messageTime: '2026-06-28 16:13:52' }
  ])

  assert.equal(duration, 107000)
})

await run('keeps recent conversations when lastMessageTime is a datetime string', async () => {
  const now = Date.parse('2026-06-28T18:00:00')
  const filtered = filterRecentConversationSnapshots([
    { sid: 'fresh', lastMessageTime: '2026-06-28 16:15:39' },
    { sid: 'stale', lastMessageTime: '2026-06-10 16:15:39' }
  ], { now })

  assert.deepEqual(filtered.map(item => item.sid), ['fresh'])
})

await run('preserves legacy deleted sid markers during deleted-conversation checks', async () => {
  const deletedSet = new Set(['63247704189'])
  const conversation = { sid: '63247704189', xianyuAccountId: 1 }

  assert.equal(isConversationDeleted(deletedSet, conversation), true)
})

await run('formats conversation read count text consistently from unread counts', async () => {
  assert.equal(formatConversationReadCountText(0), '-')
  assert.equal(formatConversationReadCountText(1), '1 次')
  assert.equal(formatConversationReadCountText(3), '3 次')
})

await run('marks a conversation as read only when unread messages exist', async () => {
  assert.equal(shouldMarkConversationAsRead({ unreadCount: 0 }), false)
  assert.equal(shouldMarkConversationAsRead({ unreadCount: 2 }), true)
  assert.equal(shouldMarkConversationAsRead({ unreadCount: '5' }), true)
})

await run('retries text messages through the text send path', async () => {
  assert.deepEqual(
    resolveRetryMessageAction({ contentType: 1, msgContent: '你好' }),
    { kind: 'text', text: '你好' }
  )
})

await run('extracts readable text from non-image extended message payloads', async () => {
  assert.equal(
    extractMessageDisplayText({
      contentType: 8,
      msgContent: '',
      message: '自动发货的呢？',
      content: ''
    }),
    '自动发货的呢？'
  )
  assert.deepEqual(
    resolveRetryMessageAction({
      contentType: 8,
      msgContent: '',
      message: '自动发货的呢？'
    }),
    { kind: 'text', text: '自动发货的呢？' }
  )
})

await run('retries image messages through the image send path when an image url exists', async () => {
  assert.deepEqual(
    resolveRetryMessageAction({ contentType: 2, imageUrls: ['https://img.example.com/demo.png'], msgContent: '[图片]' }),
    { kind: 'image', imageUrl: 'https://img.example.com/demo.png' }
  )
  assert.deepEqual(
    resolveRetryMessageAction({ contentType: 2, msgContent: 'https://img.example.com/demo.png' }),
    { kind: 'image', imageUrl: 'https://img.example.com/demo.png' }
  )
})

await run('does not mis-send placeholder image messages as plain text on retry', async () => {
  assert.deepEqual(
    resolveRetryMessageAction({ contentType: 2, msgContent: '[图片]', displayText: '[图片]' }),
    { kind: 'unsupported', reason: 'image' }
  )
})

await run('applies unread state consistently to count, read text, and badge text', async () => {
  assert.deepEqual(
    applyConversationUnreadState({ unreadCount: 3, statusCode: 0, statusText: '' }, 0),
    { unreadCount: 0, statusCode: 0, statusText: '', readCountText: '-', badgeText: '会话' }
  )
  assert.deepEqual(
    applyConversationUnreadState({ unreadCount: 0, statusCode: 1, statusText: '已完成' }, 2),
    { unreadCount: 2, statusCode: 1, statusText: '已完成', readCountText: '2 次', badgeText: '新消息' }
  )
})

await run('prunes stale deleted conversation markers once the conversation is back in the list', async () => {
  const activeConversation = { sid: '63247704189', xianyuAccountId: 2 }
  const next = pruneDeletedConversationMarks(
    new Set(['account:2|sid:63247704189', '63247704189', 'account:9|sid:other']),
    [activeConversation]
  )

  assert.deepEqual(Array.from(next).sort(), ['account:9|sid:other'])
})

await run('parses multiple image urls from comma and newline separated input', async () => {
  assert.deepEqual(
    parseImageUrlBatchInput('https://a.test/1.png, https://a.test/2.png\nhttps://a.test/3.png，https://a.test/4.png'),
    [
      'https://a.test/1.png',
      'https://a.test/2.png',
      'https://a.test/3.png',
      'https://a.test/4.png'
    ]
  )
})

await run('main send button only enables for text draft, not image-url-only composer state', async () => {
  assert.equal(shouldEnableMainComposerSend({
    accountId: 1,
    conversationSid: 'sid-1',
    isSystemConversation: false,
    sending: false,
    isDeletedConversation: false,
    draftText: '   '
  }), false)
  assert.equal(shouldEnableMainComposerSend({
    accountId: 1,
    conversationSid: 'sid-1',
    isSystemConversation: false,
    sending: false,
    isDeletedConversation: false,
    draftText: '你好'
  }), true)
})

await run('keeps image batch preview as image when at least one image send has succeeded', async () => {
  const preview = resolveImageBatchPreviewState([
    { id: 'a', sendStatus: 'sent' },
    { id: 'b', sendStatus: 'failed' }
  ], { msg: '旧预览' })

  assert.deepEqual(preview, { shouldRestorePrevious: false, nextPreviewText: '[图片]' })
})

await run('restores previous preview only when every image in the batch failed', async () => {
  const preview = resolveImageBatchPreviewState([
    { id: 'a', sendStatus: 'failed' },
    { id: 'b', sendStatus: 'failed' }
  ], { msg: '旧预览' })

  assert.deepEqual(preview, { shouldRestorePrevious: true, nextPreviewText: '旧预览' })
})

await run('marks only pending image batch items as failed after a partial batch error', async () => {
  const next = markImageRetryBatchFailure([
    { id: 'a', sendStatus: 'sent' },
    { id: 'b', sendStatus: 'sending' },
    { id: 'c', sendStatus: 'failed' }
  ], new Set(['a', 'b', 'c']))

  assert.deepEqual(next, [
    { id: 'a', sendStatus: 'sent' },
    { id: 'b', sendStatus: 'failed' },
    { id: 'c', sendStatus: 'failed' }
  ])
})

await run('clears stale selection, context and deleted marks when switching accounts', async () => {
  const next = resolveAccountSwitchState({
    selectedAccountId: 2,
    previousSelectedConversation: { sid: 'sid-1', xianyuAccountId: 1 },
    deletedConversations: new Set(['account:1|sid:sid-1']),
    contextMessages: [{ id: 'm1' }],
    error: '旧错误'
  })

  assert.deepEqual(next, {
    selected: null,
    contextMessages: [],
    hasMoreContext: false,
    deletedConversations: new Set(),
    error: ''
  })
})

await run('keeps account-local state when account switch does not actually change the active account', async () => {
  const previousSelectedConversation = { sid: 'sid-2', xianyuAccountId: 2 }
  const deletedConversations = new Set(['account:2|sid:sid-2'])
  const contextMessages = [{ id: 'm2' }]
  const next = resolveAccountSwitchState({
    selectedAccountId: 2,
    previousSelectedConversation,
    deletedConversations,
    contextMessages,
    error: '保留'
  })

  assert.equal(next.selected, previousSelectedConversation)
  assert.equal(next.contextMessages, contextMessages)
  assert.equal(next.deletedConversations, deletedConversations)
  assert.equal(next.error, '保留')
})

await run('merges selected conversation snapshot while preserving active-read state consistently', async () => {
  const merged = mergeSelectedConversationSnapshot(
    {
      sid: 'sid-1',
      xianyuAccountId: 1,
      unreadCount: 0,
      statusCode: 0,
      statusText: '',
      badgeText: '会话',
      readCountText: '-'
    },
    {
      sid: 'sid-1',
      xianyuAccountId: 1,
      unreadCount: 5,
      statusCode: 1,
      statusText: '已完成',
      badgeText: '新消息',
      readCountText: '5 次',
      msg: '新预览'
    },
    { preserveUnreadAsRead: true }
  )

  assert.deepEqual(merged, {
    sid: 'sid-1',
    xianyuAccountId: 1,
    unreadCount: 0,
    statusCode: 1,
    statusText: '已完成',
    badgeText: '已完成',
    readCountText: '-',
    msg: '新预览'
  })
})

console.log('messages-page-state: ok')
