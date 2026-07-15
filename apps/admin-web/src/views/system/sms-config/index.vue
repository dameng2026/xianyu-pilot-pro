<!-- 短信接口配置页面 -->
<template>
  <div class="sms-config-page">
    <div class="page-header">
      <h3 class="page-title">短信接口配置</h3>
      <p class="page-desc">当前仅保存配置草稿，真实短信发送器接入并验收后才能生效</p>
    </div>

    <ElAlert
      title="短信发送器未接入"
      description="测试发送和生产验证码短信均不可用；请勿将配置已保存视为通道已开通。"
      type="warning"
      show-icon
      :closable="false"
      class="capability-alert"
    />

    <AdminDataState
      v-if="configState === 'loading'"
      state="loading"
      title="正在读取短信配置"
      description="读取完成前不会开放保存。"
    />
    <AdminDataState
      v-else-if="configState === 'error'"
      state="error"
      title="短信配置暂不可用"
      :description="configError"
      retry-text="重新读取"
      @retry="loadConfig"
    />

    <div v-show="configState === 'ready'" class="config-card art-card-sm">
      <h4 class="card-title">基础设置</h4>
      <ElForm
        :model="form"
        :rules="rules"
        ref="formRef"
        label-width="120px"
        label-position="right"
        class="config-form"
      >
        <!-- 服务商选择 -->
        <ElFormItem label="短信服务商" prop="provider">
          <ElSelect v-model="form.provider" placeholder="请选择短信服务商" style="width: 100%; max-width: 400px">
            <ElOption label="阿里云短信" value="aliyun" />
            <ElOption label="腾讯云短信" value="tencent" />
            <ElOption label="华为云短信" value="huawei" />
            <ElOption label="自定义接口" value="custom" />
          </ElSelect>
        </ElFormItem>

        <!-- 接口地址 -->
        <ElFormItem label="接口地址" prop="apiUrl">
          <ElInput
            v-model="form.apiUrl"
            placeholder="https://dysmsapi.aliyuncs.com/"
            style="width: 100%; max-width: 500px"
          />
        </ElFormItem>

        <!-- API密钥 -->
        <ElFormItem label="AccessKey ID" prop="accessKeyId">
          <ElInput
            v-model="form.accessKeyId"
            placeholder="请输入AccessKey ID"
            show-password
            style="width: 100%; max-width: 500px"
          />
        </ElFormItem>

        <ElFormItem label="AccessKey Secret" prop="accessKeySecret">
          <ElInput
            v-model="form.accessKeySecret"
            :placeholder="form.accessKeySecretConfigured ? '已安全配置，留空表示保持不变' : '请输入AccessKey Secret'"
            :disabled="form.clearAccessKeySecret"
            show-password
            style="width: 100%; max-width: 500px"
          />
          <div v-if="form.accessKeySecretConfigured" class="secret-state">
            <ElTag type="success" effect="plain" size="small">密钥已配置</ElTag>
            <ElCheckbox v-model="form.clearAccessKeySecret">保存时清除已保存密钥</ElCheckbox>
          </div>
        </ElFormItem>

        <!-- 签名和模板 -->
        <ElFormItem label="短信签名" prop="signName">
          <ElInput
            v-model="form.signName"
            placeholder="如：闲鱼助手"
            style="width: 100%; max-width: 500px"
          />
        </ElFormItem>

        <ElFormItem label="验证码模板" prop="templateCode">
          <ElInput
            v-model="form.templateCode"
            placeholder="短信模板CODE"
            style="width: 100%; max-width: 500px"
          />
        </ElFormItem>

        <ElFormItem label="模板参数" prop="templateParam">
          <ElInput
            v-model="form.templateParam"
            placeholder='{"code":"${code}"}'
            style="width: 100%; max-width: 500px"
          />
          <div class="form-tip">验证码将自动替换模板中的变量</div>
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
            <ElButton type="primary" v-ripple @click="handleSave" :loading="saving" :disabled="configState !== 'ready'">保存配置草稿</ElButton>
            <ElTooltip content="短信发送器未接入，测试功能不可用" placement="top">
              <span><ElButton disabled>发送测试短信</ElButton></span>
            </ElTooltip>
            <ElButton @click="handleReset" :disabled="configState !== 'ready'">恢复已读取配置</ElButton>
          </div>
        </ElFormItem>
      </ElForm>
    </div>

    <!-- 发送器未接入时不请求或伪造发送记录 -->
    <div class="config-card art-card-sm mt-5">
      <h4 class="card-title">发送记录</h4>
      <ElAlert
        title="短信发送器未接入，无真实记录"
        description="接入可审计的发送器与记录数据源后，此处才会展示真实投递结果。"
        type="info"
        show-icon
        :closable="false"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormItemRule, FormRules } from 'element-plus'
import {
  fetchGetSmsConfig,
  fetchSaveSmsConfig,
  type SmsConfigData
} from '@/api/notification-config'
import AdminDataState from '@/components/business/admin-data-state/index.vue'
import { isHttpError } from '@/utils/http/error'

const formRef = ref<FormInstance>()
const saving = ref(false)
const configState = ref<'loading' | 'ready' | 'error'>('loading')
const configError = ref('')
let loadedSnapshot: SmsConfigData | null = null

const form = reactive<SmsConfigData>({
  provider: 'aliyun',
  apiUrl: 'https://dysmsapi.aliyuncs.com/',
  accessKeyId: '',
  accessKeySecret: '',
  accessKeySecretConfigured: false,
  clearAccessKeySecret: false,
  signName: '闲鱼助手',
  templateCode: 'SMS_123456789',
  templateParam: '{"code":"${code}"}',
  codeLength: 6,
  validSeconds: 300,
  sendInterval: 60,
  dailyLimit: 20
})

function validateAccessKeySecret(
  _rule: FormItemRule,
  value: unknown,
  callback: (error?: Error) => void
) {
  const hasReplacementSecret = typeof value === 'string' && value.trim().length > 0
  if (form.accessKeySecretConfigured || form.clearAccessKeySecret || hasReplacementSecret) {
    callback()
    return
  }
  callback(new Error('请输入AccessKey Secret'))
}

function readableError(error: unknown, fallback: string) {
  if (isHttpError(error)) return error.displayMessage
  return error instanceof Error && error.message ? error.message : fallback
}

const rules: FormRules = {
  provider: [{ required: true, message: '请选择短信服务商', trigger: 'change' }],
  apiUrl: [{ required: true, message: '请输入接口地址', trigger: 'blur' }],
  accessKeyId: [{ required: true, message: '请输入AccessKey ID', trigger: 'blur' }],
  accessKeySecret: [{ validator: validateAccessKeySecret, trigger: 'blur' }],
  signName: [{ required: true, message: '请输入短信签名', trigger: 'blur' }],
  templateCode: [{ required: true, message: '请输入模板CODE', trigger: 'blur' }]
}

// 加载配置
async function loadConfig() {
  configState.value = 'loading'
  configError.value = ''
  try {
    const response = await fetchGetSmsConfig()
    if (!response || typeof response !== 'object') throw new Error('服务未返回有效短信配置')
    Object.assign(form, response)
    form.accessKeySecret = ''
    form.accessKeySecretConfigured = response.accessKeySecretConfigured === true
    form.clearAccessKeySecret = false
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
    ElMessage.error('短信配置尚未成功读取，已阻止保存')
    return
  }
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await fetchSaveSmsConfig({ ...form })
    ElMessage.success('短信配置草稿已保存；发送器未接入，尚不能发送短信')
    await loadConfig()
  } catch (error) {
    ElMessage.error(readableError(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

// 重置
function handleReset() {
  if (!loadedSnapshot) return
  Object.assign(form, loadedSnapshot)
  formRef.value?.clearValidate()
  ElMessage.info('已恢复为最近一次成功读取的短信配置')
}

onMounted(() => {
  void loadConfig()
})
</script>

<style scoped>
.sms-config-page {
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
</style>
