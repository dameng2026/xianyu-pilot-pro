<template>
  <div class="delivery-mall">
    <!-- 顶部标题区域 -->
    <header class="mall-head">
      <div class="mall-head-title">
        <span class="circle-ico blue-bg mall-head-icon"><Icon name="product" /></span>
        <div>
          <h1>货源商城</h1>
          <p>海量优质虚拟商品资源，自动发货，即买即用</p>
        </div>
      </div>
      <div class="mall-head-stat">
        <span class="circle-ico blue-bg"><Icon name="users" /></span>
        <div class="mall-head-stat-info">
          <span>已购买人数</span>
          <strong>12,458 人</strong>
          <em>昨日新增 326 人</em>
        </div>
      </div>
    </header>

    <div class="mall-grid">
      <!-- 中间主内容区 -->
      <section class="mall-main">
        <!-- 宣传与说明区域 -->
        <div class="mall-banner">
          <div class="mall-banner-left">
            <div class="mall-banner-text">
              <h2>自动发货 · <span class="mall-brand">货源商城</span></h2>
              <ul class="mall-points">
                <li>海量优质资源，持续更新</li>
                <li>自动发货，秒发到手</li>
                <li>安全稳定，售后无忧</li>
              </ul>
              <div class="mall-banner-art">
                <span class="art-box art-box-1"></span>
                <span class="art-box art-box-2"></span>
                <span class="art-tag">自动发货</span>
              </div>
            </div>
            <div class="mall-search">
              <input class="input" placeholder="输入商品名称或关键词" />
              <select class="input mall-search-cat">
                <option>全部分类</option>
                <option v-for="c in mallCategories.slice(1)" :key="c">{{ c }}</option>
              </select>
              <button class="app-btn primary" type="button">
                <Icon name="search" /><span>搜索</span>
              </button>
            </div>
          </div>

          <aside class="mall-banner-right">
            <div class="mall-info-block">
              <div class="mall-info-head">
                <span class="circle-ico blue-bg"><Icon name="help" /></span>
                <b>文本商品说明</b>
              </div>
              <p>本站所有文本商品会一直更新，若出现文本商品不可用情况，可点击<em class="t-blue">投诉</em>，核实后将会<em class="t-red">下架处理</em>，感谢您的监督与支持！</p>
            </div>
            <div class="mall-info-divider"></div>
            <div class="mall-info-block">
              <div class="mall-info-head">
                <span class="circle-ico green-bg"><Icon name="key" /></span>
                <b>卡密商品说明</b>
              </div>
              <p>卡密商品库存实时更新，购买后自动发货，请及时使用。如遇问题可联系客服或提交工单，我们将尽快为您处理！</p>
            </div>
          </aside>
        </div>

        <!-- 商品主体卡片 -->
        <div class="card-panel mall-content">
          <!-- 商品类型切换 -->
          <div class="mall-type-tabs">
            <button class="mall-type-tab active" type="button">文本商品</button>
            <button class="mall-type-tab" type="button">卡密商品</button>
          </div>

          <!-- 筛选与视图工具栏 -->
          <div class="mall-toolbar">
            <div class="mall-cats">
              <button
                v-for="(c, i) in mallCategories"
                :key="c"
                type="button"
                :class="['mall-cat', { active: i === 0 }]"
              >
                {{ c }}
              </button>
            </div>
            <div class="mall-tools">
              <input class="input mall-tool-search" placeholder="搜索商品" />
              <select class="input">
                <option>综合排序</option>
                <option>销量优先</option>
                <option>价格从低到高</option>
                <option>价格从高到低</option>
                <option>最新上架</option>
              </select>
              <button class="mall-view active" type="button" :title="'宫格视图'">
                <Icon name="product" />
              </button>
              <button class="mall-view" type="button" :title="'列表视图'">
                <Icon name="data" />
              </button>
            </div>
          </div>

          <!-- 商品宫格 -->
          <div class="mall-products">
            <MallProductCard
              v-for="p in textProducts"
              :key="p.id"
              :product="p"
              type="text"
            />
          </div>

          <!-- 隐藏预留：卡密商品卡片结构（切换到卡密Tab时展示） -->
          <div v-if="false" class="mall-products">
            <MallProductCard
              v-for="p in cardProducts"
              :key="p.id"
              :product="p"
              type="card"
            />
          </div>

          <!-- 分页 -->
          <div class="mall-pagination">
            <button class="page-no" type="button">上一页</button>
            <button class="page-no active" type="button">1</button>
            <button class="page-no" type="button">2</button>
            <button class="page-no" type="button">3</button>
            <button class="page-no" type="button">4</button>
            <button class="page-no" type="button">5</button>
            <span class="mall-ellipsis">…</span>
            <button class="page-no" type="button">12</button>
            <button class="page-no" type="button">下一页</button>
            <span class="mall-page-total">共12页，96条数据</span>
          </div>
        </div>
      </section>

      <!-- 右侧辅助栏 -->
      <aside class="mall-side">
        <!-- 使用指南 -->
        <div class="card-panel mall-side-card">
          <h3 class="mall-side-title">使用指南</h3>
          <div v-for="g in mallGuides" :key="g.title" class="mall-guide-item">
            <span class="circle-ico blue-bg"><Icon :name="g.icon" /></span>
            <div class="mall-guide-main">
              <b>{{ g.title }}</b>
              <span>{{ g.desc }}</span>
            </div>
          </div>
        </div>

        <!-- 公告通知 -->
        <div class="card-panel mall-side-card">
          <h3 class="mall-side-title">公告通知</h3>
          <div v-for="(a, i) in mallAnnouncements" :key="i" class="mall-notice-item">
            <span class="mall-notice-date">{{ a.date }}</span>
            <span class="mall-notice-text">{{ a.text }}</span>
            <span v-if="a.badge" :class="['mall-notice-badge', a.badge === 'NEW' ? 'new' : 'hot']">{{ a.badge }}</span>
          </div>
        </div>

        <!-- 联系客服 -->
        <div class="card-panel mall-side-card">
          <h3 class="mall-side-title">联系客服</h3>
          <div class="mall-contact-item">
            <div class="mall-contact-main">
              <b>在线客服</b>
              <span>工作日 9:00-22:00 在线</span>
            </div>
            <button class="app-btn mall-contact-btn" type="button">立即咨询</button>
          </div>
          <div class="mall-contact-item">
            <div class="mall-contact-main">
              <b>工单反馈</b>
              <span>提交问题，专人跟进</span>
            </div>
            <button class="app-btn mall-contact-btn" type="button">提交工单</button>
          </div>
          <div class="mall-contact-item">
            <div class="mall-contact-main">
              <b>常见问题</b>
              <span>查看高频问题解答</span>
            </div>
            <button class="app-btn mall-contact-btn" type="button">立即查看</button>
          </div>
        </div>

        <!-- 温馨提示 -->
        <div class="mall-warm-tip">
          <span class="circle-ico warm-icon"><Icon name="bell" /></span>
          <p>请在购买后及时查看商品内容，如遇问题请第一时间联系我们！</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import Icon from '../components/Icon.vue'
import MallProductCard from '../components/MallProductCard.vue'
import {
  textProducts,
  cardProducts,
  mallCategories,
  mallAnnouncements,
  mallGuides
} from '../data/mallProducts.js'
</script>

<style scoped>
.delivery-mall {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 顶部标题区域 */
.mall-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--shadow);
  padding: 18px 22px;
}

.mall-head-title {
  display: flex;
  align-items: center;
  gap: 14px;
}

.mall-head-icon .ui-icon-img {
  width: 30px;
  height: 30px;
}

.mall-head-title h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  color: var(--text);
  letter-spacing: .3px;
}

.mall-head-title p {
  margin: 6px 0 0;
  color: #72809a;
  font-size: 14px;
}

.mall-head-stat {
  display: flex;
  align-items: center;
  gap: 14px;
  background: linear-gradient(135deg, #f3f8ff, #eef4ff);
  border: 1px solid #dbe8fa;
  border-radius: 12px;
  padding: 12px 18px;
  min-width: 280px;
}

.mall-head-stat .circle-ico {
  width: 46px;
  height: 46px;
}

.mall-head-stat .ui-icon-img {
  width: 28px;
  height: 28px;
}

.mall-head-stat-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.mall-head-stat-info span {
  font-size: 12.5px;
  color: #72809a;
}

.mall-head-stat-info strong {
  font-size: 22px;
  color: var(--text);
  font-weight: 800;
  margin: 2px 0;
}

.mall-head-stat-info em {
  font-style: normal;
  font-size: 12px;
  color: var(--green);
}

/* 主网格：中间内容 + 右侧辅助栏 */
.mall-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  align-items: start;
}

.mall-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

/* 宣传与说明区域 */
.mall-banner {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr);
  gap: 16px;
  height: 220px;
}

.mall-banner-left {
  position: relative;
  border-radius: 14px;
  padding: 22px 24px;
  overflow: hidden;
  background: linear-gradient(120deg, #eef2ff 0%, #e7ecff 45%, #e0e7ff 100%);
  border: 1px solid #dfe5fb;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.mall-banner-text {
  position: relative;
  z-index: 1;
}

.mall-banner-text h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #2b3358;
  letter-spacing: .3px;
}

.mall-brand {
  color: var(--primary);
}

.mall-points {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mall-points li {
  position: relative;
  padding-left: 18px;
  color: #41506c;
  font-size: 14px;
  font-weight: 600;
}

.mall-points li::before {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--primary);
  box-shadow: 0 0 0 3px rgba(13, 107, 255, .15);
}

.mall-banner-art {
  position: absolute;
  right: 18px;
  top: 14px;
  width: 150px;
  height: 80px;
}

.art-box {
  position: absolute;
  border-radius: 16px;
  background: linear-gradient(135deg, #b8c8ff, #6a8dff);
  box-shadow: 0 12px 24px rgba(13, 107, 255, .22);
}

.art-box-1 {
  width: 92px;
  height: 58px;
  right: 30px;
  top: 4px;
  transform: rotate(-8deg);
}

.art-box-2 {
  width: 70px;
  height: 46px;
  right: 0;
  top: 32px;
  background: linear-gradient(135deg, #c9b6ff, #8b5cf6);
  transform: rotate(10deg);
  opacity: .92;
}

.art-tag {
  position: absolute;
  left: 8px;
  bottom: -2px;
  height: 24px;
  padding: 0 10px;
  border-radius: 7px;
  background: #fff;
  color: var(--primary);
  font-size: 12px;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  box-shadow: 0 6px 16px rgba(31, 53, 94, .14);
}

.mall-search {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 8px;
  align-items: center;
}

.mall-search .input {
  flex: 1;
  background: #fff;
}

.mall-search-cat {
  min-width: 130px;
  max-width: 150px;
}

.mall-search .app-btn {
  height: 38px;
  min-width: 88px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.mall-search .app-btn .ui-icon-img {
  width: 16px;
  height: 16px;
  filter: brightness(0) invert(1);
}

/* 右侧说明卡片 */
.mall-banner-right {
  background: rgba(255, 255, 255, .82);
  backdrop-filter: blur(4px);
  border: 1px solid #e3e9fb;
  border-radius: 14px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.mall-info-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.mall-info-head .circle-ico {
  width: 34px;
  height: 34px;
}

.mall-info-head .ui-icon-img {
  width: 20px;
  height: 20px;
}

.mall-info-head b {
  font-size: 15px;
  color: var(--text);
}

.mall-info-block p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: #5f6f8b;
}

.mall-info-block .t-blue {
  font-style: normal;
  color: var(--primary);
  font-weight: 700;
}

.mall-info-block .t-red {
  font-style: normal;
  color: #ff3b30;
  font-weight: 700;
}

.mall-info-divider {
  height: 1px;
  background: #eaeff8;
  margin: 14px 0;
}

/* 商品主体卡片 */
.mall-content {
  padding: 16px 18px 20px;
}

.mall-type-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 14px;
}

.mall-type-tab {
  height: 42px;
  padding: 0 18px;
  border: 0;
  background: transparent;
  color: #6c7890;
  font-size: 15px;
  font-weight: 650;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}

.mall-type-tab.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  font-weight: 800;
}

/* 工具栏 */
.mall-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.mall-cats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.mall-cat {
  height: 32px;
  padding: 0 14px;
  border: 1px solid var(--line);
  background: #fff;
  color: #41506c;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s ease;
}

.mall-cat:hover {
  border-color: #bcd7ff;
  color: var(--primary);
}

.mall-cat.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  box-shadow: 0 6px 14px rgba(13, 107, 255, .22);
}

.mall-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mall-tool-search {
  width: 160px;
}

.mall-tools .input {
  height: 34px;
}

.mall-view {
  width: 34px;
  height: 34px;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  color: #6c7890;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.mall-view .ui-icon-img {
  width: 18px;
  height: 18px;
}

.mall-view.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.mall-view.active .ui-icon-img {
  filter: brightness(0) invert(1);
}

/* 商品宫格 */
.mall-products {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

/* 分页 */
.mall-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 22px;
  flex-wrap: wrap;
}

.mall-pagination .page-no {
  min-width: 34px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid #e4ebf5;
  background: #fff;
  border-radius: 8px;
  color: #41506c;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.mall-pagination .page-no.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.mall-ellipsis {
  color: #98a4b7;
  padding: 0 2px;
}

.mall-page-total {
  margin-left: 10px;
  color: #72809a;
  font-size: 13px;
}

/* 右侧辅助栏 */
.mall-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.mall-side-card {
  padding: 16px 18px;
}

.mall-side-title {
  margin: 0 0 14px;
  font-size: 16px;
  font-weight: 800;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
}

.mall-side-title::before {
  content: "";
  width: 4px;
  height: 15px;
  border-radius: 3px;
  background: var(--primary);
}

/* 使用指南 */
.mall-guide-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f0f4fa;
}

.mall-guide-item:last-child {
  border-bottom: 0;
}

.mall-guide-item .circle-ico {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
}

.mall-guide-item .ui-icon-img {
  width: 20px;
  height: 20px;
}

.mall-guide-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.mall-guide-main b {
  font-size: 14px;
  color: var(--text);
}

.mall-guide-main span {
  font-size: 12px;
  color: #8a96aa;
  line-height: 1.5;
}

/* 公告通知 */
.mall-notice-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid #f0f4fa;
}

.mall-notice-item:last-child {
  border-bottom: 0;
}

.mall-notice-date {
  color: #98a4b7;
  font-size: 12px;
  font-weight: 600;
  flex: 0 0 auto;
}

.mall-notice-text {
  flex: 1;
  font-size: 13px;
  color: #41506c;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mall-notice-badge {
  height: 18px;
  padding: 0 6px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
}

.mall-notice-badge.new {
  background: #edf5ff;
  color: var(--primary);
}

.mall-notice-badge.hot {
  background: #fff0f1;
  color: #ff5b61;
}

/* 联系客服 */
.mall-contact-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 11px 0;
  border-bottom: 1px solid #f0f4fa;
}

.mall-contact-item:last-child {
  border-bottom: 0;
}

.mall-contact-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.mall-contact-main b {
  font-size: 14px;
  color: var(--text);
}

.mall-contact-main span {
  font-size: 12px;
  color: #8a96aa;
}

.mall-contact-btn {
  height: 32px;
  min-width: 0;
  padding: 0 12px;
  border-radius: 7px;
  border: 1px solid var(--primary);
  background: #fff;
  color: var(--primary);
  font-size: 12.5px;
  font-weight: 700;
  box-shadow: none;
  flex: 0 0 auto;
}

/* 温馨提示 */
.mall-warm-tip {
  display: flex;
  align-items: center;
  gap: 12px;
  background: linear-gradient(135deg, #eef2ff, #f3eeff);
  border: 1px solid #e0e6fb;
  border-radius: 14px;
  padding: 16px 18px;
}

.mall-warm-tip .warm-icon {
  width: 38px;
  height: 38px;
  background: #fff;
  color: var(--primary);
  flex: 0 0 auto;
}

.mall-warm-tip .ui-icon-img {
  width: 22px;
  height: 22px;
}

.mall-warm-tip p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #41506c;
  font-weight: 600;
}

/* 响应式：窄屏堆叠 */
@media (max-width: 1500px) {
  .mall-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .mall-products {
    grid-template-columns: repeat(3, 1fr);
  }

  .mall-banner {
    grid-template-columns: 1fr;
    height: auto;
  }

  .mall-banner-right {
    order: -1;
  }
}

@media (max-width: 1100px) {
  .mall-products {
    grid-template-columns: repeat(2, 1fr);
  }

  .mall-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .mall-head-stat {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .mall-products {
    grid-template-columns: 1fr;
  }

  .mall-cats,
  .mall-tools {
    width: 100%;
  }

  .mall-tool-search {
    flex: 1;
    width: auto;
  }
}
</style>
