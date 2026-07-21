<template>
  <Teleport to="body">
    <transition name="m-uploader-fade">
      <div v-if="visible" class="m-uploader-mask" role="dialog" aria-modal="true" @click.self="onClose">
        <div class="m-uploader-sheet" aria-label="发送图片" role="dialog">
          <div class="m-uploader-header">
            <button type="button" class="m-uploader-close" aria-label="关闭" @click="onClose">
              <MIcon name="x" :size="20" />
            </button>
            <h3>发送图片</h3>
            <button
              type="button"
              class="m-uploader-send"
              :disabled="!canSendAll || uploading"
              @click="onSendAll"
            >
              {{ uploading ? `上传中 ${finishedCount}/${queue.length}` : `发送(${queue.length})` }}
            </button>
          </div>

          <div class="m-uploader-body">
            <div v-if="errorMessage" class="m-uploader-error" role="alert">{{ errorMessage }}</div>

            <div class="m-uploader-grid">
              <div
                v-for="(item, index) in queue"
                :key="item.id"
                class="m-uploader-thumb"
                :class="{ 'is-failed': item.status === 'failed', 'is-uploading': item.status === 'uploading' }"
              >
                <img :src="item.previewUrl" :alt="`图片${index + 1}`" />
                <div v-if="item.status === 'uploading'" class="m-uploader-mask-overlay">
                  <div class="m-uploader-spinner"></div>
                </div>
                <div v-else-if="item.status === 'failed'" class="m-uploader-mask-overlay failed">
                  <MIcon name="info" :size="18" />
                  <span>失败</span>
                </div>
                <button
                  v-if="item.status !== 'uploading'"
                  type="button"
                  class="m-uploader-remove"
                  aria-label="移除图片"
                  @click="removeItem(item.id)"
                >
                  <MIcon name="x" :size="14" />
                </button>
                <div v-if="item.errorMessage" class="m-uploader-thumb-error">{{ item.errorMessage }}</div>
              </div>

              <button
                v-if="queue.length < maxCount"
                type="button"
                class="m-uploader-add"
                @click="triggerPick"
              >
                <MIcon name="plus" :size="24" />
                <span>{{ queue.length === 0 ? '选择图片' : '继续添加' }}</span>
                <small>{{ queue.length }}/{{ maxCount }}</small>
              </button>
            </div>

            <div class="m-uploader-tips">
              <MIcon name="info" :size="12" />
              <span>支持 JPEG/PNG/GIF/WebP，单张不超过 5MB，最多 {{ maxCount }} 张</span>
            </div>

            <div class="m-uploader-actions">
              <button type="button" class="m-uploader-action" @click="triggerPick('camera')">
                <MIcon name="image" :size="20" />
                <span>拍照</span>
              </button>
              <button type="button" class="m-uploader-action" @click="triggerPick('album')">
                <MIcon name="plus" :size="20" />
                <span>从相册选择</span>
              </button>
            </div>
          </div>

          <input
            ref="fileInputRef"
            type="file"
            accept="image/*"
            multiple
            hidden
            @change="onFileChange"
          />
          <input
            ref="cameraInputRef"
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            @change="onFileChange"
          />
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import MIcon from '../MIcon.vue'
import { uploadImage } from '../../api/misc.js'
import { imageUploadValidationMessage } from '../../utils/imageUploadPolicy.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  accountId: { type: Number, default: 0 },
  maxCount: { type: Number, default: 9 },
})

const emit = defineEmits(['close', 'send'])

const fileInputRef = ref(null)
const cameraInputRef = ref(null)
const queue = ref([])
const uploading = ref(false)
const errorMessage = ref('')
let itemSeed = 0

const canSendAll = computed(() => queue.value.some(item => item.status === 'success'))
const finishedCount = computed(() => queue.value.filter(item => item.status === 'success' || item.status === 'failed').length)

function triggerPick(source = 'album') {
  errorMessage.value = ''
  if (source === 'camera') {
    cameraInputRef.value?.click()
  } else {
    fileInputRef.value?.click()
  }
}

function onFileChange(event) {
  const files = Array.from(event?.target?.files || [])
  if (!files.length) return
  errorMessage.value = ''
  const remaining = props.maxCount - queue.value.length
  if (remaining <= 0) {
    errorMessage.value = `最多只能选择 ${props.maxCount} 张图片`
    event.target.value = ''
    return
  }
  const slice = files.slice(0, remaining)
  if (files.length > remaining) {
    errorMessage.value = `已达到上限，仅添加前 ${remaining} 张`
  }
  slice.forEach(file => {
    const validationMessage = imageUploadValidationMessage(file)
    const previewUrl = URL.createObjectURL(file)
    const item = {
      id: `img_${Date.now()}_${++itemSeed}`,
      file,
      previewUrl,
      status: validationMessage ? 'failed' : 'pending',
      imageUrl: '',
      errorMessage: validationMessage || '',
    }
    queue.value.push(item)
  })
  event.target.value = ''
}

async function uploadSingle(item) {
  if (item.status === 'success') return item.imageUrl
  if (!props.accountId) {
    item.status = 'failed'
    item.errorMessage = '账号信息缺失'
    return ''
  }
  item.status = 'uploading'
  item.errorMessage = ''
  try {
    const res = await uploadImage(props.accountId, item.file)
    const data = res?.data
    const imageUrl = data?.imageUrl || data?.url || data?.data?.url || data?.data?.imageUrl || res?.imageUrl || res?.url || ''
    if (!imageUrl) throw new Error('图片上传成功但未返回可发送地址')
    item.imageUrl = imageUrl
    item.status = 'success'
    return imageUrl
  } catch (e) {
    item.status = 'failed'
    item.errorMessage = e?.message || '上传失败'
    return ''
  }
}

async function onSendAll() {
  if (uploading.value) return
  const pending = queue.value.filter(item => item.status === 'pending' || item.status === 'failed')
  if (!pending.length && !canSendAll.value) return
  uploading.value = true
  errorMessage.value = ''
  try {
    // 并发上传（限制并发数 3）
    const CONCURRENCY = 3
    for (let i = 0; i < pending.length; i += CONCURRENCY) {
      const batch = pending.slice(i, i + CONCURRENCY)
      await Promise.all(batch.map(item => uploadSingle(item)))
    }
    const successUrls = queue.value
      .filter(item => item.status === 'success' && item.imageUrl)
      .map(item => item.imageUrl)
    if (!successUrls.length) {
      errorMessage.value = '所有图片上传失败，请重试'
      return
    }
    emit('send', successUrls)
    resetQueue()
  } finally {
    uploading.value = false
  }
}

function removeItem(id) {
  const idx = queue.value.findIndex(item => item.id === id)
  if (idx < 0) return
  const [removed] = queue.value.splice(idx, 1)
  if (removed?.previewUrl) {
    try { URL.revokeObjectURL(removed.previewUrl) } catch { /* ignore */ }
  }
}

function resetQueue() {
  queue.value.forEach(item => {
    if (item.previewUrl) {
      try { URL.revokeObjectURL(item.previewUrl) } catch { /* ignore */ }
    }
  })
  queue.value = []
  errorMessage.value = ''
}

function onClose() {
  if (uploading.value) return
  resetQueue()
  emit('close')
}

onBeforeUnmount(() => {
  resetQueue()
})

defineExpose({ resetQueue })
</script>

<style scoped>
.m-uploader-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: var(--m-mask-modal);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.m-uploader-sheet {
  width: 100%;
  max-width: 100%;
  max-height: 90vh;
  background: var(--m-color-bg-elevated);
  border-top-left-radius: var(--m-radius-2xl);
  border-top-right-radius: var(--m-radius-2xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: env(safe-area-inset-bottom);
  box-shadow: var(--m-shadow-elevated);
}
.m-uploader-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-uploader-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-uploader-close {
  width: var(--m-space-8);
  height: var(--m-space-8);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-bg-subtle);
  border: none;
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.m-uploader-close:active { background: var(--m-color-bg-hover); }
.m-uploader-send {
  min-width: 76px;
  height: var(--m-space-8);
  padding: 0 var(--m-space-3);
  border-radius: var(--m-radius-xl);
  border: none;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}
.m-uploader-send:disabled {
  background: var(--m-color-border);
  color: var(--m-color-text-disabled);
  cursor: not-allowed;
}

.m-uploader-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: var(--m-space-3) var(--m-space-4) var(--m-space-4);
}
.m-uploader-error {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  margin-bottom: var(--m-space-3);
}
.m-uploader-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-space-2);
}
.m-uploader-thumb {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
}
.m-uploader-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-uploader-thumb.is-failed {
  border-color: var(--m-color-danger-border);
  background: var(--m-color-danger-bg);
}
.m-uploader-mask-overlay {
  position: absolute;
  inset: 0;
  background: var(--m-mask-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-inverse);
  flex-direction: column;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-tiny);
}
.m-uploader-mask-overlay.failed {
  background: rgba(201, 54, 62, 0.65);
}
.m-uploader-spinner {
  width: 24px;
  height: 24px;
  border: 2.5px solid rgba(255, 255, 255, 0.4);
  border-top-color: var(--m-color-text-inverse);
  border-radius: var(--m-radius-circle);
  animation: m-uploader-spin 0.8s linear infinite;
}
@keyframes m-uploader-spin { to { transform: rotate(360deg); } }
.m-uploader-remove {
  position: absolute;
  top: var(--m-space-1);
  right: var(--m-space-1);
  width: 22px;
  height: 22px;
  border-radius: var(--m-radius-circle);
  background: rgba(15, 23, 42, 0.7);
  border: none;
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.m-uploader-thumb-error {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(201, 54, 62, 0.85);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-tiny);
  padding: var(--m-space-1);
  text-align: center;
  line-height: var(--m-line-height-base);
}

.m-uploader-add {
  aspect-ratio: 1 / 1;
  border-radius: var(--m-radius-lg);
  border: 1.5px dashed var(--m-color-border);
  background: var(--m-color-bg-page);
  color: var(--m-color-text-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  cursor: pointer;
  padding: 0;
}
.m-uploader-add small { color: var(--m-color-text-disabled); font-size: var(--m-font-size-tiny); }
.m-uploader-add:active { background: var(--m-color-primary-bg); }

.m-uploader-tips {
  margin-top: var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
}
.m-uploader-tips :deep(svg) { color: var(--m-color-purple); flex-shrink: 0; }

.m-uploader-actions {
  margin-top: var(--m-space-3);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-2);
}
.m-uploader-action {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  padding: var(--m-space-3) var(--m-space-2);
  background: var(--m-color-bg-page);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  color: var(--m-color-primary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}
.m-uploader-action :deep(svg) { color: var(--m-color-primary); }
.m-uploader-action:active { background: var(--m-color-primary-bg); }

.m-uploader-fade-enter-active,
.m-uploader-fade-leave-active {
  transition: opacity 0.2s ease;
}
.m-uploader-fade-enter-active .m-uploader-sheet,
.m-uploader-fade-leave-active .m-uploader-sheet {
  transition: transform 0.25s ease;
}
.m-uploader-fade-enter-from,
.m-uploader-fade-leave-to {
  opacity: 0;
}
.m-uploader-fade-enter-from .m-uploader-sheet,
.m-uploader-fade-leave-to .m-uploader-sheet {
  transform: translateY(100%);
}
</style>
