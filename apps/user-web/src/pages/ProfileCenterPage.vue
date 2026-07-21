<template>
  <div class="profile-center">
    <div v-if="notice.text" :class="['global-notice', notice.type]">
      {{ notice.text }}
    </div>
    <div v-if="overviewLoadError" class="global-notice error" role="alert">
      {{ overviewLoadError }}
      <button type="button" class="app-btn" @click="loadOverview">重新加载</button>
    </div>

    <div class="profile-page-header">
      <div class="pph-breadcrumb">个人中心 / <span class="pph-breadcrumb-current">{{ currentTabLabel }}</span></div>
    </div>

    <div class="profile-tabs-bar">
      <button
        v-for="item in tabs"
        :key="item.key"
        type="button"
        :class="['profile-tab', { active: menuActiveKey === item.key }]"
        @click="activeTab = item.key"
      >
        {{ item.label }}
      </button>
    </div>

    <div class="profile-main">
      <div v-if="activeTab === 'overview'" class="profile-main-section profile-overview-v2">
        <section class="pc-banner">
          <div class="pc-banner-left">
            <div class="pc-avatar-wrap">
              <div class="pc-avatar-ring"></div>
              <div class="pc-avatar">
                <svg viewBox="0 0 80 80" width="80" height="80">
                  <defs>
                    <clipPath id="avClip"><circle cx="40" cy="40" r="34"/></clipPath>
                    <linearGradient id="avBg" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#fce7c4"/>
                      <stop offset="100%" stop-color="#f5d5a8"/>
                    </linearGradient>
                  </defs>
                  <circle cx="40" cy="40" r="38" fill="#fff"/>
                  <circle cx="40" cy="40" r="36" fill="url(#avBg)" clip-path="url(#avClip)"/>
                  <ellipse cx="40" cy="34" rx="14" ry="16" fill="#f5d5b0"/>
                  <path d="M25 28c0-10 7-18 15-18s15 8 15 18c0 3-1 5-2 6-1-4-4-8-13-8s-12 4-13 8c-1-1-2-3-2-6z" fill="#3a2a1c"/>
                  <path d="M26 30c1-5 6-10 14-10s13 5 14 10c-2-3-7-5-14-5s-12 2-14 5z" fill="#2a1e14"/>
                  <ellipse cx="34" cy="36" rx="2" ry="2.5" fill="#2a1e14"/>
                  <ellipse cx="46" cy="36" rx="2" ry="2.5" fill="#2a1e14"/>
                  <circle cx="34" cy="35.5" r="0.8" fill="#fff"/>
                  <circle cx="46" cy="35.5" r="0.8" fill="#fff"/>
                  <path d="M32 42c3 2 13 2 16 0" stroke="#c97b6a" stroke-width="1.2" stroke-linecap="round" fill="none"/>
                  <path d="M36 38c-1 1-1 2 0 2M44 38c1 1 1 2 0 2" stroke="#d4927f" stroke-width="1" stroke-linecap="round" fill="none"/>
                  <path d="M24 52c0-12 8-20 16-20s16 8 16 20c0 4-32 4-32 0z" fill="#e88a5a"/>
                  <path d="M30 50c2-4 5-6 10-6s8 2 10 6" stroke="#d0734a" stroke-width="1" fill="none"/>
                </svg>
              </div>
            </div>
            <div class="pc-banner-info">
              <div class="pc-username-row">
                <span class="pc-username">{{ overview.nickname || overview.username || '—' }}</span>
                <span v-if="planBadge !== 'FREE' && planBadge !== 'UNKNOWN'" class="pc-svip-badge">
                  <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
                    <path d="M8 1.5l2.5 3-2.5 8-2.5-8z" fill="#d97706"/>
                    <path d="M8 1.5l2.5 3h-5z" fill="#fbbf24"/>
                    <circle cx="8" cy="5" r="0.8" fill="#fff" opacity="0.6"/>
                  </svg>
                  {{ planBadgeText }}
                </span>
                <span class="pc-connect-status">
                  <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
                    <circle cx="8" cy="8" r="6" fill="#22c55e" opacity="0.15"/>
                    <path d="M5 8l2.2 2.2L11 6" stroke="#22c55e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  已连接
                </span>
              </div>
              <div class="pc-user-tags">
                <span class="pc-tag pc-tag-blue">
                  <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
                    <circle cx="8" cy="5.5" r="2.5" stroke="currentColor" stroke-width="1.3"/>
                    <path d="M3 13c0-2.8 2.2-5 5-5s5 2.2 5 5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                  </svg>
                  用户类型：个人用户
                </span>
                <span :class="['pc-tag', overview.emailVerified ? 'pc-tag-blue' : 'pc-tag-gray']">
                  <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
                    <rect x="2.5" y="4" width="11" height="8" rx="2" stroke="currentColor" stroke-width="1.3"/>
                    <path d="M3 5.5l5 3.5 5-3.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  {{ overview.emailVerified ? '邮箱已验证' : (maskedEmail ? '邮箱未验证' : '邮箱未绑定') }}
                </span>
                <span :class="['pc-tag', overview.phoneVerified ? 'pc-tag-green' : 'pc-tag-gray']">
                  <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
                    <rect x="5" y="2" width="6" height="11" rx="1.5" stroke="currentColor" stroke-width="1.3"/>
                    <line x1="7" y1="11" x2="9" y2="11" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                  </svg>
                  {{ overview.phoneVerified ? '手机号已绑定' : (maskedPhone ? '手机号未验证' : '手机号未绑定') }}
                </span>
              </div>
              <button type="button" class="pc-btn pc-btn-primary pc-manage-btn" @click="activeTab = 'security'">
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
                  <circle cx="8" cy="5" r="3" stroke="currentColor" stroke-width="1.3"/>
                  <path d="M2.5 14c0-3 2.5-5 5.5-5s5.5 2 5.5 5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                </svg>
                管理资料
              </button>
            </div>
          </div>
          <div class="pc-banner-right">
            <div class="pc-banner-illustration" aria-hidden="true">
              <svg viewBox="0 0 220 160" width="220" height="160">
                <defs>
                  <linearGradient id="shieldG2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95"/>
                    <stop offset="100%" stop-color="#dbeafe" stop-opacity="0.8"/>
                  </linearGradient>
                </defs>
                <ellipse cx="110" cy="148" rx="80" ry="6" fill="#1e3a8a" opacity="0.08"/>
                <path d="M110 18 L168 42 V86 C168 124 144 150 110 162 C76 150 52 124 52 86 V42 Z" fill="#ffffff" opacity="0.35"/>
                <path d="M110 28 L158 48 V84 C158 116 138 140 110 152 C82 140 62 116 62 84 V48 Z" fill="url(#shieldG2)" stroke="#ffffff" stroke-width="1.5"/>
                <circle cx="110" cy="86" r="26" fill="#ffffff" opacity="0.95"/>
                <path d="M96 86 L106 96 L124 76" stroke="#2563eb" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                <circle cx="58" cy="48" r="3" fill="#ffffff" opacity="0.6"/>
                <circle cx="170" cy="60" r="2.5" fill="#ffffff" opacity="0.5"/>
                <circle cx="160" cy="120" r="2" fill="#ffffff" opacity="0.4"/>
              </svg>
            </div>
          </div>
        </section>

          <div class="pc-stats-row">
            <article class="pc-stat-card">
              <div class="pc-stat-head">
                <div class="pc-stat-ico pc-stat-ico-blue">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
                    <ellipse cx="12" cy="5" rx="7" ry="2.5" fill="currentColor" fill-opacity="0.25" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M5 5v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V5" stroke="currentColor" stroke-width="1.5"/>
                    <ellipse cx="12" cy="10" rx="7" ry="2.5" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M5 10v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-5" stroke="currentColor" stroke-width="1.5"/>
                    <ellipse cx="12" cy="15" rx="7" ry="2.5" fill="currentColor" fill-opacity="0.1" stroke="currentColor" stroke-width="1.5"/>
                  </svg>
                </div>
                <span class="pc-stat-label">Token余额</span>
              </div>
              <div class="pc-stat-value">
                <strong>{{ formatNumber(overview.tokenBalance ?? 0) }}</strong>
                <em>Token</em>
              </div>
              <div class="pc-stat-sub">
                <span class="pc-stat-yuan">≈ ¥{{ formatNumber((overview.tokenBalance ?? 0) / 100) }}</span>
              </div>
              <button type="button" class="pc-btn pc-btn-primary pc-stat-btn" @click="paymentVisible = true">充值</button>
            </article>

            <article class="pc-stat-card">
              <div class="pc-stat-head">
                <div class="pc-stat-ico pc-stat-ico-green">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
                    <path d="M3 17l6-6 4 4 8-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M17 4h4v4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
                <span class="pc-stat-label">今日消耗</span>
              </div>
              <div class="pc-stat-value">
                <strong>{{ formatNumber(tokenStats.todayConsume ?? 0) }}</strong>
                <em>Token</em>
              </div>
              <div class="pc-stat-sub">
                <span class="pc-stat-yuan">今日 0 点至今累计</span>
              </div>
            </article>

            <article class="pc-stat-card">
              <div class="pc-stat-head">
                <div class="pc-stat-ico pc-stat-ico-red">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
                    <path d="M3 17l6-6 4 4 8-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M17 4h4v4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
                <span class="pc-stat-label">本月消耗</span>
              </div>
              <div class="pc-stat-value">
                <strong>{{ formatNumber(tokenStats.monthConsume ?? 0) }}</strong>
                <em>Token</em>
              </div>
              <div class="pc-stat-sub">
                <span class="pc-stat-yuan">本月 1 日至今累计</span>
              </div>
            </article>

            <article class="pc-stat-card">
              <div class="pc-stat-head">
                <div class="pc-stat-ico pc-stat-ico-gold">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
                    <path d="M3 7l4 4 5-6 5 6 4-4-2 11H5L3 7z" fill="currentColor" fill-opacity="0.2" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
                    <circle cx="7" cy="11" r="1.2" fill="currentColor"/>
                    <circle cx="12" cy="7" r="1.2" fill="currentColor"/>
                    <circle cx="17" cy="11" r="1.2" fill="currentColor"/>
                    <rect x="4" y="16" width="16" height="1.5" rx="0.5" fill="currentColor" opacity="0.3"/>
                  </svg>
                </div>
                <span class="pc-stat-label">会员等级</span>
              </div>
              <div class="pc-stat-value pc-stat-value-svip">
                <strong>{{ planBadgeText }}</strong>
              </div>
              <div class="pc-stat-sub">
                <span class="pc-stat-yuan">{{ planPeriodText }}</span>
              </div>
              <button type="button" class="pc-btn pc-btn-outline pc-stat-btn" @click="handleQuickAction('vip')">查看权益</button>
            </article>
          </div>

          <div class="pc-three-col">
            <section class="pc-card pc-userinfo-card">
              <h3 class="pc-card-title">用户信息</h3>
              <div class="pc-userinfo-list">
                <div class="pc-info-row">
                  <span class="pc-info-label">用户名</span>
                  <span class="pc-info-value">{{ overview.username || '—' }}</span>
                </div>
                <div class="pc-info-row">
                  <span class="pc-info-label">会员等级</span>
                  <span class="pc-info-value pc-info-value-gold">{{ planBadgeText }}</span>
                </div>
                <div class="pc-info-row">
                  <span class="pc-info-label">用户类型</span>
                  <span class="pc-info-value">个人用户</span>
                </div>
                <div class="pc-info-row">
                  <span class="pc-info-label">邮箱</span>
                  <span class="pc-info-value">{{ maskedEmail || '未绑定邮箱' }}</span>
                </div>
                <div class="pc-info-row">
                  <span class="pc-info-label">邮箱验证</span>
                  <span :class="['pc-info-value', emailVerifiedTone]">{{ emailVerifiedText }}</span>
                </div>
                <div class="pc-info-row">
                  <span class="pc-info-label">手机号</span>
                  <span class="pc-info-value">{{ maskedPhone || '未绑定手机号' }}</span>
                </div>
                <div class="pc-info-row">
                  <span class="pc-info-label">手机号绑定</span>
                  <span :class="['pc-info-value', phoneVerifiedTone]">{{ phoneVerifiedText }}</span>
                </div>
                <div class="pc-info-row">
                  <span class="pc-info-label">注册时间</span>
                  <span class="pc-info-value">{{ displayDateOnly(overview.createdTime) }}</span>
                </div>
                <div class="pc-info-row">
                  <span class="pc-info-label">最近登录</span>
                  <span class="pc-info-value">{{ displayDateOnly(overview.lastLoginTime) }}</span>
                </div>
              </div>
            </section>

            <section class="pc-card pc-recharge-card">
              <h3 class="pc-card-title">充值与消费</h3>
              <p class="pc-recharge-desc">灵活充值，透明消费</p>
              <ul class="pc-recharge-features">
                <li>
                  <span class="pc-recharge-feature-label">账户余额</span>
                  <strong>¥{{ formatNumber((overview.tokenBalance ?? 0) / 100) }}</strong>
                </li>
                <li>
                  <span class="pc-recharge-feature-label">本月消耗</span>
                  <strong>{{ formatNumber(tokenStats.monthConsume ?? 0) }} Token</strong>
                </li>
                <li>
                  <span class="pc-recharge-feature-label">套餐状态</span>
                  <strong class="pc-recharge-status-active">{{ planStatusText }}</strong>
                </li>
              </ul>
              <div class="pc-recharge-btns">
                <button type="button" class="pc-btn pc-btn-primary pc-recharge-main" @click="paymentVisible = true">立即充值</button>
                <button type="button" class="pc-btn pc-btn-light pc-recharge-sub" @click="activeTab = 'token'">消费明细</button>
              </div>
            </section>
          </div>

          <div class="pc-analytics-row">
            <section class="pc-card pc-chart-card pc-pie-card">
              <h3 class="pc-card-title">Token使用概览<span class="pc-card-sub">（近7天）</span></h3>
              <div class="pc-pie-wrap">
                <div ref="pieChartRef" class="pc-chart-dom"></div>
              </div>
            </section>

            <section class="pc-card pc-chart-card pc-line-card">
              <h3 class="pc-card-title">Token消耗趋势<span class="pc-card-sub">（近7天）</span></h3>
              <div ref="lineChartRef" class="pc-chart-dom"></div>
            </section>

            <section class="pc-card pc-expire-card">
              <h3 class="pc-card-title">到期提醒</h3>
              <div class="pc-expire-ico" aria-hidden="true">
                <svg viewBox="0 0 56 56" width="48" height="48">
                  <defs>
                    <linearGradient id="calTopG2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#60a5fa"/>
                      <stop offset="100%" stop-color="#3b82f6"/>
                    </linearGradient>
                  </defs>
                  <rect x="6" y="14" width="44" height="36" rx="6" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.5"/>
                  <rect x="6" y="14" width="44" height="12" rx="6" fill="url(#calTopG2)"/>
                  <rect x="14" y="6" width="4" height="10" rx="2" fill="#3b82f6"/>
                  <rect x="38" y="6" width="4" height="10" rx="2" fill="#3b82f6"/>
                  <text x="28" y="42" text-anchor="middle" fill="#2563eb" font-size="18" font-weight="800" font-family="-apple-system, 'SF Pro Display', sans-serif">{{ planExpireDayText }}</text>
                </svg>
              </div>
              <div class="pc-expire-days">{{ planExpireDisplay }}<span class="pc-expire-unit">{{ planExpireUnitText }}</span></div>
              <div class="pc-expire-date">{{ planExpireDateText }}</div>
              <button type="button" class="pc-btn pc-btn-primary" @click="handleQuickAction('vip')">续费会员</button>
            </section>
          </div>

          <section class="pc-card pc-compare-card">
            <div class="pc-compare-head">
              <h3 class="pc-card-title">会员等级功能对比</h3>
              <button
                type="button"
                class="pc-compare-refresh"
                :disabled="memberComparisonLoading"
                @click="loadMemberComparison"
              >{{ memberComparisonLoading ? '加载中…' : '刷新' }}</button>
            </div>
            <p class="pc-compare-desc">数据来源：后台「系统运维 → 功能管理」配置。✓ 表示该等级可用，— 表示该等级不可用。</p>
            <div class="pc-compare-table-wrap">
              <EmptyState
                v-if="memberComparisonError"
                variant="error"
                title="功能对比数据加载失败"
                :description="memberComparisonError"
              >
                <template #actions>
                  <button type="button" class="app-btn" @click="loadMemberComparison">重新加载</button>
                </template>
              </EmptyState>
              <EmptyState
                v-else-if="!memberComparisonLoading && memberCompareData.length === 0"
                variant="default"
                title="暂无功能对比数据"
                description="后台尚未配置功能开关，请前往管理端「系统运维 → 功能管理」初始化默认配置后再查看。"
              />
              <table v-else class="pc-compare-table">
                <thead>
                  <tr>
                    <th class="pc-th-feature">功能 / 权益</th>
                    <th class="pc-th-normal">普通会员</th>
                    <th class="pc-th-vip">VIP会员</th>
                    <th class="pc-th-svip">
                      <div class="pc-svip-th-inner">
                        <span class="pc-svip-crown" aria-hidden="true">
                          <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
                            <path d="M2 13l2-7 4 3.5 4-3.5 2 7H2z" fill="#d97706"/>
                            <path d="M4 6l4 3.5L12 6l-1 5H5L4 6z" fill="#fbbf24"/>
                          </svg>
                        </span>
                        SVIP会员
                        <span class="pc-svip-badge">你的等级</span>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="(group, gIdx) in memberCompareData" :key="'g'+gIdx">
                    <tr class="pc-group-row">
                      <td colspan="4">
                        <span class="pc-feature-ico" aria-hidden="true">{{ group.icon }}</span>
                        <span class="pc-group-label">{{ group.category }}</span>
                        <span class="pc-group-count">{{ group.items.length }} 项</span>
                      </td>
                    </tr>
                    <tr v-for="(item, iIdx) in group.items" :key="'i'+gIdx+'-'+iIdx" :class="['pc-feature-row', { 'pc-feature-row-alt': iIdx % 2 === 1 }]">
                      <td class="pc-td-name">{{ item.name }}</td>
                      <td class="pc-td-normal" :class="{ 'pc-mark-on': item.normal === '✓', 'pc-mark-off': item.normal !== '✓' }">
                        <span v-if="item.normal === '✓'" class="pc-check-ico">
                          <svg viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="7" fill="#dcfce7" stroke="#16a34a" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#16a34a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                        </span>
                        <span v-else class="pc-dash">—</span>
                      </td>
                      <td class="pc-td-vip" :class="{ 'pc-mark-on': item.vip === '✓', 'pc-mark-off': item.vip !== '✓' }">
                        <span v-if="item.vip === '✓'" class="pc-check-ico">
                          <svg viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="7" fill="#dcfce7" stroke="#16a34a" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#16a34a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                        </span>
                        <span v-else class="pc-dash">—</span>
                      </td>
                      <td class="pc-td-svip" :class="{ 'pc-mark-on': item.svip === '✓', 'pc-mark-off': item.svip !== '✓' }">
                        <span v-if="item.svip === '✓'" class="pc-check-ico pc-check-gold">
                          <svg viewBox="0 0 16 16" width="18" height="18"><circle cx="8" cy="8" r="7" fill="#fef3c7" stroke="#d97706" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#d97706" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                        </span>
                        <span v-else class="pc-dash">—</span>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
              <div class="pc-compare-note">注：以上对比仅供参考，具体功能以实际产品为准。我们保留对会员权益的最终解释权。</div>
            </div>
          </section>
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
              <svg class="security-level-visual-illustration" viewBox="0 0 240 200" fill="none">
                <ellipse cx="120" cy="180" rx="80" ry="6" fill="rgba(var(--security-accent-rgb), 0.08)"/>
                <path class="security-orbit-line" d="M40 165c25-22 60-35 80-35s55 13 80 35" />
                <circle class="security-orbit-dot dot-left" cx="42" cy="165" r="4" />
                <circle class="security-orbit-dot dot-right" cx="200" cy="165" r="4" />
                <g transform="translate(60 30)">
                  <path class="security-shield-back" d="M60 6 110 26v44c0 33-20 62-50 81C30 132 10 103 10 70V26L60 6Z" />
                  <path class="security-shield-front" d="M60 12 102 30v38c0 29-15 54-42 70C33 122 18 97 18 68V30L60 12Z" />
                  <path class="security-shield-check" d="m40 70 14 14 28-29" />
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

        <div v-else-if="activeTab === 'token'" class="token-dashboard">
          <section class="td-banner-card">
            <div class="td-banner-left">
              <div class="td-banner-avatar">
                <svg viewBox="0 0 64 64" width="56" height="56">
                  <defs>
                    <linearGradient id="tdAvBg" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#60a5fa"/>
                      <stop offset="100%" stop-color="#2563eb"/>
                    </linearGradient>
                  </defs>
                  <circle cx="32" cy="32" r="32" fill="url(#tdAvBg)"/>
                  <text x="32" y="40" text-anchor="middle" fill="#fff" font-size="26" font-weight="700" font-family="Arial">{{ (overview.nickname || overview.username || 'S').charAt(0).toUpperCase() }}</text>
                </svg>
              </div>
              <div class="td-banner-userinfo">
                <div class="td-banner-username-row">
                  <span class="td-banner-username">{{ overview.nickname || overview.username || '—' }}</span>
                  <span v-if="planBadge !== 'FREE' && planBadge !== 'UNKNOWN'" class="td-badge td-badge-svip">
                    <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
                      <path d="M8 1.5l1.6 3.8 4.2.4-3.2 2.8 1 4.1L8 10.5 4.4 12.6l1-4.1-3.2-2.8 4.2-.4L8 1.5z" fill="#f59e0b"/>
                    </svg>
                    {{ planBadgeText }}
                  </span>
                  <span class="td-badge td-badge-connected">
                    <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
                      <circle cx="8" cy="8" r="6" fill="#22c55e" opacity="0.15"/>
                      <path d="M5 8l2.2 2.2L11 6" stroke="#22c55e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    已连接
                  </span>
                </div>
                <p class="td-banner-desc">合理规划 Token 使用，提升自动化效率，节省运营成本。</p>
              </div>
            </div>
            <div class="td-banner-right" aria-hidden="true">
              <svg class="td-banner-art" viewBox="0 0 220 140" width="220" height="140">
                <defs>
                  <linearGradient id="tdCoinGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#60a5fa"/>
                    <stop offset="100%" stop-color="#2563eb"/>
                  </linearGradient>
                </defs>
                <ellipse cx="110" cy="128" rx="86" ry="6" fill="#1e3a8a" opacity="0.08"/>
                <path d="M40 118 L180 118 L172 96 L48 96 Z" fill="#dbeafe" opacity="0.7"/>
                <g transform="translate(110 60)">
                  <circle r="34" fill="url(#tdCoinGrad)"/>
                  <circle r="34" fill="none" stroke="#fff" stroke-width="1.5" opacity="0.4"/>
                  <text x="0" y="9" text-anchor="middle" fill="#fff" font-size="28" font-weight="700" font-family="Arial">T</text>
                </g>
                <path d="M28 110 L52 86 L78 96 L120 60 L168 78" stroke="#3b82f6" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="0.55"/>
                <circle cx="52" cy="86" r="3" fill="#3b82f6"/>
                <circle cx="78" cy="96" r="3" fill="#3b82f6"/>
                <circle cx="120" cy="60" r="3" fill="#3b82f6"/>
                <circle cx="168" cy="78" r="3" fill="#3b82f6"/>
              </svg>
            </div>
          </section>

          <div class="td-stats-grid">
            <div class="td-stat-card">
              <div class="td-stat-head">
                <span class="td-stat-ico td-ico-balance">
                  <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
                    <path d="M10 2v2M10 16v2M4 10H2M18 10h-2M5 5l1.5 1.5M13.5 13.5L15 15M5 15l1.5-1.5M13.5 6.5L15 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <circle cx="10" cy="10" r="4" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M10 7v6M8.5 9h2.5a1.5 1.5 0 010 3h-1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                </span>
                <span class="td-stat-label">当前Token余额</span>
              </div>
              <div class="td-stat-value-row">
                <strong class="td-stat-num">{{ formatNumber(tokenStats.tokenBalance ?? 0) }}</strong>
                <span class="td-stat-unit">Token</span>
              </div>
              <div class="td-stat-yuan">≈ ¥{{ tokenYuanValue }}</div>
              <button type="button" class="td-recharge-btn" @click="paymentVisible = true">充值</button>
            </div>
            <div class="td-stat-card">
              <div class="td-stat-head">
                <span class="td-stat-ico td-ico-today">
                  <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
                    <path d="M4 14l3-3 3 2 5-6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M12 7h3v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
                <span class="td-stat-label">今日消耗</span>
              </div>
              <div class="td-stat-value-row">
                <strong class="td-stat-num">{{ formatNumber(tokenStats.todayConsume ?? 0) }}</strong>
                <span class="td-stat-unit">Token</span>
              </div>
              <div class="td-stat-compare td-compare-down">
                <svg viewBox="0 0 12 12" width="12" height="12" fill="none"><path d="M6 3v6M3 6l3 3 3-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                今日数据实时统计
              </div>
            </div>
            <div class="td-stat-card">
              <div class="td-stat-head">
                <span class="td-stat-ico td-ico-month">
                  <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
                    <path d="M3 17l4-5 3 2 6-8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M13 4h3v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
                <span class="td-stat-label">本月消耗</span>
              </div>
              <div class="td-stat-value-row">
                <strong class="td-stat-num">{{ formatNumber(tokenStats.monthConsume ?? 0) }}</strong>
                <span class="td-stat-unit">Token</span>
              </div>
              <div class="td-stat-compare td-compare-up">
                <svg viewBox="0 0 12 12" width="12" height="12" fill="none"><path d="M6 9V3M3 6l3-3 3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                本月 1 日至今累计
              </div>
            </div>
            <div class="td-stat-card">
              <div class="td-stat-head">
                <span class="td-stat-ico td-ico-budget">
                  <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
                    <path d="M10 2l2.2 5.5L18 8.3l-4.2 3.8 1.2 5.7L10 14.8 5 17.8l1.2-5.7L2 8.3l5.8-.8L10 2z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
                  </svg>
                </span>
                <span class="td-stat-label">本月预算使用率</span>
              </div>
              <div class="td-stat-value-row">
                <strong class="td-stat-num td-num-big">{{ budgetPercent }}</strong>
                <span class="td-stat-unit">%</span>
              </div>
              <div class="td-progress-bar">
                <div class="td-progress-fill" :style="{ width: budgetPercent + '%' }"></div>
              </div>
              <div class="td-budget-text">预算使用 <strong>{{ formatNumber(tokenStats.monthConsume ?? 0) }}</strong> / 10,000 Token</div>
            </div>
          </div>

          <div class="td-charts-row">
            <div class="td-card td-trend-card">
              <div class="td-card-head">
                <div class="td-card-title-wrap">
                  <h3 class="td-card-title">Token消耗趋势</h3>
                  <span class="td-card-sub">（近30天）</span>
                  <span class="td-info-ico" title="消耗趋势说明">
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
                      <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.3"/>
                      <path d="M8 7v4M8 5v.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                    </svg>
                  </span>
                </div>
                <div class="td-card-actions">
                  <select class="td-select">
                    <option>近30天</option>
                    <option>近7天</option>
                    <option>近90天</option>
                  </select>
                  <div class="td-seg-btns">
                    <button type="button" class="td-seg-btn active">按天</button>
                    <button type="button" class="td-seg-btn">按周</button>
                  </div>
                </div>
              </div>
              <div ref="trendChartRef" class="td-chart-area"></div>
              <div class="td-trend-summary">
                <div class="td-summary-item">
                  <span class="td-summary-label">日均消耗</span>
                  <strong class="td-summary-val">{{ formatNumber(avgDaily) }}</strong>
                  <span class="td-summary-unit">Token</span>
                </div>
                <div class="td-summary-divider"></div>
                <div class="td-summary-item">
                  <span class="td-summary-label">最高单日</span>
                  <strong class="td-summary-val">{{ formatNumber(peakDay.val) }}</strong>
                  <span class="td-summary-unit">Token</span>
                  <span class="td-summary-date">{{ dateLabel(peakDay.idx) }}</span>
                </div>
                <div class="td-summary-divider"></div>
                <div class="td-summary-item">
                  <span class="td-summary-label">最低单日</span>
                  <strong class="td-summary-val">{{ formatNumber(lowDay.val) }}</strong>
                  <span class="td-summary-unit">Token</span>
                  <span class="td-summary-date">{{ dateLabel(lowDay.idx) }}</span>
                </div>
              </div>
            </div>

            <div class="td-card td-pie-card">
              <div class="td-card-head">
                <h3 class="td-card-title">Token使用构成</h3>
                <span class="td-card-sub">（本月）</span>
              </div>
              <div class="td-pie-wrap">
                <div ref="tokenPieChartRef" class="td-pie-chart"></div>
                <div class="td-pie-center">
                  <strong>{{ formatNumber(tokenStats.monthConsume ?? 0) }}</strong>
                  <span>总消耗 Token</span>
                </div>
              </div>
              <div class="td-pie-legend">
                <div v-for="item in pieLegendData" :key="item.name" class="td-legend-item">
                  <span class="td-legend-dot" :style="{ background: item.color }"></span>
                  <span class="td-legend-name">{{ item.name }}</span>
                  <span class="td-legend-val">{{ formatNumber(item.value) }} Token</span>
                  <span class="td-legend-pct">{{ item.pct }}%</span>
                </div>
              </div>
              <button type="button" class="td-link-btn">查看详情 <svg viewBox="0 0 12 12" width="12" height="12" fill="none"><path d="M4.5 3l3 3-3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
            </div>
          </div>

          <div class="td-card td-package-card">
            <div class="td-package-left">
              <div class="td-package-illu" aria-hidden="true">
                <svg viewBox="0 0 160 110" width="160" height="110">
                  <defs>
                    <linearGradient id="tdPkgCoin" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#60a5fa"/>
                      <stop offset="100%" stop-color="#2563eb"/>
                    </linearGradient>
                  </defs>
                  <ellipse cx="80" cy="100" rx="60" ry="6" fill="#1e3a8a" opacity="0.08"/>
                  <g transform="translate(20 30)">
                    <rect x="0" y="10" width="56" height="48" rx="6" fill="url(#tdPkgCoin)"/>
                    <ellipse cx="28" cy="10" rx="28" ry="8" fill="#3b82f6"/>
                    <ellipse cx="28" cy="10" rx="22" ry="6" fill="#60a5fa"/>
                    <text x="28" y="42" text-anchor="middle" fill="#fff" font-size="18" font-weight="700" font-family="Arial">T</text>
                  </g>
                  <g transform="translate(85 18)">
                    <rect x="0" y="0" width="58" height="74" rx="8" fill="#fff" stroke="#dbeafe" stroke-width="1.5"/>
                    <rect x="8" y="10" width="42" height="3" rx="1.5" fill="#e0edff"/>
                    <rect x="8" y="18" width="28" height="3" rx="1.5" fill="#f0f7ff"/>
                    <path d="M10 60 L22 50 L32 56 L46 38" stroke="#3b82f6" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="22" cy="50" r="2" fill="#3b82f6"/>
                    <circle cx="32" cy="56" r="2" fill="#3b82f6"/>
                    <circle cx="46" cy="38" r="2" fill="#3b82f6"/>
                  </g>
                </svg>
              </div>
              <div class="td-package-info">
                <h3 class="td-package-title">多种套餐，按需选择</h3>
                <p class="td-package-desc">高性价比 Token 包，助力高效运营</p>
                <button type="button" class="td-package-cta" @click="paymentVisible = true">立即充值</button>
              </div>
            </div>
            <div class="td-package-right">
              <div v-for="pkg in packageList" :key="pkg.id" :class="['td-pkg-item', { recommend: pkg.recommend }]">
                <span v-if="pkg.recommend" class="td-pkg-tag">推荐</span>
                <div class="td-pkg-name">{{ pkg.name }}</div>
                <div class="td-pkg-amount">{{ formatNumber(pkg.amount) }} <span>Token</span></div>
                <div class="td-pkg-price">
                  <span class="td-pkg-symbol">¥</span>
                  <span class="td-pkg-price-num">{{ pkg.price }}</span>
                </div>
                <div class="td-pkg-unit-price">约 ¥{{ pkg.unitPrice }} / Token</div>
                <button type="button" :class="['td-pkg-buy', { primary: pkg.recommend }]" @click="paymentVisible = true">购买</button>
              </div>
              <div v-if="!packageList.length" class="td-pkg-empty">暂无可选套餐，请前往充值弹窗查看或联系管理员配置</div>
            </div>
            <p class="td-package-note">* 购买后 Token 将立刻到账，可在当前账户使用，有效期 365 天。</p>
          </div>

          <div class="td-bottom-row">
            <div class="td-card td-table-card">
              <div class="td-card-head">
                <div class="td-card-title-wrap">
                  <h3 class="td-card-title">消耗明细记录</h3>
                  <span class="td-info-ico">
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
                      <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.3"/>
                      <path d="M8 7v4M8 5v.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                    </svg>
                  </span>
                </div>
              </div>
              <div class="td-table-wrap">
                <table class="td-table">
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>类型</th>
                      <th>模块</th>
                      <th>消耗Token</th>
                      <th>状态</th>
                      <th>备注</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in displayTableRows" :key="row.id">
                      <td class="td-date">{{ row.createdTime ? formatTokenTime(row.createdTime) : '-' }}</td>
                      <td><span class="td-type-tag" :class="changeTypeClass(row.changeType)">{{ changeTypeLabel(row.changeType) }}</span></td>
                      <td>{{ refTypeLabel(row.refType) }}</td>
                      <td class="td-amount-cell">{{ Math.abs(Number(row.changeAmount) || 0) }}</td>
                      <td><span class="td-status-tag success">成功</span></td>
                      <td class="td-remark-cell">{{ row.remark || '-' }}</td>
                    </tr>
                    <tr v-if="!displayTableRows.length">
                      <td colspan="6" class="td-empty-cell">暂无消耗记录</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="td-table-pager">
                <div class="td-pager-left">
                  <button class="td-pager-btn" :disabled="(tokenLedger.current || 1) <= 1" @click="loadTokenLedger((tokenLedger.current || 1) - 1)">
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="none"><path d="M10 12L6 8l4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  </button>
                  <button v-for="p in pageNumbers" :key="'p-' + p" type="button" :class="['td-pager-num', { active: (tokenLedger.current || 1) === p }]" @click="loadTokenLedger(p)">{{ p }}</button>
                  <button v-if="totalPages > 5 && (tokenLedger.current || 1) < totalPages - 2" class="td-pager-ellipsis" disabled>...</button>
                  <button v-if="totalPages > 5" type="button" :class="['td-pager-num', { active: (tokenLedger.current || 1) === totalPages }]" @click="loadTokenLedger(totalPages)">{{ totalPages }}</button>
                  <button class="td-pager-btn" :disabled="(tokenLedger.current || 1) >= totalPages" @click="loadTokenLedger((tokenLedger.current || 1) + 1)">
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="none"><path d="M6 12l4-4-4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  </button>
                </div>
                <div class="td-pager-right">
                  <span class="td-pager-total">共 <strong>{{ tokenLedger.total || 0 }}</strong> 条</span>
                  <select class="td-pager-size" v-model.number="tokenLedger.size" @change="loadTokenLedger(1)">
                    <option :value="8">8条/页</option>
                    <option :value="20">20条/页</option>
                    <option :value="50">50条/页</option>
                  </select>
                </div>
              </div>
            </div>

            <div class="td-right-col">
              <div class="td-card td-rank-card">
                <div class="td-card-head">
                  <h3 class="td-card-title">
                    <svg viewBox="0 0 16 16" width="16" height="16" fill="none" class="td-card-crown">
                      <path d="M2 5l3 3 3-5 3 5 3-3v6a2 2 0 01-2 2H4a2 2 0 01-2-2V5z" stroke="#f59e0b" stroke-width="1.3" fill="#fef3c7"/>
                    </svg>
                    本月消耗排行
                  </h3>
                </div>
                <div class="td-rank-list">
                  <div v-for="(item, idx) in rankList" :key="item.name" class="td-rank-item">
                    <span :class="['td-rank-num', `rank-${idx + 1}`]">{{ idx + 1 }}</span>
                    <span class="td-rank-name">{{ item.name }}</span>
                    <div class="td-rank-bar-wrap">
                      <div class="td-rank-bar" :style="{ width: item.pct + '%' }"></div>
                    </div>
                    <span class="td-rank-val">{{ formatNumber(item.value) }} Token</span>
                    <span class="td-rank-pct">{{ item.pct }}%</span>
                  </div>
                </div>
                <button type="button" class="td-link-btn td-rank-more">查看全部排行 <svg viewBox="0 0 12 12" width="12" height="12" fill="none"><path d="M4.5 3l3 3-3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
              </div>

              <div class="td-card td-advice-card">
                <div class="td-card-head">
                  <h3 class="td-card-title">节省建议</h3>
                </div>
                <div class="td-advice-list">
                  <div v-for="advice in adviceList" :key="advice.title" class="td-advice-item">
                    <span class="td-advice-ico" :class="advice.type">
                      <svg v-if="advice.type === 'info'" viewBox="0 0 16 16" width="14" height="14" fill="none">
                        <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.3"/>
                        <path d="M8 7v4M8 5v.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                      </svg>
                      <svg v-else-if="advice.type === 'check'" viewBox="0 0 16 16" width="14" height="14" fill="none">
                        <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.3"/>
                        <path d="M5 8l2.2 2.2L11 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                      <svg v-else viewBox="0 0 16 16" width="14" height="14" fill="none">
                        <path d="M8 2l6 12H2L8 2z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
                        <path d="M8 7v3M8 12v.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                      </svg>
                    </span>
                    <div class="td-advice-content">
                      <div class="td-advice-title">{{ advice.title }}</div>
                      <div class="td-advice-desc">{{ advice.desc }}</div>
                    </div>
                    <button type="button" class="td-advice-action">{{ advice.action }}</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'recharge'" class="card-panel recharge-panel content-panel">
          <div class="panel-head">
            <div>
              <h3>充值记录</h3>
              <p>查看你的 Token 充值历史，含订单号、到账 Token、来源与时间。</p>
            </div>
            <button type="button" class="app-btn" :disabled="rechargeLoading" @click="loadRechargeRecords(rechargeRecords.current || 1)">刷新</button>
          </div>

          <div class="recharge-summary-grid">
            <div class="recharge-summary-card">
              <div class="recharge-summary-label">累计充值笔数</div>
              <div class="recharge-summary-value">{{ formatNumber(rechargeStats.totalRecords) }}</div>
              <div class="recharge-summary-sub">所有时间</div>
            </div>
            <div class="recharge-summary-card">
              <div class="recharge-summary-label">累计充值 Token</div>
              <div class="recharge-summary-value">{{ formatNumber(rechargeStats.totalTokens) }}</div>
              <div class="recharge-summary-sub">所有时间</div>
            </div>
            <div class="recharge-summary-card">
              <div class="recharge-summary-label">当前 Token 余额</div>
              <div class="recharge-summary-value">{{ formatNumber(tokenStats.tokenBalance ?? 0) }}</div>
              <div class="recharge-summary-sub">实时</div>
            </div>
          </div>

          <p v-if="rechargeLoadError" class="recharge-error">{{ rechargeLoadError }}</p>

          <div class="recharge-table-wrap">
            <table class="recharge-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>订单号</th>
                  <th>充值 Token</th>
                  <th>充值前余额</th>
                  <th>充值后余额</th>
                  <th>来源</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rechargeRecords.records" :key="row.id">
                  <td class="recharge-date">{{ row.createdTime ? formatTokenTime(row.createdTime) : '-' }}</td>
                  <td class="recharge-order">{{ row.orderNo || '-' }}</td>
                  <td class="recharge-amount-cell">+{{ formatNumber(row.tokenAmount) }}</td>
                  <td>{{ formatNumber(row.beforeBalance) }}</td>
                  <td>{{ formatNumber(row.afterBalance) }}</td>
                  <td><span class="recharge-source-tag">{{ rechargeSourceLabel(row.source) }}</span></td>
                  <td class="recharge-remark-cell">{{ row.remark || '-' }}</td>
                </tr>
                <tr v-if="!rechargeRecords.records.length && !rechargeLoading">
                  <td colspan="7" class="recharge-empty-cell">暂无充值记录</td>
                </tr>
                <tr v-if="rechargeLoading">
                  <td colspan="7" class="recharge-loading-cell">正在加载充值记录…</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="recharge-pager">
            <div class="recharge-pager-left">
              <button class="recharge-pager-btn" :disabled="(rechargeRecords.current || 1) <= 1" @click="loadRechargeRecords((rechargeRecords.current || 1) - 1)">
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none"><path d="M10 12L6 8l4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </button>
              <button v-for="p in rechargePageNumbers" :key="'rp-' + p" type="button" :class="['recharge-pager-num', { active: (rechargeRecords.current || 1) === p }]" @click="loadRechargeRecords(p)">{{ p }}</button>
              <button class="recharge-pager-btn" :disabled="(rechargeRecords.current || 1) >= rechargeTotalPages" @click="loadRechargeRecords((rechargeRecords.current || 1) + 1)">
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none"><path d="M6 12l4-4-4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </button>
            </div>
            <div class="recharge-pager-right">
              <span class="recharge-pager-total">共 <strong>{{ rechargeRecords.total || 0 }}</strong> 条</span>
              <select class="recharge-pager-size" v-model.number="rechargeRecords.size" @change="loadRechargeRecords(1)">
                <option :value="8">8条/页</option>
                <option :value="20">20条/页</option>
                <option :value="50">50条/页</option>
              </select>
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

    <footer class="profile-footer">
      <div class="profile-footer-inner">
        <span class="profile-footer-left">闲鱼助手 V{{ APP_VERSION }}</span>
        <span class="profile-footer-right">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="#ef4444" style="vertical-align:middle;margin-right:4px">
            <path d="M8 14s-5.5-3.5-5.5-7A3 3 0 0 1 8 4.5 3 3 0 0 1 13.5 7c0 3.5-5.5 7-5.5 7z"/>
          </svg>
          Made with love for sellers
        </span>
      </div>
    </footer>

    <PaymentModal
      :visible="paymentVisible"
      order-type="token"
      @close="paymentVisible = false"
      @paid="handleTokenPaid"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import PaymentModal from '../components/PaymentModal.vue'
import EmptyState from '../components/EmptyState.vue'
import {
  changeProfileEmail,
  changeProfilePassword,
  changeProfilePhone,
  getProfileOverview,
  getRechargeRecords,
  getTokenLedger,
  getTokenTrend,
  sendProfileCode
} from '../api/profile.js'
import { useAuthCapabilities } from '../utils/useAuthCapabilities.js'
import { globalConfirm } from '../composables/confirmState.js'
import { getFeatureSwitchStatus, getFeatureSwitchComparison } from '../api/feature-switch.js'
import { getTokenRechargePlans } from '../api/payment.js'
import { APP_VERSION } from '../utils/appMeta.js'

const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'security', label: '账号安全' },
  { key: 'token', label: 'Token 消耗' },
  { key: 'recharge', label: '充值记录' }
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
const PROFILE_MAIN_TABS = new Set(['overview', 'security', 'token', 'recharge'])
const activeTab = ref('overview')
const saving = ref(false)
const overview = reactive({})
const overviewAvailable = ref(false)
const overviewLoadError = ref('')
const notice = reactive({ text: '', type: 'info' })
const paymentVisible = ref(false)
const tokenPlans = ref([])
async function loadTokenPlans() {
  // 加载后台配置的 Token 充值套餐
  try {
    const plans = await getTokenRechargePlans()
    tokenPlans.value = Array.isArray(plans) ? plans : []
  } catch (e) {
    tokenPlans.value = []
  }
}
const tokenLedger = reactive({ records: [], total: 0, current: 1, size: 8 })
const tokenLoading = ref(false)
const tokenLoadError = ref('')
const tokenStats = reactive({ todayConsume: null, sevenDayConsume: null, monthConsume: null, tokenBalance: null })
// Token 消耗趋势（按日聚合）与本月分类构成，由后端 /profile/token-trend 返回真实数据
const tokenTrendSeries = ref([])
const tokenTrendCategories = ref([])
const tokenTrendDays = ref(7)
const tokenTrendLoading = ref(false)
const jumpPage = ref(1)
const trendChartRef = ref(null)
const tokenPieChartRef = ref(null)
let trendChartInstance = null
let tokenPieChartInstance = null

// 充值记录状态（前台用户查看自己的 Token 充值历史）
const rechargeRecords = reactive({ records: [], total: 0, current: 1, size: 8 })
const rechargeLoading = ref(false)
const rechargeLoadError = ref('')
const rechargeStats = reactive({ totalRecords: 0, totalTokens: 0 })

const packageList = computed(() => {
  if (!tokenPlans.value.length) return []
  return tokenPlans.value.map((plan, index) => {
    const tokenAmount = Number(plan.tokenAmount || 0)
    const bonusToken = Number(plan.bonusToken || 0)
    const totalToken = tokenAmount + bonusToken
    const priceYuan = Number(plan.priceYuan || 0)
    const unitPrice = totalToken > 0 && priceYuan > 0
      ? (priceYuan / totalToken).toFixed(4).replace(/\.?0+$/, '')
      : '0'
    return {
      id: plan.id,
      name: plan.planName || `${formatNumber(totalToken)} Token`,
      amount: totalToken,
      price: formatPlanPrice(plan.priceYuan),
      unitPrice,
      recommend: index === 0
    }
  })
})

function formatPlanPrice(priceYuan) {
  if (priceYuan === null || priceYuan === undefined || priceYuan === '') return '—'
  const num = Number(priceYuan)
  if (!Number.isFinite(num)) return '—'
  return Number.isInteger(num) ? String(num) : num.toFixed(2).replace(/\.00$/, '')
}

const adviceList = [
  { title: '优化自动化频率', desc: '自动发货消耗占比较高，可适当调整触发频率，节省Token。', action: '去优化', type: 'info' },
  { title: '排查高消耗工作流', desc: '部分工作流消耗波动较大，建议检查任务配置。', action: '去排查', type: 'check' },
  { title: '关注异常波动', desc: '消耗达到峰值时建议复盘日志，优化调用策略。', action: '查看趋势', type: 'warn' }
]

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

const currentTabLabel = computed(() => {
  const found = tabs.find(t => t.key === menuActiveKey.value)
  return found ? found.label : '概览'
})

function handleHeaderRefresh() {
  if (activeTab.value === 'token') {
    loadTokenLedger(tokenLedger.current || 1)
    loadTokenTrend(30)
  } else if (activeTab.value === 'recharge') {
    loadRechargeRecords(rechargeRecords.current || 1)
  } else {
    loadOverview()
    loadTokenLedger(1, 1)
    loadTokenTrend(7)
  }
  loadMemberComparison()
}
const planPeriodText = computed(() => {
  if (!overview.activePlan) return '套餐状态暂不可用'
  return overview.activePlan.endTime ? `有效期至 ${displayDateOnly(overview.activePlan.endTime)}` : '有效期以后台权益为准'
})

// 会员等级展示文案：FREE/UNKNOWN 显示"普通会员"，其他显示 planName
const planBadgeText = computed(() => {
  if (planBadge.value === 'FREE' || planBadge.value === 'UNKNOWN') return '普通会员'
  return planName.value || '普通会员'
})

// 套餐状态展示文案（用于"充值与消费"卡片）
const planStatusText = computed(() => {
  if (planBadge.value === 'FREE' || planBadge.value === 'UNKNOWN') return '免费版'
  return planName.value || '已激活'
})

// 邮箱/手机号验证状态展示
const emailVerifiedText = computed(() => {
  if (!overviewAvailable.value) return '—'
  if (!maskedEmail.value) return '未绑定'
  return overview.emailVerified ? '已验证' : '未验证'
})
const emailVerifiedTone = computed(() => {
  if (!overviewAvailable.value || !maskedEmail.value) return ''
  return overview.emailVerified ? 'pc-info-value-green' : 'pc-info-value-orange'
})
const phoneVerifiedText = computed(() => {
  if (!overviewAvailable.value) return '—'
  if (!maskedPhone.value) return '未绑定'
  return overview.phoneVerified ? '已绑定' : '未验证'
})
const phoneVerifiedTone = computed(() => {
  if (!overviewAvailable.value || !maskedPhone.value) return ''
  return overview.phoneVerified ? 'pc-info-value-green' : 'pc-info-value-orange'
})

// 到期提醒板块：基于 overview.activePlan.endTime 计算剩余天数
const planExpireInfo = computed(() => {
  const endTime = overview.activePlan?.endTime
  if (!endTime) {
    // 手动 vip_level 或无订阅：无固定到期日
    return { hasEnd: false, days: null, dateText: '有效期以后台权益为准' }
  }
  const end = new Date(endTime)
  if (Number.isNaN(end.getTime())) {
    return { hasEnd: false, days: null, dateText: '有效期以后台权益为准' }
  }
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  end.setHours(0, 0, 0, 0)
  const diffMs = end.getTime() - today.getTime()
  const days = Math.round(diffMs / (24 * 60 * 60 * 1000))
  return { hasEnd: true, days, dateText: `有效期至 ${displayDateOnly(endTime)}` }
})
const planExpireDayText = computed(() => {
  const info = planExpireInfo.value
  if (!info.hasEnd) return '∞'
  if (info.days < 0) return '0'
  return String(info.days)
})
const planExpireDisplay = computed(() => {
  const info = planExpireInfo.value
  if (!info.hasEnd) return '永久'
  if (info.days < 0) return '已过期'
  return String(info.days)
})
const planExpireUnitText = computed(() => {
  const info = planExpireInfo.value
  if (!info.hasEnd) return ''
  if (info.days < 0) return ''
  return '天后到期'
})
const planExpireDateText = computed(() => planExpireInfo.value.dateText)

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

const pieChartRef = ref(null)
const lineChartRef = ref(null)
let pieChart = null
let lineChart = null

// 会员功能对比：默认空数组，由 loadMemberComparison() 从后端拉取后填充。
// 数据结构与后台 /admin-api/system/feature-switches 一致（key/title/group/normal/vip/svp），
// 仅用于只读展示。失败降级为空数组 + 错误提示。
const memberCompareFeatures = ref([])
const memberComparisonLoading = ref(false)
const memberComparisonError = ref('')

/**
 * 功能分组定义，与后台 admin-web feature-switch/index.vue 的 GROUPS 常量保持一致。
 * 顺序即展示顺序；未匹配 group 的功能归入 "其他"。
 */
const FEATURE_COMPARISON_GROUPS = [
  { key: 'overview', label: '概览', icon: '📊' },
  { key: 'account', label: '账号与商品', icon: '📦' },
  { key: 'message', label: '消息与商机', icon: '💬' },
  { key: 'automation', label: '自动化', icon: '⚙️' },
  { key: 'system', label: '系统设置', icon: '🛠️' },
  { key: 'hidden', label: '会员', icon: '👑' },
  { key: 'misc', label: '其他', icon: '📂' }
]

/** 按分组聚合后的对比数据，用于表格渲染 */
const memberCompareData = computed(() => {
  const features = memberCompareFeatures.value
  if (!Array.isArray(features) || features.length === 0) return []
  const buckets = new Map()
  for (const g of FEATURE_COMPARISON_GROUPS) buckets.set(g.key, [])
  for (const f of features) {
    const g = String(f?.group || 'misc')
    if (!buckets.has(g)) buckets.set(g, [])
    buckets.get(g).push(f)
  }
  const result = []
  for (const g of FEATURE_COMPARISON_GROUPS) {
    const items = buckets.get(g.key) || []
    if (items.length === 0) continue
    result.push({
      category: g.label,
      icon: g.icon,
      items: items.map(f => ({
        key: f.key,
        name: f.title || f.key,
        normal: boolToMark(f.normal),
        vip: boolToMark(f.vip),
        svip: boolToMark(f.svp)
      }))
    })
  }
  return result
})

function boolToMark(value) {
  return value === true || value === 'true' || value === 1 || value === '1' ? '✓' : '—'
}

async function loadMemberComparison() {
  memberComparisonLoading.value = true
  memberComparisonError.value = ''
  try {
    const list = await getFeatureSwitchComparison()
    memberCompareFeatures.value = Array.isArray(list) ? list : []
    return true
  } catch (error) {
    memberCompareFeatures.value = []
    memberComparisonError.value = error?.message || '功能对比数据加载失败'
    return false
  } finally {
    memberComparisonLoading.value = false
  }
}

function initCharts() {
  if (!pieChartRef.value || !lineChartRef.value) return

  pieChart = echarts.init(pieChartRef.value)
  lineChart = echarts.init(lineChartRef.value)

  // 使用真实 tokenStats：余额、今日消耗、本月消耗（本月消耗剔除今日部分避免重复）
  const balance = Number(tokenStats.tokenBalance ?? overview.tokenBalance ?? 0) || 0
  const todayUsed = Number(tokenStats.todayConsume ?? 0) || 0
  const monthUsed = Math.max(0, (Number(tokenStats.monthConsume ?? 0) || 0) - todayUsed)
  const pieData = [
    { value: balance, name: '剩余Token', itemStyle: { color: '#2563eb' } },
    { value: todayUsed, name: '今日消耗', itemStyle: { color: '#16a34a' } },
    { value: monthUsed, name: '本月消耗', itemStyle: { color: '#9333ea' } }
  ]

  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} Token ({d}%)' },
    color: ['#2563eb', '#16a34a', '#9333ea'],
    series: [{
      type: 'pie',
      radius: ['48%', '70%'],
      center: ['50%', '42%'],
      avoidLabelOverlap: false,
      label: {
        show: true,
        position: 'center',
        formatter: function(params) {
          const total = pieData.reduce((s, d) => s + d.value, 0)
          return total.toLocaleString() + '\nToken'
        },
        fontSize: 18,
        fontWeight: 'bold',
        color: '#1e293b',
        lineHeight: 24
      },
      labelLine: { show: false },
      data: pieData,
      itemStyle: {
        borderWidth: 3,
        borderColor: '#fff'
      }
    }],
    legend: {
      orient: 'horizontal',
      bottom: 4,
      left: 'center',
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 16,
      icon: 'circle',
      textStyle: { fontSize: 12, color: '#64748b' },
      formatter: function(name) {
        const total = pieData.reduce((s, d) => s + d.value, 0)
        const item = pieData.find(d => d.name === name)
        const pct = total > 0 ? ((item.value / total) * 100).toFixed(1) : '0.0'
        return name + '  ' + pct + '%'
      }
    }
  })

  // 7 日趋势图：使用后端返回的真实每日消耗序列
  const tData = trendData.value
  const dates = trendDateLabels.value.length
    ? trendDateLabels.value
    : Array.from({ length: tokenTrendDays.value }, (_, i) => dateLabel(i))

  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
      axisLabel: { fontSize: 10, color: '#94a3b8' }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
      axisLabel: { fontSize: 10, color: '#94a3b8' }
    },
    series: [{
      type: 'line',
      data: tData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#3b82f6', width: 2.5 },
      itemStyle: { color: '#3b82f6', borderWidth: 2, borderColor: '#fff' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59, 130, 246, 0.18)' },
          { offset: 1, color: 'rgba(59, 130, 246, 0.02)' }
        ])
      }
    }]
  })
}

function disposeCharts() {
  if (pieChart) { pieChart.dispose(); pieChart = null }
  if (lineChart) { lineChart.dispose(); lineChart = null }
  if (trendChartInstance) { trendChartInstance.dispose(); trendChartInstance = null }
  if (tokenPieChartInstance) { tokenPieChartInstance.dispose(); tokenPieChartInstance = null }
}

function handleResize() {
  pieChart?.resize()
  lineChart?.resize()
  trendChartInstance?.resize()
  tokenPieChartInstance?.resize()
}

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

const pageNumbers = computed(() => {
  const cur = tokenLedger.current || 1
  const total = totalPages.value
  if (total <= 5) return Array.from({ length: total }, (_, i) => i + 1)
  if (cur <= 3) return [1, 2, 3, 4, 5]
  if (cur >= total - 2) return [total - 4, total - 3, total - 2, total - 1, total]
  return [cur - 2, cur - 1, cur, cur + 1, cur + 2]
})

const displayTableRows = computed(() => {
  return tokenLedger.records || []
})

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
    image_gen: 'AI 生图', admin: '管理员', system: '系统',
    auto_delivery: '自动发货', auto_reply: '在线消息', workflow: '工作流',
    product_publish: '发布商品', opportunity: '商机发掘', polish: '润色',
    rag_chat: 'AI客服', rewrite: '改写'
  }
  return map[type] || type
}

const refTypeCategory = type => {
  if (!type) return '其他'
  if (type.includes('auto_delivery')) return '自动发货'
  if (type.includes('workflow') || type.includes('polish')) return '工作流'
  if (type.includes('product') || type.includes('publish') || type.includes('rewrite')) return '发布商品'
  if (type.includes('reply') || type.includes('chat') || type.includes('message')) return '在线消息'
  return '其他'
}

const categoryColorMap = {
  '自动发货': '#165DFF',
  '工作流': '#36CFC9',
  '发布商品': '#F7BA1E',
  '在线消息': '#F77234',
  '其他': '#86909C'
}

const tokenPageSize = 8

const pieLegendData = computed(() => {
  // 优先使用后端 /profile/token-trend 返回的本月分类汇总（真实数据）
  const cats = tokenTrendCategories.value || []
  if (cats.length) {
    const totalVal = cats.reduce((s, c) => s + (Number(c.consume) || 0), 0) || 1
    return cats.map(c => {
      const value = Number(c.consume) || 0
      const name = refTypeCategory(c.refType)
      return {
        name,
        value,
        pct: Math.round(value / totalVal * 1000) / 10,
        color: categoryColorMap[name] || '#86909C'
      }
    })
  }
  // 后端数据未就绪时返回空数组，让饼图显示"暂无数据"
  return []
})

const rankList = computed(() => {
  const legend = pieLegendData.value
  if (!legend.length) return []
  const maxVal = legend[0].value || 1
  return legend.map(item => ({
    ...item,
    pct: Math.round(item.value / maxVal * 100)
  }))
})

// 趋势图数据：直接使用后端返回的每日消耗序列（真实数据），不再本地生成
const trendData = computed(() => {
  const series = tokenTrendSeries.value || []
  return series.map(p => Number(p.consume) || 0)
})

// 趋势图日期标签：使用后端返回的真实日期
const trendDateLabels = computed(() => {
  const series = tokenTrendSeries.value || []
  return series.map(p => {
    const dateStr = p.date || ''
    // yyyy-MM-dd → MM-dd
    const parts = dateStr.split('-')
    if (parts.length === 3) return `${parts[1]}-${parts[2]}`
    return dateStr
  })
})

const avgDaily = computed(() => {
  const arr = trendData.value
  return arr.length ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0
})

const peakDay = computed(() => {
  const arr = trendData.value
  if (!arr.length) return { val: 0, idx: 0 }
  let max = arr[0], idx = 0
  arr.forEach((v, i) => { if (v > max) { max = v; idx = i } })
  return { val: max, idx }
})

const lowDay = computed(() => {
  const arr = trendData.value
  if (!arr.length) return { val: 0, idx: 0 }
  let min = arr[0], idx = 0
  arr.forEach((v, i) => { if (v < min) { min = v; idx = i } })
  return { val: min, idx }
})

// 兼容历史调用：按 tokenTrendDays 推导日期标签
const dateLabel = offset => {
  const labels = trendDateLabels.value
  if (labels.length && offset >= 0 && offset < labels.length) return labels[offset]
  const d = new Date()
  d.setDate(d.getDate() - ((tokenTrendDays.value - 1) - offset))
  return `${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')}`
}

const budgetPercent = computed(() => {
  const used = tokenStats.monthConsume || 0
  const total = 10000
  return Math.min(100, Math.round(used / total * 100))
})

const tokenYuanValue = computed(() => {
  return ((tokenStats.tokenBalance || 0) / 100).toFixed(2)
})

function updateTokenChartsData() {
  if (!trendChartInstance || !tokenPieChartInstance) return
  const tData = trendData.value
  const dates = trendDateLabels.value.length
    ? trendDateLabels.value
    : Array.from({ length: tokenTrendDays.value }, (_, i) => dateLabel(i))
  trendChartInstance.setOption({
    xAxis: { data: dates },
    series: [{ data: tData }]
  })
  tokenPieChartInstance.setOption({
    series: [{
      data: pieLegendData.value.map(d => ({ value: d.value, name: d.name, itemStyle: { color: d.color } }))
    }]
  })
}

// 加载后端 /profile/token-trend 返回的真实每日消耗序列与本月分类构成
async function loadTokenTrend(days = 7) {
  tokenTrendLoading.value = true
  try {
    const res = await getTokenTrend({ days })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Token 趋势响应格式异常')
    }
    tokenTrendSeries.value = Array.isArray(data.series) ? data.series : []
    tokenTrendCategories.value = Array.isArray(data.categories) ? data.categories : []
    tokenTrendDays.value = Number(data.days) || days
  } catch (e) {
    tokenTrendSeries.value = []
    tokenTrendCategories.value = []
  } finally {
    tokenTrendLoading.value = false
  }
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
    const monthConsume = nullableNumber(stats.monthConsume)
    const tokenBalance = nullableNumber(stats.tokenBalance)
    if ([todayConsume, sevenDayConsume, tokenBalance].some(value => value === null || value < 0)) {
      throw new Error('Token 统计响应缺少有效指标')
    }
    tokenStats.todayConsume = todayConsume
    tokenStats.sevenDayConsume = sevenDayConsume
    tokenStats.monthConsume = monthConsume ?? 0
    tokenStats.tokenBalance = tokenBalance
    updateTokenChartsData()
    jumpPage.value = tokenLedger.current
  } catch (error) {
    tokenLedger.records = []
    tokenLedger.total = 0
    Object.assign(tokenStats, { todayConsume: null, sevenDayConsume: null, monthConsume: null, tokenBalance: null })
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

// 充值记录分页总页数
const rechargeTotalPages = computed(() => {
  const total = Number(rechargeRecords.total) || 0
  const size = Number(rechargeRecords.size) || 8
  return Math.max(1, Math.ceil(total / size))
})

// 充值记录分页页码（最多显示 5 个）
const rechargePageNumbers = computed(() => {
  const total = rechargeTotalPages.value
  const current = Number(rechargeRecords.current) || 1
  if (total <= 5) return Array.from({ length: total }, (_, i) => i + 1)
  if (current <= 3) return [1, 2, 3, 4, 5]
  if (current >= total - 2) return [total - 4, total - 3, total - 2, total - 1, total]
  return [current - 2, current - 1, current, current + 1, current + 2]
})

// 来源标签文案
function rechargeSourceLabel(source) {
  if (!source) return '—'
  const map = {
    alipay: '支付宝',
    wechat: '微信支付',
    admin: '后台手动',
    system: '系统赠送',
    plan: '套餐购买',
    manual: '手动充值'
  }
  return map[String(source).toLowerCase()] || source
}

async function loadRechargeRecords(page = 1) {
  rechargeLoading.value = true
  rechargeLoadError.value = ''
  try {
    const res = await getRechargeRecords({ current: page, size: rechargeRecords.size })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('充值记录响应格式异常')
    }
    if (!Array.isArray(data.records)) throw new Error('充值记录响应格式异常')
    rechargeRecords.records = data.records.map((record, index) => ({
      ...record,
      id: record.id ?? `r-${page}-${index}`,
      createdTime: record.createdTime || record.createTime || record.time || '',
      orderNo: record.orderNo || record.paymentOrderId || '',
      tokenAmount: nullableNumber(record.tokenAmount ?? record.amount ?? record.tokens) ?? 0,
      beforeBalance: nullableNumber(record.beforeBalance ?? record.balanceBefore) ?? 0,
      afterBalance: nullableNumber(record.afterBalance ?? record.balanceAfter) ?? 0,
      source: record.source || record.channel || '',
      remark: record.remark || record.description || ''
    }))
    rechargeRecords.total = Number(data.total) || 0
    rechargeRecords.current = Number(data.current) || 1
    rechargeRecords.size = Number(data.size) || rechargeRecords.size
    const stats = data.stats || {}
    rechargeStats.totalRecords = Number(stats.totalRecords || data.total || 0)
    rechargeStats.totalTokens = Number(stats.totalTokens || 0)
  } catch (error) {
    rechargeRecords.records = []
    rechargeRecords.total = 0
    rechargeStats.totalRecords = 0
    rechargeStats.totalTokens = 0
    rechargeLoadError.value = error?.message || '充值记录加载失败，请重试。'
  } finally {
    rechargeLoading.value = false
  }
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

function displayTokenNum(value, fallback = 0) {
  if (value === null || value === undefined || value === '') return formatNumber(fallback)
  return formatNumber(value)
}

function formatTokenTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function badgeTypeClass(type) {
  if (!type) return 'tp-badge-gray'
  if (type === 'recharge' || type === 'refund') return 'tp-badge-green'
  if (type === 'ai_charge' || type === 'ai_image_charge' || type.startsWith('deduct')) return 'tp-badge-red'
  return 'tp-badge-orange'
}

function amountColorClass(value) {
  if (value === null || value === undefined) return ''
  const n = Number(value)
  if (n > 0) return 'tp-amount-positive'
  if (n < 0) return 'tp-amount-negative'
  return 'tp-amount-zero'
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
    // 检查"升级会员"功能开关：开启则前往会员中心，关闭则提示暂未开放
    try {
      const status = await getFeatureSwitchStatus()
      if (status?.accessible?.['member-upgrade'] === true) {
        location.hash = '#/vip'
        return
      }
    } catch (e) {
      // 查询失败时降级为提示暂未开放，避免后端故障导致误跳转
    }
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
  loadTokenPlans()
  const refreshed = await loadOverview()
  // 支付成功后刷新 Token 统计与趋势，确保概览/Token 页数据一致
  loadTokenLedger(activeTab.value === 'token' ? (tokenLedger.current || 1) : 1, activeTab.value === 'token' ? tokenLedger.size : 1)
  loadTokenTrend(activeTab.value === 'token' ? 30 : 7)
  showNotice(refreshed ? '支付成功，Token 余额已刷新' : '支付成功，但余额刷新失败，请稍后重试', refreshed ? 'success' : 'warn')
}

function onHeaderAction(event) {
  if (event.detail === 'refresh-profile') handleHeaderRefresh()
}

function onProfileTabOpen(event) {
  activeTab.value = normalizeProfileTab(event.detail)
}

async function initOverviewCharts() {
  await nextTick()
  disposeCharts()
  if (activeTab.value === 'overview') {
    setTimeout(() => {
      initCharts()
      window.addEventListener('resize', handleResize)
    }, 100)
  }
}

function initTokenCharts() {
  if (!trendChartRef.value || !tokenPieChartRef.value) return

  if (trendChartInstance) { trendChartInstance.dispose() }
  if (tokenPieChartInstance) { tokenPieChartInstance.dispose() }

  const tData = trendData.value
  const dates = trendDateLabels.value.length
    ? trendDateLabels.value
    : Array.from({ length: tokenTrendDays.value }, (_, i) => dateLabel(i))
  const maxVal = Math.max(...tData, 100)
  const yMax = Math.ceil(maxVal / 200) * 200 + 200

  trendChartInstance = echarts.init(trendChartRef.value)
  trendChartInstance.setOption({
    grid: { left: 45, right: 15, top: 20, bottom: 35 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#E5E6EB' } },
      axisTick: { show: false },
      axisLabel: { color: '#86909C', fontSize: 11, interval: 4 }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: yMax,
      splitNumber: 5,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#F2F3F5', type: 'dashed' } },
      axisLabel: { color: '#86909C', fontSize: 11 }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#E5E6EB',
      textStyle: { color: '#1D2129' }
    },
    series: [{
      type: 'line',
      data: tData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#165DFF', width: 2.5 },
      itemStyle: { color: '#165DFF', borderWidth: 2, borderColor: '#fff' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(22, 93, 255, 0.15)' },
          { offset: 1, color: 'rgba(22, 93, 255, 0.02)' }
        ])
      }
    }]
  })

  tokenPieChartInstance = echarts.init(tokenPieChartRef.value)
  tokenPieChartInstance.setOption({
    series: [{
      type: 'pie',
      radius: ['65%', '85%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      labelLine: { show: false },
      data: pieLegendData.value.map(d => ({
        value: d.value,
        name: d.name,
        itemStyle: { color: d.color }
      }))
    }]
  })

  window.addEventListener('resize', handleResize)
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  window.addEventListener('xya-profile-open-tab', onProfileTabOpen)
  consumeRequestedProfileTab()
  refreshAuthCapabilities()
  loadOverview().then(() => {
    initOverviewCharts()
  })
  // 概览页需要 tokenStats（余额/今日/本月）与 7 日趋势数据来渲染统计卡片与图表
  // loadTokenLedger(1, 1) 仅用于获取 stats（取 1 条记录最小化开销）
  loadTokenLedger(1, 1).then(() => {
    if (activeTab.value === 'overview') initOverviewCharts()
  })
  // 加载 7 日趋势序列与本月分类构成（真实数据）
  loadTokenTrend(7).then(() => {
    if (activeTab.value === 'overview') initOverviewCharts()
  })
  loadMemberComparison()
  loadTokenPlans()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
  window.removeEventListener('xya-profile-open-tab', onProfileTabOpen)
  window.removeEventListener('resize', handleResize)
  disposeCharts()
})

watch(activeTab, async (tab) => {
  if (tab === 'token') {
    loadTokenLedger()
    // Token 页使用 30 天趋势数据
    await loadTokenTrend(30)
    await nextTick()
    setTimeout(() => initTokenCharts(), 100)
  }
  if (tab === 'recharge') {
    loadRechargeRecords(rechargeRecords.current || 1)
  }
  if (tab === 'overview') {
    // 概览页使用 7 天趋势数据；若已被 token 页切回，重新加载 7 天
    if (tokenTrendDays.value !== 7) {
      await loadTokenTrend(7)
    }
    initOverviewCharts()
  } else if (tab !== 'token') {
    window.removeEventListener('resize', handleResize)
    disposeCharts()
  }
})
</script>

<style scoped>
.profile-center {
  width: 100%;
  min-height: calc(100vh - 44px);
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
  border-radius: 14px;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.98), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  padding: 18px 16px 16px;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04);
}

.security-card.enhanced {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 260px;
}

.security-card.enhanced:hover {
  box-shadow: 0 4px 12px rgba(31, 53, 94, 0.08);
  border-color: rgba(13, 107, 255, 0.25);
}

.security-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
}

.security-card-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
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
  font-size: 16px;
  font-weight: 700;
}

.security-card > span {
  display: block;
  min-height: 44px;
  margin: 0;
  color: #667491;
  font-size: 13px;
  line-height: 1.6;
}

.security-card .badge { margin-bottom: 6px; }
.security-card .app-btn {
  width: 100%;
  min-width: 0;
  margin-top: auto;
  align-self: stretch;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 4px 10px rgba(13, 107, 255, 0.18);
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
  grid-template-columns: 220px minmax(0, 1fr);
  align-items: center;
  gap: 18px;
  padding: 18px 22px 14px;
  border-radius: 14px;
  margin-bottom: 16px;
  border: 1px solid rgba(238, 227, 201, 0.9);
  background:
    radial-gradient(circle at 14% 60%, rgba(var(--security-accent-rgb), 0.1), transparent 26%),
    linear-gradient(135deg, #fff8ea, #ffffff 70%);
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(31, 53, 94, 0.04);
}

.security-level-card::before {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  pointer-events: none;
}

.security-level-card.high {
  --security-accent: #16bf78;
  --security-accent-rgb: 22, 191, 120;
  background:
    radial-gradient(circle at 14% 60%, rgba(var(--security-accent-rgb), 0.1), transparent 26%),
    linear-gradient(135deg, #ebfaf1, #ffffff 70%);
  border-color: #bfe7ce;
}

.security-level-card.medium {
  --security-accent: #ff9f22;
  --security-accent-rgb: 255, 159, 34;
  background:
    radial-gradient(circle at 14% 60%, rgba(var(--security-accent-rgb), 0.12), transparent 26%),
    linear-gradient(135deg, #fff7e9, #ffffff 70%);
  border-color: #fde1b3;
}

.security-level-card.low {
  --security-accent: #ff5b61;
  --security-accent-rgb: 255, 91, 97;
  background:
    radial-gradient(circle at 14% 60%, rgba(var(--security-accent-rgb), 0.1), transparent 26%),
    linear-gradient(135deg, #fff2f2, #ffffff 70%);
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
  min-height: 170px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.security-level-visual::after {
  content: '';
  position: absolute;
  left: 30px;
  right: 30px;
  bottom: 20px;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0.2));
  opacity: 0.8;
}

.security-level-visual-image {
  display: none;
}

.security-level-visual-illustration {
  position: relative;
  width: 100%;
  height: 170px;
  overflow: visible;
  z-index: 1;
}

.security-illustration-shape {
  display: none;
}

.security-orbit-glow,
.security-stage-shadow,
.security-stage-plate,
.security-stage-core {
  display: none;
}

.security-orbit-line,
.security-orbit-dash {
  fill: none;
  stroke: rgba(var(--security-accent-rgb), 0.36);
  stroke-linecap: round;
}

.security-orbit-line {
  stroke-width: 2;
}

.security-orbit-dash {
  stroke-width: 2;
  stroke-dasharray: 6 7;
  opacity: 0.8;
}

.security-orbit-dot {
  fill: rgba(var(--security-accent-rgb), 0.88);
}

.security-orbit-dot.dot-top {
  fill: rgba(var(--security-accent-rgb), 0.7);
}

.security-shield-back {
  fill: rgba(var(--security-accent-rgb), 0.22);
}

.security-shield-front {
  fill: var(--security-accent);
  filter: drop-shadow(0 8px 14px rgba(var(--security-accent-rgb), 0.18));
}

.security-shield-gloss {
  display: none;
}

.security-shield-outline {
  fill: none;
  stroke: rgba(255, 255, 255, 0.7);
  stroke-width: 2.5;
}

.security-shield-check {
  fill: none;
  stroke: #fff;
  stroke-width: 6;
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
  font-size: 13px;
  color: #667491;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.security-level-text strong {
  display: block;
  margin: 4px 0 8px;
  font-size: 36px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.02em;
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
  box-shadow: 0 2px 6px rgba(var(--security-accent-rgb), 0.18);
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
  gap: 18px;
  margin-top: 16px;
  padding: 16px;
  background:
    linear-gradient(180deg, #fcfdff 0%, #f7faff 100%);
  border: 1px solid #e6eefa;
  border-radius: 14px;
}

.security-tips-copy h4 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 700;
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
  min-height: 86px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(225, 235, 248, 0.9);
  background: rgba(255, 255, 255, 0.9);
}

.security-tip-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  background: #eef5ff;
}

.security-tip-icon svg {
  width: 20px;
  height: 20px;
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

.profile-overview-v2 {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.profile-overview-v2 .pc-banner {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 156px;
  padding: 24px 28px;
  border-radius: 18px;
  background: linear-gradient(135deg, #e0ecff 0%, #c7ddff 50%, #b3d1ff 100%);
  overflow: hidden;
  border: 1px solid rgba(147, 197, 253, 0.5);
  box-shadow: 0 4px 14px rgba(59, 130, 246, 0.08);
}

.profile-overview-v2 .pc-banner::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 90% 30%, rgba(255, 255, 255, 0.35) 0%, transparent 55%);
  pointer-events: none;
}

.profile-overview-v2 .pc-banner::after {
  display: none;
}

.pc-banner-left {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 20px;
}

.pc-avatar-wrap {
  flex-shrink: 0;
  position: relative;
}

.pc-avatar {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(37, 99, 235, 0.25), 0 2px 8px rgba(37, 99, 235, 0.1);
  border: 4px solid rgba(255,255,255,0.9);
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.pc-banner-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pc-username-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.pc-username {
  font-size: 28px;
  font-weight: 800;
  color: #1e3a5f;
  letter-spacing: -0.01em;
  text-shadow: 0 1px 2px rgba(255,255,255,0.3);
}

.pc-svip-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 20px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #b45309;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid #fcd34d;
}

.pc-connect-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #22c55e;
  font-weight: 600;
}

.pc-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.2);
}

.pc-user-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pc-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.pc-tag-blue {
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #dbeafe;
}

.pc-tag-green {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #dcfce7;
}

.pc-tag-gray {
  background: #f8fafc;
  color: #94a3b8;
  border: 1px solid #e2e8f0;
}

.pc-manage-btn {
  width: fit-content;
  padding: 8px 20px;
  font-size: 13px;
  margin-top: 2px;
}

.pc-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
  text-decoration: none;
  white-space: nowrap;
}

.pc-btn-primary {
  background: #2563eb;
  color: #fff;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.2);
}

.pc-btn-primary:hover {
  background: #1d4ed8;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3);
}

.pc-btn-outline {
  background: #fff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
}

.pc-btn-outline:hover {
  background: #eff6ff;
  border-color: #93c5fd;
}

.pc-btn-light {
  background: #fff;
  color: #475569;
  border: 1px solid #e2e8f0;
}

.pc-btn-light:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #334155;
}

.pc-btn-light:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #334155;
}

.pc-banner-right {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: flex-start;
}

.pc-banner-shield {
  position: absolute;
  right: 40px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1;
}

.pc-refresh-btn {
  position: relative;
  z-index: 3;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: rgba(255,255,255,0.8);
  border: 1px solid rgba(186, 216, 255, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #3b82f6;
  transition: all 0.2s;
  backdrop-filter: blur(4px);
}

.pc-refresh-btn:hover {
  background: #fff;
  transform: rotate(180deg);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.pc-stats-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.pc-stat-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  border: 1px solid #eef2f7;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 132px;
  position: relative;
  overflow: hidden;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}

.pc-stat-card::before {
  display: none;
}

.pc-stat-card:hover {
  box-shadow: 0 3px 10px rgba(15, 23, 42, 0.06);
  border-color: #dbe3ee;
}

.pc-stat-card:hover::before {
  opacity: 0;
}

.pc-stat-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pc-stat-ico {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06);
  position: relative;
}

.pc-stat-ico::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(255,255,255,0.4) 0%, transparent 50%);
  pointer-events: none;
}

.pc-stat-ico-blue {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
}

.pc-stat-ico-green {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: #fff;
}

.pc-stat-ico-red {
  background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
  color: #fff;
}

.pc-stat-ico-gold {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: #fff;
}

.pc-stat-label {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
}

.pc-stat-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 4px;
}

.pc-stat-value strong {
  font-size: 24px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1.15;
  font-family: -apple-system, 'SF Pro Display', 'PingFang SC', sans-serif;
  letter-spacing: -0.01em;
}

.pc-stat-value em {
  font-size: 13px;
  font-style: normal;
  color: #94a3b8;
  font-weight: 600;
}

.pc-stat-value-svip strong {
  font-size: 20px;
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.pc-stat-sub {
  margin-top: auto;
  padding-top: 4px;
}

.pc-stat-yuan {
  font-size: 12px;
  color: #94a3b8;
}

.pc-stat-trend {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  font-weight: 600;
}

.pc-trend-down {
  color: #22c55e;
}

.pc-trend-up {
  color: #ef4444;
}

.pc-stat-btn {
  margin-top: 8px;
  width: 100%;
  padding: 8px;
  font-size: 13px;
}

.pc-three-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.pc-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  border: 1px solid #eef2f7;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}

.pc-card:hover {
  box-shadow: 0 3px 10px rgba(15, 23, 42, 0.06);
  border-color: #dbe3ee;
}

.pc-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 14px 0;
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  letter-spacing: -0.01em;
}

.pc-card-sub {
  font-size: 12px;
  font-weight: 500;
  color: #94a3b8;
  margin-left: 4px;
}

.pc-userinfo-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.pc-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed #f1f5f9;
}

.pc-info-row:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.pc-info-label {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 500;
}

.pc-info-value {
  font-size: 13px;
  color: #334155;
  font-weight: 600;
}

.pc-info-value-gold {
  color: #d97706;
}

.pc-info-value-green {
  color: #16a34a;
}

.pc-info-value-orange {
  color: #ea580c;
}

.pc-recharge-card {
  display: flex;
  flex-direction: column;
}

.pc-recharge-features {
  list-style: none;
  margin: 0 0 16px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.pc-recharge-features li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 9px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #eef2f7;
  font-size: 13px;
}

.pc-recharge-feature-label {
  color: #64748b;
  font-weight: 500;
}

.pc-recharge-features strong {
  color: #1e293b;
  font-weight: 700;
  font-family: -apple-system, 'SF Pro Display', 'PingFang SC', sans-serif;
  font-size: 13px;
}

.pc-recharge-status-active {
  color: #16a34a !important;
}

.pc-recharge-btns {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pc-recharge-main,
.pc-recharge-sub {
  width: 100%;
  padding: 10px;
}

.pc-analytics-row {
  display: grid;
  grid-template-columns: 1.2fr 1.5fr 1fr;
  gap: 14px;
}

.pc-chart-card {
  padding: 18px 20px;
}

.pc-chart-dom {
  width: 100%;
  height: 200px;
}

.pc-pie-wrap {
  width: 100%;
}

.pc-expire-card,
.pc-invite-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.pc-expire-ico {
  margin: 4px 0;
}

.pc-expire-days {
  font-size: 26px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1.15;
  margin: 6px 0 4px;
  font-family: -apple-system, 'SF Pro Display', 'PingFang SC', sans-serif;
  letter-spacing: -0.01em;
}

.pc-expire-unit {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-left: 3px;
}

.pc-expire-date {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 16px;
}

.pc-expire-card .pc-btn {
  width: 100%;
  margin-top: auto;
}

.pc-gift-ico {
  margin: 4px 0 8px;
}

.pc-invite-text {
  font-size: 13px;
  color: #64748b;
  line-height: 1.7;
  margin: 0 0 16px 0;
}

.pc-invite-text strong {
  color: #1677ff;
  font-size: 16px;
}

.pc-invite-card .pc-btn {
  width: 100%;
  margin-top: auto;
}

.pc-compare-card {
  padding: 18px 20px;
  overflow: hidden;
}

.pc-compare-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}

.pc-compare-head .pc-card-title {
  margin: 0;
}

.pc-compare-refresh {
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.pc-compare-refresh:hover:not(:disabled) {
  background: #dbeafe;
  border-color: #93c5fd;
}

.pc-compare-refresh:disabled {
  color: #94a3b8;
  background: #f1f5f9;
  border-color: #e2e8f0;
  cursor: not-allowed;
}

.pc-compare-desc {
  margin: 0 0 14px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.pc-compare-table-wrap {
  overflow-x: auto;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.pc-compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  table-layout: fixed;
}

.pc-compare-table thead th {
  padding: 14px 12px;
  text-align: center;
  font-weight: 600;
  font-size: 13px;
  color: #475569;
  background: #f8fafc;
  border-bottom: 2px solid #e2e8f0;
  position: sticky;
  top: 0;
  z-index: 2;
  letter-spacing: 0.2px;
}

.pc-compare-table th:first-child {
  text-align: left;
  padding-left: 18px;
}

.pc-th-feature {
  width: 46%;
}

.pc-th-normal {
  width: 18%;
  color: #94a3b8 !important;
  font-weight: 600;
}

.pc-th-vip {
  width: 18%;
  color: #2563eb !important;
}

.pc-th-svip {
  width: 18%;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%) !important;
  color: #92400e !important;
  position: relative;
}

.pc-th-svip::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #f59e0b, #fbbf24, #f59e0b);
}

.pc-svip-crown {
  display: inline-flex;
  align-items: center;
  margin-right: 4px;
  vertical-align: middle;
}

.pc-svip-th-inner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.pc-svip-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  background: #d97706;
  color: #fff;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 4px;
  vertical-align: middle;
}

.pc-compare-table td {
  padding: 9px 12px;
  text-align: center;
  color: #64748b;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
  line-height: 1.4;
}

/* 分组分隔行：用整行 colspan 显示分类，将原本占两列的功能合并到一列 */
.pc-group-row td {
  background: linear-gradient(90deg, #f1f5f9 0%, #eef2f7 100%) !important;
  padding: 8px 18px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  border-bottom: 1px solid #e2e8f0;
  border-top: 1px solid #e2e8f0;
  letter-spacing: 0.3px;
}

.pc-group-row:first-child td {
  border-top: none;
}

.pc-feature-ico {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  font-size: 12px;
  line-height: 1;
  margin-right: 8px;
  vertical-align: middle;
  flex-shrink: 0;
}

.pc-group-label {
  vertical-align: middle;
}

.pc-group-count {
  margin-left: 8px;
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
  vertical-align: middle;
}

/* 功能行：斑马纹只作用于功能行，不影响分组行 */
.pc-feature-row-alt td {
  background: #fbfcfe;
}

.pc-compare-table tbody tr.pc-feature-row:last-child td {
  border-bottom: none;
}

.pc-compare-table tbody tr.pc-feature-row:hover td {
  background: #f5f8ff;
}

.pc-compare-table td:first-child {
  text-align: left;
  padding-left: 18px;
}

.pc-td-svip {
  background: linear-gradient(180deg, #fffdf5 0%, #fef9e7 100%) !important;
  color: #92400e !important;
  font-weight: 600;
}

.pc-feature-row:hover .pc-td-svip {
  background: linear-gradient(180deg, #fff7e0 0%, #fef3c7 100%) !important;
}

.pc-td-name {
  color: #334155 !important;
  font-weight: 500;
}

.pc-check-ico {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.pc-check-gold svg circle {
  fill: #fef3c7;
  stroke: #d97706;
}

.pc-check-gold svg path {
  stroke: #d97706;
}

.pc-dash {
  color: #cbd5e1;
  font-size: 14px;
  font-weight: 500;
}

/* 移除旧的文本标记样式，保留类名兼容性 */
.pc-mark-on, .pc-mark-off {
  font-weight: 500;
}

.pc-compare-note {
  margin-top: 12px;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}

.profile-page-header {
  margin-bottom: 16px;
}

.pph-breadcrumb {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 500;
}

.pph-breadcrumb-current {
  color: #3b82f6;
  font-weight: 600;
}

.profile-tabs-bar {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  padding: 0;
  background: transparent;
  border-radius: 0;
  width: 100%;
  border: none;
  box-shadow: none;
  border-bottom: 1px solid #e2e8f0;
}

.profile-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 0;
  margin-right: 32px;
  border-radius: 0;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.profile-tab:hover {
  color: #334155;
  background: transparent;
}

.profile-tab.active {
  background: transparent;
  color: #2563eb;
  box-shadow: none;
}

.profile-tab.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: #2563eb;
  border-radius: 1px;
}

.profile-tab-ico {
  display: none;
}

.profile-tab-ico svg {
  width: 0;
  height: 0;
}

.profile-main {
  min-width: 0;
}

.profile-overview-v2 {
  display: grid;
  gap: 16px;
}

.profile-footer {
  margin-top: 32px;
  padding: 20px 0 8px;
  border-top: 1px solid #f1f5f9;
}

.profile-footer-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.profile-footer-left {
  color: #64748b;
  font-weight: 500;
}

.profile-footer-right {
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
}

.pc-avatar-ring {
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  background: conic-gradient(from 0deg, #3b82f6, #60a5fa, #93c5fd, #3b82f6);
  animation: ring-spin 8s linear infinite;
  opacity: 0.6;
}

@keyframes ring-spin {
  to { transform: rotate(360deg); }
}

.pc-avatar-wrap {
  position: relative;
  width: 84px;
  height: 84px;
  flex-shrink: 0;
}

.pc-avatar {
  position: relative;
  z-index: 1;
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.15);
  border: 3px solid #fff;
  overflow: hidden;
}

.pc-avatar-img {
  width: 100%;
  height: 100%;
}

.pc-banner-right {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-shrink: 0;
}

.pc-banner-illust {
  width: 260px;
  height: 190px;
  filter: drop-shadow(0 8px 24px rgba(59, 130, 246, 0.12));
}

.pc-recharge-desc {
  margin: 0 0 8px;
  font-size: 12px;
  color: #94a3b8;
}

.pc-banner-shield {
  display: none;
}

@supports (background: conic-gradient(red, blue)) {
  .pc-avatar-ring {
    display: block;
  }
}

@supports not (background: conic-gradient(red, blue)) {
  .pc-avatar-ring {
    background: #3b82f6;
    opacity: 0.2;
  }
}

@media (max-width: 1200px) {
  .pc-analytics-row {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .pc-stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .pc-banner {
    flex-direction: column;
    align-items: flex-start;
    gap: 20px;
    min-height: auto;
    padding: 24px;
  }
  .pc-banner-right {
    width: 100%;
    justify-content: center;
  }
  .pc-banner-illust {
    width: 200px;
    height: 150px;
  }
  .pc-three-col {
    grid-template-columns: 1fr;
  }
  .pc-recharge-btns {
    width: 100%;
  }
  .pc-analytics-row {
    grid-template-columns: 1fr;
  }
  .profile-tabs-bar {
    width: 100%;
    overflow-x: auto;
  }
}

@media (max-width: 600px) {
  .pc-stats-row {
    grid-template-columns: 1fr;
  }
  .pc-username {
    font-size: 22px;
  }
  .profile-footer-inner {
    flex-direction: column;
    gap: 4px;
  }
  .profile-footer-sep {
    display: none;
  }
}

.profile-layout {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.profile-sidebar {
  position: sticky;
  top: 16px;
}

.profile-sidebar-card {
  background: #fff;
  border-radius: 18px;
  border: 1px solid rgba(229, 236, 247, 0.9);
  box-shadow: 0 8px 24px rgba(31, 53, 94, 0.05);
  padding: 8px;
}

.profile-side-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px 14px;
  border: none;
  border-radius: 14px;
  background: transparent;
  color: #50617d;
  font-size: 14px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
  margin-bottom: 2px;
}

.profile-side-item:last-child {
  margin-bottom: 0;
}

.profile-side-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 0;
  border-radius: 999px;
  background: linear-gradient(180deg, #7cb8ff 0%, #0d6bff 100%);
  transition: height 0.18s ease;
}

.profile-side-item:hover {
  background: rgba(13, 107, 255, 0.04);
  color: #0d6bff;
}

.profile-side-item.active {
  background: linear-gradient(135deg, #eef5ff 0%, #e0ecff 100%);
  color: #0d6bff;
  box-shadow: 0 6px 16px rgba(13, 107, 255, 0.12);
}

.profile-side-item.active::before {
  height: 24px;
}

.profile-side-ico {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #f1f5fb;
  color: #7b879d;
  flex: 0 0 auto;
  transition: all 0.18s ease;
}

.profile-side-item.active .profile-side-ico {
  background: linear-gradient(135deg, #5b7cff 0%, #0d6bff 100%);
  color: #fff;
  box-shadow: 0 4px 10px rgba(13, 107, 255, 0.25);
}

.profile-side-ico svg {
  width: 16px;
  height: 16px;
}

.profile-side-label {
  flex: 1 1 auto;
  min-width: 0;
}

.token-page {
  min-width: 0;
}

.tp-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.tp-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
  color: #17213d;
}

.tp-desc {
  margin: 0;
  font-size: 13px;
  color: #8a96ac;
}

.tp-refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 18px;
  border: 1px solid #e2e8f4;
  border-radius: 10px;
  background: #fff;
  color: #50617d;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tp-refresh-btn:hover {
  border-color: #0d6bff;
  color: #0d6bff;
  background: #f0f6ff;
}

.tp-stats-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.tp-stat-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 20px;
  overflow: hidden;
}

.tp-stat-today {
  background: linear-gradient(135deg, #fff0f0 0%, #fff5f5 50%, #ffffff 100%);
  border: 1px solid rgba(255, 107, 122, 0.15);
}

.tp-stat-week {
  background: linear-gradient(135deg, #fff8e6 0%, #fffaf0 50%, #ffffff 100%);
  border: 1px solid rgba(255, 180, 71, 0.18);
}

.tp-stat-balance {
  background: linear-gradient(135deg, #eef5ff 0%, #f3f7ff 50%, #ffffff 100%);
  border: 1px solid rgba(13, 107, 255, 0.15);
}

.tp-stat-ico {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  font-size: 20px;
  font-weight: 800;
  color: #fff;
  flex: 0 0 auto;
}

.tp-ico-today {
  background: linear-gradient(145deg, #ff7a8a 0%, #ff5252 100%);
  box-shadow: 0 8px 18px rgba(255, 82, 82, 0.25);
}

.tp-ico-week {
  background: linear-gradient(145deg, #ffc266 0%, #ff9f22 100%);
  box-shadow: 0 8px 18px rgba(255, 159, 34, 0.25);
}

.tp-ico-balance {
  background: linear-gradient(145deg, #5b7cff 0%, #0d6bff 100%);
  box-shadow: 0 8px 18px rgba(13, 107, 255, 0.25);
}

.tp-stat-content {
  flex: 1 1 auto;
  min-width: 0;
}

.tp-stat-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #8a96ac;
  margin-bottom: 4px;
}

.tp-label-blue {
  color: #0d6bff;
}

.tp-stat-num {
  display: block;
  font-size: 26px;
  font-weight: 800;
  line-height: 1.2;
  font-family: 'SF Mono', 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
  margin-bottom: 2px;
}

.tp-num-red {
  color: #e53935;
}

.tp-num-orange {
  color: #d97706;
}

.tp-num-blue {
  color: #0d6bff;
}

.tp-stat-sub {
  display: block;
  font-size: 11px;
  color: #a0aec0;
  font-weight: 500;
}

.tp-table-card {
  background: #fff;
  border-radius: 20px;
  border: 1px solid rgba(229, 236, 247, 0.9);
  box-shadow: 0 10px 28px rgba(31, 53, 94, 0.045);
  overflow: hidden;
}

.tp-table-wrap {
  max-height: 560px;
  overflow-x: auto;
  overflow-y: auto;
}

.tp-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.tp-table thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 14px 12px;
  background: #f7f9fc;
  color: #6b7a94;
  font-weight: 600;
  font-size: 12px;
  text-align: center;
  border-bottom: 1px solid #edf1f7;
  white-space: nowrap;
}

.tp-table thead th:first-child {
  text-align: left;
  padding-left: 20px;
}

.tp-table tbody td {
  padding: 13px 12px;
  color: #44536f;
  text-align: center;
  border-bottom: 1px solid #f3f5f9;
  font-size: 12px;
}

.tp-table tbody td:first-child {
  text-align: left;
  padding-left: 20px;
  color: #6b7a94;
  font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
  font-size: 11.5px;
}

.tp-table tbody tr:last-child td {
  border-bottom: none;
}

.tp-table tbody tr:nth-child(even) td {
  background: #fafbfd;
}

.tp-table tbody tr:hover td {
  background: #f0f6ff;
}

.td-type {
  width: 90px;
}

.td-source {
  color: #6b7a94;
}

.td-balance {
  font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
  font-weight: 600;
  color: #4a5568;
}

.td-remark {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #8a96ac;
  text-align: left;
  padding-right: 20px;
}

.tp-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
}

.tp-badge-red {
  background: rgba(255, 82, 82, 0.1);
  color: #e53935;
}

.tp-badge-green {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.tp-badge-orange {
  background: rgba(255, 159, 34, 0.12);
  color: #d97706;
}

.tp-badge-gray {
  background: #f1f5f9;
  color: #64748b;
}

.tp-amount-negative {
  color: #e53935 !important;
  font-weight: 600;
  font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
}

.tp-amount-positive {
  color: #16a34a !important;
  font-weight: 600;
  font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
}

.tp-amount-zero {
  color: #16a34a !important;
  font-weight: 600;
  font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
}

.tp-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-top: 1px solid #f1f5f9;
  background: #fff;
}

.tp-record-count {
  font-size: 12px;
  color: #8a96ac;
  font-weight: 500;
}

.tp-pager {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tp-page-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid #e2e8f4;
  border-radius: 8px;
  background: #fff;
  color: #50617d;
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 0;
}

.tp-page-btn:hover:not(:disabled) {
  border-color: #0d6bff;
  color: #0d6bff;
  background: #f0f6ff;
}

.tp-page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tp-page-nums {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tp-page-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #50617d;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tp-page-num:hover:not(:disabled):not(.active) {
  background: #f1f5f9;
}

.tp-page-num.active {
  background: #0d6bff;
  color: #fff;
  border-color: #0d6bff;
  box-shadow: 0 4px 10px rgba(13, 107, 255, 0.25);
}

.tp-page-ellipsis {
  color: #a0aec0;
  cursor: default;
}

.tp-page-ellipsis:hover {
  background: transparent !important;
}

.tp-page-size {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7a94;
  margin-left: 4px;
}

.tp-page-size select {
  height: 32px;
  padding: 0 24px 0 10px;
  border: 1px solid #e2e8f4;
  border-radius: 8px;
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7a94' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E") no-repeat right 8px center;
  background-size: 12px;
  color: #44536f;
  font-size: 12px;
  cursor: pointer;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}

.tp-page-size select:focus {
  border-color: #0d6bff;
}

.tp-page-jump {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7a94;
  margin-left: 4px;
}

.tp-page-jump input {
  width: 48px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid #e2e8f4;
  border-radius: 8px;
  text-align: center;
  font-size: 12px;
  color: #44536f;
  outline: none;
  -moz-appearance: textfield;
}

.tp-page-jump input::-webkit-outer-spin-button,
.tp-page-jump input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.tp-page-jump input:focus {
  border-color: #0d6bff;
}

.tp-jump-btn {
  height: 32px;
  padding: 0 14px;
  border: 1px solid #e2e8f4;
  border-radius: 8px;
  background: #fff;
  color: #50617d;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tp-jump-btn:hover {
  border-color: #0d6bff;
  color: #0d6bff;
  background: #f0f6ff;
}

@media (max-width: 1100px) {
  .profile-layout {
    grid-template-columns: 1fr;
  }
  .profile-sidebar {
    position: static;
  }
  .profile-sidebar-card {
    display: flex;
    gap: 4px;
    padding: 6px;
    overflow-x: auto;
  }
  .profile-side-item {
    flex: 0 0 auto;
    margin-bottom: 0;
    width: auto;
  }
  .profile-side-item::before {
    display: none;
  }
}

@media (max-width: 768px) {
  .tp-stats-row {
    grid-template-columns: 1fr;
  }
  .tp-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .tp-pagination {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  .tp-pager {
    width: 100%;
    flex-wrap: wrap;
  }
}

.token-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.td-banner-card {
  background: linear-gradient(135deg, #eff5ff 0%, #e0ecff 60%, #f0f7ff 100%);
  border: 1px solid #dbe7ff;
  border-radius: 14px;
  padding: 18px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.td-banner-card::before {
  content: '';
  position: absolute;
  top: -40%;
  right: -8%;
  width: 240px;
  height: 240px;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.06) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.td-banner-left {
  display: flex;
  align-items: center;
  gap: 14px;
  z-index: 1;
}

.td-banner-avatar {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.td-banner-avatar svg {
  display: block;
}

.td-banner-username-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.td-banner-username {
  font-size: 18px;
  font-weight: 600;
  color: #1D2129;
  letter-spacing: -0.01em;
}

.td-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.td-badge-svip {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #d97706;
}

.td-badge-connected {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.td-banner-desc {
  font-size: 13px;
  color: #4E5969;
  margin: 8px 0 0 0;
}

.td-banner-right {
  flex-shrink: 0;
  z-index: 1;
}

.td-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.td-stat-card {
  background: #fff;
  border: 1px solid #F2F3F5;
  border-radius: 12px;
  padding: 14px 16px;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}

.td-stat-card:hover {
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  border-color: #dbe3ee;
}

.td-stat-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.td-stat-ico {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.td-ico-balance {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
}

.td-ico-today {
  background: linear-gradient(135deg, #22c55e, #16a34a);
}

.td-ico-month {
  background: linear-gradient(135deg, #ef4444, #dc2626);
}

.td-ico-budget {
  background: linear-gradient(135deg, #f59e0b, #d97706);
}

.td-stat-label {
  font-size: 13px;
  color: #86909C;
  font-weight: 500;
}

.td-stat-value-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 6px;
}

.td-stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #1D2129;
  line-height: 1.2;
  letter-spacing: -0.01em;
}

.td-stat-num.td-num-big {
  font-size: 30px;
}

.td-stat-unit {
  font-size: 14px;
  color: #86909C;
  font-weight: 500;
}

.td-stat-yuan {
  font-size: 12px;
  color: #86909C;
  margin-bottom: 12px;
}

.td-recharge-btn {
  width: 100%;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #165DFF, #2563eb);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.18s ease;
}

.td-recharge-btn:hover {
  opacity: 0.9;
}

.td-stat-compare {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
}

.td-compare-down {
  color: #22c55e;
}

.td-compare-up {
  color: #ef4444;
}

.td-progress-bar {
  width: 100%;
  height: 8px;
  background: #E8F3FF;
  border-radius: 4px;
  overflow: hidden;
  margin: 8px 0 6px;
}

.td-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #165DFF, #3b82f6);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.td-budget-text {
  font-size: 12px;
  color: #86909C;
}

.td-budget-text strong {
  color: #165DFF;
  font-weight: 600;
}

.td-charts-row {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 16px;
}

.td-card {
  background: #fff;
  border: 1px solid #F2F3F5;
  border-radius: 12px;
  padding: 16px 18px;
}

.td-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.td-card-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.td-card-title {
  font-size: 15px;
  font-weight: 700;
  color: #1D2129;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.td-card-crown {
  color: #f59e0b;
}

.td-card-sub {
  font-size: 13px;
  color: #86909C;
  font-weight: 400;
}

.td-info-ico {
  color: #C9CDD4;
  cursor: help;
  display: flex;
  align-items: center;
}

.td-card-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.td-select {
  height: 32px;
  padding: 0 10px;
  border: 1px solid #E5E6EB;
  border-radius: 6px;
  font-size: 13px;
  color: #4E5969;
  background: #fff;
  cursor: pointer;
  outline: none;
}

.td-select:focus {
  border-color: #165DFF;
}

.td-seg-btns {
  display: flex;
  border: 1px solid #E5E6EB;
  border-radius: 6px;
  overflow: hidden;
}

.td-seg-btn {
  height: 30px;
  padding: 0 14px;
  border: none;
  background: #fff;
  font-size: 13px;
  color: #86909C;
  cursor: pointer;
  transition: all 0.2s;
}

.td-seg-btn.active {
  background: #165DFF;
  color: #fff;
}

.td-chart-area {
  width: 100%;
  height: 220px;
}

.td-trend-summary {
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-top: 10px;
  padding-top: 12px;
  border-top: 1px solid #F2F3F5;
}

.td-summary-item {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.td-summary-label {
  font-size: 12px;
  color: #86909C;
}

.td-summary-val {
  font-size: 18px;
  font-weight: 700;
  color: #1D2129;
  letter-spacing: -0.01em;
}

.td-summary-unit {
  font-size: 11px;
  color: #86909C;
}

.td-summary-date {
  font-size: 11px;
  color: #C9CDD4;
}

.td-summary-divider {
  width: 1px;
  height: 36px;
  background: #F2F3F5;
}

.td-pie-wrap {
  position: relative;
  width: 150px;
  height: 150px;
  margin: 0 auto 12px;
}

.td-pie-chart {
  width: 100%;
  height: 100%;
}

.td-pie-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.td-pie-center strong {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #1D2129;
  line-height: 1.2;
  letter-spacing: -0.01em;
}

.td-pie-center span {
  font-size: 11px;
  color: #86909C;
}

.td-pie-legend {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.td-legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.td-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.td-legend-name {
  color: #4E5969;
  flex: 1;
}

.td-legend-val {
  color: #1D2129;
  font-weight: 500;
}

.td-legend-pct {
  color: #86909C;
  width: 42px;
  text-align: right;
}

.td-link-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  padding: 8px;
  border: none;
  background: transparent;
  color: #165DFF;
  font-size: 13px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.td-link-btn:hover {
  opacity: 0.8;
}

.td-package-card {
  padding: 18px 20px;
}

.td-package-left {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.td-package-illu {
  flex-shrink: 0;
}

.td-package-info {
  flex: 1;
}

.td-package-title {
  font-size: 16px;
  font-weight: 700;
  color: #1D2129;
  margin: 0 0 4px 0;
  letter-spacing: -0.01em;
}

.td-package-desc {
  font-size: 13px;
  color: #86909C;
  margin: 0 0 12px 0;
}

.td-package-cta {
  height: 34px;
  padding: 0 20px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #165DFF, #2563eb);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.18s ease;
}

.td-package-cta:hover {
  opacity: 0.9;
}

.td-package-right {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 14px;
}

.td-pkg-empty {
  grid-column: 1 / -1;
  padding: 24px 16px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  border: 1px dashed #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.td-pkg-item {
  position: relative;
  border: 1px solid #E5E6EB;
  border-radius: 10px;
  padding: 16px 14px;
  text-align: center;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}

.td-pkg-item:hover {
  border-color: #165DFF;
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.08);
}

.td-pkg-item.recommend {
  border-color: #165DFF;
  background: linear-gradient(180deg, #f0f7ff 0%, #fff 30%);
}

.td-pkg-tag {
  position: absolute;
  top: -1px;
  right: 16px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 0 0 6px 6px;
}

.td-pkg-name {
  font-size: 14px;
  font-weight: 600;
  color: #1D2129;
  margin-bottom: 6px;
}

.td-pkg-amount {
  font-size: 20px;
  font-weight: 700;
  color: #1D2129;
  margin-bottom: 4px;
  letter-spacing: -0.01em;
}

.td-pkg-amount span {
  font-size: 12px;
  font-weight: 400;
  color: #86909C;
}

.td-pkg-price {
  margin-bottom: 4px;
}

.td-pkg-symbol {
  font-size: 13px;
  color: #165DFF;
  font-weight: 500;
}

.td-pkg-price-num {
  font-size: 28px;
  font-weight: 700;
  color: #165DFF;
  letter-spacing: -0.01em;
}

.td-pkg-unit-price {
  font-size: 11px;
  color: #86909C;
  margin-bottom: 12px;
}

.td-pkg-buy {
  width: 100%;
  height: 32px;
  border: 1px solid #165DFF;
  border-radius: 8px;
  background: #fff;
  color: #165DFF;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.18s ease;
}

.td-pkg-buy:hover {
  background: #f0f7ff;
}

.td-pkg-buy.primary {
  background: linear-gradient(135deg, #165DFF, #2563eb);
  color: #fff;
  border-color: transparent;
}

.td-pkg-buy.primary:hover {
  opacity: 0.9;
}

.td-package-note {
  text-align: center;
  font-size: 12px;
  color: #C9CDD4;
  margin: 16px 0 0 0;
}

.td-bottom-row {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 16px;
}

.td-right-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.td-table-wrap {
  overflow-x: auto;
}

.td-table {
  width: 100%;
  border-collapse: collapse;
}

.td-table th {
  text-align: left;
  padding: 9px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #86909C;
  background: #F7F8FA;
  border-bottom: 1px solid #F2F3F5;
  white-space: nowrap;
}

.td-table th:first-child {
  border-radius: 6px 0 0 6px;
}

.td-table th:last-child {
  border-radius: 0 6px 6px 0;
}

.td-table td {
  padding: 10px 12px;
  font-size: 13px;
  color: #4E5969;
  border-bottom: 1px solid #F7F8FA;
}

.td-table tbody tr:hover {
  background: #f9fbfd;
}

.td-date {
  white-space: nowrap;
  color: #86909C;
  font-size: 12px;
}

.td-type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: #E8F3FF;
  color: #165DFF;
}

.td-type-tag.green {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.td-type-tag.red {
  background: rgba(245, 63, 63, 0.1);
  color: #f53f3f;
}

.td-type-tag.orange {
  background: rgba(247, 126, 38, 0.1);
  color: #f77234;
}

.td-empty-cell {
  text-align: center;
  padding: 40px 0;
  color: #86909C;
  font-size: 13px;
}

.td-amount-cell {
  font-weight: 600;
  color: #F53F3F;
}

.td-status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.td-status-tag.success {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.td-remark-cell {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #86909C;
}

.td-table-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #F2F3F5;
}

.td-pager-left {
  display: flex;
  align-items: center;
  gap: 4px;
}

.td-pager-btn {
  width: 30px;
  height: 30px;
  border: 1px solid #E5E6EB;
  border-radius: 6px;
  background: #fff;
  color: #4E5969;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.18s ease, color 0.18s ease;
}

.td-pager-btn:hover:not(:disabled) {
  border-color: #165DFF;
  color: #165DFF;
}

.td-pager-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.td-pager-num {
  min-width: 30px;
  height: 30px;
  padding: 0 8px;
  border: 1px solid #E5E6EB;
  border-radius: 6px;
  background: #fff;
  color: #4E5969;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease;
}

.td-pager-num.active {
  background: #165DFF;
  border-color: #165DFF;
  color: #fff;
}

.td-pager-num:hover:not(.active) {
  border-color: #165DFF;
  color: #165DFF;
}

.td-pager-ellipsis {
  width: 20px;
  text-align: center;
  color: #C9CDD4;
  font-size: 13px;
}

.td-pager-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.td-pager-total {
  font-size: 13px;
  color: #86909C;
}

.td-pager-total strong {
  color: #1D2129;
  font-weight: 600;
}

.td-pager-size {
  height: 30px;
  padding: 0 8px;
  border: 1px solid #E5E6EB;
  border-radius: 6px;
  font-size: 13px;
  color: #4E5969;
  background: #fff;
  cursor: pointer;
  outline: none;
}

.td-rank-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.td-rank-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.td-rank-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  background: #F2F3F5;
  color: #86909C;
}

.td-rank-num.rank-1 {
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  color: #fff;
}

.td-rank-num.rank-2 {
  background: linear-gradient(135deg, #9ca3af, #6b7280);
  color: #fff;
}

.td-rank-num.rank-3 {
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
}

.td-rank-name {
  width: 60px;
  color: #4E5969;
  flex-shrink: 0;
}

.td-rank-bar-wrap {
  flex: 1;
  height: 6px;
  background: #F2F3F5;
  border-radius: 3px;
  overflow: hidden;
}

.td-rank-bar {
  height: 100%;
  background: linear-gradient(90deg, #165DFF, #3b82f6);
  border-radius: 3px;
}

.td-rank-val {
  color: #1D2129;
  font-weight: 500;
  width: 75px;
  text-align: right;
}

.td-rank-pct {
  color: #86909C;
  width: 35px;
  text-align: right;
}

.td-rank-more {
  margin-top: 0;
}

.td-advice-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.td-advice-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.td-advice-ico {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.td-advice-ico.info {
  background: #E8F3FF;
  color: #165DFF;
}

.td-advice-ico.check {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.td-advice-ico.warn {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.td-advice-content {
  flex: 1;
  min-width: 0;
}

.td-advice-title {
  font-size: 13px;
  font-weight: 600;
  color: #1D2129;
  margin-bottom: 3px;
}

.td-advice-desc {
  font-size: 11px;
  color: #86909C;
  line-height: 1.5;
}

.td-advice-action {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #165DFF;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 0;
  white-space: nowrap;
}

.td-advice-action:hover {
  text-decoration: underline;
}

@media (max-width: 1200px) {
  .td-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .td-charts-row {
    grid-template-columns: 1fr;
  }
  .td-bottom-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .td-banner-card {
    flex-direction: column;
    text-align: center;
    padding: 20px;
  }
  .td-banner-left {
    flex-direction: column;
  }
  .td-banner-right {
    display: none;
  }
  .td-stats-grid {
    grid-template-columns: 1fr;
  }
  .td-package-right {
    grid-template-columns: 1fr;
  }
  .td-package-left {
    flex-direction: column;
    text-align: center;
  }
  .td-trend-summary {
    flex-wrap: wrap;
    gap: 12px;
  }
  .td-summary-divider {
    display: none;
  }
  .td-card-actions {
    flex-direction: column;
    align-items: flex-end;
  }
}

/* 充值记录面板 */
.recharge-panel {
  padding: 24px;
}
.recharge-panel .panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}
.recharge-panel .panel-head h3 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
  color: #1D2129;
}
.recharge-panel .panel-head p {
  margin: 0;
  font-size: 13px;
  color: #86909C;
}
.recharge-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.recharge-summary-card {
  padding: 16px 18px;
  border-radius: 14px;
  background: linear-gradient(135deg, #f5f9ff 0%, #eaf2ff 100%);
  border: 1px solid #dbeafe;
}
.recharge-summary-label {
  font-size: 12px;
  color: #4E5969;
  margin-bottom: 6px;
}
.recharge-summary-value {
  font-size: 22px;
  font-weight: 700;
  color: #165DFF;
  line-height: 1.2;
}
.recharge-summary-sub {
  margin-top: 4px;
  font-size: 11px;
  color: #86909C;
}
.recharge-error {
  margin: 0 0 12px;
  padding: 8px 12px;
  background: #fff1f0;
  border: 1px solid #ffccc7;
  border-radius: 8px;
  color: #cf1322;
  font-size: 13px;
}
.recharge-table-wrap {
  overflow-x: auto;
  margin-bottom: 16px;
}
.recharge-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  background: #fff;
}
.recharge-table thead th {
  padding: 12px 14px;
  background: #f7f9fc;
  color: #4E5969;
  font-weight: 600;
  text-align: left;
  border-bottom: 1px solid #e5e6eb;
  white-space: nowrap;
}
.recharge-table tbody td {
  padding: 12px 14px;
  border-bottom: 1px solid #f2f3f5;
  color: #1D2129;
  vertical-align: middle;
}
.recharge-table tbody tr:hover {
  background: #fafbfc;
}
.recharge-date {
  white-space: nowrap;
  color: #4E5969;
}
.recharge-order {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  color: #4E5969;
}
.recharge-amount-cell {
  font-weight: 700;
  color: #00b42a;
}
.recharge-source-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  background: #e8f3ff;
  color: #165DFF;
  font-size: 12px;
  white-space: nowrap;
}
.recharge-remark-cell {
  max-width: 220px;
  color: #86909C;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recharge-empty-cell,
.recharge-loading-cell {
  text-align: center;
  padding: 28px 0 !important;
  color: #86909C;
  font-size: 13px;
}
.recharge-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.recharge-pager-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.recharge-pager-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e6eb;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  color: #4E5969;
  transition: all 0.2s;
}
.recharge-pager-btn:hover:not(:disabled) {
  border-color: #165DFF;
  color: #165DFF;
}
.recharge-pager-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.recharge-pager-num {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e6eb;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  color: #4E5969;
  font-size: 13px;
  transition: all 0.2s;
}
.recharge-pager-num:hover {
  border-color: #165DFF;
  color: #165DFF;
}
.recharge-pager-num.active {
  background: #165DFF;
  border-color: #165DFF;
  color: #fff;
}
.recharge-pager-right {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #86909C;
}
.recharge-pager-total strong {
  color: #1D2129;
  margin: 0 2px;
}
.recharge-pager-size {
  height: 32px;
  padding: 0 8px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  color: #4E5969;
  cursor: pointer;
}
@media (max-width: 768px) {
  .recharge-summary-grid {
    grid-template-columns: 1fr;
  }
  .recharge-panel {
    padding: 16px;
  }
  .recharge-pager {
    flex-direction: column;
    align-items: stretch;
  }
  .recharge-pager-left {
    justify-content: center;
    flex-wrap: wrap;
  }
}
</style>
