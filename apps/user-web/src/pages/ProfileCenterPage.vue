<template>
  <div class="profile-center">
    <div v-if="notice.text" :class="['global-notice', notice.type]">
      {{ notice.text }}
    </div>
    <div v-if="overviewLoadError" class="global-notice error" role="alert">
      {{ overviewLoadError }}
      <button type="button" class="app-btn" @click="loadOverview">重新加载</button>
    </div>

    <div class="profile-shell">
      <aside class="profile-side">
        <div class="card-panel profile-side-card">
          <div class="profile-side-head">
            <h2>个人中心</h2>
          </div>

          <div class="profile-side-nav">
            <button
              v-for="item in tabs"
              :key="item.key"
              type="button"
              :class="['profile-side-tab', { active: menuActiveKey === item.key }]"
              @click="activeTab = item.key"
            >
              <span class="profile-side-tab-icon" aria-hidden="true">
                <svg v-if="item.key === 'overview'" viewBox="0 0 24 24" fill="none">
                  <path d="M4.5 10.5L12 4l7.5 6.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M7.5 9.5v9h9v-9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M10.5 18.5v-5h3v5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                <svg v-else-if="item.key === 'security'" viewBox="0 0 24 24" fill="none">
                  <path d="M12 3l6.5 3v5.3c0 4.3-2.8 8.2-6.5 9.7-3.7-1.5-6.5-5.4-6.5-9.7V6L12 3z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="7" stroke="currentColor" stroke-width="1.8" />
                  <circle cx="12" cy="12" r="2.5" fill="currentColor" />
                </svg>
              </span>
              <span class="profile-side-tab-label">{{ item.label }}</span>
            </button>
          </div>
        </div>
      </aside>

      <div class="profile-main">
        <div v-if="activeTab === 'overview'" class="profile-main-section profile-overview">
          <section class="card-panel welcome-hero">
            <div class="welcome-content">
              <div class="welcome-avatar">
                <svg viewBox="0 0 64 64" width="64" height="64">
                  <defs>
                    <linearGradient id="avG" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#5a9fff" />
                      <stop offset="100%" stop-color="#0d6bff" />
                    </linearGradient>
                  </defs>
                  <circle cx="32" cy="32" r="30" fill="url(#avG)" opacity="0.12" />
                  <circle cx="32" cy="24" r="10" fill="url(#avG)" />
                  <path d="M14 52c0-10 8-16 18-16s18 6 18 16" fill="url(#avG)" />
                </svg>
              </div>

              <div class="welcome-text">
                <h2>
                  <span class="welcome-greeting">欢迎回来，</span>
                  <span class="welcome-user-name">{{ overview.nickname || overview.username || '用户' }}</span>
                  <span class="wave">👋</span>
                </h2>
                <p>管理您的账户资料、安全设置和会员权益，保障账户安全，提升使用效率。</p>

                <div class="welcome-tags">
                  <span class="chip plan-chip">{{ planName }}</span>
                  <span class="chip subtle-chip">{{ planBadge }}</span>
                  <span v-if="overview.tenantName" class="chip subtle-chip">{{ overview.tenantName }}</span>
                  <span :class="['chip', verificationState(overview.emailVerified) === true ? '' : 'warn-chip']">
                    <svg v-if="verificationState(overview.emailVerified) === true" viewBox="0 0 16 16" width="12" height="12" fill="none">
                      <circle cx="8" cy="8" r="7" fill="#16bf78" />
                      <path d="M5 8l2 2 4-4" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <svg v-else viewBox="0 0 16 16" width="12" height="12" fill="none">
                      <circle cx="8" cy="8" r="7" fill="#ff9f22" />
                      <path d="M8 5v4M8 11v.5" stroke="#fff" stroke-width="1.5" stroke-linecap="round" />
                    </svg>
                    邮箱：{{ verificationStatusText(overview.emailVerified) }}
                  </span>
                  <span :class="['chip', verificationState(overview.phoneVerified) === true ? '' : 'warn-chip']">
                    <svg v-if="verificationState(overview.phoneVerified) === true" viewBox="0 0 16 16" width="12" height="12" fill="none">
                      <circle cx="8" cy="8" r="7" fill="#16bf78" />
                      <path d="M5 8l2 2 4-4" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <svg v-else viewBox="0 0 16 16" width="12" height="12" fill="none">
                      <circle cx="8" cy="8" r="7" fill="#ff9f22" />
                      <path d="M8 5v4M8 11v.5" stroke="#fff" stroke-width="1.5" stroke-linecap="round" />
                    </svg>
                    手机：{{ verificationStatusText(overview.phoneVerified, true) }}
                  </span>
                </div>
              </div>
            </div>

            <div class="welcome-visual" aria-hidden="true">
              <div class="welcome-visual-glow"></div>
              <img class="welcome-visual-image" src="/xya/profile-center/profile-hero.png" alt="" />
            </div>
          </section>

          <div class="profile-stats">
            <article v-for="item in statCards" :key="item.label" class="stat-card">
              <div class="stat-card-main">
                <div :class="['stat-icon', item.toneClass]">
                  <img class="stat-icon-img" :src="item.iconSrc" alt="" />
                </div>
                <div class="stat-info">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>

              <div class="stat-card-foot">
                <em>{{ item.desc }}</em>
                <svg :class="['stat-wave', item.toneClass]" viewBox="0 0 96 18" preserveAspectRatio="none" aria-hidden="true">
                  <path d="M2 11c7 0 7-8 14-8s7 8 14 8 7-8 14-8 7 8 14 8 7-8 14-8 7 8 14 8" />
                </svg>
              </div>
            </article>
          </div>

          <div class="two-col-grid">
            <section class="card-panel member-panel">
              <div class="panel-head">
                <div class="panel-title">
                  <span class="panel-head-mark gold" aria-hidden="true">
                    <img class="panel-head-icon" src="/xya/profile-center/icons/shield.png" alt="" />
                  </span>
                  <h3>会员信息与权益</h3>
                </div>
              </div>

              <div class="member-card-inner">
                <div class="member-left">
                  <div class="crown-big" aria-hidden="true">
                    <img class="member-card-icon" src="/xya/profile-center/icons/shield.png" alt="" />
                  </div>
                  <div>
                    <div class="member-name-row">
                      <strong>{{ planName }}</strong>
                      <span class="badge gray">{{ planBadge }}</span>
                    </div>
                    <span class="member-sub">{{ planPeriodText }}</span>
                  </div>
                </div>

                <div class="member-actions">
                  <button type="button" class="app-btn primary" @click="handleQuickAction('vip')">升级会员</button>
                </div>
              </div>

              <div class="benefits-row">
                <span class="benefits-label">VIP 权益：</span>
                <div class="benefits-grid">
                  <div v-for="b in memberBenefits" :key="b.label" class="benefit-feature">
                    <span class="benefit-feature-icon" aria-hidden="true">
                      <img class="benefit-icon" :src="b.iconSrc" alt="" />
                    </span>
                    <span class="benefit-feature-label">{{ b.label }}</span>
                  </div>
                  <span v-if="!memberBenefits.length" class="subtle">权益明细未随个人资料返回，请前往会员中心查看后台套餐配置。</span>
                </div>
              </div>
            </section>

            <section class="card-panel token-panel">
              <div class="panel-head">
                <div class="panel-title">
                  <span class="panel-head-mark violet" aria-hidden="true">
                    <img class="panel-head-icon" src="/xya/profile-center/icons/token.png" alt="" />
                  </span>
                  <h3>Token 余额</h3>
                </div>
              </div>

              <div class="token-amount">
                <span class="token-label">账户余额</span>
                <strong>{{ formatNumber(overview.tokenBalance) }} <em>Token</em></strong>
                <span class="token-plan">当前套餐：{{ planName }}</span>
              </div>

              <button type="button" class="app-btn primary recharge-btn" @click="paymentVisible = true">充值 Tokens</button>

              <div class="token-coin" aria-hidden="true">
                <div class="token-coin-glow"></div>
                <img class="token-coin-image" src="/xya/profile-center/profile-token.png" alt="" />
              </div>
            </section>
          </div>

          <div class="overview-bottom-grid">
            <section class="card-panel account-panel">
              <div class="panel-head">
                <div class="panel-title">
                  <span class="panel-head-mark blue" aria-hidden="true">
                    <img class="panel-head-icon" src="/xya/profile-center/icons/wallet.png" alt="" />
                  </span>
                  <h3>账户信息</h3>
                </div>
              </div>

              <div class="account-info-grid">
                <article v-for="item in accountInfoItems" :key="item.label" class="account-info-item">
                  <span class="account-info-label">{{ item.label }}</span>
                  <div class="account-info-value-row">
                    <strong>{{ item.value }}</strong>
                    <span v-if="item.badge" :class="['badge', item.badgeClass]">{{ item.badge }}</span>
                  </div>
                </article>
              </div>
            </section>

            <section class="card-panel quick-panel">
              <div class="panel-head">
                <div class="panel-title">
                  <span class="panel-head-mark mint" aria-hidden="true">
                    <img class="panel-head-icon" src="/xya/profile-center/icons/workflow.png" alt="" />
                  </span>
                  <h3>快捷操作</h3>
                </div>
              </div>

              <div class="quick-grid-2col">
                <button
                  v-for="item in quickActionItems"
                  :key="item.title"
                  type="button"
                  class="quick-card quick-action-btn"
                  @click="handleQuickAction(item.action)"
                >
                  <div :class="['circle-ico', item.tone]">
                    <img class="quick-icon-img" :src="item.iconSrc" alt="" />
                  </div>
                  <div class="quick-card-copy">
                    <b>{{ item.title }}</b>
                    <span>{{ item.desc }}</span>
                  </div>
                </button>
              </div>
            </section>
          </div>
        </div>

        <div v-else-if="activeTab === 'security'" class="card-panel security-panel content-panel">
          <div class="panel-head">
            <div>
              <h3>账号安全</h3>
              <p>管理密码、手机号、邮箱验证状态，保护账号安全。</p>
            </div>
            <button type="button" class="app-btn" @click="loadOverview">刷新</button>
          </div>

          <EmptyState
            v-if="!overviewAvailable"
            variant="error"
            title="账号安全状态暂时不可用"
            :description="overviewLoadError || '正在加载个人资料，当前不会把未知状态显示为未绑定或存在风险。'"
          >
            <template #actions><button type="button" class="app-btn" @click="loadOverview">重新加载</button></template>
          </EmptyState>
          <template v-else>
          <div v-if="!profileVerificationCapability.available" class="global-notice warn" role="status">
            {{ profileVerificationStatusText }}
            {{ authCapabilities.supportMessage }}
            <button v-if="authCapabilityError" type="button" class="app-btn" @click="refreshAuthCapabilities">重新检查</button>
          </div>
          <div class="security-level-card" :class="securityLevel.tone">
            <div class="security-level-visual" aria-hidden="true">
              <div class="security-level-visual-ring"></div>
              <svg class="security-level-visual-illustration" viewBox="0 0 320 220" fill="none">
                <path class="security-illustration-shape shape-left" d="M55 70c16-18 39-24 59-17-10 8-16 20-16 34 0 9 2 17 7 24-25 7-44 4-60-11-13-12-19-34 10-30Z" />
                <path class="security-illustration-shape shape-right" d="M213 58c12-7 29-8 44-2-8 6-13 15-13 27 0 11 4 21 12 27-17 8-34 6-47-7-12-13-13-33 4-45Z" />
                <ellipse class="security-orbit-glow" cx="140" cy="168" rx="84" ry="28" />
                <ellipse class="security-orbit-line" cx="140" cy="164" rx="96" ry="38" />
                <path class="security-orbit-dash" d="M46 167c18-22 49-35 93-35 44 0 75 13 95 33" />
                <circle class="security-orbit-dot dot-left" cx="50" cy="166" r="4.5" />
                <circle class="security-orbit-dot dot-right" cx="231" cy="135" r="4.5" />
                <circle class="security-orbit-dot dot-top" cx="262" cy="152" r="3.5" />
                <ellipse class="security-stage-shadow" cx="140" cy="174" rx="70" ry="18" />
                <ellipse class="security-stage-plate outer" cx="140" cy="164" rx="76" ry="22" />
                <ellipse class="security-stage-plate middle" cx="140" cy="160" rx="62" ry="18" />
                <ellipse class="security-stage-core" cx="140" cy="156" rx="42" ry="12" />
                <g transform="translate(78 18)">
                  <path class="security-shield-back" d="M78 8 126 28v40c0 33-18 62-48 81-30-19-48-48-48-81V28L78 8Z" />
                  <path class="security-shield-front" d="M74 14 116 31v35c0 29-15 54-42 70C47 120 32 95 32 66V31l42-17Z" />
                  <path class="security-shield-gloss" d="M74 21 103 33v29c0 18-8 35-23 47-17-8-29-22-34-40 8 5 18 7 27 7 12 0 23-4 31-12V34L74 21Z" />
                  <path class="security-shield-outline" d="M74 14 116 31v35c0 29-15 54-42 70C47 120 32 95 32 66V31l42-17Z" />
                  <path class="security-shield-check" d="m56 71 14 14 28-29" />
                </g>
              </svg>
            </div>
            <div class="security-level-main">
              <div class="security-level-topline">
                <div class="security-level-info">
                  <div class="security-level-icon">
                    <svg viewBox="0 0 24 24" width="28" height="28" fill="none">
                      <path d="M12 2L4 6v6c0 5 3.5 9.5 8 10 4.5-.5 8-5 8-10V6l-8-4z" fill="currentColor" opacity="0.18" />
                      <path d="M12 2L4 6v6c0 5 3.5 9.5 8 10 4.5-.5 8-5 8-10V6l-8-4z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
                      <path v-if="securityLevel.score >= 3" d="M8.5 12.5l2.5 2.5 4.5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                      <path v-else d="M12 8v4M12 16v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                    </svg>
                  </div>
                  <div class="security-level-text">
                    <h4>账号安全等级</h4>
                    <strong>{{ securityLevel.label }}</strong>
                    <div class="security-level-summary">
                      <span v-if="securityRiskCount > 0" class="security-risk-pill">
                        存在 {{ securityRiskCount }} 项待完善安全设置
                      </span>
                      <span v-else class="security-risk-pill safe">
                        安全项已全部完成
                      </span>
                    </div>
                    <p>{{ securityLevel.desc }}</p>
                  </div>
                </div>
                <span class="security-link-hint">安全等级说明</span>
              </div>

              <div class="security-progress-wrap">
                <div class="security-progress">
                  <div class="security-progress-bar" :style="{ width: securityLevel.percent + '%' }"></div>
                </div>
                <div class="security-progress-labels">
                  <span :class="{ active: securityLevel.score === 1 }">低</span>
                  <span :class="{ active: securityLevel.score === 2 }">中</span>
                  <span :class="{ active: securityLevel.score >= 3 }">高</span>
                </div>
              </div>

              <div class="security-meta">
                <span>上次安全更新：{{ displayDate(overview.lastSecurityUpdateTime) || '暂无' }}</span>
                <span>最近登录：{{ displayDate(overview.lastLoginTime) || '暂无' }}</span>
              </div>
            </div>
          </div>

          <div class="security-grid">
            <div class="security-card enhanced">
              <div class="security-card-head">
                <div class="security-card-icon blue">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
                    <rect x="5" y="11" width="14" height="9" rx="2" fill="currentColor" opacity="0.18" />
                    <rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" stroke-width="1.8" />
                    <path d="M8 11V8a4 4 0 018 0v3" stroke="currentColor" stroke-width="1.8" />
                  </svg>
                </div>
                <span class="badge">已设置</span>
              </div>
              <b>登录密码</b>
              <span>建议定期更换，使用 8 位以上字母、数字组合，不要与其他平台共用。</span>
              <div class="security-card-note">
                <span class="security-card-note-dot"></span>
                <span>{{ securityPasswordHint }}</span>
              </div>
              <button type="button" class="app-btn primary" @click="activeTab = 'password'">修改密码</button>
            </div>

            <div class="security-card enhanced">
              <div class="security-card-head">
                <div class="security-card-icon" :class="overview.phoneVerified ? 'green' : 'orange'">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
                    <rect x="7" y="3" width="10" height="18" rx="2" stroke="currentColor" stroke-width="1.8" fill="currentColor" fill-opacity="0.12" />
                    <line x1="11" y1="18" x2="13" y2="18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
                  </svg>
                </div>
                <span :class="['badge', overview.phoneVerified ? '' : 'orange']">
                  {{ overview.phoneVerified ? '已验证' : '未验证' }}
                </span>
              </div>
              <b>手机号</b>
              <span>{{ maskedPhone || '未绑定手机号，建议尽快绑定以提升账号安全' }}</span>
              <div :class="['security-card-note', overview.phoneVerified ? 'ok' : 'warn']">
                <span class="security-card-note-dot"></span>
                <span>{{ overview.phoneVerified
                  ? '已通过验证，可用于登录保护和找回账号'
                  : profileVerificationCapability.available
                    ? '尚未验证，建议绑定手机号以提升账号安全'
                    : profileVerificationUnavailableText }}</span>
              </div>
              <button
                type="button"
                class="app-btn primary"
                :disabled="!profileVerificationCapability.available"
                :title="profileVerificationCapability.reason"
                @click="activeTab = 'phone'"
              >
                {{ profileVerificationCapability.available ? (maskedPhone ? '更换手机号' : '绑定手机号') : profileVerificationActionText }}
              </button>
            </div>

            <div class="security-card enhanced">
              <div class="security-card-head">
                <div class="security-card-icon" :class="overview.emailVerified ? 'green' : 'orange'">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
                    <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.8" fill="currentColor" fill-opacity="0.12" />
                    <path d="M4 7l8 6 8-6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                </div>
                <span :class="['badge', overview.emailVerified ? '' : 'orange']">
                  {{ overview.emailVerified ? '已验证' : '未验证' }}
                </span>
              </div>
              <b>邮箱</b>
              <span>{{ maskedEmail || '未绑定邮箱，绑定后可用于找回密码和接收通知' }}</span>
              <div :class="['security-card-note', overview.emailVerified ? 'ok' : 'warn']">
                <span class="security-card-note-dot"></span>
                <span>{{ overview.emailVerified
                  ? '已通过验证，可接收安全提醒与找回邮件'
                  : profileVerificationCapability.available
                    ? '尚未验证，建议完成邮箱验证以提升通知可达性'
                    : profileVerificationUnavailableText }}</span>
              </div>
              <button
                type="button"
                class="app-btn primary"
                :disabled="!profileVerificationCapability.available"
                :title="profileVerificationCapability.reason"
                @click="activeTab = 'email'"
              >
                {{ profileVerificationCapability.available ? (maskedEmail ? '更换邮箱' : '绑定邮箱') : profileVerificationActionText }}
              </button>
            </div>
          </div>

          <div class="security-tips">
            <div class="security-tips-copy">
              <h4>安全建议</h4>
              <ul class="security-bullet-list">
                <li v-for="item in securityAdviceList" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
          </template>
        </div>

        <div v-else-if="activeTab === 'token'" class="card-panel content-panel token-ledger-panel">
          <div class="panel-head">
            <div>
              <h3>Token 消耗明细</h3>
              <p>展示 AI 生图、改写等功能的 Token 消耗记录与统计。</p>
            </div>
            <button type="button" class="app-btn" @click="loadTokenLedger(1)">刷新</button>
          </div>

          <div class="token-stats">
            <article
              v-for="item in tokenStatCards"
              :key="item.key"
              :class="['metric-tile', 'token-stat-card', `stat-${item.tone}`]"
            >
              <div class="token-stat-ico">{{ item.icon }}</div>
              <div class="token-stat-body">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <small>{{ item.desc }}</small>
              </div>
            </article>
          </div>

          <div class="token-table-card">
            <div class="table-wrap">
              <EmptyState v-if="tokenLoadError" variant="error" title="Token 记录暂时无法加载" :description="tokenLoadError">
                <template #actions><button type="button" class="app-btn" @click="loadTokenLedger(1)">重试</button></template>
              </EmptyState>
              <table v-else-if="tokenLedger.records.length" class="base-table token-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>类型</th>
                    <th>来源</th>
                    <th>变动数量</th>
                    <th>变动前</th>
                    <th>变动后</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in tokenLedger.records" :key="row.id">
                    <td class="time-cell">{{ displayDate(row.createdTime) }}</td>
                    <td>
                      <span :class="['badge', changeTypeClass(row.changeType)]">
                        {{ changeTypeLabel(row.changeType) }}
                      </span>
                    </td>
                    <td>{{ refTypeLabel(row.refType) }}</td>
                    <td :class="changeAmountClass(row.changeAmount)">
                      {{ formatSignedNumber(row.changeAmount) }}
                    </td>
                    <td class="mono">{{ formatNumber(row.beforeBalance) }}</td>
                    <td class="mono">{{ formatNumber(row.afterBalance) }}</td>
                    <td class="remark-cell" :title="row.remark || ''">{{ row.remark || '-' }}</td>
                  </tr>
                </tbody>
              </table>
              <EmptyState v-else icon="🪙" :title="tokenLoading ? '加载中...' : '暂无 Token 消耗记录'" description="使用 AI 生图、AI 改写等功能后，Token 消耗记录会显示在这里。" />
            </div>
            <div class="token-table-foot">
              <span v-if="tokenLedger.total > 0" class="token-record-count">共 {{ formatNumber(tokenLedger.total) }} 条记录</span>
              <div v-if="tokenLedger.total > 0" class="pagination">
                <button class="page-btn icon" :disabled="tokenLedger.current <= 1" @click="loadTokenLedger(tokenLedger.current - 1)">‹</button>
                <div class="page-jump">
                  <button type="button" class="page-number" :class="{ active: tokenLedger.current === 1 }" @click="loadTokenLedger(1)">1</button>
                  <button
                    v-if="tokenLedger.current > 2"
                    type="button"
                    class="page-number"
                    @click="loadTokenLedger(Math.max(1, tokenLedger.current - 1))"
                  >
                    {{ Math.max(1, tokenLedger.current - 1) }}
                  </button>
                  <button
                    v-if="tokenLedger.current !== 1 && tokenLedger.current !== totalPages"
                    type="button"
                    class="page-number active"
                  >
                    {{ tokenLedger.current }}
                  </button>
                  <button
                    v-if="tokenLedger.current < totalPages - 1"
                    type="button"
                    class="page-number"
                    @click="loadTokenLedger(Math.min(totalPages, tokenLedger.current + 1))"
                  >
                    {{ Math.min(totalPages, tokenLedger.current + 1) }}
                  </button>
                  <span v-if="totalPages > 4" class="page-ellipsis">…</span>
                  <button
                    v-if="totalPages > 1"
                    type="button"
                    class="page-number"
                    :class="{ active: tokenLedger.current === totalPages }"
                    @click="loadTokenLedger(totalPages)"
                  >
                    {{ totalPages }}
                  </button>
                </div>
                <button class="page-btn icon" :disabled="tokenLedger.current >= totalPages" @click="loadTokenLedger(tokenLedger.current + 1)">›</button>
                <div class="page-size">
                  <span>每页</span>
                  <select v-model.number="tokenLedger.size" @change="loadTokenLedger(1)">
                    <option :value="20">20</option>
                    <option :value="50">50</option>
                    <option :value="100">100</option>
                    <option :value="200">200</option>
                    <option :value="500">500</option>
                  </select>
                </div>
                <div class="page-jump compact">
                  <span>跳至</span>
                  <input v-model.number="jumpPage" type="number" min="1" :max="totalPages" @keyup.enter="goToJumpPage" />
                  <button type="button" class="page-btn" @click="goToJumpPage">确定</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'password'" class="card-panel form-panel content-panel">
          <div class="panel-head">
            <div>
              <h3>修改密码</h3>
              <p>新密码至少 8 位。修改成功后建议重新登录。</p>
            </div>
            <button type="button" class="app-btn" @click="activeTab = 'security'">返回</button>
          </div>
          <form class="profile-form" @submit.prevent="submitPassword">
            <label>
              <span>当前密码</span>
              <input v-model="passwordForm.oldPassword" type="password" autocomplete="current-password" placeholder="请输入当前密码" />
            </label>
            <label>
              <span>新密码</span>
              <input v-model="passwordForm.newPassword" type="password" autocomplete="new-password" placeholder="至少 8 位" />
            </label>
            <label>
              <span>确认新密码</span>
              <input v-model="passwordForm.confirmPassword" type="password" autocomplete="new-password" placeholder="再次输入新密码" />
            </label>
            <button type="submit" class="app-btn primary submit-btn" :disabled="saving">保存新密码</button>
          </form>
        </div>

        <div v-else-if="activeTab === 'phone'" class="card-panel form-panel content-panel">
          <div class="panel-head">
            <div>
              <h3>修改手机号</h3>
              <p>先获取验证码，再提交绑定。验证码有效期 5 分钟。</p>
            </div>
            <button type="button" class="app-btn" @click="activeTab = 'security'">返回</button>
          </div>
          <div v-if="!profileVerificationCapability.available" class="profile-capability-unavailable" role="status">
            <p>{{ profileVerificationStatusText }}</p>
            <p>{{ authCapabilities.supportMessage }}</p>
            <button v-if="authCapabilityError" type="button" class="app-btn" @click="refreshAuthCapabilities">重新检查</button>
          </div>
          <form v-else class="profile-form" @submit.prevent="submitPhone">
            <label>
              <span>新手机号</span>
              <input v-model="phoneForm.phone" type="tel" placeholder="请输入 11 位手机号" />
            </label>
            <div class="code-row">
              <label class="code-label">
                <span>验证码</span>
                <input v-model="phoneForm.code" type="text" placeholder="请输入验证码" />
              </label>
              <button type="button" class="app-btn" @click="sendCode('phone')">获取验证码</button>
            </div>
            <button type="submit" class="app-btn primary submit-btn" :disabled="saving">绑定手机号</button>
          </form>
        </div>

        <div v-else-if="activeTab === 'email'" class="card-panel form-panel content-panel">
          <div class="panel-head">
            <div>
              <h3>修改邮箱</h3>
              <p>先获取验证码，再提交绑定。验证码有效期 5 分钟。</p>
            </div>
            <button type="button" class="app-btn" @click="activeTab = 'security'">返回</button>
          </div>
          <div v-if="!profileVerificationCapability.available" class="profile-capability-unavailable" role="status">
            <p>{{ profileVerificationStatusText }}</p>
            <p>{{ authCapabilities.supportMessage }}</p>
            <button v-if="authCapabilityError" type="button" class="app-btn" @click="refreshAuthCapabilities">重新检查</button>
          </div>
          <form v-else class="profile-form" @submit.prevent="submitEmail">
            <label>
              <span>新邮箱</span>
              <input v-model="emailForm.email" type="email" placeholder="请输入邮箱地址" />
            </label>
            <div class="code-row">
              <label class="code-label">
                <span>验证码</span>
                <input v-model="emailForm.code" type="text" placeholder="请输入验证码" />
              </label>
              <button type="button" class="app-btn" @click="sendCode('email')">获取验证码</button>
            </div>
            <button type="submit" class="app-btn primary submit-btn" :disabled="saving">绑定邮箱</button>
          </form>
        </div>
      </div>
    </div>

    <PaymentModal
      :visible="paymentVisible"
      order-type="token"
      @close="paymentVisible = false"
      @paid="handleTokenPaid"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import PaymentModal from '../components/PaymentModal.vue'
import EmptyState from '../components/EmptyState.vue'
import {
  changeProfileEmail,
  changeProfilePassword,
  changeProfilePhone,
  getProfileOverview,
  getTokenLedger,
  sendProfileCode
} from '../api/profile.js'
import { useAuthCapabilities } from '../utils/useAuthCapabilities.js'
import { globalConfirm } from '../composables/confirmState.js'

const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'security', label: '账号安全' },
  { key: 'token', label: 'Token 消耗' }
]

const {
  authCapabilities,
  authCapabilityLoading,
  authCapabilityError,
  refreshAuthCapabilities,
} = useAuthCapabilities()
const profileVerificationCapability = computed(() => authCapabilities.value.profileVerification)
const profileVerificationStatusText = computed(() => {
  if (authCapabilityLoading.value) return '正在确认当前部署的验证码能力，确认前相关入口保持关闭。'
  return authCapabilityError.value || profileVerificationCapability.value.reason
})
const profileVerificationUnavailableText = computed(() => {
  if (authCapabilityLoading.value) return '验证码能力正在确认，当前不会开放手机或邮箱验证'
  if (authCapabilityError.value) return '验证码能力状态无法确认，当前不会开放手机或邮箱验证'
  return '验证码服务未启用，当前无法完成手机或邮箱验证'
})
const profileVerificationActionText = computed(() => authCapabilityLoading.value ? '正在确认验证能力' : '验证服务不可用')

const PROFILE_ENTRY_STORAGE_KEY = 'xya_profile_initial_tab'
const PROFILE_MAIN_TABS = new Set(['overview', 'security', 'token'])
const activeTab = ref('overview')
const saving = ref(false)
const overview = reactive({})
const overviewAvailable = ref(false)
const overviewLoadError = ref('')
const notice = reactive({ text: '', type: 'info' })
const paymentVisible = ref(false)
const tokenLedger = reactive({ records: [], total: 0, current: 1, size: 20 })
const tokenLoading = ref(false)
const tokenLoadError = ref('')
const tokenStats = reactive({ todayConsume: null, sevenDayConsume: null, tokenBalance: null })
const jumpPage = ref(1)

const passwordForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })
const phoneForm = reactive({ phone: '', code: '' })
const emailForm = reactive({ email: '', code: '' })

let noticeTimer = null

const stats = computed(() => overview.stats || {})
const planName = computed(() => overview.activePlan?.planName || '套餐状态未知')
const planBadge = computed(() => {
  if (!overview.activePlan?.planCode) return 'UNKNOWN'
  const code = String(overview.activePlan.planCode).toUpperCase()
  return code === 'NORMAL' ? 'FREE' : code
})
const maskedPhone = computed(() => maskPhone(overview.phone))
const maskedEmail = computed(() => maskEmail(overview.email))
const menuActiveKey = computed(() => {
  if (['password', 'phone', 'email'].includes(activeTab.value)) return 'security'
  return activeTab.value
})
const planPeriodText = computed(() => {
  if (!overview.activePlan) return '套餐状态暂不可用'
  return overview.activePlan.endTime ? `有效期至 ${displayDateOnly(overview.activePlan.endTime)}` : '有效期以后台权益为准'
})

const securityLevel = computed(() => {
  if (!overviewAvailable.value) return { score: 0, label: '未知', tone: 'unknown', desc: '个人资料未加载，当前不能评估账号安全等级', percent: 0 }
  const score = 1 + (overview.phoneVerified ? 1 : 0) + (overview.emailVerified ? 1 : 0)
  if (score >= 3) return { score, label: '高', tone: 'high', desc: '您的账号安全等级较高，请继续保持良好的安全习惯', percent: 100 }
  if (!profileVerificationCapability.value.available) {
    const desc = authCapabilityLoading.value
      ? '验证码能力正在确认，当前不会把未知状态显示为可用'
      : authCapabilityError.value
        ? '验证码能力状态无法确认，手机和邮箱验证入口已安全关闭'
        : '当前部署未启用验证码供应商，手机和邮箱验证暂不可完成'
    return { score, label: '受限', tone: 'unknown', desc, percent: Math.round(score / 3 * 100) }
  }
  if (score === 2) return { score, label: '中', tone: 'medium', desc: '建议绑定所有安全项以提升账号安全等级', percent: 66 }
  return { score, label: '低', tone: 'low', desc: '请尽快完善账号安全设置，绑定手机号和邮箱', percent: 33 }
})

const securityRiskCount = computed(() => {
  if (!overviewAvailable.value) return null
  let count = 0
  if (!overview.phoneVerified) count += 1
  if (!overview.emailVerified) count += 1
  return count
})

const securityPasswordHint = computed(() => {
  if (!overviewAvailable.value) return '安全更新时间暂时不可用'
  const value = overview.lastSecurityUpdateTime || overview.updatedTime
  if (!value) return '建议尽快完成首次密码更新并定期轮换'
  return `最近安全更新：${displayDate(value)}`
})

const statCards = computed(() => [
  { label: '闲鱼账号', value: metricText(stats.value.xianyuAccountCount), desc: overviewAvailable.value ? '已绑定账号' : '状态不可用', iconSrc: '/xya/profile-center/icons/wallet.png', toneClass: '' },
  { label: '商品总数', value: metricText(stats.value.goodsCount), desc: overviewAvailable.value ? '全部商品' : '状态不可用', iconSrc: '/xya/profile-center/icons/bag.png', toneClass: 'green' },
  { label: '订单总数', value: metricText(stats.value.orderCount), desc: overviewAvailable.value ? '全部订单' : '状态不可用', iconSrc: '/xya/profile-center/icons/audit.png', toneClass: 'orange' },
  { label: '在线会话', value: metricText(stats.value.conversationCount), desc: overviewAvailable.value ? '当前会话数' : '状态不可用', iconSrc: '/xya/profile-center/icons/message.png', toneClass: 'purple' }
])

const memberBenefits = computed(() => {
  const benefits = overview.activePlan?.features
  if (!Array.isArray(benefits)) return []
  return benefits.filter(Boolean).map(label => ({ label: String(label), iconSrc: '/xya/profile-center/icons/shield.png' }))
})

const quickActionItems = [
  { title: '账户安全', desc: '修改密码、手机号、邮箱', iconSrc: '/xya/profile-center/icons/shield.png', tone: 'blue-bg', action: 'security' },
  { title: '商品管理', desc: '查看商品、发布商品', iconSrc: '/xya/profile-center/icons/bag.png', tone: 'green-bg', action: 'products' },
  { title: 'Token 消耗', desc: '查看消耗明细', iconSrc: '/xya/profile-center/icons/token.png', tone: 'purple-bg', action: 'token' },
  { title: '升级会员', desc: '续费、升级套餐', iconSrc: '/xya/profile-center/icons/audit.png', tone: 'orange-bg', action: 'payment' }
]

const securityAdviceCards = [
  { icon: '🔐', tone: 'blue', title: '定期更换密码', desc: '避免使用与其他平台相同的密码' },
  { icon: '✉', tone: 'mint', title: '绑定手机号和邮箱', desc: '确保账号找回渠道畅通' },
  { icon: '👤', tone: 'violet', title: '不要使用简单密码', desc: '建议使用大小写字母、数字和符号组合' },
  { icon: '🛡', tone: 'sky', title: '开启设备与登录提醒', desc: '及时发现异常登录，保护账号安全' }
]

const securityAdviceList = securityAdviceCards.length
  ? [
      '定期更换密码，避免使用与其他平台相同的密码',
      '绑定手机号和邮箱，确保账号找回通道畅通',
      '不要向任何人透露密码、验证码等敏感信息',
      '如发现异常登录，请立即修改密码并联系客服'
    ]
  : []

const tokenStatCards = computed(() => [
  {
    key: 'today',
    tone: 'red',
    icon: '今',
    label: '今日消耗',
    value: formatNumber(tokenStats.todayConsume),
    desc: '今日 0 点至今累计消耗',
    badge: '今日累计'
  },
  {
    key: 'week',
    tone: 'orange',
    icon: '七',
    label: '七日消耗',
    value: formatNumber(tokenStats.sevenDayConsume),
    desc: '近 7 天累计消耗',
    badge: '近 7 天累计'
  },
  {
    key: 'balance',
    tone: 'blue',
    icon: '余',
    label: 'Token 余额',
    value: formatNumber(tokenStats.tokenBalance),
    desc: '账户当前可用余额',
    badge: '服务端实时余额'
  }
])

const accountInfoItems = computed(() => [
  { label: '用户名', value: overview.username || '-' },
  { label: '昵称', value: overview.nickname || '-' },
  { label: '账户邮箱', value: maskedEmail.value || '-', ...bindingBadge(maskedEmail.value, overview.emailVerified, false) },
  { label: '手机号码', value: maskedPhone.value || '-', ...bindingBadge(maskedPhone.value, overview.phoneVerified, true) },
  { label: '账户 ID', value: overview.userId ?? '-' },
  { label: '所属租户', value: overview.tenantName || '-' },
  { label: '账号状态', value: formatUserStatus(overview.status) },
  { label: '当前套餐', value: planName.value || '-' },
  { label: '最近登录', value: displayDate(overview.lastLoginTime) },
  { label: '安全更新', value: displayDate(overview.lastSecurityUpdateTime) }
])

function bindingBadge(maskedValue, verified, phone) {
  if (!overviewAvailable.value) return { badge: '状态未知', badgeClass: 'gray' }
  if (!maskedValue) return { badge: '未绑定', badgeClass: 'orange' }
  const state = verificationState(verified)
  if (state === true) return { badge: phone ? '已绑定' : '已验证', badgeClass: 'green' }
  if (state === false) return { badge: '未验证', badgeClass: 'orange' }
  return { badge: '状态未知', badgeClass: 'gray' }
}

function showNotice(text, type = 'info') {
  notice.text = text
  notice.type = type
  if (noticeTimer) clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => { notice.text = '' }, 4200)
}

function metricText(value) {
  return value === null || value === undefined || value === '' ? '—' : value
}

function verificationState(value) {
  if (value === true || value === 1 || value === '1') return true
  if (value === false || value === 0 || value === '0') return false
  return null
}

function verificationStatusText(value, phone = false) {
  const state = verificationState(value)
  if (state === true) return phone ? '已绑定' : '已验证'
  if (state === false) return phone ? '未绑定' : '未验证'
  return '状态未知'
}

const totalPages = computed(() => Math.max(1, Math.ceil(tokenLedger.total / tokenLedger.size)))

const changeTypeLabel = type => {
  const map = {
    recharge: '充值', ai_charge: 'AI扣费', ai_image_charge: '生图扣费',
    deduct: '消耗', deduct_image: '生图', deduct_rewrite: '改写', deduct_chat: '对话',
    refund: '退款', admin_adjust: '管理员调整', system: '系统'
  }
  return map[type] || type || '-'
}

const changeTypeClass = type => {
  if (!type) return ''
  if (type === 'recharge' || type === 'refund') return 'green'
  if (type === 'ai_charge' || type === 'ai_image_charge' || type.startsWith('deduct')) return 'red'
  return 'orange'
}

const refTypeLabel = type => {
  if (!type) return '-'
  const map = {
    ai_usage: 'AI 调用', payment_order: '支付订单', payment: '支付订单',
    image_gen: 'AI 生图', admin: '管理员', system: '系统'
  }
  return map[type] || type
}

async function loadTokenLedger(page = 1) {
  tokenLoading.value = true
  tokenLoadError.value = ''
  try {
    const res = await getTokenLedger({ current: page, size: tokenLedger.size })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Token 记录响应格式异常')
    if (!Array.isArray(data.records)) throw new Error('Token 记录响应格式异常')
    const records = data.records
    tokenLedger.records = records.map((record, index) => {
      const changeAmount = nullableNumber(record.changeAmount ?? record.amount ?? record.changeValue)
      const beforeBalance = nullableNumber(record.beforeBalance ?? record.balanceBefore ?? record.prevBalance)
      const afterBalance = nullableNumber(record.afterBalance ?? record.balanceAfter ?? record.nextBalance)

      return {
        ...record,
        id: record.id ?? `${page}-${index}`,
        createdTime: record.createdTime || record.createTime || record.changeTime || record.time || '',
        changeType: record.changeType || record.type || '',
        refType: record.refType || record.sourceType || record.source || '',
        changeAmount,
        beforeBalance,
        afterBalance,
        remark: record.remark || record.description || record.desc || ''
      }
    })
    const total = Number(data.total)
    const current = Number(data.current)
    const size = Number(data.size)
    if (!Number.isSafeInteger(total) || total < records.length
      || !Number.isSafeInteger(current) || current < 1
      || !Number.isSafeInteger(size) || size < 1) {
      throw new Error('Token 记录分页响应格式异常')
    }
    tokenLedger.total = total
    tokenLedger.current = current
    tokenLedger.size = size
    const stats = data.stats
    if (!stats || typeof stats !== 'object' || Array.isArray(stats)) throw new Error('Token 统计响应格式异常')
    const todayConsume = nullableNumber(stats.todayConsume)
    const sevenDayConsume = nullableNumber(stats.sevenDayConsume)
    const tokenBalance = nullableNumber(stats.tokenBalance)
    if ([todayConsume, sevenDayConsume, tokenBalance].some(value => value === null || value < 0)) {
      throw new Error('Token 统计响应缺少有效指标')
    }
    tokenStats.todayConsume = todayConsume
    tokenStats.sevenDayConsume = sevenDayConsume
    tokenStats.tokenBalance = tokenBalance
    jumpPage.value = tokenLedger.current
  } catch (error) {
    tokenLedger.records = []
    tokenLedger.total = 0
    Object.assign(tokenStats, { todayConsume: null, sevenDayConsume: null, tokenBalance: null })
    tokenLoadError.value = error?.message || 'Token 记录加载失败，请重试。'
  } finally {
    tokenLoading.value = false
  }
}

function goToJumpPage() {
  const target = Number(jumpPage.value)
  if (!Number.isFinite(target) || target < 1) {
    return
  }
  const targetPage = Math.min(Math.max(1, Math.floor(target)), totalPages.value)
  jumpPage.value = targetPage
  if (targetPage !== tokenLedger.current) loadTokenLedger(targetPage)
}

async function loadOverview() {
  overviewLoadError.value = ''
  overviewAvailable.value = false
  try {
    const res = await getProfileOverview()
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)
      || typeof res.data.phoneVerified !== 'boolean'
      || typeof res.data.emailVerified !== 'boolean'
      || !res.data.stats || typeof res.data.stats !== 'object' || Array.isArray(res.data.stats)) {
      throw new Error('个人中心响应格式异常')
    }
    Object.keys(overview).forEach(key => delete overview[key])
    Object.assign(overview, res.data)
    overviewAvailable.value = true
    return true
  } catch (error) {
    Object.keys(overview).forEach(key => delete overview[key])
    overviewLoadError.value = `${error?.message || '个人中心数据加载失败'}；未取得的资料与指标显示为“—”。`
    return false
  }
}

async function submitPassword() {
  if (!passwordForm.oldPassword || !passwordForm.newPassword) return showNotice('请完整填写密码信息', 'warn')
  if (passwordForm.newPassword.length < 8) return showNotice('新密码至少 8 位', 'warn')
  if (passwordForm.newPassword !== passwordForm.confirmPassword) return showNotice('两次输入的新密码不一致', 'warn')
  saving.value = true
  try {
    await changeProfilePassword({ oldPassword: passwordForm.oldPassword, newPassword: passwordForm.newPassword })
    Object.assign(passwordForm, { oldPassword: '', newPassword: '', confirmPassword: '' })
    await loadOverview()
    showNotice('密码已修改', 'success')
  } catch (error) {
    showNotice(error.message || '密码修改失败', 'error')
  } finally {
    saving.value = false
  }
}

async function sendCode(type) {
  if (!profileVerificationCapability.value.available) return
  const target = type === 'phone' ? phoneForm.phone : emailForm.email
  if (!target) return showNotice(type === 'phone' ? '请先输入手机号' : '请先输入邮箱', 'warn')
  try {
    const res = await sendProfileCode({ targetType: type, target, purpose: type === 'phone' ? 'change_phone' : 'change_email' })
    const code = res.data?.debugCode ? `，开发验证码：${res.data.debugCode}` : ''
    showNotice(`验证码已发送${code}`, 'success')
  } catch (error) {
    showNotice(error.message || '验证码发送失败', 'error')
  }
}

async function submitPhone() {
  if (!profileVerificationCapability.value.available) return
  if (!phoneForm.phone || !phoneForm.code) return showNotice('请填写手机号和验证码', 'warn')
  saving.value = true
  try {
    await changeProfilePhone({ phone: phoneForm.phone, code: phoneForm.code })
    Object.assign(phoneForm, { phone: '', code: '' })
    await loadOverview()
    showNotice('手机号已更新', 'success')
  } catch (error) {
    showNotice(error.message || '手机号修改失败', 'error')
  } finally { saving.value = false }
}

async function submitEmail() {
  if (!profileVerificationCapability.value.available) return
  if (!emailForm.email || !emailForm.code) return showNotice('请填写邮箱和验证码', 'warn')
  saving.value = true
  try {
    await changeProfileEmail({ email: emailForm.email, code: emailForm.code })
    Object.assign(emailForm, { email: '', code: '' })
    await loadOverview()
    showNotice('邮箱已更新', 'success')
  } catch (error) {
    showNotice(error.message || '邮箱修改失败', 'error')
  } finally { saving.value = false }
}

function displayDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function displayDateOnly(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10)
  const pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN') : '—'
}

function formatSignedNumber(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  const text = Math.abs(n).toLocaleString('zh-CN')
  return `${n >= 0 ? '+' : '-'}${text}`
}

function nullableNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function changeAmountClass(value) {
  if (value === null || value === undefined) return ''
  return Number(value) >= 0 ? 'pos' : 'neg'
}

function formatUserStatus(value) {
  if (value == null || value === '' || value === 'null' || value === 'undefined') return '-'
  const status = Number(value)
  if (status === 1) return '正常'
  if (status === 0) return '禁用'
  return String(value)
}

function maskPhone(value) {
  if (!value || value === 'null' || value === 'undefined') return ''
  const s = String(value)
  return s.length >= 11 ? `${s.slice(0, 3)}****${s.slice(7)}` : s
}

function maskEmail(value) {
  if (!value || value === 'null' || value === 'undefined') return ''
  const s = String(value)
  const at = s.indexOf('@')
  return at > 1 ? `${s.slice(0, 1)}***${s.slice(at)}` : s
}

async function handleQuickAction(action) {
  if (action === 'security' || action === 'token') { activeTab.value = action; return }
  if (action === 'payment' || action === 'vip') {
    await globalConfirm.alert('暂未开放', '会员升级与续费功能暂未开放，敬请期待。')
    return
  }
  if (action === 'products') location.hash = '#/products'
}

function normalizeProfileTab(tab) {
  return PROFILE_MAIN_TABS.has(tab) ? tab : 'overview'
}

function consumeRequestedProfileTab() {
  const tab = localStorage.getItem(PROFILE_ENTRY_STORAGE_KEY)
  if (!tab) return
  localStorage.removeItem(PROFILE_ENTRY_STORAGE_KEY)
  activeTab.value = normalizeProfileTab(tab)
}

async function handleTokenPaid() {
  paymentVisible.value = false
  const refreshed = await loadOverview()
  showNotice(refreshed ? '支付成功，Token 余额已刷新' : '支付成功，但余额刷新失败，请稍后重试', refreshed ? 'success' : 'warn')
}

function onHeaderAction(event) {
  if (event.detail === 'refresh-profile') loadOverview()
}

function onProfileTabOpen(event) {
  activeTab.value = normalizeProfileTab(event.detail)
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  window.addEventListener('xya-profile-open-tab', onProfileTabOpen)
  consumeRequestedProfileTab()
  refreshAuthCapabilities()
  loadOverview()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
  window.removeEventListener('xya-profile-open-tab', onProfileTabOpen)
})

watch(activeTab, (tab) => {
  if (tab === 'token') loadTokenLedger()
})
</script>

<style scoped>
.profile-center {
  width: 100%;
}

.profile-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.profile-side,
.profile-main,
.content-panel {
  min-width: 0;
}

.profile-side-card,
.welcome-hero,
.member-panel,
.token-panel,
.account-panel,
.quick-panel,
.content-panel {
  border-radius: 24px;
  border: 1px solid rgba(229, 236, 247, 0.96);
  box-shadow: 0 12px 34px rgba(29, 53, 87, 0.05);
}

.profile-side-card {
  position: relative;
  padding: 12px;
  background:
    radial-gradient(circle at top left, rgba(13, 107, 255, 0.06), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #f7faff 100%);
}

.profile-side-head {
  display: none;
}

.profile-side-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.profile-side-tab {
  position: relative;
  display: flex;
  align-items: center;
  gap: 9px;
  flex: 1 1 180px;
  width: auto;
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid rgba(219, 228, 243, 0.9);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
  color: #50617d;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.profile-side-tab::before {
  content: '';
  position: absolute;
  left: -1px;
  top: 10px;
  bottom: 10px;
  width: 4px;
  border-radius: 999px;
  background: transparent;
  transition: background 0.18s ease;
}

.profile-side-tab:hover {
  transform: translateY(-1px);
  border-color: rgba(13, 107, 255, 0.22);
  box-shadow: 0 12px 28px rgba(13, 107, 255, 0.08);
}

.profile-side-tab.active {
  color: #0d6bff;
  border-color: rgba(13, 107, 255, 0.2);
  background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
  box-shadow: 0 16px 36px rgba(13, 107, 255, 0.12);
}

.profile-side-tab.active::before {
  background: linear-gradient(180deg, #7cb8ff 0%, #0d6bff 100%);
}

.profile-side-tab-icon {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #eef4ff;
  color: #0d6bff;
  flex: 0 0 auto;
}

.profile-side-tab-icon svg {
  width: 16px;
  height: 16px;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.profile-side-tab.active .profile-side-tab-icon {
  background: linear-gradient(145deg, #dbeafe 0%, #bfdbfe 100%);
}

.profile-side-tab-label {
  font-size: 13px;
  font-weight: 700;
}

.profile-main-section {
  display: grid;
  gap: 16px;
}

.welcome-hero {
  position: relative;
  overflow: hidden;
  min-height: 190px;
  padding: 24px 28px 22px;
  background:
    radial-gradient(circle at 14% 50%, rgba(255, 255, 255, 0.08), transparent 18%),
    radial-gradient(circle at 81% 34%, rgba(255, 255, 255, 0.42), transparent 18%),
    radial-gradient(circle at 68% 54%, rgba(229, 240, 255, 0.34), transparent 22%),
    linear-gradient(92deg, #6aaefe 0%, #7dbbff 18%, #9ccaff 57%, #bbdbff 100%);
}

.welcome-hero::before {
  content: '';
  position: absolute;
  inset: 10px 210px 10px 46%;
  background:
    radial-gradient(ellipse at 58% 56%, transparent 58%, rgba(255, 255, 255, 0.18) 59%, transparent 60%),
    radial-gradient(ellipse at 58% 56%, transparent 70%, rgba(255, 255, 255, 0.14) 71%, transparent 72%),
    radial-gradient(ellipse at 58% 56%, transparent 82%, rgba(255, 255, 255, 0.12) 83%, transparent 84%);
  opacity: 0.7;
  pointer-events: none;
}

.welcome-hero::after {
  content: '';
  position: absolute;
  inset: 14px;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  pointer-events: none;
}

.welcome-content {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 22px;
  max-width: calc(100% - 388px);
}

.welcome-avatar {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 24px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.92) 0%, rgba(231, 242, 255, 0.85) 100%);
  border: 1px solid rgba(255, 255, 255, 0.46);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92), 0 20px 40px rgba(22, 76, 163, 0.18);
}

.welcome-avatar svg {
  width: 74px;
  height: 74px;
}

.welcome-text h2 {
  margin: 0;
  font-size: 39px;
  color: #ffffff;
  font-weight: 800;
  line-height: 1.12;
  letter-spacing: -0.02em;
  text-shadow: 0 10px 24px rgba(45, 98, 177, 0.18);
}

.wave {
  font-size: 24px;
}

.welcome-text p {
  margin: 8px 0 14px;
  color: rgba(245, 249, 255, 0.98);
  font-size: 14px;
  max-width: 680px;
}

.welcome-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.86);
  color: #4a5f7f;
  font-size: 11px;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(31, 53, 94, 0.035);
}

.plan-chip {
  color: #1674ff;
  border-color: rgba(255, 255, 255, 0.36);
  background: linear-gradient(135deg, rgba(244, 250, 255, 0.98) 0%, rgba(223, 238, 255, 0.94) 100%);
}

.subtle-chip {
  background: rgba(255, 255, 255, 0.76);
}

.warn-chip {
  background: #fff5e6;
  border-color: #fde3bb;
  color: #d97706;
}

.welcome-visual {
  position: absolute;
  right: 14px;
  top: 0;
  width: 372px;
  height: 188px;
  pointer-events: none;
  z-index: 1;
}

.welcome-visual-glow {
  position: absolute;
  inset: 16px 24px 16px 38px;
  border-radius: 68px;
  background: radial-gradient(circle at 50% 55%, rgba(255, 255, 255, 0.3) 0%, rgba(202, 228, 255, 0.18) 36%, transparent 74%);
  filter: blur(8px);
}

.welcome-visual-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center;
  filter: drop-shadow(0 22px 30px rgba(61, 113, 224, 0.13));
}

.profile-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 116px;
  padding: 17px 16px;
  border-radius: 18px;
  border: 1px solid rgba(228, 235, 247, 0.96);
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.98), transparent 36%),
    linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  box-shadow: 0 10px 28px rgba(31, 53, 94, 0.045);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04), 0 16px 32px rgba(31, 53, 94, 0.08);
  border-color: rgba(13, 107, 255, 0.16);
}

.stat-card-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stat-card .stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #edf4ff 0%, #dbeafe 100%);
  color: #0d6bff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
}

.stat-icon-img {
  width: 28px;
  height: 28px;
  object-fit: contain;
  filter: drop-shadow(0 8px 16px rgba(31, 53, 94, 0.12));
}

.stat-card .stat-icon.green {
  background: linear-gradient(145deg, #e8fbef 0%, #c9f2d8 100%);
  color: #16a34a;
}

.stat-card .stat-icon.orange {
  background: linear-gradient(145deg, #fff6e8 0%, #ffe0ae 100%);
  color: #f59e0b;
}

.stat-card .stat-icon.purple {
  background: linear-gradient(145deg, #f3ecff 0%, #e3d4ff 100%);
  color: #8b5cf6;
}

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.stat-info span {
  font-size: 13px;
  font-weight: 700;
  color: #667491;
}

.stat-info strong {
  font-size: 28px;
  line-height: 1;
  font-weight: 900;
  color: #17213d;
  font-family: 'SF Mono', 'JetBrains Mono', 'Cascadia Code', monospace;
}

.stat-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
}

.stat-card-foot em {
  font-style: normal;
  font-size: 11px;
  color: #7a879e;
}

.stat-wave {
  width: 84px;
  height: 18px;
  flex: 0 0 auto;
}

.stat-wave path {
  fill: none;
  stroke: #5b7cff;
  stroke-width: 3;
  stroke-linecap: round;
}

.stat-wave.green path {
  stroke: #22c55e;
}

.stat-wave.orange path {
  stroke: #fb923c;
}

.stat-wave.purple path {
  stroke: #8b5cf6;
}

.two-col-grid,
.overview-bottom-grid {
  display: grid;
  gap: 16px;
}

.two-col-grid {
  grid-template-columns: minmax(0, 1.5fr) minmax(300px, 1fr);
}

.overview-bottom-grid {
  grid-template-columns: minmax(0, 1.68fr) minmax(320px, 0.96fr);
}

.profile-overview .panel-head {
  margin-bottom: 12px;
}

.profile-overview .panel-head h3 {
  font-size: 17px;
}

.profile-overview .member-panel,
.profile-overview .token-panel,
.profile-overview .account-panel,
.profile-overview .quick-panel {
  padding: 18px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.panel-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.panel-head-mark {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border: 1px solid rgba(226, 234, 245, 0.95);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
}

.panel-head-mark.gold {
  background: linear-gradient(145deg, #fff8e5 0%, #ffe8ab 100%);
}

.panel-head-mark.violet {
  background: linear-gradient(145deg, #f5ecff 0%, #ead8ff 100%);
}

.panel-head-mark.blue {
  background: linear-gradient(145deg, #eef5ff 0%, #dbeafe 100%);
}

.panel-head-mark.mint {
  background: linear-gradient(145deg, #ecfbf3 0%, #d7f5e5 100%);
}

.panel-head-icon {
  width: 14px;
  height: 14px;
  object-fit: contain;
}

.panel-head h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #17213d;
}

.panel-head p {
  margin: 6px 0 0;
  color: #667491;
  font-size: 13px;
  line-height: 1.6;
}

.member-panel {
  background:
    radial-gradient(circle at top left, rgba(255, 233, 183, 0.14), transparent 28%),
    linear-gradient(180deg, #ffffff 0%, #fffdfa 100%);
}

.member-card-inner {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background:
    radial-gradient(circle at 12% 50%, rgba(255, 236, 179, 0.34), transparent 28%),
    radial-gradient(circle at 92% 18%, rgba(255, 255, 255, 0.9), transparent 22%),
    linear-gradient(135deg, #fffaf1 0%, #ffffff 68%);
  border: 1px solid rgba(248, 227, 177, 0.9);
  border-radius: 18px;
  margin-bottom: 12px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.88),
    0 12px 24px rgba(234, 179, 8, 0.08);
}

.member-card-inner::after {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.56);
  pointer-events: none;
}

.member-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.crown-big {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-radius: 18px;
  box-shadow: 0 16px 28px rgba(234, 179, 8, 0.18);
}

.member-card-icon {
  width: 30px;
  height: 30px;
  object-fit: contain;
  filter: drop-shadow(0 10px 18px rgba(234, 179, 8, 0.18));
}

.member-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.member-name-row strong {
  font-size: 24px;
  font-weight: 800;
  color: var(--text);
  line-height: 1.1;
}

.member-sub {
  display: block;
  margin-top: 2px;
  color: #98a2b3;
  font-size: 12px;
}

.member-actions {
  display: flex;
  gap: 10px;
}

.benefits-row {
  display: grid;
  gap: 8px;
}

.benefits-label {
  font-size: 12px;
  color: #667491;
  font-weight: 700;
}

.benefits-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 9px;
}

.benefit-feature {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 8px 9px;
  border-radius: 15px;
  border: 1px solid rgba(229, 236, 247, 0.9);
  background:
    radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.9), transparent 36%),
    linear-gradient(180deg, #fbfdff 0%, #f6f9ff 100%);
  box-shadow: 0 8px 18px rgba(31, 53, 94, 0.035);
  text-align: center;
}

.benefit-feature-icon {
  width: 28px;
  height: 28px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 30% 30%, #ffffff 0%, #e9f1ff 66%, #dce7ff 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.benefit-feature-label {
  font-size: 11px;
  line-height: 1.25;
  color: #51627c;
  font-weight: 700;
}

.benefit-icon {
  width: 15px;
  height: 15px;
  object-fit: contain;
}

.token-panel {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at top right, rgba(139, 92, 246, 0.2), transparent 34%),
    radial-gradient(circle at left center, rgba(255, 255, 255, 0.84), transparent 32%),
    linear-gradient(135deg, #f5f3ff 0%, #faf5ff 44%, #fdf4ff 100%);
  border-color: #ede9fe;
}

.token-panel::after {
  content: '';
  position: absolute;
  inset: 14px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.48);
  pointer-events: none;
}

.token-amount {
  margin-bottom: 14px;
}

.token-label {
  display: block;
  font-size: 12px;
  color: #667491;
  font-weight: 700;
}

.token-amount strong {
  display: block;
  margin-top: 4px;
  font-size: 38px;
  font-weight: 900;
  color: #6d28d9;
  line-height: 1.02;
  font-family: -apple-system, 'SF Pro Display', 'PingFang SC', sans-serif;
}

.token-amount strong em {
  font-size: 16px;
  font-weight: 700;
  font-style: normal;
  color: #7c3aed;
  margin-left: 4px;
}

.token-plan {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #98a2b3;
}

.recharge-btn {
  background: linear-gradient(90deg, #7c3aed, #8b5cf6) !important;
  border-color: #7c3aed !important;
  box-shadow: 0 8px 18px rgba(124, 58, 237, 0.25) !important;
}

.token-coin {
  position: absolute;
  right: 8px;
  top: 0;
  bottom: 0;
  transform: none;
  width: 184px;
  height: 100%;
  opacity: 0.96;
}

.token-coin-glow {
  position: absolute;
  inset: 18px 12px 18px 24px;
  border-radius: 50%;
  background: radial-gradient(circle at center, rgba(139, 92, 246, 0.24) 0%, rgba(139, 92, 246, 0.09) 42%, transparent 76%);
  filter: blur(12px);
}

.token-coin-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center;
  filter: drop-shadow(0 22px 28px rgba(124, 58, 237, 0.18));
}

.account-panel,
.quick-panel,
.content-panel {
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.96), transparent 28%),
    linear-gradient(180deg, #ffffff 0%, #fcfdff 100%);
}

.security-panel,
.token-ledger-panel {
  padding: 20px 18px 18px;
}

.security-panel > .panel-head,
.token-ledger-panel > .panel-head {
  margin-bottom: 18px;
}

.account-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.account-info-item {
  min-height: 72px;
  padding: 13px 15px;
  border-radius: 18px;
  border: 1px solid #e7eef8;
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 8px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
}

.account-info-label {
  font-size: 11px;
  font-weight: 700;
  color: #8b98ad;
}

.account-info-value-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.account-info-value-row strong {
  font-size: 14px;
  line-height: 1.3;
  color: #17213d;
  font-weight: 800;
  word-break: break-all;
}

.quick-grid-2col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.quick-action-btn {
  min-height: 96px;
  padding: 16px;
  border: 1px solid #e8eef8;
  border-radius: 18px;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.96), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
  text-align: left;
  gap: 12px;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.quick-action-btn:hover {
  transform: translateY(-2px);
  border-color: rgba(13, 107, 255, 0.16);
  box-shadow: 0 16px 30px rgba(31, 53, 94, 0.07);
}

.quick-action-btn .circle-ico {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
}

.quick-card-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  gap: 4px;
}

.quick-icon-img {
  width: 26px;
  height: 26px;
  object-fit: contain;
  filter: drop-shadow(0 8px 14px rgba(31, 53, 94, 0.12));
}

.quick-action-btn b {
  font-size: 13px;
}

.quick-action-btn span {
  font-size: 12px;
}

.quick-action-btn b {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0;
}

.quick-action-btn span {
  font-size: 12px;
  color: #7a879e;
  line-height: 1.55;
}

.security-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.security-card {
  border: 1px solid rgba(225, 235, 248, 0.96);
  border-radius: 22px;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.98), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  padding: 22px 20px 20px;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  box-shadow: 0 12px 28px rgba(31, 53, 94, 0.05);
}

.security-card.enhanced {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 286px;
}

.security-card.enhanced:hover {
  transform: translateY(-2px);
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04), 0 16px 32px rgba(31, 53, 94, 0.1);
  border-color: rgba(13, 107, 255, 0.25);
}

.security-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
}

.security-card-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eef5ff;
  color: var(--primary);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.security-card-icon.green { background: #e7f8f0; color: #16bf78; }
.security-card-icon.orange { background: #fff5e6; color: #ff9f22; }
.security-card-icon.blue { background: #eef5ff; color: var(--primary); }

.security-card b {
  display: block;
  color: var(--text);
  font-size: 18px;
  font-weight: 800;
}

.security-card > span {
  display: block;
  min-height: 50px;
  margin: 0;
  color: #667491;
  font-size: 13px;
  line-height: 1.7;
}

.security-card .badge { margin-bottom: 8px; }
.security-card .app-btn {
  width: 100%;
  min-width: 0;
  margin-top: auto;
  align-self: stretch;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 800;
  box-shadow: 0 14px 24px rgba(13, 107, 255, 0.2);
}

.security-card-note {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  margin: 4px 0 6px;
  padding: 0 14px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(238, 245, 255, 0.92), rgba(245, 249, 255, 0.78));
  color: #6a7a95;
  font-size: 11px;
  font-weight: 700;
}

.security-card-note.ok {
  background: linear-gradient(90deg, rgba(232, 251, 239, 0.98), rgba(244, 255, 248, 0.84));
  color: #0f9f63;
}

.security-card-note.warn {
  background: linear-gradient(90deg, rgba(255, 247, 234, 0.98), rgba(255, 250, 242, 0.88));
  color: #d97706;
}

.security-card-note-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  flex: 0 0 auto;
  opacity: 0.9;
}

.security-level-card {
  --security-accent: #ff9f22;
  --security-accent-rgb: 255, 159, 34;
  position: relative;
  display: grid;
  grid-template-columns: 272px minmax(0, 1fr);
  align-items: center;
  gap: 18px;
  padding: 24px 26px 16px;
  border-radius: 24px;
  margin-bottom: 18px;
  border: 1px solid rgba(238, 227, 201, 0.9);
  background:
    radial-gradient(circle at 12% 58%, rgba(var(--security-accent-rgb), 0.14), transparent 22%),
    radial-gradient(circle at 82% 35%, rgba(255, 255, 255, 0.28), transparent 18%),
    linear-gradient(135deg, #fff8ea, #fffefb 70%, #ffffff);
  overflow: hidden;
  box-shadow: 0 22px 46px rgba(31, 53, 94, 0.055);
}

.security-level-card::before {
  content: '';
  position: absolute;
  inset: 12px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.56);
  pointer-events: none;
}

.security-level-card.high {
  --security-accent: #16bf78;
  --security-accent-rgb: 22, 191, 120;
  background:
    radial-gradient(circle at 12% 58%, rgba(var(--security-accent-rgb), 0.12), transparent 24%),
    radial-gradient(circle at 82% 35%, rgba(255, 255, 255, 0.24), transparent 18%),
    linear-gradient(135deg, #ebfaf1, #ffffff);
  border-color: #bfe7ce;
}

.security-level-card.medium {
  --security-accent: #ff9f22;
  --security-accent-rgb: 255, 159, 34;
  background:
    radial-gradient(circle at 12% 58%, rgba(var(--security-accent-rgb), 0.16), transparent 22%),
    radial-gradient(circle at 82% 35%, rgba(255, 255, 255, 0.24), transparent 18%),
    linear-gradient(135deg, #fff7e9, #ffffff);
  border-color: #fde1b3;
}

.security-level-card.low {
  --security-accent: #ff5b61;
  --security-accent-rgb: 255, 91, 97;
  background:
    radial-gradient(circle at 12% 58%, rgba(var(--security-accent-rgb), 0.12), transparent 24%),
    radial-gradient(circle at 82% 35%, rgba(255, 255, 255, 0.24), transparent 18%),
    linear-gradient(135deg, #fff2f2, #ffffff);
  border-color: #f9cbcb;
}

.security-level-main {
  position: relative;
  z-index: 1;
  min-width: 0;
  padding-right: 6px;
}

.security-level-visual {
  position: relative;
  min-height: 206px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.security-level-visual::after {
  content: '';
  position: absolute;
  left: 40px;
  right: 54px;
  bottom: 26px;
  height: 18px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.64), rgba(255, 255, 255, 0.22));
  opacity: 0.88;
  filter: blur(0.4px);
}

.security-level-visual-ring {
  position: absolute;
  inset: 36px 6px 14px 2px;
  border-radius: 50%;
  background: radial-gradient(circle at center, rgba(var(--security-accent-rgb), 0.24), rgba(var(--security-accent-rgb), 0.08) 42%, transparent 72%);
  filter: blur(1px);
}

.security-level-visual-image {
  position: relative;
  width: 100%;
  height: 204px;
  object-fit: contain;
  object-position: center bottom;
  filter: sepia(0.84) saturate(1.34) hue-rotate(-18deg) brightness(1.05) drop-shadow(0 24px 28px rgba(255, 159, 34, 0.14));
}

.security-level-visual-illustration {
  position: relative;
  width: 100%;
  height: 206px;
  overflow: visible;
  z-index: 1;
}

.security-illustration-shape {
  fill: rgba(var(--security-accent-rgb), 0.08);
}

.security-illustration-shape.shape-left {
  opacity: 1;
}

.security-illustration-shape.shape-right {
  fill: rgba(var(--security-accent-rgb), 0.06);
}

.security-orbit-glow {
  fill: rgba(var(--security-accent-rgb), 0.1);
}

.security-orbit-line,
.security-orbit-dash {
  fill: none;
  stroke: rgba(var(--security-accent-rgb), 0.44);
  stroke-linecap: round;
}

.security-orbit-line {
  stroke-width: 3;
}

.security-orbit-dash {
  stroke-width: 2.5;
  stroke-dasharray: 7 8;
  opacity: 0.88;
}

.security-orbit-dot {
  fill: rgba(var(--security-accent-rgb), 0.92);
}

.security-orbit-dot.dot-top {
  fill: rgba(var(--security-accent-rgb), 0.72);
}

.security-stage-shadow {
  fill: rgba(var(--security-accent-rgb), 0.12);
}

.security-stage-plate {
  stroke: rgba(255, 255, 255, 0.92);
}

.security-stage-plate.outer {
  fill: rgba(255, 255, 255, 0.32);
  stroke-width: 5;
}

.security-stage-plate.middle {
  fill: rgba(255, 255, 255, 0.56);
  stroke-width: 4;
}

.security-stage-core {
  fill: rgba(255, 255, 255, 0.78);
  stroke: rgba(255, 255, 255, 0.94);
  stroke-width: 3;
}

.security-shield-back {
  fill: rgba(var(--security-accent-rgb), 0.22);
}

.security-shield-front {
  fill: var(--security-accent);
  filter: drop-shadow(0 16px 22px rgba(var(--security-accent-rgb), 0.16));
}

.security-shield-gloss {
  fill: rgba(255, 255, 255, 0.28);
}

.security-shield-outline {
  fill: none;
  stroke: rgba(255, 255, 255, 0.7);
  stroke-width: 3;
}

.security-shield-check {
  fill: none;
  stroke: #fff;
  stroke-width: 9;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.security-level-topline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.security-level-info {
  display: flex;
  align-items: flex-start;
  gap: 0;
  flex: 1 1 auto;
}

.security-level-icon {
  display: none;
}

.security-level-text h4 {
  margin: 0;
  font-size: 15px;
  color: #667491;
  font-weight: 700;
}

.security-level-text strong {
  display: block;
  margin: 4px 0 10px;
  font-size: 58px;
  line-height: 1;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: var(--text);
}

.security-level-card.high .security-level-text strong { color: #0a8a55; }
.security-level-card.medium .security-level-text strong { color: #b45309; }
.security-level-card.low .security-level-text strong { color: #dc2626; }

.security-level-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.security-risk-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  height: 30px;
  border-radius: 999px;
  background: rgba(255, 247, 234, 0.94);
  color: #c26c06;
  font-size: 12px;
  font-weight: 800;
}

.security-risk-pill::before {
  content: '!';
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #ff9f22;
  color: #fff;
  font-size: 11px;
  font-weight: 900;
}

.security-risk-pill.safe {
  background: rgba(232, 251, 239, 0.98);
  color: #0f9f63;
}

.security-risk-pill.safe::before {
  content: '✓';
  background: #16bf78;
}

.security-level-text p {
  margin: 0;
  max-width: 540px;
  font-size: 13px;
  color: #7a879e;
  line-height: 1.5;
}

.security-risk-pill.safe::before {
  content: '✓';
}

.security-link-hint {
  color: #0d6bff;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  position: relative;
  padding-right: 14px;
}

.security-link-hint::after {
  content: '';
  position: absolute;
  top: 50%;
  right: 1px;
  width: 6px;
  height: 6px;
  border-top: 1.8px solid currentColor;
  border-right: 1.8px solid currentColor;
  transform: translateY(-50%) rotate(45deg);
}

.security-risk-pill.safe::before {
  content: '\2713';
  background: #16bf78;
}

.security-progress-wrap {
  margin-top: 14px;
}

.security-progress {
  position: relative;
  height: 7px;
  border-radius: 999px;
  background:
    linear-gradient(90deg, rgba(255, 187, 71, 0.16) 0 33.333%, rgba(255, 187, 71, 0.1) 33.333% 66.666%, rgba(255, 187, 71, 0.06) 66.666% 100%);
  overflow: hidden;
}

.security-progress::before,
.security-progress::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  z-index: 1;
}

.security-progress::before {
  left: calc(33.333% - 4px);
}

.security-progress::after {
  left: calc(66.666% - 4px);
}

.security-progress-bar {
  position: relative;
  z-index: 0;
  height: 100%;
  border-radius: 999px;
  box-shadow: 0 8px 16px rgba(255, 159, 34, 0.24);
  transition: width 0.35s ease;
}

.security-level-card.high .security-progress-bar { background: linear-gradient(90deg, #16bf78, #0a8a55); }
.security-level-card.medium .security-progress-bar { background: linear-gradient(90deg, #ffb547, #ff9f22); }
.security-level-card.low .security-progress-bar { background: linear-gradient(90deg, #ff8a8a, #ff5b61); }

.security-progress-labels {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 11px;
  color: #a0abc0;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
}

.security-progress-labels span.active {
  color: var(--security-accent);
}

.security-meta {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
  font-size: 12px;
  color: #7a879e;
}

.security-tips {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  align-items: center;
  gap: 20px;
  margin-top: 18px;
  padding: 18px 18px 18px 18px;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.96), transparent 34%),
    linear-gradient(180deg, #fcfdff 0%, #f7faff 100%);
  border: 1px solid #e6eefa;
  border-radius: 22px;
}

.security-tips-copy h4 {
  margin: 0 0 12px;
  font-size: 17px;
  font-weight: 800;
  color: var(--text);
}

.security-tips-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.security-tip-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-height: 96px;
  padding: 16px 14px;
  border-radius: 16px;
  border: 1px solid rgba(225, 235, 248, 0.9);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.84);
}

.security-tip-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  background: #eef5ff;
}

.security-tip-icon svg {
  width: 22px;
  height: 22px;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.security-tip-icon.blue { background: linear-gradient(145deg, #eef5ff 0%, #dbeafe 100%); color: #0d6bff; }
.security-tip-icon.mint { background: linear-gradient(145deg, #ecfbf3 0%, #d8f7e7 100%); color: #16bf78; }
.security-tip-icon.violet { background: linear-gradient(145deg, #f5ecff 0%, #e9dcff 100%); color: #8b5cf6; }
.security-tip-icon.sky { background: linear-gradient(145deg, #edf9ff 0%, #d8efff 100%); color: #4f86ff; }

.security-tip-copy {
  min-width: 0;
}

.security-tip-copy strong {
  display: block;
  color: #17213d;
  font-size: 15px;
  font-weight: 800;
}

.security-tip-copy p {
  margin: 6px 0 0;
  color: #667491;
  font-size: 12px;
  line-height: 1.65;
}

.security-tips-visual {
  position: relative;
  min-height: 154px;
}

.security-tips-visual-ring {
  position: absolute;
  inset: 20px 24px 20px 24px;
  border-radius: 50%;
  background: radial-gradient(circle at center, rgba(98, 156, 255, 0.16), rgba(98, 156, 255, 0.04) 54%, transparent 76%);
}

.security-tips-image {
  position: relative;
  width: 100%;
  height: 154px;
  object-fit: contain;
  filter: sepia(0.12) saturate(1.1) hue-rotate(-5deg) drop-shadow(0 18px 28px rgba(76, 131, 224, 0.16));
}

.security-card .app-btn {
  width: auto;
  min-width: 112px;
  margin-top: auto;
  align-self: flex-start;
  border-radius: 12px;
  font-size: 14px;
  box-shadow: 0 10px 20px rgba(13, 107, 255, 0.18);
}

.profile-side-card {
  position: sticky;
  top: 0;
  padding: 16px 12px;
  border-radius: 24px;
  border: 1px solid rgba(229, 236, 247, 0.96);
  background:
    radial-gradient(circle at top left, rgba(13, 107, 255, 0.06), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #f7faff 100%);
  box-shadow: 0 12px 34px rgba(29, 53, 87, 0.05);
}

.profile-side-nav {
  display: grid;
  grid-template-columns: 1fr;
  justify-content: stretch;
  gap: 6px;
}

.profile-side-tab {
  flex: none;
  width: 100%;
  padding: 10px 11px;
  border-radius: 16px;
}

.profile-side-tab-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
}

.profile-side-tab-label {
  font-size: 13px;
}

.profile-side-head {
  display: block;
  margin-bottom: 8px;
}

.profile-side-head h2 {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  color: #17213d;
}

.profile-shell {
  grid-template-columns: 188px minmax(0, 1fr);
  gap: 14px;
}

.welcome-hero {
  min-height: 176px;
  padding: 20px 24px 18px;
}

.account-info-grid,
.quick-grid-2col {
  gap: 12px;
}

.account-info-item {
  min-height: 62px;
  padding: 11px 13px;
  border-radius: 16px;
}

.account-info-label {
  font-size: 10px;
}

.account-info-value-row strong {
  font-size: 13px;
}

.quick-action-btn {
  min-height: 84px;
  padding: 13px;
  border-radius: 16px;
  gap: 10px;
}

.quick-action-btn .circle-ico {
  width: 40px;
  height: 40px;
}

.quick-icon-img {
  width: 24px;
  height: 24px;
}

.quick-card-copy {
  gap: 3px;
}

.quick-action-btn b {
  font-size: 14px;
}

.quick-action-btn span {
  font-size: 11px;
  line-height: 1.45;
}

.security-level-card {
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: 10px;
  padding: 14px 16px 10px;
  margin-bottom: 10px;
  box-shadow: 0 14px 30px rgba(31, 53, 94, 0.045);
}

.security-level-card::before {
  display: none;
}

.security-level-card.high,
.security-level-card.medium,
.security-level-card.low {
  background:
    radial-gradient(circle at 10% 50%, rgba(var(--security-accent-rgb), 0.1), transparent 20%),
    linear-gradient(135deg, #fff8ea 0%, #fffdf7 58%, #ffffff 100%);
}

.security-level-card.high {
  border-color: #cde8d9;
  background:
    radial-gradient(circle at 10% 50%, rgba(22, 191, 120, 0.1), transparent 20%),
    linear-gradient(135deg, #effbf4 0%, #fbfffd 58%, #ffffff 100%);
}

.security-level-card.medium {
  border-color: #f7ddb1;
}

.security-level-card.low {
  border-color: #f3c7cb;
  background:
    radial-gradient(circle at 10% 50%, rgba(255, 91, 97, 0.08), transparent 20%),
    linear-gradient(135deg, #fff4f4 0%, #fffdfd 58%, #ffffff 100%);
}

.security-level-main {
  padding-right: 0;
}

.security-level-visual {
  display: none;
}

.security-level-topline {
  gap: 12px;
}

.security-level-info {
  align-items: center;
  gap: 14px;
}

.security-level-icon {
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--security-accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.security-level-text strong {
  margin: 0 0 5px;
  font-size: 30px;
}

.security-level-text p {
  max-width: none;
  font-size: 11px;
  line-height: 1.45;
}

.security-level-summary {
  margin-bottom: 8px;
}

.security-risk-pill {
  height: 24px;
  padding: 0 9px;
  font-size: 11px;
}

.security-risk-pill::before {
  width: 16px;
  height: 16px;
  font-size: 10px;
}

.security-link-hint {
  font-size: 11px;
}

.security-progress-wrap {
  margin-top: 10px;
}

.security-progress {
  height: 6px;
  background: #edf1f6;
}

.security-progress-bar {
  box-shadow: none;
}

.security-progress-labels {
  margin-top: 8px;
  font-size: 12px;
}

.security-meta {
  margin-top: 8px;
  font-size: 11px;
}

.security-grid {
  gap: 14px;
}

.security-card {
  padding: 16px 16px 14px;
  border-radius: 20px;
  box-shadow: 0 10px 24px rgba(31, 53, 94, 0.04);
}

.security-card.enhanced {
  min-height: 230px;
  gap: 8px;
}

.security-card-icon {
  width: 50px;
  height: 50px;
  border-radius: 16px;
}

.security-card b {
  font-size: 16px;
}

.security-card > span {
  min-height: 42px;
  font-size: 12px;
  line-height: 1.6;
}

.security-card-note {
  min-height: auto;
  margin: 2px 0 4px;
  padding: 0;
  border-radius: 0;
  background: transparent;
  font-size: 11px;
}

.security-card-note.ok,
.security-card-note.warn {
  background: transparent;
}

.security-card-note-dot {
  width: 6px;
  height: 6px;
}

.security-tips {
  display: block;
  margin-top: 14px;
  padding: 16px 18px 14px;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.96), transparent 30%),
    linear-gradient(180deg, #f8fbff 0%, #f3f7ff 100%);
  border: 1px solid #e3ebf8;
}

.security-tips-copy h4 {
  margin: 0 0 10px;
  font-size: 16px;
}

.security-bullet-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 10px;
  color: #5e6d88;
  font-size: 13px;
  line-height: 1.65;
}

.security-bullet-list li::marker {
  color: #4f86ff;
}

.security-risk-pill.safe::before {
  content: '\2713';
  background: #16bf78;
}

.token-ledger-panel {
  padding: 16px 16px 14px;
}

.token-ledger-panel > .panel-head {
  margin-bottom: 14px;
}

.token-stats {
  gap: 12px;
  margin-bottom: 12px;
}

.token-stat-card {
  min-height: 90px;
  padding: 12px 14px 10px;
  border-radius: 18px;
  align-items: center;
}

.token-stat-ico {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  font-size: 17px;
}

.token-stat-body > strong {
  font-size: 24px;
}

.token-stat-body small {
  margin-top: 2px;
}

.token-stat-side,
.token-stat-pill,
.token-stat-wave {
  display: none;
}

.token-table-card {
  border-radius: 20px;
}

.table-wrap {
  max-height: none;
  overflow-y: visible;
  padding: 0 16px;
}

.base-table th {
  padding: 13px 8px 10px;
  font-size: 11px;
}

.base-table td {
  padding: 11px 8px;
}

.remark-cell,
.time-cell,
.mono,
.pos,
.neg {
  font-size: 11px;
}

.token-table-foot {
  padding: 14px 18px;
}

.pagination {
  gap: 10px;
}

.form-panel {
  max-width: 880px;
}

.profile-form {
  display: grid;
  gap: 16px;
  max-width: 460px;
}

.profile-capability-unavailable {
  display: grid;
  gap: 12px;
  max-width: 620px;
  padding: 18px;
  border: 1px solid #f2d49b;
  border-radius: 14px;
  background: #fff9ed;
  color: #8b5a0c;
  line-height: 1.65;
}

.profile-capability-unavailable p {
  margin: 0;
}

.profile-form label {
  display: grid;
  gap: 8px;
  color: #34425d;
  font-size: 14px;
  font-weight: 700;
}

.profile-form label span { font-size: 13px; }

.profile-form input {
  width: 100%;
  box-sizing: border-box;
  height: 42px;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 10px;
  padding: 0 14px;
  outline: none;
  font-size: 14px;
  color: #44536f;
}

.profile-form input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 4px rgba(13, 107, 255, 0.08);
}

.code-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 130px;
  gap: 12px;
  align-items: end;
}

.code-label { margin-bottom: 0 !important; }

.submit-btn {
  height: 42px;
  font-size: 14px;
}

.token-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.token-stat-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  min-height: 116px;
  padding: 18px 18px 14px;
  overflow: hidden;
  flex: none !important;
  height: auto !important;
  border-radius: 20px;
  border: 1px solid rgba(231, 238, 248, 0.96);
  box-shadow: 0 12px 28px rgba(31, 53, 94, 0.045);
}

.token-stat-card::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.5;
}

.stat-red { background: linear-gradient(135deg, #fff5f5, #fff); }
.stat-red::before { background: radial-gradient(circle at 88% 16%, rgba(255, 91, 97, 0.1), transparent 60%); }
.stat-red .token-stat-ico { color: #fff; background: linear-gradient(145deg, #ff6b8a, #ff5b61); box-shadow: 0 8px 16px rgba(255, 91, 97, 0.22); }

.stat-orange { background: linear-gradient(135deg, #fff8e8, #fff); }
.stat-orange::before { background: radial-gradient(circle at 88% 16%, rgba(255, 159, 34, 0.12), transparent 60%); }
.stat-orange .token-stat-ico { color: #fff; background: linear-gradient(145deg, #ffb547, #ff9f22); box-shadow: 0 8px 16px rgba(255, 159, 34, 0.22); }

.stat-blue { background: linear-gradient(135deg, #eef5ff, #fff); }
.stat-blue::before { background: radial-gradient(circle at 88% 16%, rgba(13, 107, 255, 0.12), transparent 60%); }
.stat-blue .token-stat-ico { color: #fff; background: linear-gradient(145deg, #5b7cff, #0d6bff); box-shadow: 0 8px 16px rgba(13, 107, 255, 0.22); }

.token-stat-ico {
  width: 58px;
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  font-size: 18px;
  font-weight: 900;
  flex: 0 0 auto;
  position: relative;
  z-index: 1;
}

.token-stat-body {
  position: relative;
  z-index: 1;
  min-width: 0;
  flex: 1 1 auto;
}

.token-stat-body > span {
  color: #7b879d;
  font-size: 12px;
  font-weight: 700;
  display: block;
}

.token-stat-body > strong {
  display: block;
  margin-top: 4px;
  color: #17213d;
  font-size: 28px;
  line-height: 1.1;
  font-weight: 800;
  font-family: 'SF Mono', 'JetBrains Mono', 'Cascadia Code', monospace;
}

.stat-red strong { color: #dc2626 !important; }
.stat-orange strong { color: #b45309 !important; }
.stat-blue strong { color: #0d6bff !important; }

.token-stat-body small {
  display: block;
  margin-top: 4px;
  color: #98a4ba;
  font-size: 11px;
  font-weight: 600;
}

.token-stat-side {
  position: relative;
  z-index: 1;
  min-width: 126px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 22px;
}

.token-stat-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #18a36b;
  font-size: 12px;
  font-weight: 800;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
}

.token-stat-wave {
  width: 100px;
  height: 18px;
}

.token-stat-wave path {
  fill: none;
  stroke: rgba(255, 107, 138, 0.9);
  stroke-width: 3;
  stroke-linecap: round;
}

.stat-orange .token-stat-wave path {
  stroke: rgba(255, 159, 34, 0.92);
}

.stat-blue .token-stat-wave path {
  stroke: rgba(13, 107, 255, 0.88);
}

.token-table-card {
  display: flex;
  flex-direction: column;
  border-radius: 22px;
  border: 1px solid rgba(229, 236, 247, 0.96);
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.98), transparent 36%),
    linear-gradient(180deg, #ffffff 0%, #fcfdff 100%);
  box-shadow: 0 14px 30px rgba(31, 53, 94, 0.045);
  overflow: hidden;
}

.table-wrap {
  max-height: 650px;
  overflow-x: auto;
  overflow-y: auto;
  padding: 0 18px 0;
  scrollbar-gutter: stable;
}

.base-table {
  font-size: 13px;
  border-collapse: separate;
  border-spacing: 0;
}

.base-table th {
  font-weight: 800;
  padding: 18px 12px 13px;
  font-size: 12px;
  white-space: nowrap;
  color: #7f8ba1;
  border-bottom: 1px solid rgba(232, 238, 247, 0.9);
}

.base-table td {
  padding: 16px 12px;
  border-bottom: 1px solid rgba(240, 244, 251, 0.96);
  vertical-align: middle;
}

.token-table tbody tr:nth-child(even) td {
  background: rgba(247, 250, 255, 0.56);
}

.token-table tbody tr:hover td {
  background: rgba(239, 245, 255, 0.72);
}

.token-table thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(8px);
}

.time-cell { white-space: nowrap; color: #7b879d; font-size: 12px; }
.mono { font-family: 'SF Mono', 'JetBrains Mono', 'Cascadia Code', monospace; font-size: 12px; font-weight: 700; color: #475569; }

.pos { color: #059669; font-weight: 800; font-family: 'SF Mono', monospace; font-size: 13px; white-space: nowrap; }
.neg { color: #dc2626; font-weight: 800; font-family: 'SF Mono', monospace; font-size: 13px; white-space: nowrap; }

.remark-cell {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #5d6c86;
  font-size: 12px;
}

.token-table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 18px;
  border-top: 1px solid rgba(232, 238, 247, 0.9);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(251, 253, 255, 0.98) 100%);
}

.token-record-count {
  color: #667491;
  font-size: 13px;
  font-weight: 700;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  padding: 0;
  font-size: 12px;
  color: #7b879d;
}

.page-size {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #5d6c86;
  font-size: 12px;
  font-weight: 700;
}

.page-size select {
  height: 30px;
  border: 1px solid rgba(126, 143, 179, 0.22);
  border-radius: 7px;
  padding: 0 8px;
  background: #fff;
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  outline: none;
}

.page-btn {
  height: 36px;
  border: 1px solid rgba(126, 143, 179, 0.22);
  border-radius: 12px;
  padding: 0 12px;
  background: #fff;
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.page-btn.icon {
  width: 36px;
  padding: 0;
  justify-content: center;
}

.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-btn:not(:disabled):hover { border-color: var(--primary); color: var(--primary); background: #f5f8ff; }

.page-jump {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #5d6c86;
  font-size: 12px;
  font-weight: 700;
}

.page-jump.compact {
  gap: 8px;
}

.page-jump input {
  width: 52px;
  height: 36px;
  box-sizing: border-box;
  border: 1px solid rgba(126, 143, 179, 0.22);
  border-radius: 12px;
  padding: 0 8px;
  background: #fff;
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  text-align: center;
  outline: none;
  -moz-appearance: textfield;
}

.page-jump input::-webkit-outer-spin-button,
.page-jump input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.page-jump input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(13, 107, 255, 0.1); }

.total-count { color: #5d6c86; font-size: 12px; font-weight: 700; }

.page-number {
  min-width: 36px;
  height: 36px;
  border: 1px solid rgba(126, 143, 179, 0.18);
  border-radius: 12px;
  background: #fff;
  color: #586780;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.page-number.active {
  background: linear-gradient(180deg, #1976ff 0%, #0d6bff 100%);
  border-color: #0d6bff;
  color: #fff;
  box-shadow: 0 12px 20px rgba(13, 107, 255, 0.2);
}

.page-ellipsis {
  color: #94a3b8;
  font-weight: 800;
  padding: 0 2px;
}

@media (max-width: 1280px) {
  .welcome-content {
    max-width: calc(100% - 340px);
  }

  .benefits-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 1200px) {
  .profile-shell {
    grid-template-columns: 1fr;
  }

  .profile-side-card {
    position: static;
  }

  .profile-side-nav {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .profile-side-tab {
    flex: 1 1 calc(33.333% - 7px);
  }

  .two-col-grid,
  .overview-bottom-grid {
    grid-template-columns: 1fr;
  }

  .profile-stats,
  .security-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .benefits-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .security-level-topline {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 900px) {
  .welcome-content {
    max-width: none;
  }

  .welcome-visual {
    display: none;
  }

  .security-level-info {
    align-items: flex-start;
  }
}

@media (max-width: 768px) {
  .profile-stats,
  .quick-grid-2col,
  .token-stats,
  .account-info-grid,
  .security-grid,
  .benefits-grid {
    grid-template-columns: 1fr;
  }

  .profile-side-head {
    display: none;
  }

  .profile-side-card {
    padding: 10px;
  }

  .profile-side-tab {
    flex: 1 1 100%;
    width: 100%;
  }

  .welcome-hero {
    padding: 24px 20px;
  }

  .welcome-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 18px;
  }

  .welcome-text h2 {
    font-size: 34px;
  }

  .member-card-inner {
    flex-direction: column;
    align-items: flex-start;
  }

  .benefit-feature {
    flex-direction: row;
    justify-content: flex-start;
    text-align: left;
    padding: 12px 14px;
  }

  .member-actions,
  .member-actions .app-btn {
    width: 100%;
  }

  .token-amount strong {
    font-size: 40px;
  }

  .token-coin {
    position: relative;
    right: auto;
    top: auto;
    bottom: auto;
    transform: none;
    width: 168px;
    height: 140px;
    margin: 20px 0 0 auto;
  }

  .form-panel {
    max-width: none;
  }

  .profile-form {
    max-width: none;
  }

  .code-row {
    grid-template-columns: 1fr;
  }

  .pagination {
    justify-content: flex-start;
  }

  .security-level-info,
  .security-meta {
    flex-direction: column;
    align-items: flex-start;
  }

  .security-level-topline {
    flex-direction: column;
  }

  .token-table-foot {
    align-items: flex-start;
  }

  .table-wrap {
    max-height: none;
  }
}

@media (max-width: 560px) {
  .profile-shell {
    gap: 12px;
  }

  .profile-side-card {
    padding: 8px;
    border-radius: 18px;
  }

  .profile-side-nav {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .profile-side-tab {
    flex: none;
    flex-direction: column;
    justify-content: center;
    width: 100%;
    min-width: 0;
    min-height: 78px;
    padding: 10px 6px;
    gap: 6px;
    border-radius: 12px;
    text-align: center;
  }

  .profile-side-tab::before {
    top: auto;
    right: auto;
    bottom: 5px;
    left: 50%;
    width: 24px;
    height: 3px;
    transform: translateX(-50%);
  }

  .profile-side-tab-icon {
    width: 36px;
    height: 36px;
  }

  .profile-side-tab-label {
    font-size: 12px;
    white-space: nowrap;
  }

  .welcome-hero {
    min-height: 0;
    padding: 18px 16px 16px;
    border-radius: 20px;
  }

  .welcome-hero::before {
    display: none;
  }

  .welcome-hero::after {
    inset: 10px;
    border-radius: 16px;
  }

  .welcome-content {
    gap: 12px;
  }

  .welcome-avatar {
    width: 60px;
    height: 60px;
    border-radius: 18px;
  }

  .welcome-avatar svg {
    width: 54px;
    height: 54px;
  }

  .welcome-text {
    width: 100%;
    min-width: 0;
  }

  .welcome-text h2 {
    font-size: clamp(24px, 7.5vw, 30px);
    line-height: 1.18;
  }

  .welcome-greeting,
  .welcome-user-name {
    display: block;
  }

  .welcome-user-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .wave {
    display: none;
  }

  .welcome-text p {
    margin: 8px 0 12px;
    font-size: 13px;
    line-height: 1.6;
  }

  .welcome-tags {
    gap: 6px;
  }

  .welcome-tags .chip {
    max-width: 100%;
    padding: 6px 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .profile-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .stat-card {
    min-height: 104px;
    padding: 14px 12px;
    border-radius: 16px;
  }

  .stat-card .stat-icon {
    width: 40px;
    height: 40px;
    border-radius: 13px;
  }

  .stat-icon-img {
    width: 23px;
    height: 23px;
  }

  .stat-info span {
    font-size: 12px;
  }

  .stat-info strong {
    font-size: 23px;
  }

  .stat-card-foot {
    margin-top: 9px;
  }
}

@media (max-width: 380px) {
  .profile-side-tab {
    min-height: 72px;
    padding: 8px 4px;
  }

  .profile-side-tab-label {
    font-size: 11px;
  }

  .stat-wave {
    display: none;
  }
}
</style>
