<template>
  <div class="admin-page">
    <ElCard shadow="never" class="hero-card">
      <div class="page-title-row">
        <div>
          <h2>开源版广告套餐</h2>
          <p>这里配置开源版首页轮播广告与文字广告的真实价格、展示文案和权益说明，前台申请页会实时读取。</p>
        </div>
        <div class="toolbar-actions">
          <ElButton type="primary" :disabled="!canMutate" @click="openDialog()">
            <ElIcon><Plus /></ElIcon>
            新增广告套餐
          </ElButton>
        </div>
      </div>

      <div v-if="canMutate" class="summary-grid">
        <div class="summary-card">
          <strong>{{ list.length }}</strong>
          <span>套餐总数</span>
        </div>
        <div class="summary-card">
          <strong>{{ enabledCount }}</strong>
          <span>当前启用</span>
        </div>
        <div class="summary-card">
          <strong>{{ recommendedCount }}</strong>
          <span>推荐套餐</span>
        </div>
      </div>
    </ElCard>

    <AdminDataState
      v-if="listState === 'loading'"
      state="loading"
      title="正在加载广告套餐"
      :retryable="false"
    />
    <AdminDataState
      v-else-if="listState === 'error'"
      state="error"
      title="广告套餐暂时不可用"
      description="无法确认线上套餐和价格，统计与写入操作已暂停。"
      @retry="loadList"
    />
    <ElCard v-else shadow="never" class="cards-card">
      <div class="section-head">
        <div>
          <h3>套餐列表</h3>
          <span>请至少保留一个轮播广告套餐和一个文字广告套餐，方便开源版申请页自动展示。</span>
        </div>
      </div>

      <div v-if="loading" class="loading-state">正在加载广告套餐...</div>
      <div v-else-if="!list.length" class="empty-state">
        <ElEmpty description="暂无广告套餐配置" />
      </div>
      <div v-else class="plan-grid">
        <article v-for="item in list" :key="item.id" class="plan-card">
          <div class="plan-head">
            <div>
              <small>{{ positionLabel(item.positionType) }}</small>
              <h3>{{ item.title }}</h3>
            </div>
            <div class="head-tags">
              <ElTag v-if="item.recommended" type="success">推荐</ElTag>
              <ElTag :type="item.enabled ? 'primary' : 'info'">{{ item.enabled ? '启用' : '停用' }}</ElTag>
            </div>
          </div>
          <div class="price-block">
            <strong>{{ item.priceYuan ? `￥${item.priceYuan}` : '￥0' }}</strong>
            <span>{{ item.priceLabel || '未填写前台价签' }}</span>
          </div>
          <p class="plan-desc">{{ item.description || '请补充套餐说明。' }}</p>
          <ul class="benefit-list">
            <li v-for="benefit in item.benefits" :key="benefit">{{ benefit }}</li>
          </ul>
          <div class="plan-meta">
            <span>编码：{{ item.code }}</span>
            <span>排序：{{ item.sortOrder }}</span>
          </div>
          <div class="plan-actions">
            <ElButton size="small" type="primary" plain @click="openDialog(item)">编辑</ElButton>
            <ElButton size="small" type="danger" plain @click="handleDelete(item)">删除</ElButton>
          </div>
        </article>
      </div>
    </ElCard>

    <ElDialog v-model="dialogVisible" :title="isEdit ? '编辑广告套餐' : '新增广告套餐'" width="760px" destroy-on-close>
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="110px" label-position="right">
        <div class="form-grid">
          <ElFormItem label="套餐编码" prop="code">
            <ElInput v-model="form.code" maxlength="80" placeholder="例如：home-carousel / sidebar-text" />
          </ElFormItem>
          <ElFormItem label="广告位类型" prop="positionType">
            <ElSelect v-model="form.positionType">
              <ElOption label="首页轮播广告" value="home_carousel" />
              <ElOption label="首页文字广告" value="sidebar_text" />
            </ElSelect>
          </ElFormItem>
        </div>

        <ElFormItem label="套餐标题" prop="title">
          <ElInput v-model="form.title" maxlength="80" show-word-limit />
        </ElFormItem>

        <div class="form-grid">
          <ElFormItem label="真实价格" prop="priceYuan">
            <ElInput v-model="form.priceYuan" maxlength="20" placeholder="例如：399" />
          </ElFormItem>
          <ElFormItem label="前台价签" prop="priceLabel">
            <ElInput v-model="form.priceLabel" maxlength="80" show-word-limit placeholder="例如：￥399 / 7天" />
          </ElFormItem>
        </div>

        <ElFormItem label="套餐说明" prop="description">
          <ElInput v-model="form.description" type="textarea" :rows="4" maxlength="300" show-word-limit />
        </ElFormItem>
        <ElFormItem label="权益列表" prop="benefitsText">
          <ElInput
            v-model="form.benefitsText"
            type="textarea"
            :rows="6"
            placeholder="每行一条权益说明"
          />
          <div class="form-tip">这些内容会展示在开源版申请页，建议写运营和投放收益点。</div>
        </ElFormItem>

        <div class="form-grid">
          <ElFormItem label="排序值" prop="sortOrder">
            <ElInputNumber v-model="form.sortOrder" :min="0" :max="999" style="width: 180px" />
          </ElFormItem>
          <ElFormItem label="推荐套餐" prop="recommended">
            <ElSwitch v-model="form.recommended" active-text="推荐" inactive-text="普通" />
          </ElFormItem>
        </div>

        <ElFormItem label="启用状态" prop="enabled">
          <ElSwitch v-model="form.enabled" active-text="启用" inactive-text="停用" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="handleSave">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  deleteOpenSourceAdPlan,
  getOpenSourceAdPlans,
  saveOpenSourceAdPlan,
  updateOpenSourceAdPlan,
  type OpenSourceAdPlanItem,
  type OpenSourceAdPositionType,
} from '@/api/open-source-ads'

defineOptions({ name: 'AdminOpenSourceAdPlansPage' })

type AdPlanFormState = OpenSourceAdPlanItem & {
  benefitsText: string
}

const list = ref<OpenSourceAdPlanItem[]>([])
const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const saving = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()

const defaultForm = (): AdPlanFormState => ({
  code: '',
  positionType: 'home_carousel',
  title: '',
  description: '',
  priceLabel: '',
  priceYuan: '',
  priceCent: 0,
  benefits: [],
  benefitsText: '',
  recommended: false,
  enabled: true,
  sortOrder: 0,
})

const form = reactive<AdPlanFormState>(defaultForm())

const rules: FormRules = {
  code: [{ required: true, message: '请输入套餐编码', trigger: 'blur' }],
  title: [{ required: true, message: '请输入套餐标题', trigger: 'blur' }],
  positionType: [{ required: true, message: '请选择广告位类型', trigger: 'change' }],
  priceYuan: [{ required: true, message: '请输入真实价格', trigger: 'blur' }],
  priceLabel: [{ required: true, message: '请输入前台价签', trigger: 'blur' }],
  benefitsText: [{
    validator: (_rule, value, callback) => {
      const rows = parseBenefits(String(value || ''))
      if (!rows.length) {
        callback(new Error('请至少填写一条权益说明'))
        return
      }
      callback()
    },
    trigger: 'blur',
  }],
}

const enabledCount = computed(() => list.value.filter(item => item.enabled).length)
const recommendedCount = computed(() => list.value.filter(item => item.recommended).length)
const canMutate = computed(() => listState.value === 'ready' || listState.value === 'empty')

function positionLabel(positionType: OpenSourceAdPositionType) {
  return positionType === 'home_carousel' ? '首页轮播广告' : '首页文字广告'
}

function parseBenefits(text: string) {
  return String(text || '')
    .split(/\r?\n/)
    .map(item => item.trim())
    .filter(Boolean)
}

function normalizePriceYuan(value: string) {
  const text = String(value || '').trim().replace(/[^\d.]/g, '')
  if (!text) return ''
  const number = Number(text)
  if (!Number.isFinite(number) || number <= 0) return ''
  return String(number % 1 === 0 ? number.toFixed(0) : number.toFixed(2)).replace(/\.00$/, '')
}

function toPriceCent(priceYuan: string) {
  const number = Number(normalizePriceYuan(priceYuan) || 0)
  return Number.isFinite(number) ? Math.round(number * 100) : 0
}

async function loadList() {
  loading.value = true
  listState.value = 'loading'
  try {
    const res = await getOpenSourceAdPlans()
    list.value = res.slice().sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))
    listState.value = list.value.length > 0 ? 'ready' : 'empty'
  } catch {
    list.value = []
    listState.value = 'error'
  } finally {
    loading.value = false
  }
}

function openDialog(row?: OpenSourceAdPlanItem) {
  if (!canMutate.value) return
  isEdit.value = !!row
  if (row) {
    Object.assign(form, {
      id: row.id,
      code: row.code,
      positionType: row.positionType,
      title: row.title,
      description: row.description,
      priceLabel: row.priceLabel,
      priceYuan: String(row.priceYuan || ''),
      priceCent: Number(row.priceCent || 0),
      benefits: row.benefits,
      benefitsText: Array.isArray(row.benefits) ? row.benefits.join('\n') : '',
      recommended: row.recommended,
      enabled: row.enabled,
      sortOrder: row.sortOrder,
    })
  } else {
    Object.assign(form, defaultForm())
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!canMutate.value) {
    ElMessage.warning('广告套餐尚未成功读取，当前不能保存')
    return
  }
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const priceYuan = normalizePriceYuan(form.priceYuan || '')
  const priceCent = toPriceCent(priceYuan)
  if (!priceYuan || priceCent <= 0) {
    ElMessage.warning('请输入有效的真实价格')
    return
  }

  saving.value = true
  try {
    const payload: OpenSourceAdPlanItem = {
      ...form,
      priceYuan,
      priceCent,
      priceLabel: form.priceLabel.trim() || `￥${priceYuan}`,
      benefits: parseBenefits(form.benefitsText),
    }
    if (isEdit.value && !form.id) {
      ElMessage.error('套餐标识缺失，无法安全更新')
      return
    }
    if (isEdit.value) {
      await updateOpenSourceAdPlan(payload)
    } else {
      await saveOpenSourceAdPlan(payload)
    }
    ElMessage.success(isEdit.value ? '广告套餐更新成功' : '广告套餐创建成功')
    dialogVisible.value = false
    await loadList()
  } catch (error: any) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: OpenSourceAdPlanItem) {
  if (!row.id || !canMutate.value) {
    ElMessage.error('套餐标识缺失或列表不可用，无法安全删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      '确定删除这个广告套餐吗？如果前台仍在使用该编码，申请页会看不到这个档位。',
      '确认删除',
      { type: 'warning' }
    )
    await deleteOpenSourceAdPlan(row.id)
    ElMessage.success('删除成功')
    await loadList()
  } catch {
    // ignore cancel
  }
}

onMounted(() => loadList())
</script>

<style scoped>
.admin-page { padding: 4px; }
.hero-card, .cards-card { border-radius: 18px; }
.page-title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 22px; font-weight: 800; }
.page-title-row p { margin: 0; color: var(--art-gray-500); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; }
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
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
.section-head h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #17315c;
}
.section-head span {
  display: block;
  margin-top: 6px;
  color: var(--art-gray-500);
  font-size: 12px;
}
.loading-state,
.empty-state {
  padding: 32px 0;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.plan-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 260px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid var(--el-border-color-lighter);
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}
.plan-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.plan-head small {
  color: var(--art-gray-500);
  font-size: 12px;
  font-weight: 700;
}
.plan-head h3 {
  margin: 6px 0 0;
  color: #17315c;
  font-size: 18px;
  line-height: 1.3;
}
.head-tags {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.price-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.price-block strong {
  color: #1d4ed8;
  font-size: 28px;
  line-height: 1;
}
.price-block span {
  color: var(--art-gray-500);
  font-size: 12px;
}
.plan-desc {
  margin: 0;
  color: #4b5563;
  line-height: 1.8;
}
.benefit-list {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  line-height: 1.8;
}
.benefit-list li + li {
  margin-top: 6px;
}
.plan-meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: auto;
  color: var(--art-gray-500);
  font-size: 12px;
}
.plan-actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 18px;
}
.form-tip {
  margin-top: 8px;
  color: var(--art-gray-500);
  font-size: 12px;
  line-height: 1.7;
}
@media (max-width: 960px) {
  .summary-grid,
  .plan-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
