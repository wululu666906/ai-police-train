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

// 配置路由
const routes = [
  { path: '/login', component: () => import('./views/Login.vue'), meta: { guestOnly: true } },
  { 
    path: '/admin',
    component: () => import('./views/AdminLayout.vue'),
    redirect: '/admin/dashboard',
    meta: { requiresAuth: true, roles: ['admin'] },
    children: [
      { path: 'dashboard', component: () => import('./views/Dashboard.vue') },
      { path: 'cases', component: () => import('./views/Cases.vue') },
      { path: 'cases/:id', component: () => import('./views/CaseDetail.vue') },
      { path: 'cases/:id/edit', component: () => import('./views/CaseEdit.vue') },
      { path: 'knowledge', component: () => import('./views/Knowledge.vue') },
      { path: 'roles', component: () => import('./views/Roles.vue') },
      { path: 'roles/new', component: () => import('./views/RoleEdit.vue') },
      { path: 'roles/:id/edit', component: () => import('./views/RoleEdit.vue') },
      { path: 'classes', component: () => import('./views/AdminClasses.vue') },
      { path: 'videos', component: () => import('./views/AdminVideoLibrary.vue') },
      { path: 'video-sessions', component: () => import('./views/AdminVideoSessions.vue') },
      { path: 'video-sessions/:sessionId/report', component: () => import('./views/VideoTrainingReportPage.vue'), meta: { reportRole: 'admin' } },
      { path: 'students', component: () => import('./views/Students.vue') },
      { path: 'students/:id', component: () => import('./views/StudentProfile.vue') },
      { path: 'face-demo', component: () => import('./views/FaceRecognitionDemo.vue') },
      { path: 'profile', component: () => import('./views/Profile.vue') }
    ]
  },
  { path: '/', redirect: () => (getStoredRole() === 'student' ? '/student/hall' : '/admin/dashboard') },
  {
    path: '/student',
    component: () => import('./views/StudentLayout.vue'),
    redirect: '/student/hall',
    meta: { requiresAuth: true, roles: ['student', 'admin'] },
    children: [
      { path: 'hall', component: () => import('./views/StudentHall.vue') },
      { path: 'videos', component: () => import('./views/StudentVideoHall.vue') },
      { path: 'video-history', component: () => import('./views/StudentVideoHistory.vue') },
      { path: 'video-report/:sessionId', component: () => import('./views/VideoTrainingReportPage.vue'), meta: { reportRole: 'student' } },
      { path: 'classes', component: () => import('./views/StudentClasses.vue') },
      { path: 'history', component: () => import('./views/StudentHistory.vue') },
      { path: 'evaluation', component: () => import('./views/StudentEvaluation.vue') },
      { path: 'settings', component: () => import('./views/StudentSettings.vue') }
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
    sessionStorage.removeItem(DYNAMIC_IMPORT_RECOVERY_KEY)
    console.error('Dynamic import recovery failed after reload:', message)
    return
  }

  sessionStorage.setItem(DYNAMIC_IMPORT_RECOVERY_KEY, targetPath)
  window.location.assign(targetPath)
})

router.beforeEach((to) => {
  if (sessionStorage.getItem(DYNAMIC_IMPORT_RECOVERY_KEY) === to.fullPath) {
    sessionStorage.removeItem(DYNAMIC_IMPORT_RECOVERY_KEY)
  }

  if (to.path === '/login') {
    resetLoginRedirectState()
  }

  const token = localStorage.getItem('token')
  const role = getStoredRole()
  const requiredRoles = to.meta.roles as string[] | undefined

  if (to.meta.guestOnly && token) {
    return role === 'student' ? '/student/hall' : '/admin/dashboard'
  }

  if (to.meta.requiresAuth && !isLoggedIn()) {
    return '/login'
  }

  if (requiredRoles && role && !requiredRoles.includes(role)) {
    return role === 'student' ? '/student/hall' : '/admin/dashboard'
  }

  if (requiredRoles && !role && token) {
    clearAuth()
    return '/login'
  }

  return true
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
