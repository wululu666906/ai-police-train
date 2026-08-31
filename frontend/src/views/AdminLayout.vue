<template>
  <div class="admin-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <div v-if="menuOpen" class="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" @click="menuOpen = false"></div>

    <aside
      :class="[
        'admin-sidebar fixed inset-y-0 left-0 z-40 transition-transform duration-200 lg:translate-x-0',
        menuOpen ? 'translate-x-0' : '-translate-x-full',
      ]"
    >
      <div class="admin-brand">
        <div class="crest">
          <van-icon name="shield-o" size="19" />
        </div>
        <div class="admin-brand-text">
          <b>虚拟警情模拟训练平台</b>
          <span>ADMIN CONSOLE</span>
        </div>
      </div>

      <nav class="admin-nav">
        <template v-for="group in navGroups" :key="group.name || group.label">
          <button
            v-if="group.name"
            type="button"
            class="admin-nav-item"
            :class="{ active: active === group.name, 'admin-nav-item--collapsed': sidebarCollapsed }"
            :title="sidebarCollapsed ? group.label : ''"
            @click="onChange(group.name)"
          >
            <span class="admin-nav-icon"><van-icon :name="group.icon" size="19" /></span>
            <span class="admin-nav-label">{{ group.label }}</span>
          </button>

          <div
            v-else
            class="admin-group"
            :class="{ 'admin-group--flyout': sidebarCollapsed, 'admin-group--flyout-open': sidebarCollapsed && openFlyoutGroup === group.label }"
            @mouseenter="openFlyout(group.label)"
            @mouseleave="scheduleCloseFlyout"
            @focusin="openFlyout(group.label)"
            @focusout="handleFlyoutFocusOut"
          >
            <button
              type="button"
              class="admin-nav-item admin-nav-item--group"
              :class="{ 'admin-nav-item--collapsed': sidebarCollapsed, 'active': isGroupActive(group) }"
              :aria-expanded="sidebarCollapsed ? openFlyoutGroup === group.label : !isGroupCollapsed(group.label)"
              :aria-haspopup="sidebarCollapsed ? 'menu' : undefined"
              :title="sidebarCollapsed ? group.label : ''"
              @click="sidebarCollapsed ? toggleFlyout(group.label) : toggleGroup(group.label)"
              @keydown="handleGroupKeydown($event, group)"
            >
              <span class="admin-nav-icon"><van-icon :name="group.icon" size="19" /></span>
              <span class="admin-nav-label">{{ group.label }}</span>
              <span class="admin-nav-arrow" :class="{ 'admin-nav-arrow--closed': isGroupCollapsed(group.label) }">⌄</span>
            </button>
            <div
              v-if="sidebarCollapsed && openFlyoutGroup === group.label"
              class="admin-flyout"
              role="menu"
              :aria-label="`${group.label}子菜单`"
              @mouseenter="cancelCloseFlyout"
              @mouseleave="scheduleCloseFlyout"
            >
              <button
                v-for="child in group.children || []"
                :key="child.name"
                type="button"
                class="admin-flyout-item"
                role="menuitem"
                :class="{ active: active === child.name }"
                @click="onChange(child.name)"
              >
                <span>{{ child.shortLabel || child.label }}</span>
              </button>
            </div>
            <div v-else-if="!sidebarCollapsed && !isGroupCollapsed(group.label)" class="admin-sub">
              <button
                v-for="child in group.children || []"
                :key="child.name"
                type="button"
                class="admin-nav-item admin-nav-item--sub"
                :class="{ active: active === child.name }"
                @click="onChange(child.name)"
              >
                <span class="admin-nav-label">{{ child.label }}</span>
              </button>
            </div>
          </div>
        </template>
      </nav>

    </aside>

    <main class="admin-main">
      <header class="admin-topbar">
        <div class="admin-top-left">
          <button
            type="button"
            class="admin-sidebar-toggle hidden lg:inline-flex"
            @click="toggleSidebar"
            :title="sidebarCollapsed ? '展开导航' : '收起导航'"
            :aria-label="sidebarCollapsed ? '展开导航' : '收起导航'"
            :aria-pressed="sidebarCollapsed"
          >
            <van-icon :name="sidebarCollapsed ? 'arrow-right' : 'arrow-left'" size="18" />
          </button>
          <button
            type="button"
            class="admin-sidebar-toggle inline-flex lg:hidden"
            @click="menuOpen = true"
            aria-label="打开导航"
            title="打开导航"
          >
            <van-icon name="wap-nav" size="18" />
          </button>

          <div class="admin-top-title">{{ currentItem?.label || route.meta.title || '管理后台' }}</div>
        </div>

        <div class="admin-top-actions">
          <van-button
            size="small"
            plain
            type="primary"
            icon="bell"
            class="admin-head-btn admin-head-btn--icon"
            aria-label="通知中心"
            title="通知中心"
            @click="router.push('/admin/notifications')"
          />

          <van-button
            size="small"
            plain
            type="primary"
            icon="exchange"
            @click="router.push('/student/home')"
            class="admin-head-btn admin-head-btn--link"
          >
            切换到学员端
          </van-button>

          <van-button
            size="small"
            plain
            type="danger"
            icon="sign"
            class="admin-head-btn"
            @click="logout"
          >
            退出登录
          </van-button>

          <div class="admin-user">
            <div class="admin-avatar">{{ avatarText }}</div>
            <b>{{ username }}</b>
            <span>{{ roleLabel }}</span>
          </div>
        </div>
      </header>

      <div class="admin-tabs">
        <button
          v-for="tab in pageTabs"
          :key="tab.path"
          type="button"
          class="page-tab"
          :class="{ active: route.fullPath === tab.path }"
          @click="activateTab(tab.path)"
        >
          <span v-if="route.fullPath === tab.path" class="page-tab-dot"></span>
          <span class="page-tab-label">{{ tab.label }}</span>
          <span
            v-if="tab.closable"
            class="page-tab-close"
            @click.stop="closeTab(tab.path)"
          >
            <van-icon name="cross" size="12" />
          </span>
        </button>
      </div>

      <div class="admin-content" :class="{ 'admin-content--fixed': isFixedContentPage }">
        <router-view :key="route.path" v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showSuccessToast } from 'vant'
import { clearAuth } from '../utils/auth'

const SIDEBAR_COLLAPSED_KEY = 'admin.sidebar.collapsed'

const router = useRouter()
const route = useRoute()

const active = ref('dashboard')
const menuOpen = ref(false)
const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1')
const collapsedGroups = ref<Record<string, boolean>>({})
const openFlyoutGroup = ref('')
const pageTabs = ref<PageTab[]>([])
let flyoutCloseTimer: ReturnType<typeof setTimeout> | null = null

type AdminNavLeaf = {
  name: string
  label: string
  shortLabel?: string
  icon?: string
}

type AdminNavGroup = {
  label: string
  icon: string
  name?: string
  shortLabel?: string
  children?: AdminNavLeaf[]
}

type PageTab = {
  path: string
  label: string
  closable: boolean
}

const navGroups: AdminNavGroup[] = [
  { name: 'dashboard', label: '工作台', shortLabel: '首页', icon: 'home-o' },
  {
    label: '内容中心',
    icon: 'apps-o',
    children: [
      { name: 'cases', label: '案件与场景', shortLabel: '案件' },
      { name: 'roles', label: '角色配置', shortLabel: '角色' },
      { name: 'knowledge', label: '知识库', shortLabel: '知识' },
      { name: 'videos', label: '视频内容', shortLabel: '视频' },
    ],
  },
  {
    label: '教务管理',
    icon: 'friends-o',
    children: [
      { name: 'classes', label: '班级管理', shortLabel: '班级' },
      { name: 'students', label: '学员关系', shortLabel: '学员' },
    ],
  },
  {
    label: '训练管理',
    icon: 'todo-list-o',
    children: [
      { name: 'text-sessions', label: '普通训练', shortLabel: '普通训练' },
      { name: 'video-sessions', label: '视频训练记录', shortLabel: '视频记录' },
    ],
  },
  { name: 'settings', label: '系统设置', shortLabel: '设置', icon: 'setting-o' },
  { name: 'notifications', label: '通知中心', shortLabel: '通知', icon: 'bell' },
]

const navItems = computed(() => navGroups.flatMap((item) => item.name ? [item as AdminNavLeaf] : (item.children || [])))

const username = computed(() => localStorage.getItem('username') || '管理员')
const roleLabel = computed(() => (localStorage.getItem('role') === 'admin' ? '管理员账号' : '学员账号'))
const avatarText = computed(() => username.value.slice(0, 1).toUpperCase())

const logout = async () => {
  try {
    await showConfirmDialog({
      title: '退出登录',
      message: '确认退出当前管理账号？',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
    clearAuth()
    router.push('/login')
    showSuccessToast('已成功退出')
  } catch {
    // cancelled
  }
}

const currentItem = computed(() => navItems.value.find((item) => item.name === active.value))
const isFixedContentPage = computed(() => route.path === '/admin/students')

const getPageTabLabel = () => {
  const metaTitle = route.meta.title
  const isNavRoot = route.path.split('/').filter(Boolean).length <= 2

  if (isNavRoot) {
    return currentItem.value?.shortLabel || currentItem.value?.label || (typeof metaTitle === 'string' ? metaTitle : route.path)
  }

  return typeof metaTitle === 'string' ? metaTitle : currentItem.value?.label || route.path
}

const ensureActiveTab = () => {
  const existing = pageTabs.value.find((tab) => tab.path === route.fullPath)
  const label = getPageTabLabel()

  if (existing) {
    existing.label = label
    return
  }

  pageTabs.value.push({
    path: route.fullPath,
    label,
    closable: route.path !== '/admin/dashboard',
  })
}

watch(
  () => route.path,
  (val) => {
    menuOpen.value = false
    openFlyoutGroup.value = ''
    if (val.includes('/dashboard')) active.value = 'dashboard'
    else if (val.includes('/text-sessions')) active.value = 'text-sessions'
    else if (val.includes('/cases')) active.value = 'cases'
    else if (val.includes('/videos')) active.value = 'videos'
    else if (val.includes('/video-sessions')) active.value = 'video-sessions'
    else if (val.includes('/knowledge')) active.value = 'knowledge'
    else if (val.includes('/roles')) active.value = 'roles'
    else if (val.includes('/classes')) active.value = 'classes'
    else if (val.includes('/students')) active.value = 'students'
    else if (val.includes('/profile')) active.value = 'profile'
    else if (val.includes('/settings')) active.value = 'settings'
    else if (val.includes('/notifications')) active.value = 'notifications'

    ensureActiveTab()
  },
  { immediate: true }
)

watch(sidebarCollapsed, (value) => {
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? '1' : '0')
  if (!value) openFlyoutGroup.value = ''
})

const onChange = (name: string) => {
  openFlyoutGroup.value = ''
  menuOpen.value = false
  router.push(`/admin/${name}`)
}

const isGroupActive = (group: AdminNavGroup) =>
  Boolean(group.children?.some((child) => child.name === active.value))

const openFlyout = (label: string) => {
  if (!sidebarCollapsed.value) return
  cancelCloseFlyout()
  openFlyoutGroup.value = label
}

const scheduleCloseFlyout = () => {
  if (!sidebarCollapsed.value) return
  cancelCloseFlyout()
  flyoutCloseTimer = setTimeout(() => {
    openFlyoutGroup.value = ''
    flyoutCloseTimer = null
  }, 180)
}

const cancelCloseFlyout = () => {
  if (flyoutCloseTimer) {
    clearTimeout(flyoutCloseTimer)
    flyoutCloseTimer = null
  }
}

const handleFlyoutFocusOut = (event: FocusEvent) => {
  if (!sidebarCollapsed.value) return
  const current = event.currentTarget as HTMLElement | null
  const next = event.relatedTarget as Node | null
  if (current && next && current.contains(next)) return
  scheduleCloseFlyout()
}

const handleGroupKeydown = (event: KeyboardEvent, group: AdminNavGroup) => {
  if (!sidebarCollapsed.value) return
  if (event.key === 'Escape') {
    openFlyoutGroup.value = ''
    return
  }
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    toggleFlyout(group.label)
  }
}

const activateTab = (path: string) => {
  if (path !== route.fullPath) router.push(path)
}

const closeTab = (path: string) => {
  const index = pageTabs.value.findIndex((tab) => tab.path === path)
  const tab = pageTabs.value[index]
  if (!tab?.closable) return

  pageTabs.value.splice(index, 1)

  if (path !== route.fullPath) return

  const nextTab = pageTabs.value[index] || pageTabs.value[index - 1] || pageTabs.value[0]
  router.push(nextTab?.path || '/admin/dashboard')
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const isGroupCollapsed = (label: string) => Boolean(collapsedGroups.value[label])

const toggleGroup = (label: string) => {
  collapsedGroups.value[label] = !collapsedGroups.value[label]
}

const toggleFlyout = (label: string) => {
  openFlyoutGroup.value = openFlyoutGroup.value === label ? '' : label
}

</script>

<style scoped>
.admin-shell {
  --sidebar-width: 226px;
  --admin-navy: #0b1e3c;
  --admin-navy-panel: #102947;
  --admin-blue: #0b49b4;
  --admin-blue-hover: #083f9d;
  --admin-bg: #eef3f8;
  --admin-card-border: #e3eaf3;
  height: 100dvh;
  max-height: 100dvh;
  overflow: hidden;
  display: flex;
  background: var(--admin-bg);
  color: #17213b;
}

.admin-shell.sidebar-collapsed {
  --sidebar-width: 60px;
}

.admin-sidebar {
  width: var(--sidebar-width);
  height: 100dvh;
  max-height: 100dvh;
  display: flex;
  flex: none;
  flex-direction: column;
  background: var(--admin-navy);
  color: #c4ccdc;
  box-shadow: none;
  will-change: width, transform;
}

.admin-brand {
  height: 68px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  overflow: hidden;
  flex: none;
}

.crest {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  border: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #dbe8ff;
  background: var(--admin-blue);
  flex: none;
}

.admin-brand-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.admin-brand-text b {
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0;
  white-space: nowrap;
}

.admin-brand-text span {
  color: rgba(216, 225, 244, 0.56);
  font-size: 10px;
  letter-spacing: 0.12em;
  white-space: nowrap;
}

.admin-nav {
  flex: 1;
  overflow: auto;
  padding: 13px 6px 24px;
}

.admin-nav-item {
  width: 100%;
  height: 44px;
  border: 0;
  border-radius: 8px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  gap: 11px;
  cursor: pointer;
  color: #bdc6d8;
  background: transparent;
  margin: 2px 0;
  position: relative;
  text-align: left;
  transition:
    background 0.18s ease,
    color 0.18s ease;
}

.admin-nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.admin-nav-item.active {
  background: var(--admin-blue);
  color: #fff;
}

.admin-nav-icon {
  width: 19px;
  height: 19px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.admin-nav-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-nav-arrow {
  margin-left: auto;
  color: rgba(196, 204, 220, 0.72);
  transition: transform 0.18s ease;
}

.admin-nav-arrow--closed {
  transform: rotate(-90deg);
}

.admin-group {
  margin-top: 5px;
}

.admin-nav-item--group {
  cursor: default;
}

.admin-sub {
  padding-left: 36px;
}

.admin-sub .admin-nav-item {
  height: 40px;
  padding-left: 15px;
  font-size: 13px;
}

.admin-main {
  height: 100dvh;
  max-height: 100dvh;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--admin-bg);
  transition: margin-left 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: margin-left;
}

.admin-topbar {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid var(--admin-card-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  gap: 16px;
  flex: none;
}

.admin-top-left {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-sidebar-toggle {
  width: 40px;
  height: 40px;
  align-items: center;
  justify-content: center;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  color: #53647d;
  background: #fff;
  font-size: 23px;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  flex: none;
  transition:
    background 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease;
}

.admin-sidebar-toggle:hover {
  background: #f5f8fd;
  border-color: #c8d5e6;
  color: var(--admin-blue);
}

.admin-top-title {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  color: #17213b;
  font-size: 18px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-top-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
}

.admin-head-btn {
  height: 34px !important;
  border-color: #dfe5ed !important;
  border-radius: 6px !important;
  background: #fff !important;
  color: #5d6677 !important;
  padding: 0 12px !important;
}

.admin-head-btn--icon {
  width: 34px !important;
  padding: 0 !important;
}

.admin-head-btn--link {
  color: var(--admin-blue) !important;
}

.admin-user {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #253047;
  white-space: nowrap;
}

.admin-user b {
  font-size: 14px;
  font-weight: 800;
}

.admin-user span {
  color: #8b96a8;
  font-size: 12px;
}

.admin-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--admin-blue);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
}

.admin-tabs {
  height: 40px;
  background: #fff;
  border-bottom: 1px solid var(--admin-card-border);
  display: flex;
  align-items: center;
  padding: 0 8px;
  gap: 5px;
  flex: none;
  overflow-x: auto;
  overflow-y: hidden;
}

.page-tab {
  height: 31px;
  max-width: 180px;
  border: 0;
  border-radius: 5px;
  background: #f2f4f7;
  color: #5d6677;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 12px;
  font-size: 13px;
  cursor: pointer;
  flex: none;
  min-width: 0;
  white-space: nowrap;
}

.page-tab.active {
  background: var(--admin-blue);
  color: #fff;
}

.page-tab-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
  flex: none;
}

.page-tab-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.page-tab-close {
  width: 17px;
  height: 17px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  margin-right: -4px;
  color: inherit;
}

.page-tab-close:hover {
  background: rgba(23, 33, 59, 0.1);
}

.page-tab.active .page-tab-close:hover {
  background: rgba(255, 255, 255, 0.18);
}

.admin-content {
  flex: 1;
  overflow: auto;
  padding: 24px;
  background: var(--admin-bg);
}

.admin-content--fixed {
  min-height: 0;
  overflow: hidden;
  overscroll-behavior: none;
}

.sidebar-collapsed .admin-brand {
  justify-content: center;
  padding: 0;
}

.sidebar-collapsed .admin-brand-text,
.sidebar-collapsed .admin-nav-label,
.sidebar-collapsed .admin-nav-arrow,
.sidebar-collapsed .admin-sub {
  display: none;
}

.sidebar-collapsed .admin-sidebar,
.sidebar-collapsed .admin-nav {
  overflow: visible;
}

.admin-group--flyout {
  position: relative;
}

.admin-flyout {
  position: absolute;
  top: 0;
  left: 100%;
  z-index: 60;
  min-width: 168px;
  padding: 8px 8px 8px 14px;
  margin-left: -6px;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
}

.admin-group--flyout-open .admin-nav-item--group {
  background: rgba(255, 255, 255, 0.08);
}

.admin-flyout-item {
  display: flex;
  width: 100%;
  align-items: center;
  min-height: 40px;
  padding: 0 12px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #253047;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.admin-flyout-item:hover,
.admin-flyout-item:focus-visible,
.admin-flyout-item.active {
  background: #eff6ff;
  color: #2563eb;
  outline: none;
}

.sidebar-collapsed .admin-nav-item,
.sidebar-collapsed .admin-nav-item:hover {
  justify-content: center;
  padding: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.28s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(12px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

.admin-content :deep(.rounded-3xl),
.admin-content :deep(.rounded-2xl),
.admin-content :deep(.rounded-xl) {
  border-radius: 8px !important;
}

.admin-content :deep(.shadow-xl),
.admin-content :deep(.shadow-lg),
.admin-content :deep(.shadow-md),
.admin-content :deep(.shadow-sm) {
  box-shadow: 0 4px 16px rgba(35, 56, 104, 0.07) !important;
}

.admin-content :deep(.border-gray-100),
.admin-content :deep(.border-gray-200),
.admin-content :deep(.border-slate-200),
.admin-content :deep(.border-slate-100) {
  border-color: #e6ebf3 !important;
}

.admin-content :deep(.bg-white) {
  background-color: #fff !important;
}

.admin-content :deep(.bg-gray-50),
.admin-content :deep(.bg-slate-50) {
  background-color: #fafbfd !important;
}

.admin-content :deep(.text-gray-800),
.admin-content :deep(.text-slate-800) {
  color: #17213b !important;
}

.admin-content :deep(.text-gray-700),
.admin-content :deep(.text-slate-700) {
  color: #253047 !important;
}

.admin-content :deep(.text-gray-500),
.admin-content :deep(.text-gray-400),
.admin-content :deep(.text-slate-500),
.admin-content :deep(.text-slate-400) {
  color: #8b96aa !important;
}

.admin-content :deep(.admin-card),
.admin-content :deep(.admin-filter-panel),
.admin-content :deep(.admin-table-panel),
.admin-content :deep(.admin-table-card),
.admin-content :deep(.stat-card),
.admin-content :deep(.metric-card),
.admin-content :deep(.a-card) {
  border: 1px solid #e6ebf3 !important;
  border-radius: 8px !important;
  background: #fff !important;
  box-shadow: 0 4px 16px rgba(35, 56, 104, 0.07) !important;
}

.admin-content :deep(.admin-filter-panel),
.admin-content :deep(.filter-bar),
.admin-content :deep(.admin-filter-bar) {
  background: #fff !important;
  border-color: #e6ebf3 !important;
}

.admin-content :deep(table) {
  border-collapse: collapse;
}

.admin-content :deep(th) {
  background: #fafbfd !important;
  color: #263248 !important;
  font-weight: 700 !important;
}

.admin-content :deep(td),
.admin-content :deep(th) {
  border-color: #edf0f5 !important;
}

.admin-content :deep(tr:hover td) {
  background: #fbfcff !important;
}

.admin-content :deep(input),
.admin-content :deep(select),
.admin-content :deep(textarea),
.admin-content :deep(.el-input__wrapper),
.admin-content :deep(.el-select__wrapper) {
  border: 1px solid #dde3ec !important;
  border-color: #dde3ec !important;
  border-radius: 7px !important;
  box-shadow: none !important;
}

.admin-content :deep(input:focus),
.admin-content :deep(select:focus),
.admin-content :deep(textarea:focus),
.admin-content :deep(.el-input__wrapper.is-focus),
.admin-content :deep(.el-select__wrapper.is-focused) {
  border-color: #7996f7 !important;
  box-shadow: 0 0 0 3px rgba(53, 102, 246, 0.08) !important;
}

.admin-content :deep(.van-button),
.admin-content :deep(.el-button) {
  border-radius: 7px !important;
}

.admin-content :deep(.van-button--primary),
.admin-content :deep(.el-button--primary) {
  background: var(--admin-blue) !important;
  border-color: var(--admin-blue) !important;
  color: #fff !important;
}

.admin-content :deep(.van-tag),
.admin-content :deep(.el-tag) {
  border-radius: 7px !important;
}

@media (min-width: 1024px) {
  .admin-shell,
  .admin-sidebar,
  .admin-main {
    height: calc(100dvh / var(--platform-display-scale, 1));
    max-height: calc(100dvh / var(--platform-display-scale, 1));
  }

  .admin-sidebar {
    width: var(--sidebar-width);
    transition:
      width 0.38s cubic-bezier(0.22, 1, 0.36, 1),
      transform 0.2s ease;
  }

  .admin-main {
    margin-left: var(--sidebar-width);
  }
}
</style>

