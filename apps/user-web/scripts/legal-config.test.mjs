import assert from 'node:assert/strict'

import { resolveLegalConfig } from '../src/utils/legalConfig.js'

assert.deepEqual(resolveLegalConfig({}), {
  termsUrl: '',
  privacyUrl: '',
  icpLicense: '',
})

assert.deepEqual(
  resolveLegalConfig({
    VITE_TERMS_URL: ' /legal/terms ',
    VITE_PRIVACY_URL: 'https://example.com/privacy',
    VITE_ICP_LICENSE: ' 京ICP备00000000号 ',
  }),
  {
    termsUrl: '/legal/terms',
    privacyUrl: 'https://example.com/privacy',
    icpLicense: '京ICP备00000000号',
  },
)

const unsafe = resolveLegalConfig({
  VITE_TERMS_URL: 'javascript:alert(1)',
  VITE_PRIVACY_URL: 'data:text/html,not-a-policy',
})
assert.equal(unsafe.termsUrl, '')
assert.equal(unsafe.privacyUrl, '')

console.log('legal-config: ok')
