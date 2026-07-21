<template>
  <div class="m-chat-detail">
    <div class="m-detail-placeholder">
      <div class="m-placeholder-icon">
        <MIcon name="messageCircle" :size="48" />
      </div>
      <div class="m-placeholder-title">聊天详情</div>
      <div class="m-placeholder-desc">移动端聊天功能正在开发中</div>
      <button class="m-placeholder-btn" @click="emit('back')">
        <MIcon name="chevronLeft" :size="16" />
        返回消息列表
      </button>
    </div>
    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import MIcon from './MIcon.vue'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])
</script>

<style scoped>
.m-chat-detail {
  padding: 0 16px;
}
.m-detail-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
}
.m-placeholder-icon {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e6f9f1, #d4f5e7);
  color: #16bf78;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}
.m-placeholder-title {
  font-size: 18px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 8px;
}
.m-placeholder-desc {
  font-size: 14px;
  color: #8c98ae;
  margin-bottom: 24px;
}
.m-placeholder-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #0d6bff, #3b9bff);
  color: white;
  border: none;
  border-radius: 100px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(13,107,255,0.3);
}
.m-placeholder-btn:active {
  transform: scale(0.97);
}
.m-safe-bottom {
  height: calc(40px + env(safe-area-inset-bottom));
}
</style>
