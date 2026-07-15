import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.join(__dirname, '..', 'src', 'pages', 'OpportunityPage.vue')
const source = fs.readFileSync(sourcePath, 'utf8')

for (const expected of [
  'function resetOpportunityItemState()',
  'function activateSelectedItem(item)',
  'rewriteDraft.value = null',
  'rewriteLoading.value = false',
  'generatedImages.value = []',
  'configCoverImage.value = []',
  'function removeGeneratedImage(idx)',
  'configCoverImage.value = configCoverImage.value.filter(url => url !== removedUrl)',
  '@click.stop="removeGeneratedImage(idx)"',
  ':disabled="!shouldEnableOpportunityRewriteAction({ rewriteLoading, aiStatusLoading })"',
  'buildOpportunityRewritePayload({',
  'getOpportunityItemIdentity(selectedItem.value)',
  'activateSelectedItem(items.value[0])',
  'activateSelectedItem(storeItems[0])'
]) {
  assert(source.includes(expected), `OpportunityPage should include: ${expected}`)
}

assert(!source.includes('(!aiStatus.rewriteEnabled && !aiStatusLoadError)'), 'rewrite button should no longer be blocked by a stale enabled flag')

console.log('opportunity-page-contract: ok')
