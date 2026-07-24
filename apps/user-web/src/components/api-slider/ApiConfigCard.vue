<template>
  <CardPanel title="前台对接配置" desc="查看与管理您的对接凭证">
    <div class="form-row">
      <label>API 地址</label>
      <div class="input-group">
        <input :value="apiUrl" readonly class="readonly-input" />
        <button class="mini-btn" @click="$emit('copy', apiUrl, 'API地址')">复制</button>
      </div>
    </div>
    <div class="form-row">
      <label>对接密钥</label>
      <div class="input-group">
        <input :value="maskedKey" readonly class="readonly-input" />
        <button class="mini-btn" @click="$emit('copy', credential?.api_key_plain, '密钥')" v-if="credential">复制</button>
      </div>
    </div>
    <div class="form-row">
      <label>当前扣费单价</label>
      <input :value="`${overview?.perCallTokens ?? 5} Token / 次`" readonly class="readonly-input" />
    </div>
    <div class="form-actions">
      <button class="btn-secondary" @click="$emit('copy', credential?.api_key_plain, '密钥')" v-if="credential">复制密钥</button>
      <button class="btn-secondary" @click="$emit('copy', apiUrl, 'API地址')">复制地址</button>
      <button class="btn-primary" @click="$emit('reset-key')">重置密钥</button>
    </div>
  </CardPanel>
</template>

<script setup>
import { computed } from 'vue'
import CardPanel from '../CardPanel.vue'

const props = defineProps({
  credential: { type: Object, default: null },
  overview: { type: Object, default: () => ({}) },
})
defineEmits(['copy', 'reset-key'])

const apiUrl = computed(() => {
  if (typeof window !== 'undefined') return `${window.location.origin}/api/v1/slider/solve`
  return 'https://api.xianyupilot.com/api/v1/slider/solve'
})
const maskedKey = computed(() => {
  const prefix = props.credential?.api_key_prefix
  return prefix ? `${prefix}••••••••` : '尚未生成'
})
</script>

<style scoped>
.form-row { margin-bottom: 16px; }
.form-row label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
.input-group { display: flex; gap: 8px; }
.readonly-input {
  flex: 1; height: 36px; padding: 0 12px;
  border: 1px solid var(--line); border-radius: 6px;
  background: #f5f8ff; color: var(--text); font-size: 13px;
}
.mini-btn {
  border: 1px solid var(--primary); background: #fff; color: var(--primary);
  border-radius: 6px; padding: 0 12px; cursor: pointer; font-size: 12px;
}
.form-actions { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.btn-secondary {
  border: 1px solid var(--line); background: #fff; color: var(--text);
  border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 13px;
}
.btn-primary {
  border: none; background: var(--primary); color: #fff;
  border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 13px;
}
.btn-primary:hover { opacity: 0.9; }
</style>
