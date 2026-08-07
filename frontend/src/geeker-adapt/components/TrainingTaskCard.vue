<template>
  <article
    class="task-card card"
    :class="{ 'task-card--list': viewMode === 'list', 'task-card--compact': compact }"
  >
    <div class="task-card-head">
      <span class="status-tag" :class="`status-tag--${status}`">{{ statusLabel }}</span>
      <span class="task-date">{{ formattedDate }}</span>
    </div>

    <h3 class="task-title">{{ caseItem.title || '未命名案件' }}</h3>
    <p class="task-summary" :class="{ mle: !compact }">{{ summary }}</p>

    <div class="scene-panel">
        <div
          v-for="scene in displayScenes"
          :key="scene.id"
          class="scene-row"
          :class="[`scene-row--${sceneStatus(scene)}`, { 'scene-row--single': isSingleScene }]"
        >
          <div class="scene-main">
            <span class="scene-name">{{ scene.name }}</span>
            <span v-if="isSingleScene" class="scene-description">{{ scene.description || '围绕当前警情开展实操训练' }}</span>
          </div>
          <span class="scene-difficulty" :class="`scene-difficulty--${difficultyLevel(scene.difficulty)}`">
            {{ difficultyLabel(scene.difficulty) }}
          </span>
          <span class="scene-status">{{ sceneStatusLabel(scene) }}</span>
          <div class="scene-actions">
            <template v-if="scene.training_status === 'completed'">
              <el-button
                size="small"
                plain
                class="scene-btn detail-btn"
                :disabled="disabled"
                @click="emit('view-review', scene)"
              >
                查看复盘
              </el-button>
              <el-button
                type="primary"
                size="small"
                class="scene-btn"
                :loading="loadingSceneId === scene.id"
                :disabled="disabled"
                @click="emit('start-scene', scene)"
              >
                重新训练
              </el-button>
            </template>
            <el-button
              v-else
              type="primary"
              size="small"
              class="scene-btn"
              :loading="loadingSceneId === scene.id"
              :disabled="disabled || scene.training_status === 'evaluating'"
              @click="emit('start-scene', scene)"
            >
              {{ sceneActionLabel(scene) }}
            </el-button>
          </div>
        </div>
        <button
          v-if="hasMoreScenes"
          type="button"
          class="scene-expand-btn"
          @click="emit('view-detail')"
        >
          <span>展开全部场景</span>
          <span class="scene-expand-btn__count">+{{ hiddenSceneCount }}</span>
        </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export type TaskSceneItem = {
  id: number
  name: string
  difficulty?: string
  description?: string
  has_active_session?: boolean
  active_session_id?: number | null
  finished_session_id?: number | null
  final_score?: number | null
  training_status?: 'not_started' | 'in_progress' | 'evaluating' | 'completed'
  status_label?: string
}

export type TaskCaseItem = {
  id: number
  title: string
  case_type: string
  background: string
  created_at?: string
  train_count?: number
  scenes?: TaskSceneItem[]
}

const props = defineProps<{
  caseItem: TaskCaseItem
  status: 'active' | 'completed' | 'idle'
  statusLabel: string
  viewMode?: 'grid' | 'list'
  compact?: boolean
  loading?: boolean
  loadingSceneId?: number | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  'start-scene': [scene: TaskSceneItem]
  'view-review': [scene: TaskSceneItem]
  'view-detail': []
}>()

const displayScenes = computed(() => (props.caseItem.scenes || []).slice(0, 4))
const totalScenes = computed(() => (props.caseItem.scenes || []).length)
const hiddenSceneCount = computed(() => Math.max(0, totalScenes.value - displayScenes.value.length))
const hasMoreScenes = computed(() => hiddenSceneCount.value > 0)
const isSingleScene = computed(() => totalScenes.value === 1)

const sceneStatus = (scene: TaskSceneItem) => {
  if (scene.training_status) return scene.training_status
  if (scene.has_active_session) return 'in_progress'
  return 'not_started'
}

const difficultyLabel = (value?: string) => {
  const text = String(value || '').trim()
  if (text.includes('低') || text.includes('简')) return '低'
  if (text.includes('高') || text.includes('困')) return '高'
  return '中'
}

const difficultyLevel = (value?: string) => {
  const label = difficultyLabel(value)
  if (label === '低') return 'low'
  if (label === '高') return 'high'
  return 'medium'
}

const formattedDate = computed(() => {
  const raw = props.caseItem.created_at
  if (!raw) return '--'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw.slice(0, 10)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
})

const summary = computed(() => {
  const text = String(props.caseItem.background || '').trim()
  if (!text) return '当前案件暂无完整背景描述。'
  const max = props.compact ? 40 : 80
  return text.length > max ? `${text.slice(0, max)}...` : text
})

const sceneStatusLabel = (scene: TaskSceneItem) => {
  if (scene.training_status === 'completed') return scene.final_score != null ? `已评分 ${scene.final_score}分` : '已完成训练'
  if (scene.status_label) return scene.status_label
  if (scene.training_status === 'evaluating') return '评估中'
  if (scene.training_status === 'in_progress' || scene.has_active_session) return '可继续'
  return '未开始训练'
}

const sceneActionLabel = (scene: TaskSceneItem) => {
  if (scene.training_status === 'evaluating') return '评估中'
  if (scene.training_status === 'in_progress' || scene.has_active_session) return '继续训练'
  return '开始训练'
}
</script>

<style scoped lang="scss">
.task-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 18px;
  width: 100%;
  height: 380px;
  box-sizing: border-box;
  overflow: hidden;

  &--list {
    height: auto;
    min-height: auto;
  }

  &--compact {
    gap: 3px;
    min-height: 0;
    height: 100%;
    padding: 8px 12px;

    .task-title {
      font-size: 12px;
    }

    .task-summary {
      font-size: 11px;
      height: 18px;
      min-height: auto;
    }

    .scene-panel {
      flex: 1;

      .scene-row {
        min-height: 0;
        max-height: none;
      }
    }
  }
}

.task-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  height: 20px;
  flex-shrink: 0;
  overflow: hidden;
}

.status-tag {
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;

  &--active,
  &--completed {
    color: #047857;
    background: #ecfdf5;
  }

  &--idle {
    color: #c2410c;
    background: #fff7ed;
  }
}

.task-date {
  font-size: 10px;
  color: #9ca3af;
}

.task-title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  color: #111827;
  line-height: 22px;
  height: 22px;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-summary {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
  height: 34px;
  flex-shrink: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

.scene-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
  box-sizing: border-box;
}

.scene-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border-radius: 6px;
  background: #f8fafc;
  padding: 0 10px;
  border: 1px solid #f1f5f9;
}

.scene-row--single {
  align-items: flex-start;
  flex-wrap: wrap;
  padding: 14px;
  background: #f8fafc;
}

.scene-expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-shrink: 0;
  min-height: 32px;
  padding: 0 12px;
  border: 1px dashed #bfdbfe;
  border-radius: 6px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.scene-expand-btn__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 800;
}

.scene-status {
  font-size: 11px;
  color: #9ca3af;
  flex-shrink: 0;
  white-space: nowrap;
}

.scene-difficulty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  min-width: 28px;
  height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;

  &--low {
    color: #047857;
    background: #ecfdf5;
  }

  &--medium {
    color: #b45309;
    background: #fffbeb;
  }

  &--high {
    color: #b91c1c;
    background: #fef2f2;
  }
}

.scene-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.scene-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.scene-name {
  min-width: 0;
  font-size: 12px;
  color: #4b5563;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

.scene-description {
  display: -webkit-box;
  max-width: 100%;
  overflow: hidden;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

.scene-btn {
  flex-shrink: 0;
  padding: 4px 10px !important;
  height: 26px !important;
  font-size: 12px !important;
}

.detail-btn {
  color: var(--student-accent, #0066ff) !important;
  border-color: #b3d4ff !important;
}
</style>
