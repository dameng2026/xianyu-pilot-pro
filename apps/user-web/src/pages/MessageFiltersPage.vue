<template>
  <div class="mf-page">
    <section class="mf-hero">
      <div class="mf-hero-copy">
        <h2>消息过滤</h2>
        <p>
          按账号和关键词屏蔽骚扰、广告或系统提示类消息：命中「跳过自动回复」的消息不会触发 AI/规则回复，
          命中「跳过通知」的消息不会出现在在线消息的新消息提醒中，消息本身仍会正常入库便于人工查看。
        </p>
        <p class="mf-moved">此功能已合并至「AI 客服配置」页面，可进入「AI客服配置」在「消息过滤」板块进行管理。</p>
      </div>
    </section>

    <MessageFiltersSection />
  </div>
</template>

<script setup>
import MessageFiltersSection from '../components/MessageFiltersSection.vue'
</script>

<style scoped>
.mf-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.mf-hero {
  padding: 18px 20px;
  background: linear-gradient(135deg, #1f6feb 0%, #7b5cff 100%);
  border-radius: 14px;
  color: #fff;
}

.mf-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.mf-hero-copy p {
  margin: 0;
  max-width: 760px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.92;
}

.mf-hero-copy p.mf-moved {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.85;
}
</style>
