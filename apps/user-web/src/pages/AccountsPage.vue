<template>
  <div class="grid wide-right" v-bind="$attrs">
    <div>
      <div class="alert-line">账号数据已接入后端：账号列表、手动添加、删除、刷新资料、WebSocket 状态和扫码登录均调用真实接口。</div>
      <div v-if="error" class="global-notice error">{{ error }}</div>
      <div v-if="accountsLoadError" class="global-notice error">账号列表加载失败：{{ accountsLoadError }}</div>
      <div v-if="qrSuccessMsg" class="global-notice success">{{ qrSuccessMsg }}</div>
      <!-- 滑块求解状态说明：常驻展示，告知用户各状态含义与对应处理方式 -->
      <div class="solve-info-card">
        <div class="solve-info-head">
          <span class="solve-info-title">滑块求解说明</span>
          <span class="solve-info-sub">每个账号每分钟仅可主动求解 1 次，失败后可立即点击"重试求解"</span>
        </div>
        <div class="solve-info-grid">
          <div class="solve-info-item">
            <span class="solve-info-dot dot-red"></span>
            <div>
              <strong>Cookie 失效</strong>
              <p>账号登录态已过期或被闲鱼平台拒绝，滑块求解无法恢复，需点击"重新扫码"登录获取新 Cookie。</p>
            </div>
          </div>
          <div class="solve-info-item">
            <span class="solve-info-dot dot-orange"></span>
            <div>
              <strong>滑块求解失败</strong>
              <p>系统已尝试自动拖动滑块但未通过，可点击"重试求解"再次尝试；多次失败建议手动完成验证。</p>
            </div>
          </div>
          <div class="solve-info-item">
            <span class="solve-info-dot dot-red"></span>
            <div>
              <strong>触发人机验证</strong>
              <p>闲鱼平台监测到自动化访问行为后，会要求用户完成滑块验证以证明自身为人类（即"人机验证"）。系统会自动尝试通过浏览器模拟滑动求解，若持续失败建议手动在闲鱼 APP 中完成验证。</p>
            </div>
          </div>
          <div class="solve-info-item">
            <span class="solve-info-dot dot-purple"></span>
            <div>
              <strong>WS Token 获取失败</strong>
              <p>在线消息页面遇到滑块验证时系统会自动求解；若自动失败，WS 连接将断开，可在本页重试求解后重连 WS。</p>
            </div>
          </div>
          <div class="solve-info-item">
            <span class="solve-info-dot dot-blue"></span>
            <div>
              <strong>服务暂时不可用</strong>
              <p>滑块求解服务（crawler-service）繁忙或不可达，可稍后点击重试；持续失败请联系管理员。</p>
            </div>
          </div>
          <div class="solve-info-item">
            <span class="solve-info-dot dot-gray"></span>
            <div>
              <strong>账号不活跃 / 已禁用</strong>
              <p>账号超过 3 天未操作或已被禁用，滑块求解已被暂停，请先手动连接账号或联系管理员启用。</p>
            </div>
          </div>
          <div class="solve-info-item">
            <span class="solve-info-dot dot-green"></span>
            <div>
              <strong>求解成功</strong>
              <p>滑块已通过且 Cookie 二次验证有效，可重新启动 WebSocket 连接恢复在线消息。</p>
            </div>
          </div>
        </div>
      </div>
      <div class="grid stat-grid" style="grid-template-columns:repeat(5,1fr)">
        <StatCard title="账号总数" :value="accountMetric(stats.total)" change="本页统计" icon="users" />
        <StatCard title="正常账号" :value="accountMetric(stats.normal)" change="本页统计" icon="account" color="green" />
        <StatCard title="需验证" :value="accountMetric(stats.verify)" change="本页统计" icon="shield" color="orange" />
        <StatCard title="WS在线" :value="accountMetric(stats.wsOnline)" change="本页统计" icon="link" color="purple" />
        <StatCard title="Cookie异常" :value="accountMetric(stats.cookieWarn)" change="本页统计" icon="opportunity" color="orange" />
      </div>
      <!-- 滑块求解状态提示横幅：在统计卡片下方集中展示求解进度/结果/下一步操作 -->
      <div v-if="captchaAlerts.length" class="captcha-alert-list">
        <div v-for="alert in captchaAlerts" :key="alert.accountId" :class="['captcha-alert-banner', alert.type]">
          <div class="captcha-alert-main">
            <div class="captcha-alert-head">
              <strong>{{ alert.accountName || `账号 ${alert.accountId}` }}</strong>
              <span :class="['captcha-alert-tag', alert.type]">{{ alert.statusText }}</span>
            </div>
            <div class="captcha-alert-reason">{{ alert.reason }}</div>
            <div v-if="alert.nextAction" class="captcha-alert-next">下一步：{{ alert.nextAction }}</div>
          </div>
          <button v-if="alert.canRetry" class="captcha-alert-retry" :disabled="alert.type === 'solving'" @click="handleManualSolve(alert.accountId)">
            {{ alert.type === 'solving' ? '求解中...' : '重试求解' }}
          </button>
        </div>
      </div>
      <div class="toolbar">
        <input v-model="keyword" class="input large" :disabled="!accountsAvailable" placeholder="搜索昵称 / UID / 备注" @keyup.enter="loadAccounts">
        <select v-model="statusFilter" class="input" style="max-width:150px" :disabled="!accountsAvailable">
          <option value="all">全部状态</option>
          <option value="normal">正常</option>
          <option value="verify">需验证</option>
          <option value="cookieWarn">Cookie异常</option>
          <option value="wsOnline">WS在线</option>
        </select>
        <AppButton :disabled="loading" @click="loadAccounts">{{ loading ? '加载中...' : (accountsAvailable ? '刷新' : '重试') }}</AppButton>
      </div>
      <CardPanel>
        <EmptyState v-if="!accountsAvailable" icon="⚠" title="账号列表不可用" :description="accountsLoadError || '正在加载账号列表，请稍候。'" />
        <BaseTable v-else :columns="cols" :rows="rows" :row-class="rowClass">
          <template #account="{ row }"><div class="product-cell" style="cursor:pointer" @click="selectAccount(row.raw)"><img v-if="row.avatar" :src="row.avatar" class="avatar small" alt="" loading="lazy" @error="onListAvatarError"><div v-else class="avatar small avatar-img"></div><div><strong>{{ row.name }}</strong><em>{{ row.tag }}</em></div></div></template>
          <template #status="{ row }">
            <div class="status-cell">
              <Badge :type="row.statusType">{{ row.statusText }}</Badge>
            </div>
          </template>
          <template #health="{ row }"><Badge>{{ row.health != null ? row.health + '分' : '—' }}</Badge></template>
          <template #cookie="{ row }"><Badge :type="row.cookieType">{{ row.cookie }}</Badge></template>
          <template #ws="{ row }"><span><i :class="['dot', row.wsState === true ? '' : row.wsState === false ? 'red' : 'gray']"></i>{{ row.ws }}</span></template>
          <template #op="{ row }">
            <button class="link" @click="refreshProfile(row.raw.id)">刷新资料</button>
            <button class="link" @click="openRescanModal(row.raw)">重新扫码</button>
            <button class="link solve-op-btn" :class="solveOpBtnClass(row.raw.id)" :title="solveOpBtnTitle(row.raw.id)" :disabled="solveOpBtnDisabled(row.raw.id)" @click="handleManualSolve(row.raw.id)">{{ solveOpBtnText(row.raw.id) }}</button>
            <button class="link" :disabled="polishingAccountId === row.raw.id" @click="handleItemPolish(row.raw)">{{ polishingAccountId === row.raw.id ? '擦亮中...' : '一键擦亮' }}</button>
            <button class="link" :disabled="isWsBusy(row.raw.id)" @click="toggleWs(row.raw)">{{ isWsBusy(row.raw.id) ? '处理中...' : wsActionText(row.wsState) }}</button>
            <button class="link danger-text" @click="removeAccount(row.raw.id)">删除</button>
          </template>
        </BaseTable>
        <Pagination v-if="accountsAvailable" :total="total" :current="current" :page-size="pageSize" @page-change="goPage" />
      </CardPanel>
    </div>
    <div class="right-drawer">
      <aside class="right-drawer account-detail-drawer">
  <div class="detail-title-row">
    <h3>账号详情</h3>
    <button
      class="detail-close"
      type="button"
      aria-label="关闭账号详情"
      @click="closeDetail"
    >
      ×
    </button>
  </div>

  <template v-if="accountsAvailable && selected">
    <!-- 账号基础信息 -->
    <section class="account-summary">
      <img
        v-if="selectedAvatarUrl"
        :src="selectedAvatarUrl"
        class="detail-avatar"
        alt=""
        @error="onDetailAvatarError"
      >
      <div v-else class="detail-avatar avatar-fallback"></div>

      <div class="account-summary-main">
        <div class="account-name-row">
          <strong>{{ accountTitle(selected) }}</strong>
          <span
            v-if="isCurrentAccount(selected)"
            class="current-account-tag"
          >
            当前账号
          </span>
        </div>

        <div class="account-meta-line">
          UID：{{ selected.externalUid || selected.unb || selected.id || '-' }}
        </div>

        <div class="account-meta-line account-meta-split">
          <span>地区：{{ selected.province && selected.city ? `${selected.province} ${selected.city}` : (selected.ipLocation || selected.province || '-') }}</span>
          <i></i>
          <span>注册时间：{{ accountRegisterDate(selected) }}</span>
        </div>
      </div>

      <span :class="['online-state', { offline: selectedWsState === false, unknown: selectedWsState === null }]">
        <i></i>
        {{ selectedWsState === true ? '在线' : selectedWsState === false ? '离线' : '状态未知' }}
      </span>
    </section>

    <!-- Cookie 状态警告 -->
    <div v-if="selected && selectedAuthDisplay.cookieStatus === 0" class="cookie-warn-banner">
      <Icon name="help" />
      <span>{{ accountLoginHint(selected, selectedWs) }}</span>
    </div>
    <div v-else-if="selected && selectedAuthDisplay.cookieStatus === 2" class="cookie-warn-banner cookie-expired">
      <Icon name="help" />
      <span>{{ accountLoginHint(selected, selectedWs) }}</span>
    </div>

    <section class="drawer-section diagnosis-card">
      <h4>连接诊断</h4>
      <div v-for="item in accountDiagnostics" :key="item.title" class="diagnosis-item" :class="item.level">
        <span><i></i>{{ item.title }}</span>
        <b>{{ item.text }}</b>
        <small>{{ item.tip }}</small>
      </div>
      <div class="diagnosis-actions">
        <button type="button" class="link" @click="refreshProfile(selected.id)">刷新资料</button>
        <button type="button" class="link" @click="openCookieEdit(selected)">更新 Cookie</button>
        <button type="button" class="link" @click="openRescanModal(selected)">重新扫码</button>
        <button type="button" class="link" @click="toggleWs(selected)">{{ wsActionText(selectedWsState) }}</button>
      </div>
    </section>

    <!-- 闲鱼主页资料（刷新资料后展示） -->
    <section v-if="selected.displayName || selected.followers != null || selected.soldCount != null" class="profile-stats-card">
      <h4>闲鱼主页资料</h4>

      <div v-if="selected.introduction" class="profile-intro">
        <span class="profile-intro-label">简介</span>
        <p>{{ selected.introduction }}</p>
      </div>

      <div class="profile-stats-grid">
        <div v-if="selected.followers != null" class="profile-stat-item">
          <b>{{ fmtNumber(selected.followers) }}</b>
          <span>粉丝</span>
        </div>
        <div v-if="selected.following != null" class="profile-stat-item">
          <b>{{ fmtNumber(selected.following) }}</b>
          <span>关注</span>
        </div>
        <div v-if="selected.soldCount != null" class="profile-stat-item">
          <b>{{ fmtNumber(selected.soldCount) }}</b>
          <span>已售</span>
        </div>
        <div v-if="selected.reviewNum != null" class="profile-stat-item">
          <b>{{ fmtNumber(selected.reviewNum) }}</b>
          <span>评价</span>
        </div>
      </div>

      <div class="profile-extra">
        <div v-if="selected.sellerLevel" class="profile-extra-item">
          <span>卖家等级</span>
          <b>{{ selected.sellerLevel }}</b>
        </div>
        <div v-if="selected.praiseRatio" class="profile-extra-item">
          <span>好评率</span>
          <b>{{ selected.praiseRatio }}</b>
        </div>
        <div v-if="selected.fishShopScore != null" class="profile-extra-item">
          <span>鱼小铺分数</span>
          <b>{{ selected.fishShopScore }}</b>
        </div>
        <div v-if="selected.fishShopUser" class="profile-extra-item">
          <span>鱼小铺</span>
          <b class="green-tag">已开通</b>
        </div>
      </div>
    </section>

    <!-- 账号健康 -->
    <template v-if="false">
    <section class="health-card">
      <h4>账号健康</h4>

      <div class="health-content">
        <div class="health-ring-wrap">
          <div class="health-ring" :style="healthRingStyle">
            <div class="health-ring-inner">
              <strong>
                {{ accountHealth(selected) ?? '—' }}<small v-if="accountHealth(selected)">分</small>
              </strong>
              <span>健康分接口开发中</span>
            </div>
          </div>
        </div>

        <div class="health-metrics">
          <div>
            <span><i></i>账号安全</span>
            <b>{{ metricScore(selected, 'securityScore') ?? '—' }}<span v-if="metricScore(selected, 'securityScore')">分</span></b>
          </div>
          <div>
            <span><i></i>活跃度</span>
            <b>{{ metricScore(selected, 'activityScore') ?? '—' }}<span v-if="metricScore(selected, 'activityScore')">分</span></b>
          </div>
          <div>
            <span><i></i>交易表现</span>
            <b>{{ metricScore(selected, 'tradeScore') ?? '—' }}<span v-if="metricScore(selected, 'tradeScore')">分</span></b>
          </div>
          <div>
            <span><i></i>合规状态</span>
            <b>{{ metricScore(selected, 'complianceScore') ?? '—' }}<span v-if="metricScore(selected, 'complianceScore')">分</span></b>
          </div>
        </div>
      </div>

      <div class="health-footer">
        <span>
          更新时间：
          {{ displayDateTime(selected.profileUpdatedTime || selected.updatedTime) }}
        </span>

        <button
          class="text-action"
          type="button"
          disabled
          title="健康分接口开发中"
          style="cursor:not-allowed;opacity:.6"
        >
          查看详情 <b>›</b>
        </button>
      </div>
    </section>

    <!-- 最近活动 -->
    <section class="drawer-section activity-section">
      <h4>最近活动</h4>

      <EmptyState v-if="!recentActivitiesAvailable" icon="⚠" title="最近活动暂不可用" description="账号接口未返回活动记录，当前无法判断是否没有最近操作。" />
      <EmptyState v-else-if="recentActivities.length === 0" icon="📋" title="暂无最近活动" description="账号操作记录将在此显示。" />
      <div v-else class="activity-list">
        <div
          v-for="item in recentActivities"
          :key="`${item.time}-${item.text}`"
        >
          <time>{{ item.time }}</time>
          <span>{{ item.text }}</span>
        </div>
      </div>

      <button
        class="text-action activity-more"
        type="button"
        @click="dispatchAccountAction('activity-list')"
      >
        查看更多 <b>›</b>
      </button>
    </section>

    <!-- 快捷操作 -->
    </template>
    <section class="drawer-section quick-section">
      <h4>快捷操作</h4>

      <div class="quick-actions">
        <button
          type="button"
          @click="openCookieEdit(selected)"
        >
          <span>✎</span>
          编辑Cookie
        </button>

        <button
          type="button"
          @click="refreshProfile(selected.id)"
        >
          <span>↻</span>
          刷新资料
        </button>

        <button
          type="button"
          @click="dispatchAccountAction('sync-products')"
        >
          <span>◇</span>
          同步商品
        </button>

        <button
          type="button"
          @click="emit('navigate', 'auto-reply')"
        >
          <span>↻</span>
          自动回复
        </button>

        <button
          type="button"
          @click="emit('navigate', 'auto-delivery')"
        >
          <span>⇪</span>
          自动发货
        </button>

        <button
          type="button"
          @click="emit('navigate', 'messages')"
        >
          <span>✉</span>
          在线消息
        </button>

        <button
          type="button"
          @click="checkSelectedAuth"
        >
          <span>ⓘ</span>
          登录验证
        </button>
        <button
          type="button"
          @click="openRescanModal(selected)"
        >
          <span>◫</span>
          重新扫码
        </button>

        <button
          type="button"
          @click="openFaceVerificationModal(selected)"
        >
          <span>☉</span>
          人脸验证
        </button>

        <button
          type="button"
          @click="openAutoRateModal(selected)"
        >
          <span>✦</span>
          自动评价
        </button>

        <button
          type="button"
          @click="openLoginCredentialModal(selected)"
        >
          <span>⌘</span>
          账号密码登录
        </button>

        <button
          type="button"
          @click="openAccountStrategyModal(selected)"
        >
          <span>⌛</span>
          消息等待
        </button>

        <button
          type="button"
          @click="openUnifiedConfigModal(selected)"
        >
          <span>≡</span>
          统一配置
        </button>

        <template v-if="false">
        <button
          class="more-action"
          type="button"
          @click="dispatchAccountAction('more-actions')"
        >
          <span>⌄</span>
          更多操作⌄
        </button>
        <div v-if="moreActionsOpen" class="more-actions-backdrop" @click="closeMoreActionsMenu"></div>
        <div v-if="moreActionsOpen" class="more-actions-menu">
          <button type="button" @click="moreActionNavigate('products')">同步商品</button>
          <button type="button" @click="moreActionNavigate('auto-reply')">自动回复</button>
          <button type="button" @click="moreActionNavigate('auto-delivery')">自动发货</button>
          <button type="button" @click="moreActionNavigate('messages')">在线消息</button>
        </div>
        </template>
      </div>
    </section>
  </template>

  <div v-else class="empty-state detail-empty">
    {{ accountsAvailable ? '请选择一个账号查看详情' : '账号列表不可用，详情与写操作已禁用' }}
  </div>
</aside>
    </div>
  </div>

  <Teleport to="body">
    <div v-if="modal" class="modal-mask" @click.self="closeModal">
      <section v-if="modal==='scan'" class="xy-modal scan-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <h2>{{ qr.mode === 'rescan' ? '重新扫码更新账号' : '扫码添加闲鱼账号' }}</h2>
        <div class="scan-steps">
          <div class="scan-step" :class="{active: Boolean(qr.qrUrl)}"><b>1</b><span>{{ qr.qrUrl ? '二维码已生成' : '生成二维码' }}</span></div>
          <i></i><div class="scan-step" :class="{active: qr.status==='scanned'}"><b>2</b><span>扫码确认</span></div>
          <i></i><div class="scan-step" :class="{active: qr.status==='confirmed'}"><b>3</b><span>{{ qr.mode === 'rescan' ? '更新账号 Cookie' : '自动添加账号' }}</span></div>
        </div>
        <div class="scan-main">
          <div>
            <div class="qr-box">
              <img v-if="qr.qrUrl" :src="qr.qrUrl" alt="二维码">
              <div v-else-if="qrUnavailable" class="qr-unavailable" role="alert">
                <Icon name="help" />
                <b>二维码不可用</b>
                <span>请重试生成，仍失败时检查登录服务配置</span>
              </div>
              <span v-if="qr.loading" class="qr-loading"></span>
            </div>
            <p class="qr-tip">{{ qr.message || '正在自动生成二维码，请稍候...' }}</p>
          </div>
          <div class="scan-guide">
            <h4>{{ qr.mode === 'rescan' ? '重新扫码流程' : '添加流程' }}</h4>
            <p>1. {{ qr.qrUrl ? '系统已生成可扫描二维码' : '点击生成二维码并等待服务返回可扫描内容' }}</p>
            <p>2. 使用闲鱼 App 扫码并确认登录</p>
            <p>3. {{ qr.mode === 'rescan' ? '系统会把新的登录 Cookie 回写到当前账号并刷新状态' : '系统自动添加账号并刷新资料' }}</p>
            <div class="session-box">
              <h4>会话信息</h4>
              <div v-if="qr.accountId"><span>目标账号：</span><b>{{ qrTargetAccount?.nickname || qrTargetAccount?.displayName || qrTargetAccount?.externalUid || qr.accountId }}</b></div>
              <div><span>会话 ID：</span><b>{{ qr.sessionId || '-' }}</b></div>
              <div><span>当前状态：</span><b>{{ qr.status || '-' }}</b><button class="inline-link" @click="startQrLogin"><Icon name="refresh" /> 生成/刷新二维码</button></div>
            </div>
          </div>
        </div>
        <div class="notice-box"><b><Icon name="help" /> 说明</b><p>{{ qr.qrUrl ? '二维码已生成，可使用闲鱼 App 扫码登录。' : '当前没有可扫描二维码，生成成功后才可继续扫码。' }}</p><p>{{ qr.mode === 'rescan' ? '登录成功后会更新当前账号 Cookie，并重新同步该账号状态。' : '登录成功后将自动添加账号并刷新资料' }}</p></div>
        <div class="modal-actions"><AppButton @click="closeModal">取消</AppButton><AppButton type="primary" @click="startQrLogin">生成二维码</AppButton></div>
      </section>

      <section v-if="modal==='manual'" class="xy-modal manual-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <h2>手动添加账号</h2>
        <label class="field-label">账号备注 <span>可选</span></label>
        <div class="modal-input-wrap"><input v-model="manual.accountNote" placeholder="请输入备注名称（可选，不填写显示闲鱼昵称）"><em>{{ manual.accountNote.length }}/50</em></div>
        <label class="field-label required">Cookie <span>必填</span></label>
        <textarea v-model="manual.cookie" class="cookie-area" placeholder="请输入闲鱼账号 Cookie 字符串"></textarea>

        <!-- Cookie 解析预览 -->
        <div v-if="manualCookieParsed" class="cookie-parse-preview">
          <div v-if="!manualCookieParsed.validation.valid" class="cookie-parse-error">
            <Icon name="help" /> {{ manualCookieParsed.validation.error }}
          </div>
          <div v-if="manualCookieParsed.validation.valid" class="cookie-parse-fields">
            <div class="cookie-parse-header">
              <span>解析结果</span>
              <em>共 {{ manualCookieParsed.keyFields.parsedCount }} 个字段</em>
            </div>
            <div class="cookie-field-grid">
              <div class="cookie-field-item" :class="{ missing: !manualCookieParsed.keyFields.unb }">
                <label>unb（身份标识）<span class="required-mark">*必填</span></label>
                <code>{{ manualCookieParsed.masked.unb }}</code>
              </div>
              <div class="cookie-field-item" :class="{ missing: !manualCookieParsed.keyFields.mH5Tk }">
                <label>_m_h5_tk（签名Token）</label>
                <code>{{ manualCookieParsed.masked.mH5Tk }}</code>
              </div>
              <div v-if="manualCookieParsed.keyFields.userId" class="cookie-field-item">
                <label>user_id</label>
                <code>{{ manualCookieParsed.masked.userId }}</code>
              </div>
            </div>
            <div v-if="manualCookieParsed.validation.warning" class="cookie-parse-warning">
              <Icon name="help" /> {{ manualCookieParsed.validation.warning }}
            </div>
          </div>
        </div>

        <div v-if="manualError" class="input-error">{{ manualError }}</div>
        <div class="modal-hint"><Icon name="help" /> 提交后调用 /api/xianyu/accounts/manual-cookie，后端会解析并保存账号信息</div>
        <div class="usage-box">
          <h4><Icon name="map" /> 使用说明</h4>
          <div><span><Icon name="shield" /></span>Cookie 为空时会进行前端校验</div>
          <div><span><Icon name="shield" /></span>添加成功后自动刷新账号列表</div>
          <div><span><Icon name="shield" /></span>请勿把 Cookie 暴露给不可信页面或日志</div>
        </div>
        <div class="manual-actions"><AppButton @click="closeModal">取消</AppButton><AppButton type="primary" :disabled="manualCookieParsed && !manualCookieParsed.validation.valid" @click="submitManual">{{ submitting ? '添加中...' : '添加' }}</AppButton></div>
      </section>

      <section v-if="modal==='cookieEdit'" class="xy-modal manual-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <h2>编辑账号 Cookie</h2>
        <div class="edit-account-info">
          <span>账号：</span><b>{{ selected?.nickname || selected?.displayName || selected?.externalUid || selected?.unb || selected?.id }}</b>
          <span v-if="selected?.unb" class="current-unb-tag">UNB: {{ maskValue(selected.unb) }}</span>
        </div>
        <div class="cookie-edit-label-row">
          <label class="field-label required">Cookie <span>必填</span></label>
          <span class="cookie-edit-toolbar">
            <span v-if="cookieEditLoading" class="cookie-loading-hint"><Icon name="refresh" class="spin" /> 加载当前 Cookie...</span>
            <button v-else type="button" class="link cookie-copy-btn" :disabled="!cookieEdit.cookie" @click="copyCookieEdit">复制 Cookie</button>
          </span>
        </div>
        <textarea v-model="cookieEdit.cookie" class="cookie-area" :placeholder="cookieEditLoading ? '正在加载当前 Cookie...' : '请输入闲鱼账号 Cookie 字符串（从浏览器 F12 开发者工具中复制）'" :disabled="cookieEditLoading"></textarea>

        <!-- Cookie 解析预览 -->
        <div v-if="cookieEditParsed" class="cookie-parse-preview">
          <!-- 格式校验错误 -->
          <div v-if="!cookieEditParsed.validation.valid" class="cookie-parse-error">
            <Icon name="help" /> {{ cookieEditParsed.validation.error }}
          </div>

          <!-- 身份校验警告（防串号） -->
          <div v-if="cookieEditParsed.validation.valid && !cookieEditParsed.identity.valid" class="cookie-parse-error cookie-identity-error">
            <Icon name="shield" /> {{ cookieEditParsed.identity.error }}
          </div>

          <!-- 解析结果展示 -->
          <div v-if="cookieEditParsed.validation.valid" class="cookie-parse-fields">
            <div class="cookie-parse-header">
              <span>解析结果</span>
              <em>共 {{ cookieEditParsed.keyFields.parsedCount }} 个字段</em>
            </div>
            <div class="cookie-field-grid">
              <div class="cookie-field-item" :class="{ missing: !cookieEditParsed.keyFields.unb }">
                <label>unb（身份标识）<span class="required-mark">*必填</span></label>
                <code>{{ cookieEditParsed.masked.unb }}</code>
              </div>
              <div class="cookie-field-item" :class="{ missing: !cookieEditParsed.keyFields.mH5Tk }">
                <label>_m_h5_tk（签名Token）</label>
                <code>{{ cookieEditParsed.masked.mH5Tk }}</code>
              </div>
              <div v-if="cookieEditParsed.keyFields.userId" class="cookie-field-item">
                <label>user_id</label>
                <code>{{ cookieEditParsed.masked.userId }}</code>
              </div>
              <div v-if="cookieEditParsed.keyFields.loginToken" class="cookie-field-item">
                <label>_cookie_login_token_</label>
                <code>{{ cookieEditParsed.masked.loginToken }}</code>
              </div>
            </div>
            <!-- 警告信息 -->
            <div v-if="cookieEditParsed.validation.warning" class="cookie-parse-warning">
              <Icon name="help" /> {{ cookieEditParsed.validation.warning }}
            </div>
          </div>
        </div>

        <div v-if="cookieEditError" class="input-error">{{ cookieEditError }}</div>
        <div class="modal-hint"><Icon name="help" /> 提交后自动提取 unb、_m_h5_tk 等关键字段并重置 Cookie 状态为正常。保存后建议重新连接 WebSocket。</div>
        <div class="usage-box">
          <h4><Icon name="map" /> 使用说明</h4>
          <div><span><Icon name="shield" /></span>遇到"被挤爆"滑块验证时需要更换 Cookie</div>
          <div><span><Icon name="shield" /></span>Cookie 从浏览器 F12 → Application → Cookies 中复制</div>
          <div><span><Icon name="shield" /></span>请勿把 Cookie 暴露给不可信页面或日志</div>
        </div>
        <div class="manual-actions"><AppButton @click="closeModal">取消</AppButton><AppButton type="primary" :disabled="cookieEditSubmitting || (cookieEditParsed && !cookieEditParsed.validation.valid)" @click="submitCookieEdit">{{ cookieEditSubmitting ? '保存中...' : '保存' }}</AppButton></div>
      </section>

      <section v-if="modal==='faceVerify'" class="xy-modal face-verify-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <h2>人脸验证</h2>
        <div class="edit-account-info">
          <span>账号：</span><b>{{ selected?.nickname || selected?.displayName || selected?.externalUid || selected?.id || '-' }}</b>
        </div>
        <div class="modal-hint"><Icon name="help" /> 这里展示当前账号最近的人机验证提醒，处理完成后可以标记已读。</div>
        <div v-if="faceVerificationError" class="input-error">{{ faceVerificationError }}</div>
        <div v-if="faceVerificationLoading" class="face-verify-loading">正在加载验证提醒...</div>
        <EmptyState
          v-else-if="!faceVerificationError && faceVerificationItems.length === 0"
          icon="🛡"
          title="暂无待处理的人机验证"
          description="当前账号最近没有新的验证提醒。"
        />
        <div v-else class="face-verify-list">
          <article
            v-for="item in faceVerificationItems"
            :key="item.id"
            class="face-verify-item"
            :class="{ read: Number(item.readFlag) === 1 }"
          >
            <div class="face-verify-item-head">
              <strong>{{ item.title || '人机验证提醒' }}</strong>
              <Badge :type="Number(item.readFlag) === 1 ? '' : 'orange'">{{ Number(item.readFlag) === 1 ? '已读' : '待处理' }}</Badge>
            </div>
            <p>{{ item.content || '请尽快回到闲鱼完成验证。' }}</p>
            <div class="face-verify-item-foot">
              <span>{{ displayDateTime(item.createdTime) }}</span>
              <button
                type="button"
                class="link"
                :disabled="faceVerificationMarkingId === item.id || Number(item.readFlag) === 1"
                @click="markFaceVerificationRead(item)"
              >
                {{ faceVerificationMarkingId === item.id ? '处理中...' : (Number(item.readFlag) === 1 ? '已标记' : '标记已读') }}
              </button>
            </div>
          </article>
        </div>
        <div class="manual-actions">
          <AppButton @click="closeModal">关闭</AppButton>
          <AppButton type="primary" @click="openFaceVerificationModal(selected)">刷新</AppButton>
        </div>
      </section>

      <section v-if="modal==='autoRate'" class="xy-modal manual-modal auto-rate-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <h2>自动评价</h2>
        <div class="edit-account-info">
          <span>账号：</span><b>{{ selected?.nickname || selected?.displayName || selected?.externalUid || selected?.id || '-' }}</b>
        </div>
        <label class="auto-rate-toggle">
          <input v-model="autoRateForm.enabled" type="checkbox" :disabled="!autoRateLoaded">
          <span>启用该账号的自动评价</span>
        </label>
        <label class="field-label required">每天执行时间 <span>必选</span></label>
        <select v-model="autoRateForm.scheduleHour" class="input large" :disabled="!autoRateLoaded">
          <option v-for="opt in autoRateScheduleHourOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <div class="modal-hint"><Icon name="help" /> 启用后，每天到点会自动拉取该账号评价管理，对未评价订单提交好评。非鱼小铺账号、Cookie 失效、未配置评价内容时会自动跳过并写入日志。</div>
        <label class="field-label">评价方式</label>
        <select v-model="autoRateForm.rateType" class="input large" :disabled="!autoRateLoaded">
          <option value="text">固定文本</option>
          <option value="api">外部 API</option>
        </select>
        <template v-if="autoRateForm.rateType === 'text'">
          <label class="field-label required">评价内容 <span>必填</span></label>
          <textarea
            v-model="autoRateForm.textContent"
            class="cookie-area"
            :disabled="!autoRateLoaded"
            placeholder="请输入默认评价内容，例如：交易顺利，感谢支持。"
          ></textarea>
        </template>
        <template v-else>
          <label class="field-label required">API 地址 <span>必填</span></label>
          <input
            v-model="autoRateForm.apiUrl"
            class="input large"
            :disabled="!autoRateLoaded"
            placeholder="https://example.com/xianyu/auto-rate"
          >
          <label class="field-label">兜底评价内容 <span>可选</span></label>
          <textarea
            v-model="autoRateForm.textContent"
            class="cookie-area"
            :disabled="!autoRateLoaded"
            placeholder="当外部接口不可用时，可回退到这段文本。"
          ></textarea>
        </template>
        <div v-if="autoRateError" class="input-error">{{ autoRateError }}</div>
        <div class="modal-hint"><Icon name="help" /> 当前先保存账号级自动评价配置，后续自动执行链路会直接复用这里的参数。</div>
        <div class="manual-actions">
          <AppButton @click="closeModal">取消</AppButton>
          <AppButton type="primary" :disabled="!autoRateLoaded || autoRateSaving" @click="saveAutoRateConfig">{{ autoRateSaving ? '保存中...' : '保存' }}</AppButton>
        </div>
      </section>

      <section v-if="modal==='accountStrategy'" class="xy-modal manual-modal auto-rate-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <h2>消息等待</h2>
        <div class="edit-account-info">
          <span>账号：</span><b>{{ selected?.nickname || selected?.displayName || selected?.externalUid || selected?.id || '-' }}</b>
        </div>
        <label class="field-label required">相同消息等待时间（秒） <span>0-86400</span></label>
        <input
          v-model="accountStrategyForm.messageExpireTime"
          class="input large"
          type="number"
          min="0"
          max="86400"
          placeholder="3600"
          :disabled="!accountStrategyLoaded"
        >
        <label class="auto-rate-toggle">
          <input v-model="accountStrategyForm.scheduledRedelivery" type="checkbox" :disabled="!accountStrategyLoaded">
          <span>开启该账号的定时补发货</span>
        </label>
        <label class="auto-rate-toggle">
          <input v-model="accountStrategyForm.autoPolish" type="checkbox" :disabled="!accountStrategyLoaded">
          <span>开启该账号的自动擦亮商品</span>
        </label>
        <div v-if="accountStrategyError" class="input-error">{{ accountStrategyError }}</div>
        <div class="modal-hint"><Icon name="help" /> 该配置会作为账号级策略保存，后续消息等待、定时补发货和商品擦亮会直接复用这里的参数。</div>
        <div class="manual-actions">
          <AppButton @click="closeModal">取消</AppButton>
          <AppButton type="primary" :disabled="!accountStrategyLoaded || accountStrategySaving" @click="saveAccountStrategyConfig">{{ accountStrategySaving ? '保存中...' : '保存' }}</AppButton>
        </div>
      </section>

      <section v-if="modal==='loginCredential'" class="xy-modal manual-modal auto-rate-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <h2>账号密码登录</h2>
        <div class="edit-account-info">
          <span>账号：</span><b>{{ selected?.nickname || selected?.displayName || selected?.externalUid || selected?.id || '-' }}</b>
        </div>
        <label class="field-label required">登录账号 <span>必填</span></label>
        <input
          v-model="accountLoginCredentialForm.loginUsername"
          class="input large"
          autocomplete="username"
          placeholder="请输入闲鱼登录账号"
          :disabled="!loginCredentialLoaded"
        >
        <label class="field-label">登录密码 <span>{{ accountLoginCredentialForm.hasLoginPassword ? '留空则保持不变' : '首次配置' }}</span></label>
        <input
          v-model="accountLoginCredentialForm.loginPassword"
          class="input large"
          type="password"
          autocomplete="new-password"
          placeholder="重新输入将覆盖已保存密码"
          :disabled="!loginCredentialLoaded"
        >
        <label v-if="accountLoginCredentialForm.hasLoginPassword" class="auto-rate-toggle">
          <input v-model="accountLoginCredentialForm.clearLoginPassword" type="checkbox" :disabled="!loginCredentialLoaded">
          <span>清空已保存密码</span>
        </label>
        <label class="auto-rate-toggle">
          <input v-model="accountLoginCredentialForm.showBrowser" type="checkbox" :disabled="!loginCredentialLoaded">
          <span>登录时显示浏览器窗口</span>
        </label>
        <div v-if="loginCredentialError" class="input-error">{{ loginCredentialError }}</div>
        <div class="modal-hint"><Icon name="help" /> 该配置会作为账号密码登录和会话续期的基础凭据保存。已保存密码不会回显，重新输入才会覆盖。</div>
        <div class="manual-actions">
          <AppButton @click="closeModal">取消</AppButton>
          <AppButton type="primary" :disabled="!loginCredentialLoaded || loginCredentialSaving" @click="saveAccountLoginCredential">{{ loginCredentialSaving ? '保存中...' : '保存凭据' }}</AppButton>
        </div>
      </section>

      <section v-if="modal==='unifiedConfig'" class="xy-modal manual-modal auto-rate-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <h2>统一配置 / 批量应用</h2>
        <div class="edit-account-info">
          <span>基准账号：</span><b>{{ selected?.nickname || selected?.displayName || selected?.externalUid || selected?.id || '-' }}</b>
        </div>
        <p class="modal-subtitle">以当前选中的账号为基准，将自动评价、消息等待等配置快速应用到当前列表中的账号。</p>
        <div class="modal-hint"><Icon name="help" /> 当前将对 {{ accounts.length }} 个账号执行批量操作；如只想作用于部分账号，请先通过搜索缩小列表范围。</div>
        <div v-if="unifiedConfigError" class="input-error">{{ unifiedConfigError }}</div>
        <div v-if="unifiedConfigSuccess" class="global-notice success" style="margin-top:12px">{{ unifiedConfigSuccess }}</div>
        <div class="unified-config-grid">
          <button type="button" class="unified-config-card" :disabled="unifiedConfigBusy" @click="applyCurrentAutoRateToVisibleAccounts">
            <strong>同步自动评价</strong>
            <span>将当前账号的自动评价配置应用到当前列表中的账号。</span>
          </button>
          <button type="button" class="unified-config-card" :disabled="unifiedConfigBusy" @click="applyCurrentStrategyToVisibleAccounts">
            <strong>同步消息等待</strong>
            <span>将消息等待、定时重发等策略配置同步到当前列表中的账号。</span>
          </button>
          <button type="button" class="unified-config-card" :disabled="unifiedConfigBusy" @click="runBatchAuthCheckForVisibleAccounts">
            <strong>统一登录校验</strong>
            <span>批量检查当前列表账号的登录状态、Cookie 和会话有效性。</span>
          </button>
        </div>
        <div v-if="unifiedConfigBusy" class="modal-hint" style="margin-top:14px"><Icon name="help" /> 正在执行：{{ unifiedConfigTaskText }}</div>
        <div class="manual-actions">
          <AppButton @click="closeModal">关闭</AppButton>
        </div>
      </section>

      <section v-if="modal==='confirmDelete'" class="xy-modal confirm-delete-modal">
        <button class="modal-close" @click="closeModal"><Icon name="close" /></button>
        <div class="confirm-delete-icon">
          <Icon name="warning" />
        </div>
        <h2>确认删除该闲鱼账号？</h2>
        <p class="confirm-delete-desc">删除后将移除该账号的本地连接、资料和后续自动化配置关联，请确认已不再运营该账号。</p>
        <div class="confirm-delete-actions">
          <AppButton @click="closeModal">取消</AppButton>
          <AppButton type="danger" @click="executeDelete">确认删除</AppButton>
        </div>
      </section>
    </div>
  </Teleport>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import StatCard from '../components/StatCard.vue'; import CardPanel from '../components/CardPanel.vue'; import BaseTable from '../components/BaseTable.vue'; import Badge from '../components/Badge.vue'; import AppButton from '../components/AppButton.vue'; import Icon from '../components/Icon.vue'; import EmptyState from '../components/EmptyState.vue'; import Pagination from '../components/Pagination.vue'
import { checkAccountAuth, deleteAccount, getLiteAccounts, createAccountByCookie, getAccountDetail, refreshAccountProfile, updateAccountCookie, getAccountCookie, runItemPolish, getItemPolishProgress, getAccountAutoRateConfig, saveAccountAutoRateConfig, getAccountFaceVerifications, markAccountFaceVerificationRead, getAccountStrategyConfig as getAccountStrategyConfigRequest, saveAccountStrategyConfig as saveAccountStrategyConfigRequest, getAccountLoginCredential as getAccountLoginCredentialRequest, saveAccountLoginCredential as saveAccountLoginCredentialRequest } from '../api/accounts.js'
import { startWebSocket, stopWebSocket, websocketStatus } from '../api/websocket.js'
import { useDebouncedRef } from '../composables/useDebouncedRef.js'
import { guardFeatureAction } from '../composables/featureGuard.js'
const emit = defineEmits(['navigate'])
import { generateQrLogin, getQrLoginStatus, cleanupQrLogin } from '../api/qrlogin.js'
import { accountName } from '../utils/format.js'
import { resolveTrustedMediaUrl, resolveAvatarUrl } from '../utils/safeMediaUrl.js'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { accountAuthUsable, accountCookieBadgeType, accountCookieLabel, accountLoginHint, accountWsConnectionState, resolveAccountAuthDisplayState } from '../utils/accountAuth.js'
import { extractKeyFields, maskKeyFields, validateCookie, checkIdentity, maskValue } from '../utils/cookie.js'
import { useCaptchaSolver } from '../composables/useCaptchaSolver.js'
import { getFeatureStatus, invalidateFeatureSwitchCache } from '../api/feature-switch.js'
import { globalConfirm } from '../composables/confirmState.js'

const { solveStates, isAccountSolving, isAccountQueued, getAccountSolveStatus, solveManually, initCaptchaSolverListener, destroyCaptchaSolverListener } = useCaptchaSolver()

const modal = ref('')
const manual = reactive({ accountNote:'', cookie:'' })
const manualError = ref('')
const submitting = ref(false)
const loading = ref(false)
const error = ref('')
const accountsLoadError = ref('')
const accountsAvailable = ref(false)
const keyword = ref('')
const debouncedKeyword = useDebouncedRef(keyword, 300)
const statusFilter = ref('all')
const accounts = ref([])
const current = ref(1)
const pageSize = ref(20)
const total = ref(0)
const selected = ref(null)
const selectedId = ref(null)
const wsMap = reactive({})
const wsBusyMap = reactive({})
// 滑块求解成功后正在自动连接 WebSocket 的账号 ID 集合（用于横幅文案与状态展示）
const autoConnectingWs = reactive(new Set())
// 手动求解入队成功后标记"待自动连接 WS"，等 SSE success 事件到达时触发自动连接
// 求解改为队列异步后，成功结果不再同步返回，需要通过 SSE 事件异步触发
const pendingAutoConnectWsAfterSolve = reactive(new Set())
const selectedWs = computed(() => wsMap[selected.value?.id] || {})
const selectedWsState = computed(() => accountWsConnectionState(selected.value, selectedWs.value))
const selectedAuthDisplay = computed(() => resolveAccountAuthDisplayState(selected.value, selectedWs.value))
const qrTargetAccount = computed(() => {
  if (!qr.accountId) return null
  if (selected.value?.id === qr.accountId) return selected.value
  return accounts.value.find(item => item.id === qr.accountId) || null
})
let qrTimer = null
const qr = reactive({ loading:false, sessionId:'', qrUrl:'', status:'', message:'', mode:'create', accountId:null })
const qrUnavailable = computed(() => !qr.loading && !qr.qrUrl)
const qrSuccessMsg = ref('')
const cookieEdit = reactive({ accountId: null, cookie: '' })
const cookieEditError = ref('')
const cookieEditSubmitting = ref(false)
const cookieEditLoading = ref(false)
const faceVerificationLoading = ref(false)
const faceVerificationError = ref('')
const faceVerificationItems = ref([])
const faceVerificationMarkingId = ref(null)
const autoRateSaving = ref(false)
const autoRateError = ref('')
const autoRateLoaded = ref(false)
const autoRateForm = reactive({
  enabled: false,
  rateType: 'text',
  textContent: '',
  apiUrl: '',
  scheduleHour: 9,
})
const autoRateScheduleHourOptions = Array.from({ length: 24 }, (_, h) => ({
  value: h,
  label: `${String(h).padStart(2, '0')}:00`,
}))
const loginCredentialSaving = ref(false)
const loginCredentialError = ref('')
const loginCredentialLoaded = ref(false)
const accountLoginCredentialForm = reactive({
  loginUsername: '',
  loginPassword: '',
  clearLoginPassword: false,
  hasLoginPassword: false,
  showBrowser: false,
})
const accountStrategySaving = ref(false)
const accountStrategyError = ref('')
const accountStrategyLoaded = ref(false)
const accountStrategyForm = reactive({
  messageExpireTime: 3600,
  scheduledRedelivery: false,
  autoPolish: false,
})
const unifiedConfigBusy = ref(false)
const unifiedConfigError = ref('')
const unifiedConfigSuccess = ref('')
const unifiedConfigTaskText = ref('')
let polishTimer = null
let polishTaskId = ''
const polishingAccountId = ref(null)  // 正在擦亮的账号ID
const pendingDeleteId = ref(null)     // 待删除的账号ID

// Cookie 编辑弹窗 - 实时解析预览
const cookieEditParsed = computed(() => {
  if (!cookieEdit.cookie.trim()) return null
  const validation = validateCookie(cookieEdit.cookie)
  const keyFields = extractKeyFields(cookieEdit.cookie)
  const masked = maskKeyFields(keyFields)
  // 身份校验：与当前选中账号的 unb 对比
  const identity = selected.value
    ? checkIdentity(keyFields.unb, selected.value)
    : { valid: true, error: null, unbChanged: false }
  return { validation, keyFields, masked, identity }
})

// 手动添加账号弹窗 - 实时解析预览
const manualCookieParsed = computed(() => {
  if (!manual.cookie.trim()) return null
  const validation = validateCookie(manual.cookie)
  const keyFields = extractKeyFields(manual.cookie)
  const masked = maskKeyFields(keyFields)
  return { validation, keyFields, masked }
})

function accountTitle(account){ return accountName(account) }
function accountStatus(status){ return ({ 1:'正常', '-1':'需手机验证', '-2':'需人机验证' }[status] || '未知') }
function accountHealth(){ return null } // 健康分接口开发中

function captchaSolveBadge(accountId) {
  const state = getAccountSolveStatus(accountId)
  if (!state) return null
  if (state.status === 'queued') return { text: '排队中', color: 'blue' }
  if (state.status === 'retrying') return { text: '滑块求解中', color: 'orange' }
  if (state.status === 'success') return { text: '求解成功', color: 'green' }
  if (state.status === 'fail') return { text: '求解失败', color: 'red' }
  if (state.status === 'timeout') return { text: '求解超时', color: 'red' }
  if (state.status === 'precheck_rejected') return { text: '预校验拒绝', color: 'red' }
  return null
}

const manualRetryBusy = ref(null)
// 单账号手动求解冷却：每分钟最多 1 次主动求解；失败后点击"重试求解"不受冷却限制
// key = accountId(string), value = 上次主动求解时间戳(ms)
const manualSolveCooldown = reactive({})
const MANUAL_SOLVE_COOLDOWN_MS = 60 * 1000  // 1 分钟

// 判断账号是否处于冷却中（仅用于"主动求解"，重试求解不受限制）
function manualSolveCooldownRemaining(accountId) {
  const last = manualSolveCooldown[String(accountId)] || 0
  if (!last) return 0
  const remaining = MANUAL_SOLVE_COOLDOWN_MS - (Date.now() - last)
  return remaining > 0 ? remaining : 0
}

// 冷却 tick：驱动 disabled/title 响应式更新（每秒刷新一次）
const cooldownTick = ref(0)
let cooldownTimer = null
function ensureCooldownTimer() {
  if (cooldownTimer) return
  cooldownTimer = setInterval(() => { cooldownTick.value++ }, 1000)
}
ensureCooldownTimer()

async function handleManualSolve(accountId) {
  if (!accountId || manualRetryBusy.value === accountId || isAccountSolving(accountId)) return
  // 前端双层校验：manual-slider-solve 功能开关
  // 被拦截时弹窗展示关闭原因 + 引导升级会员，不发请求
  const fsStatus = await getFeatureStatus('manual-slider-solve')
  if (!fsStatus.allowed) {
    await showManualSolveBlockedDialog(fsStatus)
    return
  }
  // 根据当前求解状态判断场景：已有失败/超时/预校验拒绝状态时为"重试求解"，否则为"手动触发"
  const state = getAccountSolveStatus(accountId)
  const isRetry = !!(state && (state.status === 'fail' || state.status === 'timeout' || state.status === 'precheck_rejected'))
  // 仅"主动求解"（非重试）受 1 分钟冷却限制
  if (!isRetry) {
    const remaining = manualSolveCooldownRemaining(accountId)
    if (remaining > 0) {
      const seconds = Math.ceil(remaining / 1000)
      error.value = `该账号 ${seconds} 秒内已主动求解过，请稍后再试；如需立即重试，请等本次求解失败后点击"重试求解"`
      setTimeout(() => { if (error.value && error.value.includes('已主动求解过')) error.value = '' }, 4000)
      return
    }
  }
  manualRetryBusy.value = accountId
  try {
    const scene = isRetry ? 'manual_retry' : 'manual'
    // 仅"主动求解"记录冷却开始时间（重试不记录）
    if (!isRetry) manualSolveCooldown[String(accountId)] = Date.now()
    const result = await solveManually(accountId, scene, {
      openReason: '用户在账号管理页点击滑块求解按钮',
      solveReason: isRetry
        ? '用户在账号管理页点击重试求解（上次求解失败）'
        : '用户在账号管理页主动触发滑块求解',
    })
    // 求解改为队列异步后，成功/失败通过 SSE 通知
    // 入队成功时标记"待自动连接 WS"，等 SSE success 事件触发时执行
    if (result?.queued) {
      pendingAutoConnectWsAfterSolve.add(Number(accountId))
    } else if (result?.deduplicated) {
      // 被后端去重跳过（同账号 60 秒内已入队）：展示临时提示，不污染求解状态
      error.value = result.message || '该账号近期已触发过求解，请稍后再试'
      setTimeout(() => { if (error.value && error.value.includes('已触发过求解')) error.value = '' }, 4000)
    }
  } catch (e) {
    // 后端 403 拦截（前端绕过场景）：解析 errData 中的 reason_text 弹窗引导
    const errData = e?.data || e?.raw?.data || {}
    if (e?.code === 403 && errData?.feature_key === 'manual-slider-solve') {
      await showManualSolveBlockedDialog({
        allowed: false,
        reason: errData.reason,
        required_level: errData.required_level,
        reason_text: errData.reason_text,
      })
      // 强制刷新功能开关缓存，避免前端缓存陈旧
      invalidateFeatureSwitchCache()
    } else {
      throw e
    }
  } finally {
    manualRetryBusy.value = null
  }
}

/**
 * 手动滑块求解被功能开关拦截时的弹窗引导。
 * 展示管理员填写的关闭原因 + 需升级到的会员等级，提供"去升级"按钮跳转会员中心。
 */
async function showManualSolveBlockedDialog(status) {
  const levelText = { vip: 'VIP', svp: 'SVIP', normal: '普通用户' }[status.required_level] || 'VIP'
  const reasonText = status.reason_text || '您的会员等级未开启手动滑块求解功能'
  const description = status.reason === 'disabled'
    ? `${reasonText}\n\n该功能目前对所有等级关闭，如有需要请联系管理员开启。`
    : `${reasonText}\n\n请升级到 ${levelText} 会员后使用此功能。`
  const confirmed = await globalConfirm.confirm(
    '无法使用手动滑块求解',
    description,
    '去升级会员',
  )
  if (confirmed) emit('navigate', 'vip')
}

// 滑块求解状态横幅：从 solveStates 提取所有有状态的账号，生成原因+下一步操作
const captchaAlerts = computed(() => {
  const alerts = []
  const stateMap = solveStates
  for (const key of Object.keys(stateMap)) {
    const state = stateMap[key]
    if (!state) continue
    const accountId = Number(key)
    // 查找账号名称
    const account = accounts.value.find(a => Number(a.id) === accountId)
    const accountName = state.accountName || (account ? accountTitle(account) : '')

    let type = 'solving'
    let statusText = '求解中'
    let reason = state.reason || ''
    let nextAction = ''
    let canRetry = false

    if (state.status === 'success') {
      type = 'success'
      statusText = '求解成功'
      reason = state.reason || '滑块求解成功，Cookie 已恢复'
      // 求解成功后已自动连接 WebSocket 时，提示用户留意在线状态变化；否则提示可手动连接
      nextAction = autoConnectingWs.has(accountId)
        ? '正在自动连接 WebSocket，请留意在线状态'
        : '可重新启动 WebSocket 连接'
    } else if (state.status === 'queued') {
      type = 'queued'
      statusText = '排队中'
      const pos = state.queuePosition || 0
      const total = state.queueTotal || 0
      reason = pos > 0
        ? `任务已入队，当前排队第 ${pos} 位（共 ${total} 个任务），前方任务处理完毕后自动开始求解`
        : (state.reason || '任务已入队，等待排队...')
      nextAction = '请耐心等待，无需重复点击求解'
      canRetry = false
    } else if (state.status === 'retrying') {
      type = 'solving'
      statusText = '求解中'
      reason = state.reason || 'worker 已开始处理，正在自动求解滑块...'
      canRetry = false
    } else if (state.status === 'fail') {
      type = 'fail'
      statusText = '求解失败'
      reason = state.reason || '滑块求解失败'

      // 根据失败原因判断下一步操作
      const reasonLower = reason.toLowerCase()
      if (reasonLower.includes('session') || reasonLower.includes('过期') || reasonLower.includes('重新扫码') || reasonLower.includes('登录')) {
        // Cookie Session 已过期 —— 滑块求解无法解决，必须人工重新扫码
        nextAction = 'Cookie 已失效，需点击"重新扫码"登录获取新 Cookie（滑块求解无法解决此问题）'
        canRetry = false
      } else if (reasonLower.includes('服务暂时不可用') || reasonLower.includes('unavailable') || reasonLower.includes('连接')) {
        // 求解服务不可用 —— 可重试
        nextAction = '求解服务暂时不可用，可点击重试；若持续失败请联系管理员检查 crawler-service'
        canRetry = true
      } else if (reasonLower.includes('未通过') || reasonLower.includes('未检测到') || reasonLower.includes('失败')) {
        // 滑块未通过 —— 可重试
        nextAction = '可点击重试求解；若多次失败建议手动完成验证'
        canRetry = true
      } else {
        nextAction = '可点击重试求解；若持续失败请手动处理'
        canRetry = true
      }
    } else if (state.status === 'timeout') {
      type = 'fail'
      statusText = '求解超时'
      reason = state.reason || '滑块求解超时'
      nextAction = '可点击重试求解；若持续超时请检查网络或联系管理员'
      canRetry = true
    } else if (state.status === 'precheck_rejected') {
      type = 'fail'
      statusText = '预校验拒绝'
      reason = state.reason || '滑块求解预校验未通过'
      // 根据 reason 文案细化下一步操作（按优先级匹配，冷却中优先级最高）
      const reasonLower = reason.toLowerCase()
      if (reasonLower.includes('冷却') || reasonLower.includes('剩余') || reasonLower.includes('failcount')) {
        // 冷却拦截：自动求解 60 秒内连续失败触发冷却，手动触发可跳过
        nextAction = '滑块求解冷却中，请稍候或点击"重试求解"主动跳过冷却'
        canRetry = true
      } else if (reasonLower.includes('session') || reasonLower.includes('过期') || reasonLower.includes('重新扫码') || reasonLower.includes('登录') || reasonLower.includes('cookie')) {
        nextAction = 'Cookie 已失效，需点击"重新扫码"登录获取新 Cookie'
        canRetry = false
      } else if (reasonLower.includes('不活跃') || reasonLower.includes('inactive') || reasonLower.includes('未登录') || reasonLower.includes('3天')) {
        nextAction = '账号已超过 3 天未登录前台，已暂停自动求解；请登录前台后恢复活跃状态'
        canRetry = false
      } else if (reasonLower.includes('禁用') || reasonLower.includes('disabled')) {
        nextAction = '账号已被禁用，无法进行滑块求解'
        canRetry = false
      } else if (reasonLower.includes('服务暂时不可用') || reasonLower.includes('unavailable') || reasonLower.includes('haslogin')) {
        nextAction = 'Cookie 校验服务暂时不可用，请稍后重试'
        canRetry = true
      } else {
        nextAction = '预校验未通过，请检查账号状态后重试'
        canRetry = true
      }
    }

    // 成功状态 5 秒后自动消失（通过时间戳判断）
    if (state.status === 'success' && state.timestamp && Date.now() - state.timestamp > 5000) {
      continue
    }

    alerts.push({
      accountId,
      accountName,
      type,
      statusText,
      reason,
      nextAction,
      canRetry,
    })
  }
  return alerts
})

// 监听求解状态变化：手动求解成功后自动连接 WebSocket
// 求解改为队列异步后，成功结果通过 SSE captcha_solve 事件通知，不再由 solveManually 同步返回
watch(
  () => Object.keys(solveStates).map(k => `${k}:${solveStates[k]?.status}`),
  () => {
    for (const key of Object.keys(solveStates)) {
      const state = solveStates[key]
      if (!state || state.status !== 'success') continue
      const accountId = Number(key)
      if (!pendingAutoConnectWsAfterSolve.has(accountId)) continue
      pendingAutoConnectWsAfterSolve.delete(accountId)
      const account = accounts.value.find(a => a.id === accountId)
      if (account) autoConnectWsAfterSolve(account)
    }
  }
)

// 操作列滑块求解按钮文字
function solveOpBtnText(accountId) {
  if (manualRetryBusy.value === accountId) return '提交中...'
  if (isAccountQueued(accountId)) return '排队中...'
  if (isAccountSolving(accountId)) return '求解中...'
  void cooldownTick.value  // 响应冷却倒计时刷新
  const state = getAccountSolveStatus(accountId)
  if (!state) {
    // 无状态时检查冷却：冷却中显示倒计时
    const remaining = manualSolveCooldownRemaining(accountId)
    if (remaining > 0) return `冷却 ${Math.ceil(remaining / 1000)}s`
    return '滑块求解'
  }
  if (state.status === 'success') return '已求解'
  if (state.status === 'fail') return '重试求解'
  if (state.status === 'timeout') return '重试求解'
  if (state.status === 'precheck_rejected') return '重试求解'
  return '滑块求解'
}

// 操作列滑块求解按钮状态样式类
function solveOpBtnClass(accountId) {
  if (manualRetryBusy.value === accountId) return 'solving'
  if (isAccountQueued(accountId)) return 'queued'
  if (isAccountSolving(accountId)) return 'solving'
  void cooldownTick.value  // 响应冷却倒计时刷新
  const state = getAccountSolveStatus(accountId)
  if (!state) {
    // 无状态但冷却中：标记为冷却样式
    if (manualSolveCooldownRemaining(accountId) > 0) return 'cooldown'
    return ''
  }
  if (state.status === 'success') return 'success'
  if (state.status === 'fail') return 'fail'
  if (state.status === 'timeout') return 'fail'
  if (state.status === 'precheck_rejected') return 'fail'
  return ''
}

// 操作列滑块求解按钮是否禁用：求解中或冷却中（且非失败/超时/预校验拒绝重试状态）禁用
function solveOpBtnDisabled(accountId) {
  if (manualRetryBusy.value === accountId || isAccountSolving(accountId)) return true
  void cooldownTick.value  // 响应冷却倒计时刷新
  const state = getAccountSolveStatus(accountId)
  // 失败/超时/预校验拒绝重试状态不受冷却限制
  if (state && (state.status === 'fail' || state.status === 'timeout' || state.status === 'precheck_rejected')) return false
  // 其他状态（含无状态/成功）受冷却限制
  return manualSolveCooldownRemaining(accountId) > 0
}

// 操作列滑块求解按钮悬停提示
function solveOpBtnTitle(accountId) {
  void cooldownTick.value
  const state = getAccountSolveStatus(accountId)
  if (!state) {
    const remaining = manualSolveCooldownRemaining(accountId)
    if (remaining > 0) return `该账号 ${Math.ceil(remaining / 1000)} 秒内已主动求解过，请稍后再试`
    return '手动触发滑块求解'
  }
  if (state.status === 'fail' || state.status === 'timeout' || state.status === 'precheck_rejected') {
    return state.reason || '点击重试求解'
  }
  return state.reason || state.status || '滑块求解'
}

function metricScore(account, key) {
  const value = Number(account?.[key])
  if (!Number.isFinite(value)) return null
  return Math.max(0, Math.min(100, Math.round(value)))
}

function accountRegisterDate(account) {
  const value =
    account?.registerTime ||
    account?.createdTime ||
    account?.createTime

  if (!value) return '-'

  return String(value)
    .replace('T', ' ')
    .slice(0, 10)
}

function displayDateTime(value) {
  if (!value) return '-'

  return String(value)
    .replace('T', ' ')
    .slice(0, 16)
}

function fmtNumber(num) {
  if (num == null) return '-'
  if (num >= 10000) {
    return (num / 10000).toFixed(1).replace(/\.0$/, '') + '万'
  }
  return String(num)
}

function activityTime(value) {
  if (!value) return '-- --:--'

  const text = String(value).replace('T', ' ')

  return text.length >= 16
    ? text.slice(5, 16)
    : text
}

function isCurrentAccount(account) {
  return (
    account?.isCurrentAccount === true ||
    account?.current === true ||
    account?.id === accounts.value[0]?.id
  )
}

function closeDetail() {
  selected.value = null
}

function dispatchAccountAction(action) {
  if (!selected.value) return
  switch (action) {
    case 'sync-products':
      emit('navigate', 'products')
      break
    case 'health-detail':
      error.value = '健康分功能即将上线，敬请期待'
      setTimeout(() => { error.value = '' }, 2400)
      break
    case 'activity-list':
      emit('navigate', 'logs')
      break
    case 'more-actions':
      toggleMoreActionsMenu()
      break
    default:
      console.warn('[AccountsPage] 未知的账号操作:', action)
  }
}

const moreActionsOpen = ref(false)
function toggleMoreActionsMenu() {
  moreActionsOpen.value = !moreActionsOpen.value
}
function closeMoreActionsMenu() {
  moreActionsOpen.value = false
}
function moreActionNavigate(page) {
  closeMoreActionsMenu()
  emit('navigate', page)
}

const healthRingStyle = computed(() => {
  const score = accountHealth(selected.value)
  return {
    '--health-score': score != null ? `${score}%` : '0%'
  }
})


const accountDiagnostics = computed(() => {
  const a = selected.value || {}
  const ws = selectedWs.value || {}
  const authState = resolveAccountAuthDisplayState(a, ws)
  const cookieUnknown = !authState.authKnown
  const cookieBad = authState.authKnown && !authState.usable
  const verify = a.status === -1 || a.status === -2
  const accountStatusKnown = a.status !== null && a.status !== undefined
  const wsState = accountWsConnectionState(a, ws)
  return [
    {
      title: 'Cookie 状态',
      level: cookieUnknown ? 'warn' : cookieBad ? 'danger' : 'ok',
      text: accountCookieLabel(a, ws),
      tip: cookieUnknown ? '请先刷新登录状态后再执行依赖 Cookie 的操作。' : cookieBad ? accountLoginHint(a, ws) : '可继续同步商品和接收消息。'
    },
    {
      title: '账号验证',
      level: !accountStatusKnown ? 'warn' : verify ? 'warn' : a.status === 1 ? 'ok' : 'warn',
      text: !accountStatusKnown ? '状态未知' : verify ? accountStatus(a.status) : a.status === 1 ? '无需处理' : accountStatus(a.status),
      tip: !accountStatusKnown ? '账号状态未返回，请刷新资料后确认。' : verify ? '请先在闲鱼完成手机/人机验证，再回到系统刷新。' : a.status === 1 ? '当前账号状态可执行常规运营动作。' : '请确认账号状态后再执行运营动作。'
    },
    {
      title: '消息连接',
      level: wsState === true ? 'ok' : 'warn',
      text: wsState === true ? 'WebSocket 在线' : wsState === false ? '未连接' : '状态未知',
      tip: wsState === true ? '系统正在监听实时消息。' : wsState === false ? '自动回复前请启动连接，避免漏接买家消息。' : '请刷新连接状态后再决定是否启动或断开。'
    }
  ]
})

const recentActivitiesAvailable = computed(() => {
  const account = selected.value
  return !!account && (Array.isArray(account.recentActivities) || Array.isArray(account.activities))
})

const recentActivities = computed(() => {
  const account = selected.value || {}
  const backendActivities =
    account.recentActivities ||
    account.activities

  if (
    Array.isArray(backendActivities) &&
    backendActivities.length
  ) {
    return backendActivities
      .slice(0, 3)
      .map(item => ({
        time: activityTime(
          item.time ||
          item.createdTime ||
          item.updatedTime
        ),
        text:
          item.text ||
          item.title ||
          item.content ||
          '-'
      }))
  }

  // 无真实数据来源，返回空，待后端补全
  return []
})
function resetQrState() {
  qr.loading = false
  qr.sessionId = ''
  qr.qrUrl = ''
  qr.status = ''
  qr.message = ''
  qr.mode = 'create'
  qr.accountId = null
}

async function openModal(type){
  if (!await guardFeatureAction()) return
  if (!accountsAvailable.value) {
    error.value = '账号列表不可用，已禁用新增与扫码操作；请先重试加载。'
    return
  }
  modal.value = type
  if(type === 'manual') {
    manual.accountNote=''
    manual.cookie=''
    manualError.value=''
  }
  if(type === 'scan') {
    qr.mode = 'create'
    qr.accountId = null
    startQrLogin()
  }
}
function closeModal(){
  modal.value = ''
  faceVerificationError.value = ''
  autoRateError.value = ''
  autoRateLoaded.value = false
  loginCredentialError.value = ''
  loginCredentialLoaded.value = false
  accountStrategyError.value = ''
  accountStrategyLoaded.value = false
  unifiedConfigError.value = ''
  unifiedConfigSuccess.value = ''
  unifiedConfigTaskText.value = ''
  stopQrPolling()
  resetQrState()
}
function openRescanModal(account) {
  if (!account?.id) return
  modal.value = 'scan'
  qr.mode = 'rescan'
  qr.accountId = account.id
  startQrLogin()
}

function requireResponseObject(res, label) {
  const data = res?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error(`${label}响应格式异常`)
  }
  return data
}

function autoRateConfigOf(res) {
  const data = requireResponseObject(res, '自动评价配置')
  if (typeof data.enabled !== 'boolean' || !['text', 'api'].includes(data.rateType)) {
    throw new Error('自动评价配置缺少有效开关或评价方式')
  }
  if (typeof data.textContent !== 'string' || typeof data.apiUrl !== 'string') {
    throw new Error('自动评价配置内容响应格式异常')
  }
  // scheduleHour 兜底为 9（旧数据无此字段时使用默认）
  const sh = Number(data.scheduleHour)
  data.scheduleHour = Number.isFinite(sh) && sh >= 0 && sh <= 23 ? sh : 9
  return data
}

function strategyConfigOf(res) {
  const data = requireResponseObject(res, '账号策略配置')
  const messageExpireTime = Number(data.messageExpireTime)
  if (!Number.isFinite(messageExpireTime) || messageExpireTime < 0 || messageExpireTime > 86400) {
    throw new Error('账号策略等待时间响应格式异常')
  }
  if (typeof data.scheduledRedelivery !== 'boolean' || typeof data.autoPolish !== 'boolean') {
    throw new Error('账号策略开关响应格式异常')
  }
  return { ...data, messageExpireTime }
}

function loginCredentialConfigOf(res) {
  const data = requireResponseObject(res, '账号密码登录配置')
  if (data.loginUsername != null && typeof data.loginUsername !== 'string') {
    throw new Error('登录账号响应格式异常')
  }
  if (typeof data.hasLoginPassword !== 'boolean' || typeof data.showBrowser !== 'boolean') {
    throw new Error('账号密码登录状态响应格式异常')
  }
  return data
}

function accountAuthStatusOf(res) {
  const data = requireResponseObject(res, '登录校验')
  if (typeof data.usable !== 'boolean') throw new Error('登录校验响应缺少可用状态')
  if (data.cookieStatus != null && !Number.isFinite(Number(data.cookieStatus))) {
    throw new Error('登录校验 Cookie 状态响应格式异常')
  }
  return data
}

async function openFaceVerificationModal(account = selected.value) {
  if (!account?.id) return
  modal.value = 'faceVerify'
  faceVerificationLoading.value = true
  faceVerificationError.value = ''
  faceVerificationMarkingId.value = null
  try {
    const res = await getAccountFaceVerifications({ accountId: account.id, current: 1, size: 20 })
    faceVerificationItems.value = recordsOfOrThrow(res?.data, '人脸验证提醒响应格式异常')
  } catch (e) {
    faceVerificationItems.value = []
    faceVerificationError.value = e.message || '加载人脸验证提醒失败'
  } finally {
    faceVerificationLoading.value = false
  }
}
async function markFaceVerificationRead(item) {
  if (!item?.id || faceVerificationMarkingId.value) return
  faceVerificationMarkingId.value = item.id
  try {
    await markAccountFaceVerificationRead(item.id)
    item.readFlag = 1
  } catch (e) {
    faceVerificationError.value = e.message || '标记已读失败'
  } finally {
    faceVerificationMarkingId.value = null
  }
}
async function openAutoRateModal(account = selected.value) {
  if (!account?.id) return
  modal.value = 'autoRate'
  autoRateError.value = ''
  autoRateSaving.value = false
  autoRateLoaded.value = false
  autoRateForm.enabled = false
  autoRateForm.rateType = 'text'
  autoRateForm.textContent = ''
  autoRateForm.apiUrl = ''
  autoRateForm.scheduleHour = 9
  try {
    const res = await getAccountAutoRateConfig(account.id)
    const data = autoRateConfigOf(res)
    autoRateForm.enabled = data.enabled
    autoRateForm.rateType = data.rateType
    autoRateForm.textContent = data.textContent
    autoRateForm.apiUrl = data.apiUrl
    autoRateForm.scheduleHour = data.scheduleHour
    autoRateLoaded.value = true
  } catch (e) {
    autoRateError.value = e.message || '加载自动评价配置失败'
  }
}

async function saveAutoRateConfig() {
  if (!selected.value?.id || !autoRateLoaded.value || autoRateSaving.value) return
  autoRateError.value = ''
  if (autoRateForm.rateType === 'text' && !autoRateForm.textContent.trim()) {
    autoRateError.value = '请输入评价内容'
    return
  }
  if (autoRateForm.rateType === 'api' && !autoRateForm.apiUrl.trim()) {
    autoRateError.value = '请输入 API 地址'
    return
  }
  autoRateSaving.value = true
  try {
    const res = await saveAccountAutoRateConfig(selected.value.id, {
      enabled: autoRateForm.enabled,
      rateType: autoRateForm.rateType,
      textContent: autoRateForm.textContent.trim(),
      apiUrl: autoRateForm.apiUrl.trim(),
      scheduleHour: Number(autoRateForm.scheduleHour),
    })
    autoRateConfigOf(res)
    closeModal()
    qrSuccessMsg.value = '自动评价配置已保存'
    setTimeout(() => { if (qrSuccessMsg.value === '自动评价配置已保存') qrSuccessMsg.value = '' }, 4000)
    await loadAccounts()
  } catch (e) {
    autoRateError.value = e.message || '保存自动评价配置失败'
  } finally {
    autoRateSaving.value = false
  }
}

async function openLoginCredentialModal(account = selected.value) {
  if (!account?.id) return
  modal.value = 'loginCredential'
  loginCredentialError.value = ''
  loginCredentialSaving.value = false
  loginCredentialLoaded.value = false
  accountLoginCredentialForm.loginUsername = ''
  accountLoginCredentialForm.loginPassword = ''
  accountLoginCredentialForm.clearLoginPassword = false
  accountLoginCredentialForm.hasLoginPassword = false
  accountLoginCredentialForm.showBrowser = false
  try {
    const res = await getAccountLoginCredentialRequest(account.id)
    const data = loginCredentialConfigOf(res)
    accountLoginCredentialForm.loginUsername = data.loginUsername || ''
    accountLoginCredentialForm.hasLoginPassword = data.hasLoginPassword
    accountLoginCredentialForm.showBrowser = data.showBrowser
    loginCredentialLoaded.value = true
  } catch (e) {
    loginCredentialError.value = e.message || '加载账号密码登录配置失败'
  }
}

async function saveAccountLoginCredential() {
  if (!selected.value?.id || !loginCredentialLoaded.value || loginCredentialSaving.value) return
  loginCredentialError.value = ''
  const loginUsername = accountLoginCredentialForm.loginUsername.trim()
  const loginPassword = accountLoginCredentialForm.loginPassword.trim()
  if ((loginPassword || (!accountLoginCredentialForm.clearLoginPassword && accountLoginCredentialForm.hasLoginPassword)) && !loginUsername) {
    loginCredentialError.value = '请输入登录账号'
    return
  }
  loginCredentialSaving.value = true
  try {
    const res = await saveAccountLoginCredentialRequest(selected.value.id, {
      loginUsername: loginUsername || null,
      loginPassword: loginPassword || null,
      clearLoginPassword: accountLoginCredentialForm.clearLoginPassword,
      showBrowser: accountLoginCredentialForm.showBrowser,
    })
    const data = loginCredentialConfigOf(res)
    accountLoginCredentialForm.hasLoginPassword = data.hasLoginPassword
    closeModal()
    qrSuccessMsg.value = '账号密码登录配置已保存'
    setTimeout(() => { if (qrSuccessMsg.value === '账号密码登录配置已保存') qrSuccessMsg.value = '' }, 4000)
  } catch (e) {
    loginCredentialError.value = e.message || '保存账号密码登录配置失败'
  } finally {
    loginCredentialSaving.value = false
  }
}

async function openAccountStrategyModal(account = selected.value) {
  if (!account?.id) return
  modal.value = 'accountStrategy'
  accountStrategyError.value = ''
  accountStrategySaving.value = false
  accountStrategyLoaded.value = false
  accountStrategyForm.messageExpireTime = 3600
  accountStrategyForm.scheduledRedelivery = false
  accountStrategyForm.autoPolish = false
  try {
    const res = await getAccountStrategyConfigRequest(account.id)
    const data = strategyConfigOf(res)
    accountStrategyForm.messageExpireTime = data.messageExpireTime
    accountStrategyForm.scheduledRedelivery = data.scheduledRedelivery
    accountStrategyForm.autoPolish = data.autoPolish
    accountStrategyLoaded.value = true
  } catch (e) {
    accountStrategyError.value = e.message || '加载账号策略配置失败'
  }
}

async function saveAccountStrategyConfig() {
  if (!selected.value?.id || !accountStrategyLoaded.value || accountStrategySaving.value) return
  accountStrategyError.value = ''
  const messageExpireTime = Number(accountStrategyForm.messageExpireTime)
  if (!Number.isFinite(messageExpireTime) || messageExpireTime < 0 || messageExpireTime > 86400) {
    accountStrategyError.value = '消息等待时间需在 0 到 86400 秒之间'
    return
  }
  accountStrategySaving.value = true
  try {
    const res = await saveAccountStrategyConfigRequest(selected.value.id, {
      messageExpireTime: Math.round(messageExpireTime),
      scheduledRedelivery: accountStrategyForm.scheduledRedelivery,
      autoPolish: accountStrategyForm.autoPolish,
    })
    strategyConfigOf(res)
    closeModal()
    qrSuccessMsg.value = '账号策略已保存'
    setTimeout(() => { if (qrSuccessMsg.value === '账号策略已保存') qrSuccessMsg.value = '' }, 4000)
    await loadAccounts()
  } catch (e) {
    accountStrategyError.value = e.message || '保存账号策略失败'
  } finally {
    accountStrategySaving.value = false
  }
}

function openUnifiedConfigModal(account = selected.value) {
  if (!account?.id) return
  unifiedConfigError.value = ''
  unifiedConfigSuccess.value = ''
  unifiedConfigTaskText.value = ''
  modal.value = 'unifiedConfig'
}

function visibleAccountsForUnifiedConfig() {
  return accounts.value.filter(account => Number(account?.id) > 0)
}

async function applyUnifiedAction(taskText, runner) {
  if (unifiedConfigBusy.value) return
  const visibleAccounts = visibleAccountsForUnifiedConfig()
  if (!selected.value?.id) {
    unifiedConfigError.value = '请先选择一个基准账号'
    return
  }
  if (visibleAccounts.length === 0) {
    unifiedConfigError.value = '当前页面没有可处理的账号'
    return
  }
  unifiedConfigBusy.value = true
  unifiedConfigError.value = ''
  unifiedConfigSuccess.value = ''
  unifiedConfigTaskText.value = taskText
  try {
    const summary = await runner(visibleAccounts)
    const failed = Number(summary?.failed || 0)
    const success = Number(summary?.success || 0)
    unifiedConfigSuccess.value = `${taskText}完成，成功 ${success} 个账号${failed ? `，失败 ${failed} 个` : ''}`
    if (summary?.message) {
      unifiedConfigError.value = summary.message
    }
    await loadAccounts()
  } catch (e) {
    unifiedConfigError.value = e.message || `${taskText}失败`
  } finally {
    unifiedConfigBusy.value = false
    unifiedConfigTaskText.value = ''
  }
}

async function applyCurrentAutoRateToVisibleAccounts() {
  await applyUnifiedAction('同步自动评价', async (visibleAccounts) => {
    const sourceRes = await getAccountAutoRateConfig(selected.value.id)
    const source = autoRateConfigOf(sourceRes)
    const payload = {
      enabled: source.enabled,
      rateType: source.rateType,
      textContent: source.textContent,
      apiUrl: source.apiUrl,
      scheduleHour: Number(source.scheduleHour),
    }
    let success = 0
    let failed = 0
    const errors = []
    for (const account of visibleAccounts) {
      try {
        await saveAccountAutoRateConfig(account.id, payload)
        success += 1
      } catch (e) {
        failed += 1
        errors.push(`${accountTitle(account)}: ${e.message || '保存失败'}`)
      }
    }
    return {
      success,
      failed,
      message: errors.slice(0, 3).join('; '),
    }
  })
}

async function applyCurrentStrategyToVisibleAccounts() {
  await applyUnifiedAction('同步消息等待', async (visibleAccounts) => {
    const sourceRes = await getAccountStrategyConfigRequest(selected.value.id)
    const source = strategyConfigOf(sourceRes)
    const payload = {
      messageExpireTime: source.messageExpireTime,
      scheduledRedelivery: source.scheduledRedelivery,
      autoPolish: source.autoPolish,
    }
    let success = 0
    let failed = 0
    const errors = []
    for (const account of visibleAccounts) {
      try {
        await saveAccountStrategyConfigRequest(account.id, payload)
        success += 1
      } catch (e) {
        failed += 1
        errors.push(`${accountTitle(account)}: ${e.message || '保存失败'}`)
      }
    }
    return {
      success,
      failed,
      message: errors.slice(0, 3).join('; '),
    }
  })
}

async function runBatchAuthCheckForVisibleAccounts() {
  await applyUnifiedAction('统一登录校验', async (visibleAccounts) => {
    let success = 0
    let failed = 0
    const errors = []
    for (const account of visibleAccounts) {
      try {
        const data = accountAuthStatusOf(await checkAccountAuth(account.id))
        // 后端在登录失效时返回 200 + {usable:false}，必须以 usable 为准
        if (data.usable === true) {
          success += 1
        } else {
          failed += 1
          errors.push(`${accountTitle(account)}: ${data.loginStatusMessage || '登录校验未通过'}`)
        }
      } catch (e) {
        failed += 1
        errors.push(`${accountTitle(account)}: ${e.message || '校验失败'}`)
      }
    }
    return {
      success,
      failed,
      message: errors.slice(0, 3).join('; '),
    }
  })
}

function handleHeaderAction(e){ if(e.detail === 'refresh-accounts') return loadAccounts(); if(e.detail === 'open-scan-account') openModal('scan'); if(e.detail === 'open-manual-account') openModal('manual') }

const cols=[{key:'account',title:'账号信息'},{key:'uid',title:'UID'},{key:'area',title:'地区'},{key:'level',title:'等级'},{key:'status',title:'账号状态'},{key:'health',title:'账号健康'},{key:'cookie',title:'Cookie状态'},{key:'ws',title:'WS状态'},{key:'sync',title:'资料同步'},{key:'op',title:'操作'}]

const rowClass = (row) => row.raw?.id === selectedId.value ? 'row-selected' : ''

const rows = computed(() => {
  const kw = (debouncedKeyword.value || '').trim().toLowerCase()
  const searchFields = ['nickname', 'displayName', 'accountNote', 'externalUid', 'unb', 'province', 'city', 'ipLocation', 'remark']
  return accounts.value
  .filter(a => {
    const ws = wsMap[a.id] || {}
    // 状态筛选
    if (statusFilter.value === 'normal' && a.status !== 1) return false
    if (statusFilter.value === 'verify' && a.status !== -1 && a.status !== -2) return false
    if (statusFilter.value === 'cookieWarn' && accountAuthUsable(a, ws)) return false
    if (statusFilter.value === 'wsOnline' && !ws.connected) return false
    // 关键词筛选
    if (!kw) return true
    // 仅匹配用户可见字段，避免匹配 id/时间戳等无关字段导致搜索结果不准
    return searchFields.some(f => String(a[f] || '').toLowerCase().includes(kw))
  })
  .map(a => {
    const ws = wsMap[a.id] || {}
    return {
      raw: a,
      name: accountTitle(a),
      avatar: resolveAvatarUrl(a.avatarUrl || a.avatar || ''),
      tag: a.accountNote && (a.nickname || a.displayName) ? (a.nickname || a.displayName) : '',
      uid: a.externalUid || a.unb || a.id,
      area: a.province && a.city ? `${a.province} ${a.city}` : (a.ipLocation || a.province || '-'),
      level: a.accountLevel || a.sellerLevel || a.fishShopLevel || '-',
      statusText: accountStatus(a.status),
      statusType: a.status === 1 ? 'green' : 'orange',
      health: accountHealth(a),
      cookie: accountCookieLabel(a, ws),
      cookieType: accountCookieBadgeType(a, ws),
      ws: accountWsConnectionState(a, ws) === true ? '在线' : accountWsConnectionState(a, ws) === false ? '离线' : '状态未知',
      wsState: accountWsConnectionState(a, ws),
      sync: a.lastSyncTime || a.profileUpdatedTime || a.updatedTime || '-'
    }
  })
})

// 账号详情头像：清洗 URL，过滤脏数据/历史格式 {avatar=http://...}，避免 <img> 加载失败
const selectedAvatarUrl = computed(() => {
  if (!selected.value) return ''
  const raw = selected.value.avatarUrl || selected.value.avatar || ''
  return resolveAvatarUrl(raw)
})

// 详情头像加载失败时清空 src，触发 v-if 切换到占位 div
function onDetailAvatarError(e) {
  if (e?.target) e.target.style.display = 'none'
}

// 列表头像加载失败时隐藏 img，露出底层占位 div 背景
function onListAvatarError(e) {
  if (e?.target) e.target.style.display = 'none'
}

const stats = computed(() => {
  const accountStatusKnown = accounts.value.every(account => account.status !== null && account.status !== undefined)
  const wsStates = accounts.value.map(account => accountWsConnectionState(account, wsMap[account.id] || {}))
  const cookieTypes = accounts.value.map(account => accountCookieBadgeType(account, wsMap[account.id] || {}))
  return {
    total: total.value,
    normal: accountStatusKnown ? accounts.value.filter(a => a.status === 1).length : null,
    verify: accountStatusKnown ? accounts.value.filter(a => a.status === -1 || a.status === -2).length : null,
    wsOnline: wsStates.some(state => state === null) ? null : wsStates.filter(state => state === true).length,
    cookieWarn: cookieTypes.includes('gray') ? null : cookieTypes.filter(type => ['red', 'orange'].includes(type)).length
  }
})
function accountMetric(value) { return accountsAvailable.value && value !== null && value !== undefined ? value : '—' }
function wsActionText(state) { return state === true ? '断开' : state === false ? '连接' : '刷新连接状态' }

async function loadAccounts() {
  loading.value = true
  error.value = ''
  accountsLoadError.value = ''
  accountsAvailable.value = false
  accounts.value = []
  total.value = 0
  selected.value = null
  selectedId.value = null
  // 不再清空全部 wsMap，保留现有账号的 WS 状态缓存，避免刷新列表时其他账号显示离线
  try {
    const res = await getLiteAccounts({ current: current.value, size: pageSize.value }, { force: true })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    const rawTotal = data?.total ?? data?.totalCount ?? data?.count ?? list.length
    const parsedTotal = Number(rawTotal)
    total.value = Number.isFinite(parsedTotal) && parsedTotal >= 0 ? parsedTotal : list.length
    accountsAvailable.value = true
    // 仅移除不再存在于账号列表中的 wsMap 缓存条目
    const currentIds = new Set(list.map(a => Number(a.id)))
    for (const key of Object.keys(wsMap)) {
      if (!currentIds.has(Number(key))) {
        delete wsMap[key]
      }
    }
    return true
  } catch (e) {
    accountsLoadError.value = e?.message || '账号列表加载失败'
    return false
  } finally {
    loading.value = false
  }
}

async function refreshUncachedWsStatus() {
  if (!accountsAvailable.value || !accounts.value.length) return
  const uncached = accounts.value.filter(a => {
    const ws = wsMap[a.id]
    return !ws || !Object.prototype.hasOwnProperty.call(ws, 'connected')
  })
  if (!uncached.length) return
  // 并发刷新未缓存的 WS 状态，每批最多 5 个
  const batchSize = 5
  for (let i = 0; i < uncached.length; i += batchSize) {
    const batch = uncached.slice(i, i + batchSize)
    await Promise.allSettled(batch.map(async a => {
      try {
        const res = await websocketStatus(a.id)
        const data = res?.data
        if (!data || typeof data !== 'object' || Array.isArray(data)) return
        // 仅缓存 connected=true 的结果，或 DB ws_status=0 时缓存 connected=false
        // 避免在 WS 重连窗口期缓存 connected=false 导致 DB ws_status=1 的账号误显示离线
        if (data.connected === true) {
          wsMap[a.id] = data
        } else {
          const dbWsStatus = Number(a.wsStatus ?? a.ws_status)
          if (dbWsStatus === 0) {
            wsMap[a.id] = data
          }
          // else: connected=false 但 DB ws_status=1，不缓存，让显示回退到 DB 的在线状态
        }
      } catch {
        // 查询失败不缓存，让显示回退到 DB ws_status
      }
    }))
  }
}

// 进入页面时主动校验当前页账号的 cookie 实时状态。
// 仅依赖 DB 缓存的 cookie_status 会导致 cookie 已失效但 DB 未更新时账号卡片仍显示"正常"，
// 用户必须点击发布/搜索才被动发现问题。这里在 onMounted 后异步批量调用 /check-auth
// 实时探活，把最新结果直接更新到 accounts / selected，让 UI 立即反映真实状态。
// 失败静默处理（不阻塞页面加载、不弹错误），仅刷新成功的账号。
async function refreshVisibleAccountsAuthOnPageEnter() {
  if (!accountsAvailable.value || !accounts.value.length) return
  const targets = accounts.value.slice()
  const batchSize = 5
  for (let i = 0; i < targets.length; i += batchSize) {
    const batch = targets.slice(i, i + batchSize)
    await Promise.allSettled(batch.map(async (account) => {
      try {
        const data = accountAuthStatusOf(await checkAccountAuth(account.id))
        const target = accounts.value.find(item => item.id === account.id)
        if (!target) return
        target.cookieStatus = data.cookieStatus
        target.authUsable = data.usable
        target.loginStatusCode = data.loginStatusCode
        target.loginStatusMessage = data.loginStatusMessage
        target.loginCheckTime = data.checkedAt
        if (selected.value?.id === target.id) {
          selected.value = { ...selected.value, ...target }
        }
      } catch {
        // 单个账号校验失败不阻塞其他账号；UI 仍显示 DB 缓存状态
      }
    }))
  }
}

function goPage(p) {
  current.value = p
  loadAccounts()
}

async function selectAccount(account) {
  if (!accountsAvailable.value || !account?.id) return
  selected.value = account
  selectedId.value = account.id
  loadWsStatus(account.id)

  if (selected.value?.__detailLoaded) {
    return
  }

  try {
    const res = await getAccountDetail(account.id)
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)) throw new Error('账号详情响应格式异常')
    if (selectedId.value === account.id) {
      selected.value = {
        ...(selected.value || {}),
        ...res.data,
        __detailLoaded: true,
      }
    }
  } catch (detailError) {
    error.value = detailError?.message || '账号详情加载失败'
  }
}

async function loadWsStatus(accountId) {
  if (!accountId) return
  try {
    const res = await websocketStatus(accountId)
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)) throw new Error('连接状态响应格式异常')
    wsMap[accountId] = res.data
    return true
  } catch (e) {
    wsMap[accountId] = { connected: null, status: '状态未知', lastError: e?.message || '连接状态加载失败' }
    return false
  }
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function refreshAccountAuthBeforeConnect(accountId) {
  if (!accountId) return null
  const res = await checkAccountAuth(accountId)
  const data = accountAuthStatusOf(res)
  const account = accounts.value.find(item => item.id === accountId)
  if (account) {
    account.cookieStatus = data.cookieStatus
    account.authUsable = data.usable
    account.loginStatusCode = data.loginStatusCode
    account.loginStatusMessage = data.loginStatusMessage
    account.loginCheckTime = data.checkedAt
  }
  if (selected.value?.id === account?.id) {
    selected.value = { ...selected.value, ...account }
  }
  return data
}

async function refreshAccountAfterQrConfirmed(accountId, { pollWs = false } = {}) {
  if (!accountId) return
  const intervals = pollWs ? [0, 1200, 2600, 5200] : [0]
  for (const waitMs of intervals) {
    if (waitMs > 0) {
      await delay(waitMs)
    }
    try {
      await refreshAccountAuthBeforeConnect(accountId)
    } catch (authErr) {
      console.warn('扫码后刷新统一登录状态失败:', authErr)
    }
    try {
      await loadWsStatus(accountId)
    } catch (wsErr) {
      console.warn('扫码后刷新 WS 状态失败:', wsErr)
    }
    const ws = wsMap[accountId] || {}
    const phase = String(ws.status || '').toLowerCase()
    if (ws.connected || ['connected', 'already_connected', 'connecting', 'recovering'].includes(phase)) {
      break
    }
  }
}

async function checkSelectedAuth() {
  if (!selected.value?.id) return
  try {
    const res = await checkAccountAuth(selected.value.id)
    const data = accountAuthStatusOf(res)
    const account = accounts.value.find(item => item.id === selected.value.id)
    if (account) {
      account.cookieStatus = data.cookieStatus
      account.authUsable = data.usable
      account.loginStatusCode = data.loginStatusCode
      account.loginStatusMessage = data.loginStatusMessage
      account.loginCheckTime = data.checkedAt
    }
    if (selected.value?.id === account?.id) {
      selected.value = { ...selected.value, ...account }
    }
    qrSuccessMsg.value = data.loginStatusMessage || '登录校验已完成'
    setTimeout(() => {
      if (qrSuccessMsg.value === (data.loginStatusMessage || '登录校验已完成')) qrSuccessMsg.value = ''
    }, 4000)
    await loadAccounts()
  } catch (e) {
    error.value = e.message || '登录校验失败'
  }
}

async function refreshProfile(accountId) {
  try {
    error.value = ''
    const res = await refreshAccountProfile(accountId)
    const data = requireResponseObject(res, '账号资料刷新')
    // 刷新成功后的提示
    const displayName = data.displayName || data.nickname || ''
    qrSuccessMsg.value = displayName ? `资料刷新成功: ${displayName}` : '资料刷新成功'
    setTimeout(() => { if (qrSuccessMsg.value && qrSuccessMsg.value.startsWith('资料刷新')) qrSuccessMsg.value = '' }, 4000)
    // 更新选中账号的详情
    if (selected.value && selected.value.id === accountId) {
      selected.value = { ...selected.value, ...data }
    }
    await loadAccounts()
  } catch (e) {
    error.value = e.message || '刷新资料失败'
  }
}

function isWsBusy(accountId) { return !!wsBusyMap[accountId] }

async function toggleWs(account) {
  if (!accountsAvailable.value || !account?.id || isWsBusy(account.id)) return
  wsBusyMap[account.id] = true
  error.value = ''
  try {
    let current = wsMap[account.id] || {}
    let connectionState = accountWsConnectionState(account, current)
    if (connectionState === null) {
      await loadWsStatus(account.id)
      current = wsMap[account.id] || {}
      connectionState = accountWsConnectionState(account, current)
      if (connectionState === null) throw new Error('连接状态仍不可用，已阻止启动或断开操作')
    }
    if (connectionState === true) {
      await stopWebSocket(account.id)
      qrSuccessMsg.value = '已提交断开连接请求'
    } else {
      const auth = await refreshAccountAuthBeforeConnect(account.id)
      if (auth?.usable === false && auth?.loginStatusMessage) {
        qrSuccessMsg.value = `${auth.loginStatusMessage}，继续尝试恢复连接...`
      }
      const res = await startWebSocket(account.id, { forceReconnect: true })
      const data = requireResponseObject(res, 'WebSocket 启动')
      if (typeof data.connected !== 'boolean') throw new Error('WebSocket 启动响应缺少连接状态')
      if (data.connected === true) {
        wsMap[account.id] = data
        qrSuccessMsg.value = data.optimistic ? 'WS 连接已提交，未检测到滑块/验证' : 'WS 连接已就绪，正在接收消息'
      } else {
        qrSuccessMsg.value = data.message || '连接请求返回未连接状态，请刷新后确认'
      }
      if (data.optimistic) {
        setTimeout(() => loadWsStatus(account.id), 8000)
      }
    }
    setTimeout(() => { if (qrSuccessMsg.value?.includes('连接') || qrSuccessMsg.value?.includes('建立') || qrSuccessMsg.value?.includes('WS 连接') || qrSuccessMsg.value?.includes('断开连接')) qrSuccessMsg.value = '' }, 5000)
    if (!wsMap[account.id]?.optimistic) {
      await new Promise(resolve => setTimeout(resolve, connectionState === true ? 300 : 1200))
      await loadWsStatus(account.id)
    }
  } catch (e) {
    error.value = e.message || 'WebSocket 操作失败'
  } finally {
    wsBusyMap[account.id] = false
  }
}

// ============================================================
// 滑块求解成功后自动连接 WebSocket + 实时刷新连接状态
// ============================================================
// WS 连接状态轮询定时器（求解成功后自动连接时使用，实时刷新连接状态）
const wsPollTimers = {}

function stopWsPolling(accountId) {
  const key = String(accountId)
  if (wsPollTimers[key]) {
    clearInterval(wsPollTimers[key])
    delete wsPollTimers[key]
  }
}

// 轮询刷新 WS 连接状态，直到状态稳定（已连接或失败终态）
function pollWsStatusUntilStable(accountId, { intervalMs = 2500, maxRounds = 8, onStable } = {}) {
  if (!accountId) return
  const key = String(accountId)
  stopWsPolling(accountId)  // 避免重复轮询
  let round = 0
  const tick = async () => {
    round++
    try {
      await loadWsStatus(accountId)
    } catch { /* 忽略单次查询失败 */ }
    const ws = wsMap[accountId] || {}
    const phase = String(ws.status || '').toLowerCase()
    const stable = ws.connected === true
      || ['disconnected', 'stopped', 'auth_failed', 'token_failed', 'register_failed', 'expired'].includes(phase)
    if (stable || round >= maxRounds) {
      stopWsPolling(accountId)
      if (typeof onStable === 'function') onStable(ws)
    }
  }
  tick()  // 立即先查一次
  wsPollTimers[key] = setInterval(tick, intervalMs)
}

// 滑块求解成功后自动连接 WebSocket，并实时刷新连接状态
async function autoConnectWsAfterSolve(account) {
  if (!account?.id) return
  const accountId = account.id
  // 已连接或已在处理中（如用户手动点了连接）则跳过
  if (wsMap[accountId]?.connected === true) return
  if (isWsBusy(accountId)) return
  wsBusyMap[accountId] = true
  autoConnectingWs.add(accountId)
  try {
    // 求解刚恢复 Cookie，刷新本地鉴权状态
    await refreshAccountAuthBeforeConnect(accountId)
    // 启动 WebSocket 连接
    const res = await startWebSocket(accountId, { forceReconnect: true })
    const data = requireResponseObject(res, 'WebSocket 启动')
    if (typeof data.connected === 'boolean') {
      wsMap[accountId] = data
    }
    qrSuccessMsg.value = data.connected
      ? (data.optimistic ? '滑块求解成功，正在自动连接 WebSocket…' : '滑块求解成功，WebSocket 已连接')
      : (data.message || '正在自动连接 WebSocket…')
    setTimeout(() => {
      if (qrSuccessMsg.value?.includes('自动连接') || qrSuccessMsg.value?.includes('WebSocket 已连接')) qrSuccessMsg.value = ''
    }, 5000)
    // 实时刷新连接状态直到稳定；轮询结束后清除自动连接标记
    pollWsStatusUntilStable(accountId, {
      onStable: () => autoConnectingWs.delete(accountId),
    })
  } catch (e) {
    // 静默处理，不打断求解成功的提示；用户仍可手动点击"连接"
    autoConnectingWs.delete(accountId)
    console.warn('求解成功后自动连接 WebSocket 失败:', e)
  } finally {
    wsBusyMap[accountId] = false
  }
}

async function removeAccount(accountId) {
  pendingDeleteId.value = accountId
  modal.value = 'confirmDelete'
}

async function executeDelete() {
  if (pendingDeleteId.value === null) return
  const id = pendingDeleteId.value
  pendingDeleteId.value = null
  closeModal()
  try {
    await deleteAccount(id)
    if (selected.value?.id === id) selected.value = null
    await loadAccounts()
  } catch (e) {
    error.value = e.message || '删除失败'
  }
}

let handleItemPolish

function showPolishMessage(message) {
  qrSuccessMsg.value = message || '擦亮完成'
  setTimeout(() => {
    if (qrSuccessMsg.value && qrSuccessMsg.value.startsWith('擦亮')) qrSuccessMsg.value = ''
  }, 5000)
}

function stopPolishPolling(resetTaskId = true) {
  if (polishTimer) {
    clearInterval(polishTimer)
    polishTimer = null
  }
  if (resetTaskId) polishTaskId = ''
}

function applyPolishTerminalState(data) {
  stopPolishPolling()
  polishingAccountId.value = null

  if (data?.needManual || data?.status === 'need_manual') {
    error.value = data.message || '擦亮暂停：检测到风控，请完成滑块验证后重试'
    return
  }

  if (data.status === 'failed' || data.status === 'not_found') {
    error.value = data?.message || '擦亮失败'
    return
  }

  if (data.status !== 'completed') {
    error.value = '擦亮任务返回未知终态，完成状态未确认'
    return
  }

  showPolishMessage(data.message || `擦亮完成：成功 ${data.polished}，失败 ${data.failed}`)
}

function polishTaskDataOf(response) {
  const data = requireResponseObject(response, '擦亮任务')
  const knownStatuses = ['queued', 'running', 'completed', 'failed', 'need_manual', 'not_found']
  if (!knownStatuses.includes(data.status) || typeof data.running !== 'boolean') {
    throw new Error('擦亮任务响应缺少有效状态')
  }
  if (['queued', 'running'].includes(data.status) && !String(data.taskId || '').trim()) {
    throw new Error('擦亮任务响应缺少任务编号')
  }
  if (data.status === 'completed') {
    const polished = Number(data.polished)
    const failed = Number(data.failed)
    if (!Number.isFinite(polished) || polished < 0 || !Number.isFinite(failed) || failed < 0) {
      throw new Error('擦亮完成结果缺少有效统计')
    }
    return { ...data, polished, failed }
  }
  return data
}

function startPolishPolling(accountId, taskId) {
  stopPolishPolling(false)
  polishTaskId = taskId
  let polling = false

  const poll = async () => {
    if (!polishTaskId || polling) return
    polling = true
    try {
      const response = await getItemPolishProgress(polishTaskId)
      const data = polishTaskDataOf(response)
      if (data.running || data.status === 'queued' || data.status === 'running') return
      applyPolishTerminalState(data)
    } catch (e) {
      stopPolishPolling()
      polishingAccountId.value = null
      error.value = '擦亮失败: ' + (e.message || '未知错误')
    } finally {
      polling = false
    }
  }

  polishingAccountId.value = accountId
  polishTimer = setInterval(() => { void poll() }, 1500)
  setTimeout(() => { void poll() }, 300)
}

const handleItemPolishWithProgress = async (account) => {
  if (!account?.id) return
  if (polishingAccountId.value && polishingAccountId.value !== account.id) {
    error.value = '请等待当前擦亮任务完成后再操作其他账号'
    return
  }

  polishingAccountId.value = account.id
  error.value = ''
  try {
    const response = await runItemPolish(account.id)
    const data = polishTaskDataOf(response)

    if (data.taskId && (data.running || data.status === 'queued' || data.status === 'running')) {
      showPolishMessage(data.message || '擦亮任务已提交，后台处理中')
      startPolishPolling(account.id, data.taskId)
      return
    }

    applyPolishTerminalState(data)
  } catch (e) {
    stopPolishPolling()
    polishingAccountId.value = null
    error.value = '擦亮失败: ' + (e.message || '未知错误')
  }
}

handleItemPolish = handleItemPolishWithProgress

async function submitManual() {
  if (!await guardFeatureAction()) return
  manualError.value = ''
  if (!manual.cookie.trim()) return (manualError.value = '请输入 Cookie 字符串')
  // 前端预校验
  const validation = validateCookie(manual.cookie)
  if (!validation.valid) {
    manualError.value = validation.error
    return
  }
  submitting.value = true
  try {
    const keyFields = extractKeyFields(manual.cookie)
    await createAccountByCookie({
      accountNote: manual.accountNote.trim(),
      cookie: manual.cookie.trim(),
      extractedUnb: keyFields.unb,
      extractedMH5Tk: keyFields.mH5Tk,
    })
    closeModal()
    await loadAccounts()
  } catch (e) {
    manualError.value = e.message || '添加账号失败'
  } finally {
    submitting.value = false
  }
}

async function openCookieEdit(account) {
  if (!account) return
  cookieEdit.accountId = account.id
  cookieEdit.cookie = ''
  cookieEditError.value = ''
  cookieEditSubmitting.value = false
  cookieEditLoading.value = true
  modal.value = 'cookieEdit'
  // 回填当前 Cookie，便于用户复制或微调
  try {
    const res = await getAccountCookie(account.id)
    const data = requireResponseObject(res, '账号 Cookie')
    const current = typeof data.cookie === 'string' ? data.cookie : ''
    cookieEdit.cookie = current
    if (!current) {
      cookieEditError.value = '该账号暂无 Cookie 记录，请粘贴新的 Cookie 字符串'
    }
  } catch (e) {
    cookieEditError.value = e?.message || '加载当前 Cookie 失败，请直接粘贴新 Cookie'
  } finally {
    cookieEditLoading.value = false
  }
}

async function submitCookieEdit() {
  cookieEditError.value = ''
  if (!cookieEdit.cookie.trim()) {
    cookieEditError.value = '请输入 Cookie 字符串'
    return
  }
  // 前端预校验
  const validation = validateCookie(cookieEdit.cookie)
  if (!validation.valid) {
    cookieEditError.value = validation.error
    return
  }
  // 身份校验（防串号）
  if (selected.value) {
    const keyFields = extractKeyFields(cookieEdit.cookie)
    const identity = checkIdentity(keyFields.unb, selected.value)
    if (!identity.valid) {
      cookieEditError.value = identity.error
      return
    }
  }
  cookieEditSubmitting.value = true
  try {
    // 提取关键字段一并传给后端
    const keyFields = extractKeyFields(cookieEdit.cookie)
    await updateAccountCookie(cookieEdit.accountId, cookieEdit.cookie.trim(), {
      unb: keyFields.unb,
      mH5Tk: keyFields.mH5Tk,
    })
    closeModal()
    qrSuccessMsg.value = 'Cookie 更新成功'
    setTimeout(() => { if (qrSuccessMsg.value === 'Cookie 更新成功') qrSuccessMsg.value = '' }, 4000)
    await loadAccounts()
  } catch (e) {
    cookieEditError.value = e.message || '更新 Cookie 失败'
  } finally {
    cookieEditSubmitting.value = false
  }
}

async function copyCookieEdit() {
  if (!cookieEdit.cookie) return
  try {
    await navigator.clipboard.writeText(cookieEdit.cookie)
    qrSuccessMsg.value = '当前 Cookie 已复制'
    setTimeout(() => { if (qrSuccessMsg.value === '当前 Cookie 已复制') qrSuccessMsg.value = '' }, 2500)
  } catch {
    cookieEditError.value = '复制失败，请手动选中文本框内容复制'
  }
}

async function startQrLogin() {
  if (!await guardFeatureAction()) return
  qr.loading = true
  qr.message = ''
  qr.qrUrl = ''
  qr.sessionId = ''
  qr.status = ''
  stopQrPolling()
  try {
    const res = qr.accountId
      ? await generateQrLogin({ accountId: qr.accountId })
      : await generateQrLogin()
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('二维码响应格式异常')
    qr.sessionId = data.sessionId || data.id || ''
    qr.qrUrl = data.qrCodeBase64 || data.qrImage || data.qrUrl || data.qrcodeUrl || data.qrCodeUrl || data.url || ''
    if (!qr.sessionId) throw new Error('二维码响应缺少登录会话编号')
    if (!qr.qrUrl) throw new Error('二维码响应缺少可扫描内容，请检查登录服务配置')
    if (!['pending', 'scanned'].includes(data.status)) throw new Error('二维码响应缺少有效登录状态')
    qr.status = data.status
    qr.message = data.message || '请使用闲鱼 App 扫码'
    if (qr.sessionId) startQrPolling()
  } catch (e) {
    qr.status = 'error'
    qr.qrUrl = ''
    qr.sessionId = ''
    qr.message = e.message || '生成二维码失败'
  } finally {
    qr.loading = false
  }
}

function startQrPolling() {
  stopQrPolling()
  qrTimer = setInterval(checkQrStatus, 2000)
}
function stopQrPolling() { if (qrTimer) { clearInterval(qrTimer); qrTimer = null } }
async function checkQrStatus() {
  if (!qr.sessionId) return
  try {
    const res = qr.accountId
      ? await getQrLoginStatus(qr.sessionId, { accountId: qr.accountId })
      : await getQrLoginStatus(qr.sessionId)
    const data = requireResponseObject(res, '扫码登录状态')
    const knownStatuses = ['pending', 'scanned', 'confirmed', 'expired', 'failed', 'cancelled', 'verification_required']
    if (!knownStatuses.includes(data.status)) throw new Error('扫码登录状态响应格式异常')
    const prevStatus = qr.status
    qr.status = data.status
    qr.message = data.message || qr.message

    if (qr.status === 'confirmed') {
      const confirmedAccountId = Number(data.accountId || qr.accountId || 0)
      if (confirmedAccountId) {
        stopQrPolling()
        const isRescan = qr.mode === 'rescan'
        closeModal()
        const externalUid = data.externalUid || data.unb || ''
        qrSuccessMsg.value = data.authUsable === true
          ? (data.message || (externalUid ? `账号 ${externalUid.slice(0, 8)}... 登录成功` : '账号登录成功'))
          : data.authUsable === false
            ? (data.loginStatusMessage || '扫码已确认，但统一登录校验未通过')
            : '账号已保存，但登录可用状态未确认，请刷新账号状态'
        if (isRescan && data.authUsable === true && !data.message) qrSuccessMsg.value = '账号 Cookie 已更新并通过登录校验'
        try {
          await loadAccounts()
          await refreshAccountAfterQrConfirmed(confirmedAccountId, { pollWs: isRescan })
          // 刷新其他未缓存账号的 WS 状态，确保所有账号显示实时状态
          refreshUncachedWsStatus()
        } catch (listErr) {
          console.warn('账号列表刷新失败:', listErr)
          qrSuccessMsg.value = '账号已保存，但列表刷新失败，请手动刷新'
        }
        setTimeout(() => { if (qrSuccessMsg.value) qrSuccessMsg.value = '' }, 6000)
      } else if (prevStatus !== 'confirmed') {
        throw new Error('扫码已确认，但服务端未完成账号保存，请重新生成二维码后重试')
      }
    }
    if (qr.status === 'error') {
      stopQrPolling()
      qr.message = data.message || '账号保存失败，请重试'
      if (data.errorCode) {
        console.warn('扫码保存错误码:', data.errorCode)
      }
    }
    if (['expired', 'failed', 'cancelled'].includes(qr.status)) stopQrPolling()
  } catch (e) {
    stopQrPolling()
    qr.status = 'error'
    qr.message = e.message || '查询扫码状态失败'
  }
}

function handleSseEvent(e) {
  const event = e.detail
  if (!event) return
  if (event.type === 'account_added') {
    qrSuccessMsg.value = '账号登录成功'
    loadAccounts().then(() => refreshUncachedWsStatus())
    setTimeout(() => { qrSuccessMsg.value = '' }, 4000)
  } else if (event.type === 'cookie_status_changed') {
    // 从服务端重新拉取账号列表，确保 cookie 状态与后端一致
    const targetId = event.accountId
    const newStatus = Number(event.cookieStatus)
    if (!targetId || ![0, 1, 2].includes(newStatus)) {
      console.warn('[Accounts] 忽略格式异常的 Cookie 状态事件', event)
      return
    }
    // Cookie 失效时清除该账号的 WS 状态缓存，让显示回退到 DB 的 ws_status=0
    if (newStatus === 0) {
      delete wsMap[targetId]
    }
    // 优先使用后端推送的 loginStatusCode / loginStatusMessage（滑块求解场景会携带）
    const eventStatusCode = event.loginStatusCode || (Number(newStatus) === 1 ? 'OK' : 'COOKIE_EXPIRED')
    const eventStatusMessage = event.loginStatusMessage || (Number(newStatus) === 1 ? '账号登录状态正常' : 'Cookie 已失效，请重新登录闲鱼账号')
    // 先更新本地缓存，避免列表闪现旧状态
    const account = accounts.value.find(a => String(a.id) === String(targetId))
    if (account) {
      account.cookieStatus = newStatus
      account.authUsable = Number(newStatus) === 1
      account.loginStatusCode = eventStatusCode
      account.loginStatusMessage = eventStatusMessage
      if (selected.value && String(selected.value.id) === String(targetId)) {
        selected.value.cookieStatus = newStatus
        selected.value.authUsable = Number(newStatus) === 1
        selected.value.loginStatusCode = eventStatusCode
        selected.value.loginStatusMessage = eventStatusMessage
      }
    }
    // 显示提示信息（滑块求解中的 VERIFYING 状态不显示顶部提示，避免与求解横幅重复）
    if (newStatus === 0 && eventStatusCode !== 'VERIFYING') {
      qrSuccessMsg.value = `账号 ${targetId} Cookie 已失效（可能遇到滑块验证），请更换 Cookie 或重新扫码登录`
      setTimeout(() => { if (qrSuccessMsg.value && qrSuccessMsg.value.includes('Cookie 已失效')) qrSuccessMsg.value = '' }, 8000)
    }
    // 从服务端重新拉取，确保数据同步
    loadAccounts().then(() => {
      if (newStatus === 1) refreshUncachedWsStatus()
    })
  }
}

onMounted(() => {
  window.addEventListener('xya-header-action', handleHeaderAction)
  window.addEventListener('xya-sse-event', handleSseEvent)
  // 注册 SSE captcha_solve 监听器：接收后端推送的滑块求解状态变化（retrying/success/fail），
  // 否则按钮点击后状态只能靠 solveManually 内部 await 更新，无法响应后端异步进度
  initCaptchaSolverListener()
  loadAccounts().then(() => {
    refreshUncachedWsStatus()
    // 进入页面时主动校验当前页账号的 cookie 实时状态，
    // 避免 DB 中 cookie_status 仍是"正常"但 cookie 实际已失效时 UI 显示假"正常"。
    refreshVisibleAccountsAuthOnPageEnter()
  })
})
onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', handleHeaderAction)
  window.removeEventListener('xya-sse-event', handleSseEvent)
  destroyCaptchaSolverListener()
  stopQrPolling()
  stopPolishPolling()
  void cleanupQrLogin()
  if (cooldownTimer) { clearInterval(cooldownTimer); cooldownTimer = null }
  // 清理所有 WS 状态轮询定时器（求解成功后自动连接时创建）
  Object.keys(wsPollTimers).forEach(key => stopWsPolling(key))
})
</script>

<style scoped>
.grid.wide-right {
  grid-template-columns: minmax(0, 1fr) 392px;
  gap: 16px;
  align-items: start;
}

.account-detail-drawer {
  min-width: 0;
  padding: 15px 14px 14px;
  border: 1px solid #e6edf5;
  border-radius: 9px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(39, 72, 118, 0.045);
  color: #2a3851;
}

.detail-title-row,
.account-summary,
.account-name-row,
.health-footer,
.quick-actions button {
  display: flex;
  align-items: center;
}

.detail-title-row {
  justify-content: space-between;
}

.detail-title-row h3,
.account-detail-drawer h4 {
  margin: 0;
  color: #1e2d47;
  font-weight: 700;
}

.detail-title-row h3 {
  font-size: 15px;
  line-height: 24px;
}

.account-detail-drawer h4 {
  font-size: 14px;
  line-height: 22px;
}

.detail-close {
  width: 26px;
  height: 26px;
  border: 0;
  background: transparent;
  color: #51627c;
  font-size: 24px;
  font-weight: 300;
  line-height: 20px;
  cursor: pointer;
}

.account-summary {
  position: relative;
  gap: 12px;
  margin-top: 14px;
  padding: 0 0 13px;
}

.detail-avatar {
  width: 56px;
  height: 56px;
  flex: 0 0 56px;
  border-radius: 50%;
  object-fit: cover;
  background: linear-gradient(135deg, #e7f0fa, #f7fbff);
  box-shadow: inset 0 0 0 1px #e5edf5;
}

.avatar-fallback {
  position: relative;
}

.avatar-fallback::before {
  position: absolute;
  inset: 13px;
  border-radius: 50%;
  background: #cfdae7;
  content: '';
}

.account-summary-main {
  min-width: 0;
  padding-right: 4px;
}

.account-name-row {
  gap: 8px;
  min-height: 22px;
}

.account-name-row strong {
  max-width: 128px;
  overflow: hidden;
  color: #23324b;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-account-tag,
.plan-tag {
  display: inline-flex;
  align-items: center;
  min-height: 21px;
  padding: 0 9px;
  border-radius: 4px;
  background: #edf4ff;
  color: #4087ff;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.account-meta-line {
  margin-top: 4px;
  color: #687891;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}

.account-meta-split {
  display: flex;
  align-items: center;
  gap: 10px;
}

.account-meta-split i {
  width: 1px;
  height: 12px;
  background: #e2e9f1;
}

.online-state {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  align-self: flex-start;
  padding-top: 3px;
  color: #19bd78;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.online-state i,
.health-metrics i {
  display: inline-block;
  border-radius: 50%;
  background: #18bf78;
}

.online-state i {
  width: 7px;
  height: 7px;
}

.online-state.offline {
  color: #9aa8ba;
}

.online-state.offline i {
  background: #9aa8ba;
}

.online-state.unknown {
  color: #64748b;
}

.online-state.unknown i,
.dot.gray {
  background: #94a3b8;
}

.health-card,
.profile-stats-card {
  border: 1px solid #e8eef5;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 2px 7px rgba(31, 65, 113, 0.035);
}

.health-card {
  padding: 11px 12px 10px;
}

.health-content {
  display: grid;
  grid-template-columns: 134px 1fr;
  align-items: center;
  min-height: 110px;
}

.health-ring-wrap {
  display: flex;
  justify-content: center;
}

.health-ring {
  position: relative;
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background:
    conic-gradient(
      #16bf78 var(--health-score),
      #e8f1ee 0
    );
}

.health-ring::before {
  position: absolute;
  inset: 8px;
  border-radius: 50%;
  background: #fff;
  content: '';
}

.health-ring-inner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  flex-direction: column;
  justify-content: center;
}

.health-ring-inner strong {
  color: #22304a;
  font-size: 22px;
  line-height: 24px;
}

.health-ring-inner small {
  margin-left: 1px;
  font-size: 10px;
}

.health-ring-inner span {
  margin-top: 2px;
  color: #6d7c91;
  font-size: 11px;
}

.health-metrics {
  display: grid;
  gap: 8px;
}

.health-metrics div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #5d6d84;
  font-size: 12px;
}

.health-metrics span {
  display: flex;
  align-items: center;
  gap: 9px;
  white-space: nowrap;
}

.health-metrics i {
  width: 6px;
  height: 6px;
}

.health-metrics b {
  color: #19bd78;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.health-footer {
  justify-content: space-between;
  gap: 12px;
  padding-top: 4px;
  color: #78879b;
  font-size: 11px;
}

.text-action {
  border: 0;
  background: transparent;
  color: #3486ff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.text-action b {
  font-size: 18px;
  font-weight: 400;
  vertical-align: -1px;
}

.drawer-section {
  padding: 17px 3px 0;
}

.activity-list {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.activity-list div {
  display: grid;
  grid-template-columns: 94px minmax(0, 1fr);
  gap: 10px;
  color: #617189;
  font-size: 12px;
  line-height: 17px;
}

.activity-list time {
  color: #74849a;
}

.activity-more {
  padding: 7px 0 0;
}

.quick-section {
  margin-top: 11px;
  padding-top: 15px;
  border-top: 1px solid #eef2f6;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
  position: relative;
}

.quick-actions button {
  justify-content: center;
  gap: 7px;
  min-width: 0;
  height: 38px;
  padding: 0 5px;
  border: 1px solid #e1e9f2;
  border-radius: 5px;
  background: #fff;
  color: #53627a;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.quick-actions button:hover {
  border-color: #bcd4ff;
  color: #3383ff;
}

.quick-actions button span {
  color: #5d7190;
  font-size: 17px;
  line-height: 1;
}

.quick-actions .more-action {
  grid-column: 3;
}

.modal-subtitle {
  margin: 10px 0 0;
  color: #66768f;
  font-size: 13px;
  line-height: 1.6;
}

.unified-config-grid {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.unified-config-card {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid #dbe5f1;
  border-radius: 10px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
}

.unified-config-card:hover:not(:disabled) {
  border-color: #82aef7;
  box-shadow: 0 8px 20px rgba(64, 110, 188, 0.08);
  transform: translateY(-1px);
}

.unified-config-card:disabled {
  cursor: not-allowed;
  opacity: .65;
}

.unified-config-card strong {
  display: block;
  color: #20304a;
  font-size: 14px;
}

.unified-config-card span {
  display: block;
  margin-top: 6px;
  color: #6b7b92;
  font-size: 12px;
  line-height: 1.6;
}

.more-actions-backdrop {
  position: fixed;
  inset: 0;
  z-index: 240;
}

.more-actions-menu {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 6px;
  z-index: 250;
  background: #fff;
  border: 1px solid #e8eef8;
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(31, 53, 94, .14);
  padding: 6px;
  display: flex;
  flex-direction: column;
  min-width: 160px;
}

.more-actions-menu button {
  appearance: none;
  border: none;
  background: transparent;
  padding: 10px 14px;
  font-size: 14px;
  color: #2c3e50;
  text-align: left;
  border-radius: 8px;
  cursor: pointer;
  transition: background .15s;
}

.more-actions-menu button:hover {
  background: #f1f6ff;
  color: #2d5bff;
}

.detail-empty {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9aa8ba;
}

/* Table row selection highlight */
.base-table tbody tr.row-selected {
  background: #e6f4ff;
  box-shadow: inset 3px 0 0 #1677ff;
}
.base-table tbody tr.row-selected:hover {
  background: #d6edff;
}

.qr-unavailable {
  width: 100%;
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 18px;
  box-sizing: border-box;
  border: 1px dashed #f59e0b;
  border-radius: 12px;
  background: #fffbeb;
  color: #92400e;
  text-align: center;
}

.qr-unavailable span {
  font-size: 12px;
  line-height: 1.5;
}

/* ===== 闲鱼主页资料卡片 ===== */
.profile-stats-card {
  margin-top: 13px;
  padding: 12px 12px 11px;
}

.profile-stats-card h4 {
  margin: 0 0 10px 0;
}

.profile-intro {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 5px;
  background: #f7f9fc;
}

.profile-intro-label {
  display: block;
  margin-bottom: 4px;
  color: #8e9cb0;
  font-size: 11px;
}

.profile-intro p {
  margin: 0;
  color: #3a4b63;
  font-size: 12px;
  line-height: 18px;
  word-break: break-all;
}

.profile-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 10px;
}

.profile-stat-item {
  text-align: center;
  padding: 8px 4px;
  border-radius: 5px;
  background: #f7f9fc;
}

.profile-stat-item b {
  display: block;
  color: #1e2d47;
  font-size: 16px;
  font-weight: 700;
  line-height: 22px;
}

.profile-stat-item span {
  color: #7a8ca5;
  font-size: 11px;
}

.profile-extra {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 12px;
}

.profile-extra-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 0;
  color: #687891;
  font-size: 12px;
}

.profile-extra-item b {
  color: #34425a;
  font-weight: 600;
}

.green-tag {
  color: #13be77 !important;
}

/* Cookie 状态警告横幅 */
.cookie-warn-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #fff3e0;
  border: 1px solid #ffcc80;
  color: #e65100;
  font-size: 12px;
  line-height: 18px;
}

.cookie-warn-banner.cookie-expired {
  background: #ffebee;
  border-color: #ef9a9a;
  color: #c62828;
}

/* 编辑账号信息 */
.edit-account-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding: 8px 12px;
  border-radius: 5px;
  background: #f5f7fa;
  font-size: 13px;
  color: #58687a;
}

.edit-account-info b {
  color: #1e2d47;
  font-weight: 600;
}

@media (max-width: 1480px) {
  .grid.wide-right {
    grid-template-columns: minmax(0, 1fr) 360px;
  }

  .account-meta-split {
    display: block;
  }

  .account-meta-split i {
    display: none;
  }

  .health-content {
    grid-template-columns: 118px 1fr;
  }
}

/* ===== Cookie 解析预览 ===== */
.cookie-parse-preview {
  margin-top: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.cookie-parse-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  background: #fff3e0;
  border-bottom: 1px solid #ffcc80;
  color: #e65100;
  font-size: 12px;
  line-height: 18px;
}

.cookie-parse-error.cookie-identity-error {
  background: #ffebee;
  border-color: #ef9a9a;
  color: #c62828;
}

.cookie-parse-fields {
  padding: 10px 12px;
  background: #f8fafc;
}

.cookie-parse-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.cookie-parse-header span {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.cookie-parse-header em {
  font-size: 11px;
  color: #94a3b8;
  font-style: normal;
}

.cookie-field-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.cookie-field-item {
  padding: 6px 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
}

.cookie-field-item.missing {
  background: #fff8f8;
  border-color: #fecaca;
}

.cookie-field-item label {
  display: block;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 2px;
}

.cookie-field-item code {
  display: block;
  font-size: 12px;
  color: #334155;
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  word-break: break-all;
}

.cookie-field-item.missing code {
  color: #dc2626;
}

.required-mark {
  color: #ef4444;
  font-size: 10px;
  margin-left: 4px;
}

.cookie-parse-warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 8px;
  padding: 6px 8px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 5px;
  color: #92400e;
  font-size: 11px;
  line-height: 16px;
}

.current-unb-tag {
  display: inline-flex;
  align-items: center;
  margin-left: 8px;
  padding: 2px 8px;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 4px;
  color: #4338ca;
  font-size: 11px;
  font-weight: 500;
}

.diagnosis-card{border:1px solid #e8eef8;border-radius:18px;padding:16px;background:#fbfdff;margin:14px 0}
.diagnosis-card h4{margin:0 0 12px;color:#16213e}
.diagnosis-item{padding:10px 0;border-bottom:1px solid #eef3fa}
.diagnosis-item:last-child{border-bottom:0}
.diagnosis-item span{display:flex;align-items:center;gap:8px;color:#526079;font-weight:700}
.diagnosis-item i{width:9px;height:9px;border-radius:50%;background:#16bf78}.diagnosis-item.warn i{background:#f79009}.diagnosis-item.danger i{background:#ef4444}
.diagnosis-item b{display:block;margin-top:5px;color:#16213e}.diagnosis-item small{display:block;margin-top:4px;color:#667085;line-height:1.5}
.diagnosis-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}

/* 删除确认弹窗 */
.confirm-delete-modal {
  width: 420px;
  text-align: center;
  padding: 40px 36px 28px;
}

.confirm-delete-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  margin: 0 auto 18px;
  border-radius: 50%;
  background: #fef2f2;
}

.confirm-delete-icon .ui-icon {
  width: 32px;
  height: 32px;
}

.confirm-delete-modal h2 {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.confirm-delete-desc {
  margin: 0 0 28px;
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
}

.confirm-delete-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.confirm-delete-actions .app-btn {
  min-width: 120px;
  height: 40px;
  font-size: 14px;
}

/* 滑块求解状态 Badge 和重试按钮 */
.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}

.status-cell .solve-badge {
  font-size: 11px;
  line-height: 18px;
}

/* 操作列滑块求解按钮状态色 */
.solve-op-btn.solving {
  color: #f59e0b;
}

.solve-op-btn.queued {
  color: #3b82f6;
}

.solve-op-btn.success {
  color: #16bf78;
}

.solve-op-btn.fail {
  color: #ef4444;
}

/* 冷却中：灰色 + 弱化 */
.solve-op-btn.cooldown {
  color: #94a3b8;
}

.solve-op-btn:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

/* 滑块求解状态说明卡片（统计卡片上方常驻） */
.solve-info-card {
  margin-bottom: 14px;
  padding: 14px 18px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  border: 1px solid #e2e8f0;
}

.solve-info-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.solve-info-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.solve-info-sub {
  font-size: 12px;
  color: #64748b;
}

.solve-info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 16px;
}

@media (max-width: 1024px) {
  .solve-info-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .solve-info-grid {
    grid-template-columns: 1fr;
  }
}

.solve-info-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.solve-info-item strong {
  display: block;
  font-size: 13px;
  color: #1e293b;
  margin-bottom: 2px;
}

.solve-info-item p {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #475569;
  word-break: break-word;
}

.solve-info-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: #cbd5e1;
}

.solve-info-dot.dot-red { background: #ef4444; }
.solve-info-dot.dot-orange { background: #f59e0b; }
.solve-info-dot.dot-purple { background: #8b5cf6; }
.solve-info-dot.dot-blue { background: #3b82f6; }
.solve-info-dot.dot-gray { background: #94a3b8; }
.solve-info-dot.dot-green { background: #16bf78; }

/* 滑块求解状态横幅（统计卡片下方集中提示） */
.captcha-alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.captcha-alert-banner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 13px;
  line-height: 1.5;
}

.captcha-alert-banner.solving {
  background: linear-gradient(135deg, #fff7e6, #fff1d6);
  border-color: #ffd591;
}

.captcha-alert-banner.queued {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-color: #93c5fd;
}

.captcha-alert-banner.success {
  background: linear-gradient(135deg, #f0f9eb, #e1f3d8);
  border-color: #b7eb8f;
}

.captcha-alert-banner.fail {
  background: linear-gradient(135deg, #fff1f0, #ffccc7);
  border-color: #ffa39e;
}

.captcha-alert-main {
  flex: 1;
  min-width: 0;
}

.captcha-alert-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.captcha-alert-head strong {
  font-size: 14px;
  color: #1e293b;
}

.captcha-alert-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.captcha-alert-tag.solving {
  background: #ffd591;
  color: #ad6800;
}

.captcha-alert-tag.queued {
  background: #93c5fd;
  color: #1e40af;
}

.captcha-alert-tag.success {
  background: #b7eb8f;
  color: #389e0d;
}

.captcha-alert-tag.fail {
  background: #ffa39e;
  color: #cf1322;
}

.captcha-alert-reason {
  color: #475569;
  word-break: break-word;
}

.captcha-alert-next {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.captcha-alert-retry {
  flex-shrink: 0;
  height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid #ffa39e;
  background: #fff;
  color: #cf1322;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.captcha-alert-retry:hover:not(:disabled) {
  background: #fff1f0;
}

.captcha-alert-retry:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

/* 编辑 Cookie 弹窗：标签栏工具区（加载提示 / 复制按钮） */
.cookie-edit-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 0 8px;
}

.cookie-edit-label-row .field-label {
  margin: 0;
}

.cookie-edit-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #8a96aa;
  font-weight: 500;
}

.cookie-edit-toolbar .cookie-loading-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #0d6bff;
  font-size: 12px;
}

.cookie-edit-toolbar .cookie-loading-hint .ui-icon.spin {
  width: 14px;
  height: 14px;
  animation: cookie-spin 0.9s linear infinite;
}

.cookie-edit-toolbar .cookie-copy-btn {
  margin-right: 0;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}

.cookie-edit-toolbar .cookie-copy-btn:disabled {
  color: #b6bfcc;
  cursor: not-allowed;
}

.cookie-area:disabled {
  background: #f5f7fb;
  cursor: progress;
}

@keyframes cookie-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
