<template>
  <ElDialog
    v-model="visible"
    :title="isEdit ? '编辑活动' : '新建活动'"
    width="900px"
    top="6vh"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :before-close="handleBeforeClose"
  >
    <ElForm
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
      label-position="right"
      :disabled="saving"
    >
      <ElDivider content-position="left">基础信息</ElDivider>
      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="活动名称" prop="activityName">
            <ElInput v-model="form.activityName" placeholder="如：会员限时优惠" maxlength="100" show-word-limit />
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="活动编码" prop="activityCode">
            <ElInput
              v-model="form.activityCode"
              placeholder="如：2026-summer-promo"
              maxlength="50"
              show-word-limit
              :disabled="isEdit"
            />
            <div class="form-tip">用于后台识别，创建后不可修改。</div>
          </ElFormItem>
        </ElCol>
      </ElRow>
      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="开始时间" prop="startTime">
            <ElDatePicker
              v-model="form.startTime"
              type="datetime"
              placeholder="选择开始时间"
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 100%"
            />
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="结束时间" prop="endTime" :required="!form.isLongTerm">
            <ElDatePicker
              v-model="form.endTime"
              type="datetime"
              placeholder="选择结束时间"
              value-format="YYYY-MM-DDTHH:mm:ss"
              :disabled="form.isLongTerm"
              style="width: 100%"
            />
          </ElFormItem>
        </ElCol>
      </ElRow>
      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="长期活动">
            <ElSwitch v-model="form.isLongTerm" />
            <div class="form-tip">开启后无需设置结束时间，长期生效。</div>
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="到期自动关闭">
            <ElSwitch v-model="form.autoCloseOnEnd" />
            <div class="form-tip">关闭后到期需手动处理待支付订单。</div>
          </ElFormItem>
        </ElCol>
      </ElRow>
      <ElFormItem label="活动备注">
        <ElInput
          v-model="form.description"
          type="textarea"
          :rows="2"
          placeholder="后台备注，仅管理员可见"
          maxlength="500"
          show-word-limit
        />
      </ElFormItem>

      <ElDivider content-position="left">前台通知文案</ElDivider>
      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="通知标题">
            <ElInput v-model="form.noticeTitle" placeholder="如：限时特惠" maxlength="50" show-word-limit />
          </ElFormItem>
        </ElCol>
        <ElCol :span="6">
          <ElFormItem label="展示位置">
            <ElSelect v-model="form.noticePosition" style="width: 100%">
              <ElOption label="顶部" value="top" />
              <ElOption label="横幅" value="banner" />
              <ElOption label="卡片" value="card" />
            </ElSelect>
          </ElFormItem>
        </ElCol>
        <ElCol :span="6">
          <ElFormItem label="通知图标">
            <ElSelect v-model="form.noticeIcon" style="width: 100%">
              <ElOption label="热门" value="hot" />
              <ElOption label="礼物" value="gift" />
              <ElOption label="闪电" value="flash" />
              <ElOption label="星标" value="star" />
            </ElSelect>
          </ElFormItem>
        </ElCol>
      </ElRow>
      <ElFormItem label="通知正文">
        <ElInput
          v-model="form.noticeContent"
          type="textarea"
          :rows="2"
          placeholder="如：本平台预计一周后调整会员价格，当前活动价格仅在活动期间有效。"
          maxlength="500"
          show-word-limit
        />
        <div class="form-tip">仅支持纯文本，HTML 标签会被自动过滤。名额、时间等动态信息由系统自动生成。</div>
      </ElFormItem>
      <ElFormItem label="前台展示">
        <ElSwitch v-model="form.noticeVisible" />
      </ElFormItem>

      <ElDivider content-position="left">
        <span>套餐活动配置</span>
        <ElButton
          type="primary"
          link
          size="small"
          style="margin-left: 12px"
          :disabled="!form.startTime"
          @click="addPlanRow"
        >
          + 添加套餐
        </ElButton>
      </ElDivider>
      <div v-if="!form.startTime" class="plan-tip">
        请先选择「开始时间」后再添加套餐配置
      </div>
      <ElTable v-else :data="form.plans" border stripe size="small">
        <template #empty>
          <div class="empty-state">暂未配置套餐，点击「+ 添加套餐」</div>
        </template>
        <ElTableColumn label="套餐" min-width="180">
          <template #default="{ row, $index }">
            <ElSelect
              v-model="row.planId"
              placeholder="选择套餐"
              filterable
              style="width: 100%"
              :disabled="isEdit"
              @change="onPlanChange($index)"
            >
              <ElOption
                v-for="p in availablePlans"
                :key="p.id"
                :label="`${p.planName}（${periodText(row.periodType)}原价 ¥${originalPriceYuan(p, row.periodType)}）`"
                :value="p.id"
              />
            </ElSelect>
          </template>
        </ElTableColumn>
        <ElTableColumn label="计费周期" width="110">
          <template #default="{ row, $index }">
            <ElSelect v-model="row.periodType" @change="onPeriodChange($index)">
              <ElOption label="月" value="month" />
              <ElOption label="季" value="quarter" />
              <ElOption label="年" value="year" />
            </ElSelect>
          </template>
        </ElTableColumn>
        <ElTableColumn label="活动价/元" width="140">
          <template #default="{ row }">
            <ElInputNumber
              v-model="row.activityPriceYuan"
              :min="0"
              :max="row._originalPriceYuan || 1000000"
              :precision="2"
              :step="1"
              controls-position="right"
              size="small"
              style="width: 100%"
              @change="onActivityPriceChange(row as PlanRow)"
            />
            <div v-if="row._originalPriceYuan" class="muted small-text">原价 ¥{{ row._originalPriceYuan }}</div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="名额" width="120">
          <template #default="{ row }">
            <ElInputNumber
              v-model="row.quota"
              :min="0"
              :step="10"
              controls-position="right"
              size="small"
              style="width: 100%"
            />
            <div class="muted small-text">0=不限量</div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="标签" width="120">
          <template #default="{ row }">
            <ElInput v-model="row.activityTag" placeholder="如：限时特价" maxlength="20" size="small" />
          </template>
        </ElTableColumn>
        <ElTableColumn label="展示选项" width="200">
          <template #default="{ row }">
            <div class="switch-row">
              <ElCheckbox v-model="row.showSoldCount">已售</ElCheckbox>
              <ElCheckbox v-model="row.showQuota">名额</ElCheckbox>
              <ElCheckbox v-model="row.showRemain">剩余</ElCheckbox>
            </div>
            <div class="switch-row">
              <ElCheckbox v-model="row.allowRepurchase">允许复购</ElCheckbox>
            </div>
            <ElInputNumber
              v-model="row.maxPurchasePerUser"
              :min="0"
              :step="1"
              controls-position="right"
              size="small"
              style="width: 100%; margin-top: 4px"
            />
            <div class="muted small-text">每人限购次数（0=不限制）</div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="排序" width="80">
          <template #default="{ row }">
            <ElInputNumber
              v-model="row.sortOrder"
              :min="0"
              :step="10"
              controls-position="right"
              size="small"
              style="width: 100%"
            />
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="80" fixed="right">
          <template #default="{ $index }">
            <ElButton link type="danger" size="small" @click="removePlanRow($index)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElForm>
    <template #footer>
      <ElButton @click="visible = false" :disabled="saving">取消</ElButton>
      <ElButton type="primary" :loading="saving" @click="onSave">
        {{ isEdit ? '保存修改' : '创建活动' }}
      </ElButton>
    </template>
  </ElDialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createPromotionActivity,
  fetchEnabledBillingPlans,
  updatePromotionActivity
} from '@/api/promotion'

defineOptions({ name: 'ActivityFormDialog' })

const props = defineProps<{
  modelValue: boolean
  /** 编辑时传入活动详情，新建时传 null */
  detail: Record<string, any> | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v)
})

const formRef = ref<FormInstance>()
const saving = ref(false)
const availablePlans = ref<any[]>([])

const isEdit = computed(() => !!props.detail?.id)

interface PlanRow {
  planId: number | null
  periodType: 'month' | 'quarter' | 'year'
  activityPriceCent: number
  activityPriceYuan: number
  _originalPriceYuan: number | null
  quota: number
  sortOrder: number
  activityTag: string
  showSoldCount: boolean
  showQuota: boolean
  showRemain: boolean
  allowRepurchase: boolean
  maxPurchasePerUser: number
}

const form = reactive<any>({
  id: undefined,
  activityName: '',
  activityCode: '',
  description: '',
  startTime: '',
  endTime: '',
  isLongTerm: false,
  autoCloseOnEnd: true,
  noticeTitle: '',
  noticeContent: '',
  noticeVisible: true,
  noticePosition: 'top',
  noticeIcon: 'hot',
  plans: [] as PlanRow[]
})

const rules: FormRules = {
  activityName: [
    { required: true, message: '请输入活动名称', trigger: 'blur' },
    { max: 100, message: '活动名称不超过 100 字符', trigger: 'blur' }
  ],
  activityCode: [
    { required: true, message: '请输入活动编码', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_-]{1,50}$/, message: '仅支持字母、数字、下划线、短横线', trigger: 'blur' }
  ],
  startTime: [{ required: true, message: '请选择开始时间', trigger: 'change' }]
}

function periodText(periodType: string): string {
  return periodType === 'quarter' ? '季' : periodType === 'year' ? '年' : '月'
}

function originalPriceYuan(plan: any, periodType: string): string {
  const cent = periodType === 'quarter'
    ? Number(plan.priceQuarterCent) || 0
    : periodType === 'year'
      ? Number(plan.priceYearCent) || 0
      : Number(plan.priceMonthCent) || 0
  return (cent / 100).toFixed(2)
}

function resetForm() {
  Object.assign(form, {
    id: undefined,
    activityName: '',
    activityCode: '',
    description: '',
    startTime: '',
    endTime: '',
    isLongTerm: false,
    autoCloseOnEnd: true,
    noticeTitle: '',
    noticeContent: '',
    noticeVisible: true,
    noticePosition: 'top',
    noticeIcon: 'hot',
    plans: []
  })
  formRef.value?.clearValidate?.()
}

function loadDetail(detail: Record<string, any>) {
  Object.assign(form, {
    id: detail.id,
    activityName: detail.activityName || '',
    activityCode: detail.activityCode || '',
    description: detail.description || '',
    startTime: normalizeDateTime(detail.startTime),
    endTime: normalizeDateTime(detail.endTime),
    isLongTerm: !!detail.isLongTerm,
    autoCloseOnEnd: detail.autoCloseOnEnd !== false && detail.autoCloseOnEnd !== 0,
    noticeTitle: detail.noticeTitle || '',
    noticeContent: detail.noticeContent || '',
    noticeVisible: detail.noticeVisible !== false && detail.noticeVisible !== 0,
    noticePosition: detail.noticePosition || 'top',
    noticeIcon: detail.noticeIcon || 'hot',
    plans: (detail.plans || []).map((p: any) => ({
      planId: p.planId,
      periodType: p.periodType,
      activityPriceCent: p.activityPriceCent,
      activityPriceYuan: Number(p.activityPriceYuan) || (Number(p.activityPriceCent) || 0) / 100,
      _originalPriceYuan: computeOriginalYuan(p),
      quota: Number(p.quota) || 0,
      sortOrder: Number(p.sortOrder) || 0,
      activityTag: p.activityTag || '',
      showSoldCount: p.showSoldCount !== false && p.showSoldCount !== 0,
      showQuota: p.showQuota !== false && p.showQuota !== 0,
      showRemain: p.showRemain !== false && p.showRemain !== 0,
      allowRepurchase: p.allowRepurchase !== false && p.allowRepurchase !== 0,
      maxPurchasePerUser: Number(p.maxPurchasePerUser) || 0
    }))
  })
}

function computeOriginalYuan(plan: any): number | null {
  const bp = availablePlans.value.find(p => p.id === plan.planId)
  if (!bp) return null
  const cent = plan.periodType === 'quarter'
    ? Number(bp.priceQuarterCent) || 0
    : plan.periodType === 'year'
      ? Number(bp.priceYearCent) || 0
      : Number(bp.priceMonthCent) || 0
  return cent > 0 ? Number((cent / 100).toFixed(2)) : null
}

function normalizeDateTime(v: any): string {
  if (!v) return ''
  // 兼容 "2026-07-27 12:00:00" 与 ISO 格式
  return String(v).replace(' ', 'T')
}

function addPlanRow() {
  if (!form.startTime) {
    ElMessage.warning('请先选择开始时间')
    return
  }
  form.plans.push({
    planId: null,
    periodType: 'month',
    activityPriceCent: 0,
    activityPriceYuan: 0,
    _originalPriceYuan: null,
    quota: 0,
    sortOrder: form.plans.length * 10,
    activityTag: '',
    showSoldCount: true,
    showQuota: true,
    showRemain: true,
    allowRepurchase: true,
    maxPurchasePerUser: 0
  })
}

function removePlanRow(index: number) {
  form.plans.splice(index, 1)
}

function onPlanChange(index: number) {
  const row = form.plans[index]
  if (!row.planId) {
    row._originalPriceYuan = null
    return
  }
  // 校验重复
  const dup = form.plans.findIndex((p: any, i: number) => i !== index && p.planId === row.planId && p.periodType === row.periodType)
  if (dup >= 0) {
    ElMessage.warning('该套餐的此周期已添加')
    row.planId = null
    row._originalPriceYuan = null
    return
  }
  refreshOriginalPrice(row)
  // 默认活动价 = 原价（用户可调低）
  if (row._originalPriceYuan && row.activityPriceYuan === 0) {
    row.activityPriceYuan = row._originalPriceYuan
    row.activityPriceCent = Math.round(row._originalPriceYuan * 100)
  }
}

function onPeriodChange(index: number) {
  const row = form.plans[index]
  // 校验重复
  if (row.planId) {
    const dup = form.plans.findIndex((p: any, i: number) => i !== index && p.planId === row.planId && p.periodType === row.periodType)
    if (dup >= 0) {
      ElMessage.warning('该套餐的此周期已添加')
      row.periodType = row.periodType === 'month' ? 'quarter' : 'month'
      return
    }
  }
  refreshOriginalPrice(row)
}

function refreshOriginalPrice(row: PlanRow) {
  if (!row.planId) {
    row._originalPriceYuan = null
    return
  }
  const bp = availablePlans.value.find(p => p.id === row.planId)
  if (!bp) {
    row._originalPriceYuan = null
    return
  }
  const cent = row.periodType === 'quarter'
    ? Number(bp.priceQuarterCent) || 0
    : row.periodType === 'year'
      ? Number(bp.priceYearCent) || 0
      : Number(bp.priceMonthCent) || 0
  row._originalPriceYuan = cent > 0 ? Number((cent / 100).toFixed(2)) : null
}

function onActivityPriceChange(row: PlanRow) {
  row.activityPriceCent = Math.round((Number(row.activityPriceYuan) || 0) * 100)
  if (row._originalPriceYuan && row.activityPriceYuan > row._originalPriceYuan) {
    ElMessage.warning(`活动价不能高于原价 ¥${row._originalPriceYuan}`)
  }
}

async function loadAvailablePlans() {
  try {
    availablePlans.value = await fetchEnabledBillingPlans()
  } catch (error: any) {
    ElMessage.error(error?.message || '会员套餐列表读取失败')
    availablePlans.value = []
  }
}

async function onSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (!form.isLongTerm && !form.endTime) {
    ElMessage.warning('请选择结束时间或开启长期活动')
    return
  }
  if (!form.isLongTerm && form.endTime && form.startTime >= form.endTime) {
    ElMessage.warning('结束时间必须晚于开始时间')
    return
  }
  if (!form.plans || form.plans.length === 0) {
    ElMessage.warning('请至少添加一个套餐配置')
    return
  }
  // 校验套餐配置
  for (const [i, p] of form.plans.entries()) {
    if (!p.planId) {
      ElMessage.warning(`第 ${i + 1} 个套餐配置未选择套餐`)
      return
    }
    if (p.activityPriceCent < 0) {
      ElMessage.warning(`第 ${i + 1} 个套餐配置活动价不能为负数`)
      return
    }
    if (p._originalPriceYuan && p.activityPriceYuan > p._originalPriceYuan) {
      ElMessage.warning(`第 ${i + 1} 个套餐配置活动价不能高于原价`)
      return
    }
    if (p.quota < 0) {
      ElMessage.warning(`第 ${i + 1} 个套餐配置名额不能为负数`)
      return
    }
  }
  saving.value = true
  try {
    const payload = {
      activityName: form.activityName?.trim(),
      activityCode: form.activityCode?.trim(),
      description: form.description?.trim() || undefined,
      startTime: form.startTime,
      endTime: form.isLongTerm ? form.endTime || '9999-12-31T23:59:59' : form.endTime,
      isLongTerm: form.isLongTerm,
      autoCloseOnEnd: form.autoCloseOnEnd,
      noticeTitle: form.noticeTitle?.trim() || undefined,
      noticeContent: form.noticeContent?.trim() || undefined,
      noticeVisible: form.noticeVisible,
      noticePosition: form.noticePosition,
      noticeIcon: form.noticeIcon,
      plans: form.plans.map((p: PlanRow) => ({
        planId: p.planId,
        periodType: p.periodType,
        activityPriceCent: p.activityPriceCent,
        quota: p.quota,
        sortOrder: p.sortOrder,
        activityTag: p.activityTag?.trim() || undefined,
        showSoldCount: p.showSoldCount,
        showQuota: p.showQuota,
        showRemain: p.showRemain,
        allowRepurchase: p.allowRepurchase,
        maxPurchasePerUser: p.maxPurchasePerUser
      }))
    }
    if (isEdit.value) {
      await updatePromotionActivity(form.id, payload)
    } else {
      await createPromotionActivity(payload)
    }
    visible.value = false
    emit('saved')
  } catch (error: any) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function handleBeforeClose(done: () => void) {
  if (saving.value) {
    ElMessage.warning('正在保存，请稍候')
    return
  }
  done()
}

watch(
  () => props.modelValue,
  async v => {
    if (v) {
      await loadAvailablePlans()
      if (props.detail) {
        loadDetail(props.detail)
      } else {
        resetForm()
      }
    }
  }
)
</script>

<style scoped lang="scss">
.form-tip {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.plan-tip {
  padding: 16px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.empty-state {
  padding: 24px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.switch-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
}

.muted {
  color: var(--el-text-color-secondary);
}

.small-text {
  font-size: 11px;
  margin-top: 2px;
}
</style>
