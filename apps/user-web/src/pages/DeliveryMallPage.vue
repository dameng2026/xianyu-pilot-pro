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
              @click="selectTab(tab.value)"
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
                @click="selectCategory(cat)"
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
                <input type="text" v-model="searchKeyword" @input="onSearchInput" placeholder="搜索商品名称、关键词" class="tool-search-input">
              </div>
              <select v-model="sortOrder" @change="onSortChange" class="tool-select">
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

          <div v-if="loading" class="mall-loading">加载中...</div>
          <div v-else-if="displayProducts.length === 0" class="mall-empty">暂无商品</div>
          <div v-else :class="['mall-products', viewMode]">
            <MallProductCard
              v-for="product in displayProducts"
              :key="product.id"
              :product="product"
              :product-type="activeTab"
              @detail="handleDetail(product)"
              @buy="handleBuy(product)"
            />
          </div>

          <div v-if="totalPages > 1" class="mall-pagination">
            <button class="page-btn page-prev" :disabled="pageNum === 1" @click="goToPage(pageNum - 1)">上一页</button>
            <template v-for="(p, idx) in pageNumbers" :key="idx">
              <span v-if="p === '...'" class="page-dots">...</span>
              <button v-else :class="['page-btn page-num', { active: pageNum === p }]" @click="goToPage(p)">{{ p }}</button>
            </template>
            <button class="page-btn page-next" :disabled="pageNum === totalPages" @click="goToPage(pageNum + 1)">下一页</button>
            <span class="page-info">共{{ totalPages }}页，{{ totalItems }}条数据</span>
          </div>
        </div>
      </div>

      <!-- 在线客服弹窗 -->
      <div v-if="serviceModalVisible" class="mall-modal-mask" @click.self="serviceModalVisible = false">
        <div class="mall-modal-dialog">
          <div class="mall-modal-header">
            <h3 class="mall-modal-title">联系客服</h3>
            <button type="button" class="mall-modal-close" @click="serviceModalVisible = false">×</button>
          </div>
          <div class="mall-modal-body">
            <div v-if="!hasServiceInfo" class="mall-modal-empty">暂无客服配置信息</div>
            <template v-else>
              <div v-if="serviceConfig.servicePhone" class="mall-modal-row">
                <div class="mall-modal-row-label">客服电话</div>
                <div class="mall-modal-row-value">{{ serviceConfig.servicePhone }}</div>
              </div>
              <div v-if="serviceConfig.serviceEmail" class="mall-modal-row">
                <div class="mall-modal-row-label">客服邮箱</div>
                <div class="mall-modal-row-value">{{ serviceConfig.serviceEmail }}</div>
              </div>
              <div v-if="serviceConfig.companyAddress" class="mall-modal-row">
                <div class="mall-modal-row-label">公司地址</div>
                <div class="mall-modal-row-value">{{ serviceConfig.companyAddress }}</div>
              </div>
              <div v-if="serviceConfig.wechatOfficial" class="mall-modal-row">
                <div class="mall-modal-row-label">公众号</div>
                <div class="mall-modal-row-value">{{ serviceConfig.wechatOfficial }}</div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 工单反馈弹窗 -->
      <div v-if="feedbackModalVisible" class="mall-modal-mask" @click.self="closeFeedbackModal">
        <div class="mall-modal-dialog">
          <div class="mall-modal-header">
            <h3 class="mall-modal-title">提交工单</h3>
            <button type="button" class="mall-modal-close" @click="closeFeedbackModal">×</button>
          </div>
          <div class="mall-modal-body">
            <div class="mall-form-row">
              <label class="mall-form-label">反馈类型</label>
              <select v-model="feedbackForm.type" class="mall-form-input">
                <option v-for="opt in feedbackTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
            <div class="mall-form-row">
              <label class="mall-form-label">标题</label>
              <input v-model="feedbackForm.title" type="text" class="mall-form-input" placeholder="请输入标题" maxlength="60" />
            </div>
            <div class="mall-form-row">
              <label class="mall-form-label">问题描述</label>
              <textarea v-model="feedbackForm.content" class="mall-form-input mall-form-textarea" placeholder="请详细描述您遇到的问题" rows="4" maxlength="500"></textarea>
            </div>
            <div class="mall-form-row">
              <label class="mall-form-label">联系方式（可选）</label>
              <input v-model="feedbackForm.contact" type="text" class="mall-form-input" placeholder="QQ / 微信 / 邮箱" maxlength="60" />
            </div>
            <div v-if="feedbackError" class="mall-form-error">{{ feedbackError }}</div>
            <button type="button" class="mall-form-submit" :disabled="feedbackSubmitting" @click="submitFeedbackForm">
              {{ feedbackSubmitting ? '提交中...' : '提交工单' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 常见问题弹窗 -->
      <div v-if="faqModalVisible" class="mall-modal-mask" @click.self="faqModalVisible = false">
        <div class="mall-modal-dialog">
          <div class="mall-modal-header">
            <h3 class="mall-modal-title">常见问题</h3>
            <button type="button" class="mall-modal-close" @click="faqModalVisible = false">×</button>
          </div>
          <div class="mall-modal-body">
            <div v-if="faqLoading" class="mall-modal-empty">加载中...</div>
            <div v-else-if="faqs.length === 0" class="mall-modal-empty">暂无常见问题</div>
            <div v-else class="mall-faq-list">
              <div v-for="(faq, idx) in faqs" :key="idx" class="mall-faq-item">
                <button type="button" class="mall-faq-question" @click="toggleFaq(idx)">
                  <span class="mall-faq-q-text">{{ faqQuestion(faq) }}</span>
                  <span class="mall-faq-arrow" :class="{ open: openFaqIndex === idx }">›</span>
                </button>
                <div v-if="openFaqIndex === idx" class="mall-faq-answer">{{ faqAnswer(faq) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 支付弹窗 -->
      <div v-if="payModalVisible" class="mall-modal-mask" @click.self="closePayModal">
        <div class="mall-modal-dialog mall-pay-dialog">
          <div class="mall-modal-header">
            <h3 class="mall-modal-title">商品支付</h3>
            <button type="button" class="mall-modal-close" @click="closePayModal">×</button>
          </div>
          <div class="mall-modal-body">
            <div v-if="payStep === 'select'">
              <div class="mall-pay-product">
                <div class="mall-pay-product-title">{{ currentPayProduct?.title }}</div>
                <div class="mall-pay-product-price"><em>¥</em>{{ payAmountYuan }}</div>
              </div>
              <div class="mall-form-row">
                <label class="mall-form-label">支付方式</label>
                <div class="mall-pay-methods">
                  <button
                    v-for="m in paymentMethods"
                    :key="m.channelType"
                    type="button"
                    :class="['mall-pay-method', { active: payMethod === m.channelType }]"
                    @click="payMethod = m.channelType"
                  >{{ methodLabel(m) }}</button>
                </div>
              </div>
              <div v-if="payError" class="mall-form-error">{{ payError }}</div>
              <button type="button" class="mall-form-submit" :disabled="paySubmitting || !payMethod" @click="createMallOrder">
                {{ paySubmitting ? '正在创建订单...' : '确认支付' }}
              </button>
            </div>
            <div v-else-if="payStep === 'qr'">
              <div class="mall-pay-product">
                <div class="mall-pay-product-title">{{ currentPayProduct?.title }}</div>
                <div class="mall-pay-product-price"><em>¥</em>{{ payAmountYuan }}</div>
              </div>
              <div class="mall-pay-qr-wrap">
                <img v-if="currentOrder?.qrImage" :src="currentOrder.qrImage" alt="支付二维码" class="mall-pay-qr-img" />
                <div v-else class="mall-pay-qr-unavailable">二维码不可用</div>
              </div>
              <div class="mall-pay-countdown" v-if="payCountdownSeconds > 0">剩余支付时间：{{ payCountdownText }}</div>
              <div v-if="payError" class="mall-form-error">{{ payError }}</div>
              <div class="mall-pay-tip">请使用对应 APP 扫描二维码完成支付，支付成功后将自动刷新</div>
              <button type="button" class="mall-form-submit mall-form-submit-outline" :disabled="payChecking" @click="checkPaymentPaid">
                {{ payChecking ? '正在查询...' : '我已完成支付' }}
              </button>
            </div>
            <div v-else-if="payStep === 'success'" class="mall-pay-success">
              <div class="mall-pay-success-icon">✓</div>
              <h3>支付成功</h3>
              <p>{{ currentPayProduct?.title }} 已完成支付</p>
              <button type="button" class="mall-form-submit" @click="closePayModal">完成</button>
            </div>
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
              <button class="service-btn" @click="openServiceModal">立即咨询</button>
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
              <button class="service-btn" @click="openFeedbackModal">提交工单</button>
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
              <button class="service-btn" @click="openFaqModal">查看帮助</button>
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

    <!-- 商品详情弹窗（上架该商品入口） -->
    <div v-if="detailModalVisible" class="mall-modal-mask" @click.self="closeDetailModal">
      <div class="mall-modal-dialog mall-detail-dialog">
        <div class="mall-modal-header">
          <h3 class="mall-modal-title">商品详情</h3>
          <button type="button" class="mall-modal-close" @click="closeDetailModal">×</button>
        </div>
        <div class="mall-modal-body">
          <div v-if="detailLoading" class="mall-modal-empty">加载中...</div>
          <template v-else-if="detailProduct">
            <div class="detail-cover-wrap">
              <img v-if="detailCoverUrl" :src="detailCoverUrl" alt="商品封面图" class="detail-cover-img" />
              <div v-else class="detail-cover-placeholder">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <path d="M21 15l-5-5L5 21"/>
                </svg>
                <span>暂无封面图</span>
              </div>
              <span v-if="detailIsText" class="detail-type-tag detail-type-text">文本商品</span>
              <span v-else-if="detailIsCard" class="detail-type-tag detail-type-card">卡密商品</span>
            </div>

            <div class="detail-info-section">
              <div class="detail-info-label">商品标题</div>
              <div class="detail-info-value detail-title-value">{{ detailProduct.title || '-' }}</div>
            </div>

            <div v-if="detailProduct.subtitle" class="detail-info-section">
              <div class="detail-info-label">介绍</div>
              <div class="detail-info-value">{{ detailProduct.subtitle }}</div>
            </div>

            <div v-if="detailProduct.copy" class="detail-info-section">
              <div class="detail-info-label">文案</div>
              <div class="detail-info-value detail-copy-text">{{ detailProduct.copy }}</div>
            </div>

            <div class="detail-info-grid">
              <div class="detail-info-cell">
                <div class="detail-info-label">价格</div>
                <div class="detail-info-value detail-price-value"><em>¥</em>{{ detailPriceDisplay }}</div>
              </div>
              <div class="detail-info-cell">
                <div class="detail-info-label">创建时间</div>
                <div class="detail-info-value">{{ detailCreateTimeDisplay }}</div>
              </div>
              <div class="detail-info-cell">
                <div class="detail-info-label">购买人数</div>
                <div class="detail-info-value">{{ detailBoughtDisplay }} 人</div>
              </div>
            </div>

            <!-- 文本商品精美提示 -->
            <div v-if="detailIsText" class="detail-text-product-tip">
              <div class="detail-tip-icon">
                <svg viewBox="0 0 20 20" fill="none">
                  <path d="M5 10C5 7.23858 7.23858 5 10 5C12.7614 5 15 7.23858 15 10C15 12.7614 12.7614 15 10 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  <path d="M10 8V10.5L11.5 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </div>
              <div class="detail-tip-content">
                <div class="detail-tip-title">本站点货源商城文本货源</div>
                <div class="detail-tip-desc">一直更新维护，后续无需担心链接失效</div>
              </div>
            </div>

            <div v-if="detailError" class="detail-error-tip">{{ detailError }}</div>

            <!-- 操作按钮区域 -->
            <div class="detail-action-area">
              <template v-if="!detailPurchased">
                <!-- 未购买：展示支付流程提示 + 立即支付按钮 -->
                <div class="detail-flow-tip">
                  <div class="flow-tip-label">支付后流程</div>
                  <div class="flow-tip-chain">
                    <span class="flow-step-chip">支付</span>
                    <span class="flow-arrow">→</span>
                    <span class="flow-step-chip">商家发布</span>
                    <span class="flow-arrow">→</span>
                    <span class="flow-step-chip">AI 改写</span>
                    <span class="flow-arrow">→</span>
                    <span class="flow-step-chip">AI 生图</span>
                    <span class="flow-arrow">→</span>
                    <span class="flow-step-chip">配置</span>
                    <span class="flow-arrow">→</span>
                    <span class="flow-step-chip">发布</span>
                  </div>
                </div>
                <button type="button" class="detail-pay-btn" @click="handleDetailPay">
                  <span class="detail-pay-btn-icon">
                    <svg viewBox="0 0 20 20" fill="none">
                      <path d="M3 6C3 4.89543 3.89543 4 5 4H15C16.1046 4 17 4.89543 17 6V14C17 15.1046 16.1046 16 15 16H5C3.89543 16 3 15.1046 3 14V6Z" stroke="currentColor" stroke-width="1.5"/>
                      <path d="M3 10H17" stroke="currentColor" stroke-width="1.5"/>
                    </svg>
                  </span>
                  立即支付 ¥{{ detailPriceDisplay }}
                </button>
              </template>
              <template v-else>
                <!-- 已购买：展示开始上架 + 一键上架按钮 -->
                <div class="detail-purchased-tip">
                  <svg viewBox="0 0 20 20" fill="none">
                    <circle cx="10" cy="10" r="8" fill="#16bf78" fill-opacity="0.15"/>
                    <path d="M6 10L9 13L14 7" stroke="#16bf78" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <span>您已购买此商品，可以开始上架到闲鱼</span>
                </div>
                <div class="detail-list-btns">
                  <button type="button" class="detail-list-btn detail-list-btn-primary" @click="openListFlow(false)">
                    开始上架
                  </button>
                  <button type="button" class="detail-list-btn detail-list-btn-auto" @click="openListFlow(true)">
                    <svg viewBox="0 0 20 20" fill="none">
                      <path d="M5 10L8 13L15 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M10 3V5M10 15V17M3 10H5M15 10H17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    一键上架
                  </button>
                </div>
              </template>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- 上架流程弹窗（4 步：AI改写 → AI生图 → 配置 → 发布） -->
    <div v-if="listFlowVisible" class="mall-modal-mask" @click.self="closeListFlow">
      <div class="mall-modal-dialog mall-listflow-dialog">
        <div class="mall-modal-header">
          <h3 class="mall-modal-title">{{ listFlowAuto ? '一键上架' : '上架到闲鱼' }}</h3>
          <button type="button" class="mall-modal-close" @click="closeListFlow" :disabled="listFlowAutoRunning || rewriteLoading || imageLoading || publishing">×</button>
        </div>
        <div class="mall-modal-body">
          <!-- 步骤指示器 -->
          <div class="listflow-steps">
            <div :class="['listflow-step', { active: listFlowStep >= 1, current: listFlowStep === 1 }]">
              <span class="step-num">1</span><span class="step-text">AI 改写</span>
            </div>
            <span class="step-line" :class="{ active: listFlowStep > 1 }"></span>
            <div :class="['listflow-step', { active: listFlowStep >= 2, current: listFlowStep === 2 }]">
              <span class="step-num">2</span><span class="step-text">AI 生图</span>
            </div>
            <span class="step-line" :class="{ active: listFlowStep > 2 }"></span>
            <div :class="['listflow-step', { active: listFlowStep >= 3, current: listFlowStep === 3 }]">
              <span class="step-num">3</span><span class="step-text">配置</span>
            </div>
            <span class="step-line" :class="{ active: listFlowStep > 3 }"></span>
            <div :class="['listflow-step', { active: listFlowStep >= 4, current: listFlowStep === 4 }]">
              <span class="step-num">4</span><span class="step-text">发布</span>
            </div>
          </div>

          <div v-if="listFlowError" class="listflow-error-tip">{{ listFlowError }}</div>
          <div v-if="listFlowMessage" class="listflow-message-tip">{{ listFlowMessage }}</div>

          <!-- Step 1: AI 改写 -->
          <div v-show="listFlowStep === 1" class="listflow-step-panel">
            <div class="listflow-section">
              <div class="listflow-section-title">AI 改写</div>
              <p class="listflow-section-desc">根据商品标题与商品文案，AI 自动生成新的标题与正文，作为发布与生图的依据。</p>
              <div v-if="aiStatusLoading" class="listflow-status">AI 改写状态检测中...</div>
              <div v-else-if="!listFlowCanRewrite" class="listflow-status listflow-status-warn">
                {{ aiStatusLoadError || '平台暂未开放 AI 改写功能，无法继续' }}
              </div>
              <div class="listflow-form-row">
                <label>改写风格</label>
                <select v-model="rewriteStyle" class="listflow-input">
                  <option value="friendly">口语化风格</option>
                  <option value="concise">简洁风格</option>
                  <option value="click">吸引眼球风格</option>
                </select>
              </div>
              <div class="listflow-form-row">
                <label>新标题</label>
                <input v-model="rewriteTitle" type="text" class="listflow-input" maxlength="30" placeholder="AI 改写后的标题（可手动修改）" />
                <span class="char-count">{{ rewriteTitle.length }}/30</span>
              </div>
              <div class="listflow-form-row">
                <label>新正文</label>
                <textarea v-model="rewriteDescription" class="listflow-input listflow-textarea" rows="5" placeholder="AI 改写后的正文（可手动修改）"></textarea>
              </div>
            </div>
            <div class="listflow-step-footer">
              <button type="button" class="listflow-btn listflow-btn-ghost" @click="closeListFlow" :disabled="listFlowAutoRunning">取消</button>
              <button type="button" class="listflow-btn listflow-btn-primary" :disabled="rewriteLoading || listFlowAutoRunning || !listFlowCanRewrite" @click="handleRewriteAction">
                {{ rewriteLoading ? 'AI 改写中...' : 'AI 改写' }}
              </button>
              <button type="button" class="listflow-btn listflow-btn-secondary" :disabled="listFlowAutoRunning || rewriteLoading" @click="listFlowGotoStep(2)">下一步</button>
            </div>
          </div>

          <!-- Step 2: AI 生图 -->
          <div v-show="listFlowStep === 2" class="listflow-step-panel">
            <div class="listflow-section">
              <div class="listflow-section-title">AI 生图</div>
              <p class="listflow-section-desc">根据上一步生成的新标题与正文，AI 自动生成商品封面图。</p>
              <div v-if="imageStatusLoading" class="listflow-status">生图状态检测中...</div>
              <div v-else-if="!listFlowCanGenImage" class="listflow-status listflow-status-warn">
                {{ imageStatusLoadError || '平台暂未开放生图功能，请稍后再试' }}
              </div>
              <div class="listflow-form-row">
                <label>生图模型</label>
                <select v-model="selectedModelKey" class="listflow-input" :disabled="!availableImageModels.length">
                  <option value="" :disabled="true">{{ availableImageModels.length ? '请选择模型' : '暂无可用模型' }}</option>
                  <option v-for="m in availableImageModels" :key="m.moduleKey" :value="m.moduleKey">{{ m.name || m.moduleKey }}</option>
                </select>
              </div>
              <div v-if="generatedImages.length" class="listflow-image-grid">
                <div v-for="(img, idx) in generatedImages" :key="img.url || img.b64Json || idx" class="listflow-image-item">
                  <img :src="imgUrl(img)" alt="AI 生成图片" />
                </div>
              </div>
              <div v-else-if="!imageLoading" class="listflow-image-empty">
                暂未生成图片，点击下方按钮生成
              </div>
            </div>
            <div class="listflow-step-footer">
              <button type="button" class="listflow-btn listflow-btn-ghost" @click="listFlowGotoStep(1)" :disabled="listFlowAutoRunning">上一步</button>
              <button type="button" class="listflow-btn listflow-btn-primary" :disabled="imageLoading || listFlowAutoRunning || !listFlowCanGenImage" @click="handleGenerateImagesAction">
                {{ imageLoading ? '生成中（约 2-3 分钟）...' : '生成图片' }}
              </button>
              <button type="button" class="listflow-btn listflow-btn-secondary" :disabled="listFlowAutoRunning || imageLoading || !generatedImages.length" @click="listFlowGotoStep(3)">下一步</button>
            </div>
          </div>

          <!-- Step 3: 配置 -->
          <div v-show="listFlowStep === 3" class="listflow-step-panel">
            <div class="listflow-section">
              <div class="listflow-section-title">配置发布信息</div>
              <div class="listflow-form-row">
                <label>发布账号</label>
                <div class="listflow-account-info">
                  <select v-model="selectedAccountId" class="listflow-input">
                    <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.nickname || a.displayName || a.externalUid || ('账号' + a.id) }}</option>
                  </select>
                  <span v-if="accountLevelHint" class="listflow-hint" :class="{ 'listflow-hint-warn': !isFishShopAccount }">{{ accountLevelHint }}</span>
                </div>
              </div>
              <div class="listflow-form-row">
                <label>发布价格（元）</label>
                <input v-model="configPrice" type="text" class="listflow-input" placeholder="请输入发布价格" />
              </div>
              <div class="listflow-form-row">
                <label>库存</label>
                <div class="listflow-stock-info">
                  <span class="listflow-stock-value">{{ stockDisplayText }}</span>
                  <span v-if="stockStrategyHint" class="listflow-hint">{{ stockStrategyHint }}</span>
                </div>
              </div>
              <div class="listflow-form-row">
                <label>发布位置</label>
                <div class="listflow-address-area">
                  <PublishAddressCascader v-model="configAddress" clearable />
                  <span v-if="!listFlowAddressComplete" class="listflow-hint listflow-hint-warn">请完成省、市、区选择</span>
                  <span v-else class="listflow-hint listflow-hint-success">位置已配置</span>
                </div>
              </div>
              <div class="listflow-form-row">
                <label>分类</label>
                <input v-model="configCategory" type="text" class="listflow-input" placeholder="商品分类（可手动修改）" />
              </div>
            </div>
            <div class="listflow-step-footer">
              <button type="button" class="listflow-btn listflow-btn-ghost" @click="listFlowGotoStep(2)" :disabled="listFlowAutoRunning">上一步</button>
              <button type="button" class="listflow-btn listflow-btn-secondary" :disabled="listFlowAutoRunning" @click="listFlowGotoStep(4)">下一步</button>
            </div>
          </div>

          <!-- Step 4: 发布 -->
          <div v-show="listFlowStep === 4" class="listflow-step-panel">
            <div class="listflow-section">
              <div class="listflow-section-title">确认发布</div>
              <div class="listflow-summary">
                <div class="listflow-summary-row"><span>发布账号</span><b>{{ selectedAccount?.nickname || selectedAccount?.displayName || selectedAccount?.externalUid || '-' }}</b></div>
                <div class="listflow-summary-row"><span>商品标题</span><b>{{ rewriteTitle || '-' }}</b></div>
                <div class="listflow-summary-row"><span>发布价格</span><b class="listflow-price">¥{{ configPrice || '-' }}</b></div>
                <div class="listflow-summary-row"><span>库存</span><b>{{ stockDisplayText }}</b></div>
                <div class="listflow-summary-row"><span>发布位置</span><b>{{ listFlowAddressComplete ? '已配置' : '未配置' }}</b></div>
                <div class="listflow-summary-row"><span>图片数量</span><b>{{ generatedImages.length }} 张</b></div>
              </div>
              <div v-if="!listFlowAddressComplete" class="listflow-status listflow-status-warn">
                发布位置未配置，请返回配置步骤完成省市区选择
              </div>
            </div>
            <div class="listflow-step-footer">
              <button type="button" class="listflow-btn listflow-btn-ghost" @click="listFlowGotoStep(3)" :disabled="listFlowAutoRunning || publishing">上一步</button>
              <button type="button" class="listflow-btn listflow-btn-primary" :disabled="publishing || listFlowAutoRunning || !listFlowAddressComplete" @click="handlePublishAction">
                {{ publishing ? '发布中...' : '确认发布' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import MallProductCard from '../components/MallProductCard.vue'
import PublishAddressCascader from '../components/PublishAddressCascader.vue'
import { getMallProducts, getMallCategories, getMallFaqs, getMallProductDetail, purchaseMallProduct, getMallServiceConfig } from '../api/mall.js'
import { submitFeedback } from '../api/feedback.js'
import { getPaymentMethods, getPaymentOrder, closePaymentOrder } from '../api/payment.js'
import { rewriteOpportunity, getOpportunityAiStatus, getOpportunityImageStatus, getOpportunityImageModels, generateOpportunityImages } from '../api/opportunity.js'
import { ensureAiTokenBalance } from '../utils/aiTokenGuard.js'
import { getLiteAccounts, checkAccountAuth } from '../api/accounts.js'
import { publishItem } from '../api/items.js'
import { getDeliverySources, applyDeliverySourceToGoods, getDeliverySourceByMallProduct } from '../api/autoDelivery.js'
import { accountAuthUsable, pickPreferredAccount, accountLoginHint } from '../utils/accountAuth.js'
import { isPublishAddressComplete, normalizePublishAddress } from '../utils/publishAddress.js'
import { friendlyError } from '../utils/friendlyError.js'
import { getPublishAddressHistory } from '../api/publishAddress.js'

const activeTab = ref('text')
const activeCategory = ref('全部')
const viewMode = ref('grid')
const searchKeyword = ref('')
const sortOrder = ref('')

const productTabs = [
  { label: '文本商品', value: 'text' },
  { label: '卡密商品', value: 'card' }
]

const categories = ref(['全部'])
const products = ref([])
const loading = ref(false)
const pageNum = ref(1)
const pageSize = 20
const totalPages = ref(1)
const totalItems = ref(0)

const displayProducts = computed(() => products.value)

const guideList = [
  { title: '注册账号', desc: '完成注册并实名认证', color: 'rgba(79,124,255,.92)', icon: 'M4 13C4 10.79 5.79 9 8 9H12M12 9L9.5 6.5M12 9L9.5 11.5' },
  { title: '选择商品', desc: '浏览商品并查看详情', color: 'rgba(99,102,241,.92)', icon: 'M8 6L12 2L16 6M12 2V13' },
  { title: '购买商品', desc: '完成支付自动获取卡密', color: 'rgba(139,92,246,.92)', icon: 'M3 7H17M5 7H15V14C15 14.55 14.55 15 14 15H6C5.45 15 5 14.55 5 14V7Z' },
  { title: '开始使用', desc: '查看订单并使用商品', color: 'rgba(168,85,247,.92)', icon: 'M5 13L8 16L15 9' }
]

// ===== 商品列表加载 =====
async function loadProducts() {
  loading.value = true
  try {
    const params = {
      type: activeTab.value,
      page: pageNum.value,
      pageSize
    }
    if (activeCategory.value && activeCategory.value !== '全部') {
      params.category = activeCategory.value
    }
    const kw = searchKeyword.value.trim()
    if (kw) params.keyword = kw
    if (sortOrder.value) params.sort = sortOrder.value
    const data = await getMallProducts(params)
    const list = Array.isArray(data) ? data : (data?.list || data?.items || data?.records || [])
    products.value = list
    totalPages.value = Number(data?.totalPages || data?.pages || Math.ceil((Number(data?.total || data?.totalCount || list.length)) / pageSize)) || 1
    totalItems.value = Number(data?.total || data?.totalCount || list.length) || 0
  } catch (e) {
    console.error('[mall] 加载商品失败', e)
    products.value = []
    totalPages.value = 1
    totalItems.value = 0
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    const data = await getMallCategories()
    const list = Array.isArray(data) ? data : (data?.list || data?.items || [])
    const names = list.map(c => typeof c === 'string' ? c : (c?.name || c?.label || c?.title)).filter(Boolean)
    categories.value = ['全部', ...names]
  } catch (e) {
    console.error('[mall] 加载分类失败', e)
    categories.value = ['全部']
  }
}

function selectTab(value) {
  if (activeTab.value === value) return
  activeTab.value = value
  pageNum.value = 1
  activeCategory.value = '全部'
  loadProducts()
}

function selectCategory(cat) {
  if (activeCategory.value === cat) return
  activeCategory.value = cat
  pageNum.value = 1
  loadProducts()
}

let searchTimer = null
function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    pageNum.value = 1
    loadProducts()
  }, 350)
}

function onSortChange() {
  pageNum.value = 1
  loadProducts()
}

function goToPage(n) {
  if (n < 1 || n > totalPages.value || n === pageNum.value) return
  pageNum.value = n
  loadProducts()
}

const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur = pageNum.value
  const arr = []
  if (total <= 7) {
    for (let i = 1; i <= total; i++) arr.push(i)
  } else {
    arr.push(1)
    if (cur > 4) arr.push('...')
    const start = Math.max(2, cur - 1)
    const end = Math.min(total - 1, cur + 1)
    for (let i = start; i <= end; i++) arr.push(i)
    if (cur < total - 3) arr.push('...')
    arr.push(total)
  }
  return arr
})

onMounted(async () => {
  await loadCategories()
  await loadProducts()
  loadServiceConfig()
})

// ===== 在线客服弹窗 =====
const serviceModalVisible = ref(false)
const serviceConfig = ref({
  servicePhone: '',
  serviceEmail: '',
  companyAddress: '',
  wechatOfficial: ''
})

async function loadServiceConfig() {
  try {
    const data = await getMallServiceConfig()
    const cfg = data?.data || data || {}
    serviceConfig.value = {
      servicePhone: cfg.servicePhone || cfg.service_phone || cfg.phone || '',
      serviceEmail: cfg.serviceEmail || cfg.service_email || cfg.email || '',
      companyAddress: cfg.companyAddress || cfg.company_address || cfg.address || '',
      wechatOfficial: cfg.wechatOfficial || cfg.wechat_official || cfg.officialAccount || cfg.public_account || ''
    }
  } catch (e) {
    console.error('[mall] 加载客服配置失败', e)
  }
}

function openServiceModal() {
  serviceModalVisible.value = true
}

const hasServiceInfo = computed(() => {
  const c = serviceConfig.value
  return !!(c.servicePhone || c.serviceEmail || c.companyAddress || c.wechatOfficial)
})

// ===== 工单反馈弹窗 =====
const feedbackModalVisible = ref(false)
const feedbackSubmitting = ref(false)
const feedbackError = ref('')
const feedbackForm = ref({
  type: 'product_invalid',
  title: '',
  content: '',
  contact: ''
})

const feedbackTypeOptions = [
  { value: 'product_invalid', label: '商品失效' },
  { value: 'feature_issue', label: '功能问题' },
  { value: 'not_shipped', label: '未发货问题' },
  { value: 'other', label: '其他' }
]

function openFeedbackModal() {
  feedbackForm.value = { type: 'product_invalid', title: '', content: '', contact: '' }
  feedbackError.value = ''
  feedbackModalVisible.value = true
}

function closeFeedbackModal() {
  if (feedbackSubmitting.value) return
  feedbackModalVisible.value = false
}

async function submitFeedbackForm() {
  if (!feedbackForm.value.title.trim()) {
    feedbackError.value = '请填写标题'
    return
  }
  if (!feedbackForm.value.content.trim()) {
    feedbackError.value = '请填写问题描述'
    return
  }
  feedbackSubmitting.value = true
  feedbackError.value = ''
  try {
    await submitFeedback({
      type: feedbackForm.value.type,
      title: feedbackForm.value.title.trim(),
      content: feedbackForm.value.content.trim(),
      contact: feedbackForm.value.contact.trim()
    })
    feedbackModalVisible.value = false
  } catch (e) {
    feedbackError.value = e?.message || '提交失败，请稍后重试'
  } finally {
    feedbackSubmitting.value = false
  }
}

// ===== 常见问题弹窗 =====
const faqModalVisible = ref(false)
const faqLoading = ref(false)
const faqs = ref([])
const openFaqIndex = ref(-1)

async function openFaqModal() {
  faqModalVisible.value = true
  if (faqs.value.length === 0) {
    faqLoading.value = true
    try {
      const data = await getMallFaqs()
      const list = Array.isArray(data) ? data : (data?.list || data?.items || [])
      faqs.value = list
    } catch (e) {
      console.error('[mall] 加载常见问题失败', e)
      faqs.value = []
    } finally {
      faqLoading.value = false
    }
  }
}

function toggleFaq(idx) {
  openFaqIndex.value = openFaqIndex.value === idx ? -1 : idx
}

function faqQuestion(item) {
  return item?.question || item?.title || ''
}
function faqAnswer(item) {
  return item?.answer || item?.content || item?.desc || ''
}

// ===== 支付弹窗 =====
const payModalVisible = ref(false)
const payStep = ref('select') // 'select' | 'qr' | 'success'
const currentPayProduct = ref(null)
const paymentMethods = ref([])
const payMethod = ref('')
const paySubmitting = ref(false)
const payError = ref('')
const currentOrder = ref(null)
const payCountdownSeconds = ref(0)
const payChecking = ref(false)
let payPollTimer = null
let payCountdownTimer = null

const PAY_TIMEOUT_SECONDS = 15 * 60

const payAmountYuan = computed(() => {
  const p = currentPayProduct.value || {}
  if (p.priceYuan != null) return p.priceYuan
  if (p.priceCent != null) {
    const n = Number(p.priceCent)
    if (!Number.isNaN(n)) return (n / 100).toFixed(2)
  }
  return String(p.price || '').replace(/^¥\s*/, '')
})

const payCountdownText = computed(() => {
  const s = payCountdownSeconds.value
  if (s <= 0) return '00:00'
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

async function handleBuy(product) {
  currentPayProduct.value = product
  payStep.value = 'select'
  payMethod.value = ''
  payError.value = ''
  currentOrder.value = null
  payCountdownSeconds.value = 0
  payModalVisible.value = true
  if (paymentMethods.value.length === 0) {
    try {
      const data = await getPaymentMethods()
      const list = Array.isArray(data) ? data : (data?.list || data?.methods || [])
      paymentMethods.value = list.filter(m => m.channelType === 'wechat' || m.channelType === 'alipay')
      if (paymentMethods.value.length > 0 && !payMethod.value) {
        payMethod.value = paymentMethods.value[0].channelType
      }
    } catch (e) {
      console.error('[mall] 加载支付方式失败', e)
      paymentMethods.value = [
        { channelType: 'wechat', name: '微信支付' },
        { channelType: 'alipay', name: '支付宝' }
      ]
      payMethod.value = 'wechat'
    }
  }
}

async function createMallOrder() {
  if (!currentPayProduct.value || !payMethod.value) return
  paySubmitting.value = true
  payError.value = ''
  try {
    const order = await purchaseMallProduct({
      productId: currentPayProduct.value.id,
      paymentMethod: payMethod.value
    })
    currentOrder.value = order
    payStep.value = 'qr'
    payCountdownSeconds.value = PAY_TIMEOUT_SECONDS
    startPayPolling()
    startPayCountdown()
  } catch (e) {
    payError.value = e?.message || '创建订单失败，请稍后重试'
  } finally {
    paySubmitting.value = false
  }
}

// 用户主动点击"我已完成支付"按钮时调用，主动查询订单状态
// 用于本地开发环境（易支付异步回调无法到达本机）或管理员后台强制标记已支付后
async function checkPaymentPaid() {
  const orderNo = currentOrder.value?.orderNo
  if (!orderNo || payChecking.value) return
  payChecking.value = true
  payError.value = ''
  try {
    const data = await getPaymentOrder(orderNo)
    if (!data) {
      payError.value = '订单状态查询失败，请稍后重试'
      return
    }
    currentOrder.value = { ...currentOrder.value, ...data }
    const rawStatus = data.status ?? data.orderStatus
    const statusNum = Number(rawStatus)
    const statusStr = String(rawStatus || '').toLowerCase()
    if (statusNum === 1 || statusStr === 'paid' || statusStr === 'success' || statusStr === 'completed') {
      payStep.value = 'success'
      stopPayPolling()
      stopPayCountdown()
    } else if (statusNum === 2 || statusStr === 'closed' || statusStr === 'failed' || statusStr === 'expired') {
      stopPayPolling()
      stopPayCountdown()
      payError.value = data.statusText || '订单已关闭或支付失败，请重新创建订单'
    } else {
      payError.value = '订单尚未支付成功，请完成扫码支付后再点击此按钮（若已扫码支付，请等待几秒后重试）'
    }
  } catch (e) {
    payError.value = e?.message || '订单状态查询失败，请稍后重试'
  } finally {
    payChecking.value = false
  }
}

function startPayPolling() {
  stopPayPolling()
  payPollTimer = setInterval(async () => {
    const orderNo = currentOrder.value?.orderNo
    if (!orderNo) return
    try {
      const data = await getPaymentOrder(orderNo)
      if (!data) return
      currentOrder.value = { ...currentOrder.value, ...data }
      // 后端 status 字段为数字：0=待支付 1=已支付 2=已关闭
      // 兼容字符串形式（paid/success）和数字形式（1）
      const rawStatus = data.status ?? data.orderStatus
      const statusNum = Number(rawStatus)
      const statusStr = String(rawStatus || '').toLowerCase()
      const isPaid = statusNum === 1 || statusStr === 'paid' || statusStr === 'success' || statusStr === 'success_paid' || statusStr === 'completed'
      const isClosed = statusNum === 2 || statusStr === 'closed' || statusStr === 'failed' || statusStr === 'expired'
      if (isPaid) {
        payStep.value = 'success'
        stopPayPolling()
        stopPayCountdown()
      } else if (isClosed) {
        stopPayPolling()
        stopPayCountdown()
        payError.value = data.statusText || '订单已关闭或支付失败，请重新创建订单'
      }
    } catch (e) {
      console.error('[mall] 轮询订单状态失败', e)
    }
  }, 3000)
}

function stopPayPolling() {
  if (payPollTimer) {
    clearInterval(payPollTimer)
    payPollTimer = null
  }
}

function startPayCountdown() {
  stopPayCountdown()
  payCountdownTimer = setInterval(() => {
    payCountdownSeconds.value = Math.max(0, payCountdownSeconds.value - 1)
    if (payCountdownSeconds.value <= 0) {
      stopPayCountdown()
      stopPayPolling()
      payError.value = '支付超时，订单已失效'
    }
  }, 1000)
}

function stopPayCountdown() {
  if (payCountdownTimer) {
    clearInterval(payCountdownTimer)
    payCountdownTimer = null
  }
}

async function closePayModal() {
  const orderNo = currentOrder.value?.orderNo
  stopPayPolling()
  stopPayCountdown()
  // 关闭前主动查询一次订单状态（支持管理员在后台强制标记已支付后，用户关闭弹窗也能识别）
  let detectedPaid = payStep.value === 'success'
  if (orderNo && payStep.value === 'qr') {
    try {
      const latest = await getPaymentOrder(orderNo)
      if (latest) {
        currentOrder.value = { ...currentOrder.value, ...latest }
        const rawStatus = latest.status ?? latest.orderStatus
        const statusNum = Number(rawStatus)
        const statusStr = String(rawStatus || '').toLowerCase()
        if (statusNum === 1 || statusStr === 'paid' || statusStr === 'success' || statusStr === 'completed') {
          detectedPaid = true
          payStep.value = 'success'
        }
      }
    } catch (e) { /* 忽略查询失败 */ }
  }
  // 仅在仍未支付时才关闭订单（已支付订单不能关闭）
  if (orderNo && payStep.value === 'qr') {
    try { await closePaymentOrder(orderNo) } catch (e) { /* 忽略关闭失败 */ }
  }
  const wasSuccess = detectedPaid || payStep.value === 'success'
  payModalVisible.value = false
  if (wasSuccess) {
    loadProducts()
    // 支付成功后，若详情弹窗曾关闭以触发支付，重新打开详情弹窗（让用户看到"开始上架"按钮）
    refreshDetailAfterPayment()
    if (detailProduct.value?.id && !detailModalVisible.value) {
      // 重新打开详情弹窗，展示已购买状态
      const pid = detailProduct.value.id
      const refreshed = await getMallProductDetail(pid).catch(() => null)
      if (refreshed) {
        detailProduct.value = { ...detailProduct.value, ...refreshed }
      }
      detailModalVisible.value = true
    }
  }
}

function methodLabel(m) {
  return m?.name || m?.label || (m?.channelType === 'wechat' ? '微信支付' : m?.channelType === 'alipay' ? '支付宝' : m?.channelType)
}

function handleDetail(product) {
  openDetailModal(product)
}

// ===== 商品详情弹窗（上架该商品入口） =====
const detailModalVisible = ref(false)
const detailProduct = ref(null)
const detailLoading = ref(false)
const detailError = ref('')

const detailIsText = computed(() => detailProduct.value?.productType === 'text' || detailProduct.value?.type === 'text')
const detailIsCard = computed(() => detailProduct.value?.productType === 'card' || detailProduct.value?.type === 'card')
const detailPurchased = computed(() => !!detailProduct.value?.purchased)

const detailCreateTimeDisplay = computed(() => {
  const raw = detailProduct.value?.createdTime || detailProduct.value?.createTime
  if (!raw) return '-'
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return String(raw)
  const y = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${mm}-${dd} ${hh}:${mi}`
})

const detailBoughtDisplay = computed(() => {
  const raw = detailProduct.value?.boughtCount
  if (raw == null) return '0'
  const num = Number(raw)
  if (!Number.isNaN(num)) return num.toLocaleString('zh-CN')
  return String(raw)
})

const detailPriceDisplay = computed(() => {
  const p = detailProduct.value || {}
  if (p.priceYuan != null) return p.priceYuan
  if (p.priceCent != null) {
    const n = Number(p.priceCent)
    if (!Number.isNaN(n)) return (n / 100).toFixed(2)
  }
  return String(p.price || '').replace(/^¥\s*/, '')
})

const detailCoverUrl = computed(() => {
  const url = detailProduct.value?.coverUrl || ''
  if (!url) return ''
  if (/^(https?:)?\/\//.test(url) || url.startsWith('/') || url.startsWith('blob:') || url.startsWith('data:')) return url
  return '/' + url.replace(/^\/+/, '')
})

async function openDetailModal(product) {
  if (!product?.id) return
  detailModalVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detailProduct.value = { ...product }
  try {
    const data = await getMallProductDetail(product.id)
    if (data && typeof data === 'object') {
      detailProduct.value = { ...product, ...data }
    }
  } catch (e) {
    // 详情获取失败时仍展示列表基础信息
    detailError.value = e?.message || '商品详情获取失败，仅展示基础信息'
  } finally {
    detailLoading.value = false
  }
}

function closeDetailModal() {
  detailModalVisible.value = false
  detailProduct.value = null
  detailError.value = ''
}

function handleDetailPay() {
  if (!detailProduct.value) return
  const product = detailProduct.value
  // 关闭详情弹窗，打开支付弹窗
  detailModalVisible.value = false
  handleBuy(product)
}

// 支付成功后若详情弹窗曾打开，刷新详情
function refreshDetailAfterPayment() {
  if (detailModalVisible.value && detailProduct.value?.id) {
    const id = detailProduct.value.id
    detailLoading.value = true
    getMallProductDetail(id).then(data => {
      if (data && typeof data === 'object') {
        detailProduct.value = { ...detailProduct.value, ...data }
      }
    }).catch(() => {}).finally(() => {
      detailLoading.value = false
    })
  } else if (detailProduct.value?.id) {
    // 详情弹窗已关闭但记忆中的商品需要刷新列表
    loadProducts()
  }
}

// ===== 上架流程弹窗（4 步：AI改写 → AI生图 → 配置 → 发布） =====
const listFlowVisible = ref(false)
const listFlowAuto = ref(false)
const listFlowStep = ref(1) // 1=改写, 2=生图, 3=配置, 4=发布
const listFlowLoading = ref(false)
const listFlowError = ref('')
const listFlowMessage = ref('')
const listFlowAutoRunning = ref(false)

// AI 改写
const rewriteTitle = ref('')
const rewriteDescription = ref('')
const rewriteLoading = ref(false)
const rewriteStyle = ref('friendly')

// AI 生图
const generatedImages = ref([])
const imageLoading = ref(false)
const selectedModelKey = ref('')
const availableImageModels = ref([])
const imageStatus = ref({ configured: null, defaultPrompt: '', tokensPerImage: null })
const imageStatusLoading = ref(false)
const imageStatusLoadError = ref('')

// AI 改写状态
const aiStatus = ref({ configured: null, rewriteEnabled: null })
const aiStatusLoading = ref(false)
const aiStatusLoadError = ref('')

// 配置
const configPrice = ref('')
const configAddress = ref(null)
const configCategory = ref('')
const publishing = ref(false)

// 账号
const accounts = ref([])
const accountLoaded = ref(false)
const accountLoadError = ref('')
const selectedAccountId = ref(null)

const selectedAccount = computed(() => accounts.value.find(a => a.id === selectedAccountId.value) || null)
const isFishShopAccount = computed(() => !!(selectedAccount.value?.fishShopUser))

// 库存策略：
// - 文本货源：固定 999（虚拟商品无限库存）
// - 卡密货源：跟随卡密库存
// - 普通用户（非鱼小铺）：发布时由 Python 后端强制为 1，前端展示提示
const configStock = computed(() => {
  const p = detailProduct.value
  if (!p) return 1
  const type = p.productType || p.type
  if (type === 'text') return 999
  if (type === 'card') {
    const stock = Number(p.stock ?? 0)
    return Number.isFinite(stock) && stock > 0 ? stock : 0
  }
  return 1
})

const stockDisplayText = computed(() => {
  const p = detailProduct.value
  const type = p?.productType || p?.type
  if (type === 'text') return '999（文本货源固定库存）'
  if (type === 'card') {
    const stock = Number(p?.stock ?? 0)
    return `${stock}（跟随卡密库存）`
  }
  return String(configStock.value)
})

const stockStrategyHint = computed(() => {
  const p = detailProduct.value
  const type = p?.productType || p?.type
  if (type === 'text') {
    return '文本货源库存固定 999'
  }
  if (type === 'card') {
    return '卡密货源库存跟随卡密库存'
  }
  return ''
})

const accountLevelHint = computed(() => {
  if (!selectedAccount.value) return ''
  if (isFishShopAccount.value) return '当前账号为鱼小铺账号，可自定义库存'
  return '当前账号为普通账号，发布时库存将被强制为 1（闲鱼平台限制）'
})

const listFlowCanRewrite = computed(() => !aiStatusLoading.value && aiStatus.value.rewriteEnabled === true)
const listFlowCanGenImage = computed(() => !imageStatusLoading.value && imageStatus.value.configured === true && availableImageModels.value.length > 0)
const listFlowAddressComplete = computed(() => isPublishAddressComplete(configAddress.value))

const imgUrl = (img) => img.originalUrl || img.url || ('data:image/png;base64,' + img.b64Json)

function isCoverSelected(img) {
  // 在上架流程中，所有生成的图片都会作为发布图集，无需选择
  return !!img
}

async function loadAccountsForList() {
  accountLoaded.value = false
  accountLoadError.value = ''
  try {
    const res = await getLiteAccounts({ current: 1, size: 100 })
    const data = res?.data
    const list = Array.isArray(data) ? data : (data?.records || data?.list || data?.accounts || [])
    accounts.value = list
    const preferred = pickPreferredAccount(list, selectedAccountId.value)
    if (preferred) {
      selectedAccountId.value = preferred.id
    } else if (list.length && !selectedAccountId.value) {
      selectedAccountId.value = list[0].id
    }
    if (!list.length) {
      accountLoadError.value = '请先到「账号管理」扫码登录闲鱼账号后再上架'
    }
  } catch (e) {
    accountLoadError.value = e?.message || '闲鱼账号加载失败'
    accounts.value = []
  } finally {
    accountLoaded.value = true
  }
}

async function loadAiStatusForList() {
  aiStatusLoading.value = true
  aiStatusLoadError.value = ''
  try {
    const res = await getOpportunityAiStatus()
    const data = res?.data
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      aiStatus.value = {
        configured: data.configured === true,
        rewriteEnabled: data.rewriteEnabled === true || (data.configured === true && data.rewriteEnabled !== false),
      }
    } else {
      aiStatus.value = { configured: null, rewriteEnabled: null }
      aiStatusLoadError.value = 'AI 改写状态响应异常'
    }
  } catch (e) {
    aiStatus.value = { configured: null, rewriteEnabled: null }
    aiStatusLoadError.value = e?.message || 'AI 改写状态暂时不可用'
  } finally {
    aiStatusLoading.value = false
  }
}

async function loadImageStatusForList() {
  imageStatusLoading.value = true
  imageStatusLoadError.value = ''
  try {
    const [statusRes, modelsRes] = await Promise.all([
      getOpportunityImageStatus(),
      getOpportunityImageModels(),
    ])
    const statusData = statusRes?.data
    if (statusData && typeof statusData === 'object' && !Array.isArray(statusData)) {
      imageStatus.value = {
        configured: statusData.configured === true,
        defaultPrompt: statusData.defaultPrompt || '',
        tokensPerImage: statusData.tokensPerImage ?? null,
      }
    } else {
      imageStatus.value = { configured: null, defaultPrompt: '', tokensPerImage: null }
      imageStatusLoadError.value = '生图状态响应异常'
    }
    const modelsData = modelsRes?.data
    const modelsList = Array.isArray(modelsData) ? modelsData : (Array.isArray(modelsData?.list) ? modelsData.list : [])
    availableImageModels.value = modelsList.filter(m => m && m.moduleKey)
    if (availableImageModels.value.length && !selectedModelKey.value) {
      selectedModelKey.value = availableImageModels.value[0].moduleKey
    }
  } catch (e) {
    imageStatus.value = { configured: null, defaultPrompt: '', tokensPerImage: null }
    imageStatusLoadError.value = e?.message || '生图状态暂时不可用'
  } finally {
    imageStatusLoading.value = false
  }
}

async function loadHistoryAddressForList() {
  try {
    const res = await getPublishAddressHistory()
    const data = res?.data
    const list = Array.isArray(data) ? data : (Array.isArray(data?.list) ? data.list : [])
    if (list.length) {
      // 选取最近一次地址作为默认
      const latest = list[0]
      const normalized = normalizePublishAddress(latest)
      if (normalized && isPublishAddressComplete(normalized)) {
        configAddress.value = normalized
      }
    }
  } catch (_e) {
    // 历史地址加载失败不阻断流程
  }
}

async function openListFlow(auto = false) {
  const product = detailProduct.value
  if (!product) {
    listFlowError.value = '请先选择要上架的商品'
    return
  }
  // 1. 校验是否已购买
  if (!detailPurchased.value) {
    listFlowError.value = '请先完成支付后再上架'
    return
  }
  listFlowVisible.value = true
  listFlowAuto.value = !!auto
  listFlowStep.value = 1
  listFlowLoading.value = true
  listFlowError.value = ''
  listFlowMessage.value = ''
  rewriteTitle.value = product.title || ''
  // AI 改写输入使用 copy 字段（商品文案），若为空则降级到 content
  rewriteDescription.value = product.copy || product.content || ''
  rewriteStyle.value = 'friendly'
  generatedImages.value = []
  selectedModelKey.value = ''
  configPrice.value = String(detailPriceDisplay.value ?? '')
  configAddress.value = null
  configCategory.value = product.category || '货源商城'
  publishing.value = false
  listFlowAutoRunning.value = false

  // 并行加载：账号列表、AI 状态、生图状态、历史地址
  try {
    await Promise.all([
      loadAccountsForList(),
      loadAiStatusForList(),
      loadImageStatusForList(),
      loadHistoryAddressForList(),
    ])
  } finally {
    listFlowLoading.value = false
  }

  // 兜底校验：账号 / AI 状态
  if (!accounts.value.length) {
    listFlowError.value = accountLoadError.value || '请先到「账号管理」扫码登录闲鱼账号后再上架'
    return
  }
  if (auto) {
    // 自动模式下，启动一键流程
    runAutoFlow()
  }
}

function closeListFlow() {
  if (listFlowLoading.value || publishing.value || imageLoading.value || rewriteLoading.value) {
    listFlowError.value = '操作进行中，请等待完成后再关闭弹窗'
    return
  }
  listFlowVisible.value = false
  listFlowAutoRunning.value = false
}

function listFlowGotoStep(step) {
  if (step < 1 || step > 4) return
  listFlowStep.value = step
  listFlowError.value = ''
}

// AI 改写：根据商品标题与商品文案生成新的标题与正文
async function runRewrite() {
  const product = detailProduct.value
  if (!product) return
  if (!listFlowCanRewrite.value) {
    listFlowError.value = aiStatusLoadError.value || '平台暂未开放 AI 改写功能，无法继续'
    return false
  }
  if (!(await ensureAiTokenBalance({ sceneName: 'AI 文案润色' }))) return false
  rewriteLoading.value = true
  listFlowError.value = ''
  listFlowMessage.value = 'AI 正在改写标题与正文...'
  try {
    const sourceTitle = product.title || ''
    const sourceDescription = product.copy || product.content || sourceTitle
    const payload = {
      keyword: '货源商城',
      item: {
        title: sourceTitle,
        description: sourceDescription,
        link: '',
        image: product.coverUrl || '',
        itemId: 'mall-' + product.id,
      },
      title: sourceTitle,
      description: sourceDescription,
      style: rewriteStyle.value || 'friendly',
    }
    const res = await rewriteOpportunity(payload)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('AI 改写响应格式异常，请重试')
    }
    if (typeof data.ok !== 'boolean') throw new Error('AI 改写响应缺少成功状态')
    if (data.ok === false || data.error) {
      throw new Error(data.error || data.message || 'AI 改写失败，请重试')
    }
    if (!data.rewrite || typeof data.rewrite !== 'object'
      || typeof data.rewrite.title !== 'string' || !data.rewrite.title.trim()
      || typeof data.rewrite.description !== 'string' || !data.rewrite.description.trim()) {
      throw new Error(data.message || 'AI 改写结果异常，请重试')
    }
    rewriteTitle.value = data.rewrite.title.slice(0, 30)
    rewriteDescription.value = data.rewrite.description
    listFlowMessage.value = 'AI 改写完成，已生成新标题与正文'
    return true
  } catch (e) {
    listFlowError.value = friendlyError(e, 'AI 改写失败')
    return false
  } finally {
    rewriteLoading.value = false
  }
}

// AI 生图：根据新标题与正文生成封面图
async function runGenerateImages() {
  if (!listFlowCanGenImage.value) {
    listFlowError.value = imageStatusLoadError.value || '平台暂未开放生图功能，无法继续'
    return false
  }
  if (!selectedModelKey.value) {
    listFlowError.value = '请选择生图模型'
    return false
  }
  const title = rewriteTitle.value?.trim()
  const description = rewriteDescription.value?.trim()
  if (!title && !description) {
    listFlowError.value = '标题和正文均为空，无法生成图片'
    return false
  }
  if (!(await ensureAiTokenBalance({ sceneName: 'AI 生图' }))) return false
  imageLoading.value = true
  listFlowError.value = ''
  listFlowMessage.value = '正在生成图片（约需 2-3 分钟，请耐心等待）...'
  try {
    const res = await generateOpportunityImages({
      prompt: '',
      promptMode: 'default',
      customPrompt: '',
      count: 1,
      size: '1024x1024',
      itemTitle: title,
      itemDescription: description,
      systemPrompt: imageStatus.value.defaultPrompt || '',
      modelKey: selectedModelKey.value,
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('生图服务响应格式异常')
    }
    if (typeof data.ok !== 'boolean') throw new Error('生图服务响应缺少成功状态')
    if (data.ok === false) {
      throw new Error(data.error || data.message || '生图失败，请重试')
    }
    const images = Array.isArray(data.images) ? data.images.filter(img => img && (img.originalUrl || img.url || img.b64Json)) : []
    const returnedCount = Number(data.count)
    if (!Number.isSafeInteger(returnedCount) || returnedCount !== images.length) {
      throw new Error('生图服务返回的图片数量不一致')
    }
    if (!images.length) throw new Error('生图返回结果为空，请重试')
    generatedImages.value = images
    const chargedTokens = Number(data.chargedTokens)
    listFlowMessage.value = Number.isFinite(chargedTokens) && chargedTokens >= 0
      ? `已生成 ${images.length} 张图片，扣除 ${chargedTokens} Token`
      : `已生成 ${images.length} 张图片`
    return true
  } catch (e) {
    listFlowError.value = friendlyError(e, '生图失败，请稍后重试')
    return false
  } finally {
    imageLoading.value = false
  }
}

async function ensureAccountReady() {
  if (!accountLoaded.value) {
    // 等待账号加载
    const maxWait = 5000
    const start = Date.now()
    while (!accountLoaded.value && Date.now() - start < maxWait) {
      await new Promise(r => setTimeout(r, 150))
    }
  }
  if (!accounts.value.length) {
    listFlowError.value = accountLoadError.value || '请先到「账号管理」扫码登录闲鱼账号后再上架'
    return false
  }
  const preferred = pickPreferredAccount(accounts.value, selectedAccountId.value)
  if (!preferred) {
    listFlowError.value = '未选择有效的闲鱼账号，请到「账号管理」扫码登录后再使用'
    return false
  }
  selectedAccountId.value = preferred.id
  // 实时探活账号 cookie
  try {
    const authRes = await checkAccountAuth(preferred.id)
    const authData = authRes?.data
    if (authData && typeof authData === 'object' && authData.usable === false) {
      const refreshed = accounts.value.find(a => a.id === preferred.id)
      if (refreshed && !accountAuthUsable(refreshed)) {
        listFlowError.value = `账号「${refreshed.nickname || refreshed.displayName || refreshed.externalUid || ('账号' + refreshed.id)}」Cookie 已失效（${accountLoginHint(refreshed)}），请到「账号管理」重新登录后再使用`
        return false
      }
    }
  } catch (_e) {
    // 接口异常时降级到缓存判断
    if (!accountAuthUsable(preferred)) {
      listFlowError.value = `账号「${preferred.nickname || preferred.displayName || preferred.externalUid || ('账号' + preferred.id)}」状态不可用，请到「账号管理」检查或重新登录`
      return false
    }
  }
  return true
}

async function runPublish() {
  const product = detailProduct.value
  if (!product) return false
  if (!(await ensureAccountReady())) return false
  const location = normalizePublishAddress(configAddress.value)
  if (!isPublishAddressComplete(location)) {
    listFlowError.value = '请先在配置步骤完成发布位置的省、市、区选择'
    listFlowStep.value = 3
    return false
  }
  const publishPrice = Number(String(configPrice.value || '').replace(/[¥￥,]/g, '').trim())
  if (!Number.isFinite(publishPrice) || publishPrice <= 0) {
    listFlowError.value = '请填写大于 0 的有效发布价格'
    listFlowStep.value = 3
    return false
  }
  if (!rewriteTitle.value.trim()) {
    listFlowError.value = '商品标题为空，请先回到改写步骤'
    listFlowStep.value = 1
    return false
  }
  const imageUrls = (generatedImages.value || [])
    .map(img => img.originalUrl || img.url || '')
    .filter(url => typeof url === 'string' && url.trim() && (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('/uploads/')))
  // 文本货源：若生图失败，回退到商品原有 coverUrl
  if (!imageUrls.length && product.coverUrl) {
    const cover = product.coverUrl
    if (cover.startsWith('http://') || cover.startsWith('https://') || cover.startsWith('/uploads/')) {
      imageUrls.push(cover)
    }
  }
  if (!imageUrls.length) {
    listFlowError.value = '发布到闲鱼需要至少一张可访问的商品图片，请先生成图片'
    listFlowStep.value = 2
    return false
  }
  publishing.value = true
  listFlowError.value = ''
  listFlowMessage.value = '正在发布到闲鱼...'
  try {
    const publishRes = await publishItem({
      xianyuAccountId: Number(selectedAccountId.value),
      title: rewriteTitle.value.slice(0, 30),
      description: rewriteDescription.value || product.copy || product.content || product.title,
      imageUrls,
      price: String(publishPrice),
      stock: Number(configStock.value),
      category: configCategory.value || product.category || '货源商城',
      freeShipping: true,
      supportSelfPick: false,
      location,
      source: 'mall_product',
      sourceItemId: String(product.id),
      sourceLink: '',
    })
    const publishData = publishRes?.data
    if (!publishData || typeof publishData !== 'object' || Array.isArray(publishData)) {
      throw new Error('发布请求已返回，但结果格式异常，无法确认是否成功，请先到闲鱼核对后再重试')
    }
    const itemId = String(publishData.itemId ?? publishData.xyGoodsId ?? publishData.id ?? '').trim()
    if (!itemId) {
      throw new Error('发布请求已返回，但未获得商品 ID，无法确认是否成功，请先到闲鱼核对后再重试')
    }
    localStorage.setItem('xianyu_pending_sync', 'true')
    listFlowMessage.value = `已发布到闲鱼（商品ID：${itemId}），正在绑定货源...`
    // 自动绑定货源：商城货源上架后，自动把对应货源绑定到新上架商品，启用自动发货
    // 此功能仅对商城购买货源有效（用户已支付购买商城货源后才能上架）
    try {
      const sourceRes = await getDeliverySourceByMallProduct(Number(product.id))
      const sourceData = sourceRes?.data
      const sourceId = sourceData?.id
      if (sourceId) {
        await applyDeliverySourceToGoods(sourceId, {
          goodsIds: [Number(itemId)],
          timing: 'paid'
        })
        listFlowMessage.value = `已发布到闲鱼（商品ID：${itemId}），货源已自动绑定（发货时机：买家付款后）`
      } else {
        // 当前用户尚未购买该商城货源（理论上不应出现，因为只有购买后才能上架），提示用户手动绑定
        listFlowMessage.value = `已发布到闲鱼（商品ID：${itemId}）。未找到对应货源，请到「会员库」手动绑定货源`
      }
    } catch (bindErr) {
      // 货源绑定失败不影响上架成功的总体结果，仅提示用户后续手动绑定
      listFlowMessage.value = `已发布到闲鱼（商品ID：${itemId}），但货源自动绑定失败：${friendlyError(bindErr, '请到「会员库」手动绑定')}`
    }
    return true
  } catch (e) {
    listFlowError.value = friendlyError(e, '发布到闲鱼失败')
    return false
  } finally {
    publishing.value = false
  }
}

// 一键上架：依次执行 改写 → 生图 → 配置（默认值）→ 发布
async function runAutoFlow() {
  if (listFlowAutoRunning.value) return
  listFlowAutoRunning.value = true
  listFlowError.value = ''
  listFlowMessage.value = '一键上架流程启动...'
  try {
    // Step 1: AI 改写
    listFlowStep.value = 1
    listFlowMessage.value = '正在 AI 改写...'
    const rewriteOk = await runRewrite()
    if (!rewriteOk || listFlowUnmounted) return
    // Step 2: AI 生图
    listFlowStep.value = 2
    listFlowMessage.value = '正在 AI 生图...'
    const imageOk = await runGenerateImages()
    if (!imageOk || listFlowUnmounted) return
    // Step 3: 配置（使用默认值，校验地址）
    listFlowStep.value = 3
    if (!isPublishAddressComplete(configAddress.value)) {
      listFlowMessage.value = '一键上架流程中止：未配置发布位置，请在配置步骤完成省市区选择后手动发布'
      listFlowError.value = '请先完成发布位置的省、市、区选择'
      return
    }
    if (listFlowUnmounted) return
    // Step 4: 发布
    listFlowStep.value = 4
    listFlowMessage.value = '正在发布到闲鱼...'
    const publishOk = await runPublish()
    if (!publishOk) {
      listFlowMessage.value = '一键上架流程中止：发布失败'
      return
    }
    listFlowMessage.value = '一键上架完成！商品已发布到闲鱼'
  } finally {
    listFlowAutoRunning.value = false
  }
}

async function handleRewriteAction() {
  await runRewrite()
}

async function handleGenerateImagesAction() {
  await runGenerateImages()
}

async function handlePublishAction() {
  await runPublish()
}

let listFlowUnmounted = false

onBeforeUnmount(() => {
  listFlowUnmounted = true
  stopPayPolling()
  stopPayCountdown()
  if (searchTimer) clearTimeout(searchTimer)
})
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

.mall-loading,
.mall-empty {
  padding: 48px 0;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===== 弹窗通用样式 ===== */
.mall-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(16, 28, 52, 0.5);
  backdrop-filter: blur(8px);
  overflow-y: auto;
}

.mall-modal-dialog {
  width: 100%;
  max-width: 460px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.18);
  overflow: hidden;
  margin: auto;
}

.mall-pay-dialog {
  max-width: 420px;
}

.mall-modal-header {
  position: relative;
  padding: 18px 20px 14px;
  border-bottom: 1px solid #f1f5f9;
}

.mall-modal-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  text-align: center;
}

.mall-modal-close {
  position: absolute;
  right: 14px;
  top: 14px;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  font-size: 22px;
  color: #94a3b8;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all .15s;
  line-height: 1;
}

.mall-modal-close:hover {
  background: #f1f5f9;
  color: #475569;
}

.mall-modal-body {
  padding: 18px 20px 20px;
}

.mall-modal-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 24px 0;
}

.mall-modal-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed #f1f5f9;
}

.mall-modal-row:last-child {
  border-bottom: none;
}

.mall-modal-row-label {
  flex-shrink: 0;
  width: 70px;
  font-size: 13px;
  color: #94a3b8;
  font-weight: 500;
}

.mall-modal-row-value {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #1e293b;
  word-break: break-all;
  line-height: 1.6;
}

/* ===== 表单 ===== */
.mall-form-row {
  margin-bottom: 14px;
}

.mall-form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 6px;
}

.mall-form-input {
  width: 100%;
  height: 38px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 0 12px;
  font-size: 13px;
  color: #1e293b;
  outline: none;
  box-sizing: border-box;
  transition: all .2s;
  font-family: inherit;
}

.mall-form-input:focus {
  border-color: #4F7CFF;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(79, 124, 255, .1);
}

.mall-form-textarea {
  height: auto;
  padding: 10px 12px;
  line-height: 1.6;
  resize: vertical;
  min-height: 90px;
}

.mall-form-error {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #fef2f2;
  color: #ef4444;
  font-size: 12px;
  border-radius: 8px;
  line-height: 1.5;
}

.mall-form-submit {
  width: 100%;
  height: 42px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}

.mall-form-submit:hover:not(:disabled) {
  box-shadow: 0 6px 14px rgba(13, 107, 255, .3);
}

.mall-form-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.mall-form-submit-outline {
  margin-top: 12px;
  background: #fff;
  color: #0865f4;
  border: 1px solid #0865f4;
}

.mall-form-submit-outline:hover:not(:disabled) {
  background: #f5f9ff;
  box-shadow: none;
}

/* ===== 常见问题 ===== */
.mall-faq-list {
  display: flex;
  flex-direction: column;
}

.mall-faq-item {
  border-bottom: 1px solid #f1f5f9;
}

.mall-faq-item:last-child {
  border-bottom: none;
}

.mall-faq-question {
  width: 100%;
  padding: 12px 0;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
}

.mall-faq-q-text {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.5;
}

.mall-faq-arrow {
  flex-shrink: 0;
  font-size: 20px;
  color: #94a3b8;
  transform: rotate(0deg);
  transition: transform .2s;
  line-height: 1;
}

.mall-faq-arrow.open {
  transform: rotate(90deg);
  color: #4F7CFF;
}

.mall-faq-answer {
  padding: 0 0 12px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.7;
  white-space: pre-line;
}

/* ===== 支付弹窗 ===== */
.mall-pay-product {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: #f8fafc;
  border-radius: 10px;
  margin-bottom: 16px;
}

.mall-pay-product-title {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mall-pay-product-price {
  font-size: 20px;
  font-weight: 800;
  color: #ff3b30;
  line-height: 1;
  display: inline-flex;
  align-items: flex-start;
}

.mall-pay-product-price em {
  font-size: 13px;
  font-style: normal;
  font-weight: 700;
  margin-right: 1px;
  margin-top: 2px;
}

.mall-pay-methods {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.mall-pay-method {
  flex: 1;
  min-width: 100px;
  height: 40px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: all .15s;
}

.mall-pay-method:hover {
  border-color: #c7d2fe;
  color: #4F7CFF;
}

.mall-pay-method.active {
  border-color: #4F7CFF;
  background: rgba(79, 124, 255, .08);
  color: #4F7CFF;
}

.mall-pay-qr-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: #f8fafc;
  border-radius: 10px;
  margin-bottom: 12px;
}

.mall-pay-qr-img {
  width: 200px;
  height: 200px;
  object-fit: contain;
  display: block;
}

.mall-pay-qr-unavailable {
  width: 200px;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px dashed #e2e8f0;
  border-radius: 8px;
  color: #94a3b8;
  font-size: 13px;
}

.mall-pay-countdown {
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: #f59e0b;
  margin-bottom: 8px;
  font-variant-numeric: tabular-nums;
}

.mall-pay-tip {
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}

.mall-pay-success {
  text-align: center;
  padding: 20px 0;
}

.mall-pay-success-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #10b981;
  color: #fff;
  font-size: 32px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 14px;
}

.mall-pay-success h3 {
  margin: 0 0 6px;
  font-size: 16px;
  color: #0f172a;
}

.mall-pay-success p {
  margin: 0;
  font-size: 13px;
  color: #64748b;
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

/* ===== 商品详情弹窗 ===== */
.mall-detail-dialog {
  max-width: 560px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
}

.mall-detail-dialog .mall-modal-body {
  overflow-y: auto;
  padding: 18px 20px 20px;
}

.detail-cover-wrap {
  position: relative;
  width: 100%;
  height: 220px;
  border-radius: 12px;
  overflow: hidden;
  background: linear-gradient(135deg, #f1f5f9, #e2e8f0);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.detail-cover-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 12px;
}

.detail-cover-placeholder svg {
  width: 48px;
  height: 48px;
  opacity: 0.6;
}

.detail-type-tag {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.3px;
  backdrop-filter: blur(4px);
}

.detail-type-text {
  background: linear-gradient(135deg, rgba(79, 124, 255, .92), rgba(99, 102, 241, .92));
}

.detail-type-card {
  background: linear-gradient(135deg, rgba(245, 158, 11, .92), rgba(217, 119, 6, .92));
}

.detail-info-section {
  margin-bottom: 14px;
}

.detail-info-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
  margin-bottom: 4px;
  letter-spacing: 0.3px;
}

.detail-info-value {
  font-size: 14px;
  color: #1e293b;
  line-height: 1.6;
  word-break: break-word;
}

.detail-title-value {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.detail-copy-text {
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 12px;
  border: 1px solid #f1f5f9;
  font-size: 13px;
  color: #475569;
  white-space: pre-wrap;
}

.detail-info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 12px 14px;
  background: #f8fafc;
  border-radius: 10px;
  margin-bottom: 14px;
}

.detail-info-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.detail-price-value {
  font-size: 18px;
  font-weight: 800;
  color: #ff3b30;
  line-height: 1.2;
  display: inline-flex;
  align-items: flex-start;
}

.detail-price-value em {
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  margin-right: 1px;
  margin-top: 3px;
}

.detail-text-product-tip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  border: 1px solid #e0e7ff;
  margin-bottom: 14px;
}

.detail-tip-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(99, 102, 241, .15);
  color: #6366f1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-tip-icon svg {
  width: 20px;
  height: 20px;
}

.detail-tip-content {
  flex: 1;
  min-width: 0;
}

.detail-tip-title {
  font-size: 13px;
  font-weight: 700;
  color: #4f46e5;
  margin-bottom: 2px;
}

.detail-tip-desc {
  font-size: 12px;
  color: #6366f1;
  line-height: 1.4;
}

.detail-error-tip {
  padding: 10px 12px;
  background: #fef2f2;
  color: #ef4444;
  font-size: 12px;
  border-radius: 8px;
  line-height: 1.5;
  margin-bottom: 12px;
}

.detail-action-area {
  margin-top: 4px;
  padding-top: 14px;
  border-top: 1px solid #f1f5f9;
}

.detail-flow-tip {
  padding: 12px 14px;
  background: linear-gradient(135deg, #f0f9ff, #eef2ff);
  border: 1px solid #dbeafe;
  border-radius: 10px;
  margin-bottom: 12px;
}

.flow-tip-label {
  font-size: 11px;
  font-weight: 700;
  color: #2563eb;
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}

.flow-tip-chain {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.flow-step-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #dbeafe;
  font-size: 11px;
  font-weight: 600;
  color: #2563eb;
  white-space: nowrap;
}

.flow-arrow {
  color: #93c5fd;
  font-size: 12px;
  font-weight: 700;
}

.detail-pay-btn {
  width: 100%;
  height: 46px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all .2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 6px 16px rgba(13, 107, 255, .25);
}

.detail-pay-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(13, 107, 255, .35);
}

.detail-pay-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.detail-pay-btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.detail-pay-btn-icon svg {
  width: 18px;
  height: 18px;
}

.detail-purchased-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #ecfdf5;
  border: 1px solid #d1fae5;
  border-radius: 10px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #16bf78;
  font-weight: 600;
}

.detail-purchased-tip svg {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.detail-list-btns {
  display: flex;
  gap: 10px;
}

.detail-list-btn {
  flex: 1;
  height: 44px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all .2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.detail-list-btn svg {
  width: 18px;
  height: 18px;
}

.detail-list-btn-primary {
  background: #fff;
  border: 1px solid #4F7CFF;
  color: #4F7CFF;
}

.detail-list-btn-primary:hover:not(:disabled) {
  background: rgba(79, 124, 255, .08);
}

.detail-list-btn-auto {
  flex: 1.4;
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  box-shadow: 0 4px 12px rgba(13, 107, 255, .25);
}

.detail-list-btn-auto:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(13, 107, 255, .35);
}

.detail-list-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ===== 上架流程弹窗 ===== */
.mall-listflow-dialog {
  max-width: 620px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
}

.mall-listflow-dialog .mall-modal-body {
  overflow-y: auto;
  padding: 18px 20px 20px;
}

.listflow-steps {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 12px 4px 16px;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 14px;
}

.listflow-step {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.step-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all .2s;
}

.step-text {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
  transition: all .2s;
}

.listflow-step.active .step-num {
  background: #4F7CFF;
  color: #fff;
}

.listflow-step.active .step-text {
  color: #1e293b;
}

.listflow-step.current .step-num {
  background: linear-gradient(135deg, #0865f4, #147dff);
  color: #fff;
  box-shadow: 0 2px 8px rgba(13, 107, 255, .35);
}

.listflow-step.current .step-text {
  color: #0865f4;
  font-weight: 700;
}

.step-line {
  flex: 1;
  height: 2px;
  background: #e2e8f0;
  border-radius: 1px;
  transition: all .2s;
  min-width: 16px;
}

.step-line.active {
  background: #4F7CFF;
}

.listflow-step-panel {
  min-height: 200px;
}

.listflow-section {
  margin-bottom: 12px;
}

.listflow-section-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.listflow-section-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  margin-bottom: 12px;
}

.listflow-form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
  position: relative;
}

.listflow-form-row label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.listflow-input {
  width: 100%;
  height: 36px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 0 12px;
  font-size: 13px;
  color: #1e293b;
  outline: none;
  box-sizing: border-box;
  transition: all .2s;
  font-family: inherit;
}

.listflow-input:focus {
  border-color: #4F7CFF;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(79, 124, 255, .1);
}

.listflow-textarea {
  height: auto;
  min-height: 90px;
  padding: 10px 12px;
  line-height: 1.6;
  resize: vertical;
}

.char-count {
  position: absolute;
  right: 8px;
  bottom: 6px;
  font-size: 11px;
  color: #94a3b8;
  background: rgba(248, 250, 252, .9);
  padding: 1px 6px;
  border-radius: 4px;
  pointer-events: none;
}

.listflow-hint {
  font-size: 11px;
  color: #64748b;
  line-height: 1.5;
  margin-top: 2px;
}

.listflow-hint-warn {
  color: #ef4444;
}

.listflow-hint-success {
  color: #16bf78;
}

.listflow-account-info,
.listflow-stock-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.listflow-stock-value {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  padding: 4px 10px;
  background: #f1f5f9;
  border-radius: 6px;
}

.listflow-address-area {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.listflow-image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-top: 8px;
}

.listflow-image-item {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  overflow: hidden;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}

.listflow-image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.listflow-image-empty {
  padding: 28px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
  background: #f8fafc;
  border: 1px dashed #e2e8f0;
  border-radius: 8px;
}

.listflow-step-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  margin-top: 12px;
}

.listflow-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
  border: none;
  font-family: inherit;
}

.listflow-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.listflow-btn-ghost {
  background: transparent;
  color: #64748b;
  border: 1px solid #e2e8f0;
}

.listflow-btn-ghost:hover:not(:disabled) {
  background: #f8fafc;
  color: #475569;
}

.listflow-btn-secondary {
  background: #fff;
  color: #4F7CFF;
  border: 1px solid #4F7CFF;
}

.listflow-btn-secondary:hover:not(:disabled) {
  background: rgba(79, 124, 255, .08);
}

.listflow-btn-primary {
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  box-shadow: 0 4px 10px rgba(13, 107, 255, .25);
}

.listflow-btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(13, 107, 255, .35);
}

.listflow-status {
  padding: 10px 12px;
  background: #f1f5f9;
  border-radius: 8px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  margin-bottom: 12px;
}

.listflow-status-warn {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
}

.listflow-error-tip {
  padding: 10px 12px;
  background: #fef2f2;
  color: #ef4444;
  font-size: 12px;
  border-radius: 8px;
  line-height: 1.5;
  margin-bottom: 12px;
  border: 1px solid #fecaca;
}

.listflow-message-tip {
  padding: 10px 12px;
  background: #ecfdf5;
  color: #065f46;
  font-size: 12px;
  border-radius: 8px;
  line-height: 1.5;
  margin-bottom: 12px;
  border: 1px solid #d1fae5;
}

.listflow-summary {
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.listflow-summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px dashed #e2e8f0;
}

.listflow-summary-row:last-child {
  border-bottom: none;
}

.listflow-summary-row span {
  color: #64748b;
  font-size: 12px;
  flex-shrink: 0;
}

.listflow-summary-row b {
  color: #1e293b;
  font-weight: 600;
  text-align: right;
  word-break: break-all;
}

.listflow-price {
  color: #ff3b30 !important;
  font-weight: 800 !important;
  font-size: 15px !important;
}

/* 响应式 */
@media (max-width: 640px) {
  .detail-info-grid {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  .detail-list-btns {
    flex-direction: column;
  }
  .listflow-steps {
    flex-wrap: wrap;
    gap: 8px;
  }
  .step-text {
    font-size: 11px;
  }
  .listflow-step-footer {
    flex-wrap: wrap;
  }
  .listflow-btn {
    flex: 1;
    min-width: 90px;
  }
}
</style>
