<template>
  <article class="mall-card">
    <div class="mall-cover" :style="{ background: `linear-gradient(135deg, ${product.coverFrom}, ${product.coverTo})` }">
      <span class="mall-cover-name">{{ product.title }}</span>
      <span v-if="product.tag" class="mall-cover-tag">{{ product.tag }}</span>
    </div>
    <div class="mall-body">
      <h3 class="mall-title" :title="product.title">{{ product.title }}</h3>
      <p class="mall-intro">{{ product.intro }}</p>
      <div v-if="type === 'card'" class="mall-stock" :class="stockTone">库存 {{ product.stock }} 件</div>
      <div class="mall-meta">
        <span class="mall-bought">{{ product.boughtCount }} 人已购买</span>
        <span class="mall-time">{{ product.publishTime }}</span>
      </div>
      <div class="mall-footer">
        <span class="mall-price">{{ product.price }}</span>
        <div class="mall-actions">
          <button class="app-btn mall-btn-outline" type="button">查看详情</button>
          <button class="app-btn primary mall-btn-buy" type="button">立即购买</button>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  product: { type: Object, required: true },
  type: { type: String, default: 'text' } // 'text' | 'card'
})

const stockTone = computed(() => {
  const stock = Number(props.product.stock) || 0
  if (stock <= 0) return 'none'
  if (stock < 50) return 'low'
  return 'enough'
})
</script>

<style scoped>
.mall-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 10px 26px rgba(31, 53, 94, .055);
  display: flex;
  flex-direction: column;
  transition: transform .18s ease, box-shadow .18s ease;
}

.mall-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 1px 2px rgba(31, 53, 94, .04), 0 16px 36px rgba(31, 53, 94, .12);
}

.mall-cover {
  width: 100%;
  aspect-ratio: 16 / 9;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 16px;
  overflow: hidden;
}

.mall-cover::after {
  content: "";
  position: absolute;
  right: -26px;
  bottom: -34px;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  background: rgba(255, 255, 255, .18);
}

.mall-cover-name {
  position: relative;
  z-index: 1;
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: .3px;
  text-align: center;
  text-shadow: 0 2px 8px rgba(0, 0, 0, .18);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mall-cover-tag {
  position: absolute;
  left: 10px;
  top: 10px;
  z-index: 1;
  height: 22px;
  padding: 0 9px;
  border-radius: 6px;
  background: rgba(255, 255, 255, .88);
  color: #ff5b61;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}

.mall-body {
  padding: 14px 15px 15px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.mall-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 43px;
}

.mall-intro {
  margin: 0;
  font-size: 12.5px;
  color: #8a96aa;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 39px;
}

.mall-stock {
  font-size: 12.5px;
  font-weight: 700;
}

.mall-stock.enough { color: var(--green); }
.mall-stock.low { color: var(--orange); }
.mall-stock.none { color: #98a4b7; }

.mall-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #98a4b7;
}

.mall-bought {
  display: inline-flex;
  align-items: center;
}

.mall-footer {
  margin-top: auto;
  padding-top: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.mall-price {
  font-size: 20px;
  font-weight: 900;
  color: #ff3b30;
  letter-spacing: .3px;
}

.mall-actions {
  display: flex;
  gap: 8px;
}

.mall-actions .app-btn {
  height: 34px;
  min-width: 0;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 13px;
}

.mall-btn-outline {
  background: #fff;
  border: 1px solid var(--primary);
  color: var(--primary);
  box-shadow: none;
}

.mall-btn-buy {
  border-color: var(--primary);
}
</style>
