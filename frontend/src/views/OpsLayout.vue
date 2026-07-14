<template>
  <div class="ops-shell">
    <aside class="ops-sidebar">
      <div class="ops-brand">
        <div class="ops-brand__mark"><OpsIcon name="shield" :size="22" /></div>
        <div>
          <div class="ops-brand__title">
            <h1>维护端</h1>
            <OpsIcon name="bookmark-plus" :size="18" />
          </div>
          <p>账号运维</p>
        </div>
      </div>

      <nav class="ops-nav">
        <button type="button" class="ops-nav__item" :class="{ 'ops-nav__item--active': route.path.startsWith('/ops/accounts') }" @click="router.push('/ops/accounts')">
          <OpsIcon name="users" />
          <span>账号管理</span>
        </button>
        <button type="button" class="ops-nav__item" :class="{ 'ops-nav__item--active': route.path.startsWith('/ops/usage') }" @click="router.push('/ops/usage')">
          <OpsIcon name="search" />
          <span>账号监管</span>
        </button>
      </nav>

      <button type="button" class="ops-logout" @click="logout">
        <OpsIcon name="logout" />
        <span>退出登录</span>
      </button>
    </aside>

    <section class="ops-main">
      <header class="ops-topbar">
        <div>
          <h2>账号生命周期维护</h2>
          <p>开通管理端账号与学员账号，执行密码重置和账号回收。</p>
        </div>
        <div class="ops-user">
          <span>{{ username }}</span>
          <strong>维护人员</strong>
        </div>
      </header>
      <main class="ops-content">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearAuth } from '../utils/auth'
import OpsIcon from '../components/OpsIcon.vue'

const router = useRouter()
const route = useRoute()
const username = computed(() => localStorage.getItem('username') || 'maintainer')

const logout = () => {
  clearAuth()
  router.push('/ops/login')
}
</script>

<style scoped>
.ops-shell {
  display: flex;
  min-height: 100vh;
  background: #eef2f7;
}

.ops-sidebar {
  width: 210px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #1f2937;
  background: #111827;
  color: #fff;
}

.ops-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.ops-brand__mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  background: #2563eb;
  color: #dbeafe;
}

.ops-brand h1 {
  margin: 0;
  font-size: 16px;
}

.ops-brand__title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #fff;
}

.ops-brand__title .ops-icon {
  color: #bfdbfe;
}

.ops-brand p {
  margin: 2px 0 0;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.ops-nav {
  flex: 1;
  padding: 12px;
}

.ops-nav__item,
.ops-logout {
  width: 100%;
  height: 40px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  border-radius: 6px;
  padding: 0 12px;
  color: #cbd5e1;
  background: transparent;
  font-weight: 800;
  text-align: left;
}

.ops-nav__item--active {
  color: #fff;
  background: #2563eb;
}

.ops-logout {
  margin: 12px;
  width: calc(100% - 24px);
}

.ops-logout:hover,
.ops-nav__item:hover {
  color: #fff;
  background: #1f2937;
}

.ops-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.ops-topbar {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #dbe3ee;
  background: #fff;
  padding: 0 24px;
}

.ops-topbar h2 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
}

.ops-topbar p {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 13px;
}

.ops-user {
  display: grid;
  justify-items: end;
  gap: 2px;
  color: #475569;
  font-size: 13px;
}

.ops-user strong {
  color: #2563eb;
}

.ops-content {
  flex: 1;
  min-width: 0;
  padding: 20px;
  overflow: auto;
}

@media (max-width: 780px) {
  .ops-shell {
    display: block;
  }

  .ops-sidebar {
    width: 100%;
  }

  .ops-topbar {
    height: auto;
    align-items: flex-start;
    padding: 16px;
  }
}
</style>
