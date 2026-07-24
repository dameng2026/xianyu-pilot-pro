<template>
  <CardPanel title="Token 消费说明" desc="成功才扣费，失败不扣费">
    <p class="desc">Token 仅在滑块成功求解后扣费，失败/预检测未通过/超时/服务不可用等情况一律不扣费。</p>
    <div class="mini-stats">
      <div class="mini-card">
        <div class="mini-value">{{ overview?.todayChargedTokens ?? 0 }}</div>
        <div class="mini-label">今日消耗</div>
      </div>
      <div class="mini-card">
        <div class="mini-value">{{ monthCharged }}</div>
        <div class="mini-label">本月消耗</div>
      </div>
      <div class="mini-card">
        <div class="mini-value">{{ successRate }}%</div>
        <div class="mini-label">近7天成功率</div>
      </div>
    </div>
    <div class="legend">
      <div class="legend-item"><span class="dot dot-green"></span>成功扣费</div>
      <div class="legend-item"><span class="dot dot-red"></span>失败不扣费</div>
      <div class="legend-item"><span class="dot dot-orange"></span>预检测不扣费</div>
      <div class="legend-item"><span class="dot dot-purple"></span>超时不扣费</div>
    </div>
  </CardPanel>
</template>

<script setup>
import { computed } from 'vue'
import CardPanel from '../CardPanel.vue'

const props = defineProps({
  overview: { type: Object, default: () => ({}) },
  stats: { type: Object, default: () => ({ kpi: {}, trend: [] }) },
})

const monthCharged = computed(() => {
  const kpi = props.stats?.kpi || {}
  return kpi.charged_tokens ?? 0
})

const successRate = computed(() => {
  const kpi = props.stats?.kpi || {}
  const total = Number(kpi.total ?? 0)
  const success = Number(kpi.success_count ?? 0)
  if (total === 0) return 0
  return Math.round((success / total) * 100)
})
</script>

<style scoped>
.desc { font-size: 13px; color: var(--muted); margin: 0 0 16px; line-height: 1.6; }
.mini-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.mini-card { text-align: center; padding: 12px; background: #f5f8ff; border-radius: 8px; }
.mini-value { font-size: 22px; font-weight: 600; color: var(--primary); }
.mini-label { font-size: 12px; color: var(--muted); margin-top: 4px; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--muted); }
.legend-item { display: flex; align-items: center; gap: 4px; }
.dot { width: 10px; height: 10px; border-radius: 50%; }
.dot-green { background: var(--green); }
.dot-red { background: var(--red); }
.dot-orange { background: var(--orange); }
.dot-purple { background: var(--purple); }
</style>
