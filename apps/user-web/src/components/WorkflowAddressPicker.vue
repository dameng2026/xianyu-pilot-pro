<template>
  <div v-if="visible" class="wf-addr-mask" @click.self="onCancel">
    <div class="wf-addr-dialog">
      <div>
        <strong>未检测到可用的发布地址</strong>
        <p>请选择完整的省、市、区。选择结果会保存为常用发布地址，并继续执行工作流。</p>
      </div>

      <div v-if="addressHistory.length" class="history">
        <span>历史地址</span>
        <button
          v-for="address in addressHistory"
          :key="address.id || address.poiName"
          :class="{ active: selectedHistoryId === address.id }"
          type="button"
          @click="pickHistory(address)"
        >
          {{ address.poiName || address.address || '历史地址' }}
        </button>
      </div>

      <PublishAddressCascader v-model="selectedAddress" />

      <div class="actions">
        <button type="button" @click="onCancel">取消</button>
        <button type="button" :disabled="!canConfirm" @click="onConfirm">
          {{ saving ? '保存中...' : '保存并继续执行' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import PublishAddressCascader from './PublishAddressCascader.vue'
import { isPublishAddressComplete, normalizePublishAddress } from '../utils/publishAddress.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  addressHistory: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
})
const emit = defineEmits(['confirm', 'cancel'])

const selectedAddress = ref(null)
const selectedHistoryId = ref(null)
const canConfirm = computed(() => isPublishAddressComplete(selectedAddress.value) && !props.saving)

function pickHistory(address) {
  selectedHistoryId.value = address.id || null
  selectedAddress.value = normalizePublishAddress(address)
}

function onConfirm() {
  if (canConfirm.value) emit('confirm', normalizePublishAddress(selectedAddress.value))
}

function onCancel() {
  emit('cancel')
}

watch(() => props.visible, (visible) => {
  if (!visible) return
  selectedAddress.value = null
  selectedHistoryId.value = null
})
</script>

<style scoped>
.wf-addr-mask { position: fixed; inset: 0; z-index: 9999; display: grid; place-items: center; background: rgba(15, 23, 42, .55); }
.wf-addr-dialog { width: 540px; max-width: 92vw; padding: 24px; border-radius: 14px; background: #fff; box-shadow: 0 24px 48px rgba(15,23,42,.18); }
.wf-addr-dialog strong { color: #b45309; font-size: 17px; }
.wf-addr-dialog p { margin: 6px 0 16px; color: #64748b; font-size: 13px; line-height: 1.6; }
.history { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 14px; }
.history span { width: 100%; color: #475569; font-size: 13px; }
.history button { border: 1px solid #dbe3ef; border-radius: 8px; padding: 6px 9px; background: #f8fafc; color: #334155; cursor: pointer; font-size: 12px; }
.history button.active { border-color: #60a5fa; background: #eff6ff; color: #1d4ed8; }
.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
.actions button { border: 0; border-radius: 7px; padding: 8px 14px; cursor: pointer; background: #f1f5f9; color: #475569; }
.actions button:last-child { background: #1677ff; color: #fff; }
.actions button:disabled { cursor: not-allowed; background: #94a3b8; }
</style>
