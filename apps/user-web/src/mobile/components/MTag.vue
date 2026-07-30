<template>
  <span class="m-tag" :class="tagClass">
    <slot />
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: { type: String, default: 'neutral' },
  size: { type: String, default: 'md' },
  count: { type: Boolean, default: false }
})

const tagClass = computed(() => [
  `m-tag--${props.type}`,
  `m-tag--${props.size}`,
  { 'm-tag--count': props.count }
])
</script>

<style scoped>
.m-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  padding: 0 9px;
  border-radius: 7px;
  font-weight: 700;
  font-size: 12px;
  line-height: 1;
}

.m-tag--sm { 
  height: 20px; 
  font-size: 11px;
  padding: 0 7px;
}
.m-tag--md { 
  height: 24px; 
  font-size: 12px;
}

/* PC版Badge配色 */
.m-tag--success { 
  background: #eafaf3; 
  color: #0e9f6e; 
}
.m-tag--warning { 
  background: #fff5e6; 
  color: #d97706; 
}
.m-tag--danger { 
  background: #fff0f1; 
  color: #ef4444; 
}
.m-tag--info { 
  background: #edf5ff; 
  color: #0d6bff; 
}
.m-tag--blue {
  background: #edf5ff;
  color: #0d6bff;
}
.m-tag--orange {
  background: #fff5e6;
  color: #d97706;
}
.m-tag--red {
  background: #fff0f1;
  color: #ef4444;
}
.m-tag--green {
  background: #eafaf3;
  color: #0e9f6e;
}
.m-tag--purple {
  background: #f3e8ff;
  color: #7c3aed;
}
.m-tag--neutral { 
  background: #f1f4f8; 
  color: #718096; 
}
.m-tag--gray {
  background: #f1f4f8;
  color: #718096;
}
.m-tag--yellow {
  background: #fef9c3;
  color: #ca8a04;
}
.m-tag--outline { 
  background: transparent; 
  color: #72809a; 
  border: 1px solid #e7edf7; 
}

/* 数字徽标 */
.m-tag--count {
  background: #ff5b61;
  color: #fff;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 10px;
}
</style>
