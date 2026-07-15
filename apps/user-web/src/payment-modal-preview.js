import { createApp, h, ref } from 'vue'
import PaymentModal from './components/PaymentModal.vue'

const previewMethods = [
  { channelType: 'wechat', providerType: 'official', configName: '微信支付', sandbox: 0 }
]

const previewTokenPlans = [
  { id: 1, planName: '10 Token', tokenAmount: 10, bonusToken: 0, priceYuan: 1, priceCent: 100 },
  { id: 2, planName: '1000 Token', tokenAmount: 1000, bonusToken: 0, priceYuan: 10, priceCent: 1000 },
  { id: 3, planName: '10000 Token', tokenAmount: 10000, bonusToken: 0, priceYuan: 100, priceCent: 10000 }
]

function createLine(className = '') {
  return h('span', { class: `line ${className}`.trim() })
}

createApp({
  setup() {
    const visible = ref(true)

    return () => h('div', { class: 'preview-scene' }, [
      h('div', { class: 'preview-shell' }, [
        h('aside', { class: 'preview-sidebar' }, [
          h('div', { class: 'preview-brand' }, [
            h('div', { class: 'preview-brand-mark' }),
            h('span', null, 'Northbusiness')
          ]),
          h('div', { class: 'preview-nav' }, [
            createLine('wide'),
            createLine(),
            createLine('active'),
            createLine(),
            createLine(),
            createLine()
          ]),
          h('div', { class: 'preview-avatar' })
        ]),
        h('main', { class: 'preview-main' }, [
          h('header', { class: 'preview-topbar' }, [
            h('div', { class: 'preview-topbar-title' }, [
              h('span', { class: 'crumb' }),
              h('span', { class: 'pill' })
            ]),
            h('div', { class: 'preview-topbar-actions' }, [
              h('span', { class: 'mini' }),
              h('span', { class: 'primary-btn' }),
              h('span', { class: 'mini' }),
              h('span', { class: 'avatar-mini' })
            ])
          ]),
          h('section', { class: 'preview-hero' }, [
            h('div', { class: 'preview-hero-card large' }),
            h('div', { class: 'preview-hero-card side' })
          ]),
          h('section', { class: 'preview-grid' }, [
            h('div', { class: 'preview-card stat' }),
            h('div', { class: 'preview-card stat' }),
            h('div', { class: 'preview-card stat' }),
            h('div', { class: 'preview-card stat wide' }),
            h('div', { class: 'preview-card stat' }),
            h('div', { class: 'preview-card stat' })
          ])
        ])
      ]),
      h(PaymentModal, {
        visible: visible.value,
        orderType: 'token',
        targetType: 'user_account',
        targetId: 1,
        previewMethods,
        previewTokenPlans,
        onClose: () => {
          visible.value = false
        }
      })
    ])
  }
}).mount('#app')
