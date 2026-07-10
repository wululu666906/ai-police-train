import * as echarts from 'echarts/core'
import { GaugeChart, PieChart } from 'echarts/charts'
import { LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { GaugeSeriesOption, PieSeriesOption } from 'echarts/charts'
import type { LegendComponentOption, TitleComponentOption, TooltipComponentOption } from 'echarts/components'
import type { ComposeOption } from 'echarts/core'

export type ECOption = ComposeOption<
  PieSeriesOption | GaugeSeriesOption | TitleComponentOption | TooltipComponentOption | LegendComponentOption
>

echarts.use([TitleComponent, TooltipComponent, LegendComponent, PieChart, GaugeChart, CanvasRenderer])

export default echarts
