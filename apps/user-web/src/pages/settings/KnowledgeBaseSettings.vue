<template>
  <div class="kb-settings">
    <!-- 平台说明横幅 -->
    <div class="kb-banner">
      <div class="kb-banner-title">💡 让 AI 客服像真人一样</div>
      <p class="kb-banner-desc">
        我们致力于让 AI 客服像真人一样帮你完成更多事情。客服拥有自主学习能力，
        每天自动学习海量真实对话，知识库越来越健壮。你可以按分类启用所需知识库。
      </p>
    </div>

    <!-- 顶部操作 -->
    <div class="kb-toolbar">
      <button class="btn-feedback" @click="openFeedback">反馈建议</button>
      <button class="btn-add" @click="openCreateUserKb">+ 新增我的知识库</button>
    </div>

    <!-- Tab 切换 -->
    <div class="kb-tabs">
      <button :class="{active: tab==='learned'}" @click="tab='learned'">平台学习知识库</button>
      <button :class="{active: tab==='user'}" @click="tab='user'">我的知识库</button>
    </div>

    <!-- 全局 Toast -->
    <div v-if="toast.visible" :class="['kb-toast', toast.error ? 'is-error' : 'is-success']">
      {{ toast.message }}
    </div>

    <!-- Tab1: 平台学习知识库 - 左右分栏 -->
    <div v-if="tab==='learned'" class="kb-learned-panel">
      <div class="kb-layout">
        <!-- 左侧分类边栏 -->
        <aside class="kb-sidebar">
          <div class="kb-sidebar-title">分类导航</div>
          <div v-if="loading.categories" class="kb-empty-mini">加载中...</div>
          <div v-else class="kb-category-list">
            <button
              v-for="cat in categories"
              :key="cat.code || cat.id"
              :class="['kb-category-item', {active: selectedCategory === (cat.code || cat.name)}]"
              @click="selectCategory(cat.code || cat.name)"
            >
              <span class="kb-cat-name">{{ cat.name }}</span>
              <span class="kb-cat-count">{{ cat.total_count ?? cat.entry_count ?? 0 }}</span>
              <span v-if="cat.user_enabled" class="kb-cat-badge kb-cat-badge-on" title="已全部启用">✓</span>
              <span v-else-if="cat.user_partial" class="kb-cat-badge kb-cat-badge-partial" title="部分启用">◐</span>
            </button>
          </div>
        </aside>

        <!-- 右侧 Q&A 列表 -->
        <section class="kb-content">
          <div class="kb-filter">
            <input
              v-model="filter.keyword"
              :placeholder="selectedCategory ? `在「${selectedCategoryName}」中搜索` : '搜索关键词'"
              @keyup.enter="loadLearned"
            >
            <button :disabled="loading.learned" @click="loadLearned">
              {{ loading.learned ? '搜索中...' : '搜索' }}
            </button>
            <button
              v-if="selectedCategory"
              class="btn-bind"
              :disabled="loading.bindCategory"
              @click="toggleCategoryBind"
            >
              {{ loading.bindCategory ? '处理中...' : (currentCategoryEnabled ? '取消启用该分类' : '一键启用该分类') }}
            </button>
          </div>

          <div v-if="loading.learned && !learnedList.length" class="kb-empty">加载中...</div>
          <div v-else class="kb-list">
            <div v-for="item in learnedList" :key="item.id" class="kb-card">
              <div class="kb-card-header">
                <span class="kb-cat">{{ item.category_name || item.category_code || '未分类' }}</span>
                <span class="kb-source">· {{ item.source_count }} 会话 · {{ item.conversation_turn_count || 0 }} 轮</span>
              </div>
              <div class="kb-card-q">Q: {{ item.question }}</div>
              <div class="kb-card-a">A: {{ item.answer_preview }}</div>
              <div class="kb-card-tags" v-if="item.tags">
                <span v-for="t in item.tags.split(',')" :key="t" class="kb-tag">{{ t }}</span>
              </div>
              <div class="kb-card-actions">
                <button class="btn-link" @click="viewDetail(item.id)">查看详情</button>
                <button class="btn-link" @click="viewConversation(item.id)">查看对话</button>
                <span v-if="bindingSet.has(item.id)" class="kb-bound">✓ 已启用</span>
                <button
                  v-if="bindingSet.has(item.id)"
                  class="btn-link danger"
                  :disabled="loading.unbind === item.id"
                  @click="unbindLearned(item.id)"
                >
                  {{ loading.unbind === item.id ? '取消中...' : '取消启用' }}
                </button>
                <button
                  v-else
                  class="btn-link primary"
                  :disabled="loading.bindOne === item.id"
                  @click="bindOne(item.id)"
                >
                  {{ loading.bindOne === item.id ? '启用中...' : '启用' }}
                </button>
              </div>
            </div>
            <div v-if="!learnedList.length" class="kb-empty">
              {{ selectedCategory ? '该分类下暂无知识库' : '请从左侧选择分类' }}
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- Tab2: 我的知识库 -->
    <div v-if="tab==='user'" class="kb-user-panel">
      <div v-if="loading.userKb && !userList.length" class="kb-empty">加载中...</div>
      <div v-else class="kb-list">
        <div v-for="item in userList" :key="item.id" class="kb-card">
          <div class="kb-card-header">
            <span class="kb-cat">{{ item.category || '未分类' }}</span>
          </div>
          <div class="kb-card-q">{{ item.title }}</div>
          <div class="kb-card-a">{{ (item.content || '').slice(0, 200) }}</div>
          <div class="kb-card-actions">
            <button class="btn-link" @click="editUserKb(item)">编辑</button>
            <button
              class="btn-link danger"
              :disabled="loading.remove === item.id"
              @click="removeUserKb(item.id)"
            >
              {{ loading.remove === item.id ? '删除中...' : '删除' }}
            </button>
          </div>
        </div>
        <div v-if="!userList.length" class="kb-empty">还没有知识库，点击右上角"新增"</div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div v-if="detailVisible" class="kb-modal" @click.self="detailVisible=false">
      <div class="kb-modal-content">
        <h3>知识库详情</h3>
        <div v-if="loading.detail" class="kb-empty">加载中...</div>
        <div v-else-if="detail">
          <p><b>分类:</b> {{ detail.category_name || detail.category_code }}</p>
          <p><b>评分:</b> {{ detail.score }}</p>
          <p><b>来源会话数:</b> {{ detail.source_count }}</p>
          <p><b>对话轮数:</b> {{ detail.conversation_turn_count || 0 }}</p>
          <p><b>标签:</b> {{ detail.tags }}</p>
          <hr>
          <p><b>问题:</b></p>
          <div class="kb-detail-text">{{ detail.question }}</div>
          <p><b>回答:</b></p>
          <div class="kb-detail-text">{{ detail.answer }}</div>
        </div>
        <button @click="detailVisible=false">关闭</button>
      </div>
    </div>

    <!-- 原始对话弹窗 -->
    <div v-if="conversationVisible" class="kb-modal" @click.self="conversationVisible=false">
      <div class="kb-modal-content kb-modal-conversation">
        <h3>原始对话</h3>
        <div v-if="loading.conversation" class="kb-empty">加载中...</div>
        <div v-else-if="conversationMessages.length" class="kb-chat">
          <div
            v-for="(msg, idx) in conversationMessages"
            :key="idx"
            :class="['kb-chat-msg', msg.direction === 'incoming' ? 'msg-in' : 'msg-out']"
          >
            <div class="kb-chat-sender">
              {{ msg.sender || '未知' }}
              <span v-if="msg.is_auto_reply" class="kb-ai-tag">AI</span>
            </div>
            <div class="kb-chat-bubble">{{ msg.content }}</div>
          </div>
        </div>
        <div v-else class="kb-empty">该 Q&A 未关联原始对话</div>
        <button @click="conversationVisible=false">关闭</button>
      </div>
    </div>

    <!-- 新增/编辑用户 KB 弹窗 -->
    <div v-if="formVisible" class="kb-modal" @click.self="formVisible=false">
      <div class="kb-modal-content">
        <h3>{{ editingId ? '编辑知识库' : '新增我的知识库' }}</h3>
        <div class="kb-form">
          <label>标题（最多 100 字）</label>
          <input v-model="form.title" maxlength="100" placeholder="必填">
          <label>内容（最多 5000 字）</label>
          <textarea v-model="form.content" rows="6" maxlength="5000" placeholder="必填"></textarea>
          <label>分类（最多 30 字）</label>
          <input v-model="form.category" maxlength="30" placeholder="可选">
          <label>标签（逗号分隔，最多 100 字）</label>
          <input v-model="form.tags" maxlength="100" placeholder="可选">
        </div>
        <div class="kb-form-actions">
          <button :disabled="loading.save" @click="formVisible=false">取消</button>
          <button class="btn-primary" :disabled="loading.save" @click="saveUserKb">
            {{ loading.save ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 反馈弹窗 -->
    <div v-if="feedbackVisible" class="kb-modal" @click.self="feedbackVisible=false">
      <div class="kb-modal-content">
        <h3>反馈建议</h3>
        <textarea
          v-model="feedbackContent"
          rows="6"
          maxlength="1000"
          placeholder="请输入你的反馈（最多 1000 字）..."
        ></textarea>
        <div class="kb-form-actions">
          <button :disabled="loading.feedback" @click="feedbackVisible=false">取消</button>
          <button class="btn-primary" :disabled="loading.feedback" @click="submitFeedbackContent">
            {{ loading.feedback ? '提交中...' : '提交' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import {
  listLearnedKb, getLearnedKbDetail, getLearnedKbConversation,
  listKbCategories, listLearnedKbByCategory, bindCategory, unbindCategory,
  listUserKb, createUserKb, updateUserKb, deleteUserKb,
  listBindings, bindKbs, unbindKb,
  submitFeedback
} from '../../api/kbLearning.js'

const tab = ref('learned')
const learnedList = ref([])
const userList = ref([])
const categories = ref([])
const bindings = ref([])
const selectedCategory = ref('')

const filter = reactive({ keyword: '' })

const detailVisible = ref(false)
const detail = ref(null)

const conversationVisible = ref(false)
const conversationMessages = ref([])

const formVisible = ref(false)
const editingId = ref(null)
const form = reactive({ title: '', content: '', category: '', tags: '' })

const feedbackVisible = ref(false)
const feedbackContent = ref('')

const loading = reactive({
  learned: false,
  categories: false,
  userKb: false,
  bindings: false,
  detail: false,
  conversation: false,
  bind: false,
  unbind: null,
  bindOne: null,
  bindCategory: false,
  save: false,
  remove: null,
  feedback: false,
})

const toast = reactive({ visible: false, message: '', error: false })
let toastTimer = null
function showToast(message, error = false) {
  toast.message = message
  toast.error = error
  toast.visible = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.visible = false }, 3000)
}

const bindingSet = computed(() => new Set(
  bindings.value.filter(b => b.kb_type === 'learned' && b.enabled).map(b => b.kb_id)
))

const selectedCategoryName = computed(() => {
  const cat = categories.value.find(c => (c.code || c.name) === selectedCategory.value)
  return cat?.name || selectedCategory.value
})

const currentCategoryEnabled = computed(() => {
  const cat = categories.value.find(c => (c.code || c.name) === selectedCategory.value)
  return cat?.user_enabled === true
})

function selectCategory(code) {
  selectedCategory.value = code
  filter.keyword = ''
  loadLearned()
}

async function loadCategories() {
  loading.categories = true
  try {
    const res = await listKbCategories()
    categories.value = res.data || res || []
    // 默认选中第一个分类
    if (categories.value.length && !selectedCategory.value) {
      const first = categories.value[0]
      selectedCategory.value = first.code || first.name
      await loadLearned()
    }
  } catch (e) {
    showToast('加载分类失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.categories = false
  }
}

async function loadLearned() {
  if (!selectedCategory.value) {
    // 未选分类时加载全部
    loading.learned = true
    try {
      const res = await listLearnedKb({ keyword: filter.keyword })
      learnedList.value = res.data || res || []
    } catch (e) {
      showToast('加载知识库列表失败：' + (e?.message || '未知错误'), true)
    } finally {
      loading.learned = false
    }
    return
  }

  loading.learned = true
  try {
    const res = await listLearnedKbByCategory(selectedCategory.value, { keyword: filter.keyword })
    learnedList.value = res.data || res || []
  } catch (e) {
    showToast('加载知识库列表失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.learned = false
  }
}

async function loadUserKb() {
  loading.userKb = true
  try {
    const res = await listUserKb()
    userList.value = res.data || res || []
  } catch (e) {
    showToast('加载我的知识库失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.userKb = false
  }
}

async function loadBindings() {
  loading.bindings = true
  try {
    const res = await listBindings()
    bindings.value = res.data || res || []
  } catch (e) {
    showToast('加载启用状态失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.bindings = false
  }
}

async function viewDetail(id) {
  detailVisible.value = true
  loading.detail = true
  detail.value = null
  try {
    const res = await getLearnedKbDetail(id)
    detail.value = res.data || res
  } catch (e) {
    showToast('加载详情失败：' + (e?.message || '未知错误'), true)
    detailVisible.value = false
  } finally {
    loading.detail = false
  }
}

async function viewConversation(id) {
  conversationVisible.value = true
  loading.conversation = true
  conversationMessages.value = []
  try {
    const res = await getLearnedKbConversation(id)
    conversationMessages.value = res.data || res || []
  } catch (e) {
    showToast('加载对话失败：' + (e?.message || '未知错误'), true)
    conversationVisible.value = false
  } finally {
    loading.conversation = false
  }
}

async function toggleCategoryBind() {
  if (!selectedCategory.value) return
  loading.bindCategory = true
  try {
    if (currentCategoryEnabled.value) {
      const res = await unbindCategory(selectedCategory.value)
      const count = res?.data?.unbound_count ?? res?.unbound_count ?? 0
      showToast(`已取消启用该分类（${count} 条）`)
    } else {
      const res = await bindCategory(selectedCategory.value)
      const count = res?.data?.bound_count ?? res?.bound_count ?? 0
      showToast(`已启用该分类下 ${count} 条知识库`)
    }
    // 刷新分类列表（更新启用状态）+ 绑定列表
    await Promise.all([loadCategories(), loadBindings()])
  } catch (e) {
    showToast('操作失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.bindCategory = false
  }
}

async function bindOne(id) {
  loading.bindOne = id
  try {
    await bindKbs([{ kb_type: 'learned', kb_id: id }])
    await loadBindings()
    showToast('已启用')
  } catch (e) {
    showToast('启用失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.bindOne = null
  }
}

async function unbindLearned(id) {
  loading.unbind = id
  try {
    await unbindKb('learned', id)
    await loadBindings()
    showToast('已取消启用')
  } catch (e) {
    showToast('取消启用失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.unbind = null
  }
}

function openCreateUserKb() {
  editingId.value = null
  form.title = ''
  form.content = ''
  form.category = ''
  form.tags = ''
  formVisible.value = true
}

function editUserKb(item) {
  editingId.value = item.id
  form.title = item.title
  form.content = item.content
  form.category = item.category || ''
  form.tags = item.tags || ''
  formVisible.value = true
}

async function saveUserKb() {
  const title = (form.title || '').trim()
  const content = (form.content || '').trim()
  if (!title || !content) {
    showToast('标题和内容必填', true)
    return
  }
  if (title.length > 100 || content.length > 5000) {
    showToast('标题或内容超出长度限制', true)
    return
  }
  loading.save = true
  try {
    const payload = {
      title,
      content,
      category: (form.category || '').trim(),
      tags: (form.tags || '').trim(),
    }
    if (editingId.value) {
      await updateUserKb(editingId.value, payload)
    } else {
      await createUserKb(payload)
    }
    formVisible.value = false
    await loadUserKb()
    showToast(editingId.value ? '已更新' : '已创建')
  } catch (e) {
    showToast('保存失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.save = false
  }
}

async function removeUserKb(id) {
  if (!confirm('确定删除该知识库？此操作不可恢复。')) return
  loading.remove = id
  try {
    await deleteUserKb(id)
    await loadUserKb()
    showToast('已删除')
  } catch (e) {
    showToast('删除失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.remove = null
  }
}

function openFeedback() {
  feedbackContent.value = ''
  feedbackVisible.value = true
}

async function submitFeedbackContent() {
  if (!feedbackContent.value.trim()) {
    showToast('请输入反馈内容', true)
    return
  }
  loading.feedback = true
  try {
    await submitFeedback({
      category: 'kb_feedback',
      title: '关于客服知识库的反馈',
      content: feedbackContent.value
    })
    feedbackVisible.value = false
    showToast('反馈已提交，感谢！')
  } catch (e) {
    showToast('提交反馈失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.feedback = false
  }
}

onMounted(async () => {
  await Promise.allSettled([loadCategories(), loadUserKb(), loadBindings()])
})
</script>

<style scoped>
.kb-settings { padding: 16px 24px; }
.kb-banner {
  background: linear-gradient(135deg, #e3f2fd, #fce4ec);
  padding: 16px 20px; border-radius: 8px; margin-bottom: 16px;
}
.kb-banner-title { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.kb-banner-desc { font-size: 13px; color: #666; line-height: 1.6; }
.kb-toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.kb-toolbar button { padding: 8px 16px; border-radius: 4px; border: 1px solid #ddd; cursor: pointer; }
.kb-toolbar button:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-add { background: #1890ff; color: white; border-color: #1890ff; }
.btn-feedback { background: white; }
.kb-tabs { display: flex; gap: 4px; border-bottom: 1px solid #eee; margin-bottom: 16px; }
.kb-tabs button { padding: 8px 16px; border: none; background: none; cursor: pointer; border-bottom: 2px solid transparent; }
.kb-tabs button.active { color: #1890ff; border-bottom-color: #1890ff; }

/* 左右分栏布局 */
.kb-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  min-height: 500px;
}
.kb-sidebar {
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 12px;
  background: #fafafa;
  max-height: 70vh;
  overflow-y: auto;
}
.kb-sidebar-title {
  font-size: 13px;
  color: #999;
  margin-bottom: 8px;
  font-weight: 600;
}
.kb-category-list { display: flex; flex-direction: column; gap: 2px; }
.kb-category-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: 4px;
  text-align: left;
  font-size: 13px;
  color: #333;
  transition: background 0.15s;
}
.kb-category-item:hover { background: #e6f7ff; }
.kb-category-item.active { background: #1890ff; color: white; }
.kb-category-item.active .kb-cat-count { color: rgba(255,255,255,0.8); }
.kb-cat-name { flex: 1; }
.kb-cat-count {
  font-size: 11px;
  color: #999;
  background: rgba(0,0,0,0.05);
  padding: 1px 6px;
  border-radius: 8px;
  min-width: 20px;
  text-align: center;
}
.kb-category-item.active .kb-cat-count {
  background: rgba(255,255,255,0.2);
  color: white;
}
.kb-cat-badge { font-size: 14px; }
.kb-cat-badge-on { color: #52c41a; }
.kb-cat-badge-partial { color: #faad14; }
.kb-category-item.active .kb-cat-badge-on { color: #b7eb8f; }
.kb-category-item.active .kb-cat-badge-partial { color: #ffe58f; }

.kb-content {
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 12px;
  background: white;
}
.kb-filter { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap; }
.kb-filter input { padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; flex: 1; min-width: 200px; }
.kb-filter button { padding: 6px 12px; border: 1px solid #ddd; background: white; cursor: pointer; border-radius: 4px; }
.kb-filter button:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-bind { background: #52c41a; color: white; border-color: #52c41a; }
.btn-bind:disabled { background: #ccc; border-color: #ccc; cursor: not-allowed; opacity: 1; }

.kb-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.kb-card { border: 1px solid #eee; border-radius: 6px; padding: 12px; }
.kb-card-header { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 12px; color: #999; }
.kb-cat { background: #f5f5f5; padding: 2px 8px; border-radius: 4px; }
.kb-card-q { font-weight: 600; margin-bottom: 6px; font-size: 14px; }
.kb-card-a { font-size: 13px; color: #666; margin-bottom: 8px; line-height: 1.5; }
.kb-card-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
.kb-tag { background: #e6f7ff; color: #1890ff; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
.kb-card-actions { display: flex; align-items: center; gap: 12px; font-size: 12px; }
.btn-link { background: none; border: none; color: #1890ff; cursor: pointer; padding: 0; }
.btn-link:disabled { color: #ccc; cursor: not-allowed; }
.btn-link.danger { color: #ff4d4f; }
.btn-link.primary { color: #52c41a; font-weight: 600; }
.btn-link.danger:disabled { color: #ccc; }
.kb-bound { color: #52c41a; font-weight: 600; }
.kb-empty { grid-column: 1 / -1; text-align: center; color: #999; padding: 40px; }
.kb-empty-mini { text-align: center; color: #999; padding: 20px; font-size: 12px; }

.kb-modal {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 2000;
}
.kb-modal-content {
  background: white; padding: 20px; border-radius: 8px;
  max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto;
}
.kb-modal-conversation { max-width: 700px; }
.kb-modal-content h3 { margin-top: 0; }
.kb-detail-text { background: #f9f9f9; padding: 8px; border-radius: 4px; margin: 8px 0; white-space: pre-wrap; }
.kb-form { display: flex; flex-direction: column; gap: 6px; }
.kb-form label { font-size: 13px; color: #666; margin-top: 8px; }
.kb-form input, .kb-form textarea { padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; }
.kb-form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.kb-form-actions button:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #1890ff; color: white; border: none; padding: 6px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

/* 对话消息样式 */
.kb-chat {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 6px;
}
.kb-chat-msg { display: flex; flex-direction: column; max-width: 70%; }
.kb-chat-msg.msg-in { align-self: flex-start; }
.kb-chat-msg.msg-out { align-self: flex-end; align-items: flex-end; }
.kb-chat-sender { font-size: 11px; color: #999; margin-bottom: 2px; padding: 0 8px; }
.kb-ai-tag {
  display: inline-block;
  background: #1890ff;
  color: white;
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 4px;
}
.kb-chat-bubble {
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}
.msg-in .kb-chat-bubble { background: white; color: #333; border: 1px solid #e8e8e8; }
.msg-out .kb-chat-bubble { background: #1890ff; color: white; }

.kb-toast {
  position: fixed; top: 24px; left: 50%; transform: translateX(-50%);
  padding: 10px 20px; border-radius: 4px; color: white; z-index: 3000;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 14px;
}
.kb-toast.is-success { background: #52c41a; }
.kb-toast.is-error { background: #ff4d4f; }

/* 移动端适配：左侧边栏改为顶部水平滚动标签栏 */
@media (max-width: 768px) {
  .kb-layout {
    grid-template-columns: 1fr;
  }
  .kb-sidebar {
    max-height: none;
    padding: 8px;
  }
  .kb-sidebar-title { margin-bottom: 4px; }
  .kb-category-list {
    flex-direction: row;
    overflow-x: auto;
    gap: 4px;
    padding-bottom: 4px;
  }
  .kb-category-item {
    flex-shrink: 0;
    padding: 6px 10px;
    white-space: nowrap;
  }
  .kb-cat-badge { display: none; }
  .kb-list { grid-template-columns: 1fr; }
}
</style>
