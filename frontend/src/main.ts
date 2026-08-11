import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { Button, NavBar, Icon, Toast, ConfigProvider, Field, CellGroup, Form, Cell, Tabbar, TabbarItem, Loading, Circle, Progress, Popup, Dialog, Tag, Step, Steps, Slider, Divider, Image, Switch } from 'vant'

import 'vant/lib/index.css'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import { setupStudentElementPlus } from './geeker-adapt/setupElementPlus'
import { clearAuth, getStoredRole, isLoggedIn, resetLoginRedirectState } from './utils/auth'
import { suppressKnownDevConsoleNoise } from './utils/suppressDevConsoleNoise'

suppressKnownDevConsoleNoise()

// 配置路由
const routes = [
  { path: '/login', component: () => import('./views/Login.vue'), meta: { guestOnly: true } },
  { path: '/ops/login', redirect: '/login' },
  {
    path: '/ops',
    component: () => import('./views/OpsLayout.vue'),
    redirect: '/ops/overview',
    meta: { requiresAuth: true, roles: ['maintainer'], title: '平台维护' },
    children: [
      { path: 'overview', component: () => import('./views/OpsOverview.vue'), meta: { title: '维护总览' } },
      { path: 'accounts', component: () => import('./views/OpsAccounts.vue'), meta: { title: '账号维护' } },
      { path: 'usage', component: () => import('./views/OpsUsage.vue'), meta: { title: '使用监管' } },
      { path: 'system-issues', component: () => import('./views/OpsSystemIssues.vue'), meta: { title: '系统异常' } },
    ],
  },
  { 
    path: '/admin',
    component: () => import('./views/AdminLayout.vue'),
    redirect: '/admin/dashboard',
    meta: { requiresAuth: true, roles: ['admin'], title: '管理端' },
    children: [
      { path: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '数据总览' } },
      { path: 'stats', redirect: '/admin/dashboard' },
      { path: 'cases', component: () => import('./views/Cases.vue'), meta: { title: '案件脚本库' } },
      { path: 'cases/:id', component: () => import('./views/CaseDetail.vue'), meta: { title: '案件详情' } },
      { path: 'cases/:id/edit', component: () => import('./views/CaseEdit.vue'), meta: { title: '案件编辑' } },
      { path: 'knowledge', component: () => import('./views/Knowledge.vue'), meta: { title: '知识库管理' } },
      { path: 'roles', component: () => import('./views/Roles.vue'), meta: { title: '角色库' } },
      { path: 'roles/new', component: () => import('./views/RoleEdit.vue'), meta: { title: '新建角色' } },
      { path: 'roles/:id/edit', component: () => import('./views/RoleEdit.vue'), meta: { title: '编辑角色' } },
      { path: 'classes', component: () => import('./views/AdminClasses.vue'), meta: { title: '班级训练' } },
      { path: 'videos', component: () => import('./views/AdminVideoLibrary.vue'), meta: { title: '视频素材库' } },
      { path: 'text-sessions', component: () => import('./views/AdminTextSessions.vue'), meta: { title: '普通训练' } },
      { path: 'text-sessions/:sessionId/report', component: () => import('./views/StudentEvaluation.vue'), meta: { reportRole: 'admin', title: '训练评估报告' } },
      { path: 'text-sessions/:sessionId/dialogue', component: () => import('./views/StudentDialogueRecord.vue'), meta: { reportRole: 'admin', title: '对话记录' } },
      { path: 'video-sessions', component: () => import('./views/AdminVideoSessions.vue'), meta: { title: '视频实训' } },
      { path: 'video-sessions/:sessionId/report', component: () => import('./views/VideoTrainingReportPage.vue'), meta: { reportRole: 'admin', title: '训练评估报告' } },
      { path: 'students', component: () => import('./views/Students.vue'), meta: { title: '学员账号' } },
      { path: 'students/:id', component: () => import('./views/StudentProfile.vue'), meta: { title: '学员档案' } },
      { path: 'profile', component: () => import('./views/Profile.vue'), meta: { title: '个人中心' } },
      { path: 'settings', component: () => import('./views/Profile.vue'), meta: { title: '系统设置' } },
    ]
  },
  { path: '/', redirect: () => {
    if (window.location.port === '6670') return getStoredRole() === 'maintainer' ? '/ops/overview' : '/login'
    return getStoredRole() === 'student' ? '/student/home' : '/admin/dashboard'
  } },
  {
    path: '/student',
    component: () => import('./views/StudentLayout.vue'),
    redirect: '/student/home',
    meta: { requiresAuth: true, roles: ['student', 'admin'], title: '学生控制台' },
    children: [
      { path: 'home', component: () => import('./views/StudentPracticeHome.vue'), meta: { title: '训练首页' } },
      { path: 'training-center', component: () => import('./views/StudentTrainingCenter.vue'), meta: { title: '训练中心' } },
      { path: 'hall', redirect: '/student/training-center?tab=free', meta: { title: '训练中心' } },
      { path: 'videos', component: () => import('./views/StudentVideoHall.vue'), meta: { title: '视频实训' } },
      { path: 'video-history', component: () => import('./views/StudentVideoHistory.vue'), meta: { title: '实训记录' } },
      { path: 'video-report/:sessionId', component: () => import('./views/StudentEvaluation.vue'), meta: { reportKind: 'video', title: '训练评估报告' } },
      { path: 'classes', component: () => import('./views/StudentClasses.vue'), meta: { title: '我的班级' } },
      { path: 'history', component: () => import('./views/StudentPracticeHistory.vue'), meta: { title: '练习记录' } },
      { path: 'text-history', component: () => import('./views/StudentHistory.vue'), meta: { title: '文字训练记录' } },
      { path: 'evaluation', component: () => import('./views/StudentEvaluation.vue'), meta: { title: '训练评估报告' } },
      { path: 'settings', component: () => import('./views/StudentSettings.vue'), meta: { title: '个人设置' } }
    ]
  },
  { path: '/student/history/:id/dialogue', component: () => import('./views/StudentDialogueRecord.vue'), meta: { requiresAuth: true, roles: ['student', 'admin'] } },
  { path: '/student/training/:id', component: () => import('./views/StudentTraining.vue'), meta: { requiresAuth: true, roles: ['student', 'admin'] } },
  { path: '/student/video-training/:id', component: () => import('./views/StudentVideoTraining.vue'), meta: { requiresAuth: true, roles: ['student', 'admin'] } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const DYNAMIC_IMPORT_RECOVERY_KEY = 'vite-dynamic-import-recovery'

router.onError((error, to) => {
  const message = error instanceof Error ? error.message : String(error || '')
  const isDynamicImportFailure =
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed')

  if (!isDynamicImportFailure) return

  const targetPath = typeof to?.fullPath === 'string' ? to.fullPath : window.location.pathname
  const lastRecoveredPath = sessionStorage.getItem(DYNAMIC_IMPORT_RECOVERY_KEY)
  if (lastRecoveredPath === targetPath) {
    console.error('Dynamic import recovery failed after reload:', message)
    return
  }

  sessionStorage.setItem(DYNAMIC_IMPORT_RECOVERY_KEY, targetPath)
  window.location.assign(targetPath)
})

router.beforeEach((to) => {
  if (to.path === '/login') {
    resetLoginRedirectState()
  }

  const token = localStorage.getItem('token')
  const role = getStoredRole()
  const requiredRoles = to.meta.roles as string[] | undefined

  if (to.meta.guestOnly && token) {
    if (role === 'maintainer') return '/ops/overview'
    return role === 'student' ? '/student/home' : '/admin/dashboard'
  }

  if (to.meta.requiresAuth && !isLoggedIn()) {
    return '/login'
  }

  if (requiredRoles && role && !requiredRoles.includes(role)) {
    if (requiredRoles.includes('maintainer')) {
      return role === 'student' ? '/student/home' : '/admin/dashboard'
    }
    if (role === 'maintainer') return '/ops/overview'
    return role === 'student' ? '/student/home' : '/admin/dashboard'
  }

  if (requiredRoles && !role && token) {
    clearAuth()
    return '/login'
  }

  return true
})

router.afterEach(() => {
  sessionStorage.removeItem(DYNAMIC_IMPORT_RECOVERY_KEY)
})

const app = createApp(App)

// 注册 Vant 组件
app.use(Button).use(NavBar).use(Icon).use(Toast).use(ConfigProvider)
app.use(Field).use(CellGroup).use(Form).use(Cell)
app.use(Tabbar).use(TabbarItem)
app.use(Loading).use(Circle).use(Progress).use(Popup).use(Dialog)
app.use(Tag).use(Step).use(Steps).use(Slider)
app.use(Divider).use(Image).use(Switch)

setupStudentElementPlus(app)

app.use(createPinia())
app.use(router)

app.mount('#app')


