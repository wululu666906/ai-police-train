import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { Button, NavBar, Icon, Toast, ConfigProvider, Field, CellGroup, Form, Cell, Tabbar, TabbarItem, Loading, Circle, Progress, Popup, Dialog, Tag, Step, Steps, Slider, Divider, Image } from 'vant'

import 'vant/lib/index.css'
import './style.css'
import App from './App.vue'

// 配置路由
const routes = [
  { path: '/login', component: () => import('./views/Login.vue') },
  { 
    path: '/admin',
    component: () => import('./views/AdminLayout.vue'),
    redirect: '/admin/dashboard',
    children: [
      { path: 'dashboard', component: () => import('./views/Dashboard.vue') },
      { path: 'cases', component: () => import('./views/Cases.vue') },
      { path: 'knowledge', component: () => import('./views/Knowledge.vue') },
      { path: 'roles', component: () => import('./views/Roles.vue') },
      { path: 'profile', component: () => import('./views/Profile.vue') }
    ]
  },
  { path: '/', redirect: '/admin/dashboard' },
  { path: '/training/:id', component: () => import('./views/Training.vue') },
  { path: '/evaluation', component: () => import('./views/EvaluationReport.vue') },
  {
    path: '/student',
    component: () => import('./views/StudentLayout.vue'),
    redirect: '/student/hall',
    children: [
      { path: 'hall', component: () => import('./views/StudentHall.vue') },
      { path: 'history', component: () => import('./views/StudentHistory.vue') },
      { path: 'evaluation', component: () => import('./views/StudentEvaluation.vue') }
    ]
  },
  { path: '/student/training/:id', component: () => import('./views/StudentTraining.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
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
