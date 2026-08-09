<template>
  <article class="task-card" :class="{ 'task-card--list': viewMode === 'list' }">
    <section class="task-card__main" aria-label="案件训练概要">
      <div class="task-card__topline">
        <span class="task-card__difficulty" :class="`task-card__difficulty--${difficultyLevel}`">
          <i aria-hidden="true" />
          {{ difficultyLabel }}
        </span>
        <span class="task-card__date">
          <el-icon><Clock /></el-icon>
          {{ formattedDate }}
        </span>
      </div>

      <div class="task-card__content">
        <h3>{{ caseItem.title || '未命名案件' }}</h3>
        <p class="task-card__summary">{{ summary }}</p>
      </div>
    </section>

    <section class="task-card__footer">
      <div class="task-card__meta" aria-label="训练配置">
        <span>
          <el-icon><Clock /></el-icon>
          {{ estimatedTimeText }}
        </span>
        <span>
          <el-icon>
            <UserFilled v-if="isTeamTraining" />
            <User v-else />
          </el-icon>
          {{ modeText }}
        </span>
      </div>

      <button class="task-card__button" type="button" :disabled="disabled" @click="emit('start-case', caseItem)">
        <span>{{ actionLabel }}</span>
        <el-icon><Right /></el-icon>
      </button>
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Clock, Right, User, UserFilled } from '@element-plus/icons-vue'

export type TaskSceneItem = {
  id: number
  name: string
  difficulty?: string
  estimated_minutes?: number | null
  description?: string
  dispatch_brief?: string | null
  first_impression?: string | null
  stages?: any[]
  has_active_session?: boolean
  active_session_id?: number | null
  active_session_is_empty?: boolean
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
  scene_count?: number
  primary_difficulty?: string
  estimated_minutes_summary?: string | null
  core_items?: string[]
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
  'start-case': [caseItem: TaskCaseItem]
}>()

const scenes = computed(() => Array.isArray(props.caseItem.scenes) ? props.caseItem.scenes : [])

const normalizeDifficulty = (value?: string) => {
  const text = String(value || '').trim().toLowerCase()
  if (text.includes('低') || text.includes('简') || text.includes('easy') || text.includes('low')) return '低'
  if (text.includes('高') || text.includes('困') || text.includes('hard') || text.includes('high')) return '高'
  return '中'
}

const difficultyText = computed(() => normalizeDifficulty(props.caseItem.primary_difficulty || scenes.value[0]?.difficulty))
const difficultyLevel = computed(() => difficultyText.value === '低' ? 'low' : difficultyText.value === '高' ? 'high' : 'medium')
const difficultyLabel = computed(() => {
  if (difficultyText.value === '低') return '低 (Low)'
  if (difficultyText.value === '高') return '高 (High)'
  return '中 (Medium)'
})

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
  return text.length > 66 ? `${text.slice(0, 66)}...` : text
})

const estimatedTimeText = computed(() => {
  const summaryText = String(props.caseItem.estimated_minutes_summary || '').trim()
  if (summaryText) return summaryText.replace(/分钟/g, 'mins')
  const minutes = scenes.value.find((scene) => Number(scene.estimated_minutes) > 0)?.estimated_minutes
  return minutes ? `${minutes} mins` : '待定'
})
const isTeamTraining = computed(() => Number(props.caseItem.scene_count || scenes.value.length || 0) > 1)
const modeText = computed(() => isTeamTraining.value ? 'Team' : 'Solo')
const actionLabel = computed(() => props.status === 'active' ? '继续训练' : props.status === 'completed' ? '重新训练' : '开始训练')
</script>

<style scoped lang="scss">
.task-card {
  position: relative;
  display: flex;
  width: 100%;
  max-width: calc(100vw - 32px);
  min-height: 292px;
  flex-direction: column;
  overflow: hidden;
  border: none;
  border-radius: 20px;
  background: #f7f7f2;
  box-shadow:
    10px 10px 20px rgb(0 0 0 / 7%),
    -10px -10px 20px #fff;
  transition: transform 220ms ease, box-shadow 220ms ease;
}

.task-card:hover {
  transform: translateY(-2px);
  box-shadow:
    12px 12px 24px rgb(0 0 0 / 8%),
    -10px -10px 20px #fff;
}

.task-card__main {
  display: flex;
  flex-direction: column;
  min-height: 178px;
  padding: 24px 26px 20px;
  overflow: hidden;
  border-bottom: 1px solid rgb(226 226 218 / 66%);
  background: #f7f7f2;
}

.task-card__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  margin-bottom: 28px;
}

.task-card__difficulty {
  display: inline-flex;
  max-width: 52%;
  min-height: 30px;
  align-items: center;
  gap: 7px;
  padding: 6px 13px;
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 70%);
  border-radius: 999px;
  background: rgb(255 255 255 / 46%);
  box-shadow: 2px 2px 5px rgb(0 0 0 / 5%);
  color: #1f2937;
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-card__difficulty i {
  width: 10px;
  height: 10px;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #eab308;
  box-shadow: 0 0 0 3px rgb(234 179 8 / 12%);
}

.task-card__difficulty--low i {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgb(34 197 94 / 12%);
}

.task-card__difficulty--high i {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgb(239 68 68 / 12%);
}

.task-card__date {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  color: #64748b;
  font-size: 16px;
  font-weight: 650;
  line-height: 1;
  white-space: nowrap;
}

.task-card__content {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.task-card__content h3 {
  display: -webkit-box;
  min-height: 34px;
  margin: 0;
  overflow: hidden;
  color: #061936;
  font-size: 26px;
  font-weight: 900;
  line-height: 1.24;
  letter-spacing: 0;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  word-break: break-word;
}

.task-card__summary {
  display: -webkit-box;
  min-height: 42px;
  margin: 0;
  overflow: hidden;
  color: #41556f;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.36;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  word-break: break-word;
}

.task-card__footer {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 26px 26px;
}

.task-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 22px;
  min-width: 0;
  color: #34465e;
  font-size: 16px;
  font-weight: 650;
}

.task-card__meta span {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.task-card__button {
  display: inline-flex;
  width: 100%;
  min-height: 56px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: auto;
  border: none;
  border-radius: 14px;
  background: #f7f7f2;
  box-shadow:
    8px 8px 16px rgb(0 0 0 / 6%),
    -8px -8px 16px #fff;
  color: #061936;
  cursor: pointer;
  font-size: 18px;
  font-weight: 900;
  line-height: 1;
  transition: transform 180ms ease, box-shadow 180ms ease;
}

.task-card__button:hover:not(:disabled) {
  transform: translateY(1px);
  box-shadow:
    inset 6px 6px 12px rgb(0 0 0 / 6%),
    inset -6px -6px 12px #fff;
}

.task-card__button:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.task-card--list {
  width: 100%;
}

@media (max-width: 640px) {
  .task-card {
    min-height: 334px;
  }

  .task-card__main,
  .task-card__footer {
    padding: 24px;
  }

  .task-card__topline {
    margin-bottom: 28px;
  }

  .task-card__difficulty {
    max-width: 58%;
    min-height: 34px;
    padding: 7px 12px;
    font-size: 14px;
  }

  .task-card__date,
  .task-card__summary,
  .task-card__meta {
    font-size: 16px;
  }

  .task-card__content h3 {
    min-height: 36px;
    font-size: 26px;
  }

  .task-card__button {
    min-height: 60px;
    font-size: 18px;
  }
}
</style>
