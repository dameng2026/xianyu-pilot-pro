<template>
  <div class="manual-page">
    <!-- 顶部 Hero -->
    <section class="manual-hero">
      <div class="hero-bg"></div>
      <div class="hero-inner">
        <div class="hero-brand">
          <div class="brand-mark">
            <span></span>
            <span></span>
          </div>
          <div class="hero-text">
            <div class="hero-title-row">
              <h1>使用手册</h1>
              <Badge type="blue">v{{ APP_VERSION }}</Badge>
              <Badge>小白也能轻松上手</Badge>
            </div>
            <p>从零开始，一步步带你完成闲鱼店铺的自动化运营：账号接入、商品发布、24 小时自动发货、AI 自动客服、自动回复、数据看板。</p>
            <div class="hero-meta">
              <span class="hero-meta-item"><i class="dot dot-green"></i>无需编程基础</span>
              <span class="hero-meta-divider"></span>
              <span class="hero-meta-item">所有功能均可通过界面配置</span>
              <span class="hero-meta-divider"></span>
              <span class="hero-meta-item">配套真实页面截图</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 主体：左目录 + 右内容 -->
    <div class="manual-layout">
      <aside class="manual-toc">
        <nav class="toc-inner">
          <div class="toc-title">目录</div>
          <a v-for="sec in sections" :key="sec.id" :href="`#${sec.id}`" :class="['toc-link', { active: activeSection === sec.id }]" @click.prevent="scrollToSection(sec.id)">{{ sec.label }}</a>
        </nav>
      </aside>

      <div class="manual-content">
        <!-- 一、30秒快速了解 -->
        <section id="overview" class="manual-section">
          <CardPanel title="一、30 秒快速了解闲鱼助手" desc="它是什么、能帮你做什么、为什么能省一半人力">
            <div class="section-body">
              <p class="lead">闲鱼助手是一站式闲鱼店铺自动化运营平台。把店铺接进来之后，<strong>商品发布、买家消息、订单发货</strong>都可以交给系统自动完成，你只需要看着数据面板盯结果。</p>
              <div class="feature-pill-row">
                <span class="feature-pill"><strong>多账号</strong>统一管理</span>
                <span class="feature-pill"><strong>AI 自动客服</strong>24 小时在线</span>
                <span class="feature-pill"><strong>自动发货</strong>付款即发</span>
                <span class="feature-pill"><strong>工作流</strong>批量上架</span>
                <span class="feature-pill"><strong>商机发掘</strong>跟品爆款</span>
                <span class="feature-pill"><strong>数据看板</strong>实时洞察</span>
              </div>
              <figure class="shot-figure">
                <img :src="shot('dashboard.png')" alt="导航面板首页截图" loading="lazy" @error="onShotError" />
                <figcaption>图 1.1 / 登录后第一眼看到的导航面板，左侧是功能菜单，顶部是常用入口。</figcaption>
              </figure>
              <div class="callout callout-info">
                <strong>适合谁用？</strong>
                <p>闲鱼个人卖家、卡密虚拟商品卖家、多店铺矩阵运营者，每天有大量重复的发货和客服工作需要自动化。</p>
              </div>
            </div>
          </CardPanel>
        </section>

        <!-- 二、新用户从零开始的 5 步 -->
        <section id="getting-started" class="manual-section">
          <CardPanel title="二、新用户从零开始的 5 步" desc="按照这个顺序操作，10 分钟内完成基础接入">
            <div class="section-body">
              <ol class="step-list">
                <li>
                  <div class="step-head"><span class="step-num">1</span><strong>注册账号并登录</strong></div>
                  <p>在登录页使用邮箱验证码或账号密码登录。首次进入会进入"导航面板"首页，看到快速开始入口。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">2</span><strong>添加闲鱼店铺账号</strong></div>
                  <p>进入「闲鱼账号」页面，点击右上角"扫码加账号"，用闲鱼 App 扫描二维码完成授权。授权成功后账号会出现在列表里。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'accounts')">前往闲鱼账号 ›</button>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">3</span><strong>保持 WebSocket 在线</strong></div>
                  <p>进入「连接管理」页面，确认账号的 WS 状态显示为"在线"。WS 在线是接收消息和触发自动化的前提。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'connections')">前往连接管理 ›</button>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">4</span><strong>同步或发布商品</strong></div>
                  <p>进入「商品管理」点击"同步闲鱼商品"把已有商品拉到系统；或进入「发布商品」新建商品。商品是后续订单、发货、客服的载体。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'products')">前往商品管理 ›</button>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">5</span><strong>开启自动化</strong></div>
                  <p>按需进入「自动发货」「自动回复」「工作流」开启自动化规则。后面的章节会逐个详细讲解。</p>
                </li>
              </ol>
              <figure class="shot-figure">
                <img :src="shot('accounts.png')" alt="闲鱼账号管理截图" loading="lazy" @error="onShotError" />
                <figcaption>图 2.1 / 「闲鱼账号」页面：所有账号的 Cookie、WS 状态、自动回复/发货开关都集中在这里。</figcaption>
              </figure>
            </div>
          </CardPanel>
        </section>

        <!-- 三、24 小时自动发货完整流程 -->
        <section id="auto-delivery-flow" class="manual-section">
          <CardPanel title="三、从零实现 24 小时自动发货" desc="买家付款 → 系统自动发卡密/文本 → 自动确认收货，全程无人值守">
            <div class="section-body">
              <p class="lead">自动发货是闲鱼助手最核心的能力之一。只要按下述 7 步配置完成，买家付款后系统会在几秒内自动把发货内容发到会话里。</p>

              <div class="flow-diagram">
                <span class="flow-node">买家付款</span>
                <span class="flow-arrow">→</span>
                <span class="flow-node">订单同步</span>
                <span class="flow-arrow">→</span>
                <span class="flow-node">匹配发货规则</span>
                <span class="flow-arrow">→</span>
                <span class="flow-node">取卡密 / 取文本</span>
                <span class="flow-arrow">→</span>
                <span class="flow-node">发送会话</span>
                <span class="flow-arrow">→</span>
                <span class="flow-node">记录发货日志</span>
              </div>

              <ol class="step-list">
                <li>
                  <div class="step-head"><span class="step-num">1</span><strong>添加账号并保持 WS 在线</strong></div>
                  <p>参考"新用户 5 步"的步骤 2-3。WS 必须在线，否则系统收不到订单事件。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">2</span><strong>同步商品到商品管理</strong></div>
                  <p>在「商品管理」点击"同步闲鱼商品"。同步成功后，每个商品都会有一个商品 ID，自动发货规则按商品维度配置。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">3</span><strong>准备发货内容</strong></div>
                  <p>发货内容有两种形式，二选一即可：</p>
                  <ul class="bullet-list">
                    <li><strong>卡密发货</strong>：进入「卡密仓库」新建卡密组，批量导入卡密（支持"卡号----密码"格式）。系统每次发货会自动取一个未使用的卡密。</li>
                    <li><strong>文本发货</strong>：进入「货源库」新增货源，填写标题和正文。正文里可以插入变量，适合发链接、提取码、网盘地址等。</li>
                  </ul>
                  <div class="action-row">
                    <button class="inline-link" type="button" @click="$emit('navigate', 'card-warehouse')">前往卡密仓库 ›</button>
                    <button class="inline-link" type="button" @click="$emit('navigate', 'delivery-source-library')">前往货源库 ›</button>
                  </div>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">4</span><strong>配置自动发货规则</strong></div>
                  <p>进入「自动发货」页面，找到要配置的商品，点击对应时机列（付款后 / 收货后 / 好评后）的按钮，在弹窗里：</p>
                  <ul class="bullet-list">
                    <li>开启"启用"开关</li>
                    <li>选择发货模式：<strong>text 文本</strong> 或 <strong>card 卡密</strong></li>
                    <li>text 模式：选择关联的货源、填写消息头部、正文（支持变量与 {分段} 拆分）</li>
                    <li>card 模式：选择卡密分组和卡密模板</li>
                    <li>设置重试次数、库存预警阈值、库存不足时是否自动停用</li>
                  </ul>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'auto-delivery')">前往自动发货 ›</button>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">5</span><strong>配置发货声明（可选）</strong></div>
                  <p>进入「发货声明」开启开关，编辑声明文案（支持 {订单编号}、{商品标题}、{买家昵称}、{发货确认链接} 等变量），系统会在发货内容后追加这段声明，规避售后纠纷。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'delivery-statement')">前往发货声明 ›</button>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">6</span><strong>配置通知提醒（可选）</strong></div>
                  <p>进入「通知设置」配置 SMTP 邮件或飞书自建应用，把"发货成功/失败/缺货"等事件推送到你的邮箱或飞书群，便于随时掌握异常。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'settings-notify')">前往通知设置 ›</button>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">7</span><strong>验证发货记录</strong></div>
                  <p>真实订单付款后，进入「发货记录」查看是否自动发货成功。如果失败，详情面板会显示原因（缺货 / 配置错误 / WS 断开等），可点击"重新发货"或"安排重新发货"（Cron 定时）。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'delivery-records')">前往发货记录 ›</button>
                </li>
              </ol>

              <figure class="shot-figure">
                <img :src="shot('auto-delivery.png')" alt="自动发货配置截图" loading="lazy" @error="onShotError" />
                <figcaption>图 3.1 / 「自动发货」页面：每行是一个商品，三种时机列分别展示付款后/收货后/好评后的配置状态。</figcaption>
              </figure>

              <div class="callout callout-warn">
                <strong>常见踩坑</strong>
                <ul>
                  <li>WS 必须保持在线，离线期间产生的订单不会自动补发，需要手动触发。</li>
                  <li>卡密库存不足时系统会按"库存预警阈值"提醒；如果开了"自动停用"，会停止发货避免超卖。</li>
                  <li>同一商品同时配置了"付款后发卡密"和"收货后发感谢语"，两个时机都会触发，互不冲突。</li>
                </ul>
              </div>
            </div>
          </CardPanel>
        </section>

        <!-- 四、24 小时自动客服 -->
        <section id="ai-cs-flow" class="manual-section">
          <CardPanel title="四、为闲鱼店铺配置 24 小时 AI 自动客服" desc="让 AI 替你回复买家咨询，晚上睡觉也能接单">
            <div class="section-body">
              <p class="lead">AI 自动客服 = AI 客服配置 + 自动回复开关。前者定义"AI 怎么回"，后者定义"什么场景下让 AI 回"。</p>

              <ol class="step-list">
                <li>
                  <div class="step-head"><span class="step-num">1</span><strong>进入 AI 客服配置</strong></div>
                  <p>左侧菜单 →「系统设置」→「AI 客服配置」Tab。这是 AI 客服的中枢配置页。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'settings-ai-cs')">前往 AI 客服配置 ›</button>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">2</span><strong>开启并选择工作模式</strong></div>
                  <p>顶部开启"启用 AI 客服"。选择工作模式：</p>
                  <ul class="bullet-list">
                    <li><strong>24 小时全天</strong>：任何时间都让 AI 接待，最省心。</li>
                    <li><strong>工作时段</strong>：只在指定时段（如 22:00-08:00）让 AI 接管，白天你自己回。</li>
                  </ul>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">3</span><strong>选择接待模式</strong></div>
                  <ul class="bullet-list">
                    <li><strong>auto 全自动</strong>：AI 直接回复，无需人工干预。推荐 24 小时无人值守场景。</li>
                    <li><strong>hybrid 混合</strong>：AI 先回，命中"转人工关键词"或"转人工阈值"时切换人工。</li>
                    <li><strong>manual 仅人工</strong>：AI 不自动回，仅作为草稿建议。</li>
                  </ul>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">4</span><strong>配置角色人设与语气</strong></div>
                  <p>填写人设描述（如"你是某虚拟商品店铺的客服小助手，态度友好、回答简洁"），选择语气（friendly 友好 / professional 专业 / casual 随意），设置 System Prompt 与欢迎语（买家首次发起会话时 AI 主动发送的问候）。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">5</span><strong>上传知识库（可选但强烈推荐）</strong></div>
                  <p>支持 .md / .txt / .pptx / .xlsx / .csv。把商品说明书、售后政策、常见问答整理成文档上传，AI 会优先基于知识库回答，避免胡说八道。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">6</span><strong>配置安全策略</strong></div>
                  <ul class="bullet-list">
                    <li><strong>转人工关键词</strong>：买家说到"退款/投诉/人工"等关键词时，自动切换人工。</li>
                    <li><strong>黑名单关键词</strong>：命中后 AI 不回复。</li>
                    <li><strong>转人工阈值</strong>：连续 N 轮对话后强制转人工，防止 AI 死循环。</li>
                    <li><strong>每日最大回复数</strong>：单会话每日上限，防止恶意消耗 Token。</li>
                    <li><strong>会话超时</strong>：买家多久没回话就结束会话。</li>
                  </ul>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">7</span><strong>实时预览测试</strong></div>
                  <p>页面底部的"实时回复预览"区可以直接输入测试消息，验证 AI 回复效果。调到满意再保存。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">8</span><strong>在自动回复控制台开启</strong></div>
                  <p>AI 配置只是"模板"，还需要在「自动回复」页面把开关打开。可以选择作用层级：全局（所有账号所有商品）/ 账号级 / 商品级。新用户建议直接开"全局"。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'auto-reply')">前往自动回复控制台 ›</button>
                </li>
              </ol>

              <figure class="shot-figure">
                <img :src="shot('ai-cs-settings.png')" alt="AI 客服配置截图" loading="lazy" @error="onShotError" />
                <figcaption>图 4.1 / 「AI 客服配置」页面：工作模式、接待模式、人设、知识库、安全策略都在这里集中配置。</figcaption>
              </figure>

              <div class="callout callout-info">
                <strong>Token 余额</strong>
                <p>AI 回复会消耗 Token 余额，可在「个人中心」查看余额并充值。余额不足时 AI 自动降级（不回复或仅回模板），不会消耗超出余额的费用。</p>
              </div>
            </div>
          </CardPanel>
        </section>

        <!-- 五、自动回复配置 -->
        <section id="auto-reply-flow" class="manual-section">
          <CardPanel title="五、配置自动回复（开关 + 作用层级）" desc="决定 AI 客服在哪些账号、哪些商品上生效">
            <div class="section-body">
              <p class="lead">自动回复控制台是 AI 客服的"开关面板"。AI 客服配置定义能力，自动回复控制台决定能力作用到哪里。</p>

              <ol class="step-list">
                <li>
                  <div class="step-head"><span class="step-num">1</span><strong>选择账号范围</strong></div>
                  <p>页面顶部筛选要管理的账号，可以单选、多选或全选。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">2</span><strong>选择商品范围</strong></div>
                  <p>进一步筛选商品，支持按状态、关键词过滤。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">3</span><strong>选择作用层级</strong></div>
                  <ul class="bullet-list">
                    <li><strong>全局</strong>：所有账号所有商品生效，最简单。</li>
                    <li><strong>账号</strong>：只对选中的账号生效，适合矩阵账号差异化运营。</li>
                    <li><strong>商品</strong>：只对选中的商品生效，适合给某些商品单独开 AI。</li>
                  </ul>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">4</span><strong>批量操作</strong></div>
                  <p>勾选目标项，点击"一键全部开启"或"批量开启/批量关闭"。</p>
                </li>
                <li>
                  <div class="step-head"><span class="step-num">5</span><strong>验证效果</strong></div>
                  <p>进入「在线消息」找一条买家会话发起新消息，看右侧"自动回复诊断"面板的状态：作用范围、Token 余额、账号登录是否正常都会实时显示。</p>
                  <button class="inline-link" type="button" @click="$emit('navigate', 'messages')">前往在线消息 ›</button>
                </li>
              </ol>

              <figure class="shot-figure">
                <img :src="shot('auto-reply.png')" alt="自动回复控制台截图" loading="lazy" @error="onShotError" />
                <figcaption>图 5.1 / 「自动回复」页面：左侧筛选账号/商品，右侧批量开关自动回复。</figcaption>
              </figure>
            </div>
          </CardPanel>
        </section>

        <!-- 六、功能模块详解 -->
        <section id="modules" class="manual-section">
          <CardPanel title="六、全部功能模块详解" desc="按左侧菜单顺序逐一讲解，每个模块都附截图">
            <div class="section-body">
              <!-- 6.1 概览 -->
              <h3 class="module-group-title" id="mod-overview">6.1 概览</h3>

              <article class="module-card">
                <header>
                  <h4>导航面板 <button class="nav-jump" type="button" @click="$emit('navigate', 'dashboard')">前往 ›</button></h4>
                  <p>登录后的首页，是所有功能的入口枢纽。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>顶部轮播</strong>：管理员配置的活动 banner。</li>
                  <li><strong>快速开始</strong>：添加账号、WS 连接、商品管理、自动发货 4 个最常用入口。</li>
                  <li><strong>功能特性</strong>：8 个核心功能的卡片入口。</li>
                  <li><strong>最近实时事件</strong>：SSE 推送的最新 5 条业务事件。</li>
                  <li><strong>右侧使用指南</strong>：新手入门步骤、可折叠的功能教程与最佳实践。</li>
                  <li><strong>右侧最近通知 + 系统状态</strong>：API/WS/数据库/存储 4 项健康度。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('dashboard.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.1 / 导航面板。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>数据面板 <button class="nav-jump" type="button" @click="$emit('navigate', 'data')">前往 ›</button></h4>
                  <p>查看运营核心指标和趋势。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>统计卡片</strong>：订单数、发货成功、发货失败、待发货、AI 回复数。</li>
                  <li><strong>近 7 天趋势</strong>：发货成功/失败/AI 回复的折线图。</li>
                  <li><strong>AI 回复分布</strong>：环形图展示各账号 AI 回复占比。</li>
                  <li><strong>实时事件流</strong>：SSE 推送的业务事件实时滚动。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('data.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.2 / 数据面板。</figcaption></figure>
              </article>

              <!-- 6.2 账号与商品 -->
              <h3 class="module-group-title" id="mod-account-product">6.2 账号与商品</h3>

              <article class="module-card">
                <header>
                  <h4>闲鱼账号 <button class="nav-jump" type="button" @click="$emit('navigate', 'accounts')">前往 ›</button></h4>
                  <p>所有店铺账号的统一管理中心。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>添加账号</strong>：扫码加账号（推荐）或手动添加。</li>
                  <li><strong>账号列表</strong>：显示别名、Cookie 状态、WS 状态、自动回复/发货开关。</li>
                  <li><strong>快捷操作抽屉</strong>：编辑 Cookie、刷新资料、同步商品、跳转自动回复/发货、连接管理、在线消息、登录验证、重新扫码、人脸验证、自动评价、账号密码登录、统一配置。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('accounts.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.3 / 闲鱼账号管理。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>连接管理 <button class="nav-jump" type="button" @click="$emit('navigate', 'connections')">前往 ›</button></h4>
                  <p>监控所有账号的 WebSocket 长连接状态。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>统计卡片</strong>：在线 / 离线 / 重连中 / Cookie 异常等数量。</li>
                  <li><strong>连接详情</strong>：每条连接的 Cookie 状态、WS 状态、心跳、延迟、自动重连、代理。</li>
                  <li><strong>操作</strong>：断开、启动、刷新 Cookie、检查登录。</li>
                  <li><strong>默认重连策略</strong>：最大重试 3 次，重试间隔 2 秒，自动重连开关。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('connections.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.4 / 连接管理。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>商品管理 <button class="nav-jump" type="button" @click="$emit('navigate', 'products')">前往 ›</button></h4>
                  <p>集中管理闲鱼商品，支持同步、筛选、批量操作。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>同步闲鱼商品</strong>：从闲鱼拉取所有在售/下架/草稿商品到系统。</li>
                  <li><strong>筛选</strong>：按账号、状态（在售/下架/草稿/已删除）、关键词。</li>
                  <li><strong>商品级开关</strong>：在售开关、自动回复开关。</li>
                  <li><strong>同步任务历史</strong>：查看每次同步的进度与结果。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('products.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.5 / 商品管理。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>订单管理 <button class="nav-jump" type="button" @click="$emit('navigate', 'orders')">前往 ›</button></h4>
                  <p>查看闲鱼订单并支持手动发货。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>状态筛选</strong>：待付款 / 已付款 / 待发货 / 已发货 / 已完成 / 已关闭。</li>
                  <li><strong>同步订单</strong>：从闲鱼拉取当前账号最新订单。</li>
                  <li><strong>手动发货</strong>：在订单详情弹窗中填写发货方式（text/card）、触发时机、发货数量、发货内容并提交。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('orders.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.6 / 订单管理。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>发布商品 <button class="nav-jump" type="button" @click="$emit('navigate', 'product-publish')">前往 ›</button></h4>
                  <p>完整的闲鱼商品发布流程。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>基础信息</strong>：标题（30 字）、描述，可一键 AI 生成描述。</li>
                  <li><strong>图片</strong>：拖拽排序，最多 10 张，支持 AI 生成封面图。</li>
                  <li><strong>分类</strong>：三级级联选择，支持 AI 自动选择、搜索、收藏、最近使用。</li>
                  <li><strong>价格与规格</strong>：支持多规格组合。</li>
                  <li><strong>发货设置</strong>：包邮 / 一口价 / 无需邮寄 / 支持自提。</li>
                </ul>
                <div class="callout callout-warn">
                  <strong>强制规则</strong>
                  <p>未生成 AI 封面图的商品严禁发布，系统会在发布前强制校验 <code>img_ai_ok == True</code>。</p>
                </div>
                <figure class="shot-figure"><img :src="shot('product-publish.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.7 / 发布商品。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>商机发掘 <button class="nav-jump" type="button" @click="$emit('navigate', 'opportunities')">前往 ›</button></h4>
                  <p>通过商品关键词搜索或店铺链接抓取竞品商机，并支持 AI 改写与一键发布。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>两种模式</strong>：商品关键词搜索 / 店铺链接抓取。</li>
                  <li><strong>搜索速度</strong>：auto 智能降级（推荐）/ fast 直调 API / slow 浏览器拦截。</li>
                  <li><strong>结果指标</strong>：热度、总数、在售、想要、竞争度。</li>
                  <li><strong>四步流程</strong>：抓取 → AI 改写（口语化/简洁/吸引眼球）→ AI 生图（1-9 张）→ 配置并发布。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('opportunities.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.8 / 商机发掘。</figcaption></figure>
              </article>

              <!-- 6.3 消息 -->
              <h3 class="module-group-title" id="mod-message">6.3 消息</h3>

              <article class="module-card">
                <header>
                  <h4>在线消息 <button class="nav-jump" type="button" @click="$emit('navigate', 'messages')">前往 ›</button></h4>
                  <p>实时会话工作台，集中处理买家咨询。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>左侧会话列表</strong>：按账号筛选、关键词搜索、未读/AI 标签过滤。</li>
                  <li><strong>中间聊天面板</strong>：发送文本/图片/商品链接、转人工、结束会话、开启自动回复、快捷模板。</li>
                  <li><strong>右侧诊断面板</strong>：商品信息、客户订单、自动回复状态（作用范围/Token 余额/账号登录）、实时 SSE 诊断。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('messages.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.9 / 在线消息。</figcaption></figure>
              </article>

              <!-- 6.4 自动化 -->
              <h3 class="module-group-title" id="mod-automation">6.4 自动化</h3>

              <article class="module-card">
                <header>
                  <h4>工作流 <button class="nav-jump" type="button" @click="$emit('navigate', 'workflow')">前往 ›</button></h4>
                  <p>可视化拖拽编排自动化业务流程，适合批量上架、跟品发布。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>节点类型</strong>：TRIGGER 触发 / PRODUCT_FETCH 商品获取 / PRODUCT_FILTER 商品筛选 / PRODUCT_POLISH 商品润色 / AI 生图 / PUBLISH 发布。</li>
                  <li><strong>商品获取方式</strong>：keyword 关键词 / shop 店铺 / AI 提取关键词。</li>
                  <li><strong>发布账号</strong>：多选，可同时发布到多个账号。</li>
                  <li><strong>状态</strong>：草稿 / 已发布。发布后可在「工作流任务」查看执行记录。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('workflow.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.10 / 工作流编排。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>工作流任务 <button class="nav-jump" type="button" @click="$emit('navigate', 'workflow-tasks')">前往 ›</button></h4>
                  <p>查看工作流执行记录，支持终止与重试。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>统计</strong>：执行记录数 / 成功 / 失败 / 进行中。</li>
                  <li><strong>详情</strong>：执行编号、触发方式、进度、节点步骤、时间线、节点产物。</li>
                  <li><strong>操作</strong>：终止执行、重试失败节点。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('workflow-tasks.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.11 / 工作流任务。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>自动发货 <button class="nav-jump" type="button" @click="$emit('navigate', 'auto-delivery')">前往 ›</button></h4>
                  <p>详见第三章「24 小时自动发货完整流程」。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>统计卡片</strong>：今日成功 / 今日失败 / 待处理 / 库存不足 / 已启用。</li>
                  <li><strong>批量设置</strong>：勾选多个商品统一配置发货规则。</li>
                  <li><strong>三个时机列</strong>：付款后 / 收货后 / 好评后，分别配置独立规则。</li>
                </ul>
              </article>

              <article class="module-card">
                <header>
                  <h4>货源库 <button class="nav-jump" type="button" @click="$emit('navigate', 'delivery-source-library')">前往 ›</button></h4>
                  <p>统一管理文本发货内容，支持 AI 智能推荐匹配商品。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>货源字段</strong>：标题、正文、备注、已配置商品数。</li>
                  <li><strong>AI 一键配置</strong>：让 AI 根据货源内容自动匹配适合的商品。</li>
                  <li><strong>批量配置</strong>：选择发货时机（付款后/收货后/好评后）批量绑定商品。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('delivery-source-library.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.12 / 货源库。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>发货声明 <button class="nav-jump" type="button" @click="$emit('navigate', 'delivery-statement')">前往 ›</button></h4>
                  <p>配置全店或指定商品的发货声明文案。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>生效范围</strong>：all 全店 / specific 单独启用。</li>
                  <li><strong>变量插值</strong>：{订单编号}、{商品标题}、{买家昵称}、{发货确认链接}。</li>
                  <li><strong>预览</strong>：保存前可预览渲染效果。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('delivery-statement.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.13 / 发货声明。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>模板管理 <button class="nav-jump" type="button" @click="$emit('navigate', 'delivery-templates')">前往 ›</button></h4>
                  <p>管理可复用的发货模板与变量。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>模板类型</strong>：付款后 / 收货后 / 好评后 / 发货声明 / 卡密发货 / 普通文本。</li>
                  <li><strong>随机模板</strong>：同一类型配多条，系统随机选一条发送，避免被风控。</li>
                  <li><strong>分段发送</strong>：用 <code>{分段}</code> 标记把一条模板拆成多条消息依次发送。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('delivery-templates.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.14 / 模板管理。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>发货记录 <button class="nav-jump" type="button" @click="$emit('navigate', 'delivery-records')">前往 ›</button></h4>
                  <p>追踪所有发货记录，支持重试与定时重发。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>状态筛选</strong>：待处理 / 进行中 / 成功 / 失败 / 缺货 / 配置错误。</li>
                  <li><strong>详情面板</strong>：订单、商品、买家、卖家、时间、状态、进度、发货内容、错误信息。</li>
                  <li><strong>操作</strong>：批量重试、导出 CSV、重新发货、安排重新发货（Cron）。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('delivery-records.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.15 / 发货记录。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>卡密仓库 <button class="nav-jump" type="button" @click="$emit('navigate', 'card-warehouse')">前往 ›</button></h4>
                  <p>管理卡密库存，支持 5 种卡密类型。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>卡密类型</strong>：unique 唯一 / card_password 卡号+密码 / link_code 链接+提取码 / account_password 账号+密码 / custom 自定义。</li>
                  <li><strong>导入格式</strong>：粘贴或文件，支持"卡号----密码"格式批量导入。</li>
                  <li><strong>卡密状态</strong>：未使用 / 已锁定 / 已使用 / 已作废 / 异常。</li>
                  <li><strong>库存预警</strong>：低于阈值时自动通知。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('card-warehouse.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.16 / 卡密仓库。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>定时任务 <button class="nav-jump" type="button" @click="$emit('navigate', 'scheduled-tasks')">前往 ›</button></h4>
                  <p>管理 Cron 定时任务，支持手动运行与表达式校验。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>任务字段</strong>：任务名、账号 ID、任务类型、Cron 表达式（5-7 段）、配置 JSON、启用状态。</li>
                  <li><strong>操作</strong>：手动运行、删除、保存。</li>
                  <li><strong>典型用途</strong>：定时重发失败订单、定时同步商品、定时启动工作流。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('scheduled-tasks.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.17 / 定时任务。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>自动回复 <button class="nav-jump" type="button" @click="$emit('navigate', 'auto-reply')">前往 ›</button></h4>
                  <p>详见第五章「自动回复配置」。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>总开关</strong>：一键关闭所有 AI 自动回复。</li>
                  <li><strong>作用层级</strong>：全局 / 账号 / 商品。</li>
                  <li><strong>批量操作</strong>：一键全部开启 / 批量开启 / 批量关闭。</li>
                </ul>
              </article>

              <!-- 6.5 系统 -->
              <h3 class="module-group-title" id="mod-system">6.5 系统</h3>

              <article class="module-card">
                <header>
                  <h4>操作日志 <button class="nav-jump" type="button" @click="$emit('navigate', 'logs')">前往 ›</button></h4>
                  <p>查询与导出所有用户操作日志。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>操作类型</strong>：登录、发送消息、自动发货、自动回复、确认收货、同步商品、启动/断开连接、发布商品、卡密导入等。</li>
                  <li><strong>详情</strong>：请求参数 JSON、响应结果 JSON，可一键复制。</li>
                  <li><strong>导出</strong>：CSV 格式。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('logs.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.18 / 操作日志。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>滑块求解 <button class="nav-jump" type="button" @click="$emit('navigate', 'slider-solve-records')">前往 ›</button></h4>
                  <p>查看滑块验证码自动求解记录。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>触发场景</strong>：manual 手动 / manual_retry 手动重试 / ws_connect WS 连接 / cookie_keepalive Cookie 保活 / token_refresh Token 刷新。</li>
                  <li><strong>详情</strong>：账号、状态、结果、验证引擎、重试次数、事件描述、耗时、调试截图。</li>
                  <li><strong>SSE 自动刷新</strong>：800ms 防抖。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('slider-solve-records.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.19 / 滑块求解记录。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>反馈建议 <button class="nav-jump" type="button" @click="$emit('navigate', 'feedback')">前往 ›</button></h4>
                  <p>提交与跟踪产品反馈。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>分类与优先级</strong>：高 / 中 / 低。</li>
                  <li><strong>状态流转</strong>：待处理 → 处理中 → 已回复。</li>
                  <li><strong>桥接同步</strong>：本地提交会同步到商业版后端。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('feedback.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.20 / 反馈建议。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>通知设置 <button class="nav-jump" type="button" @click="$emit('navigate', 'settings-notify')">前往 ›</button></h4>
                  <p>统一管理通知渠道与触发规则。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>渠道类型</strong>：SMTP 邮件 / 飞书自建应用 / 自定义。</li>
                  <li><strong>SMTP 配置</strong>：Host / Port / User / Pass / FromEmail / Receiver。</li>
                  <li><strong>飞书自建应用</strong>：AppID / AppSecret / VerificationToken / EncryptKey / ReceiveId / ReceiveIdType（open_id / user_id / chat_id / union_id）。</li>
                  <li><strong>触发规则</strong>：按事件类型配置何时推送。</li>
                  <li><strong>投递健康度</strong>：投递记录、异常、平均耗时一览。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('notify-settings.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.21 / 通知设置。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>系统设置 <button class="nav-jump" type="button" @click="$emit('navigate', 'settings-ai-cs')">前往 ›</button></h4>
                  <p>包含 AI 客服配置、商品操作、关于三个 Tab。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>AI 客服配置</strong>：详见第四章。</li>
                  <li><strong>商品操作</strong>：库存归零自动下架开关（默认开启）。</li>
                  <li><strong>关于</strong>：版本号、构建日期、更新日志、服务支持、协议链接。</li>
                </ul>
              </article>

              <!-- 6.6 会员与个人 -->
              <h3 class="module-group-title" id="mod-profile">6.6 会员与个人</h3>

              <article class="module-card">
                <header>
                  <h4>VIP 会员中心 <button class="nav-jump" type="button" @click="$emit('navigate', 'vip')">前往 ›</button></h4>
                  <p>查看并购买 VIP 套餐。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>套餐等级</strong>：normal / vip / svp，功能权益逐级递增。</li>
                  <li><strong>权益对比</strong>：可绑定闲鱼账号数、可管理商品数、AI 回复额度、自动发货、自动化发布工作流。</li>
                  <li><strong>支付</strong>：点击"立即升级"打开支付弹窗。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('vip.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.22 / VIP 会员中心。</figcaption></figure>
              </article>

              <article class="module-card">
                <header>
                  <h4>个人中心 <button class="nav-jump" type="button" @click="$emit('navigate', 'profile')">前往 ›</button></h4>
                  <p>管理账户资料、安全设置与会员权益。</p>
                </header>
                <ul class="bullet-list">
                  <li><strong>总览 Tab</strong>：套餐、邮箱/手机验证状态、Token 余额（含充值入口）、账户信息、快捷操作。</li>
                  <li><strong>账号安全 Tab</strong>：安全等级、密码、手机号验证、邮箱验证状态。</li>
                </ul>
                <figure class="shot-figure"><img :src="shot('profile.png')" alt="" loading="lazy" @error="onShotError" /><figcaption>图 6.23 / 个人中心。</figcaption></figure>
              </article>
            </div>
          </CardPanel>
        </section>

        <!-- 七、常见问题 -->
        <section id="faq" class="manual-section">
          <CardPanel title="七、常见问题 FAQ" desc="把最常被问到的问题集中回答">
            <div class="section-body">
              <div class="faq-item">
                <h4>Q1 / 为什么我的账号显示 WS 离线？</h4>
                <p>A：通常是 Cookie 过期或触发闲鱼滑块风控。进入「连接管理」点击"刷新 Cookie"或"检查登录"，必要时到「闲鱼账号」重新扫码授权。如果触发滑块，系统会自动求解，可在「滑块求解」查看结果。</p>
              </div>
              <div class="faq-item">
                <h4>Q2 / 自动发货没触发，订单一直是"待处理"怎么办？</h4>
                <p>A：按以下顺序排查：① WS 是否在线（连接管理）；② 商品是否配置了对应时机的发货规则（自动发货）；③ 卡密库存或货源是否充足（卡密仓库/货源库）；④ 在「发货记录」看失败原因。常见原因：缺货、配置错误、WS 断开。</p>
              </div>
              <div class="faq-item">
                <h4>Q3 / AI 客服为什么不回复？</h4>
                <p>A：排查顺序：① AI 客服配置是否启用并保存（系统设置 → AI 客服配置）；② 自动回复总开关是否开启（自动回复）；③ 对应账号/商品是否在作用层级范围内；④ Token 余额是否充足（个人中心）；⑤ 接待模式是否为 manual（manual 模式 AI 不自动回）。</p>
              </div>
              <div class="faq-item">
                <h4>Q4 / 商机发掘的 fast / slow / auto 有什么区别？</h4>
                <p>A：fast 直调闲鱼 API 速度最快（约 1 秒）但可能触发风控；slow 通过浏览器拦截响应最稳定（2-3 秒）；auto 默认先 fast 失败自动降级 slow，是最推荐的模式。</p>
              </div>
              <div class="faq-item">
                <h4>Q5 / 发布商品时提示"未生成 AI 封面图"怎么办？</h4>
                <p>A：这是强制规则。在发布流程的图片步骤必须使用"AI 生成封面图"功能至少生成一张，系统校验 <code>img_ai_ok == True</code> 后才允许发布。</p>
              </div>
              <div class="faq-item">
                <h4>Q6 / 卡密库存不足时系统会怎么处理？</h4>
                <p>A：在「自动发货」配置时可以设置"库存预警阈值"和"自动停用"开关。库存低于阈值会发通知；如果开启自动停用，系统会停止该商品的自动发货，避免超卖。</p>
              </div>
              <div class="faq-item">
                <h4>Q7 / 工作流和自动发货是什么关系？</h4>
                <p>A：工作流负责"商品上架前的批量处理"（抓取 → 改写 → 生图 → 发布），自动发货负责"商品上架后的订单履约"（付款 → 发货 → 确认收货）。两者是上下游关系，配合使用可以做到从跟品到交付的完全自动化。</p>
              </div>
              <div class="faq-item">
                <h4>Q8 / Token 余额用完了会怎样？</h4>
                <p>A：AI 客服会自动降级：不再调用 AI 模型，改为不回复或仅回退模板，不会产生超额费用。建议在「个人中心」设置余额预警或及时充值。</p>
              </div>
            </div>
          </CardPanel>
        </section>

        <!-- 八、联系与反馈 -->
        <section id="support" class="manual-section">
          <CardPanel title="八、联系与反馈" desc="遇到问题可以这样找我们">
            <div class="section-body">
              <div class="support-grid">
                <button class="support-tile" type="button" @click="$emit('navigate', 'feedback')">
                  <div class="support-ico ico-blue">📝</div>
                  <div class="support-text"><b>提交反馈建议</b><p>在系统内直接提交，我们会跟踪处理</p></div>
                </button>
                <button class="support-tile" type="button" @click="$emit('navigate', 'settings-about')">
                  <div class="support-ico ico-green">ℹ️</div>
                  <div class="support-text"><b>查看关于页</b><p>版本号、更新日志、服务支持渠道</p></div>
                </button>
                <button class="support-tile" type="button" @click="$emit('navigate', 'logs')">
                  <div class="support-ico ico-orange">📋</div>
                  <div class="support-text"><b>导出操作日志</b><p>反馈问题时附上日志有助于快速定位</p></div>
                </button>
              </div>
              <div class="callout callout-info">
                <strong>建议先自助排查</strong>
                <p>80% 的常见问题都能通过本手册第七章 FAQ 自行解决。如果仍未解决，请通过「反馈建议」提交，并附上「操作日志」导出的 CSV。</p>
              </div>
            </div>
          </CardPanel>
        </section>

        <div class="manual-footer">
          <p>© {{ copyrightYear }} XianYuAssistant · 使用手册 v{{ APP_VERSION }} · 最后更新 {{ todayText }}</p>
          <button class="back-top" type="button" @click="scrollToTop">回到顶部 ↑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
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
const copyrightYear = getCopyrightYear()
const todayText = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })

function shot(filename) {
  return `/xya/manual/${filename}`
}

function onShotError(e) {
  // 截图缺失时显示占位样式，避免破图
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

function scrollToSection(id) {
  const el = document.getElementById(id)
  if (!el) return
  const top = el.getBoundingClientRect().top + window.scrollY - 80
  window.scrollTo({ top, behavior: 'smooth' })
  activeSection.value = id
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function onScroll() {
  // 滚动时高亮当前目录
  const scrollPos = window.scrollY + 120
  let current = sections[0].id
  for (const sec of sections) {
    const el = document.getElementById(sec.id)
    if (el && el.offsetTop <= scrollPos) current = sec.id
  }
  activeSection.value = current
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<style scoped>
.manual-page { width: 100%; }

/* Hero */
.manual-hero {
  position: relative;
  overflow: hidden;
  border-radius: 22px;
  padding: 28px 32px 26px;
  margin-bottom: 18px;
  border: 1px solid rgba(220, 232, 248, 0.95);
  background: linear-gradient(120deg, #f5f9ff 0%, #f3eefe 100%);
  box-shadow: 0 18px 42px rgba(31, 53, 94, 0.08);
}
.hero-bg {
  position: absolute; inset: 0;
  background:
    radial-gradient(circle at 8% 12%, rgba(37, 99, 235, 0.12), transparent 36%),
    radial-gradient(circle at 92% 18%, rgba(139, 92, 246, 0.12), transparent 34%);
  pointer-events: none;
}
.hero-inner { position: relative; z-index: 1; }
.hero-brand { display: flex; align-items: center; gap: 20px; }
.brand-mark { width: 64px; height: 64px; position: relative; flex-shrink: 0; }
.brand-mark span {
  position: absolute; left: 26px; top: 0;
  width: 18px; height: 64px; border-radius: 12px;
  background: linear-gradient(180deg, #0d7fff, #16b7ff);
  transform: rotate(42deg);
  box-shadow: 0 8px 22px rgba(13, 107, 255, 0.32);
}
.brand-mark span + span { transform: rotate(-42deg); background: linear-gradient(180deg, #25a5ff, #0362f4); }
.hero-text { min-width: 0; }
.hero-title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.hero-title-row h1 { margin: 0; font-size: 26px; font-weight: 900; color: #13213d; }
.hero-text p { margin: 10px 0 0; color: #4a5a73; font-size: 14px; line-height: 1.7; max-width: 880px; }
.hero-meta { display: flex; align-items: center; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
.hero-meta-item { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #6c7a93; font-weight: 600; }
.hero-meta-divider { width: 1px; height: 10px; background: #d8e0ec; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-green { background: #22c55e; box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18); }

/* 布局 */
.manual-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.manual-toc {
  position: sticky;
  top: 88px;
}
.toc-inner {
  background: #fff;
  border: 1px solid #e8eef8;
  border-radius: 16px;
  padding: 16px 14px;
  box-shadow: 0 10px 26px rgba(31, 53, 94, 0.06);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.toc-title {
  font-size: 11px;
  font-weight: 800;
  color: #94a3b8;
  letter-spacing: 1px;
  padding: 4px 8px 8px;
  text-transform: uppercase;
}
.toc-link {
  display: block;
  padding: 8px 10px;
  border-radius: 8px;
  color: #445874;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: background 0.18s ease, color 0.18s ease;
  cursor: pointer;
}
.toc-link:hover { background: #f5f8fc; color: #1d2d4b; }
.toc-link.active {
  background: linear-gradient(90deg, #eef4ff, #f5f9ff);
  color: #2563eb;
  border-left: 3px solid #2563eb;
}

.manual-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.manual-section :deep(.card-panel) {
  border-radius: 18px;
  padding: 24px 26px;
  box-shadow: 0 16px 40px rgba(32, 68, 132, 0.06);
  border: 1px solid #eef2f8;
  background: #fff;
}
.manual-section :deep(.panel-head h3) {
  font-size: 18px;
  color: #13213d;
}
.manual-section :deep(.panel-head p) {
  font-size: 13px;
  color: #6c7a93;
}

.section-body { font-size: 14px; color: #3a4a63; line-height: 1.75; }
.section-body .lead {
  font-size: 15px;
  color: #2c3d59;
  line-height: 1.8;
  margin: 0 0 16px;
}
.section-body strong { color: #1d2d4b; }

/* 流程图 */
.flow-diagram {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 14px;
  background: linear-gradient(90deg, #f5f9ff, #f3eefe);
  border: 1px dashed #cdd9eb;
  margin: 14px 0 18px;
}
.flow-node {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 14px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #c9dcff;
  color: #1d2d4b;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.06);
}
.flow-arrow {
  color: #2563eb;
  font-weight: 900;
  font-size: 14px;
}

/* 步骤列表 */
.step-list {
  list-style: none;
  margin: 14px 0 0;
  padding: 0;
  counter-reset: step;
}
.step-list > li {
  position: relative;
  padding: 14px 0 14px 0;
  border-bottom: 1px dashed #e8eef8;
}
.step-list > li:last-child { border-bottom: 0; }
.step-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.step-num {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #4f7eff);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.24);
}
.step-head strong { font-size: 15px; color: #1d2d4b; }
.step-list p { margin: 4px 0 6px; color: #445874; }
.step-list ul { margin: 6px 0; }

.bullet-list {
  list-style: none;
  margin: 6px 0;
  padding: 0;
}
.bullet-list li {
  position: relative;
  padding-left: 16px;
  margin: 4px 0;
  color: #445874;
  line-height: 1.75;
}
.bullet-list li::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 11px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #2563eb;
}
.bullet-list code {
  background: #eef4ff;
  color: #2563eb;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 8px;
}

.inline-link {
  border: 0;
  padding: 0;
  background: transparent;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  margin-top: 6px;
}
.inline-link:hover { color: #1d4ed8; text-decoration: underline; }

/* 功能特性胶囊 */
.feature-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 16px;
}
.feature-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eef4ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid #d4e3ff;
}
.feature-pill strong { color: #1d4ed8; margin-right: 4px; }

/* 截图 */
.shot-figure {
  margin: 18px 0 8px;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #e2e8f3;
  background: #f8fafc;
  box-shadow: 0 12px 30px rgba(31, 53, 94, 0.08);
}
.shot-figure img {
  display: block;
  width: 100%;
  height: auto;
  background: #f5f8fc;
}
.shot-figure figcaption {
  padding: 10px 14px;
  font-size: 12px;
  color: #6c7a93;
  background: #f5f8fc;
  border-top: 1px solid #e8eef8;
}

/* Callout */
.callout {
  margin: 16px 0 4px;
  padding: 14px 16px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.75;
}
.callout strong { display: block; margin-bottom: 4px; font-size: 13px; }
.callout p { margin: 0; color: #445874; }
.callout ul { margin: 6px 0 0; padding-left: 18px; }
.callout ul li { margin: 4px 0; color: #445874; }
.callout-info {
  background: #eef6ff;
  border: 1px solid #cfe2ff;
}
.callout-info strong { color: #1d4ed8; }
.callout-warn {
  background: #fff7ed;
  border: 1px solid #fed7aa;
}
.callout-warn strong { color: #c2410c; }
.callout code {
  background: rgba(255, 255, 255, 0.65);
  color: #c2410c;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

/* 模块组标题 */
.module-group-title {
  margin: 26px 0 10px;
  padding: 10px 14px;
  font-size: 15px;
  font-weight: 800;
  color: #1d2d4b;
  background: linear-gradient(90deg, #f5f9ff, #fafcff);
  border-left: 4px solid #2563eb;
  border-radius: 8px;
  scroll-margin-top: 100px;
}
.module-group-title:first-of-type { margin-top: 8px; }

/* 模块卡片 */
.module-card {
  padding: 16px 0 18px;
  border-bottom: 1px solid #eef2f8;
  scroll-margin-top: 100px;
}
.module-card:last-child { border-bottom: 0; }
.module-card header h4 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 800;
  color: #13213d;
  display: flex;
  align-items: center;
  gap: 10px;
}
.module-card header p {
  margin: 0 0 8px;
  color: #6c7a93;
  font-size: 13px;
}
.nav-jump {
  border: 0;
  padding: 0;
  background: transparent;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.nav-jump:hover { color: #1d4ed8; text-decoration: underline; }

/* FAQ */
.faq-item {
  padding: 14px 0;
  border-bottom: 1px dashed #e8eef8;
}
.faq-item:last-child { border-bottom: 0; }
.faq-item h4 {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 800;
  color: #1d2d4b;
}
.faq-item p {
  margin: 0;
  color: #445874;
  font-size: 13px;
  line-height: 1.75;
}

/* 支持入口 */
.support-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0 4px;
}
.support-tile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid #e8eef8;
  border-radius: 14px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.support-tile:hover {
  transform: translateY(-1px);
  border-color: #c9dcff;
  box-shadow: 0 12px 26px rgba(37, 99, 235, 0.08);
}
.support-ico {
  width: 40px; height: 40px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.ico-blue { background: #eef4ff; }
.ico-green { background: #ecfdf3; }
.ico-orange { background: #fff7ed; }
.support-text b { display: block; font-size: 13px; color: #13213d; }
.support-text p { margin: 2px 0 0; font-size: 11px; color: #7a879e; line-height: 1.5; }

/* 页脚 */
.manual-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 4px 4px;
  color: #94a3b8;
  font-size: 12px;
}
.back-top {
  border: 1px solid #e8eef8;
  background: #fff;
  color: #445874;
  font-size: 12px;
  font-weight: 700;
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}
.back-top:hover { background: #f5f8fc; color: #1d2d4b; }

/* 响应式 */
@media (max-width: 1180px) {
  .manual-layout { grid-template-columns: 1fr; }
  .manual-toc { position: static; }
  .toc-inner {
    flex-direction: row;
    flex-wrap: wrap;
    overflow-x: auto;
  }
  .toc-title { width: 100%; }
  .toc-link { white-space: nowrap; }
}
@media (max-width: 900px) {
  .support-grid { grid-template-columns: 1fr; }
  .hero-brand { flex-direction: column; align-items: flex-start; gap: 12px; }
  .manual-hero { padding: 20px; }
  .manual-section :deep(.card-panel) { padding: 18px; }
}
</style>
