<template>
  <section class="card-panel">
    <div v-if="title || $slots.action" class="panel-head">
      <div>
        <h3><slot name="title">{{ title }}</slot></h3>
        <p v-if="$slots.desc || desc"><slot name="desc">{{ desc }}</slot></p>
      </div>
      <slot name="action" />
    </div>
    <slot />
  </section>
</template>
<script setup>
defineProps({ title: String, desc: String })
</script>
