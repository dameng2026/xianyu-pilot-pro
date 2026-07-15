import type { EChartsOption } from '@/plugins/echarts'

export type LegendPosition = 'bottom' | 'top' | 'left' | 'right'

export type SymbolType =
  | 'circle'
  | 'rect'
  | 'roundRect'
  | 'triangle'
  | 'diamond'
  | 'pin'
  | 'arrow'
  | 'none'

export interface ChartThemeConfig {
  chartHeight: string
  fontSize: number
  fontColor: string
  themeColor: string
  colors: string[]
}

export interface UseChartOptions {
  initOptions?: EChartsOption
  initDelay?: number
  threshold?: number
  autoTheme?: boolean
}

export interface BaseChartProps {
  height?: string
  loading?: boolean
  isEmpty?: boolean
  colors?: string[]
}

export interface AxisDisplayProps {
  showAxisLabel?: boolean
  showAxisLine?: boolean
  showSplitLine?: boolean
}

export interface InteractionProps {
  showTooltip?: boolean
  showLegend?: boolean
  legendPosition?: LegendPosition
}

export interface BarDataItem {
  name: string
  data: number[]
  barWidth?: string | number
  stack?: string
}

export interface BarChartProps extends BaseChartProps, AxisDisplayProps, InteractionProps {
  data: number[] | BarDataItem[]
  xAxisData?: string[]
  barWidth?: string | number
  stack?: boolean
  borderRadius?: number | number[]
}

export interface LineDataItem {
  name: string
  data: number[]
  lineWidth?: number
  showAreaColor?: boolean
  areaStyle?: {
    startOpacity?: number
    endOpacity?: number
    custom?: any
  }
  smooth?: boolean
  symbol?: SymbolType
  symbolSize?: number
  lineStyleType?: 'solid' | 'dashed' | 'dotted'
  shadowBlur?: number
  shadowColor?: string
  shadowOffsetY?: number
}

export interface LineChartProps extends BaseChartProps, AxisDisplayProps, InteractionProps {
  data: number[] | LineDataItem[]
  xAxisData?: string[]
  lineWidth?: number
  showAreaColor?: boolean
  smooth?: boolean
  symbol?: SymbolType
  symbolSize?: number
  animationDelay?: number
  yAxisMin?: number
  yAxisMax?: number
  showXAxisLabel?: boolean
  showYAxisLabel?: boolean
  splitNumber?: number
  gridPadding?: {
    top?: number
    right?: number
    bottom?: number
    left?: number
  }
}

export interface RadarDataItem {
  name: string
  value: number[]
}

export interface RadarChartProps extends BaseChartProps, InteractionProps {
  indicator?: Array<{ name: string; max: number }>
  data?: RadarDataItem[]
}

export interface PieDataItem {
  value: number
  name: string
}

export interface RingChartProps extends BaseChartProps, InteractionProps {
  data: PieDataItem[]
  radius?: string[]
  borderRadius?: number
  centerText?: string
  showLabel?: boolean
}

export interface KLineDataItem {
  time: string
  open: number
  close: number
  high: number
  low: number
}

export interface KLineChartProps extends BaseChartProps {
  data?: KLineDataItem[]
  showDataZoom?: boolean
  dataZoomStart?: number
  dataZoomEnd?: number
}

export interface ScatterDataItem {
  value: number[]
}

export interface ScatterChartProps extends BaseChartProps, AxisDisplayProps, InteractionProps {
  data?: ScatterDataItem[]
  symbolSize?: number
}

export interface DualBarCompareChartProps extends BaseChartProps {
  topData: number[]
  bottomData: number[]
  xAxisData: string[]
  topColor?: string
  bottomColor?: string
  barWidth?: number
}

export interface MapChartProps extends BaseChartProps {
  mapData?: any[]
  selectedRegion?: string
  showLabels?: boolean
  showScatter?: boolean
}

export interface BidirectionalBarChartProps
  extends BaseChartProps,
    AxisDisplayProps,
    InteractionProps {
  positiveData: number[]
  negativeData: number[]
  xAxisData?: string[]
  positiveName?: string
  negativeName?: string
  barWidth?: string | number
  yAxisMin?: number
  yAxisMax?: number
  showDataLabel?: boolean
  positiveBorderRadius?: number | number[]
  negativeBorderRadius?: number | number[]
}

export type ChartOptionGenerator = () => EChartsOption

export type ChartEventCallback = (params: any) => void

export interface ChartError {
  code: string
  message: string
  details?: any
}
