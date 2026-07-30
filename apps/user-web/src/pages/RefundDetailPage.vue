<template>
  <div class="refund-detail-page">
    <!-- 顶部导航条 -->
    <div class="detail-header">
      <div class="header-left">
        <button type="button" class="back-btn" @click="onBackToList">
          <span class="back-icon">←</span>
          <span>返回退款管理</span>
        </button>
        <div class="header-title-group">
          <h2 class="detail-title">退款详情</h2>
          <span v-if="lastSuccessAt" class="last-refresh">
            · 最后刷新 {{ formatTime(lastSuccessAt) }}
          </span>
        </div>
      </div>
      <div class="header-actions">
        <AppButton
          type="primary"
          :loading="refreshing"
          :disabled="loading || refreshing"
          class="btn-refresh"
          @click="onRefreshAll"
        >
          <span class="refresh-icon">↻</span>
          {{ refreshing ? '刷新中...' : '刷新全部' }}
        </AppButton>
      </div>
    </div>

    <!-- 路由参数错误 / 权限错误 / 不存在 -->
    <EmptyState
      v-if="routeError"
      variant="error"
      icon="⚠"
      title="无法打开退款详情"
      :description="routeError"
    >
      <template #actions>
        <AppButton type="primary" @click="onBackToList">返回退款管理</AppButton>
      </template>
    </EmptyState>

    <template v-else>
      <!-- 全部失败且无缓存 -->
      <EmptyState
        v-if="allFailedNoCache"
        variant="error"
        icon="⚠"
        title="退款详情加载失败"
        :description="allFailedError || '三个详情接口均失败，且暂无缓存数据。'"
      >
        <template #actions>
          <AppButton type="primary" :loading="refreshing" @click="onRefreshAll">重新加载</AppButton>
        </template>
      </EmptyState>

      <!-- 顶部状态卡（来自 summary + refundDetail.topLevel + basicRefundInfo） -->
      <section v-if="statusCardVisible" class="status-card">
        <div class="status-card-row">
          <div class="status-card-item">
            <span class="label">所属账号</span>
            <span class="value">{{ accountLabel }}</span>
          </div>
          <div class="status-card-item">
            <span class="label">退款状态</span>
            <span class="value" :class="['status-badge', refundStatusBadgeClass]">
              {{ displayRefundStatus || '-' }}
            </span>
          </div>
          <div class="status-card-item">
            <span class="label">退款类型</span>
            <span class="value">{{ displayRefundType || '-' }}</span>
          </div>
          <div class="status-card-item">
            <span class="label">申请金额</span>
            <span class="value money">{{ formatMoney(displayApplyMoney) }}</span>
          </div>
        </div>
        <div class="status-card-row">
          <div class="status-card-item">
            <span class="label">退款原因</span>
            <span class="value">{{ displayReason || '-' }}</span>
          </div>
          <div class="status-card-item">
            <span class="label">申请时间</span>
            <span class="value">{{ formatTime(displayGmtCreated) || '-' }}</span>
          </div>
          <div class="status-card-item">
            <span class="label">结束时间</span>
            <span class="value">{{ formatTime(displayDisputeEnd) || '-' }}</span>
          </div>
          <div class="status-card-item">
            <span class="label">客服介入</span>
            <span class="value">{{ displayCsStatus || '-' }}</span>
          </div>
        </div>
        <div class="status-card-row">
          <div class="status-card-item">
            <span class="label">orderId</span>
            <span class="value mono" :title="routeOrderId">{{ routeOrderId }}</span>
          </div>
          <div class="status-card-item">
            <span class="label">refundId</span>
            <span class="value mono" :title="routeRefundId">{{ routeRefundId }}</span>
          </div>
        </div>
      </section>

      <!-- 三接口状态指示器（局部失败时显示单独重试） -->
      <section class="api-status-bar">
        <div
          v-for="api in apiStatusList"
          :key="api.key"
          :class="['api-status-item', `status-${api.status}`]"
        >
          <span class="api-name">{{ api.label }}</span>
          <span class="api-state">{{ api.stateText }}</span>
          <button
            v-if="api.status === 'failed'"
            type="button"
            class="retry-btn"
            :disabled="api.retrying"
            @click="onRetryApi(api.key)"
          >
            {{ api.retrying ? '重试中...' : '重试' }}
          </button>
        </div>
      </section>

      <!-- 退款阶段节点 nodeStatusInfo -->
      <section v-if="nodeStatusInfo" class="detail-card">
        <h3 class="card-title">退款阶段节点</h3>
        <div v-if="!nodeStatusInfo.needShowStatusNode && !nodeStatusInfo.nodeStatusList?.length" class="card-empty">
          暂无阶段节点信息
        </div>
        <ol v-else class="node-list">
          <li
            v-for="(node, idx) in (nodeStatusInfo.nodeStatusList || [])"
            :key="idx"
            class="node-item"
          >
            <span class="node-time">{{ formatTime(node.time) || '-' }}</span>
            <span class="node-text">{{ node.txt || '-' }}</span>
          </li>
        </ol>
      </section>

      <!-- 退款基本信息 basicRefundInfo -->
      <section v-if="basicRefundInfo" class="detail-card">
        <h3 class="card-title">退款基本信息</h3>
        <dl class="info-grid">
          <div class="info-item"><dt>退款类型</dt><dd>{{ basicRefundInfo.refundTypeDesc || basicRefundInfo.refundType || '-' }}</dd></div>
          <div class="info-item"><dt>申请金额</dt><dd>{{ formatMoney(basicRefundInfo.applyMoney) }}</dd></div>
          <div class="info-item"><dt>退款原因</dt><dd>{{ basicRefundInfo.reasonText || '-' }}</dd></div>
          <div class="info-item"><dt>商品状态</dt><dd>{{ basicRefundInfo.goodsStatusDesc || basicRefundInfo.goodsStatus || '-' }}</dd></div>
          <div class="info-item"><dt>退款状态</dt><dd>{{ basicRefundInfo.refundStatusDesc || basicRefundInfo.refundStatus || '-' }}</dd></div>
          <div class="info-item"><dt>客服介入</dt><dd>{{ basicRefundInfo.csStatusDesc || basicRefundInfo.csStatus || '-' }}</dd></div>
          <div class="info-item"><dt>运费承担</dt><dd>{{ basicRefundInfo.postFeeBear || '-' }}</dd></div>
          <div class="info-item"><dt>申请时间</dt><dd>{{ formatTime(basicRefundInfo.gmtCreatedTime) || '-' }}</dd></div>
          <div class="info-item"><dt>修改时间</dt><dd>{{ formatTime(basicRefundInfo.gmtModifiedTime) || '-' }}</dd></div>
          <div class="info-item"><dt>结束时间</dt><dd>{{ formatTime(basicRefundInfo.disputeEndTime) || '-' }}</dd></div>
        </dl>
      </section>

      <!-- 退款进度 progressDetail -->
      <section v-if="progressDetail" class="detail-card">
        <h3 class="card-title">{{ progressDetail.title || '退款进度' }}</h3>
        <div v-if="!progressDetail.progressNodeList?.length" class="card-empty">暂无进度信息</div>
        <ol v-else class="progress-list">
          <li
            v-for="(node, idx) in progressDetail.progressNodeList"
            :key="idx"
            class="progress-item"
          >
            <div class="progress-head">
              <span class="progress-time">{{ node.timeStr || '-' }}</span>
              <span class="progress-text">{{ node.text || '-' }}</span>
            </div>
            <p v-if="node.tips" class="progress-tips">{{ node.tips }}</p>
            <div v-if="node.proofInfoList?.length" class="progress-proofs">
              <img
                v-for="(img, i) in node.proofInfoList"
                :key="i"
                :src="img.url"
                :alt="`凭证${i + 1}`"
                class="proof-thumb"
                loading="lazy"
                @click="openImagePreview(img.url)"
                @error="onImageError"
              >
            </div>
          </li>
        </ol>
      </section>

      <!-- 退款历史 refundRecordList（当前 refundId 高亮） -->
      <section v-if="serviceRecordData" class="detail-card">
        <h3 class="card-title">退款历史</h3>
        <div v-if="!serviceRecordData.refundRecordList?.length" class="card-empty">
          暂无退款历史记录
        </div>
        <table v-else class="record-table">
          <thead>
            <tr>
              <th>退款ID</th>
              <th>退款类型</th>
              <th>金额</th>
              <th>原因</th>
              <th>状态</th>
              <th>申请时间</th>
              <th>结束时间</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="record in serviceRecordData.refundRecordList"
              :key="record.refundId || Math.random()"
              :class="{ 'current-refund': record.isCurrent }"
            >
              <td class="mono">
                {{ record.refundId || '-' }}
                <span v-if="record.isCurrent" class="current-tag">当前</span>
              </td>
              <td>{{ record.refundType || '-' }}</td>
              <td>{{ formatMoney(record.money) }}</td>
              <td>{{ record.reasonText || '-' }}</td>
              <td>{{ record.statusDesc || record.status || '-' }}</td>
              <td>{{ formatTime(record.gmtCreatedTime) || '-' }}</td>
              <td>{{ formatTime(record.endTime) || '-' }}</td>
            </tr>
          </tbody>
        </table>

        <!-- 退运费记录 postageRefundRecordList -->
        <h4 v-if="serviceRecordData.postageRefundRecordList?.length" class="card-subtitle">
          退运费记录
        </h4>
        <div
          v-else
          class="postage-empty"
        >
          暂无退运费记录
        </div>
        <table v-if="serviceRecordData.postageRefundRecordList?.length" class="record-table">
          <thead>
            <tr>
              <th>退款ID</th>
              <th>金额</th>
              <th>状态</th>
              <th>申请时间</th>
              <th>结束时间</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="record in serviceRecordData.postageRefundRecordList"
              :key="record.refundId || Math.random()"
            >
              <td class="mono">{{ record.refundId || '-' }}</td>
              <td>{{ formatMoney(record.money) }}</td>
              <td>{{ record.statusDesc || record.status || '-' }}</td>
              <td>{{ formatTime(record.gmtCreatedTime) || '-' }}</td>
              <td>{{ formatTime(record.endTime) || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 商品和订单信息 -->
      <section v-if="fullInfoData" class="detail-card">
        <h3 class="card-title">商品和订单信息</h3>
        <div v-if="!fullInfoData._valid" class="card-empty">订单信息加载失败</div>
        <template v-else>
          <div v-if="fullInfoData.merchantItemVO" class="item-block">
            <img
              v-if="fullInfoData.merchantItemVO.itemPicUrl"
              :src="fullInfoData.merchantItemVO.itemPicUrl"
              :alt="fullInfoData.merchantItemVO.title || '商品图片'"
              class="item-pic"
              loading="lazy"
              @error="onImageError"
            >
            <div class="item-meta">
              <div class="item-title">{{ fullInfoData.merchantItemVO.title || '-' }}</div>
              <div class="item-spec">{{ fullInfoData.merchantItemVO.itemInfoLines || '-' }}</div>
            </div>
          </div>
          <dl v-if="fullInfoData.merchantCommonData" class="info-grid">
            <div class="info-item"><dt>商品ID</dt><dd class="mono">{{ fullInfoData.merchantCommonData.itemId || '-' }}</dd></div>
            <div class="info-item"><dt>订单ID</dt><dd class="mono">{{ fullInfoData.merchantCommonData.orderId || '-' }}</dd></div>
            <div class="info-item"><dt>订单状态</dt><dd>{{ fullInfoData.merchantCommonData.orderStatus || '-' }}</dd></div>
            <div class="info-item"><dt>下单时间</dt><dd>{{ formatTime(fullInfoData.merchantCommonData.createTime) || '-' }}</dd></div>
            <div class="info-item"><dt>付款时间</dt><dd>{{ formatTime(fullInfoData.merchantCommonData.paySuccessTime) || '-' }}</dd></div>
            <div class="info-item"><dt>发货时间</dt><dd>{{ formatTime(fullInfoData.merchantCommonData.consignTime) || '-' }}</dd></div>
          </dl>
        </template>
      </section>

      <!-- 金额明细 -->
      <section v-if="fullInfoData?._valid && (fullInfoData.merchantPriceVO || fullInfoData.orderInfoVO?.priceInfo)" class="detail-card">
        <h3 class="card-title">金额明细</h3>
        <dl class="info-grid">
          <div v-if="fullInfoData.merchantPriceVO?.auctionPrice !== null" class="info-item">
            <dt>商品单价</dt><dd>{{ formatMoney(fullInfoData.merchantPriceVO?.auctionPrice) }}</dd>
          </div>
          <div v-if="fullInfoData.merchantPriceVO?.buyNum" class="info-item">
            <dt>件数</dt><dd>{{ fullInfoData.merchantPriceVO.buyNum }}</dd>
          </div>
          <div v-if="fullInfoData.merchantPriceVO?.totalPrice !== null" class="info-item">
            <dt>商品总价</dt><dd>{{ formatMoney(fullInfoData.merchantPriceVO?.totalPrice) }}</dd>
          </div>
          <div v-if="fullInfoData.merchantPriceVO?.postFee !== null" class="info-item">
            <dt>运费</dt><dd>{{ formatMoney(fullInfoData.merchantPriceVO?.postFee) }}</dd>
          </div>
          <div v-if="fullInfoData.merchantPriceVO?.discountFee !== null" class="info-item">
            <dt>优惠</dt><dd>{{ formatMoney(fullInfoData.merchantPriceVO?.discountFee) }}</dd>
          </div>
          <div v-if="fullInfoData.merchantPriceVO?.confirmFee !== null" class="info-item">
            <dt>已确认金额</dt><dd>{{ formatMoney(fullInfoData.merchantPriceVO?.confirmFee) }}</dd>
          </div>
          <div class="info-item highlight">
            <dt>当前退款申请金额</dt>
            <dd>{{ formatMoney(displayApplyMoney) }}</dd>
          </div>
          <div v-if="fullInfoData.merchantPriceVO?.refundFee !== null" class="info-item">
            <dt>订单维度退款金额</dt>
            <dd>{{ formatMoney(fullInfoData.merchantPriceVO?.refundFee) }}</dd>
          </div>
        </dl>
        <p class="amount-tip">
          注：当前退款申请金额以 refund.detail.basicRefundInfo.applyMoney 为准，
          不被 merchantPriceVO.refundFee 覆盖（订单维度退款金额可能为 0，但当前申请金额仍存在）。
        </p>
      </section>

      <!-- 买家脱敏信息 -->
      <section v-if="fullInfoData?.merchantBuyerVO" class="detail-card">
        <h3 class="card-title">买家信息（已脱敏）</h3>
        <dl class="info-grid">
          <div class="info-item"><dt>买家昵称</dt><dd>{{ fullInfoData.merchantBuyerVO.userNick || '-' }}</dd></div>
          <div class="info-item"><dt>买家ID</dt><dd class="mono">{{ fullInfoData.merchantBuyerVO.buyerId || '-' }}</dd></div>
          <div class="info-item"><dt>姓名</dt><dd>{{ fullInfoData.merchantBuyerVO.name || '-' }}</dd></div>
          <div class="info-item"><dt>电话</dt><dd>{{ fullInfoData.merchantBuyerVO.phone || '-' }}</dd></div>
          <div class="info-item"><dt>地址</dt><dd>{{ fullInfoData.merchantBuyerVO.address || '-' }}</dd></div>
        </dl>
        <p class="amount-tip">仅展示服务端已脱敏内容，不尝试解密 encryptedPhone。</p>
      </section>

      <!-- 订单时间线 orderStatusVO -->
      <section v-if="fullInfoData?.orderStatusVO" class="detail-card">
        <h3 class="card-title">订单时间线</h3>
        <div v-if="fullInfoData.orderStatusVO.orderStatusInfo?.title" class="order-status-head">
          当前状态：{{ fullInfoData.orderStatusVO.orderStatusInfo.title }}
        </div>
        <div v-if="!fullInfoData.orderStatusVO.orderStatusNodeList?.length" class="card-empty">
          暂无订单时间线
        </div>
        <ol v-else class="timeline-list">
          <li
            v-for="(node, idx) in fullInfoData.orderStatusVO.orderStatusNodeList"
            :key="idx"
            :class="['timeline-item', { completed: node.completed }]"
          >
            <span class="timeline-dot" :class="{ done: node.completed }"></span>
            <div class="timeline-content">
              <div class="timeline-title">{{ node.title || '-' }}</div>
              <div class="timeline-time">{{ formatTime(node.time) || '-' }}</div>
            </div>
          </li>
        </ol>
      </section>

      <!-- 卖家发货物流 + 买家退货物流 -->
      <section v-if="anyLogistics" class="detail-card">
        <h3 class="card-title">物流信息</h3>
        <!-- 卖家发货物流 -->
        <div class="logistics-block">
          <h4 class="card-subtitle">卖家发货物流</h4>
          <dl class="info-grid">
            <div class="info-item">
              <dt>物流公司</dt>
              <dd>{{ sellerLogistics.companyName || summary?.logisticsCompany || '-' }}</dd>
            </div>
            <div class="info-item">
              <dt>运单号</dt>
              <dd class="mono">{{ sellerLogistics.mailNo || summary?.logisticsMailNo || '-' }}</dd>
            </div>
            <div class="info-item">
              <dt>发货时间</dt>
              <dd>{{ formatTime(sellerLogistics.consignTime) || formatTime(summary?.consignTime) || '-' }}</dd>
            </div>
          </dl>
        </div>
        <!-- 买家退货物流 -->
        <div class="logistics-block">
          <h4 class="card-subtitle">买家退货物流</h4>
          <dl class="info-grid">
            <div class="info-item">
              <dt>物流公司</dt>
              <dd>{{ buyerReturnLogistics.companyName || '-' }}</dd>
            </div>
            <div class="info-item">
              <dt>运单号</dt>
              <dd class="mono">{{ buyerReturnLogistics.mailNo || '-' }}</dd>
            </div>
            <div class="info-item">
              <dt>发货时间</dt>
              <dd>{{ formatTime(buyerReturnLogistics.consignTime) || '-' }}</dd>
            </div>
          </dl>
        </div>
        <p v-if="!sellerLogistics.companyName && !buyerReturnLogistics.companyName" class="card-empty">
          暂无物流信息
        </p>
      </section>

      <!-- 退款说明 refundDescribe（富文本安全渲染） -->
      <section v-if="refundDescribe" class="detail-card">
        <h3 class="card-title">{{ refundDescribe.title || '退款说明' }}</h3>
        <div v-if="!refundDescribe.descRichText?.length" class="card-empty">暂无说明</div>
        <div v-else class="rich-text-container">
          <div
            v-for="(item, idx) in refundDescribe.descRichText"
            :key="idx"
            class="rich-text-item"
            :style="buildSafeStyle(item.style)"
          >
            <span class="rich-text-content">{{ item.content }}</span>
            <a
              v-if="item.linkUrl && item.type === 'link'"
              :href="item.linkUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="rich-text-link"
              @click.stop
            >
              官方指南
            </a>
          </div>
        </div>
      </section>

      <!-- 退款凭证 refundProof + progressNodeList[].proofInfoList -->
      <section v-if="allProofs.length" class="detail-card">
        <h3 class="card-title">退款凭证</h3>
        <div class="proof-grid">
          <img
            v-for="(img, i) in allProofs"
            :key="i"
            :src="img.url"
            :alt="`凭证${i + 1}`"
            class="proof-thumb"
            loading="lazy"
            @click="openImagePreview(img.url)"
            @error="onImageError"
          >
        </div>
      </section>

      <!-- 当前允许的退款操作 bottomBar（已过滤递归"退款详情"按钮） -->
      <section v-if="bottomBarButtons.length" class="detail-card actions-card">
        <h3 class="card-title">可执行的退款操作</h3>
        <div class="actions-row">
          <template v-for="btn in bottomBarButtons" :key="btn.code">
            <button
              v-if="btn.code === 'applyDisputePage'"
              type="button"
              class="action-btn op-warn"
              @click="onApplyDispute(btn)"
            >
              {{ btn.name || '我要维权' }}
            </button>
            <button
              v-else-if="btn.code === 'agreeRefundApply'"
              type="button"
              class="action-btn op-primary"
              :disabled="agreeing"
              @click="onAgreeRefund(btn)"
            >
              {{ agreeing ? '处理中...' : (btn.name || '同意退款') }}
            </button>
          </template>
        </div>
        <p class="amount-tip">
          注：当前页面本身就是退款详情页，不显示会跳回相同退款详情的"退款详情"按钮，避免递归跳转。
          联系买家、提醒收货、延长收货暂未实现，不动态执行响应中返回的任意 MTOP API。
        </p>
      </section>

      <!-- 同意退款二次确认弹窗 -->
      <Teleport to="body">
        <div v-if="agreeModal.visible" class="refund-modal-mask" @click.self="closeAgreeModal">
          <div class="refund-modal">
            <div class="refund-modal-head">
              <h3>{{ agreeModal.title || '确认同意退款' }}</h3>
              <button type="button" class="refund-modal-close" @click="closeAgreeModal">×</button>
            </div>
            <div class="refund-modal-body">
              <p v-if="agreeModal.confirmText" class="modal-confirm-text">{{ agreeModal.confirmText }}</p>
              <p v-if="agreeModal.riskDesc" class="modal-risk">{{ agreeModal.riskDesc }}</p>
              <div class="modal-info">
                <div>账号：{{ agreeModal.accountLabel }}</div>
                <div>商品：{{ agreeModal.itemTitle }}</div>
                <div>退款金额：{{ agreeModal.refundFee ? `¥${agreeModal.refundFee}` : '-' }}</div>
              </div>
            </div>
            <div class="refund-modal-foot">
              <button type="button" class="action-btn" :disabled="agreeModal.submitting" @click="closeAgreeModal">取消</button>
              <button
                type="button"
                class="action-btn op-primary"
                :disabled="agreeModal.submitting"
                @click="confirmAgreeRefund"
              >
                {{ agreeModal.submitButtonText || '确认同意退款' }}
              </button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- 图片预览弹窗 -->
      <Teleport to="body">
        <div v-if="previewImageUrl" class="refund-modal-mask" @click.self="closeImagePreview">
          <div class="image-preview">
            <button type="button" class="image-preview-close" @click="closeImagePreview">×</button>
            <img :src="previewImageUrl" alt="凭证预览">
          </div>
        </div>
      </Teleport>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, shallowRef } from 'vue'
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'
import {
  getRefundDetail,
  refreshRefundDetail,
  retryRefundDetailApi,
  agreeRefund,
} from '../api/refunds.js'
// 注意：不在此处导入 saveRefundListState / consumeRefundListState
// 详情页返回列表时仅触发 navigate 事件，列表状态由 RefundsPage 在 onMounted 时自行消费
// 若在详情页消费会提前清除状态，导致 RefundsPage 无法恢复筛选条件

const emit = defineEmits(['navigate'])

// ============================================================
// 路由参数解析：#/refund-detail/{accountId}/{orderId}/{refundId}
// ============================================================
const routeAccountId = ref('')
const routeOrderId = ref('')
const routeRefundId = ref('')
const routeError = ref('')

function parseRouteParams() {
  const raw = (location.hash || '').replace(/^#\//, '')
  // 期望格式：refund-detail/{accountId}/{orderId}/{refundId}
  const m = raw.match(/^refund-detail\/([^/]+)\/([^/]+)\/([^/]+)$/)
  if (!m) {
    routeError.value = '详情页地址参数缺失，请从退款列表进入'
    return
  }
  routeAccountId.value = decodeURIComponent(m[1])
  routeOrderId.value = decodeURIComponent(m[2])
  routeRefundId.value = decodeURIComponent(m[3])
}

// ============================================================
// 状态
// ============================================================
const loading = ref(true)
const refreshing = ref(false)
const summary = ref(null)
const detail = shallowRef(null)
const cachedFlag = ref(false)
const cacheExpiredFlag = ref(false)
const globalError = ref('')
// 单接口重试中状态：{ service_record: bool, full_info: bool, refund_detail: bool }
const retryingMap = reactive({
  service_record: false,
  full_info: false,
  refund_detail: false,
})

// 同意退款
const agreeing = ref(false)
const agreeModal = reactive({
  visible: false,
  refundId: '',
  accountId: null,
  accountLabel: '',
  itemTitle: '',
  refundFee: '',
  riskDesc: '',
  confirmText: '',
  title: '',
  submitButtonText: '',
  submitting: false,
})

// 图片预览
const previewImageUrl = ref('')

// ============================================================
// 计算属性
// ============================================================
const accountLabel = computed(() => {
  return summary.value?.accountNickname || `账号 ${routeAccountId.value}`
})

const lastSuccessAt = computed(() => detail.value?.lastSuccessAt || null)

// 退款状态徽章
const refundStatusBadgeClass = computed(() => {
  const status = displayRefundStatus.value || ''
  const s = String(status)
  if (s.includes('成功') || s.includes('完成')) return 'green'
  if (s.includes('失败') || s.includes('拒绝') || s.includes('关闭')) return 'red'
  if (s.includes('等待') || s.includes('处理')) return 'orange'
  return 'blue'
})

// 当前退款状态（优先级：basicRefundInfo.refundStatusDesc > refundStatusInfo.title > summary）
const displayRefundStatus = computed(() => {
  const basic = basicRefundInfo.value
  if (basic?.refundStatusDesc) return basic.refundStatusDesc
  if (basic?.refundStatus) return basic.refundStatus
  const statusInfo = refundDetailData.value?.components?.refundStatusInfo
  if (statusInfo?.title) return statusInfo.title
  return summary.value?.refundStatusDesc || summary.value?.refundStatus || ''
})

const displayRefundType = computed(() => {
  const basic = basicRefundInfo.value
  if (basic?.refundTypeDesc) return basic.refundTypeDesc
  if (basic?.refundType) return basic.refundType
  return ''
})

const displayApplyMoney = computed(() => {
  const basic = basicRefundInfo.value
  if (basic?.applyMoney !== null && basic?.applyMoney !== undefined) return basic.applyMoney
  return summary.value?.refundFee || null
})

const displayReason = computed(() => {
  const basic = basicRefundInfo.value
  if (basic?.reasonText) return basic.reasonText
  return summary.value?.refundReason || ''
})

const displayGmtCreated = computed(() => {
  const basic = basicRefundInfo.value
  if (basic?.gmtCreatedTime) return basic.gmtCreatedTime
  return summary.value?.refundCreateTime || null
})

const displayDisputeEnd = computed(() => {
  const basic = basicRefundInfo.value
  return basic?.disputeEndTime || null
})

const displayCsStatus = computed(() => {
  const basic = basicRefundInfo.value
  if (basic?.csStatusDesc) return basic.csStatusDesc
  if (basic?.csStatus) return basic.csStatus
  return ''
})

const statusCardVisible = computed(() => {
  return !routeError.value && (summary.value || refundDetailData.value)
})

// 三接口分别的数据
const serviceRecordData = computed(() => detail.value?.serviceRecord?.data || null)
const fullInfoData = computed(() => detail.value?.fullInfo?.data || null)
const refundDetailData = computed(() => detail.value?.refundDetail?.data || null)

const basicRefundInfo = computed(() => refundDetailData.value?.components?.basicRefundInfo || null)
const nodeStatusInfo = computed(() => refundDetailData.value?.components?.nodeStatusInfo || null)
const progressDetail = computed(() => refundDetailData.value?.components?.progressDetail || null)
const refundDescribe = computed(() => refundDetailData.value?.components?.refundDescribe || null)
const bottomBarButtons = computed(() => refundDetailData.value?.components?.bottomBar || [])

// 物流：明确区分卖家发货 vs 买家退货
const sellerLogistics = computed(() => {
  // 卖家发货物流：优先 tradeLogisticInfo，回退 summary 中的物流（来自列表 commonData）
  const tradeLog = basicRefundInfo.value?.tradeLogisticInfo
  if (tradeLog && (tradeLog.companyName || tradeLog.mailNo)) {
    return tradeLog
  }
  return {
    companyName: summary.value?.logisticsCompany || null,
    mailNo: summary.value?.logisticsMailNo || null,
    consignTime: summary.value?.consignTime || null,
  }
})

const buyerReturnLogistics = computed(() => {
  // 买家退货物流：仅来自 basicRefundInfo.buyerReturnLogisticInfo
  return basicRefundInfo.value?.buyerReturnLogisticInfo || { companyName: null, mailNo: null, consignTime: null }
})

const anyLogistics = computed(() => {
  return !!(
    sellerLogistics.value.companyName ||
    sellerLogistics.value.mailNo ||
    buyerReturnLogistics.value.companyName ||
    buyerReturnLogistics.value.mailNo ||
    summary.value?.logisticsCompany
  )
})

// 所有凭证图片（来自 refundProof + progressNodeList.proofInfoList）
const allProofs = computed(() => {
  const result = []
  const proof = basicRefundInfo.value?.refundProof?.proofMultiMediaList
  if (Array.isArray(proof)) {
    result.push(...proof.filter(p => p && p.url))
  }
  const progress = progressDetail.value?.progressNodeList || []
  for (const node of progress) {
    if (Array.isArray(node.proofInfoList)) {
      result.push(...node.proofInfoList.filter(p => p && p.url))
    }
  }
  return result
})

// 错误码 → 友好提示映射（脱敏，不暴露 ret / Cookie / sign）
const ERROR_CODE_FRIENDLY_TEXT = {
  AUTH_EXPIRED: '登录状态失效，请刷新账号 Cookie 后重试',
  NETWORK_TIMEOUT: '网络请求超时，请稍后重试',
  NETWORK_ERROR: '网络请求失败，请稍后重试',
  MTOP_RET_FAILURE: '闲鱼接口返回失败，可能是账号权限不足或风控拦截',
  INVALID_RESPONSE_SHAPE: '服务端返回的数据结构异常',
  ID_CONSISTENCY_ERROR: '退款与账号不匹配或订单不存在',
  ACCOUNT_MISMATCH: '退款与账号不匹配',
  REFUND_NOT_FOUND: '退款记录不存在',
  EMPTY_CREDENTIAL: '账号 Cookie 或签名 token 为空',
  UNKNOWN_ERROR: '未知错误，请稍后重试',
}

function friendlyErrorText(block) {
  if (!block) return ''
  const code = block.errorCode
  if (code && ERROR_CODE_FRIENDLY_TEXT[code]) {
    return ERROR_CODE_FRIENDLY_TEXT[code]
  }
  // 兜底：使用后端 error，但截断过长文本
  const raw = String(block.error || '')
  return raw.length > 80 ? raw.slice(0, 80) + '…' : raw
}

// 三接口状态指示器
const apiStatusList = computed(() => {
  const list = [
    { key: 'service_record', label: '退款服务记录', stateText: '未请求' },
    { key: 'full_info', label: '完整订单信息', stateText: '未请求' },
    { key: 'refund_detail', label: '退款核心详情', stateText: '未请求' },
  ]
  if (!detail.value) return list
  const mapping = {
    service_record: 'serviceRecord',
    full_info: 'fullInfo',
    refund_detail: 'refundDetail',
  }
  return list.map(item => {
    const block = detail.value[mapping[item.key]] || {}
    const status = block.status || 'skipped'
    let stateText = '未请求'
    if (status === 'ok') stateText = '已加载'
    else if (status === 'failed') stateText = friendlyErrorText(block)
    else if (status === 'skipped') stateText = '未请求'
    return {
      ...item,
      status,
      stateText,
      retrying: !!retryingMap[item.key],
    }
  })
})

const allFailedNoCache = computed(() => {
  if (!detail.value) return false
  if (cachedFlag.value) return false  // 有缓存就不显示"全部失败"
  const all = ['serviceRecord', 'fullInfo', 'refundDetail']
  return all.every(k => detail.value[k]?.status === 'failed')
})

const allFailedError = computed(() => {
  if (!detail.value) return ''
  const errors = []
  if (detail.value.serviceRecord?.status === 'failed') errors.push(`服务记录：${friendlyErrorText(detail.value.serviceRecord)}`)
  if (detail.value.fullInfo?.status === 'failed') errors.push(`订单信息：${friendlyErrorText(detail.value.fullInfo)}`)
  if (detail.value.refundDetail?.status === 'failed') errors.push(`退款详情：${friendlyErrorText(detail.value.refundDetail)}`)
  return errors.join('；')
})

// ============================================================
// 工具方法
// ============================================================
function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '—'
  const s = String(value).trim()
  if (!s) return '—'
  const cleaned = s.replace(/[^0-9.-]/g, '')
  if (!cleaned || cleaned === '-' || cleaned === '.') return String(value)
  const num = Number(cleaned)
  if (!Number.isFinite(num)) return String(value)
  return `¥${num.toFixed(2)}`
}

function formatTime(value) {
  if (!value) return ''
  if (typeof value === 'number') {
    const d = new Date(value)
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('zh-CN', { hour12: false })
  }
  return String(value).replace('T', ' ').replace(/\.\d+$/, '')
}

function buildSafeStyle(styleObj) {
  if (!styleObj || typeof styleObj !== 'object') return {}
  // 仅允许有限安全样式（与后端 _SAFE_STYLE_PROPERTIES 一致）
  const allowed = ['color', 'fontSize', 'fontWeight', 'lineHeight', 'marginTop', 'marginBottom', 'textAlign']
  const result = {}
  for (const key of Object.keys(styleObj)) {
    const camelKey = key.replace(/-([a-z])/g, (_, c) => c.toUpperCase())
    if (allowed.includes(camelKey)) {
      result[camelKey] = styleObj[key]
    }
  }
  return result
}

function onImageError(event) {
  if (event?.target) event.target.style.display = 'none'
}

function openImagePreview(url) {
  if (!url) return
  previewImageUrl.value = url
}

function closeImagePreview() {
  previewImageUrl.value = ''
}

// ============================================================
// 加载详情
// ============================================================
async function loadDetail(forceRefresh = false) {
  if (routeError.value) return
  if (forceRefresh) {
    refreshing.value = true
  } else {
    loading.value = true
  }
  globalError.value = ''
  try {
    const params = {
      accountId: routeAccountId.value,
      orderId: routeOrderId.value,
      refundId: routeRefundId.value,
    }
    const res = forceRefresh
      ? await refreshRefundDetail(params)
      : await getRefundDetail(params)
    const data = res?.data || {}
    if (data.ok === false) {
      globalError.value = data.error || '查询失败'
      // 仍尝试展示已有 summary
      if (data.summary) summary.value = data.summary
      return
    }
    summary.value = data.summary || null
    if (data.detail) {
      detail.value = data.detail
      cachedFlag.value = !!data.cached
      cacheExpiredFlag.value = !!data.cacheExpired
    }
  } catch (err) {
    globalError.value = err?.message || '查询退款详情失败'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

// 手动刷新全部三接口
async function onRefreshAll() {
  if (refreshing.value) return
  await loadDetail(true)
}

// 单独重试某个失败接口
async function onRetryApi(apiKey) {
  if (retryingMap[apiKey]) return
  retryingMap[apiKey] = true
  try {
    const res = await retryRefundDetailApi({
      accountId: routeAccountId.value,
      orderId: routeOrderId.value,
      refundId: routeRefundId.value,
      api: apiKey,
    })
    const data = res?.data || {}
    if (data.ok === false) {
      window.dispatchEvent(new CustomEvent('xya-toast', {
        detail: { message: data.error || '重试失败', isError: true },
      }))
      return
    }
    if (data.detail) {
      detail.value = data.detail
    }
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: '重试成功', type: 'success' },
    }))
  } catch (err) {
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: err?.message || '重试失败', isError: true },
    }))
  } finally {
    retryingMap[apiKey] = false
  }
}

// ============================================================
// 操作：我要维权
// ============================================================
function onApplyDispute(btn) {
  const url = btn?.clickEvent?.data?.url
  if (!url) {
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: '该退款记录未返回有效的维权链接', isError: true },
    }))
    return
  }
  // URL 已由后端做过白名单校验，但前端再检查一次
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error('协议不安全')
    }
  } catch {
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: '链接不安全，已拒绝打开', isError: true },
    }))
    return
  }
  try {
    const opened = window.open(url, '_blank', 'noopener,noreferrer')
    if (!opened) {
      window.dispatchEvent(new CustomEvent('xya-toast', {
        detail: { message: '浏览器拦截了新窗口，请允许弹窗后重试' },
      }))
    } else {
      try { opened.opener = null } catch { /* noopener already isolates */ }
    }
  } catch {
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: '链接打开失败', isError: true },
    }))
  }
}

// ============================================================
// 操作：同意退款
// ============================================================
async function onAgreeRefund(btn) {
  if (agreeing.value) return
  const doubleCheck = btn?.clickEvent?.data || {}
  agreeModal.refundId = routeRefundId.value
  agreeModal.accountId = routeAccountId.value
  agreeModal.accountLabel = accountLabel.value
  agreeModal.itemTitle = summary.value?.itemTitle || ''
  agreeModal.refundFee = displayApplyMoney.value ? String(displayApplyMoney.value) : ''
  agreeModal.riskDesc = doubleCheck.riskDesc || '同意退款后可能立即退款给买家，此操作不可撤销。'
  agreeModal.confirmText = doubleCheck.confirmText || ''
  agreeModal.title = doubleCheck.title || '确认同意退款'
  agreeModal.submitButtonText = doubleCheck.confirmButtonText || '确认同意退款'
  agreeModal.submitting = false
  agreeModal.visible = true
}

async function confirmAgreeRefund() {
  if (agreeModal.submitting) return
  if (!agreeModal.refundId || !agreeModal.accountId) {
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: '参数缺失，无法同意退款', isError: true },
    }))
    closeAgreeModal()
    return
  }

  agreeModal.submitting = true
  agreeing.value = true

  try {
    const res = await agreeRefund(agreeModal.refundId, { accountId: Number(agreeModal.accountId) })
    const data = res?.data || {}
    if (data.ok === false) {
      window.dispatchEvent(new CustomEvent('xya-toast', {
        detail: { message: data.error || '同意退款失败', isError: true },
      }))
    } else {
      window.dispatchEvent(new CustomEvent('xya-toast', {
        detail: { message: data.message || '同意退款请求已提交', type: 'success' },
      }))
      closeAgreeModal()
      // 写操作成功后：刷新当前退款详情（不刷新全部账号）
      // 失效缓存由后端处理（invalidate_refund_detail_cache_after_write）
      await loadDetail(true)
    }
  } catch (err) {
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: err?.message || '同意退款失败', isError: true },
    }))
  } finally {
    agreeModal.submitting = false
    agreeing.value = false
  }
}

function closeAgreeModal() {
  if (agreeModal.submitting) return
  agreeModal.visible = false
}

// ============================================================
// 返回列表（恢复筛选状态）
// ============================================================
function onBackToList() {
  // 消费保存的列表状态（让 RefundsPage 在 onMounted 时恢复）
  // 注意：consumeRefundListState 会清除状态，所以即使 RefundsPage 未挂载也会丢失
  // 因此这里仅触发导航，状态由 RefundsPage 自己在 onMounted 时消费
  emit('navigate', 'refunds')
}

// ============================================================
// 生命周期
// ============================================================
onMounted(async () => {
  parseRouteParams()
  if (routeError.value) {
    loading.value = false
    return
  }
  await loadDetail(false)
})
</script>

<style scoped>
.refund-detail-page {
  padding: 20px 24px 32px;
  width: 100%;
  color: #1f2937;
  box-sizing: border-box;
}

/* ============ 顶部导航条 ============ */
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
  padding: 14px 18px;
  background: linear-gradient(135deg, #ffffff 0%, #f8faff 100%);
  border: 1px solid #e5e9f2;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(16, 24, 40, 0.04);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.header-title-group {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid #d0d7e6;
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  color: #3b6fd4;
  font-size: 13px;
  transition: all 0.15s ease;
}
.back-btn:hover {
  background: #eef3ff;
  border-color: #3b6fd4;
  transform: translateX(-1px);
}
.back-icon { font-size: 16px; font-weight: 600; }
.detail-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  letter-spacing: 0.2px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.last-refresh {
  font-size: 12px;
  color: #6b7280;
}
.btn-refresh .refresh-icon {
  display: inline-block;
  margin-right: 4px;
}

/* ============ 状态卡 ============ */
.status-card {
  background: linear-gradient(135deg, #f5f9ff 0%, #eef4ff 100%);
  border: 1px solid #d4e1fb;
  border-radius: 14px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(59, 111, 212, 0.06);
}
.status-card-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px 24px;
  margin-bottom: 14px;
}
.status-card-row:last-child { margin-bottom: 0; }
.status-card-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.status-card-item .label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
  letter-spacing: 0.3px;
}
.status-card-item .value {
  font-size: 14px;
  color: #111827;
  font-weight: 500;
  word-break: break-all;
  line-height: 1.5;
}
.status-card-item .value.money {
  color: #d97706;
  font-weight: 700;
  font-size: 17px;
}
.status-card-item .value.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12.5px;
  color: #4b5563;
}
.status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: #eef2f7;
  color: #475467;
  width: fit-content;
}
.status-badge.green { background: #d1fadf; color: #079455; }
.status-badge.red { background: #fee4e2; color: #d92d20; }
.status-badge.orange { background: #fef0c7; color: #dc6803; }
.status-badge.blue { background: #dbeafe; color: #1d4ed8; }

/* ============ 三接口状态指示器 ============ */
.api-status-bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
.api-status-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e5e9f2;
  font-size: 13px;
  min-width: 0;
}
.api-status-item.status-ok {
  background: #ecfdf3;
  border-color: #abefc6;
  color: #079455;
}
.api-status-item.status-failed {
  background: #fef3f2;
  border-color: #fda29b;
  color: #d92d20;
}
.api-status-item.status-skipped {
  background: #f1f5f9;
  border-color: #e2e8f0;
  color: #64748b;
}
.api-name { font-weight: 600; flex-shrink: 0; }
.api-state {
  color: inherit;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.retry-btn {
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity 0.15s;
}
.retry-btn:hover:not(:disabled) { opacity: 0.85; }
.retry-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* ============ 详情卡 ============ */
.detail-card {
  background: #fff;
  border: 1px solid #e5e9f2;
  border-radius: 12px;
  padding: 18px 22px;
  margin-bottom: 14px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.detail-card:hover {
  border-color: #d4ddea;
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.06);
}
.card-title {
  margin: 0 0 14px;
  font-size: 15px;
  font-weight: 700;
  color: #111827;
  border-left: 3px solid #3b6fd4;
  padding-left: 10px;
  letter-spacing: 0.3px;
}
.card-subtitle {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #475467;
  padding-left: 2px;
}
.card-empty {
  color: #9ca3af;
  font-size: 13px;
  padding: 14px 0;
  text-align: center;
}
.postage-empty {
  color: #9ca3af;
  font-size: 12px;
  margin-top: 8px;
  padding: 6px 0;
}

/* ============ 阶段节点 ============ */
.node-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.node-item {
  display: flex;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px dashed #eef2f7;
}
.node-item:last-child { border-bottom: none; }
.node-time {
  flex: 0 0 160px;
  color: #6b7280;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.node-text {
  flex: 1;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.5;
  min-width: 0;
}

/* ============ 信息网格 ============ */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px 20px;
  margin: 0;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #eef2f7;
}
.info-item dt {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}
.info-item dd {
  margin: 0;
  font-size: 14px;
  color: #111827;
  word-break: break-all;
  line-height: 1.5;
}
.info-item dd.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  color: #4b5563;
}
.info-item.highlight {
  background: linear-gradient(135deg, #fff7e6 0%, #ffefcf 100%);
  border-color: #ffd99c;
}
.info-item.highlight dd {
  color: #d97706;
  font-weight: 700;
  font-size: 16px;
}

/* ============ 退款进度 ============ */
.progress-list {
  list-style: none;
  padding: 0;
  margin: 0;
  position: relative;
}
.progress-list::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 12px;
  bottom: 12px;
  width: 2px;
  background: linear-gradient(to bottom, #3b6fd4 0%, #e5e9f2 100%);
}
.progress-item {
  position: relative;
  padding: 10px 0 10px 28px;
  border-bottom: none;
}
.progress-item:last-child { padding-bottom: 0; }
.progress-item::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 14px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #3b6fd4;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #3b6fd4;
}
.progress-head {
  display: flex;
  gap: 14px;
  align-items: baseline;
  flex-wrap: wrap;
}
.progress-time {
  flex: 0 0 160px;
  color: #6b7280;
  font-size: 12.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.progress-text {
  flex: 1;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.5;
  min-width: 0;
}
.progress-tips {
  margin: 6px 0 0 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
  padding: 6px 10px;
  background: #f8fafc;
  border-left: 2px solid #cbd5e1;
  border-radius: 4px;
}
.progress-proofs {
  margin: 8px 0 0 0;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* ============ 退款历史表 ============ */
.record-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
  margin-top: 8px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e9f2;
}
.record-table th,
.record-table td {
  border-bottom: 1px solid #eef2f7;
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
}
.record-table tr:last-child td { border-bottom: none; }
.record-table th {
  background: #f6f9ff;
  color: #475467;
  font-weight: 600;
  font-size: 12.5px;
  letter-spacing: 0.2px;
}
.record-table tbody tr:hover { background: #f9fbff; }
.record-table tr.current-refund {
  background: linear-gradient(90deg, #fff8e6 0%, #fffcf0 100%);
}
.record-table tr.current-refund:hover {
  background: linear-gradient(90deg, #fff3d6 0%, #fffae6 100%);
}
.current-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 2px 8px;
  background: #d97706;
  color: #fff;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

/* ============ 商品信息 ============ */
.item-block {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 14px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #eef2f7;
}
.item-pic {
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #e5e9f2;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.15s;
}
.item-pic:hover { transform: scale(1.03); }
.item-meta { flex: 1; min-width: 0; }
.item-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
  line-height: 1.5;
}
.item-spec { font-size: 13px; color: #6b7280; line-height: 1.5; }

/* ============ 时间线 ============ */
.timeline-list {
  list-style: none;
  padding: 0;
  margin: 0;
  position: relative;
}
.timeline-list::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: linear-gradient(to bottom, #079455 0%, #e5e9f2 100%);
}
.timeline-item {
  position: relative;
  padding: 6px 0 16px 26px;
}
.timeline-item:last-child { padding-bottom: 0; }
.timeline-dot {
  position: absolute;
  left: 0;
  top: 8px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #e5e9f2;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px #e5e9f2;
  transition: all 0.2s;
}
.timeline-dot.done {
  background: #079455;
  box-shadow: 0 0 0 2px #b6e8c8;
}
.timeline-content { padding-left: 6px; }
.timeline-title {
  font-size: 14px;
  color: #111827;
  font-weight: 500;
  line-height: 1.5;
}
.timeline-time {
  font-size: 12px;
  color: #6b7280;
  margin-top: 3px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* ============ 物流 ============ */
.logistics-block {
  margin-bottom: 14px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #eef2f7;
}
.logistics-block:last-child { margin-bottom: 0; }
.logistics-block .info-item { background: #fff; }
.logistics-block .card-subtitle { margin-top: 0; }

/* ============ 富文本 ============ */
.rich-text-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rich-text-item {
  font-size: 14px;
  line-height: 1.7;
  color: #1f2937;
}
.rich-text-link {
  margin-left: 8px;
  color: #1d4ed8;
  text-decoration: underline;
  font-size: 13px;
}

/* ============ 凭证 ============ */
.proof-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 12px;
}
.proof-thumb {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #e5e9f2;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  background: #f8fafc;
}
.proof-thumb:hover {
  transform: scale(1.04);
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.12);
}

/* ============ 操作 ============ */
.actions-card {
  background: linear-gradient(135deg, #fffaf0 0%, #fff5e6 100%);
  border-color: #ffe1b0;
}
.actions-card .actions-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.action-btn {
  padding: 8px 18px;
  border: 1px solid #d0d7e6;
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #475467;
  transition: all 0.15s ease;
  font-weight: 500;
}
.action-btn:hover:not(:disabled) {
  border-color: #3b6fd4;
  color: #3b6fd4;
}
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.action-btn.op-primary {
  background: #3b6fd4;
  color: #fff;
  border-color: #3b6fd4;
}
.action-btn.op-primary:hover:not(:disabled) {
  background: #2a5bbf;
  border-color: #2a5bbf;
  color: #fff;
}
.action-btn.op-warn {
  background: #fff5e6;
  color: #d97706;
  border-color: #ffe1b0;
}
.action-btn.op-warn:hover:not(:disabled) {
  background: #ffe9c4;
  border-color: #ffc966;
  color: #b35d00;
}
.amount-tip {
  margin: 12px 0 0;
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.6;
  padding-left: 2px;
}

/* ============ 同意退款弹窗 ============ */
.refund-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}
.refund-modal {
  background: #fff;
  border-radius: 14px;
  width: 440px;
  max-width: 92vw;
  max-height: 92vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}
.refund-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #eef2f7;
}
.refund-modal-head h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
  font-weight: 700;
}
.refund-modal-close {
  background: transparent;
  border: none;
  font-size: 24px;
  color: #9ca3af;
  cursor: pointer;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.refund-modal-close:hover { background: #f1f5f9; color: #4b5563; }
.refund-modal-body {
  padding: 18px 20px;
  flex: 1;
  overflow-y: auto;
}
.modal-confirm-text {
  margin: 0 0 10px;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.6;
}
.modal-risk {
  margin: 0 0 14px;
  color: #d92d20;
  font-size: 13px;
  background: #fee4e2;
  padding: 10px 12px;
  border-radius: 8px;
  line-height: 1.6;
  border: 1px solid #fda29b;
}
.modal-info {
  background: #f6f9ff;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 13px;
  color: #475467;
  line-height: 1.9;
  border: 1px solid #e5e9f2;
}
.refund-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #eef2f7;
}

/* ============ 图片预览 ============ */
.image-preview {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}
.image-preview img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}
.image-preview-close {
  position: absolute;
  top: -40px;
  right: 0;
  background: #fff;
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 18px;
  cursor: pointer;
  color: #111827;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}
.image-preview-close:hover { background: #f1f5f9; }

/* ============ 响应式适配 ============ */
@media (max-width: 1280px) {
  .refund-detail-page { padding: 16px 18px 28px; }
}
@media (max-width: 1024px) {
  .status-card-row { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
  .info-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
}
@media (max-width: 768px) {
  .refund-detail-page { padding: 12px 12px 24px; }
  .detail-header {
    padding: 12px 14px;
    gap: 10px;
  }
  .header-left { gap: 10px; }
  .detail-title { font-size: 18px; }
  .status-card { padding: 16px 16px; }
  .status-card-row { grid-template-columns: 1fr; gap: 12px; }
  .info-grid { grid-template-columns: 1fr; gap: 10px; }
  .api-status-bar { grid-template-columns: 1fr; }
  .progress-head { flex-direction: column; gap: 4px; }
  .progress-time { flex: none; }
  .record-table { font-size: 12px; }
  .record-table th, .record-table td { padding: 8px 8px; }
  .detail-card { padding: 14px 14px; }
  .proof-grid { grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); }
}
@media (max-width: 480px) {
  .detail-header {
    flex-direction: column;
    align-items: stretch;
  }
  .header-actions { justify-content: flex-end; }
  .back-btn { width: fit-content; }
}
</style>
