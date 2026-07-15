import assert from 'node:assert/strict'

import {
  buildOpportunityRewritePayload,
  shouldEnableOpportunityRewriteAction,
  getOpportunityItemIdentity,
} from '../src/utils/opportunityPageState.js'

const selectedItem = {
  itemId: '123',
  title: '小米17 全新',
  description: '原文案内容，描述商品成色和配置',
  link: 'https://example.com/item/123',
}

const payload = buildOpportunityRewritePayload({
  selectedItem,
  keyword: '小米17',
  style: 'friendly',
})

assert.equal(payload.item.title, '小米17 全新')
assert.equal(payload.item.description, '原文案内容，描述商品成色和配置')
assert.equal(payload.title, '小米17 全新')
assert.equal(payload.description, '原文案内容，描述商品成色和配置')
assert.equal(payload.keyword, '小米17')
assert.equal(getOpportunityItemIdentity(selectedItem), '123')
assert.equal(shouldEnableOpportunityRewriteAction({ rewriteLoading: false, aiStatusLoading: false }), true)
assert.equal(shouldEnableOpportunityRewriteAction({ rewriteLoading: true, aiStatusLoading: false }), false)
assert.equal(shouldEnableOpportunityRewriteAction({ rewriteLoading: false, aiStatusLoading: true }), false)

const draftPayload = buildOpportunityRewritePayload({
  selectedItem,
  rewriteDraft: { title: '改写后标题', description: '改写后正文' },
  keyword: '小米17',
})

assert.equal(draftPayload.item.title, '改写后标题')
assert.equal(draftPayload.item.description, '改写后正文')

console.log('opportunity-page-state: ok')
