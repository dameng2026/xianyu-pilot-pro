<template><span :class="['switch', { on }]" /></template>
<script setup>defineProps({ on: { type: Boolean, default: true } })</script>
