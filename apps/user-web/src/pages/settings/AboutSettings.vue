<template>
  <div class="about-page">
    <CardPanel class="about-shell">
      <div class="about-content">
        <section class="hero-card">
          <div class="hero-visual">
            <img :src="heroImage" alt="" aria-hidden="true" />
          </div>
          <div class="hero-brand">
            <div class="brand-mark">
              <span></span>
              <span></span>
            </div>
            <div class="hero-text">
              <div class="hero-title-row">
                <h1>XianYuAssistant 闲鱼助手</h1>
                <Badge>v{{ APP_VERSION }}</Badge>
                <Badge type="blue">当前构建</Badge>
              </div>
              <p>让闲鱼生意更简单，智能化运营平台</p>
              <div class="hero-meta">
                <span class="hero-meta-item"><i class="dot dot-green"></i>前端页面已加载</span>
                <span class="hero-meta-divider"></span>
                <span class="hero-meta-item">构建于 Vue 3 + Vite</span>
                <span class="hero-meta-divider"></span>
                <span class="hero-meta-item">{{ releaseLabel }}</span>
              </div>
            </div>
          </div>
        </section>

        <div class="metric-row">
          <div class="metric-tile metric-tile-blue">
            <div class="metric-icon">
              <Icon name="aboutVersion" />
            </div>
            <div class="metric-info">
              <span class="metric-label">当前版本</span>
              <b class="metric-value">v{{ APP_VERSION }}</b>
            </div>
          </div>
          <div class="metric-tile metric-tile-green">
            <div class="metric-icon">
              <Icon name="aboutStatus" />
            </div>
            <div class="metric-info">
              <span class="metric-label">页面状态</span>
              <b class="metric-value metric-value-green">已加载</b>
            </div>
          </div>
          <div class="metric-tile metric-tile-purple">
            <div class="metric-icon">
              <Icon name="aboutUpdate" />
            </div>
            <div class="metric-info">
              <span class="metric-label">最后更新</span>
              <b class="metric-value">{{ buildDateText }}</b>
            </div>
          </div>
        </div>

        <div class="main-grid">
          <CardPanel title="更新日志" desc="版本迭代与功能演进记录">
            <div class="changelog">
              <div
                v-for="(log, idx) in releaseNotes"
                :key="log.version"
                :class="['log-item', `log-${log.type}`]"
              >
                <div class="log-rail">
                  <span class="log-dot"></span>
                  <span v-if="idx < releaseNotes.length - 1" class="log-line"></span>
                </div>
                <div class="log-body">
                  <div class="log-head">
                    <span class="log-ver">v{{ log.version }}</span>
                    <span :class="['log-type', `log-type-${log.type}`]">
                      {{ typeMeta[log.type].label }}
                    </span>
                    <span class="log-date">{{ log.date }}</span>
                  </div>
                  <h4 class="log-title">{{ log.title }}</h4>
                  <p class="log-desc">{{ log.summary }}</p>
                  <div v-for="group in log.changes" :key="group.label" class="log-change-group">
                    <span class="log-change-label">{{ group.label }}</span>
                    <ul class="log-change-list">
                      <li v-for="item in group.items" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-if="log.remark" class="log-remark">{{ log.remark }}</div>
                </div>
              </div>
            </div>
          </CardPanel>

          <div class="side-stack">
            <CardPanel title="服务支持" desc="仅展示部署方已配置并可核验的支持渠道">
              <div v-if="supports.length" class="support-grid">
                <button v-for="support in supports" :key="support.label" class="support-card" type="button" @click="onSupport(support)">
                  <span class="support-icon" :class="support.tone">
                    <Icon :name="support.icon" />
                  </span>
                  <div class="support-text">
                    <b>{{ support.label }}</b>
                    <p>{{ support.desc }}</p>
                  </div>
                </button>
              </div>
              <div v-else class="about-unavailable" role="status">
                支持渠道尚未由部署方配置，请联系实际部署与运营主体。
              </div>
            </CardPanel>

            <CardPanel title="相关链接" desc="协议、隐私与系统工具" style="margin-top: 16px">
              <div class="link-list">
                <button
                  v-for="link in links"
                  :key="link.label"
                  class="link-row"
                  type="button"
                  :disabled="link.disabled"
                  :title="link.reason || ''"
                  @click="link.action"
                >
                  <span class="link-label">
                    <Icon :name="link.icon" />
                    {{ link.label }}
                  </span>
                  <span class="link-action">{{ link.actionText }} <span class="link-arrow">›</span></span>
                </button>
              </div>
              <div v-if="legalLinksMissing" class="about-unavailable" role="status">
                协议链接尚未配置；部署方需设置 VITE_TERMS_URL 与 VITE_PRIVACY_URL。
              </div>
            </CardPanel>
          </div>
        </div>
      </div>
    </CardPanel>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import CardPanel from '../../components/CardPanel.vue'
import Badge from '../../components/Badge.vue'
import Icon from '../../components/Icon.vue'
import { APP_BUILD_DATE, APP_VERSION, formatBuildDate, formatReleaseLabel } from '../../utils/appMeta.js'
import { getLegalDocumentUrl, LEGAL_CONFIG } from '../../utils/legalConfig.js'
import { releaseNotes as staticReleaseNotes, RELEASE_TYPE_META } from '../../data/releaseNotes.js'

const heroImage = '/xya/illustrations/about-hero.svg'
const buildDateText = formatBuildDate(APP_BUILD_DATE)
const releaseLabel = formatReleaseLabel(APP_BUILD_DATE)

// 更新日志优先走后端实时接口（与 AI 客服共用同一数据源），失败时回退到内置静态数据
const releaseNotes = ref(staticReleaseNotes)

defineProps({ active: String })

const typeMeta = RELEASE_TYPE_META

const supports = []

const legalLinksMissing = computed(() => !LEGAL_CONFIG.termsUrl || !LEGAL_CONFIG.privacyUrl)
const links = computed(() => [
  buildLegalLink('terms', '用户协议', 'aboutShield'),
  buildLegalLink('privacy', '隐私政策', 'aboutEye'),
  {
    label: '检查更新',
    icon: 'refresh',
    actionText: '未接入',
    disabled: true,
    reason: '版本检查服务尚未配置',
    action: () => {},
  },
  { label: '导出诊断日志', icon: 'download', actionText: '导出', disabled: false, reason: '', action: exportDiagnostics }
])

onMounted(async () => {
  try {
    const resp = await fetch('/api/content/release-notes', {
      headers: { Accept: 'application/json' },
    })
    if (!resp.ok) return
    const payload = await resp.json()
    const notes = payload?.data?.releaseNotes
    if (Array.isArray(notes) && notes.length > 0) {
      releaseNotes.value = notes
    }
  } catch (e) {
    // 接口不可用时保留内置静态数据
  }
})

function onSupport(item) {
  item.action?.()
}

function toast(message) {
  window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message } }))
}

function buildLegalLink(type, label, icon) {
  const url = getLegalDocumentUrl(type)
  return {
    label,
    icon,
    actionText: url ? '查看' : '未配置',
    disabled: !url,
    reason: url ? '' : `${label}链接尚未配置`,
    action: () => openLegalDoc(type, label),
  }
}

function openLegalDoc(type, title) {
  const url = getLegalDocumentUrl(type)
  if (!url) {
    toast(`${title}链接尚未配置`)
    return
  }
  const openedWindow = window.open(url, '_blank', 'noopener,noreferrer')
  if (!openedWindow) {
    toast(`${title} 打开失败，请检查浏览器弹窗权限`)
    return
  }
  toast(`已打开${title}`)
}

function exportDiagnostics() {
  const payload = {
    version: APP_VERSION,
    buildDate: APP_BUILD_DATE,
    route: location.hash || location.pathname,
    userAgent: navigator.userAgent,
    exportedAt: new Date().toISOString()
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `xya-diagnostics-${Date.now()}.json`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
  toast('诊断日志已导出')
}
</script>

<style scoped>
.about-page { width: 100%; }
.about-shell {
  padding: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at 0% 0%, rgba(37, 99, 235, 0.08), transparent 36%),
    radial-gradient(circle at 100% 0%, rgba(139, 92, 246, 0.08), transparent 34%),
    rgba(255, 255, 255, 0.98);
}
.about-content { padding: 18px; }
.about-unavailable {
  padding: 14px 16px;
  border: 1px dashed #d8e1ee;
  border-radius: 12px;
  background: #f8fafc;
  color: #65748b;
  font-size: 13px;
  line-height: 1.6;
}
.hero-card {
  position: relative;
  overflow: hidden;
  border-radius: 22px;
  min-height: 164px;
  padding: 24px 28px 22px;
  background: linear-gradient(90deg, rgba(241, 246, 255, 0.98), rgba(246, 239, 255, 0.88));
  border: 1px solid rgba(220, 232, 248, 0.95);
  box-shadow: 0 18px 42px rgba(31, 53, 94, 0.08);
}
.hero-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent 45%);
  pointer-events: none;
}
.hero-visual {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 12px 0 0;
  pointer-events: none;
  z-index: 0;
}
.hero-visual img {
  width: min(100%, 1180px);
  height: auto;
  display: block;
  object-fit: contain;
  object-position: center right;
  opacity: 0.95;
}
.hero-brand {
  position: relative;
  display: flex;
  align-items: center;
  gap: 18px;
  z-index: 1;
  max-width: 560px;
}
.brand-mark { width: 76px; height: 76px; position: relative; flex-shrink: 0; }
.brand-mark span {
  position: absolute;
  left: 31px;
  top: 0;
  width: 22px;
  height: 76px;
  border-radius: 14px;
  background: linear-gradient(180deg, #0d7fff, #16b7ff);
  transform: rotate(42deg);
  box-shadow: 0 8px 22px rgba(13, 107, 255, 0.32);
}
.brand-mark span + span { transform: rotate(-42deg); background: linear-gradient(180deg, #25a5ff, #0362f4); }
.hero-text { min-width: 0; }
.hero-title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.hero-title-row h1 { margin: 0; font-size: 24px; line-height: 1.15; font-weight: 900; color: #13213d; }
.hero-text p { margin: 8px 0 0; font-size: 13px; color: #65748b; }
.hero-meta { display: flex; align-items: center; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
.hero-meta-item { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; color: #7a879e; font-weight: 600; }
.hero-meta-divider { width: 1px; height: 10px; background: #d8e0ec; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-green { background: #22c55e; box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18); }
.metric-row { margin-top: 16px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.metric-tile {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(231, 237, 247, 0.95);
  box-shadow: 0 10px 26px rgba(31, 53, 94, 0.06);
}
.metric-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.metric-tile-blue .metric-icon { background: #eef4ff; color: #2563eb; }
.metric-tile-green .metric-icon { background: #ecfdf3; color: #16a34a; }
.metric-tile-purple .metric-icon { background: #f4efff; color: #8b5cf6; }
.metric-icon :deep(.ui-icon), .metric-icon :deep(.ui-icon-img) { width: 20px; height: 20px; }
.metric-info { display: flex; flex-direction: column; gap: 2px; }
.metric-label { font-size: 11px; color: #7a879e; font-weight: 600; }
.metric-value { font-size: 20px; font-weight: 900; color: #13213d; }
.metric-value-green { color: #16a34a; }
.main-grid { margin-top: 16px; display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 16px; align-items: start; }
.side-stack { min-width: 0; }
.changelog { display: flex; flex-direction: column; gap: 4px; }
.log-item { display: flex; gap: 14px; padding: 8px 0; }
.log-rail { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; padding-top: 4px; }
.log-dot { width: 12px; height: 12px; border-radius: 50%; background: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18); }
.log-major .log-dot { background: #ea580c; box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.18); }
.log-minor .log-dot { background: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18); }
.log-patch .log-dot { background: #16a34a; box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.18); }
.log-line { flex: 1; width: 2px; background: #e2e8f3; margin-top: 4px; min-height: 18px; }
.log-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.log-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.log-ver { font-size: 12px; font-weight: 800; padding: 3px 10px; border-radius: 999px; background: #eef4ff; color: #2563eb; }
.log-major .log-ver { background: #fff0e6; color: #ea580c; }
.log-minor .log-ver { background: #eef4ff; color: #2563eb; }
.log-patch .log-ver { background: #ecfdf3; color: #16a34a; }
.log-type { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px; }
.log-type-major { background: #fff0e6; color: #ea580c; border: 1px solid #ffd9b8; }
.log-type-minor { background: #eef4ff; color: #2563eb; border: 1px solid #cfdefc; }
.log-type-patch { background: #ecfdf3; color: #16a34a; border: 1px solid #c2f0d2; }
.log-date { font-size: 11px; color: #99a4b4; font-weight: 600; }
.log-title { margin: 0; font-size: 15px; font-weight: 800; color: #13213d; }
.log-desc { margin: 0; font-size: 13px; color: #3a4a63; line-height: 1.72; }
.log-change-group { display: flex; flex-direction: column; gap: 6px; margin-top: 2px; }
.log-change-label {
  align-self: flex-start;
  font-size: 11px;
  font-weight: 700;
  color: #2563eb;
  padding: 2px 8px;
  border-radius: 5px;
  background: #eef4ff;
}
.log-change-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.log-change-list li {
  position: relative;
  padding-left: 14px;
  font-size: 13px;
  line-height: 1.72;
  color: #3a4a63;
}
.log-change-list li::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 10px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #94a3b8;
}
.log-remark {
  font-size: 12px;
  color: #65748b;
  line-height: 1.6;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px dashed #d8e1ee;
}
.support-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.support-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(231, 237, 247, 0.95);
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.support-card:hover {
  transform: translateY(-2px);
  border-color: #bcd2ff;
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.1);
}
.support-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.support-icon.blue { background: linear-gradient(135deg, #e8f0ff, #d6e6ff); color: #2563eb; }
.support-icon.green { background: linear-gradient(135deg, #e6f7ee, #d2f1e2); color: #16a34a; }
.support-icon.orange { background: linear-gradient(135deg, #fff1e0, #ffe5c2); color: #ea8a00; }
.support-icon.violet { background: linear-gradient(135deg, #f1e8ff, #e6d6ff); color: #7c3aed; }
.support-icon :deep(.ui-icon), .support-icon :deep(.ui-icon-img) { width: 18px; height: 18px; }
.support-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.support-text b { font-size: 13px; color: #13213d; }
.support-text p { margin: 0; font-size: 11px; color: #7a879e; line-height: 1.45; }
.link-list { display: flex; flex-direction: column; }
.link-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 8px;
  border: 0;
  border-bottom: 1px solid #eef2f8;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.2s ease;
}
.link-row:last-child { border-bottom: 0; }
.link-row:hover { background: #f6faff; }
.link-row:disabled {
  cursor: not-allowed;
  color: #94a3b8;
  background: #fafbfc;
}
.link-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #13213d;
  font-weight: 600;
}
.link-label :deep(.ui-icon), .link-label :deep(.ui-icon-img) { width: 18px; height: 18px; }
.link-action { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: #6b7a90; white-space: nowrap; }
.link-arrow { font-size: 16px; color: #b3bccd; }
@media (max-width: 1260px) {
  .main-grid { grid-template-columns: 1fr; }
  .support-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 920px) {
  .metric-row,
  .support-grid { grid-template-columns: 1fr; }
  .hero-card { min-height: 0; }
  .hero-visual { opacity: 0.32; }
  .hero-brand { max-width: none; align-items: flex-start; }
}
@media (max-width: 560px) {
  .about-content { padding: 12px; }
  .hero-card { padding: 18px; border-radius: 18px; }
  .hero-brand { gap: 12px; min-width: 0; }
  .brand-mark { width: 52px; height: 52px; }
  .brand-mark span {
    left: 21px;
    width: 15px;
    height: 52px;
    border-radius: 10px;
  }
  .hero-text { flex: 1; min-width: 0; }
  .hero-title-row { gap: 6px; }
  .hero-title-row h1 {
    flex: 1 1 100%;
    min-width: 0;
    max-width: 100%;
    font-size: 20px;
    line-height: 1.25;
    overflow-wrap: anywhere;
  }
  .hero-meta { gap: 8px; margin-top: 10px; }
  .hero-meta-divider { display: none; }
}
</style>
