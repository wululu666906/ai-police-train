<template>
  <div class="resume-card">
    <div class="resume-info">
      <div class="resume-title">{{ scene.case_title }}</div>
      <div class="resume-meta">案件类型：{{ scene.case_type || '未分类' }}</div>
    </div>
    <div class="resume-progress">
      <el-progress :percentage="progress" :stroke-width="6" :show-text="false" color="#0066ff" />
      <span class="progress-text">{{ progress }}%</span>
    </div>
    <div class="resume-time">上次训练 {{ lastTrainAt }}</div>
    <div class="resume-actions">
      <el-button type="primary" size="small" :loading="loading" :disabled="disabled" @click="emit('continue')">
        继续训练
      </el-button>
      <el-button size="small" type="danger" plain :loading="deleting" :disabled="disabled" @click="emit('clear')">
        清除对话
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getMockLastTrainAt, getMockProgress } from '../../mocks/studentHallMock'

export type ResumeScene = {
  id: number
  name: string
  case_id: number
  case_title: string
  case_type: string
  active_session_id?: number | null
}

const props = defineProps<{
  scene: ResumeScene
  loading?: boolean
  deleting?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  continue: []
  clear: []
}>()

const progress = computed(() => getMockProgress(props.scene.case_id, props.scene.active_session_id))
const lastTrainAt = computed(() =>
  props.scene.active_session_id ? getMockLastTrainAt(props.scene.active_session_id) : '--',
)
</script>

<style scoped lang="scss">
.resume-card {
  display: grid;
  grid-template-columns: minmax(120px, 1.2fr) minmax(100px, 1fr) minmax(130px, 0.9fr) auto;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fafbfc;
  min-height: 56px;
}

.resume-info {
  min-width: 0;
}

.resume-title {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resume-meta {
  margin-top: 2px;
  font-size: 11px;
  color: #6b7280;
}

.resume-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;

  :deep(.el-progress) {
    flex: 1;
  }
}

.progress-text {
  font-size: 12px;
  font-weight: 700;
  color: var(--student-accent, #0066ff);
  flex-shrink: 0;
}

.resume-time {
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
}

.resume-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

@media (max-width: 1100px) {
  .resume-card {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .resume-actions {
    justify-content: flex-end;
  }
}
</style>
