<template>
  <div class="settings-layout">
    <ConfigNav :active="active" @navigate="emit('navigate', $event)" />
    <div class="settings-main">
      <component :is="current" :active="active" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ConfigNav from '../components/ConfigNav.vue'
import AiCsSettings from './settings/AiCsSettings.vue'
import ProductOpSettings from './settings/ProductOpSettings.vue'
import NotifySettings from './settings/NotifySettings.vue'
import AboutSettings from './settings/AboutSettings.vue'

const props = defineProps({ active: String })
const emit = defineEmits(['navigate'])

const map = {
  'settings-ai-cs': AiCsSettings,
  'settings-product': ProductOpSettings,
  'settings-about': AboutSettings,
  'settings-notify': NotifySettings
}

const current = computed(() => map[props.active] || AiCsSettings)
</script>

<style scoped>
.settings-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.settings-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 1260px) {
  .settings-layout {
    grid-template-columns: 1fr;
  }
}
</style>
