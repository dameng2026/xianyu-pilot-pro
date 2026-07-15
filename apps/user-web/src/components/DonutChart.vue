<template>
  <div class="donut-row">
    <div class="donut" :style="style"><strong>{{ center }}</strong><span>{{ label }}</span></div>
    <div class="donut-legend">
      <div v-for="(item,i) in items" :key="item.label"><i :style="{background: colors[i%colors.length]}"></i><span>{{ item.label }}</span><b>{{ item.value }}</b></div>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
defineProps({ center: String, label: String, items: Array })
const colors = ['#1977ff','#18c785','#ffb020','#ff6b6b','#9b5cff','#33cdd2']
const style = computed(() => ({ background: `conic-gradient(${colors[0]} 0 42%, ${colors[1]} 42% 65%, ${colors[2]} 65% 80%, ${colors[3]} 80% 90%, ${colors[4]} 90% 100%)` }))
</script>
