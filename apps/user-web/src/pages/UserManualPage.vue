<template>
  <div class="manual-page">
    <!-- 图片 Lightbox -->
    <div v-if="lightboxOpen" class="lightbox-overlay" @click="closeLightbox">
      <button class="lightbox-close" @click.stop="closeLightbox">×</button>
      <button class="lightbox-prev" @click.stop="prevLightbox" v-if="lightboxIndex > 0">‹</button>
      <div class="lightbox-content" @click.stop>
        <img :src="lightboxImages[lightboxIndex]" alt="截图预览" />
      </div>
      <button class="lightbox-next" @click.stop="nextLightbox" v-if="lightboxIndex < lightboxImages.length - 1">›</button>
      <div class="lightbox-counter">{{ lightboxIndex + 1 }} / {{ lightboxImages.length }}</div>
    </div>

    <!-- 顶部 Hero -->
    <section class="manual-hero">
      <div class="hero-bg-deco">
        <div class="hero-blob hero-blob-1"></div>
        <div class="hero-blob hero-blob-2"></div>
        <div class="hero-blob hero-blob-3"></div>
        <div class="hero-grid"></div>
      </div>
      <div class="hero-inner">
        <div class="hero-breadcrumb">
          <button type="button" class="crumb-btn" @click="$emit('navigate', 'dashboard')">首页</button>
          <span class="crumb-sep">/</span>
          <span class="crumb-current">使用手册</span>
        </div>
        <div class="hero-brand-row">
          <div class="brand-mark">
            <span></span>
            <span></span>
          </div>
          <div class="hero-text">
            <div class="hero-badges">
              <Badge type="blue">v{{ APP_VERSION }}</Badge>
              <Badge>小白友好</Badge>
              <Badge type="orange">图文教程</Badge>
            </div>
            <h1>使用手册</h1>
            <p class="hero-desc">从零开始，一步步带你完成闲鱼店铺的自动化运营。<br/>账号接入、商品发布、24 小时自动发货、AI 自动客服、自动回复、数据看板——所有功能，一篇掌握。</p>
            <div class="hero-meta">
              <span class="hero-meta-item"><i class="dot dot-green"></i>无需编程基础</span>
              <span class="hero-meta-divider"></span>
              <span class="hero-meta-item">全部界面操作</span>
              <span class="hero-meta-divider"></span>
              <span class="hero-meta-item">真实页面截图</span>
              <span class="hero-meta-divider"></span>
              <span class="hero-meta-item">常见问题解答</span>
            </div>
          </div>
        </div>
        <!-- 快捷入口 -->
        <div class="quick-actions">
          <button class="qa-card qa-primary" type="button" @click="switchSection('getting-started')">
            <span class="qa-ico">🚀</span>
            <span class="qa-text"><b>新用户入门</b><em>5 步完成基础接入</em></span>
          </button>
          <button class="qa-card" type="button" @click="switchSection('auto-delivery-flow')">
            <span class="qa-ico">📦</span>
            <span class="qa-text"><b>自动发货教程</b><em>24 小时无人值守</em></span>
          </button>
          <button class="qa-card" type="button" @click="switchSection('ai-cs-flow')">
            <span class="qa-ico">🤖</span>
            <span class="qa-text"><b>AI 客服配置</b><em>让 AI 替你回复</em></span>
          </button>
          <button class="qa-card" type="button" @click="switchSection('faq')">
            <span class="qa-ico">❓</span>
            <span class="qa-text"><b>常见问题</b><em>8 个高频问题解答</em></span>
          </button>
        </div>
      </div>
    </section>

    <!-- 主体：左目录 + 右内容 -->
    <div class="manual-layout">
      <aside class="manual-toc">
        <nav class="toc-inner">
          <div class="toc-head">
            <span class="toc-title-icon">📑</span>
            <span class="toc-title">目录导航</span>
          </div>
          <a
            v-for="(sec, i) in sections"
            :key="sec.id"
            :href="`#${sec.id}`"
            :class="['toc-link', { active: activeSection === sec.id }]"
            @click.prevent="switchSection(sec.id)"
          >
            <span class="toc-num">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="toc-label">{{ sec.label.replace(/^[一二三四五六七八九十]+、/, '') }}</span>
          </a>
          <div class="toc-foot">
            <button type="button" class="toc-backtop" @click="switchSection('overview')">🏠 返回首页</button>
          </div>
        </nav>
      </aside>

      <div class="manual-content">
        <!-- 一、30秒快速了解 -->
        <section v-show="activeSection === 'overview'" id="overview" class="manual-section">
          <CardPanel>
            <template #title>
              <span class="sec-head"><span class="sec-num">01</span>30 秒快速了解闲鱼助手</span>
            </template>
            <template #desc>它是什么、能帮你做什么、为什么能省一半人力</template>
            <div class="section-body">
              <div class="lead-card">
                <span class="lead-ico">💡</span>
                <p class="lead">闲鱼助手是一站式闲鱼店铺自动化运营平台。把店铺接进来之后，<strong>商品发布、买家消息、订单发货</strong>都可以交给系统自动完成，你只需要看着数据面板盯结果。</p>
              </div>
              <div class="feature-pill-row">
                <span class="feature-pill fp-blue">👥 <strong>多账号</strong>统一管理</span>
                <span class="feature-pill fp-purple">🤖 <strong>AI 自动客服</strong>24 小时在线</span>
                <span class="feature-pill fp-green">📦 <strong>自动发货</strong>付款即发</span>
                <span class="feature-pill fp-orange">⚙️ <strong>工作流</strong>批量上架</span>
                <span class="feature-pill fp-pink">🔍 <strong>商机发掘</strong>跟品爆款</span>
                <span class="feature-pill fp-cyan">📊 <strong>数据看板</strong>实时洞察</span>
              </div>
              <figure class="shot-figure">
                <div class="shot-img-wrap" @click="openLightbox(shot('dashboard.png'))">
                  <img :src="shot('dashboard.png')" alt="导航面板首页截图" loading="lazy" @error="onShotError" />
                  <div class="shot-zoom-hint"><span>🔍</span> 点击放大</div>
                </div>
                <figcaption>▲ 图 1.1 / 登录后第一眼看到的导航面板，左侧是功能菜单，顶部是常用入口。</figcaption>
              </figure>
              <div class="callout callout-tip">
                <span class="callout-ico">🎯</span>
                <div class="callout-body">
                  <strong>适合谁用？</strong>
                  <p>闲鱼个人卖家、卡密虚拟商品卖家、多店铺矩阵运营者，每天有大量重复的发货和客服工作需要自动化。</p>
                </div>
              </div>
            </div>
            <div class="section-nav">
              <button type="button" class="sn-btn sn-next" @click="switchSection(sections[1].id)">
                <span class="sn-label">下一章</span>
                <span class="sn-title">{{ sections[1].label }}</span>
                <span class="sn-arrow">›</span>
              </button>
            </div>
          </CardPanel>
        </section>

        <!-- 二、新用户从零开始的 5 步 -->
        <section v-show="activeSection === 'getting-started'" id="getting-started" class="manual-section">
          <CardPanel>
            <template #title>
              <span class="sec-head"><span class="sec-num">02</span>新用户从零开始的 5 步</span>
            </template>
            <template #desc>按照这个顺序操作，10 分钟内完成基础接入</template>
            <div class="section-body">
              <div class="step-timeline">
                <div v-for="(step, idx) in beginnerSteps" :key="idx" class="step-item">
                  <div class="step-marker">
                    <span class="step-circle">{{ idx + 1 }}</span>
                    <span v-if="idx < beginnerSteps.length - 1" class="step-line"></span>
                  </div>
                  <div class="step-body">
                    <div class="step-title-row">
                      <h4>{{ step.title }}</h4>
                    </div>
                    <p>{{ step.desc }}</p>
                    <button v-if="step.route" class="step-action" type="button" @click="$emit('navigate', step.route)">
                      前往 {{ step.routeName }} <span class="arrow">›</span>
                    </button>
                  </div>
                </div>
              </div>
              <figure class="shot-figure">
                <div class="shot-img-wrap" @click="openLightbox(shot('accounts.png'))">
                  <img :src="shot('accounts.png')" alt="闲鱼账号管理截图" loading="lazy" @error="onShotError" />
                  <div class="shot-zoom-hint"><span>🔍</span> 点击放大</div>
                </div>
                <figcaption>▲ 图 2.1 / 「闲鱼账号」页面：所有账号的 Cookie、WS 状态、自动回复/发货开关都集中在这里。</figcaption>
              </figure>
            </div>
            <div class="section-nav">
              <button type="button" class="sn-btn sn-prev" @click="switchSection(sections[0].id)">
                <span class="sn-arrow">‹</span>
                <span class="sn-text">
                  <span class="sn-label">上一章</span>
                  <span class="sn-title">{{ sections[0].label }}</span>
                </span>
              </button>
              <button type="button" class="sn-btn sn-next" @click="switchSection(sections[2].id)">
                <span class="sn-text">
                  <span class="sn-label">下一章</span>
                  <span class="sn-title">{{ sections[2].label }}</span>
                </span>
                <span class="sn-arrow">›</span>
              </button>
            </div>
          </CardPanel>
        </section>

        <!-- 三、24 小时自动发货完整流程 -->
        <section v-show="activeSection === 'auto-delivery-flow'" id="auto-delivery-flow" class="manual-section">
          <CardPanel>
            <template #title>
              <span class="sec-head"><span class="sec-num">03</span>从零实现 24 小时自动发货</span>
            </template>
            <template #desc>买家付款 → 系统自动发卡密/文本 → 自动确认收货，全程无人值守</template>
            <div class="section-body">
              <div class="lead-card lead-card-green">
                <span class="lead-ico">📦</span>
                <p class="lead">自动发货是闲鱼助手最核心的能力之一。按下述 7 步配置完成，买家付款后系统会在<strong>几秒内</strong>自动把发货内容发到会话里。</p>
              </div>

              <div class="flow-visual">
                <div class="flow-step" v-for="(node, i) in deliveryFlow" :key="i">
                  <div class="flow-node">
                    <span class="flow-ico">{{ node.ico }}</span>
                    <span class="flow-label">{{ node.label }}</span>
                  </div>
                  <span v-if="i < deliveryFlow.length - 1" class="flow-connector">→</span>
                </div>
              </div>

              <div class="step-timeline">
                <div v-for="(step, idx) in deliverySteps" :key="idx" class="step-item">
                  <div class="step-marker">
                    <span class="step-circle step-circle-green">{{ idx + 1 }}</span>
                    <span v-if="idx < deliverySteps.length - 1" class="step-line"></span>
                  </div>
                  <div class="step-body">
                    <div class="step-title-row">
                      <h4>{{ step.title }}</h4>
                    </div>
                    <p v-if="step.desc">{{ step.desc }}</p>
                    <ul v-if="step.items" class="bullet-list">
                      <li v-for="(item, li) in step.items" :key="li" v-html="item"></li>
                    </ul>
                    <div v-if="step.routes" class="step-actions">
                      <button v-for="(rt, ri) in step.routes" :key="ri" class="step-action" type="button" @click="$emit('navigate', rt.route)">
                        前往 {{ rt.name }} <span class="arrow">›</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <figure class="shot-figure">
                <div class="shot-img-wrap" @click="openLightbox(shot('auto-delivery.png'))">
                  <img :src="shot('auto-delivery.png')" alt="自动发货配置截图" loading="lazy" @error="onShotError" />
                  <div class="shot-zoom-hint"><span>🔍</span> 点击放大</div>
                </div>
                <figcaption>▲ 图 3.1 / 「自动发货」页面：每行是一个商品，三种时机列分别展示付款后/收货后/好评后的配置状态。</figcaption>
              </figure>

              <div class="callout callout-warn">
                <span class="callout-ico">⚠️</span>
                <div class="callout-body">
                  <strong>常见踩坑</strong>
                  <ul>
                    <li>WS 必须保持在线，离线期间产生的订单不会自动补发，需要手动触发。</li>
                    <li>卡密库存不足时系统会按"库存预警阈值"提醒；如果开了"自动停用"，会停止发货避免超卖。</li>
                    <li>同一商品同时配置了"付款后发卡密"和"收货后发感谢语"，两个时机都会触发，互不冲突。</li>
                  </ul>
                </div>
              </div>
            </div>
            <div class="section-nav">
              <button type="button" class="sn-btn sn-prev" @click="switchSection(sections[1].id)">
                <span class="sn-arrow">‹</span>
                <span class="sn-text">
                  <span class="sn-label">上一章</span>
                  <span class="sn-title">{{ sections[1].label }}</span>
                </span>
              </button>
              <button type="button" class="sn-btn sn-next" @click="switchSection(sections[3].id)">
                <span class="sn-text">
                  <span class="sn-label">下一章</span>
                  <span class="sn-title">{{ sections[3].label }}</span>
                </span>
                <span class="sn-arrow">›</span>
              </button>
            </div>
          </CardPanel>
        </section>

        <!-- 四、24 小时自动客服 -->
        <section v-show="activeSection === 'ai-cs-flow'" id="ai-cs-flow" class="manual-section">
          <CardPanel>
            <template #title>
              <span class="sec-head"><span class="sec-num">04</span>为闲鱼店铺配置 24 小时 AI 自动客服</span>
            </template>
            <template #desc>让 AI 替你回复买家咨询，晚上睡觉也能接单</template>
            <div class="section-body">
              <div class="lead-card lead-card-purple">
                <span class="lead-ico">🤖</span>
                <p class="lead">AI 自动客服 = <strong>AI 客服配置</strong> + <strong>自动回复开关</strong>。前者定义"AI 怎么回"，后者定义"什么场景下让 AI 回"。</p>
              </div>

              <div class="step-timeline">
                <div v-for="(step, idx) in aiCsSteps" :key="idx" class="step-item">
                  <div class="step-marker">
                    <span class="step-circle step-circle-purple">{{ idx + 1 }}</span>
                    <span v-if="idx < aiCsSteps.length - 1" class="step-line"></span>
                  </div>
                  <div class="step-body">
                    <div class="step-title-row">
                      <h4>{{ step.title }}</h4>
                    </div>
                    <p v-if="step.desc">{{ step.desc }}</p>
                    <ul v-if="step.items" class="bullet-list">
                      <li v-for="(item, li) in step.items" :key="li" v-html="item"></li>
                    </ul>
                    <button v-if="step.route" class="step-action step-action-purple" type="button" @click="$emit('navigate', step.route)">
                      前往 {{ step.routeName }} <span class="arrow">›</span>
                    </button>
                  </div>
                </div>
              </div>

              <figure class="shot-figure">
                <div class="shot-img-wrap" @click="openLightbox(shot('ai-cs-settings.png'))">
                  <img :src="shot('ai-cs-settings.png')" alt="AI 客服配置截图" loading="lazy" @error="onShotError" />
                  <div class="shot-zoom-hint"><span>🔍</span> 点击放大</div>
                </div>
                <figcaption>▲ 图 4.1 / 「AI 客服配置」页面：工作模式、接待模式、人设、知识库、安全策略都在这里集中配置。</figcaption>
              </figure>

              <div class="callout callout-tip">
                <span class="callout-ico">💰</span>
                <div class="callout-body">
                  <strong>Token 余额</strong>
                  <p>AI 回复会消耗 Token 余额，可在「个人中心」查看余额并充值。余额不足时 AI 自动降级（不回复或仅回退模板），不会消耗超出余额的费用。</p>
                </div>
              </div>
            </div>
            <div class="section-nav">
              <button type="button" class="sn-btn sn-prev" @click="switchSection(sections[2].id)">
                <span class="sn-arrow">‹</span>
                <span class="sn-text">
                  <span class="sn-label">上一章</span>
                  <span class="sn-title">{{ sections[2].label }}</span>
                </span>
              </button>
              <button type="button" class="sn-btn sn-next" @click="switchSection(sections[4].id)">
                <span class="sn-text">
                  <span class="sn-label">下一章</span>
                  <span class="sn-title">{{ sections[4].label }}</span>
                </span>
                <span class="sn-arrow">›</span>
              </button>
            </div>
          </CardPanel>
        </section>

        <!-- 五、自动回复配置 -->
        <section v-show="activeSection === 'auto-reply-flow'" id="auto-reply-flow" class="manual-section">
          <CardPanel>
            <template #title>
              <span class="sec-head"><span class="sec-num">05</span>配置自动回复（开关 + 作用层级）</span>
            </template>
            <template #desc>决定 AI 客服在哪些账号、哪些商品上生效</template>
            <div class="section-body">
              <div class="lead-card">
                <span class="lead-ico">🎚️</span>
                <p class="lead">自动回复控制台是 AI 客服的"开关面板"。AI 客服配置定义能力，自动回复控制台决定<strong>能力作用到哪里</strong>。</p>
              </div>

              <div class="step-timeline">
                <div v-for="(step, idx) in autoReplySteps" :key="idx" class="step-item">
                  <div class="step-marker">
                    <span class="step-circle step-circle-blue">{{ idx + 1 }}</span>
                    <span v-if="idx < autoReplySteps.length - 1" class="step-line"></span>
                  </div>
                  <div class="step-body">
                    <div class="step-title-row">
                      <h4>{{ step.title }}</h4>
                    </div>
                    <p v-if="step.desc">{{ step.desc }}</p>
                    <ul v-if="step.items" class="bullet-list">
                      <li v-for="(item, li) in step.items" :key="li" v-html="item"></li>
                    </ul>
                    <button v-if="step.route" class="step-action" type="button" @click="$emit('navigate', step.route)">
                      前往 {{ step.routeName }} <span class="arrow">›</span>
                    </button>
                  </div>
                </div>
              </div>

              <figure class="shot-figure">
                <div class="shot-img-wrap" @click="openLightbox(shot('auto-reply.png'))">
                  <img :src="shot('auto-reply.png')" alt="自动回复控制台截图" loading="lazy" @error="onShotError" />
                  <div class="shot-zoom-hint"><span>🔍</span> 点击放大</div>
                </div>
                <figcaption>▲ 图 5.1 / 「自动回复」页面：左侧筛选账号/商品，右侧批量开关自动回复。</figcaption>
              </figure>
            </div>
            <div class="section-nav">
              <button type="button" class="sn-btn sn-prev" @click="switchSection(sections[3].id)">
                <span class="sn-arrow">‹</span>
                <span class="sn-text">
                  <span class="sn-label">上一章</span>
                  <span class="sn-title">{{ sections[3].label }}</span>
                </span>
              </button>
              <button type="button" class="sn-btn sn-next" @click="switchSection(sections[5].id)">
                <span class="sn-text">
                  <span class="sn-label">下一章</span>
                  <span class="sn-title">{{ sections[5].label }}</span>
                </span>
                <span class="sn-arrow">›</span>
              </button>
            </div>
          </CardPanel>
        </section>

        <!-- 六、功能模块详解 -->
        <section v-show="activeSection === 'modules'" id="modules" class="manual-section">
          <CardPanel>
            <template #title>
              <span class="sec-head"><span class="sec-num">06</span>全部功能模块详解</span>
            </template>
            <template #desc>按左侧菜单顺序逐一讲解，每个模块都附截图</template>
            <div class="section-body">
              <div v-for="group in moduleGroups" :key="group.id" class="module-group">
                <h3 class="module-group-title">
                  <span class="mgt-ico">{{ group.ico }}</span>{{ group.title }}
                </h3>
                <div v-for="mod in group.modules" :key="mod.name" class="module-card" :class="`mc-${group.color}`">
                  <div class="mc-accent"></div>
                  <div class="mc-body">
                    <header>
                      <h4>
                        <span class="mc-ico">{{ mod.ico }}</span>{{ mod.name }}
                        <button v-if="mod.route" class="nav-jump" type="button" @click="$emit('navigate', mod.route)">前往 ›</button>
                      </h4>
                      <p>{{ mod.desc }}</p>
                    </header>
                    <ul v-if="mod.features" class="bullet-list">
                      <li v-for="(f, fi) in mod.features" :key="fi" v-html="f"></li>
                    </ul>
                    <div v-if="mod.callout" class="mc-callout">
                      <span class="mc-callout-ico">{{ mod.callout.ico }}</span>
                      <p v-html="mod.callout.text"></p>
                    </div>
                    <figure v-if="mod.shot" class="shot-figure shot-figure-sm">
                      <div class="shot-img-wrap" @click="openLightbox(shot(mod.shot))">
                        <img :src="shot(mod.shot)" :alt="mod.name + '截图'" loading="lazy" @error="onShotError" />
                        <div class="shot-zoom-hint"><span>🔍</span> 点击放大</div>
                      </div>
                      <figcaption>▲ {{ mod.fig }}</figcaption>
                    </figure>
                  </div>
                </div>
              </div>
            </div>
            <div class="section-nav">
              <button type="button" class="sn-btn sn-prev" @click="switchSection(sections[4].id)">
                <span class="sn-arrow">‹</span>
                <span class="sn-text">
                  <span class="sn-label">上一章</span>
                  <span class="sn-title">{{ sections[4].label }}</span>
                </span>
              </button>
              <button type="button" class="sn-btn sn-next" @click="switchSection(sections[6].id)">
                <span class="sn-text">
                  <span class="sn-label">下一章</span>
                  <span class="sn-title">{{ sections[6].label }}</span>
                </span>
                <span class="sn-arrow">›</span>
              </button>
            </div>
          </CardPanel>
        </section>

        <!-- 七、常见问题 -->
        <section v-show="activeSection === 'faq'" id="faq" class="manual-section">
          <CardPanel>
            <template #title>
              <span class="sec-head"><span class="sec-num">07</span>常见问题 FAQ</span>
            </template>
            <template #desc>点击问题展开答案</template>
            <div class="section-body">
              <div v-for="(qa, idx) in faqItems" :key="idx" class="faq-item" :class="{ open: openFaq === idx }">
                <button class="faq-q" type="button" @click="toggleFaq(idx)">
                  <span class="faq-q-num">Q{{ idx + 1 }}</span>
                  <span class="faq-q-text">{{ qa.q }}</span>
                  <span class="faq-toggle">{{ openFaq === idx ? '−' : '+' }}</span>
                </button>
                <div class="faq-a" v-show="openFaq === idx">
                  <span class="faq-a-label">A</span>
                  <p v-html="qa.a"></p>
                </div>
              </div>
            </div>
            <div class="section-nav">
              <button type="button" class="sn-btn sn-prev" @click="switchSection(sections[5].id)">
                <span class="sn-arrow">‹</span>
                <span class="sn-text">
                  <span class="sn-label">上一章</span>
                  <span class="sn-title">{{ sections[5].label }}</span>
                </span>
              </button>
              <button type="button" class="sn-btn sn-next" @click="switchSection(sections[7].id)">
                <span class="sn-text">
                  <span class="sn-label">下一章</span>
                  <span class="sn-title">{{ sections[7].label }}</span>
                </span>
                <span class="sn-arrow">›</span>
              </button>
            </div>
          </CardPanel>
        </section>

        <!-- 八、联系与反馈 -->
        <section v-show="activeSection === 'support'" id="support" class="manual-section">
          <CardPanel>
            <template #title>
              <span class="sec-head"><span class="sec-num">08</span>联系与反馈</span>
            </template>
            <template #desc>遇到问题可以这样找我们</template>
            <div class="section-body">
              <div class="support-grid">
                <button class="support-tile st-blue" type="button" @click="$emit('navigate', 'feedback')">
                  <div class="support-ico">📝</div>
                  <div class="support-text"><b>提交反馈建议</b><p>在系统内直接提交，我们会跟踪处理</p></div>
                  <span class="support-arrow">›</span>
                </button>
                <button class="support-tile st-green" type="button" @click="$emit('navigate', 'settings-about')">
                  <div class="support-ico">ℹ️</div>
                  <div class="support-text"><b>查看关于页</b><p>版本号、更新日志、服务支持渠道</p></div>
                  <span class="support-arrow">›</span>
                </button>
                <button class="support-tile st-orange" type="button" @click="$emit('navigate', 'logs')">
                  <div class="support-ico">📋</div>
                  <div class="support-text"><b>导出操作日志</b><p>反馈问题时附上日志有助于快速定位</p></div>
                  <span class="support-arrow">›</span>
                </button>
              </div>
              <div class="callout callout-tip">
                <span class="callout-ico">✅</span>
                <div class="callout-body">
                  <strong>建议先自助排查</strong>
                  <p>80% 的常见问题都能通过本手册第七章 FAQ 自行解决。如果仍未解决，请通过「反馈建议」提交，并附上「操作日志」导出的 CSV。</p>
                </div>
              </div>
            </div>
            <div class="section-nav">
              <button type="button" class="sn-btn sn-prev" @click="switchSection(sections[6].id)">
                <span class="sn-arrow">‹</span>
                <span class="sn-text">
                  <span class="sn-label">上一章</span>
                  <span class="sn-title">{{ sections[6].label }}</span>
                </span>
              </button>
            </div>
          </CardPanel>
        </section>
      </div>
    </div>

    <div class="manual-footer">
      <p>© {{ copyrightYear }} XianYuAssistant · 使用手册 v{{ APP_VERSION }} · 最后更新 {{ todayText }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import Badge from '../components/Badge.vue'
import { APP_VERSION, getCopyrightYear } from '../utils/appMeta.js'

defineEmits(['navigate'])

const sections = [
  { id: 'overview', label: '一、30 秒快速了解' },
  { id: 'getting-started', label: '二、新用户 5 步入门' },
  { id: 'auto-delivery-flow', label: '三、24 小时自动发货' },
  { id: 'ai-cs-flow', label: '四、24 小时 AI 客服' },
  { id: 'auto-reply-flow', label: '五、自动回复配置' },
  { id: 'modules', label: '六、全部功能模块详解' },
  { id: 'faq', label: '七、常见问题 FAQ' },
  { id: 'support', label: '八、联系与反馈' }
]

const activeSection = ref('overview')
const openFaq = ref(0)
const copyrightYear = getCopyrightYear()
const todayText = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })

const lightboxOpen = ref(false)
const lightboxIndex = ref(0)
const lightboxImages = ref([])

function collectLightboxImages() {
  const images = [
    shot('dashboard.png'),
    shot('accounts.png'),
    shot('auto-delivery.png'),
    shot('ai-cs-settings.png'),
    shot('auto-reply.png')
  ]
  for (const group of moduleGroups) {
    for (const mod of group.modules) {
      if (mod.shot) {
        images.push(shot(mod.shot))
      }
    }
  }
  lightboxImages.value = images
}

function openLightbox(url) {
  const idx = lightboxImages.value.indexOf(url)
  lightboxIndex.value = idx >= 0 ? idx : 0
  lightboxOpen.value = true
  document.body.style.overflow = 'hidden'
}

function closeLightbox() {
  lightboxOpen.value = false
  document.body.style.overflow = ''
}

function prevLightbox() {
  if (lightboxIndex.value > 0) {
    lightboxIndex.value--
  }
}

function nextLightbox() {
  if (lightboxIndex.value < lightboxImages.value.length - 1) {
    lightboxIndex.value++
  }
}

function onLightboxKeydown(e) {
  if (!lightboxOpen.value) return
  if (e.key === 'Escape') closeLightbox()
  if (e.key === 'ArrowLeft') prevLightbox()
  if (e.key === 'ArrowRight') nextLightbox()
}

// 新用户 5 步
const beginnerSteps = [
  { title: '注册账号并登录', desc: '在登录页使用邮箱验证码或账号密码登录。首次进入会进入"导航面板"首页，看到快速开始入口。', route: null },
  { title: '添加闲鱼店铺账号', desc: '进入「闲鱼账号」页面，点击右上角"扫码加账号"，用闲鱼 App 扫描二维码完成授权。授权成功后账号会出现在列表里。', route: 'accounts', routeName: '闲鱼账号' },
  { title: '保持 WebSocket 在线', desc: '在「闲鱼账号」页面查看账号的 WS 状态，确保显示为"在线"。WS 在线是接收消息和触发自动化的前提。', route: 'accounts', routeName: '闲鱼账号' },
  { title: '同步或发布商品', desc: '进入「商品管理」点击"同步闲鱼商品"把已有商品拉到系统；或进入「发布商品」新建商品。商品是后续订单、发货、客服的载体。', route: 'products', routeName: '商品管理' },
  { title: '开启自动化', desc: '按需进入「自动发货」「自动回复」「工作流」开启自动化规则。后面的章节会逐个详细讲解。', route: null }
]

// 自动发货流程图
const deliveryFlow = [
  { ico: '💳', label: '买家付款' },
  { ico: '🔄', label: '订单同步' },
  { ico: '🎯', label: '匹配规则' },
  { ico: '📤', label: '取卡密/文本' },
  { ico: '💬', label: '发送会话' },
  { ico: '📝', label: '记录日志' }
]

// 自动发货 7 步
const deliverySteps = [
  { title: '添加账号并保持 WS 在线', desc: '参考"新用户 5 步"的步骤 2-3。WS 必须在线，否则系统收不到订单事件。' },
  { title: '同步商品到商品管理', desc: '在「商品管理」点击"同步闲鱼商品"。同步成功后，每个商品都会有一个商品 ID，自动发货规则按商品维度配置。' },
  { title: '准备发货内容', desc: '发货内容有两种形式，二选一即可：', items: [
    '<strong>卡密发货</strong>：进入「卡密仓库」新建卡密组，批量导入卡密（支持"卡号----密码"格式）。系统每次发货会自动取一个未使用的卡密。',
    '<strong>文本发货</strong>：进入「货源库」新增货源，填写标题和正文。正文里可以插入变量，适合发链接、提取码、网盘地址等。'
  ], routes: [
    { route: 'card-warehouse', name: '卡密仓库' },
    { route: 'delivery-source-library', name: '货源库' }
  ]},
  { title: '配置自动发货规则', desc: '进入「自动发货」页面，找到要配置的商品，点击对应时机列（付款后 / 收货后 / 好评后）的按钮，在弹窗里：', items: [
    '开启"启用"开关',
    '选择发货模式：<strong>text 文本</strong> 或 <strong>card 卡密</strong>',
    'text 模式：选择关联的货源、填写消息头部、正文（支持变量与 {分段} 拆分）',
    'card 模式：选择卡密分组和卡密模板',
    '设置重试次数、库存预警阈值、库存不足时是否自动停用'
  ], routes: [{ route: 'auto-delivery', name: '自动发货' }]},
  { title: '配置发货声明（可选）', desc: '进入「发货声明」开启开关，编辑声明文案（支持 {订单编号}、{商品标题}、{买家昵称}、{发货确认链接} 等变量），系统会在发货内容后追加这段声明，规避售后纠纷。', routes: [{ route: 'delivery-statement', name: '发货声明' }]},
  { title: '配置通知提醒（可选）', desc: '进入「通知设置」配置 SMTP 邮件或飞书自建应用，把"发货成功/失败/缺货"等事件推送到你的邮箱或飞书群，便于随时掌握异常。', routes: [{ route: 'settings-notify', name: '通知设置' }]},
  { title: '验证发货记录', desc: '真实订单付款后，进入「发货记录」查看是否自动发货成功。如果失败，详情面板会显示原因（缺货 / 配置错误 / WS 断开等），可点击"重新发货"或"安排重新发货"（Cron 定时）。', routes: [{ route: 'delivery-records', name: '发货记录' }]}
]

// AI 客服 8 步
const aiCsSteps = [
  { title: '进入 AI 客服配置', desc: '左侧菜单 →「系统设置」→「AI 客服配置」Tab。这是 AI 客服的中枢配置页。', route: 'settings-ai-cs', routeName: 'AI 客服配置' },
  { title: '开启并选择工作模式', desc: '顶部开启"启用 AI 客服"。选择工作模式：', items: [
    '<strong>24 小时全天</strong>：任何时间都让 AI 接待，最省心。',
    '<strong>工作时段</strong>：只在指定时段（如 22:00-08:00）让 AI 接管，白天你自己回。'
  ]},
  { title: '选择接待模式', items: [
    '<strong>auto 全自动</strong>：AI 直接回复，无需人工干预。推荐 24 小时无人值守场景。',
    '<strong>hybrid 混合</strong>：AI 先回，命中"转人工关键词"或"转人工阈值"时切换人工。',
    '<strong>manual 仅人工</strong>：AI 不自动回，仅作为草稿建议。'
  ]},
  { title: '配置角色人设与语气', desc: '填写人设描述（如"你是某虚拟商品店铺的客服小助手，态度友好、回答简洁"），选择语气（friendly 友好 / professional 专业 / casual 随意），设置 System Prompt 与欢迎语（买家首次发起会话时 AI 主动发送的问候）。' },
  { title: '上传知识库（可选但强烈推荐）', desc: '支持 .md / .txt / .pptx / .xlsx / .csv。把商品说明书、售后政策、常见问答整理成文档上传，AI 会优先基于知识库回答，避免胡说八道。' },
  { title: '配置安全策略', items: [
    '<strong>转人工关键词</strong>：买家说到"退款/投诉/人工"等关键词时，自动切换人工。',
    '<strong>黑名单关键词</strong>：命中后 AI 不回复。',
    '<strong>转人工阈值</strong>：连续 N 轮对话后强制转人工，防止 AI 死循环。',
    '<strong>每日最大回复数</strong>：单会话每日上限，防止恶意消耗 Token。',
    '<strong>会话超时</strong>：买家多久没回话就结束会话。'
  ]},
  { title: '实时预览测试', desc: '页面底部的"实时回复预览"区可以直接输入测试消息，验证 AI 回复效果。调到满意再保存。' },
  { title: '在自动回复控制台开启', desc: 'AI 配置只是"模板"，还需要在「自动回复」页面把开关打开。可以选择作用层级：全局（所有账号所有商品）/ 账号级 / 商品级。新用户建议直接开"全局"。', route: 'auto-reply', routeName: '自动回复控制台' }
]

// 自动回复 5 步
const autoReplySteps = [
  { title: '选择账号范围', desc: '页面顶部筛选要管理的账号，可以单选、多选或全选。' },
  { title: '选择商品范围', desc: '进一步筛选商品，支持按状态、关键词过滤。' },
  { title: '选择作用层级', items: [
    '<strong>全局</strong>：所有账号所有商品生效，最简单。',
    '<strong>账号</strong>：只对选中的账号生效，适合矩阵账号差异化运营。',
    '<strong>商品</strong>：只对选中的商品生效，适合给某些商品单独开 AI。'
  ]},
  { title: '批量操作', desc: '勾选目标项，点击"一键全部开启"或"批量开启/批量关闭"。' },
  { title: '验证效果', desc: '进入「在线消息」找一条买家会话发起新消息，看右侧"自动回复诊断"面板的状态：作用范围、Token 余额、账号登录是否正常都会实时显示。', route: 'messages', routeName: '在线消息' }
]

// 模块分组
const moduleGroups = [
  {
    id: 'overview',
    title: '概览',
    ico: '🏠',
    color: 'blue',
    modules: [
      { name: '导航面板', ico: '🏠', desc: '登录后的首页，是所有功能的入口枢纽。', route: 'dashboard', shot: 'dashboard.png', fig: '图 6.1 / 导航面板。', features: [
        '<strong>顶部轮播</strong>：管理员配置的活动 banner。',
        '<strong>快速开始</strong>：添加账号、WS 连接、商品管理、自动发货 4 个最常用入口。',
        '<strong>功能特性</strong>：8 个核心功能的卡片入口。',
        '<strong>最近实时事件</strong>：SSE 推送的最新 5 条业务事件。',
        '<strong>右侧使用指南</strong>：新手入门步骤、可折叠的功能教程与最佳实践。',
        '<strong>右侧最近通知 + 系统状态</strong>：API/WS/数据库/存储 4 项健康度。'
      ]},
      { name: '数据面板', ico: '📊', desc: '查看运营核心指标和趋势。', route: 'data', shot: 'data.png', fig: '图 6.2 / 数据面板。', features: [
        '<strong>统计卡片</strong>：订单数、发货成功、发货失败、待发货、AI 回复数。',
        '<strong>近 7 天趋势</strong>：发货成功/失败/AI 回复的折线图。',
        '<strong>AI 回复分布</strong>：环形图展示各账号 AI 回复占比。',
        '<strong>实时事件流</strong>：SSE 推送的业务事件实时滚动。'
      ]}
    ]
  },
  {
    id: 'account',
    title: '账号与商品',
    ico: '👥',
    color: 'green',
    modules: [
      { name: '闲鱼账号', ico: '👤', desc: '所有店铺账号的统一管理中心。', route: 'accounts', shot: 'accounts.png', fig: '图 6.3 / 闲鱼账号管理。', features: [
        '<strong>添加账号</strong>：扫码加账号（推荐）或手动添加。',
        '<strong>账号列表</strong>：显示别名、Cookie 状态、WS 状态、自动回复/发货开关。',
        '<strong>快捷操作抽屉</strong>：编辑 Cookie、刷新资料、同步商品、跳转自动回复/发货、在线消息、登录验证、重新扫码、人脸验证、自动评价、账号密码登录、统一配置。'
      ]},
      { name: '商品管理', ico: '📦', desc: '集中管理闲鱼商品，支持同步、筛选、批量操作。', route: 'products', shot: 'products.png', fig: '图 6.5 / 商品管理。', features: [
        '<strong>同步闲鱼商品</strong>：从闲鱼拉取所有在售/下架/草稿商品到系统。',
        '<strong>筛选</strong>：按账号、状态（在售/下架/草稿/已删除）、关键词。',
        '<strong>商品级开关</strong>：在售开关、自动回复开关。',
        '<strong>同步任务历史</strong>：查看每次同步的进度与结果。'
      ]},
      { name: '订单管理', ico: '🧾', desc: '查看闲鱼订单并支持手动发货。', route: 'orders', shot: 'orders.png', fig: '图 6.6 / 订单管理。', features: [
        '<strong>状态筛选</strong>：待付款 / 已付款 / 待发货 / 已发货 / 已完成 / 已关闭。',
        '<strong>同步订单</strong>：从闲鱼拉取当前账号最新订单。',
        '<strong>手动发货</strong>：在订单详情弹窗中填写发货方式（text/card）、触发时机、发货数量、发货内容并提交。'
      ]},
      { name: '发布商品', ico: '✏️', desc: '完整的闲鱼商品发布流程。', route: 'product-publish', shot: 'product-publish.png', fig: '图 6.7 / 发布商品。', features: [
        '<strong>基础信息</strong>：标题（30 字）、描述，可一键 AI 生成描述。',
        '<strong>图片</strong>：拖拽排序，最多 10 张，支持 AI 生成封面图。',
        '<strong>分类</strong>：三级级联选择，支持 AI 自动选择、搜索、收藏、最近使用。',
        '<strong>价格与规格</strong>：支持多规格组合。',
        '<strong>发货设置</strong>：包邮 / 一口价 / 无需邮寄 / 支持自提。'
      ], callout: { ico: '⚠️', text: '未生成 AI 封面图的商品严禁发布，系统会在发布前强制校验 <code>img_ai_ok == True</code>。' }},
      { name: '商机发掘', ico: '🔍', desc: '通过商品关键词搜索或店铺链接抓取竞品商机，并支持 AI 改写与一键发布。', route: 'opportunities', shot: 'opportunities.png', fig: '图 6.8 / 商机发掘。', features: [
        '<strong>两种模式</strong>：商品关键词搜索 / 店铺链接抓取。',
        '<strong>搜索速度</strong>：auto 智能降级（推荐）/ fast 直调 API / slow 浏览器拦截。',
        '<strong>结果指标</strong>：热度、总数、在售、想要、竞争度。',
        '<strong>四步流程</strong>：抓取 → AI 改写（口语化/简洁/吸引眼球）→ AI 生图（1-9 张）→ 配置并发布。'
      ]}
    ]
  },
  {
    id: 'message',
    title: '消息',
    ico: '💬',
    color: 'purple',
    modules: [
      { name: '在线消息', ico: '💬', desc: '实时会话工作台，集中处理买家咨询。', route: 'messages', shot: 'messages.png', fig: '图 6.9 / 在线消息。', features: [
        '<strong>左侧会话列表</strong>：按账号筛选、关键词搜索、未读/AI 标签过滤。',
        '<strong>中间聊天面板</strong>：发送文本/图片/商品链接、转人工、结束会话、开启自动回复、快捷模板。',
        '<strong>右侧诊断面板</strong>：商品信息、客户订单、自动回复状态（作用范围/Token 余额/账号登录）、实时 SSE 诊断。'
      ]}
    ]
  },
  {
    id: 'automation',
    title: '自动化',
    ico: '⚙️',
    color: 'orange',
    modules: [
      { name: '工作流', ico: '⚙️', desc: '可视化拖拽编排自动化业务流程，适合批量上架、跟品发布。', route: 'workflow', shot: 'workflow.png', fig: '图 6.10 / 工作流编排。', features: [
        '<strong>节点类型</strong>：TRIGGER 触发 / PRODUCT_FETCH 商品获取 / PRODUCT_FILTER 商品筛选 / PRODUCT_POLISH 商品润色 / AI 生图 / PUBLISH 发布。',
        '<strong>商品获取方式</strong>：keyword 关键词 / shop 店铺 / AI 提取关键词。',
        '<strong>发布账号</strong>：多选，可同时发布到多个账号。',
        '<strong>状态</strong>：草稿 / 已发布。发布后可在「工作流任务」查看执行记录。'
      ]},
      { name: '工作流任务', ico: '📋', desc: '查看工作流执行记录，支持终止与重试。', route: 'workflow-tasks', shot: 'workflow-tasks.png', fig: '图 6.11 / 工作流任务。', features: [
        '<strong>统计</strong>：执行记录数 / 成功 / 失败 / 进行中。',
        '<strong>详情</strong>：执行编号、触发方式、进度、节点步骤、时间线、节点产物。',
        '<strong>操作</strong>：终止执行、重试失败节点。'
      ]},
      { name: '自动发货', ico: '📦', desc: '详见第三章「24 小时自动发货完整流程」。', route: 'auto-delivery', features: [
        '<strong>统计卡片</strong>：今日成功 / 今日失败 / 待处理 / 库存不足 / 已启用。',
        '<strong>批量设置</strong>：勾选多个商品统一配置发货规则。',
        '<strong>三个时机列</strong>：付款后 / 收货后 / 好评后，分别配置独立规则。'
      ]},
      { name: '货源库', ico: '📚', desc: '统一管理文本发货内容，支持 AI 智能推荐匹配商品。', route: 'delivery-source-library', shot: 'delivery-source-library.png', fig: '图 6.12 / 货源库。', features: [
        '<strong>货源字段</strong>：标题、正文、备注、已配置商品数。',
        '<strong>AI 一键配置</strong>：让 AI 根据货源内容自动匹配适合的商品。',
        '<strong>批量配置</strong>：选择发货时机（付款后/收货后/好评后）批量绑定商品。'
      ]},
      { name: '发货声明', ico: '📢', desc: '配置全店或指定商品的发货声明文案。', route: 'delivery-statement', shot: 'delivery-statement.png', fig: '图 6.13 / 发货声明。', features: [
        '<strong>生效范围</strong>：all 全店 / specific 单独启用。',
        '<strong>变量插值</strong>：{订单编号}、{商品标题}、{买家昵称}、{发货确认链接}。',
        '<strong>预览</strong>：保存前可预览渲染效果。'
      ]},
      { name: '模板管理', ico: '📝', desc: '管理可复用的发货模板与变量。', route: 'delivery-templates', shot: 'delivery-templates.png', fig: '图 6.14 / 模板管理。', features: [
        '<strong>模板类型</strong>：付款后 / 收货后 / 好评后 / 发货声明 / 卡密发货 / 普通文本。',
        '<strong>随机模板</strong>：同一类型配多条，系统随机选一条发送，避免被风控。',
        '<strong>分段发送</strong>：用 <code>{分段}</code> 标记把一条模板拆成多条消息依次发送。'
      ]},
      { name: '发货记录', ico: '📊', desc: '追踪所有发货记录，支持重试与定时重发。', route: 'delivery-records', shot: 'delivery-records.png', fig: '图 6.15 / 发货记录。', features: [
        '<strong>状态筛选</strong>：待处理 / 进行中 / 成功 / 失败 / 缺货 / 配置错误。',
        '<strong>详情面板</strong>：订单、商品、买家、卖家、时间、状态、进度、发货内容、错误信息。',
        '<strong>操作</strong>：批量重试、导出 CSV、重新发货、安排重新发货（Cron）。'
      ]},
      { name: '卡密仓库', ico: '🔑', desc: '管理卡密库存，支持 5 种卡密类型。', route: 'card-warehouse', shot: 'card-warehouse.png', fig: '图 6.16 / 卡密仓库。', features: [
        '<strong>卡密类型</strong>：unique 唯一 / card_password 卡号+密码 / link_code 链接+提取码 / account_password 账号+密码 / custom 自定义。',
        '<strong>导入格式</strong>：粘贴或文件，支持"卡号----密码"格式批量导入。',
        '<strong>卡密状态</strong>：未使用 / 已锁定 / 已使用 / 已作废 / 异常。',
        '<strong>库存预警</strong>：低于阈值时自动通知。'
      ]},
      { name: '定时任务', ico: '⏰', desc: '管理 Cron 定时任务，支持手动运行与表达式校验。', route: 'scheduled-tasks', shot: 'scheduled-tasks.png', fig: '图 6.17 / 定时任务。', features: [
        '<strong>任务字段</strong>：任务名、账号 ID、任务类型、Cron 表达式（5-7 段）、配置 JSON、启用状态。',
        '<strong>操作</strong>：手动运行、删除、保存。',
        '<strong>典型用途</strong>：定时重发失败订单、定时同步商品、定时启动工作流。'
      ]},
      { name: '自动回复', ico: '💬', desc: '详见第五章「自动回复配置」。', route: 'auto-reply', features: [
        '<strong>总开关</strong>：一键关闭所有 AI 自动回复。',
        '<strong>作用层级</strong>：全局 / 账号 / 商品。',
        '<strong>批量操作</strong>：一键全部开启 / 批量开启 / 批量关闭。'
      ]}
    ]
  },
  {
    id: 'system',
    title: '系统',
    ico: '🛠️',
    color: 'cyan',
    modules: [
      { name: '操作日志', ico: '📜', desc: '查询与导出所有用户操作日志。', route: 'logs', shot: 'logs.png', fig: '图 6.18 / 操作日志。', features: [
        '<strong>操作类型</strong>：登录、发送消息、自动发货、自动回复、确认收货、同步商品、启动/断开连接、发布商品、卡密导入等。',
        '<strong>详情</strong>：请求参数 JSON、响应结果 JSON，可一键复制。',
        '<strong>导出</strong>：CSV 格式。'
      ]},
      { name: '滑块求解', ico: '🧩', desc: '查看滑块验证码自动求解记录。', route: 'slider-solve-records', shot: 'slider-solve-records.png', fig: '图 6.19 / 滑块求解记录。', features: [
        '<strong>触发场景</strong>：manual 手动 / manual_retry 手动重试 / ws_connect WS 连接 / cookie_keepalive Cookie 保活 / token_refresh Token 刷新。',
        '<strong>详情</strong>：账号、状态、结果、验证引擎、重试次数、事件描述、耗时、调试截图。',
        '<strong>SSE 自动刷新</strong>：800ms 防抖。'
      ]},
      { name: '反馈建议', ico: '💡', desc: '提交与跟踪产品反馈。', route: 'feedback', shot: 'feedback.png', fig: '图 6.20 / 反馈建议。', features: [
        '<strong>分类与优先级</strong>：高 / 中 / 低。',
        '<strong>状态流转</strong>：待处理 → 处理中 → 已回复。',
        '<strong>桥接同步</strong>：本地提交会同步到商业版后端。'
      ]},
      { name: '通知设置', ico: '🔔', desc: '统一管理通知渠道与触发规则。', route: 'settings-notify', shot: 'notify-settings.png', fig: '图 6.21 / 通知设置。', features: [
        '<strong>渠道类型</strong>：SMTP 邮件 / 飞书自建应用 / 自定义。',
        '<strong>SMTP 配置</strong>：Host / Port / User / Pass / FromEmail / Receiver。',
        '<strong>飞书自建应用</strong>：AppID / AppSecret / VerificationToken / EncryptKey / ReceiveId / ReceiveIdType。',
        '<strong>触发规则</strong>：按事件类型配置何时推送。',
        '<strong>投递健康度</strong>：投递记录、异常、平均耗时一览。'
      ]},
      { name: '系统设置', ico: '⚙️', desc: '包含 AI 客服配置、商品操作、关于三个 Tab。', route: 'settings-ai-cs', features: [
        '<strong>AI 客服配置</strong>：详见第四章。',
        '<strong>商品操作</strong>：库存归零自动下架开关（默认开启）。',
        '<strong>关于</strong>：版本号、构建日期、更新日志、服务支持、协议链接。'
      ]}
    ]
  },
  {
    id: 'profile',
    title: '会员与个人',
    ico: '👑',
    color: 'pink',
    modules: [
      { name: 'VIP 会员中心', ico: '👑', desc: '查看并购买 VIP 套餐。', route: 'vip', shot: 'vip.png', fig: '图 6.22 / VIP 会员中心。', features: [
        '<strong>套餐等级</strong>：normal / vip / svp，功能权益逐级递增。',
        '<strong>权益对比</strong>：可绑定闲鱼账号数、可管理商品数、AI 回复额度、自动发货、自动化发布工作流。',
        '<strong>支付</strong>：点击"立即升级"打开支付弹窗。'
      ]},
      { name: '个人中心', ico: '👤', desc: '管理账户资料、安全设置与会员权益。', route: 'profile', shot: 'profile.png', fig: '图 6.23 / 个人中心。', features: [
        '<strong>总览 Tab</strong>：套餐、邮箱/手机验证状态、Token 余额（含充值入口）、账户信息、快捷操作。',
        '<strong>账号安全 Tab</strong>：安全等级、密码、手机号验证、邮箱验证状态。'
      ]}
    ]
  }
]

// FAQ
const faqItems = [
  { q: '为什么我的账号显示 WS 离线？', a: '通常是 Cookie 过期或触发闲鱼滑块风控。进入「闲鱼账号」详情点击"刷新 Cookie"或"登录验证"，必要时重新扫码授权。如果触发滑块，系统会自动求解，可在「滑块求解」查看结果。' },
  { q: '自动发货没触发，订单一直是"待处理"怎么办？', a: '按以下顺序排查：① WS 是否在线（闲鱼账号）；② 商品是否配置了对应时机的发货规则（自动发货）；③ 卡密库存或货源是否充足（卡密仓库/货源库）；④ 在「发货记录」看失败原因。常见原因：缺货、配置错误、WS 断开。' },
  { q: 'AI 客服为什么不回复？', a: '排查顺序：① AI 客服配置是否启用并保存（系统设置 → AI 客服配置）；② 自动回复总开关是否开启（自动回复）；③ 对应账号/商品是否在作用层级范围内；④ Token 余额是否充足（个人中心）；⑤ 接待模式是否为 manual（manual 模式 AI 不自动回）。' },
  { q: '商机发掘的 fast / slow / auto 有什么区别？', a: 'fast 直调闲鱼 API 速度最快（约 1 秒）但可能触发风控；slow 通过浏览器拦截响应最稳定（2-3 秒）；auto 默认先 fast 失败自动降级 slow，是最推荐的模式。' },
  { q: '发布商品时提示"未生成 AI 封面图"怎么办？', a: '这是强制规则。在发布流程的图片步骤必须使用"AI 生成封面图"功能至少生成一张，系统校验 <code>img_ai_ok == True</code> 后才允许发布。' },
  { q: '卡密库存不足时系统会怎么处理？', a: '在「自动发货」配置时可以设置"库存预警阈值"和"自动停用"开关。库存低于阈值会发通知；如果开启自动停用，系统会停止该商品的自动发货，避免超卖。' },
  { q: '工作流和自动发货是什么关系？', a: '工作流负责"商品上架前的批量处理"（抓取 → 改写 → 生图 → 发布），自动发货负责"商品上架后的订单履约"（付款 → 发货 → 确认收货）。两者是上下游关系，配合使用可以做到从跟品到交付的完全自动化。' },
  { q: 'Token 余额用完了会怎样？', a: 'AI 客服会自动降级：不再调用 AI 模型，改为不回复或仅回退模板，不会产生超额费用。建议在「个人中心」设置余额预警或及时充值。' }
]

function shot(filename) {
  return `/xya/manual/${filename}`
}

function onShotError(e) {
  const img = e.target
  if (img.dataset.fallback === '1') return
  img.dataset.fallback = '1'
  img.alt = '截图准备中'
  img.src = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="220" viewBox="0 0 1280 220">
      <rect width="1280" height="220" fill="#f5f8fc"/>
      <rect x="1" y="1" width="1278" height="218" fill="none" stroke="#d8e1ee" stroke-width="1" stroke-dasharray="6 4"/>
      <text x="640" y="115" font-family="PingFang SC, Microsoft YaHei, sans-serif" font-size="16" fill="#94a3b8" text-anchor="middle">截图准备中，请稍后刷新页面</text>
    </svg>`
  )
}

function switchSection(id) {
  activeSection.value = id
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function toggleFaq(idx) {
  openFaq.value = openFaq.value === idx ? -1 : idx
}

onMounted(() => {
  collectLightboxImages()
  window.addEventListener('keydown', onLightboxKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onLightboxKeydown)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.manual-page { width: 100%; }

/* Hero */
.manual-hero {
  position: relative;
  overflow: hidden;
  border-radius: 24px;
  padding: 28px 32px 24px;
  margin-bottom: 20px;
  border: 1px solid rgba(220, 232, 248, 0.8);
  background: linear-gradient(135deg, #f0f6ff 0%, #f5f0ff 50%, #eef8ff 100%);
  box-shadow: 0 20px 50px rgba(31, 53, 94, 0.07);
}
.hero-bg-deco { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.hero-blob {
  position: absolute; border-radius: 50%; filter: blur(60px); opacity: 0.5;
}
.hero-blob-1 {
  width: 280px; height: 280px;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.18), transparent 70%);
  top: -80px; right: -40px;
}
.hero-blob-2 {
  width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.15), transparent 70%);
  bottom: -60px; left: 30%;
}
.hero-blob-3 {
  width: 160px; height: 160px;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.12), transparent 70%);
  top: 40%; right: 20%;
}
.hero-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(37, 99, 235, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(37, 99, 235, 0.03) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse at 50% 50%, black 20%, transparent 70%);
}
.hero-inner { position: relative; z-index: 1; }

.hero-breadcrumb {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #7a879e; margin-bottom: 14px;
}
.crumb-btn {
  border: 0; background: transparent; padding: 0;
  color: #2563eb; cursor: pointer; font-size: 12px; font-weight: 600;
}
.crumb-btn:hover { text-decoration: underline; }
.crumb-sep { color: #c0cce0; }
.crumb-current { color: #445874; font-weight: 600; }

.hero-brand-row { display: flex; align-items: flex-start; gap: 22px; }
.brand-mark {
  width: 72px; height: 72px; position: relative; flex-shrink: 0;
  margin-top: 4px;
}
.brand-mark span {
  position: absolute; left: 29px; top: 0;
  width: 20px; height: 72px; border-radius: 14px;
  background: linear-gradient(180deg, #0d7fff, #16b7ff);
  transform: rotate(42deg);
  box-shadow: 0 10px 28px rgba(13, 107, 255, 0.3);
}
.brand-mark span + span { transform: rotate(-42deg); background: linear-gradient(180deg, #25a5ff, #0362f4); }
.hero-text { min-width: 0; flex: 1; }
.hero-badges { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.hero-badges :deep(.badge) { font-size: 11px; }
.hero-text h1 {
  margin: 0; font-size: 32px; font-weight: 900; color: #13213d;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, #13213d, #2563eb);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-desc {
  margin: 10px 0 0; color: #4a5a73; font-size: 14px; line-height: 1.8; max-width: 780px;
}
.hero-meta { display: flex; align-items: center; gap: 12px; margin-top: 14px; flex-wrap: wrap; }
.hero-meta-item {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: #5a6b86; font-weight: 600;
  padding: 4px 10px; border-radius: 20px;
  background: rgba(255,255,255,0.7); border: 1px solid rgba(200,215,240,0.5);
}
.hero-meta-divider { display: none; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-green { background: #22c55e; box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.15); }

/* 快捷入口 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 22px;
}
.qa-card {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(220, 232, 248, 0.9);
  border-radius: 16px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(8px);
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.qa-card:hover {
  transform: translateY(-2px);
  border-color: #c9dcff;
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.1);
}
.qa-primary {
  background: linear-gradient(135deg, #2563eb, #4f7eff);
  border-color: transparent;
  color: #fff;
}
.qa-primary:hover {
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.3);
}
.qa-primary .qa-text b, .qa-primary .qa-text em { color: #fff; }
.qa-ico { font-size: 24px; flex-shrink: 0; }
.qa-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.qa-text b { font-size: 13px; color: #13213d; font-weight: 800; }
.qa-text em { font-size: 11px; color: #7a879e; font-style: normal; }
.qa-primary .qa-text em { color: rgba(255,255,255,0.8); }

/* 布局 */
.manual-layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}
.manual-toc {
  position: sticky; top: 88px;
}
.toc-inner {
  background: #fff;
  border: 1px solid #e8eef8;
  border-radius: 18px;
  padding: 18px 12px 14px;
  box-shadow: 0 8px 24px rgba(31, 53, 94, 0.05);
  display: flex; flex-direction: column; gap: 2px;
}
.toc-head {
  display: flex; align-items: center; gap: 8px;
  padding: 0 8px 12px;
  border-bottom: 1px solid #f0f4fa;
  margin-bottom: 6px;
}
.toc-title-icon { font-size: 16px; }
.toc-title {
  font-size: 13px; font-weight: 800; color: #1d2d4b;
}
.toc-link {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px;
  border-radius: 10px;
  color: #5a6b86;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.18s ease;
  cursor: pointer;
}
.toc-link:hover { background: #f5f8fc; color: #1d2d4b; }
.toc-link.active {
  background: linear-gradient(90deg, #eef4ff, #f8faff);
  color: #2563eb;
}
.toc-link.active .toc-num {
  background: #2563eb; color: #fff;
}
.toc-num {
  font-size: 10px; font-weight: 800;
  color: #94a3b8;
  background: #f0f4fa;
  border-radius: 6px;
  padding: 2px 5px;
  flex-shrink: 0;
  transition: all 0.18s ease;
}
.toc-label { flex: 1; min-width: 0; }
.toc-foot {
  margin-top: 8px; padding-top: 8px;
  border-top: 1px solid #f0f4fa;
}
.toc-backtop {
  width: 100%; border: 0; background: transparent;
  padding: 8px 10px;
  color: #94a3b8; font-size: 12px; font-weight: 600;
  cursor: pointer;
  border-radius: 8px;
  text-align: left;
  transition: all 0.18s ease;
}
.toc-backtop:hover { background: #f5f8fc; color: #2563eb; }

.manual-content {
  min-width: 0;
  display: flex; flex-direction: column; gap: 20px;
}
.manual-section {
  animation: sectionFadeIn 0.3s ease;
}
@keyframes sectionFadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.manual-section :deep(.card-panel) {
  border-radius: 20px;
  padding: 28px 30px;
  box-shadow: 0 8px 30px rgba(32, 68, 132, 0.05);
  border: 1px solid #eef2f8;
  background: #fff;
}
.manual-section :deep(.panel-head) {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f4fa;
}
.manual-section :deep(.panel-head h3) {
  font-size: 19px; color: #13213d; font-weight: 800;
}
.manual-section :deep(.panel-head p) {
  font-size: 13px; color: #7a879e; margin-top: 4px;
}

.section-body { font-size: 14px; color: #3a4a63; line-height: 1.8; }
.section-body strong { color: #1d2d4b; }

/* 章节标题 */
.sec-head {
  display: inline-flex; align-items: center; gap: 12px;
}
.sec-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px;
  border-radius: 9px;
  background: linear-gradient(135deg, #2563eb, #4f7eff);
  color: #fff;
  font-size: 13px; font-weight: 900;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.2);
}

/* Lead card */
.lead-card {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 16px 18px;
  border-radius: 14px;
  background: linear-gradient(135deg, #f0f6ff, #f5f9ff);
  border: 1px solid #d4e3ff;
  margin-bottom: 16px;
}
.lead-card-green {
  background: linear-gradient(135deg, #ecfdf3, #f0fdf4);
  border-color: #bbf7d0;
}
.lead-card-purple {
  background: linear-gradient(135deg, #f4efff, #faf5ff);
  border-color: #ddd6fe;
}
.lead-ico { font-size: 22px; flex-shrink: 0; margin-top: 1px; }
.lead { margin: 0; font-size: 15px; color: #2c3d59; line-height: 1.8; }

/* 流程可视化 */
.flow-visual {
  display: flex; align-items: center; flex-wrap: wrap;
  gap: 4px;
  padding: 18px 20px;
  border-radius: 16px;
  background: linear-gradient(135deg, #f0fdf4, #ecfdf3, #f0fdf4);
  border: 1px solid #bbf7d0;
  margin: 16px 0 20px;
}
.flow-step { display: flex; align-items: center; gap: 4px; }
.flow-node {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #86efac;
  font-size: 12px; font-weight: 700; color: #166534;
  box-shadow: 0 2px 8px rgba(34, 197, 94, 0.08);
}
.flow-ico { font-size: 14px; }
.flow-connector {
  color: #22c55e; font-weight: 900; font-size: 14px;
  padding: 0 2px;
}

/* 步骤时间线 */
.step-timeline {
  margin: 16px 0 0;
  padding: 0;
}
.step-item {
  display: flex; gap: 16px;
  padding: 0 0 20px 0;
  position: relative;
  transition: transform 0.2s ease;
}
.step-item:hover {
  transform: translateX(2px);
}
.step-item:last-child { padding-bottom: 0; }
.step-marker {
  display: flex; flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 36px;
}
.step-circle {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #4f7eff);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
  flex-shrink: 0;
  z-index: 1;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.step-item:hover .step-circle {
  transform: scale(1.08);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.35);
}
.step-circle-green {
  background: linear-gradient(135deg, #22c55e, #4ade80);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.25);
}
.step-item:hover .step-circle-green {
  box-shadow: 0 6px 16px rgba(34, 197, 94, 0.35);
}
.step-circle-purple {
  background: linear-gradient(135deg, #8b5cf6, #a78bfa);
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.25);
}
.step-item:hover .step-circle-purple {
  box-shadow: 0 6px 16px rgba(139, 92, 246, 0.35);
}
.step-circle-blue {
  background: linear-gradient(135deg, #06b6d4, #22d3ee);
  box-shadow: 0 4px 12px rgba(6, 182, 212, 0.25);
}
.step-item:hover .step-circle-blue {
  box-shadow: 0 6px 16px rgba(6, 182, 212, 0.35);
}
.step-line {
  width: 2px; flex: 1;
  background: linear-gradient(180deg, #dbeafe, #f0f4fa);
  margin: 4px 0;
  min-height: 20px;
}
.step-body { flex: 1; min-width: 0; padding-top: 4px; }
.step-title-row { margin-bottom: 6px; }
.step-body h4 {
  margin: 0; font-size: 15px; font-weight: 800; color: #1d2d4b;
}
.step-body p { margin: 4px 0 6px; color: #445874; line-height: 1.75; }
.step-body ul { margin: 6px 0; }

.step-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
.step-action {
  display: inline-flex; align-items: center; gap: 4px;
  border: 1px solid #d4e3ff;
  padding: 6px 14px;
  border-radius: 8px;
  background: #eef4ff;
  color: #2563eb;
  font-size: 12px; font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
  margin-top: 4px;
}
.step-action:hover { background: #2563eb; color: #fff; border-color: #2563eb; }
.step-action-purple {
  border-color: #ddd6fe; background: #f4efff; color: #7c3aed;
}
.step-action-purple:hover { background: #7c3aed; color: #fff; border-color: #7c3aed; }
.step-action .arrow { font-size: 14px; font-weight: 800; }

/* 列表 */
.bullet-list {
  list-style: none; margin: 6px 0; padding: 0;
}
.bullet-list li {
  position: relative;
  padding-left: 20px;
  margin: 5px 0;
  color: #445874; line-height: 1.75;
}
.bullet-list li::before {
  content: '';
  position: absolute; left: 4px; top: 11px;
  width: 6px; height: 6px;
  border-radius: 2px;
  background: #2563eb;
}
.bullet-list code {
  background: #eef4ff; color: #2563eb;
  padding: 2px 7px; border-radius: 5px;
  font-size: 12px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

/* 功能特性胶囊 */
.feature-pill-row {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin: 14px 0 18px;
}
.feature-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 7px 14px;
  border-radius: 999px;
  font-size: 12px; font-weight: 600;
  border: 1px solid transparent;
}
.feature-pill strong { margin-right: 2px; }
.fp-blue { background: #eef4ff; color: #1d4ed8; border-color: #bfdbfe; }
.fp-purple { background: #f4efff; color: #7c3aed; border-color: #ddd6fe; }
.fp-green { background: #ecfdf3; color: #15803d; border-color: #bbf7d0; }
.fp-orange { background: #fff7ed; color: #c2410c; border-color: #fed7aa; }
.fp-pink { background: #fdf2f8; color: #be185d; border-color: #fbcfe8; }
.fp-cyan { background: #ecfeff; color: #0e7490; border-color: #a5f3fc; }

/* 截图 */
.shot-figure {
  margin: 20px auto 8px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e2e8f3;
  background: #f8fafc;
  box-shadow: 0 6px 18px rgba(31, 53, 94, 0.06);
  transition: box-shadow 0.25s ease, transform 0.25s ease;
  max-width: 50%;
}
.shot-figure:hover {
  box-shadow: 0 10px 28px rgba(31, 53, 94, 0.1);
  transform: translateY(-1px);
}
.shot-img-wrap {
  position: relative;
  cursor: zoom-in;
  overflow: hidden;
}
.shot-img-wrap img {
  display: block; width: 100%; height: auto;
  background: #f5f8fc;
  transition: transform 0.3s ease;
}
.shot-img-wrap:hover img {
  transform: scale(1.01);
}
.shot-zoom-hint {
  position: absolute;
  top: 12px; right: 12px;
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 12px;
  background: rgba(19, 33, 61, 0.75);
  color: #fff;
  font-size: 12px; font-weight: 600;
  border-radius: 20px;
  backdrop-filter: blur(8px);
  opacity: 0;
  transform: translateY(-4px);
  transition: opacity 0.2s ease, transform 0.2s ease;
  pointer-events: none;
}
.shot-zoom-hint span { font-size: 14px; }
.shot-img-wrap:hover .shot-zoom-hint {
  opacity: 1;
  transform: translateY(0);
}
.shot-figure figcaption {
  padding: 10px 16px;
  font-size: 12px; color: #7a879e;
  background: linear-gradient(180deg, #f8fafc, #f5f8fc);
  border-top: 1px solid #e8eef8;
  font-weight: 500;
}
.shot-figure-sm { margin: 14px 0 4px; }

/* Callout */
.callout {
  display: flex; gap: 12px;
  margin: 16px 0 4px;
  padding: 14px 18px;
  border-radius: 14px;
  font-size: 13px; line-height: 1.7;
  align-items: flex-start;
}
.callout-ico { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
.callout-body { flex: 1; }
.callout-body strong { display: block; margin-bottom: 4px; font-size: 13px; }
.callout-body p { margin: 0; color: #445874; }
.callout-body ul { margin: 6px 0 0; padding-left: 18px; }
.callout-body ul li { margin: 4px 0; color: #445874; }
.callout-tip {
  background: linear-gradient(135deg, #eff6ff, #f0f7ff);
  border: 1px solid #bfdbfe;
}
.callout-tip .callout-body strong { color: #1d4ed8; }
.callout-warn {
  background: linear-gradient(135deg, #fffbeb, #fff7ed);
  border: 1px solid #fed7aa;
}
.callout-warn .callout-body strong { color: #c2410c; }
.callout code {
  background: rgba(255,255,255,0.7); color: #c2410c;
  padding: 2px 6px; border-radius: 4px; font-size: 12px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

/* 模块组 */
.module-group { margin-top: 4px; }
.module-group-title {
  display: flex; align-items: center; gap: 10px;
  margin: 24px 0 12px;
  padding: 12px 16px;
  font-size: 16px; font-weight: 800; color: #1d2d4b;
  background: linear-gradient(90deg, #f5f9ff, #fafcff);
  border-radius: 12px;
  scroll-margin-top: 100px;
}
.module-group-title:first-of-type { margin-top: 4px; }
.mgt-ico { font-size: 20px; }

/* 模块卡片 */
.module-card {
  position: relative;
  display: flex;
  padding: 18px 0 20px;
  border-bottom: 1px solid #f0f4fa;
  scroll-margin-top: 100px;
}
.module-card:last-child { border-bottom: 0; }
.mc-accent {
  position: absolute; left: 0; top: 18px; bottom: 20px;
  width: 4px; border-radius: 4px;
}
.mc-blue .mc-accent { background: linear-gradient(180deg, #3b82f6, #93c5fd); }
.mc-green .mc-accent { background: linear-gradient(180deg, #22c55e, #86efac); }
.mc-purple .mc-accent { background: linear-gradient(180deg, #8b5cf6, #c4b5fd); }
.mc-orange .mc-accent { background: linear-gradient(180deg, #f97316, #fdba74); }
.mc-cyan .mc-accent { background: linear-gradient(180deg, #06b6d4, #67e8f9); }
.mc-pink .mc-accent { background: linear-gradient(180deg, #ec4899, #f9a8d4); }
.mc-body { flex: 1; padding-left: 18px; }
.mc-body header h4 {
  margin: 0 0 4px;
  font-size: 15px; font-weight: 800; color: #13213d;
  display: flex; align-items: center; gap: 8px;
}
.mc-ico { font-size: 16px; }
.mc-body header p {
  margin: 0 0 8px; color: #6c7a93; font-size: 13px; line-height: 1.6;
}
.nav-jump {
  border: 0; padding: 0; background: transparent;
  color: #2563eb; font-size: 12px; font-weight: 700;
  cursor: pointer;
  margin-left: auto;
  padding: 3px 10px; border-radius: 6px;
  transition: all 0.18s ease;
}
.nav-jump:hover { background: #eef4ff; color: #1d4ed8; text-decoration: none; }
.mc-callout {
  display: flex; align-items: flex-start; gap: 8px;
  margin: 10px 0 4px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  font-size: 12px; color: #9a3412; line-height: 1.6;
}
.mc-callout-ico { font-size: 14px; flex-shrink: 0; margin-top: 1px; }
.mc-callout code {
  background: rgba(255,255,255,0.6); color: #c2410c;
  padding: 1px 5px; border-radius: 4px; font-size: 11px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

/* FAQ */
.faq-item {
  border: 1px solid #eef2f8;
  border-radius: 12px;
  margin-bottom: 8px;
  overflow: hidden;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.faq-item.open {
  border-color: #c9dcff;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.08);
}
.faq-q {
  width: 100%;
  display: flex; align-items: center; gap: 12px;
  padding: 14px 18px;
  border: 0; background: transparent;
  cursor: pointer;
  text-align: left;
  font-size: 14px; font-weight: 700; color: #1d2d4b;
  transition: background 0.18s ease;
}
.faq-q:hover { background: #f8fafc; }
.faq-item.open .faq-q { background: #f5f9ff; }
.faq-q-num {
  flex-shrink: 0;
  width: 26px; height: 26px;
  border-radius: 8px;
  background: #eef4ff;
  color: #2563eb;
  font-size: 11px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
}
.faq-item.open .faq-q-num {
  background: #2563eb; color: #fff;
}
.faq-q-text { flex: 1; }
.faq-toggle {
  flex-shrink: 0;
  width: 24px; height: 24px;
  border-radius: 50%;
  background: #f0f4fa; color: #5a6b86;
  font-size: 16px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s ease;
}
.faq-item.open .faq-toggle {
  background: #2563eb; color: #fff; transform: rotate(180deg);
}
.faq-a {
  display: flex; gap: 12px;
  padding: 0 18px 14px;
  font-size: 13px; color: #445874; line-height: 1.8;
  animation: faqSlide 0.25s ease;
}
@keyframes faqSlide {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
.faq-a-label {
  flex-shrink: 0;
  width: 26px; height: 26px;
  border-radius: 8px;
  background: #ecfdf3;
  color: #16a34a;
  font-size: 11px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
  margin-top: 0;
}
.faq-a p { margin: 0; flex: 1; }
.faq-a code {
  background: #eef4ff; color: #2563eb;
  padding: 2px 6px; border-radius: 4px; font-size: 12px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

/* 支持入口 */
.support-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 14px 0 6px;
}
.support-tile {
  display: flex; align-items: center; gap: 14px;
  padding: 18px;
  border: 1px solid #e8eef8;
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}
.support-tile:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(31, 53, 94, 0.08);
}
.st-blue:hover { border-color: #bfdbfe; background: linear-gradient(135deg, #fff, #eff6ff); }
.st-green:hover { border-color: #bbf7d0; background: linear-gradient(135deg, #fff, #ecfdf3); }
.st-orange:hover { border-color: #fed7aa; background: linear-gradient(135deg, #fff, #fff7ed); }
.support-ico {
  width: 46px; height: 46px;
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.st-blue .support-ico { background: #eef4ff; }
.st-green .support-ico { background: #ecfdf3; }
.st-orange .support-ico { background: #fff7ed; }
.support-text { flex: 1; min-width: 0; }
.support-text b { display: block; font-size: 14px; color: #13213d; font-weight: 800; }
.support-text p { margin: 3px 0 0; font-size: 12px; color: #7a879e; line-height: 1.5; }
.support-arrow {
  font-size: 18px; color: #c0cce0; font-weight: 700;
  transition: transform 0.2s ease, color 0.2s ease;
}
.support-tile:hover .support-arrow { color: #2563eb; transform: translateX(3px); }

/* 页脚 */
.manual-footer {
  display: flex; align-items: center; justify-content: center;
  padding: 24px 4px 16px;
  color: #94a3b8; font-size: 12px;
  text-align: center;
}

/* 章节导航 */
.section-nav {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #f0f4fa;
}
.sn-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border: 1px solid #e8eef8;
  border-radius: 14px;
  background: #fff;
  cursor: pointer;
  transition: all 0.22s ease;
  text-align: left;
}
.sn-btn:hover {
  border-color: #c9dcff;
  background: linear-gradient(135deg, #f8faff, #eef4ff);
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.08);
  transform: translateY(-1px);
}
.sn-prev { justify-content: flex-start; }
.sn-next { justify-content: flex-end; text-align: right; }
.sn-btn.sn-next .sn-text { align-items: flex-end; }
.sn-arrow {
  font-size: 24px;
  font-weight: 700;
  color: #94a3b8;
  transition: all 0.22s ease;
  flex-shrink: 0;
}
.sn-btn:hover .sn-arrow { color: #2563eb; }
.sn-prev:hover .sn-arrow { transform: translateX(-3px); }
.sn-next:hover .sn-arrow { transform: translateX(3px); }
.sn-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.sn-label {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.sn-btn:hover .sn-label { color: #2563eb; }
.sn-title {
  font-size: 13px;
  font-weight: 700;
  color: #1d2d4b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* Lightbox */
.lightbox-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  animation: lightboxFadeIn 0.25s ease;
}
@keyframes lightboxFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.lightbox-close {
  position: absolute;
  top: 20px;
  right: 24px;
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 28px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  z-index: 10;
  line-height: 1;
}
.lightbox-close:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: rotate(90deg);
}
.lightbox-prev,
.lightbox-next {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 52px;
  height: 52px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 32px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  z-index: 10;
  line-height: 1;
}
.lightbox-prev { left: 24px; }
.lightbox-next { right: 24px; }
.lightbox-prev:hover,
.lightbox-next:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: translateY(-50%) scale(1.1);
}
.lightbox-content {
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: lightboxZoom 0.28s ease;
}
@keyframes lightboxZoom {
  from { opacity: 0; transform: scale(0.92); }
  to { opacity: 1; transform: scale(1); }
}
.lightbox-content img {
  max-width: 100%;
  max-height: 85vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.5);
}
.lightbox-counter {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 20px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  border-radius: 20px;
  backdrop-filter: blur(8px);
}

/* 响应式 */
@media (max-width: 1200px) {
  .manual-layout { grid-template-columns: 200px minmax(0, 1fr); gap: 16px; }
  .quick-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .shot-figure { max-width: 65%; }
}
@media (max-width: 1024px) {
  .manual-layout { grid-template-columns: 1fr; }
  .manual-toc { position: static; }
  .toc-inner {
    flex-direction: row; flex-wrap: wrap;
    overflow-x: auto; padding: 12px;
  }
  .toc-head { width: 100%; border-bottom: 0; padding-bottom: 6px; margin-bottom: 4px; }
  .toc-foot { display: none; }
  .toc-link { white-space: nowrap; }
  .shot-figure { max-width: 80%; }
}
@media (max-width: 768px) {
  .support-grid { grid-template-columns: 1fr; }
  .hero-brand-row { flex-direction: column; align-items: flex-start; gap: 14px; }
  .manual-hero { padding: 20px; border-radius: 18px; }
  .manual-section :deep(.card-panel) { padding: 18px; border-radius: 16px; }
  .quick-actions { grid-template-columns: 1fr; }
  .hero-text h1 { font-size: 26px; }
  .flow-visual { padding: 14px; }
  .flow-node { padding: 6px 10px; font-size: 11px; }
  .section-nav { flex-direction: column; gap: 8px; }
  .sn-btn { padding: 12px 14px; }
  .sn-title { font-size: 12px; }
  .lightbox-overlay { padding: 16px; }
  .lightbox-prev, .lightbox-next { width: 40px; height: 40px; font-size: 24px; }
  .lightbox-prev { left: 10px; }
  .lightbox-next { right: 10px; }
  .lightbox-close { top: 12px; right: 12px; width: 38px; height: 38px; font-size: 24px; }
  .shot-zoom-hint { opacity: 1; transform: translateY(0); font-size: 11px; padding: 4px 10px; }
  .shot-figure { max-width: 100%; }
}
</style>
