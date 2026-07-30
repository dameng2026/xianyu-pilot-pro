<template>
  <div class="admin-page">
    <ElCard shadow="never" class="hero-card">
      <div class="page-title-row">
        <div>
          <h2>开源版关于页</h2>
          <p>
            维护开源版前台“关于 / 设置说明”页的动态内容。保存后，开源版后端会通过 bridge
            读取该配置，而不是直接访问商业版数据库。
          </p>
        </div>
        <div class="toolbar-actions">
          <ElButton :disabled="loading || saving" @click="loadContent">重新加载</ElButton>
          <ElButton
            type="primary"
            :loading="saving"
            :disabled="configState !== 'ready'"
            @click="handleSave"
          >保存关于页内容</ElButton>
        </div>
      </div>

      <div v-if="configState === 'ready'" class="summary-grid">
        <div class="summary-card">
          <strong>{{ logsCount }}</strong>
          <span>更新日志条目</span>
        </div>
        <div class="summary-card">
          <strong>{{ supportsCount }}</strong>
          <span>支持入口数</span>
        </div>
        <div class="summary-card">
          <strong>{{ communityCardsCount }}</strong>
          <span>社区卡片数</span>
        </div>
        <div class="summary-card">
          <strong>{{ linksCount }}</strong>
          <span>底部快捷链接数</span>
        </div>
      </div>

      <ElAlert
        type="info"
        :closable="false"
        title="建议"
        description="这页仍保留结构化 JSON 编辑能力；下面新增的联系方式、微信群二维码、QQ群聊二维码、微信客服二维码和赞助码会在保存时自动合并回 communityCards，确保 bridge 数据结构与开源版前台保持一致。"
      />
    </ElCard>

    <AdminDataState
      v-if="configState === 'loading'"
      state="loading"
      title="正在加载开源版关于页配置"
      :retryable="false"
    />
    <AdminDataState
      v-else-if="configState === 'error'"
      state="error"
      title="开源版关于页配置暂时不可用"
      description="无法确认线上内容，表单、图片导入和保存已暂停，避免默认值覆盖真实配置。"
      @retry="loadContent"
    />

    <ElAlert
      v-if="configState === 'ready' && configurationWarning"
      class="configuration-warning"
      type="warning"
      :closable="false"
      show-icon
      title="部分历史配置已安全降级"
      :description="configurationWarning"
    />

    <div v-if="configState === 'ready'" class="page-grid">
      <div class="page-main">
        <ElCard shadow="never" class="section-card">
          <template #header>
            <div class="card-head">
              <div>
                <h3>基础文案</h3>
                <span>控制 about 页顶部主标题、徽标文案和运行状态文案</span>
              </div>
            </div>
          </template>

          <ElForm
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="110px"
            label-position="right"
            v-loading="loading"
          >
            <ElFormItem label="主标题" prop="heroTitle">
              <ElInput v-model="form.heroTitle" maxlength="80" show-word-limit />
            </ElFormItem>
            <ElFormItem label="徽标文案" prop="heroBadgeText">
              <ElInput v-model="form.heroBadgeText" maxlength="40" show-word-limit />
            </ElFormItem>
            <ElFormItem label="主描述" prop="heroDescription">
              <ElInput
                v-model="form.heroDescription"
                type="textarea"
                :rows="3"
                maxlength="200"
                show-word-limit
              />
            </ElFormItem>
            <ElFormItem label="服务状态" prop="serviceStatusText">
              <ElInput v-model="form.serviceStatusText" maxlength="40" show-word-limit />
            </ElFormItem>
          </ElForm>
        </ElCard>

        <ElCard shadow="never" class="section-card">
          <template #header>
            <div class="card-head">
              <div>
                <h3>法律与联系信息</h3>
                <span>控制用户协议、隐私政策和默认支持邮箱</span>
              </div>
            </div>
          </template>

          <div class="field-grid">
            <div class="field-block">
              <label>用户协议 URL</label>
              <ElInput v-model="form.termsUrl" placeholder="https://example.com/terms" />
            </div>
            <div class="field-block">
              <label>隐私政策 URL</label>
              <ElInput v-model="form.privacyUrl" placeholder="https://example.com/privacy" />
            </div>
            <div class="field-block field-block-full">
              <label>支持邮箱</label>
              <ElInput v-model="form.supportEmail" placeholder="support@example.com" />
            </div>
          </div>
        </ElCard>

        <ElCard shadow="never" class="section-card">
          <template #header>
            <div class="card-head">
              <div>
                <h3>社区卡片快捷配置</h3>
                <span>直接维护联系方式、微信群二维码、QQ群聊二维码、微信客服二维码与赞助码，并自动同步到 communityCards</span>
              </div>
            </div>
          </template>

          <div class="field-grid">
            <div class="field-block field-block-full">
              <label>联系方式</label>
              <ElInput
                v-model="form.contactValue"
                placeholder="填写微信号、QQ、邮箱、Telegram 或其他可复制的联系方式"
              />
              <span class="field-tip">开源版前台会将这项作为“联系方式”卡片内容，并支持一键复制。</span>
            </div>

            <div class="field-block field-block-full">
              <label>联系方式提示</label>
              <ElInput
                v-model="form.contactHint"
                placeholder="例如：工作日 09:00 - 18:00，添加时请备注来源"
              />
            </div>

            <div class="field-block field-block-full">
              <label>微信群二维码</label>
              <div class="media-editor">
                <div class="media-preview" :class="{ 'is-empty': !form.wechatGroupImageUrl }">
                  <img
                    v-if="form.wechatGroupImageUrl"
                    :src="resolveImage(form.wechatGroupImageUrl)"
                    alt="微信群二维码"
                  />
                  <Upload v-else class="media-placeholder-icon" />
                </div>
                <div class="media-actions">
                  <div class="media-toolbar">
                    <ElUpload
                      accept="image/png,image/jpeg"
                      :show-file-list="false"
                      :before-upload="beforeImageUpload"
                      :http-request="options => handleManagedImageUpload('group', options)"
                    >
                      <ElButton :icon="Upload" :loading="imageUploadingKey === 'group'">上传二维码</ElButton>
                    </ElUpload>
                    <ElButton
                      link
                      type="danger"
                      :disabled="!form.wechatGroupImageUrl"
                      @click="clearManagedImage('group')"
                    >
                      清空图片
                    </ElButton>
                  </div>
                  <div class="media-url-row">
                    <ElInput
                      v-model="imageUrlImportMap.group"
                      placeholder="https://example.com/group-qrcode.png"
                    />
                    <ElButton :loading="imageImportingKey === 'group'" @click="handleManagedImportFromUrl('group')">
                      从 URL 导入
                    </ElButton>
                  </div>
                  <ElInput v-model="form.wechatGroupHint" placeholder="例如：扫码加入微信群" />
                  <span class="field-tip">
                    保存后会覆盖 communityCards 中匹配“微信群 / 微信交流群 / wechat”的卡片。
                  </span>
                </div>
              </div>
            </div>

            <div class="field-block field-block-full">
              <label>QQ群聊二维码</label>
              <div class="media-editor">
                <div class="media-preview" :class="{ 'is-empty': !form.qqGroupImageUrl }">
                  <img
                    v-if="form.qqGroupImageUrl"
                    :src="resolveImage(form.qqGroupImageUrl)"
                    alt="QQ群聊二维码"
                  />
                  <Upload v-else class="media-placeholder-icon" />
                </div>
                <div class="media-actions">
                  <div class="media-toolbar">
                    <ElUpload
                      accept="image/png,image/jpeg"
                      :show-file-list="false"
                      :before-upload="beforeImageUpload"
                      :http-request="options => handleManagedImageUpload('qqGroup', options)"
                    >
                      <ElButton :icon="Upload" :loading="imageUploadingKey === 'qqGroup'">上传二维码</ElButton>
                    </ElUpload>
                    <ElButton
                      link
                      type="danger"
                      :disabled="!form.qqGroupImageUrl"
                      @click="clearManagedImage('qqGroup')"
                    >
                      清空图片
                    </ElButton>
                  </div>
                  <div class="media-url-row">
                    <ElInput
                      v-model="imageUrlImportMap.qqGroup"
                      placeholder="https://example.com/qq-group-qrcode.png"
                    />
                    <ElButton :loading="imageImportingKey === 'qqGroup'" @click="handleManagedImportFromUrl('qqGroup')">
                      从 URL 导入
                    </ElButton>
                  </div>
                  <ElInput v-model="form.qqGroupHint" placeholder="例如：扫码加入QQ群" />
                  <span class="field-tip">
                    保存后会覆盖 communityCards 中匹配“QQ / qq群”的卡片。
                  </span>
                </div>
              </div>
            </div>

            <div class="field-block field-block-full">
              <label>微信客服二维码</label>
              <div class="media-editor">
                <div class="media-preview" :class="{ 'is-empty': !form.wechatKefuImageUrl }">
                  <img
                    v-if="form.wechatKefuImageUrl"
                    :src="resolveImage(form.wechatKefuImageUrl)"
                    alt="微信客服二维码"
                  />
                  <Upload v-else class="media-placeholder-icon" />
                </div>
                <div class="media-actions">
                  <div class="media-toolbar">
                    <ElUpload
                      accept="image/png,image/jpeg"
                      :show-file-list="false"
                      :before-upload="beforeImageUpload"
                      :http-request="options => handleManagedImageUpload('wechatKefu', options)"
                    >
                      <ElButton :icon="Upload" :loading="imageUploadingKey === 'wechatKefu'">上传二维码</ElButton>
                    </ElUpload>
                    <ElButton
                      link
                      type="danger"
                      :disabled="!form.wechatKefuImageUrl"
                      @click="clearManagedImage('wechatKefu')"
                    >
                      清空图片
                    </ElButton>
                  </div>
                  <div class="media-url-row">
                    <ElInput
                      v-model="imageUrlImportMap.wechatKefu"
                      placeholder="https://example.com/wechat-kefu-qrcode.png"
                    />
                    <ElButton :loading="imageImportingKey === 'wechatKefu'" @click="handleManagedImportFromUrl('wechatKefu')">
                      从 URL 导入
                    </ElButton>
                  </div>
                  <ElInput v-model="form.wechatKefuHint" placeholder="例如：扫码添加微信客服" />
                  <span class="field-tip">
                    保存后会覆盖 communityCards 中匹配“微信客服 / 客服二维码”的卡片。
                  </span>
                </div>
              </div>
            </div>

            <div class="field-block field-block-full">
              <label>赞助码</label>
              <div class="media-editor">
                <div class="media-preview" :class="{ 'is-empty': !form.sponsorImageUrl }">
                  <img
                    v-if="form.sponsorImageUrl"
                    :src="resolveImage(form.sponsorImageUrl)"
                    alt="赞助码"
                  />
                  <Upload v-else class="media-placeholder-icon" />
                </div>
                <div class="media-actions">
                  <div class="media-toolbar">
                    <ElUpload
                      accept="image/png,image/jpeg"
                      :show-file-list="false"
                      :before-upload="beforeImageUpload"
                      :http-request="options => handleManagedImageUpload('sponsor', options)"
                    >
                      <ElButton :icon="Upload" :loading="imageUploadingKey === 'sponsor'">上传赞助码</ElButton>
                    </ElUpload>
                    <ElButton
                      link
                      type="danger"
                      :disabled="!form.sponsorImageUrl"
                      @click="clearManagedImage('sponsor')"
                    >
                      清空图片
                    </ElButton>
                  </div>
                  <div class="media-url-row">
                    <ElInput
                      v-model="imageUrlImportMap.sponsor"
                      placeholder="https://example.com/sponsor-qrcode.png"
                    />
                    <ElButton
                      :loading="imageImportingKey === 'sponsor'"
                      @click="handleManagedImportFromUrl('sponsor')"
                    >
                      从 URL 导入
                    </ElButton>
                  </div>
                  <ElInput v-model="form.sponsorHint" placeholder="例如：扫码赞助项目维护" />
                  <span class="field-tip">保存后会覆盖 communityCards 中匹配“赞助 / sponsor”的卡片。</span>
                </div>
              </div>
            </div>
          </div>
        </ElCard>
      </div>

      <div class="page-side">
        <ElCard shadow="never" class="section-card">
          <template #header>
            <div class="card-head">
              <div>
                <h3>结构化数组</h3>
                <span>JSON 必须保持数组格式，字段名需与开源版前台模型一致</span>
              </div>
            </div>
          </template>

          <div class="json-group">
            <div class="json-block">
              <div class="json-head">
                <strong>logs</strong>
                <span>更新日志与桥接说明</span>
              </div>
              <ElInput v-model="form.logsJson" type="textarea" :rows="12" class="mono-input" />
            </div>

            <div class="json-block">
              <div class="json-head">
                <strong>supports</strong>
                <span>官方网站 / 后台 / 客服 / 反馈等入口</span>
              </div>
              <ElInput v-model="form.supportsJson" type="textarea" :rows="10" class="mono-input" />
            </div>

            <div class="json-block">
              <div class="json-head">
                <strong>communityCards</strong>
                <span>交流群、赞助码、联系方式等卡片</span>
              </div>
              <ElInput v-model="form.communityCardsJson" type="textarea" :rows="12" class="mono-input" />
            </div>

            <div class="json-block">
              <div class="json-head">
                <strong>links</strong>
                <span>底部快捷操作与跳转项</span>
              </div>
              <ElInput v-model="form.linksJson" type="textarea" :rows="8" class="mono-input" />
            </div>
          </div>
        </ElCard>

        <ElCard shadow="never" class="section-card">
          <template #header>
            <div class="card-head">
              <div>
                <h3>保存预检查</h3>
                <span>帮助运营快速确认结构是否可用</span>
              </div>
            </div>
          </template>

          <div class="check-list">
            <div class="check-row">
              <span>主标题</span>
              <strong>{{ form.heroTitle || '-' }}</strong>
            </div>
            <div class="check-row">
              <span>支持邮箱</span>
              <strong>{{ form.supportEmail || '-' }}</strong>
            </div>
            <div class="check-row">
              <span>联系方式</span>
              <strong>{{ form.contactValue || '-' }}</strong>
            </div>
            <div class="check-row">
              <span>微信群二维码</span>
              <strong>{{ form.wechatGroupImageUrl ? '已配置' : '未配置' }}</strong>
            </div>
            <div class="check-row">
              <span>QQ群聊二维码</span>
              <strong>{{ form.qqGroupImageUrl ? '已配置' : '未配置' }}</strong>
            </div>
            <div class="check-row">
              <span>微信客服二维码</span>
              <strong>{{ form.wechatKefuImageUrl ? '已配置' : '未配置' }}</strong>
            </div>
            <div class="check-row">
              <span>赞助码</span>
              <strong>{{ form.sponsorImageUrl ? '已配置' : '未配置' }}</strong>
            </div>
            <div class="check-row">
              <span>logs 数量</span>
              <strong>{{ logsCount }}</strong>
            </div>
            <div class="check-row">
              <span>supports 数量</span>
              <strong>{{ supportsCount }}</strong>
            </div>
            <div class="check-row">
              <span>communityCards 数量</span>
              <strong>{{ communityCardsCount }}</strong>
            </div>
            <div class="check-row">
              <span>links 数量</span>
              <strong>{{ linksCount }}</strong>
            </div>
          </div>
        </ElCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadRequestOptions } from 'element-plus'
import {
  getOpenSourceAboutContent,
  importOpenSourceContentImageFromUrl,
  saveOpenSourceAboutContent,
  uploadOpenSourceContentImage,
  type OpenSourceAboutCommunityCard,
  type OpenSourceAboutContent,
  type OpenSourceAboutLinkItem,
  type OpenSourceAboutLogItem,
  type OpenSourceAboutSupportItem
} from '@/api/open-source-content'

defineOptions({ name: 'AdminOpenSourceAboutPage' })

type AboutFormState = {
  heroTitle: string
  heroBadgeText: string
  heroDescription: string
  serviceStatusText: string
  termsUrl: string
  privacyUrl: string
  supportEmail: string
  contactValue: string
  contactHint: string
  wechatGroupImageUrl: string
  wechatGroupHint: string
  qqGroupImageUrl: string
  qqGroupHint: string
  wechatKefuImageUrl: string
  wechatKefuHint: string
  sponsorImageUrl: string
  sponsorHint: string
  logsJson: string
  supportsJson: string
  communityCardsJson: string
  linksJson: string
}

type ManagedCommunityCardKey = 'group' | 'qqGroup' | 'wechatKefu' | 'sponsor'
type ManagedCommunityCardMatchKey = ManagedCommunityCardKey | 'contact'

const loading = ref(false)
const configState = ref<'loading' | 'ready' | 'error'>('loading')
const saving = ref(false)
const configurationWarning = ref('')
const formRef = ref<FormInstance>()
const imageUploadingKey = ref<ManagedCommunityCardKey | null>(null)
const imageImportingKey = ref<ManagedCommunityCardKey | null>(null)
const imageUrlImportMap = reactive<Record<ManagedCommunityCardKey, string>>({
  group: '',
  qqGroup: '',
  wechatKefu: '',
  sponsor: ''
})

const form = reactive<AboutFormState>({
  heroTitle: '',
  heroBadgeText: '',
  heroDescription: '',
  serviceStatusText: '',
  termsUrl: '',
  privacyUrl: '',
  supportEmail: '',
  contactValue: '',
  contactHint: '',
  wechatGroupImageUrl: '',
  wechatGroupHint: '',
  qqGroupImageUrl: '',
  qqGroupHint: '',
  wechatKefuImageUrl: '',
  wechatKefuHint: '',
  sponsorImageUrl: '',
  sponsorHint: '',
  logsJson: '[]',
  supportsJson: '[]',
  communityCardsJson: '[]',
  linksJson: '[]'
})

const rules: FormRules = {
  heroTitle: [{ required: true, message: '请输入主标题', trigger: 'blur' }],
  heroDescription: [{ required: true, message: '请输入主描述', trigger: 'blur' }],
  serviceStatusText: [{ required: true, message: '请输入服务状态文案', trigger: 'blur' }]
}

const logsCount = computed(() => safeArrayLength(form.logsJson))
const supportsCount = computed(() => safeArrayLength(form.supportsJson))
const communityCardsCount = computed(() => safeArrayLength(form.communityCardsJson))
const linksCount = computed(() => safeArrayLength(form.linksJson))

const DEFAULT_GROUP_CARD: OpenSourceAboutCommunityCard = {
  label: '交流群',
  title: '微信群二维码',
  desc: '用于版本通知、使用答疑、投放交流与功能建议收集。',
  placeholderText: 'GROUP',
  hint: '配置后可扫码',
  tone: 'blue',
  actionType: 'toast',
  actionText: '配置后可扫码',
  actionValue: '请在商业版后台为开源版关于页配置微信群二维码。',
  imageAlt: '微信群二维码'
}

const DEFAULT_QQ_GROUP_CARD: OpenSourceAboutCommunityCard = {
  label: 'QQ群',
  title: 'QQ群聊二维码',
  desc: '用于版本通知、使用答疑与功能建议收集，方便习惯使用 QQ 的用户加入。',
  placeholderText: 'QQ',
  hint: '配置后可扫码',
  tone: 'violet',
  actionType: 'toast',
  actionText: '配置后可扫码',
  actionValue: '请在商业版后台为开源版关于页配置QQ群聊二维码。',
  imageAlt: 'QQ群聊二维码'
}

const DEFAULT_WECHAT_KEFU_CARD: OpenSourceAboutCommunityCard = {
  label: '微信客服',
  title: '微信客服二维码',
  desc: '用于一对一咨询、技术支持与商务合作，扫码后可添加客服微信。',
  placeholderText: 'KEFU',
  hint: '配置后可扫码',
  tone: 'green',
  actionType: 'toast',
  actionText: '配置后可扫码',
  actionValue: '请在商业版后台为开源版关于页配置微信客服二维码。',
  imageAlt: '微信客服二维码'
}

const DEFAULT_SPONSOR_CARD: OpenSourceAboutCommunityCard = {
  label: '赞助支持',
  title: '赞助码',
  desc: '用于支持项目维护、联调验证、体验优化与后续版本更新。',
  placeholderText: 'SPONSOR',
  hint: '配置后可扫码',
  tone: 'orange',
  actionType: 'toast',
  actionText: '配置后可扫码',
  actionValue: '请在商业版后台为开源版关于页配置赞助二维码。',
  imageAlt: '赞助码'
}

const DEFAULT_CONTACT_CARD: OpenSourceAboutCommunityCard = {
  label: '联系方式',
  title: '商务合作方式待配置',
  desc: '管理员配置有效联系方式后，可用于广告投放、功能合作或技术支持。',
  hint: '尚未配置服务时间',
  tone: 'green',
  actionType: 'toast',
  actionText: '待管理员配置',
  actionValue: '联系方式尚未配置'
}

function prettyJson(value: unknown) {
  return JSON.stringify(value ?? [], null, 2)
}

function safeArrayLength(raw: string) {
  try {
    const parsed = JSON.parse(raw || '[]')
    return Array.isArray(parsed) ? parsed.length : 0
  } catch {
    return 0
  }
}

function resolveImage(imageUrl: string) {
  const value = String(imageUrl || '').trim()
  if (!value) return ''
  if (/^(https?:)?\/\//.test(value) || value.startsWith('/')) return value
  return `/${value.replace(/^\/+/, '')}`
}

function matchesCommunityCard(item: OpenSourceAboutCommunityCard | undefined, keywords: string[]) {
  const haystack = [item?.label, item?.title, item?.placeholderText, item?.actionValue]
    .map(value => String(value || '').toLowerCase())
    .join(' ')
  return keywords.some(keyword => haystack.includes(keyword))
}

function findManagedCommunityCard(
  cards: OpenSourceAboutCommunityCard[],
  key: ManagedCommunityCardMatchKey
) {
  if (key === 'group') {
    // 微信群二维码：收紧关键词避免与 QQ 群匹配冲突（不再使用裸 '群'）
    return cards.find(item => matchesCommunityCard(item, ['微信群', '微信交流群', 'wechat', '交流群']))
  }
  if (key === 'qqGroup') {
    return cards.find(item => matchesCommunityCard(item, ['qq', 'qq群', 'qq group']))
  }
  if (key === 'wechatKefu') {
    return cards.find(item => matchesCommunityCard(item, ['微信客服', '客服二维码', 'kefu', 'customer service']))
  }
  if (key === 'sponsor') {
    return cards.find(item => matchesCommunityCard(item, ['赞助', 'sponsor']))
  }
  return cards.find(item => matchesCommunityCard(item, ['联系', 'contact', 'business']))
}

function applyPayload(payload: Partial<OpenSourceAboutContent> = {}) {
  configurationWarning.value = String(payload.configurationWarning || '')
  const communityCards = Array.isArray(payload.communityCards) ? payload.communityCards : []
  const groupCard = findManagedCommunityCard(communityCards, 'group')
  const qqGroupCard = findManagedCommunityCard(communityCards, 'qqGroup')
  const wechatKefuCard = findManagedCommunityCard(communityCards, 'wechatKefu')
  const sponsorCard = findManagedCommunityCard(communityCards, 'sponsor')
  const contactCard = findManagedCommunityCard(communityCards, 'contact')

  form.heroTitle = String(payload.heroTitle || '')
  form.heroBadgeText = String(payload.heroBadgeText || '')
  form.heroDescription = String(payload.heroDescription || '')
  form.serviceStatusText = String(payload.serviceStatusText || '')
  form.termsUrl = String(payload.legalDocs?.termsUrl || '')
  form.privacyUrl = String(payload.legalDocs?.privacyUrl || '')
  form.supportEmail = String(payload.legalDocs?.supportEmail || '')
  form.contactValue = String(contactCard?.value || contactCard?.actionValue || '')
  form.contactHint = String(contactCard?.hint || DEFAULT_CONTACT_CARD.hint || '')
  form.wechatGroupImageUrl = String(groupCard?.imageUrl || '')
  form.wechatGroupHint = String(groupCard?.hint || DEFAULT_GROUP_CARD.hint || '')
  form.qqGroupImageUrl = String(qqGroupCard?.imageUrl || '')
  form.qqGroupHint = String(qqGroupCard?.hint || DEFAULT_QQ_GROUP_CARD.hint || '')
  form.wechatKefuImageUrl = String(wechatKefuCard?.imageUrl || '')
  form.wechatKefuHint = String(wechatKefuCard?.hint || DEFAULT_WECHAT_KEFU_CARD.hint || '')
  form.sponsorImageUrl = String(sponsorCard?.imageUrl || '')
  form.sponsorHint = String(sponsorCard?.hint || DEFAULT_SPONSOR_CARD.hint || '')
  imageUrlImportMap.group = ''
  imageUrlImportMap.qqGroup = ''
  imageUrlImportMap.wechatKefu = ''
  imageUrlImportMap.sponsor = ''
  form.logsJson = prettyJson(Array.isArray(payload.logs) ? payload.logs : [])
  form.supportsJson = prettyJson(Array.isArray(payload.supports) ? payload.supports : [])
  form.communityCardsJson = prettyJson(communityCards)
  form.linksJson = prettyJson(Array.isArray(payload.links) ? payload.links : [])
}

function parseArrayJson<T>(label: string, raw: string): T[] {
  try {
    const parsed = JSON.parse(raw || '[]')
    if (!Array.isArray(parsed)) {
      throw new Error('必须是 JSON 数组')
    }
    return parsed as T[]
  } catch (error: any) {
    throw new Error(`${label} JSON 格式错误：${error?.message || '解析失败'}`)
  }
}

function upsertManagedCommunityCard(
  cards: OpenSourceAboutCommunityCard[],
  key: ManagedCommunityCardMatchKey,
  nextCard: OpenSourceAboutCommunityCard
) {
  const currentCard = findManagedCommunityCard(cards, key)
  const currentIndex = currentCard ? cards.indexOf(currentCard) : -1
  if (currentIndex >= 0) {
    cards[currentIndex] = nextCard
    return
  }
  cards.push(nextCard)
}

function buildManagedCommunityCards(rawCards: OpenSourceAboutCommunityCard[]) {
  const cards = Array.isArray(rawCards) ? [...rawCards] : []
  const currentGroupCard = findManagedCommunityCard(cards, 'group')
  const currentQqGroupCard = findManagedCommunityCard(cards, 'qqGroup')
  const currentWechatKefuCard = findManagedCommunityCard(cards, 'wechatKefu')
  const currentSponsorCard = findManagedCommunityCard(cards, 'sponsor')
  const currentContactCard = findManagedCommunityCard(cards, 'contact')
  const groupImageUrl = form.wechatGroupImageUrl.trim()
  const qqGroupImageUrl = form.qqGroupImageUrl.trim()
  const wechatKefuImageUrl = form.wechatKefuImageUrl.trim()
  const sponsorImageUrl = form.sponsorImageUrl.trim()
  const contactValue = form.contactValue.trim()

  upsertManagedCommunityCard(cards, 'group', {
    ...DEFAULT_GROUP_CARD,
    ...currentGroupCard,
    imageUrl: groupImageUrl,
    hint: form.wechatGroupHint.trim() || currentGroupCard?.hint || DEFAULT_GROUP_CARD.hint,
    actionType: 'toast',
    actionText: currentGroupCard?.actionText || DEFAULT_GROUP_CARD.actionText,
    actionValue: groupImageUrl ? '请直接扫码加入微信群。' : DEFAULT_GROUP_CARD.actionValue
  })

  upsertManagedCommunityCard(cards, 'qqGroup', {
    ...DEFAULT_QQ_GROUP_CARD,
    ...currentQqGroupCard,
    imageUrl: qqGroupImageUrl,
    hint: form.qqGroupHint.trim() || currentQqGroupCard?.hint || DEFAULT_QQ_GROUP_CARD.hint,
    actionType: 'toast',
    actionText: currentQqGroupCard?.actionText || DEFAULT_QQ_GROUP_CARD.actionText,
    actionValue: qqGroupImageUrl ? '请直接扫码加入QQ群。' : DEFAULT_QQ_GROUP_CARD.actionValue
  })

  upsertManagedCommunityCard(cards, 'wechatKefu', {
    ...DEFAULT_WECHAT_KEFU_CARD,
    ...currentWechatKefuCard,
    imageUrl: wechatKefuImageUrl,
    hint: form.wechatKefuHint.trim() || currentWechatKefuCard?.hint || DEFAULT_WECHAT_KEFU_CARD.hint,
    actionType: 'toast',
    actionText: currentWechatKefuCard?.actionText || DEFAULT_WECHAT_KEFU_CARD.actionText,
    actionValue: wechatKefuImageUrl ? '请直接扫码添加微信客服。' : DEFAULT_WECHAT_KEFU_CARD.actionValue
  })

  upsertManagedCommunityCard(cards, 'sponsor', {
    ...DEFAULT_SPONSOR_CARD,
    ...currentSponsorCard,
    imageUrl: sponsorImageUrl,
    hint: form.sponsorHint.trim() || currentSponsorCard?.hint || DEFAULT_SPONSOR_CARD.hint,
    actionType: 'toast',
    actionText: currentSponsorCard?.actionText || DEFAULT_SPONSOR_CARD.actionText,
    actionValue: sponsorImageUrl ? '请直接扫码支持项目维护。' : DEFAULT_SPONSOR_CARD.actionValue
  })

  upsertManagedCommunityCard(cards, 'contact', {
    ...DEFAULT_CONTACT_CARD,
    ...currentContactCard,
    value: contactValue,
    hint: form.contactHint.trim() || currentContactCard?.hint || DEFAULT_CONTACT_CARD.hint,
    actionType: contactValue ? 'copy' : 'toast',
    actionText: contactValue ? '复制联系方式' : '待管理员配置',
    actionValue: contactValue || '联系方式尚未配置'
  })

  return cards
}

function beforeImageUpload(file: File) {
  const isSupportedImage = ['image/png', 'image/jpeg'].includes(file.type)
  if (!isSupportedImage) {
    ElMessage.error('本地上传仅支持可完整解码的 PNG、JPEG 格式；其他格式请先转换')
    return false
  }

  const isWithinLimit = file.size / 1024 / 1024 <= 5
  if (!isWithinLimit) {
    ElMessage.error('图片大小不能超过 5MB')
    return false
  }

  return true
}

function updateManagedImageValue(key: ManagedCommunityCardKey, value: string) {
  if (key === 'group') {
    form.wechatGroupImageUrl = value
    return
  }
  if (key === 'qqGroup') {
    form.qqGroupImageUrl = value
    return
  }
  if (key === 'wechatKefu') {
    form.wechatKefuImageUrl = value
    return
  }
  form.sponsorImageUrl = value
}

function managedCardKeyLabel(key: ManagedCommunityCardKey) {
  if (key === 'group') return '微信群二维码'
  if (key === 'qqGroup') return 'QQ群聊二维码'
  if (key === 'wechatKefu') return '微信客服二维码'
  return '赞助码'
}

function clearManagedImage(key: ManagedCommunityCardKey) {
  updateManagedImageValue(key, '')
  imageUrlImportMap[key] = ''
}

async function handleManagedImageUpload(key: ManagedCommunityCardKey, options: UploadRequestOptions) {
  if (configState.value !== 'ready') {
    ElMessage.warning('关于页配置尚未成功读取，当前不能上传图片')
    return
  }
  const file = options.file
  if (!(file instanceof File)) {
    ElMessage.error('上传文件无效')
    return
  }

  imageUploadingKey.value = key
  try {
    const res = await uploadOpenSourceContentImage(file)
    updateManagedImageValue(key, String(res?.url || ''))
    imageUrlImportMap[key] = ''
    ElMessage.success(`${managedCardKeyLabel(key)}上传成功`)
    options.onSuccess?.(res)
  } catch (error: any) {
    ElMessage.error(error?.message || '图片上传失败')
    options.onError?.(error)
  } finally {
    imageUploadingKey.value = null
  }
}

async function handleManagedImportFromUrl(key: ManagedCommunityCardKey) {
  if (configState.value !== 'ready') {
    ElMessage.warning('关于页配置尚未成功读取，当前不能导入图片')
    return
  }
  const sourceUrl = imageUrlImportMap[key].trim()
  if (!sourceUrl) {
    ElMessage.warning('请先填写图片 URL')
    return
  }

  imageImportingKey.value = key
  try {
    const res = await importOpenSourceContentImageFromUrl(sourceUrl)
    updateManagedImageValue(key, String(res?.url || ''))
    imageUrlImportMap[key] = ''
    ElMessage.success(`${managedCardKeyLabel(key)}导入成功`)
  } catch (error: any) {
    ElMessage.error(error?.message || 'URL 导入失败')
  } finally {
    imageImportingKey.value = null
  }
}

async function loadContent() {
  loading.value = true
  configState.value = 'loading'
  try {
    const res = await getOpenSourceAboutContent()
    applyPayload(res)
    configState.value = 'ready'
  } catch {
    configState.value = 'error'
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (configState.value !== 'ready') {
    ElMessage.warning('关于页配置尚未成功读取，当前不能保存')
    return
  }
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  let payload: OpenSourceAboutContent
  try {
    const rawCommunityCards = parseArrayJson<OpenSourceAboutCommunityCard>('communityCards', form.communityCardsJson)
    const communityCards = buildManagedCommunityCards(rawCommunityCards)
    form.communityCardsJson = prettyJson(communityCards)

    payload = {
      heroTitle: form.heroTitle.trim(),
      heroBadgeText: form.heroBadgeText.trim(),
      heroDescription: form.heroDescription.trim(),
      serviceStatusText: form.serviceStatusText.trim(),
      logs: parseArrayJson<OpenSourceAboutLogItem>('logs', form.logsJson),
      supports: parseArrayJson<OpenSourceAboutSupportItem>('supports', form.supportsJson),
      communityCards,
      links: parseArrayJson<OpenSourceAboutLinkItem>('links', form.linksJson),
      legalDocs: {
        termsUrl: form.termsUrl.trim(),
        privacyUrl: form.privacyUrl.trim(),
        supportEmail: form.supportEmail.trim()
      }
    }
  } catch (error: any) {
    ElMessage.error(error?.message || 'JSON 解析失败')
    return
  }

  saving.value = true
  try {
    const res = await saveOpenSourceAboutContent(payload)
    applyPayload(res)
    ElMessage.success('开源版关于页内容已保存')
  } catch (error: any) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => loadContent())
</script>

<style scoped>
.admin-page {
  padding: 4px;
}

.hero-card,
.section-card {
  border-radius: 18px;
}

.configuration-warning {
  margin: 16px 0;
}

.page-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-title-row h2 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 800;
}

.page-title-row p {
  margin: 0;
  color: var(--art-gray-500);
  max-width: 820px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 18px 0;
}

.summary-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
  padding: 16px 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #f5f8ff 100%);
}

.summary-card strong {
  display: block;
  color: #17315c;
  font-size: 22px;
  line-height: 1.2;
}

.summary-card span {
  display: block;
  margin-top: 8px;
  color: var(--art-gray-500);
  font-size: 12px;
}

.page-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 460px;
  gap: 16px;
  margin-top: 16px;
  align-items: start;
}

.page-main,
.page-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-head h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #17315c;
}

.card-head span {
  display: block;
  margin-top: 6px;
  color: var(--art-gray-500);
  font-size: 12px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-block label {
  color: #314666;
  font-size: 13px;
  font-weight: 700;
}

.field-block-full {
  grid-column: 1 / -1;
}

.field-tip {
  color: var(--art-gray-500);
  font-size: 12px;
  line-height: 1.6;
}

.media-editor {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.media-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 160px;
  height: 160px;
  border: 1px dashed var(--el-border-color);
  border-radius: 18px;
  overflow: hidden;
  background: linear-gradient(180deg, #fbfdff 0%, #f4f8ff 100%);
}

.media-preview.is-empty {
  color: #92a2c0;
}

.media-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.media-placeholder-icon {
  width: 28px;
  height: 28px;
}

.media-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.media-toolbar,
.media-url-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.media-url-row :deep(.el-input) {
  flex: 1;
}

.json-group {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.json-block {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  padding: 14px;
  background: #fff;
}

.json-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.json-head strong {
  color: #17315c;
  font-size: 14px;
}

.json-head span {
  color: var(--art-gray-500);
  font-size: 12px;
}

:deep(.mono-input textarea) {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.check-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.check-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 40px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}

.check-row span {
  color: #60718c;
  font-size: 13px;
}

.check-row strong {
  color: #17315c;
  font-size: 13px;
  text-align: right;
  word-break: break-all;
}

@media (max-width: 1280px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-grid,
  .field-grid {
    grid-template-columns: 1fr;
  }

  .media-editor {
    grid-template-columns: 1fr;
  }

  .media-preview {
    width: 100%;
    max-width: 220px;
  }

  .media-toolbar,
  .media-url-row {
    flex-wrap: wrap;
  }
}
</style>
