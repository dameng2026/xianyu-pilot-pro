function normalizeText(value, fallback = '') {
  const text = String(value ?? '').trim()
  return text || fallback
}

export function getOpportunityItemIdentity(item) {
  if (!item) return ''
  return normalizeText(item.itemId || item.link || item.title || item.name || '')
}

export function shouldEnableOpportunityRewriteAction({ rewriteLoading = false, aiStatusLoading = false } = {}) {
  return !rewriteLoading && !aiStatusLoading
}

export function buildOpportunityRewritePayload({
  selectedItem,
  selectedOpportunity,
  rewriteDraft,
  keyword,
  style,
  customPrompt,
} = {}) {
  const sourceItem = selectedOpportunity || selectedItem || {}
  const sourceTitle = normalizeText(rewriteDraft?.title || sourceItem.title || sourceItem.name || '')
  const sourceDescription = normalizeText(
    rewriteDraft?.description || sourceItem.description || sourceItem.desc || sourceItem.content || sourceTitle
  )

  return {
    keyword: normalizeText(keyword, ''),
    item: {
      ...sourceItem,
      title: sourceTitle,
      description: sourceDescription,
    },
    title: sourceTitle,
    description: sourceDescription,
    style: normalizeText(style, 'friendly'),
    customPrompt: normalizeText(customPrompt, '') || undefined,
  }
}
