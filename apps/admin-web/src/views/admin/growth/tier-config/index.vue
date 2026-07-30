<template>
  <div class="growth-tier-config-page">
    <!-- 顶部标题 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>代理等级配置</h2>
          <p>
            配置各代理等级的名称、自动升级所需拉新人数、分成比例与 Token 奖励。前台页面会根据此配置动态展示等级与权益。
          </p>
        </div>
        <div class="actions">
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
          <ElButton type="primary" @click="openCreate">新增等级</ElButton>
        </div>
      </div>
    </ElCard>

    <ElAlert type="info" :closable="false" show-icon class="tip-alert">
      <template #title>
        <span>
          <b>自动升级规则</b>：当一级用户的拉新人数达到该等级的 <b>minReferrals</b> 时，自动升级到对应等级。
          等级按 <b>sort</b> 升序排列，分成比例（commissionRate）为 0-100 的整数（表示百分比）。
        </span>
      </template>
    </ElAlert>

    <!-- 等级列表 -->
    <ElCard shadow="never" class="section-card">
      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取代理等级" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="代理等级暂不可用"
        :description="listError"
        retry-text="重试"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list" border stripe>
          <template #empty><div class="empty-state">暂无代理等级配置</div></template>
          <ElTableColumn prop="tierCode" label="等级编码" width="140" />
          <ElTableColumn prop="tierName" label="等级名称" min-width="140">
            <template #default="scope">
              <ElTag v-if="scope.row.tierName" type="warning" size="small">{{ scope.row.tierName }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="自动升级条件" width="140">
            <template #default="scope">
              <span>拉新 ≥ <b>{{ scope.row.minReferrals }}</b> 人</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="分成比例" width="120">
            <template #default="scope">
              <b class="text-success">{{ scope.row.commissionRate }}%</b>
            </template>
          </ElTableColumn>
          <ElTableColumn label="Token 奖励" width="120">
            <template #default="scope">
              <b>{{ scope.row.tokenRewardPerReferral ?? '—' }}</b> 个/人
            </template>
          </ElTableColumn>
          <ElTableColumn prop="sort" label="排序" width="80" />
          <ElTableColumn label="状态" width="80">
            <template #default="scope">
              <ElTag :type="Number(scope.row.enabled) === 1 ? 'success' : 'info'" size="small">
                {{ Number(scope.row.enabled) === 1 ? '启用' : '禁用' }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="description" label="描述" min-width="180" show-overflow-tooltip />
          <ElTableColumn label="操作" width="130" fixed="right">
            <template #default="scope">
              <ElButton link type="primary" size="small" @click="openEdit(scope.row)">编辑</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </template>
    </ElCard>

    <!-- 编辑对话框 -->
    <ElDialog
      v-model="dialogVisible"
      :title="form.id ? '编辑代理等级' : '新增代理等级'"
      width="640px"
      @close="onDialogClose"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="140px" label-position="right">
        <ElFormItem label="等级编码" prop="tierCode">
          <ElInput
            v-model="form.tierCode"
            placeholder="如 normal / silver / gold / platinum"
            :disabled="!!form.id"
          />
          <div class="form-tip">等级唯一标识，创建后不可修改</div>
        </ElFormItem>
        <ElFormItem label="等级名称" prop="tierName">
          <ElInput v-model="form.tierName" placeholder="如 普通代理 / 白银代理 / 黄金代理" />
        </ElFormItem>
        <ElFormItem label="自动升级人数" prop="minReferrals">
          <ElInputNumber
            v-model="form.minReferrals"
            :min="0"
            :step="1"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">达到此拉新人数自动升级到该等级。normal 等级建议填 0</div>
        </ElFormItem>
        <ElFormItem label="分成比例" prop="commissionRate">
          <ElInputNumber
            v-model="form.commissionRate"
            :min="0"
            :max="100"
            :step="5"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">0-100 的整数，表示百分比。如 30 表示 30% 分成</div>
        </ElFormItem>
        <ElFormItem label="Token 奖励" prop="tokenRewardPerReferral">
          <ElInputNumber
            v-model="form.tokenRewardPerReferral"
            :min="0"
            :step="10"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">该等级一级用户每邀请 1 人奖励的 Token 数（留空则使用全局配置）</div>
        </ElFormItem>
        <ElFormItem label="排序">
          <ElInputNumber
            v-model="form.sort"
            :min="0"
            :step="1"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">数字越小越靠前</div>
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="form.enabled" :active-value="1" :inactive-value="0" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="该等级的权益说明（前台展示用）"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="onSubmit">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, reactive, ref } from 'vue'
  import { ElMessage, type FormInstance } from 'element-plus'
  import { getGrowthTierConfigs, saveGrowthTierConfig, type GrowthTierConfig } from '@/api/growth'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminGrowthTierConfigPage' })

  const loading = ref(false)
  const submitting = ref(false)
  const listState = ref<'loading' | 'ready' | 'error'>('loading')
  const listError = ref('')
  const list = ref<GrowthTierConfig[]>([])

  const dialogVisible = ref(false)
  const formRef = ref<FormInstance>()

  const form = reactive<any>({
    id: null,
    tierCode: '',
    tierName: '',
    minReferrals: 0,
    commissionRate: 0,
    tokenRewardPerReferral: null,
    sort: 0,
    enabled: 1,
    description: ''
  })

  const rules = {
    tierCode: [{ required: true, message: '请输入等级编码', trigger: 'blur' }],
    tierName: [{ required: true, message: '请输入等级名称', trigger: 'blur' }],
    minReferrals: [{ required: true, message: '请输入自动升级人数', trigger: 'blur' }],
    commissionRate: [{ required: true, message: '请输入分成比例', trigger: 'blur' }]
  }

  async function loadList() {
    listState.value = 'loading'
    listError.value = ''
    loading.value = true
    try {
      list.value = await getGrowthTierConfigs()
      listState.value = 'ready'
    } catch (e: any) {
      listError.value = e?.message || '未知错误'
      listState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  function openCreate() {
    Object.assign(form, {
      id: null,
      tierCode: '',
      tierName: '',
      minReferrals: 0,
      commissionRate: 0,
      tokenRewardPerReferral: null,
      sort: list.value.length,
      enabled: 1,
      description: ''
    })
    dialogVisible.value = true
  }

  function openEdit(row: unknown) {
    const r = row as GrowthTierConfig
    Object.assign(form, {
      id: r.id ?? null,
      tierCode: r.tierCode ?? '',
      tierName: r.tierName ?? '',
      minReferrals: r.minReferrals ?? 0,
      commissionRate: r.commissionRate ?? 0,
      tokenRewardPerReferral: r.tokenRewardPerReferral ?? null,
      sort: r.sort ?? 0,
      enabled: r.enabled ?? 1,
      description: r.description ?? ''
    })
    dialogVisible.value = true
  }

  function onDialogClose() {
    formRef.value?.resetFields()
  }

  async function onSubmit() {
    if (!formRef.value) return
    await formRef.value.validate(async (valid) => {
      if (!valid) return
      submitting.value = true
      try {
        const payload: Partial<GrowthTierConfig> = {
          tierCode: form.tierCode,
          tierName: form.tierName,
          minReferrals: Number(form.minReferrals),
          commissionRate: Number(form.commissionRate),
          tokenRewardPerReferral: form.tokenRewardPerReferral === null ? null : Number(form.tokenRewardPerReferral),
          sort: Number(form.sort),
          enabled: Number(form.enabled),
          description: form.description || ''
        }
        if (form.id) payload.id = form.id
        await saveGrowthTierConfig(payload)
        ElMessage.success(form.id ? '已更新' : '已新增')
        dialogVisible.value = false
        await loadList()
      } catch (e: any) {
        ElMessage.error('保存失败：' + (e?.message || '未知错误'))
      } finally {
        submitting.value = false
      }
    })
  }

  onMounted(() => {
    loadList()
  })
</script>

<style scoped lang="scss">
  .growth-tier-config-page {
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

  .form-tip {
    font-size: 12px;
    color: #9ca3af;
    margin-top: 4px;
  }

  .text-success {
    color: #10b981;
  }

  .empty-state {
    text-align: center;
    color: #9ca3af;
    padding: 24px;
  }

  .tip-alert {
    margin-top: -4px;
  }
</style>
