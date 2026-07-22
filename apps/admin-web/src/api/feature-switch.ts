import request from '@/utils/http'

/**
 * 功能开关配置项（每级别独立开关）
 */
export interface FeatureSwitchItem {
  /** 页面 key（唯一标识） */
  key: string
  /** 显示名称 */
  title?: string
  /** 分组：overview/account/message/automation/system/hidden */
  group?: string
  /** 普通用户是否可访问 */
  normal: boolean
  /** VIP 是否可访问 */
  vip: boolean
  /** SVP 是否可访问 */
  svp: boolean
  /** 关闭原因（仅 manual-slider-solve 使用，选填）
   * 管理员填写后，前台被拦截时展示给用户；未填写时使用系统默认文案。
   * 后端会做长度截断（≤200）与 HTML 标签过滤。 */
  reason?: string
}

/**
 * 保存配置时的请求体
 */
export interface FeatureSwitchConfig {
  features: FeatureSwitchItem[]
}

/**
 * 获取全部功能开关配置
 */
export function fetchGetFeatureSwitches() {
  return request.get<FeatureSwitchItem[]>({
    url: '/system/feature-switches',
    skipDedupe: true,
    showErrorMessage: false
  }).then(value => {
    const data = (value as any)?.data ?? value
    return Array.isArray(data) ? data as FeatureSwitchItem[] : []
  })
}

/**
 * 保存功能开关配置（整体覆盖）
 */
export function fetchSaveFeatureSwitches(features: FeatureSwitchItem[]) {
  return request.put<void>({
    url: '/system/feature-switches',
    data: { features } as FeatureSwitchConfig,
    showErrorMessage: false
  })
}

/**
 * 初始化默认配置（幂等，仅首次写入）
 */
export function fetchInitFeatureSwitches() {
  return request.post<{ initialized: boolean; features: FeatureSwitchItem[] }>({
    url: '/system/feature-switches/init',
    showErrorMessage: false
  })
}
