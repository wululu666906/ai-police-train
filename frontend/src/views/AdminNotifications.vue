<template>
  <div class="admin-notifications">
    <header class="admin-notifications__header">
      <div>
        <h1>通知中心</h1>
        <p>查看已发布的班级通知与平台消息记录。</p>
      </div>
      <el-button v-if="viewMode === 'list'" plain :loading="loading" @click="fetchNotifications">刷新</el-button>
    </header>

    <section v-if="viewMode === 'detail' && activeItem" class="admin-notifications__detail">
      <NotificationDetailView
        :item="activeItem"
        portal="admin"
        @back="backToList"
        @go-class="openClass"
      />
    </section>

    <template v-else>
      <section v-if="loading" class="admin-notifications__state">
        <el-skeleton :rows="5" animated />
      </section>

      <section v-else-if="!items.length" class="admin-notifications__state">
        <el-empty description="暂无通知" />
      </section>

      <section v-else class="admin-notifications__list">
        <button
          v-for="item in items"
          :key="String(item.id)"
          type="button"
          class="admin-notification-card"
          :class="{ 'admin-notification-card--active': isActiveItem(item) }"
          @click="openDetail(item)"
        >
          <div class="admin-notification-card__head">
            <span>{{ notificationTypeLabel(item) }}</span>
            <time>{{ formatNotificationDateTime(item.created_at) }}</time>
          </div>
          <h2>{{ item.title || '班级通知' }}</h2>
          <p>{{ firstNotificationLine(item.content) }}</p>
          <div class="admin-notification-card__meta">
            <span>来源：{{ notificationSourceLabel(item) }}</span>
            <span class="admin-notification-card__hint">点击查看详情</span>
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

const openClass = (classId?: number) => {
  if (!classId) return
  router.push({ path: '/admin/classes', query: { class_id: String(classId) } })
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
.admin-notifications {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.admin-notifications__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.admin-notifications__header h1 {
  margin: 0;
  font-size: 22px;
  color: #17213b;
}

.admin-notifications__header p {
  margin: 6px 0 0;
  color: #8b96aa;
  font-size: 13px;
}

.admin-notifications__state,
.admin-notifications__detail,
.admin-notifications__list {
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #fff;
}

.admin-notifications__state {
  padding: 24px;
}

.admin-notifications__list {
  display: grid;
  gap: 0;
}

.admin-notification-card {
  display: block;
  width: 100%;
  padding: 18px 20px;
  border: 0;
  border-bottom: 1px solid #eef2f7;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.admin-notification-card:last-child {
  border-bottom: 0;
}

.admin-notification-card:hover,
.admin-notification-card--active {
  background: #f8fbff;
}

.admin-notification-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #8b96aa;
  font-size: 12px;
}

.admin-notification-card__head span:first-child {
  padding: 2px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-weight: 700;
}

.admin-notification-card h2 {
  margin: 0;
  color: #17213b;
  font-size: 16px;
}

.admin-notification-card p {
  margin: 8px 0 0;
  color: #475569;
  line-height: 1.7;
}

.admin-notification-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  color: #94a3b8;
  font-size: 12px;
}

.admin-notification-card__hint {
  color: #2563eb;
  font-weight: 600;
}
</style>
