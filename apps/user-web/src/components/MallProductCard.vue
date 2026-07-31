<template>
  <article class="mall-card">
    <div class="mall-cover" :style="coverStyle">
      <img v-if="product.coverUrl" :src="product.coverUrl" class="cover-img" alt="" />
      <template v-else>
        <div class="cover-decor"></div>
        <div class="cover-title-wrap">
          <span class="cover-title">{{ product.shortTitle || product.title }}</span>
        </div>
        <div class="cover-shine"></div>
      </template>
      <span v-if="product.tag" class="mall-cover-tag" :class="tagClass">{{ product.tag }}</span>
    </div>
    <div class="mall-body">
      <h3 class="mall-title" :title="product.title">{{ product.title }}</h3>
      <p class="mall-intro">{{ product.subtitle || product.intro || product.content }}</p>
      <div v-if="type === 'card'" class="mall-stock" :class="stockTone">库存 {{ stockDisplay }} 件</div>
      <div class="mall-meta">
        <span class="mall-bought">
          <svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          {{ boughtDisplay }} 人已购买
        </span>
        <span class="mall-time">
          <svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          {{ timeDisplay }}
        </span>
      </div>
      <div class="mall-footer">
        <template v-if="purchased">
          <span class="mall-price mall-price-owned">已领取</span>
          <div class="mall-actions">
            <button class="mall-btn-outline" type="button" @click="$emit('detail')">查看详情</button>
            <button class="mall-btn-owned" type="button" @click="$emit('detail')">管理商品</button>
          </div>
        </template>
        <template v-else>
          <span v-if="isFree" class="mall-price mall-price-free">免费</span>
          <span v-else class="mall-price"><em>¥</em>{{ priceNum }}</span>
          <div class="mall-actions">
            <button class="mall-btn-outline" type="button" @click="$emit('detail')">上架该商品</button>
            <button class="mall-btn-buy" type="button" @click="$emit('buy')">{{ isFree ? '立即领取' : '立即购买' }}</button>
          </div>
        </template>
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

defineEmits(['detail', 'buy'])

const coverStyle = computed(() => {
  if (props.product.coverUrl) return {}
  return {
    background: props.product.coverBg || `linear-gradient(135deg, ${props.product.coverFrom}, ${props.product.coverTo})`
  }
})

const stockValue = computed(() => {
  const p = props.product || {}
  if (p.stockCount != null) return Number(p.stockCount) || 0
  if (p.stock != null) return Number(p.stock) || 0
  return 0
})

const stockDisplay = computed(() => stockValue.value)

const stockTone = computed(() => {
  const stock = stockValue.value
  if (stock <= 0) return 'none'
  if (stock < 50) return 'low'
  return 'enough'
})

const priceNum = computed(() => {
  const p = props.product || {}
  if (p.priceYuan != null) return String(p.priceYuan)
  if (p.priceCent != null) {
    const n = Number(p.priceCent)
    if (!Number.isNaN(n)) return (n / 100).toFixed(2)
  }
  return String(p.price || '').replace(/^¥\s*/, '')
})

// 是否为免费商品（价格为 0）
const isFree = computed(() => {
  const p = props.product || {}
  if (p.priceCent != null) {
    const n = Number(p.priceCent)
    if (!Number.isNaN(n)) return n === 0
  }
  if (p.priceYuan != null) {
    const n = Number(p.priceYuan)
    if (!Number.isNaN(n)) return n === 0
  }
  const raw = String(p.price || '').replace(/[¥￥\s]/g, '')
  if (raw !== '') {
    const n = Number(raw)
    if (!Number.isNaN(n)) return n === 0
  }
  return false
})

// 当前用户是否已拥有该商品（已购买/已领取）
const purchased = computed(() => !!props.product?.purchased)

const boughtDisplay = computed(() => {
  const raw = props.product?.boughtCount
  if (raw == null || raw === '') return '0'
  if (typeof raw === 'number') return raw.toLocaleString('zh-CN')
  const num = Number(String(raw).replace(/[^0-9]/g, ''))
  if (!Number.isNaN(num)) return num.toLocaleString('zh-CN')
  return raw
})

const timeDisplay = computed(() => {
  const raw = props.product?.createTime || props.product?.publishTime
  if (!raw) return props.product?.publishTime || ''
  if (props.product?.publishTime && !props.product?.createTime) return props.product.publishTime
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return String(raw)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
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
  aspect-ratio: 1 / 1;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #f6f9ff 0%, #eef3fa 100%);
}

.cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.32s cubic-bezier(0.4, 0, 0.2, 1);
}

.mall-card:hover .cover-img {
  transform: scale(1.06);
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

.mall-price-free {
  color: #00b578;
  font-size: 18px;
  letter-spacing: 1px;
}

.mall-price-owned {
  color: #16bf78;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: .5px;
  display: inline-flex;
  align-items: center;
}

.mall-price-owned::before {
  content: "";
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 4px;
  border-radius: 50%;
  background: #16bf78;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'/></svg>");
  background-size: 10px 10px;
  background-repeat: no-repeat;
  background-position: center;
}

.mall-btn-owned {
  background: linear-gradient(90deg, #16bf78, #1dd68a);
  color: #fff;
  box-shadow: 0 4px 10px rgba(22, 191, 120, .2);
}

.mall-btn-owned:hover {
  box-shadow: 0 6px 14px rgba(22, 191, 120, .3);
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
