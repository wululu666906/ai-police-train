import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { PieSeriesOption } from 'echarts/charts'
import type { LegendComponentOption, TitleComponentOption, TooltipComponentOption } from 'echarts/components'
import type { ComposeOption } from 'echarts/core'

export type ECOption = ComposeOption<
  PieSeriesOption | TitleComponentOption | TooltipComponentOption | LegendComponentOption
>

echarts.use([TitleComponent, TooltipComponent, LegendComponent, PieChart, CanvasRenderer])

export default echarts
