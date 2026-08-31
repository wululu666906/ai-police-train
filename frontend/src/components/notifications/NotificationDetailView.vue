<template>
  <section class="notification-detail">
    <header class="notification-detail__header">
      <div>
        <span class="notification-detail__type">{{ notificationTypeLabel(item) }}</span>
        <h2>{{ item.title || '系统通知' }}</h2>
        <p>{{ formatNotificationDateTime(item.created_at) }}</p>
      </div>
      <el-button plain @click="emit('back')">返回列表</el-button>
    </header>

    <div class="notification-detail__body">
      <p class="notification-detail__content">{{ item.content || '暂无正文' }}</p>
      <div v-if="item.notification_type === 'training_anomaly' && item.failure_count" class="notification-detail__meta-row">
        <span>累计异常次数</span>
        <strong>{{ item.failure_count }} 次</strong>
      </div>
    </div>

    <footer class="notification-detail__actions">
      <span>来源：{{ notificationSourceLabel(item) }}</span>
      <div class="notification-detail__action-buttons">
        <el-button
          v-if="showGoClasses"
          plain
          @click="emit('go-classes')"
        >
          前往班级作业
        </el-button>
        <el-button
          v-if="showGoClassAdmin"
          plain
          @click="emit('go-class', item.class_id)"
        >
          前往班级
        </el-button>
        <el-button
          v-if="showEvaluation"
          type="primary"
          @click="emit('open-evaluation', item)"
        >
          查看评估报告
        </el-button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  formatNotificationDateTime,
  notificationSourceLabel,
  notificationTypeLabel,
  type NotificationRecord,
} from '../../utils/notificationDisplay'

const props = defineProps<{
  item: NotificationRecord
  portal?: 'student' | 'admin'
  showGoClasses?: boolean
}>()

const emit = defineEmits<{
  (event: 'back'): void
  (event: 'go-classes'): void
  (event: 'go-class', classId?: number): void
  (event: 'open-evaluation', item: NotificationRecord): void
}>()

const showEvaluation = computed(() =>
  props.portal === 'student'
  && props.item.notification_type === 'training_anomaly'
  && Boolean(props.item.session_id),
)

const showGoClassAdmin = computed(() =>
  props.portal === 'admin' && Boolean(props.item.class_id),
)
</script>

<style scoped lang="scss">
.notification-detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 360px;
  padding: 22px 24px;
  border: 1px solid #e6ebf3;
  border-radius: 10px;
  background: #fff;
}

.notification-detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.notification-detail__type {
  display: inline-flex;
  margin-bottom: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
}

.notification-detail__header h2 {
  margin: 0;
  color: #17213b;
  font-size: 22px;
  line-height: 1.35;
}

.notification-detail__header p {
  margin: 8px 0 0;
  color: #94a3b8;
  font-size: 13px;
}

.notification-detail__body {
  flex: 1;
  overflow: auto;
  padding: 16px 18px;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #fafbfd;
}

.notification-detail__content {
  margin: 0;
  color: #334155;
  font-size: 15px;
  line-height: 1.85;
  white-space: pre-wrap;
}

.notification-detail__meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 13px;
}

.notification-detail__meta-row strong {
  color: #b42318;
}

.notification-detail__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  color: #94a3b8;
  font-size: 12px;
}

.notification-detail__action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
