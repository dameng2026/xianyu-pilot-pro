<template>
  <div class="admin-page">
    <ElCard shadow="never" class="hero-card">
      <div class="page-title-row">
        <div>
          <h2>开源版首页轮播</h2>
          <p>维护开源版前台首页首屏轮播。数据会写入商业版后台的开源版专属配置，再通过 bridge 接口提供给开源版读取。</p>
        </div>
        <div class="toolbar-actions">
          <ElButton :disabled="loading || saving" @click="loadConfig">重新加载</ElButton>
          <ElButton
            type="primary"
            :loading="saving"
            :disabled="configState !== 'ready'"
            @click="handleSave"
          >保存开源版轮播</ElButton>
        </div>
      </div>

      <div v-if="configState === 'ready'" class="summary-grid">
        <div class="summary-card">
          <strong>{{ form.coverItems.length }}</strong>
          <span>轮播图片数</span>
        </div>
        <div class="summary-card">
          <strong>{{ enabledCoverCount }}</strong>
          <span>启用中的图片</span>
        </div>
        <div class="summary-card summary-card-wide">
          <strong>{{ primaryLinkText }}</strong>
          <span>当前主跳转链接</span>
        </div>
      </div>

      <div class="bridge-tip">
        说明：这里维护的是 <b>开源版专属首页轮播</b>，不会改动商业版自己的首页轮播配置。
      </div>
    </ElCard>

    <AdminDataState
      v-if="configState === 'loading'"
      state="loading"
      title="正在加载开源版轮播配置"
      :retryable="false"
    />
    <AdminDataState
      v-else-if="configState === 'error'"
      state="error"
      title="开源版轮播配置暂时不可用"
      description="无法确认线上轮播，编辑、上传和保存已暂停，避免默认值覆盖真实配置。"
      @retry="loadConfig"
    />

    <div v-else class="page-grid">
      <ElCard shadow="never" class="preview-card">
        <div class="section-head">
          <div>
            <h3>开源版前台预览</h3>
            <span>按封面顺序轮播，点击缩略图可切换预览</span>
          </div>
          <ElTag type="info">{{ previewSlides.length }} 张可展示</ElTag>
        </div>

        <div v-if="activePreview" class="preview-stage">
          <div class="preview-main">
            <img class="preview-image" :src="resolveImage(activePreview.imageUrl)" :alt="activePreview.title || form.title || '开源版首页轮播'" />
            <div class="preview-overlay">
              <strong>{{ activePreview.title || form.title || '开源版首页轮播' }}</strong>
              <p>{{ activePreview.description || form.description || '开源版首页首屏轮播图' }}</p>
            </div>
          </div>

          <div class="thumb-list">
            <button
              v-for="(slide, index) in previewSlides"
              :key="slide.id || slide.imageUrl || index"
              type="button"
              :class="['thumb-item', { active: activePreviewIndex === index }]"
              @click="activePreviewIndex = index"
            >
              <img :src="resolveImage(slide.imageUrl)" :alt="slide.title || `轮播图 ${index + 1}`" />
              <span>{{ slide.title || `轮播图 ${index + 1}` }}</span>
            </button>
          </div>
        </div>

        <ElEmpty v-else description="请先添加至少一张可用的轮播图" />
      </ElCard>

      <ElCard shadow="never" class="editor-card">
        <div class="section-head">
          <div>
            <h3>轮播内容编辑</h3>
            <span>保存后，开源版前台会通过商业版 bridge 读取这组最新配置</span>
          </div>
        </div>

        <ElForm ref="formRef" :model="form" :rules="rules" label-width="110px" label-position="right" v-loading="loading">
          <div class="form-grid">
            <ElFormItem label="轮播标题" prop="title">
              <ElInput v-model="form.title" placeholder="例如：开源版首页推荐位" maxlength="60" show-word-limit />
            </ElFormItem>
            <ElFormItem label="排序值" prop="sortOrder">
              <ElInputNumber v-model="form.sortOrder" :min="0" :max="999" style="width: 180px" />
            </ElFormItem>
          </div>

          <ElFormItem label="副标题描述" prop="description">
            <ElInput
              v-model="form.description"
              placeholder="例如：通过商业版后台动态配置开源版首页轮播"
              maxlength="120"
              show-word-limit
            />
          </ElFormItem>

          <ElFormItem label="启用状态" prop="enabled">
            <ElSwitch v-model="form.enabled" active-text="启用" inactive-text="禁用" />
          </ElFormItem>

          <ElFormItem label="轮播图片" prop="coverItems">
            <div class="cover-editor">
              <div class="cover-editor-head">
                <div>
                  <strong>多封面图配置</strong>
                  <span>开源版前台会按下方顺序逐张轮播，第一张可用图片会作为主图和主链接</span>
                </div>
                <ElButton type="primary" plain @click="addCoverItem">新增轮播图</ElButton>
              </div>

              <div v-for="(cover, index) in form.coverItems" :key="cover.id" class="cover-editor-card">
                <div class="cover-card-head">
                  <div>
                    <strong>轮播图 {{ index + 1 }}</strong>
                    <span>{{ cover.sourceType === 'upload' ? '文件上传' : '图片地址' }}</span>
                  </div>
                  <div class="cover-card-actions">
                    <ElButton size="small" :disabled="index === 0" @click="moveCover(index, -1)">上移</ElButton>
                    <ElButton size="small" :disabled="index === form.coverItems.length - 1" @click="moveCover(index, 1)">下移</ElButton>
                    <ElButton size="small" type="danger" link :disabled="form.coverItems.length === 1" @click="removeCover(index)">删除</ElButton>
                  </div>
                </div>

                <div class="cover-card-grid">
                  <ElFormItem label="来源方式" :prop="`coverItems.${index}.sourceType`" label-width="88px">
                    <ElRadioGroup v-model="cover.sourceType">
                      <ElRadioButton label="upload">文件上传</ElRadioButton>
                      <ElRadioButton label="url">地址输入</ElRadioButton>
                    </ElRadioGroup>
                  </ElFormItem>

                  <ElFormItem label="封面标题" :prop="`coverItems.${index}.title`" label-width="88px">
                    <ElInput v-model="cover.title" placeholder="可选，前台覆盖展示文案" maxlength="60" show-word-limit />
                  </ElFormItem>

                  <ElFormItem label="封面描述" :prop="`coverItems.${index}.description`" label-width="88px" class="full-row">
                    <ElInput v-model="cover.description" placeholder="可选，前台覆盖展示副文案" maxlength="120" show-word-limit />
                  </ElFormItem>

                  <ElFormItem label="图片上传" label-width="88px" class="full-row">
                    <div class="upload-area">
                      <div v-if="cover.imageUrl" class="upload-preview">
                        <ElImage :src="resolveImage(cover.imageUrl)" fit="cover" class="upload-preview-image" />
                        <ElButton size="small" type="danger" plain @click="clearCoverImage(index)">移除</ElButton>
                      </div>
                      <ElUpload
                        :show-file-list="false"
                        :before-upload="beforeImageUpload"
                        :http-request="(options) => handleImageUpload(index, options)"
                        accept="image/png, image/jpeg"
                      >
                        <ElButton type="primary" plain>
                          <ElIcon><Upload /></ElIcon>
                          选择文件上传
                        </ElButton>
                      </ElUpload>
                      <ElButton plain :loading="urlImportingIndex === index" @click="handleImportFromUrl(index)">
                        从地址导入
                      </ElButton>
                    </div>
                  </ElFormItem>

                  <ElFormItem
                    label="图片地址"
                    :prop="`coverItems.${index}.imageUrl`"
                    :rules="[{ required: true, message: '请上传图片或输入图片地址', trigger: 'blur' }]"
                    label-width="88px"
                    class="full-row"
                  >
                    <ElInput v-model="cover.imageUrl" placeholder="支持输入外部图片 URL，或通过上传自动回填" />
                  </ElFormItem>

                  <ElFormItem label="跳转链接" :prop="`coverItems.${index}.linkUrl`" label-width="88px" class="full-row">
                    <ElInput v-model="cover.linkUrl" placeholder="点击该封面图后的跳转 URL，可为空" />
                  </ElFormItem>

                  <ElFormItem label="排序值" :prop="`coverItems.${index}.sortOrder`" label-width="88px">
                    <ElInputNumber v-model="cover.sortOrder" :min="0" :max="999" style="width: 160px" />
                  </ElFormItem>

                  <ElFormItem label="是否启用" :prop="`coverItems.${index}.enabled`" label-width="88px">
                    <ElSwitch v-model="cover.enabled" active-text="启用" inactive-text="禁用" />
                  </ElFormItem>
                </div>
              </div>
            </div>
          </ElFormItem>
        </ElForm>
      </ElCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadRequestOptions } from 'element-plus'
import {
  deleteOpenSourceHomeCarousel,
  getOpenSourceHomeCarouselList,
  saveOpenSourceHomeCarousel,
  updateOpenSourceHomeCarousel,
  type OpenSourceHomeCarouselItem
} from '@/api/open-source-content'
import { uploadCarouselImage, uploadCarouselImageFromUrl } from '@/api/carousel'
import {
  buildCarouselSavePlan,
  buildUnifiedCarouselConfig,
  createEmptyCarouselCover,
  type UnifiedCarouselConfig
} from '../../carousel/page-model'

defineOptions({ name: 'AdminOpenSourceHomeCarouselPage' })

const loading = ref(false)
const configState = ref<'loading' | 'ready' | 'error'>('loading')
const saving = ref(false)
const formRef = ref<FormInstance>()
const urlImportingIndex = ref<number | null>(null)
const activePreviewIndex = ref(0)

const form = reactive<UnifiedCarouselConfig>(buildUnifiedCarouselConfig([]))

const rules: FormRules = {
  title: [{ required: true, message: '请输入轮播标题', trigger: 'blur' }],
  coverItems: [{
    validator: (_rule, value, callback) => {
      const items = Array.isArray(value) ? value : []
      if (!items.length) {
        callback(new Error('请至少配置 1 张轮播图'))
        return
      }
      if (!items.some(item => String(item.imageUrl || '').trim())) {
        callback(new Error('请至少上传或填写 1 张轮播图地址'))
        return
      }
      callback()
    },
    trigger: 'change'
  }]
}

const previewSlides = computed(() => {
  return (form.coverItems || [])
    .filter(item => item.enabled !== false && String(item.imageUrl || '').trim())
    .slice()
    .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))
})

const activePreview = computed(() => previewSlides.value[activePreviewIndex.value] || previewSlides.value[0] || null)
const enabledCoverCount = computed(() => (form.coverItems || []).filter(item => item.enabled !== false).length)
const primaryLinkText = computed(() => activePreview.value?.linkUrl || '未设置跳转链接')

watch(previewSlides, (slides) => {
  if (activePreviewIndex.value >= slides.length) {
    activePreviewIndex.value = 0
  }
})

function resolveImage(imageUrl: string) {
  const value = String(imageUrl || '').trim()
  if (!value) return ''
  if (/^(https?:)?\/\//.test(value) || value.startsWith('/')) return value
  return `/${value.replace(/^\/+/, '')}`
}

function syncPrimaryFields() {
  const first = previewSlides.value[0] || form.coverItems[0]
  form.imageUrl = first?.imageUrl || ''
  form.linkUrl = first?.linkUrl || ''
  form.sourceType = first?.sourceType || 'upload'
}

async function loadConfig() {
  loading.value = true
  configState.value = 'loading'
  try {
    const res = await getOpenSourceHomeCarouselList()
    const next = buildUnifiedCarouselConfig(Array.isArray(res) ? res : [])
    Object.assign(form, next)
    syncPrimaryFields()
    configState.value = 'ready'
  } catch {
    Object.assign(form, buildUnifiedCarouselConfig([]))
    configState.value = 'error'
  } finally {
    loading.value = false
  }
}

function addCoverItem() {
  form.coverItems.push(createEmptyCarouselCover(form.coverItems.length))
}

function removeCover(index: number) {
  if (form.coverItems.length === 1) return
  form.coverItems.splice(index, 1)
  reindexCoverItems()
}

function moveCover(index: number, direction: number) {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= form.coverItems.length) return
  const [item] = form.coverItems.splice(index, 1)
  form.coverItems.splice(targetIndex, 0, item)
  reindexCoverItems()
}

function reindexCoverItems() {
  form.coverItems = form.coverItems.map((item, index) => ({
    ...item,
    sortOrder: index
  }))
  syncPrimaryFields()
}

function clearCoverImage(index: number) {
  form.coverItems[index].imageUrl = ''
  syncPrimaryFields()
}

async function handleSave() {
  if (configState.value !== 'ready') {
    ElMessage.warning('开源版轮播尚未成功读取，当前不能保存')
    return
  }
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const savePlan = buildCarouselSavePlan(form)
  if (!savePlan.payload.coverItems?.length) {
    ElMessage.error('请至少配置 1 张有效轮播图')
    return
  }

  saving.value = true
  try {
    let saved: OpenSourceHomeCarouselItem
    if (form.id) {
      saved = await updateOpenSourceHomeCarousel(savePlan.payload)
    } else {
      saved = await saveOpenSourceHomeCarousel(savePlan.payload)
    }

    if (savePlan.deleteIds.length > 0) {
      await Promise.all(savePlan.deleteIds.map(id => deleteOpenSourceHomeCarousel(id)))
    }

    ElMessage.success('开源版轮播保存成功')
    Object.assign(form, buildUnifiedCarouselConfig([saved]))
    await loadConfig()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function beforeImageUpload(file: File) {
  const validType = ['image/png', 'image/jpeg'].includes(file.type)
  if (!validType) {
    ElMessage.error('本地上传仅支持可完整解码的 PNG、JPEG 格式；其他格式请先转换')
    return false
  }
  if (file.size / 1024 / 1024 > 5) {
    ElMessage.error('图片大小不能超过 5MB')
    return false
  }
  return true
}

async function handleImageUpload(index: number, options: UploadRequestOptions) {
  if (configState.value !== 'ready') {
    ElMessage.warning('开源版轮播尚未成功读取，当前不能上传图片')
    return
  }
  try {
    const res = await uploadCarouselImage(options.file)
    if (res?.url) {
      form.coverItems[index].imageUrl = res.url
      form.coverItems[index].sourceType = 'upload'
      syncPrimaryFields()
      ElMessage.success('图片上传成功')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
  }
}

async function handleImportFromUrl(index: number) {
  if (configState.value !== 'ready') {
    ElMessage.warning('开源版轮播尚未成功读取，当前不能导入图片')
    return
  }
  const rawUrl = String(form.coverItems[index]?.imageUrl || '').trim()
  if (!rawUrl) {
    ElMessage.warning('请先填写图片地址，再执行导入')
    return
  }
  if (!/^https?:\/\//i.test(rawUrl)) {
    ElMessage.warning('仅支持导入 http 或 https 图片地址')
    return
  }
  urlImportingIndex.value = index
  try {
    const res = await uploadCarouselImageFromUrl(rawUrl)
    if (res?.url) {
      form.coverItems[index].imageUrl = res.url
      form.coverItems[index].sourceType = 'url'
      syncPrimaryFields()
      ElMessage.success('图片地址导入成功')
    } else {
      ElMessage.error('地址导入失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '地址导入失败')
  } finally {
    urlImportingIndex.value = null
  }
}

onMounted(() => loadConfig())
</script>

<style scoped>
.admin-page { padding: 4px; }
.hero-card, .preview-card, .editor-card { border-radius: 18px; }
.page-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 22px; font-weight: 800; }
.page-title-row p { margin: 0; color: var(--art-gray-500); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
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
.summary-card-wide strong {
  font-size: 15px;
  word-break: break-all;
}
.bridge-tip {
  margin-top: 14px;
  border-radius: 14px;
  padding: 12px 14px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 13px;
}
.page-grid {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
  align-items: start;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
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
.preview-stage {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.preview-main {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid #dbe7ff;
  background: linear-gradient(180deg, #f5f8ff 0%, #eef4ff 100%);
  aspect-ratio: 2048 / 646;
}
.preview-image {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.preview-overlay {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 18px;
  border-radius: 16px;
  padding: 14px 16px;
  background: linear-gradient(180deg, rgba(18, 31, 52, 0.02) 0%, rgba(18, 31, 52, 0.68) 100%);
  color: #fff;
}
.preview-overlay strong {
  display: block;
  font-size: 16px;
  font-weight: 800;
}
.preview-overlay p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.92);
}
.thumb-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.thumb-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  padding: 8px;
  background: #fff;
  text-align: left;
}
.thumb-item.active {
  border-color: #5b8def;
  box-shadow: 0 10px 24px rgba(37, 106, 214, 0.1);
}
.thumb-item img {
  width: 100%;
  height: 92px;
  border-radius: 10px;
  object-fit: cover;
  display: block;
}
.thumb-item span {
  display: block;
  margin-top: 8px;
  color: #294166;
  font-size: 12px;
  font-weight: 700;
}
.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 18px;
}
.cover-editor {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.cover-editor-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
}
.cover-editor-head strong { display: block; color: var(--art-gray-900); }
.cover-editor-head span { font-size: 12px; color: var(--art-gray-500); }
.cover-editor-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
  padding: 16px;
  background: #fff;
}
.cover-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}
.cover-card-head strong { display: block; color: var(--art-gray-900); }
.cover-card-head span { font-size: 12px; color: var(--art-gray-500); }
.cover-card-actions { display: flex; align-items: center; gap: 8px; }
.cover-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 18px;
}
.full-row { grid-column: 1 / -1; }
.upload-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.upload-preview {
  display: flex;
  align-items: center;
  gap: 12px;
}
.upload-preview-image {
  width: 180px;
  height: 96px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-light);
}
@media (max-width: 1180px) {
  .page-grid,
  .summary-grid,
  .thumb-list {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 900px) {
  .page-title-row,
  .cover-editor-head {
    flex-direction: column;
    align-items: stretch;
  }
  .form-grid,
  .cover-card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
