<!-- 邮箱接口配置页面 -->
<template>
  <div class="email-config-page">
    <div class="page-header">
      <h3 class="page-title">邮箱接口配置</h3>
      <p class="page-desc">配置 SMTP 发件参数；保存后即可用于登录、注册、找回密码的邮箱验证码发送</p>
    </div>

    <ElAlert
      v-if="!form.passwordConfigured"
      title="SMTP 凭据未配置"
      description="尚未配置 SMTP 用户名/密码，验证码邮件无法发送。请填写完整并保存后再启用相关认证能力。"
      type="warning"
      show-icon
      :closable="false"
      class="capability-alert"
    />

    <!-- 配置说明（可折叠） -->
    <ElCollapse v-show="configState === 'ready'" class="config-guide">
      <ElCollapseItem name="guide">
        <template #title>
          <span class="guide-title">
            <ElIcon class="guide-icon"><InfoFilled /></ElIcon>
            不知如何配置？点击查看完整填写指南
          </span>
        </template>
        <div class="guide-content">
          <div class="guide-section">
            <h5 class="guide-h">一、字段说明（必填项）</h5>
            <ul class="guide-ul">
              <li><strong>邮件服务商</strong>：选择您使用的邮箱类型，下方字段会自动填充对应默认值。</li>
              <li><strong>SMTP 服务器</strong>：邮箱服务商提供的发信服务器地址，无需自创。</li>
              <li><strong>SMTP 端口</strong>：SSL 加密通常填 <code>465</code>，TLS 加密通常填 <code>587</code>。</li>
              <li><strong>加密方式</strong>：QQ/腾讯企业邮推荐 <code>SSL</code>。</li>
              <li><strong>发件人邮箱</strong>：用于显示发件人的邮箱地址，必须与登录邮箱一致。</li>
              <li><strong>发件人名称</strong>：收件人看到的发件人名称，可自定义。</li>
              <li><strong>用户名</strong>：SMTP 登录用户名，<span class="hl">通常就是邮箱地址本身</span>（QQ 邮箱即 <code>xxxxx@qq.com</code>）。</li>
              <li><strong>密码/授权码</strong>：邮箱服务商生成的授权码，<span class="hl-warn">不是邮箱登录密码</span>。</li>
              <li><strong>邮件主题/模板</strong>：验证码邮件的标题与正文，<code>{code}</code> 占位符会被替换为实际验证码。</li>
            </ul>
          </div>

          <div class="guide-section">
            <h5 class="guide-h">二、QQ 邮箱配置示例（最常用）</h5>
            <table class="guide-table">
              <thead>
                <tr><th>字段</th><th>填写内容</th></tr>
              </thead>
              <tbody>
                <tr><td>邮件服务商</td><td>QQ 个人邮箱</td></tr>
                <tr><td>SMTP 服务器</td><td><code>smtp.qq.com</code></td></tr>
                <tr><td>SMTP 端口</td><td><code>465</code></td></tr>
                <tr><td>加密方式</td><td><code>SSL</code></td></tr>
                <tr><td>发件人邮箱</td><td>您的 QQ 邮箱地址（如 <code>12345678@qq.com</code>）</td></tr>
                <tr><td>用户名</td><td><span class="hl">与发件人邮箱完全相同</span>，即 <code>12345678@qq.com</code></td></tr>
                <tr><td>密码/授权码</td><td>16 位授权码（获取方式见下文）</td></tr>
              </tbody>
            </table>
          </div>

          <div class="guide-section">
            <h5 class="guide-h">三、如何获取 QQ 邮箱授权码</h5>
            <ol class="guide-ol">
              <li>登录 QQ 邮箱网页版：<a href="https://mail.qq.com" target="_blank" rel="noopener">https://mail.qq.com</a></li>
              <li>点击顶部「设置」→「账户」</li>
              <li>找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务」模块</li>
              <li>开启「IMAP/SMTP 服务」（如已开启，先关闭再重新开启可生成新授权码）</li>
              <li>按页面提示用绑定的手机号发送指定短信完成验证</li>
              <li>验证成功后，页面会返回一个 <strong>16 位授权码</strong>（如 <code>abcdefghijklmnopqrstuvwxyz</code>）</li>
              <li>复制该授权码，粘贴到下方「密码/授权码」字段</li>
            </ol>
            <ElAlert
              type="warning"
              :closable="false"
              :show-icon="true"
              class="guide-tip"
              title="常见问题"
            >
              <ul class="guide-ul">
                <li><strong>授权码 ≠ QQ 密码</strong>：填 QQ 登录密码会报 535 错误。</li>
                <li><strong>用户名 ≠ QQ 号</strong>：必须填完整邮箱地址 <code>xxxxx@qq.com</code>，不能只填 QQ 号。</li>
                <li><strong>发件人邮箱 = 用户名</strong>：QQ 邮箱要求两者一致，否则会被拒绝。</li>
                <li><strong>授权码失效</strong>：换网络或长时间未用可能失效，重新生成即可。</li>
              </ul>
            </ElAlert>
          </div>

          <div class="guide-section">
            <h5 class="guide-h">四、其他邮箱常用配置</h5>
            <table class="guide-table">
              <thead>
                <tr><th>邮箱类型</th><th>SMTP 服务器</th><th>端口</th><th>用户名</th><th>密码</th></tr>
              </thead>
              <tbody>
                <tr><td>QQ 个人邮箱</td><td><code>smtp.qq.com</code></td><td>465/SSL</td><td>完整邮箱地址</td><td>16 位授权码</td></tr>
                <tr><td>腾讯企业邮箱</td><td><code>smtp.exmail.qq.com</code></td><td>465/SSL</td><td>完整邮箱地址</td><td>邮箱登录密码</td></tr>
                <tr><td>网易 163 邮箱</td><td><code>smtp.163.com</code></td><td>465/SSL</td><td>完整邮箱地址</td><td>客户端授权码</td></tr>
                <tr><td>阿里云邮箱</td><td><code>smtp.aliyun.com</code></td><td>465/SSL</td><td>完整邮箱地址</td><td>邮箱登录密码</td></tr>
                <tr><td>Gmail</td><td><code>smtp.gmail.com</code></td><td>587/TLS</td><td>完整邮箱地址</td><td>应用专用密码</td></tr>
              </tbody>
            </table>
          </div>

          <div class="guide-section">
            <h5 class="guide-h">五、配置完成后</h5>
            <ol class="guide-ol">
              <li>点击「保存配置」按钮保存。</li>
              <li>点击「发送测试邮件」，输入一个可接收邮件的邮箱地址验证配置是否生效。</li>
              <li>测试邮件成功收到后，前台用户注册/登录/找回密码的验证码即可正常发送。</li>
            </ol>
          </div>
        </div>
      </ElCollapseItem>
    </ElCollapse>

    <AdminDataState
      v-if="configState === 'loading'"
      state="loading"
      title="正在读取邮件配置"
      description="读取完成前不会开放保存。"
    />
    <AdminDataState
      v-else-if="configState === 'error'"
      state="error"
      title="邮件配置暂不可用"
      :description="configError"
      retry-text="重新读取"
      @retry="loadConfig"
    />

    <div v-show="configState === 'ready'" class="config-card art-card-sm">
      <h4 class="card-title">SMTP服务器设置</h4>
      <ElForm
        :model="form"
        :rules="rules"
        ref="formRef"
        label-width="120px"
        label-position="right"
        class="config-form"
      >
        <!-- 邮件服务商 -->
        <ElFormItem label="邮件服务商" prop="provider">
          <ElSelect v-model="form.provider" placeholder="请选择邮件服务商" style="width: 100%; max-width: 400px" @change="onProviderChange">
            <ElOption label="自定义SMTP" value="custom" />
            <ElOption label="QQ 个人邮箱" value="qq" />
            <ElOption label="腾讯企业邮箱" value="qq_enterprise" />
            <ElOption label="网易 163 邮箱" value="netease_163" />
            <ElOption label="阿里企业邮箱" value="ali_enterprise" />
            <ElOption label="网易企业邮箱" value="netease_enterprise" />
            <ElOption label="Gmail" value="gmail" />
          </ElSelect>
          <div class="form-tip">选择邮箱类型后会自动填充 SMTP 服务器、端口、加密方式等默认值</div>
        </ElFormItem>

        <!-- SMTP服务器 -->
        <ElFormItem label="SMTP服务器" prop="smtpHost">
          <ElInput
            v-model="form.smtpHost"
            placeholder="如：smtp.qq.com"
            style="width: 100%; max-width: 400px"
          />
          <div class="form-tip">邮箱服务商提供的发信服务器地址，QQ 邮箱为 <code>smtp.qq.com</code></div>
        </ElFormItem>

        <!-- SMTP端口 -->
        <ElFormItem label="SMTP端口" prop="smtpPort">
          <ElInputNumber v-model="form.smtpPort" :min="1" :max="65535" style="width: 100%; max-width: 200px" />
          <span class="form-tip">SSL端口通常为465，TLS端口通常为587</span>
        </ElFormItem>

        <!-- 加密方式 -->
        <ElFormItem label="加密方式" prop="encryption">
          <ElRadioGroup v-model="form.encryption">
            <ElRadio label="ssl">SSL</ElRadio>
            <ElRadio label="tls">TLS</ElRadio>
            <ElRadio label="none">不加密</ElRadio>
          </ElRadioGroup>
          <div class="form-tip">QQ 邮箱推荐选 SSL；Gmail 推荐 TLS</div>
        </ElFormItem>

        <!-- 发件人信息 -->
        <ElFormItem label="发件人邮箱" prop="fromEmail">
          <ElInput
            v-model="form.fromEmail"
            placeholder="如：12345678@qq.com"
            style="width: 100%; max-width: 400px"
          />
          <div class="form-tip">用于发件的邮箱地址，<span class="hl">必须与下方用户名一致</span>（QQ 邮箱即完整邮箱地址）</div>
        </ElFormItem>

        <ElFormItem label="发件人名称" prop="fromName">
          <ElInput
            v-model="form.fromName"
            placeholder="如：闲鱼助手"
            style="width: 100%; max-width: 400px"
          />
          <div class="form-tip">收件人看到的发件人名称，可自定义</div>
        </ElFormItem>

        <!-- 认证信息 -->
        <ElFormItem label="用户名" prop="username">
          <ElInput
            v-model="form.username"
            placeholder="如：12345678@qq.com"
            style="width: 100%; max-width: 400px"
          />
          <div class="form-tip"><span class="hl">QQ/网易/阿里邮箱：用户名就是完整邮箱地址</span>；腾讯企业邮箱也是完整邮箱地址。不能只填 QQ 号或前缀</div>
        </ElFormItem>

        <ElFormItem label="密码/授权码" prop="password">
          <ElInput
            v-model="form.password"
            :placeholder="form.passwordConfigured ? '已安全配置，留空表示保持不变' : 'SMTP认证密码或授权码'"
            :disabled="form.clearPassword"
            show-password
            style="width: 100%; max-width: 400px"
          />
          <div class="form-tip">
            <span class="hl-warn">QQ 邮箱：填 16 位授权码（不是 QQ 登录密码）</span>；
            网易 163：填客户端授权码；腾讯企业邮箱/Gmail：填邮箱登录密码或应用专用密码
          </div>
          <div v-if="form.passwordConfigured" class="secret-state">
            <ElTag type="success" effect="plain" size="small">密码已配置</ElTag>
            <ElCheckbox v-model="form.clearPassword">保存时清除已保存密码</ElCheckbox>
          </div>
        </ElFormItem>

        <!-- 邮件模板 -->
        <ElFormItem label="邮件主题" prop="subject">
          <ElInput
            v-model="form.subject"
            placeholder="如：【闲鱼助手】验证码通知"
            style="width: 100%; max-width: 500px"
          />
        </ElFormItem>

        <ElFormItem label="邮件模板" prop="template">
          <ElInput
            v-model="form.template"
            type="textarea"
            :rows="8"
            placeholder="请输入HTML邮件模板内容，使用 {code} 作为验证码占位符"
            style="width: 100%; max-width: 600px"
          />
          <div class="form-tip">支持HTML格式，{code} 将替换为实际验证码</div>
        </ElFormItem>

        <!-- 验证码设置 -->
        <ElFormItem label="验证码长度" prop="codeLength">
          <ElInputNumber v-model="form.codeLength" :min="4" :max="6" style="width: 100%; max-width: 200px" />
        </ElFormItem>

        <ElFormItem label="有效时长" prop="validSeconds">
          <ElInputNumber v-model="form.validSeconds" :min="60" :max="600" style="width: 100%; max-width: 200px" />
          <span class="form-unit">秒</span>
        </ElFormItem>

        <ElFormItem label="发送间隔" prop="sendInterval">
          <ElInputNumber v-model="form.sendInterval" :min="30" :max="300" style="width: 100%; max-width: 200px" />
          <span class="form-unit">秒</span>
        </ElFormItem>

        <ElFormItem label="每日上限" prop="dailyLimit">
          <ElInputNumber v-model="form.dailyLimit" :min="5" :max="100" style="width: 100%; max-width: 200px" />
          <span class="form-unit">条</span>
        </ElFormItem>

        <!-- 操作按钮 -->
        <ElFormItem>
          <div class="form-actions">
            <ElButton type="primary" v-ripple @click="handleSave" :loading="saving" :disabled="configState !== 'ready'">保存配置</ElButton>
            <ElButton
              v-ripple
              :loading="testing"
              :disabled="configState !== 'ready' || !form.passwordConfigured"
              @click="openTestDialog"
            >
              发送测试邮件
            </ElButton>
            <ElButton @click="handleReset" :disabled="configState !== 'ready'">恢复已读取配置</ElButton>
          </div>
        </ElFormItem>
      </ElForm>
    </div>

    <!-- 邮件模板预览 -->
    <div v-if="configState === 'ready'" class="config-card art-card-sm mt-5">
      <h4 class="card-title">邮件模板预览</h4>
      <div class="email-preview">
        <div class="email-header">
          <span class="email-from">{{ form.fromName || '闲鱼助手' }}</span>
          <span class="email-to">发送至：test@example.com</span>
        </div>
        <div class="email-body" v-html="safePreviewContent"></div>
      </div>
    </div>

    <!-- 测试发送对话框 -->
    <ElDialog
      v-model="testDialogVisible"
      title="发送测试邮件"
      width="460px"
      :close-on-click-modal="false"
    >
      <ElForm :model="testForm" label-width="100px">
        <ElFormItem label="收件邮箱">
          <ElInput
            v-model="testForm.email"
            placeholder="请输入接收测试邮件的邮箱地址"
            type="email"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="testDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="testing" @click="handleSendTest">立即发送</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import type { FormInstance, FormItemRule, FormRules } from 'element-plus'
import {
  fetchGetEmailConfig,
  fetchSaveEmailConfig,
  fetchTestEmail,
  type EmailConfigData
} from '@/api/notification-config'
import { sanitizeHtml } from '@/utils/sanitizeHtml'
import AdminDataState from '@/components/business/admin-data-state/index.vue'
import { isHttpError } from '@/utils/http/error'

// 各邮箱服务商的 SMTP 默认配置
const PROVIDER_PRESETS: Record<string, { smtpHost: string; smtpPort: number; encryption: string }> = {
  custom: { smtpHost: 'smtp.qq.com', smtpPort: 465, encryption: 'ssl' },
  qq: { smtpHost: 'smtp.qq.com', smtpPort: 465, encryption: 'ssl' },
  qq_enterprise: { smtpHost: 'smtp.exmail.qq.com', smtpPort: 465, encryption: 'ssl' },
  netease_163: { smtpHost: 'smtp.163.com', smtpPort: 465, encryption: 'ssl' },
  netease_enterprise: { smtpHost: 'smtp.qiye.163.com', smtpPort: 994, encryption: 'ssl' },
  ali_enterprise: { smtpHost: 'smtp.qiye.aliyun.com', smtpPort: 465, encryption: 'ssl' },
  gmail: { smtpHost: 'smtp.gmail.com', smtpPort: 587, encryption: 'tls' }
}

// 选择邮箱服务商时自动填充默认 SMTP 参数（不影响用户已填的邮箱、用户名、密码）
function onProviderChange(provider: string) {
  const preset = PROVIDER_PRESETS[provider]
  if (!preset) return
  form.smtpHost = preset.smtpHost
  form.smtpPort = preset.smtpPort
  form.encryption = preset.encryption
}

const formRef = ref<FormInstance>()
const saving = ref(false)
const testing = ref(false)
const testDialogVisible = ref(false)
const testForm = reactive({ email: '' })
const configState = ref<'loading' | 'ready' | 'error'>('loading')
const configError = ref('')
let loadedSnapshot: EmailConfigData | null = null

const form = reactive<EmailConfigData>({
  provider: 'custom',
  smtpHost: 'smtp.qq.com',
  smtpPort: 465,
  encryption: 'ssl',
  fromEmail: 'noreply@xianyu.local',
  fromName: '闲鱼助手',
  username: '',
  password: '',
  passwordConfigured: false,
  clearPassword: false,
  subject: '【闲鱼助手】验证码通知',
  template: `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto; background: #fff; border-radius: 8px; padding: 30px;">
    <h2 style="color: #0d6bff;">闲鱼助手</h2>
    <p>您好！</p>
    <p>您的验证码是：</p>
    <div style="background: #f0f4ff; padding: 15px; border-radius: 6px; text-align: center;">
      <span style="font-size: 28px; font-weight: bold; color: #0d6bff; letter-spacing: 4px;">{code}</span>
    </div>
    <p style="color: #999; font-size: 12px;">验证码5分钟内有效，请勿泄露给他人。</p>
    <p style="color: #999; font-size: 12px;">如非本人操作，请忽略此邮件。</p>
  </div>
</body>
</html>`,
  codeLength: 6,
  validSeconds: 300,
  sendInterval: 60,
  dailyLimit: 20
})

const previewContent = computed(() => {
  return form.template.replace(/{code}/g, '<span style="color: #0d6bff; font-weight: bold;">123456</span>')
})
const safePreviewContent = computed(() => sanitizeHtml(previewContent.value))

function validatePassword(
  _rule: FormItemRule,
  value: unknown,
  callback: (error?: Error) => void
) {
  const hasReplacementPassword = typeof value === 'string' && value.trim().length > 0
  if (form.passwordConfigured || form.clearPassword || hasReplacementPassword) {
    callback()
    return
  }
  callback(new Error('请输入密码/授权码'))
}

function readableError(error: unknown, fallback: string) {
  if (isHttpError(error)) return error.displayMessage
  return error instanceof Error && error.message ? error.message : fallback
}

const rules: FormRules = {
  provider: [{ required: true, message: '请选择邮件服务商', trigger: 'change' }],
  smtpHost: [{ required: true, message: '请输入SMTP服务器地址', trigger: 'blur' }],
  smtpPort: [{ required: true, message: '请输入SMTP端口', trigger: 'blur' }],
  fromEmail: [
    { required: true, message: '请输入发件人邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  fromName: [{ required: true, message: '请输入发件人名称', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ validator: validatePassword, trigger: 'blur' }],
  subject: [{ required: true, message: '请输入邮件主题', trigger: 'blur' }],
  template: [{ required: true, message: '请输入邮件模板', trigger: 'blur' }]
}

// 加载配置
async function loadConfig() {
  configState.value = 'loading'
  configError.value = ''
  try {
    const response = await fetchGetEmailConfig()
    if (!response || typeof response !== 'object') throw new Error('服务未返回有效邮件配置')
    Object.assign(form, response)
    form.password = ''
    form.passwordConfigured = response.passwordConfigured === true
    form.clearPassword = false
    loadedSnapshot = { ...form }
    configState.value = 'ready'
  } catch (error) {
    loadedSnapshot = null
    configError.value = readableError(
      error,
      '读取失败，请检查网络或服务状态后重试。'
    )
    configState.value = 'error'
  }
}

// 保存配置
async function handleSave() {
  if (configState.value !== 'ready') {
    ElMessage.error('邮件配置尚未成功读取，已阻止保存')
    return
  }
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await fetchSaveEmailConfig({ ...form })
    ElMessage.success('邮件配置已保存')
    await loadConfig()
  } catch (error) {
    ElMessage.error(readableError(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

// 打开测试发送对话框
function openTestDialog() {
  testForm.email = ''
  testDialogVisible.value = true
}

// 发送测试邮件
async function handleSendTest() {
  const email = testForm.email.trim()
  if (!email) {
    ElMessage.error('请输入收件邮箱')
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    ElMessage.error('邮箱格式不正确')
    return
  }
  testing.value = true
  try {
    await fetchTestEmail(email)
    ElMessage.success('测试邮件已发送，请前往收件邮箱查收')
    testDialogVisible.value = false
  } catch (error) {
    ElMessage.error(readableError(error, '测试邮件发送失败'))
  } finally {
    testing.value = false
  }
}

// 重置
function handleReset() {
  if (!loadedSnapshot) return
  Object.assign(form, loadedSnapshot)
  formRef.value?.clearValidate()
  ElMessage.info('已恢复为最近一次成功读取的邮件配置')
}

onMounted(() => {
  void loadConfig()
})
</script>

<style scoped>
.email-config-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
}

.page-desc {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.capability-alert {
  margin-bottom: 20px;
}

.config-card {
  padding: 24px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.config-form {
  max-width: 700px;
}

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.secret-state {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  margin-top: 8px;
}

.form-unit {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.form-actions {
  display: flex;
  gap: 12px;
}

.mt-5 { margin-top: 20px; }
.empty-state { padding: 40px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 14px; }

/* 邮件预览 */
.email-preview {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}

.email-header {
  display: flex;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.email-from {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.email-body {
  padding: 20px;
  min-height: 200px;
}

.email-body :deep(h2) {
  color: #0d6bff;
  margin-top: 0;
}

.email-body :deep(p) {
  color: #333;
}

/* 配置说明区 */
.config-guide {
  margin-bottom: 20px;
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 8px;
  overflow: hidden;
}

.config-guide :deep(.el-collapse-item__header) {
  padding: 0 16px;
  background: var(--el-color-primary-light-9);
  font-size: 14px;
  font-weight: 600;
}

.config-guide :deep(.el-collapse-item__content) {
  padding: 16px 20px;
}

.guide-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-color-primary);
}

.guide-icon {
  font-size: 16px;
}

.guide-content {
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
}

.guide-section {
  margin-bottom: 18px;
}

.guide-section:last-child {
  margin-bottom: 0;
}

.guide-h {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--el-color-primary);
  padding-bottom: 4px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}

.guide-ul,
.guide-ol {
  margin: 4px 0 4px 4px;
  padding-left: 20px;
}

.guide-ul li,
.guide-ol li {
  margin-bottom: 4px;
}

.guide-content code {
  background: var(--el-fill-color-light);
  color: var(--el-color-danger);
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'Cascadia Mono', Consolas, Monaco, monospace;
  font-size: 12px;
}

.guide-content a {
  color: var(--el-color-primary);
  text-decoration: none;
}

.guide-content a:hover {
  text-decoration: underline;
}

.guide-table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12.5px;
}

.guide-table th,
.guide-table td {
  border: 1px solid var(--el-border-color-lighter);
  padding: 6px 10px;
  text-align: left;
}

.guide-table th {
  background: var(--el-fill-color-light);
  font-weight: 600;
}

.guide-table code {
  background: transparent;
  color: var(--el-color-danger);
  padding: 0;
}

.guide-tip {
  margin-top: 10px;
}

.guide-tip :deep(.el-alert__content) {
  text-align: left;
}

.guide-tip .guide-ul {
  margin: 4px 0 0;
}

.hl {
  color: var(--el-color-primary);
  font-weight: 600;
}

.hl-warn {
  color: var(--el-color-danger);
  font-weight: 600;
}
</style>
