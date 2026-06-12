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
      { path: 'students', component: () => import('./views/Students.vue') },
      { path: 'students/:id', component: () => import('./views/StudentProfile.vue') },
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
      { path: 'history', component: () => import('./views/StudentHistory.vue') },
      { path: 'evaluation', component: () => import('./views/StudentEvaluation.vue') }
    ]
  },
  { path: '/student/training/:id', component: () => import('./views/StudentTraining.vue'), meta: { requiresAuth: true, roles: ['student', 'admin'] } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
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
app.use(Divider).use(Image).use(Dialog).use(Switch)

setupStudentElementPlus(app)

app.use(createPinia())
app.use(router)

app.mount('#app')
