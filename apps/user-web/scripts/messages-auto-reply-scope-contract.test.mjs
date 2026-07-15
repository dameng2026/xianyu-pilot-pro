import assert from 'node:assert/strict'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const messagesPage = fs.readFileSync(path.join(root, 'src', 'pages', 'MessagesPage.vue'), 'utf8')
const autoReplyScopeApi = fs.readFileSync(path.join(root, 'src', 'api', 'autoReplyScope.js'), 'utf8')

assert(!messagesPage.includes('未找到当前商品的本地记录'), 'MessagesPage should not hard fail when the local goods record is missing')
assert(messagesPage.includes('updateProductAutoReplyScope({'), 'MessagesPage should send a structured product scope payload')
assert(messagesPage.includes('goodsId,'), 'MessagesPage should include the current goodsId when toggling auto reply')
assert(messagesPage.includes('accountId: Number(query.xianyuAccountId)'), 'MessagesPage should include the current accountId when toggling auto reply')
assert(autoReplyScopeApi.includes("typeof itemIdOrPayload === 'object'"), 'autoReplyScope API should support structured product scope payloads')

console.log('messages-auto-reply-scope-contract: ok')
