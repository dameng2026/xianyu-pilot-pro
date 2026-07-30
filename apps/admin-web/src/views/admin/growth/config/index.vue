<template>
  <div class="growth-config-page">
    <!-- 顶部标题 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>增长配置</h2>
          <p>配置拉新奖励、最低提现金额、首月分成开关、提现开关等全局参数。</p>
        </div>
        <div class="actions">
          <ElButton :loading="loading" @click="loadConfig">刷新</ElButton>
          <ElButton type="primary" :loading="saving" :disabled="!formReady" @click="onSave">保存配置</ElButton>
        </div>
      </div>
    </ElCard>

    <AdminDataState v-if="formState === 'loading'" state="loading" title="正在读取配置" />
    <AdminDataState
      v-else-if="formState === 'error'"
      state="error"
      title="增长配置暂不可用"
      :description="formError"
      retry-text="重试"
      @retry="loadConfig"
    />
    <template v-else>
      <!-- 拉新奖励配置 -->
      <ElCard shadow="never" class="section-card">
        <template #header>
          <div class="section-title">
            <span class="title-text">拉新奖励配置</span>
            <span class="title-sub">用户每邀请 1 人产生消费行为，奖励一级用户的 Token 数量</span>
          </div>
        </template>
        <ElForm label-width="180px" label-position="right">
          <ElRow :gutter="16">
            <ElCol :span="12">
              <ElFormItem label="每邀请 1 人奖励 Token">
                <ElInputNumber
                  v-model="form.tokenRewardPerReferral"
                  :min="0"
                  :step="10"
                  controls-position="right"
                  style="width: 100%"
                />
                <div class="form-tip">二级用户产生消费行为后，一级用户立得此数量 Token。默认 100</div>
              </ElFormItem>
            </ElCol>
            <ElCol :span="12">
              <ElFormItem label="首月分成限制">
                <ElSwitch
                  v-model="form.firstMonthOnly"
                  :active-value="1"
                  :inactive-value="0"
                  active-text="仅首月消费参与分成"
                  inactive-text="所有消费都参与分成"
                />
                <div class="form-tip">开启后，二级用户仅首月消费按代理等级分成给一级用户</div>
              </ElFormItem>
            </ElCol>
          </ElRow>
        </ElForm>
      </ElCard>

      <!-- 提现配置 -->
      <ElCard shadow="never" class="section-card">
        <template #header>
          <div class="section-title">
            <span class="title-text">提现配置</span>
            <span class="title-sub">控制提现开关与最低提现金额</span>
          </div>
        </template>
        <ElForm label-width="180px" label-position="right">
          <ElRow :gutter="16">
            <ElCol :span="12">
              <ElFormItem label="提现功能">
                <ElSwitch
                  v-model="form.withdrawEnabled"
                  :active-value="1"
                  :inactive-value="0"
                  active-text="开放"
                  inactive-text="关闭"
                />
                <div class="form-tip">关闭后用户无法发起提现申请</div>
              </ElFormItem>
            </ElCol>
            <ElCol :span="12">
              <ElFormItem label="最低提现金额">
                <ElInputNumber
                  v-model="minWithdrawalYuan"
                  :min="0"
                  :step="10"
                  :precision="2"
                  controls-position="right"
                  style="width: 100%"
                />
                <div class="form-tip">单位：元。默认 50 元。用户可提现余额需 ≥ 此金额方可发起提现</div>
              </ElFormItem>
            </ElCol>
          </ElRow>
        </ElForm>
      </ElCard>

      <!-- 当前配置预览 -->
      <ElCard shadow="never" class="section-card preview-card">
        <template #header>
          <div class="section-title">
            <span class="title-text">前台显示预览</span>
            <span class="title-sub">前台增长合伙人页面将根据以下参数动态展示</span>
          </div>
        </template>
        <div class="preview-grid">
          <div class="preview-item">
            <span class="preview-label">邀请奖励</span>
            <b>{{ form.tokenRewardPerReferral ?? 0 }} Token / 人</b>
          </div>
          <div class="preview-item">
            <span class="preview-label">首月分成</span>
            <b>{{ form.firstMonthOnly === 1 ? '仅首月' : '所有消费' }}</b>
          </div>
          <div class="preview-item">
            <span class="preview-label">提现开关</span>
            <b :class="form.withdrawEnabled === 1 ? 'text-success' : 'text-danger'">
              {{ form.withdrawEnabled === 1 ? '已开放' : '已关闭' }}
            </b>
          </div>
          <div class="preview-item">
            <span class="preview-label">最低提现</span>
            <b>¥{{ formatYuan(minWithdrawalYuan) }}</b>
          </div>
        </div>
      </ElCard>

      <ElAlert type="info" :closable="false" show-icon class="tip-alert">
        <template #title>
          <span>
            修改后请点击右上角「保存配置」生效。代理等级、分成比例等高级配置请前往
            <router-link :to="{ name: 'AdminGrowthTierConfig' }" class="inline-link">代理等级</router-link>
            页面。
          </span>
        </template>
      </ElAlert>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref, watch } from 'vue'
  import { ElMessage } from 'element-plus'
  import { getGrowthConfig, saveGrowthConfig } from '@/api/growth'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminGrowthConfigPage' })

  const loading = ref(false)
  const saving = ref(false)
  const formState = ref<'loading' | 'ready' | 'error'>('loading')
  const formError = ref('')

  const form = reactive<any>({
    tokenRewardPerReferral: 100,
    minWithdrawalAmount: 5000, // 单位：分
    firstMonthOnly: 1,
    withdrawEnabled: 1,
    updatedBy: 'admin'
  })

  // 最低提现金额（元），用于表单输入；提交时再转回分
  const minWithdrawalYuan = ref(50)

  const formReady = computed(() => formState.value === 'ready')

  watch(minWithdrawalYuan, (val) => {
    form.minWithdrawalAmount = Math.round(Number(val || 0) * 100)
  })

  function formatYuan(value: any): string {
    const n = Number(value)
    if (!Number.isFinite(n)) return '0.00'
    return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  async function loadConfig() {
    formState.value = 'loading'
    formError.value = ''
    loading.value = true
    try {
      const cfg = await getGrowthConfig()
      Object.assign(form, {
        tokenRewardPerReferral: cfg.tokenRewardPerReferral ?? 100,
        minWithdrawalAmount: cfg.minWithdrawalAmount ?? 5000,
        firstMonthOnly: cfg.firstMonthOnly ?? 1,
        withdrawEnabled: cfg.withdrawEnabled ?? 1,
        updatedBy: 'admin'
      })
      minWithdrawalYuan.value = Number(form.minWithdrawalAmount || 0) / 100
      formState.value = 'ready'
    } catch (e: any) {
      formError.value = e?.message || '未知错误'
      formState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  async function onSave() {
    saving.value = true
    try {
      await saveGrowthConfig({
        tokenRewardPerReferral: Number(form.tokenRewardPerReferral),
        minWithdrawalAmount: Math.round(Number(minWithdrawalYuan.value || 0) * 100),
        firstMonthOnly: Number(form.firstMonthOnly),
        withdrawEnabled: Number(form.withdrawEnabled),
        updatedBy: 'admin'
      })
      ElMessage.success('配置已保存')
      await loadConfig()
    } catch (e: any) {
      ElMessage.error('保存失败：' + (e?.message || '未知错误'))
    } finally {
      saving.value = false
    }
  }

  onMounted(() => {
    loadConfig()
  })
</script>

<style scoped lang="scss">
  .growth-config-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .toolbar-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .page-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;

    h2 {
      margin: 0 0 4px;
      font-size: 18px;
      font-weight: 600;
    }
    p {
      margin: 0;
      font-size: 13px;
      color: #6b7280;
    }
    .actions {
      display: flex;
      gap: 8px;
    }
  }

  .section-title {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title-text {
      font-size: 14px;
      font-weight: 600;
      color: #111827;
    }
    .title-sub {
      font-size: 12px;
      color: #9ca3af;
      margin-left: 8px;
    }
  }

  .form-tip {
    font-size: 12px;
    color: #9ca3af;
    margin-top: 4px;
  }

  .preview-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .preview-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;

    @media (max-width: 960px) {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  .preview-item {
    padding: 14px 16px;
    border-radius: 10px;
    background: #f9fafb;
    border: 1px solid #f0f0f0;
    display: flex;
    flex-direction: column;
    gap: 4px;

    .preview-label {
      font-size: 12px;
      color: #6b7280;
    }
    b {
      font-size: 16px;
      color: #111827;
    }
  }

  .text-success {
    color: #10b981;
  }
  .text-danger {
    color: #ef4444;
  }

  .tip-alert {
    .inline-link {
      color: #2563eb;
      margin-left: 4px;
      &:hover {
        text-decoration: underline;
      }
    }
  }
</style>
