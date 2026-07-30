<template>
  <div class="kb-settings">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">客服知识库</h2>
        <p class="page-subtitle">管理 AI 客服知识库，让 AI 像真人销冠一样回复买家</p>
      </div>
    </div>

    <!-- 平台说明横幅 -->
    <div class="kb-banner">
      <div class="kb-banner-icon">💡</div>
      <div class="kb-banner-content">
        <div class="kb-banner-title">让 AI 客服像真人销冠一样</div>
        <p class="kb-banner-desc">
          客服拥有自主学习能力，每天自动学习海量真实对话，知识库越来越健壮。你可以按一级大类或二级子类启用所需知识库，
          启用后 AI 客服将按"系统提示 → 回复规则 → 知识库"的优先级回复买家。
        </p>
      </div>
      <div class="kb-banner-stats">
        <div class="kb-stat-item">
          <b>{{ stats.totalCategories }}</b>
          <span>一级大类</span>
        </div>
        <div class="kb-stat-item">
          <b>{{ stats.totalSubCategories }}</b>
          <span>二级子类</span>
        </div>
        <div class="kb-stat-item">
          <b>{{ stats.totalKb }}</b>
          <span>条知识</span>
        </div>
        <div class="kb-stat-item kb-stat-enabled">
          <b>{{ stats.enabledKb }}</b>
          <span>条已启用</span>
        </div>
      </div>
    </div>

    <!-- 知识库使用说明 -->
    <div class="kb-info-banner">
      <div class="kb-info-icon">📌</div>
      <div class="kb-info-content">
        <div class="kb-info-title">知识库使用说明</div>
        <p class="kb-info-desc">
          知识库内容仅作参考。AI 自动回复时，会严格按以下优先级生成回复：
          <span class="kb-info-chain">系统提示词 → 商品回复规则 → 商品标题与正文 → 知识库参考</span>
        </p>
        <p class="kb-info-desc">
          因此即使知识库中的回答针对单个商品（如某本书的正版验证），您也无需担心——AI 会自动根据您实际商品的标题与正文生成合适的回复，敏感信息会自动适配，无需手动调整。
        </p>
      </div>
    </div>

    <!-- 顶部操作 -->
    <div class="kb-toolbar">
      <button class="btn-feedback" @click="openFeedback">
        <span class="btn-icon">💬</span>
        反馈建议
      </button>
      <button class="btn-add" @click="openCreateUserKb">
        <span class="btn-icon">+</span>
        新增我的知识库
      </button>
    </div>

    <!-- Tab 切换 -->
    <div class="kb-tabs">
      <button :class="{active: tab==='learned'}" @click="tab='learned'">
        <span class="tab-icon">📚</span>
        平台学习知识库
      </button>
      <button :class="{active: tab==='user'}" @click="tab='user'">
        <span class="tab-icon">📝</span>
        我的知识库
      </button>
    </div>

    <!-- 全局 Toast -->
    <div v-if="toast.visible" :class="['kb-toast', toast.error ? 'is-error' : 'is-success']">
      <span class="toast-icon">{{ toast.error ? '❌' : '✅' }}</span>
      {{ toast.message }}
    </div>

    <!-- Tab1: 平台学习知识库 - 三级树形 + 右侧详情 -->
    <div v-if="tab==='learned'" class="kb-learned-panel">
      <div class="kb-layout">
        <!-- 左侧：三级树形分类导航 -->
        <aside class="kb-sidebar">
          <div class="kb-sidebar-header">
            <span class="kb-sidebar-title">🗂 分类导航</span>
            <div class="kb-sidebar-actions">
              <button class="btn-mini" @click="expandAllCategories" title="展开全部">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 13l5 5 5-5M7 6l5-5 5 5"/></svg>
              </button>
              <button class="btn-mini" @click="collapseAllCategories" title="折叠全部">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 11l-5-5-5 5M17 18l-5 5-5-5"/></svg>
              </button>
            </div>
          </div>

          <div v-if="loading.categories" class="kb-loading">
            <div class="loading-spinner"></div>
            <span>加载中...</span>
          </div>
          <div v-else class="kb-tree">
            <!-- 全部 -->
            <button
              :class="['kb-tree-all', {active: selectedType === 'all'}]"
              @click="selectAllCategories"
            >
              <span class="kb-tree-icon">🌟</span>
              <span class="kb-tree-name">全部知识</span>
              <span class="kb-tree-count">{{ stats.totalKb }}</span>
            </button>

            <!-- 一级分类循环 -->
            <div v-for="parent in categories" :key="parent.code || parent.id" class="kb-tree-parent">
              <div
                :class="['kb-tree-parent-row', {active: selectedType === 'parent' && selectedCode === parent.code}]"
                :style="{ borderLeftColor: parent.color || '#4A6CF7' }"
              >
                <button
                  class="kb-tree-toggle"
                  @click="toggleParentExpand(parent.code)"
                  :title="expandedParents.has(parent.code) ? '点击折叠' : '点击展开'"
                >
                  <span :class="['kb-toggle-icon', {expanded: expandedParents.has(parent.code)}]">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 18l6-6-6-6"/></svg>
                  </span>
                </button>
                <button
                  class="kb-tree-parent-info"
                  @click="selectParentCategory(parent.code)"
                >
                  <span class="kb-tree-icon">{{ parent.icon || '📦' }}</span>
                  <span class="kb-tree-name">{{ parent.name }}</span>
                  <span class="kb-tree-count">{{ parent.total_count ?? 0 }}</span>
                </button>
                <button
                  :class="['kb-tree-bind', parent.user_enabled ? 'is-on' : (parent.user_partial ? 'is-partial' : 'is-off')]"
                  :disabled="loading.bindParent === parent.code"
                  :title="parent.user_enabled ? '已全部启用，点击取消' : (parent.user_partial ? '部分启用，点击全部启用' : '点击一键启用整个大类')"
                  @click="toggleParentBind(parent)"
                >
                  <span v-if="loading.bindParent === parent.code" class="btn-spinner"></span>
                  <span v-else-if="parent.user_enabled">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg>
                  </span>
                  <span v-else-if="parent.user_partial">◐</span>
                  <span v-else>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
                  </span>
                </button>
              </div>

              <!-- 二级子分类（展开时显示） -->
              <div v-if="expandedParents.has(parent.code)" class="kb-tree-children">
                <div
                  v-for="child in (parent.children || [])"
                  :key="child.code || child.id"
                  :class="['kb-tree-child-row', {active: selectedType === 'child' && selectedCode === child.code}]"
                >
                  <button
                    class="kb-tree-child-info"
                    @click="selectChildCategory(child.code)"
                    :title="child.name + '（' + (child.total_count ?? 0) + ' 条）'"
                  >
                    <span class="kb-tree-child-dot"></span>
                    <span class="kb-tree-child-name">{{ child.name }}</span>
                    <span class="kb-tree-child-count">{{ child.total_count ?? 0 }}</span>
                  </button>
                  <button
                    :class="['kb-tree-bind', 'kb-tree-bind-mini', child.user_enabled ? 'is-on' : (child.user_partial ? 'is-partial' : 'is-off')]"
                    :disabled="loading.bindChild === child.code"
                    :title="child.user_enabled ? '已全部启用，点击取消' : (child.user_partial ? '部分启用，点击全部启用' : '点击启用此子类')"
                    @click.stop="toggleChildBind(child, parent)"
                  >
                    <span v-if="loading.bindChild === child.code" class="btn-spinner"></span>
                    <span v-else-if="child.user_enabled">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg>
                    </span>
                    <span v-else-if="child.user_partial">◐</span>
                    <span v-else>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
                    </span>
                  </button>
                </div>
                <div v-if="!(parent.children && parent.children.length)" class="kb-tree-empty">
                  暂无子分类
                </div>
              </div>
            </div>
          </div>
        </aside>

        <!-- 右侧 Q&A 列表 -->
        <section class="kb-content">
          <div class="kb-content-header">
            <div class="kb-content-title-wrap">
              <span v-if="selectedType === 'all'" class="kb-content-title">🌟 全部知识</span>
              <span v-else-if="selectedType === 'parent'" class="kb-content-title">
                {{ selectedParentName }}<span class="kb-content-subtitle">（一级大类）</span>
              </span>
              <span v-else-if="selectedType === 'child'" class="kb-content-title">
                {{ selectedChildName }}<span class="kb-content-subtitle">（二级子类）</span>
              </span>
            </div>
            <div class="kb-filter">
              <div class="search-input-wrap">
                <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input
                  v-model="filter.keyword"
                  :placeholder="filterPlaceholder"
                  @keyup.enter="loadLearned"
                >
              </div>
              <button class="btn-search" :disabled="loading.learned" @click="loadLearned">
                {{ loading.learned ? '搜索中...' : '搜索' }}
              </button>
              <button
                v-if="selectedType !== 'all'"
                class="btn-bind"
                :disabled="loading.bindCategory"
                @click="toggleCurrentBind"
              >
                <span v-if="loading.bindCategory" class="btn-spinner"></span>
                {{ loading.bindCategory ? '处理中...' : (currentSelectionEnabled ? '取消启用' : '一键启用') }}
              </button>
            </div>
          </div>

          <div v-if="loading.learned && !learnedList.length" class="kb-loading-large">
            <div class="loading-spinner large"></div>
            <span>加载中...</span>
          </div>
          <div v-else class="kb-list">
            <div v-for="item in learnedList" :key="item.id" class="kb-card">
              <div class="kb-card-header">
                <span class="kb-cat">
                  <span v-if="item.parent_name" class="kb-cat-parent">{{ item.parent_name }} ›</span>
                  {{ item.category_name || item.category_code || '未分类' }}
                </span>
                <span class="kb-source">{{ item.source_count }} 会话 · {{ item.conversation_turn_count || 0 }} 轮</span>
              </div>
              <div class="kb-card-q">
                <span class="q-label">Q</span>
                <span class="q-text">{{ item.question }}</span>
              </div>
              <div class="kb-card-a">
                <span class="a-label">A</span>
                <span class="a-text">{{ item.answer_preview }}</span>
              </div>
              <div class="kb-card-tags" v-if="item.tags">
                <span v-for="t in item.tags.split(',')" :key="t" class="kb-tag">{{ t }}</span>
              </div>
              <div class="kb-card-footer">
                <div class="kb-card-actions">
                  <button class="btn-link" @click="viewDetail(item.id)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    查看详情
                  </button>
                </div>
                <div class="kb-card-status">
                  <span v-if="bindingSet.has(item.id)" class="kb-bound">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
                    已启用
                  </span>
                  <button
                    v-if="bindingSet.has(item.id)"
                    class="btn-link danger"
                    :disabled="loading.unbind === item.id"
                    @click="unbindLearned(item.id)"
                  >
                    <span v-if="loading.unbind === item.id" class="btn-spinner small"></span>
                    {{ loading.unbind === item.id ? '取消中...' : '取消启用' }}
                  </button>
                  <button
                    v-else
                    class="btn-link primary"
                    :disabled="loading.bindOne === item.id"
                    @click="bindOne(item.id)"
                  >
                    <span v-if="loading.bindOne === item.id" class="btn-spinner small"></span>
                    {{ loading.bindOne === item.id ? '启用中...' : '启用' }}
                  </button>
                </div>
              </div>
              <div class="kb-card-ref">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                仅供参考，AI 会根据您的商品自动适配
              </div>
            </div>
            <div v-if="!learnedList.length" class="kb-empty">
              <div class="kb-empty-icon">📭</div>
              <div class="kb-empty-text">
                {{ selectedType === 'all' ? '暂无知识库' : (selectedType === 'parent' ? '该大类下暂无知识库' : '该子类下暂无知识库') }}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- Tab2: 我的知识库 -->
    <div v-if="tab==='user'" class="kb-user-panel">
      <div class="kb-info-inline">
        <span class="info-icon">💡</span>
        这里是你自定义的知识库。AI 回复时，会严格按"系统提示词 → 商品回复规则 → 商品正文 → 知识库参考"的优先级，自动根据实际商品适配，无需担心敏感信息。
      </div>
      <div v-if="loading.userKb && !userList.length" class="kb-loading-large">
        <div class="loading-spinner large"></div>
        <span>加载中...</span>
      </div>
      <div v-else class="kb-list kb-user-list">
        <div v-for="item in userList" :key="item.id" class="kb-card kb-user-card">
          <div class="kb-card-header">
            <span class="kb-cat kb-cat-user">{{ formatUserCategory(item.category) }}</span>
          </div>
          <div class="kb-card-q">
            <span class="q-label">Q</span>
            <span class="q-text">{{ item.title }}</span>
          </div>
          <div class="kb-card-a">
            <span class="a-label">A</span>
            <span class="a-text">{{ (item.content || '').slice(0, 200) }}</span>
          </div>
          <div class="kb-card-tags" v-if="item.tags">
            <span v-for="t in item.tags.split(',')" :key="t" class="kb-tag">{{ t }}</span>
          </div>
          <div class="kb-card-footer">
            <div class="kb-card-actions">
              <button class="btn-link" @click="editUserKb(item)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                编辑
              </button>
            </div>
            <button
              class="btn-link danger"
              :disabled="loading.remove === item.id"
              @click="removeUserKb(item.id)"
            >
              <span v-if="loading.remove === item.id" class="btn-spinner small"></span>
              {{ loading.remove === item.id ? '删除中...' : '删除' }}
            </button>
          </div>
        </div>
        <div v-if="!userList.length" class="kb-empty">
          <div class="kb-empty-icon">📝</div>
          <div class="kb-empty-text">还没有知识库，点击右上角"新增"</div>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div v-if="detailVisible" class="kb-modal-overlay" @click.self="detailVisible=false">
      <div class="kb-modal">
        <div class="kb-modal-header">
          <h3>知识库详情</h3>
          <button class="kb-modal-close" @click="detailVisible=false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div v-if="loading.detail" class="kb-modal-loading">
          <div class="loading-spinner"></div>
          <span>加载中...</span>
        </div>
        <div v-else-if="detail" class="kb-modal-body">
          <div class="kb-detail-meta">
            <div class="meta-item">
              <span class="meta-label">分类</span>
              <span class="meta-value">{{ detail.category_name || detail.category_code }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">评分</span>
              <span class="meta-value">{{ detail.score }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">来源会话数</span>
              <span class="meta-value">{{ detail.source_count }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">对话轮数</span>
              <span class="meta-value">{{ detail.conversation_turn_count || 0 }}</span>
            </div>
            <div class="meta-item" v-if="detail.tags">
              <span class="meta-label">标签</span>
              <span class="meta-value">{{ detail.tags }}</span>
            </div>
          </div>
          <div class="kb-detail-section">
            <div class="detail-label">
              <span class="q-label">Q</span>
              问题
            </div>
            <div class="kb-detail-text">{{ detail.question }}</div>
          </div>
          <div class="kb-detail-section">
            <div class="detail-label">
              <span class="a-label">A</span>
              回答
            </div>
            <div class="kb-detail-text">{{ detail.answer }}</div>
          </div>
          <div class="kb-detail-ref">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            此回答仅作参考。AI 自动回复时，会严格根据您实际商品的标题与正文重新生成回复，敏感信息会自动适配。
          </div>
        </div>
        <div class="kb-modal-footer">
          <button class="btn-modal" @click="detailVisible=false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 新增/编辑用户 KB 弹窗 -->
    <div v-if="formVisible" class="kb-modal-overlay" @click.self="formVisible=false">
      <div class="kb-modal">
        <div class="kb-modal-header">
          <h3>{{ editingId ? '编辑知识库' : '新增我的知识库' }}</h3>
          <button class="kb-modal-close" @click="formVisible=false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="kb-modal-body">
          <div class="kb-form">
            <div class="form-group">
              <label>问题（最多 100 字）<span class="required">*</span></label>
              <input v-model="form.title" maxlength="100" placeholder="必填，如：这本书是正版吗？" />
            </div>

            <div class="form-group">
              <label>回答（最多 5000 字）<span class="required">*</span></label>
              <textarea v-model="form.content" rows="6" maxlength="5000" placeholder="必填，如：是的，本店所售图书均为正版，支持专柜验货..."></textarea>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>一级分类（可选，可新建）</label>
                <input
                  v-model="form.parentCategory"
                  list="userParentCatList"
                  maxlength="30"
                  placeholder="可选，如：图书教材"
                >
                <datalist id="userParentCatList">
                  <option v-for="cat in userParentCategories" :key="cat" :value="cat"></option>
                </datalist>
              </div>

              <div class="form-group">
                <label>二级分类（可选，依赖一级，可新建）</label>
                <input
                  v-model="form.childCategory"
                  list="userChildCatList"
                  maxlength="30"
                  placeholder="可选，如：教材"
                  :disabled="!form.parentCategory"
                >
                <datalist id="userChildCatList">
                  <option v-for="cat in userChildCategoriesOfParent" :key="cat" :value="cat"></option>
                </datalist>
              </div>
            </div>
            <p class="form-hint">💡 提示：从下拉选择已有分类，或直接输入新建分类。二级分类需先选择一级分类。</p>

            <div class="form-group">
              <label>标签（逗号分隔，最多 100 字）</label>
              <input v-model="form.tags" maxlength="100" placeholder="可选，如：正版,售后,退款">
            </div>
          </div>
        </div>
        <div class="kb-modal-footer">
          <button class="btn-modal" :disabled="loading.save" @click="formVisible=false">取消</button>
          <button class="btn-modal btn-primary" :disabled="loading.save" @click="saveUserKb">
            <span v-if="loading.save" class="btn-spinner"></span>
            {{ loading.save ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 反馈弹窗 -->
    <div v-if="feedbackVisible" class="kb-modal-overlay" @click.self="feedbackVisible=false">
      <div class="kb-modal">
        <div class="kb-modal-header">
          <h3>反馈建议</h3>
          <button class="kb-modal-close" @click="feedbackVisible=false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="kb-modal-body">
          <textarea
            v-model="feedbackContent"
            rows="6"
            maxlength="1000"
            placeholder="请输入你的反馈（最多 1000 字）..."
            class="feedback-textarea"
          ></textarea>
        </div>
        <div class="kb-modal-footer">
          <button class="btn-modal" :disabled="loading.feedback" @click="feedbackVisible=false">取消</button>
          <button class="btn-modal btn-primary" :disabled="loading.feedback" @click="submitFeedbackContent">
            <span v-if="loading.feedback" class="btn-spinner"></span>
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
  listLearnedKb, getLearnedKbDetail,
  listKbCategories, bindCategory, unbindCategory,
  listLearnedKbByParentCategory, bindParentCategory, unbindParentCategory,
  listLearnedKbByCategory,
  listUserKb, createUserKb, updateUserKb, deleteUserKb,
  listBindings, bindKbs, unbindKb,
  submitFeedback
} from '../../api/kbLearning.js'

const tab = ref('learned')
const learnedList = ref([])
const userList = ref([])
const categories = ref([])
const bindings = ref([])

// 选中状态：'all' = 全部，'parent' = 一级，'child' = 二级
const selectedType = ref('all')
const selectedCode = ref('')
const expandedParents = ref(new Set())

const filter = reactive({ keyword: '' })

const detailVisible = ref(false)
const detail = ref(null)

const formVisible = ref(false)
const editingId = ref(null)
// 表单字段：parentCategory/childCategory 用于 UI，保存时拼装为 category 提交
const form = reactive({ title: '', content: '', parentCategory: '', childCategory: '', tags: '' })

const feedbackVisible = ref(false)
const feedbackContent = ref('')

const loading = reactive({
  learned: false,
  categories: false,
  userKb: false,
  bindings: false,
  detail: false,
  bind: false,
  unbind: null,
  bindOne: null,
  bindCategory: false,
  bindParent: null,
  bindChild: null,
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

// 统计数据：总数/已启用数
const stats = computed(() => {
  let totalCategories = 0
  let totalSubCategories = 0
  let totalKb = 0
  let enabledKb = 0
  for (const parent of categories.value) {
    totalCategories++
    totalKb += parent.total_count ?? 0
    enabledKb += parent.bound_count ?? 0
    for (const child of (parent.children || [])) {
      totalSubCategories++
    }
  }
  return { totalCategories, totalSubCategories, totalKb, enabledKb }
})

// 当前选中的名称（用于标题展示）
const selectedParentName = computed(() => {
  if (selectedType.value !== 'parent') return ''
  const p = categories.value.find(c => c.code === selectedCode.value)
  return p ? (p.icon ? `${p.icon} ${p.name}` : p.name) : selectedCode.value
})

const selectedChildName = computed(() => {
  if (selectedType.value !== 'child') return ''
  for (const p of categories.value) {
    for (const ch of (p.children || [])) {
      if (ch.code === selectedCode.value) return ch.name
    }
  }
  return selectedCode.value
})

const filterPlaceholder = computed(() => {
  if (selectedType.value === 'all') return '搜索全部知识库'
  if (selectedType.value === 'parent') return `在「${selectedParentName.value}」大类中搜索`
  return `在「${selectedChildName.value}」子类中搜索`
})

// 当前选中是否已启用
const currentSelectionEnabled = computed(() => {
  if (selectedType.value === 'parent') {
    const p = categories.value.find(c => c.code === selectedCode.value)
    return p?.user_enabled === true
  }
  if (selectedType.value === 'child') {
    for (const p of categories.value) {
      for (const ch of (p.children || [])) {
        if (ch.code === selectedCode.value) return ch.user_enabled === true
      }
    }
  }
  return false
})

// ===== 用户私有知识库分类管理 =====

// 用户已配置的一级分类列表（去重）
const userParentCategories = computed(() => {
  const set = new Set()
  for (const item of userList.value) {
    const cat = (item.category || '').trim()
    if (!cat) continue
    const parts = cat.split('/')
    const parent = parts[0].trim()
    if (parent) set.add(parent)
  }
  return Array.from(set).sort()
})

// 当前选中一级分类下的已有二级分类列表（去重）
const userChildCategoriesOfParent = computed(() => {
  const parent = (form.parentCategory || '').trim()
  if (!parent) return []
  const set = new Set()
  for (const item of userList.value) {
    const cat = (item.category || '').trim()
    if (!cat) continue
    const parts = cat.split('/')
    if (parts[0].trim() === parent && parts.length > 1) {
      const child = parts.slice(1).join('/').trim()
      if (child) set.add(child)
    }
  }
  return Array.from(set).sort()
})

// 格式化展示用户私有 KB 的分类面包屑
function formatUserCategory(category) {
  const cat = (category || '').trim()
  if (!cat) return '未分类'
  const parts = cat.split('/')
  if (parts.length === 1) return parts[0]
  return `${parts[0]} › ${parts.slice(1).join('/')}`
}

// ===== 树形展开/折叠 =====
function toggleParentExpand(code) {
  const s = new Set(expandedParents.value)
  if (s.has(code)) s.delete(code)
  else s.add(code)
  expandedParents.value = s
}

function expandAllCategories() {
  expandedParents.value = new Set(categories.value.map(c => c.code).filter(Boolean))
}

function collapseAllCategories() {
  expandedParents.value = new Set()
}

// ===== 选中分类 =====
function selectAllCategories() {
  selectedType.value = 'all'
  selectedCode.value = ''
  filter.keyword = ''
  loadLearned()
}

function selectParentCategory(code) {
  selectedType.value = 'parent'
  selectedCode.value = code
  filter.keyword = ''
  if (!expandedParents.value.has(code)) {
    const s = new Set(expandedParents.value)
    s.add(code)
    expandedParents.value = s
  }
  loadLearned()
}

function selectChildCategory(code) {
  selectedType.value = 'child'
  selectedCode.value = code
  filter.keyword = ''
  loadLearned()
}

// ===== 加载数据 =====
async function loadCategories() {
  loading.categories = true
  try {
    const res = await listKbCategories()
    const list = res.data || res || []
    categories.value = list
    if (list.length && expandedParents.value.size === 0) {
      const first = list[0]
      if (first?.code) {
        expandedParents.value = new Set([first.code])
      }
    }
    if (!selectedType.value || selectedType.value === 'all') {
      await loadLearned()
    }
  } catch (e) {
    showToast('加载分类失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.categories = false
  }
}

async function loadLearned() {
  loading.learned = true
  try {
    let res
    if (selectedType.value === 'all') {
      res = await listLearnedKb({ keyword: filter.keyword })
    } else if (selectedType.value === 'parent') {
      res = await listLearnedKbByParentCategory(selectedCode.value, { keyword: filter.keyword })
    } else if (selectedType.value === 'child') {
      res = await listLearnedKbByCategory(selectedCode.value, { keyword: filter.keyword })
    }
    learnedList.value = res?.data || res || []
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

// ===== 启用/取消启用 =====
async function toggleParentBind(parent) {
  if (!parent?.code) return
  loading.bindParent = parent.code
  try {
    if (parent.user_enabled) {
      const res = await unbindParentCategory(parent.code)
      const count = res?.data?.unbound_count ?? res?.unbound_count ?? 0
      showToast(`已取消启用「${parent.name}」大类（${count} 条）`)
    } else {
      const res = await bindParentCategory(parent.code)
      const count = res?.data?.bound_count ?? res?.bound_count ?? 0
      showToast(`已启用「${parent.name}」大类下 ${count} 条知识库`)
    }
    await Promise.all([loadCategories(), loadBindings()])
    if (selectedType.value === 'parent' && selectedCode.value === parent.code) {
      await loadLearned()
    } else if (selectedType.value === 'child') {
      const isInParent = (parent.children || []).some(ch => ch.code === selectedCode.value)
      if (isInParent) await loadLearned()
    }
  } catch (e) {
    showToast('操作失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.bindParent = null
  }
}

async function toggleChildBind(child, parent) {
  if (!child?.code) return
  loading.bindChild = child.code
  try {
    if (child.user_enabled) {
      const res = await unbindCategory(child.code)
      const count = res?.data?.unbound_count ?? res?.unbound_count ?? 0
      showToast(`已取消启用「${child.name}」子类（${count} 条）`)
    } else {
      const res = await bindCategory(child.code)
      const count = res?.data?.bound_count ?? res?.bound_count ?? 0
      showToast(`已启用「${child.name}」子类下 ${count} 条知识库`)
    }
    await Promise.all([loadCategories(), loadBindings()])
    if (selectedType.value === 'child' && selectedCode.value === child.code) {
      await loadLearned()
    }
  } catch (e) {
    showToast('操作失败：' + (e?.message || '未知错误'), true)
  } finally {
    loading.bindChild = null
  }
}

async function toggleCurrentBind() {
  if (selectedType.value === 'all') return
  loading.bindCategory = true
  try {
    if (selectedType.value === 'parent') {
      if (currentSelectionEnabled.value) {
        const res = await unbindParentCategory(selectedCode.value)
        const count = res?.data?.unbound_count ?? res?.unbound_count ?? 0
        showToast(`已取消启用该大类（${count} 条）`)
      } else {
        const res = await bindParentCategory(selectedCode.value)
        const count = res?.data?.bound_count ?? res?.bound_count ?? 0
        showToast(`已启用该大类下 ${count} 条知识库`)
      }
    } else if (selectedType.value === 'child') {
      if (currentSelectionEnabled.value) {
        const res = await unbindCategory(selectedCode.value)
        const count = res?.data?.unbound_count ?? res?.unbound_count ?? 0
        showToast(`已取消启用该子类（${count} 条）`)
      } else {
        const res = await bindCategory(selectedCode.value)
        const count = res?.data?.bound_count ?? res?.bound_count ?? 0
        showToast(`已启用该子类下 ${count} 条知识库`)
      }
    }
    await Promise.all([loadCategories(), loadBindings()])
    await loadLearned()
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

// ===== 用户私有 KB =====
function openCreateUserKb() {
  editingId.value = null
  form.title = ''
  form.content = ''
  form.parentCategory = ''
  form.childCategory = ''
  form.tags = ''
  formVisible.value = true
}

function editUserKb(item) {
  editingId.value = item.id
  form.title = item.title || ''
  form.content = item.content || ''
  form.tags = item.tags || ''
  const cat = (item.category || '').trim()
  if (cat) {
    const parts = cat.split('/')
    form.parentCategory = parts[0].trim()
    form.childCategory = parts.length > 1 ? parts.slice(1).join('/').trim() : ''
  } else {
    form.parentCategory = ''
    form.childCategory = ''
  }
  formVisible.value = true
}

async function saveUserKb() {
  const title = (form.title || '').trim()
  const content = (form.content || '').trim()
  if (!title || !content) {
    showToast('问题和回答必填', true)
    return
  }
  if (title.length > 100 || content.length > 5000) {
    showToast('问题或回答超出长度限制', true)
    return
  }
  const parent = (form.parentCategory || '').trim()
  const child = (form.childCategory || '').trim()
  let category = ''
  if (parent && child) {
    category = `${parent}/${child}`
  } else if (parent) {
    category = parent
  } else if (child) {
    showToast('请先选择或输入一级分类', true)
    return
  }
  loading.save = true
  try {
    const payload = {
      title,
      content,
      category,
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
.kb-settings {
  padding: 20px 24px;
  width: 100%;
  min-width: 0;
}

/* ===== 页面标题 ===== */
.page-header {
  margin-bottom: 20px;
}
.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  color: #15213d;
  letter-spacing: -0.3px;
}
.page-subtitle {
  margin: 6px 0 0;
  font-size: 14px;
  color: #7a879e;
}

/* ===== 平台横幅 ===== */
.kb-banner {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 50%, #f0f0ff 100%);
  padding: 20px 24px;
  border-radius: 16px;
  margin-bottom: 16px;
  border: 1px solid #d0e3ff;
  box-shadow: 0 2px 8px rgba(13, 107, 255, 0.06);
}
.kb-banner-icon {
  font-size: 32px;
  flex-shrink: 0;
  margin-top: 2px;
}
.kb-banner-content {
  flex: 1;
  min-width: 0;
}
.kb-banner-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 8px;
  color: #15213d;
}
.kb-banner-desc {
  font-size: 13px;
  color: #5a6a85;
  line-height: 1.7;
  margin: 0;
}
.kb-banner-stats {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.kb-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
  padding: 10px 16px;
  border-radius: 12px;
  min-width: 80px;
  border: 1px solid rgba(255, 255, 255, 0.6);
}
.kb-stat-item b {
  font-size: 22px;
  font-weight: 800;
  color: #0d6bff;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.kb-stat-item span {
  font-size: 11px;
  color: #7a879e;
  margin-top: 2px;
  font-weight: 600;
}
.kb-stat-enabled b { color: #16bf78; }

/* ===== 知识库使用说明 ===== */
.kb-info-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: linear-gradient(135deg, #fffbf0 0%, #fff7e6 100%);
  border: 1px solid #ffe58f;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 20px;
}
.kb-info-icon {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 1px;
}
.kb-info-content { flex: 1; }
.kb-info-title {
  font-size: 14px;
  font-weight: 700;
  color: #8a6d3b;
  margin-bottom: 6px;
}
.kb-info-desc {
  font-size: 12px;
  color: #8a6d3b;
  line-height: 1.7;
  margin: 0 0 4px;
}
.kb-info-desc:last-child { margin-bottom: 0; }
.kb-info-chain {
  display: inline-block;
  background: rgba(250, 173, 20, 0.2);
  color: #8a6d3b;
  padding: 2px 10px;
  border-radius: 6px;
  font-weight: 600;
  margin: 0 4px;
  font-size: 12px;
}
.kb-info-inline {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 10px;
  padding: 14px 18px;
  font-size: 13px;
  color: #8a6d3b;
  line-height: 1.7;
  margin-bottom: 16px;
}
.info-icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }

/* ===== 工具栏 ===== */
.kb-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  justify-content: flex-end;
}
.kb-toolbar button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border-radius: 10px;
  border: 1px solid #e4ebf5;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.18s;
}
.kb-toolbar button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.kb-toolbar button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
.btn-add {
  background: linear-gradient(135deg, #0d6bff 0%, #2d5bff 100%);
  color: white;
  border-color: transparent !important;
}
.btn-add:hover {
  background: linear-gradient(135deg, #0a5ae6 0%, #2550e6 100%);
}
.btn-feedback {
  background: white;
  color: #526079;
}
.btn-feedback:hover {
  border-color: #0d6bff;
  color: #0d6bff;
}
.btn-icon { font-size: 14px; }

/* ===== Tabs ===== */
.kb-tabs {
  display: flex;
  gap: 4px;
  background: #f5f7fb;
  padding: 4px;
  border-radius: 12px;
  margin-bottom: 20px;
  width: fit-content;
}
.kb-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #667085;
  transition: all 0.18s;
}
.kb-tabs button:hover {
  color: #0d6bff;
  background: rgba(13, 107, 255, 0.06);
}
.kb-tabs button.active {
  color: #0d6bff;
  background: white;
  box-shadow: 0 2px 6px rgba(31, 53, 94, 0.08);
}
.tab-icon { font-size: 15px; }

/* ===== 左右分栏布局 ===== */
.kb-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 20px;
  min-height: 600px;
}

/* ===== 左侧树形导航 ===== */
.kb-sidebar {
  border: 1px solid #e4ebf5;
  border-radius: 16px;
  padding: 0;
  background: white;
  max-height: calc(100vh - 280px);
  overflow-y: auto;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.04);
}
.kb-sidebar::-webkit-scrollbar { width: 4px; }
.kb-sidebar::-webkit-scrollbar-thumb { background: #dce5f2; border-radius: 4px; }

.kb-sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 16px 12px;
  border-bottom: 1px solid #f0f3f8;
  position: sticky;
  top: 0;
  background: white;
  z-index: 1;
  border-radius: 16px 16px 0 0;
}
.kb-sidebar-title {
  font-size: 14px;
  color: #15213d;
  font-weight: 700;
}
.kb-sidebar-actions { display: flex; gap: 6px; }
.btn-mini {
  width: 28px;
  height: 28px;
  border: 1px solid #e4ebf5;
  background: #f8fafd;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  color: #667085;
  padding: 0;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.btn-mini:hover {
  background: #edf5ff;
  border-color: #0d6bff;
  color: #0d6bff;
}

.kb-tree { padding: 10px 12px 16px; }

/* 全部 */
.kb-tree-all {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px 14px;
  border: none;
  background: linear-gradient(135deg, #fff9e6 0%, #fff3cd 100%);
  cursor: pointer;
  border-radius: 10px;
  text-align: left;
  font-size: 13px;
  font-weight: 700;
  color: #8a6d3b;
  margin-bottom: 8px;
  transition: all 0.18s;
  border: 1px solid #ffeaa7;
}
.kb-tree-all:hover {
  background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
  transform: translateX(2px);
}
.kb-tree-all.active {
  background: linear-gradient(135deg, #faad14 0%, #d48806 100%);
  color: white;
  border-color: #d48806;
}
.kb-tree-all.active .kb-tree-count {
  background: rgba(255, 255, 255, 0.25);
  color: white;
}

/* 一级分类 */
.kb-tree-parent { margin-bottom: 4px; }
.kb-tree-parent-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 10px 10px 12px;
  border-radius: 10px;
  background: white;
  border: 1px solid transparent;
  border-left: 3px solid #4A6CF7;
  transition: all 0.15s;
  margin-bottom: 2px;
}
.kb-tree-parent-row:hover {
  background: #f6f9ff;
  border-color: #e4ebf5;
}
.kb-tree-parent-row.active {
  background: linear-gradient(135deg, #e6f3ff 0%, #d0e7ff 100%);
  border-color: #91caff;
}
.kb-tree-toggle {
  width: 20px;
  height: 20px;
  border: none;
  background: none;
  cursor: pointer;
  padding: 0;
  color: #98a2b3;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.15s;
}
.kb-tree-toggle:hover {
  color: #0d6bff;
  background: rgba(13, 107, 255, 0.08);
}
.kb-toggle-icon {
  display: inline-flex;
  transition: transform 0.2s;
  align-items: center;
  justify-content: center;
}
.kb-toggle-icon.expanded { transform: rotate(90deg); }
.kb-tree-parent-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  font-weight: 600;
  color: #1a2742;
  padding: 0;
}
.kb-tree-parent-row.active .kb-tree-parent-info { color: #0958d9; }
.kb-tree-icon { font-size: 15px; }
.kb-tree-name { flex: 1; }
.kb-tree-count {
  font-size: 11px;
  background: #f0f3f8;
  color: #667085;
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 24px;
  text-align: center;
  font-weight: 600;
}
.kb-tree-parent-row.active .kb-tree-count {
  background: rgba(13, 107, 255, 0.15);
  color: #0d6bff;
}

/* 一级分类启用按钮 */
.kb-tree-bind {
  width: 26px;
  height: 26px;
  border: 1.5px solid #e4ebf5;
  background: white;
  cursor: pointer;
  border-radius: 50%;
  padding: 0;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s;
  flex-shrink: 0;
}
.kb-tree-bind:hover {
  transform: scale(1.1);
}
.kb-tree-bind.is-off { color: #98a2b3; border-color: #e4ebf5; }
.kb-tree-bind.is-off:hover { color: #16bf78; border-color: #16bf78; background: #f0fdf4; }
.kb-tree-bind.is-partial { color: #f59e0b; border-color: #fcd34d; background: #fffbeb; }
.kb-tree-bind.is-partial:hover { background: #f59e0b; color: white; border-color: #f59e0b; }
.kb-tree-bind.is-on { color: white; border-color: #16bf78; background: #16bf78; }
.kb-tree-bind.is-on:hover { background: #059669; border-color: #059669; }
.kb-tree-bind:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.kb-tree-bind-mini { width: 22px; height: 22px; }

/* 二级子分类 */
.kb-tree-children {
  margin-left: 26px;
  padding: 4px 0 4px 10px;
  border-left: 1.5px dashed #dce5f2;
}
.kb-tree-child-row {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
  color: #526079;
  transition: all 0.15s;
  margin-bottom: 2px;
}
.kb-tree-child-row:hover {
  background: #f0f5ff;
  color: #0d6bff;
}
.kb-tree-child-row.active {
  background: #0d6bff;
  color: white;
}
.kb-tree-child-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  font-size: 12px;
  color: inherit;
  padding: 0;
  font-weight: 500;
}
.kb-tree-child-dot {
  width: 5px;
  height: 5px;
  background: currentColor;
  border-radius: 50%;
  opacity: 0.5;
}
.kb-tree-child-row.active .kb-tree-child-dot {
  opacity: 1;
  background: white;
}
.kb-tree-child-name { flex: 1; }
.kb-tree-child-count {
  font-size: 10px;
  background: rgba(0, 0, 0, 0.05);
  color: #98a2b3;
  padding: 1px 7px;
  border-radius: 8px;
  min-width: 20px;
  text-align: center;
  font-weight: 600;
}
.kb-tree-child-row.active .kb-tree-child-count {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}
.kb-tree-empty {
  padding: 8px 12px;
  font-size: 11px;
  color: #c0c8d5;
  font-style: italic;
}

/* ===== 右侧内容区 ===== */
.kb-content {
  border: 1px solid #e4ebf5;
  border-radius: 16px;
  padding: 20px;
  background: white;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.04);
}
.kb-content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.kb-content-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.kb-content-title {
  font-size: 18px;
  font-weight: 800;
  color: #15213d;
}
.kb-content-subtitle {
  font-size: 13px;
  color: #98a2b3;
  font-weight: 500;
}
.kb-filter {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.search-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.search-icon {
  position: absolute;
  left: 12px;
  color: #98a2b3;
  pointer-events: none;
}
.kb-filter input {
  padding: 10px 14px 10px 38px;
  border: 1px solid #e4ebf5;
  border-radius: 10px;
  min-width: 240px;
  font-size: 13px;
  transition: all 0.18s;
  background: #f8fafd;
}
.kb-filter input:focus {
  outline: none;
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, 0.1);
  background: white;
}
.kb-filter button {
  padding: 10px 18px;
  border: 1px solid #e4ebf5;
  background: white;
  cursor: pointer;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.15s;
  color: #526079;
}
.kb-filter button:hover:not(:disabled) {
  background: #f6f9ff;
  border-color: #c7d2fe;
  color: #0d6bff;
}
.kb-filter button:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-search { background: #f5f7fb !important; }
.btn-bind {
  background: linear-gradient(135deg, #16bf78 0%, #059669 100%) !important;
  color: white !important;
  border-color: transparent !important;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn-bind:hover:not(:disabled) {
  background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
  color: white !important;
}
.btn-bind:disabled {
  background: #d1d5db !important;
  border-color: transparent !important;
  cursor: not-allowed;
}

/* ===== 知识卡片列表 ===== */
.kb-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}
.kb-card {
  border: 1px solid #e4ebf5;
  border-radius: 14px;
  padding: 18px;
  transition: all 0.2s;
  background: white;
  position: relative;
}
.kb-card:hover {
  box-shadow: 0 8px 24px rgba(31, 53, 94, 0.08);
  border-color: #c7d2fe;
  transform: translateY(-2px);
}
.kb-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  font-size: 11px;
}
.kb-cat {
  display: inline-flex;
  align-items: center;
  background: #f0f5ff;
  padding: 4px 10px;
  border-radius: 8px;
  color: #0d6bff;
  font-weight: 600;
  font-size: 11px;
}
.kb-cat-parent { color: #0d6bff; margin-right: 4px; opacity: 0.7; }
.kb-cat-user { background: #f0fdf4; color: #16bf78; }
.kb-source { color: #98a2b3; font-size: 11px; font-weight: 500; }
.kb-card-q, .kb-card-a {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  line-height: 1.6;
}
.q-label, .a-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 800;
  flex-shrink: 0;
  margin-top: 1px;
}
.q-label {
  background: linear-gradient(135deg, #0d6bff 0%, #2d5bff 100%);
  color: white;
}
.a-label {
  background: linear-gradient(135deg, #16bf78 0%, #059669 100%);
  color: white;
}
.q-text {
  font-weight: 600;
  font-size: 14px;
  color: #1a2742;
}
.a-text {
  font-size: 13px;
  color: #526079;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.kb-card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.kb-tag {
  background: #f8fafd;
  color: #667085;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  border: 1px solid #e4ebf5;
}
.kb-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid #f0f3f8;
}
.kb-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.kb-card-status {
  display: flex;
  align-items: center;
  gap: 10px;
}
.btn-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: #0d6bff;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.15s;
}
.btn-link:hover {
  background: #edf5ff;
  text-decoration: none;
}
.btn-link:disabled { color: #c0c8d5; cursor: not-allowed; }
.btn-link.danger { color: #ef4444; }
.btn-link.danger:hover { background: #fef2f2; }
.btn-link.primary { color: #16bf78; }
.btn-link.primary:hover { background: #f0fdf4; }
.kb-bound {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #16bf78;
  font-weight: 700;
  font-size: 12px;
}
.kb-card-ref {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #fef3c7;
  font-size: 11px;
  color: #f59e0b;
  line-height: 1.5;
}

/* 空状态 */
.kb-empty {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 40px;
  color: #98a2b3;
}
.kb-empty-icon { font-size: 48px; margin-bottom: 12px; opacity: 0.6; }
.kb-empty-text { font-size: 14px; font-weight: 500; }

/* 加载状态 */
.kb-loading, .kb-loading-large {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #98a2b3;
  font-size: 13px;
  padding: 40px;
}
.kb-loading { padding: 30px; }
.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2.5px solid #e4ebf5;
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-spinner.large {
  width: 36px;
  height: 36px;
  border-width: 3px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.btn-spinner.small {
  width: 12px;
  height: 12px;
  border-width: 1.5px;
  border-top-color: #0d6bff;
  border-color: rgba(13, 107, 255, 0.2);
}

/* ===== 弹窗 ===== */
.kb-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(20, 36, 58, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  animation: fadeIn 0.2s ease;
  padding: 20px;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.kb-modal {
  background: white;
  border-radius: 20px;
  max-width: 640px;
  width: 100%;
  max-height: 85vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 28px 80px rgba(17, 35, 67, 0.25);
  animation: modalIn 0.25s cubic-bezier(0.2, 1, 0.3, 1);
}
@keyframes modalIn {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.kb-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 22px 24px 16px;
  border-bottom: 1px solid #f0f3f8;
}
.kb-modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #15213d;
}
.kb-modal-close {
  width: 32px;
  height: 32px;
  border: none;
  background: #f5f7fb;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667085;
  transition: all 0.15s;
}
.kb-modal-close:hover {
  background: #fee2e2;
  color: #ef4444;
}
.kb-modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}
.kb-modal-body::-webkit-scrollbar { width: 4px; }
.kb-modal-body::-webkit-scrollbar-thumb { background: #dce5f2; border-radius: 4px; }
.kb-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px 22px;
  border-top: 1px solid #f0f3f8;
}
.kb-modal-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  color: #98a2b3;
}

/* 详情弹窗内容 */
.kb-detail-meta {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
  padding: 16px;
  background: #f8fafd;
  border-radius: 12px;
}
.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.meta-label {
  font-size: 11px;
  color: #98a2b3;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.meta-value {
  font-size: 14px;
  color: #1a2742;
  font-weight: 600;
}
.kb-detail-section {
  margin-bottom: 16px;
}
.detail-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #1a2742;
  margin-bottom: 8px;
}
.kb-detail-text {
  background: #f8fafd;
  padding: 14px 16px;
  border-radius: 10px;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.7;
  color: #344054;
  border: 1px solid #eef2f7;
}
.kb-detail-ref {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 16px;
  padding: 12px 16px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  font-size: 12px;
  color: #92400e;
  line-height: 1.6;
}

/* 表单 */
.kb-form { display: flex; flex-direction: column; gap: 4px; }
.form-group {
  margin-bottom: 16px;
}
.form-group:last-child { margin-bottom: 0; }
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.kb-form label {
  display: block;
  font-size: 13px;
  color: #344054;
  margin-bottom: 6px;
  font-weight: 600;
}
.required { color: #ef4444; margin-left: 2px; }
.form-hint {
  font-size: 12px;
  color: #98a2b3;
  margin: 4px 0 0;
  line-height: 1.5;
}
.kb-form input,
.kb-form textarea,
.feedback-textarea {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #e4ebf5;
  border-radius: 10px;
  font-size: 13px;
  font-family: inherit;
  transition: all 0.18s;
  background: #f8fafd;
  box-sizing: border-box;
}
.kb-form input:focus,
.kb-form textarea:focus,
.feedback-textarea:focus {
  outline: none;
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, 0.1);
  background: white;
}
.kb-form input:disabled { background: #f5f5f5; cursor: not-allowed; }
.kb-form textarea, .feedback-textarea {
  resize: vertical;
  min-height: 100px;
  line-height: 1.6;
}
.feedback-textarea { min-height: 140px; }

.btn-modal {
  padding: 10px 20px;
  border: 1px solid #e4ebf5;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  background: white;
  color: #526079;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn-modal:hover { background: #f6f9ff; border-color: #c7d2fe; color: #0d6bff; }
.btn-modal:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary {
  background: linear-gradient(135deg, #0d6bff 0%, #2d5bff 100%) !important;
  color: white !important;
  border-color: transparent !important;
}
.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #0a5ae6 0%, #2550e6 100%) !important;
  color: white !important;
}

/* ===== Toast ===== */
.kb-toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 24px;
  border-radius: 12px;
  color: white;
  z-index: 3000;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.18);
  font-size: 14px;
  font-weight: 600;
  animation: toastIn 0.25s ease;
}
@keyframes toastIn {
  from { opacity: 0; transform: translate(-50%, -12px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}
.toast-icon { font-size: 16px; }
.kb-toast.is-success { background: linear-gradient(135deg, #16bf78 0%, #059669 100%); }
.kb-toast.is-error { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }

/* ===== 用户知识库卡片特殊样式 ===== */
.kb-user-card { border-color: #dcfce7; }
.kb-user-card:hover { border-color: #86efac; }

/* ===== 响应式 ===== */
@media (max-width: 1200px) {
  .kb-layout { grid-template-columns: 260px 1fr; }
  .kb-list { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .kb-settings { padding: 16px; }
  .kb-banner { flex-direction: column; }
  .kb-banner-stats { width: 100%; }
  .kb-layout { grid-template-columns: 1fr; }
  .kb-sidebar { max-height: 320px; position: static; }
  .kb-content-header { flex-direction: column; align-items: stretch; }
  .kb-filter { width: 100%; }
  .kb-filter input { min-width: 0; flex: 1; }
  .form-row { grid-template-columns: 1fr; }
}
</style>
