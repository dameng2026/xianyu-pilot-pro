<template>
  <div class="payment-admin-page">
    <section class="payment-head">
      <div>
        <h2>支付配置</h2>
        <p>集中配置微信、支付宝官方接口与易支付通道；支付订单、回调与权益发放由 Java 业务端统一处理。</p>
      </div>
      <div class="head-actions"><ElButton plain :loading="sandboxLoading" :disabled="configState !== 'ready'" @click="enableSandbox">一键启用沙箱支付</ElButton><ElButton type="primary" :disabled="configState !== 'ready'" @click="openConfig()">新增支付通道</ElButton></div>
    </section>

    <ElAlert
      v-if="paymentMode === 'sandbox'"
      title="当前处于沙箱支付环境：用户端只会生成测试订单，不会产生真实扣款。启用任意真实支付配置后，系统会自动关闭沙箱配置。"
      type="warning"
      show-icon
      :closable="false"
    />
    <ElAlert
      v-else-if="paymentMode === 'production'"
      title="当前处于真实支付环境：请确认商户号、API Key、回调地址和验签配置均为生产参数。启用沙箱配置会自动关闭真实支付配置。"
      type="success"
      show-icon
      :closable="false"
    />

    <section class="payment-grid">
      <AdminDataState v-if="configState === 'loading'" state="loading" title="正在读取支付通道" compact />
      <AdminDataState
        v-else-if="configState === 'error'"
        state="error"
        title="支付通道暂不可用"
        :description="configError"
        retry-text="重新读取通道"
        compact
        @retry="loadConfigs"
      />
      <template v-else-if="configs.length === 0">
        <ElEmpty description="暂无支付通道配置" />
      </template>
      <ElCard v-for="item in configState === 'ready' ? configs : []" :key="item.id" shadow="never" class="payment-card">
        <template #header>
          <div class="card-head">
            <strong>{{ item.configName }}</strong>
            <div class="card-tags"><ElTag :type="item.enabled ? 'success' : 'info'">{{ item.enabled ? '启用' : '禁用' }}</ElTag><ElTag v-if="item.sandbox" type="warning">沙箱</ElTag></div>
          </div>
        </template>
        <div class="config-line"><span>支付方式</span><b>{{ channelLabel(item.channelType) }}</b></div>
        <div class="config-line"><span>通道类型</span><b>{{ providerLabel(item.providerType) }}</b></div>
        <div class="config-line"><span>商户号</span><b>{{ item.merchantId || '-' }}</b></div>
        <div class="config-line"><span>回调地址</span><b>{{ item.notifyUrl || '-' }}</b></div>
        <div class="config-line"><span>测试模式</span><b>{{ item.sandbox ? '已启用沙箱模拟支付' : '真实支付环境' }}</b></div>
        <ElButton class="edit-btn" @click="openConfig(item)">编辑配置</ElButton>
      </ElCard>
    </section>

    <ElCard shadow="never" class="panel-card">
      <template #header>
        <div class="card-head"><strong>Token 充值套餐</strong><ElButton type="primary" plain :disabled="planState !== 'ready'" @click="openTokenPlan()">新增套餐</ElButton></div>
      </template>
      <AdminDataState v-if="planState === 'loading'" state="loading" title="正在读取充值套餐" compact />
      <AdminDataState
        v-else-if="planState === 'error'"
        state="error"
        title="充值套餐暂不可用"
        :description="planError"
        retry-text="重新读取套餐"
        compact
        @retry="loadTokenPlans"
      />
      <ElTable v-else :data="tokenPlanPage.records" border style="width: 100%">
        <template #empty><div class="empty-state">暂无充值套餐，点击"新增套餐"创建</div></template>
        <ElTableColumn prop="planName" label="套餐名称" min-width="140" />
        <ElTableColumn prop="tokenAmount" label="Token" width="110" />
        <ElTableColumn prop="bonusToken" label="赠送" width="100" />
        <ElTableColumn label="价格" width="110"><template #default="{ row }">¥{{ row.priceYuan }}</template></ElTableColumn>
        <ElTableColumn prop="sortOrder" label="排序" width="90" />
        <ElTableColumn label="状态" width="90"><template #default="{ row }"><ElTag :type="row.status === 1 ? 'success' : 'info'">{{ row.status === 1 ? '启用' : '禁用' }}</ElTag></template></ElTableColumn>
        <ElTableColumn label="操作" width="150" fixed="right"><template #default="{ row }"><ElButton link type="primary" @click="openTokenPlan(row)">编辑</ElButton><ElButton link type="danger" @click="removeTokenPlan(row)">删除</ElButton></template></ElTableColumn>
      </ElTable>
    </ElCard>

    <ElCard shadow="never" class="panel-card">
      <template #header>
        <div class="card-head"><strong>支付订单</strong><ElButton plain :loading="orderLoading" @click="loadOrders">刷新</ElButton></div>
      </template>
      <AdminDataState v-if="orderState === 'loading'" state="loading" title="正在读取支付订单" compact />
      <AdminDataState
        v-else-if="orderState === 'error'"
        state="error"
        title="支付订单暂不可用"
        :description="orderError"
        retry-text="重新读取订单"
        compact
        @retry="loadOrders"
      />
      <ElTable v-else :data="orderPage.records" border style="width: 100%">
        <template #empty><div class="empty-state">暂无支付订单记录</div></template>
        <ElTableColumn prop="orderNo" label="订单号" min-width="190" />
        <ElTableColumn prop="username" label="用户" width="120" />
        <ElTableColumn prop="title" label="商品" min-width="160" />
        <ElTableColumn prop="orderType" label="类型" width="90" />
        <ElTableColumn prop="amount" label="金额" width="100" />
        <ElTableColumn prop="paymentMethod" label="方式" width="90" />
        <ElTableColumn label="状态" width="100"><template #default="{ row }"><ElTag :type="row.status === 1 ? 'success' : row.status === 0 ? 'warning' : 'info'">{{ row.statusText }}</ElTag></template></ElTableColumn>
        <ElTableColumn prop="createdTime" label="创建时间" min-width="160" />
      </ElTable>
    </ElCard>

    <ElDialog v-model="configDialog" title="支付通道配置" width="520px">
      <ElForm :model="configForm" label-width="110px">
        <ElFormItem label="支付方式"><ElSelect v-model="configForm.channelType" @change="autoFill"><ElOption label="微信支付" value="wechat" /><ElOption label="支付宝" value="alipay" /></ElSelect></ElFormItem>
        <ElFormItem label="通道类型"><ElSelect v-model="configForm.providerType" @change="autoFill"><ElOption label="易支付" value="yipay" /><ElOption label="官方接口" value="official" /></ElSelect></ElFormItem>
        <ElFormItem label="商户号/PID"><ElInput v-model="configForm.merchantId" placeholder="易支付商户ID" /></ElFormItem>
        <ElFormItem label="API Key"><ElInput v-model="configForm.apiKey" type="password" show-password placeholder="商户密钥" /></ElFormItem>
        <ElFormItem v-if="configForm.providerType === 'yipay'" label="网关地址"><ElInput v-model="configForm.gatewayUrl" placeholder="易支付网关地址，如 https://z-pay.cn" /></ElFormItem>
        <ElFormItem label="启用"><ElSwitch v-model="configForm.enabled" /></ElFormItem>
        <ElFormItem label="沙箱模式">
          <ElSwitch v-model="configForm.sandbox" />
          <div class="form-tip">沙箱模式下用户端支付弹窗会显示“模拟支付成功”，仅用于测试订单和权益发放闭环。</div>
        </ElFormItem>
      </ElForm>
      <template #footer><ElButton @click="configDialog = false">取消</ElButton><ElButton type="primary" :loading="configSaving" :disabled="configState !== 'ready'" @click="submitConfig">保存</ElButton></template>
    </ElDialog>

    <ElDialog v-model="tokenDialog" title="Token 充值套餐" width="520px">
      <ElForm :model="tokenForm" label-width="100px">
        <ElFormItem label="套餐名称"><ElInput v-model="tokenForm.planName" /></ElFormItem>
        <ElFormItem label="Token 数"><ElInputNumber v-model="tokenForm.tokenAmount" :min="1" /></ElFormItem>
        <ElFormItem label="赠送 Token"><ElInputNumber v-model="tokenForm.bonusToken" :min="0" /></ElFormItem>
        <ElFormItem label="价格/元"><ElInputNumber v-model="tokenForm.priceYuan" :min="0.01" :precision="2" /></ElFormItem>
        <ElFormItem label="排序"><ElInputNumber v-model="tokenForm.sortOrder" :min="0" /></ElFormItem>
        <ElFormItem label="状态"><ElSwitch v-model="tokenForm.enabled" /></ElFormItem>
      </ElForm>
      <template #footer><ElButton @click="tokenDialog = false">取消</ElButton><ElButton type="primary" :loading="planSaving" :disabled="planState !== 'ready'" @click="submitTokenPlan">保存</ElButton></template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref } from 'vue'
  import { ElMessage, ElMessageBox } from 'element-plus'
  import {
    deleteTokenRechargePlan,
    fetchPaymentConfigs,
    fetchPaymentOrders,
    fetchTokenRechargePlans,
    savePaymentConfig,
    saveTokenRechargePlan
  } from '@/api/payment'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminPaymentConfigPage' })

  const configs = ref<any[]>([])
  const sandboxLoading = ref(false)
  const planLoading = ref(false)
  const orderLoading = ref(false)
  const configLoading = ref(false)
  const configSaving = ref(false)
  const planSaving = ref(false)
  const orderPage = reactive<any>({ records: [], total: 0 })
  const tokenPlanPage = reactive<any>({ records: [], total: 0 })
  const configDialog = ref(false)
  const tokenDialog = ref(false)
  const configForm = reactive<any>({})
  const tokenForm = reactive<any>({})
  const configState = ref<'loading' | 'ready' | 'error'>('loading')
  const planState = ref<'loading' | 'ready' | 'error'>('loading')
  const orderState = ref<'loading' | 'ready' | 'error'>('loading')
  const configError = ref('')
  const planError = ref('')
  const orderError = ref('')

  function channelLabel(v: string) { return v === 'wechat' ? '微信支付' : v === 'alipay' ? '支付宝' : `未识别（${v || '-'}）` }
  function providerLabel(v: string) { return v === 'yipay' ? '易支付' : v === 'official' ? '官方接口' : `未识别（${v || '-'}）` }
  const paymentMode = computed(() => {
    if (configState.value !== 'ready') return 'unknown'
    const enabled = configs.value.filter(item => item.enabled === 1 || item.enabled === true)
    if (!enabled.length) return 'disabled'
    return enabled.some(item => item.sandbox === 1 || item.sandbox === true) ? 'sandbox' : 'production'
  })

  async function loadConfigs() {
    configLoading.value = true
    configState.value = 'loading'
    configError.value = ''
    try {
      const data = await fetchPaymentConfigs()
      if (!Array.isArray(data)) throw new Error('支付通道接口返回格式异常')
      configs.value = data
      configState.value = 'ready'
    } catch (error: any) {
      configError.value = error?.message || '支付通道读取失败，请检查服务状态后重试。'
      configState.value = 'error'
    }
    finally { configLoading.value = false }
  }
  async function loadOrders() {
    orderLoading.value = true
    orderState.value = 'loading'
    orderError.value = ''
    try {
      const data = await fetchPaymentOrders({ current: 1, size: 20 })
      if (!data || !Array.isArray(data.records)) throw new Error('支付订单接口返回格式异常')
      Object.assign(orderPage, data)
      orderState.value = 'ready'
    } catch (error: any) {
      orderError.value = error?.message || '支付订单读取失败，请检查服务状态后重试。'
      orderState.value = 'error'
    }
    finally { orderLoading.value = false }
  }
  async function loadTokenPlans() {
    planLoading.value = true
    planState.value = 'loading'
    planError.value = ''
    try {
      const data = await fetchTokenRechargePlans({ current: 1, size: 20 })
      if (!data || !Array.isArray(data.records)) throw new Error('充值套餐接口返回格式异常')
      Object.assign(tokenPlanPage, data)
      planState.value = 'ready'
    } catch (error: any) {
      planError.value = error?.message || '充值套餐读取失败，请检查服务状态后重试。'
      planState.value = 'error'
    }
    finally { planLoading.value = false }
  }

  function autoFill() {
    const channelLabel = configForm.channelType === 'wechat' ? '微信支付' : '支付宝'
    const providerLabel = configForm.providerType === 'yipay' ? '易支付' : '官方接口'
    if (!configForm.id) {
      configForm.configName = `${channelLabel}·${providerLabel}`
    }
    configForm.notifyUrl = `/open-api/payment/callback/${configForm.channelType}`
  }

  function openConfig(row: any = {}) {
    if (configState.value !== 'ready') return
    Object.keys(configForm).forEach(k => delete configForm[k])
    Object.assign(configForm, {
      channelType: 'wechat', providerType: 'yipay',
      ...row,
      enabled: row.enabled === 1 || row.enabled === true,
      sandbox: row.sandbox === 1 || row.sandbox === true
    })
    if (!row.id) autoFill()
    configDialog.value = true
  }
  async function submitConfig() {
    if (configState.value !== 'ready') {
      ElMessage.error('支付通道尚未成功读取，已阻止保存')
      return
    }
    configSaving.value = true
    try {
      if (configForm.enabled && configForm.sandbox) {
        await ElMessageBox.confirm('启用沙箱支付后，系统会自动关闭已启用的真实支付配置。确认继续？', '环境隔离确认', { type: 'warning' })
      } else if (configForm.enabled) {
        await ElMessageBox.confirm('启用真实支付后，系统会自动关闭已启用的沙箱支付配置。请确认当前商户参数为生产参数。', '生产支付确认', { type: 'warning' })
      }
      await savePaymentConfig({ ...configForm, enabled: configForm.enabled ? 1 : 0, sandbox: configForm.sandbox ? 1 : 0 })
      configDialog.value = false
      await loadConfigs()
    } catch (error: any) {
      if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '支付通道保存失败')
    } finally {
      configSaving.value = false
    }
  }

  function openTokenPlan(row: any = {}) {
    if (planState.value !== 'ready') return
    Object.keys(tokenForm).forEach(k => delete tokenForm[k])
    Object.assign(tokenForm, { tokenAmount: 100, bonusToken: 0, priceYuan: 1, sortOrder: 100, ...row, enabled: row.status === undefined ? true : row.status === 1 })
    tokenDialog.value = true
  }
  async function submitTokenPlan() {
    if (planState.value !== 'ready') {
      ElMessage.error('充值套餐尚未成功读取，已阻止保存')
      return
    }
    planSaving.value = true
    try {
      await saveTokenRechargePlan({ ...tokenForm, status: tokenForm.enabled ? 1 : 0 })
      tokenDialog.value = false
      await loadTokenPlans()
    } catch (error: any) {
      ElMessage.error(error?.message || '充值套餐保存失败')
    } finally {
      planSaving.value = false
    }
  }

  async function enableSandbox() {
    if (configState.value !== 'ready') {
      ElMessage.error('支付通道尚未成功读取，已阻止沙箱配置写入')
      return
    }
    sandboxLoading.value = true
    try {
      const base = {
        channelType: 'wechat' as const,
        providerType: 'official' as const,
        configName: '微信支付·沙箱测试',
        merchantId: 'sandbox-merchant',
        apiKey: 'sandbox-key',
        notifyUrl: '/open-api/payment/callback/wechat',
        gatewayUrl: '',
        enabled: 1,
        sandbox: 1,
        remark: '仅用于测试环境模拟支付，不会发起真实扣款。'
      }
      const existing = configs.value.find(item => item.channelType === 'wechat' && item.providerType === 'official')
      await savePaymentConfig({ ...base, id: existing?.id })
      await loadConfigs()
    } catch (error: any) {
      ElMessage.error(error?.message || '沙箱支付配置启用失败')
    } finally {
      sandboxLoading.value = false
    }
  }

  async function removeTokenPlan(row: any) {
    try {
      await ElMessageBox.confirm(`确认删除 ${row.planName}？`, '删除确认')
      await deleteTokenRechargePlan(row.id)
      await loadTokenPlans()
    } catch (error: any) {
      if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '充值套餐删除失败')
    }
  }

  onMounted(async () => { await Promise.all([loadConfigs(), loadOrders(), loadTokenPlans()]) })
</script>

<style scoped lang="scss">
.payment-admin-page { display: grid; gap: 18px; }
.head-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.card-tags { display: inline-flex; align-items: center; gap: 8px; }
.form-tip { margin-top: 6px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.payment-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 22px; border-radius: 18px; background: var(--el-bg-color); box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06); }
.payment-head h2 { margin: 0; font-size: 24px; }
.payment-head p { margin: 8px 0 0; color: var(--el-text-color-secondary); }
.payment-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.payment-card { border-radius: 18px; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.config-line { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 9px 0; color: var(--el-text-color-secondary); border-bottom: 1px dashed var(--el-border-color-lighter); }
.config-line b { color: var(--el-text-color-primary); font-weight: 600; word-break: break-all; text-align: right; }
.edit-btn { width: 100%; margin-top: 14px; }
.panel-card { border-radius: 18px; }
.empty-state { padding: 40px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 14px; }
@media (max-width: 1100px) { .payment-grid { grid-template-columns: 1fr; } }
</style>
