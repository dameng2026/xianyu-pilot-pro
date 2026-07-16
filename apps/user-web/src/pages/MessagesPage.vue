<template>
  <div class="xya-msg-page">
    <div class="xya-msg-layout">
      <aside class="xya-msg-sidebar">
        <div class="xya-msg-sidebar-head">
          <div>
            <h2>在线消息</h2>
            <p>集中处理买家咨询、会话状态与 AI 自动回复。</p>
          </div>
          <div class="xya-msg-head-actions">
            <button class="xya-msg-icon-btn" type="button" :disabled="loading" aria-label="刷新会话" @click="reload">
              <Icon name="refresh" />
            </button>
            <button class="xya-msg-primary-btn" type="button" :disabled="connectingWs || !accountsAvailable" @click="startCurrentConnection">
              {{ connectingWs ? '连接中...' : '重连消息' }}
            </button>
          </div>
        </div>

        <div class="xya-msg-sidebar-toolbar">
          <select v-model="query.xianyuAccountId" class="xya-msg-select" :disabled="!accountsAvailable">
            <option value="">{{ accountsAvailable ? '全部账号' : '账号列表不可用' }}</option>
            <option v-for="account in accounts" :key="account.id" :value="String(account.id)">
              {{ accountLabel(account) }}
            </option>
          </select>
          <input
            v-model.trim="keyword"
            class="xya-msg-search"
            type="text"
            placeholder="搜索买家、商品或消息内容"
          />
        </div>

        <div class="xya-msg-filter-row">
          <button
            v-for="item in filterTabs"
            :key="item.key"
            type="button"
            :class="['xya-msg-filter-btn', { active: activeFilter === item.key }]"
            @click="activeFilter = item.key"
          >
            <span>{{ item.label }}</span>
            <em>{{ item.count }}</em>
          </button>
        </div>

        <div v-if="captchaBannerText" :class="['xya-msg-captcha-banner', captchaBannerType]">
          <span class="xya-msg-captcha-text">{{ captchaBannerText }}</span>
          <button
            v-if="captchaSolveStatus?.status === 'fail' && captchaRetryCount >= CAPTCHA_MAX_RETRY"
            type="button"
            class="xya-msg-captcha-retry"
            :disabled="captchaSolveStatus?.status === 'retrying'"
            @click="handleManualCaptchaSolve"
          >重试求解</button>
        </div>
        <div v-if="error" class="xya-msg-alert">{{ error }}</div>
        <div v-if="accountsLoadError" class="xya-msg-alert">账号列表加载失败：{{ accountsLoadError }}</div>
        <div v-if="aiSettingsError" class="xya-msg-alert">自动回复状态加载失败：{{ aiSettingsError }}</div>
        <div v-if="tokenBalanceError" class="xya-msg-alert">Token 余额加载失败：{{ tokenBalanceError }}</div>

        <div ref="conversationListRef" class="xya-msg-conversation-list" @scroll="handleConversationListScroll">
          <div v-if="loading && displayList.length === 0" class="xya-msg-empty">正在加载会话...</div>
          <div v-else-if="!accountsAvailable" class="xya-msg-empty">账号列表不可用，无法加载会话。</div>
          <div v-else-if="accounts.length === 0" class="xya-msg-empty">暂无可用闲鱼账号，请先前往账号管理添加。</div>
          <div v-else-if="!conversationsAvailable" class="xya-msg-empty">会话列表不可用，请点击刷新重试。</div>
          <div v-else-if="displayList.length === 0 && !loading" class="xya-msg-empty">
            当前暂无可显示的在线会话
          </div>

          <button
            v-for="c in displayList"
            :key="conversationDedupeKey(c)"
            type="button"
            :class="['xya-msg-conversation', { active: conversationDedupeKey(selected) === conversationDedupeKey(c) }]"
            @click="selectChat(c)"
          >
            <div class="xya-msg-avatar-wrap">
              <img
                v-if="conversationAvatarUrl(c)"
                :src="conversationAvatarUrl(c)"
                class="xya-msg-avatar avatar-image"
                alt=""
              />
              <div v-else class="xya-msg-avatar">{{ avatarText(resolvePeerName(c)) }}</div>
              <span v-if="Number(c.unreadCount || 0) > 0" class="xya-msg-unread-dot">{{ Number(c.unreadCount || 0) > 99 ? '99+' : c.unreadCount }}</span>
            </div>

            <div class="xya-msg-conversation-main">
              <div class="xya-msg-conversation-top">
                <strong>{{ resolvePeerName(c) }}</strong>
                <span>{{ formatConversationTime(c.lastMessageTime || c.updatedAt) }}</span>
              </div>
              <div class="xya-msg-conversation-middle">
                <span v-if="c.lastIsAutoReply" class="xya-msg-ai-tag">AI</span>
                <span class="xya-msg-conversation-preview">{{ shortText(c.msg || c.lastMessage || c.lastContent || '暂无消息', 46) }}</span>
              </div>
              <div class="xya-msg-conversation-bottom">
                <div class="xya-msg-goods-wrap">
                  <img v-if="c.goodsCoverPic" :src="c.goodsCoverPic" class="xya-msg-goods-thumb" alt="" />
                  <span class="xya-msg-goods-text">{{ c.product || c.goodsTitle || '未关联商品' }}</span>
                </div>
                <span class="xya-msg-status-chip" :class="conversationStatusClass(c)">{{ conversationStatusText(c) }}</span>
              </div>
            </div>
          </button>

          <div v-if="loadingMoreConversations" class="xya-msg-more-wrap">
            <div class="xya-msg-more-tip">正在加载更多会话...</div>
          </div>
          <div v-else-if="displayList.length > 0 && !conversationHasMore" class="xya-msg-more-wrap">
            <div class="xya-msg-more-tip">暂无更多会话</div>
          </div>
        </div>

        <div class="xya-msg-footer-note">共 {{ displayList.length }} 条会话</div>
      </aside>

      <section class="xya-msg-chat-panel">
        <template v-if="selected && (accountSelectionReady || cacheHydrated)">
          <div class="xya-msg-chat-head">
            <div class="xya-msg-chat-title">
              <img
                v-if="conversationAvatarUrl(selected)"
                :src="conversationAvatarUrl(selected)"
                class="xya-msg-avatar large avatar-image"
                alt=""
              />
              <div v-else class="xya-msg-avatar large">{{ avatarText(resolvePeerName(selected)) }}</div>
              <div>
                <h3>{{ resolvePeerName(selected) }}</h3>
                <div class="xya-msg-chat-goods">
                  <img v-if="selected.goodsCoverPic" :src="selected.goodsCoverPic" class="xya-msg-goods-thumb small" alt="" />
                  <p>{{ selected.product || selected.goodsTitle || '未关联商品' }}</p>
                </div>
              </div>
            </div>

            <div class="xya-msg-chat-actions">
              <button type="button" class="xya-msg-ghost-btn" :disabled="switchingAccount || statusUpdating" @click="transferSession">转人工</button>
              <button type="button" class="xya-msg-ghost-btn danger" :disabled="switchingAccount || statusUpdating" @click="endSession">结束会话</button>
            </div>
          </div>

          <div ref="messagesContainer" class="xya-msg-chat-stream">
            <div v-if="contextLoading && contextMessages.length === 0" class="xya-msg-empty">正在加载消息记录...</div>
            <div v-else-if="!contextAvailable" class="xya-msg-empty">消息记录不可用，已禁用发送操作。</div>
            <div v-else-if="contextMessages.length === 0" class="xya-msg-empty">当前会话暂无历史消息</div>

            <div
              v-for="m in contextMessages"
              :key="messageIdentity(m)"
              :class="['xya-msg-bubble-row', { me: m.isMe, 'image-message': shouldRenderImageMessage(m) }]"
            >
              <img
                v-if="!m.isMe && conversationAvatarUrl(selected)"
                :src="conversationAvatarUrl(selected)"
                class="xya-msg-avatar small avatar-image"
                alt=""
              />
              <div v-else-if="!m.isMe" class="xya-msg-avatar small">{{ avatarText(resolvePeerName(selected)) }}</div>

              <div v-if="shouldRenderImageMessage(m)" :class="['xya-msg-image-message', { me: m.isMe }]">
                <div :class="['xya-msg-image-stack', { multiple: m.imageUrls.length > 1 }]">
                  <button
                    v-for="(img, index) in m.imageUrls"
                    :key="`${img}-${index}`"
                    type="button"
                    class="xya-msg-image-card"
                    @click="openImagePreview(img)"
                  >
                    <img
                      :src="img"
                      class="xya-msg-image"
                      alt=""
                      draggable="false"
                    />
                  </button>
                </div>

                <div class="xya-msg-image-message-meta">
                  <span class="xya-msg-image-message-time">{{ formatMessageTime(m.messageTime) }}</span>
                  <span v-if="m.sendStatus === 'failed'" class="danger-text">发送失败</span>
                  <span v-else-if="m.sendStatus === 'sending'">发送中</span>
                </div>
              </div>

              <div v-else class="xya-msg-bubble">
                <div v-if="m.isAutoReply" class="xya-msg-bubble-label">AI 自动回复</div>

                <template v-if="m.imageUrls?.length">
                  <div :class="['xya-msg-bubble-images', { multiple: m.imageUrls.length > 1 }]">
                    <button
                      v-for="(img, index) in m.imageUrls"
                      :key="`${img}-${index}`"
                      type="button"
                      class="xya-msg-image-card"
                      @click="openImagePreview(img)"
                    >
                      <img
                        :src="img"
                        class="xya-msg-image"
                        alt=""
                        draggable="false"
                      />
                      <span class="xya-msg-image-tag">图片</span>
                    </button>
                  </div>
                </template>

                <div v-if="m.text && (!m.imageUrls?.length || m.text !== '[图片]')" class="xya-msg-bubble-text">
                  {{ m.text }}
                </div>

                <div class="xya-msg-bubble-meta">
                  <span>{{ formatMessageTime(m.messageTime) }}</span>
                  <span v-if="m.sendStatus === 'failed'" class="danger-text">发送失败</span>
                  <span v-else-if="m.sendStatus === 'sending'">发送中</span>
                </div>
              </div>
            </div>
          </div>

          <div class="xya-msg-composer">
            <div class="xya-msg-composer-top">
              <div v-if="quickTemplates.length" class="xya-msg-template-list">
                <button
                  v-for="item in quickTemplates"
                  :key="item.id || item.title"
                  type="button"
                  class="xya-msg-template-item"
                  :title="item.content || item.text"
                  @click="insertTemplate(item)"
                >
                  <strong>{{ item.title || '模板' }}</strong>
                  <span>{{ shortText(item.content || item.text || '', 20) }}</span>
                </button>
              </div>
              <span v-if="templatesLoadError" class="xya-msg-template-error">快捷模板不可用</span>
              <button type="button" class="xya-msg-link-btn" @click="showTemplateModal = true">更多模板</button>
            </div>

            <div class="xya-msg-composer-toolbar">
              <button type="button" class="xya-msg-ghost-btn" :disabled="switchingAccount || !contextAvailable" @click="triggerImagePick">发送图片</button>
              <button type="button" class="xya-msg-ghost-btn" :disabled="switchingAccount || !contextAvailable || !selected?.xyGoodsId" @click="sendGoodsLink(selected?.xyGoodsId)">发送商品链接</button>
              <button type="button" class="xya-msg-ghost-btn" :disabled="switchingAccount || aiSwitchLoading || !aiSettingsAvailable" @click="toggleAiAutoReply">
                {{ aiSwitchLoading ? '处理中...' : aiAutoReplyEnabled === true ? '关闭当前自动回复' : aiAutoReplyEnabled === false ? '开启当前自动回复' : '自动回复状态未知' }}
              </button>
              <input ref="imageInput" type="file" accept="image/*" hidden @change="handleImagePick" />
            </div>

            <textarea
              v-model="draft"
              class="xya-msg-textarea"
              :disabled="switchingAccount || !contextAvailable"
              rows="4"
              placeholder="输入消息，Enter 发送，Shift+Enter 换行"
              @keydown.enter.exact.prevent="sendCurrentMessage"
            />

            <div class="xya-msg-send-row">
              <div class="xya-msg-send-meta">
                <span>{{ realtimeStatusText }}</span>
                <span v-if="sendingImage">图片上传中</span>
              </div>
              <button type="button" class="xya-msg-primary-btn" :disabled="!canSend" @click="sendCurrentMessage">
                {{ sending ? '发送中...' : '发送消息' }}
              </button>
            </div>
          </div>
        </template>

        <div v-else class="xya-msg-empty big">
          请选择左侧会话开始处理消息
        </div>
      </section>

      <aside class="xya-msg-detail-panel">
        <section class="xya-msg-card">
          <h3>商品信息</h3>
          <template v-if="selected && (accountSelectionReady || cacheHydrated)">
            <div class="xya-msg-product">
              <img :src="conversationGoodsCover(selected)" class="xya-msg-product-cover" alt="" />
              <div class="xya-msg-product-info">
                <strong>{{ selected.product || selected.goodsTitle || '未关联商品' }}</strong>
                <span>ID: {{ selected.xyGoodsId || selected.goodsId || '-' }}</span>
                <div class="xya-msg-card-actions">
                  <button type="button" class="xya-msg-ghost-btn" :disabled="!selected.xyGoodsId" @click="viewGoofishItem(selected.xyGoodsId)">
                    查看商品
                  </button>
                  <button type="button" class="xya-msg-ghost-btn" :disabled="!selected.xyGoodsId" @click="sendGoodsLink(selected.xyGoodsId)">
                    发送商品
                  </button>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="xya-msg-card-empty">选中会话后可查看当前商品。</div>
        </section>

        <section class="xya-msg-card">
          <h3 class="xya-msg-order-head">
            客户订单
            <span v-if="customerOrders.length" class="xya-msg-order-count">({{ customerOrders.length }})</span>
            <button
              type="button"
              class="xya-msg-order-refresh"
              :class="{ spinning: loadingCustomerOrders }"
              :disabled="!selected || loadingCustomerOrders"
              :title="loadingCustomerOrders ? '加载中…' : '刷新订单'"
              @click="refreshCustomerOrders"
            >
              <Icon name="refresh" />
            </button>
          </h3>
          <template v-if="selected">
            <div v-if="loadingCustomerOrders && !customerOrders.length" class="xya-msg-card-empty">正在加载客户订单…</div>
            <div v-else-if="customerOrdersError" class="xya-msg-card-empty xya-msg-order-error">{{ customerOrdersError }}</div>
            <div v-else-if="!customerOrders.length" class="xya-msg-card-empty">暂未匹配到该客户订单。</div>
            <div v-else class="xya-msg-order-list">
              <div v-for="order in customerOrders" :key="order.id" class="xya-msg-order-item">
                <div class="xya-msg-order-item-main">
                  <div class="xya-msg-order-cover-wrap">
                    <span class="xya-msg-order-cover-placeholder">
                      <Icon name="product" />
                    </span>
                    <img
                      v-if="resolveOrderCover(order)"
                      :src="resolveOrderCover(order)"
                      class="xya-msg-order-cover"
                      alt=""
                      @error="onOrderCoverError"
                    />
                  </div>
                  <div class="xya-msg-order-item-info">
                    <div class="xya-msg-order-title" :title="orderItemTitle(resolveOrderFirstItem(order))">
                      {{ orderItemTitle(resolveOrderFirstItem(order)) }}
                    </div>
                    <div class="xya-msg-order-meta">
                      <span class="xya-msg-order-amount">{{ formatOrderAmount(order.totalAmount) }}<template v-if="Number(order.quantityTotal) > 0"> × {{ order.quantityTotal }}</template></span>
                      <span class="xya-msg-order-status" :class="customerOrderStatusClass(order.orderStatus)">{{ customerOrderStatusText(order.orderStatus) }}</span>
                    </div>
                    <div class="xya-msg-order-no" :title="order.externalOrderId || order.id">订单号：{{ order.externalOrderId || order.id }}</div>
                    <div v-if="order.deliveryFailReason" class="xya-msg-order-fail">{{ order.deliveryFailReason }}</div>
                    <div class="xya-msg-order-time">{{ formatOrderTime(order.createTime) }}</div>
                  </div>
                </div>
                <div class="xya-msg-card-actions">
                  <button type="button" class="xya-msg-ghost-btn" :disabled="loadingOrderDetail" @click="viewOrderDetail(order.id)">订单详情</button>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="xya-msg-card-empty">选中会话后可查看该客户订单。</div>
        </section>

        <section class="xya-msg-card">
          <h3>自动回复状态</h3>
          <div class="xya-msg-metrics">
            <div>
              <span>当前作用范围</span>
              <strong>{{ aiScopeLabel }}</strong>
            </div>
            <div>
              <span>当前状态</span>
              <strong :class="{ 'success-text': aiAutoReplyEnabled === true, 'danger-text': aiAutoReplyEnabled === false }">
                {{ aiAutoReplyEnabled === true ? 'AI 自动接待中' : aiAutoReplyEnabled === false ? '已暂停' : '状态未知' }}
              </strong>
            </div>
            <div>
              <span>Token 余额</span>
              <strong>{{ tokenBalanceText }}</strong>
            </div>
            <div>
              <span>账号登录</span>
              <strong>{{ currentAccountLoginText }}</strong>
            </div>
          </div>
          <div
            class="xya-msg-card-status"
            :class="{ warning: aiAutoReplyEnabled === true && !tokenBalanceError && Number(tokenBalance) <= 0, success: aiAutoReplyEnabled === true && !tokenBalanceError && Number(tokenBalance) > 0 }"
          >
            {{ aiRuntimeStatusText }}
          </div>
          <div class="xya-msg-card-actions">
            <button type="button" class="xya-msg-primary-btn" :disabled="switchingAccount || aiSwitchLoading || !aiSettingsAvailable" @click="toggleAiAutoReply">
              {{ aiAutoReplyEnabled === true ? '关闭自动回复' : aiAutoReplyEnabled === false ? '开启自动回复' : '自动回复状态未知' }}
            </button>
            <button type="button" class="xya-msg-ghost-btn" @click="handleRefreshCurrentAccountLoginState">刷新登录状态</button>
          </div>
        </section>

        <section class="xya-msg-card">
          <h3>实时诊断</h3>
          <div class="xya-msg-metrics">
            <div>
              <span>SSE 状态</span>
              <strong>{{ sseHealthy ? '实时正常' : '已切换轮询兜底' }}</strong>
            </div>
            <div>
              <span>最后活动</span>
              <strong>{{ lastRealtimeActivityText }}</strong>
            </div>
            <div>
              <span>账号连接</span>
              <strong>{{ currentWsText }}</strong>
            </div>
          </div>

          <div v-if="events.length" class="xya-msg-event-list">
            <div v-for="(item, index) in events" :key="`${item.time}-${index}`" class="xya-msg-event-item">
              <strong>{{ item.time }}</strong>
              <span>{{ item.text }}</span>
            </div>
          </div>
          <div v-else class="xya-msg-card-empty">暂无诊断事件。</div>
        </section>
      </aside>
    </div>

    <div v-if="showTemplateModal" class="xya-msg-modal-mask" @click.self="showTemplateModal = false">
      <div class="xya-msg-modal">
        <div class="xya-msg-modal-head">
          <h3>快捷回复模板</h3>
          <button type="button" class="xya-msg-icon-btn" @click="showTemplateModal = false">
            <Icon name="close" />
          </button>
        </div>

        <div class="xya-msg-modal-body">
          <div v-if="templatesLoadError" class="xya-msg-card-empty error-state" role="alert">
            <strong>快捷模板暂时无法加载</strong>
            <span>{{ templatesLoadError }}</span>
            <button type="button" class="xya-msg-primary-btn" @click="loadQuickTemplates">重新加载</button>
          </div>
          <template v-else>
          <div class="xya-msg-template-edit-row">
            <input v-model="editingTemplate.title" type="text" placeholder="模板标题" class="xya-msg-modal-input" />
            <textarea v-model="editingTemplate.content" placeholder="模板内容" class="xya-msg-modal-textarea" rows="3"></textarea>
            <div class="xya-msg-template-edit-actions">
              <button type="button" class="xya-msg-ghost-btn" @click="resetTemplateEdit">清空</button>
              <button type="button" class="xya-msg-primary-btn" @click="saveTemplate">保存模板</button>
            </div>
          </div>

          <div class="xya-msg-template-manage-list">
            <div v-for="item in allTemplates" :key="item.id" class="xya-msg-template-manage-item">
              <div class="xya-msg-template-manage-info">
                <strong>{{ item.title || '未命名模板' }}</strong>
                <span>{{ item.content || item.text }}</span>
              </div>
              <div class="xya-msg-template-manage-actions">
                <button type="button" class="xya-msg-ghost-btn" @click="insertTemplate(item)">插入</button>
                <button type="button" class="xya-msg-ghost-btn" @click="editTemplate(item)">编辑</button>
                <button type="button" class="xya-msg-ghost-btn danger" @click="deleteTemplate(item.id)">删除</button>
              </div>
            </div>
            <div v-if="!allTemplates.length" class="xya-msg-card-empty">暂无快捷模板。</div>
          </div>
          </template>
        </div>
      </div>
    </div>

    <div v-if="previewImageUrl" class="xya-msg-modal-mask xya-msg-image-preview-mask" @click.self="closeImagePreview">
      <div class="xya-msg-image-preview">
        <button type="button" class="xya-msg-image-preview-close" @click="closeImagePreview">
          <Icon name="close" />
        </button>
        <img :src="previewImageUrl" alt="" />
      </div>
    </div>

    <div v-if="showOrderDetailModal" class="xya-msg-modal-mask" @click.self="closeOrderDetailModal">
      <div class="xya-msg-order-modal">
        <div class="xya-msg-modal-head">
          <h3>订单详情</h3>
          <button type="button" class="xya-msg-icon-btn" @click="closeOrderDetailModal">
            <Icon name="close" />
          </button>
        </div>
        <div class="xya-msg-order-modal-body">
          <div v-if="loadingOrderDetail" class="xya-msg-card-empty">正在加载订单详情…</div>
          <div v-else-if="orderDetailError" class="xya-msg-card-empty xya-msg-order-error">{{ orderDetailError }}</div>
          <template v-else-if="orderDetailData">
            <div class="xya-msg-order-detail-section">
              <div class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">订单号</span>
                <strong class="xya-msg-order-detail-value">{{ orderDetailData.externalOrderId || orderDetailData.id || '-' }}</strong>
              </div>
              <div class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">订单状态</span>
                <span class="xya-msg-order-status" :class="customerOrderStatusClass(orderDetailData.orderStatus)">{{ customerOrderStatusText(orderDetailData.orderStatus) }}</span>
              </div>
              <div class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">商品总额</span>
                <strong class="xya-msg-order-detail-value">{{ formatOrderAmount(orderDetailData.totalAmount) }}</strong>
              </div>
              <div class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">买家昵称</span>
                <span class="xya-msg-order-detail-value">{{ orderDetailData.buyerName || '-' }}</span>
              </div>
              <div class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">买家ID</span>
                <span class="xya-msg-order-detail-value">{{ orderDetailData.buyerId || '-' }}</span>
              </div>
              <div class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">下单时间</span>
                <span class="xya-msg-order-detail-value">{{ formatOrderTime(orderDetailData.createTime) }}</span>
              </div>
              <div v-if="orderDetailData.payTime" class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">付款时间</span>
                <span class="xya-msg-order-detail-value">{{ formatOrderTime(orderDetailData.payTime) }}</span>
              </div>
              <div v-if="orderDetailData.shipTime" class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">发货时间</span>
                <span class="xya-msg-order-detail-value">{{ formatOrderTime(orderDetailData.shipTime) }}</span>
              </div>
              <div v-if="orderDetailData.deliveryMethod" class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">发货方式</span>
                <span class="xya-msg-order-detail-value">{{ orderDetailData.deliveryMethod }}</span>
              </div>
              <div v-if="orderDetailData.deliveryStatus" class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">发货状态</span>
                <span class="xya-msg-order-detail-value">{{ orderDetailData.deliveryStatus }}</span>
              </div>
              <div v-if="orderDetailData.deliveryFailReason" class="xya-msg-order-detail-row">
                <span class="xya-msg-order-detail-label">失败原因</span>
                <span class="xya-msg-order-detail-value xya-msg-order-fail">{{ orderDetailData.deliveryFailReason }}</span>
              </div>
            </div>
            <div v-if="orderDetailData.items && orderDetailData.items.length" class="xya-msg-order-detail-section">
              <h4 class="xya-msg-order-detail-subtitle">商品明细</h4>
              <div v-for="item in orderDetailData.items" :key="item.id" class="xya-msg-order-detail-item">
                <div class="xya-msg-order-detail-item-title">{{ item.goodsTitle || '-' }}</div>
                <div class="xya-msg-order-detail-item-meta">
                  <span>¥{{ Number(item.goodsPrice || 0).toFixed(2) }}</span>
                  <span>×{{ Math.max(Number(item.goodsCount) || 1, 1) }}</span>
                  <span v-if="item.specSummary || (item.specName && item.specValue)" class="xya-msg-order-detail-spec">{{ item.specSummary || `${item.specName}: ${item.specValue}` }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import Icon from '../components/Icon.vue'
import { getLiteAccounts } from '../api/accounts.js'
import {
  onlineConversations,
  messageContext,
  markConversationRead,
  queryUserAvatars,
  updateConversationStatus,
} from '../api/messages.js'
import { checkLogin, sendImageMessage, sendMessage, startWebSocket, websocketStatus } from '../api/websocket.js'
import { uploadImage } from '../api/misc.js'
import { getCustomerOrders, getOrderDetail } from '../api/orders.js'
import { imageUploadValidationMessage } from '../utils/imageUploadPolicy.js'
import { getBusinessSettings, saveBusinessSettings } from '../api/businessSettings.js'
import { deleteQuickReplyTemplate, getAiCsSetting, getTokenBalance, listQuickReplyTemplates, saveQuickReplyTemplate } from '../api/quickReply.js'
import {
  getAutoReplyScopeProducts,
  getAutoReplyScopeStatus,
  updateAccountAutoReplyScope,
  updateProductAutoReplyScope,
} from '../api/autoReplyScope.js'
import { confirmAction } from '../utils/confirmAction.js'
import {
  accountAuthUsable,
  accountLoginHint,
  accountWsConnectionState,
  pickPreferredAccount,
  resolveAccountAuthDisplayState,
  resolveAccountAutoReplyScopeEnabled,
  shouldAttemptAccountWebSocketStart,
} from '../utils/accountAuth.js'
import {
  applyConversationUnreadState,
  compareConversationStatus,
  extractImageMessageUrls,
  extractMessageDisplayText,
  findConversationByIdentity,
  findConversationMatchIndex,
  findPreservedConversation,
  getConversationIdentityKey,
  getConversationRecordId,
  isRealtimeConversationEvent,
  isRealtimeConversationSignalStale,
  isSameConversationByPayload,
  matchesAccountSelection,
  mergeConversationDisplaySnapshot,
  mergeConversationSnapshots,
  mergeSelectedConversationSnapshot,
  resolveConversationGoodsCover,
  resolveConversationGoodsId,
  resolveConversationGoodsTitle,
  resolveAccountSwitchState,
  formatDisplayDateTime,
  parseMessageTimestamp,
  shouldApplyContextLoadResult,
  shouldApplyConversationLoadResult,
  shouldMarkConversationAsRead,
  shouldEnableMainComposerSend,
  shouldRunMessagePolling,
  sortMessagesByTime,
} from '../utils/messagesPageState.js'
import { createRequestGate } from '../utils/requestLifecycle.js'
import { createSessionPrivacyStore } from '../utils/privacySession.js'
import { resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'
import { useCaptchaSolver } from '../composables/useCaptchaSolver.js'

const POLL_INTERVAL_SSE_HEALTHY = 8000
const POLL_INTERVAL_FALLBACK = 2500
const SSE_STALE_TIMEOUT = 15000
const CHAT_BOTTOM_THRESHOLD = 72
const CONVERSATION_LIST_LOAD_MORE_THRESHOLD = 72
const MESSAGE_CACHE_VERSION = 1
const MESSAGE_CACHE_TTL = 5 * 60 * 1000
const MESSAGE_CACHE_PRUNE_INTERVAL = 2 * 60 * 1000
const MESSAGE_CACHE_MAX_CONVERSATIONS = 120
const MESSAGE_CACHE_MAX_CONTEXTS = 12
const MESSAGE_CACHE_MAX_MESSAGES = 120
const LEGACY_IMAGE_PLACEHOLDER = '[\u9365\u5267\u5896]'
const messagesPageCacheStore = createSessionPrivacyStore('messages-page-cache:v2', { ttlMs: MESSAGE_CACHE_TTL })
const messagesPageAccountsStore = createSessionPrivacyStore('messages-page-accounts:v2', { ttlMs: MESSAGE_CACHE_TTL })

const accounts = ref([])
const conversations = ref([])
const contextMessages = ref([])
const selected = ref(null)
const loading = ref(false)
const contextLoading = ref(false)
const loadingMoreConversations = ref(false)
const sending = ref(false)
const sendingImage = ref(false)
const connectingWs = ref(false)
const statusUpdating = ref(false)
const error = ref('')

// === 滑块求解状态 ===
const { solveStates, solveManually, getAccountSolveStatus } = useCaptchaSolver()
const captchaRetryCount = ref(0)
const CAPTCHA_MAX_RETRY = 3
const captchaSolveStatus = computed(() => {
  const aid = selectedAccountId()
  if (!aid) return null
  return getAccountSolveStatus(aid)
})
const captchaBannerText = computed(() => {
  const s = captchaSolveStatus.value
  if (!s) return ''
  if (s.status === 'retrying') return `正在自动求解滑块…（第 ${captchaRetryCount.value + 1} 次尝试）`
  if (s.status === 'success') return '滑块求解成功，正在刷新消息…'
  if (s.status === 'fail') {
    if (captchaRetryCount.value < CAPTCHA_MAX_RETRY) return `滑块求解失败，正在重试…（${captchaRetryCount.value}/${CAPTCHA_MAX_RETRY}）`
    return '滑块求解失败，请手动处理或重新扫码登录'
  }
  return ''
})
const captchaBannerType = computed(() => {
  const s = captchaSolveStatus.value
  if (!s) return ''
  if (s.status === 'retrying') return 'solving'
  if (s.status === 'success') return 'success'
  if (s.status === 'fail') return captchaRetryCount.value < CAPTCHA_MAX_RETRY ? 'solving' : 'fail'
  return ''
})
const keyword = ref('')
const activeFilter = ref('all')
const events = ref([])
const imageInput = ref(null)
const conversationListRef = ref(null)
const messagesContainer = ref(null)
const draft = ref('')
const previewImageUrl = ref('')
const showTemplateModal = ref(false)
const quickTemplates = ref([])
const allTemplates = ref([])
const templatesLoadError = ref('')
const templatesAvailable = ref(false)
const tokenBalance = ref(null)
const tokenBalanceError = ref('')
const aiGlobalEnabled = ref(null)
const aiAccountScopes = ref({})
const aiScopeProducts = ref([])
const aiAutoReplyEnabled = ref(null)
const aiSettingsAvailable = ref(false)
const aiSettingsError = ref('')
const accountsAvailable = ref(false)
const accountsLoadError = ref('')
const conversationsAvailable = ref(false)
const contextAvailable = ref(false)
const aiSwitchLoading = ref(false)
const sseHealthy = ref(false)
const lastSseActivity = ref(0)
const deletedConversations = ref(new Set())
const conversationCursor = ref(null)
const conversationHasMore = ref(false)
const userInfoCacheRef = ref({})
const switchingAccount = ref(false)
const accountSelectionReady = ref(false)
const cacheHydrated = ref(false)
const aiSettingsGate = createRequestGate()

// === 客户订单板块状态 ===
const customerOrders = ref([])
const loadingCustomerOrders = ref(false)
const customerOrdersError = ref('')
const customerOrdersGate = createRequestGate()
const showOrderDetailModal = ref(false)
const orderDetailData = ref(null)
const loadingOrderDetail = ref(false)
const orderDetailError = ref('')
const CUSTOMER_ORDER_STATUS_META = {
  0: { text: '待付款', className: 'warning' },
  1: { text: '已付款', className: 'info' },
  2: { text: '待发货', className: 'warning' },
  3: { text: '已发货', className: 'success' },
  4: { text: '已完成', className: 'success' },
  5: { text: '已关闭', className: 'muted' },
}

const query = reactive({ xianyuAccountId: '', pageSize: 50 })
const editingTemplate = reactive({ id: null, title: '', content: '' })
const wsStateMap = reactive({})

let pollingTimer = null
let visibilityChangeHandler = null
let conversationLoadRequestId = 0
let contextLoadRequestId = 0
let lastWsHealthCheck = 0
let accountSwitchRequestId = 0
let cachePersistTimer = null
let cachePruneTimer = null
let avatarHydrationTimer = null
const prefetchedConversationPages = new Map()
const prefetchedConversationPromises = new Map()

const filterTabs = computed(() => {
  const list = accountSelectionReady.value || cacheHydrated.value ? conversations.value : []
  return [
    { key: 'all', label: '全部', count: list.length },
    { key: 'unread', label: '未读', count: list.filter(item => Number(item.unreadCount || 0) > 0).length },
    { key: 'active', label: '进行中', count: list.filter(item => normalizeConversationStatus(item) === 'inProgress').length },
    { key: 'done', label: '已结束', count: list.filter(item => normalizeConversationStatus(item) !== 'inProgress').length },
  ]
})

const displayList = computed(() => {
  const sourceList = accountSelectionReady.value || cacheHydrated.value ? conversations.value : []
  const search = keyword.value.trim().toLowerCase()
  return sourceList.filter(item => {
    const status = normalizeConversationStatus(item)
    if (activeFilter.value === 'unread' && Number(item.unreadCount || 0) <= 0) return false
    if (activeFilter.value === 'active' && status !== 'inProgress') return false
    if (activeFilter.value === 'done' && status === 'inProgress') return false
    if (!search) return true
    return [
      resolvePeerName(item),
      item.product,
      item.goodsTitle,
      item.msg,
      item.lastMessage,
      item.lastContent,
      item.peerUserId,
    ]
      .map(value => String(value || '').toLowerCase())
      .some(value => value.includes(search))
  })
})

const aiScopeLabel = computed(() => {
  if (selected.value?.xyGoodsId) return '当前商品'
  if (query.xianyuAccountId) return '当前账号'
  return '全局'
})

const tokenBalanceText = computed(() => {
  if (tokenBalanceError.value) return '状态未知'
  if (tokenBalance.value === null) return '加载中...'
  const balance = Number(tokenBalance.value)
  return balance > 0 ? `${balance} tokens` : 'token为零'
})

const aiRuntimeStatusText = computed(() => {
  if (aiSwitchLoading.value) return '正在更新自动回复状态'
  if (switchingAccount.value) return '正在切换账号'
  if (!aiSettingsAvailable.value || aiAutoReplyEnabled.value === null) return '自动回复状态未知'
  if (aiAutoReplyEnabled.value && tokenBalanceError.value) return '自动回复已开启，Token 余额未知'
  if (aiAutoReplyEnabled.value && Number(tokenBalance.value) <= 0) return 'token为零'
  return aiAutoReplyEnabled.value ? 'AI 自动回复已开启' : 'AI 自动回复已关闭'
})

const currentAccountLoginText = computed(() => {
  const account = currentAccount()
  if (!account) return '未选择账号'
  const state = resolveAccountAuthDisplayState(account, currentWsState())
  if (!state.authKnown) return '登录状态未知'
  return state.usable ? '登录正常' : accountLoginHint(account, currentWsState())
})

const currentWsText = computed(() => {
  const state = currentWsState()
  const connectionState = accountWsConnectionState(currentAccount(), state)
  if (connectionState === true) return 'WebSocket 在线'
  if (connectionState === false) return state?.status || '未连接'
  return state?.lastError ? `状态未知：${state.lastError}` : '连接状态未知'
})

const lastRealtimeActivityText = computed(() => {
  if (!lastSseActivity.value) return '暂无实时事件'
  return formatConversationTime(lastSseActivity.value)
})

const realtimeStatusText = computed(() => {
  if (!query.xianyuAccountId && !selected.value?.xianyuAccountId) return '请先选择账号'
  return sseHealthy.value ? 'SSE 正常，轮询已降频' : '实时信号异常，已启用高频轮询兜底'
})

const canSend = computed(() => {
  return contextAvailable.value && shouldEnableMainComposerSend({
    accountId: selectedAccountId(),
    conversationSid: selected.value?.sid,
    isSystemConversation: false,
    sending: switchingAccount.value || sending.value || sendingImage.value,
    isDeletedConversation: deletedConversations.value.has(conversationDedupeKey(selected.value)),
    draftText: draft.value,
  })
})

function unwrap(payload) {
  return payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'data')
    ? payload.data
    : payload
}

function selectedAccountId() {
  const direct = Number(query.xianyuAccountId || 0)
  if (direct > 0) return direct
  return Number(selected.value?.xianyuAccountId || selected.value?.accountId || 0)
}

function currentAccount() {
  const accountId = selectedAccountId()
  return accounts.value.find(item => Number(item.id) === accountId) || null
}

function currentWsState() {
  const accountId = selectedAccountId()
  return wsStateMap[accountId] || null
}

function accountLabel(account) {
  return account?.accountNote || account?.nickname || account?.displayName || account?.externalUid || account?.unb || `账号${account?.id || ''}`
}

function avatarText(value) {
  const text = String(value || '').trim()
  return text ? text.slice(0, 1).toUpperCase() : '买'
}

function shortText(value, max = 40) {
  const text = String(value || '').trim()
  if (text.length <= max) return text
  return `${text.slice(0, max)}...`
}

function normalizeSid(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const withoutPrefix = raw.startsWith('sid:') ? raw.slice(4) : raw
  return withoutPrefix.endsWith('@goofish') ? withoutPrefix.slice(0, -8) : withoutPrefix
}

function normalizePeerUserId(value) {
  const raw = String(value || '').trim()
  if (!raw || raw.startsWith('sid:')) return ''
  return raw.endsWith('@goofish') ? raw.slice(0, -8) : raw
}

function normalizeDisplayImage(url) {
  const value = String(url || '').trim()
  return resolveTrustedMediaUrl(value)
}

function createEmptyMessagesPageCacheEnvelope() {
  return {
    version: MESSAGE_CACHE_VERSION,
    selectedAccountId: '',
    accounts: {},
  }
}

function pruneMessagesPageCacheEnvelope(envelope, now = Date.now()) {
  const base = envelope && typeof envelope === 'object' ? envelope : createEmptyMessagesPageCacheEnvelope()
  const accountsMap = base.accounts && typeof base.accounts === 'object' ? base.accounts : {}
  const nextAccounts = {}

  Object.entries(accountsMap).forEach(([accountId, entry]) => {
    const normalizedAccountId = String(accountId || '').trim()
    if (!normalizedAccountId) return
    const conversationsList = mergeConversationSnapshots(
      (Array.isArray(entry?.conversations) ? entry.conversations : [])
        .filter(Boolean)
        .slice(0, MESSAGE_CACHE_MAX_CONVERSATIONS)
    )
    const rawContexts = entry?.contexts && typeof entry.contexts === 'object' ? entry.contexts : {}
    const contexts = Object.entries(rawContexts)
      .map(([key, value]) => ({
        key,
        savedAt: Number(value?.savedAt || 0),
        messages: normalizeContextMessageList(value?.messages || []).slice(-MESSAGE_CACHE_MAX_MESSAGES),
      }))
      .filter(item => item.key && item.savedAt && now - item.savedAt <= MESSAGE_CACHE_TTL && item.messages.length)
      .sort((left, right) => right.savedAt - left.savedAt)
      .slice(0, MESSAGE_CACHE_MAX_CONTEXTS)

    const savedAt = Number(entry?.savedAt || 0)
    const stillFresh = savedAt && now - savedAt <= MESSAGE_CACHE_TTL
    if (!stillFresh && !contexts.length) return

    nextAccounts[normalizedAccountId] = {
      savedAt: stillFresh ? savedAt : (contexts[0]?.savedAt || now),
      selectedConversationKey: String(entry?.selectedConversationKey || '').trim(),
      nextCursor: entry?.nextCursor ?? null,
      hasMore: Boolean(entry?.hasMore),
      conversations: stillFresh ? conversationsList : [],
      userInfoCache: stillFresh && entry?.userInfoCache && typeof entry.userInfoCache === 'object' ? entry.userInfoCache : {},
      contexts: Object.fromEntries(
        contexts.map(item => [item.key, { savedAt: item.savedAt, messages: item.messages }])
      ),
    }
  })

  const selectedAccountId = String(base.selectedAccountId || '').trim()
  return {
    version: MESSAGE_CACHE_VERSION,
    selectedAccountId: Object.prototype.hasOwnProperty.call(nextAccounts, selectedAccountId) ? selectedAccountId : '',
    accounts: nextAccounts,
  }
}

function readMessagesPageCacheEnvelope() {
  try {
    const cached = messagesPageCacheStore.read()
    return cached ? pruneMessagesPageCacheEnvelope(cached) : createEmptyMessagesPageCacheEnvelope()
  } catch {
    return createEmptyMessagesPageCacheEnvelope()
  }
}

function writeMessagesPageCacheEnvelope(envelope) {
  try {
    messagesPageCacheStore.write(pruneMessagesPageCacheEnvelope(envelope))
  } catch (e) {
    console.warn('[MSG] writeMessagesPageCacheEnvelope failed:', e)
  }
}

function readCachedAccounts() {
  try {
    const parsed = messagesPageAccountsStore.read()
    if (!parsed) return []
    const savedAt = Number(parsed?.savedAt || 0)
    if (!savedAt || Date.now() - savedAt > MESSAGE_CACHE_TTL) return []
    const list = Array.isArray(parsed?.accounts) ? parsed.accounts : []
    return list.filter(item => Number(item?.id || 0) > 0)
  } catch {
    return []
  }
}

function writeCachedAccounts(list) {
  try {
    messagesPageAccountsStore.write({
      savedAt: Date.now(),
      accounts: (Array.isArray(list) ? list : []).slice(0, 50),
    })
  } catch (e) {
    console.warn('[MSG] writeCachedAccounts failed:', e)
  }
}

function mutateMessagesPageCache(mutator) {
  const current = readMessagesPageCacheEnvelope()
  const nextEnvelope = typeof mutator === 'function'
    ? pruneMessagesPageCacheEnvelope(mutator(current) || current)
    : current
  writeMessagesPageCacheEnvelope(nextEnvelope)
  return nextEnvelope
}

function readCachedSelectedAccountId() {
  return String(readMessagesPageCacheEnvelope().selectedAccountId || '').trim()
}

function rememberSelectedAccount(accountId) {
  const normalizedAccountId = String(accountId || '').trim()
  if (!normalizedAccountId) return
  mutateMessagesPageCache(envelope => {
    envelope.selectedAccountId = normalizedAccountId
    return envelope
  })
}

function restoreCachedConversationContext(accountId, conversation, { scrollBottom = false } = {}) {
  const normalizedAccountId = String(accountId || '').trim()
  const conversationKey = conversationDedupeKey(conversation)
  if (!normalizedAccountId || !conversationKey) return false
  const envelope = readMessagesPageCacheEnvelope()
  const cachedMessages = envelope.accounts?.[normalizedAccountId]?.contexts?.[conversationKey]?.messages
  if (!Array.isArray(cachedMessages) || !cachedMessages.length) return false
  contextMessages.value = normalizeContextMessageList(cachedMessages)
  if (scrollBottom) {
    nextTick(() => scrollToBottom())
  }
  return true
}

function restoreAccountCache(accountId) {
  const normalizedAccountId = String(accountId || '').trim()
  if (!normalizedAccountId) return false
  const envelope = readMessagesPageCacheEnvelope()
  const entry = envelope.accounts?.[normalizedAccountId]
  if (!entry) return false

  const cachedConversations = mergeConversationSnapshots(entry.conversations || [])
  if (!cachedConversations.length) return false

  if (entry.userInfoCache && typeof entry.userInfoCache === 'object') {
    userInfoCacheRef.value = { ...userInfoCacheRef.value, ...entry.userInfoCache }
  }

  conversations.value = cachedConversations
  conversationCursor.value = entry.nextCursor ?? null
  conversationHasMore.value = Boolean(entry.hasMore)
  const cachedSelectedKey = String(entry.selectedConversationKey || '').trim()
  const cachedSelected = cachedSelectedKey
    ? cachedConversations.find(item => conversationDedupeKey(item) === cachedSelectedKey)
    : null
  selected.value = cachedSelected || findPreservedConversation(cachedConversations, selected.value) || cachedConversations[0] || null

  if (!selected.value || !restoreCachedConversationContext(normalizedAccountId, selected.value, { scrollBottom: false })) {
    contextMessages.value = []
  }
  return true
}

function persistCurrentAccountCache({
  accountId = selectedAccountId(),
  conversationList = conversations.value,
  selectedConversation = selected.value,
  contextList = contextMessages.value,
} = {}) {
  const normalizedAccountId = String(accountId || '').trim()
  if (!normalizedAccountId) return
  const nextConversations = mergeConversationSnapshots((Array.isArray(conversationList) ? conversationList : []).filter(Boolean))
    .slice(0, MESSAGE_CACHE_MAX_CONVERSATIONS)
  const conversationKeys = new Set(nextConversations.map(item => String(item?.sid || '').trim()).filter(Boolean))
  const selectedConversationKey = conversationDedupeKey(selectedConversation)

  mutateMessagesPageCache(envelope => {
    const previousEntry = envelope.accounts?.[normalizedAccountId] && typeof envelope.accounts[normalizedAccountId] === 'object'
      ? envelope.accounts[normalizedAccountId]
      : {}
    const previousContexts = previousEntry.contexts && typeof previousEntry.contexts === 'object'
      ? { ...previousEntry.contexts }
      : {}

    if (selectedConversationKey && Array.isArray(contextList) && contextList.length) {
      previousContexts[selectedConversationKey] = {
        savedAt: Date.now(),
        messages: normalizeContextMessageList(contextList).slice(-MESSAGE_CACHE_MAX_MESSAGES),
      }
    }

    const contexts = Object.fromEntries(
      Object.entries(previousContexts)
        .map(([key, value]) => [key, {
          savedAt: Number(value?.savedAt || Date.now()),
          messages: normalizeContextMessageList(value?.messages || []).slice(-MESSAGE_CACHE_MAX_MESSAGES),
        }])
        .filter(([, value]) => Array.isArray(value.messages) && value.messages.length)
        .sort((left, right) => Number(right[1].savedAt || 0) - Number(left[1].savedAt || 0))
        .slice(0, MESSAGE_CACHE_MAX_CONTEXTS)
    )

    const nextUserInfoCache = {}
    conversationKeys.forEach(sid => {
      if (userInfoCacheRef.value[sid]) {
        nextUserInfoCache[sid] = userInfoCacheRef.value[sid]
      }
    })

    envelope.selectedAccountId = normalizedAccountId
    envelope.accounts[normalizedAccountId] = {
      savedAt: Date.now(),
      selectedConversationKey,
      nextCursor: conversationCursor.value ?? null,
      hasMore: Boolean(conversationHasMore.value),
      conversations: nextConversations,
      userInfoCache: nextUserInfoCache,
      contexts,
    }
    return envelope
  })
}

function schedulePersistCurrentAccountCache(overrides = {}) {
  if (cachePersistTimer) {
    clearTimeout(cachePersistTimer)
  }
  cachePersistTimer = setTimeout(() => {
    cachePersistTimer = null
    persistCurrentAccountCache(overrides)
  }, 120)
}

function startMessagesPageCacheMaintenance() {
  stopMessagesPageCacheMaintenance()
  cachePruneTimer = setInterval(() => {
    writeMessagesPageCacheEnvelope(readMessagesPageCacheEnvelope())
  }, MESSAGE_CACHE_PRUNE_INTERVAL)
}

function stopMessagesPageCacheMaintenance() {
  if (cachePersistTimer) {
    clearTimeout(cachePersistTimer)
    cachePersistTimer = null
  }
  if (cachePruneTimer) {
    clearInterval(cachePruneTimer)
    cachePruneTimer = null
  }
}

function normalizeConversationStatus(conversation) {
  return conversation?.sessionStatus || compareConversationStatus(conversation?.statusCode, conversation?.statusText)
}

function conversationStatusText(conversation) {
  const status = normalizeConversationStatus(conversation)
  if (Number(conversation?.unreadCount || 0) > 0) return `${conversation.unreadCount} 条未读`
  if (status === 'completed') return '已完成'
  if (status === 'closed') return '已关闭'
  if (status === 'transferred') return '已转人工'
  return '进行中'
}

function conversationStatusClass(conversation) {
  const status = normalizeConversationStatus(conversation)
  if (Number(conversation?.unreadCount || 0) > 0) return 'highlight'
  if (status === 'completed') return 'success'
  if (status === 'closed' || status === 'transferred') return 'muted'
  return 'active'
}

function formatClock(value) {
  return formatDisplayDateTime(value, { withSeconds: true })
}

function formatConversationTime(value) {
  return formatDisplayDateTime(value, { withSeconds: true })
}

function formatMessageTime(value) {
  return formatDisplayDateTime(value, { withSeconds: true })
}

function conversationDedupeKey(conversation) {
  return getConversationIdentityKey(conversation)
}

function resolvePeerName(conversation) {
  return (
    conversation?.name ||
    conversation?.peerUserName ||
    conversation?.buyerName ||
    conversation?.peerName ||
    conversation?.peerNick ||
    (conversation?.peerUserId ? `买家${String(conversation.peerUserId).slice(-4)}` : '买家')
  )
}

function conversationAvatarUrl(conversation) {
  const direct = normalizeDisplayImage(
    conversation?.avatarUrl ||
    conversation?.buyerAvatar ||
    conversation?.peerUserAvatar ||
    conversation?.otherUserAvatar ||
    ''
  )
  if (direct) return direct
  const sid = String(conversation?.sid || '').trim()
  if (!sid) return ''
  const cached = userInfoCacheRef.value[sid]
  return normalizeDisplayImage(cached?.avatar || '')
}

function conversationGoodsCover(conversation) {
  return resolveConversationGoodsCover(conversation, '/xya/illustrations/about-feedback.svg') || '/xya/illustrations/about-feedback.svg'
}

function messageIdentity(message) {
  const pnmId = String(message?.pnmId || message?.messageUid || message?.uuid || '').trim()
  if (pnmId && !pnmId.startsWith('temp_')) return `pnm:${pnmId}`
  const id = String(message?.id || '').trim()
  if (id && !id.startsWith('temp_')) return `id:${id}`
  const sid = normalizeSid(message?.sid || message?.sId || message?.sessionId || '')
  const direction = String(message?.direction || message?.msgDirection || '').toUpperCase()
  const sender = normalizePeerUserId(message?.senderUserId || message?.fromUserId || '')
  const receiver = normalizePeerUserId(message?.receiverUserId || message?.toUserId || '')
  const content = String(message?.text || message?.content || message?.displayText || '').trim()
  const messageTime = parseMessageTimestamp(message?.messageTime || message?.createdAt || message?.sendTime || message?.timestamp || 0)
  return `fallback:${sid}:${direction}:${sender}:${receiver}:${messageTime}:${content}`
}

function messageContentIdentity(message) {
  const sid = normalizeSid(message?.sid || message?.sId || message?.sessionId || '')
  const direction = String(message?.direction || message?.msgDirection || '').toUpperCase()
  const sender = normalizePeerUserId(message?.senderUserId || message?.fromUserId || '')
  const receiver = normalizePeerUserId(message?.receiverUserId || message?.toUserId || '')
  const content = String(message?.text || message?.content || message?.displayText || '').trim()
  return `content:${sid}:${direction}:${sender}:${receiver}:${content}`
}

function isDuplicateMessage(existing, incoming) {
  if (messageIdentity(existing) === messageIdentity(incoming)) return true
  if (messageContentIdentity(existing) === messageContentIdentity(incoming)) return true

  // 乐观消息去重：乐观消息（sendStatus='sending'/'sent'）没有 sender/receiver，
  // SSE/DB 消息有这些字段，导致 messageContentIdentity 不匹配。
  // 当一方是乐观消息、另一方是真实消息时，仅用 sid + direction + content 匹配。
  const existingIsOptimistic = existing?.sendStatus === 'sending' || existing?.sendStatus === 'sent'
  const incomingIsOptimistic = incoming?.sendStatus === 'sending' || incoming?.sendStatus === 'sent'
  if (existingIsOptimistic !== incomingIsOptimistic) {
    const sid1 = normalizeSid(existing?.sid || existing?.sId || '')
    const sid2 = normalizeSid(incoming?.sid || incoming?.sId || '')
    const dir1 = String(existing?.direction || '').toUpperCase()
    const dir2 = String(incoming?.direction || '').toUpperCase()
    const content1 = String(existing?.text || existing?.content || '').trim()
    const content2 = String(incoming?.text || incoming?.content || '').trim()
    if (sid1 && sid1 === sid2 && dir1 === dir2 && content1 && content1 === content2) {
      return true
    }
  }

  return false
}

function isImageOnlyMessage(message) {
  const text = String(message?.text || message?.displayText || '').trim()
  return Array.isArray(message?.imageUrls)
    && message.imageUrls.length > 0
      && (!text || text === LEGACY_IMAGE_PLACEHOLDER || text === '[图片]')
}

function shouldRenderImageMessage(message) {
  return isImageOnlyMessage(message)
}

function normalizeMessage(item) {
  const imageUrls = extractImageMessageUrls(item).map(normalizeDisplayImage).filter(Boolean)
  const text = extractMessageDisplayText(item, imageUrls.length ? '[图片]' : '')
  const direction = String(item?.direction || item?.msgDirection || '').toUpperCase()
  const isMe = direction === 'OUT' || direction === 'SEND' || item?.fromSelf === true || item?.self === true || item?.isSelf === true
  return {
    ...item,
    sid: normalizeSid(item?.sid || item?.sId || item?.sessionId || item?.conversationId || ''),
    peerUserId: normalizePeerUserId(item?.peerUserId || item?.peerExternalUid || item?.externalBuyerId || item?.senderUserId || item?.receiverUserId || ''),
    xianyuAccountId: Number(item?.xianyuAccountId || item?.accountId || selectedAccountId() || 0) || undefined,
    accountId: Number(item?.accountId || item?.xianyuAccountId || selectedAccountId() || 0) || undefined,
    text,
    content: text,
    displayText: text,
    imageUrls,
    messageTime: parseMessageTimestamp(item?.messageTime || item?.createdAt || item?.sendTime || item?.timestamp || Date.now()) || Date.now(),
    isAutoReply: Boolean(item?.isAutoReply || item?.is_auto_reply || item?.lastIsAutoReply),
    isMe,
  }
}

function normalizeContextMessageList(list) {
  const result = []
  for (const item of sortMessagesByTime((Array.isArray(list) ? list : []).map(normalizeMessage))) {
    const isDup = result.some(existing => isDuplicateMessage(existing, item))
    if (!isDup) result.push(item)
  }
  return result
}

function normalizeConversationBatch(raw) {
  const list = Array.isArray(raw)
    ? raw
    : Array.isArray(raw?.conversations)
      ? raw.conversations
      : Array.isArray(raw?.records)
        ? raw.records
        : Array.isArray(raw?.list)
          ? raw.list
          : Array.isArray(raw?.items)
            ? raw.items
            : null
  if (!Array.isArray(list)) throw new Error('会话列表响应格式异常')
  if (!Array.isArray(raw) && typeof raw?.hasMore !== 'boolean') throw new Error('会话分页状态响应格式异常')
  if (!Array.isArray(raw) && raw.hasMore === true
    && (raw.nextCursor === null || raw.nextCursor === undefined || raw.nextCursor === '')) {
    throw new Error('会话分页游标响应格式异常')
  }
  return {
    list,
    nextCursor: Array.isArray(raw) ? null : (raw?.nextCursor ?? null),
    hasMore: Array.isArray(raw) ? false : raw.hasMore,
  }
}

async function fetchConversationPage(accountId, cursor = null) {
  const res = await onlineConversations(accountId, {
    cursor,
    pageSize: query.pageSize,
  })
  const raw = unwrap(res?.data)
  return normalizeConversationBatch(raw)
}

function conversationPageCacheKey(accountId, cursor) {
  return `${Number(accountId || 0)}:${cursor ?? 'root'}`
}

function rememberPrefetchedConversationPage(key, page) {
  if (!page) return
  prefetchedConversationPages.set(key, page)
  if (prefetchedConversationPages.size <= 40) return
  const oldestKey = prefetchedConversationPages.keys().next().value
  if (oldestKey) prefetchedConversationPages.delete(oldestKey)
}

function primeConversationPage(accountId, cursor) {
  if (!accountId || cursor === null || cursor === undefined || cursor === '') return
  const key = conversationPageCacheKey(accountId, cursor)
  if (prefetchedConversationPages.has(key) || prefetchedConversationPromises.has(key)) return
  const promise = fetchConversationPage(accountId, cursor)
    .then(page => {
      rememberPrefetchedConversationPage(key, page)
      return page
    })
    .catch(() => null)
    .finally(() => {
      prefetchedConversationPromises.delete(key)
    })
  prefetchedConversationPromises.set(key, promise)
}

async function resolveConversationPage(accountId, cursor = null) {
  const key = conversationPageCacheKey(accountId, cursor)
  if (prefetchedConversationPages.has(key)) {
    const page = prefetchedConversationPages.get(key)
    prefetchedConversationPages.delete(key)
    return page
  }
  const inflight = prefetchedConversationPromises.get(key)
  if (inflight) {
    const page = await inflight
    if (page) {
      prefetchedConversationPages.delete(key)
      return page
    }
  }
  return fetchConversationPage(accountId, cursor)
}

function toDisplayConversation(dto) {
  const sid = normalizeSid(dto?.sid || dto?.sId || dto?.sessionId || dto?.conversationId || dto?.cid || dto?.id || '')
  const peerUserId = normalizePeerUserId(dto?.peerUserId || dto?.peerExternalUid || dto?.externalBuyerId || dto?.senderUserId || dto?.receiverUserId || '')
  const accountId = Number(dto?.xianyuAccountId || dto?.accountId || selectedAccountId() || 0) || undefined
  const preview = extractMessageDisplayText(dto, dto?.lastMessage || dto?.lastContent || '')
  const time = parseMessageTimestamp(dto?.lastMessageTime || dto?.updatedAt || dto?.messageTime || dto?.createdAt || Date.now()) || Date.now()
  const normalized = {
    ...dto,
    raw: dto,
    id: dto?.id,
    rawId: dto?.id,
    xianyuAccountId: accountId,
    accountId,
    sid,
    sId: sid,
    sessionId: sid,
    peerUserId,
    name: dto?.name || dto?.peerUserName || dto?.buyerName || dto?.peerName || dto?.peerNick || '',
    msg: preview,
    lastMessage: preview,
    lastContent: preview,
    product: resolveConversationGoodsTitle(dto, ''),
    goodsTitle: resolveConversationGoodsTitle(dto, ''),
    goodsCoverPic: resolveConversationGoodsCover(dto, ''),
    xyGoodsId: resolveConversationGoodsId(dto, ''),
    lastMessageTime: time,
    updatedAt: time,
    unreadCount: Number(dto?.unreadCount || dto?.unread || 0) || 0,
    statusCode: dto?.statusCode ?? dto?.status ?? dto?.sessionStatusCode ?? 0,
    statusText: dto?.statusText || dto?.statusName || '',
    sessionStatus: compareConversationStatus(dto?.statusCode ?? dto?.status ?? 0, dto?.statusText || dto?.statusName || ''),
    lastIsAutoReply: Boolean(dto?.lastIsAutoReply || dto?.isAutoReply || dto?.is_auto_reply),
    botEnabled: Boolean(dto?.botEnabled || dto?.hasAiReply || dto?.lastIsAutoReply || dto?.isAutoReply || dto?.is_auto_reply),
    avatarUrl: normalizeDisplayImage(dto?.buyerAvatar || dto?.avatarUrl || dto?.peerUserAvatar || dto?.otherUserAvatar || ''),
  }
  return sid || peerUserId ? applyConversationUnreadState(normalized, normalized.unreadCount, compareConversationStatus) : null
}

function resolveReceiverId(conversation) {
  return normalizePeerUserId(conversation?.peerUserId || conversation?.peerExternalUid || conversation?.externalBuyerId || '')
    || normalizeSid(conversation?.sid || conversation?.sId || '')
}

function getUploadImageUrl(payload) {
  const data = unwrap(payload)
  return data?.imageUrl || data?.url || data?.data?.url || data?.data?.imageUrl || payload?.imageUrl || payload?.url || ''
}

function updateConversationPreview(targetConversation, updater) {
  const key = conversationDedupeKey(targetConversation)
  if (!key) return
  conversations.value = conversations.value.map(item => conversationDedupeKey(item) === key ? updater(item) : item)
  const nextSelected = conversations.value.find(item => conversationDedupeKey(item) === key)
  if (nextSelected && conversationDedupeKey(selected.value) === key) {
    selected.value = nextSelected
  }
  schedulePersistCurrentAccountCache()
}

function conversationPreviewSnapshot(conversation) {
  return {
    msg: conversation?.msg,
    lastMessage: conversation?.lastMessage,
    lastContent: conversation?.lastContent,
    lastMessageTime: conversation?.lastMessageTime,
    updatedAt: conversation?.updatedAt,
    unreadCount: conversation?.unreadCount,
  }
}

function messageSendAckOf(res, expectedSid, label = '消息发送') {
  const data = res?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error(`${label}响应格式异常`)
  const acknowledged = String(data.uuid || '').trim() || data.message === 'Sent' || data.success === true
  if (!acknowledged) throw new Error(`${label}响应未确认发送成功`)
  if (data.sid != null && String(data.sid) !== String(expectedSid)) throw new Error(`${label}响应会话不一致`)
  return data
}

function setConversationUnread(targetConversation, unreadCount) {
  const key = conversationDedupeKey(targetConversation)
  if (!key) return
  conversations.value = conversations.value.map(item =>
    conversationDedupeKey(item) === key ? applyConversationUnreadState(item, unreadCount, compareConversationStatus) : item
  )
  if (conversationDedupeKey(selected.value) === key && selected.value) {
    selected.value = applyConversationUnreadState(selected.value, unreadCount, compareConversationStatus)
  }
  schedulePersistCurrentAccountCache()
}

async function fetchMissingAvatars(accountId, convs) {
  if (!accountId || !Array.isArray(convs) || !convs.length) return
  const missing = convs.filter(conv => {
    const sid = String(conv?.sid || '').trim()
    if (!sid) return false
    if (conversationAvatarUrl(conv) && resolvePeerName(conv) !== '买家') return false
    const cached = userInfoCacheRef.value[sid]
    return !(cached?.avatar && cached?.nick)
  })
  if (!missing.length) return
  const queries = Array.from(new Set(missing.map(conv => String(conv.sid || '').trim())))
    .filter(Boolean)
    .map(cid => ({ cid }))

  const BATCH_SIZE = 10
  for (let index = 0; index < queries.length; index += BATCH_SIZE) {
    const batch = queries.slice(index, index + BATCH_SIZE)
    try {
      const res = await queryUserAvatars(accountId, batch)
      const items = res?.data?.items || res?.data?.data?.items || []
      const itemMap = new Map(items.map(item => [item.cid, item]))
      for (const item of items) {
        if (item?.cid) {
          userInfoCacheRef.value[item.cid] = { avatar: item.avatar || '', nick: item.nick || '' }
        }
      }
      conversations.value = conversations.value.map(conv => {
        const item = itemMap.get(String(conv?.sid || '').trim())
        if (!item) return conv
        return {
          ...conv,
          avatarUrl: normalizeDisplayImage(item.avatar || conv.avatarUrl),
          buyerAvatar: normalizeDisplayImage(item.avatar || conv.buyerAvatar),
          name: item.nick || conv.name,
        }
      })
      if (selected.value) {
        const sid = String(selected.value?.sid || '').trim()
        const item = itemMap.get(sid)
        if (item) {
          selected.value = {
            ...selected.value,
            avatarUrl: normalizeDisplayImage(item.avatar || selected.value.avatarUrl),
            buyerAvatar: normalizeDisplayImage(item.avatar || selected.value.buyerAvatar),
            name: item.nick || selected.value.name,
          }
        }
      }
      schedulePersistCurrentAccountCache({
        accountId,
        conversationList: conversations.value,
        selectedConversation: selected.value,
        contextList: contextMessages.value,
      })
    } catch (e) {
      console.warn('[MSG] fetchMissingAvatars failed:', e)
    }
  }
}

function scheduleAvatarHydration(accountId, convs, delayMs = 1200) {
  if (avatarHydrationTimer) {
    clearTimeout(avatarHydrationTimer)
    avatarHydrationTimer = null
  }
  avatarHydrationTimer = setTimeout(() => {
    avatarHydrationTimer = null
    fetchMissingAvatars(accountId, convs).catch(() => {})
  }, delayMs)
}

async function loadAccountsData(preferredId = null) {
  accountsAvailable.value = false
  accountsLoadError.value = ''
  accounts.value = []
  try {
    const res = await getLiteAccounts({ current: 1, size: 50 })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    accountsAvailable.value = true
    writeCachedAccounts(list)
    if (!accounts.value.length) {
      query.xianyuAccountId = ''
      return true
    }
    if (!query.xianyuAccountId || !accounts.value.some(item => String(item.id) === String(query.xianyuAccountId))) {
      const preferred = pickPreferredAccount(accounts.value, preferredId || query.xianyuAccountId)
      query.xianyuAccountId = preferred ? String(preferred.id) : String(accounts.value[0].id)
    }
    const selectedId = selectedAccountId()
    if (selectedId) rememberSelectedAccount(selectedId)
    return true
  } catch (e) {
    accountsLoadError.value = e?.message || '账号列表加载失败'
    throw e
  }
}

async function loadSelectedWsStatus(accountId) {
  if (!accountId) return
  try {
    const res = await websocketStatus(accountId)
    const data = unwrap(res?.data) || res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.connected !== 'boolean') {
      throw new Error('连接状态响应格式异常')
    }
    wsStateMap[accountId] = data
  } catch (e) {
    wsStateMap[accountId] = { connected: null, status: '状态未知', lastError: e?.message || '连接状态加载失败' }
  }
}

async function loadConversations(preserveSelected = true, { silent = false } = {}) {
  const requestId = ++conversationLoadRequestId
  const requestedAccountId = Number(query.xianyuAccountId || 0)
  if (!requestedAccountId && query.xianyuAccountId) {
    conversations.value = []
    selected.value = null
    contextMessages.value = []
    conversationsAvailable.value = false
    contextAvailable.value = false
    return
  }

  if (!silent) {
    loading.value = true
    error.value = ''
    conversationsAvailable.value = false
    contextAvailable.value = false
    conversations.value = []
    selected.value = null
    contextMessages.value = []
  }

  try {
    const accountIds = requestedAccountId
      ? [requestedAccountId]
      : accounts.value.map(item => Number(item?.id || 0)).filter(Boolean)
    const batches = await Promise.all(accountIds.map(async accountId => {
      const page = await fetchConversationPage(accountId, null)
      return {
        accountId,
        ...page,
      }
    }))

    if (!shouldApplyConversationLoadResult({
      requestId,
      latestRequestId: conversationLoadRequestId,
      requestedAccountId,
      currentAccountId: Number(query.xianyuAccountId || 0),
    })) {
      return
    }

    conversationsAvailable.value = true

    const previousConversationMap = new Map(conversations.value.map(item => [conversationDedupeKey(item), item]))
    const nextConversations = mergeConversationSnapshots(
      batches
        .flatMap(batch => batch.list.map(item => toDisplayConversation({ ...item, xianyuAccountId: batch.accountId })))
        .filter(Boolean)
    ).map(item => mergeConversationDisplaySnapshot(previousConversationMap.get(conversationDedupeKey(item)), item) || item)

    const preserveLoadedPages = Boolean(
      silent &&
      requestedAccountId &&
      batches.length === 1 &&
      conversations.value.length > nextConversations.length &&
      conversationCursor.value !== null &&
      conversationCursor.value !== ''
    )

    if (preserveLoadedPages) {
      const mergedConversationMap = new Map(nextConversations.map(item => [conversationDedupeKey(item), item]))
      conversations.value.forEach(item => {
        const key = conversationDedupeKey(item)
        if (!key || mergedConversationMap.has(key)) return
        mergedConversationMap.set(key, item)
      })
      conversations.value = mergeConversationSnapshots(Array.from(mergedConversationMap.values()))
    } else {
      conversations.value = nextConversations
      conversationCursor.value = batches.length === 1 ? (batches[0]?.nextCursor ?? null) : null
      conversationHasMore.value = batches.length === 1
        ? Boolean(batches[0]?.hasMore && batches[0]?.nextCursor !== null && batches[0]?.nextCursor !== undefined && batches[0]?.nextCursor !== '')
        : false
    }

    if (
      batches.length === 1 &&
      requestedAccountId &&
      conversationHasMore.value &&
      conversationCursor.value !== null &&
      conversationCursor.value !== ''
    ) {
      primeConversationPage(requestedAccountId, conversationCursor.value)
    }

    if (!conversations.value.length) {
      selected.value = null
      contextMessages.value = []
      draft.value = ''
      schedulePersistCurrentAccountCache({
        accountId: requestedAccountId,
        conversationList: [],
        selectedConversation: null,
        contextList: [],
      })
      return
    }

    const matched = preserveSelected ? findPreservedConversation(conversations.value, selected.value) : null
    if (matched) {
      selected.value = mergeSelectedConversationSnapshot(selected.value, matched, { preserveUnreadAsRead: true })
    } else if (!selected.value || !preserveSelected) {
      selected.value = conversations.value[0]
      const selectedConversationAccountId = Number(selected.value?.xianyuAccountId || requestedAccountId || 0)
      if (!restoreCachedConversationContext(selectedConversationAccountId, selected.value, { scrollBottom: false })) {
        contextMessages.value = []
      }
    }

    schedulePersistCurrentAccountCache({
      accountId: requestedAccountId,
      conversationList: conversations.value,
      selectedConversation: selected.value,
      contextList: contextMessages.value,
    })
    // 补全缺失的买家头像（初始加载和账号切换时触发）
    const avatarAccountId = requestedAccountId || Number(selected.value?.xianyuAccountId || 0)
    if (avatarAccountId) {
      scheduleAvatarHydration(avatarAccountId, conversations.value, silent ? 2000 : 800)
    }
    if (!silent && selected.value) await loadContext(true)
  } catch (e) {
    if (!shouldApplyConversationLoadResult({
      requestId,
      latestRequestId: conversationLoadRequestId,
      requestedAccountId,
      currentAccountId: Number(query.xianyuAccountId || 0),
    })) {
      return
    }
    error.value = e.message || '会话加载失败'
    if (!silent) {
      conversationsAvailable.value = false
      contextAvailable.value = false
      conversations.value = []
      selected.value = null
      contextMessages.value = []
    }
  } finally {
    if (!silent && requestId === conversationLoadRequestId) {
      loading.value = false
    }
  }
}

async function loadMoreConversations() {
  const accountId = selectedAccountId()
  if (!accountId || !conversationHasMore.value || loadingMoreConversations.value) return
  loadingMoreConversations.value = true
  try {
    let page
    try {
      page = await resolveConversationPage(accountId, conversationCursor.value)
    } catch {
      await ensureCurrentAccountWebSocketConnected({ reason: 'loadMoreConversations' })
      page = await resolveConversationPage(accountId, conversationCursor.value)
    }
    const previousConversationMap = new Map(conversations.value.map(item => [conversationDedupeKey(item), item]))
    const nextBatch = page.list
      .map(item => toDisplayConversation({ ...item, xianyuAccountId: accountId }))
      .filter(Boolean)
      .map(item => mergeConversationDisplaySnapshot(previousConversationMap.get(conversationDedupeKey(item)), item) || item)
    const merged = new Map(conversations.value.map(item => [conversationDedupeKey(item), item]))
    nextBatch.forEach(item => {
      const key = conversationDedupeKey(item)
      merged.set(key, mergeConversationDisplaySnapshot(merged.get(key), item) || item)
    })
    conversations.value = mergeConversationSnapshots(Array.from(merged.values()))
    conversationCursor.value = page.nextCursor
    conversationHasMore.value = Boolean(page.hasMore && page.nextCursor !== null && page.nextCursor !== undefined && page.nextCursor !== '')
    if (conversationHasMore.value && conversationCursor.value !== null && conversationCursor.value !== '') {
      primeConversationPage(accountId, conversationCursor.value)
    }
    scheduleAvatarHydration(accountId, conversations.value, 400)
    schedulePersistCurrentAccountCache({
      accountId,
      conversationList: conversations.value,
      selectedConversation: selected.value,
      contextList: contextMessages.value,
    })
  } catch (e) {
    error.value = e.message || '加载更多会话失败'
  } finally {
    loadingMoreConversations.value = false
  }
}

async function markSelectedConversationRead(conversation) {
  if (!conversation || !shouldMarkConversationAsRead(conversation)) return
  const id = getConversationRecordId(conversation)
  if (!id) {
    error.value = '当前会话缺少服务端记录编号，未将未读状态改为已读'
    return false
  }
  try {
    await markConversationRead(id)
    setConversationUnread(conversation, 0)
    return true
  } catch (readError) {
    error.value = readError?.message || '会话已打开，但已读状态同步失败'
    return false
  }
}

function normalizeMessageContextBatch(raw) {
  const list = Array.isArray(raw)
    ? raw
    : Array.isArray(raw?.records)
      ? raw.records
      : Array.isArray(raw?.list)
        ? raw.list
        : Array.isArray(raw?.messages)
          ? raw.messages
          : null
  if (!Array.isArray(list)) throw new Error('消息记录响应格式异常')
  return list
}

async function loadContext(scrollBottom = true, { silent = false } = {}) {
  const requestId = ++contextLoadRequestId
  const conversation = selected.value
  const accountId = Number(conversation?.xianyuAccountId || conversation?.accountId || selectedAccountId() || 0)
  if (!conversation || !accountId) {
    contextMessages.value = []
    contextAvailable.value = false
    return
  }

  if (!silent) {
    contextLoading.value = true
    contextAvailable.value = false
    contextMessages.value = []
  }
  try {
    const sid = normalizeSid(conversation.sid)
    const peerUserId = normalizePeerUserId(conversation.peerUserId || conversation.peerExternalUid || conversation.externalBuyerId || '')
    const basePayload = {
      xianyuAccountId: accountId,
      sid,
      sId: sid,
      sessionId: sid,
      peerUserId,
      limit: 100,
      offset: 0,
    }

    let res = await messageContext(basePayload)
    let raw = unwrap(res?.data)
    let list = normalizeMessageContextBatch(raw)

    if (!list.length && peerUserId) {
      res = await messageContext({ ...basePayload, sid: '', sId: '', sessionId: '' })
      raw = unwrap(res?.data)
      list = normalizeMessageContextBatch(raw)
    }

    if (!shouldApplyContextLoadResult({
      requestId,
      latestRequestId: contextLoadRequestId,
      requestedAccountId: accountId,
      currentAccountId: selectedAccountId(),
      requestedConversation: conversation,
      currentConversation: selected.value,
    })) {
      return
    }

    contextMessages.value = normalizeContextMessageList(list)
    contextAvailable.value = true
    schedulePersistCurrentAccountCache({
      accountId,
      conversationList: conversations.value,
      selectedConversation: selected.value,
      contextList: contextMessages.value,
    })
    if (scrollBottom) {
      await nextTick()
      scrollToBottom()
    }
  } catch (e) {
    if (!shouldApplyContextLoadResult({
      requestId,
      latestRequestId: contextLoadRequestId,
      requestedAccountId: accountId,
      currentAccountId: selectedAccountId(),
      requestedConversation: conversation,
      currentConversation: selected.value,
    })) {
      return
    }
    error.value = e.message || '消息记录加载失败'
    if (!silent) {
      contextAvailable.value = false
      contextMessages.value = []
    }
  } finally {
    if (!silent && requestId === contextLoadRequestId) {
      contextLoading.value = false
    }
  }
}

async function selectChat(conversation) {
  const nextConversation = findConversationByIdentity(conversations.value, conversation) || conversation
  selected.value = mergeSelectedConversationSnapshot(selected.value, nextConversation, { preserveUnreadAsRead: true })
  error.value = ''
  restoreCachedConversationContext(selectedAccountId(), selected.value, { scrollBottom: true })
  await loadContext(true)
  await markSelectedConversationRead(selected.value)
  refreshAiScopeState()
  schedulePersistCurrentAccountCache()
}

async function reload() {
  if (!accountsAvailable.value) {
    try {
      await loadAccountsData(readCachedSelectedAccountId() || null)
    } catch (e) {
      error.value = e?.message || '账号列表加载失败'
      return
    }
  }
  if (!accounts.value.length) {
    conversationsAvailable.value = true
    conversations.value = []
    return
  }
  await loadConversations(false)
}

function handleConversationListScroll(event) {
  const el = event?.target || conversationListRef.value
  if (!el || loadingMoreConversations.value || !conversationHasMore.value) return
  const remaining = el.scrollHeight - (el.scrollTop + el.clientHeight)
  if (remaining <= CONVERSATION_LIST_LOAD_MORE_THRESHOLD) {
    loadMoreConversations().catch(() => {})
  }
}

function scrollToBottom() {
  const el = messagesContainer.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

function isChatNearBottom(threshold = CHAT_BOTTOM_THRESHOLD) {
  const el = messagesContainer.value
  if (!el) return true
  return el.scrollHeight - (el.scrollTop + el.clientHeight) <= threshold
}

function triggerImagePick() {
  imageInput.value?.click()
}

async function handleImagePick(event) {
  const file = event?.target?.files?.[0]
  if (!file) return
  try {
    await sendImage(file)
  } finally {
    event.target.value = ''
  }
}

async function sendImage(file) {
  const validationMessage = imageUploadValidationMessage(file)
  if (validationMessage) {
    error.value = validationMessage
    return
  }
  if (!contextAvailable.value) {
    error.value = '消息记录不可用，已阻止发送图片；请重新打开会话并重试。'
    return
  }
  if (!selected.value) {
    error.value = '请先选择会话'
    return
  }
  const accountId = Number(selected.value?.xianyuAccountId || selectedAccountId() || 0)
  if (!accountId) {
    error.value = '请先选择账号'
    return
  }
  const receiverId = resolveReceiverId(selected.value)
  if (!receiverId) {
    error.value = '当前会话缺少接收方标识'
    return
  }

  sending.value = true
  sendingImage.value = true
  error.value = ''

  const tempId = `temp_image_${Date.now()}`
  const previewBeforeSend = conversationPreviewSnapshot(selected.value)
  const optimistic = normalizeMessage({
    id: tempId,
    pnmId: tempId,
    sid: selected.value.sid,
    sId: selected.value.sid,
    direction: 'OUT',
    contentType: 2,
    imageUrls: [],
    msgContent: '[图片]',
    displayText: '[图片]',
    messageTime: Date.now(),
    sendStatus: 'sending',
  })
  contextMessages.value = normalizeContextMessageList([...contextMessages.value, optimistic])
  updateConversationPreview(selected.value, item => ({
    ...item,
    msg: '[图片]',
    lastMessage: '[图片]',
    lastContent: '[图片]',
    lastMessageTime: Date.now(),
    updatedAt: Date.now(),
  }))
  await nextTick()
  scrollToBottom()

  try {
    const uploadRes = await uploadImage(accountId, file)
    const imageUrl = getUploadImageUrl(uploadRes)
    if (!imageUrl) {
      throw new Error('图片上传成功但未返回可发送地址')
    }

    contextMessages.value = contextMessages.value.map(item => {
      if (item.id !== tempId) return item
      return { ...item, imageUrls: [normalizeDisplayImage(imageUrl)], sendStatus: 'sending' }
    })

    const res = await sendImageMessage({
      xianyuAccountId: accountId,
      cid: selected.value.sid,
      sid: selected.value.sid,
      sId: selected.value.sid,
      sessionId: selected.value.sid,
      toId: receiverId,
      peerUserId: receiverId,
      imageUrl,
      xyGoodsId: selected.value.xyGoodsId || selected.value.goodsId || '',
    })
    const sendAck = messageSendAckOf(res, selected.value.sid, '图片发送')
    const realUuid = String(sendAck.uuid || '').trim()
    contextMessages.value = contextMessages.value.map(item => {
      if (item.id !== tempId) return item
      return { ...item, id: realUuid || item.id, pnmId: realUuid || item.pnmId, sendStatus: 'sent' }
    })
    events.value.unshift({ text: '已发送图片', time: formatClock(Date.now()) })
    events.value = events.value.slice(0, 20)
  } catch (e) {
    contextMessages.value = contextMessages.value.map(item => {
      if (item.id !== tempId) return item
      return { ...item, sendStatus: 'failed' }
    })
    updateConversationPreview(selected.value, item => ({ ...item, ...previewBeforeSend }))
    error.value = e.message || '图片发送失败'
  } finally {
    sending.value = false
    sendingImage.value = false
    schedulePersistCurrentAccountCache()
  }
}

async function sendCurrentMessage() {
  if (!canSend.value || !selected.value) return
  const accountId = Number(selected.value?.xianyuAccountId || selectedAccountId() || 0)
  const receiverId = resolveReceiverId(selected.value)
  const text = draft.value.trim()
  if (!accountId || !receiverId || !text) return

  const tempId = `temp_${Date.now()}`
  const previewBeforeSend = conversationPreviewSnapshot(selected.value)
  const optimistic = normalizeMessage({
    id: tempId,
    pnmId: tempId,
    sid: selected.value.sid,
    sId: selected.value.sid,
    direction: 'OUT',
    text,
    content: text,
    message: text,
    msgContent: text,
    messageTime: Date.now(),
    sendStatus: 'sending',
  })

  sending.value = true
  error.value = ''
  draft.value = ''
  contextMessages.value = normalizeContextMessageList([...contextMessages.value, optimistic])
  updateConversationPreview(selected.value, item => ({
    ...item,
    msg: text,
    lastMessage: text,
    lastContent: text,
    lastMessageTime: Date.now(),
    updatedAt: Date.now(),
    unreadCount: 0,
  }))
  await nextTick()
  scrollToBottom()

  try {
    const res = await sendMessage({
      xianyuAccountId: accountId,
      cid: selected.value.sid,
      sid: selected.value.sid,
      sId: selected.value.sid,
      sessionId: selected.value.sid,
      toId: receiverId,
      peerUserId: receiverId,
      text,
      content: text,
      message: text,
      xyGoodsId: selected.value.xyGoodsId || selected.value.goodsId || '',
      msgType: 'text',
    })
    const sendAck = messageSendAckOf(res, selected.value.sid)
    const realUuid = String(sendAck.uuid || '').trim()
    contextMessages.value = contextMessages.value.map(item => {
      if (item.id !== tempId) return item
      return { ...item, id: realUuid || item.id, pnmId: realUuid || item.pnmId, sendStatus: 'sent' }
    })
    events.value.unshift({ text: `已发送消息：${shortText(text, 24)}`, time: formatClock(Date.now()) })
    events.value = events.value.slice(0, 20)
  } catch (e) {
    contextMessages.value = contextMessages.value.map(item => {
      if (item.id !== tempId) return item
      return { ...item, sendStatus: 'failed' }
    })
    updateConversationPreview(selected.value, item => ({ ...item, ...previewBeforeSend }))
    draft.value = text
    error.value = e.message || '消息发送失败'
  } finally {
    sending.value = false
    schedulePersistCurrentAccountCache()
  }
}

async function persistConversationStatus(action, patch, successText) {
  if (!selected.value?.sid) return
  const id = getConversationRecordId(selected.value)
  if (!id || statusUpdating.value) return
  statusUpdating.value = true
  try {
    await updateConversationStatus(id, { action })
    updateConversationPreview(selected.value, item => ({
      ...item,
      ...patch,
      unreadCount: 0,
    }))
    events.value.unshift({ text: successText, time: formatClock(Date.now()) })
    events.value = events.value.slice(0, 20)
  } catch (e) {
    error.value = e.message || `${successText}失败`
  } finally {
    statusUpdating.value = false
  }
}

async function transferSession() {
  if (!selected.value) return
  const confirmed = await confirmAction({
    title: '确认转人工',
    description: '转人工后该会话会从自动接待流程切换为人工处理。',
  })
  if (!confirmed) return
  await persistConversationStatus('transferred', { sessionStatus: 'transferred', statusText: '已转人工' }, '会话已转人工')
}

async function endSession() {
  if (!selected.value) return
  const confirmed = await confirmAction({
    title: '确认结束会话',
    description: '结束后该会话会进入已完成状态。',
    dangerous: true,
  })
  if (!confirmed) return
  await persistConversationStatus('completed', { sessionStatus: 'completed', statusText: '已完成' }, '会话已结束')
}

async function loadQuickTemplates() {
  templatesLoadError.value = ''
  templatesAvailable.value = false
  try {
    const res = await listQuickReplyTemplates({ size: 100 })
    const list = res?.data?.records || (Array.isArray(res?.data) ? res.data : null)
    if (!Array.isArray(list)) throw new Error('快捷模板响应格式异常')
    allTemplates.value = list.map(item => ({
      id: item.id,
      title: item.title || '',
      content: item.content || '',
      text: item.content || '',
    }))
    quickTemplates.value = allTemplates.value.slice(0, 6)
    templatesAvailable.value = true
  } catch (e) {
    allTemplates.value = []
    quickTemplates.value = []
    templatesLoadError.value = e?.message || '请检查网络连接后重试。'
  }
}

function insertTemplate(item) {
  const text = item?.content || item?.text || ''
  if (!text) return
  draft.value = draft.value ? `${draft.value}\n${text}` : text
}

function editTemplate(item) {
  editingTemplate.id = item.id
  editingTemplate.title = item.title || ''
  editingTemplate.content = item.content || item.text || ''
}

function resetTemplateEdit() {
  editingTemplate.id = null
  editingTemplate.title = ''
  editingTemplate.content = ''
}

async function saveTemplate() {
  if (!templatesAvailable.value) return
  const title = editingTemplate.title.trim()
  const content = editingTemplate.content.trim()
  if (!title || !content) return
  try {
    await saveQuickReplyTemplate({
      id: editingTemplate.id || null,
      title,
      content,
    })
    resetTemplateEdit()
    await loadQuickTemplates()
  } catch (e) {
    error.value = e.message || '模板保存失败'
  }
}

async function deleteTemplate(id) {
  if (!templatesAvailable.value) return
  const confirmed = await confirmAction({
    title: '确认删除模板',
    description: '删除后无法恢复，请确认不再需要该回复模板。',
    dangerous: true,
  })
  if (!confirmed) return
  try {
    await deleteQuickReplyTemplate(id)
    await loadQuickTemplates()
  } catch (e) {
    error.value = e.message || '模板删除失败'
  }
}

async function loadAiCsSetting() {
  const requestGeneration = aiSettingsGate.begin()
  const accountId = selectedAccountId()
  aiSettingsAvailable.value = false
  aiSettingsError.value = ''
  aiGlobalEnabled.value = null
  aiAutoReplyEnabled.value = null
  aiAccountScopes.value = {}
  aiScopeProducts.value = []
  try {
    const [settingRes, scopeRes, productsRes] = await Promise.all([
      getBusinessSettings('ai-customer-service').catch(() => getAiCsSetting()),
      getAutoReplyScopeStatus(accountId || undefined),
      accountId ? getAutoReplyScopeProducts(accountId) : Promise.resolve({ data: { items: [] } }),
    ])
    if (
      !aiSettingsGate.isCurrent(requestGeneration)
      || Number(accountId || 0) !== Number(selectedAccountId() || 0)
    ) return
    const config = settingRes?.data
    const scopeData = scopeRes?.data
    const productData = productsRes?.data
    if (!config || typeof config !== 'object' || Array.isArray(config) || typeof config.enabled !== 'boolean') throw new Error('AI 客服配置响应格式异常')
    if (!scopeData || typeof scopeData !== 'object' || Array.isArray(scopeData)) throw new Error('自动回复作用域响应格式异常')
    const scopeGlobalEnabled = scopeData.global_enabled ?? scopeData.globalEnabled
    if (typeof scopeGlobalEnabled !== 'boolean') throw new Error('自动回复作用域缺少主开关状态')
    const accountScopes = scopeData.account_scopes ?? scopeData.accountScopes ?? {}
    if (!accountScopes || typeof accountScopes !== 'object' || Array.isArray(accountScopes)
      || Object.values(accountScopes).some(value => typeof value !== 'boolean')) {
      throw new Error('账号自动回复作用域响应格式异常')
    }
    const products = Array.isArray(productData) ? productData : productData?.items || productData?.records || productData?.list
    if (!Array.isArray(products)) throw new Error('商品自动回复作用域响应格式异常')
    aiGlobalEnabled.value = config.enabled && scopeGlobalEnabled
    aiAccountScopes.value = accountScopes
    aiScopeProducts.value = products
    aiSettingsAvailable.value = true
    refreshAiScopeState()
    return true
  } catch (e) {
    if (!aiSettingsGate.isCurrent(requestGeneration)) return
    aiSettingsError.value = e?.message || '自动回复状态加载失败'
    aiAutoReplyEnabled.value = null
    return false
  }
}

function refreshAiScopeState() {
  if (!aiSettingsAvailable.value || typeof aiGlobalEnabled.value !== 'boolean') {
    aiAutoReplyEnabled.value = null
    return
  }
  const goodsId = String(selected.value?.xyGoodsId || '')
  if (goodsId) {
    const product = aiScopeProducts.value.find(item => String(item.goodsId || '') === goodsId)
    if (typeof product?.effective_enabled === 'boolean') {
      aiAutoReplyEnabled.value = product.effective_enabled
      return
    }
    const accountId = String(selectedAccountId() || '')
    aiAutoReplyEnabled.value = accountId
      ? resolveAccountAutoReplyScopeEnabled(aiGlobalEnabled.value, aiAccountScopes.value, accountId)
      : aiGlobalEnabled.value
    return
  }
  const accountId = String(selectedAccountId() || '')
  if (accountId) {
    aiAutoReplyEnabled.value = resolveAccountAutoReplyScopeEnabled(aiGlobalEnabled.value, aiAccountScopes.value, accountId)
    return
  }
  aiAutoReplyEnabled.value = aiGlobalEnabled.value
}

async function loadTokenBalanceValue() {
  tokenBalance.value = null
  tokenBalanceError.value = ''
  try {
    const res = await getTokenBalance()
    const data = res?.data?.data || res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Token 余额响应格式异常')
    const rawBalance = data.balance ?? data.tokenBalance
    const balance = Number(rawBalance)
    if (rawBalance === null || rawBalance === undefined || !Number.isFinite(balance)) throw new Error('Token 余额响应缺少有效余额')
    tokenBalance.value = balance
    return true
  } catch (e) {
    tokenBalance.value = null
    tokenBalanceError.value = e?.message || 'Token 余额加载失败'
    return false
  }
}

async function refreshCurrentAccountLoginState(accountId) {
  if (!accountId) return null
  const res = await checkLogin(accountId)
  const data = res?.data
  const status = data?.status
  if (!data || typeof data !== 'object' || Array.isArray(data)
    || !status || typeof status !== 'object' || Array.isArray(status)
    || typeof status.usable !== 'boolean') {
    throw new Error('账号登录状态响应格式异常')
  }
  const index = accounts.value.findIndex(item => Number(item.id) === Number(accountId))
  if (index >= 0) {
    accounts.value[index] = {
      ...accounts.value[index],
      cookieStatus: status.cookieStatus,
      authUsable: status.usable,
      loginStatusCode: status.loginStatusCode,
      loginStatusMessage: status.loginStatusMessage,
      loginCheckTime: status.checkedAt,
    }
  }
  return status
}

async function handleRefreshCurrentAccountLoginState() {
  const accountId = selectedAccountId()
  if (!accountId) return
  try {
    await refreshCurrentAccountLoginState(accountId)
    await loadSelectedWsStatus(accountId)
    await loadAccountsData(accountId)
  } catch (e) {
    error.value = e.message || '刷新登录状态失败'
  }
}

async function saveAiCsEnabled(enabled) {
  const current = await getBusinessSettings('ai-customer-service').then(response => response?.data)
  if (!current || typeof current !== 'object' || Array.isArray(current)) throw new Error('AI 客服配置不可用，已阻止覆盖保存')
  await saveBusinessSettings('ai-customer-service', { ...current, enabled })
  aiGlobalEnabled.value = Boolean(enabled)
  refreshAiScopeState()
}

async function ensureGlobalEnabledBeforeScopeEnable() {
  if (aiGlobalEnabled.value) return true
  const confirmed = await confirmAction({
    title: '当前全局 AI 自动回复未开启',
    description: '开启当前账号或商品自动回复前，需要先打开全局 AI 自动回复开关。',
    confirmText: '开启全局 AI',
  })
  if (!confirmed) return null
  await saveAiCsEnabled(true)
  return true
}

async function toggleAiAutoReply() {
  if (aiSwitchLoading.value) return
  if (!aiSettingsAvailable.value || aiAutoReplyEnabled.value === null) {
    error.value = '自动回复状态不可用，已阻止修改；请刷新页面后重试。'
    return
  }
  const accountId = Number(selectedAccountId() || 0)
  if (!accountId) {
    error.value = '请先选择账号'
    return
  }
  aiSwitchLoading.value = true
  try {
    const newValue = !aiAutoReplyEnabled.value
    const goodsId = String(selected.value?.xyGoodsId || '')
    if (goodsId) {
      if (newValue) {
        const ensured = await ensureGlobalEnabledBeforeScopeEnable()
        if (ensured == null) return
      }
      const product = aiScopeProducts.value.find(item => String(item.goodsId || '') === goodsId)
      await updateProductAutoReplyScope({
        itemId: product?.id || null,
        goodsId,
        accountId: Number(query.xianyuAccountId),
        title: selected.value?.product || selected.value?.goodsTitle || '',
        imageUrl: normalizeDisplayImage(selected.value?.goodsCoverPic || selected.value?.raw?.goodsCoverPic || ''),
        enabled: newValue,
      })
    } else {
      if (newValue) {
        const ensured = await ensureGlobalEnabledBeforeScopeEnable()
        if (ensured == null) return
      }
      await updateAccountAutoReplyScope(accountId, newValue)
    }
    await loadAiCsSetting()
    await loadTokenBalanceValue()
  } catch (e) {
    error.value = e.message || '自动回复开关更新失败'
  } finally {
    aiSwitchLoading.value = false
  }
}

// === 客户订单板块 ===
function customerOrderStatusMeta(status) {
  return CUSTOMER_ORDER_STATUS_META[Number(status)] || { text: String(status ?? '-'), className: 'muted' }
}

function customerOrderStatusText(status) {
  return customerOrderStatusMeta(status).text
}

function customerOrderStatusClass(status) {
  return customerOrderStatusMeta(status).className
}

function formatOrderAmount(amount) {
  const value = Number(amount)
  if (!Number.isFinite(value) || value <= 0) return '--'
  return `¥${value.toFixed(2)}`
}

function formatOrderTime(time) {
  return formatDisplayDateTime(time)
}

function resolveOrderCover(order) {
  const items = Array.isArray(order?.items) ? order.items : []
  for (const item of items) {
    const image = item?.goodsImage
    if (image && typeof image === 'string' && image.trim()) {
      return normalizeDisplayImage(image)
    }
  }
  return ''
}

function resolveOrderFirstItem(order) {
  const items = Array.isArray(order?.items) ? order.items : []
  return items.length ? items[0] : null
}

function orderItemTitle(item) {
  const title = item?.goodsTitle
  if (title && String(title).trim()) return title
  const externalId = item?.externalGoodsId
  return externalId ? `商品 ${externalId}` : '未命名商品'
}

function onOrderCoverError(event) {
  const target = event?.target
  if (!target) return
  target.style.display = 'none'
  const placeholder = target.parentElement?.querySelector('.xya-msg-order-cover-placeholder')
  if (placeholder) placeholder.style.display = 'inline-flex'
}

function resolveCustomerBuyerId(conversation) {
  return normalizePeerUserId(conversation?.peerUserId || conversation?.peerExternalUid || conversation?.externalBuyerId || '')
}

async function loadCustomerOrders(silent = false) {
  const conversation = selected.value
  const buyerId = resolveCustomerBuyerId(conversation)
  const accountId = Number(conversation?.xianyuAccountId || conversation?.accountId || selectedAccountId() || 0) || undefined
  if (!buyerId || !accountId) {
    customerOrders.value = []
    customerOrdersError.value = ''
    return
  }
  if (!silent) {
    loadingCustomerOrders.value = true
    customerOrdersError.value = ''
  }
  const gate = customerOrdersGate.begin()
  try {
    const res = await getCustomerOrders(accountId, buyerId, 10)
    if (!customerOrdersGate.isCurrent(gate)) return
    const data = unwrap(res)
    const records = Array.isArray(data?.records) ? data.records : (Array.isArray(data?.list) ? data.list : (Array.isArray(data) ? data : []))
    customerOrders.value = records
    customerOrdersError.value = ''
  } catch (e) {
    if (!customerOrdersGate.isCurrent(gate)) return
    customerOrders.value = []
    customerOrdersError.value = e?.message || '获取客户订单失败'
  } finally {
    if (customerOrdersGate.isCurrent(gate)) {
      loadingCustomerOrders.value = false
    }
  }
}

async function refreshCustomerOrders() {
  await loadCustomerOrders(false)
}

async function viewOrderDetail(orderId) {
  if (!orderId) return
  loadingOrderDetail.value = true
  orderDetailError.value = ''
  orderDetailData.value = null
  showOrderDetailModal.value = true
  try {
    const res = await getOrderDetail(orderId)
    const data = unwrap(res)
    orderDetailData.value = data
  } catch (e) {
    orderDetailError.value = e?.message || '加载订单详情失败'
  } finally {
    loadingOrderDetail.value = false
  }
}

function closeOrderDetailModal() {
  showOrderDetailModal.value = false
}

async function ensureCurrentAccountWebSocketConnected({ reason = 'ensure', allowUnverified = false, showError = false } = {}) {
  const accountId = selectedAccountId()
  if (!accountId) return false
  let account = currentAccount()
  let allowReconnect = allowUnverified

  if (allowReconnect) {
    try {
      const status = await refreshCurrentAccountLoginState(accountId)
      account = currentAccount()
      if (status?.usable) {
        allowReconnect = false
      }
    } catch (e) {
      console.warn(`[MSG] ${reason}: refresh login state failed`, e)
    }
  }

  if (!allowReconnect && !accountAuthUsable(account)) {
    if (showError) {
      error.value = accountLoginHint(account, currentWsState())
    }
    return false
  }

  try {
    const statusRes = await websocketStatus(accountId)
    const wsState = unwrap(statusRes?.data) || statusRes?.data
    if (!wsState || typeof wsState !== 'object' || Array.isArray(wsState) || typeof wsState.connected !== 'boolean') {
      throw new Error('消息连接状态响应格式异常')
    }
    wsStateMap[accountId] = wsState
    if (!allowReconnect && !shouldAttemptAccountWebSocketStart(account, wsState)) {
      return Boolean(wsState?.connected)
    }
    if (wsState?.connected) return true
    const startRes = await startWebSocket(accountId, allowReconnect ? { forceReconnect: true } : {})
    const startState = unwrap(startRes?.data) || startRes?.data
    if (!startState || typeof startState !== 'object' || Array.isArray(startState) || typeof startState.connected !== 'boolean') {
      throw new Error('消息连接启动响应格式异常')
    }
    wsStateMap[accountId] = startState
    if (startState.connected !== true) {
      if (showError) error.value = startState.message || '连接请求已返回，但服务端尚未确认连接'
      return false
    }
    setTimeout(() => {
      loadSelectedWsStatus(accountId).catch(() => {})
    }, 1500)
    return startState.connected === true
  } catch (e) {
    if (showError) {
      error.value = e.message || '消息连接启动失败'
    }
    console.warn(`[MSG] ${reason}: websocket start failed`, e)
    return false
  }
}

async function startCurrentConnection() {
  const accountId = selectedAccountId()
  if (!accountId) {
    error.value = '请先选择账号'
    return
  }
  connectingWs.value = true
  try {
    error.value = ''
    const started = await ensureCurrentAccountWebSocketConnected({
      reason: 'manual-connect',
      allowUnverified: true,
      showError: true,
    })
    if (!started) return
    await loadSelectedWsStatus(accountId)
    events.value.unshift({ text: '已触发消息连接恢复', time: formatClock(Date.now()) })
    events.value = events.value.slice(0, 20)
    await loadConversations(true, { silent: true })
  } finally {
    connectingWs.value = false
  }
}

function viewGoofishItem(itemId) {
  if (!itemId) return
  window.open(`https://www.goofish.com/item?itemId=${itemId}`, '_blank')
}

function sendGoodsLink(itemId) {
  if (!itemId) return
  const link = `https://www.goofish.com/item?itemId=${itemId}`
  draft.value = draft.value ? `${draft.value}\n${link}` : link
}

function openImagePreview(url) {
  previewImageUrl.value = normalizeDisplayImage(url)
}

function closeImagePreview() {
  previewImageUrl.value = ''
}

function upsertConversationFromEvent(payload, { currentChat = false } = {}) {
  const sid = normalizeSid(payload?.sId || payload?.sid || payload?.cid || payload?.sessionId || '')
  const peerUserId = normalizePeerUserId(payload?.peerUserId || payload?.peerExternalUid || payload?.senderUserId || payload?.receiverUserId || '')
  const accountId = Number(payload?.xianyuAccountId || payload?.accountId || selectedAccountId() || 0) || undefined
  if (!sid && !peerUserId) return

  const nextConversation = toDisplayConversation({
    ...payload,
    sid,
    sId: sid,
    sessionId: sid,
    peerUserId,
    xianyuAccountId: accountId,
    accountId,
    lastMessageTime: payload?.messageTime || payload?.createdTime || payload?.sendTime || Date.now(),
  })
  if (!nextConversation) return

  const existingIndex = findConversationMatchIndex(conversations.value, {
    sid,
    sId: sid,
    sessionId: sid,
    peerUserId,
    xianyuAccountId: accountId,
    accountId,
  })

  const incomingUnread = !currentChat && String(payload?.direction || payload?.msgDirection || '').toUpperCase() === 'IN'
  if (existingIndex >= 0) {
    const existing = conversations.value[existingIndex]
    const merged = applyConversationUnreadState(
      mergeConversationDisplaySnapshot(existing, nextConversation),
      currentChat ? 0 : Number(existing.unreadCount || 0) + (incomingUnread ? 1 : 0),
      compareConversationStatus
    )
    conversations.value = [merged, ...conversations.value.filter((_, index) => index !== existingIndex)]
  } else {
    const next = applyConversationUnreadState(nextConversation, incomingUnread ? 1 : 0, compareConversationStatus)
    conversations.value = [next, ...conversations.value]
  }

  if (selected.value && isSameConversationByPayload(selected.value, payload)) {
    const matched = findPreservedConversation(conversations.value, selected.value)
    if (matched) {
      selected.value = mergeSelectedConversationSnapshot(selected.value, matched, { preserveUnreadAsRead: currentChat })
    }
  }

  if (accountId && !conversationAvatarUrl(findPreservedConversation(conversations.value, nextConversation) || nextConversation)) {
    fetchMissingAvatars(accountId, conversations.value.slice(0, 20)).catch(() => {})
  }
  schedulePersistCurrentAccountCache({
    accountId,
    conversationList: conversations.value,
    selectedConversation: selected.value,
    contextList: contextMessages.value,
  })
}

function onSse(event) {
  const detail = event?.detail
  const data = detail?.payload || detail || {}
  const eventType = detail?.type || data.type || data.event || 'message'
  if (!accountSelectionReady.value) {
    return
  }
  const isRelevant = isRealtimeConversationEvent(eventType, data)
  if (!isRelevant) {
    lastSseActivity.value = 0
    return
  }
  if (!matchesAccountSelection(String(query.xianyuAccountId || ''), data)) {
    lastSseActivity.value = 0
    return
  }

  lastSseActivity.value = Date.now()
  const currentChat = Boolean(selected.value && isSameConversationByPayload(selected.value, data))
  const incoming = normalizeMessage(data)
  const shouldStickToBottom = currentChat && isChatNearBottom()

  if (currentChat) {
    const exists = contextMessages.value.some(item => isDuplicateMessage(item, incoming))
    if (!exists) {
      contextMessages.value = normalizeContextMessageList([...contextMessages.value, incoming])
      schedulePersistCurrentAccountCache()
      if (shouldStickToBottom) {
        nextTick(() => scrollToBottom())
      }
    }
    setConversationUnread(selected.value, 0)
  }

  upsertConversationFromEvent(data, { currentChat })
  events.value.unshift({
    text: shortText(data?.message || data?.content || data?.msgContent || '收到实时消息', 26),
    time: formatClock(Date.now()),
  })
  events.value = events.value.slice(0, 20)
}

function getPollingInterval() {
  if (lastSseActivity.value === 0) {
    sseHealthy.value = false
    return POLL_INTERVAL_FALLBACK
  }
  const stale = isRealtimeConversationSignalStale(lastSseActivity.value, Date.now(), SSE_STALE_TIMEOUT)
  if (stale) {
    sseHealthy.value = false
    return POLL_INTERVAL_FALLBACK
  }
  sseHealthy.value = true
  return POLL_INTERVAL_SSE_HEALTHY
}

async function pollMessages() {
  const accountId = selectedAccountId()
  if (!accountId) return
  try {
    const now = Date.now()
    if (now - lastWsHealthCheck > 30000) {
      lastWsHealthCheck = now
      await ensureCurrentAccountWebSocketConnected({ reason: 'pollMessages' })
    }
    if (!sseHealthy.value) {
      await loadConversations(true, { silent: true })
      if (selected.value?.sid || selected.value?.peerUserId) {
        await loadContext(false, { silent: true })
      }
    }
  } catch (e) {
    console.warn('[MSG] pollMessages failed:', e)
  }
}

function startPolling() {
  stopPolling()
  if (!shouldRunMessagePolling({ accountId: selectedAccountId(), documentHidden: document.hidden })) return
  pollingTimer = setTimeout(async function tick() {
    try {
      await pollMessages()
    } catch (e) {
      console.warn('[MSG] pollMessages error:', e)
    }
    pollingTimer = setTimeout(tick, getPollingInterval())
  }, getPollingInterval())
}

function stopPolling() {
  if (pollingTimer) {
    clearTimeout(pollingTimer)
    pollingTimer = null
  }
}

watch(() => query.xianyuAccountId, async () => {
  const requestId = ++accountSwitchRequestId
  if (avatarHydrationTimer) {
    clearTimeout(avatarHydrationTimer)
    avatarHydrationTimer = null
  }
  const previousSelectedConversation = selected.value
  const switchState = resolveAccountSwitchState({
    selectedAccountId: query.xianyuAccountId,
    previousSelectedConversation,
    deletedConversations: deletedConversations.value,
    contextMessages: contextMessages.value,
    error: error.value,
  })
  accountSelectionReady.value = false
  cacheHydrated.value = false
  conversationCursor.value = null
  conversationHasMore.value = false
  deletedConversations.value = switchState.deletedConversations
  draft.value = ''
  lastSseActivity.value = 0
  sseHealthy.value = false
  error.value = switchState.error
  if (switchState.selected !== previousSelectedConversation) {
    conversations.value = []
  }
  selected.value = switchState.selected
  contextMessages.value = switchState.contextMessages

  const accountId = selectedAccountId()
  if (accountId) {
    rememberSelectedAccount(accountId)
    cacheHydrated.value = restoreAccountCache(accountId)
  } else {
    conversations.value = []
    contextMessages.value = []
  }
  const restoredFromCache = cacheHydrated.value
  const postLoadRefresh = Promise.allSettled([
    loadAiCsSetting(),
    loadTokenBalanceValue(),
  ])

  switchingAccount.value = true
  try {
    await loadConversations(false)
    if (requestId !== accountSwitchRequestId || Number(accountId || 0) !== Number(selectedAccountId() || 0)) {
      return
    }
    accountSelectionReady.value = true
  } finally {
    if (requestId === accountSwitchRequestId) {
      switchingAccount.value = false
    }
  }

  postLoadRefresh.then(() => {
    if (requestId !== accountSwitchRequestId || Number(accountId || 0) !== Number(selectedAccountId() || 0)) {
      return
    }
    if (!restoredFromCache) {
      return
    }
    loadConversations(true, { silent: true })
      .then(() => {
        if (requestId !== accountSwitchRequestId || Number(accountId || 0) !== Number(selectedAccountId() || 0)) {
          return
        }
      })
      .catch(() => {})
  })
})

watch(() => selected.value?.xyGoodsId, () => {
  refreshAiScopeState()
})

// 选中会话变化时加载客户订单
watch(() => {
  const conv = selected.value
  return conv ? `${conv.sid || ''}|${resolveCustomerBuyerId(conv)}` : ''
}, () => {
  if (!selected.value) {
    customerOrders.value = []
    customerOrdersError.value = ''
    return
  }
  loadCustomerOrders(false).catch(() => {})
})

watch(() => showTemplateModal.value, visible => {
  if (!visible || allTemplates.value.length) return
  loadQuickTemplates().catch(() => {})
})

// === 滑块求解状态变化：自动刷新消息 + 自动重试 ===
watch(captchaSolveStatus, async (newStatus, oldStatus) => {
  if (!newStatus) return
  const aid = selectedAccountId()
  if (!aid) return

  // 状态变为 success → 刷新会话列表
  if (newStatus.status === 'success' && oldStatus?.status !== 'success') {
    try {
      await loadConversations(true, { silent: false })
      captchaRetryCount.value = 0  // 成功后重置重试计数
    } catch {
      // 刷新失败 → 触发重试求解
      if (captchaRetryCount.value < CAPTCHA_MAX_RETRY) {
        captchaRetryCount.value++
        setTimeout(() => solveManually(aid, 'ws_connect', {
          openReason: '消息页求解成功后刷新会话失败自动重试',
          solveReason: `求解成功但刷新会话失败，自动重试求解（第 ${captchaRetryCount.value} 次）`,
        }).catch(() => {}), 1500)
      }
    }
  }

  // 状态变为 fail → 自动重试求解（最多3次）
  if (newStatus.status === 'fail' && oldStatus?.status !== 'fail') {
    if (captchaRetryCount.value < CAPTCHA_MAX_RETRY) {
      captchaRetryCount.value++
      setTimeout(() => solveManually(aid, 'ws_connect', {
        openReason: '消息页滑块求解失败自动重试',
        solveReason: `上次求解失败，消息页自动重试求解（第 ${captchaRetryCount.value} 次）`,
      }).catch(() => {}), 2000)
    }
  }
})

// 切换账号时重置重试计数
watch(() => query.xianyuAccountId, () => {
  captchaRetryCount.value = 0
})

async function handleManualCaptchaSolve() {
  const aid = selectedAccountId()
  if (!aid) return
  captchaRetryCount.value = 0
  // 根据当前求解状态判断场景：已有失败状态时为"重试求解"，否则为"手动触发"
  const state = getAccountSolveStatus(aid)
  const scene = state && state.status === 'fail' ? 'manual_retry' : 'manual'
  await solveManually(aid, scene, {
    openReason: '用户在消息页点击滑块求解按钮',
    solveReason: scene === 'manual_retry'
      ? '用户在消息页点击重试求解（上次求解失败）'
      : '用户在消息页主动触发滑块求解',
  })
}

onMounted(async () => {
  window.addEventListener('xya-sse-event', onSse)
  startMessagesPageCacheMaintenance()

  visibilityChangeHandler = () => {
    if (document.hidden) {
      stopPolling()
    } else {
      startPolling()
    }
  }
  document.addEventListener('visibilitychange', visibilityChangeHandler)

  try {
    const cachedAccountId = readCachedSelectedAccountId()
    const cachedAccounts = readCachedAccounts()
    if (cachedAccounts.length) {
      accounts.value = cachedAccounts
    }
    if (cachedAccountId) {
      cacheHydrated.value = restoreAccountCache(cachedAccountId)
    }
    await loadAccountsData(cachedAccountId || null)
    if (!accounts.value.length) {
      conversations.value = []
      selected.value = null
      contextMessages.value = []
      accountSelectionReady.value = true
      return
    }
    if (!selectedAccountId()) {
      await Promise.allSettled([
        loadAiCsSetting(),
        loadTokenBalanceValue(),
      ])
      await loadConversations(false)
      accountSelectionReady.value = true
    }
    startPolling()
  } catch (e) {
    error.value = e.message || '在线消息页面初始化失败'
  }
})

onBeforeUnmount(() => {
  aiSettingsGate.dispose()
  stopPolling()
  stopMessagesPageCacheMaintenance()
  window.removeEventListener('xya-sse-event', onSse)
  if (visibilityChangeHandler) {
    document.removeEventListener('visibilitychange', visibilityChangeHandler)
    visibilityChangeHandler = null
  }
  if (avatarHydrationTimer) {
    clearTimeout(avatarHydrationTimer)
    avatarHydrationTimer = null
  }
})
</script>

<style scoped>
.xya-msg-page {
  --xya-msg-topbar-safe-space: 52px;
  width: 100%;
  height: calc(100dvh - 48px);
  min-height: 0;
  padding-top: var(--xya-msg-topbar-safe-space);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.xya-msg-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 334px minmax(0, 1fr) 380px;
  gap: 16px;
  min-height: 0;
  height: 100%;
}

.xya-msg-sidebar,
.xya-msg-chat-panel,
.xya-msg-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e7eef9;
  box-shadow: 0 14px 40px rgba(23, 61, 135, 0.08);
}

.xya-msg-sidebar,
.xya-msg-chat-panel,
.xya-msg-detail-panel {
  min-height: 0;
}

.xya-msg-sidebar,
.xya-msg-chat-panel {
  border-radius: 24px;
  height: 100%;
}

.xya-msg-sidebar {
  padding: 18px 0 14px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.xya-msg-sidebar-head,
.xya-msg-sidebar-toolbar,
.xya-msg-filter-row,
.xya-msg-footer-note,
.xya-msg-alert {
  padding-left: 16px;
  padding-right: 16px;
}

.xya-msg-sidebar-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.xya-msg-sidebar-head h2,
.xya-msg-card h3,
.xya-msg-chat-title h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #102147;
}

.xya-msg-sidebar-head p,
.xya-msg-chat-title p {
  margin: 6px 0 0;
  color: #6d7ea5;
  font-size: 13px;
}

.xya-msg-head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.xya-msg-icon-btn,
.xya-msg-primary-btn,
.xya-msg-ghost-btn,
.xya-msg-link-btn,
.xya-msg-filter-btn,
.xya-msg-more-btn {
  border: none;
  cursor: pointer;
  transition: .2s ease;
}

.xya-msg-icon-btn {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: #f0f5ff;
  color: #3056d3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.xya-msg-primary-btn {
  height: 38px;
  padding: 0 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, #246bff, #4a86ff);
  color: #fff;
  font-weight: 600;
}

.xya-msg-ghost-btn {
  height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  background: #f6f9ff;
  color: #3155cb;
  font-weight: 600;
}

.xya-msg-link-btn {
  background: transparent;
  color: #3155cb;
  font-weight: 600;
  padding: 0;
}

.xya-msg-ghost-btn.danger {
  color: #d64545;
  background: #fff2f2;
}

.xya-msg-icon-btn:disabled,
.xya-msg-primary-btn:disabled,
.xya-msg-ghost-btn:disabled,
.xya-msg-more-btn:disabled {
  opacity: .6;
  cursor: not-allowed;
}

.xya-msg-sidebar-toolbar {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.xya-msg-select,
.xya-msg-search,
.xya-msg-textarea,
.xya-msg-modal-input,
.xya-msg-modal-textarea {
  width: 100%;
  border: 1px solid #d7e2f5;
  border-radius: 14px;
  background: #f9fbff;
  color: #12234a;
  outline: none;
}

.xya-msg-select,
.xya-msg-search {
  height: 44px;
  padding: 0 14px;
}

.xya-msg-filter-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.xya-msg-filter-btn {
  min-height: 46px;
  border-radius: 14px;
  background: #f6f9ff;
  color: #5e709a;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
}

.xya-msg-filter-btn em {
  font-style: normal;
  color: #2446aa;
  font-weight: 700;
}

.xya-msg-filter-btn.active {
  background: linear-gradient(135deg, #246bff, #4a86ff);
  color: #fff;
}

.xya-msg-filter-btn.active em {
  color: #fff;
}

.xya-msg-alert {
  margin-bottom: 12px;
  color: #bf3838;
  font-size: 13px;
}

.xya-msg-captcha-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  border: 1px solid transparent;
}

.xya-msg-captcha-banner.solving {
  background: linear-gradient(135deg, #fff7e6, #fff1d6);
  border-color: #ffd591;
  color: #ad6800;
}

.xya-msg-captcha-banner.success {
  background: linear-gradient(135deg, #f0f9eb, #e1f3d8);
  border-color: #b7eb8f;
  color: #389e0d;
}

.xya-msg-captcha-banner.fail {
  background: linear-gradient(135deg, #fff1f0, #ffccc7);
  border-color: #ffa39e;
  color: #cf1322;
}

.xya-msg-captcha-text {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}

.xya-msg-captcha-retry {
  flex-shrink: 0;
  height: 28px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid #ffa39e;
  background: #fff;
  color: #cf1322;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.xya-msg-captcha-retry:hover:not(:disabled) {
  background: #fff1f0;
}

.xya-msg-captcha-retry:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.xya-msg-conversation-list {
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0 12px 0 16px;
  min-height: 0;
  overscroll-behavior: contain;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.xya-msg-conversation-list::-webkit-scrollbar {
  width: 0;
  height: 0;
}

.xya-msg-conversation {
  width: 100%;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 12px;
  padding: 14px 10px;
  border: 1px solid transparent;
  border-radius: 18px;
  background: transparent;
  text-align: left;
  margin-bottom: 8px;
}

.xya-msg-conversation.active,
.xya-msg-conversation:hover {
  background: #f6f9ff;
  border-color: #dce6fb;
}

.xya-msg-avatar-wrap {
  position: relative;
}

.xya-msg-avatar {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  background: linear-gradient(135deg, #d6e3ff, #9cb8ff);
  color: #17337e;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  overflow: hidden;
}

.xya-msg-avatar.small {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  flex-shrink: 0;
}

.xya-msg-avatar.large {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  flex-shrink: 0;
}

.avatar-image {
  object-fit: cover;
}

.xya-msg-unread-dot {
  position: absolute;
  top: -4px;
  right: -6px;
  min-width: 18px;
  height: 18px;
  border-radius: 999px;
  padding: 0 5px;
  background: #ff5757;
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}

.xya-msg-conversation-main {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.xya-msg-conversation-top,
.xya-msg-conversation-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.xya-msg-conversation-top strong,
.xya-msg-conversation-preview,
.xya-msg-goods-text,
.xya-msg-template-manage-info span {
  display: block;
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xya-msg-conversation-top > span,
.xya-msg-conversation-bottom .xya-msg-status-chip {
  color: #8191b3;
  font-size: 12px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.xya-msg-goods-text {
  color: #8191b3;
  font-size: 12px;
}

.xya-msg-goods-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}

.xya-msg-goods-thumb {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
  background: #f0f3f9;
}

.xya-msg-goods-thumb.small {
  width: 22px;
  height: 22px;
  border-radius: 6px;
}

.xya-msg-chat-goods {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.xya-msg-chat-goods p {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xya-msg-conversation-middle {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.xya-msg-ai-tag,
.xya-msg-bubble-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  height: 22px;
  border-radius: 999px;
  background: #eff5ff;
  color: #2356df;
  font-size: 12px;
  font-weight: 700;
}

.xya-msg-status-chip {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.xya-msg-status-chip.highlight {
  background: #fff0f0;
  color: #e14d4d;
}

.xya-msg-status-chip.active {
  background: #edf6ff;
  color: #2662d8;
}

.xya-msg-status-chip.success {
  background: #edfff4;
  color: #228c52;
}

.xya-msg-status-chip.muted {
  background: #f2f5fb;
  color: #6f80a7;
}

.xya-msg-more-wrap {
  padding: 8px 0 0;
  text-align: center;
}

.xya-msg-more-btn {
  height: 34px;
  padding: 0 16px;
  border-radius: 10px;
  background: #f2f6ff;
  color: #3155cb;
}

.xya-msg-more-tip {
  padding: 10px 0 4px;
  color: #7b8cae;
  font-size: 12px;
}

.xya-msg-footer-note {
  margin-top: 10px;
  color: #7b8cae;
  font-size: 12px;
}

.xya-msg-chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.xya-msg-chat-head {
  padding: 18px 20px;
  border-bottom: 1px solid #eef3fb;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
}

.xya-msg-chat-title {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.xya-msg-chat-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.xya-msg-chat-stream {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 22px 20px;
  background:
    radial-gradient(circle at top left, rgba(36, 107, 255, 0.08), transparent 34%),
    linear-gradient(180deg, #fbfdff, #f5f8ff);
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.xya-msg-bubble-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  margin-bottom: 16px;
}

.xya-msg-bubble-row.me {
  justify-content: flex-end;
}

.xya-msg-bubble-row.image-message {
  align-items: flex-start;
}

.xya-msg-image-message {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: fit-content;
  max-width: min(78%, 420px);
  min-width: 0;
}

.xya-msg-image-message.me {
  align-items: flex-end;
  margin-left: auto;
}

.xya-msg-image-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: fit-content;
  max-width: 100%;
}

.xya-msg-image-message-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
  color: #8391b5;
  font-size: 12px;
  line-height: 1.45;
  font-variant-numeric: tabular-nums;
}

.xya-msg-image-message.me .xya-msg-image-message-meta {
  align-items: flex-end;
  text-align: right;
}

.xya-msg-image-message-time {
  white-space: nowrap;
}

.xya-msg-bubble {
  max-width: min(72%, 620px);
  padding: 12px 14px;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 8px 18px rgba(31, 74, 163, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.xya-msg-bubble.image-only {
  padding: 0;
  background: transparent;
  box-shadow: none;
  max-width: min(78%, 420px);
  width: fit-content;
}

.xya-msg-bubble-row.me .xya-msg-bubble {
  background: linear-gradient(135deg, #2d6dff, #4a86ff);
  color: #fff;
}

.xya-msg-bubble-row.me .xya-msg-bubble.image-only {
  background: transparent;
  color: inherit;
}

.xya-msg-bubble-images {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.xya-msg-image-card {
  display: block;
  width: fit-content;
  max-width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
  cursor: zoom-in;
  text-align: left;
}

.xya-msg-image-card:focus-visible {
  outline: 2px solid #246bff;
  outline-offset: 4px;
}

.xya-msg-image {
  display: block;
  width: auto;
  max-width: min(100%, 420px);
  height: auto;
  border-radius: 18px;
  background: #eef3fb;
  object-fit: contain;
}

.xya-msg-image-tag {
  position: absolute;
  top: 10px;
  right: 10px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(24, 27, 35, 0.72);
  color: #fff;
  font-size: 12px;
  line-height: 22px;
  pointer-events: none;
}

.xya-msg-bubble-text {
  white-space: pre-wrap;
  line-height: 1.6;
  word-break: break-word;
}

.xya-msg-bubble-meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(98, 115, 152, 0.9);
  font-size: 12px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.xya-msg-bubble-row.me .xya-msg-bubble-meta {
  color: rgba(255, 255, 255, 0.82);
}

.xya-msg-bubble.image-only .xya-msg-bubble-meta {
  margin-top: 6px;
  justify-content: flex-end;
}

.xya-msg-composer {
  border-top: 1px solid #eef3fb;
  padding: 14px 20px 18px;
  background: #fff;
  flex-shrink: 0;
}

.xya-msg-composer-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.xya-msg-template-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.xya-msg-template-error {
  color: #b54708;
  font-size: 12px;
}

.xya-msg-card-empty.error-state {
  display: grid;
  gap: 10px;
  justify-items: start;
  padding: 16px;
  border: 1px solid #fecaca;
  border-radius: 12px;
  background: #fff7f7;
  color: #991b1b;
}

.xya-msg-template-item {
  padding: 9px 12px;
  border: 1px solid #dce6fb;
  border-radius: 14px;
  background: #f8fbff;
  color: #29417b;
  cursor: pointer;
  max-width: 168px;
  text-align: left;
}

.xya-msg-template-item strong,
.xya-msg-template-item span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xya-msg-template-item strong {
  font-size: 12px;
  margin-bottom: 4px;
}

.xya-msg-template-item span {
  font-size: 11px;
  color: #7081a5;
}

.xya-msg-composer-toolbar,
.xya-msg-card-actions,
.xya-msg-send-row,
.xya-msg-template-edit-actions,
.xya-msg-template-manage-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.xya-msg-composer-toolbar {
  margin-bottom: 12px;
}

.xya-msg-textarea {
  resize: none;
  min-height: 110px;
  max-height: 140px;
  padding: 12px 14px;
}

.xya-msg-send-row {
  margin-top: 12px;
  align-items: center;
  justify-content: space-between;
}

.xya-msg-send-meta {
  color: #7384a8;
  font-size: 12px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.xya-msg-detail-panel {
  display: grid;
  gap: 16px;
  align-content: start;
  height: 100%;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.xya-msg-card {
  border-radius: 22px;
  padding: 18px;
}

.xya-msg-product {
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr);
  gap: 14px;
}

.xya-msg-product-cover {
  width: 86px;
  height: 86px;
  border-radius: 18px;
  object-fit: cover;
  background: #eef3fb;
}

.xya-msg-product-info {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.xya-msg-product-info strong {
  color: #112147;
  line-height: 1.5;
}

.xya-msg-product-info span,
.xya-msg-card-empty,
.xya-msg-event-item span,
.xya-msg-metrics span {
  color: #7384a8;
  font-size: 13px;
}

.xya-msg-metrics {
  display: grid;
  gap: 12px;
  margin: 6px 0 16px;
}

.xya-msg-metrics div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.xya-msg-metrics strong {
  color: #112147;
  text-align: right;
}

.xya-msg-card-status {
  margin: -4px 0 14px;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f5f8ff;
  color: #3259cf;
  font-size: 13px;
  font-weight: 600;
}

.xya-msg-card-status.warning {
  background: #fff4eb;
  color: #c56a18;
}

.xya-msg-card-status.success {
  background: #eefaf2;
  color: #1d8a52;
}

.xya-msg-event-list {
  display: grid;
  gap: 10px;
}

.xya-msg-event-item {
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fbff;
}

.xya-msg-event-item strong {
  display: block;
  font-size: 12px;
  color: #3259cf;
  margin-bottom: 4px;
}

.xya-msg-empty {
  color: #7d8dad;
  text-align: center;
  padding: 40px 18px;
}

.xya-msg-empty.big {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.xya-msg-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(10, 23, 56, 0.48);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 70;
}

.xya-msg-modal {
  width: min(820px, 100%);
  max-height: min(82vh, 880px);
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 30px 80px rgba(14, 35, 84, 0.22);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.xya-msg-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 22px;
  border-bottom: 1px solid #edf3fc;
}

.xya-msg-modal-head h3 {
  margin: 0;
}

.xya-msg-modal-body {
  padding: 20px 22px 22px;
  overflow: auto;
}

.xya-msg-template-edit-row {
  display: grid;
  gap: 10px;
  margin-bottom: 18px;
}

.xya-msg-modal-input,
.xya-msg-modal-textarea {
  padding: 12px 14px;
}

.xya-msg-modal-textarea {
  resize: vertical;
}

.xya-msg-template-manage-list {
  display: grid;
  gap: 10px;
}

.xya-msg-template-manage-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  padding: 14px;
  border-radius: 18px;
  background: #f8fbff;
}

.xya-msg-template-manage-info strong {
  display: block;
  margin-bottom: 4px;
  color: #112147;
}

.xya-msg-image-preview-mask {
  background: rgba(7, 15, 37, 0.82);
}

.xya-msg-image-preview {
  position: relative;
  max-width: min(92vw, 1100px);
  max-height: 90vh;
}

.xya-msg-image-preview img {
  display: block;
  max-width: 100%;
  max-height: 90vh;
  border-radius: 20px;
}

.xya-msg-image-preview-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 999px;
  background: rgba(16, 27, 58, 0.78);
  color: #fff;
  cursor: pointer;
}

.success-text {
  color: #228c52;
}

.danger-text {
  color: #d64545;
}

@media (max-width: 1280px) {
  .xya-msg-layout {
    grid-template-columns: 280px minmax(0, 1fr) 320px;
    gap: 12px;
  }
}

@media (max-width: 940px) {
  .xya-msg-layout {
    grid-template-columns: 300px minmax(0, 1fr);
  }

  .xya-msg-detail-panel {
    grid-column: 1 / -1;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .xya-msg-layout {
    grid-template-columns: 1fr;
  }

  .xya-msg-detail-panel {
    grid-template-columns: 1fr;
  }

  .xya-msg-chat-head,
  .xya-msg-composer-top,
  .xya-msg-send-row,
  .xya-msg-sidebar-head {
    flex-direction: column;
    align-items: stretch;
  }
}

/* === 客户订单板块 === */
.xya-msg-order-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.xya-msg-order-count {
  font-size: 13px;
  font-weight: 500;
  color: #7384a8;
}

.xya-msg-order-refresh {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  color: #3259cf;
  transition: background 0.2s ease;
}

.xya-msg-order-refresh:hover:not(:disabled) {
  background: #eef3ff;
}

.xya-msg-order-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.xya-msg-order-refresh.spinning :deep(.ui-icon),
.xya-msg-order-refresh.spinning img {
  animation: xya-msg-spin 0.9s linear infinite;
}

@keyframes xya-msg-spin {
  to {
    transform: rotate(360deg);
  }
}

.xya-msg-order-list {
  display: grid;
  gap: 12px;
  margin-top: 4px;
}

.xya-msg-order-item {
  padding: 12px;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfdff 0%, #f6faff 100%);
  border: 1px solid #e7eef9;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.xya-msg-order-item:hover {
  border-color: #c2d5f5;
  box-shadow: 0 8px 22px rgba(23, 61, 135, 0.08);
  transform: translateY(-1px);
}

.xya-msg-order-item-main {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 12px;
  align-items: flex-start;
}

.xya-msg-order-cover-wrap {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 14px;
  overflow: hidden;
  background: #eef3fb;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(23, 61, 135, 0.08);
}

.xya-msg-order-cover-placeholder {
  position: absolute;
  inset: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #9eb3d6;
}

.xya-msg-order-cover-placeholder :deep(.ui-icon),
.xya-msg-order-cover-placeholder img {
  width: 26px;
  height: 26px;
  opacity: 0.7;
}

.xya-msg-order-cover {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.xya-msg-order-item-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.xya-msg-order-title {
  font-size: 13.5px;
  font-weight: 600;
  color: #112147;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.xya-msg-order-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.xya-msg-order-amount {
  font-size: 14px;
  color: #e6532e;
  font-weight: 700;
  letter-spacing: -0.2px;
}

.xya-msg-order-status {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 9px;
  font-size: 11.5px;
  font-weight: 600;
  background: #eef3ff;
  color: #3259cf;
  letter-spacing: 0.2px;
}

.xya-msg-order-status.warning {
  background: #fff4eb;
  color: #c56a18;
}

.xya-msg-order-status.success {
  background: #eefaf2;
  color: #1d8a52;
}

.xya-msg-order-status.info {
  background: #eef3ff;
  color: #3259cf;
}

.xya-msg-order-status.muted {
  background: #f0f2f7;
  color: #7384a8;
}

.xya-msg-order-no {
  font-size: 11.5px;
  color: #9aa8c4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.xya-msg-order-time {
  font-size: 11.5px;
  color: #9aa8c4;
  font-variant-numeric: tabular-nums;
}

.xya-msg-order-fail {
  font-size: 12px;
  color: #e5484d;
  line-height: 1.5;
  background: #fdecec;
  padding: 4px 8px;
  border-radius: 8px;
  margin-top: 2px;
}

.xya-msg-order-error {
  color: #e5484d;
}

.xya-msg-order-item .xya-msg-card-actions {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e7eef9;
}

/* === 订单详情弹窗 === */
.xya-msg-order-modal {
  width: min(560px, 100%);
  max-height: min(82vh, 880px);
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 30px 80px rgba(14, 35, 84, 0.22);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.xya-msg-order-modal-body {
  padding: 20px 22px 22px;
  overflow: auto;
}

.xya-msg-order-detail-section {
  display: grid;
  gap: 10px;
}

.xya-msg-order-detail-section + .xya-msg-order-detail-section {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #edf3fc;
}

.xya-msg-order-detail-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.xya-msg-order-detail-label {
  flex-shrink: 0;
  width: 84px;
  color: #7384a8;
  font-size: 13px;
}

.xya-msg-order-detail-value {
  flex: 1;
  text-align: right;
  color: #112147;
  font-size: 13px;
  word-break: break-all;
}

.xya-msg-order-detail-subtitle {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 700;
  color: #102147;
}

.xya-msg-order-detail-item {
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fbff;
  border: 1px solid #e7eef9;
}

.xya-msg-order-detail-item + .xya-msg-order-detail-item {
  margin-top: 8px;
}

.xya-msg-order-detail-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #112147;
  line-height: 1.5;
}

.xya-msg-order-detail-item-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  font-size: 12px;
  color: #516286;
}

.xya-msg-order-detail-spec {
  color: #7384a8;
}
</style>
