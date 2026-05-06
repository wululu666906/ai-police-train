import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { Button, NavBar, Icon, Toast, ConfigProvider, Field, CellGroup, Form, Cell, Tabbar, TabbarItem, Loading, Circle, Progress, Popup, Dialog, Tag, Step, Steps, Slider, Divider, Image } from 'vant'

import 'vant/lib/index.css'
import './style.css'
import App from './App.vue'

const getStoredRole = () => localStorage.getItem('role')
const isLoggedIn = () => Boolean(localStorage.getItem('token'))

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
      { path: 'data-quality', component: () => import('./views/DataQuality.vue') },
      { path: 'knowledge', component: () => import('./views/Knowledge.vue') },
      { path: 'roles', component: () => import('./views/Roles.vue') },
      { path: 'profile', component: () => import('./views/Profile.vue') }
    ]
  },
  { path: '/', redirect: () => (getStoredRole() === 'student' ? '/student/hall' : '/admin/dashboard') },
  { path: '/training/:id', component: () => import('./views/Training.vue'), meta: { requiresAuth: true, roles: ['admin'] } },
  { path: '/evaluation', component: () => import('./views/EvaluationReport.vue'), meta: { requiresAuth: true, roles: ['admin'] } },
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
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
    localStorage.removeItem('user_id')
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
app.use(Divider).use(Image).use(Dialog)

app.use(createPinia())
app.use(router)

app.mount('#app')
