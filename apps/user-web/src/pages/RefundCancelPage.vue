<template>
  <div class="rc-page">
    <section class="rc-hero">
      <div class="rc-hero-copy">
        <h2>退款关单</h2>
        <p>
          按账号配置外部注销接口：当系统同步到退款订单时，将订单发货内容按块推送给你自己的注销/回收服务，
          用于在外部系统同步关闭订单或回收卡密。全部推送成功才会标记该订单为已注销。
        </p>
        <p class="rc-moved">此功能已合并至「退款管理」页面，可在页面顶部切换到「退款关单」视图进行配置。</p>
      </div>
    </section>

    <RefundCancelConfig />
  </div>
</template>

<script setup>
import RefundCancelConfig from '../components/RefundCancelConfig.vue'
</script>

<style scoped>
.rc-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.rc-hero {
  padding: 18px 20px;
  background: linear-gradient(135deg, #0f766e 0%, #0ea5e9 100%);
  border-radius: 14px;
  color: #fff;
}

.rc-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.rc-hero-copy p {
  margin: 0;
  max-width: 800px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.94;
}

.rc-hero-copy p.rc-moved {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.85;
}
</style>
