export interface ReleaseNote {
  version: string
  title: string
  date: string
  detail: readonly string[]
  requireReLogin?: boolean
  remark?: string
}

/**
 * Product-owned release metadata used by both the upgrade guard and changelog.
 * Keep the newest release first and never place secrets or user-provided HTML here.
 */
export const releaseNotes: readonly ReleaseNote[] = [
  {
    version: 'v1.0.0',
    title: '企业级上线前安全与可靠性基线',
    date: '2026-07-11',
    detail: [
      '强化认证失效、租户隔离和敏感配置保护',
      '补全故障状态、可访问性与不可用功能提示',
      '增加迁移、依赖、构建和生产发布门禁',
      '完善支付、AI、自动化与上传链路的失败闭锁'
    ],
    requireReLogin: true,
    remark: '生产上线仍须通过生产就绪清单中的外部凭证、基础设施、灾备、合规和验收门禁。'
  }
]
