<template>
  <el-config-provider :locale="studentElementLocale" size="default">
    <div class="student-app">
      <div class="student-shell" :class="{ 'student-shell--sidebar-collapsed': sidebarCollapsed }">
        <StudentSidebar :collapsed="sidebarCollapsed" @toggle-collapse="toggleSidebar" />

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
            <router-view v-slot="{ Component }">
              <transition appear name="fade-transform" mode="out-in">
                <component :is="Component" />
              </transition>
            </router-view>
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
        <div v-if="activeAnnouncement" class="notice-popup-card">
          <div class="notice-popup-header">
            <div>
              <span class="notice-popup-kicker">班级通知</span>
              <h2>{{ activeAnnouncement.title || '班级通知' }}</h2>
              <p>{{ activeAnnouncement.created_at ? formatDateTime(activeAnnouncement.created_at) : '最新通知' }}</p>
            </div>
            <van-icon name="cross" class="notice-popup-close" @click="showAnnouncementDialog = false" />
          </div>

          <div class="notice-popup-body">
            <section class="notice-popup-detail">
              <div class="notice-popup-label">通知内容</div>
              <p>{{ activeAnnouncement.content || '暂无正文' }}</p>
            </section>

            <section v-if="previewAnnouncements.length > 1" class="notice-popup-list">
              <div class="notice-popup-label">最近通知</div>
              <button
                v-for="item in previewAnnouncements"
                :key="item.id"
                type="button"
                class="notice-popup-item"
                :class="{ 'notice-popup-item--active': item.id === activeAnnouncement.id }"
                @click="openNotificationCenter(item)"
              >
                <strong>{{ item.title || '班级通知' }}</strong>
                <span>{{ item.content || '暂无正文' }}</span>
              </button>
            </section>
          </div>

          <div class="notice-popup-actions">
            <el-button v-if="route.path !== '/student/classes'" plain @click="goToClasses">
              前往班级作业
            </el-button>
            <el-button type="primary" @click="showAnnouncementDialog = false">关闭</el-button>
          </div>
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

const goToClasses = () => {
  showAnnouncementDialog.value = false
  router.push('/student/classes')
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
})

watch(sidebarCollapsed, (value) => {
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? '1' : '0')
})
</script>

<style scoped lang="scss">
.student-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.student-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
  background: var(--student-page-bg, #f0f2f5);
}

.student-content :deep(.student-topbar) {
  position: sticky;
  top: 0;
  z-index: 30;
}

.student-main {
  flex: 1;
  min-height: 0;
  overflow: hidden;

  &--scrollable {
    overflow: auto;
  }
}

.student-notice-popup {
  width: min(820px, calc(100vw - 24px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  background: transparent;
}

.notice-popup-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
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
  display: grid;
  gap: 18px;
  margin-top: 20px;
}

.notice-popup-detail,
.notice-popup-list {
  display: grid;
  gap: 10px;
  max-height: 280px;
  overflow: auto;
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
  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong,
  span {
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
}

.notice-popup-item--active {
  border-color: #165dff;
  background: #eef6ff;
}

.notice-popup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
</style>
