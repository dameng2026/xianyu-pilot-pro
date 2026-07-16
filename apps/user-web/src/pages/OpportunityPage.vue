<template>
  <div class="grid opportunity-layout" style="grid-template-columns:minmax(0,1fr) 420px;gap:18px">
    <div>
      <div v-if="error" class="global-notice error">{{ error }}</div>
      <div v-if="accountLoadError" class="global-notice error">闲鱼账号状态不可用：{{ accountLoadError }}</div>
      <CardPanel>
        <div class="toolbar">
          <select v-model="mode" class="input" style="max-width:110px">
            <option value="search">商品</option>
            <option value="shop">店铺</option>
          </select>
          <select v-if="mode==='search'" v-model="searchMode" class="input" style="max-width:120px" title="快速搜索直调闲鱼MTOP API(约1秒)；慢速搜索使用浏览器加载页面(约2-3秒)；自动降级先尝试快速搜索失败则改用慢速搜索">
            <option value="auto">智能模式</option>
            <option value="fast">快速搜索</option>
            <option value="slow">慢速搜索</option>
          </select>
          <input v-if="mode==='search'" v-model="keyword" class="input large" style="flex:1;height:58px;font-size:16px" placeholder="输入商品关键词，例如 iPhone 15、露营车、二手相机" @keyup.enter="doSearch">
          <input v-else v-model="shopUrl" class="input large" style="flex:1;height:58px;font-size:16px" placeholder="粘贴闲鱼店铺链接，例如 https://www.goofish.com/personal?userId=..." @keyup.enter="doCollectShop">
          <AppButton type="primary" :disabled="searchLoading || shopLoading || (mode === 'search' && !accountAvailable)" @click="mode==='search'?doSearch():doCollectShop()">{{ searchLoading ? '搜索中...' : shopLoading ? '抓取中...' : mode==='search' ? '开始搜索' : '开始抓取' }}</AppButton>
        </div>
        <p class="subtle">支持两种商机发掘方式：输入关键词搜索商品发现潜在商机；粘贴闲鱼店铺链接获取店铺全部商品。商品关键词搜索会使用已登录闲鱼账号 Cookie 进行实时 MTOP 搜索；店铺抓取走 Node 爬虫服务。</p>
        <div class="chips" style="margin-top:18px">
          <b>热门趋势：</b>
          <span v-for="t in tags" :key="t" class="chip" @click="clickTag(t)">{{ t }}</span>
          <span class="chip" @click="rotateTags">换一换</span>
        </div>
        <div v-if="stats" class="metric-row" style="margin-top:18px">
          <div class="metric-tile"><span>当前页热度估算</span><b>{{ stats.searchHeat }}</b></div>
          <div class="metric-tile"><span>商品总数</span><b>{{ stats.totalCount }}</b></div>
          <div class="metric-tile"><span>在售商品</span><b>{{ stats.onSale }}</b></div>
          <div class="metric-tile"><span>想要人数</span><b>{{ stats.wantTotal }}</b></div>
          <div class="metric-tile"><span>当前页竞争度估算</span><b>{{ stats.competition }}</b></div>
        </div>
      </CardPanel>

      <CardPanel style="margin-top:16px">
        <div class="toolbar">
          <span class="subtle">{{ searchLoading || shopLoading ? '加载中...' : resultCountText }}</span>
          <div style="flex:1"></div>
          <AppButton v-if="mode==='shop' && shopResults.length && !allCollected" type="primary" :disabled="shopLoading" @click="doCollectAll">一键采集全部</AppButton>
          <AppButton @click="resetView">重置</AppButton>
        </div>

        <div v-if="searchLoading || shopLoading" class="loading-wrap" style="padding:60px 0;text-align:center">
          <div class="spinner"></div>
          <p class="subtle" style="margin-top:12px">{{ mode==='search' ? '正在搜索商品...' : shopJobId ? '正在抓取店铺商品（异步处理中，请稍候）...' : '正在加载商品...' }}</p>
        </div>

        <EmptyState v-else-if="!searched && !collected" icon="🔍" title="开始发掘商机" description="在上方输入关键词或粘贴店铺链接，开始发掘闲鱼商机。" style="padding:60px 0" />

        <EmptyState v-else-if="!items.length" icon="📭" title="未找到相关商品" description="请尝试其他关键词，或检查店铺链接是否有效。" style="padding:60px 0" />

        <div v-else>
          <div v-for="(item, i) in items" :key="item.link + i" :class="['op-product', {active: selectedItem && selectedItem.link === item.link}]" @click="selectItem(item)">
            <input type="checkbox" :checked="selectedItem && selectedItem.link === item.link">
            <div class="product-thumb">
              <img v-if="item.image" :src="item.image" alt="" style="width:100%;height:100%;object-fit:cover">
            </div>
            <div style="flex:1;min-width:0">
              <h3 style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="item.title">{{ item.title }}</h3>
              <p style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <b style="color:#ef4444;font-size:20px">{{ item.price || '价格未知' }}</b>
                <span v-if="item.soldCount" class="chip" style="font-size:12px;color:#7a879e">已售{{ item.soldCount }}</span>
                <span v-if="item.seller" class="chip" style="font-size:12px;color:#7a879e">{{ item.seller }}</span>
                <span v-if="item.area" class="chip" style="font-size:12px;color:#7a879e">{{ item.area }}</span>
                <a v-if="item.link" :href="item.link" target="_blank" rel="noopener noreferrer" class="chip" style="text-decoration:none;color:#0d6bff">查看链接</a>
              </p>
            </div>
            <button class="app-btn" @click.stop="selectedItem = item">详情</button>
          </div>
          <!-- 分页控件 -->
          <div v-if="mode==='search' && searched && totalItems > pageSize" class="pagination">
            <button class="app-btn" :disabled="currentPage <= 1 || searchLoading" @click="goToPage(currentPage - 1)">上一页</button>
            <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页</span>
            <button class="app-btn" :disabled="!hasMore || searchLoading" @click="loadMore">下一页</button>
          </div>
        </div>
      </CardPanel>
    </div>

    <div class="right-drawer">
      <div class="steps">
        <span :class="{active: step >= 1}">1 抓取</span>
        <span :class="{active: step >= 2}">2 改写</span>
        <span :class="{active: step >= 3}">3 配置</span>
        <span :class="{active: step >= 4}">4 发布</span>
      </div>

      <!-- 草稿面板 -->
      <div v-if="savedDrafts.length" class="draft-bar">
        <div class="draft-bar-header" @click="showDrafts = !showDrafts">
          <span>📋 草稿（{{ savedDrafts.length }}）</span>
          <span class="draft-toggle">{{ showDrafts ? '▲' : '▼' }}</span>
        </div>
        <Transition name="slide-down">
          <div v-if="showDrafts" class="draft-list">
            <div v-for="d in savedDrafts" :key="d.id" class="draft-item">
              <div class="draft-info">
                <img v-if="d.productImage" :src="d.productImage" alt="" class="draft-thumb">
                <div class="draft-meta">
                  <span class="draft-title">{{ d.productTitle }}</span>
                  <span class="draft-time">步骤{{ d.step || 1 }} · {{ d.savedAt }}</span>
                </div>
              </div>
              <div class="draft-actions">
                <AppButton size="small" @click="restoreDraft(d)">恢复</AppButton>
                <button class="draft-del" title="删除" @click="deleteDraft(d.id)">×</button>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <template v-if="selectedItem">
        <!-- ============ Step 1: 抓取板块 ============ -->
        <Transition name="step-fade">
          <div v-show="step === 1" key="step1" class="step-panel">
            <div class="step-scroll">
              <CardPanel class="op-detail-hero" style="box-shadow:none">
                <div class="detail-cover">
                  <img v-if="selectedItem.image" :src="selectedItem.image" alt="">
                  <div v-else class="detail-cover-empty">无图</div>
                </div>
                <div class="detail-main">
                  <span class="source-pill">{{ mode==='search' ? '商品搜索' : '店铺采集' }}</span>
                  <h3 :title="selectedItem.title">{{ selectedItem.title }}</h3>
                  <div class="detail-price">{{ selectedItem.price || '价格未知' }}</div>
                  <div class="detail-tags">
                    <span v-if="selectedItem.area">{{ selectedItem.area }}</span>
                    <span v-if="selectedItem.seller">{{ selectedItem.seller }}</span>
                    <span v-if="selectedItem.soldCount">已售 {{ selectedItem.soldCount }}</span>
                    <span v-if="selectedItem.wantCount">想要 {{ selectedItem.wantCount }}</span>
                  </div>
                </div>
              </CardPanel>
              <CardPanel title="商品信息" class="detail-card" style="margin-top:12px;box-shadow:none">
                <div class="info-grid">
                  <div><span>商品ID</span><b>{{ extractId(selectedItem) }}</b></div>
                  <div><span>价格</span><b class="red">{{ selectedItem.price || '-' }}</b></div>
                  <div><span>地区</span><b>{{ selectedItem.area || '-' }}</b></div>
                  <div><span>卖家</span><b>{{ selectedItem.seller || '-' }}</b></div>
                </div>
                <div class="desc-box">
                  <span>标题/描述</span>
                  <p>{{ selectedItem.description || selectedItem.title }}</p>
                </div>
                <div class="toolbar" style="margin-top:12px">
                  <a v-if="selectedItem.link" :href="selectedItem.link" target="_blank" rel="noopener noreferrer" class="app-btn">查看原商品</a>
                  <AppButton @click="copyTitle">复制标题</AppButton>
                </div>
                <p v-if="saveMessage" class="subtle" style="margin-top:8px;color:#16bf78">{{ saveMessage }}</p>
              </CardPanel>
            </div>
            <div class="step-footer">
              <AppButton type="primary" size="large" style="width:100%" @click="goToStep(2)">下一步</AppButton>
            </div>
          </div>
        </Transition>

        <!-- ============ Step 2: 改写板块 ============ -->
        <Transition name="step-fade">
          <div v-show="step === 2" key="step2" class="step-panel">
            <div class="step-scroll">
              <CardPanel title="AI商品改写" style="box-shadow:none">
                <div class="rewrite-style-row">
                  <select v-model="rewriteStyle" class="input" style="max-width:160px">
                    <option value="friendly">口语化风格</option>
                    <option value="concise">简洁风格</option>
                    <option value="click">吸引眼球风格</option>
                    <option value="custom">自定义风格</option>
                  </select>
                  <AppButton
                    :disabled="!shouldEnableOpportunityRewriteAction({ rewriteLoading, aiStatusLoading })"
                    :title="aiStatusLoadError ? 'AI 改写状态获取失败，点击后会自动重试' : '点击后会重新校验 AI 改写状态'"
                    @click="handleRewriteAction"
                  >
{{ rewriteButtonText }}
</AppButton>
                </div>
                <div v-if="rewriteStyle === 'custom'" style="margin-top:12px">
                  <textarea v-model="rewriteCustomPrompt" class="input" style="width:100%;min-height:100px;font-size:13px" placeholder="请输入你希望的改写要求，例如：请用更加活泼亲切的语气改写，可以适当使用网络流行语，标题要更有吸引力。"></textarea>
                  <p class="subtle" style="margin:4px 0 0">自定义提示词将传递给 AI 作为改写依据</p>
                </div>
                <p v-if="aiStatusLoadError" class="ai-disabled-tip">AI 改写状态暂时获取失败，点击“开始改写”会自动重试。</p>
                <p v-else-if="!aiStatusLoading && !aiStatus.rewriteEnabled" class="ai-disabled-tip">平台暂未开放AI改写功能，敬请期待</p>
                <div class="form-row"><label>标题</label><input :value="rewriteTitle" maxlength="30" @input="updateRewriteTitle"><span class="char-count">{{ rewriteTitle.length }}/30</span></div>
                <div class="form-row"><label>正文</label><textarea :value="rewriteDescription" style="min-height:150px" @input="updateRewriteDescription"></textarea></div>
                <template v-if="rewriteDraft">
                  <div class="option-line"><span>标签</span><b>{{ (rewriteDraft.tags || []).join('、') || '-' }}</b></div>
                  <div class="option-line"><span>安全检查</span><b :style="{color: rewriteDraft.safety?.blocked ? '#ef4444' : '#16bf78'}">{{ rewriteDraft.safety?.message || '-' }}</b></div>
                </template>
                <div v-if="!rewriteDraft" class="subtle" style="margin-top:8px">选择商品后点击 AI 改写，生成可编辑标题和描述；发布前仍需人工确认真实性、图片授权和平台合规。</div>
              </CardPanel>
            </div>
            <div class="step-footer">
              <div class="step-footer-inner">
                <AppButton @click="goToStep(1)">上一步</AppButton>
                <AppButton type="primary" size="large" style="flex:1" @click="goToStep(3)">下一步</AppButton>
              </div>
            </div>
          </div>
        </Transition>

        <!-- ============ Step 3: 配置板块 ============ -->
        <Transition name="step-fade">
          <div v-show="step === 3" key="step3" class="step-panel">
            <div class="step-scroll">
              <!-- 3a. 商品封面图（AI生成） -->
              <CardPanel title="商品封面图" style="box-shadow:none">
                <div class="image-gen-box">
                  <div class="image-gen-head">
                    <div>
                      <b>AI生成商品图片</b>
                      <span v-if="imageStatusLoading">生图功能状态检测中...</span>
                      <span v-else-if="imageStatus.configured">每张消耗 {{ imageStatus.tokensPerImage ?? '—' }} Token</span>
                      <span v-else-if="imageStatusLoadError">生图状态暂时获取失败，可点击“生成图片”自动重试</span>
                      <span v-else>平台暂未开放生图功能，敬请期待</span>
                    </div>
                    <button type="button" class="light-mini" @click="refreshAiFeatureStatus">刷新配置</button>
                  </div>
                  <p v-if="rewriteDraft?.title || rewriteDraft?.description" class="image-gen-info">将使用改写后的标题与正文作为生图提示词</p>
                  <p v-else class="image-gen-info muted">暂无改写内容，将使用商品原标题与描述作为生图提示词</p>
                  <div class="image-prompt-mode">
                    <label>提示词模式</label>
                    <select v-model="imagePromptMode" class="input tiny-select">
                      <option value="default">默认提示词</option>
                      <option value="custom">自定义提示词</option>
                    </select>
                    <span v-if="imagePromptMode === 'default'" class="image-prompt-help">每次生图前都会重新判断类目并自动匹配后台提示词。</span>
                    <span v-else class="image-prompt-help">自定义模式将始终使用你填写的提示词。</span>
                  </div>
                  <textarea
                    v-if="imagePromptMode === 'custom'"
                    v-model="customImagePrompt"
                    class="input image-prompt-textarea"
                    placeholder="请输入你自己的生图提示词，可使用 {{TITLE}} 和 {{CONTENT}} 占位符"
                  ></textarea>
                  <div class="image-gen-actions">
                    <label>生图模型
                      <select v-model="selectedModelKey" class="input tiny-select" :disabled="!availableImageModels.length">
                        <option v-for="m in availableImageModels" :key="m.moduleKey" :value="m.moduleKey">
                          {{ m.name || m.moduleKey }}
                        </option>
                      </select>
                    </label>
                    <label>数量
                      <select v-model.number="imageCount" class="input tiny-select">
                        <option :value="1">1张</option>
                        <option :value="2">2张</option>
                        <option :value="3">3张</option>
                        <option :value="4">4张</option>
                        <option :value="6">6张</option>
                        <option :value="9">9张</option>
                      </select>
                    </label>
                    <AppButton
                      type="primary"
                      :disabled="imageLoading || imageStatusLoading || (!imageStatus.configured && !imageStatusLoadError)"
                      :title="imageStatusLoadError ? '生图状态获取失败，点击后会自动重试' : (!imageStatusLoading && !imageStatus.configured ? '平台暂未开放生图功能' : '')"
                      @click="handleGenerateImagesAction"
                    >
                      {{ imageLoading ? '生成中...' : '生成图片' }}
                    </AppButton>
                  </div>
                  <div v-if="imageLoading" class="image-gen-hint">
                    <span class="hint-icon">⏳</span>
                    <span class="hint-text">生图预计约需2-3分钟（后端采用多重保障机制），请在此期间勿关闭页面或刷新浏览器</span>
                  </div>
                  <div v-if="generatedImages.length" class="generated-grid">
                    <div
                      v-for="(img, idx) in generatedImages"
                      :key="img.url || img.b64Json || idx"
                      :class="['gen-img-item', { active: isCoverSelected(img) }]"
                    >
                      <button type="button" class="gen-img-select" @click="toggleCoverImage(img)">
                        <img :src="imgUrl(img)" alt="AI生成商品图">
                        <span v-if="isCoverSelected(img)" class="cover-badge">封面</span>
                      </button>
                      <button type="button" class="gen-img-remove" title="删除这张图片" @click.stop="removeGeneratedImage(idx)">×</button>
                    </div>
                  </div>
                  <!-- 生图方式提示 -->
                  <div v-if="imageMethodUsed && !imageLoading" class="image-gen-method">
                    <span class="method-tag">生图通道: {{ 
                      imageMethodUsed === 'proxy-async-poll' ? '最优中转' : 
                      imageMethodUsed === 'async-poll' ? '异步轮询' : 
                      imageMethodUsed === 'direct-sync' ? '同步直连' : 
                      imageMethodUsed === 'async-fallback' ? '异步兜底' : 
                      imageMethodUsed === 'history-recovery' ? '历史恢复' : imageMethodUsed 
                    }}</span>
                  </div>
                  <!-- 历史记录恢复区域 -->
                  <div v-if="imageHistoryRecords.length && !imageLoading && !generatedImages.length" class="image-gen-history">
                    <b>检测到历史生图记录：</b>
                    <div v-for="rec in imageHistoryRecords" :key="rec.id" class="history-record-item">
                      <span>{{ rec.created_time || '' }} | {{ rec.image_count || 0 }}张 | {{ rec.status }}</span>
                      <AppButton size="small" :disabled="imageRecoverLoading" @click="handleRecoverFromHistory(rec)">恢复图片</AppButton>
                    </div>
                  </div>
                </div>
                <!-- 封面预览 + 上传 -->
                <div class="cover-preview-area">
                  <div class="cover-preview-label">
                    商品封面图（{{ configCoverImage.length }}/9）
                    <span class="cover-preview-hint">上传或从下方AI生成图片中选择</span>
                  </div>
                  <div class="cover-preview-content">
                    <div v-for="(coverUrl, idx) in configCoverImage" :key="idx" class="cover-preview-img">
                      <img :src="coverUrl" alt="封面预览">
                      <button type="button" class="cover-remove" title="移除封面" @click.stop="removeCoverImage(idx)">×</button>
                      <span v-if="idx === 0" class="cover-main-badge">主图</span>
                    </div>
                    <label v-if="configCoverImage.length < 9" class="cover-upload-btn" title="上传封面图">
                      <input type="file" accept="image/*" style="display:none" @change="onCoverUpload">
                      <span>+</span>
                    </label>
                  </div>
                </div>
              </CardPanel>

              <!-- 3b. 商品价格 -->
              <CardPanel title="商品价格" style="margin-top:12px;box-shadow:none">
                <div class="price-config-row">
                  <select v-model="configCurrency" class="input" style="max-width:80px">
                    <option value="¥">¥ (CNY)</option>
                    <option value="$">$ (USD)</option>
                  </select>
                  <input v-model="configPrice" type="number" step="0.01" min="0" class="input large" style="flex:1" placeholder="请输入商品价格">
                </div>
              </CardPanel>

              <!-- 3c. 商品库存 -->
              <CardPanel title="商品库存" style="margin-top:12px;box-shadow:none">
                <div class="stock-config-row">
                  <input v-model.number="configStock" type="number" min="0" max="999" class="input large" style="max-width:140px" placeholder="库存数量">
                  <span class="stock-suffix">件</span>
                  <p v-if="configStock < 0" class="stock-warn">库存不能为负数</p>
                </div>
              </CardPanel>

              <!-- 3d. 商品地址 -->
              <CardPanel title="商品地址" style="margin-top:12px;box-shadow:none">
                <div class="draft-location" style="margin-top:0">
                  <label>发布位置 <small>省、市、区均为必填项</small></label>
                  <PublishAddressCascader v-model="selectedPublishAddress" clearable />
                  <p v-if="!isPublishAddressComplete(selectedPublishAddress)" class="subtle">请选择完整的省、市、区后再发布。</p>
                </div>
              </CardPanel>

              <!-- 3d. 商品分类 -->
              <CardPanel title="商品分类" style="margin-top:12px;box-shadow:none">
                <div class="auto-category-hint">
                  <span class="hint-icon">💡</span>
                  <span>上传封面图之后自动获取分类</span>
                  <span v-if="oppAutoCategoryLoading" class="auto-category-spinner">检测中...</span>
                </div>
                <div v-if="oppAutoCategoryMessage" :class="['auto-category-msg', oppAutoCategoryMsgType]">
                  {{ oppAutoCategoryMessage }}
                </div>
                <div v-if="oppAutoCategoryCandidates.length" class="auto-category-candidates">
                  <span class="candidates-label">推荐分类：</span>
                  <button
                    v-for="(cat, idx) in oppAutoCategoryCandidates"
                    :key="cat.catId || idx"
                    type="button"
                    class="candidate-btn"
                    @click="applyOppAutoCategory(cat)"
                  >
                    {{ cat.catName || cat.name }}
                    <small v-if="cat.score">({{ (cat.score * 100).toFixed(1) }}%)</small>
                  </button>
                </div>
                <div class="category-config-row">
                  <input v-model="configCategory" class="input large" style="flex:1" placeholder="输入商品分类，如 手机/数码/家居">
                  <AppButton v-if="aiCategoryStatus.configured" :disabled="aiCategoryLoading || !selectedItem?.title" @click="autoSelectConfigCategory">{{ aiCategoryLoading ? 'AI选择中...' : 'AI自动选择' }}</AppButton>
                  <span v-else-if="aiCategoryLoadError" class="subtle" style="color:#d97706">{{ aiCategoryLoadError }}</span>
                  <span v-else-if="aiCategoryStatus.configured === false" class="subtle">AI 服务未配置</span>
                </div>
                <p v-if="configCategory" class="subtle" style="margin-top:6px;color:#16bf78">当前分类：{{ configCategory }}<span v-if="configCategoryObj" style="color:#888;margin-left:6px">（已识别分类ID）</span></p>
              </CardPanel>

              <!-- 3e. 发货选项 -->
              <CardPanel title="发货选项" style="margin-top:12px;box-shadow:none">
                <div class="shipping-grid">
                  <label class="shipping-item" :class="{ active: shippingMode === 'free' }">
                    <span>包邮</span>
                    <input v-model="shippingMode" type="radio" value="free">
                  </label>
                  <label class="shipping-item" :class="{ active: shippingMode === 'fixed' }">
                    <span>一口价 / 运费</span>
                    <input v-model="shippingMode" type="radio" value="fixed">
                  </label>
                  <label class="shipping-item" :class="{ active: shippingMode === 'none' }">
                    <span>无需邮寄</span>
                    <input v-model="shippingMode" type="radio" value="none">
                  </label>
                  <label class="shipping-item" :class="{ active: supportSelfPick }">
                    <span>支持自提</span>
                    <input v-model="supportSelfPick" type="checkbox">
                  </label>
                </div>
              </CardPanel>
            </div>
            <div class="step-footer">
              <div class="step-footer-inner">
                <AppButton @click="goToStep(2)">上一步</AppButton>
                <AppButton type="primary" size="large" style="flex:1" @click="goToStep(4)">下一步</AppButton>
              </div>
            </div>
          </div>
        </Transition>

        <!-- ============ Step 4: 发布板块 ============ -->
        <Transition name="step-fade">
          <div v-show="step === 4" key="step4" class="step-panel">
            <div class="step-scroll">
              <!-- 发布账号选择 -->
              <CardPanel title="发布账号" style="box-shadow:none">
                <div class="account-select-row">
                  <select v-model="selectedAccountId" class="input" style="width:100%;padding:10px 12px;font-size:14px" :disabled="!accountAvailable">
                    <option :value="null" disabled>{{ accountAvailable ? '请选择发布账号' : '账号状态不可用' }}</option>
                    <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                      {{ acct.nickname || acct.displayName || acct.externalUid || '账号' + acct.id }}
                    </option>
                  </select>
                </div>
                <p v-if="accountAvailable && !accounts.length" class="subtle" style="margin-top:8px;color:#ef4444">暂未添加闲鱼账号，请先到「账号管理」添加</p>
                <p v-else-if="accountLoadError" class="subtle" style="margin-top:8px;color:#ef4444">账号列表加载失败，无法安全选择发布账号</p>
              </CardPanel>
              <CardPanel title="最终确认" style="box-shadow:none">
                <div class="publish-summary-cover">
                  <img v-if="publishCoverImage" :src="publishCoverImage" alt="">
                  <div v-else class="detail-cover-empty">暂无封面图</div>
                </div>
                <div class="publish-summary-info">
                  <div class="option-line"><span>商品标题</span><b>{{ publishTitle || '（未设置标题）' }}</b></div>
                  <div class="option-line"><span>商品价格</span><b style="color:#ef4444;font-size:18px">{{ configCurrency }}{{ configPrice || rewriteDraft?.priceSuggestion || selectedItem.price }}</b></div>
                  <div class="option-line"><span>商品库存</span><b>{{ configStock }} 件</b></div>
                  <div class="option-line"><span>商品分类</span><b>{{ configCategory || '-' }}</b></div>
                  <div class="option-line"><span>发布位置</span><b>{{ selectedPublishAddress?.poiName || '-' }}</b></div>
                  <div class="option-line"><span>发货方式</span><b>{{ shippingLabel }}</b></div>
                  <div v-if="supportSelfPick" class="option-line"><span>支持自提</span><b style="color:#16bf78">是</b></div>
                  <div class="option-line"><span>改写风格</span><b>{{ rewriteStyleLabel }}</b></div>
                </div>
              </CardPanel>
              <div v-if="error" class="global-notice error" style="margin-top:12px">{{ error }}</div>
              <div v-if="saveMessage" class="global-notice success" style="margin-top:12px">{{ saveMessage }}</div>
            </div>
            <div class="step-footer">
              <div class="step-footer-inner">
                <AppButton @click="goToStep(3)">上一步</AppButton>
                <AppButton type="primary" size="large" style="flex:1" :disabled="publishing" @click="doPublish">{{ publishing ? '发布中...' : '发布' }}</AppButton>
              </div>
            </div>
          </div>
        </Transition>
      </template>

      <EmptyState v-else icon="👈" title="请选择商品" description="从左侧列表选择商品查看商机分析、AI 改写和发布详情。" style="padding:40px 0" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import PublishAddressCascader from '../components/PublishAddressCascader.vue'
import { importGoofishStore, getCrawlJobStatus, getGoofishStoreItems, goofishSearch, uploadImage } from '../api/misc.js'
import { rewriteOpportunity, getOpportunityAiStatus, getOpportunityImageStatus, getOpportunityImageModels, generateOpportunityImages, listOpportunityImageHistory, recoverOpportunityImages } from '../api/opportunity.js'
import { getLiteAccounts, checkAccountAuth } from '../api/accounts.js'
import { publishItem, autoCategory } from '../api/items.js'
import { getAiProviderStatus, suggestCategoryByAi } from '../api/aiProvider.js'
import { fetchCategories } from '../api/categories.js'
import { accountAuthUsable, pickPreferredAccount, accountLoginHint } from '../utils/accountAuth.js'
import { friendlyError } from '../utils/friendlyError.js'
import { buildOpportunityRewritePayload, getOpportunityItemIdentity, shouldEnableOpportunityRewriteAction } from '../utils/opportunityPageState.js'
import { isPublishAddressComplete, normalizePublishAddress } from '../utils/publishAddress.js'
import { imageUploadValidationMessage } from '../utils/imageUploadPolicy.js'
import EmptyState from '../components/EmptyState.vue'

const mode = ref('search')
const keyword = ref('')
const shopUrl = ref('')
const error = ref('')
const saveMessage = ref('')
const searchLoading = ref(false)
const shopLoading = ref(false)
const shopJobId = ref(null)
const shopUserId = ref(null)
const searched = ref(false)
const collected = ref(false)
const allCollected = ref(false)
const step = ref(0)
const items = ref([])
const selectedItem = ref(null)
const rewriteLoading = ref(false)
const publishing = ref(false)
const rewriteDraft = ref(null)
const rewriteStyle = ref('friendly')
const rewriteCustomPrompt = ref('')
let rewriteRequestVersion = 0
const DEFAULT_AI_STATUS = { configured: null, rewriteEnabled: null, imageConfigured: null }
const DEFAULT_IMAGE_STATUS = { configured: null, defaultPrompt: '', tokensPerImage: null, size: '1024x1024' }
const aiStatus = ref({ ...DEFAULT_AI_STATUS })
const imageStatus = ref({ ...DEFAULT_IMAGE_STATUS })
const aiStatusLoading = ref(false)
const imageStatusLoading = ref(false)
const aiStatusLoadError = ref('')
const imageStatusLoadError = ref('')
const selectedModelKey = ref('')
const availableImageModels = ref([])
const imagePromptMode = ref('default')
const customImagePrompt = ref('')
const imageCount = ref(1)
const imageLoading = ref(false)
const generatedImages = ref([])
const imageMethodUsed = ref('')
const imageHistoryRecords = ref([])
const imageRecoverLoading = ref(false)
const shopResults = ref([])
const accounts = ref([])
const accountLoaded = ref(false)
const accountAvailable = ref(false)
const accountLoadError = ref('')
const selectedPublishAddress = ref(null)

// 配置板块变量
const configCurrency = ref('¥')
const configPrice = ref('')
const configCategory = ref('')
// 结构化分类信息（由封面图自动识别或 AI 选择设置，存储 catId/channelCatId/tbCatId 等闲鱼官方字段）
// 用户手动编辑输入框时会被清空，仅保留字符串 configCategory
const configCategoryObj = ref(null)
const configStock = ref(1)
const shippingMode = ref('free')
const supportSelfPick = ref(false)

// 自动分类（闲鱼接口）
const oppAutoCategoryLoading = ref(false)
const oppAutoCategoryMessage = ref('')
const oppAutoCategoryMsgType = ref('info')
const oppAutoCategoryCandidates = ref([])

// AI 一键选择分类（与 ProductPublishPage 统一，调用真实 AI Provider）
const aiCategoryStatus = ref({ configured: null })
const aiCategoryLoadError = ref('')
const aiCategoryLoading = ref(false)

// 分页状态
const currentPage = ref(1)
const totalItems = ref(0)
const hasMore = ref(false)
const searchKeyword = ref('')
const pageSize = 20
// 搜索方式：fast=快速搜索(直调MTOP,~1秒) | slow=慢速搜索(浏览器,~2-3秒) | auto=自动降级(默认)
const searchMode = ref('auto')
const usedSearchMode = ref('')  // 记录本次搜索实际使用的模式

const tagPools = [
  ['iPhone 17 Pro Max','小米17','华为Mate 80','Switch 2','开放式耳机','AI录音笔','大疆运动相机','苹果快充套装'],
  ['LABUBU','谷子吧唧','骑行装备','露营折叠车','扫地机器人','宠物烘干箱','婴儿推车','电动滑板车'],
  ['机械键盘套件','电竞显示器','筋膜枪','咖啡机','投影仪','二手相机','户外电源','猫砂盆']
]
const tagIndex = ref(0)
const tags = ref([...tagPools[0]])

// ---- 草稿功能 ----
const DRAFT_KEY = 'opportunity_drafts'
const MAX_DRAFTS = 5
const savedDrafts = ref([])
const showDrafts = ref(true)
let draftAutoSaveTimer = null
let draftVersion = 0 // 递增触发保存

const stats = computed(() => {
  if (!items.value.length) return null
  const total = Number(totalItems.value || items.value.length)
  const local = items.value
  const wantValues = local.map(item => numberLike(item.wantCount)).filter(value => value !== null)
  const soldValues = local.map(item => numberLike(item.soldCount)).filter(value => value !== null)
  const want = wantValues.reduce((sum, value) => sum + value, 0)
  const sold = soldValues.reduce((sum, value) => sum + value, 0)
  const sellerCount = new Set(local.map(item => item.seller).filter(Boolean)).size
  const prices = local.map(item => numberLike(item.price)).filter(n => n !== null && n > 0)
  const avgPrice = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : 0
  const cheapCount = avgPrice ? prices.filter(p => p <= avgPrice * 0.85).length : 0
  const heatScore = want + sold * 2 + total
  const competitionScore = sellerCount + Math.min(total, 50) + Math.max(0, prices.length - cheapCount)
  const heatAvailable = wantValues.length === local.length && soldValues.length === local.length
  const competitionAvailable = local.every(item => String(item.seller || '').trim()) && prices.length === local.length
  return {
    searchHeat: heatAvailable ? (heatScore > 120 ? '高' : heatScore > 40 ? '中' : '低') : '数据不足',
    totalCount: total,
    onSale: local.some(item => item.status !== null) ? local.filter(item => item.status !== null && Number(item.status) !== 3).length : '—',
    wantTotal: wantValues.length === local.length ? formatNum(want) : '—',
    competition: competitionAvailable ? (competitionScore > 65 ? '激烈' : competitionScore > 28 ? '中等' : '较低') : '数据不足'
  }
})

const resultCountText = computed(() => {
  if (!items.value.length) return ''
  const total = totalItems.value || items.value.length
  const start = (currentPage.value - 1) * pageSize + 1
  const end = Math.min(start + items.value.length - 1, total)
  const modeLabel = usedSearchMode.value === 'fast' ? '快速搜索' : usedSearchMode.value === 'slow' ? '慢速搜索' : ''
  return `共 ${total} 个商品，当前显示第 ${start}-${end} 个${modeLabel ? '（' + modeLabel + '）' : ''}`
})

const totalPages = computed(() => {
  const total = totalItems.value || items.value.length
  return Math.max(1, Math.ceil(total / pageSize))
})

// 当前选中的发布账号 ID（用户在发布板块下拉选择）
const selectedAccountId = ref(null)

// 搜索时携带 Cookie 鉴权使用的账号 ID（优先使用用户选择的发布账号，兜底取第一个账号）
const currentAccountId = computed(() => {
  const currentAccount = accounts.value.find(account => String(account?.id ?? '') === String(selectedAccountId.value ?? '')) || null
  if (currentAccount && accountAuthUsable(currentAccount)) {
    return selectedAccountId.value
  }
  return pickPreferredAccount(accounts.value, selectedAccountId.value)?.id || null
})

const configCoverImage = ref([])

const publishCoverImage = computed(() => {
  if (configCoverImage.value.length) return configCoverImage.value[0]
  if (generatedImages.value.length) {
    const img = generatedImages.value[0]
    return img.originalUrl || img.url || ('data:image/png;base64,' + img.b64Json)
  }
  return selectedItem.value?.image || ''
})

const shippingLabel = computed(() => {
  const map = { free: '包邮', fixed: '一口价 / 运费', none: '无需邮寄' }
  return map[shippingMode.value] || '包邮'
})

const rewriteStyleLabel = computed(() => {
  const map = { friendly: '口语化风格', concise: '简洁风格', click: '吸引眼球风格', custom: '自定义风格' }
  return map[rewriteStyle.value] || rewriteStyle.value
})

// 发布时使用的标题：优先使用用户在改写/配置页设置的标题，否则使用原标题
const publishTitle = computed(() => {
  return (rewriteDraft.value?.title?.trim() || selectedItem.value?.title || '').slice(0, 30)
})

const rewriteTitle = computed({
  get: () => rewriteDraft.value?.title || '',
  set: (val) => { if (rewriteDraft.value) rewriteDraft.value.title = val }
})
const rewriteDescription = computed({
  get: () => rewriteDraft.value?.description || '',
  set: (val) => { if (rewriteDraft.value) rewriteDraft.value.description = val }
})
const rewriteButtonText = computed(() => {
  if (rewriteLoading.value) return '改写中...'
  if (rewriteDraft.value?.title && rewriteDraft.value?.description) return '重新改写'
  return '开始改写'
})

function updateRewriteTitle(e) {
  rewriteTitle.value = e.target.value.slice(0, 30)
  triggerAutoSave()
}
function updateRewriteDescription(e) {
  rewriteDescription.value = e.target.value
  triggerAutoSave()
}

function goToStep(target) {
  step.value = target
  saveDraftNow()
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function retryFeatureRequest(requester, retries = 2, delayMs = 800) {
  let lastError = null
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await requester()
    } catch (error) {
      lastError = error
      if (attempt >= retries) break
      await delay(delayMs * (attempt + 1))
    }
  }
  throw lastError
}

function normalizeAiStatusResponse(response) {
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)
    || typeof data.configured !== 'boolean'
    || typeof data.rewriteEnabled !== 'boolean'
    || typeof data.imageConfigured !== 'boolean') {
    throw new Error('AI 功能状态响应格式异常')
  }
  return {
    ...DEFAULT_AI_STATUS,
    ...data,
  }
}

function normalizeImageStatusResponse(response) {
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.configured !== 'boolean') {
    throw new Error('生图功能状态响应格式异常')
  }
  const tokensPerImage = data.tokensPerImage == null ? null : Number(data.tokensPerImage)
  if (tokensPerImage != null && (!Number.isFinite(tokensPerImage) || tokensPerImage < 0)) {
    throw new Error('生图 Token 配置格式异常')
  }
  return {
    ...DEFAULT_IMAGE_STATUS,
    ...data,
    defaultPrompt: typeof data.defaultPrompt === 'string' ? data.defaultPrompt : '',
    tokensPerImage,
    size: typeof data.size === 'string' && data.size.trim() ? data.size : DEFAULT_IMAGE_STATUS.size,
  }
}

function normalizeImageModelsResponse(response) {
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.models)) {
    throw new Error('生图模型列表响应格式异常')
  }
  return data.models.filter(model => model
    && typeof model === 'object'
    && typeof model.moduleKey === 'string'
    && model.moduleKey.trim()
    && model.configured === true
    && model.enabled === true)
}

async function refreshAiFeatureStatus() {
  if (aiStatusLoading.value || imageStatusLoading.value) return
  aiStatusLoading.value = true
  imageStatusLoading.value = true
  aiStatusLoadError.value = ''
  imageStatusLoadError.value = ''
  aiStatus.value = { ...DEFAULT_AI_STATUS }
  imageStatus.value = { ...DEFAULT_IMAGE_STATUS }
  availableImageModels.value = []
  selectedModelKey.value = ''
  try {
    const [aiResult, imageResult, modelsResult] = await Promise.allSettled([
      retryFeatureRequest(() => getOpportunityAiStatus()),
      retryFeatureRequest(() => getOpportunityImageStatus()),
      retryFeatureRequest(() => getOpportunityImageModels()),
    ])

    if (aiResult.status === 'fulfilled') {
      try {
        aiStatus.value = normalizeAiStatusResponse(aiResult.value)
      } catch (statusError) {
        aiStatusLoadError.value = friendlyError(statusError, 'AI 改写状态获取失败，请稍后重试')
      }
    } else {
      aiStatusLoadError.value = friendlyError(aiResult.reason, 'AI 改写状态获取失败，请稍后重试')
    }

    if (imageResult.status === 'fulfilled') {
      try {
        imageStatus.value = normalizeImageStatusResponse(imageResult.value)
      } catch (statusError) {
        imageStatusLoadError.value = friendlyError(statusError, '生图状态获取失败，请稍后重试')
      }
    } else {
      imageStatusLoadError.value = friendlyError(imageResult.reason, '生图状态获取失败，请稍后重试')
    }

    if (modelsResult.status === 'fulfilled') {
      try {
        availableImageModels.value = normalizeImageModelsResponse(modelsResult.value)
        if (availableImageModels.value.length > 0) {
          const model2 = availableImageModels.value.find(m => m.moduleKey === 'model-config-image-2')
          selectedModelKey.value = (model2 || availableImageModels.value[0]).moduleKey
        } else if (imageStatus.value.configured === true) {
          imageStatusLoadError.value = '未获取到可用的生图模型，请刷新配置后重试'
        }
      } catch (modelsError) {
        imageStatusLoadError.value = friendlyError(modelsError, '生图模型列表获取失败，请稍后重试')
      }
    } else if (!imageStatusLoadError.value) {
      imageStatusLoadError.value = friendlyError(modelsResult.reason, '生图模型列表获取失败，请稍后重试')
    }
  } finally {
    aiStatusLoading.value = false
    imageStatusLoading.value = false
  }
}

async function loadAccounts() {
  accountLoaded.value = false
  accountAvailable.value = false
  accountLoadError.value = ''
  accounts.value = []
  try {
    const res = await getLiteAccounts({ size: 200 })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    const currentAccount = accounts.value.find(account => String(account?.id ?? '') === String(selectedAccountId.value ?? '')) || null
    const preferredAccount = pickPreferredAccount(accounts.value, selectedAccountId.value)
    if (preferredAccount && (!currentAccount || !accountAuthUsable(currentAccount))) {
      selectedAccountId.value = preferredAccount.id
    }
    // 默认选中第一个账号
    if (accounts.value.length && !selectedAccountId.value) {
      selectedAccountId.value = accounts.value[0].id
    }
    accountAvailable.value = true
    return true
  } catch (e) {
    console.error('[OppPage] 账号列表加载失败:', e)
    selectedAccountId.value = null
    accountLoadError.value = e?.message || '账号列表加载失败'
    return false
  } finally {
    accountLoaded.value = true
  }
}

async function refreshAccountAuthStatus(accountId) {
  if (!accountId) return null
  try {
    const res = await checkAccountAuth(accountId)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.usable !== 'boolean') {
      throw new Error('账号鉴权状态响应格式异常')
    }
    const account = accounts.value.find(item => item.id === accountId)
    if (account) {
      account.cookieStatus = data.cookieStatus
      account.authUsable = data.usable
      account.loginStatusCode = data.loginStatusCode
      account.loginStatusMessage = data.loginStatusMessage
      account.loginCheckTime = data.checkedAt
    }
    return data
  } catch (e) {
    console.warn('[OppPage] 账号鉴权状态刷新失败:', e)
    return null
  }
}

async function ensureLoggedXianyuAccount() {
  // 账号仍在加载时，等待最多 6 秒，避免用户一进页面就点击搜索被"加载中"拦截
  if (!accountLoaded.value) {
    const maxWait = 6000
    const start = Date.now()
    while (!accountLoaded.value && Date.now() - start < maxWait) {
      await delay(150)
    }
    if (!accountLoaded.value) {
      error.value = '闲鱼账号状态加载中，请稍后再试'
      return false
    }
  }
  if (!accountAvailable.value) {
    error.value = accountLoadError.value || '闲鱼账号状态加载失败，请重试后再搜索'
    return false
  }
  if (!accounts.value.length) {
    error.value = '商机发掘需要先登录闲鱼账号。请先到「账号管理」扫码添加账号后再使用。'
    return false
  }
  // 检测首选账号 Cookie 状态：若缓存数据显示不可用，主动刷新一次鉴权状态
  const preferred = pickPreferredAccount(accounts.value, selectedAccountId.value)
  if (preferred && !accountAuthUsable(preferred)) {
    const authStatus = await refreshAccountAuthStatus(preferred.id)
    if (!authStatus) {
      error.value = '无法确认闲鱼账号登录状态，请检查网络后重试'
      return false
    }
    const refreshed = accounts.value.find(item => item.id === preferred.id)
    if (refreshed && !accountAuthUsable(refreshed)) {
      const accountLabel = refreshed.nickname || refreshed.displayName || refreshed.externalUid || ('账号' + refreshed.id)
      error.value = `账号「${accountLabel}」Cookie 已失效（${accountLoginHint(refreshed)}），请到「账号管理」重新登录后再使用`
      return false
    }
  }
  return true
}

function numberLike(value) {
  if (value === null || value === undefined || value === '') return null
  const raw = String(value ?? '').replace(/[¥￥,人想要已售\s]/g, '')
  const n = Number(raw)
  return Number.isFinite(n) && n >= 0 ? n : null
}

function extractOpportunityItems(data, errorMessage = '商品搜索响应格式异常') {
  const list = Array.isArray(data)
    ? data
    : Array.isArray(data?.items)
      ? data.items
      : Array.isArray(data?.list)
        ? data.list
        : Array.isArray(data?.data)
          ? data.data
          : null
  if (!Array.isArray(list)) throw new Error(errorMessage)
  return list
}

function opportunitySearchResultOf(response, errorMessage = '商品搜索响应格式异常') {
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error(errorMessage)
  const items = extractOpportunityItems(data, errorMessage)
  const total = Number(data.total)
  if (!Number.isFinite(total) || total < 0 || typeof data.hasMore !== 'boolean') throw new Error(errorMessage)
  return { data, items, total }
}

function crawlerPayloadOf(response, label) {
  const candidate = response?.data && typeof response.data === 'object' && !Array.isArray(response.data)
    ? response.data
    : response
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate) || typeof candidate.ok !== 'boolean') {
    throw new Error(`${label}响应格式异常`)
  }
  return candidate
}

function formatNum(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function extractId(item) {
  if (!item) return '-'
  // 优先使用 itemId 字段
  if (item.itemId) return String(item.itemId)
  if (!item.link) return '-'
  // 匹配 itemId= (标准格式),兼容旧格式 id=
  const m = item.link.match(/[?&]itemId=(\d+)/) || item.link.match(/[?&]id=(\d+)/)
  return m ? m[1] : '-'
}

function rotateTags() {
  tagIndex.value = (tagIndex.value + 1) % tagPools.length
  tags.value = [...tagPools[tagIndex.value]]
}

function clickTag(t) {
  keyword.value = t
  mode.value = 'search'
  doSearch()
}

function selectItem(item) {
  activateSelectedItem(item)
}

function invalidateRewriteRequests() {
  rewriteRequestVersion += 1
  rewriteLoading.value = false
}

function resetOpportunityItemState() {
  invalidateRewriteRequests()
  rewriteDraft.value = null
  generatedImages.value = []
  imageMethodUsed.value = ''
  imageHistoryRecords.value = []
  configCoverImage.value = []
  configCategoryObj.value = null
  oppAutoCategoryLoading.value = false
  oppAutoCategoryMessage.value = ''
  oppAutoCategoryMsgType.value = 'info'
  oppAutoCategoryCandidates.value = []
  saveMessage.value = ''
  error.value = ''
}

function activateSelectedItem(item) {
  selectedItem.value = item
  resetOpportunityItemState()
  step.value = 1
  saveDraftNow()
}

function resetView() {
  keyword.value = ''
  shopUrl.value = ''
  items.value = []
  shopResults.value = []
  selectedItem.value = null
  searched.value = false
  collected.value = false
  allCollected.value = false
  step.value = 0
  error.value = ''
  shopJobId.value = null
  shopUserId.value = null
  currentPage.value = 1
  totalItems.value = 0
  hasMore.value = false
  searchKeyword.value = ''
  resetOpportunityItemState()
  clearPublishAddress()
}

/**
 * 搜索闲鱼商品：通过 Java 网关代理到 Python automation-service，
 * 使用当前租户下已登录闲鱼账号 Cookie + _m_h5_tk 调用 MTOP 搜索，支持分页加载。
 */
async function doSearch() {
  // 提前设置 loading 状态，让按钮在账号鉴权等待期间也显示"搜索中..."，避免用户反复点击
  searchLoading.value = true
  try {
    if (!(await ensureLoggedXianyuAccount())) return
    const q = keyword.value.trim()

    if (!q) {
      error.value = '请输入搜索关键词'
      return
    }
    if (/^https?:\/\//i.test(q)) {
      error.value = '请输入商品关键词，不要输入链接'
      return
    }
    if (q.length > 50) {
      error.value = '关键词长度不能超过 50 个字符'
      return
    }

    error.value = ''
    step.value = 0
    selectedItem.value = null
    items.value = []
    searched.value = false
    currentPage.value = 1
    totalItems.value = 0
    hasMore.value = false
    searchKeyword.value = q

    const res = await goofishSearch(q, 1, pageSize, currentAccountId.value, searchMode.value)

    const { data, items: list, total } = opportunitySearchResultOf(res)
    items.value = list.map(normalizeOpportunityItem)
    totalItems.value = total
    hasMore.value = data.hasMore
    usedSearchMode.value = typeof data.searchMode === 'string' ? data.searchMode : ''
    searched.value = true
    step.value = 1

    if (items.value.length) {
      activateSelectedItem(items.value[0])
    }

    if (!items.value.length) {
      error.value = '未搜索到商品，请更换关键词或稍后重试'
    }
  } catch (e) {
    console.error('[OppPage] 搜索异常:', e)
    error.value = friendlyError(e, '商品搜索失败，请稍后重试')
    items.value = []
  } finally {
    searchLoading.value = false
  }
}

/**
 * 翻页加载更多商品。
 */
async function goToPage(page) {
  if (!searchKeyword.value) return
  if (searchLoading.value) return

  searchLoading.value = true
  error.value = ''
  selectedItem.value = null

  try {
    const res = await goofishSearch(searchKeyword.value, page, pageSize, currentAccountId.value, searchMode.value)

    const { data, items: list, total } = opportunitySearchResultOf(res, '商品翻页响应格式异常')
    items.value = list.map(normalizeOpportunityItem)
    totalItems.value = total
    hasMore.value = data.hasMore
    usedSearchMode.value = typeof data.searchMode === 'string' ? data.searchMode : ''
    currentPage.value = page

    if (items.value.length) {
      activateSelectedItem(items.value[0])
      step.value = 1
    }
  } catch (e) {
    console.error('[OppPage] 翻页异常:', e)
    error.value = e.message || '翻页加载失败，请稍后重试'
  } finally {
    searchLoading.value = false
  }
}

/**
 * 在搜索结果中加载更多（下一页）。
 */
async function loadMore() {
  if (!hasMore.value) return
  await goToPage(currentPage.value + 1)
}

async function doCollectShop() {
  const url = shopUrl.value.trim()
  if (!url) {
    error.value = '请输入闲鱼店铺链接'
    return
  }
  shopLoading.value = true
  error.value = ''
  step.value = 0
  selectedItem.value = null
  allCollected.value = false
  shopJobId.value = null
  shopUserId.value = null
  try {
    // 1. 提交抓取任务
    const rawImport = await importGoofishStore(url)
    const importRes = crawlerPayloadOf(rawImport, '店铺抓取任务')
    if (!importRes.ok) {
      error.value = importRes.error || importRes.message || '提交抓取任务失败'
      return
    }

    // 如果已经缓存（6小时内完成且有商品），直接查数据库
    if (importRes.cached) {
      shopUserId.value = importRes.userId
      await loadStoreItems(importRes.userId)
      return
    }

    shopJobId.value = importRes.jobId
    shopUserId.value = importRes.userId
    if (!shopJobId.value) {
      error.value = '抓取任务未返回 jobId，请检查 crawler-worker 是否启动'
      return
    }

    // 2. 轮询任务状态（最多 5 分钟，爬取含详情页获取可能需要数分钟）
    const maxRetries = 150
    for (let i = 0; i < maxRetries; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const rawStatus = await getCrawlJobStatus(importRes.jobId)
      const statusRes = crawlerPayloadOf(rawStatus, '店铺抓取任务状态')
      if (!statusRes.ok) {
        error.value = statusRes.error || '抓取任务状态查询失败'
        return
      }
      if (!['pending', 'running', 'completed', 'failed'].includes(statusRes.status)) {
        throw new Error('店铺抓取任务返回未知状态')
      }
      if (statusRes.status === 'completed') {
        await loadStoreItems(importRes.userId)
        return
      }
      if (statusRes.status === 'failed') {
        error.value = statusRes.failedReason || statusRes.error || '抓取失败'
        return
      }
      // 继续等待
    }
    // 轮询超时：爬取仍在后台异步进行，提示用户稍后查看
    error.value = '店铺抓取仍在后台进行中，请稍后在店铺商品列表中查看结果'
    shopUserId.value = importRes.userId
  } catch (e) {
    error.value = e.message || '抓取请求失败，请检查后端服务是否正常运行'
    items.value = []
  } finally {
    shopLoading.value = false
  }
}

async function loadStoreItems(userId) {
  try {
    const raw = await getGoofishStoreItems(userId)
    const res = crawlerPayloadOf(raw, '店铺商品')
    if (res.ok) {
      if (!Array.isArray(res.items)) throw new Error('店铺商品响应格式异常')
      const storeItems = res.items.map(normalizeOpportunityItem)
      items.value = storeItems
      shopResults.value = [...storeItems]
      collected.value = true
      step.value = 1
      if (storeItems.length) {
        activateSelectedItem(storeItems[0])
      }
      return true
    } else {
      error.value = res.error || '获取商品列表失败'
      return false
    }
  } catch (e) {
    error.value = e.message || '获取商品列表失败'
    return false
  }
}

async function doCollectAll() {
  // 异步模式下，"全部采集"就是重新加载已有的店铺商品
  if (!shopUserId.value) {
    error.value = '请先完成店铺抓取'
    return
  }
  shopLoading.value = true
  error.value = ''
  try {
    if (await loadStoreItems(shopUserId.value)) allCollected.value = true
  } catch (e) {
    error.value = e.message || '全量采集请求失败'
  } finally {
    shopLoading.value = false
  }
}


function buildLocationData() {
  return normalizePublishAddress(selectedPublishAddress.value)
}

function clearPublishAddress() {
  selectedPublishAddress.value = null
}


function normalizeOpportunityItem(item) {
  return {
    title: item.title || item.name || '无标题商品',
    price: item.price || item.soldPrice || item.currentPrice || '',
    image: item.imageUrl || item.image || item.picUrl || item.coverPic || item.mainImageUrl || '',
    link: item.pcUrl || item.itemUrl || item.link || item.url || '',
    itemId: item.itemId || item.externalGoodsId || extractId(item),
    description: item.description || item.desc || '',
    images: Array.isArray(item.images) ? item.images : [],
    seller: item.seller || item.userNick || '',
    area: item.area || item.location || '',
    soldCount: item.soldCount ?? null,
    wantCount: item.wantCount ?? item.want ?? item.wantNum ?? null,
    status: item.status ?? item.itemStatus ?? null,
  }
}

async function handleRewriteAction() {
  if (aiStatusLoadError.value || !aiStatus.value.rewriteEnabled) {
    await refreshAiFeatureStatus()
  }
  if (!aiStatus.value.rewriteEnabled) {
    error.value = aiStatusLoadError.value || '平台暂未开放AI改写功能，敬请期待'
    return
  }
  await rewriteSelected()
}

async function rewriteSelected(retryCount) {
  const isRetry = retryCount > 0
  if (!selectedItem.value) { error.value = '请先选择商品'; return }
  const requestVersion = ++rewriteRequestVersion
  const sourceItemKey = getOpportunityItemIdentity(selectedItem.value)
  const payload = buildOpportunityRewritePayload({
    selectedItem: selectedItem.value,
    rewriteDraft: rewriteDraft.value,
    keyword: searchKeyword.value || keyword.value,
    style: rewriteStyle.value,
    customPrompt: rewriteCustomPrompt.value,
  })
  rewriteLoading.value = true
  if (!isRetry) error.value = ''
  try {
    const res = await rewriteOpportunity(payload)
    const data = res?.data
    if (requestVersion !== rewriteRequestVersion || sourceItemKey !== getOpportunityItemIdentity(selectedItem.value)) {
      return
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('AI 改写响应格式异常，请重试')
    }
    if (typeof data.ok !== 'boolean') throw new Error('AI 改写响应缺少成功状态')
    if (data.ok === false || data.error) {
      error.value = data.error || data.message || 'AI改写失败'
      // 首次失败且疑似超时，自动重试一次
      if (!isRetry && error.value && (error.value.includes('timed out') || error.value.includes('timeout') || error.value.includes('超时'))) {
        saveMessage.value = '首次改写超时，正在自动重试...'
        await rewriteSelected(1)
        return
      }
      return
    }
    if (!data.rewrite || typeof data.rewrite !== 'object' || Array.isArray(data.rewrite)
      || typeof data.rewrite.title !== 'string' || !data.rewrite.title.trim()
      || typeof data.rewrite.description !== 'string' || !data.rewrite.description.trim()) {
      error.value = data.message || 'AI改写失败，请重试'
      return
    }
    if (!Number.isFinite(Number(data.draftId)) || Number(data.draftId) <= 0 || data.saved !== true) {
      throw new Error('AI 改写结果未确认保存，原文已保留')
    }
    if (requestVersion !== rewriteRequestVersion || sourceItemKey !== getOpportunityItemIdentity(selectedItem.value)) {
      return
    }
    rewriteDraft.value = { ...data.rewrite }
    if (rewriteDraft.value) {
      rewriteDraft.value.draftId = data.draftId
      if (rewriteDraft.value.title && rewriteDraft.value.title.length > 30) {
        rewriteDraft.value.title = rewriteDraft.value.title.slice(0, 30)
      }
      // 将AI生成的标题与正文合并后填入正文输入框：标题 + "。" + 正文
      if (rewriteDraft.value.title && rewriteDraft.value.description) {
        rewriteDraft.value.description = rewriteDraft.value.title + "。" + rewriteDraft.value.description
      }
    }
    step.value = Math.max(step.value, 2)
    saveDraftNow()
  } catch (e) {
    if (requestVersion !== rewriteRequestVersion || sourceItemKey !== getOpportunityItemIdentity(selectedItem.value)) {
      return
    }
    error.value = e.message || 'AI改写失败'
    // 首次失败且疑似超时，自动重试一次
    if (!isRetry && error.value && (error.value.includes('timed out') || error.value.includes('timeout') || error.value.includes('超时'))) {
      saveMessage.value = '首次改写超时，正在自动重试...'
      await rewriteSelected(1)
      return
    }
  }
  finally {
    if (requestVersion === rewriteRequestVersion) {
      rewriteLoading.value = false
    }
  }
}


async function handleGenerateImagesAction() {
  if (imageStatusLoadError.value || !imageStatus.value.configured) {
    await refreshAiFeatureStatus()
  }
  if (!imageStatus.value.configured) {
    error.value = imageStatusLoadError.value || '平台暂未开放生图功能，敬请期待'
    return
  }
  await handleGenerateImages()
}

async function handleGenerateImages(isRetry) {
  if (!imageStatus.value.configured) {
    error.value = '平台暂未开放生图功能，敬请期待'
    return
  }
  if (!selectedItem.value) {
    error.value = '请先选择商品'
    return
  }
  if (!selectedModelKey.value || !availableImageModels.value.some(model => model.moduleKey === selectedModelKey.value)) {
    error.value = imageStatusLoadError.value || '未获取到可用的生图模型，请刷新配置后重试'
    return
  }
  const title = rewriteDraft.value?.title || selectedItem.value.title
  const description = rewriteDraft.value?.description || selectedItem.value.description || selectedItem.value.title
  if (!(title || description)) {
    error.value = '商品标题和描述为空，无法生成图片'
    return
  }
  imageLoading.value = true
  error.value = ''
  saveMessage.value = '正在生成图片（约需2-3分钟，请耐心等待）...'
  imageMethodUsed.value = ''
  try {
    const res = await generateOpportunityImages({
      prompt: '',
      promptMode: imagePromptMode.value,
      customPrompt: imagePromptMode.value === 'custom' ? customImagePrompt.value : '',
      count: imageCount.value,
      size: '1024x1024',
      itemTitle: title,
      itemDescription: description,
      systemPrompt: imageStatus.value.defaultPrompt || '',
      modelKey: selectedModelKey.value || undefined,
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('生图服务响应格式异常')
    }
    if (typeof data.ok !== 'boolean') throw new Error('生图服务响应缺少成功状态')
    if (data.ok === false) {
      error.value = data.error || data.message || '生图失败，请重试'
      // 尝试从历史记录恢复
      await tryRecoverFromHistory()
      return
    }

    const images = validGeneratedImages(data.images)
    const returnedCount = Number(data.count)
    if (!Number.isSafeInteger(returnedCount) || returnedCount !== images.length) {
      throw new Error('生图服务返回的图片数量不一致')
    }
    if (!images.length) {
      error.value = '生图返回结果为空，正在尝试从历史记录恢复...'
      await tryRecoverFromHistory()
      return
    }

    generatedImages.value = images
    imageMethodUsed.value = data.methodUsed || ''
    saveDraftNow()
    const methodHint = data.methodUsed
      ? `（使用${
          data.methodUsed === 'proxy-async-poll' ? '最优中转' :
          data.methodUsed === 'async-poll' ? '异步轮询' :
          data.methodUsed === 'direct-sync' ? '同步直连' :
          data.methodUsed === 'async-fallback' ? '异步兜底' :
          data.methodUsed === 'history-recovery' ? '历史恢复' :
          data.methodUsed === 'chat-completions-image' ? 'Gemini对话' : data.methodUsed
        }模式）`
      : ''
    const chargedTokens = Number(data.chargedTokens)
    const historyHint = data.historySaved === false ? '；历史记录保存失败，请立即保存生成图片' : ''
    saveMessage.value = Number.isFinite(chargedTokens) && chargedTokens >= 0
      ? `已生成 ${images.length} 张图片，扣除 ${chargedTokens} Token${methodHint}`
      : `已生成 ${images.length} 张图片${methodHint}；Token 扣费结果未返回，请到账户流水确认`
    saveMessage.value += historyHint
    // AI 生图成功后，若用户尚未配置封面图，则触发自动分类（使用生成的首张图片）
    if (!configCoverImage.value.length && images.length > 0) {
      triggerOppAutoCategory()
    }
  } catch (e) {
    error.value = friendlyError(e, '生图失败，请稍后重试')
    // 首次失败自动重试一次（解决冷启动首次 Connection reset 问题）
    if (!isRetry) {
      saveMessage.value = '首次请求失败，正在自动重试...'
      // 注意：不在此处重置 imageLoading，避免重试期间 UI 状态闪烁
      // imageLoading 由 finally 块统一管理，递归调用期间保持 true
      await new Promise(r => setTimeout(r, 1000))
      await handleGenerateImages(1)
      return
    }
    // 重试仍然失败，尝试从历史记录恢复
    saveMessage.value = '生图失败，正在尝试从历史记录恢复...'
    await tryRecoverFromHistory()
  } finally {
    imageLoading.value = false
  }
}

/**
 * 生图失败或超时后，尝试从历史记录中恢复图片。
 */
async function tryRecoverFromHistory() {
  try {
    const historyRes = await listOpportunityImageHistory({ limit: 5 })
    const historyData = historyRes?.data
    if (!Array.isArray(historyData)) throw new Error('生图历史响应格式异常')
    const records = historyData
    if (records.length > 0) {
      imageHistoryRecords.value = records.slice(0, 3)
      // 如果有成功记录，尝试恢复最新的
      const latest = records.find(r => r.status === 'success')
      if (latest) {
        try {
          const recoverRes = await recoverOpportunityImages(latest.id)
          const recoverData = validGeneratedImages(recoverRes?.data)
          if (recoverData.length > 0) {
            generatedImages.value = recoverData
            saveMessage.value = `已从历史记录恢复 ${recoverData.length} 张图片（记录ID: ${latest.id}）`
            imageMethodUsed.value = 'history-recovery'
            return true
          }
        } catch {
          // 恢复失败不阻断，继续显示历史记录
        }
      }
      saveMessage.value = '生图异常，检测到历史生图记录，可在下方点击"恢复历史图片"获取'
      return true
    }
    imageHistoryRecords.value = []
    saveMessage.value = ''
    return false
  } catch (historyError) {
    imageHistoryRecords.value = []
    saveMessage.value = ''
    console.warn('[OppPage] 生图历史恢复不可用:', historyError)
    return false
  }
}

/**
 * 手动从历史记录恢复图片。
 */
async function handleRecoverFromHistory(record) {
  if (!record || !record.id) return
  imageRecoverLoading.value = true
  error.value = ''
  try {
    const res = await recoverOpportunityImages(record.id)
    const data = validGeneratedImages(res?.data)
    if (data.length > 0) {
      generatedImages.value = data
      saveMessage.value = `已从历史记录成功恢复 ${data.length} 张图片`
      imageMethodUsed.value = 'history-recovery'
    } else {
      error.value = '历史记录中无可用图片'
    }
  } catch (e) {
    error.value = '恢复失败：' + (e.message || '请重试')
  } finally {
    imageRecoverLoading.value = false
  }
}

function validGeneratedImages(value) {
  if (!Array.isArray(value)) return []
  return value.filter(image => image && typeof image === 'object'
    && [image.originalUrl, image.url, image.b64Json].some(item => typeof item === 'string' && item.trim()))
}

function imgUrl(img) {
  return img.originalUrl || img.url || ('data:image/png;base64,' + img.b64Json)
}

function isCoverSelected(img) {
  return configCoverImage.value.includes(imgUrl(img))
}

function toggleCoverImage(img) {
  const url = imgUrl(img)
  const idx = configCoverImage.value.indexOf(url)
  if (idx >= 0) {
    configCoverImage.value.splice(idx, 1)
  } else if (configCoverImage.value.length < 9) {
    configCoverImage.value.push(url)
  } else {
    error.value = '最多只能选择9张封面图'
  }
  triggerAutoSave()
}

function removeCoverImage(idx) {
  configCoverImage.value.splice(idx, 1)
  triggerAutoSave()
}

function removeGeneratedImage(idx) {
  const removed = generatedImages.value[idx]
  if (!removed) return
  const removedUrl = imgUrl(removed)
  generatedImages.value.splice(idx, 1)
  if (removedUrl) {
    configCoverImage.value = configCoverImage.value.filter(url => url !== removedUrl)
  }
  if (!generatedImages.value.length) {
    imageMethodUsed.value = ''
  }
  triggerAutoSave()
}

async function onCoverUpload(e) {
  const file = e.target?.files?.[0]
  if (!file) return
  const validationMessage = imageUploadValidationMessage(file)
  if (validationMessage) {
    error.value = validationMessage
    e.target.value = ''
    return
  }
  if (configCoverImage.value.length >= 9) {
    error.value = '封面图最多上传9张'
    return
  }
  e.target.value = ''
  try {
    const accountId = selectedAccountId.value || accounts.value[0]?.id || 0
    const res = await uploadImage(accountId, file)
    if (res.code === 200 && res.data?.url) {
      configCoverImage.value.push(res.data.url)
      // 上传封面图后触发自动分类（仅对首张封面）
      if (configCoverImage.value.length === 1) {
        await triggerOppAutoCategory()
      }
      triggerAutoSave()
      return
    }
  } catch (e) {
    console.error('[OppPage] 封面图上传失败:', e)
  }
  // 上传失败时回退到 data URL 预览（但发布时无法使用）
  const reader = new FileReader()
  reader.onload = async (ev) => {
    const dataUrl = ev.target?.result || ''
    configCoverImage.value.push(dataUrl)
    // data URL 无法用于自动分类
    if (configCoverImage.value.length === 1) {
      oppAutoCategoryMessage.value = '封面图上传失败，无法自动识别分类，请手动选择'
      oppAutoCategoryMsgType.value = 'warn'
    }
    triggerAutoSave()
  }
  reader.readAsDataURL(file)
}

function buildPublishImageUrls() {
  const urls = []
  const pushUrl = url => {
    const text = String(url || '').trim()
    if (!text) return
    if (text.startsWith('http://') || text.startsWith('https://') || text.startsWith('/uploads/')) urls.push(text)
  }
  // 1. 优先使用用户在配置页面上传或选择的封面图（过滤掉 data URL，这些会在发布时上传）
  configCoverImage.value.forEach(url => {
    if (!url.startsWith('data:')) pushUrl(url)
  })
  // 2. 添加AI生成的图片（去重）
  const coverUrls = configCoverImage.value.filter(u => !u.startsWith('data:'))
  ;(generatedImages.value || []).forEach(img => {
    const imgUrl = img?.originalUrl || img?.url || ''
    if (imgUrl && !coverUrls.includes(imgUrl)) pushUrl(imgUrl)
  })
  // 3. 如果没有配置封面图也没有生成图片，才使用原商品图片作为兜底
  if (!urls.length) {
    pushUrl(selectedItem.value?.image)
    ;(selectedItem.value?.images || []).forEach(img => pushUrl(img?.url || img))
  }
  return Array.from(new Set(urls)).slice(0, 10)
}

async function doPublish() {
  if (!(await ensureLoggedXianyuAccount())) return
  if (!selectedItem.value) return
  const accountId = selectedAccountId.value
  if (!accountId) {
    error.value = '请先选择发布账号'
    return
  }
  const location = buildLocationData()
  if (!isPublishAddressComplete(location)) {
    error.value = '请先完成发布位置的省、市、区选择'
    return
  }
  const publishPrice = Number(String(configPrice.value || selectedItem.value.price || '').replace(/[¥￥,]/g, '').trim())
  if (!Number.isFinite(publishPrice) || publishPrice <= 0) {
    error.value = '请填写大于 0 的有效发布价格'
    return
  }
  if (!publishTitle.value.trim()) {
    error.value = '请填写商品标题后再发布'
    return
  }

  // 上传 data URL 格式的封面图，确保发布时使用的是可访问的图片链接
  const dataUrlCovers = configCoverImage.value.filter(url => url.startsWith('data:'))
  if (dataUrlCovers.length > 0) {
    try {
      saveMessage.value = '封面图上传中...'
      const accountId = selectedAccountId.value
      for (const dataUrl of dataUrlCovers) {
        const resp = await fetch(dataUrl)
        const blob = await resp.blob()
        const file = new File([blob], 'cover.png', { type: blob.type || 'image/png' })
        const uploadRes = await uploadImage(accountId, file)
        if (uploadRes.code === 200 && uploadRes.data?.url) {
          const idx = configCoverImage.value.indexOf(dataUrl)
          if (idx >= 0) configCoverImage.value[idx] = uploadRes.data.url
        } else {
          error.value = '封面图上传失败，请重新上传图片'
          publishing.value = false
          return
        }
      }
    } catch (e) {
      error.value = '封面图处理失败：' + (e.message || '上传异常')
      publishing.value = false
      return
    }
  }

  const imageUrls = buildPublishImageUrls()
  if (!imageUrls.length) {
    error.value = '发布到闲鱼需要至少一张可访问的商品图片，请先选择带图片的商品或上传/生成图片'
    return
  }
  publishing.value = true
  try {
    saveMessage.value = ''
    error.value = ''
    const price = String(publishPrice)
    const publishRes = await publishItem({
      xianyuAccountId: Number(accountId),
      title: publishTitle.value.slice(0, 30),
      description: rewriteDraft.value?.description || selectedItem.value.description || `来源商机发掘：${selectedItem.value.link || ''}`,
      imageUrls,
      price,
      stock: configStock.value,
      category: configCategory.value || rewriteDraft.value?.category || selectedItem.value.category || '商机发掘',
      // 传递闲鱼官方结构化分类字段（仅当 configCategoryObj 与当前 configCategory 一致时才附带，避免用户手动改过字符串后还传旧 ID）
      categoryId: configCategoryObj.value && configCategoryObj.value.catName === configCategory.value ? configCategoryObj.value.catId : undefined,
      channelCatId: configCategoryObj.value && configCategoryObj.value.catName === configCategory.value ? configCategoryObj.value.channelCatId : undefined,
      channelCatName: configCategoryObj.value && configCategoryObj.value.catName === configCategory.value ? configCategoryObj.value.channelCatName : undefined,
      tbCatId: configCategoryObj.value && configCategoryObj.value.catName === configCategory.value ? configCategoryObj.value.tbCatId : undefined,
      leafId: configCategoryObj.value && configCategoryObj.value.catName === configCategory.value ? configCategoryObj.value.leafId : undefined,
      freeShipping: shippingMode.value === 'free',
      supportSelfPick: supportSelfPick.value,
      location,
      source: 'opportunity',
      sourceItemId: selectedItem.value.itemId || extractId(selectedItem.value),
      sourceLink: selectedItem.value.link || '',
    })
    const publishData = publishRes?.data
    if (!publishData || typeof publishData !== 'object' || Array.isArray(publishData)) {
      error.value = '发布请求已返回，但结果格式异常，无法确认是否成功，请先到闲鱼核对后再重试'
      return
    }
    const itemId = String(publishData.itemId ?? publishData.xyGoodsId ?? publishData.id ?? '').trim()
    if (!itemId) {
      error.value = '发布请求已返回，但未获得商品 ID，无法确认是否成功，请先到闲鱼核对后再重试'
      return
    }
    // 标记商品待同步，下次进入商品管理页面时自动触发同步
    localStorage.setItem('xianyu_pending_sync', 'true')
    saveMessage.value = `已发布到闲鱼（商品ID：${itemId}），本页面不会额外添加商品草稿到商品列表。`
  } catch (e) {
    error.value = friendlyError(e, '发布到闲鱼失败')
  } finally {
    publishing.value = false
  }
}

async function copyTitle() {
  if (!selectedItem.value?.title) return
  try { await navigator.clipboard.writeText(selectedItem.value.title); saveMessage.value = '标题已复制' } catch { saveMessage.value = '请手动复制标题' }
}

// AI 一键选择分类状态加载（与 ProductPublishPage 统一，调用真实 AI Provider）
async function loadAiCategoryStatus() {
  aiCategoryLoadError.value = ''
  try {
    const res = await getAiProviderStatus()
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.configured !== 'boolean') {
      throw new Error('AI 服务状态响应格式异常')
    }
    aiCategoryStatus.value = data
  } catch (loadError) {
    aiCategoryStatus.value = { configured: null }
    aiCategoryLoadError.value = loadError?.message || 'AI 服务状态暂时无法加载'
  }
}

async function autoSelectConfigCategory() {
  if (aiCategoryStatus.value.configured === null) {
    error.value = aiCategoryLoadError.value || 'AI 服务状态不可用，请刷新后重试'
    return
  }
  if (aiCategoryStatus.value.configured === false) {
    error.value = 'AI 服务未配置，无法使用 AI 选择分类'
    return
  }
  const title = (rewriteDraft.value?.title || selectedItem.value?.title || '').trim()
  if (!title) {
    error.value = '请先填写商品标题，AI才能判断分类'
    return
  }
  const description = rewriteDraft.value?.description || selectedItem.value?.description || ''
  aiCategoryLoading.value = true
  error.value = ''
  saveMessage.value = ''
  try {
    // 把本地分类树扁平化后传给 AI Provider
    const options = flatOppCategoryOptions(5000)
    if (!options.length) throw new Error('分类数据暂时不可用，无法安全应用 AI 分类')
    const res = await suggestCategoryByAi({
      title,
      description,
      categories: options,
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.enabled !== 'boolean' || typeof data.matched !== 'boolean') {
      throw new Error('AI 分类响应格式异常')
    }
    if (data.enabled === false) {
      aiCategoryStatus.value = { configured: false }
      error.value = 'AI 服务未启用'
      return
    }
    if (!data.matched) {
      error.value = data.error || data.message || 'AI未能匹配到合适分类，请手动选择'
      return
    }
    const matched = data.category
    if (!matched || typeof matched !== 'object' || Array.isArray(matched)) throw new Error('AI 分类结果缺少有效分类')
    const matchedId = String(matched.id || matched.categoryId || '')
    const catName = String(matched.name || matched.categoryName || '').trim()
    const localMatch = options.find(option => (matchedId && String(option.id) === matchedId)
      || (catName && (option.name === catName || option.path === catName || option.path.endsWith(` ＞ ${catName}`))))
    if (localMatch) {
      configCategory.value = localMatch.name
      // AI 选择不提供闲鱼官方 catId，仅设置字符串分类名，清空结构化对象
      configCategoryObj.value = null
      saveMessage.value = data.reason ? `AI已选择：${data.reason}` : `AI已自动选择分类：${localMatch.name}`
    } else {
      error.value = 'AI 返回的分类不在当前可用分类树中，请手动选择'
    }
  } catch (e) {
    error.value = e.message || 'AI自动选择分类失败'
  } finally {
    aiCategoryLoading.value = false
  }
}

// 扁平化本地分类树（与 ProductPublishPage.flatCategoryOptions 对齐）
function flatOppCategoryOptions(limit = 5000) {
  const res = []
  const walk = (nodes, parents = []) => {
    for (const node of nodes || []) {
      if (res.length >= limit) return
      const name = node.label || node.title || ''
      const pathParts = [...parents, name]
      const children = node.children || []
      if (!children.length) {
        res.push({ id: node.id, name, path: pathParts.join(' ＞ ') })
      } else {
        walk(children, pathParts)
      }
    }
  }
  walk(oppCategories.value || [])
  return res
}

// 异步加载本地分类树（用于 AI 选择时提供候选）
const oppCategories = ref([])
async function loadOppCategories() {
  try {
    const module = await import('../assets/data/categories.json')
    oppCategories.value = module.default?.cation || module.cation || []
    // 静默从后端拉取最新分类树（含自动分类新增的分类）
    refreshOppCategoriesInBackground()
  } catch {
    oppCategories.value = []
  }
}

// 后台刷新分类树：自动分类服务在后台已将新分类写入后端 categories.json
// 拉取最新分类让前端级联选择器和 AI 选择能用到最新分类
async function refreshOppCategoriesInBackground() {
  try {
    const res = await fetchCategories()
    const newTree = res?.data?.cation || []
    if (newTree.length) {
      oppCategories.value = newTree
    }
  } catch {
    // 静默失败，不影响用户操作
  }
}

// ---- 自动分类（封面图上传后触发） ----
async function triggerOppAutoCategory() {
  if (!accounts.value.length) {
    oppAutoCategoryMessage.value = '请先添加闲鱼账号'
    oppAutoCategoryMsgType.value = 'error'
    return
  }
  // 优先使用用户上传的封面图，其次使用 AI 生成的图片
  let coverImageUrl = ''
  if (configCoverImage.value.length) {
    coverImageUrl = configCoverImage.value[0]
  } else if (generatedImages.value.length) {
    // AI 生成的图片：优先使用 url（/uploads/cache/xxx.jpg，后端可访问），避免使用 data URL
    const img = generatedImages.value[0]
    coverImageUrl = img.url || img.originalUrl || ''
  }
  if (!coverImageUrl) {
    return
  }
  const accountId = selectedAccountId.value
  if (!accountId) {
    oppAutoCategoryMessage.value = '请先添加闲鱼账号'
    oppAutoCategoryMsgType.value = 'error'
    return
  }
  oppAutoCategoryLoading.value = true
  oppAutoCategoryMessage.value = '正在识别商品分类...'
  oppAutoCategoryMsgType.value = 'info'
  oppAutoCategoryCandidates.value = []
  try {
    const res = await autoCategory(accountId, {
      coverImageUrl,
      title: rewriteDraft.value?.title || selectedItem.value?.title || undefined,
      description: rewriteDraft.value?.description || undefined,
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.success !== 'boolean') {
      throw new Error('封面自动分类响应格式异常')
    }
    if (data.candidates != null && !Array.isArray(data.candidates)) throw new Error('自动分类候选响应格式异常')
    if (data.success === false) {
      if (data.fallbackReason === 'COOKIE_EXPIRED' || data.fallbackReason === 'COOKIE_MISSING_M_H5_TK') {
        oppAutoCategoryMessage.value = '账号 Cookie 已失效，请重新登录后再试'
        oppAutoCategoryMsgType.value = 'error'
      } else {
        const reason = data.fallbackReason ? `（${data.fallbackReason}）` : ''
        oppAutoCategoryMessage.value = `封面图自动识别失败，请手动选择分类${reason}`
        oppAutoCategoryMsgType.value = 'warn'
        if (data.candidates && data.candidates.length) {
          oppAutoCategoryCandidates.value = data.candidates
        }
      }
      return
    }
    const selected = data.selectedCategory
    const candidates = data.candidates || []
    oppAutoCategoryCandidates.value = candidates
    if (selected) {
      const catName = selected.catName || selected.name || ''
      if (catName) {
        configCategory.value = catName
        // 同时保存结构化分类信息（含闲鱼官方 catId/channelCatId/tbCatId），发布时传给闲鱼
        configCategoryObj.value = {
          catId: selected.catId || '',
          catName,
          channelCatId: selected.channelCatId || '',
          channelCatName: selected.channelCatName || '',
          tbCatId: selected.tbCatId || '',
          leafId: selected.leafId || null,
          source: 'xianyu_auto',
        }
        oppAutoCategoryMessage.value = `已根据封面图自动识别分类：${catName}`
        oppAutoCategoryMsgType.value = 'success'
      }
    } else if (candidates.length) {
      oppAutoCategoryMessage.value = '已识别候选分类，请点击选择'
      oppAutoCategoryMsgType.value = 'info'
    }
  } catch (e) {
    oppAutoCategoryMessage.value = '自动分类请求失败：' + (e.message || '网络异常')
    oppAutoCategoryMsgType.value = 'error'
  } finally {
    oppAutoCategoryLoading.value = false
    // 后台刷新分类树，让新增的分类在前端级联选择器和 AI 选择中可见
    refreshOppCategoriesInBackground()
  }
}

function applyOppAutoCategory(cat) {
  if (!cat) return
  const catName = cat.catName || cat.name || ''
  if (catName) {
    configCategory.value = catName
    // 用户从候选列表点选时，同样保存结构化信息
    configCategoryObj.value = {
      catId: cat.catId || '',
      catName,
      channelCatId: cat.channelCatId || '',
      channelCatName: cat.channelCatName || '',
      tbCatId: cat.tbCatId || '',
      leafId: cat.leafId || null,
      source: 'candidate_pick',
    }
    oppAutoCategoryMessage.value = `已选择分类：${catName}`
    oppAutoCategoryMsgType.value = 'success'
  }
}

// ==================== 草稿功能 ====================

/** 收集当前页面状态用于保存 */
function collectDraftState() {
  const item = selectedItem.value
  return {
    savedAt: new Date().toLocaleString('zh-CN'),
    productTitle: item?.title || '未选择商品',
    productImage: item?.image || '',
    productLink: item?.link || '',
    step: step.value,
    selectedItem: item ? { ...item } : null,
    rewriteDraft: rewriteDraft.value ? JSON.parse(JSON.stringify(rewriteDraft.value)) : null,
    rewriteStyle: rewriteStyle.value,
    rewriteCustomPrompt: rewriteCustomPrompt.value,
    imagePromptMode: imagePromptMode.value,
    customImagePrompt: customImagePrompt.value,
    selectedModelKey: selectedModelKey.value,
    imageCount: imageCount.value,
    generatedImages: generatedImages.value.length ? JSON.parse(JSON.stringify(generatedImages.value)) : [],
    configCoverImage: [...configCoverImage.value],
    configPrice: configPrice.value,
    configCurrency: configCurrency.value,
    configStock: configStock.value,
    configCategory: configCategory.value,
    configCategoryObj: configCategoryObj.value,
    shippingMode: shippingMode.value,
    supportSelfPick: supportSelfPick.value,
    publishAddress: selectedPublishAddress.value ? { ...selectedPublishAddress.value } : null,
    selectedAccountId: selectedAccountId.value,
  }
}

/** 将当前状态保存为草稿（限 MAX_DRAFTS 个） */
function saveDraft() {
  if (!selectedItem.value) return // 未选择商品时不保存
  const draft = { id: Date.now(), ...collectDraftState() }
  let list
  try {
    list = JSON.parse(localStorage.getItem(DRAFT_KEY) || '[]')
  } catch { list = [] }
  // 去重：相同商品链接只保留最新的
  list = list.filter(d => d.productLink !== draft.productLink)
  list.unshift(draft)
  if (list.length > MAX_DRAFTS) list = list.slice(0, MAX_DRAFTS)
  localStorage.setItem(DRAFT_KEY, JSON.stringify(list))
  savedDrafts.value = list
}

/** 触发自动保存（防抖 2 秒） */
function triggerAutoSave() {
  draftVersion++
  const v = draftVersion
  clearTimeout(draftAutoSaveTimer)
  draftAutoSaveTimer = setTimeout(() => {
    if (v !== draftVersion) return // 有更新的保存请求
    saveDraft()
  }, 2000)
}

/** 从 localStorage 加载草稿列表 */
function loadSavedDrafts() {
  try {
    savedDrafts.value = JSON.parse(localStorage.getItem(DRAFT_KEY) || '[]')
  } catch {
    savedDrafts.value = []
    localStorage.removeItem(DRAFT_KEY)
  }
}

/** 恢复指定草稿到页面 */
function restoreDraft(draft) {
  if (!draft) return
  invalidateRewriteRequests()
  savedDrafts.value = savedDrafts.value.filter(d => d.id !== draft.id)
  // 恢复状态
  step.value = draft.step || 0
  selectedItem.value = draft.selectedItem ? { ...draft.selectedItem } : null
  rewriteDraft.value = draft.rewriteDraft ? JSON.parse(JSON.stringify(draft.rewriteDraft)) : null
  rewriteStyle.value = draft.rewriteStyle || 'friendly'
  rewriteCustomPrompt.value = draft.rewriteCustomPrompt || ''
  imagePromptMode.value = draft.imagePromptMode === 'custom' ? 'custom' : 'default'
  customImagePrompt.value = draft.customImagePrompt || ''
  selectedModelKey.value = draft.selectedModelKey || selectedModelKey.value
  imageCount.value = Math.max(1, Number(draft.imageCount || imageCount.value || 1))
  generatedImages.value = draft.generatedImages || []
  configCoverImage.value = draft.configCoverImage || []
  configPrice.value = draft.configPrice || ''
  configCurrency.value = draft.configCurrency || '¥'
  configStock.value = draft.configStock ?? 1
  configCategory.value = draft.configCategory || ''
  configCategoryObj.value = draft.configCategoryObj || null
  shippingMode.value = draft.shippingMode || 'free'
  supportSelfPick.value = draft.supportSelfPick || false
  selectedPublishAddress.value = normalizePublishAddress(draft.publishAddress || draft.selectedPoi)
  selectedAccountId.value = draft.selectedAccountId || null
  saveMessage.value = '已恢复草稿'
  // 从列表中移除已恢复的草稿
  localStorage.setItem(DRAFT_KEY, JSON.stringify(savedDrafts.value))
}

/** 删除指定草稿 */
function deleteDraft(id) {
  savedDrafts.value = savedDrafts.value.filter(d => d.id !== id)
  localStorage.setItem(DRAFT_KEY, JSON.stringify(savedDrafts.value))
}

/** 在关键操作后立即保存（无防抖） */
function saveDraftNow() {
  draftVersion++ // 取消待处理的自动保存
  clearTimeout(draftAutoSaveTimer)
  saveDraft()
}

onMounted(async()=>{
  await Promise.all([loadAccounts(), refreshAiFeatureStatus(), loadAiCategoryStatus(), loadOppCategories()])
  loadSavedDrafts()
})

// 监听关键配置变更自动保存草稿（v-model 绑定无法直接调用 triggerAutoSave）
watch([configPrice, configStock, configCurrency, configCategory, shippingMode, supportSelfPick, selectedPublishAddress], () => {
  if (selectedItem.value) triggerAutoSave()
}, { deep: true })

watch([imagePromptMode, customImagePrompt, selectedModelKey, imageCount], () => {
  if (selectedItem.value) triggerAutoSave()
})

// 用户手动编辑分类输入框时，若与已识别的结构化分类不一致，则清空结构化对象（避免发布时传旧 ID）
watch(configCategory, (newVal) => {
  if (configCategoryObj.value && newVal !== configCategoryObj.value.catName) {
    configCategoryObj.value = null
  }
})
</script>

<style scoped>
.op-product {
  height: 104px;
  border: 1px solid #eef3fa;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 14px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.op-product:hover {
  border-color: #b8d0f0;
  background: #fafcff;
}
.op-product.active {
  border-color: #0d6bff;
  background: #f7fbff;
}
.op-product h3 {
  margin: 0 0 8px;
}
.op-product p {
  display: flex;
  gap: 18px;
  align-items: center;
  margin: 0;
}
.credit {
  width: 120px;
  background: #fbfdff;
  border: 1px solid #eaf0f8;
  border-radius: 8px;
  padding: 10px;
  text-align: center;
}
.credit span {
  display: block;
  color: #7a879e;
}
.credit b {
  color: #16bf78;
}
.steps {
  display: flex;
  justify-content: space-around;
  height: 46px;
  border-bottom: 1px solid var(--line);
  align-items: center;
  color: #8a96aa;
}
.steps .active {
  color: #0d6bff;
  font-weight: 800;
}
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #eef3fa;
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.chips .chip {
  cursor: pointer;
}
.chips .chip:hover {
  color: #0d6bff;
}
.option-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f4fa;
}
.option-line:last-child {
  border-bottom: none;
}
.option-line span {
  color: #7a879e;
  font-size: 13px;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px 0 8px;
  border-top: 1px solid #eef3fa;
  margin-top: 8px;
}
.page-info {
  color: #7a879e;
  font-size: 14px;
  min-width: 100px;
  text-align: center;
}
.metric-row.compact {
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.ai-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #667085;
  line-height: 1.7;
}
.score-card {
  margin-top: 10px;
  border: 1px solid #e8eef8;
  border-radius: 10px;
  padding: 10px;
  display: grid;
  gap: 5px;
  background: #fbfdff;
}
.score-card span { color:#0d6bff; font-weight:700; }
.score-card small { color:#ef4444; }

.op-detail-hero :deep(.card-body) { padding: 0; overflow: hidden; border-radius: 16px; }
.detail-cover { height: 190px; background: linear-gradient(135deg,#f4f7ff,#e8eef8); }
.detail-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.detail-cover-empty { height: 100%; display:flex; align-items:center; justify-content:center; color:#9aa7bd; }
.detail-main { padding: 14px 16px 16px; }
.detail-main h3 { margin: 8px 0 10px; line-height: 1.45; font-size: 16px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.source-pill { display:inline-flex; padding:4px 8px; border-radius:999px; background:#eef5ff; color:#0d6bff; font-size:12px; font-weight:700; }
.detail-price { color:#ef4444; font-size:24px; font-weight:900; }
.detail-tags { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
.detail-tags span { border:1px solid #e8eef8; border-radius:999px; padding:3px 8px; font-size:12px; color:#667085; background:#fff; }
.detail-card :deep(.card-body) { padding-top: 12px; }
.info-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:10px; }
.info-grid div { border:1px solid #edf2f7; border-radius:12px; padding:10px; background:#fbfdff; min-width:0; }
.info-grid span, .desc-box span { display:block; color:#7a879e; font-size:12px; margin-bottom:5px; }
.info-grid b { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.info-grid .red { color:#ef4444; }
.desc-box { margin-top:10px; border:1px solid #edf2f7; border-radius:12px; padding:10px; background:#fff; }
.desc-box p { margin:0; line-height:1.65; color:#334155; max-height:140px; overflow:auto; white-space:pre-wrap; }


.draft-location { margin-top: 12px; border: 1px solid #eaf0f8; border-radius: 12px; padding: 12px; background: #fbfdff; }
.draft-location label { display:flex; justify-content:space-between; font-weight:800; color:#1f2a44; margin-bottom:8px; }
.draft-location small { font-weight:500; color:#8a96aa; }


.ai-disabled-tip { margin: 8px 0 0; color:#b45309; background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:9px 10px; font-size:13px; font-weight:700; }
.image-gen-box { margin-top:12px; border:1px solid #eaf0f8; border-radius:14px; padding:12px; background:linear-gradient(180deg,#fbfdff,#fff); }
.image-gen-head { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; margin-bottom:8px; }
.image-gen-head b { display:block; color:#16213e; font-size:14px; }
.image-gen-head span { display:block; margin-top:3px; color:#7a879e; font-size:12px; }
.light-mini { border:1px solid #dce6f5; background:#fff; color:#667085; border-radius:8px; padding:5px 8px; cursor:pointer; font-size:12px; }
.image-gen-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:10px; }
.image-gen-actions label { display:flex; align-items:center; gap:6px; color:#667085; font-size:12px; font-weight:700; }
.image-gen-info { margin:8px 0 0; font-size:13px; color:#667085; background:#f5f8fc; border-radius:8px; padding:8px 10px; }
.image-gen-info.muted { color:#9aa7bd; background:#fafbfd; }
.image-prompt-mode { margin-top:10px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.image-prompt-mode label { color:#667085; font-size:12px; font-weight:700; }
.image-prompt-help { color:#7a879e; font-size:12px; }
.image-prompt-textarea { width:100%; min-height:104px; margin-top:10px; font-size:13px; }
.image-gen-hint { display:flex; align-items:center; gap:8px; margin-top:10px; padding:10px 14px; background:linear-gradient(135deg,#fffbeb,#fef3c7); border:1px solid #fcd34d; border-radius:10px; box-shadow:0 2px 8px rgba(251,191,36,0.15); }
.image-gen-hint .hint-icon { font-size:20px; flex:0 0 auto; }
.image-gen-hint .hint-text { color:#92400e; font-size:13px; font-weight:700; line-height:1.5; }
.tiny-select { width:110px; height:36px; }
.image-gen-method { margin-top:8px; padding:6px 10px; background:#f0f7ff; border:1px solid #d4e4ff; border-radius:8px; display:inline-block; }
.method-tag { font-size:12px; color:#1a56db; font-weight:600; }
.image-gen-history { margin-top:12px; padding:10px 12px; background:#fffbeb; border:1px solid #fde68a; border-radius:10px; }
.image-gen-history b { display:block; font-size:13px; color:#92400e; margin-bottom:8px; }
.history-record-item { display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid #fef3c7; font-size:12px; color:#78350f; }
.history-record-item:last-child { border-bottom:none; }
.generated-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:12px; }
.gen-img-item { position:relative; border-radius:12px; overflow:hidden; border:1px solid #e5edf7; background:#f8fafc; }
.gen-img-select { display:block; width:100%; padding:0; border:0; background:transparent; cursor:pointer; position:relative; }
.gen-img-select img { width:100%; aspect-ratio:1/1; object-fit:cover; display:block; }
.gen-img-item { position:relative; cursor:pointer; transition:border-color 0.2s; }
.gen-img-item:hover { border-color:#0d6bff; }
.gen-img-item.active { border-color:#0d6bff; border-width:2px; }
.cover-badge { position:absolute; top:6px; left:6px; background:#0d6bff; color:#fff; font-size:11px; padding:2px 8px; border-radius:999px; font-weight:600; }
.gen-img-remove { position:absolute; top:6px; right:6px; width:22px; height:22px; border:0; background:rgba(0,0,0,0.6); color:#fff; border-radius:999px; cursor:pointer; font-size:16px; line-height:22px; text-align:center; padding:0; box-shadow:0 2px 8px rgba(0,0,0,0.12); }

.cover-preview-area { margin-top:16px; border-top:1px solid #eef3fa; padding-top:12px; }
.cover-preview-label { font-size:13px; font-weight:600; color:#1f2a44; margin-bottom:8px; display:flex; align-items:center; gap:8px; }
.cover-preview-hint { font-size:12px; font-weight:400; color:#8a96aa; }
.cover-preview-content { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.cover-preview-img { position:relative; width:90px; height:90px; border-radius:10px; overflow:hidden; border:1px solid #e5edf7; }
.cover-preview-img img { width:100%; height:100%; object-fit:cover; display:block; }
.cover-main-badge { position:absolute; bottom:2px; left:2px; background:#0d6bff; color:#fff; font-size:10px; padding:1px 6px; border-radius:4px; font-weight:600; line-height:1.6; }
.cover-remove { position:absolute; top:2px; right:2px; width:20px; height:20px; border:0; background:rgba(0,0,0,0.5); color:#fff; border-radius:999px; cursor:pointer; font-size:14px; line-height:20px; text-align:center; padding:0; }
.cover-upload-btn { display:inline-flex; align-items:center; justify-content:center; width:90px; height:90px; border:2px dashed #d0d8e6; border-radius:10px; cursor:pointer; background:#fafcff; transition:all 0.2s; }
.cover-upload-btn:hover { border-color:#0d6bff; background:#f0f6ff; }
.cover-upload-btn span { font-size:32px; color:#b0bccf; line-height:1; }

.char-count{font-size:12px;color:#999;margin-left:8px;white-space:nowrap}

/* ===== Step Panel Styles ===== */
.right-drawer {
  align-self: start;
}
.step-panel {
  display: flex;
  flex-direction: column;
}
.step-scroll {
  padding: 12px 0;
}
.step-footer {
  padding: 12px 0;
  border-top: 1px solid #eef3fa;
  background: #fff;
  flex-shrink: 0;
}
.step-footer-inner {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* ===== 过渡动画 ===== */
.step-fade-enter-active,
.step-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.step-fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.step-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* ===== 改写板块样式 ===== */
.rewrite-style-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.style-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.style-option {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #e0e6ed;
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  color: #667085;
  background: #fff;
  transition: all 0.2s;
  user-select: none;
}
.style-option:hover {
  border-color: #b8d0f0;
  background: #f5f9ff;
}
.style-option.active {
  border-color: #0d6bff;
  background: #eef4ff;
  color: #0d6bff;
  font-weight: 600;
}
.style-option input {
  display: none;
}

/* ===== 配置板块样式 ===== */
.price-config-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.category-config-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.stock-config-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.stock-suffix {
  color: #667085;
  font-size: 14px;
  font-weight: 600;
}
.stock-warn {
  margin: 0;
  color: #ef4444;
  font-size: 12px;
}
.shipping-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.shipping-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #eaf0f8;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}
.shipping-item:hover {
  border-color: #b8d0f0;
  background: #fafcff;
}
.shipping-item.active {
  border-color: #0d6bff;
  background: #f0f6ff;
}
.shipping-item span {
  font-weight: 600;
  color: #1f2a44;
}
.shipping-item input[type="radio"],
.shipping-item input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: #0d6bff;
  cursor: pointer;
}

/* ===== 发布板块样式 ===== */
.publish-summary-cover {
  height: 200px;
  border-radius: 12px;
  overflow: hidden;
  background: linear-gradient(135deg,#f4f7ff,#e8eef8);
  margin-bottom: 16px;
}
.publish-summary-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.publish-summary-info {
  padding: 0 4px;
}

/* ---- 自动分类 ---- */
.auto-category-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  padding: 8px 12px;
  background: #f0f7ff;
  border: 1px solid #d4e4ff;
  border-radius: 10px;
  color: #1a56db;
  font-size: 13px;
}
.auto-category-hint .hint-icon {
  font-size: 16px;
}
.auto-category-spinner {
  margin-left: auto;
  color: #0d6bff;
  font-weight: 700;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.auto-category-msg {
  margin-bottom: 10px;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
}
.auto-category-msg.success {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #059669;
}
.auto-category-msg.warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #b45309;
}
.auto-category-msg.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
}
.auto-category-msg.info {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
}
.auto-category-candidates {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  padding: 8px 12px;
  border: 1px solid #e4eaf2;
  border-radius: 10px;
  background: #fafcff;
}
.candidates-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
  white-space: nowrap;
}
.candidate-btn {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
}
.candidate-btn:hover {
  background: #dbeafe;
  border-color: #93c5fd;
}
.candidate-btn small {
  font-weight: 400;
  opacity: 0.8;
}

/* ---- 草稿面板 ---- */
.draft-bar {
  margin-bottom: 12px;
  border: 1px solid #e0e7f5;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}
.draft-bar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
  font-weight: 700;
  color: #1f2a44;
  background: #f8faff;
}
.draft-bar-header:hover {
  background: #f0f5ff;
}
.draft-toggle {
  font-size: 12px;
  color: #7a879e;
}
.draft-list {
  border-top: 1px solid #eef3fa;
  max-height: 300px;
  overflow-y: auto;
}
.draft-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid #f2f5fa;
  gap: 8px;
}
.draft-item:last-child {
  border-bottom: none;
}
.draft-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}
.draft-thumb {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
  background: #f4f7ff;
}
.draft-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.draft-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2a44;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.draft-time {
  font-size: 11px;
  color: #8a96aa;
  margin-top: 2px;
}
.draft-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.draft-del {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: #9aa7bd;
  font-size: 18px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.draft-del:hover {
  color: #ef4444;
  background: #fef2f2;
}
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.slide-down-enter-from,
.slide-down-leave-to {
  max-height: 0;
  opacity: 0;
}

/* 搜索输入框在窄屏必须独占一行，否则会被两个筛选项挤到不可用。 */
@media (max-width: 560px) {
  .opportunity-layout .toolbar > .input.large {
    flex: 1 1 100% !important;
    width: 100%;
  }
}

</style>
