<template>
  <div>
    <div v-if="overviewLoadError" class="global-notice warn">{{ overviewLoadError }}</div>
    <div class="grid stat-grid workflow-stats">
      <StatCard title="工作流总数" :value="overviewValue('workflowCount')" :change="overviewLoadError ? '状态不可用' : '真实库统计'" icon="workflow" />
      <StatCard title="已启用" :value="overviewValue('enabledCount')" :change="overviewLoadError ? '状态不可用' : '发布后可执行'" icon="play" color="green" />
      <StatCard title="今日执行" :value="overviewValue('todayExecutionCount')" :change="overviewLoadError ? '状态不可用' : 'workflow_execution'" icon="data" color="purple" />
      <StatCard title="成功率" :value="overviewValue('successRate', '%')" :change="overviewLoadError ? '状态不可用' : '按历史执行计算'" icon="shield" color="green" />
    </div>

    <div class="workflow-shell">
      <!-- 左侧：工作流列表 -->
      <CardPanel class="workflow-list-panel">
        <template #title>工作流列表</template>
        <div class="workflow-search">
          <input v-model="keyword" class="input" placeholder="搜索工作流名称" @keyup.enter="loadWorkflows" />
          <AppButton @click="loadWorkflows">搜索</AppButton>
        </div>
        <div class="workflow-tabs">
          <button :class="{active: statusFilter === ''}" @click="setStatus('')">全部</button>
          <button :class="{active: statusFilter === 'draft'}" @click="setStatus('draft')">草稿</button>
          <button :class="{active: statusFilter === 'published'}" @click="setStatus('published')">已发布</button>
        </div>
        <div class="workflow-list">
          <EmptyState v-if="workflowsLoadError" variant="error" title="工作流列表加载失败" :description="workflowsLoadError">
            <template #actions><AppButton @click="loadWorkflows">重试</AppButton></template>
          </EmptyState>
          <template v-else>
            <div
              v-for="wf in workflows"
              :key="wf.id"
              :class="['workflow-list-item', { active: selectedWorkflow?.id === wf.id }]"
              @click="selectWorkflow(wf.id)"
            >
              <span class="workflow-item-icon"><Icon name="workflow" /></span>
              <span class="workflow-item-body">
                <b>{{ wf.name }}</b>
                <em>{{ wf.description || '暂无说明' }}</em>
                <small>执行 {{ wf.executionCount ?? '—' }} · v{{ wf.version ?? '—' }}</small>
              </span>
              <span class="workflow-item-actions">
                <Badge :type="wf.status === 'published' ? 'green' : 'blue'">{{ statusText(wf.status) }}</Badge>
                <span class="workflow-item-buttons">
                  <button class="workflow-item-btn" title="重命名" @click.stop="renameWorkflow(wf)">改</button>
                  <button class="workflow-item-btn danger" title="删除" @click.stop="deleteWorkflow(wf)">删</button>
                </span>
              </span>
            </div>
            <EmptyState v-if="!workflows.length" icon="📋" title="暂无工作流" description="请新建工作流或执行数据库初始化。" />
          </template>
        </div>
        <AppButton type="primary" class="full" @click="newWorkflow">+ 新建工作流</AppButton>
      </CardPanel>

      <!-- 右侧：主面板 -->
      <div class="workflow-main">
        <div class="workflow-actions">
          <Badge :type="validation.valid ? 'green' : 'red'">{{ validation.message }}</Badge>
          <AppButton :loading="saving" :disabled="!!workflowDetailError" @click="saveDraft">保存草稿</AppButton>
          <span v-if="lastSavedAt" class="save-time">已保存 {{ lastSavedAt }}</span>
          <AppButton @click="zoomOut">缩小</AppButton>
          <AppButton @click="zoomIn">放大</AppButton>
          <AppButton @click="resetZoom">重置</AppButton>
          <AppButton type="primary" :loading="publishing" :disabled="!!workflowDetailError" @click="publishCurrent">发布</AppButton>
          <AppButton type="primary" :loading="running" :disabled="!!workflowDetailError" @click="runCurrent">运行测试</AppButton>
        </div>

        <EmptyState v-if="workflowDetailError" variant="error" title="工作流详情加载失败" :description="workflowDetailError">
          <template #actions><AppButton @click="loadWorkflows">返回列表并重试</AppButton></template>
        </EmptyState>

        <!-- ============ 画布：商品发布工作流 ============ -->
          <CardPanel v-else>
            <div class="workflow-editor-head">
              <div>
                <input v-model="draft.name" class="title-input" placeholder="工作流名称" />
                <p>{{ draft.description || '配置节点与执行参数。保存后由 Java 落库，执行动作由 Python 自动化端处理。' }}</p>
              </div>
            </div>

            <div class="workflow-canvas-wrap">
              <div class="node-palette">
                <button v-for="t in nodeTypes" :key="t.type" @click="addNode(t)">
                  <Icon :name="t.icon" />
                  <span>{{ t.label }}</span>
                </button>
              </div>
              <div ref="canvasEl" class="workflow-canvas" :style="{ overflow: canvasOverflow }" @click="clearEdgePick">
                <div class="workflow-canvas-inner" :style="canvasTransform">
                  <svg class="workflow-lines" :viewBox="`0 0 ${canvasWidth} ${canvasHeight}`" preserveAspectRatio="none">
                    <path v-for="e in edges" :key="edgeKey(e)" :class="[{ active: selectedNode?.id === e.source || selectedNode?.id === e.target }, { preview: edgeSource && edgeSource === e.source }]" :d="linePath(e)" />
                  </svg>
                  <div
                    v-for="node in nodes"
                    :key="node.id"
                    :class="['workflow-node', { selected: selectedNode?.id === node.id, source: edgeSource === node.id }]"
                    :style="{ left: node.x + 'px', top: node.y + 'px' }"
                    @click.stop="selectNode(node.id)"
                    @mousedown.stop="startDrag($event, node)"
                  >
                    <span class="node-icon"><Icon :name="node.icon || iconFor(node.type)" /></span>
                    <b>{{ node.name }}</b>
                    <em>{{ typeLabel(node.type) }}</em>
                    <small>{{ node.desc || node.type }}</small>
                    <div class="node-buttons">
                      <button title="从此节点连线" @click.stop="pickEdgeSource(node.id)">连</button>
                      <button title="删除节点" @click.stop="removeNode(node.id)">删</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardPanel>

        <!-- ============ 执行日志面板 ============ -->
        <CardPanel v-if="testResult" class="execution-log-panel">
          <template #title>
            <span class="section-icon">📝</span> 执行日志
            <span v-if="testResult.status === 'running'" class="log-badge running-badge">运行中</span>
            <span v-else-if="testResult.status === 'success'" class="log-badge success-badge">已完成</span>
            <span v-else-if="testResult.status === 'failed'" class="log-badge failed-badge">失败</span>
          </template>

          <!-- 执行概览 -->
          <div class="exec-summary">
            <div class="exec-summary-item">
              <span>执行编号</span>
              <b>{{ testResult.executionNo || '-' }}</b>
            </div>
            <div class="exec-summary-item">
              <span>状态</span>
              <b :style="{ color: testResult.status === 'success' ? '#16bf78' : testResult.status === 'failed' ? '#ef4444' : '#f59e0b' }">
                {{ testResult.status === 'success' ? '成功' : testResult.status === 'failed' ? '失败' : '运行中' }}
              </b>
            </div>
            <div class="exec-summary-item">
              <span>节点进度</span>
              <b>{{ testResult.nodeSuccess || 0 }} / {{ testResult.nodeTotal || 0 }}</b>
            </div>
            <div class="exec-summary-item">
              <span>总耗时</span>
              <b>{{ testResult.totalDuration ? testResult.totalDuration + 'ms' : '-' }}</b>
            </div>
          </div>

          <!-- 失败信息摘要 -->
          <div v-if="testResult.status === 'failed'" class="exec-failure-summary">
            <div class="failure-summary-header">
              <span class="failure-summary-icon">⚠</span>
              <span class="failure-summary-title">执行失败摘要</span>
            </div>
            <div v-if="testResult.errorMessage" class="failure-summary-row">
              <span class="failure-summary-label">失败原因：</span>
              <span class="failure-summary-text">{{ testResult.errorMessage }}</span>
            </div>
            <div v-if="testResultLogFailedNode" class="failure-summary-row">
              <span class="failure-summary-label">失败环节：</span>
              <span class="failure-summary-text">{{ testResultLogFailedNode.nodeName }}（{{ testResultLogFailedNode.nodeType }}）</span>
            </div>
            <div v-if="testResultLogFailedNode?.errorMessage" class="failure-summary-row">
              <span class="failure-summary-label">详细报错：</span>
              <pre class="failure-summary-stack">{{ testResultLogFailedNode.errorMessage }}</pre>
            </div>
            <div v-if="!testResult.errorMessage && !testResultLogFailedNode?.errorMessage" class="failure-summary-row">
              <span class="failure-summary-label">失败原因：</span>
              <span class="failure-summary-text">未捕获到具体错误信息，请查看下方日志时间线。</span>
            </div>
          </div>

          <!-- 节点详情 -->
          <div class="log-timeline">
            <div
              v-for="(log, li) in testResult.logEntries"
              :key="li"
              :class="['log-entry', `log-${log.level}`]"
            >
              <div class="log-entry-icon">
                <span v-if="log.level === 'success'">✓</span>
                <span v-else-if="log.level === 'error'">✗</span>
                <span v-else-if="log.level === 'warn'">⚠</span>
                <span v-else>●</span>
              </div>
              <div class="log-entry-body">
                <div class="log-entry-header">
                  <b>{{ log.nodeName }}</b>
                  <span class="log-entry-type">{{ log.nodeType }}</span>
                  <span v-if="log.duration" class="log-entry-duration">{{ log.duration }}ms</span>
                  <span class="log-entry-time">{{ log.time }}</span>
                </div>
                <div class="log-entry-message" :class="{ 'is-error': log.level === 'error' }">
                  {{ log.message }}
                </div>
                <div v-if="log.detail" class="log-entry-detail">
                  <pre>{{ log.detail }}</pre>
                </div>
              </div>
            </div>
            <EmptyState v-if="!testResult.logEntries.length" icon="📜" title="暂无日志记录" description="工作流测试执行后，日志会显示在这里。" />
          </div>

          <!-- 完整执行结果 JSON -->
          <div class="log-raw-toggle" @click="showRawLog = !showRawLog">
            {{ showRawLog ? '收起' : '展开' }} 原始执行结果
          </div>
          <pre v-if="showRawLog" class="mock-json">{{ JSON.stringify(testResult.rawData || {}, null, 2) }}</pre>
        </CardPanel>

        <!-- 最近执行记录 -->
        <CardPanel title="最近执行记录" class="execution-panel">
          <EmptyState v-if="executionsLoadError" variant="error" title="执行记录加载失败" :description="executionsLoadError">
            <template #actions><AppButton @click="loadExecutions">重试</AppButton></template>
          </EmptyState>
          <BaseTable v-else :columns="execCols" :rows="executions">
            <template #status="{row}">
              <span class="exec-status-cell" :class="{ 'is-failed': row.status === 'failed' }">
                <Badge :type="row.status === 'failed' ? 'red' : row.status === 'success' ? 'green' : 'blue'">{{ execStatusText(row.status) }}</Badge>
                <span v-if="row.status === 'failed' && row.errorMessage" class="exec-failure-tooltip">
                  <span class="tooltip-trigger"></span>
                  <span class="tooltip-content">{{ row.errorMessage }}</span>
                </span>
              </span>
            </template>
            <template #progress="{row}"><span class="mini-progress"><i :style="{width: `${row.progress || 0}%`}"></i></span> {{ row.progress || 0 }}%</template>
            <template #estimatedMinutes="{row}">
              <span v-if="row.status === 'running' && row.estimatedMinutes > 0" class="estimated-time">{{ row.estimatedMinutes }} 分钟</span>
              <span v-else-if="row.status !== 'running' && computedDurationMs(row) > 0" class="actual-time">{{ formatDuration(computedDurationMs(row)) }}</span>
              <span v-else class="time-na">-</span>
            </template>
            <template #createdTime="{row}">{{ formatDateTime(row.createdTime) }}</template>
            <template #op="{row}">
              <button class="link" @click="openExecution(row.id)">查看</button>
              <button class="link" style="margin-left:8px" @click="openExecutionLogs(row.id)">日志</button>
            </template>
          </BaseTable>
        </CardPanel>

        <!-- 最近运行记录 -->
        <EmptyState v-if="recentRunsLoadError" variant="error" title="最近运行记录加载失败" :description="recentRunsLoadError">
          <template #actions><AppButton @click="loadRecentRuns">重试</AppButton></template>
        </EmptyState>
        <CardPanel v-else-if="recentRuns.length" title="最近运行记录" class="execution-panel">
          <div class="recent-runs-list">
            <div v-for="run in recentRuns" :key="run.executionId" class="recent-run-item" @click="openExecution(run.executionId)">
              <div class="recent-run-header">
                <span class="recent-run-name">{{ run.workflowName }}</span>
                <Badge :type="run.status === 'failed' ? 'red' : run.status === 'success' ? 'green' : 'blue'">{{ execStatusText(run.status) }}</Badge>
              </div>
              <div class="recent-run-meta">
                <span>{{ run.executionNo }}</span>
                <span>{{ formatDuration(run.durationMs) }}</span>
                <span v-if="run.goodsTitle">商品：{{ run.goodsTitle }}</span>
              </div>
              <div v-if="run.failedNode" class="recent-run-error">
                <span class="recent-run-error-node">失败环节：{{ run.failedNode }}</span>
                <span v-if="run.errorMessage" class="recent-run-error-msg">原因：{{ run.errorMessage }}</span>
              </div>
              <div class="recent-run-time">{{ formatDateTime(run.createdTime) }}</div>
            </div>
          </div>
        </CardPanel>
      </div>

      <!-- 右侧配置面板 -->
      <CardPanel class="workflow-config-panel">
        <template #title>节点 / 工作流配置</template>
        <div class="tabs config-tabs">
          <button :class="['tab', { active: configTab === 'node' }]" @click="configTab = 'node'">节点配置</button>
          <button :class="['tab', { active: configTab === 'workflow' }]" @click="configTab = 'workflow'">工作流配置</button>
          <button :class="['tab', { active: configTab === 'execution' }]" @click="configTab = 'execution'">执行详情</button>
        </div>

        <template v-if="configTab === 'workflow'">
          <div class="form-row"><label>工作流名称</label><input v-model="draft.name" /></div>
          <div class="form-row"><label>说明</label><textarea v-model="draft.description"></textarea></div>
          <div class="form-row"><label>触发方式</label><select v-model="draft.triggerType"><option value="manual">手动触发</option><option value="scheduled">定时触发</option><option value="event">事件触发</option></select></div>
          <div class="form-row"><label>全局配置 JSON</label><textarea v-model="workflowConfigText" class="json-editor"></textarea></div>
        </template>

        <template v-else-if="configTab === 'node'">
          <template v-if="selectedNode">
            <div class="form-row"><label>节点名称</label><input v-model="selectedNode.name" /></div>
            <div class="form-row"><label>节点类型</label><select v-model="selectedNode.type"><option v-for="t in nodeTypes" :key="t.type" :value="t.type">{{ t.label }}</option></select></div>

            <!-- 触发器配置 -->
            <template v-if="selectedNode.type === 'TRIGGER'">
              <div class="form-row">
                <label>发布账号（可多选）</label>
                <div v-if="accounts.length" class="account-card-list">
                  <div
                    v-for="acct in accounts" :key="acct.id"
                    class="account-card"
                    :class="{ selected: (selectedNode.config.selectedAccountIds || []).includes(acct.id) }"
                    @click="toggleAccount(acct.id)"
                  >
                    <div class="account-card-checkbox" :class="{ checked: (selectedNode.config.selectedAccountIds || []).includes(acct.id) }"></div>
                    <img v-if="acct.avatarUrl" :src="acct.avatarUrl" class="account-card-avatar" :alt="acct.nickname" />
                    <div v-else class="account-card-avatar-placeholder">{{ (acct.nickname || 'A')[0] }}</div>
                    <div class="account-card-info">
                      <div class="account-card-name">{{ acct.nickname || acct.displayName || acct.externalUid || '账号' + acct.id }}</div>
                      <div class="account-card-status" :class="{ invalid: !accountAuthUsable(acct) }">{{ accountCookieLabel(acct) }}</div>
                      <div v-if="acct.introduction" class="account-card-intro">{{ acct.introduction }}</div>
                      <div v-else class="account-card-intro placeholder">暂无简介</div>
                    </div>
                  </div>
                </div>
                <div v-else-if="accountsLoadError" class="empty-hint error-text">{{ accountsLoadError }}</div>
                <div v-else class="empty-hint">暂无可用账号，请先在账号管理中添加</div>
              </div>
            </template>

            <!-- 商品获取节点配置 -->
            <template v-if="selectedNode.type === 'PRODUCT_FETCH'">
              <div class="form-row"><label>获取方式</label><select v-model="selectedNode.config.sourceType"><option value="keyword">商品搜索</option><option value="shop">店铺搜索</option></select></div>
              <template v-if="selectedNode.config.sourceType === 'shop'">
                <div class="form-row">
                  <label>店铺链接</label>
                  <input v-model="selectedNode.config.shopUrl" class="config-input" placeholder="粘贴闲鱼店铺链接，例如 https://www.goofish.com/personal?userId=..." />
                </div>
                <div class="form-row"><label>目标数量</label><input v-model.number="selectedNode.config.targetCount" type="number" min="1" max="100" /><span class="form-hint">从店铺商品中提取的数量（店铺爬取约20个，取前N个）</span></div>
              </template>
              <template v-else>
                <div class="form-row">
                  <label>商品关键词</label>
                  <div class="keyword-tag-input">
                    <span v-for="(kw, ki) in (selectedNode.config.keywords || [])" :key="ki" class="keyword-tag">
                      {{ kw }}<button class="tag-remove" @click="removeKeyword(ki)">&times;</button>
                    </span>
                    <input v-model="keywordInput" class="keyword-input" placeholder="输入关键词，回车或逗号添加" @keydown.enter.prevent="addKeyword" @keydown.,.prevent="addKeyword" @blur="addKeyword" />
                  </div>
                </div>
                <div class="form-row">
                  <label>从文本提取 <span class="hint-text">（支持粘贴任意文本，AI自动提取关键词）</span></label>
                  <textarea v-model="keywordExtractText" class="config-textarea" placeholder="直接粘贴品类表、商品列表、想法描述等任意文本，点击下方按钮即可由AI自动提取关键词&#10;例如可粘贴含品类/细分方向的表格、Markdown、段落等" rows="5"></textarea>
                  <div class="extract-row">
                    <AppButton size="small" type="primary" :loading="extractingKeywords" @click="doExtractKeywords">AI 提取关键词</AppButton>
                    <span v-if="extractingKeywords" class="hint-text">AI 正在分析文本，请稍候（约10-20秒）...</span>
                    <span v-else-if="lastExtractCount > 0" class="hint-text success-text">✓ 上次提取新增 {{ lastExtractCount }} 个关键词，已添加到上方关键词列表</span>
                    <span v-else-if="extractError" class="hint-text error-text">{{ extractError }}</span>
                  </div>
                  <div v-if="lastExtractedKeywords.length > 0" class="extract-result-preview">
                    <div class="extract-result-title">AI 提取到的关键词：</div>
                    <div class="extract-result-tags">
                      <span v-for="(kw, i) in lastExtractedKeywords" :key="i" class="extract-result-tag" :class="{ added: isKeywordAdded(kw) }">
                        {{ kw }}
                      </span>
                    </div>
                  </div>
                </div>
                <div class="form-row"><label>目标数量</label><input v-model.number="selectedNode.config.targetCount" type="number" min="1" max="100" /></div>
                <div class="form-row"><label>获取模式</label><select v-model="selectedNode.config.fetchMode"><option value="random">随机获取</option><option value="top">按热度获取</option><option value="newest">按最新获取</option></select></div>
              </template>
            </template>

            <!-- 商品筛选节点配置 -->
            <template v-if="selectedNode.type === 'PRODUCT_FILTER'">
              <div class="form-row">
                <label>是否启用筛选</label>
                <ToggleSwitch :on="selectedNode.config.enabled !== false" @click="selectedNode.config.enabled = selectedNode.config.enabled !== false ? false : true" />
              </div>
              <div class="form-row">
                <label>筛选规则 Prompt</label>
                <textarea v-model="selectedNode.config.screenPrompt" class="config-textarea" placeholder="输入自然语言筛选条件，例如：只保留价格低于100元、标题中包含iPhone、成色较新、描述完整的商品。&#10;留空则跳过筛选节点。" rows="4"></textarea>
              </div>
              <div v-if="selectedNode.config.screenPrompt" class="form-row">
                <label class="status-label">
                  <span class="status-dot active"></span> 已配置筛选规则
                </label>
              </div>
              <div v-else class="form-row">
                <label class="status-label">
                  <span class="status-dot skip"></span> 未配置筛选规则，将跳过筛选节点
                </label>
              </div>
              <div class="form-row">
                <label>筛选失败后处理方式</label>
                <select v-model="selectedNode.config.onFilterFail">
                  <option value="retry">回到获取节点重新获取</option>
                  <option value="skip">跳过当前商品继续</option>
                  <option value="terminate">终止工作流</option>
                </select>
              </div>
              <div class="form-row"><label>最大重试次数</label><input v-model.number="selectedNode.config.maxRetries" type="number" min="1" max="20" /></div>
            </template>

            <!-- 润色节点配置 -->
            <template v-if="selectedNode.type === 'PRODUCT_POLISH'">
              <div class="form-row">
                <label>是否启用润色</label>
                <ToggleSwitch :on="selectedNode.config.enabled !== false" @click="selectedNode.config.enabled = selectedNode.config.enabled !== false ? false : true" />
              </div>
              <div class="form-row">
<label>润色风格</label>
                <select v-model="selectedNode.config.style">
                  <option value="">请选择润色风格</option>
                  <option value="口语化">口语化风格</option>
                  <option value="简洁">简洁风格</option>
                  <option value="吸引眼球">吸引眼球风格</option>
                  <option value="自定义">自定义风格</option>
                </select>
              </div>
              <div v-if="selectedNode.config.style === '自定义'" class="form-row">
                <label>自定义 Prompt</label>
                <textarea v-model="selectedNode.config.customPrompt" class="config-textarea" placeholder="输入自定义润色要求，例如：请突出商品的高性价比和耐用性，使用亲切的语气。" rows="3"></textarea>
              </div>
              <div class="form-row">
                <label>系统默认 Prompt</label>
                <textarea :value="defaultPolishPrompt" class="config-textarea" style="color:#98a2b3" rows="2" readonly></textarea>
              </div>
              <div v-if="selectedNode.config.style" class="form-row">
                <label class="status-label">
                  <span class="status-dot active"></span> 已配置润色风格：{{ selectedNode.config.style }}
                </label>
              </div>
              <div v-else class="form-row">
                <label class="status-label">
                  <span class="status-dot skip"></span> 未配置润色风格，将跳过润色节点
                </label>
              </div>
              <div class="form-row"><label>改写前预览</label><pre class="preview-box">{{ previewBeforePolish || '暂无数据' }}</pre></div>
              <div class="form-row"><label>改写后预览</label><pre class="preview-box">{{ previewAfterPolish || '点击「测试改写」查看结果' }}</pre></div>
              <AppButton :loading="testingPolish" @click="testPolish">测试改写</AppButton>
            </template>

            <!-- 生图节点配置 -->
            <template v-if="selectedNode.type === 'IMAGE_GENERATE'">
              <div class="form-row">
                <label>是否启用生图</label>
                <ToggleSwitch :on="selectedNode.config.enabled !== false" @click="selectedNode.config.enabled = selectedNode.config.enabled !== false ? false : true" />
              </div>
              <div class="form-row">
                <label>并行任务数 <span class="hint-text">（同时生图+发布的商品数）</span></label>
                <select v-model.number="selectedNode.config.parallelCount" class="input" @change="saveDraft">
                  <option :value="1">1（顺序执行）</option>
                  <option :value="2">2（并行2个）</option>
                  <option :value="3">3（并行3个，推荐）</option>
                  <option :value="4">4（并行4个）</option>
                  <option :value="5">5（并行5个，最高）</option>
                </select>
                <div class="hint-text" style="margin-top:4px">并行度越高速度越快，但会增加 API 并发压力。同账号发布间隔仍保持 10 秒</div>
              </div>
              <div class="form-row">
                <label>生图模型</label>
                <select
                  v-model="selectedNode.config.modelKey"
                  class="input"
                  :disabled="!!imageModelsError || availableImageModels.length === 0"
                  @change="saveDraft"
                >
                  <option value="" disabled>{{ imageModelsError || '请选择已启用且完成配置的生图模型' }}</option>
                  <option v-for="m in availableImageModels" :key="m.moduleKey" :value="m.moduleKey">
                    {{ m.model || m.name || m.moduleKey }}
                  </option>
                </select>
                <div v-if="imageModelsError" class="hint-text error-text">{{ imageModelsError }}</div>
                <div v-else-if="imageModelSelectionNotice" class="hint-text error-text">{{ imageModelSelectionNotice }}</div>
              </div>
              <div class="form-row">
                <label>提示词模式</label>
                <select v-model="selectedNode.config.promptMode" class="input" @change="saveDraft">
                  <option value="default">默认提示词</option>
                  <option value="custom">自定义提示词</option>
                </select>
                <div class="hint-text" style="margin-top:4px">
                  <template v-if="selectedNode.config.promptMode === 'custom'">
                    自定义模式将始终使用你填写的提示词。
                  </template>
                  <template v-else>
                    默认模式会在每次生图前，根据当前商品标题和正文重新判断类目并自动套用后台提示词。
                  </template>
                </div>
              </div>
              <div class="form-row">
                <label>生图提示词</label>
                <textarea
                  v-if="selectedNode.config.promptMode === 'custom'"
                  v-model="selectedNode.config.customImagePrompt"
                  class="config-textarea"
                  placeholder="请输入你自己的生图提示词，可使用 {{TITLE}} 和 {{CONTENT}} 占位符"
                  rows="5"
                  @blur="saveDraft"
                ></textarea>
                <div v-else class="hint-text">当前节点将自动匹配类目提示词；如果没有命中类目，则回退到平台默认生图提示词。</div>
              </div>
              <div class="form-row">
                <label>参考图 <span class="hint-text">（{{ (selectedNode.config.referenceImages || []).length }}/9，可不上传）</span></label>
                <div class="ref-image-list">
                  <div v-for="(img, idx) in (selectedNode.config.referenceImages || [])" :key="idx" class="ref-image-item">
                    <img :src="img" alt="参考图" />
                    <button class="ref-image-remove" title="移除" @click="removeRefImage(idx)">×</button>
                  </div>
                  <label v-if="(selectedNode.config.referenceImages || []).length < 9" class="ref-image-add">
                    <input type="file" accept="image/*" multiple style="display:none" @change="handleRefImageUpload" />
                    <span>+</span>
                  </label>
                </div>
                <div class="hint-text" style="margin-top:4px">上传参考图后为图生图模式，不上传则为纯文生图</div>
              </div>
              <AppButton
                :loading="testingImage"
                :disabled="!isImageModelAvailable(selectedNode.config.modelKey)"
                @click="testGenerateImage"
              >
                测试生图
              </AppButton>
            </template>

            <!-- 发布节点配置 -->
            <template v-if="selectedNode.type === 'PUBLISH'">
              <div class="form-row">
                <label>是否启用发布</label>
                <ToggleSwitch :on="selectedNode.config.enabled !== false" @click="selectedNode.config.enabled = selectedNode.config.enabled !== false ? false : true" />
              </div>
              <div class="form-row">
                <label class="status-label">
                  <span class="status-dot active"></span> 发布账号由触发器节点提供（自动获取）
                </label>
              </div>
              <div class="form-row">
<label>发布分类</label>
                <div class="auto-category-row">
                  <input v-model="selectedNode.config.category" placeholder="留空则自动检测（原商品分类→自动分类→标题匹配）" />
                  <span class="auto-category-hint-text">自动检测</span>
                </div>
              </div>
              <div class="form-row">
<label>发布地址</label>
                <div class="address-search-box">
                  <PublishAddressCascader
                    :model-value="selectedNode.config.address"
                    clearable
                    @update:model-value="updateNodeAddress"
                  />
                  <AppButton size="small" style="margin-top:8px" @click="toggleNodeHistoryList">历史地址</AppButton>
                  <!-- 历史地址列表 -->
                  <div v-if="showNodeHistoryList && historyAddresses.length" class="address-list">
                    <div v-for="(addr, ai) in historyAddresses" :key="ai" class="address-item" @mousedown.prevent="pickAddress(addr)">
                      <span>{{ addr.poiName || addr.address || '地址' + (ai+1) }}</span>
                      <small>{{ addr.city || '' }} {{ addr.area || '' }}</small>
                    </div>
                  </div>
                  <EmptyState v-if="showNodeHistoryList && !historyAddresses.length" icon="📍" :title="historyAddressError || '暂无历史地址'" description="工作流执行成功后，发布地址会自动保存到历史记录。" />
                </div>
                <div v-if="selectedNode.config.address?.poiName && getAddressMissingFields(selectedNode.config.address).length" class="address-field-warning">
                  <span class="warning-icon">!</span>
                  <span>历史地址已保留，但缺少：{{ getAddressMissingFields(selectedNode.config.address).join('、') }}。重新选择省、市、区后可保存为完整的新地址。</span>
                </div>
                <div v-else-if="selectedNode.config.address?.poiName" class="address-field-ok">
                  <span class="ok-icon">✓</span>
                  <span>地址字段完整（prov/city/area/divisionId/gps/poiId/poiName 均已就绪）</span>
                </div>
                <div v-else class="address-field-hint">
                  请选择完整的省、市、区；未配置完整地址时不能保存或执行发布节点。
                </div>
              </div>
              <div class="form-row"><label>库存（固定 999）</label><input :value="999" disabled /></div>
              <div class="form-row"><label>价格策略</label><select v-model="selectedNode.config.priceStrategy"><option value="keep">保持原价</option></select></div>
              <div class="form-row"><label>发布失败原因</label><span class="error-text">{{ publishError || '-' }}</span></div>
            </template>

            <div class="form-row"><label>说明</label><input v-model="selectedNode.desc" /></div>
            <div class="option-line"><span>失败重试</span><ToggleSwitch :on="selectedNode.retry" @click="selectedNode.retry = !selectedNode.retry" /></div>
            <div v-if="selectedNode.retry" class="form-row"><label>重试次数</label><input v-model.number="selectedNode.retryCount" type="number" min="0" max="10" /></div>
            <div v-if="selectedNode.retry" class="form-row"><label>重试间隔（秒）</label><input v-model.number="selectedNode.retryIntervalSeconds" type="number" min="5" max="3600" /></div>
            <div class="form-row"><label>节点参数 JSON</label><textarea v-model="nodeConfigText" class="json-editor"></textarea></div>
            <div v-if="jsonError" class="json-error">{{ jsonError }}</div>
          </template>
          <EmptyState v-else icon="👈" title="请选择一个节点" description="从左侧工作流画布选择节点，查看和配置节点详情。" />
        </template>

        <template v-else>
          <div v-if="executionDetail" class="execution-detail">
            <h3>{{ executionDetail.executionNo }}</h3>
            <div v-if="executionRefreshError" class="global-notice warn execution-refresh-warning" role="alert">
              <span>{{ executionRefreshError }}；当前显示上次成功获取的执行状态。</span>
              <AppButton size="small" @click="retryExecutionRefresh">重新刷新</AppButton>
            </div>
            <p>
<Badge :type="executionDetail.status === 'failed' ? 'red' : executionDetail.status === 'success' ? 'green' : executionDetail.status === 'terminated' ? 'gray' : 'blue'">{{ execStatusText(executionDetail.status) }}</Badge> 进度 {{ executionDetail.progress }}%
              <span v-if="executionDetail.status === 'running' && executionDetail.estimatedMinutes > 0" class="detail-estimate">（预计 {{ executionDetail.estimatedMinutes }} 分钟）</span>
              <span v-else-if="executionDetail.status !== 'running' && computedDurationMs(executionDetail) > 0" class="detail-estimate">（实际耗时 {{ formatDuration(computedDurationMs(executionDetail)) }}）</span>
            </p>

            <!-- ★ 实时进度展示：运行中时显示当前环节、生图 X/Y、剩余时间等 -->
            <div v-if="executionDetail.status === 'running' && liveProgress" class="live-progress-banner">
              <div class="live-progress-icon">
                <span class="live-spinner"></span>
              </div>
              <div class="live-progress-body">
                <div class="live-progress-stage">{{ liveProgress.stage }}</div>
                <div class="live-progress-detail">{{ liveProgress.detail }}</div>
                <div v-if="liveProgress.progressBar" class="live-progress-bar-wrap">
                  <div class="live-progress-bar" :style="{ width: liveProgress.progressBar + '%' }"></div>
                  <span class="live-progress-text">{{ liveProgress.progressBar }}%</span>
                </div>
                <div v-if="liveProgress.eta" class="live-progress-eta">{{ liveProgress.eta }}</div>
              </div>
            </div>

            <!-- ★ 运行中操作区：终止按钮 -->
            <div v-if="executionDetail.status === 'running'" class="running-summary-actions">
              <AppButton
                type="danger"
                :loading="terminating"
                :disabled="!executionDetail.id"
                @click="terminateExecution"
              >
终止执行
</AppButton>
              <span class="terminate-hint">将立即终止当前工作流执行，已获取的商品与已发布的商品不会回滚，终止后可通过"继续执行"恢复</span>
            </div>

            <!-- ★ 已终止信息展示区：显示终止原因 + 继续执行按钮 -->
            <div v-if="executionDetail.status === 'terminated'" class="terminated-info-section">
              <div class="terminated-header">
                <span class="terminated-icon">■</span>
                <span class="terminated-title">执行已终止</span>
              </div>
              <div v-if="executionDetail.errorMessage" class="terminated-reason">
                <span class="terminated-label">终止原因：</span>
                <span class="terminated-reason-text">{{ executionDetail.errorMessage }}</span>
              </div>
              <div class="terminated-summary-actions">
                <AppButton
                  type="primary"
                  :loading="continuing"
                  :disabled="!executionDetail.id"
                  @click="continueExecution"
                >
继续执行（从下一节点恢复）
</AppButton>
                <span class="continue-hint">将跳过已成功的节点，从终止时未完成的节点开始继续执行</span>
              </div>
            </div>

            <!-- 失败信息展示区域 -->
            <div v-if="executionDetail.status === 'failed'" class="failure-info-section">
              <div class="failure-header">
                <span class="failure-icon">✗</span>
                <span class="failure-title">执行失败</span>
              </div>
              <div v-if="executionDetail.errorMessage" class="failure-reason">
                <span class="failure-label">失败原因：</span>
                <span class="failure-reason-text">{{ executionDetail.errorMessage }}</span>
              </div>
              <div v-if="failedStep" class="failure-step">
                <span class="failure-label">失败环节：</span>
                <span class="failure-step-text">{{ failedStep.nodeName }}（{{ failedStep.nodeType }}）</span>
              </div>
              <div v-if="failedStep && failedStep.errorMessage" class="failure-detail">
                <span class="failure-label">详细报错：</span>
                <pre class="failure-stack">{{ failedStep.errorMessage }}</pre>
              </div>
              <div v-if="!executionDetail.errorMessage && !failedStep?.errorMessage" class="failure-reason">
                <span class="failure-label">失败原因：</span>
                <span class="failure-reason-text">未捕获到具体错误信息，请查看时间线或日志获取更多信息。</span>
              </div>
              <!-- ★ 继续执行按钮：从失败节点继续执行（复用已成功节点的 state） -->
              <div v-if="failedContinueHint" class="failure-continue-hint">
                <span class="hint-icon">ⓘ</span>
                <span class="hint-text">
                  <strong>{{ failedContinueHint.summary }}</strong>
                  <template v-if="failedContinueHint.canReuseImages">
                    ，继续执行将复用已生成的图片，仅重新发布失败的商品
                  </template>
                  <template v-if="failedContinueHint.circuitBroken">
                    ，连续{{ failedContinueHint.consecutiveFailCount }}次发布失败已熔断
                  </template>
                </span>
              </div>
              <div class="failure-summary-actions">
                <AppButton
                  type="primary"
                  :loading="continuing"
                  :disabled="!executionDetail.id"
                  @click="continueExecution"
                >
继续执行（从失败节点恢复）
</AppButton>
                <span class="continue-hint">将跳过已成功的节点，从失败节点开始继续执行</span>
              </div>
            </div>

            <div class="tabs mini-tabs">
              <button :class="['tab', { active: execTab === 'steps' }]" @click="execTab = 'steps'">步骤</button>
              <button :class="['tab', { active: execTab === 'timeline' }]" @click="execTab = 'timeline'">时间线</button>
              <button :class="['tab', { active: execTab === 'artifacts' }]" @click="execTab = 'artifacts'">产物</button>
              <button :class="['tab', { active: execTab === 'state' }]" @click="execTab = 'state'">状态变量</button>
            </div>
            <div v-if="execTab === 'steps'">
              <div v-for="s in executionDetail.steps || []" :key="s.id" class="step-line">
                <i :class="s.status"></i>
                <span>{{ s.nodeName }}</span>
                <em>{{ execStatusText(s.status) }}</em>
                <small v-if="s.durationMs">{{ s.durationMs }}ms</small>
              </div>
            </div>
            <div v-if="execTab === 'timeline'">
              <div v-if="(executionDetail.timeline || []).length" class="timeline-list">
                <div v-for="t in executionDetail.timeline" :key="t.id || t.title" class="timeline-item">
                  <span :class="['tl-dot', levelClass(t.eventLevel || t.event_level) ]"></span>
                  <div class="tl-body">
                    <b>{{ t.title }}</b>
                    <p>{{ t.content || '' }}</p>
                    <small>{{ formatTime(t.createdTime) }}</small>
                  </div>
                </div>
              </div>
              <EmptyState v-else icon="🕐" title="暂无时间线数据" description="工作流执行后，节点执行时间线将在此展示。" />
            </div>
            <div v-if="execTab === 'artifacts'">
              <div v-if="(executionDetail.artifacts || []).length" class="artifact-list">
                <div v-for="a in executionDetail.artifacts" :key="a.id || a.nodeKey + a.artifactType" class="artifact-item">
                  <div class="artifact-head">
                    <span class="chip">{{ a.artifactType || a.artifact_type }}</span>
                    <span class="artifact-title">{{ a.title || '' }}</span>
                    <span class="artifact-node">{{ a.nodeKey || a.node_key || '' }}</span>
                  </div>
                  <pre class="artifact-text">{{ formatArtifact(a) }}</pre>
                </div>
              </div>
              <EmptyState v-else icon="📦" title="暂无产物数据" description="节点执行产生的图片、商品、文案等产物会显示在这里。" />
            </div>
            <div v-if="execTab === 'state'">
              <div v-if="(executionDetail.stateVariables || []).length" class="state-variable-list">
                <div v-for="v in executionDetail.stateVariables" :key="v.var_name || v.id" class="state-var-item">
                  <pre class="artifact-text">{{ formatStateVariable(v) }}</pre>
                </div>
              </div>
              <EmptyState v-else icon="🔧" title="暂无状态变量" description="工作流执行过程中产生的中间状态变量会显示在这里。" />
            </div>
          </div>
          <EmptyState v-else icon="🔍" title="请选择执行记录" description="从左侧执行记录列表中选择一项，查看详细执行信息。" />
        </template>
      </CardPanel>
    </div>

    <!-- ★ 工作流地址预检弹框（点击运行测试时若三级查找均失败则弹出） -->
    <WorkflowAddressPicker
      :visible="wfAddressPickerVisible"
      :address-history="wfAddressHistory"
      :saving="wfAddressSaving"
      @confirm="onWfAddressConfirm"
      @cancel="onWfAddressCancel"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import Badge from '../components/Badge.vue'
import BaseTable from '../components/BaseTable.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import Icon from '../components/Icon.vue'
import { confirmAction } from '../utils/confirmAction.js'
import { globalConfirm } from '../composables/confirmState.js'
import { createWorkflowDefinition, deleteWorkflowDefinition, executeWorkflowDefinition, getWorkflow, getWorkflowExecution, getRecentRuns, getExecutionLogs, listWorkflowExecutions, listWorkflows, publishWorkflow, updateWorkflowDefinition, workflowOverview, aiRewriteGoods, aiGenerateImages, aiExtractKeywords, continueWorkflowExecution, terminateWorkflowExecution } from '../api/workflow.js'
import { ensureAiTokenBalance } from '../utils/aiTokenGuard.js'
import { getLiteAccounts } from '../api/accounts.js'
import { getOpportunityImageModels } from '../api/opportunity.js'

// 统一 toast 派发：替代失效的 window.$message，通过全局 xya-toast 事件由 App.vue 渲染
function showToast(message, type = 'info') {
  if (typeof window === 'undefined' || !window.dispatchEvent) return
  window.dispatchEvent(new CustomEvent('xya-toast', {
    detail: { message, isError: type === 'error' || type === 'warning' }
  }))
}
import { getPublishAddressHistory, savePublishAddress } from '../api/publishAddress.js'
import WorkflowAddressPicker from '../components/WorkflowAddressPicker.vue'
import PublishAddressCascader from '../components/PublishAddressCascader.vue'
import EmptyState from '../components/EmptyState.vue'
import { friendlyError } from '../utils/friendlyError.js'
import { formatArtifact, formatStateVariable } from '../utils/artifactFormat.js'
import { accountAuthUsable, accountCookieLabel } from '../utils/accountAuth.js'
import { guardFeatureAction } from '../composables/featureGuard.js'
import { getPublishAddressMissingFields, isPublishAddressComplete, normalizePublishAddress } from '../utils/publishAddress.js'

// ===================== 状态 =====================
const keywordInput = ref('')
const keywordExtractText = ref('')
const extractingKeywords = ref(false)
const lastExtractCount = ref(0)
const lastExtractedKeywords = ref([])
const extractError = ref('')

// 测试结果状态
const testResult = ref(null)
const showRawLog = ref(false)

// ===================== 通用状态 =====================
const keyword = ref('')
const statusFilter = ref('')
const workflows = ref([])
const overview = ref({})
const overviewLoadError = ref('')
const workflowsLoadError = ref('')
const workflowDetailError = ref('')
const executionsLoadError = ref('')
const recentRunsLoadError = ref('')
const accountsLoadError = ref('')
const selectedWorkflow = ref(null)
const draft = ref({ name: '未命名工作流', description: '', triggerType: 'manual', config: {}, canvas: { zoom: 100 } })
const nodes = ref([])
const edges = ref([])
const executions = ref([])
const recentRuns = ref([])
const executionDetail = ref(null)
const executionRefreshError = ref('')
const selectedNodeId = ref('')
const edgeSource = ref('')
const canvasEl = ref(null)
const drag = ref(null)
const configTab = ref('node')
const execTab = ref('steps')
const jsonError = ref('')
const saving = ref(false)
const publishing = ref(false)
const running = ref(false)
// ★ 继续执行已失败工作流（复用原 execution_id，跳过已成功节点）
const continuing = ref(false)
// ★ 终止运行中的工作流
const terminating = ref(false)
const lastSavedAt = ref('')
const zoom = ref(100)
const zoomMin = 50
const zoomMax = 160
const zoomStep = 10

// 节点配置增强
const testingPolish = ref(false)
const testingImage = ref(false)
const previewBeforePolish = ref('')
const previewAfterPolish = ref('')
const availableImageModels = ref([])
const imageModelsError = ref('')
const imageModelSelectionNotice = ref('')
const publishError = ref('')
const historyAddresses = ref([])
const historyAddressError = ref('')

const showNodeHistoryList = ref(false)

// ★ 工作流全局地址预检：点击运行测试时若三级查找均失败则弹出此对话框
const wfAddressPickerVisible = ref(false)
const wfAddressHistory = ref([])
const wfAddressSaving = ref(false)
let wfAddressResolver = null  // Promise resolver，用户确认/取消时 resolve
const defaultPolishPrompt = '请根据商品的标题和正文，生成适合闲鱼平台的商品标题和描述。'
const defaultImagePrompt = '生成1张适合闲鱼/淘宝风格的中国电商商品主图（1:1正方形）。要求：不是平台截图，不要店铺名、头像、导航栏、二维码、水印、联系方式。画面必须只有一个明确主视觉，主体大、居中、易识别，整体高对比、强吸睛、适合手机缩略图点击。采用中文电商广告封面风格，可包含简短有力的大标题和2到3个短卖点标签，但不要堆满小字。背景简洁有层次，可用深色或亮色渐变搭配高饱和点缀，突出商品价值与成交感。不要复杂场景，不要3D渲染感，不要赛博霓虹，不要艺术海报感，要像高点击率商品主图。'

function normalizeImageGenerateConfig(config = {}) {
  const normalized = { ...config }
  const rawMode = String(normalized.promptMode || '').trim().toLowerCase()
  const legacyPrompt = String(normalized.imagePrompt || '').trim()
  const customPrompt = String(normalized.customImagePrompt || '').trim()
  normalized.promptMode = rawMode === 'custom' || rawMode === 'default'
    ? rawMode
    : (customPrompt || legacyPrompt ? 'custom' : 'default')
  normalized.customImagePrompt = customPrompt || legacyPrompt || ''
  normalized.imagePrompt = normalized.customImagePrompt
  normalized.parallelCount = positiveNumber(normalized.parallelCount) ? Number(normalized.parallelCount) : 3
  normalized.referenceImages = Array.isArray(normalized.referenceImages) ? normalized.referenceImages : []
  normalized.imageSize = normalized.imageSize || '1024x1024'
  normalized.enabled = normalized.enabled !== false
  return normalized
}

function buildImageGenerateTestPayload(config, overrides = {}) {
  const normalized = normalizeImageGenerateConfig(config)
  const title = overrides.title || '测试商品'
  const description = overrides.description || '这是一个测试商品描述'
  return {
    title,
    description,
    prompt: defaultImagePrompt,
    promptMode: normalized.promptMode,
    customPrompt: normalized.promptMode === 'custom' ? normalized.customImagePrompt : '',
    itemTitle: title,
    itemDescription: description,
    imageCount: 1,
    size: normalized.imageSize || '1024x1024',
    modelKey: normalized.modelKey || undefined,
    referenceImages: normalized.referenceImages || [],
  }
}

function imageModelsOf(response) {
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.models)) {
    throw new Error('图片模型列表响应格式异常')
  }
  const count = Number(data.count)
  if (!Number.isSafeInteger(count) || count < 0 || count !== data.models.length) {
    throw new Error('图片模型数量响应格式异常')
  }

  const seenKeys = new Set()
  const result = []
  data.models.forEach((model, index) => {
    if (!model || typeof model !== 'object' || Array.isArray(model)) {
      throw new Error(`第 ${index + 1} 个图片模型响应格式异常`)
    }
    const moduleKey = String(model.moduleKey || '').trim()
    if (!moduleKey || seenKeys.has(moduleKey)) {
      throw new Error(`第 ${index + 1} 个图片模型缺少唯一标识`)
    }
    // 防御性过滤：仅保留已启用且完成配置的模型，未配置的模型不显示
    if (model.configured !== true || model.enabled !== true) {
      return
    }
    seenKeys.add(moduleKey)
    result.push({ ...model, moduleKey })
  })
  return result
}

function isImageModelAvailable(moduleKey) {
  const key = String(moduleKey || '').trim()
  return Boolean(key && availableImageModels.value.some(model => model.moduleKey === key))
}

async function ensureWorkflowImageModelsReady(actionLabel) {
  const imageNodes = nodes.value.filter(node => node.type === 'IMAGE_GENERATE' && node.config?.enabled !== false)
  if (!imageNodes.length) return true
  const loaded = await loadImageModels()
  if (!loaded) {
    await globalConfirm.alert(`${actionLabel}前生图模型校验失败`, imageModelsError.value || '生图模型状态暂时不可用')
    return false
  }
  const invalidNodes = imageNodes.filter(node => !isImageModelAvailable(node.config?.modelKey))
  if (!invalidNodes.length) return true
  const labels = invalidNodes.map(node => node.name || node.id || '未命名生图节点').join('、')
  await globalConfirm.alert(`${actionLabel}前生图模型校验失败`, `以下生图节点未选择已启用且完成配置的模型：${labels}`)
  return false
}

const canvasWidth = 1060
const canvasHeight = 520
const containerWidth = ref(canvasWidth)
const accounts = ref([])

const canvasScale = computed(() => zoom.value / 100)
const fitScale = computed(() => {
  const scaleX = containerWidth.value / canvasWidth
  return Math.max(0.25, Math.min(1, scaleX))
})
const canvasTransform = computed(() => {
  const s = fitScale.value * canvasScale.value
  return { transform: `scale(${s})`, transformOrigin: '0 0' }
})
const canvasOverflow = computed(() => {
  const s = fitScale.value * canvasScale.value
  return s > 1 ? 'auto' : 'hidden'
})

const nodeTypes = [
  { type: 'TRIGGER', label: '触发器', icon: 'clock' },
  { type: 'PRODUCT_FETCH', label: '商品获取', icon: 'product' },
  { type: 'PRODUCT_FILTER', label: '商品筛选', icon: 'data' },
  { type: 'PRODUCT_POLISH', label: '润色节点', icon: 'reply' },
  { type: 'IMAGE_GENERATE', label: '生图节点', icon: 'image' },
  { type: 'PUBLISH', label: '发布节点', icon: 'publish' }
]

const execCols = [
  { key: 'executionNo', title: '执行编号' },
  { key: 'workflowName', title: '工作流' },
  { key: 'triggerMode', title: '触发方式' },
  { key: 'status', title: '状态' },
  { key: 'progress', title: '进度' },
  { key: 'estimatedMinutes', title: '预计耗时' },
  { key: 'createdTime', title: '创建时间' },
  { key: 'op', title: '操作' }
]

const selectedNode = computed(() => nodes.value.find(n => n.id === selectedNodeId.value))
const failedStep = computed(() => (executionDetail.value?.steps || []).find(s => s.status === 'failed'))
const testResultLogFailedNode = computed(() => (testResult.value?.logEntries || []).find(e => e.level === 'error'))
const EXEC_POLL_INTERVAL = 3000

function upsertExecutionRow(detail) {
  if (!detail?.id) return
  const nextRow = {
    ...detail,
    workflowId: detail.workflowId ?? selectedWorkflow.value?.id,
    workflowName: detail.workflowName ?? selectedWorkflow.value?.name ?? draft.value?.name,
  }
  const index = executions.value.findIndex(item => String(item.id) === String(detail.id))
  if (index === -1) {
    executions.value = [nextRow, ...executions.value].slice(0, 8)
    return
  }
  const next = executions.value.slice()
  next[index] = { ...next[index], ...nextRow }
  executions.value = next
}

// ★ 失败执行面板的「继续执行提示」：从 artifacts 提取生图/发布统计
//   - 若有生图成功的图片且发布有失败，提示「继续执行将复用 N 张已生成的图片重新发布」
//   - 若熔断（circuitBroken=true），额外提示熔断原因
const failedContinueHint = computed(() => {
  const detail = executionDetail.value
  if (!detail || detail.status !== 'failed') return null
  const artifacts = detail.artifacts || []
  // 找到生图+发布 artifact（artifactType=image 或 title 含「生图+发布」）
  const imgArt = artifacts.find(a => {
    const t = String(a.artifactType || a.artifact_type || '')
    const title = String(a.title || '')
    return t === 'image' || title.includes('生图') || title.includes('发布')
  })
  if (!imgArt) return null
  const c = imgArt.content || {}
  const imgCount = Array.isArray(c.images) ? c.images.length : 0
  const aiOkCount = Array.isArray(c.images) ? c.images.filter(i => i.aiOk).length : 0
  const pubSuccess = Number(c.publishSuccessCount || 0)
  const pubFailed = Number(c.publishFailedCount || 0)
  const circuitBroken = !!c.circuitBroken
  if (pubFailed === 0 && !circuitBroken) return null
  const parts = []
  if (aiOkCount > 0) parts.push(`生图已成功 ${aiOkCount}/${imgCount} 张`)
  if (pubSuccess > 0) parts.push(`发布成功 ${pubSuccess} 个`)
  if (pubFailed > 0) parts.push(`发布失败 ${pubFailed} 个`)
  if (circuitBroken) parts.push('已熔断终止')
  return {
    summary: parts.join('，'),
    canReuseImages: aiOkCount > 0 && pubFailed > 0,
    circuitBroken,
    consecutiveFailCount: Number(c.consecutiveFailCount || 0),
  }
})

// ★ 实时进度解析：从 timeline 事件中提取当前环节、逐项进度、剩余时间等
//   支持 backend 写入的 fetch_progress / polish_progress / image_progress / publish_progress / node_start 事件
const liveProgress = computed(() => {
  const detail = executionDetail.value
  if (!detail || detail.status !== 'running') return null
  const timeline = detail.timeline || []
  if (!timeline.length) return null

  const ts = t => new Date(t.createdTime || t.created_time || 0).getTime()
  const sorted = [...timeline].sort((a, b) => ts(b) - ts(a))
  const payloadOf = t => { try { return JSON.parse(t.payloadJson || t.payload_json || '{}') } catch { return {} } }

  // ★ 统一解析各类逐项进度事件，提取 done/total/首尾时间戳
  //   事件类型：
  //     image_progress(生图) / fetch_progress(商品获取) / polish_progress(润色) / publish_progress(发布)
  //     image_and_publish_progress(生图+发布一体化，新流程：生1张图→立即发布→下一张)
  const progressTypes = {
    image_progress:   { doneKey: 'progress', totalKey: 'total', label: '生图',   unit: '张', avgMs: 60000 },
    fetch_progress:  { doneKey: 'progress', totalKey: 'total', label: '商品获取', unit: '个', avgMs: 1500 },
    polish_progress: { doneKey: 'progress', totalKey: 'total', label: '润色',   unit: '个', avgMs: 5000 },
    publish_progress:{ doneKey: 'progress', totalKey: 'total', label: '发布',   unit: '个', avgMs: 12000 },
    image_and_publish_progress: { doneKey: 'imageProgress', totalKey: 'imageTotal', label: '生图+发布', unit: '张', avgMs: 70000 },
  }
  const nodeProgress = {}  // { image_progress: {done, total, firstTs, lastTs, firstTitle} }
  for (const t of timeline) {
    const et = t.eventType || t.event_type || ''
    const cfg = progressTypes[et]
    if (!cfg) continue
    const p = payloadOf(t)
    const done = p[cfg.doneKey] || 0
    const total = p[cfg.totalKey] || 0
    if (!nodeProgress[et]) nodeProgress[et] = { done: 0, total: 0, firstTs: null, lastTs: null }
    const np = nodeProgress[et]
    np.done = Math.max(np.done, done)
    if (total > 0) np.total = total
    const tms = ts(t)
    if (tms) {
      np.lastTs = tms
      if (!np.firstTs) np.firstTs = tms
    }
  }
  // ★ 新事件 image_and_publish_progress：同步合并到 image_progress 和 publish_progress
  for (const t of timeline) {
    const et = t.eventType || t.event_type || ''
    if (et !== 'image_and_publish_progress') continue
    const p = payloadOf(t)
    const imgDone = p.imageProgress || 0
    const imgTotal = p.imageTotal || 0
    const pubDone = p.publishProgress || 0
    const pubTotal = p.publishTotal || 0
    const tms = ts(t)
    // 同步到 image_progress
    if (!nodeProgress.image_progress) nodeProgress.image_progress = { done: 0, total: 0, firstTs: null, lastTs: null }
    nodeProgress.image_progress.done = Math.max(nodeProgress.image_progress.done, imgDone)
    if (imgTotal > 0) nodeProgress.image_progress.total = imgTotal
    if (tms) { nodeProgress.image_progress.lastTs = tms; if (!nodeProgress.image_progress.firstTs) nodeProgress.image_progress.firstTs = tms }
    // 同步到 publish_progress
    if (!nodeProgress.publish_progress) nodeProgress.publish_progress = { done: 0, total: 0, firstTs: null, lastTs: null }
    nodeProgress.publish_progress.done = Math.max(nodeProgress.publish_progress.done, pubDone)
    if (pubTotal > 0) nodeProgress.publish_progress.total = pubTotal
    if (tms) { nodeProgress.publish_progress.lastTs = tms; if (!nodeProgress.publish_progress.firstTs) nodeProgress.publish_progress.firstTs = tms }
  }
  // 兜底：从标题 "生图进度: 5/15" 提取
  for (const t of sorted) {
    const m = (t.title || '').match(/生图进度[:：]\s*(\d+)\s*\/\s*(\d+)/)
    if (m && (!nodeProgress.image_progress || !nodeProgress.image_progress.total)) {
      nodeProgress.image_progress = nodeProgress.image_progress || { done: 0, total: 0, firstTs: null, lastTs: null }
      nodeProgress.image_progress.done = parseInt(m[1])
      nodeProgress.image_progress.total = parseInt(m[2])
      break
    }
  }

  // ★ 找当前所处环节（最新的 progress / node_start 事件）
  let currentStage = '执行中'
  let stageDetail = ''
  let activeProgressType = null  // 当前活跃的逐项进度类型
  for (const t of sorted) {
    const et = t.eventType || t.event_type || ''
    const title = t.title || ''
    const content = t.content || ''
    if (et === 'image_and_publish_progress') {
      // ★ 新流程：生图+发布一体化，最新事件决定当前展示文案
      const p = payloadOf(t)
      const imgDone = p.imageProgress || 0
      const imgTotal = p.imageTotal || 0
      const pubDone = p.publishProgress || 0
      const pubTotal = p.publishTotal || 0
      const pubStatus = p.publishStatus || ''
      // ★ 全部完成时显示收尾文案
      if (imgDone >= imgTotal && pubDone >= pubTotal) {
        currentStage = `生图+发布已全部完成（共 ${imgTotal} 张图，${pubDone} 个发布）`
        stageDetail = `等待节点收尾进入下一步`
        activeProgressType = 'image_progress'
        break
      }
      // 并行模式下使用"已生图 N/M"代替"正在生成第N+1张"
      const parallelCount = p.parallelCount || 1
      const parallelHint = parallelCount > 1 ? `（并行${parallelCount}个）` : ''
      if (pubStatus === 'published') {
        currentStage = `正在并行生图 ${imgDone}/${imgTotal} 张并发布${parallelHint}`
        stageDetail = `已生图 ${imgDone}/${imgTotal} 张，已发布 ${pubDone}/${pubTotal} 个商品。最近：发布成功`
        activeProgressType = 'image_progress'  // ETA 按生图速度计算（更慢）
      } else if (pubStatus === 'failed') {
        currentStage = `生图成功但发布失败，继续处理中${parallelHint}`
        stageDetail = `已生图 ${imgDone}/${imgTotal} 张，已发布 ${pubDone}/${pubTotal} 个商品。失败原因：${content}`
        activeProgressType = 'image_progress'
      } else if (pubStatus === 'skipped_no_ai_image') {
        currentStage = `部分商品生图失败已跳过，继续处理中${parallelHint}`
        stageDetail = `已生图 ${imgDone}/${imgTotal} 张，已发布 ${pubDone}/${pubTotal} 个商品。无AI图跳过`
        activeProgressType = 'image_progress'
      } else if (pubStatus === 'skipped_duplicate') {
        currentStage = `部分商品已发布过（重复跳过），继续处理中${parallelHint}`
        stageDetail = `已生图 ${imgDone}/${imgTotal} 张，已发布 ${pubDone}/${pubTotal} 个商品（含跳过重复）`
        activeProgressType = 'image_progress'
      } else {
        currentStage = `正在并行生图 ${imgDone}/${imgTotal} 张${parallelHint}`
        stageDetail = `已生图 ${imgDone}/${imgTotal} 张，已发布 ${pubDone}/${pubTotal} 个`
        activeProgressType = 'image_progress'
      }
      break
    } else if (progressTypes[et]) {
      const np = nodeProgress[et] || { done: 0, total: 0 }
      const done = np.done, total = np.total
      if (et === 'image_progress') {
        // ★ 全部完成时显示收尾文案
        if (done >= total && total > 0) {
          currentStage = `生图已全部完成（共 ${total} 张）`
          stageDetail = '等待节点收尾进入下一步'
        } else {
          const rem = total - done
          currentStage = `正在生成第 ${done + 1} 张封面图（共 ${total} 张）`
          stageDetail = rem > 0 ? `已生成 ${done}/${total} 张，还剩 ${rem} 张` : '生图即将完成'
        }
      } else if (et === 'fetch_progress') {
        currentStage = `正在获取第 ${done + 1} 个商品（共 ${total} 个）`
        stageDetail = content || `已获取 ${done}/${total} 个商品`
      } else if (et === 'polish_progress') {
        currentStage = `正在润色第 ${done + 1} 个商品（共 ${total} 个）`
        stageDetail = content || `已润色 ${done}/${total} 个商品`
      } else if (et === 'publish_progress') {
        currentStage = `正在发布第 ${done + 1} 个商品（共 ${total} 个）`
        stageDetail = content || `已发布 ${done}/${total} 个商品`
      }
      activeProgressType = et
      break
    } else if (et === 'live_image_start') {
      const np = nodeProgress.image_progress || { total: payloadOf(t).total || 0 }
      currentStage = `开始生图: 共 ${np.total} 张`
      stageDetail = '生图模型正在生成第一张图像，生完即发布'
      activeProgressType = 'image_progress'
      break
    } else if (et === 'image_start') {
      // ★ 生图开始事件：每个 worker 开始调用生图模型时发射，让前端在 60-130 秒等待期间看到进度在动
      const p = payloadOf(t)
      const startIdx = p.progress || 0
      const total = p.total || (nodeProgress.image_progress?.total || 0)
      // 确保 nodeProgress.image_progress 存在，让 ETA 计算能用
      if (!nodeProgress.image_progress) nodeProgress.image_progress = { done: 0, total: 0, firstTs: null, lastTs: null }
      if (total > 0) nodeProgress.image_progress.total = total
      const tms = ts(t)
      if (tms) { nodeProgress.image_progress.lastTs = tms; if (!nodeProgress.image_progress.firstTs) nodeProgress.image_progress.firstTs = tms }
      currentStage = `正在生成第 ${startIdx} 张封面图（共 ${total} 张）`
      stageDetail = content || `生图模型正在生成图像，每张约 60-130 秒，请耐心等待`
      activeProgressType = 'image_progress'
      break
    } else if (et === 'publish_summary') {
      const p = payloadOf(t)
      currentStage = `发布完成（汇总）`
      stageDetail = `成功 ${p.successCount}，失败 ${p.failedCount}，跳过 ${(p.skippedNoAiCount || 0) + (p.skippedDuplicateCount || 0)}`
      break
    } else if (et === 'live_shop_fetched') {
      currentStage = '店铺商品爬取中'
      stageDetail = content
      break
    } else if (et === 'live_shop_done') {
      currentStage = '店铺商品获取完成'
      stageDetail = content
      break
    } else if (et === 'node_start') {
      if (title.includes('生图') || title.includes('IMAGE')) {
        const np = nodeProgress.image_progress || { total: 0 }
        currentStage = np.total > 0 ? `开始生图: 共 ${np.total} 张` : '生图准备中'
        stageDetail = '生图模型正在生成图像，生完即发布'
        activeProgressType = 'image_progress'
      } else if (title.includes('商品获取') || title.includes('PRODUCT_FETCH')) {
        currentStage = '商品获取中'
        stageDetail = '正在搜索或爬取商品'
        activeProgressType = 'fetch_progress'
      } else if (title.includes('润色') || title.includes('POLISH')) {
        currentStage = '润色文案中'
        stageDetail = 'AI 正在为每个商品生成标题和正文'
        activeProgressType = 'polish_progress'
      } else if (title.includes('筛选') || title.includes('FILTER')) {
        currentStage = '商品筛选中'
        stageDetail = '正在筛选符合要求的商品'
      } else if (title.includes('发布') || title.includes('PUBLISH')) {
        currentStage = '发布商品中'
        stageDetail = '正在将商品发布到闲鱼'
        activeProgressType = 'publish_progress'
      } else if (title.includes('触发') || title.includes('TRIGGER')) {
        currentStage = '工作流已触发'
        stageDetail = '准备开始执行'
      } else {
        currentStage = title
        stageDetail = content
      }
      break
    } else if (et === 'node_success' || et === 'node_failed') {
      // 节点已完成，没有进行中的逐项进度
      break
    }
  }

  // ★ 计算进度条
  let progressBar
  let eta = ''
  const nodeTotal = detail.nodeTotal || detail.node_total || 6
  const nodeSuccess = detail.nodeSuccess || detail.node_success || 0
  const baseUnit = 100 / nodeTotal

  if (activeProgressType && nodeProgress[activeProgressType] && nodeProgress[activeProgressType].total > 0) {
    const np = nodeProgress[activeProgressType]
    const cfg = progressTypes[activeProgressType]
    const ratio = np.done / np.total
    progressBar = Math.min(99, Math.round((nodeSuccess * baseUnit) + (ratio * baseUnit)))
    // ★ ETA 估算：用首末时间戳计算平均耗时，乘以剩余数量
    if (np.firstTs && np.lastTs && np.done > 0 && np.done < np.total) {
      const elapsed = np.lastTs - np.firstTs
      const avgPerItem = elapsed / np.done
      const remaining = np.total - np.done
      const remainingMs = remaining * avgPerItem
      const remainingMin = Math.max(1, Math.round(remainingMs / 60000))
      const remainingSec = Math.round(remainingMs / 1000)
      if (remainingMin >= 1) {
        eta = `预计还需约 ${remainingMin} 分钟（剩 ${remaining} ${cfg.unit}，平均 ${Math.round(avgPerItem / 1000)} 秒/${cfg.unit}）`
      } else {
        eta = `预计还需约 ${remainingSec} 秒（剩 ${remaining} ${cfg.unit}）`
      }
    } else if (np.done >= np.total) {
      eta = '当前节点即将完成，进入下一步'
    } else if (np.done === 0 && np.total > 0) {
      eta = `共 ${np.total} ${cfg.unit}待处理，预计 ${cfg.avgMs}ms/${cfg.unit}`
    }
  } else {
    // 无逐项进度：用节点完成度
    let inProgressBonus = 0
    for (const t of sorted) {
      const et = t.eventType || t.event_type || ''
      if (et === 'node_start') { inProgressBonus = 0.5; break }
      if (et === 'node_success' || et === 'node_failed') break
    }
    progressBar = Math.min(99, Math.round((nodeSuccess + inProgressBonus) * baseUnit))
    if (detail.status === 'success') progressBar = 100
  }
  // 优先使用后端 progress 字段（现在后端会实时更新），取较大值避免回退
  const dbProgress = detail.progress ?? 0
  if (dbProgress > 0) progressBar = Math.max(progressBar, Math.min(99, dbProgress))

  return {
    stage: currentStage,
    detail: stageDetail,
    progressBar: progressBar > 0 ? progressBar : null,
    eta: eta || null,
  }
})

// ★ 自动轮询：运行中时优先只刷新当前执行详情，降低跨区请求风暴
const EXECUTION_STATUSES = new Set(['queued', 'running', 'success', 'failed', 'partial_success', 'terminated'])
const ACTIVE_EXECUTION_STATUSES = new Set(['queued', 'running'])
let _execPollingTimer = null
let _execPollingInFlight = false

function executionDetailOf(response, expectedId) {
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('执行详情响应格式异常')
  }
  if (data.id === null || data.id === undefined || String(data.id) !== String(expectedId)) {
    throw new Error('执行详情响应与当前任务不一致')
  }
  if (!EXECUTION_STATUSES.has(data.status)) {
    throw new Error('执行详情缺少有效任务状态')
  }
  const progress = Number(data.progress)
  if (!Number.isFinite(progress) || progress < 0 || progress > 100) {
    throw new Error('执行详情进度响应格式异常')
  }
  for (const key of ['steps', 'artifacts', 'timeline', 'stateVariables']) {
    if (!Array.isArray(data[key])) throw new Error(`执行详情 ${key} 响应格式异常`)
  }
  return { ...data, progress }
}

async function refreshExecutionDetail({ refreshLists = false } = {}) {
  const detail = executionDetail.value
  if (!detail?.id) return false
  try {
    const res = await getWorkflowExecution(detail.id)
    const nextDetail = executionDetailOf(res, detail.id)
    executionDetail.value = nextDetail
    executionRefreshError.value = ''
    upsertExecutionRow(nextDetail)
    if (refreshLists) {
      await Promise.allSettled([loadExecutions(), loadRecentRuns(), loadOverview()])
    }
    return true
  } catch (error) {
    executionRefreshError.value = error?.message || '执行状态刷新失败'
    throw error
  }
}

async function retryExecutionRefresh() {
  try {
    await refreshExecutionDetail({ refreshLists: true })
  } catch {
    // The in-page unavailable notice remains visible with the last known state.
  }
}

function startExecPolling() {
  stopExecPolling()
  const tick = async () => {
    const detail = executionDetail.value
    if (!detail || !ACTIVE_EXECUTION_STATUSES.has(detail.status)) {
      stopExecPolling()
      return
    }
    if (_execPollingInFlight) return
    _execPollingInFlight = true
    try {
      await refreshExecutionDetail()
      if (executionDetail.value?.status && !ACTIVE_EXECUTION_STATUSES.has(executionDetail.value.status)) {
        await Promise.allSettled([loadExecutions(), loadRecentRuns(), loadOverview()])
      }
    } catch (e) {
      console.warn('轮询执行详情失败', e)
    } finally {
      _execPollingInFlight = false
    }
  }
  tick().catch(() => {})
  _execPollingTimer = setInterval(() => {
    tick().catch(() => {})
  }, EXEC_POLL_INTERVAL)
}
function stopExecPolling() {
  if (_execPollingTimer) { clearInterval(_execPollingTimer); _execPollingTimer = null }
}
watch(() => executionDetail.value?.status, (newStatus) => {
  if (ACTIVE_EXECUTION_STATUSES.has(newStatus)) startExecPolling()
  else stopExecPolling()
})
watch(() => executionDetail.value?.id, () => {
  executionRefreshError.value = ''
})
const nodeConfigText = computed({
  get: () => selectedNode.value ? JSON.stringify(selectedNode.value.config || {}, null, 2) : '',
  set: v => {
    if (!selectedNode.value) return
    try { selectedNode.value.config = JSON.parse(v || '{}'); jsonError.value = '' } catch { jsonError.value = '节点参数 JSON 格式错误' }
  }
})
const workflowConfigText = computed({
  get: () => JSON.stringify(draft.value.config || {}, null, 2),
  set: v => {
    try { draft.value.config = JSON.parse(v || '{}'); jsonError.value = '' } catch { jsonError.value = '工作流配置 JSON 格式错误' }
  }
})
const validation = computed(() => validateGraph(nodes.value, edges.value))

// 账号多选切换
function toggleAccount(acctId) {
  const node = selectedNode.value
  if (!node || node.type !== 'TRIGGER') return
  if (!node.config.selectedAccountIds) node.config.selectedAccountIds = []
  const idx = node.config.selectedAccountIds.indexOf(acctId)
  if (idx >= 0) {
    node.config.selectedAccountIds.splice(idx, 1)
  } else {
    node.config.selectedAccountIds.push(acctId)
  }
}

// 清理已删除账号的残留 ID：仅保留当前账号列表中仍存在的账号
// 避免触发器 selectedAccountIds / 遗留 selectedAccountId 单值 / PUBLISH 节点 accountIds
// 残留已删除账号 ID 导致运行前校验报“账号不存在或已删除”
function pruneStaleAccountIds() {
  if (!accounts.value.length) return
  // 用 String 比较避免 number/string 类型不一致导致 has() 失败
  const validIds = new Set(accounts.value.map(a => String(a.id)))
  for (const node of nodes.value) {
    const cfg = node.config
    if (!cfg || typeof cfg !== 'object') continue
    if (node.type === 'TRIGGER') {
      // 数组字段（当前格式）
      if (Array.isArray(cfg.selectedAccountIds)) {
        cfg.selectedAccountIds = cfg.selectedAccountIds.filter(id => validIds.has(String(id)))
      }
      // 遗留单值字段：selectedAccountId 不在有效账号集合中则删除
      if (cfg.selectedAccountId != null && !validIds.has(String(cfg.selectedAccountId))) {
        delete cfg.selectedAccountId
      }
    }
    if (node.type === 'PUBLISH') {
      // PUBLISH 节点可能残留 accountIds / accountId / selectedAccountId
      if (Array.isArray(cfg.accountIds)) {
        cfg.accountIds = cfg.accountIds.filter(id => validIds.has(String(id)))
        if (cfg.accountIds.length === 0) delete cfg.accountIds
      }
      if (cfg.accountId != null && !validIds.has(String(cfg.accountId))) {
        delete cfg.accountId
      }
      if (cfg.selectedAccountId != null && !validIds.has(String(cfg.selectedAccountId))) {
        delete cfg.selectedAccountId
      }
    }
  }
}

// 关键词操作
function addKeyword() {
  const node = selectedNode.value
  if (!node || node.type !== 'PRODUCT_FETCH') return
  const raw = keywordInput.value.trim()
  if (!raw) return
  const parts = raw.split(/[,，]+/).map(s => s.trim()).filter(Boolean)
  if (!parts.length) return
  if (!node.config.keywords) node.config.keywords = []
  for (const p of parts) {
    if (!node.config.keywords.includes(p)) {
      node.config.keywords.push(p)
    }
  }
  keywordInput.value = ''
}
function removeKeyword(index) {
  const node = selectedNode.value
  if (!node || !node.config.keywords) return
  node.config.keywords.splice(index, 1)
}

function isKeywordAdded(kw) {
  const node = selectedNode.value
  return !!(node?.config?.keywords && node.config.keywords.includes(kw))
}

async function doExtractKeywords() {
  const text = (keywordExtractText.value || '').trim()
  extractError.value = ''
  lastExtractedKeywords.value = []
  lastExtractCount.value = 0
  if (!text) {
    extractError.value = '请先粘贴要提取关键词的文本'
    showToast(extractError.value, 'warning')
    return
  }
  if (text.length < 3) {
    extractError.value = '文本内容太短，至少3个字符'
    showToast(extractError.value, 'warning')
    return
  }
  const node = selectedNode.value
  if (!node || node.type !== 'PRODUCT_FETCH') {
    extractError.value = '请先选中商品获取节点'
    return
  }
  extractingKeywords.value = true
  try {
    const res = await aiExtractKeywords({ text })

    // 兼容多种响应结构：res.data.keywords / res.keywords / res.data.data.keywords
    let kws = []
    if (Array.isArray(res?.data?.keywords)) kws = res.data.keywords
    else if (Array.isArray(res?.keywords)) kws = res.keywords
    else if (Array.isArray(res?.data?.data?.keywords)) kws = res.data.data.keywords
    else if (Array.isArray(res?.data)) kws = res.data

    if (!Array.isArray(kws)) kws = []
    kws = kws.map(k => String(k).trim()).filter(Boolean)

    lastExtractedKeywords.value = kws

    if (!kws.length) {
      extractError.value = 'AI未能从文本中提取出关键词，请尝试换一段文本'
      showToast(extractError.value, 'warning')
      return
    }

    // 确保keywords数组存在
    if (!Array.isArray(node.config.keywords)) node.config.keywords = []
    let added = 0
    for (const kw of kws) {
      if (!node.config.keywords.includes(kw)) {
        node.config.keywords.push(kw)
        added++
      }
    }
    lastExtractCount.value = added

    // 保存到后端；保存失败时不得把本地临时修改描述成已完成。
    const savedWorkflowId = await saveDraft()
    if (!savedWorkflowId) {
      extractError.value = `已在当前页面提取 ${kws.length} 个关键词，但草稿保存失败；请重试保存后再离开页面。`
      showToast(extractError.value, 'warning')
      return
    }

    if (added > 0) {
      showToast(`AI已提取${kws.length}个关键词，新增${added}个到关键词列表`, 'success')
    } else {
      showToast(`AI提取到${kws.length}个关键词，均已在列表中，无新增`, 'info')
    }
  } catch (e) {
    console.error('[ExtractKeywords] 提取失败:', e)
    extractError.value = e?.message || e?.msg || '关键词提取失败，请检查网络后重试'
    showToast(extractError.value, 'error')
  } finally {
    extractingKeywords.value = false
  }
}

// ===================== 节点测试方法 =====================

async function testPolish() {
  if (!await guardFeatureAction()) return
  const node = selectedNode.value
  if (!node || node.type !== 'PRODUCT_POLISH') return
  if (!(await ensureAiTokenBalance({ sceneName: '工作流润色测试' }))) return
  testingPolish.value = true
  try {
    const fetchNode = nodes.value.find(n => n.type === 'PRODUCT_FETCH')
    const firstGoodsTitle = fetchNode?.config?.keywords?.[0] || '测试商品'
    previewBeforePolish.value = `商品标题：${firstGoodsTitle}\n商品描述：这是一款优质商品，性价比高。`

    const res = await aiRewriteGoods({
      title: firstGoodsTitle,
      description: '这是一款优质商品，性价比高。',
      style: node.config.style || '',
      customPrompt: node.config.customPrompt || '',
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.title !== 'string' || typeof data.description !== 'string' || !Array.isArray(data.highlights)) {
      throw new Error('AI 改写测试响应格式异常')
    }
    previewAfterPolish.value = `标题：${data.title || ''}\n正文：${data.description || ''}\n卖点：${(data.highlights || []).join('、')}`
  } catch (e) {
    previewAfterPolish.value = '改写调用失败：' + (e.message || e.msg || '未知错误')
  } finally {
    testingPolish.value = false
  }
}

async function testGenerateImage() {
  const node = selectedNode.value
  if (!node || node.type !== 'IMAGE_GENERATE') return
  const loaded = await loadImageModels()
  if (!loaded || !isImageModelAvailable(node.config.modelKey)) {
    showToast(imageModelsError.value || imageModelSelectionNotice.value || '请选择可用的生图模型', 'error')
    return
  }
  testingImage.value = true
  try {
    const res = await aiGenerateImages(buildImageGenerateTestPayload(node.config))
    const data = res?.data
    const images = data && typeof data === 'object' && !Array.isArray(data)
      ? (Array.isArray(data.images) ? data.images : Array.isArray(data.urls) ? data.urls : null)
      : null
    if (!Array.isArray(images) || !images.length) throw new Error('生图测试响应未返回任何图片')
    showToast(`测试生图成功，已返回 ${images.length} 张图片`, 'success')
  } catch (e) {
    showToast(friendlyError(e, '生图调用失败，请稍后重试'), 'error')
  } finally {
    testingImage.value = false
  }
}

function compressImage(file, maxSize = 512, quality = 0.8) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = e => {
      const img = new Image()
      img.onload = () => {
        let { width, height } = img
        if (width > height) {
          if (width > maxSize) { height = Math.round(height * maxSize / width); width = maxSize }
        } else {
          if (height > maxSize) { width = Math.round(width * maxSize / height); height = maxSize }
        }
        const canvas = document.createElement('canvas')
        canvas.width = width; canvas.height = height
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, width, height)
        resolve(canvas.toDataURL('image/jpeg', quality))
      }
      img.onerror = reject
      img.src = e.target.result
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function handleRefImageUpload(event) {
  const node = selectedNode.value
  if (!node || node.type !== 'IMAGE_GENERATE') return
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  if (!node.config.referenceImages) node.config.referenceImages = []
  const remaining = 9 - node.config.referenceImages.length
  const toAdd = files.slice(0, remaining)
  for (const file of toAdd) {
    if (!file.type.startsWith('image/')) continue
    try {
      const dataUrl = await compressImage(file)
      node.config.referenceImages.push(dataUrl)
    } catch (e) {
      console.warn('图片处理失败:', e)
    }
  }
  event.target.value = ''
}

function removeRefImage(idx) {
  const node = selectedNode.value
  if (!node?.config?.referenceImages) return
  node.config.referenceImages.splice(idx, 1)
}

function pickAddress(addr) {
  updateNodeAddress(addr)
  showNodeHistoryList.value = false
}

function normalizeAddressFields(raw) {
  return normalizePublishAddress(raw)
}

function getAddressMissingFields(address) {
  return getPublishAddressMissingFields(address)
}

async function ensureAddressReady(address, { title = '发布地址无效' } = {}) {
  const normalized = normalizeAddressFields(address)
  if (isPublishAddressComplete(normalized)) return normalized
  const missing = getAddressMissingFields(normalized)
  const message = [
    '当前发布地址缺少关键定位字段，继续执行会导致闲鱼发布失败。',
    `缺少字段：${missing.join('、')}`,
    '请在发布节点中重新选择完整的省、市、区。'
  ].join('\n')
  await globalConfirm.alert(title, message)
  return null
}

function mergeAddressIntoPublishNode(address) {
  const normalized = normalizeAddressFields(address)
  if (!normalized) return null
  const publishNode = nodes.value.find(n => n.type === 'PUBLISH')
  if (publishNode) {
    publishNode.config.address = normalized
    publishNode.config.addressText = normalized.poiName
  }
  return normalized
}

async function saveNormalizedPublishAddress(address) {
  const normalized = normalizeAddressFields(address)
  if (!isPublishAddressComplete(normalized)) return normalized
  await savePublishAddress({
    poiName: normalized.poiName,
    city: normalized.city,
    area: normalized.area,
    detail: normalized.detail,
    prov: normalized.prov,
    divisionId: normalized.divisionId,
    gps: normalized.gps,
    poiId: normalized.poiId,
  })
  return normalized
}

function updateNodeAddress(address) {
  const node = selectedNode.value
  if (!node) return
  const normalized = normalizeAddressFields(address)
  node.config.address = normalized
  node.config.addressText = normalized?.poiName || ''
  saveNormalizedPublishAddress(normalized).catch(() => {})
}

function toggleNodeHistoryList() {
  showNodeHistoryList.value = !showNodeHistoryList.value
  if (showNodeHistoryList.value && !historyAddresses.value.length) {
    loadHistoryAddresses()
  }
}

async function loadHistoryAddresses() {
  historyAddressError.value = ''
  try {
    const res = await getPublishAddressHistory()
    if (!Array.isArray(res?.data)) throw new Error('历史地址响应格式异常')
    historyAddresses.value = res.data
  } catch (e) {
    console.warn('[loadHistoryAddresses]', e)
    historyAddressError.value = '历史地址加载失败'
    historyAddresses.value = []
  }
}

async function loadImageModels() {
  imageModelsError.value = ''
  imageModelSelectionNotice.value = ''
  try {
    const res = await getOpportunityImageModels()
    availableImageModels.value = imageModelsOf(res)
    if (!availableImageModels.value.length) {
      imageModelsError.value = '暂无已启用且完成配置的生图模型'
      return false
    }

    const node = selectedNode.value
    if (node && node.type === 'IMAGE_GENERATE') {
      const currentKey = String(node.config.modelKey || '').trim()
      if (currentKey && !isImageModelAvailable(currentKey)) {
        node.config.modelKey = ''
        imageModelSelectionNotice.value = `原生图模型「${currentKey}」当前不可用，请重新选择。`
      } else if (!currentKey) {
        const preferred = availableImageModels.value.find(model => model.moduleKey === 'model-config-image-2')
          || availableImageModels.value[0]
        node.config.modelKey = preferred.moduleKey
      }
    }
    return true
  } catch (e) {
    console.warn('[loadImageModels]', e)
    imageModelsError.value = e?.message || '模型列表加载失败，请检查后台配置'
    availableImageModels.value = []
    return false
  }
}

// ===================== 工作流操作 =====================

async function loadAll() {
  // 使用 allSettled 确保单个请求失败不会阻塞其他请求的加载
  await Promise.allSettled([loadOverview(), loadWorkflows(), loadAccounts(), loadRecentRuns()])
}
async function loadOverview() {
  overviewLoadError.value = ''
  try {
    const data = (await workflowOverview())?.data
    const keys = ['workflowCount', 'enabledCount', 'todayExecutionCount', 'successRate']
    if (!data || typeof data !== 'object' || Array.isArray(data)
      || keys.some(key => typeof data[key] !== 'number' || !Number.isFinite(data[key]) || data[key] < 0)) {
      throw new Error('工作流统计响应格式异常')
    }
    overview.value = data
  } catch (loadError) {
    overview.value = {}
    overviewLoadError.value = `${loadError?.message || '工作流统计加载失败'}，相关指标显示为“—”。`
  }
}
function overviewValue(key, suffix = '') {
  const value = overview.value?.[key]
  return value === null || value === undefined || value === '' ? '—' : `${value}${suffix}`
}
async function loadWorkflows() {
  workflowsLoadError.value = ''
  workflowDetailError.value = ''
  try {
    const res = await listWorkflows({ keyword: keyword.value, status: statusFilter.value, current: 1, size: 50 })
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data) || !Array.isArray(res.data.records)) throw new Error('工作流列表响应格式异常')
    workflows.value = res.data.records
    // 列表已渲染，详情加载与列表解耦：失败不影响列表显示
    if (!selectedWorkflow.value && workflows.value[0]) {
      selectWorkflow(workflows.value[0].id).catch(() => {})
    }
  } catch (loadError) {
    workflows.value = []
    selectedWorkflow.value = null
    workflowsLoadError.value = loadError?.message || '请检查网络连接后重试。'
  }
}
async function selectWorkflow(id) {
  workflowDetailError.value = ''
  try {
    const res = await getWorkflow(id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || String(data.id ?? '') !== String(id)) throw new Error('工作流详情响应格式异常')
    if (!Array.isArray(data.nodes) || !Array.isArray(data.edges)) throw new Error('工作流详情缺少节点或连线数据')
    selectedWorkflow.value = data
    draft.value = { id: data.id, name: data.name, description: data.description || '', triggerType: data.triggerType || 'manual', config: data.config || {}, canvas: data.canvas || { zoom: 100 } }
    nodes.value = (data.nodes || []).map(n => {
      const nodeConfig = n.config || n.params || {}
      const nodeType = n.type || n.nodeType
      let mergedConfig = { ...defaultConfig(nodeType), ...nodeConfig }
      // 兼容老工作流：selectedAccountId (单值) → selectedAccountIds (数组)
      if (nodeType === 'TRIGGER') {
        if ((!mergedConfig.selectedAccountIds || mergedConfig.selectedAccountIds.length === 0) && mergedConfig.selectedAccountId != null) {
          mergedConfig.selectedAccountIds = [mergedConfig.selectedAccountId]
        }
        if (!mergedConfig.selectedAccountIds) mergedConfig.selectedAccountIds = []
        // 删除遗留单值字段，避免后端 resolveAccountIds 同时收集 selectedAccountIds + selectedAccountId
        // 导致已删除账号的残留 ID 被校验（pruneStaleAccountIds 也会二次清理）
        delete mergedConfig.selectedAccountId
      }
      if (nodeType === 'IMAGE_GENERATE') {
        mergedConfig = normalizeImageGenerateConfig(mergedConfig)
      }
      if (nodeType === 'PUBLISH') {
        const legacyAddress = mergedConfig.address || mergedConfig.location || mergedConfig.publishAddress ||
          (mergedConfig.addressText ? { poiName: mergedConfig.addressText, source: 'legacy' } : null)
        if (legacyAddress) mergedConfig.address = normalizeAddressFields(legacyAddress)
      }
      return {
        id: n.id || n.nodeKey,
        name: n.name || n.nodeName,
        type: nodeType,
        icon: iconFor(nodeType),
        desc: n.desc || '',
        x: n.x ?? n.positionX ?? 80,
        y: n.y ?? n.positionY ?? 80,
        config: mergedConfig,
        retry: !!(n.retry || n.retryEnabled),
        retryCount: n.retryCount || 0,
        retryIntervalSeconds: n.retryIntervalSeconds || 30
      }
    })
    edges.value = (data.edges || []).map(e => ({ source: e.source || e.sourceNodeKey, target: e.target || e.targetNodeKey, condition: e.condition || e.conditionExpr || '' }))
    selectedNodeId.value = nodes.value[0]?.id || ''
    pruneStaleAccountIds()
    await loadExecutions()
  } catch (loadError) {
    selectedWorkflow.value = null
    draft.value = { name: '', description: '', triggerType: 'manual', config: {}, canvas: { zoom: 100 } }
    nodes.value = []
    edges.value = []
    workflowDetailError.value = `${loadError?.message || '详情加载失败'}；未确认服务端配置前禁止保存或发布。`
  }
}
function setStatus(s) { statusFilter.value = s; selectedWorkflow.value = null; loadWorkflows() }
function newWorkflow() {
  workflowDetailError.value = ''
  selectedWorkflow.value = null
  draft.value = { name: '商品发布工作流', description: '自动完成商品搜索、改写、生图到发布的全流程', triggerType: 'manual', config: {}, canvas: { zoom: 100 } }
  nodes.value = [
    { id: uniqueId('trigger'), name: '手动触发', type: 'TRIGGER', icon: 'clock', desc: '初始化 WorkflowState', x: 60, y: 40, config: { selectedAccountIds: [], executeCount: 1 }, retry: false, retryCount: 0, retryIntervalSeconds: 30 },
    { id: uniqueId('fetch'), name: '商品获取', type: 'PRODUCT_FETCH', icon: 'product', desc: '关键词搜索获取商品', x: 60, y: 130, config: { sourceType: 'keyword', targetCount: 5, fetchMode: 'random', keywords: [], shopUrl: '' }, retry: true, retryCount: 3, retryIntervalSeconds: 30 },
    { id: uniqueId('filter'), name: '商品筛选', type: 'PRODUCT_FILTER', icon: 'data', desc: 'AI筛选符合要求的商品', x: 60, y: 220, config: { screenPrompt: '', enabled: true, onFilterFail: 'retry', maxRetries: 5 }, retry: true, retryCount: 3, retryIntervalSeconds: 30 },
    { id: uniqueId('polish'), name: '润色文案', type: 'PRODUCT_POLISH', icon: 'reply', desc: 'AI润色标题与文案', x: 60, y: 310, config: { similarity: 0.8 }, retry: false, retryCount: 0, retryIntervalSeconds: 30 },
    { id: uniqueId('image'), name: '生成图片', type: 'IMAGE_GENERATE', icon: 'image', desc: 'AI生成商品主图', x: 60, y: 400, config: defaultConfig('IMAGE_GENERATE'), retry: false, retryCount: 0, retryIntervalSeconds: 30 },
    { id: uniqueId('publish'), name: '发布商品', type: 'PUBLISH', icon: 'publish', desc: '发布到闲鱼', x: 60, y: 490, config: { publishIntervalSeconds: 30 }, retry: false, retryCount: 0, retryIntervalSeconds: 30 }
  ]
  edges.value = [
    { source: nodes.value[0].id, target: nodes.value[1].id, condition: '' },
    { source: nodes.value[1].id, target: nodes.value[2].id, condition: '' },
    { source: nodes.value[2].id, target: nodes.value[3].id, condition: '' },
    { source: nodes.value[3].id, target: nodes.value[4].id, condition: '' },
    { source: nodes.value[4].id, target: nodes.value[5].id, condition: '' }
  ]
  selectedNodeId.value = nodes.value[0].id
  executionDetail.value = null
  testResult.value = null
}
async function renameWorkflow(wf) {
  if (!wf?.id) return
  const input = await globalConfirm.prompt('修改工作流名称', '请输入新的工作流名称', wf.name || '')
  if (input === false) return  // 用户取消
  const newName = String(input || '').trim()
  if (!newName) { await globalConfirm.alert('名称不能为空', '请输入有效的工作流名称'); return }
  if (newName === wf.name) return  // 未改动
  try {
    await updateWorkflowDefinition(wf.id, { name: newName })
    // 同步刷新列表与概览；若重命名的是当前选中工作流，同步更新 draft
    await Promise.all([loadWorkflows(), loadOverview()])
    if (selectedWorkflow.value?.id === wf.id) {
      selectedWorkflow.value = { ...selectedWorkflow.value, name: newName }
      draft.value.name = newName
    }
  } catch (e) {
    await globalConfirm.alert('重命名失败', e?.message || e?.msg || '修改工作流名称时发生错误，请稍后重试')
  }
}
async function deleteWorkflow(wf) {
  if (!wf?.id) return
  if (!await confirmAction({
    title: `确认删除工作流${wf.name ? `「${wf.name}」` : ''}？`,
    description: '删除后该工作流的所有版本和执行记录将无法恢复，请确认不再需要。',
    dangerous: true
  })) return
  try {
    await deleteWorkflowDefinition(wf.id)
    // 若删除的是当前选中工作流，清空右侧编辑区，让 loadWorkflows 自动选第一个
    if (selectedWorkflow.value?.id === wf.id) {
      selectedWorkflow.value = null
      draft.value = { name: '', description: '', triggerType: 'manual', config: {}, canvas: { zoom: 100 } }
      nodes.value = []
      edges.value = []
      executionDetail.value = null
      testResult.value = null
    }
    await Promise.all([loadWorkflows(), loadOverview()])
  } catch (e) {
    await globalConfirm.alert('删除失败', e?.message || e?.msg || '删除工作流时发生错误，请稍后重试')
  }
}
async function saveDraft(force) {
  if (!await guardFeatureAction()) return
  if (workflowDetailError.value) return
  if (!force && saving.value) return draft.value.id
  const suppressValidationModal = extractingKeywords.value
  if (suppressValidationModal && !validation.value.valid) return null
  if (!validation.value.valid) { await globalConfirm.alert('校验失败', validation.value.message); return null }
  const publishNodeForCheck = nodes.value.find(n => n.type === 'PUBLISH')
  if (publishNodeForCheck && publishNodeForCheck.config?.enabled !== false) {
    const addr = normalizeAddressFields(publishNodeForCheck.config?.address)
    if (!addr?.poiName) {
      if (suppressValidationModal) return null
      await globalConfirm.alert('请配置发布地址', '请先在发布节点中选择完整的省、市、区后再保存或执行。')
      return null
    }
    if (!isPublishAddressComplete(addr)) {
      const missing = getAddressMissingFields(addr)
      // 旧地址可继续编辑、保存和回显，执行前会明确提示重新选择省市区。
      if (addr.source === 'address-dict') {
        if (suppressValidationModal) return null
        await globalConfirm.alert('发布地址字段不完整', `请选择完整的省、市、区。缺少字段：${missing.join('、')}。`)
        return null
      }
    }
  }
  saving.value = true
  try {
    const payload = toPayload()
    let res
    if (draft.value.id) {
      res = await updateWorkflowDefinition(draft.value.id, payload)
    } else {
      res = await createWorkflowDefinition(payload)
    }
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data) || !Number.isFinite(Number(res.data.id)) || Number(res.data.id) <= 0) {
      throw new Error('工作流保存响应缺少有效工作流编号')
    }
    await loadOverview()
    await selectWorkflow(res.data.id)
    lastSavedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    return res.data.id
  } catch (e) {
    const msg = e?.message || e?.msg || '保存工作流草稿时发生错误，请稍后重试'
    await globalConfirm.alert('保存失败', msg)
    return null
  } finally {
    saving.value = false
  }
}
async function publishCurrent() {
  if (workflowDetailError.value) return
  if (publishing.value) return
  if (!await ensureWorkflowImageModelsReady('发布')) return
  if (!await confirmAction({ title: '确认发布并启用当前工作流？', description: '发布后可能被定时任务或事件触发，请确认节点参数、发布间隔和失败重试设置正确。', dangerous: true })) return
  publishing.value = true
  try {
    const id = await saveDraft()
    if (!id) return
    const publishRes = await publishWorkflow(id)
    const published = publishRes?.data
    if (!published || typeof published !== 'object' || Array.isArray(published)
      || Number(published.id) !== Number(id) || published.status !== 'published' || published.enabled !== true) {
      throw new Error('服务端未确认工作流已发布并启用')
    }
    await loadWorkflows()
    await selectWorkflow(id)
  } finally {
    publishing.value = false
  }
}

// 格式化时间
function formatTime(t) {
  if (!t) return ''
  try { return new Date(t).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) } catch { return String(t) }
}

/**
 * 估算当前工作流执行所需消耗的通用模型 Token 总数。
 *
 * 估算规则：
 * - 商品数量：取 PRODUCT_FETCH 节点的 targetCount（默认 5）
 * - 单商品调用通用模型的次数：
 *   - PRODUCT_FILTER 启用 → 1 次/商品
 *   - PRODUCT_POLISH 启用 → 1 次/商品（按最坏情况 ×2 缓冲，含重试）
 *   - IMAGE_GENERATE → 生图模型，不计入通用模型预估
 * - 总调用次数 = 单商品调用次数 × 商品数量
 * - 总 Token = 总调用次数 × perCallTokens（默认 3）
 *
 * @returns {{ totalTokens: number, callCount: number, productCount: number, perCallTokens: number, perCallPrice: number, balance: number, details: string[] } | null}
 */
async function estimateWorkflowTokenUsage() {
  const { fetchTokenBalance } = await import('../utils/aiTokenGuard.js')
  const info = await fetchTokenBalance()
  const perCallTokens = info.perCallTokens || 3

  const fetchNode = nodes.value.find(n => n.type === 'PRODUCT_FETCH')
  const productCount = Math.max(1, Number(fetchNode?.config?.targetCount) || 5)

  const filterEnabled = nodes.value.some(n => n.type === 'PRODUCT_FILTER' && n.config?.enabled !== false)
  const polishEnabled = nodes.value.some(n => n.type === 'PRODUCT_POLISH' && n.config?.enabled !== false)

  const callsPerProduct =
    (filterEnabled ? 1 : 0) +
    (polishEnabled ? 2 : 0) // 含重试缓冲 ×2

  const details = []
  if (filterEnabled) details.push(`商品筛选：1 次/商品`)
  if (polishEnabled) details.push(`商品润色：1 次/商品（含重试缓冲按 2 次预估）`)

  if (callsPerProduct === 0) {
    return {
      totalTokens: 0,
      callCount: 0,
      productCount,
      perCallTokens,
      perCallPrice: info.perCallPrice,
      balance: info.balance,
      details,
    }
  }

  const callCount = callsPerProduct * productCount
  const totalTokens = callCount * perCallTokens
  return {
    totalTokens,
    callCount,
    productCount,
    perCallTokens,
    perCallPrice: info.perCallPrice,
    balance: info.balance,
    details,
  }
}

/**
 * 工作流运行前的 Token 余额预估与弹窗确认。
 * 当余额不足以支撑本次批量调用时，弹窗提示用户充值。
 * @returns {Promise<boolean>} true 表示可以继续运行；false 表示余额不足已拦截
 */
async function preflightWorkflowTokenBalance() {
  const estimate = await estimateWorkflowTokenUsage()
  if (!estimate) return true
  if (estimate.totalTokens <= 0) return true // 无通用模型调用节点

  const { balance, totalTokens, callCount, productCount, perCallTokens, details } = estimate
  if (balance >= totalTokens) return true

  const deficit = totalTokens - balance
  const detailLines = details.length
    ? `\n\n调用明细：\n${details.map(d => `• ${d}`).join('\n')}`
    : ''
  const message =
    `本次工作流预计需要消耗 ${totalTokens} Token（${callCount} 次调用 × ${perCallTokens} Token/次，商品数 ${productCount}）。` +
    `\n当前 Token 余额：${balance}` +
    `\n不足：${deficit} Token` +
    `${detailLines}` +
    `\n\n请前往「个人中心 → Token 充值」补充余额后再次运行。`

  await globalConfirm.alert('Token 余额不足', message)
  // 自动弹出充值 modal
  if (typeof window !== 'undefined' && window.dispatchEvent) {
    window.dispatchEvent(new CustomEvent('xya-open-payment', {
      detail: {
        source: 'workflow_preflight',
        reason: 'insufficient_balance',
        requiredTokens: totalTokens,
        balance,
        perCallTokens,
      }
    }))
  }
  return false
}

// ===================== 画布操作 =====================
async function runCurrent() {
  if (!await guardFeatureAction()) return
  if (workflowDetailError.value) return
  if (running.value) return
  if (!await ensureWorkflowImageModelsReady('运行')) return
  if (!await confirmAction({ title: '确认运行一次测试？', description: '运行测试会调用当前工作流节点，可能消耗 AI 或采集额度。' })) return

  // 工作流批量调用前的 Token 预估价：估算总调用次数 × 单次扣费数，余额不足弹窗提示
  if (!await preflightWorkflowTokenBalance()) return

  // 工作流地址预检：优先使用节点地址，否则从历史地址中选择或通过省市区联动新增。
  const publishNode = nodes.value.find(n => n.type === 'PUBLISH')
  let address = null
  if (publishNode?.config?.address?.poiName) {
    address = { ...publishNode.config.address }
  }
  if (!address) {
    address = await preflightPublishAddress()
  }
  if (!address) return
  address = await ensureAddressReady(address, { title: '运行前地址校验失败' })
  if (!address) return
  mergeAddressIntoPublishNode(address)
  saveNormalizedPublishAddress(address).catch(() => {})

  // ★ 运行前显式清理已删除账号的残留 ID，确保 saveDraft 保存的是干净配置
  // 账号列表未加载时先同步拉取一次，否则 pruneStaleAccountIds 会因 accounts.value 为空而跳过清理
  if (!accounts.value.length) {
    await loadAccounts()
  }
  pruneStaleAccountIds()

  running.value = true
  try {
    executionDetail.value = null
    testResult.value = null
    const id = await saveDraft(true)
    if (!id) return
    const res = await executeWorkflowDefinition(id, {
      triggerMode: 'manual',
      keywords: findNodeKeywords(),
      isTest: true,
      // ★ 把预检得到的地址传给后端，避免 IMAGE_GENERATE 节点再次查找
      addressPayload: address,
    })
    const execution = res?.data
    if (!execution || typeof execution !== 'object' || Array.isArray(execution) || !Number.isFinite(Number(execution.id))) {
      throw new Error('工作流执行响应缺少有效执行状态')
    }
    // 执行记录已创建：无论是 running/queued 还是 failed（如自动化服务暂时不可用），
    // 都展示执行详情，让用户看到具体错误信息而非笼统的报错。
    executionDetail.value = execution
    upsertExecutionRow(execution)
    loadOverview().catch(() => {})
    loadExecutions().catch(() => {})
    loadRecentRuns().catch(() => {})
  } catch (e) {
    const invalidAccounts = e?.data?.invalidAccounts
    if (Array.isArray(invalidAccounts) && invalidAccounts.length) {
      const lines = invalidAccounts.map(item => `- ${item.nickname || `账号#${item.accountId}`}${item.accountId ? `（ID: ${item.accountId}）` : ''}：${item.reason || '登录失效'}`)
      await loadAccounts()
      await globalConfirm.alert('运行前账号校验失败', lines.join('\n'))
      return
    }
    await globalConfirm.alert('运行失败', friendlyError(e, '工作流运行失败，请稍后重试'))
  } finally {
    running.value = false
  }
}

/**
 * ★ 继续执行已失败的工作流：复用原 execution_id，跳过已成功节点，从失败节点继续执行。
 * 后端会读取 workflow_state_variable 表的 state、workflow_timeline 的 node_success 事件，
 * 自动跳过已成功的节点，从失败节点开始重新执行（如生图+发布节点）。
 */
async function continueExecution() {
  const detail = executionDetail.value
  if (!detail?.id) return
  if (detail.status === 'running') {
    await globalConfirm.alert('无法继续', '工作流正在运行中，请等待执行完成或终止后再试')
    return
  }
  if (!await confirmAction({ title: '继续执行？', description: '将跳过已成功的节点，从失败节点开始继续执行。已获取的商品、润色结果和封面图将被复用，仅对失败的发布等环节进行重试。' })) return
  continuing.value = true
  try {
    const publishNode = nodes.value.find(n => n.type === 'PUBLISH')
    if (publishNode?.config?.address?.poiName) {
      const validAddress = await ensureAddressReady(publishNode.config.address, { title: '继续执行前地址校验失败' })
      if (!validAddress) return
      mergeAddressIntoPublishNode(validAddress)
      saveNormalizedPublishAddress(validAddress).catch(() => {})
      if (draft.value.id) {
        const id = await saveDraft(true)
        if (!id) return
      }
    }
    const res = await continueWorkflowExecution(detail.id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('继续执行响应格式异常')
    if (data.ok === false) {
      // ★ 预检失败：根据 reason 给出针对性提示
      //   - ADDRESS_INVALID：地址失效，提示去地址管理修复
      //   - ACCOUNT_LOGIN_INVALID：账号掉线，列出失效账号提示重登
      const reason = data.reason || ''
      let title = '继续执行失败'
      let msg = data.message || '未知错误'
      if (reason === 'ADDRESS_INVALID') {
        title = '地址校验失败'
        const missing = Array.isArray(data.missingFields) && data.missingFields.length
          ? `缺失字段：${data.missingFields.join('、')}` : ''
        msg = `${data.message}\n\n请在发布节点中重新选择完整的省、市、区后再继续执行。${missing ? '\n' + missing : ''}`
      } else if (reason === 'ACCOUNT_LOGIN_INVALID') {
        title = '账号登录校验失败'
        const invalid = Array.isArray(data.invalidAccounts) && data.invalidAccounts.length
          ? data.invalidAccounts.map(a => `• ${a.nickname || ('账号#' + a.accountId)}（${a.code || ''}）：${a.reason || ''}`).join('\n')
          : ''
        msg = `${data.message}\n\n请到「账号管理」页面重新登录以下账号后再点继续执行：\n${invalid}`
      }
      await globalConfirm.alert(title, msg)
      return
    }
    if (data.status !== 'running' || Number(data.executionId) !== Number(detail.id)) {
      throw new Error('服务端未确认当前工作流已继续执行')
    }
    // 后端已开始后台执行，立即把状态切回 running 并启动轮询
    executionDetail.value = { ...detail, status: 'running', progress: 0, errorMessage: '' }
    upsertExecutionRow(executionDetail.value)
    loadExecutions().catch(() => {})
    loadRecentRuns().catch(() => {})
    loadOverview().catch(() => {})
  } catch (e) {
    await globalConfirm.alert('继续执行失败', e.message || '未知错误')
  } finally {
    continuing.value = false
  }
}

/**
 * ★ 终止运行中的工作流：调用后端 terminate 端点，将状态置为 terminated。
 * 仅 status === 'running' 时允许操作。
 */
async function terminateExecution() {
  if (!await guardFeatureAction()) return
  const detail = executionDetail.value
  if (!detail?.id) return
  if (detail.status !== 'running') {
    await globalConfirm.alert('无法终止', '当前工作流不在运行中')
    return
  }
  if (!await confirmAction({ title: '终止执行？', description: '将立即终止当前工作流执行。已获取的商品与已发布的商品不会回滚，终止后无法恢复运行；如需恢复可通过"继续执行"从失败节点恢复。' })) return
  terminating.value = true
  try {
    const res = await terminateWorkflowExecution(detail.id, { reason: '用户手动终止' })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('终止执行响应格式异常')
    if (data.ok === false) {
      await globalConfirm.alert('终止失败', data.message || '未知错误')
      return
    }
    if (data.status !== 'terminated') throw new Error('服务端未确认工作流已终止')
    // 立即把状态切到 terminated，并停止轮询
    executionDetail.value = { ...detail, status: 'terminated' }
    upsertExecutionRow(executionDetail.value)
    stopExecPolling()
    await Promise.allSettled([loadExecutions(), loadRecentRuns(), loadOverview()])
  } catch (e) {
    await globalConfirm.alert('终止失败', e.message || '未知错误')
  } finally {
    terminating.value = false
  }
}

/**
 * 工作流执行前的地址预检：三级查找
 *   1) 后端 GET /publish-address/history（已合并 xianyu_goods 表商品地址 + user_publish_address 表常用地址）
 *   2) 列表非空 → 返回第一个（最常用）
 *   3) 列表为空 → 弹出 WorkflowAddressPicker 让用户搜索选择，保存后返回
 *   4) 用户取消 → 返回 null
 */
async function preflightPublishAddress() {
  // 1) 拉取历史常用地址（后端合并查商品表+地址表）
  let history = []
  try {
    const res = await getPublishAddressHistory()
    if (!Array.isArray(res?.data)) throw new Error('发布地址历史响应格式异常')
    history = res.data
  } catch (e) {
    console.warn('[preflightAddress] 拉取历史地址失败', e)
  }
  if (history.length > 0) {
    // 已有常用地址，直接用第一个（按 use_count DESC 排序）
    const top = history
      .map(item => normalizeAddressFields(item))
      .find(item => item && getAddressMissingFields(item).length === 0)
    if (top) return top
  }
  // 2) 没有完整历史地址时，通过省市区联动选择；旧记录仍保留在弹框中供查看。
  wfAddressHistory.value = history
  wfAddressPickerVisible.value = true
  return new Promise(resolve => {
    wfAddressResolver = resolve
  })
}

/** 用户在 WorkflowAddressPicker 中确认选择 */
async function onWfAddressConfirm(addr) {
  wfAddressSaving.value = true
  try {
    // 保存到 user_publish_address 表，下次预检可直接命中
    await saveNormalizedPublishAddress(addr)
    const normalized = mergeAddressIntoPublishNode(addr)
    wfAddressPickerVisible.value = false
    if (wfAddressResolver) {
      wfAddressResolver(normalized)
      wfAddressResolver = null
    }
  } catch (e) {
    await globalConfirm.alert('保存地址失败', e.message || '未知错误')
  } finally {
    wfAddressSaving.value = false
  }
}

/** 用户取消地址选择 */
function onWfAddressCancel() {
  wfAddressPickerVisible.value = false
  if (wfAddressResolver) {
    wfAddressResolver(null)
    wfAddressResolver = null
  }
}
function toPayload() {
  return {
    name: draft.value.name,
    description: draft.value.description,
    triggerType: draft.value.triggerType,
    config: JSON.parse(JSON.stringify(draft.value.config || {})),
    canvas: { zoom: zoom.value },
    nodes: nodes.value.map(n => {
      const rawConfig = JSON.parse(JSON.stringify(n.config || {}))
      const config = n.type === 'IMAGE_GENERATE' ? normalizeImageGenerateConfig(rawConfig) : rawConfig
      return {
        id: n.id,
        nodeKey: n.id,
        name: n.name,
        nodeName: n.name,
        type: n.type,
        nodeType: n.type,
        x: n.x,
        y: n.y,
        config,
        retry: !!n.retry,
        retryEnabled: !!n.retry,
        retryCount: n.retryCount || 0,
        retryIntervalSeconds: n.retryIntervalSeconds || 30
      }
    }),
    edges: edges.value.map(e => ({
      source: e.source,
      target: e.target,
      sourceNodeKey: e.source,
      targetNodeKey: e.target,
      condition: e.condition || ''
    }))
  }
}
async function loadExecutions() {
  executionsLoadError.value = ''
  try {
    const params = selectedWorkflow.value?.id ? { workflowId: selectedWorkflow.value.id, current: 1, size: 8 } : { current: 1, size: 8 }
    const res = await listWorkflowExecutions(params)
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data) || !Array.isArray(res.data.records)) throw new Error('工作流执行列表响应格式异常')
    executions.value = res.data.records
  } catch (loadError) {
    executions.value = []
    executionsLoadError.value = loadError?.message || '请检查网络连接后重试。'
  }
}
async function loadRecentRuns() {
  recentRunsLoadError.value = ''
  try {
    const res = await getRecentRuns({ limit: 5 })
    if (!Array.isArray(res?.data)) throw new Error('最近运行记录响应格式异常')
    recentRuns.value = res.data
  } catch (loadError) {
    recentRuns.value = []
    recentRunsLoadError.value = loadError?.message || '请检查网络连接后重试。'
  }
}
async function openExecution(id) {
  try {
    const res = await getWorkflowExecution(id)
    executionDetail.value = executionDetailOf(res, id)
    configTab.value = 'execution'
  } catch (e) {
    executionDetail.value = null
    await globalConfirm.alert('执行详情加载失败', e?.message || '请稍后重试')
  }
}
async function openExecutionLogs(id) {
  try {
    const res = await getExecutionLogs(id)
    if (!Array.isArray(res?.data)) throw new Error('执行日志响应格式异常')
    executionDetail.value = { ...(executionDetail.value || {}), logs_data: res.data }
    configTab.value = 'execution'
    execTab.value = 'timeline'
  } catch (e) {
    await globalConfirm.alert('查看日志失败', e.message || '未知错误')
  }
}
function addNode(t) {
  const base = nodes.value[nodes.value.length - 1]
  const id = uniqueId(t.type)
  nodes.value.push({ id, name: t.label, type: t.type, icon: t.icon, desc: '点击右侧编辑参数', x: Math.min((base?.x || 60) + 190, canvasWidth - 190), y: base?.y || 120, config: defaultConfig(t.type), retry: false, retryCount: 1, retryIntervalSeconds: 30 })
  if (base) edges.value.push({ source: base.id, target: id, condition: '' })
  selectedNodeId.value = id
}
async function removeNode(id) {
  if (nodes.value.length <= 1) return await globalConfirm.alert('提示', '至少保留一个节点')
  const node = nodes.value.find(n => n.id === id)
  if (!await confirmAction({ title: `确认删除节点${node?.name ? `「${node.name}」` : ''}？`, description: '删除节点会同步删除相关连线。' })) return
  nodes.value = nodes.value.filter(n => n.id !== id)
  edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
  selectedNodeId.value = nodes.value[0]?.id || ''
}
function selectNode(id) {
  if (edgeSource.value && edgeSource.value !== id) {
    if (!edges.value.some(e => e.source === edgeSource.value && e.target === id)) edges.value.push({ source: edgeSource.value, target: id, condition: '' })
    edgeSource.value = ''
  }
  selectedNodeId.value = id
  configTab.value = 'node'
  // 选中生图节点时，加载可用生图模型列表
  const node = nodes.value.find(n => n.id === id)
  if (node && node.type === 'IMAGE_GENERATE') {
    loadImageModels()
  }
  // 当选中发布节点时，加载历史地址。
  const publishNode = nodes.value.find(n => n.id === id)
  if (publishNode && publishNode.type === 'PUBLISH') {
    loadHistoryAddresses()
    showNodeHistoryList.value = false
  }
}
function pickEdgeSource(id) { edgeSource.value = id; selectedNodeId.value = id; configTab.value = 'node' }
function zoomIn() { zoom.value = Math.min(zoomMax, zoom.value + zoomStep) }
function zoomOut() { zoom.value = Math.max(zoomMin, zoom.value - zoomStep) }
function clearEdgePick() { edgeSource.value = '' }
function resetZoom() { zoom.value = 100 }
function startDrag(e, node) {
  const rect = canvasEl.value?.getBoundingClientRect(); if (!rect) return
  drag.value = { id: node.id, dx: e.clientX - rect.left - node.x, dy: e.clientY - rect.top - node.y }
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}
function onDrag(e) {
  if (!drag.value || !canvasEl.value) return
  const rect = canvasEl.value.getBoundingClientRect()
  const n = nodes.value.find(x => x.id === drag.value.id); if (!n) return
  n.x = Math.round(Math.max(12, Math.min(canvasWidth - 170, e.clientX - rect.left - drag.value.dx)))
  n.y = Math.round(Math.max(18, Math.min(canvasHeight - 88, e.clientY - rect.top - drag.value.dy)))
}
function stopDrag() { drag.value = null; window.removeEventListener('mousemove', onDrag); window.removeEventListener('mouseup', stopDrag) }
function linePath(e) {
  const s = nodes.value.find(n => n.id === e.source)
  const t = nodes.value.find(n => n.id === e.target)
  if (!s || !t) return ''
  const sa = edgeAnchor(s)
  const ta = { x: t.x, y: t.y + 55 }
  const span = Math.max(120, Math.abs(ta.x - sa.x) * 0.45)
  const bend = ta.x >= sa.x ? span : -span
  const c1x = sa.x + bend
  const c2x = ta.x - bend
  return `M${sa.x} ${sa.y} C${c1x} ${sa.y}, ${c2x} ${ta.y}, ${ta.x} ${ta.y}`
}
function edgeKey(e) { return `${e.source}-${e.target}-${e.condition || ''}` }
function edgeAnchor(node) { return { x: node.x + 178, y: node.y + 55 } }
function validateGraph(ns, es) {
  if (!ns.length) return { valid: false, message: '至少需要一个节点' }
  const keys = new Set(ns.map(n => n.id))
  if (keys.size !== ns.length) return { valid: false, message: '存在重复节点ID' }
  const triggerNodes = ns.filter(n => n.type === 'TRIGGER')
  if (triggerNodes.length !== 1) return { valid: false, message: '必须有且只有一个触发节点' }
  const terminalTypes = new Set(['PUBLISH', 'END', 'OUTPUT', 'NOTIFY'])
  if (!ns.some(n => terminalTypes.has(n.type))) return { valid: false, message: '至少需要一个发布/结束类终态节点' }

  const indeg = Object.fromEntries([...keys].map(k => [k, 0]))
  const outdeg = Object.fromEntries([...keys].map(k => [k, 0]))
  const graph = Object.fromEntries([...keys].map(k => [k, []]))
  for (const e of es) {
    if (!keys.has(e.source) || !keys.has(e.target)) return { valid: false, message: '连线引用不存在节点' }
    if (e.source === e.target) return { valid: false, message: '节点不能连接到自身' }
    graph[e.source].push(e.target)
    indeg[e.target]++
    outdeg[e.source]++
  }
  for (const n of ns) {
    if (n.type !== 'TRIGGER' && indeg[n.id] === 0) return { valid: false, message: `节点「${n.name}」不可达，请从触发节点连线` }
    if (!terminalTypes.has(n.type) && outdeg[n.id] === 0) return { valid: false, message: `节点「${n.name}」缺少后续连线` }
    const configMsg = validateNodeConfig(n)
    if (configMsg) return { valid: false, message: `节点「${n.name}」配置不完整：${configMsg}` }
  }
  const q = Object.keys(indeg).filter(k => indeg[k] === 0); let visited = 0
  const indegForTopo = { ...indeg }
  while (q.length) { const k = q.shift(); visited++; graph[k].forEach(n => { indegForTopo[n]--; if (indegForTopo[n] === 0) q.push(n) }) }
  if (visited !== ns.length) return { valid: false, message: '存在循环依赖' }

  const reachable = new Set()
  const stack = [triggerNodes[0].id]
  while (stack.length) {
    const current = stack.pop()
    if (reachable.has(current)) continue
    reachable.add(current)
    graph[current].forEach(next => stack.push(next))
  }
  if (reachable.size !== ns.length) return { valid: false, message: '存在未从触发节点可达的孤立节点' }
  return { valid: true, message: `校验通过：${ns.length} 节点 / ${es.length} 连线` }
}
function positiveNumber(value) { return Number.isFinite(Number(value)) && Number(value) > 0 }
function validateNodeConfig(node) {
  const cfg = node.config || {}
  if (node.type === 'PRODUCT_FETCH') {
    if (cfg.sourceType === 'shop') {
      if (!cfg.shopUrl || !cfg.shopUrl.trim()) return '店铺链接不能为空'
    } else {
      if (!positiveNumber(cfg.targetCount)) return 'targetCount 必须大于0'
    }
  }
  if (node.type === 'TRIGGER' && (!cfg.selectedAccountIds || cfg.selectedAccountIds.length === 0)) return '请至少选择一个发布账号'
  if (node.type === 'IMAGE_GENERATE' && !positiveNumber(cfg.imageCount)) return 'imageCount 必须大于0'
  if (node.type === 'PRODUCT_POLISH' && (cfg.similarity == null || Number(cfg.similarity) < 0 || Number(cfg.similarity) > 1)) return 'similarity 必须在0到1之间'
  if (node.type === 'PUBLISH' && !positiveNumber(cfg.publishIntervalSeconds)) return 'publishIntervalSeconds 必须大于0'
  return ''
}
function defaultConfig(type) {
  const map = {
    PRODUCT_FETCH: { sourceType: 'keyword', targetCount: 5, fetchMode: 'random', keywords: [], shopUrl: '', enabled: true },
    PRODUCT_FILTER: { screenPrompt: '', enabled: true, onFilterFail: 'retry', maxRetries: 5 },
    IMAGE_GENERATE: { imageCount: 1, imageSize: '1024x1024', imagePrompt: '', customImagePrompt: '', promptMode: 'default', modelKey: '', enabled: true, referenceImages: [], parallelCount: 3 },
    PRODUCT_POLISH: { similarity: 0.8, style: '', customPrompt: '', enabled: true },
    PUBLISH: { publishIntervalSeconds: 30, category: '', addressText: '', address: {}, priceStrategy: 'keep', enabled: true },
    TRIGGER: { selectedAccountIds: [], executeCount: 1 }
  }
  return map[type] || {}
}
function iconFor(type) { return nodeTypes.find(t => t.type === type)?.icon || 'workflow' }
function typeLabel(type) { return nodeTypes.find(t => t.type === type)?.label || type }
function uniqueId(prefix) { return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}` }
function statusText(s) { return s === 'published' ? '已发布' : s === 'disabled' ? '已停用' : s === 'draft' ? '草稿' : '状态未知' }
function execStatusText(s) { return ({ success: '成功', failed: '失败', running: '运行中', queued: '排队中', partial_success: '部分成功', terminated: '已终止' })[s] || s || '-' }
function formatDuration(ms) { if (ms === null || ms === undefined) return '—'; if (ms < 1000) return '小于1秒'; const sec = Math.round(ms / 1000); if (sec < 60) return sec + '秒'; return Math.round(sec / 60) + '分钟' }

function formatDateTime(value) {
  if (!value) return '-'
  const s = String(value)
  return s.replace('T', ' ').replace(/\.\d+$/, '').slice(0, 19)
}
function computedDurationMs(row) {
  if (row && row.durationMs && row.durationMs > 0) return row.durationMs
  if (row && row.startedTime && row.finishedTime) {
    const start = new Date(row.startedTime).getTime()
    const end = new Date(row.finishedTime).getTime()
    if (!isNaN(start) && !isNaN(end) && end > start) return end - start
  }
  return 0
}
function levelClass(lvl) {
  const map = { INFO: 'info', WARN: 'warn', WARNING: 'warn', ERROR: 'error', DEBUG: 'debug' }
  return map[lvl] || 'info'
}
function findNodeKeywords() { return nodes.value.find(n => n.type === 'PRODUCT_FETCH')?.config?.keywords || [] }
async function loadAccounts() {
  accountsLoadError.value = ''
  try {
    const res = await getLiteAccounts({ current: 1, size: 100 })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    pruneStaleAccountIds()
  } catch (loadError) {
    accounts.value = []
    accountsLoadError.value = loadError?.message || '账号列表加载失败，当前不能为触发器选择发布账号。'
  }
}
function onHeaderAction(e) {
  const action = e.detail
  if (action === 'workflow-new') newWorkflow()
  if (action === 'workflow-save') saveDraft()
  if (action === 'workflow-run') { runCurrent() }
  if (action === 'workflow-publish') publishCurrent()
}

let resizeObserver = null
function initResizeObserver() {
  if (!canvasEl.value) return
  resizeObserver = new ResizeObserver(entries => {
    for (const entry of entries) { containerWidth.value = entry.contentRect.width }
  })
  resizeObserver.observe(canvasEl.value)
}
function destroyResizeObserver() {
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
}

onMounted(() => { window.addEventListener('xya-header-action', onHeaderAction); loadAll(); initResizeObserver() })
onBeforeUnmount(() => { stopDrag(); window.removeEventListener('xya-header-action', onHeaderAction); destroyResizeObserver(); stopExecPolling() })
</script>

<style scoped>
/* ========== 基础布局 ========== */
.workflow-shell{display:grid;grid-template-columns:320px minmax(0,1fr) 390px;gap:18px;align-items:start}
.workflow-list-panel{position:sticky;top:12px}
.workflow-search{display:flex;gap:8px;margin-bottom:12px}
.workflow-tabs{display:flex;gap:8px;margin-bottom:12px}
.workflow-tabs button{border:1px solid #e4ebf5;background:#fff;border-radius:999px;padding:7px 13px;color:#667085}
.workflow-tabs button.active{background:#eef6ff;color:#0d6bff;border-color:#bcd8ff}
.workflow-list{display:flex;flex-direction:column;gap:10px;margin-bottom:14px}
.workflow-list-item{display:grid;grid-template-columns:38px 1fr auto;gap:10px;align-items:center;border:1px solid #eaf0f8;background:#fff;border-radius:14px;padding:12px;text-align:left;cursor:pointer;position:relative}
.workflow-list-item.active{border-color:#0d6bff;background:#f7fbff;box-shadow:0 8px 18px rgba(13,107,255,.08)}
.workflow-list-item b{display:block;color:#16213e}
.workflow-list-item em{display:block;font-style:normal;color:#748098;font-size:12px;margin:4px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.workflow-list-item small{color:#98a2b3}
.workflow-item-icon{width:38px;height:38px;border-radius:12px;background:#edf5ff;color:#0d6bff;display:flex;align-items:center;justify-content:center}
.workflow-item-body{min-width:0}
.workflow-item-actions{display:flex;align-items:center;gap:6px}
.workflow-item-buttons{display:flex;gap:4px;opacity:0;transition:opacity .15s}
.workflow-list-item:hover .workflow-item-buttons,.workflow-list-item.active .workflow-item-buttons{opacity:1}
.workflow-item-btn{width:24px;height:24px;border:1px solid #e4ebf5;background:#fff;border-radius:6px;color:#667085;font-size:12px;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;transition:all .15s}
.workflow-item-btn:hover{border-color:#0d6bff;color:#0d6bff;background:#f7fbff}
.workflow-item-btn.danger:hover{border-color:#dc2626;color:#dc2626;background:#fef2f2}
.full{width:100%}

/* ========== 画布操作栏 ========== */
.workflow-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.save-time{font-size:12px;color:#98a2b3;white-space:nowrap}

/* ========== 执行日志面板 ========== */
.execution-log-panel{margin-top:16px;border:1px solid #dce8f7!important}
.execution-log-panel :deep(.card-header){background:linear-gradient(135deg,#f8fbff,#f2f7ff)}
.section-icon{font-size:16px;margin-right:6px}
.log-badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:700;margin-left:8px;vertical-align:middle}
.running-badge{background:#eff6ff;color:#0d6bff;border:1px solid #bfdbfe}
.success-badge{background:#ecfdf5;color:#059669;border:1px solid #a7f3d0}
.failed-badge{background:#fef2f2;color:#dc2626;border:1px solid #fecaca}

/* 执行概览 */
.exec-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:12px 0;margin-bottom:12px;border-bottom:1px solid #eaf0f8}
.exec-summary-item{text-align:center}
.exec-summary-item span{display:block;color:#98a2b3;font-size:12px;margin-bottom:4px}
.exec-summary-item b{font-size:15px;color:#16213e}

/* 日志时间线 */
.log-timeline{display:flex;flex-direction:column;gap:8px;max-height:500px;overflow-y:auto}
.log-entry{display:flex;gap:12px;padding:10px 12px;border-radius:12px;border:1px solid #eaf0f8;background:#fafcff;transition:all .15s}
.log-entry:hover{background:#f5f9ff;border-color:#d4e4ff}
.log-entry-icon{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-top:2px}
.log-success .log-entry-icon{background:#ecfdf5;color:#16bf78}
.log-error .log-entry-icon{background:#fef2f2;color:#ef4444}
.log-warn .log-entry-icon{background:#fffbeb;color:#f59e0b}
.log-info .log-entry-icon{background:#eff6ff;color:#0d6bff}
.log-entry-body{flex:1;min-width:0}
.log-entry-header{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px}
.log-entry-header b{font-size:14px;color:#16213e}
.log-entry-type{font-size:11px;color:#98a2b3;background:#f2f6fc;padding:1px 8px;border-radius:999px}
.log-entry-duration{font-size:11px;color:#667085;background:#f2f6fc;padding:1px 8px;border-radius:999px}
.log-entry-time{font-size:11px;color:#b0bccf;margin-left:auto}
.log-entry-message{font-size:13px;color:#667085;line-height:1.5}
.log-entry-message.is-error{color:#dc2626;font-weight:600}
.log-entry-detail{margin-top:6px}
.log-entry-detail pre{background:#f3f5f7;border-radius:8px;padding:8px;font-size:11px;max-height:120px;overflow:auto;margin:0;color:#374151}

/* 原始结果切换 */
.log-raw-toggle{padding:10px 0;text-align:center;color:#0d6bff;font-size:13px;cursor:pointer;user-select:none;border-top:1px solid #eaf0f8;margin-top:12px}
.log-raw-toggle:hover{color:#1a4fff}
.mock-json{background:#0e1726;color:#dbeafe;border-radius:12px;padding:12px;overflow:auto;max-height:300px;font-size:12px}

/* ========== 高级模式：节点编辑器 ========== */
.workflow-editor-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:16px}
.title-input{border:0;border-bottom:1px solid #dce7f5;font-size:22px;font-weight:800;color:#15223a;width:420px;max-width:100%;height:38px}
.workflow-editor-head p{margin:8px 0 0;color:#738096}
.workflow-canvas-wrap{display:grid;grid-template-columns:122px minmax(0,1fr);gap:12px}
.node-palette{display:flex;flex-direction:column;gap:8px}
.node-palette button{height:44px;border:1px solid #e5edf7;background:#fff;border-radius:11px;display:flex;align-items:center;gap:8px;padding:0 10px;color:#31415f;cursor:pointer}
.node-palette button:hover{background:#f5f9ff;border-color:#0d6bff;color:#0d6bff}
.workflow-canvas{height:520px;position:relative;background:linear-gradient(180deg,#f8fbff 0%,#f2f7ff 100%);border:1px solid #dce8f7;border-radius:18px;overflow:auto;box-shadow:inset 0 1px 0 rgba(255,255,255,.92)}
.workflow-canvas-inner{position:relative;width:1060px;height:520px;transform-origin:0 0}
.workflow-canvas::before{content:'';position:absolute;inset:0;background-image:linear-gradient(rgba(13,107,255,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(13,107,255,.07) 1px,transparent 1px);background-size:28px 28px;pointer-events:none}
.workflow-lines{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
.workflow-lines path{fill:none;stroke:#4f8cff;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 3px 8px rgba(13,107,255,.18));opacity:.92}
.workflow-lines path.active{stroke:#0d6bff;stroke-width:3.5;opacity:1}
.workflow-lines path.preview{stroke:#7ca8ff;stroke-dasharray:8 6;opacity:.55}
.workflow-node{position:absolute;z-index:2;width:178px;min-height:110px;padding:12px 12px 14px;border-radius:16px;border:1px solid #d8e4f3;background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(248,251,255,.94));box-shadow:0 12px 30px rgba(22,39,73,.08),0 1px 0 rgba(255,255,255,.9) inset;cursor:grab;user-select:none;backdrop-filter:blur(6px)}
.workflow-node::before{content:'';position:absolute;left:0;top:14px;bottom:14px;width:4px;border-radius:999px;background:linear-gradient(180deg,#5aa4ff,#0d6bff);opacity:.9}
.workflow-node:hover{box-shadow:0 16px 34px rgba(22,39,73,.12),0 1px 0 rgba(255,255,255,.9) inset;transform:translateY(-1px)}
.workflow-node.selected{border-color:#0d6bff;box-shadow:0 0 0 3px rgba(13,107,255,.14),0 16px 34px rgba(13,107,255,.16)}
.workflow-node.source{border-color:#33b17a;box-shadow:0 0 0 3px rgba(51,177,122,.16),0 16px 34px rgba(51,177,122,.14)}
.node-buttons{display:flex;gap:8px;justify-content:flex-end;margin-top:10px;position:relative;z-index:3}
.node-buttons button{height:28px;min-width:28px;padding:0 10px;border:1px solid #d9e4f3;background:#fff;border-radius:999px;color:#5e6c84;cursor:pointer}
.node-buttons button:hover{border-color:#0d6bff;color:#0d6bff;box-shadow:0 8px 18px rgba(13,107,255,.12)}
.workflow-node b,.workflow-node em,.workflow-node small{display:block;margin-left:48px}
.workflow-node b{color:#15223a;font-size:16px;line-height:1.2}
.workflow-node em{margin-top:4px;color:#0d6bff;font-style:normal;font-size:12px}
.workflow-node small{margin-top:8px;color:#68758d;font-size:12px;line-height:1.45}
.node-icon{position:absolute;left:12px;top:12px;width:28px;height:28px;border-radius:10px;background:linear-gradient(180deg,#eaf3ff,#dcecff);color:#0d6bff;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 14px rgba(13,107,255,.12)}

/* ========== 右侧配置面板 ========== */
.workflow-config-panel{position:sticky;top:12px}
.config-tabs{display:flex;gap:6px;margin-bottom:14px}
.config-tabs .tab{padding:6px 14px;border:1px solid #e4ebf5;border-radius:999px;background:#fff;color:#667085;font-size:13px;cursor:pointer}
.config-tabs .tab.active{background:#eef6ff;color:#0d6bff;border-color:#bcd8ff}
.form-row{margin-bottom:12px}
.form-row label{display:block;font-weight:700;color:#16213e;margin-bottom:6px;font-size:13px}
.form-row input,.form-row select,.form-row textarea{width:100%;padding:8px 10px;border:1px solid #d9e4f3;border-radius:8px;font-size:13px;color:#16213e;background:#fff}
.form-row textarea{min-height:80px;resize:vertical}
.form-row .disabled-input{background:#f5f7fa;color:#999;cursor:not-allowed}
.form-hint{display:block;margin-top:4px;font-size:12px;color:#8a9bb4}

/* 关键词输入（配置面板内） */
.keyword-tag-input{display:flex;flex-wrap:wrap;gap:6px;padding:8px 10px;border:1px solid #d9e4f3;border-radius:12px;background:#fff;min-height:44px;align-items:center}
.keyword-tag{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;background:#eef6ff;color:#0d6bff;border-radius:8px;font-size:13px;line-height:1.6;font-weight:500}
.keyword-tag .tag-remove{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:0;background:transparent;color:#0d6bff;cursor:pointer;font-size:16px;padding:0;line-height:1;border-radius:50%}
.keyword-tag .tag-remove:hover{background:#d0e4ff}
.keyword-input{flex:1;min-width:150px;border:0;outline:0;font-size:14px;color:#16213e;background:transparent;padding:4px 0}
.keyword-input::placeholder{color:#b0bccf}
.extract-row{display:flex;align-items:center;gap:10px;margin-top:6px;flex-wrap:wrap}
.success-text{color:#10b981}
.error-text{color:#ef4444}
.extract-result-preview{margin-top:8px;padding:10px;border-radius:8px;background:#f8fafc;border:1px solid #e4ebf5}
.extract-result-title{font-size:12px;color:#475467;margin-bottom:6px;font-weight:500}
.extract-result-tags{display:flex;flex-wrap:wrap;gap:6px}
.extract-result-tag{font-size:12px;padding:3px 10px;border-radius:12px;background:#eef2f7;color:#475467;border:1px solid #d0d7e2}
.extract-result-tag.added{background:#ecfdf5;color:#065f46;border-color:#6ee7b7}
.option-line{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f0f4fa}
.json-editor{font-family:monospace;font-size:12px;min-height:140px}
.json-error{color:#ef4444;font-size:12px;margin-top:4px}
.empty-mini{padding:22px;text-align:center;color:#98a2b3;border:1px dashed #dbe5f1;border-radius:12px;background:#fbfdff}
.auto-category-row{display:flex;gap:8px;align-items:center;width:100%}.auto-category-row input{flex:1}.auto-category-hint-text{font-size:11px;color:#0d6bff;background:#eef6ff;border:1px solid #bedaff;border-radius:6px;padding:3px 8px;white-space:nowrap;cursor:default}

/* 账号卡片多选 */
.account-card-list{display:flex;flex-direction:column;gap:8px;max-height:360px;overflow-y:auto}
.account-card{display:flex;align-items:center;gap:10px;padding:10px 12px;border:2px solid #e0e8f0;border-radius:10px;cursor:pointer;transition:all .15s;background:#fff}
.account-card:hover{border-color:#b3d4ff;background:#f8fbff}
.account-card.selected{border-color:#0d6bff;background:#eef6ff}
.account-card-checkbox{flex-shrink:0;width:18px;height:18px;border-radius:4px;border:2px solid #c5d3e0;transition:all .15s;display:flex;align-items:center;justify-content:center}
.account-card-checkbox.checked{background:#0d6bff;border-color:#0d6bff}
.account-card-checkbox.checked::after{content:'';width:5px;height:9px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(45deg)}
.account-card-avatar{width:38px;height:38px;border-radius:50%;object-fit:cover;flex-shrink:0}
.account-card-avatar-placeholder{width:38px;height:38px;border-radius:50%;background:#e0e8f0;color:#667085;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;flex-shrink:0}
.account-card-info{flex:1;min-width:0}
.account-card-name{font-size:13px;font-weight:600;color:#16213e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.account-card-status{font-size:11px;color:#10b981;margin-top:2px}
.account-card-status.invalid{color:#ef4444}
.account-card-intro{font-size:12px;color:#8a9bb4;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.account-card-intro.placeholder{color:#c0cad6}
.empty-hint{padding:16px;text-align:center;color:#98a2b3;font-size:13px;border:1px dashed #dbe5f1;border-radius:8px}

/* 增强配置样式 */
.config-textarea{width:100%;padding:8px 10px;border:1px solid #d9e4f3;border-radius:8px;font-size:13px;color:#16213e;background:#fff;resize:vertical;font-family:inherit}
.status-label{display:flex;align-items:center;gap:6px;font-size:13px;color:#667085}
.status-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.status-dot.active{background:#10b981}
.status-dot.skip{background:#f59e0b}
.preview-box{background:#f8fafc;border:1px solid #e4ebf5;border-radius:8px;padding:10px;font-size:12px;color:#374151;max-height:120px;overflow:auto;white-space:pre-wrap;margin:0}
.address-list{max-height:180px;overflow-y:auto;border:1px solid #e4ebf5;border-radius:8px;padding:4px}
.address-item{padding:8px 10px;cursor:pointer;border-radius:6px;display:flex;flex-direction:column;gap:2px}
.address-item:hover{background:#f0f6ff}
.address-item small{color:#98a2b3;font-size:11px}
.address-search-box{position:relative;display:flex;flex-direction:column;gap:6px}
.address-field-warning{display:flex;align-items:flex-start;gap:6px;padding:6px 10px;background:#fef3c7;border:1px solid #fbbf24;border-radius:6px;color:#92400e;font-size:11px;line-height:1.5;margin-top:2px}
.address-field-warning .warning-icon{flex-shrink:0;width:14px;height:14px;border-radius:50%;background:#f59e0b;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;margin-top:1px}
.address-field-ok{display:flex;align-items:center;gap:6px;padding:6px 10px;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:6px;color:#065f46;font-size:11px;line-height:1.5;margin-top:2px}
.address-field-ok .ok-icon{flex-shrink:0;width:14px;height:14px;border-radius:50%;background:#10b981;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:700}
.address-field-hint{padding:6px 10px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;color:#64748b;font-size:11px;line-height:1.5;margin-top:2px}
.recent-runs-list{display:flex;flex-direction:column;gap:8px}
.recent-run-item{padding:10px 12px;border:1px solid #eaf0f8;border-radius:12px;cursor:pointer;background:#fafcff}
.recent-run-item:hover{background:#f5f9ff;border-color:#d4e4ff}
.recent-run-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.recent-run-name{font-weight:700;color:#16213e;font-size:14px}
.recent-run-meta{display:flex;gap:12px;font-size:12px;color:#98a2b3;margin-bottom:4px}
.recent-run-error{font-size:12px;color:#ef4444;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.recent-run-time{font-size:11px;color:#b0bccf}
.image-preview-list{display:flex;flex-wrap:wrap;gap:8px}
.image-preview-item{width:80px;height:80px;border-radius:8px;overflow:hidden;border:1px solid #e4ebf5}
.image-preview-item img{width:100%;height:100%;object-fit:cover}
.error-text{color:#ef4444;font-size:12px}
.ref-image-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.ref-image-item{position:relative;width:64px;height:64px;border-radius:8px;overflow:hidden;border:1px solid #e4ebf5;flex-shrink:0}
.ref-image-item img{width:100%;height:100%;object-fit:cover;display:block}
.ref-image-remove{position:absolute;top:2px;right:2px;width:18px;height:18px;border-radius:50%;background:rgba(0,0,0,0.6);color:#fff;border:none;cursor:pointer;font-size:14px;line-height:18px;text-align:center;padding:0}
.ref-image-remove:hover{background:rgba(239,68,68,0.9)}
.ref-image-add{width:64px;height:64px;border-radius:8px;border:1px dashed #c0cad8;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#98a2b3;font-size:24px;flex-shrink:0;background:#fafbfc}
.ref-image-add:hover{border-color:#0d6bff;color:#0d6bff;background:#eef6ff}
.hint-text{color:#98a2b3;font-size:12px;font-weight:normal}
.disabled-input{background:#f0f2f5;color:#98a2b3;cursor:not-allowed}

/* 执行详情标签 */
.mini-tabs{display:flex;gap:6px;margin:10px 0;flex-wrap:wrap}
.mini-tabs .tab{padding:5px 12px;border:1px solid #e4ebf5;border-radius:999px;background:#fff;color:#667085;font-size:12px;cursor:pointer}
.mini-tabs .tab.active{background:#eef6ff;color:#0d6bff;border-color:#bcd8ff}
.timeline-list{display:flex;flex-direction:column;gap:8px;max-height:360px;overflow-y:auto}
.timeline-item{display:flex;gap:10px;align-items:flex-start;padding:8px 10px;background:#fafbfc;border-radius:10px;border-left:3px solid #e4ebf5}
.timeline-item .tl-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:5px}
.tl-dot.info{background:#0d6bff}
.tl-dot.warn{background:#f59e0b}
.tl-dot.error{background:#ef4444}
.tl-dot.debug{background:#9ca3af}
.tl-body{flex:1}
.tl-body b{display:block;font-size:13px;color:#16213e}
.tl-body p{margin:3px 0;font-size:12px;color:#667085}
.tl-body small{font-size:11px;color:#9ca3af}
.artifact-list,.state-variable-list{display:flex;flex-direction:column;gap:10px;max-height:520px;overflow-y:auto;padding-right:2px}
.artifact-item,.state-var-item{padding:10px 12px;background:#fafbfc;border-radius:10px;border:1px solid #eaf0f8}
.artifact-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.artifact-head .chip{display:inline-block;padding:2px 8px;border-radius:999px;background:#edf5ff;color:#0d6bff;font-size:11px}
.artifact-title{font-size:13px;font-weight:600;color:#16213e}
.artifact-node{font-size:11px;color:#9ca3af;margin-left:auto;font-family:ui-monospace,Menlo,Consolas,monospace}
.state-var-item .chip{display:inline-block;padding:2px 8px;border-radius:999px;background:#edf5ff;color:#0d6bff;font-size:11px;margin-right:6px}
.state-var-item b{display:block;font-size:12px;color:#16213e;margin:4px 0}
.mini-json{background:#f3f5f7;border-radius:8px;padding:8px;font-size:11px;max-height:120px;overflow:auto;margin:6px 0 0;color:#374151}
.artifact-text{
  background:#f3f5f7;border-radius:8px;padding:10px 12px;font-size:12px;line-height:1.6;
  margin:6px 0 0;color:#1f2937;font-family:ui-monospace,Menlo,Consolas,monospace;
  white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere;
  max-height:none;
}
.step-line{display:flex;align-items:center;gap:8px;padding:8px 10px;background:#fafbfc;border-radius:10px;margin-bottom:6px}
.step-line i{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.step-line i.success{background:#10b981}
.step-line i.failed{background:#ef4444}
.step-line i.running{background:#f59e0b}
.step-line i.queued{background:#9ca3af}
.step-line span{flex:1;font-size:13px;color:#16213e}
.step-line em{font-size:12px;font-style:normal;color:#667085}
.step-line small{font-size:11px;color:#9ca3af}

/* ========== 小工具 ========== */
.mini-progress{display:inline-block;width:80px;height:7px;background:#e8eef8;border-radius:7px;vertical-align:middle}
.mini-progress i{display:block;height:7px;background:var(--primary);border-radius:7px}
.link{background:none!important;border:0!important;color:#0d6bff!important;cursor:pointer;font-size:13px;padding:0!important}
.link:hover{text-decoration:underline}

/* ========== 响应式 ========== */
@media (max-width:1200px){.workflow-shell{grid-template-columns:1fr}.exec-summary{grid-template-columns:repeat(2,1fr)}}

/* ========== 失败信息展示 ========== */
.failure-info-section{background:linear-gradient(135deg,#fef2f2,#fff5f5);border:1px solid #fecaca;border-radius:12px;padding:14px 16px;margin:10px 0}

/* ========== 实时进度展示 ========== */
.live-progress-banner{display:flex;align-items:flex-start;gap:12px;background:linear-gradient(135deg,#eff6ff,#f0f9ff);border:1px solid #bfdbfe;border-radius:12px;padding:14px 16px;margin:10px 0}
.live-progress-icon{flex-shrink:0;width:32px;height:32px;display:flex;align-items:center;justify-content:center}
.live-spinner{display:inline-block;width:22px;height:22px;border:3px solid #dbeafe;border-top-color:#3b82f6;border-radius:50%;animation:live-spin 0.9s linear infinite}
@keyframes live-spin{to{transform:rotate(360deg)}}
.live-progress-body{flex:1;min-width:0}
.live-progress-stage{font-size:15px;font-weight:700;color:#1e40af;margin-bottom:4px}
.live-progress-detail{font-size:13px;color:#1e3a8a;line-height:1.5;margin-bottom:8px}
.live-progress-bar-wrap{position:relative;height:22px;background:#dbeafe;border-radius:11px;overflow:hidden;margin-bottom:6px}
.live-progress-bar{height:100%;background:linear-gradient(90deg,#3b82f6,#60a5fa);border-radius:11px;transition:width 0.5s ease}
.live-progress-text{position:absolute;top:0;left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#1e3a8a;text-shadow:0 0 2px rgba(255,255,255,0.6)}
.live-progress-eta{font-size:12px;color:#1e40af;font-style:italic}
.failure-header{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.failure-icon{width:28px;height:28px;border-radius:50%;background:#ef4444;color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700}
.failure-title{font-size:15px;font-weight:700;color:#dc2626}
.failure-reason,.failure-step,.failure-detail{margin-bottom:8px;font-size:13px;line-height:1.6}
.failure-label{color:#991b1b;font-weight:600;white-space:nowrap}
.failure-reason-text{color:#dc2626;font-weight:500}
.failure-step-text{color:#16213e;font-weight:600}
.failure-stack{background:#1e1e2e;color:#f38ba8;border-radius:8px;padding:10px 12px;font-size:12px;max-height:160px;overflow:auto;margin:6px 0 0;white-space:pre-wrap;word-break:break-all;line-height:1.5}

/* ★ 继续执行按钮区：失败信息下方，主操作按钮 + 提示文字 */
.failure-summary-actions{display:flex;align-items:center;gap:12px;margin-top:12px;padding-top:10px;border-top:1px dashed #fecaca;flex-wrap:wrap}
.continue-hint{color:#991b1b;font-size:12px;line-height:1.5;opacity:.85}
.failure-continue-hint{display:flex;align-items:flex-start;gap:8px;margin-top:10px;padding:10px 12px;background:linear-gradient(90deg,#fef3c7,#fde68a);border:1px solid #f59e0b;border-radius:6px;color:#78350f;font-size:13px;line-height:1.55}
.failure-continue-hint .hint-icon{flex-shrink:0;color:#b45309;font-weight:bold}
.failure-continue-hint .hint-text strong{color:#78350f}
.failure-continue-hint .hint-text{flex:1}
.execution-refresh-warning{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:10px 0;flex-wrap:wrap}

/* ★ 运行中操作区：终止按钮 */
.running-summary-actions{display:flex;align-items:center;gap:12px;margin:10px 0 12px;padding:10px 12px;background:linear-gradient(135deg,#fff5f5,#fef2f2);border:1px solid #fecaca;border-radius:10px;flex-wrap:wrap}
.terminate-hint{color:#991b1b;font-size:12px;line-height:1.5;opacity:.85}

/* ★ 已终止信息展示区 */
.terminated-info-section{background:linear-gradient(135deg,#f9fafb,#f3f4f6);border:1px solid #d1d5db;border-radius:12px;padding:14px 16px;margin:10px 0 12px}
.terminated-header{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.terminated-icon{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:999px;background:#6b7280;color:#fff;font-size:12px;font-weight:700}
.terminated-title{font-size:15px;font-weight:700;color:#374151}
.terminated-reason{font-size:13px;color:#374151;margin:6px 0}
.terminated-label{color:#6b7280;font-weight:600}
.terminated-reason-text{color:#1f2937}
.terminated-summary-actions{display:flex;align-items:center;gap:12px;margin-top:12px;padding-top:10px;border-top:1px dashed #d1d5db;flex-wrap:wrap}

/* 执行日志面板 - 失败摘要 */
.exec-failure-summary{background:linear-gradient(135deg,#fef2f2,#fff5f5);border:1px solid #fecaca;border-radius:12px;padding:14px 16px;margin-bottom:12px}
.failure-summary-header{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.failure-summary-icon{font-size:18px}
.failure-summary-title{font-size:15px;font-weight:700;color:#dc2626}
.failure-summary-row{margin-bottom:8px;font-size:13px;line-height:1.6}
.failure-summary-label{color:#991b1b;font-weight:600;white-space:nowrap}
.failure-summary-text{color:#dc2626;font-weight:500}
.failure-summary-stack{background:#1e1e2e;color:#f38ba8;border-radius:8px;padding:10px 12px;font-size:12px;max-height:140px;overflow:auto;margin:6px 0 0;white-space:pre-wrap;word-break:break-all;line-height:1.5}

/* 最近执行记录 - 失败悬停提示 */
.exec-status-cell{position:relative;display:inline-flex;align-items:center}
.exec-status-cell.is-failed{cursor:help}
.exec-failure-tooltip{position:relative;display:inline-block;margin-left:4px}
.exec-failure-tooltip .tooltip-trigger{display:inline-block;width:16px;height:16px;border-radius:50%;background:#fef2f2;color:#ef4444;font-size:10px;text-align:center;line-height:16px;cursor:help}
.exec-failure-tooltip .tooltip-trigger::after{content:'!'}
.exec-failure-tooltip .tooltip-content{display:none;position:absolute;left:50%;bottom:calc(100% + 6px);transform:translateX(-50%);background:#1e1e2e;color:#fca5a5;padding:8px 12px;border-radius:8px;font-size:12px;white-space:nowrap;max-width:320px;white-space:normal;z-index:100;box-shadow:0 4px 12px rgba(0,0,0,.15);line-height:1.5}
.exec-failure-tooltip .tooltip-content::after{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);border:5px solid transparent;border-top-color:#1e1e2e}
.exec-failure-tooltip:hover .tooltip-content{display:block}

/* 最近运行记录 - 失败信息 */
.recent-run-error{font-size:12px;color:#ef4444;margin-bottom:4px;display:flex;flex-direction:column;gap:2px}
.recent-run-error-node{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.recent-run-error-msg{color:#dc2626;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style>
