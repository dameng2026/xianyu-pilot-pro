import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const componentPath = path.join(root, 'src', 'components', 'PaymentModal.vue')
const assetDir = path.join(root, 'public', 'xya', 'payment-modal')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const component = fs.readFileSync(componentPath, 'utf8')
const requiredAssets = [
  'hero-shield.png',
  'wechat-pay.svg',
  'plan-blue.svg',
  'plan-purple.svg',
  'plan-orange.svg',
  'amount-bill.svg',
  'check-blue.svg',
  'shield-mini.svg'
]

assert(fs.existsSync(assetDir), 'payment modal asset dir should exist')
for (const asset of requiredAssets) {
  assert(fs.existsSync(path.join(assetDir, asset)), `payment modal asset should exist: ${asset}`)
}
assert(component.includes('/xya/payment-modal/hero-shield.png'), 'PaymentModal should reference the token modal hero illustration')
assert(component.includes('/xya/payment-modal/plan-blue.svg'), 'PaymentModal should reference the blue token plan icon')
assert(component.includes('/xya/payment-modal/plan-purple.svg'), 'PaymentModal should reference the purple token plan icon')
assert(component.includes('/xya/payment-modal/plan-orange.svg'), 'PaymentModal should reference the orange token plan icon')
assert(component.includes('/xya/payment-modal/wechat-pay.svg'), 'PaymentModal should reference the payment method icon')
assert(component.includes('token-modal-card'), 'PaymentModal should expose the token modal card container class')
assert(component.includes('method-option-card'), 'PaymentModal should expose the payment method card class')
assert(component.includes('token-plan-card'), 'PaymentModal should expose the token plan card class')
assert(component.includes('confirm-pay-btn'), 'PaymentModal should expose the confirm pay button class')
assert(component.includes('扫码充值 Token'), 'PaymentModal should render the token recharge heading')

console.log('payment-modal-contract: ok')
