import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const stateComponentPath = path.resolve('src/components/business/admin-data-state/index.vue')

assert(fs.existsSync(stateComponentPath), '管理端必须提供统一的可重试数据状态组件')

const stateComponent = fs.readFileSync(stateComponentPath, 'utf8')

for (const state of ['loading', 'empty', 'error', 'degraded']) {
  assert(stateComponent.includes(`'${state}'`), `统一数据状态组件必须支持 ${state} 状态`)
}

assert(stateComponent.includes("emit('retry')"), '错误状态必须向页面暴露重试操作')
assert(stateComponent.includes('role="alert"'), '错误或降级信息必须具备可访问的告警语义')

const settingsPage = fs.readFileSync(path.resolve('src/views/admin/ops/settings/index.vue'), 'utf8')
assert(settingsPage.includes('<AdminDataState'), '系统配置加载失败时必须展示统一错误态')
assert(
  settingsPage.includes(":disabled=\"configState !== 'ready'\""),
  '系统配置成功读取前必须禁用保存，避免默认值覆盖线上配置'
)
assert(
  settingsPage.includes("if (configState.value !== 'ready')"),
  '系统配置保存函数必须在数据未成功读取时再次阻止写入'
)

const pricingPage = fs.readFileSync(path.resolve('src/views/admin/ai-pricing/index.vue'), 'utf8')
assert(pricingPage.includes('<AdminDataState'), '费用设置请求失败时必须展示统一错误态')
assert(pricingPage.includes("listState === 'error'"), '价格列表失败必须与真实空列表区分')
assert(pricingPage.includes(":disabled=\"listState !== 'ready'\""), '价格列表读取失败时必须禁用新增配置')
assert(
  pricingPage.includes("if (!p || !Array.isArray(p.records))"),
  '价格接口返回空值或畸形结构时必须进入失败态，不能当作 0 条'
)
for (const fallback of [
  'summary.enabledModels || 0',
  'summary.todayChargeTokens || 0',
  'summary.lowBalanceUsers || 0'
]) {
  assert(!pricingPage.includes(fallback), `计费汇总失败时不能用 0 冒充真实值：${fallback}`)
}

const paymentPage = fs.readFileSync(path.resolve('src/views/admin/payment-config/index.vue'), 'utf8')
assert(paymentPage.includes('<AdminDataState'), '支付配置各数据源失败时必须展示统一错误态')
for (const state of ['configState', 'planState', 'orderState']) {
  assert(paymentPage.includes(`${state} === 'error'`), `${state} 失败必须与真实空数据区分`)
}
assert(paymentPage.includes(":disabled=\"configState !== 'ready'\""), '支付通道未读取成功前必须禁用新增和沙箱写入')
assert(paymentPage.includes(":disabled=\"planState !== 'ready'\""), '充值套餐未读取成功前必须禁用新增')

const modelConfigPage = fs.readFileSync(path.resolve('src/views/admin/model-config/index.vue'), 'utf8')
const modelConfigForm = fs.readFileSync(path.resolve('src/views/admin/model-config/ModelConfigForm.vue'), 'utf8')
for (const mojibake of ['妯″', '鍙', '鏍￠']) {
  assert(!modelConfigPage.includes(mojibake), `模型配置不能包含用户可见乱码：${mojibake}`)
}
assert.equal(
  (modelConfigPage.match(/prop: 'providerDocText'/g) || []).length,
  1,
  '模型说明正文配置项不能重复渲染'
)
assert(modelConfigForm.includes('<AdminDataState'), '模型配置读取失败时必须显示可重试错误状态')
assert(modelConfigForm.includes("loadState.value !== 'ready'"), '模型配置未成功读取前必须禁止写入和测试')
assert(modelConfigForm.includes("loadState.value = 'error'"), '模型配置请求失败不得保留默认表单伪装为真实配置')

const dashboardPage = fs.readFileSync(path.resolve('src/views/admin/module/index.vue'), 'utf8')
assert(dashboardPage.includes('<AdminDataState'), '仪表盘必须展示统一的加载、空和失败状态')
for (const state of ['loading', 'empty', 'degraded', 'unavailable']) {
  assert(dashboardPage.includes(`dashboardState.status === '${state}'`), `仪表盘必须区分 ${state} 状态`)
}
assert(dashboardPage.includes('Promise.allSettled'), '仪表盘附加监控请求必须保留分数据源失败信息')
assert(!dashboardPage.includes('getAiMonitor({ days }).catch(() => ({}))'), 'AI 监控失败不能静默伪装为空数据')

for (const [label, relativePath] of [
  ['商业版首页轮播', 'src/views/admin/carousel/index.vue'],
  ['开源版首页轮播', 'src/views/admin/open-source/home/index.vue']
] as const) {
  const carouselPage = fs.readFileSync(path.resolve(relativePath), 'utf8')
  assert(
    carouselPage.includes(':disabled="configState !== \'ready\'"'),
    `${label}成功读取前必须禁用保存，避免默认配置被误写入`
  )
  assert(
    carouselPage.includes('v-if="configState === \'ready\'" class="summary-grid"'),
    `${label}读取失败时不得用默认表单值冒充线上轮播统计`
  )
  assert(
    carouselPage.includes("if (configState.value !== 'ready')"),
    `${label}保存函数必须保留数据状态二次校验`
  )
}

const systemMenuPage = fs.readFileSync(path.resolve('src/views/system/menu/index.vue'), 'utf8')
const systemMenuDialog = fs.readFileSync(
  path.resolve('src/views/system/menu/modules/menu-dialog.vue'),
  'utf8'
)
assert(systemMenuPage.includes(':disabled="!canMutate"'), '菜单列表未成功读取前必须禁用新增')
assert(systemMenuPage.includes('const canMutate = computed'), '菜单写入能力必须由真实列表状态统一计算')
assert(systemMenuPage.includes('if (!canMutate.value)'), '菜单保存函数必须再次校验写入状态')
assert(systemMenuPage.includes(':submitting="menuSaving"'), '菜单弹窗必须展示真实保存进度并阻止重复提交')
assert(
  !systemMenuDialog.includes("ElMessage.success(`${isEdit.value ? '编辑' : '新增'}成功`)"),
  '菜单弹窗不得在后端确认前自行宣称保存成功'
)
assert(systemMenuDialog.includes(':loading="submitting"'), '菜单弹窗提交按钮必须绑定真实保存状态')

console.log('admin-truthful-state-contract: ok')
