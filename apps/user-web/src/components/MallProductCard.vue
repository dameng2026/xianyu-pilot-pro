<template>
  <article class="mall-card">
    <div class="mall-cover" :style="{ background: product.coverBg || `linear-gradient(135deg, ${product.coverFrom}, ${product.coverTo})` }">
      <div class="cover-decor"></div>
      <span v-if="product.tag" class="mall-cover-tag" :class="tagClass">{{ product.tag }}</span>
      <div class="cover-title-wrap">
        <span class="cover-title">{{ product.shortTitle || product.title }}</span>
      </div>
      <div class="cover-shine"></div>
    </div>
    <div class="mall-body">
      <h3 class="mall-title" :title="product.title">{{ product.title }}</h3>
      <p class="mall-intro">{{ product.intro }}</p>
      <div v-if="type === 'card'" class="mall-stock" :class="stockTone">库存 {{ product.stock }} 件</div>
      <div class="mall-meta">
        <span class="mall-bought">
          <svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          {{ product.boughtCount }} 人已购买
        </span>
        <span class="mall-time">
          <svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          {{ product.publishTime }}
        </span>
      </div>
      <div class="mall-footer">
        <span class="mall-price"><em>¥</em>{{ priceNum }}</span>
        <div class="mall-actions">
          <button class="mall-btn-outline" type="button">查看详情</button>
          <button class="mall-btn-buy" type="button">立即购买</button>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  product: { type: Object, required: true },
  type: { type: String, default: 'text' }
})

const stockTone = computed(() => {
  const stock = Number(props.product.stock) || 0
  if (stock <= 0) return 'none'
  if (stock < 50) return 'low'
  return 'enough'
})

const priceNum = computed(() => {
  const p = String(props.product.price || '')
  return p.replace(/^¥\s*/, '')
})

const tagClass = computed(() => {
  const tag = props.product.tag || ''
  if (tag.includes('热门')) return 'tag-hot'
  if (tag.includes('最新') || tag.includes('上新')) return 'tag-new'
  if (tag.includes('精品') || tag.includes('优质')) return 'tag-premium'
  return 'tag-default'
})
</script>

<style scoped>
.mall-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 14px rgba(31, 53, 94, .05);
  display: flex;
  flex-direction: column;
  transition: transform .18s ease, box-shadow .18s ease;
}

.mall-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 1px 2px rgba(31, 53, 94, .04), 0 14px 32px rgba(31, 53, 94, .12);
}

.mall-cover {
  width: 100%;
  aspect-ratio: 16 / 9;
  position: relative;
  overflow: hidden;
}

.cover-decor {
  position: absolute;
  right: -20px;
  top: -20px;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  background: rgba(255, 255, 255, .12);
}

.cover-decor::before {
  content: "";
  position: absolute;
  left: -40px;
  top: 50px;
  width: 70px;
  height: 70px;
  border-radius: 50%;
  background: rgba(255, 255, 255, .08);
}

.cover-shine {
  position: absolute;
  left: -50%;
  top: -60%;
  width: 60%;
  height: 160%;
  background: linear-gradient(120deg, transparent 30%, rgba(255, 255, 255, .12) 50%, transparent 70%);
  transform: skewX(-20deg);
  pointer-events: none;
}

.cover-title-wrap {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 14px 16px 12px;
  display: flex;
  align-items: flex-end;
  z-index: 1;
}

.cover-title {
  color: #fff;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: .5px;
  text-shadow: 0 2px 10px rgba(0, 0, 0, .35);
  line-height: 1.25;
  white-space: pre-line;
}

.mall-cover-tag {
  position: absolute;
  left: 10px;
  top: 10px;
  z-index: 2;
  height: 22px;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  backdrop-filter: blur(4px);
}

.mall-cover-tag.tag-hot {
  background: linear-gradient(135deg, rgba(255, 91, 97, .92), rgba(255, 123, 67, .92));
  color: #fff;
}

.mall-cover-tag.tag-new {
  background: linear-gradient(135deg, rgba(13, 107, 255, .92), rgba(49, 134, 255, .92));
  color: #fff;
}

.mall-cover-tag.tag-premium {
  background: linear-gradient(135deg, rgba(139, 92, 246, .92), rgba(168, 126, 255, .92));
  color: #fff;
}

.mall-cover-tag.tag-default {
  background: rgba(255, 255, 255, .9);
  color: var(--primary);
}

.mall-body {
  padding: 12px 14px 13px;
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 0;
}

.mall-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 39px;
}

.mall-intro {
  margin: 6px 0 0;
  font-size: 12px;
  color: #98a4b7;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 36px;
}

.mall-stock {
  margin-top: 6px;
  font-size: 12px;
  font-weight: 700;
}

.mall-stock.enough { color: var(--green); }
.mall-stock.low { color: var(--orange); }
.mall-stock.none { color: #98a4b7; }

.mall-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
  color: #98a4b7;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #f2f5fa;
  gap: 8px;
}

.mall-bought,
.mall-time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.meta-icon {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
}

.mall-time {
  flex-shrink: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  justify-content: flex-end;
}

.mall-footer {
  margin-top: auto;
  padding-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.mall-price {
  font-size: 22px;
  font-weight: 900;
  color: #ff3b30;
  letter-spacing: 0;
  line-height: 1;
  display: inline-flex;
  align-items: flex-start;
}

.mall-price em {
  font-size: 13px;
  font-style: normal;
  font-weight: 700;
  margin-right: 1px;
  margin-top: 2px;
}

.mall-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.mall-actions button {
  height: 30px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s ease;
  border: 1px solid var(--primary);
  white-space: nowrap;
}

.mall-btn-outline {
  background: #fff;
  color: var(--primary);
}

.mall-btn-outline:hover {
  background: #edf5ff;
}

.mall-btn-buy {
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  box-shadow: 0 4px 10px rgba(13, 107, 255, .2);
}

.mall-btn-buy:hover {
  box-shadow: 0 6px 14px rgba(13, 107, 255, .3);
}
</style>
