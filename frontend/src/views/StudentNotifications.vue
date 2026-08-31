<template>
  <div class="notifications-page">
    <header class="notifications-page__header">
      <div>
        <h1>通知中心</h1>
        <p>集中查看班级通知与训练异常提醒。</p>
      </div>
      <el-button v-if="viewMode === 'list'" plain :loading="loading" @click="fetchNotifications">刷新</el-button>
    </header>

    <section v-if="viewMode === 'detail' && activeItem" class="notifications-page__detail">
      <NotificationDetailView
        :item="activeItem"
        portal="student"
        :show-go-classes="route.path !== '/student/classes'"
        @back="backToList"
        @go-classes="goToClasses"
        @open-evaluation="openEvaluation"
      />
    </section>

    <template v-else>
      <section v-if="loading" class="notifications-page__state">
        <el-skeleton :rows="5" animated />
      </section>

      <section v-else-if="!items.length" class="notifications-page__state">
        <el-empty description="暂无通知" />
      </section>

      <section v-else class="notifications-list">
        <button
          v-for="item in items"
          :key="String(item.id)"
          type="button"
          class="notification-card"
          :class="[`notification-card--${item.severity || 'info'}`, { 'notification-card--active': isActiveItem(item) }]"
          @click="openDetail(item)"
        >
          <div class="notification-card__head">
            <span class="notification-card__type">{{ notificationTypeLabel(item) }}</span>
            <time>{{ formatNotificationDateTime(item.created_at) }}</time>
          </div>
          <h2>{{ item.title || '系统通知' }}</h2>
          <p>{{ firstNotificationLine(item.content) }}</p>
          <div class="notification-card__meta">
            <span>来源：{{ notificationSourceLabel(item) }}</span>
            <span class="notification-card__hint">点击查看详情</span>
          </div>
        </button>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NotificationDetailView from '../components/notifications/NotificationDetailView.vue'
import request from '../utils/request'
import {
  firstNotificationLine,
  formatNotificationDateTime,
  notificationSourceLabel,
  notificationTypeLabel,
  type NotificationRecord,
} from '../utils/notificationDisplay'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const items = ref<NotificationRecord[]>([])
const viewMode = ref<'list' | 'detail'>('list')
const activeItem = ref<NotificationRecord | null>(null)

const isActiveItem = (item: NotificationRecord) => String(activeItem.value?.id) === String(item.id)

const fetchNotifications = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/classes/notifications/inbox', { _skipErrorToast: true } as any)
    items.value = Array.isArray(res) ? res : []
    syncDetailFromQuery()
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

const openDetail = (item: NotificationRecord) => {
  activeItem.value = item
  viewMode.value = 'detail'
  router.replace({ path: route.path, query: { ...route.query, notice_id: String(item.id) } })
}

const backToList = () => {
  viewMode.value = 'list'
  activeItem.value = null
  const nextQuery = { ...route.query }
  delete nextQuery.notice_id
  router.replace({ path: route.path, query: nextQuery })
}

const syncDetailFromQuery = () => {
  const noticeId = String(route.query.notice_id || '').trim()
  if (!noticeId) return
  const matched = items.value.find((item) => String(item.id) === noticeId)
  if (!matched) return
  activeItem.value = matched
  viewMode.value = 'detail'
}

const openEvaluation = (item: NotificationRecord) => {
  if (!item.session_id) return
  const query = item.video_id ? `?session_id=${item.session_id}&type=video` : `?session_id=${item.session_id}`
  router.push(`/student/evaluation${query}`)
}

const goToClasses = () => {
  router.push('/student/classes')
}

watch(
  () => route.query.notice_id,
  () => {
    if (!route.query.notice_id) {
      if (viewMode.value === 'detail') backToList()
      return
    }
    syncDetailFromQuery()
  },
)

onMounted(fetchNotifications)
</script>

<style scoped lang="scss">
.notifications-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 8px 4px 24px;
}

.notifications-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.notifications-page__header h1 {
  margin: 0;
  font-size: 24px;
  color: #142552;
}

.notifications-page__header p {
  margin: 6px 0 0;
  color: #7f8da6;
  font-size: 13px;
}

.notifications-page__state,
.notifications-page__detail {
  border: 1px solid #e6ebf3;
  border-radius: 10px;
  background: #fff;
}

.notifications-page__state {
  padding: 24px;
}

.notifications-list {
  display: grid;
  gap: 12px;
}

.notification-card {
  display: block;
  width: 100%;
  padding: 16px 18px;
  border: 1px solid #e6ebf3;
  border-radius: 10px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.notification-card:hover,
.notification-card--active {
  border-color: #bfdbfe;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.08);
  transform: translateY(-1px);
}

.notification-card--warning {
  border-color: #fecaca;
  background: #fffafb;
}

.notification-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.notification-card__type {
  padding: 2px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
}

.notification-card--warning .notification-card__type {
  background: #fef2f2;
  color: #dc2626;
}

.notification-card__head time {
  color: #94a3b8;
  font-size: 12px;
}

.notification-card h2 {
  margin: 0;
  color: #17213b;
  font-size: 16px;
}

.notification-card p {
  margin: 8px 0 0;
  color: #475569;
  line-height: 1.7;
}

.notification-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  color: #94a3b8;
  font-size: 12px;
}

.notification-card__hint {
  color: #2563eb;
  font-weight: 600;
}
</style>
