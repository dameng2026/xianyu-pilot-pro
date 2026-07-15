import assert from 'node:assert/strict'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

const accountsPage = fs.readFileSync(path.join(root, 'src', 'pages', 'AccountsPage.vue'), 'utf8')
const connectionsPage = fs.readFileSync(path.join(root, 'src', 'pages', 'ConnectionsPage.vue'), 'utf8')
const messagesPage = fs.readFileSync(path.join(root, 'src', 'pages', 'MessagesPage.vue'), 'utf8')

assert(accountsPage.includes('refreshAccountAuthBeforeConnect'), 'AccountsPage should revalidate unified login status before starting websocket')
assert(connectionsPage.includes('refreshRowLoginStateBeforeConnect'), 'ConnectionsPage should revalidate login status before retrying websocket start')
assert(messagesPage.includes('refreshCurrentAccountLoginState'), 'MessagesPage manual connect flow should revalidate login status before forcing websocket reconnect')

console.log('connect-flow-contract: ok')
