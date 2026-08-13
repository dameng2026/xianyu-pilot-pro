<template>
  <div class="fsb-page">
    <section class="fsb-hero">
      <div class="fsb-hero-copy">
        <h2>流量分布</h2>
        <p>
          查看鱼小铺账号的浏览流量构成：来源分布、商品分布、时间分布与地域分布，
          帮助判断流量从哪来、哪些商品更受欢迎、买家活跃时段与地域特征。
        </p>
        <p class="fsb-moved">此功能已合并至「鱼小铺数据分析」页面，可在页面顶部切换到「流量分布」视图进行查看。</p>
      </div>
    </section>

    <FishShopBrowseSection />
  </div>
</template>

<script setup>
import FishShopBrowseSection from '../components/FishShopBrowseSection.vue'
</script>

<style scoped>
.fsb-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.fsb-hero {
  padding: 18px 20px;
  background: linear-gradient(135deg, #0f766e 0%, #0ea5e9 100%);
  border-radius: 14px;
  color: #fff;
}

.fsb-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.fsb-hero-copy p {
  margin: 0;
  max-width: 800px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.94;
}

.fsb-hero-copy p.fsb-moved {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.85;
}
</style>
