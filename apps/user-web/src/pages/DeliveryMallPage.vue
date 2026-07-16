<template>
  <div class="mall-page">
    <div class="mall-main-wrap">
      <div class="mall-main">
        <div class="mall-header">
          <div class="mall-header-left">
            <div class="mall-icon-wrap">
              <svg viewBox="0 0 24 24" fill="none" class="mall-header-icon">
                <path d="M7 22C8.10457 22 9 21.1046 9 20C9 18.8954 8.10457 18 7 18C5.89543 18 5 18.8954 5 20C5 21.1046 5.89543 22 7 22Z" fill="currentColor"/>
                <path d="M17 22C18.1046 22 19 21.1046 19 20C19 18.8954 18.1046 18 17 18C15.8954 18 15 18.8954 15 20C15 21.1046 15.8954 22 17 22Z" fill="currentColor"/>
                <path d="M3 3H5L5.4 5M7 13H17L19 7H5.4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <div class="mall-header-titles">
              <h2 class="mall-header-title">货源商城</h2>
              <p class="mall-header-desc">海量优质虚拟商品资源，自动发货，即买即用</p>
            </div>
          </div>
          <div class="mall-stat-card">
            <div class="stat-icon">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M17 20H5C3.89543 20 3 19.1046 3 18V7C3 5.89543 3.89543 5 5 5H19C20.1046 5 21 5.89543 21 7V13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <path d="M3 7L12 13L21 7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <circle cx="17" cy="17" r="4" fill="#4F7CFF" fill-opacity="0.15"/>
                <path d="M15 17H19M17 15V19" stroke="#4F7CFF" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
            <div class="stat-content">
              <div class="stat-label">已购买人数</div>
              <div class="stat-number">12,458<span class="stat-unit">人</span></div>
              <div class="stat-hint">昨日新增326人</div>
            </div>
          </div>
        </div>

        <div class="mall-banner">
          <div class="banner-left">
            <h3 class="banner-title">
              <span class="banner-title-dark">自动发货 ·</span>
              <span class="banner-title-blue">货源商城</span>
            </h3>
            <ul class="banner-points">
              <li>
                <span class="point-check"><svg viewBox="0 0 16 16" fill="none"><path d="M13 4L6 11L3 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
                海量优质资源，持续更新
              </li>
              <li>
                <span class="point-check"><svg viewBox="0 0 16 16" fill="none"><path d="M13 4L6 11L3 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
                自动发货，秒发到手
              </li>
              <li>
                <span class="point-check"><svg viewBox="0 0 16 16" fill="none"><path d="M13 4L6 11L3 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
                安全稳定，售后无忧
              </li>
            </ul>
            <div class="banner-illustration">
              <div class="illus-tag">
                <div class="tag-hole"></div>
                <div class="tag-hole tag-hole-r"></div>
                <span class="tag-text">自动发货</span>
                <div class="tag-string tag-string-l"></div>
                <div class="tag-string tag-string-r"></div>
              </div>
              <div class="illus-cart">
                <div class="cart-handle"></div>
                <div class="cart-basket">
                  <div class="basket-item basket-item-1"></div>
                  <div class="basket-item basket-item-2"></div>
                  <div class="basket-item basket-item-3"></div>
                </div>
                <div class="cart-wheel cart-wheel-l"></div>
                <div class="cart-wheel cart-wheel-r"></div>
              </div>
              <div class="illus-box">
                <div class="box-tape box-tape-v"></div>
                <div class="box-tape box-tape-h"></div>
                <div class="box-flap"></div>
              </div>
              <div class="illus-spark illus-spark-1"></div>
              <div class="illus-spark illus-spark-2"></div>
              <div class="illus-spark illus-spark-3"></div>
            </div>
          </div>
          <div class="banner-right">
            <div class="notice-card">
              <div class="notice-item">
                <div class="notice-head">
                  <span class="notice-icon notice-icon-blue">
                    <svg viewBox="0 0 20 20" fill="none">
                      <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
                      <path d="M10 6V11M10 14V14.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    </svg>
                  </span>
                  <span class="notice-title">文本商品说明</span>
                </div>
                <p class="notice-text">本站所有文本商品会一直更新，若出现文本商品不可用情况，可点击<span class="text-blue">投诉</span>，核实后将会<span class="text-red">下架处理</span>，感谢您的监督与支持！</p>
              </div>
              <div class="notice-divider"></div>
              <div class="notice-item">
                <div class="notice-head">
                  <span class="notice-icon notice-icon-green">
                    <svg viewBox="0 0 20 20" fill="none">
                      <rect x="2" y="5" width="16" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/>
                      <path d="M2 8H18" stroke="currentColor" stroke-width="1.5"/>
                      <path d="M6 3V7M14 3V7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                  </span>
                  <span class="notice-title">卡密商品说明</span>
                </div>
                <p class="notice-text">卡密商品库存实时更新，购买后自动发货，请及时使用。如遇问题可联系客服或提交工单，我们将尽快为您处理！</p>
              </div>
            </div>
          </div>
        </div>

        <div class="mall-content-card">
          <div class="mall-tabs">
            <div
              v-for="tab in productTabs"
              :key="tab.value"
              :class="['mall-tab', { active: activeTab === tab.value }]"
              @click="activeTab = tab.value"
            >
              {{ tab.label }}
            </div>
          </div>

          <div class="mall-toolbar">
            <div class="toolbar-left">
              <div
                v-for="cat in categories"
                :key="cat"
                :class="['cat-chip', { active: activeCategory === cat }]"
                @click="activeCategory = cat"
              >
                {{ cat }}
              </div>
            </div>
            <div class="toolbar-right">
              <div class="tool-search">
                <svg viewBox="0 0 18 18" fill="none" class="tool-search-icon">
                  <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.8"/>
                  <path d="M12.5 12.5L16 16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                </svg>
                <input type="text" placeholder="搜索商品名称、关键词" class="tool-search-input">
              </div>
              <select class="tool-select">
                <option value="">综合排序</option>
                <option value="sales">销量优先</option>
                <option value="price-asc">价格从低到高</option>
                <option value="price-desc">价格从高到低</option>
                <option value="new">最新发布</option>
              </select>
              <div class="view-switch">
                <button :class="['view-btn', { active: viewMode === 'grid' }]" @click="viewMode = 'grid'" title="宫格视图">
                  <svg viewBox="0 0 18 18" fill="none">
                    <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'grid' ? 'currentColor' : 'none'"/>
                    <rect x="11" y="2" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'grid' ? 'currentColor' : 'none'"/>
                    <rect x="2" y="11" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'grid' ? 'currentColor' : 'none'"/>
                    <rect x="11" y="11" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'grid' ? 'currentColor' : 'none'"/>
                  </svg>
                </button>
                <button :class="['view-btn', { active: viewMode === 'list' }]" @click="viewMode = 'list'" title="列表视图">
                  <svg viewBox="0 0 18 18" fill="none">
                    <rect x="2" y="3" width="3" height="2" rx="0.5" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'list' ? 'currentColor' : 'none'"/>
                    <rect x="2" y="8" width="3" height="2" rx="0.5" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'list' ? 'currentColor' : 'none'"/>
                    <rect x="2" y="13" width="3" height="2" rx="0.5" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'list' ? 'currentColor' : 'none'"/>
                    <rect x="7" y="3" width="9" height="2" rx="0.5" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'list' ? 'currentColor' : 'none'"/>
                    <rect x="7" y="8" width="9" height="2" rx="0.5" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'list' ? 'currentColor' : 'none'"/>
                    <rect x="7" y="13" width="9" height="2" rx="0.5" stroke="currentColor" stroke-width="1.5" :fill="viewMode === 'list' ? 'currentColor' : 'none'"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <div :class="['mall-products', viewMode]">
            <MallProductCard
              v-for="product in displayProducts"
              :key="product.id"
              :product="product"
              :product-type="activeTab"
              @detail="handleDetail(product)"
              @buy="handleBuy(product)"
            />
          </div>

          <div class="mall-pagination">
            <button class="page-btn page-prev">上一页</button>
            <button class="page-btn page-num active">1</button>
            <button class="page-btn page-num">2</button>
            <button class="page-btn page-num">3</button>
            <button class="page-btn page-num">4</button>
            <button class="page-btn page-num">5</button>
            <span class="page-dots">...</span>
            <button class="page-btn page-num">12</button>
            <button class="page-btn page-next">下一页</button>
            <span class="page-info">共12页，96条数据</span>
          </div>
        </div>
      </div>

      <aside class="mall-aside">
        <div class="aside-card aside-guide">
          <div class="aside-head">
            <h4 class="aside-title">使用指南</h4>
            <a href="#/user-manual" class="aside-more">查看更多</a>
          </div>
          <div class="guide-list">
            <div v-for="(item, idx) in guideList" :key="idx" class="guide-item">
              <span class="guide-dot" :style="{ background: item.color }">
                <svg viewBox="0 0 16 16" fill="none">
                  <path :d="item.icon" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </span>
              <div class="guide-text">
                <div class="guide-name">{{ item.title }}</div>
                <div class="guide-desc">{{ item.desc }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="aside-card aside-announce">
          <div class="aside-head">
            <h4 class="aside-title">公告通知</h4>
          </div>
          <div class="announce-list">
            <div v-for="(ann, idx) in announcements" :key="idx" class="announce-item">
              <span class="ann-date">{{ ann.date }}</span>
              <span class="ann-title" :title="ann.title">{{ ann.title }}</span>
              <span v-if="ann.tag" :class="['ann-tag', ann.tag]">{{ ann.tag }}</span>
            </div>
          </div>
        </div>

        <div class="aside-card aside-service">
          <div class="aside-head">
            <h4 class="aside-title">联系客服</h4>
          </div>
          <div class="service-list">
            <div class="service-item">
              <div class="service-icon-wrap s1">
                <svg viewBox="0 0 22 22" fill="none">
                  <path d="M11 2C6.58 2 3 5.24 3 9.27C3 11.54 4.23 13.54 6.12 14.76L5.36 17.9L8.72 16.34C9.44 16.51 10.2 16.6 11 16.6C15.42 16.6 19 13.36 19 9.33C19 5.3 15.42 2 11 2Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
                </svg>
              </div>
              <div class="service-text">
                <div class="service-name">在线客服</div>
                <div class="service-desc">工作日 9:00 - 18:00 在线</div>
              </div>
              <button class="service-btn">立即咨询</button>
            </div>
            <div class="service-item">
              <div class="service-icon-wrap s2">
                <svg viewBox="0 0 22 22" fill="none">
                  <rect x="4" y="3" width="14" height="16" rx="2" stroke="currentColor" stroke-width="1.8"/>
                  <path d="M4 7H18" stroke="currentColor" stroke-width="1.8"/>
                  <path d="M8 11H14M8 14H12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                </svg>
              </div>
              <div class="service-text">
                <div class="service-name">工单反馈</div>
                <div class="service-desc">24小时内响应您的问题</div>
              </div>
              <button class="service-btn">提交工单</button>
            </div>
            <div class="service-item">
              <div class="service-icon-wrap s3">
                <svg viewBox="0 0 22 22" fill="none">
                  <circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="1.8"/>
                  <path d="M9 9C9 7.9 9.9 7 11 7C12.1 7 13 7.9 13 9C13 10.1 11.6 10.6 11.3 11.3C11.1 11.7 11 12.1 11 12.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                  <circle cx="11" cy="15" r="0.8" fill="currentColor"/>
                </svg>
              </div>
              <div class="service-text">
                <div class="service-name">常见问题</div>
                <div class="service-desc">查看常见问题解答</div>
              </div>
              <button class="service-btn">查看帮助</button>
            </div>
          </div>
        </div>

        <div class="aside-tips">
          <div class="tips-icon-wrap">
            <svg viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
              <path d="M10 6V10.5M10 13.5V14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="tips-content">
            <div class="tips-title">温馨提示</div>
            <div class="tips-text">请在购买后及时查看商品内容，如遇问题请第一时间联系我们！</div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import MallProductCard from '../components/MallProductCard.vue'
import { textProducts, cardProducts } from '../data/mallProducts'

const activeTab = ref('text')
const activeCategory = ref('全部')
const viewMode = ref('grid')

const productTabs = [
  { label: '文本商品', value: 'text' },
  { label: '卡密商品', value: 'card' }
]

const categories = ['全部', '软件工具', '教程资料', '运营营销', '设计素材', '编程开发', '考试学习', '其他']

const displayProducts = computed(() => {
  return activeTab.value === 'text' ? textProducts : cardProducts
})

const guideList = [
  { title: '注册账号', desc: '完成注册并实名认证', color: 'rgba(79,124,255,.92)', icon: 'M4 13C4 10.79 5.79 9 8 9H12M12 9L9.5 6.5M12 9L9.5 11.5' },
  { title: '选择商品', desc: '浏览商品并查看详情', color: 'rgba(99,102,241,.92)', icon: 'M8 6L12 2L16 6M12 2V13' },
  { title: '购买商品', desc: '完成支付自动获取卡密', color: 'rgba(139,92,246,.92)', icon: 'M3 7H17M5 7H15V14C15 14.55 14.55 15 14 15H6C5.45 15 5 14.55 5 14V7Z' },
  { title: '开始使用', desc: '查看订单并使用商品', color: 'rgba(168,85,247,.92)', icon: 'M5 13L8 16L15 9' }
]

const announcements = [
  { date: '07-15', title: '商城上线优惠活动：新用户首单立减5元', tag: 'NEW' },
  { date: '07-14', title: '暑期运营资料包限时特惠，低至3折起', tag: 'HOT' },
  { date: '07-12', title: '新增AI大模型系列教程，持续更新中', tag: 'NEW' },
  { date: '07-10', title: '卡密自动发货系统升级，发货速度提升', tag: '' },
  { date: '07-08', title: '售后客服通道已开通，欢迎反馈问题', tag: '' }
]

function handleDetail(product) {
  console.log('detail', product)
}
function handleBuy(product) {
  console.log('buy', product)
}
</script>

<style scoped>
.mall-page {
  width: 100%;
  min-height: 100%;
  box-sizing: border-box;
}

.mall-main-wrap {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  width: 100%;
}

@media (max-width: 1200px) {
  .mall-main-wrap {
    flex-direction: column;
  }
}

.mall-main {
  flex: 1;
  min-width: 0;
}

.mall-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 16px;
  flex-wrap: wrap;
}

.mall-header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.mall-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, #4F7CFF, #6366F1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 4px 12px rgba(79, 124, 255, .25);
  flex-shrink: 0;
}

.mall-header-icon {
  width: 26px;
  height: 26px;
}

.mall-header-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mall-header-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  line-height: 1.2;
}

.mall-header-desc {
  font-size: 13px;
  color: #64748b;
  margin: 0;
  line-height: 1.5;
}

.mall-stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border-radius: 14px;
  padding: 12px 18px;
  border: 1px solid #e8edf5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, .03);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(79,124,255,.08), rgba(99,102,241,.08));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4F7CFF;
  flex-shrink: 0;
}
.stat-icon svg {
  width: 24px;
  height: 24px;
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.stat-label {
  font-size: 12px;
  color: #94a3b8;
}
.stat-number {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.2;
  letter-spacing: -0.5px;
}
.stat-unit {
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  margin-left: 1px;
}
.stat-hint {
  font-size: 11px;
  color: #94a3b8;
}

.mall-banner {
  background: linear-gradient(120deg, #dbeafe 0%, #e0e7ff 35%, #ede9fe 100%);
  border-radius: 18px;
  padding: 28px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
  position: relative;
  overflow: hidden;
}

.banner-left {
  flex: 1;
  min-width: 0;
}

.banner-title {
  font-size: 26px;
  font-weight: 800;
  margin: 0 0 16px;
  line-height: 1.2;
  letter-spacing: -0.3px;
}
.banner-title-dark {
  color: #1e293b;
}
.banner-title-blue {
  color: #4F7CFF;
}

.banner-points {
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.banner-points li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #475569;
}
.point-check {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #4F7CFF;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.point-check svg {
  width: 11px;
  height: 11px;
}

.banner-illustration {
  position: relative;
  height: 90px;
}

.illus-tag {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 80px;
  height: 54px;
  background: linear-gradient(135deg, #fef3c7, #fbbf24);
  border-radius: 4px 4px 0 0;
  clip-path: polygon(0 12%, 12% 0, 88% 0, 100% 12%, 100% 100%, 0 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 2px 4px 0 rgba(0,0,0,.08);
  transform: rotate(-8deg);
}
.tag-hole {
  position: absolute;
  top: 4px;
  left: 12px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e0e7ff;
}
.tag-hole-r {
  left: auto;
  right: 12px;
}
.tag-text {
  font-size: 11px;
  font-weight: 700;
  color: #92400e;
}
.tag-string {
  position: absolute;
  top: -18px;
  left: 14px;
  width: 2px;
  height: 20px;
  background: #94a3b8;
  border-radius: 1px;
  transform: rotate(10deg);
  transform-origin: bottom;
}
.tag-string-r {
  left: auto;
  right: 14px;
  transform: rotate(-10deg);
}

.illus-cart {
  position: absolute;
  left: 120px;
  bottom: 4px;
}
.cart-handle {
  position: absolute;
  top: -12px;
  left: -18px;
  width: 22px;
  height: 18px;
  border: 3px solid #4F7CFF;
  border-right: none;
  border-bottom: none;
  border-radius: 12px 0 0 0;
}
.cart-basket {
  width: 72px;
  height: 44px;
  background: linear-gradient(135deg, #60a5fa, #4F7CFF);
  border-radius: 6px 6px 10px 10px;
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 4px;
  padding-top: 6px;
}
.basket-item {
  width: 12px;
  border-radius: 3px;
}
.basket-item-1 {
  height: 20px;
  background: #f87171;
  margin-top: 4px;
}
.basket-item-2 {
  height: 26px;
  background: #fbbf24;
}
.basket-item-3 {
  height: 22px;
  background: #34d399;
  margin-top: 2px;
}
.cart-wheel {
  position: absolute;
  bottom: -8px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #1e293b;
  border: 2px solid #fff;
}
.cart-wheel-l {
  left: 12px;
}
.cart-wheel-r {
  right: 12px;
}

.illus-box {
  position: absolute;
  right: 60px;
  bottom: 4px;
  width: 70px;
  height: 56px;
  background: linear-gradient(135deg, #fde68a, #fcd34d);
  border-radius: 4px;
  border: 2px solid #d97706;
}
.box-tape {
  position: absolute;
  background: rgba(239, 68, 68, .8);
}
.box-tape-v {
  left: 50%;
  top: 0;
  bottom: 0;
  width: 6px;
  transform: translateX(-50%);
}
.box-tape-h {
  top: 50%;
  left: -2px;
  right: -2px;
  height: 6px;
  transform: translateY(-50%);
}
.box-flap {
  position: absolute;
  top: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 12px;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  border: 2px solid #d97706;
  border-bottom: none;
  border-radius: 4px 4px 0 0;
}

.illus-spark {
  position: absolute;
  border-radius: 50%;
}
.illus-spark-1 {
  right: 30px;
  top: 10px;
  width: 8px;
  height: 8px;
  background: #818cf8;
  box-shadow: 0 0 0 4px rgba(129,140,248,.2);
}
.illus-spark-2 {
  right: 10px;
  top: 28px;
  width: 6px;
  height: 6px;
  background: #f472b6;
  box-shadow: 0 0 0 3px rgba(244,114,182,.2);
}
.illus-spark-3 {
  left: 200px;
  top: 0;
  width: 5px;
  height: 5px;
  background: #34d399;
  box-shadow: 0 0 0 2px rgba(52,211,153,.2);
}

.banner-right {
  flex-shrink: 0;
  width: 300px;
}

@media (max-width: 900px) {
  .mall-banner {
    flex-direction: column;
    align-items: stretch;
    padding: 24px 20px;
  }
  .banner-right {
    width: 100%;
  }
  .banner-illustration {
    display: none;
  }
}

.notice-card {
  background: rgba(255,255,255,.85);
  backdrop-filter: blur(8px);
  border-radius: 14px;
  padding: 16px 18px;
  border: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 4px 16px rgba(79,124,255,.08);
}
.notice-item {
  padding: 2px 0;
}
.notice-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 12px 0;
}
.notice-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.notice-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.notice-icon svg {
  width: 14px;
  height: 14px;
}
.notice-icon-blue {
  background: rgba(79,124,255,.12);
  color: #4F7CFF;
}
.notice-icon-green {
  background: rgba(16,185,129,.12);
  color: #10b981;
}
.notice-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}
.notice-text {
  font-size: 12px;
  color: #64748b;
  line-height: 1.7;
  margin: 0;
  padding-left: 30px;
}
.text-blue {
  color: #4F7CFF;
  font-weight: 600;
}
.text-red {
  color: #ef4444;
  font-weight: 600;
}

.mall-content-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e8edf5;
  box-shadow: 0 2px 8px rgba(15, 23, 42, .04);
  padding: 16px 20px 20px;
}

.mall-tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 16px;
}
.mall-tab {
  padding: 10px 0;
  font-size: 15px;
  color: #64748b;
  cursor: pointer;
  font-weight: 500;
  position: relative;
  transition: color .2s;
}
.mall-tab.active {
  color: #4F7CFF;
  font-weight: 600;
}
.mall-tab.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: #4F7CFF;
  border-radius: 2px;
}

.mall-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.cat-chip {
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  color: #475569;
  background: #fff;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: all .2s;
  white-space: nowrap;
}
.cat-chip:hover {
  border-color: #c7d2fe;
  color: #4F7CFF;
}
.cat-chip.active {
  background: #4F7CFF;
  color: #fff;
  border-color: #4F7CFF;
  font-weight: 500;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.tool-search {
  position: relative;
  width: 220px;
}
.tool-search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 15px;
  height: 15px;
  color: #94a3b8;
}
.tool-search-input {
  width: 100%;
  height: 34px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 0 10px 0 32px;
  font-size: 13px;
  color: #1e293b;
  outline: none;
  box-sizing: border-box;
  transition: all .2s;
}
.tool-search-input:focus {
  border-color: #4F7CFF;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(79,124,255,.1);
}
.tool-search-input::placeholder {
  color: #94a3b8;
}

.tool-select {
  height: 34px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 0 28px 0 12px;
  font-size: 13px;
  color: #475569;
  outline: none;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
}

.view-switch {
  display: flex;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  height: 34px;
}
.view-btn {
  width: 36px;
  height: 100%;
  border: none;
  background: #fff;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all .15s;
  padding: 0;
}
.view-btn svg {
  width: 16px;
  height: 16px;
}
.view-btn:hover {
  color: #64748b;
}
.view-btn.active {
  color: #4F7CFF;
  background: rgba(79,124,255,.08);
}

.mall-products {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.mall-products.list {
  grid-template-columns: 1fr;
}

@media (max-width: 1700px) {
  .mall-products { grid-template-columns: repeat(4, 1fr); }
}

@media (max-width: 1400px) {
  .mall-products { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 1000px) {
  .mall-products { grid-template-columns: repeat(2, 1fr); }
}

.mall-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding-top: 12px;
  flex-wrap: wrap;
}
.page-btn {
  min-width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: all .2s;
  padding: 0 12px;
}
.page-btn:hover {
  border-color: #c7d2fe;
  color: #4F7CFF;
}
.page-btn.active {
  background: #4F7CFF;
  color: #fff;
  border-color: #4F7CFF;
  font-weight: 600;
}
.page-dots {
  color: #94a3b8;
  font-size: 13px;
  padding: 0 4px;
}
.page-info {
  font-size: 12px;
  color: #94a3b8;
  margin-left: 10px;
}

.mall-aside {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 1200px) {
  .mall-aside {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }
  .aside-card, .aside-tips {
    flex: 1;
    min-width: 260px;
  }
}

.aside-card {
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e8edf5;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, .03);
}
.aside-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.aside-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.aside-more {
  font-size: 12px;
  color: #4F7CFF;
  text-decoration: none;
}

.guide-list {
  display: flex;
  flex-direction: column;
}
.guide-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px dashed #f1f5f9;
}
.guide-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.guide-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.guide-dot svg {
  width: 14px;
  height: 14px;
}
.guide-text {
  flex: 1;
  min-width: 0;
}
.guide-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 2px;
}
.guide-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}

.announce-list {
  display: flex;
  flex-direction: column;
}
.announce-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px dashed #f1f5f9;
  font-size: 12px;
}
.announce-item:last-child {
  border-bottom: none;
}
.ann-date {
  color: #94a3b8;
  font-size: 11px;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.ann-title {
  flex: 1;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}
.ann-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
  flex-shrink: 0;
}
.ann-tag.NEW {
  background: #fff7ed;
  color: #f97316;
}
.ann-tag.HOT {
  background: #fef2f2;
  color: #ef4444;
}

.service-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.service-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  background: #f8fafc;
}
.service-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.service-icon-wrap svg {
  width: 20px;
  height: 20px;
}
.service-icon-wrap.s1 {
  background: rgba(79,124,255,.12);
  color: #4F7CFF;
}
.service-icon-wrap.s2 {
  background: rgba(16,185,129,.12);
  color: #10b981;
}
.service-icon-wrap.s3 {
  background: rgba(245,158,11,.12);
  color: #f59e0b;
}
.service-text {
  flex: 1;
  min-width: 0;
}
.service-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 2px;
}
.service-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.3;
}
.service-btn {
  height: 28px;
  padding: 0 10px;
  border-radius: 7px;
  border: 1px solid #4F7CFF;
  background: #fff;
  color: #4F7CFF;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all .2s;
  white-space: nowrap;
  flex-shrink: 0;
}
.service-btn:hover {
  background: #4F7CFF;
  color: #fff;
}

.aside-tips {
  background: linear-gradient(135deg, #eef2ff, #f5f3ff, #faf5ff);
  border-radius: 14px;
  padding: 14px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border: 1px solid #e0e7ff;
}
.tips-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(99,102,241,.15);
  color: #6366f1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tips-icon-wrap svg {
  width: 15px;
  height: 15px;
}
.tips-content {
  flex: 1;
}
.tips-title {
  font-size: 13px;
  font-weight: 700;
  color: #6366f1;
  margin-bottom: 4px;
}
.tips-text {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
}
</style>
