<template>
  <section class="m-unavailable" :class="{ compact }" role="alert">
    <div class="m-unavailable-icon"><MIcon name="warning" :size="compact ? 20 : 28" /></div>
    <div class="m-unavailable-copy">
      <strong>{{ title }}</strong>
      <p>{{ description }}</p>
    </div>
    <button v-if="retryable" type="button" class="m-unavailable-retry" @click="emit('retry')">重试</button>
  </section>
</template>

<script setup>
import MIcon from './MIcon.vue'

defineProps({
  title: { type: String, default: '数据暂时无法加载' },
  description: { type: String, default: '请检查网络连接后重试。' },
  compact: { type: Boolean, default: false },
  retryable: { type: Boolean, default: true }
})

const emit = defineEmits(['retry'])
</script>

<style scoped>
.m-unavailable {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
  padding: 16px;
  border: 1px solid #ffd0d0;
  border-radius: 16px;
  background: linear-gradient(135deg, #fff8f8, #fffdfd);
}
.m-unavailable.compact { padding: 12px; border-radius: 13px; }
.m-unavailable-icon {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff0f0;
  color: #e5484d;
}
.compact .m-unavailable-icon { width: 34px; height: 34px; }
.m-unavailable-copy { min-width: 0; }
.m-unavailable-copy strong { display: block; color: #8a1c1c; font-size: 14px; }
.m-unavailable-copy p { margin: 4px 0 0; color: #9c4a4a; font-size: 12px; line-height: 1.5; }
.m-unavailable-retry {
  border: 0;
  border-radius: 999px;
  padding: 7px 13px;
  background: #e5484d;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
@media (max-width: 380px) {
  .m-unavailable { grid-template-columns: auto minmax(0, 1fr); }
  .m-unavailable-retry { grid-column: 2; justify-self: start; }
}
</style>
