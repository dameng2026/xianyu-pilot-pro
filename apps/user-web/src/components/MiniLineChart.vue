<template>
  <div class="chart-wrap">
    <svg :viewBox="`0 0 ${width} ${height}`" class="line-chart">
      <g class="grid">
        <line v-for="y in [20,60,100,140,180]" :key="y" x1="20" :y1="y" :x2="width-20" :y2="y" />
      </g>
      <polyline :points="areaPoints" fill="rgba(22,112,255,.10)" stroke="none" />
      <polyline :points="points" fill="none" stroke="var(--primary)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
      <circle v-for="(p,i) in dotList" :key="i" :cx="p.x" :cy="p.y" r="5" fill="white" stroke="var(--primary)" stroke-width="4" />
      <g class="axis"><text v-for="(m,i) in labels" :key="m" :x="30+i*92" :y="height-10">{{ m }}</text></g>
    </svg>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ values: { type: Array, default: () => [90,140,125,130,85,92,120,150] }, labels: { type: Array, default: () => ['05-31','06-01','06-02','06-03','06-04','06-05','06-06','06-07'] } })
const width = 740, height = 240
const dotList = computed(() => props.values.map((v, i) => ({ x: 30 + i * ((width - 60) / (props.values.length - 1)), y: 210 - v })))
const points = computed(() => dotList.value.map(p => `${p.x},${p.y}`).join(' '))
const areaPoints = computed(() => `30,210 ${points.value} ${width-30},210`)
</script>
