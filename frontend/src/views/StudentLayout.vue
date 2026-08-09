<template>
  <el-config-provider :locale="studentElementLocale" size="default">
    <div class="student-app">
      <div class="student-shell" :class="{ 'student-shell--sidebar-collapsed': sidebarCollapsed }">
        <StudentSidebar
          :collapsed="sidebarCollapsed"
          :display-name="displayName"
          @toggle-collapse="toggleSidebar"
          @notify="openNotificationCenter"
        />

        <div class="student-content">
          <StudentTopbar
            :display-name="displayName"
            :can-back-to-admin="canBackToAdmin"
            :notification-count="studentAnnouncements.length"
            @back-admin="router.push('/admin/dashboard')"
            @logout="logout"
            @notify="openNotificationCenter"
          />

          <main class="student-main" :class="{ 'student-main--scrollable': mainScrollable }">
            <div class="student-main__surface">
              <router-view v-slot="{ Component }">
                <transition appear name="fade-transform" mode="out-in">
                  <component :is="Component" />
                </transition>
              </router-view>
            </div>
          </main>
        </div>
      </div>

      <van-popup
        v-model:show="showAnnouncementDialog"
        round
        class="student-notice-popup"
        :overlay-style="{ backgroundColor: 'rgba(15, 23, 42, 0.24)', backdropFilter: 'blur(6px)' }"
        teleport="body"
      >
        <div class="notice-popup-card">
          <transition name="notice-panel" mode="out-in">
            <section v-if="announcementPopupMode === 'list'" key="notice-list" class="notice-panel">
              <div class="notice-popup-header">
                <div>
                  <h2>通知中心</h2>
                  <p>{{ previewAnnouncements.length ? `共 ${previewAnnouncements.length} 条最新通知` : '暂无班级通知' }}</p>
                </div>
                <van-icon name="cross" class="notice-popup-close" @click="showAnnouncementDialog = false" />
              </div>

              <div class="notice-popup-body">
                <section class="notice-popup-list">
                  <button
                    v-for="item in previewAnnouncements"
                    :key="item.id"
                    type="button"
                    class="notice-popup-item"
                    @click="openAnnouncementDetail(item)"
                  >
                    <strong>{{ item.title || '班级通知' }}</strong>
                    <span>{{ firstAnnouncementLine(item.content) }}</span>
                    <small>来源：{{ announcementSourceLabel(item) }}</small>
                  </button>
                  <div v-if="!previewAnnouncements.length" class="notice-popup-empty">暂无班级通知</div>
                </section>
              </div>
            </section>

            <section v-else key="notice-detail" class="notice-panel">
              <div class="notice-popup-header">
                <div>
                  <h2>{{ activeAnnouncement?.title || '班级通知' }}</h2>
                  <p>{{ activeAnnouncement?.created_at ? formatDateTime(activeAnnouncement.created_at) : '最新通知' }}</p>
                </div>
                <van-icon name="cross" class="notice-popup-close" @click="showAnnouncementDialog = false" />
              </div>

              <div class="notice-popup-body notice-popup-body--detail">
                <section class="notice-popup-detail">
                  <p>{{ activeAnnouncement?.content || '暂无正文' }}</p>
                </section>
              </div>

              <div class="notice-popup-actions">
                <span class="notice-popup-source">来源：{{ announcementSourceLabel(activeAnnouncement) }}</span>
                <el-button plain @click="announcementPopupMode = 'list'">返回列表</el-button>
                <el-button v-if="route.path !== '/student/classes'" plain @click="goToClasses">
                  前往班级作业
                </el-button>
              </div>
            </section>
          </transition>
        </div>
      </van-popup>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StudentSidebar from '../geeker-adapt/components/StudentSidebar.vue'
import StudentTopbar from '../geeker-adapt/components/StudentTopbar.vue'
import { studentElementLocale } from '../geeker-adapt/setupElementPlus'
import { clearAuth } from '../utils/auth'
import { preloadPresenceDetector } from '../composables/usePresenceMonitor'
import request from '../utils/request'
import { showToast } from 'vant'
import '../geeker-adapt/styles/common.scss'
import '../geeker-adapt/styles/student-theme.scss'
import '../geeker-adapt/styles/element-student.scss'

const router = useRouter()
const route = useRoute()
const SIDEBAR_COLLAPSED_KEY = 'student.sidebar.collapsed'

const displayName = computed(() => localStorage.getItem('username') || '学员')
const canBackToAdmin = computed(() => localStorage.getItem('role') === 'admin')
const mainScrollable = ref(false)
const sidebarCollapsed = ref(false)
const studentAnnouncements = ref<any[]>([])
const showAnnouncementDialog = ref(false)
const activeAnnouncementId = ref<number | null>(null)
const announcementPopupMode = ref<'list' | 'detail'>('list')
const ANNOUNCEMENT_SEEN_KEY = 'student.announcement.latest_seen'
const previewAnnouncements = computed(() => studentAnnouncements.value.slice(0, 8))
const activeAnnouncement = computed(() => {
  if (!studentAnnouncements.value.length) return null
  return studentAnnouncements.value.find((item) => item.id === activeAnnouncementId.value) || studentAnnouncements.value[0]
})

const setMainScrollable = (value: boolean) => {
  mainScrollable.value = value
}

const setAnnouncementPanel = (announcement?: any) => {
  if (announcement?.id) {
    if (!studentAnnouncements.value.some((item) => item.id === announcement.id)) {
      studentAnnouncements.value = [announcement, ...studentAnnouncements.value]
    }
    activeAnnouncementId.value = Number(announcement.id)
  } else if (!activeAnnouncementId.value && studentAnnouncements.value.length) {
    activeAnnouncementId.value = Number(studentAnnouncements.value[0].id)
  }
  if (studentAnnouncements.value.length) {
    announcementPopupMode.value = 'list'
    showAnnouncementDialog.value = true
  } else {
    showToast('暂无班级通知')
  }
}

provide('setMainScrollable', setMainScrollable)
provide('openStudentAnnouncementPanel', setAnnouncementPanel)

const logout = () => {
  clearAuth()
  router.push('/login')
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const fetchStudentAnnouncements = async () => {
  try {
    const res: any = await request.get('/classes/student/announcements', { _skipErrorToast: true } as any)
    studentAnnouncements.value = Array.isArray(res) ? res : []
    if (!activeAnnouncementId.value && studentAnnouncements.value.length) {
      activeAnnouncementId.value = Number(studentAnnouncements.value[0].id)
    }
    const latestKey = studentAnnouncements.value.map((item) => item.id).join(',')
    const seenKey = sessionStorage.getItem(ANNOUNCEMENT_SEEN_KEY)
    if (studentAnnouncements.value.length && latestKey && latestKey !== seenKey) {
      setAnnouncementPanel(studentAnnouncements.value[0])
      sessionStorage.setItem(ANNOUNCEMENT_SEEN_KEY, latestKey)
    }
  } catch {
    studentAnnouncements.value = []
  }
}

const openNotificationCenter = (announcement?: any) => {
  setAnnouncementPanel(announcement || activeAnnouncement.value || studentAnnouncements.value[0])
}

const openAnnouncementDetail = (announcement: any) => {
  if (announcement?.id) {
    activeAnnouncementId.value = Number(announcement.id)
  }
  announcementPopupMode.value = 'detail'
}

const goToClasses = () => {
  showAnnouncementDialog.value = false
  router.push('/student/classes')
}

const firstAnnouncementLine = (content: any) => {
  const lines = String(content || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  return lines[0] || '暂无正文'
}

const announcementSourceLabel = (announcement: any) => {
  const sourceName = String(announcement?.source_label || announcement?.source_name || '').trim()
  if (sourceName) return sourceName
  if (announcement?.source_type === 'system' || announcement?.category === 'system') return '系统通知'
  return '班级通知'
}

const formatDateTime = (value: any) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

onMounted(() => {
  sidebarCollapsed.value = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1'
  fetchStudentAnnouncements()
  void preloadPresenceDetector()
})

watch(sidebarCollapsed, (value) => {
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? '1' : '0')
})
</script>

<style scoped lang="scss">
.student-app {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  position: relative;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.58), rgba(236, 245, 255, 0.74)),
    linear-gradient(135deg, #eef6ff 0%, #f8fbff 48%, #eaf3ff 100%);
}

.student-shell {
  display: flex;
  height: 100%;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  gap: 0;
  padding: 0;
  position: relative;
  z-index: 1;
}

.student-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
  background: transparent;
}

.student-content :deep(.student-topbar) {
  position: sticky;
  top: 0;
  z-index: 30;
}

.student-main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: auto;
  scrollbar-gutter: stable;
  -webkit-overflow-scrolling: touch;
  padding: 0;

  &--scrollable {
    overflow-y: auto;
    overflow-x: hidden;
  }
}

.student-main__surface {
  min-height: 100%;
  margin: 0 18px 18px 0;
  border: 1px solid rgba(219, 231, 247, 0.88);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 24px 60px rgba(58, 102, 180, 0.12);
  overflow: hidden;
  backdrop-filter: blur(14px);
}

.student-notice-popup {
  width: min(820px, calc(100vw - 40px));
  height: min(640px, calc(100vh - 48px));
  max-height: none;
  overflow: hidden;
  border: 1px solid #dbe3ee;
  border-radius: 12px !important;
  background: #fff !important;
  box-shadow: 0 22px 70px rgba(15, 23, 42, 0.22);
}

.notice-popup-card {
  height: 100%;
  background: #fff;
  overflow: hidden;
}

.notice-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: 24px;
}

.notice-popup-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;

  h2 {
    margin: 10px 0 0;
    color: #111827;
    font-size: 22px;
    font-weight: 900;
  }

  p {
    margin: 8px 0 0;
    color: #6b7280;
    font-size: 13px;
  }
}

.notice-popup-kicker,
.notice-popup-label {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: 6px;
  background: #dbeafe;
  padding: 0 9px;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.notice-popup-close {
  font-size: 22px;
  color: #9ca3af;
  cursor: pointer;
}

.notice-popup-body {
  flex: 1;
  min-height: 0;
  margin-top: 20px;
  overflow: hidden;
}

.notice-popup-body--detail {
  overflow: auto;
  overscroll-behavior: contain;
  scroll-behavior: smooth;
}

.notice-popup-detail,
.notice-popup-list {
  display: grid;
  gap: 10px;
  align-content: start;
  height: 100%;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  scroll-behavior: smooth;
  scrollbar-gutter: stable;
}

.notice-popup-detail p {
  margin: 0;
  color: #475569;
  line-height: 1.9;
  white-space: pre-wrap;
}

.notice-popup-item {
  display: grid;
  gap: 6px;
  width: 100%;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  padding: 12px 14px;
  text-align: left;
  cursor: pointer;

  strong,
  span,
  small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong,
  span,
  small {
    min-width: 0;
  }

  strong {
    color: #0f172a;
    font-size: 14px;
    font-weight: 800;
  }

  span {
    color: #64748b;
    font-size: 12px;
  }

  small {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 700;
  }
}

.notice-popup-item--active {
  border-color: #165dff;
  background: #eef6ff;
}

.notice-popup-empty {
  display: grid;
  min-height: 180px;
  place-items: center;
  color: #94a3b8;
  font-size: 14px;
}

.notice-popup-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.notice-popup-source {
  margin-right: auto;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.notice-panel-enter-active,
.notice-panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.notice-panel-enter-from {
  opacity: 0;
  transform: translateX(12px);
}

.notice-panel-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

:global(body.van-overflow-hidden) {
  padding-right: 0 !important;
}

.student-notice-popup ::-webkit-scrollbar {
  width: 6px;
}

.student-notice-popup ::-webkit-scrollbar-thumb {
  border-radius: 10px;
  background: rgba(100, 116, 139, 0.32);
}

.student-notice-popup ::-webkit-scrollbar-track {
  background: transparent;
}
</style>
