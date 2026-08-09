<template>
  <div class="student-page training-center-page">
    <section class="training-panel">
      <div class="training-panel__head">
        <div class="training-tabs" role="tablist" aria-label="训练类型">
          <button
            v-for="tab in trainingTabs"
            :key="tab.value"
            type="button"
            role="tab"
            :aria-selected="trainingTab === tab.value"
            class="training-tab"
            :class="{ 'training-tab--active': trainingTab === tab.value }"
            @click="setTrainingTab(tab.value)"
          >
            <el-icon><component :is="tab.icon" /></el-icon>
            {{ tab.label }}
            <span>{{ tab.count }}</span>
          </button>
        </div>
        <el-select
          v-model="statusFilter"
          size="small"
          class="status-select"
          placeholder="全部状态"
          :teleported="false"
        >
          <el-option label="全部状态" value="all" />
          <el-option label="进行中" value="active" />
          <el-option label="待开始" value="idle" />
          <el-option label="已完成" value="completed" />
        </el-select>
      </div>


      <div v-if="loading" class="state-panel">
        <el-skeleton :rows="6" animated />
      </div>
      <div v-else-if="activeItems.length === 0" class="state-panel">
        <el-empty description="当前没有匹配的训练内容">
          <el-button type="primary" @click="resetFilters">清除筛选</el-button>
        </el-empty>
      </div>
      <div v-else class="training-content">
        <div v-if="trainingTab === 'video'" class="video-grid">
          <article v-for="video in visibleVideos" :key="video.id" class="video-card">
            <button type="button" class="video-cover" @click="openVideo(video)">
              <img v-if="coverFor(video)" :src="coverFor(video)" :alt="video.title" @error="markVideoCoverFailed(video)" />
              <span v-else class="video-cover__placeholder"><el-icon><VideoPlay /></el-icon></span>
              <span class="video-type">{{ video.video_type === 'interactive' ? '交互实训' : '教学素材' }}</span>
              <span v-if="video.duration" class="video-duration">{{ formatDuration(video.duration) }}</span>
            </button>
            <div class="video-body">
              <div class="card-title-row">
                <h3>{{ video.title }}</h3>
                <el-tag size="small" effect="plain">{{ video.video_type === 'interactive' ? '视频' : '学习' }}</el-tag>
              </div>
              <p>{{ video.description || '进入视频内容，按节点完成学习或实训。' }}</p>
              <div class="card-meta">
                <span>{{ video.node_count || 0 }} 个节点</span>
                <span>{{ difficultyLabel(video) }}</span>
              </div>
              <div class="card-progress">
                <div class="progress-label">
                  <span>{{ videoProgressText(video) }}</span>
                  <b>{{ videoProgress(video) }}%</b>
                </div>
                <el-progress :percentage="videoProgress(video)" :show-text="false" :stroke-width="6" />
              </div>
              <el-button type="primary" class="card-action" @click="openVideo(video)">
                {{ videoActionLabel(video) }}
              </el-button>
            </div>
          </article>
        </div>


        <div v-else class="case-grid">
          <article v-for="item in visibleCases" :key="item.id" class="case-card">
            <div class="case-card__top">
              <span class="case-status" :class="`case-status--${caseStatus(item)}`">{{ caseBadgeLabel(item) }}</span>
              <span class="case-date">{{ formatDate(item.created_at) }}</span>
            </div>
            <div v-if="trainingTab === 'tasks'" class="assignment-meta">
              <span>{{ item.class_name || '班级任务' }}</span>
              <span>{{ item.assignment_title || '未命名作业' }}</span>
              <span v-if="item.due_at">截止 {{ formatDate(item.due_at) }}</span>
            </div>

            <h3>{{ item.title || '未命名训练案件' }}</h3>
            <p>{{ item.background || '围绕案件脚本、现场角色和处置阶段开展 AI 对话训练。' }}</p>

            <div class="scene-list">
              <div v-for="scene in visibleScenesForCase(item)" :key="scene.id" class="scene-row">
                <div class="scene-info">
                  <strong>{{ scene.name || '未命名场景' }}</strong>
                  <span class="difficulty-pill" :class="`difficulty-pill--${difficultyTone(scene.difficulty)}`">
                    {{ difficultyText(scene.difficulty) }}
                  </span>
                  <span class="scene-state">{{ sceneStatusLabel(scene) }}</span>
                </div>
                <div class="scene-actions">
                  <el-button
                    v-if="sceneStatus(scene) === 'completed'"
                    size="small"
                    plain
                    @click="viewSceneReview(scene)"
                  >
                    查看复盘
                  </el-button>
                  <el-button
                    type="primary"
                    size="small"
                    :loading="loadingSceneId === scene.id"
                    @click="startScene(scene)"
                  >
                    {{ sceneActionLabel(scene) }}
                  </el-button>
                </div>
              </div>
            </div>

            <button
              v-if="hiddenSceneCount(item) > 0"
              type="button"
              class="expand-scenes"
              @click="toggleCaseExpanded(item.id)"
            >
              {{ isCaseExpanded(item.id) ? '收起场景' : '展开全部场景' }}
              <span v-if="!isCaseExpanded(item.id)">+{{ hiddenSceneCount(item) }}</span>
            </button>
          </article>
        </div>
        <div v-if="false" class="task-list">
          <article v-for="item in visibleCases" :key="item.id" class="task-card">
            <div class="task-type-icon" :class="{ 'task-type-icon--active': caseStatus(item) === 'active' }">
              <el-icon><component :is="trainingTab === 'tasks' ? Document : ChatDotRound" /></el-icon>
            </div>
            <div class="task-main">
              <div class="card-title-row">
                <h3>{{ item.title || '未命名训练案件' }}</h3>
                <el-tag size="small" effect="plain">{{ item.case_type || '文字训练' }}</el-tag>
                <el-tag size="small" :type="caseTagType(item)" effect="light">{{ caseStatusLabel(item) }}</el-tag>
              </div>
              <p>{{ item.background || '围绕案件脚本、现场角色和处置阶段开展 AI 对话训练。' }}</p>
              <div class="task-meta">
                <span><el-icon><Files /></el-icon>{{ item.scenes?.length || 0 }} 个训练场景</span>
                <span><el-icon><Clock /></el-icon>预计 20-35 分钟</span>
                <span><el-icon><DataAnalysis /></el-icon>{{ completedSceneCount(item) }}/{{ item.scenes?.length || 0 }} 已完成</span>
              </div>
              <el-progress :percentage="caseProgress(item)" :show-text="false" :stroke-width="6" />
            </div>
            <div class="task-actions">
              <span class="task-date">{{ caseStatus(item) === 'active' ? '继续上次训练' : '可随时开始' }}</span>
              <el-button type="primary" size="small" @click="startCase(item)">
                {{ caseStatus(item) === 'active' ? '继续训练' : '查看场景' }}
              </el-button>
            </div>
          </article>
        </div>
      </div>
    </section>
  </div>
</template>


<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Clock, DataAnalysis, Document, Files, VideoPlay } from '@element-plus/icons-vue'
import request from '../utils/request'
import { fetchStudentCases } from '../utils/studentCases'
import { useVideoCover } from '../composables/useVideoCover'


interface SceneItem {
  id: number
  name: string
  difficulty?: string
  training_status?: string
  has_active_session?: boolean
  active_session_id?: number | null
  finished_session_id?: number | null
  assignment_id?: number | null

}


interface CaseItem {
  id: number
  title: string
  case_type?: string
  background?: string
  created_at?: string
  scenes?: SceneItem[]
  assignment_id?: number | null
  assignment_title?: string
  class_name?: string
  due_at?: string

}


interface VideoItem {
  id: number
  title: string
  description?: string
  video_type: 'teaching' | 'interactive'
  thumbnail_url?: string
  duration?: number
  node_count: number
  tags?: string[]
  teaching_unlocked?: boolean
  lock_reason?: string | null
  created_at?: string

}


interface SessionBrief {
  id: number
  video_id: number
  status: string
  current_node_index: number
  node_total: number

}


const route = useRoute()
const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')
const { ensureVideoCovers, getVideoCover, markVideoCoverFailed } = useVideoCover()


const loading = ref(true)
const taskCases = ref<CaseItem[]>([])
const cases = ref<CaseItem[]>([])
const videos = ref<VideoItem[]>([])
const videoSessions = ref<Record<number, SessionBrief>>({})
const loadingSceneId = ref<number | null>(null)
const expandedCaseIds = ref<Set<number>>(new Set())
const keyword = ref('')
const statusFilter = ref<'all' | 'active' | 'idle' | 'completed'>('all')
const trainingTab = ref<'tasks' | 'free' | 'video'>(route.query.tab === 'video' ? 'video' : route.query.tab === 'free' ? 'free' : 'tasks')


const taskScenes = computed(() => taskCases.value.flatMap((item) => item.scenes || []))
const freeScenes = computed(() => cases.value.flatMap((item) => item.scenes || []))
const activeSceneCount = computed(() => taskScenes.value.filter((scene) => sceneStatus(scene) === 'active').length)
const completedSceneTotal = computed(() => taskScenes.value.filter((scene) => sceneStatus(scene) === 'completed').length)
const activeVideoCount = computed(() => Object.values(videoSessions.value).filter((item) => item.status === 'active').length)
const pendingCount = computed(() => taskScenes.value.filter((scene) => sceneStatus(scene) === 'idle').length)
const completedCount = computed(() => completedSceneTotal.value + Object.values(videoSessions.value).filter((item) => item.status === 'finished').length)


const trainingSummary = computed(() => [
  { label: '待完成任务', value: pendingCount.value, description: '可从任务中心开始' },
  { label: '可自由训练', value: freeScenes.value.length + videos.value.length, description: `文字 ${freeScenes.value.length} · 视频 ${videos.value.length}` },
  { label: '可恢复会话', value: activeSceneCount.value + activeVideoCount.value, description: '上次未完成的训练' },
  { label: '已完成训练', value: completedCount.value, description: '持续积累训练记录' },

])


const trainingTabs = computed(() => [
  { value: 'tasks' as const, label: '我的任务', icon: Document, count: taskCases.value.length },
  { value: 'free' as const, label: '自由训练', icon: ChatDotRound, count: freeScenes.value.length },
  { value: 'video' as const, label: '视频实训', icon: VideoPlay, count: videos.value.length },

])


const visibleCases = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  const source = trainingTab.value === 'tasks' ? taskCases.value : cases.value
  return source.filter((item) => {
    const matchesKeyword = !text || [item.title, item.case_type, item.background, item.assignment_title, item.class_name].join(' ').toLowerCase().includes(text)
    const status = caseStatus(item)
    const matchesStatus = statusFilter.value === 'all' || statusFilter.value === status
    return matchesKeyword && matchesStatus
  })

})


const visibleVideos = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return videos.value.filter((item) => {
    const session = videoSessions.value[item.id]
    const status = session?.status === 'active' ? 'active' : session?.status === 'finished' ? 'completed' : 'idle'
    const matchesKeyword = !text || [item.title, item.description, ...(item.tags || [])].join(' ').toLowerCase().includes(text)
    const matchesStatus = statusFilter.value === 'all' || statusFilter.value === status
    return matchesKeyword && matchesStatus
  })

})


const activeItems = computed(() => trainingTab.value === 'video' ? visibleVideos.value : visibleCases.value)


watch(() => route.query.tab, (tab) => {
  trainingTab.value = tab === 'video' ? 'video' : tab === 'free' ? 'free' : 'tasks'

})


function setTrainingTab(tab: 'tasks' | 'free' | 'video') {
  trainingTab.value = tab
  router.replace({ query: tab === 'tasks' ? {} : { tab } })

}


function sceneStatus(scene: SceneItem): 'active' | 'completed' | 'idle' {
  if (scene.training_status === 'completed' || scene.finished_session_id) return 'completed'
  if (scene.training_status === 'in_progress' || scene.training_status === 'evaluating' || scene.has_active_session) return 'active'
  return 'idle'

}


function caseStatus(item: CaseItem) {
  const statuses = (item.scenes || []).map(sceneStatus)
  if (statuses.some((status) => status === 'active')) return 'active'
  if (statuses.length && statuses.every((status) => status === 'completed')) return 'completed'
  return 'idle'

}


function caseStatusLabel(item: CaseItem) {
  return { active: '进行中', completed: '已完成', idle: '待开始' }[caseStatus(item)]

}


function caseBadgeLabel(item: CaseItem) {
  const status = caseStatus(item)
  if (status === 'active') return '继续训练'
  if (status === 'completed') return '已完成'
  return '未开始'

}


function caseTagType(item: CaseItem) {
  return caseStatus(item) === 'completed' ? 'success' : caseStatus(item) === 'active' ? 'warning' : 'info'

}


function completedSceneCount(item: CaseItem) {
  return (item.scenes || []).filter((scene) => sceneStatus(scene) === 'completed').length

}


function caseProgress(item: CaseItem) {
  const total = item.scenes?.length || 0
  return total ? Math.round((completedSceneCount(item) / total) * 100) : 0

}


function isCaseExpanded(caseId: number) {
  return expandedCaseIds.value.has(caseId)

}


function toggleCaseExpanded(caseId: number) {
  const next = new Set(expandedCaseIds.value)
  if (next.has(caseId)) next.delete(caseId)
  else next.add(caseId)
  expandedCaseIds.value = next

}


function scenesForCase(item: CaseItem) {
  return item.scenes || []

}


function visibleScenesForCase(item: CaseItem) {
  const scenes = scenesForCase(item)
  return isCaseExpanded(item.id) ? scenes : scenes.slice(0, 3)

}


function hiddenSceneCount(item: CaseItem) {
  return Math.max(0, scenesForCase(item).length - visibleScenesForCase(item).length)

}


function formatDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10)
  return date.toISOString().slice(0, 10)

}


function difficultyText(value?: string) {
  const text = String(value || '').trim()
  if (/高|难|困/.test(text)) return '高'
  if (/低|简|易/.test(text)) return '低'
  return '中'

}


function difficultyTone(value?: string) {
  return difficultyText(value) === '高' ? 'high' : difficultyText(value) === '低' ? 'low' : 'medium'

}


function sceneStatusLabel(scene: SceneItem) {
  const status = sceneStatus(scene)
  if (status === 'completed') return '已评分'
  if (status === 'active') return '继续训练'
  return '未开始训练'

}


function sceneActionLabel(scene: SceneItem) {
  const status = sceneStatus(scene)
  if (status === 'active') return '继续训练'
  if (status === 'completed') return '重新训练'
  return '开始训练'

}


function viewSceneReview(scene: SceneItem) {
  const sessionId = Number(scene.finished_session_id || scene.active_session_id)
  if (!sessionId) {
    ElMessage.info('该场景暂无可查看的复盘记录')
    return
  }
  const assignmentQuery = scene.assignment_id ? `&assignment_id=${scene.assignment_id}` : ''
  router.push(`/student/evaluation?session_id=${sessionId}${assignmentQuery}`)

}


async function startScene(scene: SceneItem) {
  if (scene.active_session_id && sceneStatus(scene) === 'active') {
    const assignmentQuery = scene.assignment_id ? `?assignment_id=${scene.assignment_id}` : ''
    router.push(`/student/training/${scene.active_session_id}${assignmentQuery}`)
    return
  }

  loadingSceneId.value = scene.id
  try {
    const requestConfig = scene.assignment_id
      ? { params: { assignment_id: scene.assignment_id }, _skipErrorToast: true }
      : { _skipErrorToast: true }
    const res: any = await request.post(`/training/start/${scene.id}`, null, requestConfig as any)
    if (!res?.id) throw new Error('训练初始化失败')
    const assignmentQuery = scene.assignment_id ? `?assignment_id=${scene.assignment_id}` : ''
    router.push(`/student/training/${res.id}${assignmentQuery}`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '训练初始化失败，请稍后重试')
  } finally {
    loadingSceneId.value = null
  }

}


function startCase(item: CaseItem) {
  const scene = (item.scenes || []).find((entry) => sceneStatus(entry) === 'active') || (item.scenes || [])[0]
  if (scene?.active_session_id) {
    const assignmentQuery = scene.assignment_id ? `?assignment_id=${scene.assignment_id}` : ''
    router.push(`/student/training/${scene.active_session_id}${assignmentQuery}`)
    return
  }
  setTrainingTab('free')

}


function openVideo(video: VideoItem) {
  if (video.video_type === 'teaching') {
    if (video.teaching_unlocked === false) {
      ElMessage.info(video.lock_reason || '需先完成关联实训后解锁该教学素材')
      return
    }
    router.push('/student/videos')
    return
  }
  router.push(`/student/video-training/${video.id}`)

}


function videoProgress(video: VideoItem) {
  const session = videoSessions.value[video.id]
  if (!session) return 0
  if (session.status === 'finished') return 100
  return session.node_total ? Math.min(100, Math.round((session.current_node_index / session.node_total) * 100)) : 0

}


function videoProgressText(video: VideoItem) {
  const session = videoSessions.value[video.id]
  if (!session) return '未开始'
  return session.status === 'active' ? `已进行到 ${session.current_node_index}/${session.node_total} 节点` : '已完成'

}


function videoActionLabel(video: VideoItem) {
  const session = videoSessions.value[video.id]
  if (video.video_type === 'teaching') return session ? '查看视频' : '开始学习'
  return session?.status === 'active' ? '继续训练' : '进入训练'

}


function coverFor(video: VideoItem) {
  return getVideoCover(video)

}


function difficultyLabel(video: VideoItem) {
  const source = [video.title, video.description, ...(video.tags || [])].join(' ')
  if (/困难|高级|复杂/.test(source)) return '高难度'
  if (/中等|标准|进阶/.test(source)) return '中等难度'
  return '基础难度'

}


function formatDuration(seconds?: number) {
  if (!seconds) return ''
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

}


function normalizeAssignmentCase(rawCase: any, assignment: any): CaseItem {
  const assignmentId = Number(assignment?.id || rawCase?.assignment_id || 0) || null
  const scenes = Array.isArray(rawCase?.scenes) ? rawCase.scenes : []
  return {
    ...rawCase,
    id: Number(rawCase?.id || rawCase?.case_id || 0),
    title: rawCase?.title || rawCase?.case_title || '未命名班级任务',
    case_type: rawCase?.case_type || assignment?.title || '班级任务',
    background: rawCase?.background || rawCase?.description || assignment?.instructions || '',
    created_at: assignment?.published_at || assignment?.created_at || rawCase?.created_at,
    assignment_id: assignmentId,
    assignment_title: assignment?.title || '',
    class_name: assignment?.class_name || '',
    due_at: assignment?.due_at || '',
    scenes: scenes.map((scene: any) => ({
      ...scene,
      id: Number(scene?.id || scene?.scene_id || 0),
      name: scene?.name || scene?.scene_name || '未命名场景',
      assignment_id: assignmentId,
    })),
  }
}


async function fetchStudentTaskCases() {
  const assignments: any = await request.get('/classes/student/assignments', { _skipErrorToast: true } as any)
  const rows = Array.isArray(assignments) ? assignments : []
  const detailRows = await Promise.all(rows.map(async (assignment: any) => {
    if (Array.isArray(assignment?.cases) && assignment.cases.length) return assignment
    try {
      return await request.get(`/classes/student/assignments/${assignment.id}`, { _skipErrorToast: true } as any)
    } catch {
      return assignment
    }
  }))
  return detailRows.flatMap((assignment: any) => {
    const assignmentCases = Array.isArray(assignment?.cases) ? assignment.cases : []
    return assignmentCases.map((item: any) => normalizeAssignmentCase(item, assignment)).filter((item: CaseItem) => item.id)
  })
}


function resetFilters() {
  keyword.value = ''
  statusFilter.value = 'all'

}


async function fetchAllLegacy() {
  loading.value = true
  try {
    const [casesRes, videosRes, historyRes] = await Promise.all([
      request.get('/student/cases', { _skipErrorToast: true } as any),
      request.get('/videos/student/hall', { _skipErrorToast: true } as any),
      request.get('/video-training/history', { params: { page: 1, page_size: 100 }, _skipErrorToast: true } as any),
    ])
    const casesData: any = casesRes
    const videosData: any = videosRes
    const historyData: any = historyRes
    taskCases.value = []
    cases.value = Array.isArray(casesData) ? casesData : []
    videos.value = Array.isArray(videosData) ? videosData : []
    await ensureVideoCovers(videos.value)
    const sessions = Array.isArray(historyData?.items) ? historyData.items : Array.isArray(historyData) ? historyData : []
    videoSessions.value = sessions.reduce((map: Record<number, SessionBrief>, item: SessionBrief) => {
      if (item?.video_id && (!map[item.video_id] || item.status === 'active')) map[item.video_id] = item
      return map
    }, {})
  } catch {
    taskCases.value = []
    cases.value = []
    videos.value = []
    videoSessions.value = {}
    ElMessage.error('训练内容加载失败，请稍后重试')
  } finally {
    loading.value = false
  }

}


async function fetchAll() {
  loading.value = true

  const [taskCasesResult, casesResult, videosResult, historyResult] = await Promise.allSettled([
    fetchStudentTaskCases(),
    fetchStudentCases(),
    request.get('/videos/student/hall', { _skipErrorToast: true } as any),
    request.get('/video-training/history', { params: { page: 1, page_size: 100 }, _skipErrorToast: true } as any),
  ])

  if (taskCasesResult.status === 'fulfilled') {
    taskCases.value = taskCasesResult.value
  } else {
    taskCases.value = []
    ElMessage.error('班级任务加载失败，请稍后重试')
  }

  if (casesResult.status === 'fulfilled') {
    const casesData: any = casesResult.value
    cases.value = Array.isArray(casesData) ? casesData : []
  } else {
    cases.value = []
    ElMessage.error('普通训练加载失败，请稍后重试')
  }

  if (videosResult.status === 'fulfilled') {
    const videosData: any = videosResult.value
    videos.value = Array.isArray(videosData) ? videosData : []
    try {
      await ensureVideoCovers(videos.value)
    } catch {
      // 封面加载失败不影响训练列表展示。
    }
  } else {
    videos.value = []
  }

  if (historyResult.status === 'fulfilled') {
    const historyData: any = historyResult.value
    const sessions = Array.isArray(historyData?.items) ? historyData.items : Array.isArray(historyData) ? historyData : []
    videoSessions.value = sessions.reduce((map: Record<number, SessionBrief>, item: SessionBrief) => {
      if (item?.video_id && (!map[item.video_id] || item.status === 'active')) map[item.video_id] = item
      return map
    }, {})
  } else {
    videoSessions.value = {}
  }

  loading.value = false

}


onMounted(() => {
  setMainScrollable?.(true)
  fetchAll()

})
</script>


<style scoped lang="scss">
.training-center-page {
  min-height: 100%;
  padding: 22px;
  color: #17213b;
  background: #f3f6fa;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.training-panel {
  position: relative;
  overflow: visible;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(35, 56, 104, 0.06);

}


.training-panel__head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px 0;
  border-bottom: 1px solid #edf1f6;
  position: relative;
  z-index: 5;

}


.training-tabs {
  display: flex;
  align-items: center;
  flex: 1;
  gap: 4px;
  min-width: 0;

}


.training-tab {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 42px;
  padding: 0 12px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #7c8798;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;

}


.training-tab span {
  color: #a0aaba;
  font-size: 11px;
  font-weight: 500;

}


.training-tab--active {
  border-bottom-color: #3566f6;
  color: #3566f6;

}


.status-select {
  flex: 0 0 120px;
  width: 120px;
  margin-bottom: 10px;
  position: relative;

}


.training-content {
  padding: 16px;

}


.case-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;

}


.case-card {
  min-width: 0;
  padding: 18px;
  border: 1px solid #e5ebf5;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 14px rgba(35, 56, 104, 0.04);

}


.case-card:hover {
  border-color: #cbd8f6;
  box-shadow: 0 8px 22px rgba(35, 56, 104, 0.07);

}


.case-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;

}


.case-status {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border: 1px solid #dbe6ff;
  border-radius: 8px;
  background: #eef4ff;
  color: #3566f6;
  font-size: 12px;
  font-weight: 800;

}


.case-status--idle {
  border-color: #ffe4b8;
  background: #fff7e8;
  color: #d97904;

}


.case-status--completed {
  border-color: #d6f4df;
  background: #eefbf2;
  color: #17904c;

}


.case-date {
  color: #8090a8;
  font-size: 13px;

}


.assignment-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: -4px 0 12px;
  color: #6b7c95;
  font-size: 12px;

}


.assignment-meta span {
  max-width: 100%;
  padding: 3px 8px;
  overflow: hidden;
  border-radius: 6px;
  background: #f3f6fb;
  text-overflow: ellipsis;
  white-space: nowrap;

}


.case-card h3 {
  margin: 0;
  overflow: hidden;
  color: #17213b;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;

}


.case-card p {
  display: -webkit-box;
  min-height: 48px;
  margin: 14px 0 16px;
  overflow: hidden;
  color: #6f7f95;
  font-size: 13px;
  line-height: 1.8;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;

}


.scene-list {
  display: grid;
  gap: 10px;

}


.scene-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-height: 66px;
  padding: 12px;
  border: 1px solid #edf1f6;
  border-radius: 8px;
  background: #fafbfe;

}


.scene-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;

}


.scene-info strong {
  min-width: 0;
  overflow: hidden;
  color: #253047;
  font-size: 14px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;

}


.difficulty-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 24px;
  padding: 0 8px;
  border-radius: 8px;
  background: #fff4d8;
  color: #c76a00;
  font-size: 12px;
  font-weight: 800;
  flex-shrink: 0;

}


.difficulty-pill--high {
  background: #fff0f0;
  color: #d93025;

}


.difficulty-pill--low {
  background: #eafbf1;
  color: #12924d;

}


.scene-state {
  color: #8b96aa;
  font-size: 13px;
  white-space: nowrap;

}


.scene-actions {
  display: flex;
  align-items: center;
  gap: 8px;

}


.expand-scenes {
  width: 100%;
  min-height: 36px;
  margin-top: 10px;
  border: 1px dashed #cfe0ff;
  border-radius: 8px;
  background: #f3f7ff;
  color: #3566f6;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;

}


.expand-scenes span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 22px;
  margin-left: 8px;
  border-radius: 8px;
  background: #dbe8ff;

}


.task-list,
.video-grid {
  display: grid;
  gap: 12px;

}


.task-card {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 15px;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #fff;

}


.task-card:hover,
.video-card:hover {
  border-color: #cbd8f6;
  box-shadow: 0 8px 22px rgba(35, 56, 104, 0.07);

}


.task-type-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: #eef3ff;
  color: #3566f6;
  font-size: 20px;

}


.task-type-icon--active {
  background: #fff3e4;
  color: #e08322;

}


.task-main,
.video-body {
  min-width: 0;

}


.card-title-row {
  flex-wrap: wrap;
  gap: 7px;

}


.card-title-row h3 {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: #253047;
  font-size: 14px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;

}


.task-main p,
.video-body p {
  display: -webkit-box;
  margin: 8px 0;
  overflow: hidden;
  color: #7c8798;
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;

}


.task-meta,
.card-meta {
  flex-wrap: wrap;
  gap: 14px;
  color: #8b96aa;
  font-size: 11px;

}


.task-meta span,
.card-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;

}


.task-main :deep(.el-progress),
.card-progress :deep(.el-progress) {
  margin-top: 10px;

}


.task-actions {
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  min-width: 104px;

}


.task-date {
  color: #a0aaba;
  font-size: 11px;
  white-space: nowrap;

}


.video-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));

}


.video-card {
  overflow: hidden;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #fff;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;

}


.video-cover {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border: 0;
  background: #0f2b63;
  cursor: pointer;

}


.video-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;

}


.video-cover__placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: rgba(255, 255, 255, 0.8);
  font-size: 28px;

}


.video-type,
.video-duration {
  position: absolute;
  bottom: 9px;
  padding: 4px 7px;
  border-radius: 4px;
  color: #fff;
  font-size: 10px;

}


.video-type {
  top: 9px;
  right: 9px;
  bottom: auto;
  background: rgba(37, 99, 235, 0.88);

}


.video-duration {
  right: 9px;
  background: rgba(2, 6, 23, 0.7);

}


.video-body {
  padding: 14px;

}


.video-body .card-title-row {
  justify-content: space-between;
  align-items: flex-start;

}


.video-body .card-title-row h3 {
  white-space: normal;

}


.progress-label {
  justify-content: space-between;
  color: #8b96aa;
  font-size: 11px;

}


.progress-label b {
  color: #3566f6;

}


.card-action {
  width: 100%;
  margin-top: 14px;

}


.state-panel {
  padding: 48px 20px;

}


@media (max-width: 1180px) {

  .video-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

}


@media (max-width: 760px) {
  .training-center-page {
    padding: 14px;
  }
.video-grid {
    grid-template-columns: 1fr;
  }


  .training-panel__head {
    align-items: stretch;
    flex-direction: column;
    gap: 8px;
    padding-bottom: 10px;
  }


  .training-tabs {
    overflow-x: auto;
  }


  .status-select {
    flex-basis: auto;
    width: 100%;
    margin-bottom: 0;
  }


  .task-card {
    grid-template-columns: 38px minmax(0, 1fr);
  }


  .task-actions {
    grid-column: 2;
    align-items: flex-start;
  }

}
</style>




