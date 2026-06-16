import type { App, Plugin } from 'vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import {
  ElAvatar,
  ElBadge,
  ElButton,
  ElCol,
  ElConfigProvider,
  ElContainer,
  ElDescriptions,
  ElDescriptionsItem,
  ElEmpty,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElHeader,
  ElIcon,
  ElLoading,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElPagination,
  ElProgress,
  ElRow,
  ElScrollbar,
  ElSelect,
  ElSkeleton,
  ElSwitch,
  ElTabPane,
  ElTabs,
  ElTag,
  ElTooltip,
} from 'element-plus'

const studentElementComponents: Plugin[] = [
  ElConfigProvider,
  ElContainer,
  ElHeader,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElButton,
  ElTag,
  ElRow,
  ElCol,
  ElScrollbar,
  ElEmpty,
  ElSkeleton,
  ElDescriptions,
  ElDescriptionsItem,
  ElSwitch,
  ElIcon,
  ElLoading,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElAvatar,
  ElBadge,
  ElTooltip,
  ElTabs,
  ElTabPane,
  ElSelect,
  ElOption,
  ElPagination,
  ElProgress,
]

export function setupStudentElementPlus(app: App) {
  studentElementComponents.forEach((component) => {
    app.use(component)
  })
}

export const studentElementLocale = zhCn
