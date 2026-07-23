<template>
  <div class="admin-shell h-screen overflow-hidden bg-[var(--police-bg)] lg:flex" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <div v-if="menuOpen" class="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" @click="menuOpen = false"></div>

    <aside
      :class="[
        'admin-sidebar fixed inset-y-0 left-0 z-40 flex flex-col shadow-xl transition-transform duration-200 lg:translate-x-0',
        menuOpen ? 'translate-x-0' : '-translate-x-full',
      ]"
    >
      <div class="border-b border-white/10">
        <div
          :class="[
            'pt-5 transition-[padding] duration-[260ms] ease-out',
            sidebarCollapsed ? 'px-0 pb-4' : 'px-4 pb-4',
          ]"
        >
          <div :class="['flex items-center overflow-hidden', sidebarCollapsed ? 'justify-center gap-0' : 'gap-3']">
            <div class="flex h-9 w-9 items-center justify-center rounded-[8px] bg-[var(--police-primary)] text-white shadow-[0_4px_12px_rgba(0,48,135,0.35)]">
              <van-icon name="shield-o" size="20" />
            </div>

            <div
              :class="[
                'min-w-0 overflow-hidden transition-[max-width,opacity,transform] duration-[320ms] ease-[cubic-bezier(0.22,1,0.36,1)]',
                sidebarCollapsed ? 'max-w-0 -translate-x-1 opacity-0 delay-0' : 'max-w-[160px] translate-x-0 opacity-100 delay-75',
              ]"
            >
              <h1 class="truncate text-[13px] font-semibold leading-tight text-white">警情模拟平台</h1>
              <p class="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-blue-100/55">Admin Console</p>
            </div>
          </div>
        </div>
      </div>

      <nav
          :class="[
            'flex-1 overflow-y-auto transition-[padding] duration-[260ms] ease-out',
          sidebarCollapsed ? 'flex flex-col items-center px-0 py-3 space-y-1' : 'px-2 py-3 space-y-1',
        ]"
      >
        <button
          v-for="item in navItems"
          :key="item.name"
          type="button"
          :title="sidebarCollapsed ? item.label : ''"
          @click="onChange(item.name)"
          :class="[
            'admin-nav-item group relative isolate grid items-center overflow-hidden rounded-[8px] text-left transition-[padding,gap,background-color,color,box-shadow] duration-200',
            sidebarCollapsed ? 'admin-nav-item--collapsed h-10 w-10 grid-cols-[1fr] justify-items-center px-0 py-0 gap-x-0' : 'w-full grid-cols-[32px_minmax(0,1fr)] px-3 py-2.5 gap-x-2.5',
            active === item.name ? 'bg-[var(--police-primary)] text-white shadow-[0_2px_8px_rgba(0,48,135,0.4)]' : 'text-white/65 hover:bg-[#002d6e] hover:text-white',
          ]"
        >
            <span
              :class="[
                'relative z-[1] flex items-center justify-center rounded-[6px] transition-[background-color,color,transform] duration-200',
                'h-8 w-8 shrink-0',
                active === item.name
                  ? 'bg-white/10 text-white'
                  : 'bg-transparent text-white/70 group-hover:text-white',
              ]"
            >
              <van-icon :name="item.icon" size="20" />
            </span>

          <div
            :class="[
              'relative z-[1] min-w-0 overflow-hidden whitespace-nowrap transition-[max-width,opacity,transform] duration-200',
              sidebarCollapsed ? 'max-w-0 -translate-x-1 opacity-0 delay-0' : 'max-w-[132px] translate-x-0 opacity-100 delay-75',
            ]"
          >
            <span class="block truncate text-[14px] font-medium">{{ item.label }}</span>
          </div>
        </button>
      </nav>

      <div
        :class="[
          'hidden transition-[padding] duration-[380ms] ease-[cubic-bezier(0.22,1,0.36,1)] lg:block',
          sidebarCollapsed ? 'flex justify-center px-0 py-4' : 'px-3 py-4',
        ]"
      >
        <button
          type="button"
          :title="sidebarCollapsed ? '展开导航' : '收起导航'"
          @click="toggleSidebar"
          :class="[
            'group grid items-center overflow-hidden rounded-[8px] text-left text-white/65 transition-[padding,gap,background-color,color] duration-200 hover:bg-[#002d6e] hover:text-white',
            sidebarCollapsed ? 'h-10 w-10 grid-cols-[1fr] justify-items-center px-0 py-0 gap-x-0' : 'w-full grid-cols-[32px_minmax(0,1fr)] px-3 py-2.5 gap-x-2.5',
          ]"
        >
          <span
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] bg-transparent text-blue-50 transition-[background-color,color,transform] duration-200 group-hover:text-white"
          >
            <van-icon :name="sidebarCollapsed ? 'arrow' : 'arrow-left'" size="18" />
          </span>

          <span
            :class="[
              'min-w-0 overflow-hidden whitespace-nowrap font-medium transition-[max-width,opacity,transform] duration-[320ms] ease-[cubic-bezier(0.22,1,0.36,1)]',
              sidebarCollapsed ? 'max-w-0 -translate-x-1 opacity-0 delay-0' : 'max-w-[72px] translate-x-0 opacity-100 delay-75',
            ]"
          >
            {{ sidebarCollapsed ? '展开' : '收起' }}
          </span>
        </button>
      </div>
    </aside>

    <main class="admin-main flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
      <header
        class="sticky top-0 z-20 flex h-14 flex-shrink-0 items-center justify-between border-b border-[var(--police-border)] bg-white px-4 lg:px-6"
      >
        <div class="flex min-w-0 items-center gap-4">
          <button
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500 lg:hidden"
            @click="menuOpen = true"
          >
            <van-icon name="wap-nav" size="18" />
          </button>

          <div class="min-w-0">
            <h2 class="truncate text-base font-semibold text-[var(--police-text-primary)]">{{ currentItem?.label || '管理后台' }}</h2>
            <p class="truncate text-[13px] text-[var(--police-text-muted)]">管理端负责配置、审核与发布，训练统一走学员链路</p>
          </div>
        </div>

        <div class="flex items-center gap-3 lg:gap-5">
          <van-button
            size="small"
            plain
            type="primary"
            icon="exchange"
            @click="router.push('/student/hall')"
            class="!rounded-[6px] !border-[var(--police-border)] !bg-white !px-4 !text-[var(--police-primary)] lg:!px-4"
          >
            切换到学员端
          </van-button>

          <div class="hidden text-right sm:block">
            <p class="text-sm font-bold text-slate-700">{{ username }}</p>
            <p class="text-xs text-slate-400">{{ roleLabel }}</p>
          </div>

          <div class="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--police-primary)] text-[13px] font-semibold text-white">
            {{ avatarText }}
          </div>
        </div>
      </header>

      <div class="admin-content flex-1 overflow-y-auto p-4 lg:p-6">
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const SIDEBAR_COLLAPSED_KEY = 'admin.sidebar.collapsed'

const router = useRouter()
const route = useRoute()

const active = ref('dashboard')
const menuOpen = ref(false)
const sidebarCollapsed = ref(false)

const rawNavItems = [
  { name: 'dashboard', label: '数据总览', shortLabel: '总览', icon: 'bar-chart-o' },
  { name: 'cases', label: '案件剧本库', shortLabel: '案件', icon: 'orders-o' },
  { name: 'videos', label: '视频素材库', shortLabel: '视频', icon: 'video-o' },
  { name: 'video-sessions', label: '实训记录', shortLabel: '记录', icon: 'records-o' },
  { name: 'knowledge', label: '知识库管理', shortLabel: '知识', icon: 'cluster-o' },
  { name: 'roles', label: 'AI角色库', shortLabel: '角色', icon: 'friends-o' },
  { name: 'classes', label: '班级训练', shortLabel: '班级', icon: 'cluster-o' },
  { name: 'students', label: '学员账号', shortLabel: '账号', icon: 'contact-o' },
  { name: 'api-key', label: 'API Key', shortLabel: '密钥', icon: 'setting-o' },
  { name: 'profile', label: '个人中心', shortLabel: '我的', icon: 'user-o' },
]

const navItems = rawNavItems

const username = computed(() => localStorage.getItem('username') || '管理员')
const roleLabel = computed(() => (localStorage.getItem('role') === 'admin' ? '管理员账号' : '学员账号'))
const avatarText = computed(() => username.value.slice(0, 1).toUpperCase())
const currentItem = computed(() => navItems.find((item) => item.name === active.value))

watch(
  () => route.path,
  (val) => {
    menuOpen.value = false

    if (val.includes('/dashboard')) active.value = 'dashboard'
    else if (val.includes('/cases')) active.value = 'cases'
    else if (val.includes('/videos')) active.value = 'videos'
    else if (val.includes('/video-sessions')) active.value = 'video-sessions'
    else if (val.includes('/knowledge')) active.value = 'knowledge'
    else if (val.includes('/roles')) active.value = 'roles'
    else if (val.includes('/classes')) active.value = 'classes'
    else if (val.includes('/students')) active.value = 'students'
    else if (val.includes('/api-key')) active.value = 'api-key'
    else if (val.includes('/profile')) active.value = 'profile'
  },
  { immediate: true }
)

onMounted(() => {
  sidebarCollapsed.value = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1'
})

watch(sidebarCollapsed, (value) => {
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? '1' : '0')
})

const onChange = (name: string) => {
  router.push(`/admin/${name}`)
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}
</script>

<style scoped>
.admin-shell {
  --sidebar-width: 160px;
}

.admin-shell.sidebar-collapsed {
  --sidebar-width: 56px;
}

.admin-sidebar {
  width: 160px;
  background: var(--police-sidebar-bg);
  will-change: width, transform;
}

.admin-nav-item:hover {
  padding-left: 16px;
}

.sidebar-collapsed .admin-nav-item,
.sidebar-collapsed .admin-nav-item:hover {
  padding-left: 0;
  padding-right: 0;
}

.sidebar-collapsed .admin-nav-item span {
  grid-column: 1;
}

.sidebar-collapsed .admin-nav-item--collapsed {
  display: grid;
  place-items: center;
}

.admin-main {
  background: var(--police-bg, #f2f5fa);
  transition: margin-left 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: margin-left;
}

.admin-content {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.08), transparent 34rem),
    var(--police-bg, #f2f5fa);
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

@media (min-width: 1024px) {
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
