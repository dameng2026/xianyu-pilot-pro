<template>
  <div class="overview-grid">
    <!-- 对接密钥 -->
    <div class="overview-card">
      <div class="card-icon icon-blue">🔑</div>
      <div class="card-label">对接密钥</div>
      <div class="card-value key-value">{{ keyDisplay }}</div>
      <div class="card-sub">
        <Badge v-if="credential" :type="credential?.enabled === 0 ? 'gray' : 'green'">{{ credential?.enabled === 0 ? '已禁用' : '启用中' }}</Badge>
        <button class="copy-btn" @click="$emit('copy', fullKey, '密钥')" v-if="fullKey">复制</button>
        <button class="action-btn" @click="$emit('reset-key')" v-if="!loading && !credential">生成密钥</button>
      </div>
    </div>

    <!-- Token 余额 -->
    <div class="overview-card">
      <div class="card-icon icon-blue">🪙</div>
      <div class="card-label">Token 余额</div>
      <div class="card-value">{{ overview.tokenBalance ?? 0 }}</div>
      <div class="card-sub">
        <span>今日已消耗 {{ overview.todayChargedTokens ?? 0 }} Token</span>
        <button class="action-btn" @click="$emit('recharge')">充值 Token</button>
      </div>
    </div>

    <!-- 单次价格 -->
    <div class="overview-card">
      <div class="card-icon icon-purple">🏷</div>
      <div class="card-label">单次滑块求解价格</div>
      <div class="card-value">{{ overview.perCallTokens != null ? `${overview.perCallTokens} Token` : '价格不可用' }}</div>
      <div class="card-sub">{{ overview.perCallPrice != null ? `${overview.perCallPrice} 元/次` : '价格不可用' }}</div>
    </div>

    <!-- API 地址 -->
    <div class="overview-card">
      <div class="card-icon icon-green">🌐</div>
      <div class="card-label">API 对接地址</div>
      <div class="card-value card-value-sm">{{ apiUrl }}</div>
      <div class="card-sub">
        <button class="copy-btn" @click="$emit('copy', apiUrl, 'API地址')">复制</button>
      </div>
    </div>

    <!-- 计费规则 -->
    <div class="overview-card">
      <div class="card-icon icon-orange">📄</div>
      <div class="card-label">计费规则</div>
      <div class="card-value card-value-sm">仅成功求解扣费</div>
      <div class="card-sub">失败 / 预检测 / 超时不扣费</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Badge from '../Badge.vue'

const props = defineProps({
  credential: { type: Object, default: null },
  overview: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
})

defineEmits(['copy', 'recharge', 'reset-key'])

const apiUrl = computed(() => {
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/api/v1/slider/solve`
  }
  return 'https://api.xianyupilot.com/api/v1/slider/solve'
})

const keyDisplay = computed(() => {
  if (props.loading && !props.credential) return '加载中…'
  return props.credential?.api_key_plain || '尚未生成'
})

const fullKey = computed(() => props.credential?.api_key_plain || '')
</script>

<style scoped>
.overview-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.overview-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 20px;
  box-shadow: var(--shadow);
}
.card-icon {
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; margin-bottom: 12px;
}
.icon-blue { background: #e3f2fd; }
.icon-purple { background: #f3e8ff; }
.icon-green { background: #e8f5e9; }
.icon-orange { background: #fff3e0; }
.card-label { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.card-value { font-size: 26px; font-weight: 600; color: var(--text); word-break: break-all; }
.key-value { font-size: 16px; letter-spacing: 0.02em; }
.card-value-sm { font-size: 16px; }
.card-sub { margin-top: 8px; font-size: 12px; color: var(--muted); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.copy-btn, .action-btn {
  background: transparent; border: 1px solid var(--primary); color: var(--primary);
  border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer;
}
.action-btn { background: var(--primary); color: #fff; }
.copy-btn:hover, .action-btn:hover { opacity: 0.85; }
@media (max-width: 768px) {
  .overview-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
