<template>
  <div class="model-config-page">
    <section class="page-head">
      <div class="page-head__title-wrap">
        <div class="page-head__title-row">
          <h2 class="page-title">模型配置</h2>
          <div class="page-tip">
            <ElIcon><InfoFilled /></ElIcon>
            <span>菜单名称与国际化文案已同步更新</span>
          </div>
        </div>
        <p class="page-subtitle">集中管理平台各类模型的配置信息</p>
      </div>
    </section>

    <section class="overview-grid">
      <article v-for="card in statCards" :key="card.key" class="overview-card">
        <div class="overview-card__icon" :class="`is-${card.tone}`">
          <ElIcon><component :is="card.icon" /></ElIcon>
        </div>
        <div class="overview-card__content">
          <div class="overview-card__label">{{ card.label }}</div>
          <div class="overview-card__value">{{ card.value }}</div>
        </div>
      </article>
    </section>

    <section class="config-grid">
      <ModelConfigForm
        v-for="section in sections"
        :key="section.key"
        :ref="(el) => setFormRef(section.key, el as unknown as ModelConfigFormExpose | null)"
        :section="section"
        @change="handleSectionChange"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
  import { computed, reactive } from 'vue'
  import { CircleCheck, Connection, InfoFilled, Opportunity, Warning } from '@element-plus/icons-vue'
  import ModelConfigForm from './ModelConfigForm.vue'
  import type { ModelConfigFormExpose, ModelConfigSection, SectionStatePayload } from './ModelConfigForm.vue'

  defineOptions({ name: 'AdminModelConfigPage' })

  const sections: ModelConfigSection[] = [
    {
      key: 'general',
      title: '通用模型配置',
      moduleKey: 'model-config-general',
      description: '配置通用模型的基础连接信息与默认参数',
      statusText: '已启用',
      fields: [
        {
          prop: 'providerName',
          label: '默认服务商',
          placeholder: '请选择默认服务商',
          type: 'select',
          options: ['OpenAI', 'DeepSeek', 'Anthropic', '阿里云百炼'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'baseUrl',
          label: 'Base URL',
          placeholder: 'https://api.openai.com/v1',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'apiKey',
          label: 'API Key',
          placeholder: '请输入 API Key',
          type: 'password',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'defaultModel',
          label: '默认模型',
          placeholder: '请输入模型 ID，例如 gpt-4o',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'requestTimeout',
          label: '请求超时（秒）',
          type: 'number',
          min: 1,
          max: 600,
          step: 1,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'enabled',
          label: '启用状态',
          type: 'switch',
          passText: '校验通过'
        },
        {
          prop: 'perCallPrice',
          label: '按次计费价格（元）',
          placeholder: '通用模型统一按次计费，默认 0.03 元/次（兑换比例 100 时扣 3 Token）',
          type: 'number',
          min: 0,
          step: 0.0001,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'tokenExchangeRate',
          label: '兑换比例（Token/元）',
          type: 'number',
          min: 1,
          step: 1,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'polishKeywords',
          label: '润色关键词',
          type: 'textarea',
          rows: 3,
          placeholder: '润色结果中必须出现的关键词，可用逗号或回车分隔输入下一个关键词（留空表示不强制）',
          passText: '校验通过'
        },
        {
          prop: 'polishForbiddenKeywords',
          label: '润色禁止关键词',
          type: 'textarea',
          rows: 3,
          placeholder: '润色结果中绝对禁止出现的关键词，可用逗号或回车分隔输入下一个关键词（留空时默认仍会禁止「盗版、破解版、毕设」）',
          passText: '校验通过'
        }
      ]
    },
    {
      key: 'image',
      title: '生图模型配置',
      moduleKey: 'model-config-image',
      description: '配置图像生成模型及输出参数',
      statusText: '已启用',
      fields: [
        {
          prop: 'providerName',
          label: '服务商',
          placeholder: '请选择服务商',
          type: 'select',
          options: ['OpenAI Images', '阿里云百炼', 'Stability', '自定义OpenAI兼容'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'providerMode',
          label: '对接方式',
          placeholder: '请选择该生图模型的对接方式',
          type: 'select',
          options: ['openai-compatible', 'async-poll', 'webhook-callback', 'chat-completions-image'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'providerDocUrl',
          label: '模型说明/文档链接',
          placeholder: '请填写该生图模型的 API 文档链接，例如 https://platform.openai.com/docs/api-reference/images',
          passText: '校验通过'
        },
        {
          prop: 'providerDocText',
          label: '模型说明/文档正文',
          placeholder: '可粘贴生图模型的接入文档、异步轮询说明、限制、错误码等内容',
          type: 'textarea',
          rows: 8,
          passText: '校验通过'
        },
        {
          prop: 'modelName',
          label: '生图模型',
          placeholder: '请输入模型 ID，例如 gpt-image-1 / dall-e-3 / wanx2.1-t2i-turbo',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'baseUrl',
          label: 'Base URL',
          placeholder: 'https://api.openai.com/v1；为空时继承通用模型 Base URL',
          passText: '校验通过'
        },
        {
          prop: 'apiKey',
          label: 'API Key',
          placeholder: '为空时继承通用模型 API Key',
          type: 'password',
          passText: '校验通过'
        },
        {
          prop: 'imageSize',
          label: '默认尺寸',
          placeholder: '请选择默认尺寸',
          type: 'select',
          options: ['1024x1024 (1:1)'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'quality',
          label: '输出质量',
          placeholder: '请选择输出质量',
          type: 'select',
          options: ['高质量', '标准质量'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'concurrencyLimit',
          label: '并发上限',
          type: 'number',
          min: 1,
          max: 20,
          step: 1,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'safeReview',
          label: '安全审核',
          type: 'switch',
          passText: '校验通过'
        },
        {
          prop: 'tokensPerImage',
          label: '每张消耗Token',
          type: 'number',
          min: 0,
          step: 1,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'defaultSystemPrompt',
          label: '默认生图提示词',
          placeholder: '生成真实、干净、适合闲鱼商品发布的商品主图，背景简洁，避免水印和夸大宣传。',
          type: 'textarea',
          rows: 4,
          maxlength: 800,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'billingMode',
          label: '计费方式',
          type: 'select',
          options: ['按次计费（每张图片固定费用）', '按规格计费（按图片尺寸规格计费）'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'specPriceJson',
          label: '规格价格 JSON',
          placeholder: '{"1024x1024":0.05}',
          type: 'textarea',
          rows: 3,
          passText: '校验通过'
        },
        {
          prop: 'cost',
          label: '成本（元/张）',
          placeholder: '每张图片成本，例如 0.04；AI 调用日志中费用=调用张数×成本',
          type: 'number',
          min: 0,
          step: 0.0001,
          passText: '校验通过'
        }
      ]
    },
    {
      key: 'image2',
      title: '生图模型2配置',
      moduleKey: 'model-config-image-2',
      description: '配置第二个图像生成模型的参数与连接信息',
      statusText: '已启用',
      fields: [
        {
          prop: 'providerName',
          label: '服务商',
          placeholder: '请选择服务商',
          type: 'select',
          options: ['OpenAI Images', '阿里云百炼', 'Stability', '自定义OpenAI兼容'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'providerMode',
          label: '对接方式',
          placeholder: '请选择该生图模型的对接方式',
          type: 'select',
          options: ['openai-compatible', 'async-poll', 'webhook-callback', 'chat-completions-image'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'providerDocUrl',
          label: '模型说明/文档链接',
          placeholder: '请填写该生图模型的 API 文档链接，例如 https://platform.openai.com/docs/api-reference/images',
          passText: '校验通过'
        },
        {
          prop: 'modelName',
          label: '生图模型',
          placeholder: '请输入模型 ID，例如 gpt-image-1 / dall-e-3 / wanx2.1-t2i-turbo',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'baseUrl',
          label: 'Base URL',
          placeholder: 'https://api.openai.com/v1；为空时继承通用模型 Base URL',
          passText: '校验通过'
        },
        {
          prop: 'apiKey',
          label: 'API Key',
          placeholder: '为空时继承通用模型 API Key',
          type: 'password',
          passText: '校验通过'
        },
        {
          prop: 'imageSize',
          label: '默认尺寸',
          placeholder: '请选择默认尺寸',
          type: 'select',
          options: ['1024x1024 (1:1)'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'quality',
          label: '输出质量',
          placeholder: '请选择输出质量',
          type: 'select',
          options: ['高质量', '标准质量'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'concurrencyLimit',
          label: '并发上限',
          type: 'number',
          min: 1,
          max: 20,
          step: 1,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'safeReview',
          label: '安全审核',
          type: 'switch',
          passText: '校验通过'
        },
        {
          prop: 'tokensPerImage',
          label: '每张消耗Token',
          type: 'number',
          min: 0,
          step: 1,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'defaultSystemPrompt',
          label: '默认生图提示词',
          placeholder: '生成真实、干净、适合闲鱼商品发布的商品主图，背景简洁，避免水印和夸大宣传。',
          type: 'textarea',
          rows: 4,
          maxlength: 800,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'billingMode',
          label: '计费方式',
          type: 'select',
          options: ['按次计费（每张图片固定费用）', '按规格计费（按图片尺寸规格计费）'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'specPriceJson',
          label: '规格价格 JSON',
          placeholder: '{"1024x1024":0.05}',
          type: 'textarea',
          rows: 3,
          passText: '校验通过'
        },
        {
          prop: 'cost',
          label: '成本（元/张）',
          placeholder: '每张图片成本，例如 0.04；AI 调用日志中费用=调用张数×成本',
          type: 'number',
          min: 0,
          step: 0.0001,
          passText: '校验通过'
        },
        {
          prop: 'enabled',
          label: '启用状态',
          type: 'switch',
          passText: '校验通过'
        }
      ]
    },
    {
      key: 'image3',
      title: '生图模型3配置',
      moduleKey: 'model-config-image-3',
      description: '配置第三个图像生成模型的参数与连接信息',
      statusText: '已启用',
      fields: [
        {
          prop: 'providerName',
          label: '服务商',
          placeholder: '请选择服务商',
          type: 'select',
          options: ['OpenAI Images', '阿里云百炼', 'Stability', '自定义OpenAI兼容'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'providerMode',
          label: '对接方式',
          placeholder: '请选择该生图模型的对接方式',
          type: 'select',
          options: ['openai-compatible', 'async-poll', 'webhook-callback', 'chat-completions-image'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'providerDocUrl',
          label: '模型说明/文档链接',
          placeholder: '请填写该生图模型的 API 文档链接，例如 https://platform.openai.com/docs/api-reference/images',
          passText: '校验通过'
        },
        {
          prop: 'modelName',
          label: '生图模型',
          placeholder: '请输入模型 ID，例如 gpt-image-1 / dall-e-3 / wanx2.1-t2i-turbo',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'baseUrl',
          label: 'Base URL',
          placeholder: 'https://api.openai.com/v1；为空时继承通用模型 Base URL',
          passText: '校验通过'
        },
        {
          prop: 'apiKey',
          label: 'API Key',
          placeholder: '为空时继承通用模型 API Key',
          type: 'password',
          passText: '校验通过'
        },
        {
          prop: 'imageSize',
          label: '默认尺寸',
          placeholder: '请选择默认尺寸',
          type: 'select',
          options: ['1024x1024 (1:1)'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'quality',
          label: '输出质量',
          placeholder: '请选择输出质量',
          type: 'select',
          options: ['高质量', '标准质量'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'concurrencyLimit',
          label: '并发上限',
          type: 'number',
          min: 1,
          max: 20,
          step: 1,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'safeReview',
          label: '安全审核',
          type: 'switch',
          passText: '校验通过'
        },
        {
          prop: 'tokensPerImage',
          label: '每张消耗Token',
          type: 'number',
          min: 0,
          step: 1,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'defaultSystemPrompt',
          label: '默认生图提示词',
          placeholder: '生成真实、干净、适合闲鱼商品发布的商品主图，背景简洁，避免水印和夸大宣传。',
          type: 'textarea',
          rows: 4,
          maxlength: 800,
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'billingMode',
          label: '计费方式',
          type: 'select',
          options: ['按次计费（每张图片固定费用）', '按规格计费（按图片尺寸规格计费）'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'specPriceJson',
          label: '规格价格 JSON',
          placeholder: '{"1024x1024":0.05}',
          type: 'textarea',
          rows: 3,
          passText: '校验通过'
        },
        {
          prop: 'cost',
          label: '成本（元/张）',
          placeholder: '每张图片成本，例如 0.04；AI 调用日志中费用=调用张数×成本',
          type: 'number',
          min: 0,
          step: 0.0001,
          passText: '校验通过'
        },
        {
          prop: 'enabled',
          label: '启用状态',
          type: 'switch',
          passText: '校验通过'
        }
      ]
    },
    {
      key: 'chat',
      title: '对话模型配置',
      moduleKey: 'model-config-chat',
      description: '配置对话模型的参数与行为策略',
      statusText: '已启用',
      fields: [
        {
          prop: 'providerName',
          label: '服务商',
          placeholder: '请选择服务商',
          type: 'select',
          options: ['OpenAI', 'DeepSeek', 'Anthropic'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'baseUrl',
          label: 'Base URL',
          placeholder: 'https://api.openai.com/v1',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'apiKey',
          label: 'API Key',
          placeholder: '请输入 API Key',
          type: 'password',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'modelName',
          label: '对话模型',
          placeholder: '请输入模型 ID，例如 gpt-4o',
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'temperature',
          label: 'Temperature',
          type: 'number',
          min: 0,
          max: 2,
          step: 0.1,
          passText: '校验通过'
        },
        {
          prop: 'maxTokens',
          label: 'Max Tokens',
          type: 'number',
          min: 1,
          max: 200000,
          step: 1,
          passText: '校验通过'
        },
        {
          prop: 'contextWindow',
          label: '上下文长度',
          type: 'number',
          min: 1,
          max: 200000,
          step: 1,
          passText: '校验通过'
        },
        {
          prop: 'streamOutput',
          label: '流式输出',
          type: 'switch',
          passText: '校验通过'
        },
        {
          prop: 'billingMode',
          label: '计费方式',
          type: 'select',
          options: ['按Token计费（按输入/输出Token数量计费）', '按次计费（每次调用固定费用）'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'billingUnit',
          label: '计费单位',
          type: 'select',
          options: ['1K Tokens', '百万Tokens', '一兆Tokens'],
          required: true,
          passText: '校验通过'
        },
        {
          prop: 'inputPricePer1k',
          label: '输入单价（元）',
          placeholder: '按计费单位填写，例如 0.001 元/1K 或 3 元/百万Tokens',
          type: 'number',
          min: 0,
          step: 0.0001,
          passText: '校验通过'
        },
        {
          prop: 'cachedInputPricePer1k',
          label: '缓存命中输入单价（元）',
          placeholder: 'DeepSeek 等支持上下文缓存时填写，0 表示与输入单价相同',
          type: 'number',
          min: 0,
          step: 0.0001,
          passText: '校验通过'
        },
        {
          prop: 'outputPricePer1k',
          label: '输出单价（元）',
          placeholder: '按计费单位填写，例如 0.002 元/1K 或 6 元/百万Tokens',
          type: 'number',
          min: 0,
          step: 0.0001,
          passText: '校验通过'
        },
        {
          prop: 'perCallPrice',
          label: '按次价格（元）',
          type: 'number',
          min: 0,
          step: 0.0001,
          passText: '校验通过'
        },
        {
          prop: 'tokenExchangeRate',
          label: '兑换比例（Token/元）',
          type: 'number',
          min: 1,
          step: 1,
          required: true,
          passText: '校验通过'
        }
      ]
    }
  ]

  const formRefMap = reactive<Record<string, ModelConfigFormExpose | null>>({})
  const sectionStates = reactive<Record<string, SectionStatePayload>>({})

  function setFormRef(key: string, el: ModelConfigFormExpose | null) {
    if (el) {
      formRefMap[key] = el
      return
    }
    delete formRefMap[key]
  }

  function handleSectionChange(payload: SectionStatePayload) {
    sectionStates[payload.key] = payload
  }

  const statCards = computed(() => {
    const values = sections.map((section) => sectionStates[section.key])
    const total = sections.length
    const configured = values.filter((item) => item?.configured).length
    const enabled = values.filter((item) => item?.enabled).length
    const connected = values.filter((item) => item?.tested).length
    const abnormal = values.filter((item) => item && item.configured && !item.tested).length

    return [
      {
        key: 'total',
        label: '模块总数',
        value: total,
        tone: 'blue',
        icon: Opportunity
      },
      {
        key: 'configured',
        label: '已配置',
        value: configured,
        tone: 'green',
        icon: CircleCheck
      },
      {
        key: 'enabled',
        label: '启用中',
        value: enabled,
        tone: 'emerald',
        icon: Connection
      },
      {
        key: 'pending',
        label: '待校验',
        value: total - connected,
        tone: 'orange',
        icon: InfoFilled
      },
      {
        key: 'abnormal',
        label: '异常',
        value: abnormal,
        tone: 'red',
        icon: Warning
      }
    ]
  })
</script>

<style scoped>
  .model-config-page {
    padding: 4px 0 0;
  }

  .page-head {
    margin-bottom: 16px;
  }

  .page-head__title-wrap {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .page-head__title-row {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .page-title {
    margin: 0;
    font-size: 32px;
    line-height: 1.1;
    font-weight: 700;
    color: #2d3448;
    letter-spacing: -0.02em;
  }

  .page-tip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    background: #edf3ff;
    color: #7a8fcb;
    font-size: 12px;
    font-weight: 600;
  }

  .page-subtitle {
    margin: 0;
    font-size: 14px;
    color: #9098ab;
    font-weight: 500;
  }

  .overview-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 18px;
  }

  .overview-card {
    display: flex;
    align-items: center;
    gap: 14px;
    min-height: 94px;
    padding: 0 22px;
    border-radius: 18px;
    border: 1px solid #edf0f6;
    background: linear-gradient(180deg, #ffffff 0%, #fcfdff 100%);
    box-shadow: 0 8px 22px rgba(31, 46, 90, 0.05);
  }

  .overview-card__icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 46px;
    height: 46px;
    border-radius: 50%;
    font-size: 22px;
    flex-shrink: 0;
  }

  .overview-card__icon.is-blue {
    color: #4d8dff;
    background: #edf5ff;
  }

  .overview-card__icon.is-green {
    color: #4dc977;
    background: #edf9f0;
  }

  .overview-card__icon.is-emerald {
    color: #32c96a;
    background: #eefaf1;
  }

  .overview-card__icon.is-orange {
    color: #ffab47;
    background: #fff5e8;
  }

  .overview-card__icon.is-red {
    color: #ff6f66;
    background: #fff0f0;
  }

  .overview-card__label {
    font-size: 15px;
    color: #7e8798;
    font-weight: 600;
    margin-bottom: 8px;
  }

  .overview-card__value {
    font-size: 40px;
    line-height: 1;
    color: #1f2430;
    font-weight: 700;
    letter-spacing: -0.03em;
  }

  .config-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }

  @media (max-width: 1400px) {
    .overview-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  @media (max-width: 1080px) {
    .config-grid,
    .overview-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
