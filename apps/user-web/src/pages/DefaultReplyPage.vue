<template>
  <div class="dr-page">
    <section class="dr-hero">
      <div class="dr-hero-copy">
        <h2>默认回复</h2>
        <p>
          当买家发送的消息未命中关键词规则、且 AI 客服未回复时，系统按账号发送默认回复，避免买家消息无人响应。
          支持固定文本（可附图片）与外部 API 两种回复方式，也可设置同一买家仅回复一次。
        </p>
        <p class="dr-moved">此功能已合并至「AI 客服配置」页面，可进入「AI客服配置」在「默认回复」板块进行管理。</p>
      </div>
    </section>

    <DefaultReplySection />
  </div>
</template>

<script setup>
import DefaultReplySection from '../components/DefaultReplySection.vue'
</script>

<style scoped>
.dr-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.dr-hero {
  padding: 18px 20px;
  background: linear-gradient(135deg, #0f766e 0%, #0ea5e9 100%);
  border-radius: 14px;
  color: #fff;
}

.dr-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.dr-hero-copy p {
  margin: 0;
  max-width: 760px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.92;
}

.dr-hero-copy p.dr-moved {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.85;
}
</style>
