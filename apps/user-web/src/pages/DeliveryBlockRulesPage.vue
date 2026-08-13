<template>
  <div class="dbr-page">
    <section class="dbr-hero">
      <div class="dbr-hero-copy">
        <h2>发货拦截规则</h2>
        <p>
          在自动发货前执行风控检查：买家在当前账号已有其他订单、或存在未确认收货订单时，
          系统将拦截本次发货（不发送、不确认平台发货、不认领卡密），并在发货记录中写明原因。
          可针对全部账号或单个账号启用。
        </p>
      </div>
    </section>

    <section class="dbr-panel card">
      <label class="dbr-field">
        <span>适用范围</span>
        <select v-model="scope.accountId" :disabled="loading" @change="loadRules">
          <option value="0">全部账号</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}
          </option>
        </select>
      </label>

      <div v-if="loadError" class="dbr-error">{{ loadError }}</div>

      <div class="dbr-rule-list">
        <div class="dbr-rule-card">
          <div class="dbr-rule-copy">
            <strong>买家已有其他订单</strong>
            <p>买家在当前账号下已有其他未关闭订单时，禁止本次自动发货，防止多单异常交易。</p>
          </div>
          <button
            type="button"
            class="dbr-toggle"
            :class="{ on: isEnabled('buyer_has_order') }"
            :disabled="saving"
            @click="toggleRule('buyer_has_order', '买家已有其他订单')"
          >
            {{ isEnabled('buyer_has_order') ? '已启用' : '已停用' }}
          </button>
        </div>

        <div class="dbr-rule-card">
          <div class="dbr-rule-copy">
            <strong>买家存在未确认收货订单</strong>
            <p>买家在当前账号下存在已发货但未确认收货的订单时，禁止本次自动发货。</p>
          </div>
          <button
            type="button"
            class="dbr-toggle"
            :class="{ on: isEnabled('buyer_unconfirmed') }"
            :disabled="saving"
            @click="toggleRule('buyer_unconfirmed', '买家存在未确认收货订单')"
          >
            {{ isEnabled('buyer_unconfirmed') ? '已启用' : '已停用' }}
          </button>
        </div>
      </div>

      <p class="dbr-tip">
        规则为“命中即拦截”：同时启用多条时，按优先级依次检查，任一命中即中止本次自动发货。
        检查失败时按未命中处理，不会误伤正常发货。
      </p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getAccounts } from '../api/accounts.js'
import {
  listDeliveryBlockRules,
  saveDeliveryBlockRule,
  toggleDeliveryBlockRule,
} from '../api/deliveryBlockRule.js'

const accounts = ref([])
const rules = ref([])
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const scope = ref({ accountId: '0' })

const ruleMap = computed(() => {
  const map = {}
  for (const rule of rules.value) map[rule.ruleCode] = rule
  return map
})

function isEnabled(code) {
  return !!ruleMap.value[code]?.enabled
}

async function loadAccounts() {
  try {
    const res = await getAccounts({ current: 1, size: 100 })
    const list = Array.isArray(res?.data) ? res.data : (res?.data?.records || [])
    accounts.value = list
  } catch (e) {
    loadError.value = e?.message || '账号列表加载失败'
  }
}

async function loadRules() {
  loading.value = true
  loadError.value = ''
  try {
    const params = {}
    if (scope.value.accountId !== '0') params.accountId = scope.value.accountId
    const res = await listDeliveryBlockRules(params)
    rules.value = Array.isArray(res?.data?.records) ? res.data.records : []
  } catch (e) {
    loadError.value = e?.message || '规则加载失败'
  } finally {
    loading.value = false
  }
}

async function toggleRule(code, name) {
  saving.value = true
  loadError.value = ''
  try {
    const existing = ruleMap.value[code]
    if (existing) {
      await toggleDeliveryBlockRule(existing.id, !existing.enabled)
    } else {
      await saveDeliveryBlockRule({
        accountId: Number(scope.value.accountId) || 0,
        ruleCode: code,
        ruleName: name,
        enabled: true,
        priority: code === 'buyer_has_order' ? 10 : 20,
      })
    }
    await loadRules()
  } catch (e) {
    loadError.value = e?.message || '切换失败'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadAccounts()
  await loadRules()
})
</script>

<style scoped>
.dbr-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.dbr-hero {
  padding: 18px 20px;
  background: linear-gradient(135deg, #f59e0b 0%, #dc2626 100%);
  border-radius: 14px;
  color: #fff;
}

.dbr-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.dbr-hero-copy p {
  margin: 0;
  max-width: 800px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.94;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.dbr-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  max-width: 780px;
}

.dbr-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  max-width: 320px;
}

.dbr-field > span {
  font-size: 12px;
  color: #6b7280;
}

.dbr-field select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  color: #111827;
  outline: none;
}

.dbr-field select:focus {
  border-color: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.12);
}

.dbr-rule-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dbr-rule-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px 16px;
  background: #fafafa;
}

.dbr-rule-copy strong {
  font-size: 14px;
  color: #111827;
}

.dbr-rule-copy p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
  max-width: 560px;
}

.dbr-toggle {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #6b7280;
  border-radius: 999px;
  padding: 6px 16px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}

.dbr-toggle.on {
  border-color: #dc2626;
  background: #fef2f2;
  color: #b91c1c;
}

.dbr-toggle:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.dbr-tip {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.7;
  background: #f9fafb;
  border-radius: 8px;
  padding: 10px 12px;
}

.dbr-error {
  margin: 0;
  color: #dc2626;
  font-size: 13px;
}
</style>
