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
          <p>平台运维</p>
        </div>
      </div>

      <nav class="ops-nav">
        <button type="button" class="ops-nav__item" :class="{ 'ops-nav__item--active': route.path.startsWith('/ops/overview') }" @click="router.push('/ops/overview')">
          <OpsIcon name="shield" />
          <span>维护总览</span>
        </button>
        <button type="button" class="ops-nav__item" :class="{ 'ops-nav__item--active': route.path.startsWith('/ops/accounts') }" @click="router.push('/ops/accounts')">
          <OpsIcon name="users" />
          <span>账号管理</span>
        </button>
        <button type="button" class="ops-nav__item" :class="{ 'ops-nav__item--active': route.path.startsWith('/ops/usage') }" @click="router.push('/ops/usage')">
          <OpsIcon name="search" />
          <span>账号监管</span>
        </button>
        <button type="button" class="ops-nav__item" :class="{ 'ops-nav__item--active': route.path.startsWith('/ops/system-issues') }" @click="router.push('/ops/system-issues')">
          <OpsIcon name="shield" />
          <span>系统运行与异常</span>
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
          <h2>{{ pageTitle }}</h2>
          <p>{{ pageSubtitle }}</p>
        </div>
        <div class="ops-user">
          <div>
            <span>{{ username }}</span>
            <strong>维护人员</strong>
          </div>
          <button type="button" class="ops-topbar-logout" @click="logout">
            <OpsIcon name="logout" :size="16" />
            <span>退出</span>
          </button>
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
const pageMeta = computed(() => {
  if (route.path.startsWith('/ops/accounts')) {
    return {
      title: '账号生命周期维护',
      subtitle: '开通、导入、编辑、重置和回收管理端与学员端账号。',
    }
  }
  if (route.path.startsWith('/ops/usage')) {
    return {
      title: '账号使用监管',
      subtitle: '查看账号行为、训练、人脸、语音和审计记录。',
    }
  }
  if (route.path.startsWith('/ops/system-issues')) {
    return {
      title: '系统运行与异常',
      subtitle: '查看 AI 调用、功能失效、外部服务异常和规则兜底的完整处理轨迹。',
    }
  }
  return {
    title: '平台维护总览',
    subtitle: '集中查看账号规模、活跃情况、训练使用和需要跟进的风险项。',
  }
})
const pageTitle = computed(() => pageMeta.value.title)
const pageSubtitle = computed(() => pageMeta.value.subtitle)

const logout = () => {
  clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.ops-shell {
  --ops-navy: #0b1e3c;
  --ops-navy-panel: #102947;
  --ops-blue: #0b49b4;
  --ops-blue-hover: #083f9d;
  --ops-blue-soft: #eaf1ff;
  --ops-bg: #eef3f8;
  --ops-border: #e3eaf3;
  --ops-muted: #8b96aa;
  display: flex;
  min-height: 100vh;
  background: var(--ops-bg);
}

.ops-sidebar {
  width: 210px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  background: var(--ops-navy);
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
  border-radius: 8px;
  background: var(--ops-blue);
  color: #dbe8ff;
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
  color: #dbe8ff;
}

.ops-brand p {
  margin: 2px 0 0;
  color: rgba(216, 225, 244, 0.56);
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
  color: #c4ccdc;
  background: transparent;
  font-weight: 800;
  text-align: left;
}

.ops-nav__item--active {
  color: #fff;
  background: var(--ops-blue);
}

.ops-logout {
  margin: 12px;
  width: calc(100% - 24px);
}

.ops-logout:hover,
.ops-nav__item:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.06);
}

.ops-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.ops-topbar {
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--ops-border);
  background: #fff;
  padding: 12px 24px;
}

.ops-topbar h2 {
  margin: 0;
  color: #17213b;
  font-size: 18px;
}

.ops-topbar p {
  margin: 5px 0 0;
  color: var(--ops-muted);
  font-size: 13px;
}

.ops-user {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #4a5467;
  font-size: 13px;
}

.ops-user > div {
  display: grid;
  justify-items: end;
  gap: 2px;
}

.ops-user strong {
  color: var(--ops-blue);
}

.ops-topbar-logout {
  height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #dfe5ed;
  border-radius: 6px;
  background: #fff;
  color: #253047;
  padding: 0 10px;
  font-weight: 900;
}

.ops-topbar-logout:hover {
  border-color: #ef4444;
  color: #dc2626;
  background: #fef2f2;
}

.ops-content {
  flex: 1;
  min-width: 0;
  padding: 20px;
  overflow: auto;
}

.ops-content :deep(.ops-card),
.ops-content :deep(.panel),
.ops-content :deep(.toolbar),
.ops-content :deep(.ops-overview-toolbar),
.ops-content :deep(.ops-metric-card),
.ops-content :deep(.ops-panel),
.ops-content :deep(.ops-toolbar),
.ops-content :deep(.ops-summary),
.ops-content :deep(.ops-table-wrap),
.ops-content :deep(.ops-usage-toolbar),
.ops-content :deep(.account-panel),
.ops-content :deep(.usage-panel),
.ops-content :deep(.ops-account-panel),
.ops-content :deep(.ops-detail-panel) {
  border-color: var(--ops-border) !important;
  background: #fff !important;
}

.ops-content :deep(.ops-action--primary),
.ops-content :deep(.ops-action-btn--primary),
.ops-content :deep(.tabs .active),
.ops-content :deep(.ops-tabs button.active),
.ops-content :deep(.toggle button.active),
.ops-content :deep(.progress__fill),
.ops-content :deep(.ops-role-bar i),
.ops-content :deep(.ops-import-role-action.is-active) {
  border-color: var(--ops-blue) !important;
  background: var(--ops-blue) !important;
  color: #fff !important;
}

.ops-content :deep(.ops-action--primary:hover),
.ops-content :deep(.ops-action-btn--primary:hover:not(:disabled)) {
  border-color: var(--ops-blue-hover) !important;
  background: var(--ops-blue-hover) !important;
}

.ops-content :deep(.ops-action--ghost.active),
.ops-content :deep(.issue.active),
.ops-content :deep(.filter-chip.active),
.ops-content :deep(.ops-action-btn:hover:not(:disabled)),
.ops-content :deep(.ops-overview-toolbar button:hover),
.ops-content :deep(.ops-panel header button:hover),
.ops-content :deep(.ops-risk-list button:hover),
.ops-content :deep(.ops-active-list button:hover),
.ops-content :deep(.ops-account-card.active),
.ops-content :deep(.ops-category-tabs button.active),
.ops-content :deep(.ops-group-nav button.active),
.ops-content :deep(.ops-context-menu button:hover),
.ops-content :deep(.ops-preview),
.ops-content :deep(.ops-reset-target),
.ops-content :deep(.ops-role--maintainer) {
  border-color: var(--ops-blue) !important;
  background: var(--ops-blue-soft) !important;
  color: var(--ops-blue) !important;
}

.ops-content :deep(.ops-group-nav__create),
.ops-content :deep(.ops-account-name),
.ops-content :deep(.ops-row-actions button:not(.danger)) {
  color: var(--ops-blue) !important;
}

.ops-content :deep(input[type='checkbox']) {
  accent-color: var(--ops-blue);
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
