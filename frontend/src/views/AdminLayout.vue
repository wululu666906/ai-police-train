<template>
  <div class="admin-shell h-screen overflow-hidden bg-[#F4F7FB] lg:flex" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
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
            'pt-7 transition-[padding] duration-[380ms] ease-[cubic-bezier(0.22,1,0.36,1)]',
            sidebarCollapsed ? 'pl-6 pr-0 pb-5' : 'px-6 pb-5',
          ]"
        >
          <div class="flex items-center gap-3 overflow-hidden">
            <div
              class="flex h-14 w-14 items-center justify-center rounded-[20px] border border-white/10 bg-gradient-to-br from-[#2E6BFF] via-[#3D7BFF] to-[#1C4FCB] text-white shadow-[0_18px_34px_rgba(14,54,130,0.35)]"
            >
              <van-icon name="shield-o" size="26" />
            </div>

            <div
              :class="[
                'min-w-0 overflow-hidden transition-[max-width,opacity,transform] duration-[320ms] ease-[cubic-bezier(0.22,1,0.36,1)]',
                sidebarCollapsed ? 'max-w-0 -translate-x-1 opacity-0 delay-0' : 'max-w-[160px] translate-x-0 opacity-100 delay-75',
              ]"
            >
              <h1 class="truncate text-lg font-bold tracking-[0.08em] text-white">警情模拟平台</h1>
              <p class="mt-1 text-[11px] uppercase tracking-[0.28em] text-blue-100/55">Admin Console</p>
            </div>
          </div>
        </div>
      </div>

      <nav
        :class="[
          'flex-1 overflow-y-auto transition-[padding] duration-[380ms] ease-[cubic-bezier(0.22,1,0.36,1)]',
          sidebarCollapsed ? 'px-2 py-4 space-y-2' : 'px-3 py-5 space-y-2',
        ]"
      >
        <button
          v-for="item in navItems"
          :key="item.name"
          type="button"
          :title="sidebarCollapsed ? item.label : ''"
          @click="onChange(item.name)"
          :class="[
            'group relative isolate grid w-full grid-cols-[48px_minmax(0,1fr)] items-center overflow-hidden rounded-[24px] px-3.5 py-3 text-left transition-[padding,gap,background-color,color,border-radius,box-shadow] duration-[380ms] ease-[cubic-bezier(0.22,1,0.36,1)]',
            sidebarCollapsed ? 'gap-x-0' : 'gap-x-3',
            active === item.name ? 'text-[#16324F]' : 'text-blue-100/90 hover:bg-white/6',
          ]"
        >
          <span
            v-if="active === item.name"
            class="pointer-events-none absolute inset-[4px] rounded-[20px] bg-white shadow-[0_18px_38px_rgba(8,35,74,0.18)]"
          ></span>

          <span
            v-if="active === item.name"
            class="pointer-events-none absolute inset-y-2 right-2 w-14 rounded-full bg-[#2E6BFF]/20 blur-2xl"
          ></span>

            <span
              :class="[
                'relative z-[1] flex items-center justify-center rounded-2xl transition-[background-color,color,box-shadow,transform] duration-[380ms] ease-[cubic-bezier(0.22,1,0.36,1)]',
                'h-12 w-12 shrink-0',
                active === item.name
                  ? 'bg-gradient-to-br from-[#2E6BFF] via-[#3D7BFF] to-[#1D54D5] text-white shadow-[0_12px_26px_rgba(46,107,255,0.36)]'
                  : 'bg-white/10 text-blue-100/90 group-hover:bg-white/14 group-hover:text-white group-hover:shadow-[0_10px_20px_rgba(10,34,64,0.18)]',
              ]"
            >
              <van-icon :name="item.icon" size="20" />
            </span>

          <div
            :class="[
              'relative z-[1] min-w-0 overflow-hidden whitespace-nowrap transition-[max-width,opacity,transform] duration-[320ms] ease-[cubic-bezier(0.22,1,0.36,1)]',
              sidebarCollapsed ? 'max-w-0 -translate-x-1 opacity-0 delay-0' : 'max-w-[132px] translate-x-0 opacity-100 delay-75',
            ]"
          >
            <span class="block truncate font-medium">{{ item.label }}</span>
          </div>

          <span
            v-if="active === item.name"
            class="pointer-events-none absolute right-4 top-1/2 z-[1] h-9 w-1.5 -translate-y-1/2 rounded-full bg-gradient-to-b from-[#4B87FF] to-[#1F56D6] shadow-[0_0_18px_rgba(46,107,255,0.48)]"
          ></span>
        </button>
      </nav>

      <div
        :class="[
          'hidden transition-[padding] duration-[380ms] ease-[cubic-bezier(0.22,1,0.36,1)] lg:block',
          sidebarCollapsed ? 'px-2 py-4' : 'px-3 py-4',
        ]"
      >
        <button
          type="button"
          :title="sidebarCollapsed ? '展开导航' : '收起导航'"
          @click="toggleSidebar"
          :class="[
            'group grid w-full grid-cols-[48px_minmax(0,1fr)] items-center overflow-hidden rounded-[22px] px-3.5 py-3 text-left text-blue-100/72 transition-[padding,gap,background-color,color,border-radius,box-shadow] duration-[380ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:bg-white/6 hover:text-white',
            sidebarCollapsed ? 'gap-x-0' : 'gap-x-3',
          ]"
        >
          <span
            class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/10 text-blue-50 transition-[background-color,color,box-shadow,transform] duration-[380ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:bg-white/14 group-hover:text-white group-hover:shadow-[0_10px_20px_rgba(10,34,64,0.18)]"
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
        class="sticky top-0 z-20 flex h-16 flex-shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 lg:px-8"
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
            <h2 class="truncate text-lg font-bold text-slate-800">{{ currentItem?.label || '管理后台' }}</h2>
            <p class="truncate text-xs text-slate-400">管理端负责配置、审核与发布，训练统一走学员链路</p>
          </div>
        </div>

        <div class="flex items-center gap-3 lg:gap-5">
          <van-button
            size="small"
            plain
            type="primary"
            icon="exchange"
            @click="router.push('/student/hall')"
            class="!rounded-full !border-sky-100 !bg-sky-50 !px-4 !text-sky-700 lg:!px-6"
          >
            切换到学员端
          </van-button>

          <div class="hidden text-right sm:block">
            <p class="text-sm font-bold text-slate-700">{{ username }}</p>
            <p class="text-xs text-slate-400">{{ roleLabel }}</p>
          </div>

          <div class="flex h-10 w-10 items-center justify-center rounded-full bg-[#16324F] text-white font-bold">
            {{ avatarText }}
          </div>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto p-4 lg:p-8">
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

const navItems = [
  { name: 'dashboard', label: '数据总览', shortLabel: '总览', icon: 'bar-chart-o' },
  { name: 'cases', label: '案件剧本库', shortLabel: '案件', icon: 'orders-o' },
  { name: 'data-quality', label: '数据质检', shortLabel: '质检', icon: 'warning-o' },
  { name: 'state-influence', label: '四轴触发表', shortLabel: '触发表', icon: 'setting-o' },
  { name: 'knowledge', label: '知识库管理', shortLabel: '知识', icon: 'cluster-o' },
  { name: 'roles', label: 'AI角色库', shortLabel: '角色', icon: 'friends-o' },
  { name: 'students', label: '学员账号', shortLabel: '账号', icon: 'contact-o' },
  { name: 'profile', label: '个人中心', shortLabel: '我的', icon: 'user-o' },
]

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
    else if (val.includes('/data-quality')) active.value = 'data-quality'
    else if (val.includes('/state-influence')) active.value = 'state-influence'
    else if (val.includes('/knowledge')) active.value = 'knowledge'
    else if (val.includes('/roles')) active.value = 'roles'
    else if (val.includes('/students')) active.value = 'students'
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
  --sidebar-width: 248px;
}

.admin-shell.sidebar-collapsed {
  --sidebar-width: 92px;
}

.admin-sidebar {
  width: 248px;
  background:
    radial-gradient(circle at top center, rgba(76, 131, 255, 0.16), transparent 30%),
    linear-gradient(180deg, #16324f 0%, #17395b 48%, #132f49 100%);
  will-change: width, transform;
}

.admin-main {
  transition: margin-left 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: margin-left;
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
